"""
Unit tests for RSS feed processing and rendering.
"""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xteink.formats import rss

try:
    from xteink.formats import renderer

    RENDERER_AVAILABLE = True
except ImportError:
    RENDERER_AVAILABLE = False


class TestRSSParsing(unittest.TestCase):
    """Tests for RSS feed parsing."""

    def test_html_to_text(self):
        """Test HTML to plain text conversion."""
        html = "<p>Hello <strong>world</strong>!</p><br/><p>New paragraph.</p>"
        text = rss.html_to_text(html)

        self.assertIn("Hello world!", text)
        self.assertIn("New paragraph.", text)
        self.assertNotIn("<p>", text)
        self.assertNotIn("<strong>", text)

    def test_html_to_text_removes_scripts(self):
        """Test that script tags are removed."""
        html = "<p>Content</p><script>alert('xss')</script><p>More</p>"
        text = rss.html_to_text(html)

        self.assertIn("Content", text)
        self.assertIn("More", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("script", text)

    def test_html_entities(self):
        """Test HTML entity decoding."""
        html = "Hello &amp; goodbye"
        text = rss.html_to_text(html)

        self.assertEqual(text, "Hello & goodbye")


@unittest.skipIf(not RENDERER_AVAILABLE, "Renderer not available")
class TestRenderer(unittest.TestCase):
    """Tests for text-to-image renderer."""

    def test_renderer_initialization(self):
        """Test renderer can be initialized."""
        epaper = renderer.EpaperRenderer(width=480, height=800)
        self.assertEqual(epaper.width, 480)
        self.assertEqual(epaper.height, 800)

    def test_render_simple_article(self):
        """Test rendering a simple article."""
        epaper = renderer.EpaperRenderer(width=480, height=800)

        title = "Test Article"
        content = "This is a test article with some content."

        pages = epaper.render_article(title, content)

        # Should produce at least one page
        self.assertGreater(len(pages), 0)

        # Check page dimensions
        self.assertEqual(pages[0].width, 480)
        self.assertEqual(pages[0].height, 800)

    def test_render_long_article_pagination(self):
        """Test that long articles are paginated."""
        epaper = renderer.EpaperRenderer(width=480, height=800)

        title = "Long Article"
        # Create very long content
        content = " ".join(["This is a very long article."] * 200)

        pages = epaper.render_article(title, content)

        # Should produce multiple pages
        self.assertGreater(len(pages), 1)


if __name__ == "__main__":
    unittest.main()
