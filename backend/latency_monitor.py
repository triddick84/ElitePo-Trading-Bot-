"""
Signal Latency Monitor (Iter 55 — May 13, 2026)
================================================

Tracks each phase of the signal-generation pipeline (OTC fetch, ML inference,
strategy eval, abstain gate) and the end-to-end round-trip (server → TM panel
→ PO DOM click). Auto-abstains on stale-data signals when total latency
exceeds the timeframe budget.

Phases logged:
    - otc_fetch          (DB candle pull)
    - ml_prediction      (sklearn / LSTM / PPO inference)
    - strategy_eval      (strategy_registry rule evaluation)
    - abstain_gate       (BOTAI threshold resolver + classifier output)
    - total              (wall clock from request start → response sent)

Client-side phases reported via /api/signals/latency-report:
    - network_rtt_ms     (server→browser RTT, browser self-clock)
    - dom_click_lag_ms   (response received → DOM click fired)
    - exec_lag_ms        (DOM click → PO confirms trade open)

Auto-abstain budgets (server_latency_ms):
    - 5s    → 1500ms
    - 15s   → 3000ms
    - 30s   → 5000ms
    - 1m+   → 8000ms
A signal exceeding its budget gets `abstain=true` with reason
`stale_data_high_latency` so the TM panel refuses to fire it.
"""
from __future__ import annotations
import os
import time
import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Per-timeframe budgets for total server-side signal generation latency.
# If exceeded → auto-abstain on stale data.
LATENCY_BUDGETS_MS: Dict[str, int] = {
    "5s": 1500,
    "S5": 1500,
    "15s": 3000,
    "S15": 3000,
    "30s": 5000,
    "S30": 5000,
    "1m": 8000,
    "M1": 8000,
    "5m": 15000,
    "default": 5000,
}

# Cap stored entries — auto-trim
MAX_LOG_ENTRIES = 10000
LATENCY_COLL = "signal_latency_log"

_db_client: Optional[AsyncIOMotorClient] = None
_db = None


def _get_db():
    global _db_client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "trading_bot_db")
        _db_client = AsyncIOMotorClient(mongo_url)
        _db = _db_client[db_name]
    return _db


def budget_for(timeframe: Optional[str]) -> int:
    """Latency budget in ms for the given timeframe; falls back to default."""
    if not timeframe:
        return LATENCY_BUDGETS_MS["default"]
    return LATENCY_BUDGETS_MS.get(timeframe, LATENCY_BUDGETS_MS["default"])


class LatencyTracker:
    """
    Context manager that records timing for each phase of signal generation.

    Usage:
        tracker = LatencyTracker(asset='EURUSD_OTC', timeframe='5s', strategy='holly_crossover_5s')
        with tracker.phase('otc_fetch'):
            await fetch_candles(...)
        with tracker.phase('ml_prediction'):
            pred = model.predict(...)
        report = tracker.finalize()
        # report = {'phases': {...}, 'total_ms': 234.5, 'budget_ms': 1500, 'exceeded': False}
    """

    def __init__(
        self,
        asset: Optional[str] = None,
        timeframe: Optional[str] = None,
        strategy: Optional[str] = None,
    ):
        self.asset = asset
        self.timeframe = timeframe
        self.strategy = strategy
        self.start_ts = time.perf_counter()
        self.phases: Dict[str, float] = {}
        self._stack: List[tuple] = []  # (name, start)
        self.budget_ms = budget_for(timeframe)
        self.finalized = False
        self._extras: Dict[str, Any] = {}

    @contextmanager
    def phase(self, name: str):
        """Record the duration of a phase."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            # If the same phase is entered multiple times (e.g. retries) sum them
            self.phases[name] = round(self.phases.get(name, 0.0) + dt_ms, 2)

    def add_phase_ms(self, name: str, ms: float) -> None:
        """Manually contribute timing for a phase (e.g. external sub-call)."""
        self.phases[name] = round(self.phases.get(name, 0.0) + float(ms), 2)

    def annotate(self, **kwargs: Any) -> None:
        """Attach arbitrary key/values to the latency record (e.g. confidence)."""
        self._extras.update(kwargs)

    def finalize(self) -> Dict[str, Any]:
        """Compute total + budget check. Returns the report."""
        if self.finalized:
            return self.report
        total_ms = round((time.perf_counter() - self.start_ts) * 1000.0, 2)
        self.report: Dict[str, Any] = {
            "asset": self.asset,
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "phases": self.phases,
            "total_ms": total_ms,
            "budget_ms": self.budget_ms,
            "exceeded": bool(total_ms > self.budget_ms),
            "headroom_ms": round(self.budget_ms - total_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **self._extras,
        }
        self.finalized = True
        return self.report


async def log_latency_async(report: Dict[str, Any]) -> None:
    """
    Persist a latency report to MongoDB. Fire-and-forget (no await needed
    from the caller's perspective). Auto-trims oldest entries past
    MAX_LOG_ENTRIES.
    """
    if not report:
        return
    try:
        db = _get_db()
        await db[LATENCY_COLL].insert_one({**report, "_logged_at": datetime.now(timezone.utc)})
        # Periodic auto-trim: every 100 inserts approx
        if (int(time.time()) % 60) == 0:
            count = await db[LATENCY_COLL].estimated_document_count()
            if count > MAX_LOG_ENTRIES * 1.2:
                # Drop oldest 20%
                cutoff = await db[LATENCY_COLL].find(
                    {}, {"_id": 1, "_logged_at": 1}
                ).sort("_logged_at", 1).limit(count - MAX_LOG_ENTRIES).to_list(length=count)
                if cutoff:
                    await db[LATENCY_COLL].delete_many(
                        {"_id": {"$in": [d["_id"] for d in cutoff]}}
                    )
    except Exception as e:
        logger.debug(f"[latency] log_latency_async failed: {e}")


def log_latency_fire_and_forget(report: Dict[str, Any]) -> None:
    """Spawn the async log without blocking the caller."""
    if not report:
        return
    try:
        asyncio.create_task(log_latency_async(report))
    except RuntimeError:
        # No running event loop (e.g. unit test) — silently drop
        pass


async def get_latency_stats(
    asset: Optional[str] = None,
    strategy: Optional[str] = None,
    timeframe: Optional[str] = None,
    since_minutes: int = 60,
) -> Dict[str, Any]:
    """
    Aggregate latency stats: count, mean, p50, p95, p99, max, per-phase mean,
    exceeded count + rate. Filter by asset/strategy/timeframe/since.
    """
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    query: Dict[str, Any] = {"_logged_at": {"$gte": cutoff}}
    if asset:
        query["asset"] = asset
    if strategy:
        query["strategy"] = strategy
    if timeframe:
        query["timeframe"] = timeframe
    
    cursor = db[LATENCY_COLL].find(query, {"_id": 0}).sort("_logged_at", -1).limit(5000)
    docs = await cursor.to_list(length=5000)
    if not docs:
        return {
            "count": 0,
            "since_minutes": since_minutes,
            "filter": {"asset": asset, "strategy": strategy, "timeframe": timeframe},
            "stats": None,
        }
    
    totals = sorted(d.get("total_ms", 0) for d in docs)
    
    def pct(arr: List[float], p: float) -> float:
        if not arr:
            return 0.0
        k = max(0, min(len(arr) - 1, int(round((len(arr) - 1) * p / 100.0))))
        return arr[k]
    
    exceeded = sum(1 for d in docs if d.get("exceeded"))
    
    # Per-phase means
    phase_sums: Dict[str, float] = {}
    phase_counts: Dict[str, int] = {}
    for d in docs:
        for name, ms in (d.get("phases") or {}).items():
            phase_sums[name] = phase_sums.get(name, 0.0) + float(ms)
            phase_counts[name] = phase_counts.get(name, 0) + 1
    phase_means = {
        name: round(phase_sums[name] / phase_counts[name], 2)
        for name in phase_sums
    }
    
    return {
        "count": len(docs),
        "since_minutes": since_minutes,
        "filter": {"asset": asset, "strategy": strategy, "timeframe": timeframe},
        "stats": {
            "mean_ms": round(sum(totals) / len(totals), 2),
            "p50_ms": round(pct(totals, 50), 2),
            "p95_ms": round(pct(totals, 95), 2),
            "p99_ms": round(pct(totals, 99), 2),
            "max_ms": round(max(totals), 2),
            "min_ms": round(min(totals), 2),
            "exceeded_count": exceeded,
            "exceeded_rate": round(exceeded / len(docs), 4),
            "phase_means_ms": phase_means,
        },
    }


async def get_latency_health() -> Dict[str, Any]:
    """
    Quick health snapshot: last 5 minutes of latency across all signals.
    Used by the dashboard / TM panel chip.
    """
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    cursor = db[LATENCY_COLL].find({"_logged_at": {"$gte": cutoff}}, {"_id": 0}).limit(500)
    docs = await cursor.to_list(length=500)
    if not docs:
        return {"status": "no_data", "count": 0, "color": "grey"}
    
    totals = [d.get("total_ms", 0) for d in docs]
    exceeded = sum(1 for d in docs if d.get("exceeded"))
    rate = exceeded / len(docs) if docs else 0
    mean = sum(totals) / len(totals) if totals else 0
    
    # Health colour
    if rate >= 0.20:
        color = "red"
        status = "degraded"
    elif rate >= 0.05:
        color = "yellow"
        status = "warning"
    else:
        color = "green"
        status = "healthy"
    
    return {
        "status": status,
        "color": color,
        "count": len(docs),
        "mean_ms": round(mean, 2),
        "exceeded_rate": round(rate, 4),
        "window_minutes": 5,
    }


async def report_client_latency(
    signal_id: Optional[str],
    network_rtt_ms: Optional[float] = None,
    dom_click_lag_ms: Optional[float] = None,
    exec_lag_ms: Optional[float] = None,
    asset: Optional[str] = None,
    strategy: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist client-reported timings (TM panel). Stored in a sibling
    collection so a single signal can be joined with its execution stats.
    """
    db = _get_db()
    doc = {
        "signal_id": signal_id,
        "network_rtt_ms": network_rtt_ms,
        "dom_click_lag_ms": dom_click_lag_ms,
        "exec_lag_ms": exec_lag_ms,
        "asset": asset,
        "strategy": strategy,
        "notes": notes,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "_logged_at": datetime.now(timezone.utc),
    }
    await db[LATENCY_COLL + "_client"].insert_one(doc)
    return {"success": True, "stored": True}
