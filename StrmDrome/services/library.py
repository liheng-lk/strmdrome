"""
services/library.py
All read/write operations on the music library database.
Used by all API endpoints.
"""
import uuid
import hashlib
from datetime import datetime, timezone
from db.database import get_connection


def _song_id(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()

def _artist_id(name: str) -> str:
    return hashlib.md5(f"artist:{name}".encode()).hexdigest()

def _album_id(artist_name: str, album_name: str) -> str:
    return hashlib.md5(f"album:{artist_name}:{album_name}".encode()).hexdigest()


# ── Artist ───────────────────────────────────────────────────────────────────

def upsert_artist(name: str) -> str:
    aid  = _artist_id(name)
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO artists (id, name, sort_name) VALUES (?,?,?)
    """, (aid, name, name.lstrip("The ").strip()))
    conn.commit(); conn.close()
    return aid


def get_artist(artist_id: str):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM artists WHERE id=?", (artist_id,)).fetchone()
    conn.close(); return row


def list_artists():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM artists ORDER BY sort_name COLLATE NOCASE").fetchall()
    conn.close(); return rows


def update_artist_album_count(artist_id: str):
    conn = get_connection()
    conn.execute(
        "UPDATE artists SET album_count=(SELECT COUNT(*) FROM albums WHERE artist_id=?) WHERE id=?",
        (artist_id, artist_id)
    )
    conn.commit(); conn.close()


# ── Album ────────────────────────────────────────────────────────────────────

def upsert_album(artist_id: str, artist_name: str, album_name: str, year: int = 0, genre: str = "", folder_id: int = None) -> str:
    alid = _album_id(artist_name, album_name)
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO albums (id, artist_id, title, sort_title, year, genre, folder_id)
        VALUES (?,?,?,?,?,?,?)
    """, (alid, artist_id, album_name, album_name, year, genre, folder_id))
    
    # Update folder_id if it was NULL but now known
    if folder_id:
        conn.execute("UPDATE albums SET folder_id=? WHERE id=? AND folder_id IS NULL", (folder_id, alid))
        
    conn.commit(); conn.close()
    return alid


def get_album(album_id: str):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM albums WHERE id=?", (album_id,)).fetchone()
    conn.close(); return row


def list_albums_by_artist(artist_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM albums WHERE artist_id=? ORDER BY year, title COLLATE NOCASE",
        (artist_id,)
    ).fetchall()
    conn.close(); return rows


def update_album_stats(album_id: str):
    conn = get_connection()
    conn.execute("""
        UPDATE albums SET
            song_count=(SELECT COUNT(*) FROM songs WHERE album_id=?),
            duration  =(SELECT COALESCE(SUM(duration),0) FROM songs WHERE album_id=?)
        WHERE id=?
    """, (album_id, album_id, album_id))
    conn.commit(); conn.close()


# ── Song ─────────────────────────────────────────────────────────────────────

def upsert_song(path: str, album_id: str, artist_id: str, title: str,
                track_num: int = 0, disc_num: int = 1, folder_id: int = None) -> str:
    sid  = _song_id(path)
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO songs
            (id, album_id, artist_id, title, sort_title, track_num, disc_num, path, updated_at, folder_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (sid, album_id, artist_id, title, title, track_num, disc_num, path, now, folder_id))
    
    if folder_id:
        conn.execute("UPDATE songs SET folder_id=? WHERE id=? AND folder_id IS NULL", (folder_id, sid))
        
    conn.commit(); conn.close()
    return sid


def get_song(song_id: str):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
    conn.close(); return row


def list_songs_by_album(album_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM songs WHERE album_id=? ORDER BY disc_num, track_num, title COLLATE NOCASE",
        (album_id,)
    ).fetchall()
    conn.close(); return rows


def list_all_songs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM songs ORDER BY title COLLATE NOCASE").fetchall()
    conn.close(); return rows


# ── Search ───────────────────────────────────────────────────────────────────

def search(query: str, artist_count=5, album_count=10, song_count=20, offset=0):
    """Fuzzy LIKE search across artists, albums, songs."""
    q    = f"%{query}%"
    conn = get_connection()
    artists = conn.execute(
        "SELECT * FROM artists WHERE name LIKE ? ORDER BY name LIMIT ? OFFSET ?",
        (q, artist_count, offset)
    ).fetchall()
    albums = conn.execute(
        "SELECT * FROM albums WHERE title LIKE ? ORDER BY title LIMIT ? OFFSET ?",
        (q, album_count, offset)
    ).fetchall()
    songs = conn.execute(
        "SELECT * FROM songs WHERE title LIKE ? ORDER BY title LIMIT ? OFFSET ?",
        (q, song_count, offset)
    ).fetchall()
    conn.close()
    return artists, albums, songs


# ── Genre ────────────────────────────────────────────────────────────────────

def list_genres():
    conn = get_connection()
    rows = conn.execute("""
        SELECT genre, COUNT(*) as song_count, COUNT(DISTINCT album_id) as album_count
        FROM songs WHERE genre != '' GROUP BY genre ORDER BY genre
    """).fetchall()
    conn.close(); return rows


# ── Album lists ──────────────────────────────────────────────────────────────

def get_album_list(list_type: str, size=10, offset=0, from_year=None, to_year=None,
                   genre=None, user_id=None, music_folder_id=None):
    conn = get_connection()
    
    folder_filter = " AND folder_id=? " if music_folder_id else ""
    folder_params = (music_folder_id,) if music_folder_id else ()
    
    if list_type == "random":
        rows = conn.execute(
            f"SELECT * FROM albums WHERE 1=1 {folder_filter} ORDER BY RANDOM() LIMIT ? OFFSET ?", 
            (*folder_params, size, offset)
        ).fetchall()
    elif list_type == "newest":
        rows = conn.execute(
            f"SELECT * FROM albums WHERE 1=1 {folder_filter} ORDER BY rowid DESC LIMIT ? OFFSET ?", 
            (*folder_params, size, offset)
        ).fetchall()
    elif list_type == "recent":
        # Albums with recently played songs via scrobble_log
        rows = conn.execute(f"""
            SELECT DISTINCT a.* FROM albums a
            JOIN songs s ON s.album_id=a.id
            JOIN scrobble_log sl ON sl.song_id=s.id AND sl.user_id=?
            WHERE 1=1 {folder_filter.replace('folder_id', 'a.folder_id')}
            ORDER BY sl.played_at DESC LIMIT ? OFFSET ?
        """, (user_id, *folder_params, size, offset)).fetchall()
    elif list_type == "frequent":
        rows = conn.execute(f"""
            SELECT a.*, COUNT(sl.id) AS play_count FROM albums a
            JOIN songs s ON s.album_id=a.id
            JOIN scrobble_log sl ON sl.song_id=s.id AND sl.user_id=?
            WHERE 1=1 {folder_filter.replace('folder_id', 'a.folder_id')}
            GROUP BY a.id ORDER BY play_count DESC LIMIT ? OFFSET ?
        """, (user_id, *folder_params, size, offset)).fetchall()
    elif list_type == "starred":
        rows = conn.execute(f"""
            SELECT a.* FROM albums a
            JOIN annotations ann ON ann.item_id=a.id AND ann.item_type='album'
                AND ann.user_id=? AND ann.starred=1
            WHERE 1=1 {folder_filter.replace('folder_id', 'a.folder_id')}
            ORDER BY ann.starred_at DESC LIMIT ? OFFSET ?
        """, (user_id, *folder_params, size, offset)).fetchall()
    elif list_type == "byYear" and from_year is not None:
        rows = conn.execute(
            f"SELECT * FROM albums WHERE year BETWEEN ? AND ? {folder_filter} ORDER BY year LIMIT ? OFFSET ?",
            (from_year, to_year or 9999, *folder_params, size, offset)
        ).fetchall()
    elif list_type == "byGenre" and genre:
        rows = conn.execute(
            f"SELECT * FROM albums WHERE genre=? {folder_filter} ORDER BY title LIMIT ? OFFSET ?",
            (genre, *folder_params, size, offset)
        ).fetchall()
    else:  # alphabeticalByName / alphabeticalByArtist
        rows = conn.execute(
            f"SELECT * FROM albums WHERE 1=1 {folder_filter} ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (*folder_params, size, offset)
        ).fetchall()
    conn.close(); return rows


# ── Annotations ──────────────────────────────────────────────────────────────

def _ann_upsert(user_id: str, item_id: str, item_type: str, **kwargs):
    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM annotations WHERE user_id=? AND item_id=? AND item_type=?",
        (user_id, item_id, item_type)
    ).fetchone()
    if existing:
        set_clause = ", ".join(f"{k}=?" for k in kwargs)
        conn.execute(
            f"UPDATE annotations SET {set_clause} WHERE user_id=? AND item_id=? AND item_type=?",
            (*kwargs.values(), user_id, item_id, item_type)
        )
    else:
        cols = ", ".join(["user_id","item_id","item_type"] + list(kwargs.keys()))
        vals = "?, " * (len(kwargs) + 3)
        conn.execute(
            f"INSERT INTO annotations ({cols}) VALUES ({vals.rstrip(', ')})",
            (user_id, item_id, item_type, *kwargs.values())
        )
    conn.commit(); conn.close()


def star(user_id: str, item_ids: list[str], item_type: str = "song"):
    now = datetime.now(timezone.utc).isoformat()
    for iid in item_ids:
        _ann_upsert(user_id, iid, item_type, starred=1, starred_at=now)


def unstar(user_id: str, item_ids: list[str], item_type: str = "song"):
    for iid in item_ids:
        _ann_upsert(user_id, iid, item_type, starred=0, starred_at=None)


def set_rating(user_id: str, item_id: str, rating: int):
    _ann_upsert(user_id, item_id, "song", rating=rating)


def get_annotation(user_id: str, item_id: str, item_type: str = "song"):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM annotations WHERE user_id=? AND item_id=? AND item_type=?",
        (user_id, item_id, item_type)
    ).fetchone()
    conn.close(); return row


def record_scrobble(user_id: str, song_id: str):
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO scrobble_log (user_id, song_id, played_at) VALUES (?,?,?)",
        (user_id, song_id, now)
    )
    _ann_upsert(user_id, song_id, "song", play_count=conn.execute(
        "SELECT COUNT(*) FROM scrobble_log WHERE user_id=? AND song_id=?",
        (user_id, song_id)
    ).fetchone()[0], last_played=now)
    conn.commit(); conn.close()


# ── Playlists ────────────────────────────────────────────────────────────────

def list_playlists(user_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM playlists WHERE owner_id=? OR public=1 ORDER BY name", (user_id,)
    ).fetchall()
    conn.close(); return rows


def get_playlist(playlist_id: str):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM playlists WHERE id=?", (playlist_id,)).fetchone()
    conn.close(); return row


def get_playlist_songs(playlist_id: str):
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.* FROM songs s
        JOIN playlist_tracks pt ON pt.song_id=s.id AND pt.playlist_id=?
        ORDER BY pt.position
    """, (playlist_id,)).fetchall()
    conn.close(); return rows


def create_playlist(owner_id: str, name: str, song_ids: list[str], public: bool = False) -> str:
    pid  = str(uuid.uuid4())
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO playlists (id,owner_id,name,public,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (pid, owner_id, name, public, now, now)
    )
    for i, sid in enumerate(song_ids):
        conn.execute(
            "INSERT OR IGNORE INTO playlist_tracks (playlist_id,song_id,position) VALUES (?,?,?)",
            (pid, sid, i)
        )
    conn.commit(); conn.close()
    return pid


def update_playlist(playlist_id: str, name: str = None, song_ids: list[str] = None,
                    public: bool = None):
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    if name is not None:
        conn.execute("UPDATE playlists SET name=?,updated_at=? WHERE id=?", (name, now, playlist_id))
    if public is not None:
        conn.execute("UPDATE playlists SET public=?,updated_at=? WHERE id=?", (public, now, playlist_id))
    if song_ids is not None:
        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
        for i, sid in enumerate(song_ids):
            conn.execute(
                "INSERT OR IGNORE INTO playlist_tracks VALUES (?,?,?)", (playlist_id, sid, i)
            )
        conn.execute("UPDATE playlists SET updated_at=? WHERE id=?", (now, playlist_id))
    conn.commit(); conn.close()


def delete_playlist(playlist_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
    conn.commit(); conn.close()
