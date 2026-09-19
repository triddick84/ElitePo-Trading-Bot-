"""Iter 149 — Market Data + Signal Trace REST endpoints.

Prefix: /api/market-data/*  and  /api/signals/*
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/market-data", tags=["market-data"])
signals_router = APIRouter(prefix="/signals", tags=["signals"])


# ---------------------------------------------------------------------------
# Market data ingestion routes
# ---------------------------------------------------------------------------

@router.get("/status")
async def status() -> Dict[str, Any]:
    """Freshness table per (asset, timeframe) — what the models actually see."""
    from market_data_ingester import ingester
    return await ingester.status()


@router.get("/providers/health")
async def providers_health() -> Dict[str, Any]:
    """Quick round-trip probe of every configured provider."""
    from market_data_ingester import ingester
    return await ingester.providers_health()


class EnsureFreshIn(BaseModel):
    asset: str
    timeframe: str = "1m"
    limit: int = Field(200, ge=30, le=2000)
    max_age_s: Optional[int] = Field(None, ge=1, le=86400)


@router.post("/ensure-fresh")
async def ensure_fresh(req: EnsureFreshIn) -> Dict[str, Any]:
    """Force a fetch if the DB is stale for this (asset, tf) — auto-heal API."""
    from market_data_ingester import ingester
    return await ingester.ensure_fresh(
        req.asset, req.timeframe, limit=req.limit, max_age_s=req.max_age_s,
    )


class BackfillIn(BaseModel):
    assets: List[str] = Field(..., min_length=1, max_length=20)
    timeframes: List[str] = Field(default_factory=lambda: ["1m", "5m", "15m"])
    limit: int = Field(500, ge=50, le=5000)


@router.post("/backfill")
async def backfill(req: BackfillIn) -> Dict[str, Any]:
    """Blocking bulk fetch — one HTTP request each. Use sparingly."""
    from market_data_ingester import ingester
    reports = []
    for a in req.assets:
        for tf in req.timeframes:
            r = await ingester.fetch_and_persist(a, tf, limit=req.limit)
            reports.append({
                "asset": a, "timeframe": tf, "ok": r.ok,
                "provider": r.provider, "rows": r.rows,
                "latency_ms": r.latency_ms, "error": r.error,
            })
    ok_count = sum(1 for r in reports if r["ok"])
    return {
        "requested": len(reports),
        "ok": ok_count,
        "failed": len(reports) - ok_count,
        "reports": reports,
    }


# ---------------------------------------------------------------------------
# Signal generation trace — audit tool
# ---------------------------------------------------------------------------

@signals_router.get("/trace")
async def signal_trace(
    asset: str = Query(..., description="Symbol, e.g. EURUSD_OTC"),
    timeframe: str = Query("1m"),
    limit: int = Query(200, ge=30, le=2000),
    ensure_fresh: bool = Query(True, description="Auto-heal stale data first"),
) -> Dict[str, Any]:
    """Full pipeline trace — data fetch → indicators → SMC → patterns →
    TQNet → confluence gate. Returns every source's contribution so a
    user can see exactly WHY a signal did or didn't fire.
    """
    from market_data_ingester import ingester
    from routes.confluence_routes import _load_candles_from_db, get_confluence_config
    from confluence_service import score_confluence, should_fire

    trace: Dict[str, Any] = {"asset": asset, "timeframe": timeframe,
                             "steps": []}

    # ── STEP 1: ensure the DB has fresh candles
    if ensure_fresh:
        fresh = await ingester.ensure_fresh(asset, timeframe, limit=limit)
        trace["steps"].append({"step": "ensure_fresh", "result": fresh})

    # ── STEP 2: load candles
    df = await _load_candles_from_db(asset, timeframe, limit)
    trace["steps"].append({
        "step": "load_candles",
        "rows": int(len(df)),
        "first_ts": None if df.empty else str(df.index[0]) if "timestamp" not in df.columns else None,
        "last_close": float(df["close"].iloc[-1]) if not df.empty else None,
    })
    if df.empty:
        trace["final"] = {"direction": "NEUTRAL", "confidence": 0.0,
                          "fired": False, "reason": "no_candles"}
        return trace

    # ── STEP 3: each signal source
    signals: List[Dict[str, Any]] = []

    # 3a. Pattern suite
    try:
        from pattern_detector import detect_all
        hits = detect_all(df)
        pattern_signals = []
        for h in hits[-5:]:  # only the last 5 matter for real-time
            direction = getattr(h, "direction", "NEUTRAL")
            if direction not in ("CALL", "PUT"):
                continue
            sig = {
                "source": f"pattern:{getattr(h, 'pattern', 'unknown')}",
                "direction": direction,
                "confidence": float(getattr(h, "confidence", 0.6)),
                "asset": asset, "timeframe": timeframe,
            }
            signals.append(sig); pattern_signals.append(sig)
        trace["steps"].append({"step": "pattern_suite",
                               "n_hits": len(hits),
                               "signals": pattern_signals})
    except Exception as e:
        trace["steps"].append({"step": "pattern_suite", "error": str(e)[:200]})

    # 3b. Smart-money
    try:
        from smart_money import detect_all_smart_money
        sm_hits = detect_all_smart_money(df)
        sm_signals = []
        for h in sm_hits[-5:]:
            direction = getattr(h, "direction", "NEUTRAL")
            if direction not in ("CALL", "PUT"):
                continue
            sig = {
                "source": f"smart_money:{getattr(h, 'pattern', 'unknown')}",
                "direction": direction,
                "confidence": float(getattr(h, "confidence", 0.6)),
                "asset": asset, "timeframe": timeframe,
            }
            signals.append(sig); sm_signals.append(sig)
        trace["steps"].append({"step": "smart_money",
                               "n_hits": len(sm_hits),
                               "signals": sm_signals})
    except Exception as e:
        trace["steps"].append({"step": "smart_money", "error": str(e)[:200]})

    # 3c. Mean reversion
    try:
        from strategies.mean_reversion import mean_reversion_signal
        mr = mean_reversion_signal(df)
        mr_sig = None
        if mr.direction in ("CALL", "PUT"):
            mr_sig = {
                "source": "strategy:mean_reversion",
                "direction": mr.direction,
                "confidence": float(mr.confidence or 0.0),
                "asset": asset, "timeframe": timeframe,
            }
            signals.append(mr_sig)
        trace["steps"].append({"step": "mean_reversion",
                               "direction": mr.direction,
                               "confidence": float(mr.confidence or 0.0),
                               "signal": mr_sig})
    except Exception as e:
        trace["steps"].append({"step": "mean_reversion", "error": str(e)[:200]})

    # 3d. TQNet (Iter 146/147)
    try:
        from tqnet_service import tqnet_score_for_df
        tq = tqnet_score_for_df(df, t=int(len(df)), asset=asset,
                                timeframe=timeframe, window=30)
        if tq.get("direction") in ("CALL", "PUT") and float(tq.get("confidence") or 0) >= 0.05:
            signals.append(tq)
        trace["steps"].append({"step": "tqnet", "signal": tq})
    except Exception as e:
        trace["steps"].append({"step": "tqnet", "error": str(e)[:200]})

    # ── STEP 4: confluence gate
    cfg = get_confluence_config()
    threshold = float(cfg.get("threshold", 0.55))
    min_sources = int(cfg.get("min_sources", 3))
    result = score_confluence(signals, min_sources=min_sources)
    fired = should_fire(result, threshold=threshold, min_sources=min_sources)

    trace["steps"].append({
        "step": "confluence_gate",
        "n_signals_in": len(signals),
        "threshold": threshold,
        "min_sources": min_sources,
        "result": {
            "direction": result.get("direction"),
            "confluence_score": result.get("confluence_score"),
            "call_score": result.get("call_score"),
            "put_score": result.get("put_score"),
            "sources_call": result.get("sources_call"),
            "sources_put": result.get("sources_put"),
            "timeframes_call": result.get("timeframes_call"),
            "timeframes_put": result.get("timeframes_put"),
            "reason": result.get("reason"),
        },
    })
    trace["final"] = {
        "direction": result.get("direction"),
        "confluence_score": result.get("confluence_score"),
        "fired": bool(fired),
        "n_sources": len(result.get("sources_call") or []) + len(result.get("sources_put") or []),
        "reason": "confluence_passed" if fired else (
            "not_enough_sources" if (
                len(result.get("sources_call") or []) + len(result.get("sources_put") or [])
            ) < min_sources else "below_threshold"
        ),
    }
    return trace
