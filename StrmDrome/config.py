import os
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
MUSIC_DIR   = os.getenv("MUSIC_DIR",   "/music")       # read-only mount of .strm files
DATA_DIR    = os.getenv("DATA_DIR",    "/data")        # writable: db, catalog, covers, lrc, json
CATALOG_DIR = os.path.join(DATA_DIR, "catalog")        # normalized Artist/Album structure

# ── Server ─────────────────────────────────────────────────────────────────
HOST        = os.getenv("HOST", "0.0.0.0")
PORT        = int(os.getenv("PORT", "4533"))

# ── Admin credentials (created on first boot if DB is empty) ───────────────
ADMIN_USER  = os.getenv("ADMIN_USER",  "admin")
ADMIN_PASS  = os.getenv("ADMIN_PASS",  "admin")

# ── Scraping (optional keys to unlock extra sources) ──────────────────────
LASTFM_API_KEY      = os.getenv("LASTFM_API_KEY",  "")   # lastfm artist bios + similar
MUSICBRAINZ_APP     = os.getenv("MUSICBRAINZ_APP", "StrmDrome/2.0")
NETEASE_ENABLED     = os.getenv("NETEASE_ENABLED", "true").lower() == "true"

# ── Scanner behaviour ──────────────────────────────────────────────────────
SCAN_ON_STARTUP     = os.getenv("SCAN_ON_STARTUP",  "true").lower() == "true"
SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "24"))
SCRAPE_CONCURRENCY  = int(os.getenv("SCRAPE_CONCURRENCY", "4"))   # async scrape parallelism
