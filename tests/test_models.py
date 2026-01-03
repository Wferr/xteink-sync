#!/usr/bin/env python3
"""
Comprehensive model validation tests.
Tests that all Pydantic models validate data correctly.
"""

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xteink.models import (
    AuthRequest,
    BaseResponse,
    DeviceBindingResponse,
    FileUploadResponse,
    ImageResizeResponse,
    MessageResponse,
    Task,
    TaskCreateRequest,
    TaskListResponse,
)


class TestModels(unittest.TestCase):
    def test_base_response_validation(self):
        """Test BaseResponse model validation"""
        # Valid data
        resp = BaseResponse(success=True)
        self.assertTrue(resp.success)

        # Invalid data should raise ValidationError
        with self.assertRaises(ValidationError):
            BaseResponse()  # Missing required field

    def test_message_response_validation(self):
        """Test MessageResponse with defaults"""
        # With message only (success defaults to True)
        resp = MessageResponse(message="test")
        self.assertEqual(resp.message, "test")
        self.assertTrue(resp.success)

        # With both fields
        resp2 = MessageResponse(message="error", success=False)
        self.assertFalse(resp2.success)

    def test_auth_request_validation(self):
        """Test AuthRequest requires email and password"""
        # Valid
        req = AuthRequest(email="test@example.com", password="pass123")
        self.assertEqual(req.email, "test@example.com")

        # Missing fields
        with self.assertRaises(ValidationError):
            AuthRequest(email="test@example.com")  # Missing password

    def test_task_model_validation(self):
        """Test Task model with required and optional fields"""
        # Minimal valid task
        task = Task(
            task_id="123",
            file_url="http://example.com/file.txt",
            save_path="/file.txt",
            status="pending",
            type="file_transfer",
            created_at=1234567890,
            expires_at=1234567890,
        )
        self.assertEqual(task.task_id, "123")
        self.assertIsNone(task.device_id)  # Optional field

        # With optional device_id
        task2 = Task(
            task_id="456",
            device_id="device789",
            file_url="http://example.com/file.txt",
            save_path="/file.txt",
            status="completed",
            type="file_transfer",
            created_at=1234567890,
            expires_at=1234567890,
        )
        self.assertEqual(task2.device_id, "device789")

    def test_task_create_request_validation(self):
        """Test TaskCreateRequest validation"""
        # Valid request
        req = TaskCreateRequest(
            device_id="device123",
            file_url="http://example.com/file.txt",
            save_path="/file.txt",
        )
        self.assertEqual(req.device_id, "device123")
        self.assertEqual(req.type, "file_transfer")  # Default value

        # Missing required field
        with self.assertRaises(ValidationError):
            TaskCreateRequest(device_id="device123", file_url="http://example.com/file.txt")

    def test_file_upload_response_validation(self):
        """Test FileUploadResponse model"""
        resp = FileUploadResponse(
            filename="file.txt",
            download_url="http://example.com/download/file.txt",
            success=True,
        )
        self.assertEqual(resp.filename, "file.txt")
        self.assertEqual(resp.download_url, "http://example.com/download/file.txt")
        self.assertTrue(resp.success)

    def test_image_resize_response_validation(self):
        """Test ImageResizeResponse with multiple download URLs"""
        resp = ImageResizeResponse(
            download_url_fs="http://example.com/fs.bmp",
            download_url_none="http://example.com/none.bmp",
            download_url_xtg="http://example.com/xtg.xtc",
            download_url_xth="http://example.com/xth.xtch",
            download_url_xtch="http://example.com/xtch.xtch",
            success=True,
        )
        self.assertTrue(resp.download_url_fs.startswith("http://"))
        self.assertTrue(resp.download_url_xtg.endswith(".xtc"))
        self.assertTrue(resp.success)

    def test_task_list_response_validation(self):
        """Test TaskListResponse with task list"""
        resp = TaskListResponse(
            success=True,
            tasks=[],
            total=0,
            total_done=0,
            total_pending=0,
            total_processing=0,
        )
        self.assertEqual(resp.tasks, [])
        self.assertEqual(resp.total_pending, 0)
        self.assertTrue(resp.success)

    def test_device_binding_response_validation(self):
        """Test DeviceBindingResponse"""
        from xteink.models import Device

        device = Device(
            brand="xteink",
            created_at="2024-01-01T00:00:00Z",
            device_id="device123",
            device_type="ESP32C3",
            id="id123",
            updated_at="2024-01-01T00:00:00Z",
            user_id="user123",
            version="V3.1.5",
        )

        resp = DeviceBindingResponse(data=[device], success=True)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0].device_id, "device123")


if __name__ == "__main__":
    unittest.main()
