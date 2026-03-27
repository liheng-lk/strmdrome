"""
services/stream.py
Handles reading a .strm file and producing a 302 Redirect URL.
Supports: plain URL, M3U8 container (first .m3u8 → fetch and extract URL).
"""
import os
import re
import logging
import httpx

logger = logging.getLogger(__name__)


async def resolve_strm_url(strm_path: str) -> str | None:
    """
    Read a .strm file and return the playback URL.
    Handles:
      - Plain HTTP/HTTPS URL (most common)
      - URL pointing to an M3U/M3U8 playlist (extract first media URL)
    """
    if not strm_path or not os.path.exists(strm_path):
        logger.warning(f"STRM file not found: {strm_path}")
        return None

    try:
        with open(strm_path, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#"):
                    # If the url itself is a playlist, follow it
                    if url.lower().endswith((".m3u8", ".m3u")):
                        url = await _follow_playlist(url) or url
                    return url
    except Exception as e:
        logger.error(f"Failed to read STRM {strm_path}: {e}")

    return None


async def _follow_playlist(playlist_url: str) -> str | None:
    """Fetch an M3U8 and return the first non-comment line (media URL)."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(playlist_url)
            for line in r.text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except Exception as e:
        logger.debug(f"Failed to follow playlist {playlist_url}: {e}")
    return None
