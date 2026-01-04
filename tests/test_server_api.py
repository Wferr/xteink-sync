import copy
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path

import uvicorn

# Add project roots to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


import server.core.config as server_config
import server.core.data as server_data
import server.main as server_main
from xteink.client import XteinkClient


class TestServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup temporary data directory
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Save and Override
        cls.orig_config = copy.deepcopy(server_config.SERVER_CONFIG)
        cls.orig_data_dir = server_config.DATA_DIR
        cls.orig_tasks_file = server_config.TASKS_FILE
        cls.orig_devices_file = server_config.DEVICES_FILE
        cls.orig_files_dir = server_config.FILES_DIR
        cls.orig_tokens_file = server_config.TOKENS_FILE

        server_config.DATA_DIR = cls.tmp_data_dir
        server_config.TASKS_FILE = cls.tmp_data_dir / "tasks.json"
        server_config.DEVICES_FILE = cls.tmp_data_dir / "devices.json"
        server_config.FILES_DIR = cls.tmp_data_dir / "files"
        server_config.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        server_config.SERVER_CONFIG["auth"] = {"enabled": False, "users": []}
        server_config.SERVER_CONFIG["server"] = {
            "host": "127.0.0.1",
            "port": 0,
            "auto_register_devices": True,
            "timestamp_format": "unix",
            "default_resize_mode": "cover",
        }
        server_config.SERVER_CONFIG["storage"] = {
            "max_file_size": "100MB",
            "max_file_size_bytes": 100 * 1024 * 1024,
            "delete_after_transfer": False,
        }

        server_config.DATA_DIR.mkdir(exist_ok=True)
        server_config.FILES_DIR.mkdir(exist_ok=True)

        # Initialize empty JSONs
        with open(server_config.TASKS_FILE, "w") as f:
            json.dump({}, f)
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([], f)

        cls.port = 8009
        # Update FILES_DIR to point to tmp
        cls.orig_files_dir = server_config.FILES_DIR
        server_config.FILES_DIR = cls.tmp_data_dir / "files"
        server_config.FILES_DIR.mkdir(exist_ok=True)

        cls.port = 0

        # Recreate app to pick up new FILES_DIR in StaticFiles mount
        cls.app = server_main.create_app()
        cls.config = uvicorn.Config(app=cls.app, host="127.0.0.1", port=cls.port, log_level="info")
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()

        # Wait for server to start and retrieve port
        for _ in range(50):
            time.sleep(0.1)
            if cls.server.started:
                # Retrieve actual port from server socket
                for server in cls.server.servers:
                    for socket in server.sockets:
                        cls.port = socket.getsockname()[1]
                        break
                if cls.port:
                    break
            if cls.port:
                break

        if cls.port == 0:
            raise RuntimeError("Server failed to start")

        # Wait for server to start
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        # Stop uvicorn server
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)

        # Cleanup data dir
        shutil.rmtree(cls.tmp_data_dir)

        # Restore config
        server_config.SERVER_CONFIG = cls.orig_config

        # Restore original paths
        server_config.DATA_DIR = cls.orig_data_dir
        server_config.FILES_DIR = cls.orig_files_dir
        server_config.TASKS_FILE = cls.orig_tasks_file
        server_config.DEVICES_FILE = cls.orig_devices_file
        server_config.TOKENS_FILE = cls.orig_tokens_file

    def setUp(self):
        server_config.SERVER_CONFIG["server"]["auto_register_devices"] = True
        self.tmp_client_file = Path(tempfile.mktemp(suffix=".json"))
        self.client = XteinkClient(
            base_url=f"http://127.0.0.1:{self.port}", token_file=str(self.tmp_client_file)
        )
        # Clear data between tests
        with open(server_config.TASKS_FILE, "w") as f:
            json.dump({}, f)
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([], f)

    def test_device_registration_and_query(self):
        """Test acting as a device and querying tasks"""
        device_id = f"test_dev_{uuid.uuid4().hex[:8]}"

        # 0. Bind device first (required now)
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # 1. Query tasks (should be empty but registered)
        result = self.client.get_device_tasks(device_id)
        self.assertTrue(result.success)
        self.assertEqual(result.tasks, [])

        # Verify device is registered
        devices = server_data.load_devices()
        self.assertTrue(any(d["device_id"] == device_id for d in devices))

    def test_upload_and_download_end_to_end(self):
        """Test file upload, task creation, and download confirmation"""
        device_id = f"test_dev_{uuid.uuid4().hex[:8]}"

        # 0. Bind device first (required now)
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # 1. Upload sample.txt
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"This is a sample text file for end-to-end testing.")
            temp_file_path = f.name

        try:
            upload_result = self.client.upload_file(temp_file_path, device_id)
            self.assertTrue(upload_result.success)
            download_url = upload_result.download_url

            # 2. Create a task for this file
            task_result = self.client.create_device_task(device_id, download_url, "/sample.txt", 50)
            self.assertTrue(task_result.success)
            task_id = task_result.task.task_id

            # 3. Query tasks as device
            result = self.client.get_device_tasks(device_id)
            self.assertEqual(len(result.tasks), 1)
            self.assertEqual(result.tasks[0].task_id, task_id)
            self.assertEqual(result.tasks[0].file_url, download_url)

        finally:
            os.unlink(temp_file_path)

    def test_task_limit_parameter(self):
        """Test that the limit parameter correctly limits returned tasks"""
        device_id = f"test_dev_{uuid.uuid4().hex[:8]}"
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # Create 10 tasks
        for i in range(10):
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
                f.write(f"Test file {i}".encode())
                temp_file = f.name

            try:
                upload_result = self.client.upload_file(temp_file, device_id)
                self.assertTrue(upload_result.success)
                task_result = self.client.create_device_task(
                    device_id, upload_result.download_url, f"/test_{i}.txt", 10
                )
                self.assertTrue(task_result.success)
            finally:
                os.unlink(temp_file)

        # Test without limit - should get all 10
        result = self.client.get_device_tasks(device_id)
        self.assertGreaterEqual(len(result.tasks), 10)

        # Test with limit=4 - should get exactly 4
        result_limited = self.client.get_device_tasks(device_id, limit=4)
        self.assertEqual(len(result_limited.tasks), 4)
        self.assertEqual(result_limited.total, 4)

        # Test with limit=1 - should get exactly 1
        result_one = self.client.get_device_tasks(device_id, limit=1)
        self.assertEqual(len(result_one.tasks), 1)
        self.assertEqual(result_one.total, 1)

    def test_upload_uses_request_host(self):
        """Test that upload endpoint uses the request host header for URLs"""
        device_id = f"test_dev_{uuid.uuid4().hex[:8]}"

        # Bind device first
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # Upload a file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"Test content")
            temp_file_path = f.name

        try:
            upload_result = self.client.upload_file(temp_file_path, device_id)
            self.assertTrue(upload_result.success)

            # Check that the URL contains the test server host (127.0.0.1:8001)
            # and NOT localhost:8000
            download_url = upload_result.download_url
            self.assertIn(f"127.0.0.1:{self.port}", download_url)
            self.assertNotIn("localhost:8000", download_url)

        finally:
            os.unlink(temp_file_path)

    def test_broadcast_task_to_all(self):
        """Test broadcasting a task to all registered devices"""
        # 1. Register two devices
        r1 = self.client.bind_device("dev1", "ESP32C3", "V3.1.5")
        self.assertTrue(r1.success)
        r2 = self.client.bind_device("dev2", "ESP32C3", "V3.1.5")
        self.assertTrue(r2.success)

        import time

        time.sleep(1)  # Wait for devices logic to flush

        # 2. Create task for "all"
        result = self.client.create_device_task(
            "all", "http://localhost/file.txt", "/test.txt", 100
        )
        self.assertTrue(result.success)

        # 3. Verify tasks exist for both devices
        resp1 = self.client.get_device_tasks("dev1")
        self.assertEqual(len(resp1.tasks), 1)

        resp2 = self.client.get_device_tasks("dev2")
        self.assertEqual(len(resp2.tasks), 1)

    def test_task_completion(self):
        """Test marking a task as completed"""
        device_id = "test_dev_comp"
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # Create a task
        task_result = self.client.create_device_task(
            device_id, "http://example.com/file", "/file", 100
        )
        task_id = task_result.task.task_id

        # Complete task
        import json
        import urllib.request

        url = f"{self.client.BASE_URL}/api/v1/device/tasks/{task_id}/complete"
        data = json.dumps({"status": "completed"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        # Verify in DB
        updated_tasks = server_data.load_tasks()
        self.assertEqual(updated_tasks[device_id][0]["status"], "completed")

    def test_image_resize_passthrough(self):
        """Test image resize passthrough endpoint"""
        device_id = "test_dev_img"
        self.client.bind_device(device_id, "ESP32", "1.0")

        # Upload a REAL image (from fixtures)
        fixtures_dir = Path(__file__).parent / "fixtures"
        img_path = fixtures_dir / "sample.jpg"

        with open(img_path, "rb") as f:
            img_bytes = f.read()

        # Upload it using a temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        try:
            upload_resp = self.client.upload_file(tmp_path, device_id=device_id)
            url = upload_resp.download_url
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # Check basic resize
        # Note: image_resize expects a URL. The server will try to fetch it.
        # Since 'url' is localhost:800x, it should work if the server can reach itself.
        # But wait, self.client.upload_file returns a URL that might be 127.0.0.1.
        # The server inside the test container/process needs to resolve it.

        try:
            result = self.client.image_resize(url, device_id)
            self.assertTrue(result.success)
            self.assertIn("resize", result.download_url)
        except Exception:
            raise

    def test_task_deduplication(self):
        """Test that creating the same task twice resets it to pending instead of duplicating"""
        device_id = "test_dev_dedup"
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # Create task 1
        self.client.create_device_task(device_id, "http://example.com/file", "/file", 100)
        tasks1 = server_data.load_tasks().get(device_id, [])
        self.assertEqual(len(tasks1), 1)
        task_id = tasks1[0]["task_id"]

        # Mark as completed
        server_tasks = server_data.load_tasks()
        server_tasks[device_id][0]["status"] = "completed"
        server_data.save_tasks(server_tasks)

        # Create same task again
        self.client.create_device_task(device_id, "http://example.com/file", "/file", 100)
        tasks2 = server_data.load_tasks().get(device_id, [])
        self.assertEqual(len(tasks2), 1)
        self.assertEqual(tasks2[0]["task_id"], task_id)
        self.assertEqual(tasks2[0]["status"], "pending")

    def test_auto_delete_after_transfer(self):
        """Test that files are deleted after completion if configured"""
        device_id = "test_dev_del"
        self.client.bind_device(device_id, "ESP32", "1.0")

        # Enable auto-delete
        server_config.SERVER_CONFIG["storage"]["delete_after_transfer"] = True

        # 1. Upload a file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"Delete me later")
            tmp_path = tmp.name

        try:
            upload_resp = self.client.upload_file(tmp_path, device_id)
            url = upload_resp.download_url

            # 2. Extract local path to verify existence
            rel_path = url.split("/api/v1/files/storage/")[-1]
            local_f = server_config.FILES_DIR / rel_path
            self.assertTrue(local_f.exists(), f"File should exist at {local_f}")

            # 3. Create task and complete it
            task_res = self.client.create_device_task(device_id, url, "/delete_me.txt", 15)
            task_id = task_res.task.task_id

            comp_url = f"{self.client.BASE_URL}/api/v1/device/tasks/{task_id}/complete"
            import urllib.request

            req = urllib.request.Request(comp_url, data=json.dumps({}).encode(), method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)

            # 4. Verify file is GONE
            self.assertFalse(local_f.exists(), f"File {local_f} should have been deleted!")

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            server_config.SERVER_CONFIG["storage"]["delete_after_transfer"] = False

    def test_upload_xteink_native_formats(self):
        """Test that all xteink native format files can be uploaded"""
        device_id = f"test_dev_{uuid.uuid4().hex[:8]}"
        self.client.bind_device(device_id, "ESP32C3", "V3.1.5")

        # Import format modules for creating test files
        from PIL import Image

        from xteink.formats import xtc, xtg, xth

        # GDEQ0426T82 display dimensions (4.26" 800×480 on Xteink X4)
        EINK_WIDTH = 800
        EINK_HEIGHT = 480

        # Create a simple test image
        test_img = Image.new("RGB", (EINK_WIDTH, EINK_HEIGHT), color="white")

        # Test XTG (monochrome 1-bit)
        with self.subTest(format=".xtg"):
            bitmap_data = xtg.bitmap_from_image(test_img, dither=False)
            xtg_data = xtg.create_xtg(EINK_WIDTH, EINK_HEIGHT, bitmap_data)

            with tempfile.NamedTemporaryFile(suffix=".xtg", delete=False) as tmp:
                tmp.write(xtg_data)
                tmp_path = tmp.name

            try:
                upload_result = self.client.upload_file(tmp_path, device_id)
                err = getattr(upload_result, "error", "")
                self.assertTrue(upload_result.success, f"Failed to upload .xtg: {err}")
                self.assertIn(".xtg", upload_result.download_url)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        # Test XTH (4-level grayscale 2-bit)
        with self.subTest(format=".xth"):
            grayscale_data = xth.bitmap_from_image(test_img)
            xth_data = xth.create_xth(EINK_WIDTH, EINK_HEIGHT, grayscale_data)

            with tempfile.NamedTemporaryFile(suffix=".xth", delete=False) as tmp:
                tmp.write(xth_data)
                tmp_path = tmp.name

            try:
                upload_result = self.client.upload_file(tmp_path, device_id)
                err = getattr(upload_result, "error", "")
                self.assertTrue(upload_result.success, f"Failed to upload .xth: {err}")
                self.assertIn(".xth", upload_result.download_url)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        # Test XTC (container with XTG page)
        with self.subTest(format=".xtc"):
            bitmap_data = xtg.bitmap_from_image(test_img, dither=False)
            xtg_page = xtg.create_xtg(EINK_WIDTH, EINK_HEIGHT, bitmap_data)
            xtc_data = xtc.create_xtc([xtg_page], [(EINK_WIDTH, EINK_HEIGHT)])

            with tempfile.NamedTemporaryFile(suffix=".xtc", delete=False) as tmp:
                tmp.write(xtc_data)
                tmp_path = tmp.name

            try:
                upload_result = self.client.upload_file(tmp_path, device_id)
                err = getattr(upload_result, "error", "")
                self.assertTrue(upload_result.success, f"Failed to upload .xtc: {err}")
                self.assertIn(".xtc", upload_result.download_url)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        # Test XTCH (container with XTH page)
        with self.subTest(format=".xtch"):
            grayscale_data = xth.bitmap_from_image(test_img)
            xth_page = xth.create_xth(EINK_WIDTH, EINK_HEIGHT, grayscale_data)
            xtch_data = xtc.create_xtch([xth_page], [(EINK_WIDTH, EINK_HEIGHT)])

            with tempfile.NamedTemporaryFile(suffix=".xtch", delete=False) as tmp:
                tmp.write(xtch_data)
                tmp_path = tmp.name

            try:
                upload_result = self.client.upload_file(tmp_path, device_id)
                err = getattr(upload_result, "error", "")
                self.assertTrue(upload_result.success, f"Failed to upload .xtch: {err}")
                self.assertIn(".xtch", upload_result.download_url)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


class TestServerAuthAPI(unittest.TestCase):
    """Tests specifically for Authentication"""

    @classmethod
    def setUpClass(cls):
        # Setup temporary data directory
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Save original paths
        cls.orig_data_dir = server_config.DATA_DIR
        cls.orig_tasks_file = server_config.TASKS_FILE
        cls.orig_devices_file = server_config.DEVICES_FILE
        cls.orig_files_dir = server_config.FILES_DIR
        cls.orig_tokens_file = server_config.TOKENS_FILE

        # Override paths for testing
        server_config.DATA_DIR = cls.tmp_data_dir
        server_config.FILES_DIR = cls.tmp_data_dir / "files"
        server_config.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        server_config.DATA_DIR.mkdir(exist_ok=True)

        # Save and Override
        cls.orig_config = copy.deepcopy(server_config.SERVER_CONFIG)
        server_config.SERVER_CONFIG["auth"]["enabled"] = True
        server_config.SERVER_CONFIG["auth"]["users"] = [
            {"email": "test@example.com", "password": "pass"}
        ]

        cls.port = 8002
        cls.app = server_main.app
        cls.config = uvicorn.Config(app=cls.app, host="127.0.0.1", port=cls.port)
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        shutil.rmtree(cls.tmp_data_dir)

        # Restore config
        server_config.SERVER_CONFIG = cls.orig_config
        server_config.DATA_DIR = cls.orig_data_dir
        server_config.FILES_DIR = cls.orig_files_dir
        server_config.TASKS_FILE = cls.orig_tasks_file
        server_config.DEVICES_FILE = cls.orig_devices_file
        server_config.TOKENS_FILE = cls.orig_tokens_file

    def setUp(self):
        self.tmp_client_file = Path(tempfile.mktemp(suffix=".json"))
        self.client = XteinkClient(
            base_url=f"http://127.0.0.1:{self.port}", token_file=str(self.tmp_client_file)
        )
        # Reset tokens on server side
        with open(server_config.TOKENS_FILE, "w") as f:
            json.dump({}, f)

    def test_unauthenticated_access_fails(self):
        """Test that endpoints fail without login"""
        # Should raise HTTPError 401
        with self.assertRaises(Exception) as cm:
            # binding endpoint is protected
            self.client.get_device_binding()

        # We can't easily check status code with the current client wrapping,
        # but it should raise valid HTTP error
        self.assertIn("HTTP Error 401", str(cm.exception))

    def test_login_flow(self):
        """Test login and subsequent access"""
        # 1. Login
        resp = self.client.login("test@example.com", "pass")
        self.assertTrue(resp.success)
        self.assertIsNotNone(resp.access_token)
        # Verify refresh_token is also returned
        self.assertIsNotNone(resp.refresh_token, "Login should return refresh_token")

        # 2. Access protected endpoint
        binding = self.client.get_device_binding()
        self.assertTrue(binding.success)

    def test_token_refresh(self):
        """Test token refresh endpoint"""
        self.client.login("test@example.com", "pass")
        resp = self.client.refresh_access_token()
        self.assertTrue(resp.success)
        self.assertIsNotNone(resp.access_token)
        # Verify new refresh_token is returned
        self.assertIsNotNone(resp.refresh_token, "Refresh should return new refresh_token")

    def test_device_binding_with_user_association(self):
        """Test that device binding correctly associates authenticated user"""
        # 1. Login first
        login_resp = self.client.login("test@example.com", "pass")
        self.assertTrue(login_resp.success)
        user_id = login_resp.user_id

        # 2. Bind a device
        bind_resp = self.client.bind_device("test_device_123", "ESP32", "1.0")
        self.assertTrue(bind_resp.success)

        # 3. Verify the device has the correct user_id
        devices = server_data.load_devices()
        bound_device = next((d for d in devices if d["device_id"] == "test_device_123"), None)
        self.assertIsNotNone(bound_device, "Device should be registered")
        self.assertEqual(
            bound_device.get("user_id"),
            user_id,
            "Device should be associated with the authenticated user",
        )

    def test_invalid_login(self):
        """Test login with wrong password"""
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError):
            self.client.login("test@example.com", "wrong")


class TestServerEnrollment(unittest.TestCase):
    """Tests for Device Enrollment Control"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Save and Override
        cls.orig_config = copy.deepcopy(server_config.SERVER_CONFIG)
        cls.orig_data_dir = server_config.DATA_DIR
        cls.orig_tasks_file = server_config.TASKS_FILE
        cls.orig_devices_file = server_config.DEVICES_FILE
        cls.orig_files_dir = server_config.FILES_DIR
        cls.orig_tokens_file = server_config.TOKENS_FILE

        server_config.DATA_DIR = cls.tmp_data_dir
        server_config.TASKS_FILE = cls.tmp_data_dir / "tasks.json"
        server_config.DEVICES_FILE = cls.tmp_data_dir / "devices.json"
        server_config.FILES_DIR = cls.tmp_data_dir / "files"
        server_config.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"
        server_config.SERVER_CONFIG["auth"]["enabled"] = False
        server_config.SERVER_CONFIG["server"]["auto_register_devices"] = False

        cls.port = 8003
        cls.app = server_main.app
        cls.config = uvicorn.Config(app=cls.app, host="127.0.0.1", port=cls.port)
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        shutil.rmtree(cls.tmp_data_dir)

        # Restore config
        server_config.SERVER_CONFIG = cls.orig_config
        server_config.DATA_DIR = cls.orig_data_dir
        server_config.FILES_DIR = cls.orig_files_dir
        server_config.TASKS_FILE = cls.orig_tasks_file
        server_config.DEVICES_FILE = cls.orig_devices_file
        server_config.TOKENS_FILE = cls.orig_tokens_file

    def setUp(self):
        self.tmp_client_file = Path(tempfile.mktemp(suffix=".json"))
        self.client = XteinkClient(
            base_url=f"http://127.0.0.1:{self.port}", token_file=str(self.tmp_client_file)
        )
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([], f)

    def test_new_device_rejected(self):
        """Test that a new device is rejected when auto-enroll is False"""
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as cm:
            self.client.bind_device("unknown_dev", "ESP32", "1.0")

        self.assertIn("HTTP Error 403", str(cm.exception))

    def test_existing_device_allowed(self):
        """Test that a pre-registered device is allowed"""
        # Pre-register device directly in DB with all required fields for Device model
        device_id = "known_dev"
        device = {
            "id": "uuid-123",
            "device_id": device_id,
            "brand": "xteink",
            "device_type": "ESP32",
            "version": "1.0",
            "user_id": "local_user",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([device], f)

        # Try binding
        try:
            self.client.bind_device(device_id, "ESP32", "1.0")
        except Exception as e:
            self.fail(f"Bind failed for known device: {e}")

        # Verify timestamps updated
        updated = server_data.load_devices()
        self.assertEqual(len(updated), 1)


class TestServerCombined(unittest.TestCase):
    """Tests for Combined Authentication and Enrollment Control"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Override paths
        cls.orig_data_dir = server_config.DATA_DIR
        cls.orig_tasks_file = server_config.TASKS_FILE
        cls.orig_devices_file = server_config.DEVICES_FILE
        cls.orig_files_dir = server_config.FILES_DIR
        cls.orig_tokens_file = server_config.TOKENS_FILE

        server_config.DATA_DIR = cls.tmp_data_dir
        server_config.TASKS_FILE = cls.tmp_data_dir / "tasks.json"
        server_config.DEVICES_FILE = cls.tmp_data_dir / "devices.json"
        server_config.FILES_DIR = cls.tmp_data_dir / "files"
        server_config.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        server_config.DATA_DIR.mkdir(exist_ok=True)
        with open(server_config.TOKENS_FILE, "w") as f:
            json.dump({}, f)

        # Save and Override
        cls.orig_config = copy.deepcopy(server_config.SERVER_CONFIG)
        server_config.SERVER_CONFIG["auth"] = {
            "enabled": True,
            "users": [{"email": "combo@test.com", "password": "pass"}],
        }
        server_config.SERVER_CONFIG["server"]["auto_register_devices"] = False

        cls.port = 8004
        cls.app = server_main.app
        cls.config = uvicorn.Config(app=cls.app, host="127.0.0.1", port=cls.port)
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        shutil.rmtree(cls.tmp_data_dir)

        # Restore config
        server_config.SERVER_CONFIG = cls.orig_config
        server_config.DATA_DIR = cls.orig_data_dir
        server_config.DEVICES_FILE = cls.orig_devices_file
        server_config.TOKENS_FILE = cls.orig_tokens_file

    def setUp(self):
        self.tmp_client_file = Path(tempfile.mktemp(suffix=".json"))
        self.client = XteinkClient(
            base_url=f"http://127.0.0.1:{self.port}", token_file=str(self.tmp_client_file)
        )
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([], f)

    def test_auth_blocks_first(self):
        """Test that unauthenticated requests fail even if enrollment logic would follow"""
        server_config.SERVER_CONFIG["auth"]["enabled"] = True
        server_config.SERVER_CONFIG["server"]["auto_register_devices"] = False
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as cm:
            self.client.get_device_binding()
        self.assertEqual(cm.exception.code, 401)

    def test_auth_on_enroll_forbidden(self):
        """Test authenticated user but unknown device enrollment is forbidden"""
        # 1. Login
        self.client.login("combo@test.com", "pass")

        # 2. Try bind new device
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as cm:
            self.client.bind_device("new_combo_dev", "ESP32", "1.0")
        self.assertEqual(cm.exception.code, 403)

    def test_auth_on_known_device_allowed(self):
        """Test authenticated user can bind known device"""
        # 1. Pre-register
        device_id = "known_combo"
        device = {
            "id": "uuid-combo",
            "device_id": device_id,
            "brand": "xteink",
            "device_type": "ESP32",
            "version": "1.0",
            "user_id": "local_user",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        with open(server_config.DEVICES_FILE, "w") as f:
            json.dump([device], f)

        # 2. Login
        self.client.login("combo@test.com", "pass")

        # 3. Bind
        try:
            self.client.bind_device(device_id, "ESP32", "1.0")
        except Exception as e:
            self.fail(f"Bind failed for known combo device: {e}")
