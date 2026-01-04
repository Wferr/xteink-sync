"""
XTG Format Writer - Monochrome 1-bit per pixel bitmap for e-paper displays.

File Structure:
- Header: 22 bytes
- Image Data: ((width + 7) / 8) * height bytes

Pixel Storage:
- Rows stored top to bottom
- 8 pixels per byte (MSB first)
- Bit 7 (MSB) = leftmost pixel, Bit 0 (LSB) = rightmost pixel
- 0 = Black, 1 = White
"""

import struct
from typing import Optional


def create_xtg(
    width: int, height: int, bitmap_data: bytes, md5_hash: Optional[bytes] = None
) -> bytes:
    """
    Create an XTG format file from bitmap data.

    Args:
        width: Image width in pixels (1-65535)
        height: Image height in pixels (1-65535)
        bitmap_data: Raw bitmap data, 1 bit per pixel, packed 8 pixels per byte
        md5_hash: Optional MD5 checksum (first 8 bytes), defaults to zeros

    Returns:
        Complete XTG file as bytes

    Raises:
        ValueError: If dimensions or data size are invalid
    """
    if not (1 <= width <= 65535):
        raise ValueError(f"Width must be 1-65535, got {width}")
    if not (1 <= height <= 65535):
        raise ValueError(f"Height must be 1-65535, got {height}")

    # Calculate expected data size
    bytes_per_row = (width + 7) // 8
    expected_size = bytes_per_row * height

    if len(bitmap_data) != expected_size:
        raise ValueError(
            f"Bitmap data size mismatch: expected {expected_size} bytes, got {len(bitmap_data)}"
        )

    # Build header (22 bytes, little-endian)
    header = bytearray()

    # Magic number: 0x00475458 ("XTG\0")
    header.extend(struct.pack("<I", 0x00475458))

    # Width and height (uint16_t)
    header.extend(struct.pack("<H", width))
    header.extend(struct.pack("<H", height))

    # Color mode (0 = monochrome)
    header.append(0)

    # Compression (0 = uncompressed)
    header.append(0)

    # Data size (uint32_t)
    header.extend(struct.pack("<I", expected_size))

    # MD5 checksum (first 8 bytes, or zeros)
    if md5_hash:
        header.extend(md5_hash[:8])
    else:
        header.extend(b"\x00" * 8)

    # Combine header and data
    return bytes(header) + bitmap_data


def bitmap_from_image(image, dither: bool = True) -> bytes:
    """
    Convert a PIL Image to XTG bitmap format.

    Args:
        image: PIL Image object (will be converted to 1-bit mode)
        dither: Whether to apply dithering (Floyd-Steinberg) or simple thresholding

    Returns:
        Packed bitmap data (8 pixels per byte, MSB first)
    """
    # Convert to 1-bit mode (black and white)
    # dither=1 (default) is Floyd-Steinberg, dither=0 is None (nearest neighbor)
    dither_mode = 1 if dither else 0
    if image.mode != "1":
        bw_image = image.convert("1", dither=dither_mode)
    else:
        bw_image = image

    width, height = bw_image.size

    bitmap = bytearray()
    pixels = bw_image.load()

    for y in range(height):
        byte_val = 0
        bit_pos = 7
        for x in range(width):
            # Get pixel value (0 or 255 in mode '1')
            pixel = pixels[x, y]
            # Convert to bit (0 = black, 1 = white)
            # In PIL mode '1', 0 = black, 255 = white
            bit = 1 if pixel != 0 else 0
            byte_val |= bit << bit_pos
            bit_pos -= 1

            # Write byte when full or at end of row
            if bit_pos < 0 or x == width - 1:
                bitmap.append(byte_val)
                byte_val = 0
                bit_pos = 7

    return bytes(bitmap)


def image_to_xtg(image, dither: bool = True) -> bytes:
    """
    Convenience function to convert PIL Image to XTG bytes.
    """
    bitmap = bitmap_from_image(image, dither=dither)
    return create_xtg(image.width, image.height, bitmap)
