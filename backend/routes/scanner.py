"""
"Find Best Pair Today" Scanner (Iter 66)
========================================

Runs a quick deep_confluence backtest across the asset universe (OTC by default,
or a chosen scope), ranks them by a composite edge metric, and returns the top-N.

The full scan can touch 180+ symbols which would never finish in a 60s HTTP
budget, so this is implemented as a background job via the Iter 65 JobManager.

Endpoints (mounted at /api):
  POST /scanner/find-best-pairs   — submit scan, returns job_id
  GET  /scanner/latest            — last completed scan (cached in mongo)

Composite ranking:
  score = (win_rate - 50) * sqrt(signals) * profit_factor_clip
   - win_rate: 0..100, edge over 50% break-even
   - signals: raw count of trades taken in window (square-rooted so a 200-signal
              50.5% WR doesn't drown a 30-signal 65% WR)
   - profit_factor_clip = min(2.5, max(0.5, profit_factor))  — caps outliers
"""
from __future__ import annotations
import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient, DESCENDING
import os

from background_jobs import job_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scanner"])

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "gpt_signal_bot")
_client = MongoClient(_MONGO_URL)
_db = _client[_DB_NAME]
scanner_results_col = _db["scanner_results"]
scanner_results_col.create_index([("ts", DESCENDING)])


VALID_SCOPES = {
    "all",
    "all_otc",
    "forex_otc", "commodities_otc", "crypto_otc", "indices_otc", "stocks_otc",
    "forex", "commodities", "crypto", "indices", "stocks",
}


class ScannerRequest(BaseModel):
    scope: str = "all_otc"            # see VALID_SCOPES
    strategy: str = "deep_confluence"
    timeframe: Optional[str] = None   # defaults: OTC→5s, regular→M1
    days: int = 1                     # 1 = "today"
    top_n: int = 10
    min_signals: int = 20             # filter out thin samples
    min_confidence: int = 55


def _classes_for_scope(scope: str) -> List[str]:
    if scope == "all":
        return list(VALID_SCOPES - {"all"})
    if scope == "all_otc":
        return ["forex_otc", "commodities_otc", "crypto_otc", "indices_otc", "stocks_otc"]
    return [scope]


def _composite_score(win_rate: float, signals: int, profit_factor: float) -> float:
    edge = win_rate - 50.0
    pf_clip = max(0.5, min(2.5, profit_factor or 1.0))
    return round(edge * math.sqrt(max(1, signals)) * pf_clip, 2)


@router.post("/scanner/find-best-pairs")
async def find_best_pairs(req: ScannerRequest = Body(...)):
    if req.scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(VALID_SCOPES)}")
    if req.top_n < 1 or req.top_n > 50:
        raise HTTPException(status_code=400, detail="top_n must be 1..50")
    if req.days < 1 or req.days > 30:
        raise HTTPException(status_code=400, detail="days must be 1..30")

    classes = _classes_for_scope(req.scope)

    # Build the list of (symbol, timeframe) tuples
    from routes.backtest import (
        _FOREX_MAJORS, _FOREX_CROSSES, _FOREX_EXOTICS,
        _OTC_PAIRS, _COMMODITIES, _OTC_COMMODITIES,
        _CRYPTO, _OTC_CRYPTO, _INDICES, _OTC_INDICES,
        _STOCKS_US, _OTC_STOCKS,
    )
    class_to_symbols = {
        "forex": _FOREX_MAJORS + _FOREX_CROSSES + _FOREX_EXOTICS,
        "forex_otc": _OTC_PAIRS,
        "commodities": _COMMODITIES,
        "commodities_otc": _OTC_COMMODITIES,
        "crypto": _CRYPTO,
        "crypto_otc": _OTC_CRYPTO,
        "indices": _INDICES,
        "indices_otc": _OTC_INDICES,
        "stocks": _STOCKS_US,
        "stocks_otc": _OTC_STOCKS,
    }
    tasks: List[Dict[str, Any]] = []
    for cls in classes:
        is_otc = cls.endswith("_otc")
        tf = req.timeframe or ("5s" if is_otc else "M1")
        for sym in class_to_symbols.get(cls, []):
            tasks.append({"class": cls, "symbol": sym, "timeframe": tf, "is_otc": is_otc})

    if not tasks:
        raise HTTPException(status_code=400, detail="no symbols matched scope")

    async def runner(update):
        from routes.backtesting import run_backtest, BacktestRequest
        leaderboard: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        total = len(tasks)
        update(progress=2, message=f"scanning {total} symbols in scope={req.scope}")

        for i, t in enumerate(tasks):
            # Update progress every 5 symbols to avoid hammering mongo
            if i % 5 == 0 or i == total - 1:
                pct = 2 + int(96 * i / max(1, total))
                update(progress=pct, message=f"[{i + 1}/{total}] {t['symbol']} {t['timeframe']}")
            try:
                body = BacktestRequest(
                    strategy=req.strategy,
                    symbol=t["symbol"],
                    timeframe=t["timeframe"],
                    days=req.days,
                    min_confidence=req.min_confidence,
                )
                resp = await asyncio.wait_for(run_backtest(body), timeout=20)
                if not resp or not resp.get("success") or not resp.get("results"):
                    skipped.append({"symbol": t["symbol"], "reason": "no_results"})
                    continue
                r0 = resp["results"][0]
                m = r0.get("metrics") or {}
                signals = int(m.get("total_trades") or 0)
                wr = float(m.get("win_rate") or 0)
                pf = float(m.get("profit_factor") or 0)
                if signals < req.min_signals:
                    skipped.append({"symbol": t["symbol"], "reason": f"only_{signals}_signals"})
                    continue
                leaderboard.append({
                    "symbol": t["symbol"],
                    "class": t["class"],
                    "timeframe": t["timeframe"],
                    "win_rate": round(wr, 2),
                    "signals": signals,
                    "profit_factor": round(pf, 2),
                    "total_return_pct": round(float(m.get("total_return_pct") or 0), 2),
                    "max_drawdown_pct": round(float(m.get("max_drawdown_pct") or 0), 2),
                    "sharpe": round(float(m.get("sharpe_ratio") or 0), 2),
                    "data_source": resp.get("data_source"),
                    "score": _composite_score(wr, signals, pf),
                })
            except asyncio.TimeoutError:
                skipped.append({"symbol": t["symbol"], "reason": "timeout"})
            except Exception as e:
                skipped.append({"symbol": t["symbol"], "reason": str(e)[:80]})

        leaderboard.sort(key=lambda r: r["score"], reverse=True)
        top = leaderboard[: req.top_n]
        snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "scope": req.scope,
            "strategy": req.strategy,
            "days": req.days,
            "min_confidence": req.min_confidence,
            "min_signals": req.min_signals,
            "total_scanned": total,
            "qualified_count": len(leaderboard),
            "skipped_count": len(skipped),
            "top_n": req.top_n,
            "leaderboard": top,
            "all_qualified": leaderboard,  # full ranked list
            "skipped_sample": skipped[:20],
        }
        # Persist for /scanner/latest
        try:
            scanner_results_col.insert_one({**snapshot, "_ts_dt": datetime.now(timezone.utc)})
        except Exception as _e:
            logger.warning(f"[scanner] result persist failed: {_e}")
        update(progress=100, message=f"done — {len(leaderboard)}/{total} qualified")
        return snapshot

    # Heavy scan can take a while: budget 30s per symbol × ~180 = ~90 min ceiling.
    # In practice OTC backtests are <2s each, so a typical scan completes in 5–10 min.
    job = job_manager.submit("scanner", runner, payload=req.dict(), ttl_seconds=90 * 60)
    return {"success": True, **job, "queued_count": len(tasks)}


@router.get("/scanner/latest")
async def latest_scanner_result(scope: Optional[str] = None):
    q = {"scope": scope} if scope else {}
    doc = scanner_results_col.find_one(q, {"_id": 0, "_ts_dt": 0}, sort=[("ts", -1)])
    if not doc:
        return {"success": False, "error": "no_scan_yet"}
    return {"success": True, **doc}
