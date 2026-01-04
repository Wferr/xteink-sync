import json
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from xteink.models import (
    AuthResponse,
    ClientVersionResponse,
    DeviceBindingAddResponse,
    DeviceBindingResponse,
    FileUploadResponse,
    FirmwareCheckResponse,
    HealthResponse,
    ImageResizeResponse,
    MessageResponse,
    RegisterResponse,
    TaskCreateResponse,
    TaskListResponse,
    TokenRefreshResponse,
)

# Production API Endpoints (Official Xteink Cloud)
PRODUCTION_API_URL = "http://8.130.157.48:8000"  # Main API server
PRODUCTION_FIRMWARE_URL = "http://47.122.74.33:5000"  # Firmware update server


class XteinkResponse:
    """Minimal wrapper to mimic requests.Response behavior"""

    def __init__(self, data: bytes, status_code: int, headers: dict):
        self.content = data
        self.status_code = status_code
        self.headers = headers

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise HTTPError(
                None, self.status_code, f"HTTP Error {self.status_code}", self.headers, None
            )


class XteinkClient:
    """Client for interacting with Xteink cloud sync API"""

    def __init__(self, token_file: str = "~/.xteink/tokens.json", base_url: str = None):
        # Use provided base_url or default to production API
        url = base_url or PRODUCTION_API_URL

        # Ensure URL has a scheme (only http supported for now)
        if url and not url.startswith("http"):
            url = f"http://{url}"

        # Ensure URL has a port (default to 8000 for custom servers)
        if url and url != PRODUCTION_API_URL:
            parsed = urlparse(url)
            if parsed.port is None:
                if url.endswith("/"):
                    url = url[:-1]
                url = f"{url}:8000"

        self.BASE_URL = url
        self.TOKEN_FILE = Path(token_file).expanduser()
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self._load_tokens()

    def _get_headers(self, auth: bool = False) -> dict[str, str]:
        """Get headers for API requests"""
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/4.12.0",
        }
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _save_tokens(self):
        """Save tokens to config file"""
        self.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.TOKEN_FILE, "w") as f:
            json.dump(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "user_id": self.user_id,
                },
                f,
            )

    def _load_tokens(self):
        """Load tokens from config file"""
        if self.TOKEN_FILE.exists():
            with open(self.TOKEN_FILE) as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.user_id = data.get("user_id")

    def _request(
        self,
        method: str,
        url: str,
        params: dict = None,
        json_data: dict = None,
        data: bytes = None,
        headers: dict = None,
        timeout: int = 30,
    ) -> XteinkResponse:
        """Internal request helper using urllib.request"""
        if params:
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            url += "?" + urlencode(params)

        if json_data:
            data = json.dumps(json_data).encode("utf-8")

        req = Request(url, data=data, method=method)

        # Add default headers if not provided
        all_headers = self._get_headers()
        if headers:
            all_headers.update(headers)

        for k, v in all_headers.items():
            req.add_header(k, v)

        try:
            # We skip SSL verification for production IP addresses if needed,
            # but standard urllib uses system certs.
            # Since the user wants "Pure Python", we'll stick to defaults.
            with urlopen(req, timeout=timeout) as response:
                return XteinkResponse(response.read(), response.status, dict(response.getheaders()))
        except HTTPError as e:
            # Re-wrap HTTPError into our response object so raise_for_status works
            return XteinkResponse(e.read(), e.code, dict(e.headers))
        except URLError as e:
            raise ConnectionError(f"Could not connect to server: {e.reason}") from e

    def _make_authenticated_request(self, method: str, url: str, **kwargs) -> XteinkResponse:
        """Make an authenticated request with automatic token refresh on 401"""
        headers = kwargs.get("headers", {})
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # Shift json= argument to json_data for our helper
        if "json" in kwargs:
            kwargs["json_data"] = kwargs.pop("json")

        response = self._request(method, url, headers=headers, **kwargs)

        # If we get a 401, try to refresh the token and retry once
        if response.status_code == 401 and self.refresh_token:
            try:
                self.refresh_access_token()
                if self.access_token:
                    headers["Authorization"] = f"Bearer {self.access_token}"
                response = self._request(method, url, headers=headers, **kwargs)
            except Exception:
                pass  # If refresh fails, return original 401 response

        response.raise_for_status()
        return response

    def login(self, email: str, password: str) -> AuthResponse:
        """Login with email and password"""
        url = f"{self.BASE_URL}/auth/login"
        data = {"email": email, "password": password}

        response = self._request("POST", url, json_data=data)
        response.raise_for_status()

        result = AuthResponse(**response.json())
        self.access_token = result.access_token
        self.refresh_token = result.refresh_token
        self.user_id = result.user_id

        self._save_tokens()
        return result

    def send_verification_code(self, email: str, purpose: str = "register") -> MessageResponse:
        """Send email verification code"""
        url = f"{self.BASE_URL}/auth/send-email-verification-code"
        data = {"email": email, "purpose": purpose}
        response = self._request("POST", url, json_data=data)
        response.raise_for_status()
        return MessageResponse(**response.json())

    def register(
        self, email: str, nickname: str, password: str, verification_code: str
    ) -> RegisterResponse:
        """Register a new user"""
        url = f"{self.BASE_URL}/auth/register-by-email"
        data = {
            "email": email,
            "nickname": nickname,
            "password": password,
            "verification_code": verification_code,
        }
        response = self._request("POST", url, json_data=data)
        response.raise_for_status()
        result = RegisterResponse(**response.json())

        # Auto-login after registration
        self.access_token = result.access_token
        self.refresh_token = result.refresh_token
        self.user_id = result.user.id
        self._save_tokens()

        return result

    def logout(self) -> MessageResponse:
        """Logout and clear tokens"""
        url = f"{self.BASE_URL}/auth/logout"
        try:
            response = self._make_authenticated_request("POST", url)
            result = MessageResponse(**response.json())
        except Exception:
            # Even if API fails, we should clear local tokens
            result = MessageResponse(message="Logged out locally (API call failed)")

        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self._save_tokens()
        return result

    def refresh_access_token(self) -> TokenRefreshResponse:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please login first.")

        url = f"{self.BASE_URL}/auth/refresh"
        headers = {"Authorization": f"Bearer {self.refresh_token}"}

        response = self._request("POST", url, headers=headers)
        response.raise_for_status()

        result = TokenRefreshResponse(**response.json())
        self.access_token = result.access_token

        self._save_tokens()
        return result

    def get_device_binding(self) -> DeviceBindingResponse:
        """Get device binding information"""
        url = f"{self.BASE_URL}/api/v1/device/binding"
        response = self._make_authenticated_request("GET", url)
        return DeviceBindingResponse(**response.json())

    def bind_device(
        self,
        device_id: str,
        device_type: str = "ESP32C3",
        version: str = "XTOS V3.1.5",
        brand: str = "xteink",
    ) -> DeviceBindingAddResponse:
        """Bind a new device"""
        url = f"{self.BASE_URL}/api/v1/device/binding"
        data = {
            "device_id": device_id,
            "device_type": device_type,
            "version": version,
            "brand": brand,
        }
        response = self._make_authenticated_request("POST", url, json=data)
        return DeviceBindingAddResponse(**response.json())

    def unbind_device(self, device_id: str) -> MessageResponse:
        """Unbind a device"""
        url = f"{self.BASE_URL}/api/v1/device/binding/{device_id}"
        response = self._make_authenticated_request("DELETE", url)
        return MessageResponse(**response.json())

    def parse_qr_code(self, qr_hex: str) -> dict:
        """
        Parse and decrypt the Xteink QR code hex string.
        Returns a dictionary with device details.
        """
        if not qr_hex:
            raise ValueError("Empty QR code hex string")

        try:
            # Key derived from known plaintext analysis
            KEY_HEX = "600a7a210b7729504c6e3b4276afe52068db6a162a2f270f057217685d01"
            key = bytes.fromhex(KEY_HEX)
            data = bytes.fromhex(qr_hex)
            decrypted = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))

            brand = decrypted[0:6].decode("utf-8", errors="ignore").strip()
            device_type = decrypted[6:13].decode("utf-8", errors="ignore").strip()
            mac_bytes = decrypted[13:19]
            mac_address = ":".join(f"{b:02X}" for b in mac_bytes)
            device_id_int = int.from_bytes(mac_bytes[3:6], byteorder="big")
            version = decrypted[19:30].decode("utf-8", errors="ignore").strip()
            mac_underscore = "_".join(f"{b:02X}" for b in mac_bytes)
            full_device_id = f"{device_id_int}_{mac_underscore}"

            return {
                "brand": brand,
                "device_type": device_type,
                "mac_address": mac_address,
                "version": version,
                "device_id": full_device_id,
                "raw_decrypted": decrypted.hex(),
            }

        except Exception as e:
            raise ValueError(f"Failed to parse QR code: {str(e)}") from e

    def get_client_version(self, platform: str = "android") -> ClientVersionResponse:
        """Get client version information"""
        url = f"{self.BASE_URL}/api/v1/client/version/{platform}"
        response = self._make_authenticated_request("GET", url)
        return ClientVersionResponse(**response.json())

    def get_device_tasks(
        self, device_id: str, status: Optional[str] = None, limit: Optional[int] = None
    ) -> TaskListResponse:
        """Get device tasks"""
        url = f"{self.BASE_URL}/api/v1/device/tasks"
        params = {"device_id": device_id, "status": status}
        if limit:
            params["limit"] = limit
        response = self._make_authenticated_request("GET", url, params=params)
        return TaskListResponse(**response.json())

    def _generate_boundary(self) -> str:
        """Generate a random boundary string for multipart/form-data"""
        import uuid

        return f"boundary-{uuid.uuid4().hex}"

    def upload_file(self, file_path: str, device_id: str = None) -> FileUploadResponse:
        """Upload a file to the cloud using manual multipart encoding"""
        url = f"{self.BASE_URL}/api/v1/upload"

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        boundary = self._generate_boundary()

        # Build multipart body
        body = []
        if device_id:
            body.append(f"--{boundary}".encode())
            body.append(b'Content-Disposition: form-data; name="device_id"')
            body.append(b"")
            body.append(device_id.encode("utf-8"))

        body.append(f"--{boundary}".encode())
        body.append(
            f'Content-Disposition: form-data; name="file"; filename="{file_path_obj.name}"'.encode()
        )
        body.append(b"Content-Type: application/octet-stream")
        body.append(b"")
        with open(file_path, "rb") as f:
            body.append(f.read())
        body.append(f"--{boundary}--".encode())
        body.append(b"")

        data = b"\r\n".join(body)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "okhttp/4.12.0",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        response = self._request("POST", url, data=data, headers=headers)

        # Handle token refresh if needed
        if response.status_code == 401 and self.refresh_token:
            try:
                self.refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = self._request("POST", url, data=data, headers=headers)
            except Exception:
                pass

        response.raise_for_status()
        return FileUploadResponse(**response.json())

    def image_resize(
        self,
        image_url: str,
        device_id: str,
        dithering: str = "floyd_steinberg",
        crop_mode: Optional[str] = None,
    ) -> ImageResizeResponse:
        """Process an image for different display modes"""
        url = f"{self.BASE_URL}/api/v1/ai/image_resize"
        data = {
            "image_url": image_url,
            "device_id": device_id,
            "dithering": dithering,
            "crop_mode": crop_mode,
        }
        response = self._make_authenticated_request("POST", url, json=data)
        return ImageResizeResponse(**response.json())

    def create_device_task(
        self,
        device_id: str,
        file_url: str,
        save_path: str,
        size: int,
        task_type: str = "file_transfer",
        metadata: Optional[dict[str, Any]] = None,
    ) -> TaskCreateResponse:
        """Create a new device task"""
        url = f"{self.BASE_URL}/api/v1/device/tasks"
        data = {
            "device_id": device_id,
            "file_url": file_url,
            "save_path": save_path,
            "size": size,
            "type": task_type,
        }
        if metadata:
            data["metadata"] = metadata
        response = self._make_authenticated_request("POST", url, json=data)
        return TaskCreateResponse(**response.json())

    def get_health(self) -> HealthResponse:
        """Check API server health status"""
        url = f"{self.BASE_URL}/api/v1/health"
        response = self._request("GET", url)
        return HealthResponse(**response.json())

    def check_firmware_update(
        self,
        device_type: str,
        current_version: str,
        device_id: str = None,
        mac_address: str = None,
    ) -> FirmwareCheckResponse:
        """Check for firmware updates (uses separate firmware API server)"""
        params = {"current_version": current_version, "device_type": device_type}
        if device_id:
            params["device_id"] = device_id
        if mac_address:
            params["mac_address"] = mac_address

        url = f"{PRODUCTION_FIRMWARE_URL}/api/check-update"

        try:
            response = self._request("GET", url, params=params, timeout=10)
            if response.status_code == 200:
                return FirmwareCheckResponse(**response.json())
            elif response.status_code == 500:
                return FirmwareCheckResponse(
                    code=-1,
                    data={},
                    message="Server error - firmware might not be configured for this device type",
                )
            else:
                return FirmwareCheckResponse(
                    code=-1,
                    data={},
                    message=f"HTTP {response.status_code}: {response.text[:100]}",
                )
        except ConnectionError as e:
            return FirmwareCheckResponse(code=-1, data={}, message=str(e))
        except Exception as e:
            return FirmwareCheckResponse(code=-1, data={}, message=f"Error: {str(e)}")

    def is_authenticated(self) -> bool:
        """Check if client has valid tokens"""
        return self.access_token is not None
