"""Utility commands for xteink CLI (health, version, QR parsing, firmware check)."""

import json


def health(args, client):
    """Check API server health status"""
    try:
        result = client.get_health()
        if result.status == "healthy":
            print("\033[92mAPI Status: Healthy\033[0m")
            print(f"Message: {result.message}")
        else:
            print("\033[93mAPI Status: Unknown\033[0m")
            print(f"Response: {result}")
    except Exception as e:
        print(f"\033[91mFailed to check health: {str(e)}\033[0m")


def version(args, client):
    """Get client version info"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    try:
        platform = args.platform or "android"
        result = client.get_client_version(platform)

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            if result.success and result.data:
                data = result.data
                cached = result.cached

                print(f"\033[1;36mClient Version Info ({platform}):\033[0m")
                if cached:
                    print("\033[93m  (Cached)\033[0m")

                print(f"  Version: {data.version} (code: {data.version_code})")
                print(f"  Download URL: {data.download_url}")
                print(f"  Force Update: {data.force_update}")
                print(f"  Active: {data.is_active}")

                if data.description:
                    print(f"  Description: {data.description}")

                if data.created_at:
                    print(f"  Released: {data.created_at}")
    except Exception as e:
        print(f"\033[91mFailed to get version: {str(e)}\033[0m")


def qr_parse(args, client):
    """Parse a QR code hex string."""
    try:
        result = client.parse_qr_code(args.qr_hex)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\033[1;36m\nQR Code Content:\033[0m")
            print(f"  Brand: \033[92m{result['brand']}\033[0m")
            print(f"  Type: {result['device_type']}")
            print(f"  Version: {result['version']}")
            print(f"  MAC: {result['mac_address']}")
            print(f"  Device ID (for binding): \033[93m{result['device_id']}\033[0m")

    except Exception as e:
        print(f"\033[91mFailed to parse QR code: {str(e)}\033[0m")


def firmware_check(args, client):
    """Check for firmware updates."""
    try:
        device_type = args.device_type or "ESP32C3"
        current_version = args.current_version or "3.1.5"
        result = client.check_firmware_update(
            device_type=device_type,
            current_version=current_version,
            device_id=args.device_id,
            mac_address=args.mac,
        )

        print(f"Firmware Check for {device_type} (version: {current_version}):")
        print(f"  Code: {result.code}")
        print(f"  Message: {result.message}")

        if result.code == 0:
            # Update available
            data = result.data
            print("\033[92m\nFirmware Update Available!\033[0m")
            if data.get("version"):
                print(f"  New Version: {data['version']}")
            if data.get("download_url"):
                print(f"  Download URL: {data['download_url']}")
            if data.get("size"):
                print(f"  Size: {data['size']} bytes")
            if data.get("checksum"):
                print(f"  Checksum: {data['checksum']}")
            if data.get("release_notes"):
                print(f"  Release Notes: {data['release_notes']}")
        elif result.code == 1:
            # Already latest
            print("\033[92m\nFirmware is up to date.\033[0m")
        elif result.code == 2:
            # Device type not supported
            print("\033[93m\nDevice type not supported or configured.\033[0m")
        else:
            # Error
            print(f"\033[91m\nError checking firmware: {result.message}\033[0m")

    except Exception as e:
        print(f"\033[91mFailed to check firmware: {str(e)}\033[0m")
