import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add src to path
# Add src and root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from server.main import app
from xteink.formats import rss, xtg


class TestRssArticleID(unittest.TestCase):
    """Test RssArticle ID handling."""

    def test_rss_article_init_with_id(self):
        """Test RssArticle initialization with ID."""
        article = rss.RssArticle(title="Test Title", content="Content", id="test-id-123")
        self.assertEqual(article.id, "test-id-123")

    def test_rss_article_init_default_id(self):
        """Test RssArticle initialization without ID."""
        article = rss.RssArticle(title="Test Title", content="Content")
        self.assertEqual(article.id, "")


class TestXtcGeneration(unittest.TestCase):
    """Test XTC generation functions."""

    def test_image_to_xtg(self):
        """Test image_to_xtg helper."""
        from PIL import Image

        # Create a tiny 8x1 image
        img = Image.new("1", (8, 1), color=1)  # All white = 1

        # Convert to XTG
        xtg_data = xtg.image_to_xtg(img, dither=False)

        # XTG header is 22 bytes. Data is 1 byte (8 pixels).
        self.assertEqual(len(xtg_data), 23)

        # Check magic in header ("XTG\0")
        self.assertEqual(xtg_data[:4], b"\x58\x54\x47\x00")

    @patch("xteink.formats.rss.fetch_url_text")
    def test_render_url_to_xtc(self, mock_fetch):
        """Test render_url_to_xtc flow."""
        # Mock fetch result
        mock_fetch.return_value = ("Test Article", "Some content for the article.")

        # Call render_url_to_xtc
        # We need to mock renderer mainly to avoid complex font loading if inconsistent,
        # but EpaperRenderer usually works if fonts are default.
        # Let's try running it real first (integration style) to verify module wiring.

        try:
            xtc_data = rss.render_url_to_xtc("http://example.com", width=100, height=100)

            # Check magic "XTC\0"
            self.assertEqual(xtc_data[:4], b"\x58\x54\x43\x00")

            # Should have at least header(56) + page index(16) + data
            self.assertGreater(len(xtc_data), 72)

        except ImportError:
            self.skipTest("Renderer dependencies missing")


class TestServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("server.routers.rss.rss.fetch_rss_feed")
    def test_rss_parse_success(self, mock_fetch):
        """Test RSS parse endpoint success."""
        # Mock return value
        mock_article = rss.RssArticle("Title", "Content", id="123")
        mock_fetch.return_value = [mock_article]

        resp = self.client.post("/api/v1/rss/parse", json={"rss_url": "http://test.com/feed"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(data["articles"][0]["id"], "123")

    @patch("server.routers.rss.rss.fetch_rss_feed")
    def test_rss_parse_invalid_feed(self, mock_fetch):
        """Test RSS parse with invalid feed error (400)."""
        mock_fetch.side_effect = Exception("not well-formed (invalid token)")

        resp = self.client.post("/api/v1/rss/parse", json={"rss_url": "http://test.com/bad"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not well-formed", resp.json()["error"])

    @patch("server.routers.rss.rss.render_url_to_xtc")
    def test_url_xtc_conversion(self, mock_render):
        """Test URL to XTC endpoint."""
        mock_render.return_value = b"XTC\x00MockData"

        # Need to verify files write to avoid messing up real file system.
        # But since we patch open, it won't write.
        # However, pathlib.Path.mkdir is also called. We should assume FILES_DIR is safe mocked.
        # For this test, let's just let mkdir pass.
        # We'll rely on the fact that existing structure is fine.

        with patch("builtins.open", unittest.mock.mock_open()):
            resp = self.client.post(
                "/api/v1/ai/url_plain", json={"url": "http://ex.com", "format": "xtc"}
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertTrue(resp.json()["download_url"].endswith(".xtc"))
        mock_render.assert_called_once()


if __name__ == "__main__":
    unittest.main()
