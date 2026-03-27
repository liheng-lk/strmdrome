"""
services/alist.py
Client for natively integrating with OpenList/AList V3 APIs.
"""
import httpx
import logging
from typing import Iterator

logger = logging.getLogger(__name__)

# Valid music extensions to index from AList
VALID_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac', '.ape', '.wma', '.alac'}


class AListClient:
    def __init__(self, folder_id: int, url: str, username: str, password: str, token: str = None):
        self.folder_id = folder_id
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.token = token
        self.client = httpx.Client(timeout=30.0)

    def _headers(self):
        return {"Authorization": self.token} if self.token else {}

    def login(self) -> bool:
        if not self.username or not self.password:
            # Guest mode
            return True
            
        try:
            r = self.client.post(f"{self.url}/api/auth/login", json={
                "username": self.username,
                "password": self.password
            })
            data = r.json()
            if data.get("code") == 200:
                self.token = data["data"]["token"]
                
                # Update DB with new token
                from db.database import get_connection
                conn = get_connection()
                conn.execute("UPDATE folders SET alist_token=? WHERE id=?", (self.token, self.folder_id))
                conn.commit()
                conn.close()
                return True
            else:
                logger.error(f"AList login failed: {data.get('message')}")
                return False
        except Exception as e:
            logger.error(f"AList login exception: {e}")
            return False

    def walk(self, dir_path: str) -> Iterator[str]:
        """Yields absolute ALIST paths to all valid music files recursively."""
        if not dir_path.startswith('/'):
            dir_path = '/' + dir_path
            
        payload = {"path": dir_path, "password": "", "page": 1, "per_page": 0, "refresh": False}
        
        try:
            r = self.client.post(f"{self.url}/api/fs/list", json=payload, headers=self._headers())
            data = r.json()
            
            if data.get("code") == 401: # Unauthorized
                logger.info("AList token expired, re-authenticating...")
                if self.login():
                    r = self.client.post(f"{self.url}/api/fs/list", json=payload, headers=self._headers())
                    data = r.json()
                else:
                    return
            
            if data.get("code") != 200:
                logger.error(f"AList list failed for {dir_path}: {data.get('message')}")
                return

            content = data.get("data", {}).get("content") or []
            for item in content:
                name = item["name"]
                item_path = f"{dir_path}/{name}" if dir_path != "/" else f"/{name}"
                
                if item["is_dir"]:
                    yield from self.walk(item_path)
                else:
                    ext = "." + name.split('.')[-1].lower() if '.' in name else ""
                    if ext in VALID_EXTS:
                        yield item_path

        except Exception as e:
            logger.error(f"AList walk exception at {dir_path}: {e}")

    def get_stream_url(self, file_path: str) -> str | None:
        """Fetch the direct 302 streaming URL for a specific file."""
        if not file_path.startswith('/'):
            file_path = '/' + file_path
            
        payload = {"path": file_path, "password": ""}
        try:
            r = self.client.post(f"{self.url}/api/fs/get", json=payload, headers=self._headers())
            data = r.json()
            
            if data.get("code") == 401:
                if self.login():
                    r = self.client.post(f"{self.url}/api/fs/get", json=payload, headers=self._headers())
                    data = r.json()
                    
            if data.get("code") == 200:
                return data["data"]["raw_url"]
                
            logger.error(f"AList get failed for {file_path}: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"AList get exception for {file_path}: {e}")
            return None
