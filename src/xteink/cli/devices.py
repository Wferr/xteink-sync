"""Device management commands for xteink CLI."""


def devices(args, client):
    """List bound devices"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    try:
        result = client.get_device_binding()

        if args.json:
            print(result.model_dump_json())
        else:
            print("\033[1;36mBound Devices:\n\033[0m")
            for device in result.data:
                print(f"Device ID: \033[92m{device.device_id}\033[0m")
                print(f"  Type: {device.device_type}")
                print(f"  Brand: {device.brand}")
                print(f"  Version: {device.version}")
                print(f"  Created: {device.created_at}")
                print("")

    except Exception as e:
        print(f"\033[91mError fetching devices: {str(e)}\033[0m")


def bind(args, client):
    """Bind a new device manually"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    device_id = args.device_id or input("Device ID: ")
    device_type = args.type or "ESP32C3"
    version = args.version or "XTOS V3.1.5"

    try:
        print(f"Binding device {device_id}...")
        result = client.bind_device(device_id, device_type=device_type, version=version)

        print(f"\033[92m{result.message}\033[0m")
        if result.data:
            print(f"Bound ID: {result.data.id}")
            print(f"Device ID: {result.data.device_id}")

    except Exception as e:
        print(f"\033[91mBinding failed: {str(e)}\033[0m")


def unbind(args, client):
    """Unbind a device"""
    if not client.is_authenticated():
        print("\033[91mNot authenticated. Please login first.\033[0m")
        return

    device_id = args.device_id

    confirm = input(f"Are you sure you want to unbind device {device_id}? (y/N): ")
    if confirm.lower() != "y":
        print("Unbind cancelled.")
        return

    try:
        print(f"Unbinding device {device_id}...")
        result = client.unbind_device(device_id)
        print(f"\033[92m{result.message}\033[0m")

    except Exception as e:
        print(f"\033[91mUnbinding failed: {str(e)}\033[0m")
