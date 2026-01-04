import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Base Paths (Relative to this file or project root?)
# server/core/config.py -> parent=server/core -> parent=server.
# Original server.py was in server/.
# So BASE_DIR should be logical.
# Let's align with original setup:
# BASE_DIR was Path(__file__).parent (server/)
# Now config.py is in server/core/
# So BASE_DIR should be Path(__file__).parent.parent
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

TASKS_FILE = DATA_DIR / "tasks.json"
DEVICES_FILE = DATA_DIR / "devices.json"
FILES_DIR = DATA_DIR / "files"
TOKENS_FILE = DATA_DIR / "tokens.json"

# Supported file types (device limitations)
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".epub",
    ".xtg",
    ".xth",
    ".xtc",
    ".xtch",
    ".bmp",
    ".bin",
}

# Remap certain extensions to standard ones for device compatibility
EXTENSION_REMAP = {
    "md": "txt",
    "jpeg": "jpg",
}


def parse_size(size_str: Any) -> int:
    """Parse human readable size strings (e.g., '10MB', '1GB') to bytes.
    Raises ValueError on invalid input or format.
    """
    if size_str is None:
        return 100 * 1024 * 1024  # Default 100MB is acceptable if omitted

    if isinstance(size_str, int):
        return size_str

    if not isinstance(size_str, str):
        raise ValueError(f"Size must be a string or integer, got {type(size_str).__name__}")

    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

    s = size_str.strip().upper()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([A-Z]+)?$", s)
    if not match:
        msg = f"Invalid size format: '{size_str}'. Expected format like '100MB' or '1GB'."
        raise ValueError(msg)

    number_str, unit = match.groups()
    try:
        number = float(number_str)
    except ValueError as e:
        raise ValueError(f"Invalid number in size: '{number_str}'") from e

    unit = unit or "B"

    if unit not in units and unit.rstrip("S") in units:
        unit = unit.rstrip("S")

    if unit not in units:
        raise ValueError(f"Invalid size unit: '{unit}'. Supported: {', '.join(units.keys())}")

    multiplier = units[unit]
    return int(number * multiplier)


def load_server_config() -> dict[str, Any]:
    """Load configuration from config.toml with strict requirements."""
    config_path = BASE_DIR / "config.toml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        try:
            config = tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse config.toml: {e}") from e

    # Required sections check for strictness
    required = ["server", "storage", "auth"]
    for section in required:
        if section not in config:
            raise ValueError(f"Missing required section [{section}] in config.toml")

    return config


# Global config - THE Single Source of Truth
SERVER_CONFIG = load_server_config()

# Derived values stored back into SERVER_CONFIG for consolidation
SERVER_CONFIG["storage"]["max_file_size_bytes"] = parse_size(
    SERVER_CONFIG["storage"].get("max_file_size", "100MB")
)

# Standard internal paths derived from DATA_DIR (relative to BASE_DIR unless absolute)
_data_dir_name = SERVER_CONFIG["storage"].get("data_dir", "data")
DATA_DIR = (BASE_DIR / _data_dir_name).resolve()

FILES_DIR = DATA_DIR / "files"
TASKS_FILE = DATA_DIR / "tasks.json"
DEVICES_FILE = DATA_DIR / "devices.json"
TOKENS_FILE = DATA_DIR / "tokens.json"
