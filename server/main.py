import os
import sys

# Add project root to path so 'from server.*' works even if run directly
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import time  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from server.core import config  # noqa: E402
from server.core.config import FILES_DIR  # noqa: E402
from server.routers import auth, devices, files, rss, tasks  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI()

    # Static Files
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    # Mount at /api/v1/files/storage so URLs returned match file path structure
    app.mount("/api/v1/files/storage", StaticFiles(directory=str(config.FILES_DIR)), name="files")

    # Middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        path = request.url.path.lstrip("/")
        if not path.startswith("api/v1/files/storage"):
            print(f"{time.strftime('%H:%M:%S')} | {request.method} {path}")
        return await call_next(request)

    # Routers
    app.include_router(auth.router)
    app.include_router(devices.router)
    app.include_router(tasks.router)
    app.include_router(files.router)
    app.include_router(rss.router)

    return app


app = create_app()


def start():
    """Entry point for running the server programmatically"""
    # Use reload=False for production/PI stability
    import uvicorn

    print("Starting Modular Xteink Server...")
    # We use the string reference to ensure uvicorn can handle workers/reloads if needed in future
    # though reload=False allows passing app instance too.
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    start()
