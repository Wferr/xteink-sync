# Xteink Sync Tools

Tools for interacting with Xteink E-ink devices, including a CLI for the cloud API, firmware patching utilities, and a custom sync server implementation.

## Disclaimers & Security

> [!WARNING]
> **Reverse Engineered**: This project is based on reverse-engineering the official Xteink mobile app. Definitions and implementations may be incorrect, incomplete, or subject to change without notice. Use at your own risk.

> [!CAUTION]
> **Security Note**: By default, all communication with Xteink services (and this custom server) is performed over **unencrypted HTTP**. This means authentication tokens, passwords, and file data are transmitted in plain text. Do not use sensitive passwords that you use elsewhere.

## Features

- **CLI Client**: Full-featured tool for Xteink Cloud & Custom servers.
- **Sync Server**: Local file sync for patched devices (Authentication & Full Firmware server are currently mock/planned).
- **Web Interface**: Browser-based ESP32 flasher and firmware patcher.

## Installation

**Standard:**
```bash
pip install -e .
```

**Development:**
```bash
pip install -e ".[dev]"
```

*Note: It is recommended to use a virtual environment (`venv`).*

## Usage

### CLI Client for interfacing with Xteink Cloud & Custom servers

```bash
# Authentication & Devices
xteink login
xteink status
xteink devices
xteink bind

# Sending Files
xteink send <file_path> <device_id> [save_path]

# Custom Server Usage
xteink --server http://<your_ip>:8000 send <file> <device_id>
```

### Sync Server & Local Sync

1. **Start Server**: `python server/server.py`
2. **Setup Device**: Use the [Web Interface](http://localhost:8080) to patch your firmware. Replace the default API IP (`8.130.157.48`) with your computer's local IP.
3. **Flash**: Flash the patched firmware to your device.

The device will now sync directly with your local server instead of the cloud.

### Web Interface & API Docs

- **Web Flasher**: [https://wferr.com/xteink-sync/web/](https://wferr.com/xteink-sync/web/)
- **API Reference**: [https://wferr.com/xteink-sync/web/api.html](https://wferr.com/xteink-sync/web/api.html)

To run locally:
1. Start server: `cd web && python serve.py`
2. Open `http://localhost:8080` (Avoid `file://` due to CORS).

## Testing

```bash
pytest tests/ -v
```

*Static API documentation is available at [web/api.html](web/api.html) and can be regenerated using `src/xteink/generate_api_docs.py`.*
