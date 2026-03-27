"""
Full production SQLite schema for StrmDrome v2.
Supports: multi-user, artists, albums, songs, playlists, scrobbles, annotations.
"""
import sqlite3
import os
import logging
import config

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(config.DATA_DIR, "strmdrome.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables and indexes. Idempotent (safe to call multiple times)."""
    conn = get_connection()
    c = conn.cursor()

    # ── Users ────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            username     TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin     BOOLEAN DEFAULT 0,
            email        TEXT DEFAULT '',
            created_at   TEXT NOT NULL,
            last_seen    TEXT,
            max_bitrate  INTEGER DEFAULT 0,
            settings     TEXT DEFAULT '{}'
        )
    """)

    # ── Artists ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            sort_name    TEXT,
            mbz_id       TEXT,
            biography    TEXT,
            image_path   TEXT,
            last_scraped TEXT,
            album_count  INTEGER DEFAULT 0
        )
    """)

    # ── Albums ───────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            id           TEXT PRIMARY KEY,
            artist_id    TEXT REFERENCES artists(id),
            title        TEXT NOT NULL,
            sort_title   TEXT,
            year         INTEGER DEFAULT 0,
            genre        TEXT DEFAULT '',
            cover_path   TEXT,
            mbz_id       TEXT,
            disc_count   INTEGER DEFAULT 1,
            song_count   INTEGER DEFAULT 0,
            duration     INTEGER DEFAULT 0,
            last_scraped TEXT
        )
    """)

    # ── Songs ────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id           TEXT PRIMARY KEY,
            album_id     TEXT REFERENCES albums(id),
            artist_id    TEXT REFERENCES artists(id),
            title        TEXT NOT NULL,
            sort_title   TEXT,
            track_num    INTEGER DEFAULT 0,
            disc_num     INTEGER DEFAULT 1,
            duration     INTEGER DEFAULT 0,
            bit_rate     INTEGER DEFAULT 0,
            year         INTEGER DEFAULT 0,
            genre        TEXT DEFAULT '',
            path         TEXT NOT NULL,       -- canonical path to .strm in /music
            cover_path   TEXT,
            lyrics_synced TEXT,               -- LRC content
            lyrics_plain TEXT,
            last_scraped TEXT,
            updated_at   TEXT
        )
    """)

    # ── Annotations (per-user: star, rating, play count) ────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            user_id      TEXT REFERENCES users(id),
            item_id      TEXT NOT NULL,
            item_type    TEXT NOT NULL,       -- 'song', 'album', 'artist'
            starred      BOOLEAN DEFAULT 0,
            starred_at   TEXT,
            rating       INTEGER DEFAULT 0,
            play_count   INTEGER DEFAULT 0,
            last_played  TEXT,
            PRIMARY KEY (user_id, item_id, item_type)
        )
    """)

    # ── Playlists ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id           TEXT PRIMARY KEY,
            owner_id     TEXT REFERENCES users(id),
            name         TEXT NOT NULL,
            comment      TEXT DEFAULT '',
            public       BOOLEAN DEFAULT 0,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            playlist_id  TEXT REFERENCES playlists(id) ON DELETE CASCADE,
            song_id      TEXT REFERENCES songs(id)      ON DELETE CASCADE,
            position     INTEGER NOT NULL,
            PRIMARY KEY (playlist_id, position)
        )
    """)

    # ── Scrobble log ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS scrobble_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT REFERENCES users(id),
            song_id      TEXT REFERENCES songs(id),
            played_at    TEXT NOT NULL
        )
    """)

    # ── Indexes ──────────────────────────────────────────────────────────────
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_albums_artist   ON albums(artist_id)",
        "CREATE INDEX IF NOT EXISTS idx_songs_album     ON songs(album_id)",
        "CREATE INDEX IF NOT EXISTS idx_songs_artist    ON songs(artist_id)",
        "CREATE INDEX IF NOT EXISTS idx_songs_title_fts ON songs(title COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_artists_name    ON artists(name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_albums_title    ON albums(title COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_ann_user        ON annotations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_scrobble_user   ON scrobble_log(user_id, played_at)",
    ]
    for sql in indexes:
        c.execute(sql)

    conn.commit()
    conn.close()
    logger.info("Database initialized.")
