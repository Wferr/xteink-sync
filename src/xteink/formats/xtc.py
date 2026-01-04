"""
XTC Format Writer - Comic/Document container for multiple XTG/XTH pages.

File Structure:
- Header: 56 bytes
- Metadata: 256 bytes (optional)
- Chapter Data: N × 96 bytes (optional)
- Page Index Table: pageCount × 16 bytes
- Data Area: All XTG/XTH page images
- Thumbnail Area: Optional thumbnails

Reading Direction:
- 0: Left to Right (normal)
- 1: Right to Left (Japanese manga)
- 2: Top to Bottom (vertical)
"""

import struct
import time
from typing import Optional


class XtcMetadata:
    """Metadata for XTC container (256 bytes)."""

    def __init__(
        self,
        title: str = "",
        author: str = "",
        publisher: str = "",
        language: str = "en-US",
        cover_page: int = 0xFFFF,
        chapter_count: int = 0,
    ):
        self.title = title[:127]  # Max 128 bytes (null-terminated)
        self.author = author[:63]  # Max 64 bytes
        self.publisher = publisher[:31]  # Max 32 bytes
        self.language = language[:15]  # Max 16 bytes
        self.create_time = int(time.time())
        self.cover_page = cover_page
        self.chapter_count = chapter_count

    def to_bytes(self) -> bytes:
        """Serialize metadata to 256 bytes."""
        data = bytearray(256)

        # Title (128 bytes, UTF-8, null-terminated)
        title_bytes = self.title.encode("utf-8")[:127]
        data[0 : len(title_bytes)] = title_bytes

        # Author (64 bytes)
        author_bytes = self.author.encode("utf-8")[:63]
        data[128 : 128 + len(author_bytes)] = author_bytes

        # Publisher (32 bytes)
        pub_bytes = self.publisher.encode("utf-8")[:31]
        data[192 : 192 + len(pub_bytes)] = pub_bytes

        # Language (16 bytes)
        lang_bytes = self.language.encode("utf-8")[:15]
        data[224 : 224 + len(lang_bytes)] = lang_bytes

        # Create time (uint32_t at offset 240)
        struct.pack_into("<I", data, 240, self.create_time)

        # Cover page (uint16_t at offset 244)
        struct.pack_into("<H", data, 244, self.cover_page)

        # Chapter count (uint16_t at offset 246)
        struct.pack_into("<H", data, 246, self.chapter_count)

        # Reserved (8 bytes at offset 248) - already zeros

        return bytes(data)


class XtcChapter:
    """Chapter information (96 bytes per chapter)."""

    def __init__(self, name: str, start_page: int, end_page: int):
        self.name = name[:79]  # Max 80 bytes (null-terminated)
        self.start_page = start_page
        self.end_page = end_page

    def to_bytes(self) -> bytes:
        """Serialize chapter to 96 bytes."""
        data = bytearray(96)

        # Chapter name (80 bytes, UTF-8, null-terminated)
        name_bytes = self.name.encode("utf-8")[:79]
        data[0 : len(name_bytes)] = name_bytes

        # Start page (uint16_t at offset 80)
        struct.pack_into("<H", data, 80, self.start_page)

        # End page (uint16_t at offset 82)
        struct.pack_into("<H", data, 82, self.end_page)

        # Reserved fields (12 bytes at offset 84) - already zeros

        return bytes(data)


class XtcPageIndex:
    """Page index entry (16 bytes per page)."""

    def __init__(self, offset: int, size: int, width: int, height: int):
        self.offset = offset  # Absolute offset from file start
        self.size = size  # Size including 22-byte header
        self.width = width
        self.height = height

    def to_bytes(self) -> bytes:
        """Serialize page index to 16 bytes."""
        data = bytearray(16)
        struct.pack_into("<Q", data, 0, self.offset)  # uint64_t
        struct.pack_into("<I", data, 8, self.size)  # uint32_t
        struct.pack_into("<H", data, 12, self.width)  # uint16_t
        struct.pack_into("<H", data, 14, self.height)  # uint16_t
        return bytes(data)


def create_xtc(
    pages: list[bytes],
    page_dimensions: list[tuple[int, int]],
    metadata: Optional[XtcMetadata] = None,
    chapters: Optional[list[XtcChapter]] = None,
    reading_direction: int = 0,
    use_xtch: bool = False,
) -> bytes:
    """
    Create an XTC or XTCH format file from multiple XTG/XTH pages.

    Args:
        pages: List of complete XTG/XTH files (including headers)
        page_dimensions: List of (width, height) tuples for each page
        metadata: Optional metadata (256 bytes)
        chapters: Optional list of chapters
        reading_direction: 0=L→R, 1=R→L, 2=Top→Bottom
        use_xtch: If True, use XTCH magic number instead of XTC

    Returns:
        Complete XTC/XTCH file as bytes

    Raises:
        ValueError: If page count or dimensions are invalid
    """
    page_count = len(pages)
    if not (1 <= page_count <= 65535):
        raise ValueError(f"Page count must be 1-65535, got {page_count}")

    if len(page_dimensions) != page_count:
        raise ValueError("page_dimensions must match number of pages")

    has_metadata = metadata is not None
    has_chapters = chapters is not None and len(chapters) > 0
    has_thumbnails = False  # Not implemented yet

    # Calculate offsets
    header_size = 56
    metadata_offset = header_size if has_metadata else 0
    metadata_size = 256 if has_metadata else 0

    chapter_offset = metadata_offset + metadata_size if has_chapters else 0
    chapter_size = len(chapters) * 96 if has_chapters else 0

    index_offset = header_size + metadata_size + chapter_size
    index_size = page_count * 16

    data_offset = index_offset + index_size

    # Build page index
    page_indices = []
    current_offset = data_offset

    for page_data, (width, height) in zip(pages, page_dimensions):
        page_size = len(page_data)
        page_indices.append(XtcPageIndex(current_offset, page_size, width, height))
        current_offset += page_size

    thumb_offset = 0  # No thumbnails

    # Build header (56 bytes, little-endian)
    header = bytearray()

    # Magic number
    if use_xtch:
        header.extend(struct.pack("<I", 0x48435458))  # "XTCH"
    else:
        header.extend(struct.pack("<I", 0x00435458))  # "XTC\0"

    # Version (0x0100 = v1.0)
    header.extend(struct.pack("<H", 0x0100))

    # Page count
    header.extend(struct.pack("<H", page_count))

    # Reading direction
    header.append(reading_direction)

    # Flags
    header.append(1 if has_metadata else 0)
    header.append(1 if has_thumbnails else 0)
    header.append(1 if has_chapters else 0)

    # Current page (1-based, 0 = not set)
    header.extend(struct.pack("<I", 0))

    # Offsets (uint64_t each)
    header.extend(struct.pack("<Q", metadata_offset))
    header.extend(struct.pack("<Q", index_offset))
    header.extend(struct.pack("<Q", data_offset))
    header.extend(struct.pack("<Q", thumb_offset))
    header.extend(struct.pack("<Q", chapter_offset))

    # Assemble file
    result = bytearray(header)

    # Add metadata if present
    if has_metadata:
        result.extend(metadata.to_bytes())

    # Add chapters if present
    if has_chapters:
        for chapter in chapters:
            result.extend(chapter.to_bytes())

    # Add page index
    for page_idx in page_indices:
        result.extend(page_idx.to_bytes())

    # Add page data
    for page_data in pages:
        result.extend(page_data)

    return bytes(result)


def create_xtch(
    pages: list[bytes],
    page_dimensions: list[tuple[int, int]],
    metadata: Optional[XtcMetadata] = None,
    chapters: Optional[list[XtcChapter]] = None,
    reading_direction: int = 0,
) -> bytes:
    """
    Create an XTCH format file from multiple XTG/XTH pages.

    This is a convenience wrapper around create_xtc() that uses the XTCH magic number.
    XTCH is functionally identical to XTC, just with a different file identifier.

    Args:
        pages: List of complete XTG/XTH files (including headers)
        page_dimensions: List of (width, height) tuples for each page
        metadata: Optional metadata (256 bytes)
        chapters: Optional list of chapters
        reading_direction: 0=L→R, 1=R→L, 2=Top→Bottom

    Returns:
        Complete XTCH file as bytes

    Raises:
        ValueError: If page count or dimensions are invalid
    """
    return create_xtc(
        pages,
        page_dimensions,
        metadata=metadata,
        chapters=chapters,
        reading_direction=reading_direction,
        use_xtch=True,
    )
