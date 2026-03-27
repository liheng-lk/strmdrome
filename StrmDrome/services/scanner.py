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


async def scan_library_async(target_folder_id: Optional[int] = None):
    if _scan_status["scanning"]:
        logger.info("Scan already in progress, skipping.")
        return
    _scan_status["scanning"] = True
    _scan_status["count"]    = 0
    
    from db.database import get_connection
    conn = get_connection()
    if target_folder_id:
        folders = conn.execute("SELECT * FROM folders WHERE id=?", (target_folder_id,)).fetchall()
    else:
        folders = conn.execute("SELECT * FROM folders").fetchall()
    conn.close()
    
    logger.info(f"Starting library scan across {len(folders)} folders.")

    # Collect all metadata items first
    strm_files = [] # (strm_path OR alist_path, folder_path, folder_id, is_alist)
    
    for folder in folders:
        fid, fpath = folder["id"], folder["path"]
        
        # AList integration
        if folder.get("alist_url"):
            from services.alist import AListClient
            client = AListClient(fid, folder["alist_url"], folder.get("alist_username"), folder.get("alist_password"), folder.get("alist_token"))
            logger.info(f"Scanning AList remote directory: {fpath}")
            
            for alist_filepath in client.walk(fpath):
                strm_files.append((alist_filepath, fpath, fid, True))
            continue
            
        # Traditional local file scanning
        if not os.path.isdir(fpath):
            continue
            
        for root, dirs, files in os.walk(fpath):
            dirs.sort()
            for fn in sorted(files):
                if fn.lower().endswith(".strm"):
                    strm_files.append((os.path.join(root, fn), fpath, fid, False))

    logger.info(f"Found {len(strm_files)} media files.")

    # Process in semaphore-controlled async batches for the scraper
    sem = asyncio.Semaphore(config.SCRAPE_CONCURRENCY)

    async def process_one(strm_info):
        media_path, fpath, fid, is_alist = strm_info
        async with sem:
            parsed = parse_strm_path(media_path, fpath)

            artist_name = parsed.artist or "Unknown Artist"
            album_name  = parsed.album  or "Unknown Album"

            aid  = lib.upsert_artist(artist_name)
            alid = lib.upsert_album(aid, artist_name, album_name, parsed.year, folder_id=fid)
            sid  = lib.upsert_song(
                path       = media_path,
                album_id   = alid,
                artist_id  = aid,
                title      = parsed.title,
                track_num  = parsed.track_num,
                disc_num   = parsed.disc_num,
                folder_id  = fid
            )

            # Run external scraper (NetEase/LastFM) only if never scraped before
            from db.database import get_connection
            row = get_connection().execute(
                "SELECT last_scraped FROM songs WHERE id=?", (sid,)
            ).fetchone()
            if not row or not row["last_scraped"]:
                # If it's pure AList, the local path check in scrape_song (.nfo / .lrc) will safely skip
                # NetEase/MusicBrainz web APIs will still fetch the album covers!
                await scrape_song(media_path if not is_alist else fpath, parsed, aid, alid, sid)

            _scan_status["count"] += 1

    await asyncio.gather(*[process_one(info) for info in strm_files])

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


def scan_library(folder_id=None):
    """Synchronous wrapper for use in threads."""
    asyncio.run(scan_library_async(folder_id))
