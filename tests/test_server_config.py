import shutil
import tempfile
import unittest
from pathlib import Path

from server.core import config


class TestServerConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_base_dir = config.BASE_DIR
        config.BASE_DIR = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        config.BASE_DIR = self.orig_base_dir

    def test_parse_size(self):
        self.assertEqual(config.parse_size("100"), 100)
        self.assertEqual(config.parse_size("1KB"), 1024)
        self.assertEqual(config.parse_size("1MB"), 1024**2)
        self.assertEqual(config.parse_size("1GB"), 1024**3)
        self.assertEqual(config.parse_size("1.5MB"), int(1.5 * 1024**2))

        # Test strict invalid
        with self.assertRaises(ValueError):
            config.parse_size("invalid")

    def test_load_server_config(self):
        # Create a config.toml
        cfg_path = self.tmp_dir / "config.toml"
        content = (
            '[server]\nhost = "1.2.3.4"\nport = 9000\n'
            '[storage]\nmax_file_size = "200MB"\n'
            "[auth]\nenabled = false\n"
        )
        with open(cfg_path, "w") as f:
            f.write(content)

        c = config.load_server_config()
        self.assertEqual(c["server"]["host"], "1.2.3.4")
        self.assertEqual(c["server"]["port"], 9000)
        self.assertEqual(c["storage"]["max_file_size"], "200MB")

    def test_load_config_missing(self):
        # tmp_dir is empty, so config.toml is missing
        with self.assertRaises(FileNotFoundError):
            config.load_server_config()

    def test_load_config_invalid(self):
        cfg_path = self.tmp_dir / "config.toml"
        with open(cfg_path, "w") as f:
            f.write("invalid = [toml\n")
        with self.assertRaises(ValueError):
            config.load_server_config()


if __name__ == "__main__":
    unittest.main()
