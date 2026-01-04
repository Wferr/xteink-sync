"""Constants and configuration values for xteink."""

# Supported file extensions by category
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
NATIVE_XTEINK_FORMATS = {".xtg", ".xth", ".xtc", ".xtch"}
DOCUMENT_FORMATS = {".txt", ".epub", ".pdf"}
BINARY_FORMATS = {".bin"}

# All supported extensions
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | NATIVE_XTEINK_FORMATS | DOCUMENT_FORMATS | BINARY_FORMATS

# Extension remapping for normalization
EXTENSION_REMAP = {
    "jpeg": "jpg",
    "xtch": "xtc",
}

# Default date format for task save paths
DEFAULT_TASK_PATH_DATE_FORMAT = "%Y-%m-%d"

# Format mapping for image processing
FORMAT_ATTRIBUTE_MAP = {
    "fs": "download_url_fs",
    "none": "download_url_none",
    "xtg": "download_url_xtg",
    "xth": "download_url_xth",
}

# RSS Rendering defaults
DEFAULT_RSS_FORMAT = "xtc"
DEFAULT_FONT_SIZE = 20
DEFAULT_LINE_SPACING = 8
DEFAULT_PAGE_MARGIN = 40
