"""api/playlists.py — getPlaylists, getPlaylist, createPlaylist, updatePlaylist, deletePlaylist"""
from fastapi import APIRouter, Request
from typing import Optional
from api.helpers import ok, err, require_user
from api.browsing import _fmt_song
import services.library as lib

router = APIRouter()
_M     = ["GET", "POST"]
def _r(p): return [f"/rest/{p}", f"/rest/{p}.view"]


def _fmt_playlist(row, song_count: int = None, songs: list = None) -> dict:
    pl = {
        "id":        row["id"],
        "name":      row["name"],
        "comment":   row["comment"] or "",
        "public":    bool(row["public"]),
        "owner":     row["owner_id"],
        "created":   row["created_at"],
        "changed":   row["updated_at"],
        "songCount": song_count if song_count is not None else 0,
        "duration":  0,
        "coverArt":  "",
    }
    if songs is not None:
        pl["entry"]    = songs
        pl["duration"] = sum(s.get("duration", 0) for s in songs)
    return pl


@router.api_route(*_r("getPlaylists"), methods=_M)
def get_playlists(request: Request):
    user, e = require_user(request)
    if e: return e
    rows = lib.list_playlists(user["id"])
    result = []
    for row in rows:
        songs     = lib.get_playlist_songs(row["id"])
        result.append(_fmt_playlist(row, song_count=len(songs)))
    return ok({"playlists": {"playlist": result}})


@router.api_route(*_r("getPlaylist"), methods=_M)
def get_playlist(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    row = lib.get_playlist(id)
    if not row: return err(70, "Playlist not found")
    songs = lib.get_playlist_songs(id)
    uid   = user["id"] if user else None
    songs_fmt = [_fmt_song(s, uid) for s in songs]
    return ok({"playlist": _fmt_playlist(row, len(songs_fmt), songs_fmt)})


@router.api_route(*_r("createPlaylist"), methods=_M)
def create_playlist(request: Request, name: str = "", playlistId: str = "",
                    songId: list[str] = None):
    user, e = require_user(request)
    if e: return e
    if playlistId:
        lib.update_playlist(playlistId, name=name or None, song_ids=songId or [])
        row = lib.get_playlist(playlistId)
    else:
        pid = lib.create_playlist(user["id"], name or "New Playlist", songId or [])
        row = lib.get_playlist(pid)
    songs = lib.get_playlist_songs(row["id"])
    return ok({"playlist": _fmt_playlist(row, len(songs))})


@router.api_route(*_r("updatePlaylist"), methods=_M)
def update_playlist(request: Request, playlistId: str = "", name: str = None,
                    comment: str = None, public: bool = None,
                    songIdToAdd: list[str] = None, songIndexToRemove: list[int] = None):
    user, e = require_user(request)
    if e: return e
    lib.update_playlist(playlistId, name=name, public=public)
    if songIdToAdd:
        current = [s["id"] for s in lib.get_playlist_songs(playlistId)]
        lib.update_playlist(playlistId, song_ids=current + list(songIdToAdd))
    if songIndexToRemove:
        current = [s["id"] for s in lib.get_playlist_songs(playlistId)]
        for idx in sorted(songIndexToRemove, reverse=True):
            if 0 <= idx < len(current):
                current.pop(idx)
        lib.update_playlist(playlistId, song_ids=current)
    return ok()


@router.api_route(*_r("deletePlaylist"), methods=_M)
def delete_playlist(request: Request, id: str = ""):
    user, e = require_user(request)
    if e: return e
    lib.delete_playlist(id)
    return ok()
