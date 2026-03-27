"""Shared helpers used by all API handlers."""
from fastapi import Request
from fastapi.responses import JSONResponse
from services.auth import authenticate_subsonic


def ok(data: dict = None) -> JSONResponse:
    body = {"subsonic-response": {"status": "ok", "version": "1.16.1"}}
    if data:
        body["subsonic-response"].update(data)
    return JSONResponse(content=body)


def err(code: int, message: str) -> JSONResponse:
    return JSONResponse(content={
        "subsonic-response": {
            "status": "failed", "version": "1.16.1",
            "error": {"code": code, "message": message}
        }
    })


def get_user(request: Request):
    """Return current user row or None."""
    u = request.query_params.get("u", "")
    p = request.query_params.get("p", "")
    t = request.query_params.get("t", "")
    s = request.query_params.get("s", "")
    return authenticate_subsonic(u=u, p=p, t=t, s=s)


def require_user(request: Request):
    """Return user or raise 401 dict."""
    user = get_user(request)
    if not user:
        return None, err(40, "Wrong username or password.")
    return user, None
