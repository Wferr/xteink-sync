"""Test RSS reader mode functionality."""

import pytest

from xteink.formats.rss import html_to_text


def test_html_to_text_simple():
    """Test basic HTML to text conversion."""
    html = "<p>Hello <b>world</b>!</p>"
    text = html_to_text(html, reader_mode=False)
    assert "Hello world!" in text


def test_html_to_text_reader_mode_headings():
    """Test reader mode preserves heading formatting."""
    html = """
    <h1>Main Title</h1>
    <h2>Subtitle</h2>
    <h3>Section</h3>
    <p>Content here.</p>
    """
    text = html_to_text(html, reader_mode=True)

    # Check for formatted headings
    assert "═══ Main Title ═══" in text
    assert "─── Subtitle ───" in text
    assert "• Section" in text
    assert "Content here." in text


def test_html_to_text_reader_mode_lists():
    """Test reader mode preserves list formatting."""
    html = """
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    """
    text = html_to_text(html, reader_mode=True)

    # Check for bullet points
    assert "• First item" in text
    assert "• Second item" in text


def test_html_to_text_reader_mode_blockquote():
    """Test reader mode preserves blockquote indentation."""
    html = "<blockquote>This is a quote</blockquote>"
    text = html_to_text(html, reader_mode=True)

    # Check for indentation marker
    assert "│" in text
    assert "This is a quote" in text


def test_html_to_text_removes_scripts():
    """Test that script tags are removed."""
    html = """
    <p>Visible text</p>
    <script>alert('hidden');</script>
    <p>More visible text</p>
    """
    text = html_to_text(html)

    assert "Visible text" in text
    assert "More visible text" in text
    assert "alert" not in text
    assert "script" not in text


def test_render_rss_to_xtc_requires_feedparser():
    """Test that render_rss_to_xtc requires feedparser."""
    from xteink.formats.rss import render_rss_to_xtc

    # This will fail if feedparser is not installed
    # We're just checking the function exists
    assert callable(render_rss_to_xtc)


@pytest.mark.skip(reason="Requires network access and real RSS feed")
def test_render_rss_to_xtc_integration():
    """Integration test with real RSS feed (skipped by default)."""
    from xteink.formats.rss import render_rss_to_xtc

    xtc_data = render_rss_to_xtc(
        feed_url="https://news.ycombinator.com/rss",
        max_articles=2,
        width=800,
        height=600,
        dither=True,
    )

    # Check XTC magic number
    assert xtc_data[:4] == b"XTC\\x00"
    assert len(xtc_data) > 1000  # Should have substantial content
