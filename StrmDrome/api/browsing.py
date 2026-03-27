"""
api/browsing.py
ID3-mode browsing: getArtists, getArtist, getAlbum, getSong,
getMusicDirectory (legacy folder mode), getIndexes, getGenres, getArtistInfo.
"""
from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
import services.library as lib
from db.database import get_connection

router  = APIRouter()
_M      = ["GET","POST"]




def _fmt_artist(row, albums=None) -> dict:
    a = {"id": row["id"], "name": row["name"], "albumCount": row["album_count"] or 0}
    if row["image_path"]: a["artistImageUrl"] = f"/rest/getAvatar?id={row['id']}"
    if albums is not None: a["album"] = albums
    return a


def _fmt_album(row, songs=None) -> dict:
    al = {
        "id": row["id"], "name": row["title"], "title": row["title"],
        "artist": "", "artistId": row["artist_id"],
        "year": row["year"] or 0, "genre": row["genre"] or "",
        "songCount": row["song_count"] or 0, "duration": row["duration"] or 0,
    }
    if row["cover_path"]: al["coverArt"] = row["id"]
    if songs is not None: al["song"] = songs
    # Resolve artist name
    conn = get_connection()
    artist = conn.execute("SELECT name FROM artists WHERE id=?", (row["artist_id"],)).fetchone()
    conn.close()
    if artist: al["artist"] = artist["name"]
    return al


def _fmt_song(row, user_id: str = None) -> dict:
    s = {
        "id": row["id"], "title": row["title"] or "", "album": "",
        "artist": "", "artistId": row["artist_id"], "albumId": row["album_id"],
        "track": row["track_num"] or 0, "discNumber": row["disc_num"] or 1,
        "year": row["year"] or 0, "genre": row["genre"] or "",
        "duration": row["duration"] or 0,
        "suffix": "strm", "contentType": "audio/mpeg", "isDir": False,
        "type": "music",
    }
    if row["cover_path"]: s["coverArt"] = row["album_id"]
    # Resolve album + artist names
    conn = get_connection()
    album  = conn.execute("SELECT title FROM albums  WHERE id=?", (row["album_id"],)).fetchone()
    artist = conn.execute("SELECT name  FROM artists WHERE id=?", (row["artist_id"],)).fetchone()
    conn.close()
    if album:  s["album"]  = album["title"]
    if artist: s["artist"] = artist["name"]
    # Annotation
    if user_id:
        ann = lib.get_annotation(user_id, row["id"])
        if ann:
            if ann["starred"]:    s["starred"] = ann["starred_at"]
            if ann["rating"]:     s["userRating"] = ann["rating"]
            if ann["play_count"]: s["playCount"]  = ann["play_count"]
    return s


# ── getArtists (ID3 mode) ─────────────────────────────────────────────────────

@router.api_route("/rest/getArtists", methods=_M)
@router.api_route("/rest/getArtists.view", methods=_M)
def get_artists(request: Request):
    user, e = require_user(request)
    if e: return e
    artists = lib.list_artists()
    indices: dict[str, list] = {}
    for a in artists:
        ch = (a["sort_name"] or a["name"] or "#")[0].upper()
        if not ch.isalpha(): ch = "#"
        indices.setdefault(ch, []).append(_fmt_artist(a))
    index_list = [{"name": k, "artist": v} for k, v in sorted(indices.items())]
    return ok({"artists": {"index": index_list, "lastModified": 1, "ignoredArticles": "The"}})


# ── getIndexes (legacy folder mode, same as getArtists) ───────────────────────

@router.api_route("/rest/getIndexes", methods=_M)
@router.api_route("/rest/getIndexes.view", methods=_M)
def get_indexes(request: Request):
    return get_artists(request)


# ── getArtist ─────────────────────────────────────────────────────────────────

@router.api_route("/rest/getArtist", methods=_M)
@router.api_route("/rest/getArtist.view", methods=_M)
def get_artist(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_artist(id)
    if not row: return err(70, "Artist not found")
    albums = [_fmt_album(a) for a in lib.list_albums_by_artist(id)]
    return ok({"artist": _fmt_artist(row, albums)})


# ── getAlbum ──────────────────────────────────────────────────────────────────

@router.api_route("/rest/getAlbum", methods=_M)
@router.api_route("/rest/getAlbum.view", methods=_M)
def get_album(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_album(id)
    if not row: return err(70, "Album not found")
    songs = [_fmt_song(s, user["id"] if user else None) for s in lib.list_songs_by_album(id)]
    return ok({"album": _fmt_album(row, songs)})


# ── getSong ───────────────────────────────────────────────────────────────────

@router.api_route("/rest/getSong", methods=_M)
@router.api_route("/rest/getSong.view", methods=_M)
def get_song(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_song(id)
    if not row: return err(70, "Song not found")
    return ok({"song": _fmt_song(row, user["id"] if user else None)})


# ── getMusicDirectory (legacy folder browsing) ────────────────────────────────

@router.api_route("/rest/getMusicDirectory", methods=_M)
@router.api_route("/rest/getMusicDirectory.view", methods=_M)
def get_music_directory(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    # Determine if id is an artist or album
    conn = get_connection()
    row  = conn.execute("SELECT * FROM artists WHERE id=?", (id,)).fetchone()
    if row:
        children = [_fmt_album(a) for a in lib.list_albums_by_artist(id)]
        result   = {"id": id, "name": row["name"], "child": children}
        conn.close()
        return ok({"directory": result})
    row = conn.execute("SELECT * FROM albums WHERE id=?", (id,)).fetchone()
    if row:
        songs = [_fmt_song(s, user["id"] if user else None) for s in lib.list_songs_by_album(id)]
        result = {"id": id, "name": row["title"], "parent": row["artist_id"], "child": songs}
        conn.close()
        return ok({"directory": result})
    conn.close()
    return err(70, "Directory not found")


# ── getGenres ─────────────────────────────────────────────────────────────────

@router.api_route("/rest/getGenres", methods=_M)
@router.api_route("/rest/getGenres.view", methods=_M)
def get_genres(request: Request):
    user, e = require_user(request)
    if e: return e
    rows = lib.list_genres()
    genres = [{"value": r["genre"], "songCount": r["song_count"], "albumCount": r["album_count"]}
              for r in rows if r["genre"]]
    return ok({"genres": {"genre": genres}})


# ── getArtistInfo / getArtistInfo2 ────────────────────────────────────────────

@router.api_route("/rest/getArtistInfo", methods=_M)
@router.api_route("/rest/getArtistInfo.view", methods=_M)
@router.api_route("/rest/getArtistInfo2", methods=_M)
@router.api_route("/rest/getArtistInfo2.view", methods=_M)
def get_artist_info(request: Request, id: str = "", count: int = 5, includeNotPresent: bool = False):
    user, e = require_user(request)
    if e: return e
    row  = lib.get_artist(id)
    if not row: return err(70, "Artist not found")
    info: dict = {}
    if row["biography"]:  info["biography"]  = row["biography"]
    if row["image_path"]: info["largeImageUrl"] = f"/rest/getAvatar?id={id}"
    return ok({"artistInfo": info, "artistInfo2": info})
