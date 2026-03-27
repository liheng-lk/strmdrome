"""api/search.py — search3 (artists, albums, songs fuzzy search)"""
from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
from api.browsing import _fmt_artist, _fmt_album, _fmt_song
import services.library as lib

router = APIRouter()
_M     = ["GET", "POST"]
def _r(p): return [f"/rest/{p}", f"/rest/{p}.view"]


@router.api_route(*_r("search"), methods=_M)
@router.api_route(*_r("search2"), methods=_M)
@router.api_route(*_r("search3"), methods=_M)
def search3(request: Request, query: str = "", artistCount: int = 5,
            albumCount: int = 10, songCount: int = 20,
            artistOffset: int = 0, albumOffset: int = 0, songOffset: int = 0):
    user, e = require_user(request)
    if e: return e
    if not query:
        return ok({"searchResult3": {"artist": [], "album": [], "song": []}})
    uid     = user["id"] if user else None
    artists, albums, songs = lib.search(
        query,
        artist_count=artistCount, album_count=albumCount, song_count=songCount,
        offset=artistOffset,
    )
    return ok({"searchResult3": {
        "artist": [_fmt_artist(a) for a in artists],
        "album":  [_fmt_album(a)  for a in albums],
        "song":   [_fmt_song(s, uid) for s in songs],
    }})
