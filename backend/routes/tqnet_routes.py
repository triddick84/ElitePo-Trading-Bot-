"""Iter 146 — TQNet REST endpoints.

Prefix: /api/tqnet/*
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tqnet", tags=["tqnet"])


# ---------------------------------------------------------------------------
# Iter 147 — Training job registry (in-process, single-worker)
# ---------------------------------------------------------------------------
# We keep this in-memory because training runs on the same process that
# holds the predictor cache. Jobs are ephemeral; a restart invalidates
# them (the persisted weights survive independently).

_JOBS: Dict[str, Dict[str, Any]] = {}
_JOB_LOCK = threading.Lock()


def _set_job(job_id: str, **fields):
    with _JOB_LOCK:
        _JOBS.setdefault(job_id, {})
        _JOBS[job_id].update(fields)


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _JOB_LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None


class PredictIn(BaseModel):
    closes: List[float] = Field(..., min_length=30)
    timeframe: str = "1m"
    asset: Optional[str] = None
    window: int = Field(30, ge=10, le=200)
    t: Optional[int] = None
    # Optional: caller can override the cycle period `W`. If omitted we
    # derive it from the timeframe hint table.
    period: Optional[int] = Field(None, ge=2, le=1440)


class SymbolBridgeIn(BaseModel):
    symbol: str
    timeframe: str = "1m"
    limit: int = Field(200, ge=30, le=2000)


class TrainSymbolIn(BaseModel):
    symbol: str
    timeframe: str = "1m"
    limit: int = Field(500, ge=100, le=5000)      # candles to pull
    window: int = Field(30, ge=10, le=200)
    epochs: int = Field(50, ge=5, le=500)
    max_windows: int = Field(150, ge=30, le=1000)  # subsample cap


class TrainClosesIn(BaseModel):
    closes: List[float] = Field(..., min_length=50)
    symbol: str = "MANUAL"
    timeframe: str = "1m"
    window: int = Field(30, ge=10, le=200)
    epochs: int = Field(50, ge=5, le=500)
    max_windows: int = Field(150, ge=30, le=1000)


@router.post("/predict")
async def predict(req: PredictIn) -> Dict[str, Any]:
    """One-shot TQNet next-bar signal from a raw close-price list."""
    import pandas as pd
    from tqnet_service import tqnet_score_for_df, TQNET_CYCLE_HINTS
    from ml.temporal_query import TQConfig, TQNetPredictor

    df = pd.DataFrame({"close": req.closes})
    predictor = None
    if req.period is not None:
        cfg = TQConfig(channels=1, window=req.window, period=req.period)
        predictor = TQNetPredictor(cfg)
    signal = tqnet_score_for_df(
        df, t=req.t, asset=req.asset,
        timeframe=req.timeframe, window=req.window,
        predictor=predictor,
    )
    signal["cycle_hint_table"] = TQNET_CYCLE_HINTS
    return signal


@router.post("/predict-symbol")
async def predict_symbol(req: SymbolBridgeIn) -> Dict[str, Any]:
    """Load recent candles for `symbol` from Mongo and return the TQNet
    signal. Uses the same candle store as the confluence gate so scores
    are directly comparable with other sources."""
    from tqnet_service import tqnet_score_for_df
    from routes.confluence_routes import _load_candles_from_db

    df = await _load_candles_from_db(req.symbol.upper(), req.timeframe, req.limit)
    if df is None or df.empty:
        return {
            "source": "ml:tqnet", "direction": "NEUTRAL", "confidence": 0.0,
            "asset": req.symbol, "timeframe": req.timeframe,
            "meta": {"reason": "no_candles"},
        }
    return tqnet_score_for_df(
        df, t=int(len(df)), asset=req.symbol, timeframe=req.timeframe,
    )


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Cheap sanity ping — does the predictor return a well-formed result
    on a synthetic uptrend?"""
    import numpy as np
    from tqnet_service import tqnet_score_for_df
    import pandas as pd

    rng = np.random.default_rng(0)
    closes = 1.10 + np.cumsum(rng.normal(0, 0.0005, 60)) + np.linspace(0, 0.001, 60)
    df = pd.DataFrame({"close": closes})
    sig = tqnet_score_for_df(df, t=0, asset="EURUSD", timeframe="1m", window=30)
    return {
        "ok": True,
        "sample_signal": sig,
        "notes": "Uses RevIN + TQ-MHA numpy port from mql5 article 19157",
    }


# ---------------------------------------------------------------------------
# Iter 147 — Training endpoints
# ---------------------------------------------------------------------------

def _run_training(job_id: str, closes: list, symbol: str, timeframe: str,
                  window: int, epochs: int, max_windows: int) -> None:
    """Background-thread entrypoint. Fits weights + persists to disk."""
    import numpy as np
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import (
        fit_tqnet, save_weights, _weight_path, load_weights_if_exists,
    )
    from tqnet_service import TQNET_CYCLE_HINTS, invalidate_predictor_cache

    try:
        _set_job(job_id, status="running", started_at=time.time())
        W = TQNET_CYCLE_HINTS.get(timeframe, 24)
        cfg = TQConfig(channels=1, window=window, period=W)
        pred = TQNetPredictor(cfg)
        # Warm-start from any previously-saved weights so retraining is
        # incremental rather than a fresh restart.
        try:
            path = _weight_path(symbol, timeframe)
            if load_weights_if_exists(pred, path):
                _set_job(job_id, warm_started=True)
        except Exception:                                # pragma: no cover
            pass

        report = fit_tqnet(
            pred, np.asarray(closes, dtype=float),
            epochs=epochs, max_windows=max_windows,
        )

        path = _weight_path(symbol, timeframe)
        save_weights(pred, path, report)
        # Force the live service to reload the new weights on next call
        invalidate_predictor_cache(asset=symbol, timeframe=timeframe)

        _set_job(job_id,
                 status="done" if report.ok else "failed",
                 finished_at=time.time(),
                 report={
                     "ok": report.ok,
                     "initial_loss": report.initial_loss,
                     "final_loss": report.final_loss,
                     "improvement": report.improvement,
                     "n_windows": report.n_windows,
                     "n_params": report.n_params,
                     "epochs": report.epochs,
                     "elapsed_s": report.elapsed_s,
                     "baseline_direction_accuracy": report.baseline_direction_accuracy,
                     "trained_direction_accuracy": report.trained_direction_accuracy,
                     "message": report.message,
                     "meta": report.meta,
                 },
                 weight_path=path)
    except Exception as e:                                # pragma: no cover
        import traceback
        _set_job(job_id, status="failed",
                 finished_at=time.time(),
                 error=f"{type(e).__name__}: {e}",
                 traceback=traceback.format_exc()[-2000:])


@router.post("/train")
async def train_from_closes(req: TrainClosesIn,
                            bg: BackgroundTasks) -> Dict[str, Any]:
    """Fit TQNet weights against a user-supplied list of close prices.

    Returns immediately with a `job_id`; poll `GET /tqnet/train/status/{id}`.
    """
    if len(req.closes) < req.window + 5:
        raise HTTPException(400, f"need at least {req.window + 5} closes")

    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, status="queued", queued_at=time.time(),
             symbol=req.symbol.upper(), timeframe=req.timeframe,
             window=req.window, epochs=req.epochs,
             n_closes=len(req.closes))
    bg.add_task(_run_training, job_id, req.closes,
                req.symbol.upper(), req.timeframe,
                req.window, req.epochs, req.max_windows)
    return {"ok": True, "job_id": job_id, "status": "queued"}


@router.post("/train-symbol")
async def train_from_symbol(req: TrainSymbolIn,
                            bg: BackgroundTasks) -> Dict[str, Any]:
    """Pull recent candles from Mongo for `symbol` + `timeframe`, then train."""
    from routes.confluence_routes import _load_candles_from_db
    df = await _load_candles_from_db(req.symbol.upper(), req.timeframe, req.limit)
    if df is None or df.empty or "close" not in df.columns:
        raise HTTPException(404, f"no candles for {req.symbol}/{req.timeframe}")
    if len(df) < req.window + 5:
        raise HTTPException(400, f"need at least {req.window + 5} candles, got {len(df)}")

    closes = df["close"].astype(float).tolist()
    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, status="queued", queued_at=time.time(),
             symbol=req.symbol.upper(), timeframe=req.timeframe,
             window=req.window, epochs=req.epochs,
             n_closes=len(closes))
    bg.add_task(_run_training, job_id, closes,
                req.symbol.upper(), req.timeframe,
                req.window, req.epochs, req.max_windows)
    return {"ok": True, "job_id": job_id, "status": "queued",
            "candles_loaded": len(closes)}


@router.get("/train/status/{job_id}")
async def train_status(job_id: str) -> Dict[str, Any]:
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    return {"job_id": job_id, **job}


@router.get("/weights")
async def list_weights() -> Dict[str, Any]:
    from ml.tqnet_trainer import list_trained_weights
    entries = list_trained_weights()
    return {"count": len(entries), "weights": entries}


@router.delete("/weights/{symbol}/{timeframe}")
async def drop_weights(symbol: str, timeframe: str) -> Dict[str, Any]:
    import os
    from ml.tqnet_trainer import _weight_path
    from tqnet_service import invalidate_predictor_cache
    path = _weight_path(symbol.upper(), timeframe)
    removed = 0
    for p in (path, path + ".meta.json"):
        if os.path.exists(p):
            try:
                os.remove(p)
                removed += 1
            except OSError:                          # pragma: no cover
                pass
    invalidate_predictor_cache(asset=symbol.upper(), timeframe=timeframe)
    return {"ok": True, "symbol": symbol.upper(), "timeframe": timeframe, "removed_files": removed}
