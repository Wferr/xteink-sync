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
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

import server
from xteink.client import XteinkClient


class TestServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup temporary data directory
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Save original paths
        cls.orig_data_dir = server.DATA_DIR
        cls.orig_tasks_file = server.TASKS_FILE
        cls.orig_devices_file = server.DEVICES_FILE
        cls.orig_files_dir = server.FILES_DIR

        # Override paths for testing
        server.DATA_DIR = cls.tmp_data_dir
        server.TASKS_FILE = cls.tmp_data_dir / "tasks.json"
        server.DEVICES_FILE = cls.tmp_data_dir / "devices.json"
        server.FILES_DIR = cls.tmp_data_dir / "files"

        server.DATA_DIR.mkdir(exist_ok=True)
        server.FILES_DIR.mkdir(exist_ok=True)
        server.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        with open(server.TASKS_FILE, "w") as f:
            json.dump({}, f)
        with open(server.DEVICES_FILE, "w") as f:
            json.dump([], f)

        cls.port = 8001
        cls.app = server.create_app()
        cls.config = uvicorn.Config(app=cls.app, host="127.0.0.1", port=cls.port, log_level="error")
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()

        # Wait for server to start
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        # Stop uvicorn server
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)

        # Cleanup data dir
        shutil.rmtree(cls.tmp_data_dir)

        # Restore original paths
        server.DATA_DIR = cls.orig_data_dir
        server.TASKS_FILE = cls.orig_tasks_file
        server.DEVICES_FILE = cls.orig_devices_file
        server.FILES_DIR = cls.orig_files_dir

    def setUp(self):
        self.client = XteinkClient(base_url=f"http://127.0.0.1:{self.port}")
        # Clear data between tests
        with open(server.TASKS_FILE, "w") as f:
            json.dump({}, f)
        with open(server.DEVICES_FILE, "w") as f:
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
        devices = server.load_devices()
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

    def test_broadcast_task_to_all(self):
        """Test broadcasting a task to all registered devices"""
        # 1. Register two devices
        self.client.bind_device("dev1", "ESP32C3", "V3.1.5")
        self.client.bind_device("dev2", "ESP32C3", "V3.1.5")

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
        updated_tasks = server.load_tasks()
        self.assertEqual(updated_tasks[device_id][0]["status"], "completed")


class TestServerAuthAPI(unittest.TestCase):
    """Tests specifically for Authentication"""

    @classmethod
    def setUpClass(cls):
        # Setup temporary data directory
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Save original paths
        cls.orig_data_dir = server.DATA_DIR
        cls.orig_tokens_file = server.TOKENS_FILE

        # Override paths for testing
        server.DATA_DIR = cls.tmp_data_dir
        server.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        server.DATA_DIR.mkdir(exist_ok=True)

        # ENABLE AUTH
        cls.orig_enable_auth = server.ENABLE_AUTH
        server.ENABLE_AUTH = True
        server.ACCOUNTS = [{"email": "test@example.com", "password": "pass"}]

        cls.port = 8002
        cls.app = server.create_app()
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

        # Restore globals
        server.DATA_DIR = cls.orig_data_dir
        server.TOKENS_FILE = cls.orig_tokens_file
        server.ENABLE_AUTH = cls.orig_enable_auth

    def setUp(self):
        self.client = XteinkClient(base_url=f"http://127.0.0.1:{self.port}")
        # Reset tokens
        with open(server.TOKENS_FILE, "w") as f:
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

        # 2. Access protected endpoint
        binding = self.client.get_device_binding()
        self.assertTrue(binding.success)

    def test_invalid_login(self):
        """Test login with wrong password"""
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError):
            self.client.login("test@example.com", "wrong")


if __name__ == "__main__":
    unittest.main()


class TestServerEnrollment(unittest.TestCase):
    """Tests for Device Enrollment Control"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Override paths
        cls.orig_data_dir = server.DATA_DIR
        cls.orig_devices_file = server.DEVICES_FILE
        server.DATA_DIR = cls.tmp_data_dir
        server.DEVICES_FILE = cls.tmp_data_dir / "devices.json"

        server.DATA_DIR.mkdir(exist_ok=True)

        # DISABLE AUTO ENROLLMENT
        cls.orig_auto_reg = server.AUTO_REGISTER_DEVICES
        server.AUTO_REGISTER_DEVICES = False

        cls.port = 8003
        cls.app = server.create_app()
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

        # Restore globals
        server.DATA_DIR = cls.orig_data_dir
        server.DEVICES_FILE = cls.orig_devices_file
        server.AUTO_REGISTER_DEVICES = cls.orig_auto_reg

    def setUp(self):
        self.client = XteinkClient(base_url=f"http://127.0.0.1:{self.port}")
        with open(server.DEVICES_FILE, "w") as f:
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
        with open(server.DEVICES_FILE, "w") as f:
            json.dump([device], f)

        # Try binding
        try:
            self.client.bind_device(device_id, "ESP32", "1.0")
        except Exception as e:
            self.fail(f"Bind failed for known device: {e}")

        # Verify timestamps updated
        updated = server.load_devices()
        self.assertEqual(len(updated), 1)


class TestServerCombined(unittest.TestCase):
    """Tests for Combined Authentication and Enrollment Control"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_data_dir = Path(tempfile.mkdtemp())

        # Override paths
        cls.orig_data_dir = server.DATA_DIR
        cls.orig_devices_file = server.DEVICES_FILE
        cls.orig_tokens_file = server.TOKENS_FILE

        server.DATA_DIR = cls.tmp_data_dir
        server.DEVICES_FILE = cls.tmp_data_dir / "devices.json"
        server.TOKENS_FILE = cls.tmp_data_dir / "tokens.json"

        server.DATA_DIR.mkdir(exist_ok=True)
        with open(server.TOKENS_FILE, "w") as f:
            json.dump({}, f)

        # ENABLE BOTH: AUTH ON, AUTO-ENROLL OFF
        cls.orig_enable_auth = server.ENABLE_AUTH
        cls.orig_auto_reg = server.AUTO_REGISTER_DEVICES

        server.ENABLE_AUTH = True
        server.AUTO_REGISTER_DEVICES = False
        server.ACCOUNTS = [{"email": "combo@test.com", "password": "pass"}]

        cls.port = 8004
        cls.app = server.create_app()
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

        # Restore globals
        server.DATA_DIR = cls.orig_data_dir
        server.DEVICES_FILE = cls.orig_devices_file
        server.TOKENS_FILE = cls.orig_tokens_file
        server.ENABLE_AUTH = cls.orig_enable_auth
        server.AUTO_REGISTER_DEVICES = cls.orig_auto_reg

    def setUp(self):
        self.client = XteinkClient(base_url=f"http://127.0.0.1:{self.port}")
        with open(server.DEVICES_FILE, "w") as f:
            json.dump([], f)

    def test_auth_blocks_first(self):
        """Test that unauthenticated requests fail even if enrollment logic would follow"""
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
        with open(server.DEVICES_FILE, "w") as f:
            json.dump([device], f)

        # 2. Login
        self.client.login("combo@test.com", "pass")

        # 3. Bind
        try:
            self.client.bind_device(device_id, "ESP32", "1.0")
        except Exception as e:
            self.fail(f"Bind failed for known combo device: {e}")
