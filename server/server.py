import asyncio
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
DEVICES_FILE = DATA_DIR / "devices.json"
FILES_DIR = DATA_DIR / "files"
TOKENS_FILE = DATA_DIR / "tokens.json"


def parse_size(size_str: Optional[str]) -> int:
    """Parse human readable size strings (e.g., '10MB', '1GB') to bytes."""
    if not size_str:
        return 100 * 1024 * 1024  # Default 100MB

    if isinstance(size_str, int):
        return size_str

    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?$", str(size_str).strip().upper())
    if not match:
        return 100 * 1024 * 1024  # Fallback

    number, unit = match.groups()
    number = float(number)
    unit = unit or "B"

    if unit not in units and unit.rstrip("S") in units:
        unit = unit.rstrip("S")

    multiplier = units.get(unit, 1)
    return int(number * multiplier)


# Configuration Loading
def load_server_config() -> Dict[str, Any]:
    config_path = BASE_DIR / "config.toml"
    config = {
        "host": "0.0.0.0",
        "port": 8000,
        "auto_register_devices": True,
        "enable_firmware_server": False,
        "firmware_port": 5000,
        "max_file_size": "100MB",
        "enable_auth": False,
        "accounts": [
            {
                "email": "admin@example.com",
                "password": "admin",
                "nickname": "Administrator",
            }
        ],
    }
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                toml_data = tomllib.load(f)

                # Flatten TOML structure to match expected config keys

                # [server]
                if "server" in toml_data:
                    if "host" in toml_data["server"]:
                        config["host"] = toml_data["server"]["host"]
                    if "port" in toml_data["server"]:
                        config["port"] = toml_data["server"]["port"]
                    if "auto_register_devices" in toml_data["server"]:
                        config["auto_register_devices"] = toml_data["server"][
                            "auto_register_devices"
                        ]

                # [firmware]
                if "firmware" in toml_data:
                    if "enabled" in toml_data["firmware"]:
                        config["enable_firmware_server"] = toml_data["firmware"]["enabled"]
                    if "port" in toml_data["firmware"]:
                        config["firmware_port"] = toml_data["firmware"]["port"]

                # [storage]
                if "storage" in toml_data:
                    if "max_file_size" in toml_data["storage"]:
                        config["max_file_size"] = toml_data["storage"]["max_file_size"]

                # [auth]
                if "auth" in toml_data:
                    if "enabled" in toml_data["auth"]:
                        config["enable_auth"] = toml_data["auth"]["enabled"]
                    if "users" in toml_data["auth"]:
                        config["accounts"] = toml_data["auth"]["users"]

        except Exception as e:
            print(f"Error loading config.toml: {e}")
    return config


# Global config for server logic
SERVER_CONFIG = load_server_config()
MAX_FILE_SIZE_BYTES = parse_size(SERVER_CONFIG.get("max_file_size"))
MAX_FILE_SIZE_STR = SERVER_CONFIG.get("max_file_size", "100MB")
ENABLE_AUTH = SERVER_CONFIG.get("enable_auth", False)
AUTO_REGISTER_DEVICES = SERVER_CONFIG.get("auto_register_devices", True)
ACCOUNTS = SERVER_CONFIG.get("accounts", [])


class User(BaseModel):
    id: str
    email: str
    nickname: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


def load_tokens() -> Dict[str, Dict[str, Any]]:
    if not TOKENS_FILE.exists():
        return {}
    try:
        with open(TOKENS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_tokens(tokens: Dict[str, Dict[str, Any]]):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


if not TOKENS_FILE.exists():
    with open(TOKENS_FILE, "w") as f:
        json.dump({}, f)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),  # noqa: B008
) -> Optional[User]:
    """
    Dependency to get the current authenticated user.
    If ENABLE_AUTH is False, returns a dummy admin user.
    If ENABLE_AUTH is True, requires a valid Bearer token.
    """
    if not ENABLE_AUTH:
        # Auth disabled: Return dummy admin
        return User(id="admin", email="admin@local", nickname="Admin")

    if not creds:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = creds.credentials
    tokens_db = load_tokens()

    # Simple check: is token in DB?
    # In a real app, we'd check expiration, etc.
    session = tokens_db.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")

    return User(
        id=session["user_id"],
        email=session["email"],
        nickname=session.get("nickname"),
    )


DATA_DIR.mkdir(exist_ok=True, parents=True)
FILES_DIR.mkdir(exist_ok=True, parents=True)

# Supported file types (device limitations)
SUPPORTED_EXTENSIONS = {".txt", ".jpg", ".epub", ".xtc", ".xtch", ".bmp", ".bin"}

# Remap certain extensions to standard ones for device compatibility
# (e.g., Markdown files are served as .txt)
EXTENSION_REMAP = {
    "md": "txt",
}

if not TASKS_FILE.exists():
    with open(TASKS_FILE, "w") as f:
        json.dump({}, f)

if not DEVICES_FILE.exists():
    with open(DEVICES_FILE, "w") as f:
        json.dump([], f)


def load_tasks() -> Dict[str, List[Dict[str, Any]]]:
    try:
        with open(TASKS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_tasks(tasks: Dict[str, List[Dict[str, Any]]]):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def load_devices() -> List[Dict[str, Any]]:
    """Load all known devices from persistent storage"""
    try:
        with open(DEVICES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_devices(devices: List[Dict[str, Any]]):
    """Save devices to persistent storage"""
    with open(DEVICES_FILE, "w") as f:
        json.dump(devices, f, indent=2)


def is_known_device(device_id: str) -> bool:
    """Check if a device ID is registered or is a special ID"""
    if device_id == "all":
        return True
    devices = load_devices()
    return any(d.get("device_id") == device_id for d in devices)


async def load_devices_async() -> List[Dict[str, Any]]:
    """Load devices asynchronously (non-blocking)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, load_devices)


async def save_devices_async(devices: List[Dict[str, Any]]):
    """Save devices asynchronously (non-blocking)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, save_devices, devices)


async def load_tasks_async() -> Dict[str, List[Dict[str, Any]]]:
    """Load tasks asynchronously (non-blocking)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, load_tasks)


async def save_tasks_async(tasks: Dict[str, List[Dict[str, Any]]]):
    """Save tasks asynchronously (non-blocking)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, save_tasks, tasks)


def register_device(device_id: str) -> None:
    """Auto-register a device when we see it for the first time"""
    devices = load_devices()
    # Check if device already exists
    if not any(d.get("device_id") == device_id for d in devices):
        device = {
            "id": uuid.uuid4().hex,
            "device_id": device_id,
            "brand": "xteink",
            "device_type": "ESP32C3",
            "version": "UNKNOWN",
            "user_id": "local_user",  # Custom server devices are local, not tied to cloud user
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        devices.append(device)
        save_devices(devices)
        print(f"REGISTERED DEVICE: {device_id}")


def create_app():
    # Create FastAPI app
    # Disable docs for production feel
    app = FastAPI(docs_url=None, redoc_url=None)

    # Static file serving (Real files)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/files/storage", StaticFiles(directory=str(FILES_DIR)), name="files")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(request: Request, path: str):
        # Log request details (Compact version)
        log_msg = f"{time.strftime('%H:%M:%S')} | {request.method} {path}"
        if request.query_params:
            log_msg += f" ? {dict(request.query_params)}"

        # Add body info if relevant and not multipart
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            body = await request.body()
            if body:
                try:
                    body_json = json.loads(body)
                    log_msg += f" | BODY: {body_json}"
                except Exception:
                    decoded = body.decode(errors="replace")
                    log_msg += (
                        f" | BODY (raw): {decoded[:100]}..."
                        if len(decoded) > 100
                        else f" | BODY: {decoded}"
                    )

        print(log_msg)

        # AUTHENTICATION: Login
        if path == "auth/login" and request.method == "POST":
            try:
                data = await request.json()
                login_req = LoginRequest(**data)
            except Exception:
                return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

            # Check credentials against config
            user_account = next(
                (
                    u
                    for u in ACCOUNTS
                    if u["email"] == login_req.email and u["password"] == login_req.password
                ),
                None,
            )

            if user_account:
                # Generate Token
                new_token = uuid.uuid4().hex
                user_id = uuid.uuid4().hex

                # Save session
                tokens = load_tokens()
                tokens[new_token] = {
                    "user_id": user_id,
                    "email": login_req.email,
                    "nickname": "Admin",
                    "created_at": int(time.time()),
                }
                save_tokens(tokens)

                print(f"LOGIN SUCCESS: {login_req.email}")
                return {
                    "success": True,
                    "access_token": new_token,
                    "refresh_token": new_token,  # Reuse for simplicity
                    "user_id": user_id,
                    "user": {
                        "id": user_id,
                        "email": login_req.email,
                        "nickname": "Admin",
                        "role": "admin",
                        "is_active": True,
                    },
                }
            else:
                print(f"LOGIN FAILED: {login_req.email}")
                return JSONResponse(
                    {"success": False, "message": "Invalid credentials"}, status_code=401
                )

        # Protected Routes Logic
        # We manually invoke the dependency logic here because we are in a catch-all route
        # In a standard FastAPI app, we'd put Depends() on the route function.
        PROTECTED_PATHS = [
            "api/v1/device/binding",
            "api/v1/device/tasks",
            "api/v1/upload",
            "api/v1/ai/image_resize",
        ]

        # Check if path starts with any protected path
        is_protected = any(path.startswith(p) for p in PROTECTED_PATHS)

        # Exception: Allow GET /api/v1/device/tasks without auth for devices?
        # The prompt implies devices might handle auth or we just need simple account support.
        # But commonly devices use unique IDs and not user accounts.
        # However, the plan said "Apply get_current_user dependency to ... /api/v1/device/tasks".
        # Let's enforce it. If devices break, user can disable auth.

        if is_protected and ENABLE_AUTH:
            auth_header = request.headers.get("Authorization")
            token = None
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

            authorized = False
            if token:
                tokens_db = load_tokens()
                if token in tokens_db:
                    authorized = True

            if not authorized:
                return JSONResponse(
                    {"success": False, "error": "Authentication required"}, status_code=401
                )

        if path == "api/v1/device/tasks" and request.method == "POST":
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"error": "Invalid JSON"}, status_code=400)

            device_id = data.get("device_id")
            if not device_id:
                return JSONResponse({"error": "device_id required"}, status_code=400)

            # Validate device ID
            if not is_known_device(device_id):
                return JSONResponse(
                    {"error": f"Device {device_id} not recognized. Please bind it first."},
                    status_code=400,
                )

            # Remap save_path extension if needed
            save_path = data.get("save_path")
            if save_path:
                sp_obj = Path(save_path)
                sp_ext = sp_obj.suffix.lower().lstrip(".")
                if sp_ext in EXTENSION_REMAP:
                    save_path = str(sp_obj.with_suffix(f".{EXTENSION_REMAP[sp_ext]}"))

            # SUPPORT BROADCAST: "all" device_id
            if device_id == "all":
                devices = await load_devices_async()
                if not devices:
                    return JSONResponse(
                        {"error": "No devices registered to broadcast to"},
                        status_code=400,
                    )

                tasks = await load_tasks_async()
                created_tasks = []

                for dev in devices:
                    dev_id = dev["device_id"]
                    if dev_id not in tasks:
                        tasks[dev_id] = []

                    # Create task for this device
                    one_task = {
                        "task_id": uuid.uuid4().hex,
                        "device_id": dev_id,
                        "file_url": data.get("file_url"),
                        "save_path": save_path,
                        "size": data.get("size", 0),
                        "status": "pending",
                        "type": data.get("type", "file_transfer"),
                        "created_at": int(time.time()),
                        "expires_at": int(time.time()) + 259200,
                        "metadata": data.get("metadata"),
                        "retry_count": 0,
                    }

                    # Deduplication
                    existing = None
                    for t in tasks[dev_id]:
                        if (
                            t.get("save_path") == one_task["save_path"]
                            and t.get("file_url") == one_task["file_url"]
                        ):
                            existing = t
                            break

                    if existing:
                        existing["status"] = "pending"
                        existing["created_at"] = int(time.time())
                        created_tasks.append(existing)
                    else:
                        tasks[dev_id].append(one_task)
                        created_tasks.append(one_task)

                await save_tasks_async(tasks)
                print(f"BROADCASTED TASK to {len(devices)} devices")
                return {
                    "success": True,
                    "count": len(devices),
                    "tasks": created_tasks,
                    "task": created_tasks[0],  # Primary task for CLI compatibility
                }

            # SINGLE DEVICE LOGIC
            new_task = {
                "task_id": uuid.uuid4().hex,
                "device_id": device_id,
                "file_url": data.get("file_url"),
                "save_path": save_path,
                "size": data.get("size", 0),
                "status": "pending",
                "type": data.get("type", "file_transfer"),
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 259200,  # 3 days
                "metadata": data.get("metadata"),
            }

            tasks = await load_tasks_async()
            if device_id not in tasks:
                tasks[device_id] = []

            # Deduplication Logic: Check if task exists for this save_path AND file_url
            # User requested new IDs unless it is the "same exact file/path"
            existing_task = None
            for t in tasks[device_id]:
                if (
                    t.get("save_path") == new_task["save_path"]
                    and t.get("file_url") == new_task["file_url"]
                ):
                    existing_task = t
                    break

            if existing_task:
                # Reset existing task instead of creating new one
                existing_task["status"] = "pending"
                existing_task["file_url"] = new_task["file_url"]
                existing_task["created_at"] = int(time.time())
                existing_task["updated_at"] = int(time.time())
                existing_task["retry_count"] = 0  # Reset retries
                await save_tasks_async(tasks)
                print(f"UPDATED TASK [{device_id}]")
                print(f"   ID: {existing_task['task_id']} (Reset to Pending)")
                return {"success": True, "task": existing_task}
            else:
                new_task["retry_count"] = 0
                tasks[device_id].append(new_task)
                await save_tasks_async(tasks)
                print(f"CREATED TASK [{device_id}]")
                print(f"   ID: {new_task['task_id']}")
                print(f"   File: {new_task['file_url']}")
                print(f"   Target: {new_task['save_path']}")
                return {"success": True, "task": new_task}

        if path == "internal/mock/clear" and request.method == "POST":
            save_tasks({})
            return {"message": "All tasks cleared"}

        # Device binding endpoints
        if path == "api/v1/device/binding" and request.method == "GET":
            devices = await load_devices_async()
            return {"success": True, "data": devices}

        if path == "api/v1/device/binding" and request.method == "POST":
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

            device_id = data.get("device_id")
            if not device_id:
                return JSONResponse(
                    {"success": False, "error": "device_id required"}, status_code=400
                )

            # Register the device (async, non-blocking)
            # Only if auto-register is enabled OR device already exists
            is_known = is_known_device(device_id)

            if is_known or AUTO_REGISTER_DEVICES:
                await asyncio.to_thread(register_device, device_id)
            else:
                return JSONResponse(
                    {
                        "success": False,
                        "error": (
                            f"Device {device_id} is not registered and auto-enrollment is disabled."
                        ),
                    },
                    status_code=403,
                )

            # Get the registered device info (async, non-blocking)
            devices = await load_devices_async()
            registered_device = next((d for d in devices if d["device_id"] == device_id), None)

            if registered_device:
                return {
                    "success": True,
                    "message": f"Device {device_id} bound successfully",
                    "data": registered_device,
                }
            else:
                return JSONResponse(
                    {"success": False, "error": "Failed to register device"},
                    status_code=500,
                )

        # Device endpoints
        if "device/tasks" in path and path.endswith("tasks"):
            device_id = request.query_params.get("device_id")

            # AUTO-REGISTER on polling: "Connect" logic
            if device_id and device_id != "all":
                is_known = is_known_device(device_id)
                if is_known or AUTO_REGISTER_DEVICES:
                    await asyncio.to_thread(register_device, device_id)

            # Validate device ID (for list query)
            if device_id and not is_known_device(device_id):
                return JSONResponse(
                    {"success": False, "error": f"Device {device_id} not recognized"},
                    status_code=400,
                )

            # Load tasks asynchronously (non-blocking)
            all_tasks = await load_tasks_async()
            device_tasks = all_tasks.get(device_id, [])

            # Filter by status: Default to "pending" for devices
            status_filter = request.query_params.get("status", "pending")
            if status_filter != "all":
                device_tasks = [t for t in device_tasks if t.get("status") == status_filter]

            # Sort tasks: Newest first
            device_tasks.sort(key=lambda x: -x.get("created_at", 0))

            # Apply limit if requested
            limit = request.query_params.get("limit")
            if limit and limit.isdigit():
                device_tasks = device_tasks[: int(limit)]

            # Calculate stats for the response (based on all tasks for this device)
            full_device_tasks = all_tasks.get(device_id, [])
            total = len(full_device_tasks)
            total_pending = len([t for t in full_device_tasks if t.get("status") == "pending"])
            total_done = len([t for t in full_device_tasks if t.get("status") == "completed"])
            total_processing = len(
                [t for t in full_device_tasks if t.get("status") == "processing"]
            )

            return {
                "success": True,
                "tasks": device_tasks,
                "total": total,
                "total_done": total_done,
                "total_pending": total_pending,
                "total_processing": total_processing,
                "code": 0,
            }

        # Task completion endpoint
        match = re.search(r"api/v1/device/tasks/([^/]+)/complete", path)
        if match and request.method == "POST":
            task_id = match.group(1)
            try:
                data = await request.json()
                new_status = data.get("status", "completed")
            except Exception:
                new_status = "completed"

            tasks = load_tasks()
            updated = False
            for _device_id, device_tasks in tasks.items():
                for t in device_tasks:
                    if t.get("task_id") == task_id:
                        t["status"] = new_status
                        t["updated_at"] = int(time.time())

                        # Auto-Retry Logic
                        if new_status == "failed":
                            # Check if we should retry
                            retries = t.get("retry_count", 0)
                            if retries < 3:  # Max 3 retries
                                t["retry_count"] = retries + 1
                                t["status"] = "pending"
                                print(f"🔄 RETRYING Task {task_id} (Attempt {t['retry_count']})")

                        updated = True
                        break
                if updated:
                    break

            if updated:
                save_tasks(tasks)
                print(f"Task {task_id} marked as {new_status}")
                # Find the updated task to return
                updated_task = next((t for t in device_tasks if t.get("task_id") == task_id), None)
                return {"success": True, "task": updated_task}
            else:
                return JSONResponse({"error": f"task {task_id} not found"}, status_code=404)

        # File Upload - Now requires device_id for single-storage pattern
        if path == "api/v1/upload" and request.method == "POST":
            # Get uploaded file
            form = await request.form()
            file = form.get("file")
            device_id = form.get("device_id")  # Now required

            if not file:
                return JSONResponse(
                    {"success": False, "error": "No file provided"}, status_code=400
                )
            if not device_id:
                return JSONResponse(
                    {"success": False, "error": "device_id required"}, status_code=400
                )

            # Check file size
            # SpooledTemporaryFile might need to seek to end to get size or use request headers
            # FastAPI's UploadFile header 'content-length' might be missing,
            # so we check the actual size
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)  # Reset pointer

            if file_size > MAX_FILE_SIZE_BYTES:
                print(
                    f"UPLOAD REJECTED: {file.filename} is {file_size} bytes "
                    f"(limit: {MAX_FILE_SIZE_STR})"
                )
                return JSONResponse(
                    {
                        "success": False,
                        "error": f"File too large (max {MAX_FILE_SIZE_STR})",
                    },
                    status_code=413,
                )

            # Validate device ID
            if not is_known_device(device_id):
                return JSONResponse(
                    {"success": False, "error": f"Device {device_id} not recognized"},
                    status_code=400,
                )

            filename = file.filename
            ext = Path(filename).suffix.lower()
            ext_plain = ext.lstrip(".") or "bin"

            # Apply extension remapping (e.g., .md -> .txt)
            ext_clean = EXTENSION_REMAP.get(ext_plain, ext_plain)

            # Validate against supported extensions (after remapping)
            if f".{ext_clean}" not in SUPPORTED_EXTENSIONS:
                return JSONResponse(
                    {
                        "success": False,
                        "error": f"Unsupported file type '{ext}'. Allowed: "
                        f"{', '.join(sorted(SUPPORTED_EXTENSIONS))} (or remapped types)",
                    },
                    status_code=400,
                )

            content = await file.read()
            await file.close()

            # Generate task_id upfront
            task_id = uuid.uuid4().hex

            # Store directly in final location: <device_id>/<ext>/<task_id>.<ext>
            save_dir = FILES_DIR / device_id / ext_clean
            save_dir.mkdir(parents=True, exist_ok=True)

            file_path = save_dir / f"{task_id}.{ext_clean}"
            with open(file_path, "wb") as f:
                f.write(content)

            # Construct download URL
            port = request.scope.get("server", [None, None])[1]
            host_header = request.headers.get("host")
            if host_header:
                base_url = f"http://{host_header}"
            else:
                base_url = f"http://localhost:{port}"

            file_url = (
                f"{base_url}/api/v1/files/storage/{device_id}/{ext_clean}/{task_id}.{ext_clean}"
            )
            print(f"UPLOAD: {filename} -> {file_url}")

            return {
                "success": True,
                "download_url": file_url,
                "filename": filename,
                "orig_filename": filename,
                "task_id": task_id,  # Return task_id for client to use
            }

        # Image Resize - Now just returns the upload URL (no processing/copying)
        if path == "api/v1/ai/image_resize" and request.method == "POST":
            try:
                data = await request.json()
                image_url = data.get("image_url")

                # Simply return the upload URL - file is already in final location
                print(f"PASSTHROUGH: {image_url}")

                return {
                    "success": True,
                    "download_url": image_url,
                    "download_url_fs": image_url,
                    "download_url_none": image_url,
                    "download_url_xtg": image_url,
                    "download_url_xth": image_url,
                    "download_url_xtch": image_url,
                    "orig_url": image_url,
                }
            except Exception as e:
                print(f"PROCESSING FAILED: {str(e)}")
                return JSONResponse({"error": str(e)}, status_code=500)

        if path == "api/v1/health" and request.method == "GET":
            return {"message": "API is running", "status": "healthy"}

        if "api/check-update" in path:
            return {"code": 1, "message": "current version is latest", "data": {}}

        return {
            "code": 0,
            "message": f"Mock server (port {SERVER_CONFIG.get('port', 8000)}) "
            "received your request",
        }

    return app


def run_server(port, host="0.0.0.0"):
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enable-firmware",
        action="store_true",
        help="Enable firmware update server on port 5000",
    )
    parser.add_argument("--host", default=None, help="Bind host (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="Main API port (overrides config)")
    return parser.parse_args(argv)


def get_server_settings(args, config):
    enable_firmware = getattr(args, "enable_firmware", False) or config.get(
        "enable_firmware_server", False
    )
    host = getattr(args, "host", None)
    if not host:
        host = config.get("host", "0.0.0.0")

    port = getattr(args, "port", None)
    if not port:
        port = config.get("port", 8000)

    firmware_port = config.get("firmware_port", 5000)

    return {
        "enable_firmware": enable_firmware,
        "host": host,
        "port": port,
        "firmware_port": firmware_port,
    }


if __name__ == "__main__":
    # Load config if exists
    config = load_server_config()
    print(f"Loaded configuration from {BASE_DIR / 'config.json'}")

    args = parse_args()
    settings = get_server_settings(args, config)

    enable_firmware = settings["enable_firmware"]
    host = settings["host"]
    port = settings["port"]
    firmware_port = settings["firmware_port"]

    threads = []

    # Port 5000 (Firmware Mock) - Optional
    if enable_firmware:
        print(f"Starting Firmware Update Server on port {firmware_port}...")
        t1 = threading.Thread(target=run_server, args=(firmware_port, host))
        t1.daemon = True
        t1.start()
        threads.append(t1)
    else:
        print(f"Firmware Update Server (Port {firmware_port}) disabled.")

    # Main API
    print(f"Starting Xteink Custom Sync Server on port {port}...")
    t2 = threading.Thread(target=run_server, args=(port, host))
    t2.daemon = True
    t2.start()
    threads.append(t2)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Custom Sync Server...")
