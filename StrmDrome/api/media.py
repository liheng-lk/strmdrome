"""api/media.py — stream (302), download, getCoverArt (resize), getLyrics, getAvatar"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import Response, RedirectResponse
from api.helpers import ok, err, require_user
from services.stream import resolve_strm_url
import services.library as lib
from utils.image import resize_cover
from utils.lrc import parse_lrc
import asyncio

router = APIRouter()
_M     = ["GET", "POST"]


@router.api_route("/rest/stream", methods=_M)
@router.api_route("/rest/stream.view", methods=_M)
@router.api_route("/rest/download", methods=_M)
@router.api_route("/rest/download.view", methods=_M)
async def stream(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_song(id)
    if not row: return err(70, "Song not found")
    url = await resolve_strm_url(row["path"], row.get("folder_id"))
    if not url:
        return err(70, "Could not resolve stream URL")
    # Record play in background
    if user:
        try:
            lib.record_scrobble(user["id"], id)
        except Exception:
            pass
    return RedirectResponse(url=url, status_code=302)


@router.api_route("/rest/getCoverArt", methods=_M)
@router.api_route("/rest/getCoverArt.view", methods=_M)
def get_cover_art(request: Request, id: str = "", size: int = 0):
    # id can be an album_id or song_id
    conn = __import__("db.database", fromlist=["get_connection"]).get_connection()
    album = conn.execute("SELECT cover_path FROM albums WHERE id=?", (id,)).fetchone()
    if album and album["cover_path"]:
        cover = album["cover_path"]
    else:
        song  = conn.execute("SELECT cover_path FROM songs WHERE id=?", (id,)).fetchone()
        cover = song["cover_path"] if song else None
    conn.close()
    data = resize_cover(cover, size) if cover else None
    if not data:
        return Response(status_code=404)
    return Response(content=data, media_type="image/jpeg")


@router.api_route("/rest/getLyrics", methods=_M)
@router.api_route("/rest/getLyrics.view", methods=_M)
def get_lyrics(request: Request, artist: str = "", title: str = "", id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_song(id) if id else None
    # Search by title+artist if no id given
    if not row and (artist or title):
        from db.database import get_connection
        conn = get_connection()
        row  = conn.execute(
            "SELECT * FROM songs WHERE title LIKE ? LIMIT 1", (f"%{title}%",)
        ).fetchone()
        conn.close()
    if not row:
        return err(70, "Song not found")
    # Prefer synced LRC content, fallback to plain
    lrc_content = row["lyrics_synced"] or ""
    plain       = row["lyrics_plain"]  or ""
    if lrc_content:
        _, lines = parse_lrc(lrc_content)
        plain    = "\n".join(t for _, t in lines if t)
    return ok({"lyrics": {"artist": artist, "title": title, "value": plain}})


@router.api_route("/rest/getAvatar", methods=_M)
@router.api_route("/rest/getAvatar.view", methods=_M)
@router.api_route("/rest/getAvatar", methods=_M)
@router.api_route("/rest/getAvatar.view", methods=_M)
def get_avatar(request: Request, id: str = ""):
    from db.database import get_connection
    conn = get_connection()
    row  = conn.execute("SELECT image_path FROM artists WHERE id=?", (id,)).fetchone()
    conn.close()
    if row and row["image_path"] and os.path.exists(row["image_path"]):
        data = resize_cover(row["image_path"], 300)
        if data:
            return Response(content=data, media_type="image/jpeg")
    return Response(status_code=404)
