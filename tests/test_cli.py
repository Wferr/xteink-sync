#!/usr/bin/env python3
"""
Integration tests for CLI commands.
"""

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from xteink.models import (
    AuthResponse,
    Device,
    DeviceBindingResponse,
    FileUploadResponse,
    HealthResponse,
    LogoutResponse,
    MessageResponse,
    Task,
    TaskCreateResponse,
    TaskListResponse,
    TaskStatus,
)


class TestCLI(unittest.TestCase):
    def test_cli_help(self):
        """Test that --help displays usage information"""
        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "--help"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 0)
                output = fake_out.getvalue()
                self.assertIn("Xteink Cloud Sync CLI", output)
                self.assertIn("--server", output)
                self.assertIn("auth", output)
                self.assertIn("devices", output)
                self.assertIn("tasks", output)

    def test_auth_subcommand_help(self):
        """Test that auth subcommand has help text"""
        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "auth", "--help"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 0)
                output = fake_out.getvalue()
                self.assertIn("Auth subcommands", output)
                self.assertIn("login", output)
                self.assertIn("register", output)
                self.assertIn("logout", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_auth_login(self, mock_client_class):
        """Test auth login command"""
        mock_client = mock_client_class.return_value
        mock_client.login.return_value = AuthResponse(
            access_token="fake_token", success=True, user_id="user_123"
        )

        from xteink.cli.main import main

        args = ["xteink", "auth", "login", "--email", "test@test.com", "--password", "pass"]
        with patch("sys.argv", args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Login successful", output)
                self.assertIn("user_123", output)
                mock_client.login.assert_called_once_with("test@test.com", "pass")

    @patch("xteink.cli.main.XteinkClient")
    def test_auth_logout(self, mock_client_class):
        """Test auth logout command"""
        mock_client = mock_client_class.return_value
        mock_client.logout.return_value = LogoutResponse(message="Logged out", success=True)

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "auth", "logout"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Logged out", output)
                mock_client.logout.assert_called_once()

    @patch("xteink.cli.main.XteinkClient")
    def test_devices_list(self, mock_client_class):
        """Test devices list command"""
        mock_client = mock_client_class.return_value
        device = Device(
            id="1",
            device_id="dev1",
            brand="xteink",
            device_type="ESP32",
            version="1.0",
            user_id="u1",
            created_at="now",
            updated_at="now",
        )
        mock_client.get_device_binding.return_value = DeviceBindingResponse(
            data=[device], success=True
        )

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "devices"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("dev1", output)
                self.assertIn("ESP32", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_tasks_list(self, mock_client_class):
        """Test tasks list command"""
        mock_client = mock_client_class.return_value
        task = Task(
            task_id="t1",
            device_id="dev1",
            status=TaskStatus.PENDING,
            file_url="http://f.com",
            save_path="/p.txt",
        )
        mock_client.get_device_tasks.return_value = TaskListResponse(
            success=True, tasks=[task], total=1, total_done=0, total_pending=1, total_processing=0
        )

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "tasks", "dev1"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("t1", output)
                self.assertIn("PENDING", output)

    @patch("xteink.cli.main.XteinkClient")
    @patch("xteink.cli.tasks.os.path.exists")
    @patch("xteink.cli.tasks.os.path.getsize")
    def test_send_command(self, mock_getsize, mock_exists, mock_client_class):
        """Test send command (high level integration)"""
        mock_exists.return_value = True
        mock_getsize.return_value = 100
        mock_client = mock_client_class.return_value

        from xteink.models import ImageResizeResponse

        # Mock upload
        mock_client.upload_file.return_value = FileUploadResponse(
            download_url="http://u.com/f.txt", filename="f.txt", success=True
        )

        # Mock resize
        mock_client.image_resize.return_value = ImageResizeResponse(
            success=True,
            download_url_fs="http://u.com/f_fs.txt",
            filename_fs="f_fs.txt",
        )

        # Mock create task
        task = Task(
            task_id="t1",
            device_id="dev1",
            status=TaskStatus.PENDING,
            file_url="http://u.com/f_fs.txt",
            save_path="/f.txt",
        )
        mock_client.create_device_task.return_value = TaskCreateResponse(success=True, task=task)

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "send", "local.txt", "dev1", "/remote.txt"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Uploaded", output)
                self.assertIn("Task created successfully", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_health_command(self, mock_client_class):
        """Test health command"""
        mock_client = mock_client_class.return_value
        mock_client.get_health.return_value = HealthResponse(message="OK", status="healthy")

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "health"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Healthy", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_qr_parse_command(self, mock_client_class):
        """Test qr-parse command"""
        mock_client = mock_client_class.return_value
        mock_client.parse_qr_code.return_value = {
            "brand": "xteink",
            "device_type": "ESP32",
            "version": "1.0",
            "mac_address": "AA:BB",
            "device_id": "qr_dev_123",
        }

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "qr-parse", "deadbeef"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("qr_dev_123", output)
                self.assertIn("xteink", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_auth_register(self, mock_client_class):
        """Test auth register command"""
        mock_client = mock_client_class.return_value
        from xteink.models import RegisterResponse, User

        user = User(
            id="u1",
            email="t@t.com",
            nickname="nick",
            role="user",
            is_active=True,
            created_at="now",
            updated_at="now",
        )
        mock_client.register.return_value = RegisterResponse(
            access_token="a", refresh_token="r", user=user, message="Success"
        )

        from xteink.cli.main import main

        args = [
            "xteink",
            "auth",
            "register",
            "--email",
            "t@t.com",
            "--nickname",
            "nick",
            "--password",
            "p",
        ]
        with patch("sys.argv", args):
            with patch("builtins.input", return_value="123456"):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    main()
                    output = fake_out.getvalue()
                    self.assertIn("Registration successful", output)
                    self.assertIn("nick", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_auth_refresh(self, mock_client_class):
        """Test auth refresh command"""
        mock_client = mock_client_class.return_value

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "auth", "refresh"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Token refreshed successfully", output)
                mock_client.refresh_access_token.assert_called_once()

    @patch("xteink.cli.main.XteinkClient")
    def test_auth_status(self, mock_client_class):
        """Test auth status command"""
        mock_client = mock_client_class.return_value
        mock_client.BASE_URL = "http://localhost"
        mock_client.get_health.return_value = HealthResponse(message="OK", status="healthy")
        mock_client.is_authenticated.return_value = True
        mock_client.user_id = "user123"

        from xteink.cli.main import main

        # Try both 'auth status' and 'status' alias
        for cmd in [["xteink", "auth", "status"], ["xteink", "status"]]:
            with patch("sys.argv", cmd):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    main()
                    output = fake_out.getvalue()
                    self.assertIn("HEALTHY", output)
                    self.assertIn("Authentication: VALID", output)
                    self.assertIn("user123", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_files_upload(self, mock_client_class):
        """Test files upload command"""
        mock_client = mock_client_class.return_value
        mock_client.upload_file.return_value = FileUploadResponse(
            download_url="http://u.com/f", filename="f", success=True
        )

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "upload", "local.txt"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Upload successful", output)
                self.assertIn("http://u.com/f", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_devices_bind(self, mock_client_class):
        """Test devices bind command"""
        mock_client = mock_client_class.return_value
        device = Device(
            id="1",
            device_id="new_dev",
            brand="xteink",
            device_type="ESP32",
            version="1.0",
            user_id="u1",
            created_at="now",
            updated_at="now",
        )
        from xteink.models import DeviceBindingAddResponse

        mock_client.bind_device.return_value = DeviceBindingAddResponse(
            data=device, message="Bound", success=True
        )

        from xteink.cli.main import main

        args = ["xteink", "bind", "--device-id", "new_dev", "--type", "ESP32", "--version", "1.0"]
        with patch("sys.argv", args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Bound", output)
                self.assertIn("new_dev", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_devices_unbind(self, mock_client_class):
        """Test devices unbind command"""
        mock_client = mock_client_class.return_value
        mock_client.unbind_device.return_value = MessageResponse(message="Unbound", success=True)

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "unbind", "dev1"]):
            with patch("builtins.input", return_value="y"):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    main()
                    output = fake_out.getvalue()
                    self.assertIn("Unbound", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_tasks_create(self, mock_client_class):
        """Test tasks create-task command"""
        mock_client = mock_client_class.return_value
        task = Task(
            task_id="t1",
            device_id="dev1",
            status=TaskStatus.PENDING,
            file_url="http://f.com",
            save_path="/p.txt",
        )
        mock_client.create_device_task.return_value = TaskCreateResponse(success=True, task=task)

        from xteink.cli.main import main

        args = ["xteink", "create-task", "dev1", "http://f.com", "/p.txt", "100"]
        with patch("sys.argv", args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Task created successfully", output)
                self.assertIn("t1", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_utils_version(self, mock_client_class):
        """Test utils version command"""
        mock_client = mock_client_class.return_value
        from xteink.models import ClientVersionData, ClientVersionResponse

        data = ClientVersionData(
            id="v1",
            platform="android",
            version="1.2.3",
            version_code=123,
            download_url="http://v.com",
            force_update=False,
            is_active=True,
            created_at="now",
            updated_at="now",
        )
        mock_client.get_client_version.return_value = ClientVersionResponse(success=True, data=data)
        mock_client.is_authenticated.return_value = True

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "version"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("1.2.3", output)
                self.assertIn("android", output)

    @patch("xteink.cli.main.XteinkClient")
    def test_utils_firmware_check(self, mock_client_class):
        """Test utils firmware-check command"""
        mock_client = mock_client_class.return_value
        from xteink.models import FirmwareCheckResponse

        mock_client.check_firmware_update.return_value = FirmwareCheckResponse(
            code=0, data={"version": "3.1.6", "download_url": "http://fw.com"}, message="Update"
        )

        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "firmware-check"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main()
                output = fake_out.getvalue()
                self.assertIn("Firmware Update Available", output)
                self.assertIn("3.1.6", output)


if __name__ == "__main__":
    unittest.main()
