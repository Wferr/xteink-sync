"""
XTC/XTCH File Parser - Read and validate XTC/XTCH format files.

This module provides functions to parse and inspect XTC/XTCH files.
"""

import struct
from pathlib import Path


def parse_xtc_header(file_path: str) -> dict:
    """
    Parse XTC/XTCH file header and return metadata.

    Args:
        file_path: Path to XTC/XTCH file

    Returns:
        Dictionary with header information
    """
    with open(file_path, "rb") as f:
        # Read header (56 bytes)
        header = f.read(56)

        if len(header) < 56:
            raise ValueError("File too small to be valid XTC/XTCH")

        # Parse header fields (little-endian)
        magic = struct.unpack("<I", header[0:4])[0]
        version = struct.unpack("<H", header[4:6])[0]
        page_count = struct.unpack("<H", header[6:8])[0]
        read_direction = header[8]
        has_metadata = header[9]
        has_thumbnails = header[10]
        has_chapters = header[11]
        current_page = struct.unpack("<I", header[12:16])[0]
        metadata_offset = struct.unpack("<Q", header[16:24])[0]
        index_offset = struct.unpack("<Q", header[24:32])[0]
        data_offset = struct.unpack("<Q", header[32:40])[0]
        thumb_offset = struct.unpack("<Q", header[40:48])[0]
        chapter_offset = struct.unpack("<Q", header[48:56])[0]

        # Determine format
        if magic == 0x00435458:
            format_name = "XTC"
        elif magic == 0x48435458:
            format_name = "XTCH"
        else:
            format_name = f"UNKNOWN (0x{magic:08X})"

        # Parse metadata if present
        metadata = None
        if has_metadata and metadata_offset > 0:
            f.seek(metadata_offset)
            meta_bytes = f.read(256)

            title = meta_bytes[0:128].rstrip(b"\x00").decode("utf-8", errors="replace")
            author = meta_bytes[128:192].rstrip(b"\x00").decode("utf-8", errors="replace")
            publisher = meta_bytes[192:224].rstrip(b"\x00").decode("utf-8", errors="replace")
            language = meta_bytes[224:240].rstrip(b"\x00").decode("utf-8", errors="replace")
            create_time = struct.unpack("<I", meta_bytes[240:244])[0]
            cover_page = struct.unpack("<H", meta_bytes[244:246])[0]
            chapter_count = struct.unpack("<H", meta_bytes[246:248])[0]

            metadata = {
                "title": title,
                "author": author,
                "publisher": publisher,
                "language": language,
                "create_time": create_time,
                "cover_page": cover_page,
                "chapter_count": chapter_count,
            }

        # Parse page index
        pages = []
        if index_offset > 0:
            f.seek(index_offset)
            for i in range(page_count):
                idx_bytes = f.read(16)
                if len(idx_bytes) < 16:
                    break

                offset = struct.unpack("<Q", idx_bytes[0:8])[0]
                size = struct.unpack("<I", idx_bytes[8:12])[0]
                width = struct.unpack("<H", idx_bytes[12:14])[0]
                height = struct.unpack("<H", idx_bytes[14:16])[0]

                pages.append(
                    {
                        "page_num": i + 1,
                        "offset": offset,
                        "size": size,
                        "width": width,
                        "height": height,
                    }
                )

        return {
            "format": format_name,
            "magic": f"0x{magic:08X}",
            "version": f"{version >> 8}.{version & 0xFF}",
            "page_count": page_count,
            "read_direction": (
                ["L→R", "R→L", "Top→Bottom"][read_direction]
                if read_direction < 3
                else f"Unknown({read_direction})"
            ),
            "has_metadata": bool(has_metadata),
            "has_thumbnails": bool(has_thumbnails),
            "has_chapters": bool(has_chapters),
            "current_page": current_page,
            "metadata": metadata,
            "pages": pages,
            "offsets": {
                "metadata": metadata_offset,
                "index": index_offset,
                "data": data_offset,
                "thumbnails": thumb_offset,
                "chapters": chapter_offset,
            },
        }


def print_xtc_info(file_path: str):
    """Print human-readable information about an XTC/XTCH file."""
    info = parse_xtc_header(file_path)

    file_size = Path(file_path).stat().st_size

    print(f"File: {Path(file_path).name}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"\n{'=' * 60}")
    print(f"Format: {info['format']}")
    print(f"Magic Number: {info['magic']}")
    print(f"Version: {info['version']}")
    print(f"Page Count: {info['page_count']}")
    print(f"Reading Direction: {info['read_direction']}")
    print(f"Current Page: {info['current_page']}")

    print(f"\n{'=' * 60}")
    print("Features:")
    print(f"  Metadata: {'Yes' if info['has_metadata'] else 'No'}")
    print(f"  Thumbnails: {'Yes' if info['has_thumbnails'] else 'No'}")
    print(f"  Chapters: {'Yes' if info['has_chapters'] else 'No'}")

    if info["metadata"]:
        print(f"\n{'=' * 60}")
        print("Metadata:")
        print(f"  Title: {info['metadata']['title']}")
        print(f"  Author: {info['metadata']['author']}")
        print(f"  Publisher: {info['metadata']['publisher']}")
        print(f"  Language: {info['metadata']['language']}")
        print(f"  Created: {info['metadata']['create_time']}")
        print(f"  Cover Page: {info['metadata']['cover_page']}")
        print(f"  Chapters: {info['metadata']['chapter_count']}")

    if info["pages"]:
        print(f"\n{'=' * 60}")
        print(f"Pages ({len(info['pages'])} total):")
        for page in info["pages"][:10]:  # Show first 10
            print(
                f"  Page {page['page_num']}: {page['width']}×{page['height']}px, "
                f"{page['size']:,} bytes @ offset {page['offset']:,}"
            )
        if len(info["pages"]) > 10:
            print(f"  ... and {len(info['pages']) - 10} more pages")

    print(f"\n{'=' * 60}")
    print("File Structure:")
    print("  Header: 56 bytes")
    if info["offsets"]["metadata"]:
        print(f"  Metadata: @ {info['offsets']['metadata']:,}")
    if info["offsets"]["chapters"]:
        print(f"  Chapters: @ {info['offsets']['chapters']:,}")
    if info["offsets"]["index"]:
        print(f"  Page Index: @ {info['offsets']['index']:,}")
    if info["offsets"]["data"]:
        print(f"  Page Data: @ {info['offsets']['data']:,}")
    if info["offsets"]["thumbnails"]:
        print(f"  Thumbnails: @ {info['offsets']['thumbnails']:,}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python xtc_parser.py <file.xtc>")
        sys.exit(1)

    print_xtc_info(sys.argv[1])
