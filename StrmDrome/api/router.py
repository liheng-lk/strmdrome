"""
api/router.py
Mount all Subsonic API routes and enforce global authentication.
All Subsonic endpoints are registered under /rest/.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from services.auth import authenticate_subsonic
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Import sub-routers
from api import system, browsing, search, albumlist, playlists, annotation, media, user_mgmt, admin

router = APIRouter()

# ── Auth middleware helper ────────────────────────────────────────────────────

def require_auth(request: Request):
    u = request.query_params.get("u", "")
    p = request.query_params.get("p", "")
    t = request.query_params.get("t", "")
    s = request.query_params.get("s", "")
    user = authenticate_subsonic(u=u, p=p, t=t, s=s)
    return user   # None = auth failure


def auth_error():
    return JSONResponse(content={
        "subsonic-response": {
            "status": "failed", "version": "1.16.1",
            "error": {"code": 40, "message": "Wrong username or password."}
        }
    })


# Mount all sub-routers (they share auth via dependency injection in each handler)
router.include_router(system.router)
router.include_router(browsing.router)
router.include_router(search.router)
router.include_router(albumlist.router)
router.include_router(playlists.router)
router.include_router(annotation.router)
router.include_router(media.router)
router.include_router(user_mgmt.router)
router.include_router(admin.router)
