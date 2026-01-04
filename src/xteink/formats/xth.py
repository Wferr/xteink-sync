"""
XTH Format Writer - 4-level grayscale (2-bit per pixel) bitmap for e-paper displays.

File Structure:
- Header: 22 bytes
- Image Data: Two bit planes, each ((width * height + 7) / 8) bytes

Pixel Value Mapping (Xteink LUT):
- 0 (00): White
- 1 (01): Dark Grey  (Note: swapped with light grey)
- 2 (10): Light Grey (Note: swapped with dark grey)
- 3 (11): Black

Bit Plane Storage:
- First plane: Bit1 (high bit) for all pixels
- Second plane: Bit2 (low bit) for all pixels
- Vertical scan order (column-major, right to left)
- 8 vertical pixels per byte (MSB = topmost)
"""

import struct
from typing import Optional


def create_xth(
    width: int, height: int, grayscale_data: bytes, md5_hash: Optional[bytes] = None
) -> bytes:
    """
    Create an XTH format file from grayscale data.

    Args:
        width: Image width in pixels (1-65535)
        height: Image height in pixels (1-65535)
        grayscale_data: Raw grayscale data, 2 bits per pixel (values 0-3)
                       Stored as two bit planes in vertical scan order
        md5_hash: Optional MD5 checksum (first 8 bytes), defaults to zeros

    Returns:
        Complete XTH file as bytes

    Raises:
        ValueError: If dimensions or data size are invalid
    """
    if not (1 <= width <= 65535):
        raise ValueError(f"Width must be 1-65535, got {width}")
    if not (1 <= height <= 65535):
        raise ValueError(f"Height must be 1-65535, got {height}")

    # Calculate expected data size (2 bit planes)
    # Calculate expected data size (2 bit planes), assuming column-major byte alignment
    # Matches bitmap_from_image logic
    plane_size = width * ((height + 7) // 8)
    expected_size = plane_size * 2

    if len(grayscale_data) != expected_size:
        raise ValueError(
            f"Grayscale data size mismatch: expected {expected_size} bytes, "
            f"got {len(grayscale_data)}"
        )

    # Build header (22 bytes, little-endian)
    header = bytearray()

    # Magic number: 0x00485458 ("XTH\0")
    header.extend(struct.pack("<I", 0x00485458))

    # Width and height (uint16_t)
    header.extend(struct.pack("<H", width))
    header.extend(struct.pack("<H", height))

    # Color mode (0 = monochrome/grayscale)
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
    return bytes(header) + grayscale_data


def bitmap_from_image(image) -> bytes:
    """
    Convert a PIL Image to XTH bitmap format with vertical scan order.

    Args:
        image: PIL Image object (will be converted to grayscale)

    Returns:
        Packed bitmap data (two bit planes, vertical scan order)
    """
    # Convert to grayscale
    gray_image = image.convert("L")
    width, height = gray_image.size
    pixels = gray_image.load()

    # Convert grayscale to 2-bit values (0-3)
    # Map: 0-63=0(white), 64-127=2(light grey), 128-191=1(dark grey), 192-255=3(black)
    pixel_values = []
    for y in range(height):
        row = []
        for x in range(width):
            gray = pixels[x, y]
            if gray < 64:
                val = 0  # White
            elif gray < 128:
                val = 2  # Light grey
            elif gray < 192:
                val = 1  # Dark grey
            else:
                val = 3  # Black
            row.append(val)
        pixel_values.append(row)

    # Create two bit planes with vertical scan order
    # Calculate buffer size (2 bits per pixel packed)
    # Each plane is 1 bit per pixel
    # Format: Columns scanned right to left. Each column is ceil(height/8) bytes.
    bytes_per_col = (height + 7) // 8
    plane_size = width * bytes_per_col

    bit_plane1 = bytearray(plane_size)
    bit_plane2 = bytearray(plane_size)  # Low bit

    byte_idx = 0

    # Scan columns from right to left
    for x in range(width - 1, -1, -1):
        # Scan vertically in groups of 8
        for y_start in range(0, height, 8):
            byte1 = 0
            byte2 = 0

            # Pack 8 vertical pixels
            for i in range(8):
                y = y_start + i
                if y < height:
                    val = pixel_values[y][x]
                    bit1 = (val >> 1) & 1  # High bit
                    bit2 = val & 1  # Low bit

                    byte1 |= bit1 << (7 - i)
                    byte2 |= bit2 << (7 - i)

            bit_plane1[byte_idx] = byte1
            bit_plane2[byte_idx] = byte2
            byte_idx += 1

    return bytes(bit_plane1) + bytes(bit_plane2)
