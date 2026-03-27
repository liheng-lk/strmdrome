"""api/albumlist.py — getAlbumList, getAlbumList2, getRandomSongs, getSongsByGenre"""
from fastapi import APIRouter, Request
from typing import Optional
from api.helpers import ok, err, require_user
from api.browsing import _fmt_album, _fmt_song
import services.library as lib

router = APIRouter()
_M     = ["GET", "POST"]
def _r(p): return [f"/rest/{p}", f"/rest/{p}.view"]


@router.api_route(*_r("getAlbumList"),  methods=_M)
@router.api_route(*_r("getAlbumList2"), methods=_M)
def get_album_list(
    request:  Request,
    type:     str = "random",
    size:     int = 10,
    offset:   int = 0,
    fromYear: Optional[int] = None,
    toYear:   Optional[int] = None,
    genre:    Optional[str] = None,
):
    user, e = require_user(request)
    if e: return e
    uid    = user["id"] if user else None
    rows   = lib.get_album_list(type, size=size, offset=offset,
                                from_year=fromYear, to_year=toYear,
                                genre=genre, user_id=uid)
    albums = [_fmt_album(r) for r in rows]
    return ok({"albumList2": {"album": albums}, "albumList": {"album": albums}})


@router.api_route(*_r("getRandomSongs"), methods=_M)
def get_random_songs(request: Request, size: int = 10, genre: str = "",
                     fromYear: int = 0, toYear: int = 0):
    user, e = require_user(request)
    if e: return e
    from db.database import get_connection
    conn = get_connection()
    sql  = "SELECT * FROM songs WHERE 1=1"
    params: list = []
    if genre:    sql += " AND genre=?"; params.append(genre)
    if fromYear: sql += " AND year>=?"; params.append(fromYear)
    if toYear:   sql += " AND year<=?"; params.append(toYear)
    sql += f" ORDER BY RANDOM() LIMIT {min(size,500)}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    uid  = user["id"] if user else None
    return ok({"randomSongs": {"song": [_fmt_song(r, uid) for r in rows]}})


@router.api_route(*_r("getSongsByGenre"), methods=_M)
def get_songs_by_genre(request: Request, genre: str = "", count: int = 10, offset: int = 0):
    user, e = require_user(request)
    if e: return e
    from db.database import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM songs WHERE genre=? ORDER BY title LIMIT ? OFFSET ?",
        (genre, count, offset)
    ).fetchall()
    conn.close()
    uid = user["id"] if user else None
    return ok({"songsByGenre": {"song": [_fmt_song(r, uid) for r in rows]}})


@router.api_route(*_r("getNowPlaying"), methods=_M)
def get_now_playing(request: Request):
    user, e = require_user(request)
    if e: return e
    return ok({"nowPlaying": {"entry": []}})


@router.api_route(*_r("getStarred"),  methods=_M)
@router.api_route(*_r("getStarred2"), methods=_M)
def get_starred(request: Request):
    user, e = require_user(request)
    if e: return e
    uid  = user["id"]
    conn = __import__("db.database", fromlist=["get_connection"]).get_connection()
    songs = conn.execute("""
        SELECT s.* FROM songs s
        JOIN annotations a ON a.item_id=s.id AND a.item_type='song'
            AND a.user_id=? AND a.starred=1
        ORDER BY a.starred_at DESC LIMIT 100
    """, (uid,)).fetchall()
    albums = conn.execute("""
        SELECT al.* FROM albums al
        JOIN annotations a ON a.item_id=al.id AND a.item_type='album'
            AND a.user_id=? AND a.starred=1
        ORDER BY a.starred_at DESC LIMIT 50
    """, (uid,)).fetchall()
    artists = conn.execute("""
        SELECT ar.* FROM artists ar
        JOIN annotations a ON a.item_id=ar.id AND a.item_type='artist'
            AND a.user_id=? AND a.starred=1
        ORDER BY a.starred_at DESC LIMIT 50
    """, (uid,)).fetchall()
    conn.close()
    from api.browsing import _fmt_artist, _fmt_album
    result = {
        "song":   [_fmt_song(r, uid) for r in songs],
        "album":  [_fmt_album(r) for r in albums],
        "artist": [_fmt_artist(r) for r in artists],
    }
    return ok({"starred": result, "starred2": result})
