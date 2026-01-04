import io
import os
import re
import time
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

from server.core import config
from server.core.auth import User, get_current_user
from server.core.data import is_known_device
from xteink.formats import rss, xtg, xth

router = APIRouter()

# --- Helpers ---


def get_base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.headers.get('host', 'localhost:8000')}"


# --- Routes ---


@APIRouter.post(router, "/api/v1/upload")
async def upload_route(
    request: Request,
    _user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, Form(...)],
    device_id: Annotated[str, Form(...)],
):
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > config.SERVER_CONFIG["storage"]["max_file_size_bytes"]:
        max_size = config.SERVER_CONFIG["storage"].get("max_file_size", "100MB")
        msg = f"File too large (max {max_size})"
        return JSONResponse(
            {"success": False, "error": msg},
            status_code=413,
        )

    if not is_known_device(device_id):
        # We might auto-register here or fail. Original code failed if not known?
        # Re-reading original: "if not is_known_device... return 400"
        return JSONResponse(
            {"success": False, "error": f"Device {device_id} not recognized"},
            status_code=400,
        )

    filename = file.filename
    ext = Path(filename).suffix.lower()
    ext_clean = config.EXTENSION_REMAP.get(ext.lstrip("."), ext.lstrip(".") or "bin")
    # Bin allowed fallback?
    if f".{ext_clean}" not in config.SUPPORTED_EXTENSIONS and ext_clean != "bin":
        # Original code checked SUPPORTED_EXTENSIONS strictly
        if f".{ext_clean}" not in config.SUPPORTED_EXTENSIONS:
            return JSONResponse(
                {"success": False, "error": f"Unsupported file type '{ext}'"},
                status_code=400,
            )

    content = await file.read()
    task_id = uuid.uuid4().hex
    save_dir = config.FILES_DIR / device_id / ext_clean
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / f"{task_id}.{ext_clean}"
    with open(file_path, "wb") as f:
        f.write(content)

    base_url = get_base_url(request)
    storage_path = f"api/v1/files/storage/{device_id}/{ext_clean}/{task_id}.{ext_clean}"
    file_url = f"{base_url}/{storage_path}"

    print(f"UPLOAD: {filename} -> {file_url}")
    return {
        "success": True,
        "download_url": file_url,
        "filename": filename,
        "orig_filename": filename,
        "task_id": task_id,
    }


@APIRouter.post(router, "/api/v1/ai/url_plain")
async def url_plain_route(
    request: Request,
    _user: Annotated[User, Depends(get_current_user)],
):
    from pydantic import BaseModel

    class UrlProcessRequest(BaseModel):
        url: str
        download: bool = True
        format: str = "xtc"  # Default to xtc if supported, else txt

    try:
        data = await request.json()
        if "url" not in data:
            return JSONResponse({"error": "Missing 'url'"}, status_code=400)

        url_req = UrlProcessRequest(**data)
        print(f"AI: Processing URL: {url_req.url}, format={url_req.format}")

        if url_req.format == "xtc":
            # Render to XTC
            xtc_data = rss.render_url_to_xtc(url_req.url)

            # Create filename
            # Use a clean version of the title if possible, else URL
            # We need to peek at title, but render_url_to_xtc handles fetching.
            # Ideally render_url_to_xtc returns metadata too, but it returns bytes.
            # We'll use a generic name or extract from URL for now, or improve render logic later.
            # For simplicity:
            filename = re.sub(r"[^a-zA-Z0-9]", "_", url_req.url.rstrip("/").split("/")[-1])[:50]
            if not filename or len(filename) < 5:
                filename = f"article_{int(time.time())}"
            filename += ".xtc"

            save_dir = config.FILES_DIR / "url_xtc"
            save_dir.mkdir(parents=True, exist_ok=True)
            file_path = save_dir / filename

            with open(file_path, "wb") as f:
                f.write(xtc_data)

            base_url = get_base_url(request)
            download_url = f"{base_url}/api/v1/files/storage/url_xtc/{filename}"

            return {
                "success": True,
                "download_url": download_url,
                "filename": filename,
                "cache": False,
            }

        # Legacy TXT fallback
        print(f"AI: Converting URL to plain text (legacy): {url_req.url}")

        # Fetch text
        title, text_content = rss.fetch_url_text(url_req.url)

        # Create filename
        clean_title = re.sub(r"[^a-zA-Z0-9\s-]", "", title)
        clean_title = re.sub(r"\s+", "_", clean_title).strip()
        if not clean_title or len(clean_title) < 5:
            filename = re.sub(r"[^a-zA-Z0-9]", "_", url_req.url.rstrip("/").split("/")[-1])[:50]
            if not filename or len(filename) < 5:
                filename = f"article_{int(time.time())}"
        else:
            filename = clean_title[:60]

        filename += ".txt"

        save_dir = config.FILES_DIR / "url_plain"
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text_content)

        base_url = get_base_url(request)
        download_url = f"{base_url}/api/v1/files/storage/url_plain/{filename}"

        return {
            "success": True,
            "download_url": download_url,
            "filename": filename,
            "cache": False,
        }
    except Exception as e:
        print(f"URL Process Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/v1/ai/image_resize")
async def image_resize_route(request: Request, _user: Annotated[User, Depends(get_current_user)]):
    try:
        data = await request.json()
        image_url = data.get("image_url")
        # device_id = data.get("device_id", "default")  # Unused
        dithering = data.get("dithering", "none")
        crop_mode = data.get("crop_mode", config.SERVER_CONFIG["server"]["default_resize_mode"])

        if not image_url:
            return JSONResponse({"error": "image_url required"}, status_code=400)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(image_url, timeout=30.0)
                if response.status_code != 200:
                    return JSONResponse(
                        {"error": f"Failed to fetch image: {response.status_code}"}, status_code=400
                    )
                img_data = response.content
            except Exception as e:
                return JSONResponse({"error": f"Download failed: {str(e)}"}, status_code=400)

        # Process
        try:
            # Check if this is a native xteink format that shouldn't be processed
            url_path = image_url.lower()
            NATIVE_FORMATS = (".xtg", ".xth", ".xtc", ".xtch")
            if any(url_path.endswith(ext) for ext in NATIVE_FORMATS):
                return JSONResponse(
                    {
                        "error": (
                            "Native xteink format detected. "
                            "XTG/XTH/XTC/XTCH files are already in final format "
                            "and don't need processing. "
                            "Use the file URL directly for task creation."
                        )
                    },
                    status_code=400,
                )

            save_dir = config.FILES_DIR / "image_resize"
            save_dir.mkdir(parents=True, exist_ok=True)
            dest_filename = f"resize_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
            local_path = save_dir / dest_filename

            image = Image.open(io.BytesIO(img_data))
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Center crop / Resize
            MAX_SIZE = (800, 800)
            if crop_mode == "cover":
                # Center crop to aspect ratio and resize
                image = ImageOps.fit(image, MAX_SIZE, centering=(0.5, 0.5))
            else:
                # Standard thumbnail (contain)
                image.thumbnail(MAX_SIZE)

            # Generate Dithered BMP
            # Convert to 1-bit palette
            dither_mode = (
                Image.Dither.FLOYDSTEINBERG if dithering == "floyd_steinberg" else Image.Dither.NONE
            )
            img_bw = image.convert("1", dither=dither_mode)
            dest_bmp_name = f"{local_path.stem}_fs.bmp"
            dest_bmp_path = save_dir / dest_bmp_name
            img_bw.save(dest_bmp_path, "BMP")

            # Save Standard Resized (JPG)
            dest_jpg_name = f"{local_path.stem}.jpg"
            dest_jpg_path = save_dir / dest_jpg_name
            image.convert("RGB").save(dest_jpg_path, "JPEG", quality=85)
            # Generate XTG (1-bit)
            # Use '1' mode image
            xtg_bitmap = xtg.bitmap_from_image(
                image.copy(), dither=(dithering == "floyd_steinberg")
            )
            xtg_data = xtg.create_xtg(image.width, image.height, xtg_bitmap)
            dest_xtg_name = f"{local_path.stem}.xtg"
            dest_xtg_path = save_dir / dest_xtg_name
            with open(dest_xtg_path, "wb") as f:
                f.write(xtg_data)

            xth_bitmap = xth.bitmap_from_image(image.copy())
            xth_data = xth.create_xth(image.width, image.height, xth_bitmap)
            dest_xth_name = f"{local_path.stem}.xth"
            dest_xth_path = save_dir / dest_xth_name
            with open(dest_xth_path, "wb") as f:
                f.write(xth_data)

            base_url = get_base_url(request)
            # URLs
            url_jpg = f"{base_url}/api/v1/files/storage/image_resize/{dest_jpg_name}"
            url_bmp = f"{base_url}/api/v1/files/storage/image_resize/{dest_bmp_name}"
            url_xtg = f"{base_url}/api/v1/files/storage/image_resize/{dest_xtg_name}"
            url_xth = f"{base_url}/api/v1/files/storage/image_resize/{dest_xth_name}"

            return {
                "success": True,
                "download_url": url_jpg,
                "download_url_fs": url_bmp,
                "download_url_xtg": url_xtg,
                "download_url_xth": url_xth,
            }

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JSONResponse({"error": f"Image Resize Error: {str(e)}"}, status_code=400)

    except Exception as e:
        return JSONResponse({"error": f"Server error: {str(e)}"}, status_code=500)
