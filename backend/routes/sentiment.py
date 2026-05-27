"""
Iter 62 — Sentiment routes (macro forex headlines + LLM scoring).

Endpoints:
  GET  /api/sentiment/scores            — latest cached snapshot
  POST /api/sentiment/refresh           — force a fresh pull (admin / debug)
  GET  /api/sentiment/pair/{asset}      — derived directional bias for an asset
  GET  /api/sentiment/health            — loop status + last refresh age
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from sentiment_service import (
    get_latest_sentiment,
    refresh_sentiment,
    get_pair_sentiment_bias,
    sentiment_runs_col,
    SENTIMENT_FRESH_MINUTES,
    SENTIMENT_REFRESH_MINUTES,
    CURRENCIES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/scores")
async def sentiment_scores():
    """Latest cached sentiment snapshot."""
    latest = get_latest_sentiment()
    if not latest:
        return {"success": False, "error": "no_snapshot", "currencies": CURRENCIES}
    return {"success": True, **latest, "fresh_minutes": SENTIMENT_FRESH_MINUTES}


@router.post("/refresh")
async def sentiment_refresh(force: bool = True):
    """Force a fresh RSS + LLM scoring run. Returns the new snapshot."""
    try:
        snap = await refresh_sentiment(force=force)
        if snap.get("error"):
            raise HTTPException(status_code=502, detail=snap["error"])
        return {"success": True, **snap}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[sentiment] refresh failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pair/{asset}")
async def sentiment_pair(asset: str):
    """Directional bias for a single asset (e.g. EURUSD, EURUSD_OTC, XAUUSD)."""
    bias = get_pair_sentiment_bias(asset)
    if not bias:
        return {"success": False, "error": "no_bias_available", "asset": asset}
    return {"success": True, **bias}


@router.get("/health")
async def sentiment_health():
    """Loop status + last refresh age."""
    latest = get_latest_sentiment()
    last_run = sentiment_runs_col.find_one(sort=[("ts", -1)]) or {}
    last_run_iso = (
        last_run["ts"].isoformat() if isinstance(last_run.get("ts"), datetime) else None
    )
    age_min = None
    if latest and latest.get("ts"):
        try:
            ts = datetime.fromisoformat(latest["ts"].replace("Z", "+00:00"))
            age_min = round(
                (datetime.now(timezone.utc) - ts).total_seconds() / 60, 1
            )
        except Exception:
            age_min = None
    return {
        "success": True,
        "has_snapshot": bool(latest),
        "snapshot_age_minutes": age_min,
        "fresh_within_minutes": SENTIMENT_FRESH_MINUTES,
        "refresh_interval_minutes": SENTIMENT_REFRESH_MINUTES,
        "last_run_status": last_run.get("status"),
        "last_run_at": last_run_iso,
        "last_run_headline_count": last_run.get("headline_count"),
    }
