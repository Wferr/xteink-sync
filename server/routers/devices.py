import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from server.core import config
from server.core.auth import User, get_current_user
from server.core.data import format_timestamp, is_known_device, load_devices, save_devices

router = APIRouter()


@router.get("/api/v1/device/binding")
async def get_device_bindings(_user: Annotated[User, Depends(get_current_user)]):
    devices = load_devices()
    return {"success": True, "data": devices}


@router.post("/api/v1/device/binding")
async def bind_device_route(request: Request, _user: Annotated[User, Depends(get_current_user)]):
    data = await request.json()
    device_id = data.get("device_id")
    device_type = data.get("type", "unknown")
    version = data.get("version", "1.0")
    brand = data.get("brand", "xteink")

    if not device_id:
        return JSONResponse({"error": "device_id required"}, 400)

    # Check auto register
    auto_reg = config.SERVER_CONFIG["server"]["auto_register_devices"]
    if not is_known_device(device_id) and not auto_reg:
        return JSONResponse({"error": "Auto-registration disabled"}, 403)

    # Register/Update
    devices = load_devices()
    # Check if exists
    existing = next((d for d in devices if d["device_id"] == device_id), None)

    # Use string timestamps for response model compatibility
    current_time = time.time()
    formatted_time = format_timestamp(current_time)

    new_device = {
        "id": uuid.uuid4().hex,
        "device_id": device_id,
        "type": device_type,
        "device_type": device_type,
        "brand": brand,
        "version": version,
        "created_at": formatted_time,
        "updated_at": formatted_time,
        "last_seen": formatted_time,
        "user_id": _user.id if _user else "unknown",
    }

    if existing:
        existing.update(new_device)
        # Keep original ID and created_at if present
        existing["created_at"] = existing.get(
            "created_at", formatted_time
        )  # Fix fallback timestamp
        device_data = existing
    else:
        devices.append(new_device)  # Changed from device_data to new_device
        device_data = new_device  # Define device_data for the response

    save_devices(devices)

    return {"success": True, "data": device_data, "message": "Device registered"}
