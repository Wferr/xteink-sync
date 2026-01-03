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


if __name__ == "__main__":
    unittest.main()
