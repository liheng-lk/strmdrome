"""api/system.py — ping, getLicense, getMusicFolders, getScanStatus, startScan"""
from fastapi import APIRouter, Request, BackgroundTasks
from api.helpers import ok, err, require_user
from services.scanner import get_scan_status, scan_library
import threading

router = APIRouter()
_METHODS = ["GET", "POST"]


def _route(path):
    return [f"/rest/{path}", f"/rest/{path}.view"]


@router.api_route(*_route("ping"), methods=_METHODS)
def ping(request: Request):
    user, e = require_user(request)
    return e or ok()


@router.api_route(*_route("getLicense"), methods=_METHODS)
def get_license(request: Request):
    user, e = require_user(request)
    return e or ok({"license": {
        "valid": True, "email": "user@strmdrome.local",
        "licenseExpires": "2099-12-31T00:00:00"
    }})


@router.api_route(*_route("getMusicFolders"), methods=_METHODS)
def get_music_folders(request: Request):
    user, e = require_user(request)
    return e or ok({"musicFolders": {"musicFolder": [{"id": 1, "name": "Music"}]}})


@router.api_route(*_route("getScanStatus"), methods=_METHODS)
def get_scan_status_endpoint(request: Request):
    user, e = require_user(request)
    if e: return e
    st = get_scan_status()
    return ok({"scanStatus": {
        "scanning": st["scanning"],
        "count":    st["count"],
        "lastScan": st["last_scan"] or "",
    }})


@router.api_route(*_route("startScan"), methods=_METHODS)
def start_scan(request: Request):
    user, e = require_user(request)
    if e: return e
    st = get_scan_status()
    if not st["scanning"]:
        t = threading.Thread(target=scan_library, daemon=True)
        t.start()
    return ok({"scanStatus": {"scanning": True, "count": st["count"]}})
