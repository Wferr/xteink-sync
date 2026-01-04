"""Task-related commands for xteink CLI."""

import os
from datetime import datetime
from pathlib import Path

from xteink.client import PRODUCTION_API_URL
from xteink.constants import (
    DEFAULT_TASK_PATH_DATE_FORMAT,
    FORMAT_ATTRIBUTE_MAP,
    IMAGE_EXTENSIONS,
    NATIVE_XTEINK_FORMATS,
)


def tasks(args, client):
    """Get device tasks"""
    device_id = args.device_id

    # Default to "all" if missing and on custom server
    if not device_id:
        if client.BASE_URL != PRODUCTION_API_URL:
            device_id = "all"
        else:
            print("\033[91mError: Missing argument 'DEVICE_ID'.\033[0m")
            return

    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    try:
        result = client.get_device_tasks(device_id, args.status, limit=args.limit)

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            if result.success:
                print("\033[1;36mTask Statistics:\033[0m")
                print(f"Total: {result.total}")
                print(f"Done: {result.total_done}")
                print(f"Pending: {result.total_pending}")
                print(f"Processing: {result.total_processing}\n")

                tasks_list = result.tasks
                if tasks_list:
                    print("\033[1;36mTasks for device {device_id}:\033[0m")
                    for task in tasks_list:
                        print(f"\nTask ID: {task.task_id}")
                        print(f"  Status: {task.status}")
                        print(f"  File URL: {task.file_url}")
                        print(f"  Save Path: {task.save_path}")
                        print(f"  Size: {task.size or 'N/A'} bytes")
                        if task.created_at:
                            print(f"  Created: {task.created_at}")
                else:
                    print("No tasks found")
            else:
                print("No tasks found")
    except Exception as e:
        print(f"\033[91mFailed to get tasks: {str(e)}\033[0m")


def create_task(args, client):
    """Create a new device task"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    try:
        print(f"Creating task for device {args.device_id}...")
        result = client.create_device_task(
            args.device_id, args.file_url, args.save_path, args.size, args.type
        )

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            if result.success and result.task:
                task = result.task
                print("\033[92mTask created successfully!\033[0m")
                print(f"Task ID: {task.task_id}")
                print(f"Status: {task.status}")
                print(f"File URL: {task.file_url}")
                print(f"Save Path: {task.save_path}")
                print(f"Size: {task.size or 'N/A'} bytes")
            else:
                print("\033[91mFailed to create task\033[0m")
    except Exception as e:
        print(f"\033[91mFailed to create task: {str(e)}\033[0m")


def send(args, client):
    """Upload image and send to device (all-in-one command)"""
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

    # Generate default save path if not provided
    save_path = args.save_path
    try:
        # Check if input is a URL (Article mode)
        is_url = args.file_path.startswith("http://") or args.file_path.startswith("https://")

        # Check if URL is an image
        is_image_url = False
        if is_url:
            ext = Path(args.file_path).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                is_image_url = True

        # CASE 1: Article URL (Not Image)
        if is_url and not is_image_url:
            print(f"\033[1;36mProcessing Article URL: {args.file_path}\033[0m")

            # Step 1: Convert URL to XTC (or Plain Text if unsupported)
            url = f"{client.BASE_URL}/api/v1/ai/url_plain"
            payload = {"download": True, "url": args.file_path, "format": "xtc"}

            headers = {}
            if client.access_token:
                headers["Authorization"] = f"Bearer {client.access_token}"

            response = client._request("POST", url, json_data=payload, headers=headers)
            if response.status_code not in [200, 201]:
                print(f"\033[91mFailed to convert URL: {response.text}\033[0m")
                return

            data = response.json()
            download_url = data.get("download_url")
            filename = data.get("filename", "article.xtc")

            print(f"\033[92mConverted: {filename}\033[0m")

            # Use generated filename for save_path if not provided
            if not save_path:
                date_str = datetime.now().strftime(DEFAULT_TASK_PATH_DATE_FORMAT)
                save_path = f"/Pushed Files/{date_str}/{filename}"

            # Step 2: Create Task
            print("\033[1;36mCreating device task (hot_news)...\033[0m")

            task_result = client.create_device_task(
                device_id, download_url, save_path, 0, task_type="hot_news"
            )

            if args.json:
                print(task_result.model_dump_json(indent=2))
            else:
                if task_result.success and task_result.task:
                    task = task_result.task
                    print("\033[1;92m\nTask created successfully!\033[0m")
                    print(f"Task ID: {task.task_id}")
                    print(f"Status: {task.status}")
                    print(f"File URL: {task.file_url}")
                    print(f"Save to: {task.save_path}")
                else:
                    print("\033[91mFailed to create task\033[0m")

            return

        # CASE 2: Remote Image URL or Local File
        if not save_path:
            filename = Path(args.file_path).name
            date_str = datetime.now().strftime(DEFAULT_TASK_PATH_DATE_FORMAT)
            save_path = f"/Pushed Files/{date_str}/{filename}"

        image_url = None
        original_size = 0

        # Detect native xteink formats that don't need processing
        file_ext = Path(args.file_path).suffix.lower()
        is_native_format = file_ext in NATIVE_XTEINK_FORMATS

        # Create Task Flow
        if is_image_url:
            print(f"\033[1;36mProcessing Remote Image URL: {args.file_path}\033[0m")
            image_url = args.file_path
            # Size unknown (0)
            original_size = 0
        else:
            # Local File Upload
            if not os.path.exists(args.file_path):
                print(f"\033[91mFile not found: {args.file_path}\033[0m")
                return

            # Step 1: Upload
            print("\033[1;36mStep 1/3: Uploading file...\033[0m")
            upload_result = client.upload_file(args.file_path, device_id)
            if not upload_result.success:
                print("\033[91mUpload failed\033[0m")
                return

            image_url = upload_result.download_url
            original_size = os.path.getsize(args.file_path)
            print(f"\033[92mUploaded: {image_url}\033[0m")

        # Step 2: Process image (skip for native formats)
        if is_native_format:
            print("\033[1;36mStep 2/3: Skipping processing (native format)...\033[0m")
            processed_url = image_url
            print(f"\033[92mUsing native format: {file_ext}\033[0m")
        else:
            print("\033[1;36mStep 2/3: Processing image...\033[0m")
            resize_result = client.image_resize(
                image_url, device_id, args.dithering, crop_mode=args.resize_mode
            )
            if not resize_result.success:
                print("\033[91mImage processing failed\033[0m")
                return

            # Select the appropriate format
            processed_url = getattr(resize_result, FORMAT_ATTRIBUTE_MAP[args.format])
            if not processed_url:
                print(f"\033[91mFormat '{args.format}' not available\033[0m")
                return

        print(f"\033[92mProcessed ({args.format}): {processed_url}\033[0m")

        # Update save_path extension to match processed format (KISS)
        processed_ext = Path(processed_url).suffix.split("?")[0]  # Strip any query params
        if processed_ext:
            p = Path(save_path)
            save_path = str(p.with_suffix(processed_ext))

        # Size already determined above

        # Step 3: Create task
        print("\033[1;36mStep 3/3: Creating device task...\033[0m")
        task_result = client.create_device_task(device_id, processed_url, save_path, original_size)

        if args.json:
            print(task_result.model_dump_json(indent=2))
        else:
            if task_result.success and task_result.task:
                task = task_result.task
                print("\033[1;92m\nTask created successfully!\033[0m")
                print(f"Task ID: {task.task_id}")
                print(f"Status: {task.status}")
                print(f"Device will download from: {task.file_url}")
                print(f"Save to: {task.save_path}")
            else:
                print("\033[91mFailed to create task\033[0m")
    except Exception as e:
        print(f"\033[91mFailed: {str(e)}\033[0m")
