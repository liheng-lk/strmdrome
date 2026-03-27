"""
services/scraper.py
Full metadata scraping pipeline for StrmDrome v2.

Priority chain for EACH song:
  1. Local .nfo XML (Kodi/Jellyfin format)
  2. Local .json cache (StrmDrome own cache – avoids repeated API calls)
  3. Local .lrc file → write lyrics to DB
  4. 网易云音乐 (NetEase) API  — best for Chinese/Asian music
  5. MusicBrainz API          — best for Western music
  6. LastFM API               — artist biography + similar artists (optional)

All metadata, covers, and LRC files are stored in /data/catalog/
The /music directory is NEVER written to (read-only safe).
"""

import os
import json
import re
import asyncio
import logging
import hashlib
import httpx
from datetime import datetime, timezone
from typing import Optional

import config
from db.database import get_connection
from utils.parser import ParsedTrack
from utils.lrc import parse_lrc

logger = logging.getLogger(__name__)


# ── Catalog path helpers ─────────────────────────────────────────────────────

def catalog_dir(artist: str, album: str = "") -> str:
    """Return the catalog directory path for an artist/album."""
    safe_a = _safe_name(artist)
    path   = os.path.join(config.CATALOG_DIR, safe_a)
    if album:
        path = os.path.join(path, _safe_name(album))
    os.makedirs(path, exist_ok=True)
    return path


def _safe_name(s: str) -> str:
    """Sanitize a string for use as a directory/file name."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(". ")


# ── NFO Parser ───────────────────────────────────────────────────────────────

def _parse_nfo(nfo_path: str) -> dict:
    """Parse a Kodi-style .nfo XML file for music metadata."""
    meta: dict = {}
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        for tag, key in [
            ("title",   "title"),  ("artist", "artist"), ("album",  "album"),
            ("year",    "year"),   ("genre",  "genre"),  ("track",  "track_num"),
            ("comment", "description"),
        ]:
            el = root.find(tag)
            if el is not None and el.text:
                meta[key] = el.text.strip()
        if "year" in meta:
            meta["year"] = int(meta["year"]) if str(meta["year"]).isdigit() else 0
        if "track_num" in meta:
            meta["track_num"] = int(meta["track_num"]) if str(meta["track_num"]).isdigit() else 0
    except Exception as e:
        logger.debug(f"NFO parse failed for {nfo_path}: {e}")
    return meta


# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_path(song_path: str) -> str:
    """Return path to the catalog JSON cache for a given .strm file."""
    sid   = hashlib.md5(song_path.encode()).hexdigest()[:12]
    cdir  = os.path.join(config.CATALOG_DIR, ".cache")
    os.makedirs(cdir, exist_ok=True)
    return os.path.join(cdir, f"{sid}.json")


def _load_cache(song_path: str) -> Optional[dict]:
    cp = _cache_path(song_path)
    if os.path.exists(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_cache(song_path: str, data: dict):
    cp = _cache_path(song_path)
    try:
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write cache {cp}: {e}")


# ── NetEase API ───────────────────────────────────────────────────────────────

async def _netease_search(title: str, artist: str = "") -> Optional[dict]:
    """Search NetEase Cloud Music. Returns dict with duration, album, cover_url."""
    if not config.NETEASE_ENABLED:
        return None
    q = f"{artist} {title}".strip()
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer":    "http://music.163.com/"
        }) as client:
            r = await client.post(
                "http://music.163.com/api/search/get/web",
                data={"s": q, "type": 1, "offset": 0, "total": "true", "limit": 3}
            )
            songs = r.json().get("result", {}).get("songs", [])
            if not songs:
                return None
            # Use first hit, but prefer one whose artist matches
            song = songs[0]
            for s in songs:
                if artist and any(
                    a.get("name", "").lower() == artist.lower()
                    for a in s.get("artists", [])
                ):
                    song = s
                    break
            album  = song.get("album", {})
            return {
                "title":     song.get("name"),
                "artist":    song.get("artists", [{}])[0].get("name"),
                "album":     album.get("name"),
                "year":      album.get("publishTime", 0) // (1000 * 3600 * 24 * 365) + 1970 if album.get("publishTime") else 0,
                "duration":  int(song.get("duration", 0) / 1000),
                "cover_url": album.get("picUrl"),
            }
    except Exception as e:
        logger.debug(f"NetEase search failed: {e}")
    return None


# ── MusicBrainz API ──────────────────────────────────────────────────────────

async def _musicbrainz_search(title: str, artist: str = "") -> Optional[dict]:
    """Search MusicBrainz for recording metadata."""
    q = f'recording:"{title}"'
    if artist:
        q += f' AND artist:"{artist}"'
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": f"{config.MUSICBRAINZ_APP} ( https://strmdrome.local )"}
        ) as client:
            r = await client.get(
                "https://musicbrainz.org/ws/2/recording",
                params={"query": q, "fmt": "json", "limit": 3}
            )
            recs = r.json().get("recordings", [])
            if not recs:
                return None
            rec = recs[0]
            releases = rec.get("releases", [{}])
            release  = releases[0] if releases else {}
            year     = 0
            rd = release.get("date", "")
            if rd and len(rd) >= 4 and rd[:4].isdigit():
                year = int(rd[:4])
            genres = [g["name"] for g in rec.get("genres", []) if "name" in g]
            return {
                "title":   rec.get("title"),
                "mbz_id":  rec.get("id"),
                "year":    year,
                "genre":   genres[0] if genres else "",
                "album":   release.get("title", ""),
                "duration": int(rec.get("length", 0) / 1000) if rec.get("length") else 0,
            }
    except Exception as e:
        logger.debug(f"MusicBrainz search failed: {e}")
    return None


# ── LastFM API (artist bio) ──────────────────────────────────────────────────

async def _lastfm_artist_info(artist_name: str) -> Optional[dict]:
    if not config.LASTFM_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method":  "artist.getinfo",
                    "artist":  artist_name,
                    "api_key": config.LASTFM_API_KEY,
                    "format":  "json",
                    "lang":    "zh",
                }
            )
            info = r.json().get("artist", {})
            images = info.get("image", [])
            # Last image is typically highest res
            img_url = next(
                (i["#text"] for i in reversed(images) if i.get("#text")), None
            )
            return {
                "biography": info.get("bio", {}).get("summary", ""),
                "image_url": img_url,
                "similar":   [s.get("name","") for s in info.get("similar", {}).get("artist", [])],
            }
    except Exception as e:
        logger.debug(f"LastFM artist info failed: {e}")
    return None


# ── Image download ────────────────────────────────────────────────────────────

async def _download_image(url: str, dest: str):
    if not url or os.path.exists(dest):
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, follow_redirects=True)
            if r.status_code == 200:
                with open(dest, "wb") as f:
                    f.write(r.content)
    except Exception as e:
        logger.debug(f"Image download failed ({url}): {e}")


# ── Core scrape function ─────────────────────────────────────────────────────

async def scrape_song(song_path: str, parsed: ParsedTrack, artist_id: str, album_id: str, song_id: str):
    """
    Run the full scraping pipeline for one .strm file.
    Writes results to both the DB and the /data/catalog cache.
    """
    # Check local JSON cache first
    cached = _load_cache(song_path)
    if cached:
        _write_song_to_db(song_id, artist_id, album_id, song_path, cached)
        return cached

    meta: dict = {
        "title":    parsed.title,
        "artist":   parsed.artist or "Unknown Artist",
        "album":    parsed.album  or "Unknown Album",
        "track_num": parsed.track_num,
        "disc_num": parsed.disc_num,
        "year":     parsed.year,
        "duration": 0,
        "genre":    "",
        "cover_path": None,
        "lyrics_synced": None,
        "lyrics_plain": None,
    }

    base_name = os.path.splitext(os.path.basename(song_path))[0]
    song_dir  = os.path.dirname(song_path)
    artist_n  = parsed.artist or "Unknown Artist"
    album_n   = parsed.album  or "Unknown Album"

    # ── Phase 1: Local NFO ───────────────────────────────────────────────────
    for nfo_name in [f"{base_name}.nfo", "album.nfo"]:
        nfo_path = os.path.join(song_dir, nfo_name)
        if os.path.exists(nfo_path):
            meta.update({k: v for k, v in _parse_nfo(nfo_path).items() if v})
            break

    # ── Phase 2: Local LRC ───────────────────────────────────────────────────
    for lrc_name in [f"{base_name}.lrc", f"{base_name}.zh.lrc"]:
        lrc_path = os.path.join(song_dir, lrc_name)
        if os.path.exists(lrc_path):
            try:
                content   = open(lrc_path, encoding="utf-8").read()
                _, lyric_lines = parse_lrc(content)
                meta["lyrics_synced"] = content
                meta["lyrics_plain"]  = "\n".join(t for _, t in lyric_lines if t)
            except Exception:
                pass
            break

    # ── Phase 3: Local cover ─────────────────────────────────────────────────
    cdir = catalog_dir(artist_n, album_n)
    catalog_cover = os.path.join(cdir, "cover.jpg")
    for local_cover in ["cover.jpg", "folder.jpg", "cover.png", "front.jpg"]:
        p = os.path.join(song_dir, local_cover)
        if os.path.exists(p):
            import shutil
            if not os.path.exists(catalog_cover):
                shutil.copy2(p, catalog_cover)
            meta["cover_path"] = catalog_cover
            break

    # ── Phase 4: NetEase ─────────────────────────────────────────────────────
    netease = await _netease_search(parsed.title, artist_n)
    if netease:
        if not meta.get("duration") and netease.get("duration"):
            meta["duration"] = netease["duration"]
        if not meta.get("album") and netease.get("album"):
            meta["album"] = netease["album"]
        if not meta.get("year") and netease.get("year"):
            meta["year"] = netease["year"]
        # Download cover from NetEase if we still don't have one
        if not meta.get("cover_path") and netease.get("cover_url"):
            await _download_image(netease["cover_url"], catalog_cover)
            if os.path.exists(catalog_cover):
                meta["cover_path"] = catalog_cover

    # ── Phase 5: MusicBrainz (fills genre + year gaps) ───────────────────────
    if not meta.get("genre") or not meta.get("year"):
        mbz = await _musicbrainz_search(parsed.title, artist_n)
        if mbz:
            if not meta.get("genre") and mbz.get("genre"):
                meta["genre"] = mbz["genre"]
            if not meta.get("year") and mbz.get("year"):
                meta["year"] = mbz["year"]
            if not meta.get("duration") and mbz.get("duration"):
                meta["duration"] = mbz["duration"]

    # ── Write DB + cache ─────────────────────────────────────────────────────
    _save_cache(song_path, meta)
    _write_song_to_db(song_id, artist_id, album_id, song_path, meta)
    return meta


async def scrape_artist(artist_id: str, artist_name: str):
    """Fetch artist biography + image from LastFM."""
    info = await _lastfm_artist_info(artist_name)
    if not info:
        return
    adir = catalog_dir(artist_name)
    avatar_path = os.path.join(adir, "avatar.jpg")
    if info.get("image_url"):
        await _download_image(info["image_url"], avatar_path)
    conn = get_connection()
    conn.execute(
        "UPDATE artists SET biography=?, image_path=?, last_scraped=? WHERE id=?",
        (
            info.get("biography", ""),
            avatar_path if os.path.exists(avatar_path) else None,
            datetime.now(timezone.utc).isoformat(),
            artist_id,
        )
    )
    conn.commit()
    conn.close()


def _write_song_to_db(song_id: str, artist_id: str, album_id: str, path: str, meta: dict):
    conn = get_connection()
    now  = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE songs SET
            title=?, track_num=?, disc_num=?, duration=?, year=?, genre=?,
            cover_path=?, lyrics_synced=?, lyrics_plain=?, last_scraped=?, updated_at=?
        WHERE id=?
    """, (
        meta.get("title"),   meta.get("track_num", 0), meta.get("disc_num", 1),
        meta.get("duration", 0), meta.get("year", 0), meta.get("genre", ""),
        meta.get("cover_path"), meta.get("lyrics_synced"), meta.get("lyrics_plain"),
        now, now, song_id,
    ))
    conn.commit()
    conn.close()
