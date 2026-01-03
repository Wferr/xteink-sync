"""File operation commands for xteink CLI."""


def upload(args, client):
    """Upload a file to the cloud"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    file_path = args.file_path

    try:
        print(f"Uploading {file_path}...")
        result = client.upload_file(file_path)

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            if result.success:
                print("\033[92mUpload successful!\033[0m")
                print(f"Filename: {result.filename}")
                print(f"Original: {result.orig_filename or 'N/A'}")
                print(f"Download URL: {result.download_url}")
            else:
                print("\033[91mUpload failed\033[0m")
    except Exception as e:
        print(f"\033[91mFailed to upload file: {str(e)}\033[0m")
