"""
XTG/XTH/XTC/XTCH format conversion library for Xteink e-paper devices.

This package provides writers for the proprietary image formats used by
Xteink ESP32 e-paper displays.

Formats:
- XTG: Monochrome 1-bit images
- XTH: 4-level grayscale images
- XTC: Multi-page comic/document container
- XTCH: XTC variant with different magic number
"""

# Import main modules
from . import renderer, rss, xtc, xtg, xth

# Export key functions and classes for convenience
from .xtc import XtcChapter, XtcMetadata, XtcPageIndex, create_xtc, create_xtch
from .xtg import bitmap_from_image as xtg_bitmap_from_image
from .xtg import create_xtg
from .xth import bitmap_from_image as xth_bitmap_from_image
from .xth import create_xth

__all__ = [
    # Modules
    "xtg",
    "xth",
    "xtc",
    "rss",
    "renderer",
    # XTG functions
    "create_xtg",
    "xtg_bitmap_from_image",
    # XTH functions
    "create_xth",
    "xth_bitmap_from_image",
    # XTC/XTCH functions and classes
    "create_xtc",
    "create_xtch",
    "XtcMetadata",
    "XtcChapter",
    "XtcPageIndex",
]
