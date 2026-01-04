"""Local image conversion command for xteink CLI."""

import io
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps

from xteink.formats import xtg, xth


def convert(args, client=None):
    """Local conversion of images to Xteink formats."""
    file_path = args.file_path
    if not os.path.exists(file_path):
        print(f"\033[91mFile not found: {file_path}\033[0m")
        sys.exit(1)

    try:
        image = Image.open(file_path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize/Crop
        # Xteink screen is usually 1-bit or 2-bit, but we resize to max 800x800 for safety component
        # Some devices are 600x448, etc.
        # We'll use 800x800 as the bounding box like the server.
        MAX_SIZE = (800, 800)
        resize_mode = getattr(args, "resize_mode", "cover")

        if resize_mode == "cover":
            # Center crop
            image = ImageOps.fit(image, MAX_SIZE, centering=(0.5, 0.5))
        else:
            # Contain
            image.thumbnail(MAX_SIZE)

        fmt = args.format.lower()
        # dithering = getattr(args, "dithering", "floyd")
        dither_enabled = args.dithering in ["floyd", "floyd_steinberg"]

        ext = ".jpg"
        data = b""

        if fmt == "xtg":
            bitmap = xtg.bitmap_from_image(image, dither=dither_enabled)
            data = xtg.create_xtg(image.width, image.height, bitmap)
            ext = ".xtg"
        elif fmt == "xth":
            bitmap = xth.bitmap_from_image(image)
            data = xth.create_xth(image.width, image.height, bitmap)
            ext = ".xth"
        elif fmt == "bmp":
            dither_mode = Image.Dither.FLOYDSTEINBERG if dither_enabled else Image.Dither.NONE
            bw_image = image.convert("1", dither=dither_mode)
            buf = io.BytesIO()
            bw_image.save(buf, format="BMP")
            data = buf.getvalue()
            ext = ".bmp"
        elif fmt == "fs":
            # Alias for dithered BMP
            dither_mode = Image.Dither.FLOYDSTEINBERG
            bw_image = image.convert("1", dither=dither_mode)
            buf = io.BytesIO()
            bw_image.save(buf, format="BMP")
            data = buf.getvalue()
            ext = ".bmp"
        else:
            # Default to JPG
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85)
            data = buf.getvalue()
            ext = ".jpg"

        output_path = args.output
        if not output_path:
            p = Path(file_path)
            output_path = str(p.with_suffix(ext))

        with open(output_path, "wb") as f:
            f.write(data)

        msg = f"Successfully converted {file_path} -> {output_path} ({len(data)} bytes)"
        print(f"\033[92m{msg}\033[0m")
        print(f"Format: {fmt.upper()}, Resize: {resize_mode}")

    except Exception as e:
        print(f"\033[91mConversion failed: {str(e)}\033[0m")
        sys.exit(1)
