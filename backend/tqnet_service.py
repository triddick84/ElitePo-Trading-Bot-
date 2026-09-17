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

Iter 147 upgrade — the service now auto-loads trained weights from
`/app/backend/data/tqnet_weights/<SYMBOL>_<TF>.npz` when they exist,
so freshly-trained models take effect on the next signal without any
process restart. Auto-load is idempotent per predictor instance.

Also ships:
    * `tqnet_score_for_df(df, t, ...)` — one-liner used by the signal bridge
    * `TQNET_CYCLE_HINTS` — reasonable W picks for common intraday timeframes
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import pandas as pd

from ml.temporal_query import (
    TQConfig, TQNetPredictor, TQNetPredictorResult, get_default_predictor,
)
from ml.tqnet_trainer import _weight_path, load_weights_if_exists

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
    pred = predictor or _shared_predictor(cfg, asset=asset, timeframe=timeframe)

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


def _shared_predictor(cfg: TQConfig,
                      asset: Optional[str] = None,
                      timeframe: Optional[str] = None) -> TQNetPredictor:
    """Cache one predictor per (window, period, asset, timeframe) combo.

    Auto-loads trained weights from the on-disk cache when `asset` +
    `timeframe` are supplied. Missing weight file → predictor stays at
    random init (identity-plus-noise; non-destructive).
    """
    tag = f"w{cfg.window}_p{cfg.period}_c{cfg.channels}"
    key = f"{tag}::{asset or 'default'}::{timeframe or 'na'}"
    p = _predictor_cache.get(key)
    if p is None:
        p = TQNetPredictor(cfg)
        # Try to auto-load trained weights
        if asset and timeframe:
            path = _weight_path(asset, timeframe)
            if load_weights_if_exists(p, path):
                logger.info(f"[tqnet_service] loaded trained weights: {path}")
        _predictor_cache[key] = p
    return p


def invalidate_predictor_cache(asset: Optional[str] = None,
                               timeframe: Optional[str] = None) -> int:
    """Drop cached predictors so a fresh training run takes effect on the
    next signal. Returns the number of entries dropped."""
    global _predictor_cache
    if asset is None and timeframe is None:
        n = len(_predictor_cache)
        _predictor_cache = {}
        return n
    a = (asset or "default").upper() if asset else None
    dropped = 0
    for key in list(_predictor_cache.keys()):
        parts = key.split("::")
        if len(parts) < 3:
            continue
        _, cached_asset, cached_tf = parts[0], parts[1], parts[2]
        if (a is None or cached_asset.upper() == a) and (timeframe is None or cached_tf == timeframe):
            _predictor_cache.pop(key, None)
            dropped += 1
    return dropped


def _neutral(asset: Optional[str], timeframe: str, reason: str) -> Dict[str, Any]:
    return {
        "source": "ml:tqnet",
        "direction": "NEUTRAL",
        "confidence": 0.0,
        "asset": asset,
        "timeframe": timeframe,
        "meta": {"reason": reason},
    }
