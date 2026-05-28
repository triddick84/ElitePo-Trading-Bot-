"""
Background job endpoints + async wrappers for the heaviest existing routes.

Public surface (all under /api):
  GET    /jobs/{job_id}                            — poll status / fetch result
  GET    /jobs?kind=ml_train&limit=20              — recent history
  DELETE /jobs/{job_id}                            — cancel a running job
  POST   /ml/train-from-otc-async                  — async wrapper for trainer
  POST   /backtest/run-async                       — async wrapper for backtest

These are additive — the original synchronous endpoints still exist for
back-compat. The frontend can opt-in to the async variant on a per-call basis.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from background_jobs import job_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["background_jobs"])


# --------------------------------------------------------------------------- #
# Generic job CRUD
# --------------------------------------------------------------------------- #
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    doc = job_manager.get(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="job not found")
    return {"success": True, "job": doc}


@router.get("/jobs")
async def list_jobs(
    kind: Optional[str] = Query(None, description="Filter by job kind"),
    limit: int = Query(50, ge=1, le=200),
):
    return {"success": True, "jobs": job_manager.list_recent(limit=limit, kind=kind)}


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    cancelled = job_manager.cancel(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="job not running")
    return {"success": True, "cancelled": True, "job_id": job_id}


# --------------------------------------------------------------------------- #
# Async wrapper: ML training
# --------------------------------------------------------------------------- #
class TrainAsyncRequest(BaseModel):
    model: str
    symbols: Optional[List[str]] = None
    min_samples: int = 500
    epochs: int = 20
    n_episodes: int = 15


@router.post("/ml/train-from-otc-async")
async def train_from_otc_async(req: TrainAsyncRequest):
    """
    Background variant of /ml/train-from-otc. Returns immediately with a
    job_id; poll /api/jobs/{job_id} for progress and the final result.
    """
    async def runner(update):
        update(progress=5, message=f"starting {req.model} training")
        # Lazy import so this module loads even if heavy ML deps aren't present
        from routes.ml import train_ml_from_otc_data
        update(progress=10, message="invoking trainer")
        result = await train_ml_from_otc_data(
            model=req.model,
            symbols=req.symbols,
            min_samples=req.min_samples,
            epochs=req.epochs,
            n_episodes=req.n_episodes,
        )
        update(progress=100, message="training complete")
        return result

    # ML training can take 2–5 minutes. Allocate 10 min hard ceiling.
    job = job_manager.submit("ml_train", runner, payload=req.dict(), ttl_seconds=600)
    return {"success": True, **job}


# --------------------------------------------------------------------------- #
# Async wrapper: single-strategy backtest
# --------------------------------------------------------------------------- #
class BacktestAsyncRequest(BaseModel):
    strategy: str
    symbol: str
    timeframe: str = "M1"
    days: int = 30


@router.post("/backtest/run-async")
async def backtest_run_async(req: BacktestAsyncRequest):
    """
    Background variant of /backtest/run. Returns a job_id; poll /api/jobs/{id}
    until the job completes and `result` is populated.
    """
    async def runner(update):
        update(progress=5, message=f"starting backtest {req.strategy} on {req.symbol}")
        from routes.backtesting import run_backtest, BacktestRequest
        body = BacktestRequest(
            strategy=req.strategy,
            symbol=req.symbol,
            timeframe=req.timeframe,
            days=req.days,
        )
        update(progress=10, message="loading historical data")
        result = await run_backtest(body)
        update(progress=100, message="backtest complete")
        return result

    job = job_manager.submit("backtest", runner, payload=req.dict(), ttl_seconds=300)
    return {"success": True, **job}
