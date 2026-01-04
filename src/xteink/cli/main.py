"""Main CLI entry point for xteink."""

import argparse
import sys

from xteink.cli import auth, convert, devices, files, rss, tasks, utils, wallpaper
from xteink.client import XteinkClient


def main():
    """Xteink Cloud Sync CLI - Send files to Xteink devices"""
    parser = argparse.ArgumentParser(
        prog="xteink", description="Xteink Cloud Sync CLI - Send files to Xteink devices"
    )
    parser.add_argument("--server", "-s", help="Custom API Server IP or URL (e.g., 192.168.1.20)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Auth Commands
    auth_parser = subparsers.add_parser("auth", help="Authentication commands")
    auth_subs = auth_parser.add_subparsers(dest="subcommand", help="Auth subcommands")

    login_p = auth_subs.add_parser("login", help="Login to Xteink cloud")
    login_p.add_argument("--email", help="Email address")
    login_p.add_argument("--password", help="Password")
    login_p.set_defaults(func=auth.login)

    reg_p = auth_subs.add_parser("register", help="Register a new account")
    reg_p.add_argument("--email", help="Email address")
    reg_p.add_argument("--nickname", help="Nickname")
    reg_p.add_argument("--password", help="Password")
    reg_p.set_defaults(func=auth.register)

    logout_p = auth_subs.add_parser("logout", help="Logout and clear local tokens")
    logout_p.set_defaults(func=auth.logout)

    refresh_p = auth_subs.add_parser("refresh", help="Refresh access token")
    refresh_p.set_defaults(func=auth.refresh)

    status_p = auth_subs.add_parser("status", help="Check connectivity and auth status")
    status_p.set_defaults(func=auth.status)

    # Legacy alias for auth status
    status_p_legacy = subparsers.add_parser("status", help="Check connectivity and auth status")
    status_p_legacy.set_defaults(func=auth.status)

    # Device Commands
    # 'devices' list
    dev_p = subparsers.add_parser("devices", help="List bound devices")
    dev_p.set_defaults(func=devices.devices)

    bind_p = subparsers.add_parser("bind", help="Bind a new device manually")
    bind_p.add_argument("--device-id", help="Device ID")
    bind_p.add_argument("--type", help="Device Type")
    bind_p.add_argument("--version", help="Firmware Version")
    bind_p.set_defaults(func=devices.bind)

    unbind_p = subparsers.add_parser("unbind", help="Unbind a device")
    unbind_p.add_argument("device_id", help="Device ID to unbind")
    unbind_p.set_defaults(func=devices.unbind)

    # Task Commands
    tasks_p = subparsers.add_parser("tasks", help="Get device tasks")
    tasks_p.add_argument("device_id", nargs="?", help="Device ID")
    tasks_p.add_argument("--status", default="all", help="Task status filter")
    tasks_p.add_argument("--limit", type=int, help="Limit number of tasks")
    tasks_p.set_defaults(func=tasks.tasks)

    create_task_p = subparsers.add_parser("create-task", help="Create a new device task")
    create_task_p.add_argument("device_id", help="Device ID")
    create_task_p.add_argument("file_url", help="File URL")
    create_task_p.add_argument("save_path", help="Save path")
    create_task_p.add_argument("size", type=int, help="File size")
    create_task_p.add_argument("--type", default="file_transfer", help="Task type")
    create_task_p.set_defaults(func=tasks.create_task)
    send_p = subparsers.add_parser("send", help="Upload image and send to device")
    send_p.add_argument("file_path", help="Path to image file")
    send_p.add_argument("device_id", nargs="?", help="Device ID")
    send_p.add_argument("save_path", nargs="?", help="Save path on device")
    send_p.add_argument("--dithering", default="floyd_steinberg", help="Dithering algorithm")
    send_p.add_argument(
        "--format", default="fs", choices=["fs", "none", "xtg", "xth"], help="Output format"
    )
    send_p.add_argument(
        "--resize-mode",
        default="cover",
        choices=["cover", "contain"],
        help="Resize mode (cover=center crop, contain=fit)",
    )
    send_p.set_defaults(func=tasks.send)

    # Convert Command
    conv_p = subparsers.add_parser("convert", help="Local image conversion")
    conv_p.add_argument("file_path", help="Path to image file")
    conv_p.add_argument("--output", "-o", help="Output path (optional)")
    conv_p.add_argument(
        "--format", default="xtg", choices=["xtg", "xth", "bmp", "fs", "jpg"], help="Output format"
    )
    conv_p.add_argument("--dithering", default="floyd", help="Dithering mode")
    conv_p.add_argument(
        "--resize-mode",
        default="cover",
        choices=["cover", "contain"],
        help="Resize mode (cover=center crop, contain=fit)",
    )
    conv_p.set_defaults(func=convert.convert)

    # File Commands
    upload_p = subparsers.add_parser("upload", help="Upload a file to the cloud")
    upload_p.add_argument("file_path", help="Path to file")
    upload_p.set_defaults(func=files.upload)

    # Utility Commands
    health_p = subparsers.add_parser("health", help="Check API server health status")
    health_p.set_defaults(func=utils.health)

    version_p = subparsers.add_parser("version", help="Get client version info")
    version_p.add_argument("--platform", default="android", help="Platform")
    version_p.set_defaults(func=utils.version)

    qr_p = subparsers.add_parser("qr-parse", help="Parse a QR code hex string")
    qr_p.add_argument("qr_hex", help="QR code hex string")
    qr_p.set_defaults(func=utils.qr_parse)

    firm_p = subparsers.add_parser("firmware-check", help="Check for firmware updates")
    firm_p.add_argument("device_type", nargs="?", default="ESP32C3", help="Device type")
    firm_p.add_argument("current_version", nargs="?", default="3.1.4", help="Current version")
    firm_p.add_argument("--device-id", help="Device ID")
    firm_p.add_argument("--mac", help="MAC address")
    firm_p.set_defaults(func=utils.firmware_check)

    # Wallpaper Command
    wall_p = subparsers.add_parser("wallpaper", help="Upload and set wallpaper")
    wall_p.add_argument("file_path", help="Image file path")
    wall_p.add_argument("device_id", nargs="?", help="Target Device ID")
    wall_p.add_argument(
        "--dithering", default="floyd", choices=["none", "floyd"], help="Dithering mode"
    )
    wall_p.set_defaults(func=wallpaper.wallpaper)

    # RSS Commands
    rss_p = subparsers.add_parser("rss", help="Fetch and convert RSS feed")
    rss_p.add_argument("feed_url", help="RSS Feed URL")
    rss_p.add_argument("device_id", nargs="?", help="Target Device ID (optional)")
    rss_p.add_argument("--limit", type=int, default=10, help="Max articles")
    rss_p.add_argument("--format", default="xtc", choices=["xtc", "xtch"], help="Output format")
    rss_p.add_argument(
        "--dithering", default="floyd", choices=["none", "floyd"], help="Dithering mode"
    )
    rss_p.set_defaults(func=rss.rss)  # We will import this below

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Initialize client
    client = XteinkClient(base_url=args.server)

    if hasattr(args, "func"):
        args.func(args, client)
    else:
        # Handle cases where sub-commands like 'auth' are called without a subcommand
        if args.command == "auth":
            auth_parser.print_help()
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
