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

    def test_tasks_subcommand_help(self):
        """Test that tasks subcommand has help text"""
        from xteink.cli.main import main

        with patch("sys.argv", ["xteink", "tasks", "--help"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 0)
                output = fake_out.getvalue()
                # Just verify the command structure is present
                self.assertIn("device_id", output)
                self.assertIn("--status", output)
                self.assertIn("--limit", output)


if __name__ == "__main__":
    unittest.main()
