"""Xteink - Tools for interacting with Xteink E-ink devices."""

from xteink.client import XteinkClient
from xteink.models import (
    # Auth
    AuthResponse,
    BaseResponse,
    # Devices
    Device,
    DeviceBindingResponse,
    # Files
    FileUploadResponse,
    # Core responses
    MessageResponse,
    # Tasks
    Task,
    TaskCreateResponse,
    TaskListResponse,
    TokenRefreshResponse,
)

# API endpoints
PRODUCTION_API_URL = "http://8.130.157.48:8000"
PRODUCTION_FIRMWARE_URL = "http://47.122.74.33:5000"

__version__ = "0.1.0"
__all__ = [
    "XteinkClient",
    "MessageResponse",
    "BaseResponse",
    "AuthResponse",
    "TokenRefreshResponse",
    "Device",
    "DeviceBindingResponse",
    "Task",
    "TaskListResponse",
    "TaskCreateResponse",
    "FileUploadResponse",
    "PRODUCTION_API_URL",
    "PRODUCTION_FIRMWARE_URL",
]
