# Xteink Sync Server

A lightweight, local replacement for the Xteink Cloud API. This server enables **complete privacy** and **cloud-free operation** by allowing your devices to sync directly with your local machine.

## Disclaimers & Security

> [!WARNING]
> **Reverse Engineered**: This server implementation is based on reverse-engineering the official Xteink mobile app. Use at your own risk.

> [!CAUTION]
> **Security Note**: All communication is performed over **unencrypted HTTP**. Content, including any potential credentials or file data, is transmitted in plain text.

## Quick Links

- **[Main README](../README.md)**: Global project overview
- **[API Documentation](#api-documentation)**: Interactive Swagger UI

## Project Status: Honest Overview

> [!IMPORTANT]
> This server is currently a **working sync mock**. It provides 100% functional file transfers but many "Cloud" features (User accounts, Firmware storage) are currently simulated.

### What Works Today ✅
- **Device Auto-Registration**: Any device that polls the server is automatically "known" and manageable.
- **Robust File Syncing**: Upload files via CLI; devices fetch them via the standard polling loop.
- **Transparent Logging**: Every request from the device is printed to the console in real-time.
- **Deduplication**: Creating a task with the same path/file simply resets the existing one to "pending".

### What is Simulated/Mocked ⚠️
- **Firmware Server (Port 5000)**: Responds to version checks with "latest" status but **cannot** yet serve or manage physical `.bin` files.
- **Authentication**: The `Authorization: Bearer ...` header is accepted but **not validated**. The CLI can "login" to any dummy account.
- **AI Image Resizing**: Currently a pass-through; it returns the original image URL without performing actual resizing or conversion.

## Usage

### 1. Start the Server
```bash
python server/main.py
```
By default, the API runs on port **8000**. Port **5000** (firmware) is active but serves mock responses.

### 2. Configure Your Device
1. Use the **[Web Interface](http://localhost:8080)** to patch your firmware.
2. Replace the official IP `8.130.157.48` with your computer's **Local IP address**.
3. Flash and reboot.

### 3. Sync Files
```bash
xteink --server http://<your_ip>:8000 send cat.jpg <device_id>
```

## Directory Structure

- `data/files/`: The **Source of Truth**. Files are stored here by `device_id`.
- `data/tasks.json`: Persistent queue of files waiting to be fetched by devices.
- `data/devices.json`: Registry of automatically discovered devices.

## Roadmap
- [ ] **Physical Firmware Hosting**: Upload and serve actual `.bin` files for local OTA.
- [ ] **Local Auth Persistence**: Store dummy user accounts to support CLI account switching.
- [ ] **Web Dashboard**: View real-time device battery levels and sync logs in a browser.

## Testing
```bash
pytest tests/test_server_api.py -v
```
