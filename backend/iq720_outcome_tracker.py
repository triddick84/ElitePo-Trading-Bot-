"""
IQ-720 Outcome Feedback Loop — Iter 59 (May 21, 2026)
======================================================

Problem: IQ-720 ensemble is 100% rule-based (hardcoded weights for RSI,
MACD, Stochastic, EMA alignment, BB position, KC position, ADX trend
strength, candlestick patterns). It cannot "go up in accuracy" because
nothing trains it. We need a feedback loop.

Solution: every IQ-720 signal logs its `confirmations` list. When the
matching Tampermonkey trade outcome lands (in `tm_trade_reports`), the
matcher associates the W/L with each confirmation that contributed. Over
a rolling 7-day window we compute per-confirmation win-rates and persist
them to `iq720_confirmation_stats`. At signal-generation time, the engine
scales each sub-strategy score by `(win_rate / 0.50)²`:

    win_rate = 0.50 → multiplier 1.00× (neutral)
    win_rate = 0.65 → multiplier 1.69× (boost real winners)
    win_rate = 0.35 → multiplier 0.49× (downweight reliable losers)
    win_rate = 0.75 → multiplier 2.25× (capped at MAX_MULTIPLIER)

Bounded between MIN_MULTIPLIER (0.20×) and MAX_MULTIPLIER (2.50×) so a
single noisy week can't tank or runaway any indicator.

Public API:
    log_iq720_signal(signal, symbol)        - call at signal-gen time
    refresh_confirmation_stats()            - background, called by scheduler
    get_confirmation_multiplier(name)       - cheap, used by signal engine
    get_all_stats()                         - for UI display
    match_trade_outcomes()                  - one-shot matcher (idempotent)
"""
from __future__ import annotations
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

SIGNAL_LOG_COLL = "iq720_signal_log"
STATS_COLL = "iq720_confirmation_stats"

# Tunables
MIN_TRADES_PER_CONFIRMATION = 8       # need 8+ matched trades before adapting
MIN_MULTIPLIER = 0.20
MAX_MULTIPLIER = 2.50
ROLLING_WINDOW_DAYS = 7
MATCH_WINDOW_SECONDS = 90             # signal ↔ trade timestamp tolerance
STATS_REFRESH_TTL_SECONDS = 300       # in-memory cache TTL

_MULTIPLIER_CACHE: Dict[str, float] = {}
_STATS_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LOADED_AT: Optional[datetime] = None


def _get_db_async():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _get_db_sync():
    return MongoClient(MONGO_URL)[DB_NAME]


# ----------------------------------------------------------------------------
# Signal logging (called at signal generation time)
# ----------------------------------------------------------------------------

def log_iq720_signal(signal: Dict[str, Any], symbol: str) -> None:
    """
    Persist a fresh IQ-720 signal so it can be retroactively matched to a
    trade outcome. Synchronous + bounded — uses pymongo and returns fast.
    Failure mode: swallowed (we don't want signal generation to fail because
    of a log write).
    """
    try:
        confirmations = signal.get("confirmations", []) or []
        if not confirmations:
            return
        doc = {
            "_logged_at": datetime.now(timezone.utc),
            "symbol": symbol,
            "asset_normalized": symbol,
            "direction": signal.get("direction"),
            "confidence": signal.get("confidence"),
            "raw_confidence": signal.get("raw_confidence"),
            "confirmations": list(confirmations),
            "market_regime": signal.get("market_regime"),
            "session": signal.get("session"),
            "call_score": signal.get("call_score"),
            "put_score": signal.get("put_score"),
            "matched": False,
            "outcome": None,
        }
        _get_db_sync()[SIGNAL_LOG_COLL].insert_one(doc)
    except Exception as e:
        logger.debug(f"[iq720] signal-log write failed (non-fatal): {e}")


# ----------------------------------------------------------------------------
# Trade-outcome matcher (background — called periodically)
# ----------------------------------------------------------------------------

async def match_trade_outcomes(lookback_hours: int = 24) -> Dict[str, Any]:
    """
    Walk recent IQ-720 signals that haven't been matched yet. For each, find
    the closest `tm_trade_reports` doc by (symbol, timestamp) and tag the
    signal with the W/L outcome. Idempotent — already-matched signals are
    skipped.
    """
    db = _get_db_async()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    sig_coll = db[SIGNAL_LOG_COLL]
    trade_coll = db["tm_trade_reports"]

    unmatched = await sig_coll.find(
        {"matched": False, "_logged_at": {"$gte": cutoff}},
        projection={"_id": 1, "symbol": 1, "direction": 1, "_logged_at": 1},
    ).to_list(length=2000)

    matched_count = 0
    skipped_count = 0
    for sig in unmatched:
        sym = sig.get("symbol")
        sig_ts = sig.get("_logged_at")
        if not sym or not sig_ts:
            continue
        # Look in a ±MATCH_WINDOW_SECONDS window
        win_start = sig_ts - timedelta(seconds=MATCH_WINDOW_SECONDS)
        win_end = sig_ts + timedelta(seconds=MATCH_WINDOW_SECONDS)
        trade = await trade_coll.find_one(
            {
                "$and": [
                    {"$or": [{"asset_normalized": sym}, {"asset": sym}]},
                    {"outcome": {"$in": ["WIN", "LOSS", "win", "loss"]}},
                    {"server_received_at": {
                        "$gte": win_start.isoformat(),
                        "$lte": win_end.isoformat(),
                    }},
                ]
            },
            projection={"_id": 0, "outcome": 1, "direction": 1, "server_received_at": 1},
        )
        if not trade:
            skipped_count += 1
            continue
        outcome = (trade.get("outcome") or "").upper()
        await sig_coll.update_one(
            {"_id": sig["_id"]},
            {"$set": {
                "matched": True,
                "outcome": outcome,
                "matched_at": datetime.now(timezone.utc),
                "matched_trade_ts": trade.get("server_received_at"),
            }},
        )
        matched_count += 1

    return {
        "matched": matched_count,
        "skipped": skipped_count,
        "checked": len(unmatched),
    }


# ----------------------------------------------------------------------------
# Per-confirmation stats aggregation (rolling 7-day window)
# ----------------------------------------------------------------------------

async def refresh_confirmation_stats() -> Dict[str, Any]:
    """
    Aggregate matched signals over the last `ROLLING_WINDOW_DAYS` and compute
    per-confirmation win-rates. Each confirmation contributes its full vote
    to whichever direction the signal went; the W/L is binary per signal.

    A confirmation that appears on 10 winning CALL signals + 5 losing CALL
    signals has win_rate = 10/15 = 0.667. Two-way attribution: if a signal
    fires CALL with [RSI_OVERSOLD, MACD_BULLISH] and wins, both tags get +1
    win count.
    """
    db = _get_db_async()
    cutoff = datetime.now(timezone.utc) - timedelta(days=ROLLING_WINDOW_DAYS)
    cur = db[SIGNAL_LOG_COLL].find(
        {"matched": True, "_logged_at": {"$gte": cutoff}},
        projection={"_id": 0, "confirmations": 1, "outcome": 1, "direction": 1},
    )
    docs = await cur.to_list(length=10000)

    # Aggregate
    agg: Dict[str, Dict[str, int]] = {}
    for d in docs:
        outcome = (d.get("outcome") or "").upper()
        if outcome not in ("WIN", "LOSS"):
            continue
        for c in (d.get("confirmations") or []):
            if not isinstance(c, str):
                continue
            slot = agg.setdefault(c, {"wins": 0, "losses": 0, "total": 0})
            slot["total"] += 1
            if outcome == "WIN":
                slot["wins"] += 1
            else:
                slot["losses"] += 1

    # Compute per-confirmation multipliers
    now = datetime.now(timezone.utc)
    out_rows = []
    for name, s in agg.items():
        wr = s["wins"] / s["total"] if s["total"] > 0 else 0.5
        if s["total"] < MIN_TRADES_PER_CONFIRMATION:
            mult = 1.0   # not enough data — neutral
            adapted = False
        else:
            raw = (wr / 0.50) ** 2
            mult = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, raw))
            adapted = True
        out_rows.append({
            "name": name,
            "wins": s["wins"],
            "losses": s["losses"],
            "total": s["total"],
            "win_rate": round(wr, 4),
            "multiplier": round(mult, 3),
            "adapted": adapted,
            "computed_at": now,
        })

    # Persist as one-row-per-confirmation upserts
    stats_coll = db[STATS_COLL]
    for row in out_rows:
        await stats_coll.update_one(
            {"name": row["name"]},
            {"$set": row},
            upsert=True,
        )

    await _load_cache_from_db()
    return {
        "success": True,
        "confirmations_evaluated": len(out_rows),
        "rows": out_rows,
        "window_days": ROLLING_WINDOW_DAYS,
    }


# ----------------------------------------------------------------------------
# Cache + accessors (hot-path)
# ----------------------------------------------------------------------------

async def _load_cache_from_db() -> None:
    global _MULTIPLIER_CACHE, _STATS_CACHE, _CACHE_LOADED_AT
    try:
        db = _get_db_async()
        cur = db[STATS_COLL].find({}, projection={"_id": 0})
        rows = await cur.to_list(length=200)
        _MULTIPLIER_CACHE = {r["name"]: float(r.get("multiplier", 1.0)) for r in rows}
        _STATS_CACHE = {r["name"]: r for r in rows}
        _CACHE_LOADED_AT = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning(f"[iq720] stats cache reload failed: {e}")
        _CACHE_LOADED_AT = datetime.now(timezone.utc)


async def refresh_cache_if_stale() -> None:
    global _CACHE_LOADED_AT
    now = datetime.now(timezone.utc)
    if _CACHE_LOADED_AT is None or (now - _CACHE_LOADED_AT).total_seconds() > STATS_REFRESH_TTL_SECONDS:
        await _load_cache_from_db()


def get_confirmation_multiplier(name: str) -> float:
    """Cheap accessor — used by the signal engine on every vote. Returns 1.0
    if the confirmation has no rolling stats yet (cold start)."""
    return float(_MULTIPLIER_CACHE.get(name, 1.0))


def get_all_stats() -> Dict[str, Any]:
    return {
        "stats": list(_STATS_CACHE.values()),
        "multipliers": dict(_MULTIPLIER_CACHE),
        "loaded_at": _CACHE_LOADED_AT.isoformat() if _CACHE_LOADED_AT else None,
        "count": len(_MULTIPLIER_CACHE),
    }


# Sync-friendly initial cache load — invoked from server.py startup if desired
def warm_cache_sync() -> None:
    """Block-load the cache from MongoDB. Safe to call from sync startup."""
    global _MULTIPLIER_CACHE, _STATS_CACHE, _CACHE_LOADED_AT
    try:
        db = _get_db_sync()
        rows = list(db[STATS_COLL].find({}, projection={"_id": 0}))
        _MULTIPLIER_CACHE = {r["name"]: float(r.get("multiplier", 1.0)) for r in rows}
        _STATS_CACHE = {r["name"]: r for r in rows}
        _CACHE_LOADED_AT = datetime.now(timezone.utc)
        logger.info(f"[iq720] warm cache loaded — {len(rows)} confirmations cached")
    except Exception as e:
        logger.warning(f"[iq720] warm cache failed: {e}")
