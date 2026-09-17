"""Iter 146 — TQNet REST endpoints.

Prefix: /api/tqnet/*
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tqnet", tags=["tqnet"])


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
