"""
Text-to-Image Renderer for E-Paper Displays.

This module renders text content to images suitable for e-paper displays,
with support for:
- Title, date, and body text layout
- Line wrapping and pagination
- Monochrome (1-bit) and 4-level grayscale rendering
"""

from datetime import datetime
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None


class EpaperRenderer:
    """Renders text content to e-paper display images."""

    def __init__(
        self,
        width: int = 480,
        height: int = 800,
        margin: int = 40,
        title_size: int = 32,
        body_size: int = 20,
        line_spacing: int = 8,
    ):
        """
        Initialize renderer with display dimensions and styling.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            margin: Margin around content in pixels
            title_size: Font size for titles
            body_size: Font size for body text
            line_spacing: Extra spacing between lines
        """
        if Image is None:
            raise ImportError("Pillow is required for rendering. Install with: pip install Pillow")

        self.width = width
        self.height = height
        self.margin = margin
        self.title_size = title_size
        self.body_size = body_size
        self.line_spacing = line_spacing

        # Try to load fonts (fallback to default if not available)
        try:
            self.title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_size
            )
            self.body_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", body_size
            )
            self.meta_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
            )
        except Exception:
            # Fallback to default font
            self.title_font = ImageFont.load_default()
            self.body_font = ImageFont.load_default()
            self.meta_font = ImageFont.load_default()

    def render_article(
        self,
        title: str,
        content: str,
        author: str = "",
        published: Optional[datetime] = None,
        grayscale: bool = False,
    ) -> list[Image.Image]:
        """
        Render an article to one or more pages.

        Args:
            title: Article title
            content: Article body text
            author: Article author
            published: Publication date
            grayscale: If True, render in 4-level grayscale; if False, monochrome

        Returns:
            List of PIL Image objects (one per page)
        """
        pages = []
        content_area_width = self.width - 2 * self.margin
        content_area_height = self.height - 2 * self.margin

        # Create first page with title and metadata
        current_y = self.margin

        # Render title
        title_lines = self._wrap_text(title, self.title_font, content_area_width)
        title_height = len(title_lines) * (self.title_size + self.line_spacing)

        # Render metadata
        meta_text = ""
        if author:
            meta_text = f"By {author}"
        if published:
            date_str = published.strftime("%Y-%m-%d")
            meta_text += f" • {date_str}" if meta_text else date_str

        meta_height = 20 if meta_text else 0
        separator_height = 20

        # Calculate space for body on first page
        first_page_body_start = current_y + title_height + meta_height + separator_height
        first_page_body_height = self.height - self.margin - first_page_body_start

        # Wrap body text
        body_lines = self._wrap_text(content, self.body_font, content_area_width)

        # Calculate lines per page
        line_height = self.body_size + self.line_spacing
        first_page_lines = max(1, int(first_page_body_height / line_height))
        subsequent_page_lines = max(1, int(content_area_height / line_height))

        # Render first page
        img = self._create_blank_page(grayscale)
        draw = ImageDraw.Draw(img)

        # Draw title
        y = self.margin
        for line in title_lines:
            draw.text((self.margin, y), line, fill=0, font=self.title_font)
            y += self.title_size + self.line_spacing

        # Draw metadata
        if meta_text:
            fill_color = 128 if grayscale else 0
            draw.text((self.margin, y), meta_text, fill=fill_color, font=self.meta_font)
            y += meta_height

        # Draw separator
        y += 10
        draw.line([(self.margin, y), (self.width - self.margin, y)], fill=0, width=2)
        y += 10

        # Draw body text on first page
        for line in body_lines[:first_page_lines]:
            draw.text((self.margin, y), line, fill=0, font=self.body_font)
            y += line_height

        pages.append(img)

        # Render subsequent pages
        remaining_lines = body_lines[first_page_lines:]
        while remaining_lines:
            img = self._create_blank_page(grayscale)
            draw = ImageDraw.Draw(img)

            y = self.margin
            page_lines = remaining_lines[:subsequent_page_lines]
            for line in page_lines:
                draw.text((self.margin, y), line, fill=0, font=self.body_font)
                y += line_height

            pages.append(img)
            remaining_lines = remaining_lines[subsequent_page_lines:]

        return pages

    def _create_blank_page(self, grayscale: bool) -> Image.Image:
        """Create a blank page image."""
        if grayscale:
            return Image.new("L", (self.width, self.height), color=255)  # White
        else:
            return Image.new("1", (self.width, self.height), color=1)  # White

    def _wrap_text(self, text: str, font, max_width: int) -> list[str]:
        """
        Wrap text to fit within max_width.

        Args:
            text: Text to wrap
            font: PIL font object
            max_width: Maximum width in pixels

        Returns:
            List of wrapped lines
        """
        lines = []
        paragraphs = text.split("\n")

        for paragraph in paragraphs:
            if not paragraph.strip():
                lines.append("")
                continue

            words = paragraph.split()
            current_line = []

            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = font.getbbox(test_line)
                width = bbox[2] - bbox[0]

                if width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        # Single word is too long, add it anyway
                        lines.append(word)

            if current_line:
                lines.append(" ".join(current_line))

        return lines
