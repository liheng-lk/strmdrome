"""api/annotation.py — star, unstar, setRating, scrobble"""
from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
import services.library as lib

router = APIRouter()
_M     = ["GET", "POST"]


@router.api_route("/rest/star", methods=_M)
@router.api_route("/rest/star.view", methods=_M)
def star(request: Request, id: list[str] = None, albumId: list[str] = None,
         artistId: list[str] = None):
    user, e = require_user(request)
    if e: return e
    if id:       lib.star(user["id"], id,       "song")
    if albumId:  lib.star(user["id"], albumId,  "album")
    if artistId: lib.star(user["id"], artistId, "artist")
    return ok()


@router.api_route("/rest/unstar", methods=_M)
@router.api_route("/rest/unstar.view", methods=_M)
def unstar(request: Request, id: list[str] = None, albumId: list[str] = None,
           artistId: list[str] = None):
    user, e = require_user(request)
    if e: return e
    if id:       lib.unstar(user["id"], id,       "song")
    if albumId:  lib.unstar(user["id"], albumId,  "album")
    if artistId: lib.unstar(user["id"], artistId, "artist")
    return ok()


@router.api_route("/rest/setRating", methods=_M)
@router.api_route("/rest/setRating.view", methods=_M)
def set_rating(request: Request, id: str = "", rating: int = 0):
    user, e = require_user(request)
    if e: return e
    lib.set_rating(user["id"], id, rating)
    return ok()


@router.api_route("/rest/scrobble", methods=_M)
@router.api_route("/rest/scrobble.view", methods=_M)
def scrobble(request: Request, id: str = "", submission: bool = True):
    user, e = require_user(request)
    if e: return e
    if submission:
        lib.record_scrobble(user["id"], id)
    return ok()
