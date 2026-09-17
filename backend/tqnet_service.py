"""Iter 146 — TQNet service.

Thin façade that adapts the numpy TQNetPredictor to our existing
signal-scoring plumbing. Produces a confluence-source dict:

    {
        "source": "ml:tqnet",
        "direction": "CALL" | "PUT" | "NEUTRAL",
        "confidence": float in [0, 1],
        "asset": ..., "timeframe": ...,
        "meta": { ... explainability fields ... },
    }

Because the predictor is stateless-per-call, we can safely fan out across
symbols/timeframes without any locking.

Also ships:
    * `tqnet_score_for_df(df, t, ...)` — one-liner used by the signal bridge
    * `TQNET_CYCLE_HINTS` — reasonable W picks for common intraday timeframes
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from ml.temporal_query import (
    TQConfig, TQNetPredictor, TQNetPredictorResult, get_default_predictor,
)

logger = logging.getLogger(__name__)


# For a `1m` timeframe, W=24 = one 24-minute cycle (short intraday);
# W=1440 would be a full session but we keep windows small for latency.
TQNET_CYCLE_HINTS: Dict[str, int] = {
    "5s": 12,       # 1 minute of 5-second bars
    "15s": 20,
    "30s": 20,
    "1m": 24,       # a 24-minute intraday cycle
    "3m": 20,
    "5m": 12,       # an hour of 5m bars
    "15m": 8,       # a 2h window
    "30m": 8,
    "1h": 24,       # a full day of hourly bars
}


def tqnet_score_for_df(
    df: pd.DataFrame,
    *,
    t: Optional[int] = None,
    asset: Optional[str] = None,
    timeframe: str = "1m",
    window: int = 30,
    predictor: Optional[TQNetPredictor] = None,
) -> Dict[str, Any]:
    """Run TQNetPredictor on `df['close']` and wrap the result as a
    confluence-engine signal.

    Returns a signal dict (never raises — logs on failure and returns a
    NEUTRAL signal so the caller can just append it unconditionally).
    """
    if df is None or df.empty or "close" not in df.columns:
        return _neutral(asset, timeframe, reason="empty_df")
    if len(df) < window:
        return _neutral(asset, timeframe, reason=f"need_{window}_bars_have_{len(df)}")

    W = TQNET_CYCLE_HINTS.get(timeframe, 24)
    cfg = TQConfig(channels=1, window=window, period=W)
    pred = predictor or _shared_predictor(cfg)

    # `t` = absolute bar index for cyclic θ_TQ lookup. In production we'd
    # pass an epoch-derived bucket; when the caller doesn't supply one we
    # use the length of the dataframe so consecutive scans phase-advance.
    idx = t if t is not None else int(len(df))
    try:
        result: TQNetPredictorResult = pred.predict(df["close"].to_numpy(), t=idx)
    except Exception as e:
        logger.debug(f"[tqnet_service] predict failed for {asset} {timeframe}: {e}")
        return _neutral(asset, timeframe, reason=f"predict_error:{e}")

    return {
        "source": "ml:tqnet",
        "direction": result.direction,
        "confidence": float(result.confidence),
        "asset": asset,
        "timeframe": timeframe,
        "meta": {
            "signed_drift": result.signed_drift,
            "signed_drift_norm": result.signed_drift_norm,
            "attn_focus_idx": result.attn_focus_idx,
            "cycle_phase": result.cycle_phase,
            "window": window,
            "period": W,
        },
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_predictor_cache: Dict[str, TQNetPredictor] = {}


def _shared_predictor(cfg: TQConfig) -> TQNetPredictor:
    """Cache one predictor per (window, period) combo — weight-random init
    is deterministic but rebuilding matrices per-tick is wasteful."""
    key = f"w{cfg.window}_p{cfg.period}_c{cfg.channels}"
    p = _predictor_cache.get(key)
    if p is None:
        p = TQNetPredictor(cfg)
        _predictor_cache[key] = p
    return p


def _neutral(asset: Optional[str], timeframe: str, reason: str) -> Dict[str, Any]:
    return {
        "source": "ml:tqnet",
        "direction": "NEUTRAL",
        "confidence": 0.0,
        "asset": asset,
        "timeframe": timeframe,
        "meta": {"reason": reason},
    }
