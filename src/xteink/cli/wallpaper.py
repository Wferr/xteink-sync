"""Wallpaper command handler."""

import os
from pathlib import Path

from xteink.client import PRODUCTION_API_URL, XteinkClient


def wallpaper(args, client: XteinkClient) -> None:
    """Upload and set wallpaper on device."""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    device_id = args.device_id
    # Default to "all" if missing and on custom server
    if not device_id:
        if client.BASE_URL != PRODUCTION_API_URL:
            device_id = "all"
        else:
            print("\033[91mError: Missing argument 'DEVICE_ID'.\033[0m")
            return

    file_path = args.file_path
    if not os.path.exists(file_path):
        print(f"\033[91mFile not found: {file_path}\033[0m")
        return

    try:
        # Step 1: Upload
        print("\033[1;36mStep 1/3: Uploading wallpaper...\033[0m")
        upload_result = client.upload_file(file_path, device_id)
        if not upload_result.success:
            print(f"\033[91mUpload failed: {upload_result.message}\033[0m")
            return

        image_url = upload_result.download_url
        print(f"\033[92mUploaded: {image_url}\033[0m")

        # Step 2: Process image (Resize)
        print("\033[1;36mStep 2/3: Processing image variants...\033[0m")
        # Start dithering to get variants
        resize_result = client.image_resize(image_url, device_id, args.dithering)
        if not resize_result.success:
            print(f"\033[91mImage processing failed: {resize_result.error}\033[0m")
            return

        # Prepare Metadata
        # Based on trace:
        # "metadata": {
        #   "filename": "wallpaper_portrait.xtg",
        #   "formatUrls": [ ... ],
        #   "deviceId": ...
        # }

        filename_base = Path(file_path).stem
        # Production seems to prefer .xtg as "filename" in metadata
        metadata_filename = f"{filename_base}.xtg"

        format_urls = []
        # Add variants if available
        if resize_result.download_url_xtg:
            format_urls.append(
                {
                    "format": "xtg",
                    "url": resize_result.download_url_xtg,
                    "filename": f"{filename_base}.xtg",
                }
            )
        if resize_result.download_url_none:
            format_urls.append(
                {
                    "format": "none",
                    "url": resize_result.download_url_none,
                    "filename": f"{filename_base}.bmp",  # Assuming bmp
                }
            )
        if resize_result.download_url_fs:
            format_urls.append(
                {
                    "format": "fs",
                    "url": resize_result.download_url_fs,
                    "filename": f"{filename_base}.bmp",
                }
            )
        if resize_result.download_url_xth:
            format_urls.append(
                {
                    "format": "xth",
                    "url": resize_result.download_url_xth,
                    "filename": f"{filename_base}.xth",
                }
            )

        metadata = {"filename": metadata_filename, "formatUrls": format_urls, "deviceId": device_id}

        # Primary file URL for task (XTG is preferred for wallpaper usually)
        # Trace used: "file_url": "...xtg"
        primary_url = resize_result.download_url_xtg
        if not primary_url:
            # Fallback
            primary_url = resize_result.download_url_fs or resize_result.download_url_none

        if not primary_url:
            print("\033[91mNo valid image URL generated\033[0m")
            return

        # Step 3: Create Task
        print("\033[1;36mStep 3/3: Creating wallpaper task...\033[0m")

        # Original size? Trace didn't show exact size match, but let's use actual file size as base
        # or 0 if unknown (Trace hot_news used 0, but request body size hidden in trace)
        # We'll pass 0 or file size. Let's pass file size of original upload for now.
        original_size = os.path.getsize(file_path)

        # Path Mapping: /Pushed Files/壁纸导入/filename.xtg
        # Using unicode directly
        save_path = f"/Pushed Files/壁纸导入/{metadata_filename}"

        task_result = client.create_device_task(
            device_id,
            primary_url,
            save_path,
            original_size,
            task_type="wallpaper",
            metadata=metadata,
        )

        if args.json:
            print(task_result.model_dump_json(indent=2))
        else:
            if task_result.success and task_result.task:
                task = task_result.task
                print("\033[1;92m\nWallpaper Task created successfully!\033[0m")
                print(f"Task ID: {task.task_id}")
                print(f"Status: {task.status}")
                print(f"File URL: {task.file_url}")
                print(f"Save Path: {task.save_path}")
            else:
                print("\033[91mFailed to create task\033[0m")

    except Exception as e:
        print(f"\033[91mFailed: {str(e)}\033[0m")
