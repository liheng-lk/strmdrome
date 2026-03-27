from fastapi import APIRouter, Request
from api.helpers import ok, err, require_user
from db.database import get_connection

router = APIRouter()
_METHODS = ["GET", "POST"]

@router.api_route("/rest/strmdrome/getFolders", methods=_METHODS)
@router.api_route("/rest/strmdrome/getFolders.view", methods=_METHODS)
def sd_get_folders(request: Request):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires Admin role")
    conn = get_connection()
    folders = conn.execute("SELECT * FROM folders").fetchall()
    conn.close()
    return ok({"folders": [dict(f) for f in folders]})

@router.api_route("/rest/strmdrome/addFolder", methods=_METHODS)
@router.api_route("/rest/strmdrome/addFolder.view", methods=_METHODS)
def sd_add_folder(request: Request, name: str, path: str):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires Admin role")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO folders (name, path) VALUES (?, ?)", (name, path))
        conn.commit()
    except Exception as ex:
        conn.close()
        return err(0, str(ex))
    conn.close()
    return ok()

@router.api_route("/rest/strmdrome/deleteFolder", methods=_METHODS)
@router.api_route("/rest/strmdrome/deleteFolder.view", methods=_METHODS)
def sd_delete_folder(request: Request, id: int):
    user, e = require_user(request)
    if e: return e
    if not user["is_admin"]: return err(50, "Requires Admin role")
    conn = get_connection()
    conn.execute("DELETE FROM folders WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return ok()
