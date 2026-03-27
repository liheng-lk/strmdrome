"""api/user_mgmt.py — getUser, getUsers, createUser, updateUser, deleteUser, changePassword"""
from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
import services.auth as auth_svc

router = APIRouter()
_M     = ["GET", "POST"]


def _fmt_user(row) -> dict:
    return {
        "username":       row["username"],
        "email":          row["email"] or "",
        "adminRole":      bool(row["is_admin"]),
        "scrobblingEnabled": True,
        "shareRole":      True,
        "downloadRole":   True,
        "uploadRole":     False,
        "playlistRole":   True,
        "coverArtRole":   True,
        "commentRole":    False,
        "podcastRole":    False,
        "streamRole":     True,
        "jukeboxRole":    False,
        "settingsRole":   bool(row["is_admin"]),
        "maxBitRate":     row["max_bitrate"] or 0,
        "folder":         [1],
    }


@router.api_route("/rest/getUser", methods=_M)
@router.api_route("/rest/getUser.view", methods=_M)
def get_user(request: Request, username: str = ""):
    user, e = require_user(request)
    if e: return e
    target = auth_svc.get_user_by_username(username or user["username"])
    if not target: return err(70, "User not found")
    return ok({"user": _fmt_user(target)})


@router.api_route("/rest/getUsers", methods=_M)
@router.api_route("/rest/getUsers.view", methods=_M)
def get_users(request: Request):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires admin role")
    users = auth_svc.list_users()
    return ok({"users": {"user": [_fmt_user(u) for u in users]}})


@router.api_route("/rest/createUser", methods=_M)
@router.api_route("/rest/createUser.view", methods=_M)
def create_user(request: Request, username: str = "", password: str = "",
                email: str = "", adminRole: bool = False):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires admin role")
    if not username or not password:
        return err(10, "Missing username or password")
    try:
        auth_svc.create_user(username, password, is_admin=adminRole, email=email)
    except Exception as ex:
        return err(0, str(ex))
    return ok()


@router.api_route("/rest/updateUser", methods=_M)
@router.api_route("/rest/updateUser.view", methods=_M)
def update_user(request: Request, username: str = "", password: str = "",
                email: str = None, adminRole: bool = None, maxBitRate: int = None):
    user, e = require_user(request)
    if e: return e
    target = auth_svc.get_user_by_username(username)
    if not target: return err(70, "User not found")
    kwargs = {}
    if password:    kwargs["password"]    = password
    if email:       kwargs["email"]       = email
    if adminRole is not None: kwargs["is_admin"] = adminRole
    if maxBitRate:  kwargs["max_bitrate"] = maxBitRate
    auth_svc.update_user(target["id"], **kwargs)
    return ok()


@router.api_route("/rest/deleteUser", methods=_M)
@router.api_route("/rest/deleteUser.view", methods=_M)
def delete_user(request: Request, username: str = ""):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires admin role")
    target = auth_svc.get_user_by_username(username)
    if not target: return err(70, "User not found")
    auth_svc.delete_user(target["id"])
    return ok()


@router.api_route("/rest/changePassword", methods=_M)
@router.api_route("/rest/changePassword.view", methods=_M)
def change_password(request: Request, username: str = "", password: str = ""):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"] and user["username"] != username:
        return err(50, "Not authorized")
    target = auth_svc.get_user_by_username(username)
    if not target: return err(70, "User not found")
    auth_svc.update_user(target["id"], password=password)
    return ok()
