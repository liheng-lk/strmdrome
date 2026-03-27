"""
main.py — StrmDrome v2 Application Entry Point
"""
import logging
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import config
from db.database import init_db
from services.auth import ensure_admin_exists

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("StrmDrome v2 starting up…")
    import os
    os.makedirs(config.CATALOG_DIR, exist_ok=True)
    init_db()
    ensure_admin_exists()

    if config.SCAN_ON_STARTUP:
        from services.scanner import scan_library
        t = threading.Thread(target=scan_library, daemon=True, name="LibraryScanner")
        t.start()

    # ── Background periodic rescan via APScheduler ────────────────────────────
    if config.SCAN_INTERVAL_HOURS > 0:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.scanner import scan_library
        scheduler = BackgroundScheduler()
        scheduler.add_job(scan_library, "interval", hours=config.SCAN_INTERVAL_HOURS)
        scheduler.start()
        logger.info(f"Periodic rescan scheduled every {config.SCAN_INTERVAL_HOURS}h")

    yield  # App is running
    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("StrmDrome shutting down.")


app = FastAPI(
    title="StrmDrome",
    version="2.0.0",
    description="Professional-grade Navidrome-compatible STRM music server",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all Subsonic API routes
from api.router import router as api_router
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    return {"service": "StrmDrome", "version": "2.0.0",
            "docs": "/docs", "subsonic": "/rest/ping"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )
