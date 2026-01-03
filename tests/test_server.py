#!/usr/bin/env python3
"""
Comprehensive tests for custom sync server functionality.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestServer(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
        import server

        self.server = server

    def test_server_file_validation(self):
        """Test that server has supported extensions defined"""
        # Test that SUPPORTED_EXTENSIONS exists and has expected values
        self.assertTrue(hasattr(self.server, "SUPPORTED_EXTENSIONS"))
        self.assertIn(".txt", self.server.SUPPORTED_EXTENSIONS)
        self.assertIn(".jpg", self.server.SUPPORTED_EXTENSIONS)
        self.assertIn(".epub", self.server.SUPPORTED_EXTENSIONS)
        self.assertIn(".xtc", self.server.SUPPORTED_EXTENSIONS)
        self.assertIn(".bmp", self.server.SUPPORTED_EXTENSIONS)

        # Verify unsupported types are not in the set
        self.assertNotIn(".pdf", self.server.SUPPORTED_EXTENSIONS)
        self.assertNotIn(".png", self.server.SUPPORTED_EXTENSIONS)

    def test_server_task_management(self):
        """Test task creation and retrieval"""
        # Create temporary tasks file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_tasks_file = f.name
            json.dump({}, f)

        try:
            # Override tasks file path
            original_tasks_file = self.server.TASKS_FILE
            self.server.TASKS_FILE = Path(temp_tasks_file)

            # Test loading empty tasks
            tasks = self.server.load_tasks()
            self.assertEqual(tasks, {})

            # Test saving tasks for multiple devices
            test_tasks = {
                "device1": [
                    {
                        "task_id": "task123",
                        "device_id": "device1",
                        "file_url": "http://example.com/file.txt",
                        "save_path": "/test.txt",
                        "status": "pending",
                    }
                ],
                "device2": [
                    {
                        "task_id": "task456",
                        "device_id": "device2",
                        "file_url": "http://example.com/image.jpg",
                        "save_path": "/image.jpg",
                        "status": "completed",
                    }
                ],
            }
            self.server.save_tasks(test_tasks)

            # Test loading saved tasks
            loaded_tasks = self.server.load_tasks()
            self.assertEqual(len(loaded_tasks), 2)
            self.assertIn("device1", loaded_tasks)
            self.assertIn("device2", loaded_tasks)
            self.assertEqual(loaded_tasks["device1"][0]["task_id"], "task123")
            self.assertEqual(loaded_tasks["device2"][0]["status"], "completed")

        finally:
            # Cleanup
            self.server.TASKS_FILE = original_tasks_file
            Path(temp_tasks_file).unlink(missing_ok=True)

    def test_server_device_management(self):
        """Test device registration and persistence"""
        # Create temporary devices file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_devices_file = f.name
            json.dump([], f)

        try:
            # Override devices file path
            original_devices_file = self.server.DEVICES_FILE
            self.server.DEVICES_FILE = Path(temp_devices_file)

            # Test loading empty devices
            devices = self.server.load_devices()
            self.assertEqual(devices, [])

            # Test registering a device
            self.server.register_device("device_id_123")
            devices = self.server.load_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]["device_id"], "device_id_123")
            self.assertEqual(devices[0]["brand"], "xteink")
            self.assertEqual(devices[0]["device_type"], "ESP32C3")
            self.assertEqual(devices[0]["user_id"], "local_user")
            self.assertIn("created_at", devices[0])

            # Test that duplicate registration doesn't create duplicates
            self.server.register_device("device_id_123")
            devices = self.server.load_devices()
            self.assertEqual(
                len(devices), 1, "Duplicate device registration should not create duplicates"
            )

            # Test registering multiple devices
            self.server.register_device("device_id_456")
            devices = self.server.load_devices()
            self.assertEqual(len(devices), 2)
            device_ids = [d["device_id"] for d in devices]
            self.assertIn("device_id_123", device_ids)
            self.assertIn("device_id_456", device_ids)

        finally:
            # Cleanup
            self.server.DEVICES_FILE = original_devices_file
            Path(temp_devices_file).unlink(missing_ok=True)

    def test_server_task_structure(self):
        """Test that tasks have the correct structure"""
        # Create temporary tasks file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_tasks_file = f.name
            json.dump({}, f)

        try:
            original_tasks_file = self.server.TASKS_FILE
            self.server.TASKS_FILE = Path(temp_tasks_file)

            # Create a task
            test_task = {
                "task_id": "test_task_123",
                "device_id": "test_device",
                "file_url": "http://example.com/file.txt",
                "save_path": "/path/to/file.txt",
                "size": 1024,
                "status": "pending",
                "type": "file_transfer",
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 86400,
                "metadata": {"key": "value"},
            }

            tasks = {"test_device": [test_task]}
            self.server.save_tasks(tasks)

            # Load and verify structure
            loaded = self.server.load_tasks()
            self.assertEqual(loaded["test_device"][0]["task_id"], "test_task_123")
            self.assertEqual(loaded["test_device"][0]["device_id"], "test_device")
            self.assertEqual(loaded["test_device"][0]["status"], "pending")
            self.assertEqual(loaded["test_device"][0]["type"], "file_transfer")
            self.assertIn("created_at", loaded["test_device"][0])
            self.assertIn("expires_at", loaded["test_device"][0])

        finally:
            self.server.TASKS_FILE = original_tasks_file
            Path(temp_tasks_file).unlink(missing_ok=True)

    def test_server_device_structure(self):
        """Test that devices have the correct structure"""
        # Create temporary devices file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_devices_file = f.name
            json.dump([], f)

        try:
            original_devices_file = self.server.DEVICES_FILE
            self.server.DEVICES_FILE = Path(temp_devices_file)

            # Register and verify structure
            self.server.register_device("test_device_456")
            devices = self.server.load_devices()
            device = devices[0]

            # Verify required fields match Device model
            self.assertIn("id", device)
            self.assertIn("device_id", device)
            self.assertEqual(device["device_id"], "test_device_456")
            self.assertIn("brand", device)
            self.assertEqual(device["brand"], "xteink")
            self.assertIn("device_type", device)
            self.assertEqual(device["device_type"], "ESP32C3")
            self.assertIn("version", device)
            self.assertIn("user_id", device)
            self.assertEqual(device["user_id"], "local_user")
            self.assertIn("created_at", device)
            self.assertIn("updated_at", device)

        finally:
            self.server.DEVICES_FILE = original_devices_file
            Path(temp_devices_file).unlink(missing_ok=True)

    def test_parse_size(self):
        """Test the parse_size utility function"""
        # Valid cases
        self.assertEqual(self.server.parse_size("100MB"), 100 * 1024 * 1024)
        self.assertEqual(self.server.parse_size("1GB"), 1024 * 1024 * 1024)
        self.assertEqual(self.server.parse_size("1024"), 1024)
        self.assertEqual(self.server.parse_size(2048), 2048)
        self.assertEqual(self.server.parse_size("1.5MB"), int(1.5 * 1024 * 1024))
        self.assertEqual(self.server.parse_size("500b"), 500)

        # Default/Fallback
        self.assertEqual(self.server.parse_size(None), 100 * 1024 * 1024)
        self.assertEqual(self.server.parse_size(""), 100 * 1024 * 1024)
        self.assertEqual(self.server.parse_size("invalid"), 100 * 1024 * 1024)

        # Unit variations
        self.assertEqual(self.server.parse_size("1KB"), 1024)
        self.assertEqual(self.server.parse_size("1kbs"), 1024)

    def test_load_server_config_missing(self):
        """Test loading config when file is missing"""
        orig_base = self.server.BASE_DIR
        # Point to a directory that definitely doesn't have config.toml
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.server.BASE_DIR = Path(tmp_dir)
            config = self.server.load_server_config()
            self.assertEqual(config["port"], 8000)
            self.assertEqual(config["host"], "0.0.0.0")
        self.server.BASE_DIR = orig_base

    def test_load_server_config_valid(self):
        """Test loading a valid config.toml"""
        orig_base = self.server.BASE_DIR
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self.server.BASE_DIR = tmp_path
            config_file = tmp_path / "config.toml"
            with open(config_file, "w") as f:
                f.write('[server]\nport = 9000\nhost = "127.0.0.1"\n')
                f.write('[storage]\nmax_file_size = "50MB"\n')

            config = self.server.load_server_config()
            self.assertEqual(config["port"], 9000)
            self.assertEqual(config["host"], "127.0.0.1")
            self.assertEqual(config["max_file_size"], "50MB")
        self.server.BASE_DIR = orig_base


if __name__ == "__main__":
    unittest.main()
