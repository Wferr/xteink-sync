from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# --- Enums ---


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ALL = "all"


class TaskType(str, Enum):
    FILE_TRANSFER = "file_transfer"
    IMAGE_RESIZE = "image_resize"
    FIRMWARE_UPDATE = "firmware_update"


class XtcInputType(str, Enum):
    EPUB = "epub"
    PDF = "pdf"
    IMAGES = "images"


class DitheringType(str, Enum):
    FLOYD_STEINBERG = "floyd_steinberg"
    NONE = "none"


# --- Generic Response Models ---


class BaseResponse(BaseModel):
    """Base response with success flag"""

    success: bool


class MessageResponse(BaseModel):
    """Response with message and optional success flag"""

    message: str
    success: bool = True


# --- Authentication ---


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    success: bool


class LogoutResponse(BaseModel):
    message: str

    success: bool


class VerificationRequest(BaseModel):
    email: str
    purpose: str


class VerificationResponse(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    email: str
    nickname: str
    password: str
    verification_code: str


class User(BaseModel):
    id: str
    email: str
    nickname: Optional[str] = None
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    current_tokens: int = 0
    username: Optional[str] = None


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: User
    message: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    success: bool


# --- Device Management ---


class Device(BaseModel):
    brand: str
    created_at: str
    device_id: str
    device_type: str
    id: str
    updated_at: str
    user_id: str
    version: str


class DeviceBindingResponse(BaseModel):
    data: List[Device]
    success: bool


class DeviceBindingRequest(BaseModel):
    device_id: str
    device_type: str = "ESP32C3"
    version: str = "XTOS V3.1.5"
    brand: str = "xteink"


class DeviceBindingAddResponse(BaseModel):
    data: Device
    message: str
    success: bool


class Task(BaseModel):
    task_id: str
    device_id: Optional[str] = None
    status: TaskStatus
    file_url: str
    save_path: str
    size: Optional[int] = None
    created_at: Optional[int] = None
    expires_at: Optional[int] = None
    source_url: Optional[str] = None
    result_url: Optional[str] = None
    type: Optional[TaskType] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskListResponse(BaseModel):
    success: bool
    tasks: List[Task]
    total: int
    total_done: int
    total_pending: int
    total_processing: int
    code: Optional[int] = 0


class TaskCreateRequest(BaseModel):
    device_id: str
    file_url: str
    save_path: str
    size: Optional[int] = None
    type: TaskType = TaskType.FILE_TRANSFER
    source_url: Optional[str] = None
    result_url: Optional[str] = None
    auto_push: bool = False
    metadata: Optional[Dict[str, Any]] = None


class TaskCreateResponse(BaseModel):
    success: bool
    task: Task


class TaskCompletionRequest(BaseModel):
    status: TaskStatus


# --- File Management ---


class FileUploadResponse(BaseModel):
    download_url: str
    filename: str
    orig_filename: Optional[str] = None
    success: bool


# --- AI/Image Processing ---


class ImageResizeRequest(BaseModel):
    image_url: str
    device_id: str
    dithering: DitheringType = DitheringType.FLOYD_STEINBERG


class ImageResizeResponse(BaseModel):
    download_url_fs: Optional[str] = None
    download_url_none: Optional[str] = None
    download_url_xtg: Optional[str] = None
    download_url_xth: Optional[str] = None
    filename_fs: Optional[str] = None
    filename_none: Optional[str] = None
    filename_xtg: Optional[str] = None
    filename_xth: Optional[str] = None
    success: bool


class XtcConvertRequest(BaseModel):
    input_type: XtcInputType
    device_id: str
    epub_url: Optional[str] = None
    pdf_url: Optional[str] = None
    image_urls: Optional[List[str]] = None


class XtcConvertResponse(BaseModel):
    success: bool
    download_url: str
    filename: str


class XtcConvertAndSubmitRequest(XtcConvertRequest):
    device_save_path: str


class XtcConvertAndSubmitResponse(BaseModel):
    success: bool
    task: Task


# --- Wallpaper Gallery ---


class Wallpaper(BaseModel):
    download_url: str
    filename: str
    mime_type: str
    size: int


class WallpaperListResponse(BaseModel):
    category: str
    success: bool
    total: int
    wallpapers: List[Wallpaper]


# --- RSS & Web Articles ---


class RSSParseRequest(BaseModel):
    rss_url: str


class Article(BaseModel):
    title: str
    link: str
    published: Optional[str] = None


class RSSParseResponse(BaseModel):
    articles: List[Article]


class UrlToPlainRequest(BaseModel):
    url: str
    download: bool = True


class UrlToPlainResponse(BaseModel):
    success: bool
    download_url: str
    filename: str


class PdfToTextRequest(BaseModel):
    pdf_url: str


class PdfToTextResponse(BaseModel):
    success: bool
    download_url: str
    txt_filename: str


# --- Quota Management ---


class QuotaStatusRequest(BaseModel):
    endpoint: str


class QuotaStatusResponse(BaseModel):
    endpoint: str
    default_quota: int
    remaining: int
    reset_in_seconds: int


# --- Client Version ---


class ClientVersionData(BaseModel):
    id: str
    platform: str
    version: str
    version_code: int
    download_url: str
    description: Optional[str] = None
    force_update: bool
    is_active: bool
    created_at: str
    updated_at: str


class ClientVersionResponse(BaseModel):
    cached: bool = False
    success: bool
    data: ClientVersionData


# --- System Health ---


class HealthResponse(BaseModel):
    message: str
    status: str


# --- Firmware ---


class FirmwareCheckResponse(BaseModel):
    code: int
    data: Dict[str, Any]
    message: str
