"""
services/scanner.py
Library scanner: walks /music, builds DB artist/album/song records,
then fires the async scraper pipeline for each unscraped song.
Stores NOTHING in /music – all metadata goes to /data/catalog.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import config
from services import library as lib
from services.scraper import scrape_song, scrape_artist
from utils.parser import parse_strm_path

logger = logging.getLogger(__name__)

_scan_status = {"scanning": False, "last_scan": None, "count": 0}


def get_scan_status() -> dict:
    return _scan_status


async def scan_library_async():
    if _scan_status["scanning"]:
        logger.info("Scan already in progress, skipping.")
        return
    _scan_status["scanning"] = True
    _scan_status["count"]    = 0
    logger.info(f"Starting library scan: {config.MUSIC_DIR}")

    # Collect all .strm files first
    strm_files: list[str] = []
    for root, dirs, files in os.walk(config.MUSIC_DIR):
        dirs.sort()
        for fn in sorted(files):
            if fn.lower().endswith(".strm"):
                strm_files.append(os.path.join(root, fn))

    logger.info(f"Found {len(strm_files)} .strm files.")

    # Process in semaphore-controlled async batches for the scraper
    sem = asyncio.Semaphore(config.SCRAPE_CONCURRENCY)

    async def process_one(strm_path: str):
        async with sem:
            parsed = parse_strm_path(strm_path, config.MUSIC_DIR)

            artist_name = parsed.artist or "Unknown Artist"
            album_name  = parsed.album  or "Unknown Album"

            aid  = lib.upsert_artist(artist_name)
            alid = lib.upsert_album(aid, artist_name, album_name, parsed.year)
            sid  = lib.upsert_song(
                path       = strm_path,
                album_id   = alid,
                artist_id  = aid,
                title      = parsed.title,
                track_num  = parsed.track_num,
                disc_num   = parsed.disc_num,
            )

            # Run scrape only if never scraped before
            from db.database import get_connection
            row = get_connection().execute(
                "SELECT last_scraped FROM songs WHERE id=?", (sid,)
            ).fetchone()
            if not row or not row["last_scraped"]:
                await scrape_song(strm_path, parsed, aid, alid, sid)

            _scan_status["count"] += 1

    await asyncio.gather(*[process_one(p) for p in strm_files])

    # After all songs, update album stats + scrape artist bios
    artists = lib.list_artists()
    for artist in artists:
        lib.update_artist_album_count(artist["id"])
        for album in lib.list_albums_by_artist(artist["id"]):
            lib.update_album_stats(album["id"])
        if not artist["biography"] and not artist["last_scraped"]:
            await scrape_artist(artist["id"], artist["name"])

    _scan_status["scanning"] = False
    _scan_status["last_scan"] = datetime.now(timezone.utc).isoformat()
    logger.info(f"Scan complete. Processed {_scan_status['count']} tracks.")


def scan_library():
    """Synchronous wrapper for use in threads."""
    asyncio.run(scan_library_async())
