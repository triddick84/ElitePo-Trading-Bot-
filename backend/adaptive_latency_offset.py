"""
Adaptive Latency Offset Service — Iter 91.

Purpose
-------
The TM panel currently fires trades with a single GLOBAL offset
`latencyOffsetSec = +3.5s` — the click lands 3.5 s AFTER the recommended
target time to compensate for network RTT + Pocket Option DOM click lag.

Reality: RTT + DOM lag varies by asset (busy pairs = slower DOM), by user
network, and drifts over the trading session. A one-size-fits-all offset
means we're consistently early on fast pairs and late on slow ones.

This service reads the existing `signal_latency_log_client` collection
(populated by `POST /api/signals/latency-report`) and computes a per-asset
rolling-median recommended offset in seconds. The TM script (or the
Latency Dashboard) can then adopt it.

Design
------
* Read-only. Doesn't need a background loop — computed on-demand.
* Rolling window = last 50 samples per asset (env-tunable).
* Statistic = median(network_rtt_ms + dom_click_lag_ms), rounded to 0.5 s.
* Fallback: `DEFAULT_GLOBAL_OFFSET_SEC` (matches TM state.latencyOffsetSec).
* Clamped to [-5, +15] s to guard against malformed reports.
* Caches per-asset for 30 s to avoid hammering Mongo.
"""

from __future__ import annotations

import logging
import os
import statistics
import time
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


CLIENT_LATENCY_COLL = "signal_latency_log_client"
DEFAULT_GLOBAL_OFFSET_SEC = 3.5
SAMPLE_WINDOW = int(os.environ.get("ADAPTIVE_OFFSET_SAMPLES", "50"))
MIN_SAMPLES_FOR_RECOMMENDATION = int(os.environ.get("ADAPTIVE_OFFSET_MIN_SAMPLES", "8"))
MIN_OFFSET_SEC = float(os.environ.get("ADAPTIVE_OFFSET_MIN", "-5.0"))
MAX_OFFSET_SEC = float(os.environ.get("ADAPTIVE_OFFSET_MAX", "15.0"))
CACHE_TTL_SEC = float(os.environ.get("ADAPTIVE_OFFSET_CACHE_TTL", "30.0"))


# Per-asset cache: {asset -> (result_dict, monotonic_expiry)}
_cache: Dict[str, tuple] = {}


def _norm_asset(asset: Optional[str]) -> str:
    if not asset:
        return ""
    a = str(asset).strip().upper()
    if a.endswith("OTC") and not a.endswith("_OTC"):
        a = a[:-3] + "_OTC"
    return a


def _clamp(v: float) -> float:
    return max(MIN_OFFSET_SEC, min(MAX_OFFSET_SEC, v))


def _round_half(v: float) -> float:
    """Match the TM slider's 0.5 s granularity."""
    return round(v * 2.0) / 2.0


async def compute_asset_offset(
    db: AsyncIOMotorDatabase, asset: str, window: int = SAMPLE_WINDOW
) -> Dict[str, Any]:
    """
    Compute the recommended offset for a single asset from its last `window`
    client-latency samples. Returns a dict shaped like:

    {
      "asset": "EURUSD_OTC",
      "recommended_offset_sec": 4.0,   # rounded half-second, clamped
      "sample_count": 42,
      "median_total_ms": 3820,
      "median_network_rtt_ms": 180,
      "median_dom_click_lag_ms": 3640,
      "using_default": false,          # true when < MIN_SAMPLES_FOR_RECOMMENDATION
      "cache_hit": false,
    }
    """
    key = _norm_asset(asset)
    if not key:
        return {
            "asset": "",
            "recommended_offset_sec": DEFAULT_GLOBAL_OFFSET_SEC,
            "sample_count": 0,
            "using_default": True,
            "cache_hit": False,
        }

    # Serve from cache when fresh
    cached = _cache.get(key)
    now = time.monotonic()
    if cached and cached[1] > now:
        return {**cached[0], "cache_hit": True}

    coll = db[CLIENT_LATENCY_COLL]
    # Match both the OTC-suffixed and stripped variants so signals generated
    # with `asset="AUDUSD"` still find samples logged as `"AUDUSD_OTC"` and
    # vice-versa. Dedupe with a set.
    stripped = key.replace("_OTC", "")
    variants = list({key, stripped, f"{stripped}_OTC"})
    cursor = coll.find(
        {"asset": {"$in": variants}},
        {"_id": 0, "network_rtt_ms": 1, "dom_click_lag_ms": 1},
    ).sort("_logged_at", -1).limit(window)
    docs = await cursor.to_list(length=window)

    if len(docs) < MIN_SAMPLES_FOR_RECOMMENDATION:
        result = {
            "asset": key,
            "recommended_offset_sec": DEFAULT_GLOBAL_OFFSET_SEC,
            "sample_count": len(docs),
            "median_total_ms": None,
            "median_network_rtt_ms": None,
            "median_dom_click_lag_ms": None,
            "using_default": True,
        }
        _cache[key] = (result, now + CACHE_TTL_SEC)
        return {**result, "cache_hit": False}

    rtts = [d.get("network_rtt_ms") for d in docs
            if isinstance(d.get("network_rtt_ms"), (int, float))]
    lags = [d.get("dom_click_lag_ms") for d in docs
            if isinstance(d.get("dom_click_lag_ms"), (int, float))]

    def _median_or_zero(xs: List[float]) -> float:
        return statistics.median(xs) if xs else 0.0

    med_rtt = _median_or_zero(rtts)
    med_lag = _median_or_zero(lags)
    med_total_ms = med_rtt + med_lag
    raw_offset_sec = med_total_ms / 1000.0
    recommended = _clamp(_round_half(raw_offset_sec))

    result = {
        "asset": key,
        "recommended_offset_sec": recommended,
        "sample_count": len(docs),
        "median_total_ms": round(med_total_ms, 2),
        "median_network_rtt_ms": round(med_rtt, 2),
        "median_dom_click_lag_ms": round(med_lag, 2),
        "using_default": False,
    }
    _cache[key] = (result, now + CACHE_TTL_SEC)
    return {**result, "cache_hit": False}


async def compute_all_offsets(
    db: AsyncIOMotorDatabase, top_n: int = 30
) -> Dict[str, Any]:
    """
    Return recommended offsets for every asset that has at least
    MIN_SAMPLES_FOR_RECOMMENDATION samples in the latency log.
    """
    coll = db[CLIENT_LATENCY_COLL]
    # Aggregate to find the top-N most-reported assets
    try:
        pipeline = [
            {"$match": {"asset": {"$ne": None}}},
            {"$group": {"_id": "$asset", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": top_n},
        ]
        rows = await coll.aggregate(pipeline).to_list(length=top_n)
    except Exception as e:
        logger.warning(f"adaptive_offset: aggregate failed: {e}")
        return {"assets": [], "count": 0}

    offsets: List[Dict[str, Any]] = []
    for row in rows:
        asset_raw = row.get("_id")
        if not asset_raw:
            continue
        r = await compute_asset_offset(db, asset_raw)
        offsets.append(r)

    return {
        "assets": offsets,
        "count": len(offsets),
        "default_offset_sec": DEFAULT_GLOBAL_OFFSET_SEC,
        "window": SAMPLE_WINDOW,
        "min_samples_required": MIN_SAMPLES_FOR_RECOMMENDATION,
    }


def clear_cache() -> None:
    """Test-support: drop the in-memory cache."""
    _cache.clear()
