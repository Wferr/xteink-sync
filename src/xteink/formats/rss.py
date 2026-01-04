"""
RSS Feed Processing - Fetch and parse RSS feeds for e-paper display.

This module handles:
- Fetching RSS feeds via HTTP
- Parsing feed entries (title, date, content)
- Converting HTML to plain text
- Extracting article metadata
"""

import html
import re
from datetime import datetime
from typing import Optional
from urllib.request import Request, urlopen

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from readability import Document
except ImportError:
    Document = None


class RssArticle:
    """Represents a single RSS article."""

    def __init__(
        self,
        title: str,
        content: str,
        author: str = "",
        published: Optional[datetime] = None,
        link: str = "",
        id: str = "",
    ):
        self.title = title
        self.content = content
        self.author = author
        self.published = published or datetime.now()
        self.link = link
        self.id = id


def fetch_rss_feed(feed_url: str, max_articles: int = 10) -> list[RssArticle]:
    """
    Fetch and parse an RSS feed.

    Args:
        feed_url: URL of the RSS feed
        max_articles: Maximum number of articles to return

    Returns:
        List of RssArticle objects

    Raises:
        ImportError: If feedparser is not installed
        Exception: If feed cannot be fetched or parsed
    """
    if feedparser is None:
        raise ImportError(
            "feedparser is required for RSS functionality. Install with: pip install feedparser"
        )

    # Fetch feed
    try:
        req = Request(feed_url, headers={"User-Agent": "xteink-sync/1.0"})
        with urlopen(req, timeout=10) as response:
            feed_data = response.read()
    except Exception as e:
        raise Exception(f"Failed to fetch RSS feed: {e}") from e

    # Parse feed
    feed = feedparser.parse(feed_data)

    if feed.bozo and not feed.entries:
        raise Exception(f"Failed to parse RSS feed: {feed.get('bozo_exception', 'Unknown error')}")

    # Extract articles
    articles = []
    for entry in feed.entries[:max_articles]:
        # Get title
        title = entry.get("title", "Untitled")

        # Get content (try multiple fields)
        content = ""
        if "content" in entry and entry.content:
            content = entry.content[0].get("value", "")
        elif "summary" in entry:
            content = entry.get("summary", "")
        elif "description" in entry:
            content = entry.get("description", "")

        # Convert HTML to plain text
        content = html_to_text(content)

        # Get author
        author = entry.get("author", "")

        # Get published date
        published = None
        if "published_parsed" in entry and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        # Get link
        link = entry.get("link", "")

        # Get ID (guid or id or link)
        article_id = entry.get("id", entry.get("guid", link))

        articles.append(RssArticle(title, content, author, published, link, article_id))

    return articles


def html_to_text(html_content: str, reader_mode: bool = False) -> str:
    """
    Convert HTML to plain text.

    Args:
        html_content: HTML string
        reader_mode: If True, preserve formatting like headings, lists, blockquotes

    Returns:
        Plain text string
    """
    # Unescape HTML entities
    text = html.unescape(html_content)

    # Remove script, style, nav, header, footer, aside, noscript, iframe
    for tag in ["script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"]:
        text = re.sub(f"<{tag}[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)

    if reader_mode:
        # Preserve structure with formatting
        # Convert headings to formatted text
        text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n\n═══ \1 ═══\n\n", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\n─── \1 ───\n\n", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n• \1\n\n", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<h[456][^>]*>(.*?)</h[456]>", r"\n\n\1\n\n", text, flags=re.DOTALL | re.I)

        # Handle lists
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"  • \1\n", text, flags=re.DOTALL | re.I)
        text = re.sub(r"</?[uo]l[^>]*>", "\n", text, flags=re.I)

        # Blockquotes - add indentation
        def indent_blockquote(match):
            content = match.group(1).strip()
            lines = content.split("\n")
            return "\n" + "\n".join("  │ " + line for line in lines) + "\n"

        text = re.sub(
            r"<blockquote[^>]*>(.*?)</blockquote>",
            indent_blockquote,
            text,
            flags=re.DOTALL | re.I,
        )

        # Paragraphs
        text = re.sub(r"</p>", "\n\n", text, flags=re.I)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    else:
        # Simple conversion
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)

    # Remove all other HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Multiple blank lines to double
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
    text = text.strip()
    return text


def fetch_url_text(url: str, use_readability: bool = True) -> tuple[str, str]:
    """
    Fetch URL and convert content to plain text.

    Args:
        url: URL to fetch
        use_readability: If True and readability-lxml is available, use it for extraction

    Returns:
        Tuple of (title, plain text content)
    """
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; xteink-sync/1.0)"})
    with urlopen(req, timeout=15) as response:
        html_content = response.read()

    # Try readability-lxml first if available
    if use_readability and Document is not None:
        try:
            doc = Document(html_content)
            title = doc.title()
            content_html = doc.summary()
            return title, html_to_text(content_html, reader_mode=True)
        except Exception:
            # Fall back to regex method
            pass

    # Fallback to regex-based extraction
    content = html_content.decode("utf-8", errors="ignore")

    # Extract Title
    title = "Untitled"
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.DOTALL | re.IGNORECASE)
    if title_match:
        title = html.unescape(title_match.group(1).strip())

    # Try to find <article> tag
    article_match = re.search(r"<article[^>]*>(.*?)</article>", content, re.DOTALL | re.IGNORECASE)
    if article_match:
        content = article_match.group(1)
    else:
        # Fallback to body
        body_match = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE)
        if body_match:
            content = body_match.group(1)

    return title, html_to_text(content, reader_mode=True)


def render_rss_to_xtc(
    feed_url: str,
    max_articles: int = 10,
    width: int = 800,
    height: int = 600,
    dither: bool = True,
) -> bytes:
    """
    Render RSS feed to XTC format with chapters.

    Args:
        feed_url: URL of the RSS feed
        max_articles: Maximum number of articles to include
        width: Page width in pixels
        height: Page height in pixels
        dither: Whether to apply dithering

    Returns:
        Complete XTC file as bytes

    Raises:
        ImportError: If required dependencies are missing
    """
    from xteink.formats.renderer import EpaperRenderer
    from xteink.formats.xtc import XtcChapter, XtcMetadata, create_xtc
    from xteink.formats.xtg import image_to_xtg

    # Fetch articles
    articles = fetch_rss_feed(feed_url, max_articles)

    if not articles:
        raise ValueError("No articles found in feed")

    # Initialize renderer
    renderer = EpaperRenderer(width=width, height=height)

    # Render each article to pages
    all_pages = []
    page_dimensions = []
    chapters = []
    current_page = 0

    for article in articles:
        # Render article to PIL images
        article_images = renderer.render_article(
            title=article.title,
            content=article.content,
            author=article.author,
            published=article.published,
            grayscale=not dither,  # Use grayscale if no dither
        )

        # Convert each image to XTG
        article_pages = []
        for img in article_images:
            xtg_data = image_to_xtg(img, dither=dither)
            article_pages.append(xtg_data)

        # Create chapter
        start_page = current_page
        end_page = current_page + len(article_pages) - 1
        chapters.append(XtcChapter(article.title[:79], start_page, end_page))

        # Add pages
        all_pages.extend(article_pages)
        page_dimensions.extend([(width, height)] * len(article_pages))
        current_page = end_page + 1

    # Extract feed title from URL or use default
    feed_title = feed_url.split("//")[-1].split("/")[0][:127]

    # Create metadata
    metadata = XtcMetadata(
        title=f"RSS: {feed_title}",
        author="RSS Feed",
        chapter_count=len(chapters),
    )

    # Create XTC
    return create_xtc(
        pages=all_pages,
        page_dimensions=page_dimensions,
        metadata=metadata,
        chapters=chapters,
        reading_direction=0,
    )


def render_url_to_xtc(
    url: str,
    width: int = 800,
    height: int = 600,
    dither: bool = True,
) -> bytes:
    """
    Render a single URL to XTC format (single chapter).

    Args:
        url: URL of the article
        width: Page width
        height: Page height
        dither: Whether to apply dithering

    Returns:
        Complete XTC file as bytes
    """
    from xteink.formats.renderer import EpaperRenderer
    from xteink.formats.xtc import XtcChapter, XtcMetadata, create_xtc
    from xteink.formats.xtg import image_to_xtg

    # Fetch content
    title, content = fetch_url_text(url)

    # Initialize renderer
    renderer = EpaperRenderer(width=width, height=height)

    # Render article to PIL images
    article_images = renderer.render_article(
        title=title,
        content=content,
        author=url,  # Use URL as author for single articles
        published=datetime.now(),
        grayscale=not dither,
    )

    if not article_images:
        raise ValueError("Failed to render article images")

    # Convert each image to XTG
    pages = []
    for img in article_images:
        xtg_data = image_to_xtg(img, dither=dither)
        pages.append(xtg_data)

    # Create chapter (single chapter for the whole article)
    chapters = [XtcChapter(title[:79], 0, len(pages) - 1)]
    page_dimensions = [(width, height)] * len(pages)

    # Create metadata
    metadata = XtcMetadata(
        title=title[:127],
        author=url[:63],
        chapter_count=1,
    )

    # Create XTC
    return create_xtc(
        pages=pages,
        page_dimensions=page_dimensions,
        metadata=metadata,
        chapters=chapters,
        reading_direction=0,
    )
