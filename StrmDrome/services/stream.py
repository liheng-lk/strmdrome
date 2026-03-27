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


async def resolve_strm_url(strm_path: str, folder_id: int = None) -> str | None:
    """
    Return the 302 playback URL.
    1. If AList backend: request the dynamic signed URL directly from AList.
    2. If Local backend: Read the .strm file and return the plain HTTP/HTTPS URL or M3U8 payload.
    """
    if folder_id:
        from db.database import get_connection
        conn = get_connection()
        folder = conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
        conn.close()
        
        if folder and folder.get("alist_url"):
            from services.alist import AListClient
            client = AListClient(folder_id, folder["alist_url"], folder.get("alist_username"), folder.get("alist_password"), folder.get("alist_token"))
            url = client.get_stream_url(strm_path)
            if url: return url
            
    if not strm_path or not os.path.exists(strm_path):
        logger.warning(f"Media file not found locally: {strm_path}")
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
