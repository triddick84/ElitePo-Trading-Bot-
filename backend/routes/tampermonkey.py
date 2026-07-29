"""
Tampermonkey userscript integration endpoints.

These are the endpoints called by the compiled `pocket-option-auto-trader.user.js`
bundle (v8.122.0+) that were not covered by the other modular routers:

- GET  /api/tampermonkey/script  → serves the compiled userscript for @updateURL
                                    / @downloadURL auto-updates.
- GET  /api/settings/chart       → returns the user's current chart type /
                                    timeframe so the TM panel can render the
                                    right chart-mode indicator.
- POST /api/diag/ws-frames       → sink for TM WS frame diagnostics (fire-and-
                                    forget, capped so we don't blow up Mongo).

Kept intentionally lightweight — no heavy dependencies, no ML imports.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Mongo bootstrap — matches the pattern in the other route modules so we can
# read/write persisted settings without touching server.py globals.
# ---------------------------------------------------------------------------
_client: AsyncIOMotorClient | None = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).parent.parent / ".env")
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    return _db


# ---------------------------------------------------------------------------
# GET /api/tampermonkey/script  →  compiled userscript
# ---------------------------------------------------------------------------
# The compiled bundle lives in /app/frontend/public/ (served both by CRA in dev
# and copied into the static build in prod). We serve it here so Tampermonkey
# can honour @updateURL/@downloadURL without exposing an unversioned public path.

USERSCRIPT_PATHS = [
    Path("/app/frontend/public/pocket-option-auto-trader.user.js"),
    Path("/app/tampermonkey-src/dist/pocket-option-auto-trader.user.js"),
]


@router.get("/tampermonkey/script")
async def get_tampermonkey_script():
    """Serve the compiled userscript for Tampermonkey auto-updates."""
    for p in USERSCRIPT_PATHS:
        if p.exists():
            return FileResponse(
                p,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Content-Disposition": (
                        'inline; filename="pocket-option-auto-trader.user.js"'
                    ),
                },
            )
    raise HTTPException(
        status_code=404,
        detail="Compiled userscript not found on disk — rebuild TM bundle.",
    )


# ---------------------------------------------------------------------------
# GET /api/settings/chart  →  user's current chart type + timeframe
# ---------------------------------------------------------------------------
# The TM panel polls this on init to sync its "chart-mode" indicator with what
# the user has set in the React dashboard. Falls back to sensible defaults if
# no config doc exists yet.

VALID_CHART_TYPES = {
    "japanese_candles",
    "heikin_ashi",
    "line",
    "bar",
    "area",
}


@router.get("/settings/chart")
async def get_chart_settings(user_id: str = "default_user"):
    """Return current chart type + timeframe for the panel indicator."""
    try:
        db = _get_db()
        cfg = await db.trading_configurations.find_one({"user_id": user_id})

        chart_type = "japanese_candles"
        chart_timeframe = "30s"
        if cfg:
            ct = cfg.get("chart_type")
            if isinstance(ct, str) and ct in VALID_CHART_TYPES:
                chart_type = ct
            tf = cfg.get("chart_timeframe")
            if isinstance(tf, str) and tf:
                chart_timeframe = tf

        return {
            "success": True,
            "chart_type": chart_type,
            "chart_timeframe": chart_timeframe,
        }
    except Exception as exc:
        logger.error("[settings/chart] read failed: %s", exc)
        # Return defaults so the TM panel keeps working even on DB error
        return {
            "success": True,
            "chart_type": "japanese_candles",
            "chart_timeframe": "30s",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# POST /api/diag/ws-frames  →  Websocket frame diagnostics sink
# ---------------------------------------------------------------------------
# The TM script batches PO websocket frames and posts them here in chunks of
# ~40 at a time. We persist a small rolling buffer for offline debugging and
# capp at 2 000 rows/day so it can't blow up Mongo.

_MAX_FRAMES_PER_REQUEST = 200
_ROLLING_LIMIT = 2_000


@router.post("/diag/ws-frames")
async def diag_ws_frames(payload: dict = Body(default={})):
    """Fire-and-forget sink for TM WS frame batches."""
    try:
        frames = payload.get("frames") or []
        if not isinstance(frames, list):
            frames = []
        # Cap incoming batch so a bad client can't nuke us
        frames = frames[:_MAX_FRAMES_PER_REQUEST]
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}

        db = _get_db()
        doc = {
            "frames": frames,
            "meta": meta,
            "count": len(frames),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await db.tm_ws_frame_diagnostics.insert_one(doc)

        # Keep rolling buffer bounded
        try:
            total = await db.tm_ws_frame_diagnostics.count_documents({})
            if total > _ROLLING_LIMIT:
                extra = total - _ROLLING_LIMIT
                cursor = db.tm_ws_frame_diagnostics.find({}, {"_id": 1}).sort(
                    "ts", 1
                ).limit(extra)
                ids = [d["_id"] async for d in cursor]
                if ids:
                    await db.tm_ws_frame_diagnostics.delete_many(
                        {"_id": {"$in": ids}}
                    )
        except Exception:
            # Trimming errors must never poison the ack
            pass

        return {"success": True, "stored": len(frames)}
    except Exception as exc:
        logger.warning("[diag/ws-frames] store failed: %s", exc)
        return JSONResponse(
            status_code=200,
            content={"success": False, "error": str(exc)},
        )


@router.get("/diag/ws-frames")
async def diag_ws_frames_recent(limit: int = 20):
    """List recent WS frame batches — handy for offline debugging."""
    try:
        db = _get_db()
        limit = max(1, min(200, int(limit)))
        cursor = (
            db.tm_ws_frame_diagnostics.find({}, {"_id": 0, "frames": 0})
            .sort("ts", -1)
            .limit(limit)
        )
        rows = [d async for d in cursor]
        return {"success": True, "count": len(rows), "batches": rows}
    except Exception as exc:
        logger.warning("[diag/ws-frames] list failed: %s", exc)
        return {"success": False, "error": str(exc), "batches": []}
