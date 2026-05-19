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
    exceeded count + rate. Includes client-side latency means (network RTT,
    DOM click lag, exec lag) reported by the TM panel (Iter 56c).
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
    
    # Iter 56c — pull TM-reported client latency for the same window
    client_query: Dict[str, Any] = {"_logged_at": {"$gte": cutoff}}
    if asset:
        client_query["asset"] = asset
    if strategy:
        client_query["strategy"] = strategy
    client_docs = await db[LATENCY_COLL + "_client"].find(
        client_query, {"_id": 0}
    ).limit(5000).to_list(length=5000)
    
    if not docs:
        return {
            "count": 0,
            "since_minutes": since_minutes,
            "filter": {"asset": asset, "strategy": strategy, "timeframe": timeframe},
            "stats": None,
            "client": _client_latency_summary(client_docs),
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
        "client": _client_latency_summary(client_docs),
    }


def _client_latency_summary(client_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Iter 56c — compact summary of TM-reported client-side timings."""
    if not client_docs:
        return {"count": 0, "network_rtt_mean_ms": None, "dom_click_lag_mean_ms": None,
                "exec_lag_mean_ms": None, "notes_breakdown": {}}
    
    def _mean(values: List[float]) -> Optional[float]:
        vs = [v for v in values if isinstance(v, (int, float))]
        return round(sum(vs) / len(vs), 2) if vs else None
    
    notes_breakdown: Dict[str, int] = {}
    for d in client_docs:
        n = d.get("notes") or "unknown"
        # Group by prefix (executed/gated/click-failed)
        key = n.split(":", 1)[0]
        notes_breakdown[key] = notes_breakdown.get(key, 0) + 1
    
    return {
        "count": len(client_docs),
        "network_rtt_mean_ms": _mean([d.get("network_rtt_ms") for d in client_docs]),
        "dom_click_lag_mean_ms": _mean([d.get("dom_click_lag_ms") for d in client_docs]),
        "exec_lag_mean_ms": _mean([d.get("exec_lag_ms") for d in client_docs]),
        "notes_breakdown": notes_breakdown,
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


# ============================================================================
# Iter 58 — Latency-Adaptive Trade Rate Guardrail
# ============================================================================
#
# Premise: if `exec_lag_ms` p95 over the last 5 min has DOUBLED vs the trailing
# 60-min baseline, PO's DOM is slow / our broker connection is stressed. Firing
# trades in this state means our entries arrive too late and win-rate collapses.
#
# Action: when guardrail is tripped, /api/signals/force-generate-v2 flips
# `abstain=true` with `abstain_source="latency_guardrail"` on a configurable
# fraction of incoming signals (default 75% throttle = let 25% through).
#
# Resolution: when 5-min p95 returns to within 1.3x of baseline for 3 consecutive
# checks, guardrail releases automatically.

import statistics

_GUARDRAIL_STATE = {
    "tripped": False,
    "tripped_at": None,
    "released_at": None,
    "p95_current_ms": None,
    "p95_baseline_ms": None,
    "ratio": None,
    "throttle_fraction": 0.75,
    "recent_recoveries": 0,  # consecutive checks within tolerance
    "last_evaluated_at": None,
    "trip_count": 0,
    "release_count": 0,
}

GUARDRAIL_TRIP_RATIO = 2.0       # p95 must DOUBLE to trip
GUARDRAIL_RELEASE_RATIO = 1.3    # within 1.3x for 3 consecutive checks to release
GUARDRAIL_RELEASE_STREAK = 3
GUARDRAIL_MIN_SAMPLES_RECENT = 5
GUARDRAIL_MIN_SAMPLES_BASELINE = 15
GUARDRAIL_RECENT_WINDOW_MIN = 5
GUARDRAIL_BASELINE_WINDOW_MIN = 60


def _p95(values: List[float]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None and isinstance(v, (int, float))]
    if len(vals) < 2:
        return float(vals[0]) if vals else None
    vals.sort()
    # statistics.quantiles requires n>=2; method='inclusive' gives the empirical p95
    try:
        qs = statistics.quantiles(vals, n=20, method="inclusive")
        return float(qs[18])  # 95th percentile
    except Exception:
        # Fallback — index-based
        idx = max(0, int(len(vals) * 0.95) - 1)
        return float(vals[idx])


async def evaluate_latency_guardrail() -> Dict[str, Any]:
    """
    Compute current vs baseline exec_lag_ms p95 from `signal_latency_log_client`
    and update guardrail state. Called both:
      - on-demand by /api/signals/latency-guardrail/status
      - implicitly before each force-generate-v2 call
    Cheap: bounded to two MongoDB cursors of <=500 docs each.
    """
    db = _get_db()
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(minutes=GUARDRAIL_RECENT_WINDOW_MIN)
    baseline_cutoff = now - timedelta(minutes=GUARDRAIL_BASELINE_WINDOW_MIN)

    coll = db[LATENCY_COLL + "_client"]
    # Recent window
    recent_cur = coll.find(
        {"_logged_at": {"$gte": recent_cutoff}, "exec_lag_ms": {"$ne": None}},
        {"exec_lag_ms": 1, "_id": 0},
    ).limit(500)
    recent_docs = await recent_cur.to_list(length=500)
    # Baseline window (older portion)
    baseline_cur = coll.find(
        {
            "_logged_at": {"$gte": baseline_cutoff, "$lt": recent_cutoff},
            "exec_lag_ms": {"$ne": None},
        },
        {"exec_lag_ms": 1, "_id": 0},
    ).limit(500)
    baseline_docs = await baseline_cur.to_list(length=500)

    recent_p95 = _p95([d.get("exec_lag_ms") for d in recent_docs])
    baseline_p95 = _p95([d.get("exec_lag_ms") for d in baseline_docs])

    _GUARDRAIL_STATE["p95_current_ms"] = round(recent_p95, 2) if recent_p95 is not None else None
    _GUARDRAIL_STATE["p95_baseline_ms"] = round(baseline_p95, 2) if baseline_p95 is not None else None
    _GUARDRAIL_STATE["last_evaluated_at"] = now.isoformat()
    _GUARDRAIL_STATE["recent_samples"] = len(recent_docs)
    _GUARDRAIL_STATE["baseline_samples"] = len(baseline_docs)

    # Need both windows populated to make any decision
    if (
        len(recent_docs) < GUARDRAIL_MIN_SAMPLES_RECENT
        or len(baseline_docs) < GUARDRAIL_MIN_SAMPLES_BASELINE
        or recent_p95 is None
        or baseline_p95 is None
        or baseline_p95 <= 0
    ):
        _GUARDRAIL_STATE["ratio"] = None
        # Don't change tripped state when we lack data — fail open if not tripped
        return dict(_GUARDRAIL_STATE)

    ratio = recent_p95 / baseline_p95
    _GUARDRAIL_STATE["ratio"] = round(ratio, 3)

    if not _GUARDRAIL_STATE["tripped"]:
        if ratio >= GUARDRAIL_TRIP_RATIO:
            _GUARDRAIL_STATE["tripped"] = True
            _GUARDRAIL_STATE["tripped_at"] = now.isoformat()
            _GUARDRAIL_STATE["released_at"] = None
            _GUARDRAIL_STATE["recent_recoveries"] = 0
            _GUARDRAIL_STATE["trip_count"] = _GUARDRAIL_STATE.get("trip_count", 0) + 1
            logger.warning(
                f"[latency-guardrail] TRIPPED — recent p95={recent_p95:.0f}ms baseline p95={baseline_p95:.0f}ms ratio={ratio:.2f}x"
            )
    else:
        # When tripped, only release after 3 consecutive sub-1.3x checks
        if ratio <= GUARDRAIL_RELEASE_RATIO:
            _GUARDRAIL_STATE["recent_recoveries"] = _GUARDRAIL_STATE.get("recent_recoveries", 0) + 1
            if _GUARDRAIL_STATE["recent_recoveries"] >= GUARDRAIL_RELEASE_STREAK:
                _GUARDRAIL_STATE["tripped"] = False
                _GUARDRAIL_STATE["released_at"] = now.isoformat()
                _GUARDRAIL_STATE["release_count"] = _GUARDRAIL_STATE.get("release_count", 0) + 1
                logger.info(
                    f"[latency-guardrail] RELEASED — ratio={ratio:.2f}x for {GUARDRAIL_RELEASE_STREAK} consecutive checks"
                )
        else:
            _GUARDRAIL_STATE["recent_recoveries"] = 0

    return dict(_GUARDRAIL_STATE)


def get_guardrail_state() -> Dict[str, Any]:
    """Return a copy of the current guardrail state (cheap, no IO)."""
    return dict(_GUARDRAIL_STATE)


def is_guardrail_tripped() -> bool:
    """Cheap accessor for the live signal pipeline."""
    return bool(_GUARDRAIL_STATE.get("tripped"))


def should_throttle_signal() -> bool:
    """
    When guardrail is tripped, returns True for `throttle_fraction` of calls.
    Probabilistic so we still let some signals through (so we don't lose visibility).
    """
    if not _GUARDRAIL_STATE.get("tripped"):
        return False
    import random
    return random.random() < float(_GUARDRAIL_STATE.get("throttle_fraction", 0.75))


def set_guardrail_throttle_fraction(fraction: float) -> Dict[str, Any]:
    """Manual override of the throttle fraction (0.0–1.0)."""
    f = max(0.0, min(1.0, float(fraction)))
    _GUARDRAIL_STATE["throttle_fraction"] = f
    return get_guardrail_state()

