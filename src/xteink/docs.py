from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer

from xteink.client import PRODUCTION_API_URL
from xteink.models import (
    AuthRequest,
    AuthResponse,
    BaseResponse,
    ClientVersionResponse,
    DeviceBindingAddResponse,
    DeviceBindingRequest,
    DeviceBindingResponse,
    FileUploadResponse,
    FirmwareCheckResponse,
    HealthResponse,
    ImageResizeRequest,
    ImageResizeResponse,
    MessageResponse,
    PdfToTextRequest,
    PdfToTextResponse,
    QuotaStatusRequest,
    QuotaStatusResponse,
    RegisterRequest,
    RegisterResponse,
    RSSParseRequest,
    RSSParseResponse,
    TaskCompletionRequest,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TokenRefreshResponse,
    UrlToPlainRequest,
    UrlToPlainResponse,
    VerificationRequest,
    WallpaperListResponse,
    XtcConvertAndSubmitRequest,
    XtcConvertAndSubmitResponse,
    XtcConvertRequest,
    XtcConvertResponse,
)

description = """
# Xteink Cloud Sync API Documentation

**WARNING**: This documentation is based on reverse-engineering the official Xteink mobile app.
Definitions and implementations may be incorrect, incomplete, or subject to change without notice.
Use at your own risk.

**Security Note**: By default, all communication with Xteink services (and this custom server)
is performed over **unencrypted HTTP**. This means authentication tokens, passwords, and
file data are transmitted in plain text.

## Production API vs Custom Sync Server

This documentation covers two systems:

**Production API** (`http://8.130.157.48:8000`)
- Full-featured cloud service
- Authentication required
- Image processing and format conversion
- Device binding management
- Requires internet connection

**Custom Sync Server** (`http://localhost:8000` or your Pi)
- Local-only, no cloud dependency
- Core sync functionality (tasks, files)
- File type validation
- **Authentication supported** (configurable `ENABLE_AUTH`)
- **Image processing** (resizing, dithering, XTG/XTH/BMP conversion)
- **Device binding/registration** (`AUTO_REGISTER_DEVICES` support)
- **Auto-delete** (configurable `DELETE_AFTER_TRANSFER`)

## Endpoint Tags

- **[Production]**: Only available on production API
- **[Custom Server]**: Only available or specific behavior in custom sync server
- **[Both]**: Available in both systems (may have differences)

## Supported File Types (Custom Server)

The Custom Sync Server firmware only supports: `.txt`, `.jpg`, `.epub`, `.xtc`, `.xtch`,
`.bmp`, `.bin`

The custom server enforces this at upload time.

## Device Polling

Devices poll `GET /api/v1/device/tasks` with `limit=4` when in sync mode.

## Authentication Tokens

You can find your local tokens in `~/.xteink/tokens.json`:
- Use `access_token` for most API requests (AccessToken).
- Use `refresh_token` ONLY for `/auth/refresh` (RefreshToken).
"""


app = FastAPI(
    title="Xteink API Reference",
    description=description,
    version="1.0.0",
    servers=[
        {"url": PRODUCTION_API_URL, "description": "Production Server"},
        {"url": "http://localhost:8000", "description": "Custom Sync Server / Docs"},
    ],
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)

# Add security schemes for different token types
access_security = HTTPBearer(auto_error=False, scheme_name="AccessToken")
refresh_security = HTTPBearer(auto_error=False, scheme_name="RefreshToken")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# --- Authentication ---


@app.post("/auth/login", response_model=AuthResponse, tags=["[Both] Authentication"])
async def login(request: AuthRequest):
    """Login with email and password to obtain an access token.

    Custom Server:
    - Checks credentials against `config.toml` accounts.
    - Generates local tokens stored in `data/tokens.json`.
    """
    return {"access_token": "mock_token", "success": True}


@app.post("/auth/logout", response_model=MessageResponse, tags=["[Production] Authentication"])
async def logout():
    """[Production Only] Logout and invalidate tokens."""
    return {"message": "Logged out successfully"}


@app.post(
    "/auth/refresh",
    response_model=TokenRefreshResponse,
    tags=["[Both] Authentication"],
    dependencies=[Depends(refresh_security)],
)
async def refresh_token():
    """Refresh authentication token."""
    return {"access_token": "mock_new_token", "success": True}


@app.post(
    "/auth/send-email-verification-code",
    response_model=MessageResponse,
    tags=["[Production] Authentication"],
)
async def send_verification(request: VerificationRequest):
    """Send email verification code."""
    return {"message": "Verification code has been sent to your email"}


@app.post(
    "/auth/register-by-email",
    response_model=RegisterResponse,
    tags=["[Production] Authentication"],
)
async def register(request: RegisterRequest):
    """Register a new user."""
    return {
        "access_token": "mock_token",
        "refresh_token": "mock_refresh_token",
        "message": "User registered successfully",
        "user": {
            "id": "mock_id",
            "email": request.email,
            "nickname": request.nickname,
            "role": "user",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "current_tokens": 0,
        },
    }


# --- Device Management ---


@app.get(
    "/api/v1/device/binding",
    response_model=DeviceBindingResponse,
    tags=["[Both] Device"],
    dependencies=[Depends(access_security)],
)
async def get_device_binding():
    """Get bound devices for the authenticated user."""
    return {"data": [], "success": True}


@app.post(
    "/api/v1/device/binding",
    response_model=DeviceBindingAddResponse,
    tags=["[Both] Device"],
    dependencies=[Depends(access_security)],
)
async def bind_device(request: DeviceBindingRequest):
    """Bind a new device / Register device."""
    return {
        "success": True,
        "message": "Device bound successfully",
        "data": {
            "id": "mock_device_id",
            "device_id": request.device_id,
            "device_type": request.device_type,
            "brand": request.brand,
            "version": request.version,
            "user_id": "mock_user_id",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    }


@app.delete(
    "/api/v1/device/binding/{device_id}",
    response_model=MessageResponse,
    tags=["[Production] Device"],
    dependencies=[Depends(access_security)],
)
async def unbind_device(device_id: str):
    """[Production Only] Unbind a device from the authenticated user's account."""
    return {"message": "Device binding deleted successfully", "success": True}


@app.get(
    "/api/v1/device/tasks",
    response_model=TaskListResponse,
    tags=["[Both] Tasks"],
    dependencies=[Depends(access_security)],
)
async def get_device_tasks(device_id: str, status: str = "all", limit: Optional[int] = None):
    """[Both Systems] Get tasks for a device. Devices poll this endpoint every ~30 seconds.

    Custom Server Differences:
    - Tasks sorted: pending > processing > failed > completed
    - Failed tasks auto-retried (up to 3 times)
    - Authentication optional if `ENABLE_AUTH` is False
    - Supports broadcast tasks (device_id="all")

    Supported File Types: .txt, .jpg, .epub, .xtc, .xtch, .bmp, .bin

    **Example Production Response:**
    ```json
    {
      "success": true,
      "tasks": [
        {
          "completed_at": 1767344849,
          "created_at": 1767344843,
          "expires_at": 1767604049,
          "file_url": "http://example.com/api/v1/files/image_resize/...",
          "save_path": "/Pushed Files/壁纸导入/image.bmp",
          "size": 48062,
          "status": "completed",
          "task_id": "0c716b49f8304486a52da69758ea2246"
        }
      ],
      "total": 20,
      "total_done": 20,
      "total_pending": 0,
      "total_processing": 0,
      "code": 0
    }
    ```
    """
    return {
        "success": True,
        "tasks": [],
        "total": 0,
        "total_done": 0,
        "total_pending": 0,
        "total_processing": 0,
        "code": 0,
    }


@app.post(
    "/api/v1/device/tasks",
    response_model=TaskCreateResponse,
    tags=["[Both] Tasks"],
    dependencies=[Depends(access_security)],
)
async def create_task(task: TaskCreateRequest):
    """Create a new task."""
    pass


@app.post(
    "/api/v1/device/tasks/{task_id}/complete",
    response_model=BaseResponse,
    tags=["[Both] Tasks"],
    dependencies=[Depends(access_security)],
)
async def complete_task(task_id: str, request: TaskCompletionRequest):
    """
    Mark a task as completed or failed.

    Devices call this endpoint after attempting to process a task.
    Custom Server: If `DELETE_AFTER_TRANSFER` is enabled, the local file is deleted upon success.
    """
    return {"success": True, "code": 0}


@app.put(
    "/api/v1/device/tasks/{task_id}/status",
    response_model=BaseResponse,
    tags=["[Custom Server] Tasks"],
)
async def update_task_status(task_id: str, status: str):
    """[Custom Server Only] Manually update a task status."""
    return {"success": True}


# --- File Management ---


@app.post(
    "/api/v1/upload",
    response_model=FileUploadResponse,
    tags=["[Both] File"],
    dependencies=[Depends(access_security)],
)
async def upload_file(file: UploadFile = File(...)):  # noqa: B008
    """Upload a file."""
    return {"success": True, "download_url": "http://...", "filename": file.filename}


# --- AI/Image Processing ---


@app.post(
    "/api/v1/ai/image_resize",
    response_model=ImageResizeResponse,
    tags=["[Both] AI"],
    dependencies=[Depends(access_security)],
)
async def image_resize(request: ImageResizeRequest):
    """Resize/Process image for e-ink.

    Custom Server:
    - Supports `dithering` ("floyd_steinberg" or "none").
    - Returns `download_url_fs` (BMP), `download_url_xtg`, and `download_url_xth`.
    """
    return {"success": True}


@app.post(
    "/api/v1/ai/convert_xtc",
    response_model=XtcConvertResponse,
    tags=["[Production] AI"],
    dependencies=[Depends(access_security)],
)
async def convert_xtc(request: XtcConvertRequest):
    """Convert content to XTC."""
    return {"success": True, "download_url": "http://...", "filename": "converted.xtc"}


@app.post(
    "/api/v1/ai/convert_xtc_and_submit",
    response_model=XtcConvertAndSubmitResponse,
    tags=["[Production] AI"],
    dependencies=[Depends(access_security)],
)
async def convert_xtc_and_submit(request: XtcConvertAndSubmitRequest):
    """Convert and submit task."""
    pass


# --- Wallpaper ---


@app.get(
    "/api/v1/wallpaper/list",
    response_model=WallpaperListResponse,
    tags=["[Production] Wallpaper"],
)
async def get_wallpapers(device_id: str):
    """Get wallpaper gallery."""
    return {"success": True, "category": "wallpaper", "total": 0, "wallpapers": []}


# --- RSS & Articles ---


@app.post(
    "/api/v1/rss/parse",
    response_model=RSSParseResponse,
    tags=["[Both] RSS"],
)
async def parse_rss(request: RSSParseRequest):
    """Parse RSS feed."""
    return {"articles": []}


@app.post(
    "/api/v1/ai/url_plain",
    response_model=UrlToPlainResponse,
    tags=["[Both] RSS"],
)
async def url_to_plain(request: UrlToPlainRequest):
    """Convert URL to plain text."""
    return {"success": True, "download_url": "http://...", "filename": "article.txt"}


@app.post(
    "/api/v1/ai/pdf2txt",
    response_model=PdfToTextResponse,
    tags=["[Production] PDF"],
)
async def pdf_to_text(request: PdfToTextRequest):
    """Convert PDF to text."""
    return {"success": True, "download_url": "http://...", "txt_filename": "doc.txt"}


# --- Quota ---


@app.post(
    "/api/v1/quota/status",
    response_model=QuotaStatusResponse,
    tags=["[Production] Quota"],
)
async def get_quota_status(request: QuotaStatusRequest):
    """Get quota status."""
    return {
        "endpoint": request.endpoint,
        "default_quota": 100,
        "remaining": 99,
        "reset_in_seconds": 3600,
    }


# --- Client Version ---


@app.get(
    "/api/v1/client/version/{platform}",
    response_model=ClientVersionResponse,
    tags=["[Production] System"],
)
async def get_client_version(platform: str):
    """Get client version."""
    pass


# --- Health ---


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["[Both] System"],
)
async def health_check():
    """Health check."""
    return {"message": "API is running", "status": "healthy"}


# --- Firmware (Different Host in Reality) ---
@app.get(
    "/api/check-update",
    response_model=FirmwareCheckResponse,
    tags=["[Both] Firmware"],
)
async def check_firmware_update(
    current_version: str,
    device_type: str,
    device_id: Optional[str] = None,
    mac_address: Optional[str] = None,
):
    """
    Check firmware update (Mocking the firmware server).

    This endpoint is polled by the device to check for available firmware updates.
    It typically runs on a separate firmware update server (port 5000).
    """
    return {"code": 1, "message": "current version is latest", "data": {}}


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Documentation Server Starting...")
    print("Open the following URL in your browser:")
    print("👉 http://localhost:8000/docs")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
