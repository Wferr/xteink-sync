import asyncio
import json
from typing import Any

from server.core import config


def _init_data():
    try:
        config.DATA_DIR.mkdir(exist_ok=True, parents=True)
        config.FILES_DIR.mkdir(exist_ok=True, parents=True)
        (config.FILES_DIR / "image_resize").mkdir(exist_ok=True, parents=True)

        for f_path, default in [
            (config.TOKENS_FILE, {}),
            (config.TASKS_FILE, {}),
            (config.DEVICES_FILE, []),
        ]:
            if not f_path.exists():
                with open(f_path, "w") as f:
                    json.dump(default, f)
    except Exception as e:
        # Halt if we can't initialize critical data paths
        msg = f"Critical error: Could not initialize data directory {config.DATA_DIR}: {e}"
        raise RuntimeError(msg) from e


def format_timestamp(ts: float) -> str | float | int:
    """Format timestamp based on configuration. Reverts to Unix float by default."""
    if config.SERVER_CONFIG["server"].get("timestamp_format") == "iso8601":
        import time

        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))
    # Return as int if it's a whole number for cleaner JSON
    if ts == int(ts):
        return int(ts)
    return float(ts)


_init_data()


def load_tasks() -> dict[str, list[dict[str, Any]]]:
    if not config.TASKS_FILE.exists():
        return {}

    with open(config.TASKS_FILE) as f:
        return json.load(f)


def save_tasks(tasks: dict[str, list[dict[str, Any]]]):
    with open(config.TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def load_devices() -> list[dict[str, Any]]:
    if not config.DEVICES_FILE.exists():
        return []

    with open(config.DEVICES_FILE) as f:
        return json.load(f)


def save_devices(devices: list[dict[str, Any]]):
    with open(config.DEVICES_FILE, "w") as f:
        json.dump(devices, f, indent=2)


def load_tokens() -> dict[str, dict]:
    if not config.TOKENS_FILE.exists():
        return {}
    try:
        with open(config.TOKENS_FILE) as f:
            content = f.read()

            if not content:
                return {}
            data = json.loads(content)
            return data
    except Exception:
        return {}


def save_tokens(tokens: dict[str, dict]):
    import os

    with open(config.TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
        f.flush()
        os.fsync(f.fileno())


def is_known_device(device_id: str) -> bool:
    if device_id == "all":
        return True
    devices = load_devices()
    return any(d.get("device_id") == device_id for d in devices)


# Async wrappers
async def load_devices_async() -> list[dict[str, Any]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, load_devices)


async def save_devices_async(devices: list[dict[str, Any]]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, save_devices, devices)


async def load_tasks_async() -> dict[str, list[dict[str, Any]]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, load_tasks)


async def save_tasks_async(tasks: dict[str, list[dict[str, Any]]]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, save_tasks, tasks)
