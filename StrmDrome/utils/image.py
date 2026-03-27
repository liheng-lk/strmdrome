"""
Image utilities: dynamic cover resizing via Pillow.
Returns JPEG bytes at requested size, cached on disk.
"""
import os
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# Simple in-memory cache {(path, size): jpeg_bytes}
_cache: dict = {}


def resize_cover(src_path: str, size: int = 0) -> bytes | None:
    """
    Load a cover image, resize to `size`×`size` (maintaining ratio), return JPEG bytes.
    If size==0 return original JPEG.
    """
    if not src_path or not os.path.exists(src_path):
        return None

    cache_key = (src_path, size)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        with Image.open(src_path) as img:
            # Convert to RGB (handles PNGs with alpha channel)
            img = img.convert("RGB")
            if size and size > 0:
                img.thumbnail((size, size), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88, optimize=True)
            data = buf.getvalue()
            _cache[cache_key] = data
            return data
    except Exception as e:
        logger.error(f"Failed to resize cover {src_path}: {e}")
        return None
