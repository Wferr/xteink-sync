import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from server.core import config
from server.main import app


class TestServerFiles(unittest.TestCase):
    def setUp(self):
        super().setUp()
        import copy

        self.orig_config = copy.deepcopy(config.SERVER_CONFIG)
        # Ensure a valid test config
        config.SERVER_CONFIG["auth"] = {
            "enabled": True,
            "users": [{"email": "admin@example.com", "password": "admin"}],
        }
        config.SERVER_CONFIG["server"] = {
            "default_resize_mode": "cover",
            "auto_register_devices": True,
        }
        config.SERVER_CONFIG["storage"] = {
            "max_file_size_bytes": 100 * 1024 * 1024,
        }

        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_files_dir = config.FILES_DIR
        config.FILES_DIR = self.tmp_dir / "files"
        config.FILES_DIR.mkdir(parents=True)

        self.client = TestClient(app)

        # Login
        resp = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "admin"},
        )
        self.assertEqual(resp.status_code, 200, f"Login failed: {resp.text}")
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"
        else:
            # If auth disabled or failed, maybe we don't need it?
            # But tests expect 401 if not.
            pass

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        config.FILES_DIR = self.orig_files_dir
        config.SERVER_CONFIG = self.orig_config

    @patch("httpx.AsyncClient")
    def test_remote_image_resize_download(self, mock_client_cls):
        print("DEBUG: Inside test_remote_image_resize_download")
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Load real image from fixtures
        fixtures_dir = Path(__file__).parent / "fixtures"
        img_path = fixtures_dir / "sample.jpg"
        with open(img_path, "rb") as f:
            sample_jpg = f.read()

        mock_response.content = sample_jpg

        mock_ac_instance = AsyncMock()
        mock_ac_instance.get.return_value = mock_response

        # When 'async with httpx.AsyncClient() as client' is called:
        # httpx.AsyncClient() returns the instance.
        # __aenter__ returns the instance.
        mock_ac_instance.__aenter__.return_value = mock_ac_instance

        # We patch the CLASS, so calling it returns our instance
        with patch("httpx.AsyncClient", return_value=mock_ac_instance):
            resp = self.client.post(
                "/api/v1/ai/image_resize",
                json={
                    "image_url": "https://images.pdimagearchive.org/collections/marinus-pieter-filbri-microscopy/RP-F-F01133-AZ.jpg",
                    "device_id": "test_dev_1",
                },
            )

        if resp.status_code != 200:
            print(f"DEBUG: TestServerFiles 401 Body: {resp.text}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("download_url_xtg", data)
        self.assertIn("download_url_xth", data)
        self.assertIn("resize_", data["download_url"])

        # Verify file creation
        fname = data["download_url"].split("/")[-1]
        xtg_name = data["download_url_xtg"].split("/")[-1]

        self.assertTrue((config.FILES_DIR / "image_resize" / fname).exists())
        self.assertTrue((config.FILES_DIR / "image_resize" / xtg_name).exists())


if __name__ == "__main__":
    unittest.main()
