"""api/annotation.py — star, unstar, setRating, scrobble"""
from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
import services.library as lib

router = APIRouter()
_M     = ["GET", "POST"]
def _r(p): return [f"/rest/{p}", f"/rest/{p}.view"]


@router.api_route(*_r("star"), methods=_M)
def star(request: Request, id: list[str] = None, albumId: list[str] = None,
         artistId: list[str] = None):
    user, e = require_user(request)
    if e: return e
    if id:       lib.star(user["id"], id,       "song")
    if albumId:  lib.star(user["id"], albumId,  "album")
    if artistId: lib.star(user["id"], artistId, "artist")
    return ok()


@router.api_route(*_r("unstar"), methods=_M)
def unstar(request: Request, id: list[str] = None, albumId: list[str] = None,
           artistId: list[str] = None):
    user, e = require_user(request)
    if e: return e
    if id:       lib.unstar(user["id"], id,       "song")
    if albumId:  lib.unstar(user["id"], albumId,  "album")
    if artistId: lib.unstar(user["id"], artistId, "artist")
    return ok()


@router.api_route(*_r("setRating"), methods=_M)
def set_rating(request: Request, id: str = "", rating: int = 0):
    user, e = require_user(request)
    if e: return e
    lib.set_rating(user["id"], id, rating)
    return ok()


@router.api_route(*_r("scrobble"), methods=_M)
def scrobble(request: Request, id: str = "", submission: bool = True):
    user, e = require_user(request)
    if e: return e
    if submission:
        lib.record_scrobble(user["id"], id)
    return ok()
