#!/usr/bin/env python3
"""
Basic smoke tests for xteink-sync functionality.
Tests imports, basic instantiation, and model validation.
"""

import sys
import unittest
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSmoke(unittest.TestCase):
    def test_imports(self):
        """Test that all modules can be imported"""
        # If we get here, all imports succeeded
        from xteink.docs import app

        self.assertIsNotNone(app)

    def test_models(self):
        """Test that models can be instantiated and validated"""
        from xteink.models import (
            AuthRequest,
            BaseResponse,
            MessageResponse,
            Task,
            TaskCreateRequest,
        )

        # Test generic responses
        base_resp = BaseResponse(success=True)
        self.assertTrue(base_resp.success)

        msg_resp = MessageResponse(message="test")
        self.assertEqual(msg_resp.message, "test")
        self.assertTrue(msg_resp.success)

        # Test auth request
        auth_req = AuthRequest(email="test@example.com", password="pass")
        self.assertEqual(auth_req.email, "test@example.com")

        # Test task
        task = Task(
            task_id="test123",
            file_url="http://example.com/file.jpg",
            save_path="/test.jpg",
            status="pending",
            type="file_transfer",
            created_at=1234567890,
            expires_at=1234567890,
        )
        self.assertEqual(task.task_id, "test123")

        # Test task create request
        task_req = TaskCreateRequest(
            device_id="device123",
            file_url="http://example.com/file.jpg",
            save_path="/test.jpg",
        )
        self.assertEqual(task_req.device_id, "device123")

    def test_client_instantiation(self):
        """Test that client can be instantiated"""
        from xteink.client import PRODUCTION_API_URL, XteinkClient

        # Test with default URL
        client = XteinkClient()
        self.assertEqual(client.BASE_URL, PRODUCTION_API_URL)

        # Test with custom URL
        custom_client = XteinkClient(base_url="http://localhost:8000")
        self.assertEqual(custom_client.BASE_URL, "http://localhost:8000")

    def test_custom_server_imports(self):
        """Test that custom server can be imported"""
        custom_server_path = Path(__file__).parent.parent
        sys.path.insert(0, str(custom_server_path))

        import server.core.data as server_data

        # Just check that the module loads
        self.assertTrue(hasattr(server_data, "load_tasks"))
        self.assertTrue(hasattr(server_data, "save_tasks"))

    def test_docs_server(self):
        """Test that docs server can be imported"""
        from xteink.docs import app

        self.assertEqual(app.title, "Xteink API Reference")


if __name__ == "__main__":
    unittest.main()
