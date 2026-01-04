"""
Unit tests for XTG/XTH/XTC format writers.
"""

import struct
import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xteink.formats import xtc, xtg, xth

try:
    from PIL import Image
except ImportError:
    Image = None


class TestXTGFormat(unittest.TestCase):
    """Tests for XTG format writer."""

    def test_create_xtg_header(self):
        """Test XTG header generation."""
        width, height = 100, 50
        bytes_per_row = (width + 7) // 8
        data_size = bytes_per_row * height
        bitmap_data = b"\x00" * data_size

        xtg_file = xtg.create_xtg(width, height, bitmap_data)

        # Check file size (22 byte header + data)
        self.assertEqual(len(xtg_file), 22 + data_size)

        # Check magic number (little-endian)
        magic = struct.unpack("<I", xtg_file[0:4])[0]
        self.assertEqual(magic, 0x00475458)  # "XTG\0"

        # Check dimensions
        w = struct.unpack("<H", xtg_file[4:6])[0]
        h = struct.unpack("<H", xtg_file[6:8])[0]
        self.assertEqual(w, width)
        self.assertEqual(h, height)

        # Check color mode and compression
        self.assertEqual(xtg_file[8], 0)  # Monochrome
        self.assertEqual(xtg_file[9], 0)  # Uncompressed

        # Check data size
        size = struct.unpack("<I", xtg_file[10:14])[0]
        self.assertEqual(size, data_size)

    def test_xtg_data_size_validation(self):
        """Test that XTG validates data size."""
        with self.assertRaises(ValueError):
            xtg.create_xtg(100, 50, b"\x00" * 10)  # Too small

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_bitmap_from_image(self):
        """Test converting PIL Image to XTG bitmap."""
        img = Image.new("1", (16, 2), color=1)  # 16x2 white image
        bitmap = xtg.bitmap_from_image(img)

        # Should be 2 bytes per row * 2 rows = 4 bytes
        self.assertEqual(len(bitmap), 4)

        # All pixels white (1) should give 0xFF bytes
        self.assertEqual(bitmap, b"\xff\xff\xff\xff")


class TestXTHFormat(unittest.TestCase):
    """Tests for XTH format writer."""

    def test_create_xth_header(self):
        """Test XTH header generation."""
        width, height = 100, 50
        # New column-major alignment: each column is bytes_per_col = ceil(height/8)
        bytes_per_col = (height + 7) // 8
        plane_size = width * bytes_per_col
        data_size = plane_size * 2
        grayscale_data = b"\x00" * data_size

        xth_file = xth.create_xth(width, height, grayscale_data)

        # Check file size (22 byte header + data)
        self.assertEqual(len(xth_file), 22 + data_size)

        # Check magic number (little-endian)
        magic = struct.unpack("<I", xth_file[0:4])[0]
        self.assertEqual(magic, 0x00485458)  # "XTH\0"

        # Check dimensions
        w = struct.unpack("<H", xth_file[4:6])[0]
        h = struct.unpack("<H", xth_file[6:8])[0]
        self.assertEqual(w, width)
        self.assertEqual(h, height)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_bitmap_from_image_grayscale(self):
        """Test converting PIL Image to XTH bitmap."""
        # Create a simple 8x8 grayscale image
        img = Image.new("L", (8, 8), color=255)  # White
        bitmap = xth.bitmap_from_image(img)

        # 8x8 = 64 pixels, 2 bit planes
        # Each plane: width * ceil(height/8) = 8 * 1 = 8 bytes
        # Total: 16 bytes
        self.assertEqual(len(bitmap), 16)


class TestXTCFormat(unittest.TestCase):
    """Tests for XTC container format writer."""

    def test_create_xtc_header(self):
        """Test XTC header generation."""
        # Create a simple XTG page
        page_data = xtg.create_xtg(100, 50, b"\x00" * ((100 + 7) // 8 * 50))
        pages = [page_data]
        dimensions = [(100, 50)]

        xtc_file = xtc.create_xtc(pages, dimensions)

        # Check magic number
        magic = struct.unpack("<I", xtc_file[0:4])[0]
        self.assertEqual(magic, 0x00435458)  # "XTC\0"

        # Check version
        version = struct.unpack("<H", xtc_file[4:6])[0]
        self.assertEqual(version, 0x0100)  # v1.0

        # Check page count
        page_count = struct.unpack("<H", xtc_file[6:8])[0]
        self.assertEqual(page_count, 1)

    def test_create_xtch_variant(self):
        """Test XTCH variant uses correct magic number."""
        page_data = xtg.create_xtg(100, 50, b"\x00" * ((100 + 7) // 8 * 50))
        pages = [page_data]
        dimensions = [(100, 50)]

        xtch_file = xtc.create_xtc(pages, dimensions, use_xtch=True)

        # Check magic number
        magic = struct.unpack("<I", xtch_file[0:4])[0]
        self.assertEqual(magic, 0x48435458)  # "XTCH"

    def test_create_xtch_wrapper(self):
        """Test create_xtch convenience wrapper."""
        page_data = xtg.create_xtg(100, 50, b"\x00" * ((100 + 7) // 8 * 50))
        pages = [page_data]
        dimensions = [(100, 50)]

        # Use the convenience wrapper
        xtch_file = xtc.create_xtch(pages, dimensions)

        # Check magic number
        magic = struct.unpack("<I", xtch_file[0:4])[0]
        self.assertEqual(magic, 0x48435458)  # "XTCH"

    def test_xtc_with_metadata(self):
        """Test XTC with metadata."""
        page_data = xtg.create_xtg(100, 50, b"\x00" * ((100 + 7) // 8 * 50))
        pages = [page_data]
        dimensions = [(100, 50)]

        metadata = xtc.XtcMetadata(
            title="Test Comic", author="Test Author", publisher="Test Publisher"
        )

        xtc_file = xtc.create_xtc(pages, dimensions, metadata=metadata)

        # Check has_metadata flag
        has_metadata = xtc_file[9]
        self.assertEqual(has_metadata, 1)

        # Metadata should be at offset 56 (after header)
        metadata_bytes = xtc_file[56 : 56 + 256]
        title = metadata_bytes[0:128].rstrip(b"\x00").decode("utf-8")
        self.assertEqual(title, "Test Comic")

    def test_xtc_page_index(self):
        """Test XTC page index table."""
        page_data = xtg.create_xtg(100, 50, b"\x00" * ((100 + 7) // 8 * 50))
        pages = [page_data, page_data]  # Two identical pages
        dimensions = [(100, 50), (100, 50)]

        xtc_file = xtc.create_xtc(pages, dimensions)

        # Page index starts at offset 56 (no metadata)
        # Each index entry is 16 bytes
        index_offset = 56

        # First page index
        page1_size = struct.unpack("<I", xtc_file[index_offset + 8 : index_offset + 12])[0]
        page1_width = struct.unpack("<H", xtc_file[index_offset + 12 : index_offset + 14])[0]
        page1_height = struct.unpack("<H", xtc_file[index_offset + 14 : index_offset + 16])[0]

        self.assertEqual(page1_size, len(page_data))
        self.assertEqual(page1_width, 100)
        self.assertEqual(page1_height, 50)


class TestRealImageFormats(unittest.TestCase):
    """Integrated tests using real microscopy sample image."""

    @classmethod
    def setUpClass(cls):
        cls.sample_path = Path(__file__).parent / "fixtures" / "sample.jpg"
        if not cls.sample_path.exists():
            raise unittest.SkipTest("Sample image not found")
        cls.img = Image.open(cls.sample_path)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_xtg_from_real_image(self):
        """Test XTG conversion from real high-detail image."""
        # Convert to 1-bit monochrome
        bw_img = self.img.convert("1")
        bitmap = xtg.bitmap_from_image(bw_img)
        xtg_data = xtg.create_xtg(bw_img.width, bw_img.height, bitmap)
        self.assertTrue(len(xtg_data) > 22)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_xth_from_real_image(self):
        """Test XTH conversion from real high-detail image."""
        # Convert to 4-level grayscale
        gray_img = self.img.convert("L")
        bitmap = xth.bitmap_from_image(gray_img)
        xth_data = xth.create_xth(gray_img.width, gray_img.height, bitmap)
        self.assertTrue(len(xth_data) > 22)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_xtc_from_real_image(self):
        """Test XTC container with real image frames."""
        # Create 2 pages
        img_resized = self.img.resize((600, 800))
        bw_img = img_resized.convert("1")
        bitmap = xtg.bitmap_from_image(bw_img)
        page_data = xtg.create_xtg(bw_img.width, bw_img.height, bitmap)

        xtc_data = xtc.create_xtc([page_data, page_data], [(600, 800), (600, 800)])
        self.assertEqual(struct.unpack("<H", xtc_data[6:8])[0], 2)


if __name__ == "__main__":
    unittest.main()
