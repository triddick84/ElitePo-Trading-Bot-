"""
Regime classifier for the AI/ML ensemble.

Iter 84 (Jul 2026, Tier 2).

Distinct from `market_regime_detector.py` (which does bullish/bearish signal
inversion for the *signal engine*). This one is a lightweight rule-based
classifier used to **bias the ML ensemble weights** based on whether the
market is currently trending, ranging, or in a high-volatility spike.

Research on 2025-2026 binary-options ML systems highlights regime detection
as the single biggest robustness upgrade over a fixed strategy.

Outputs:
    regime ∈ {"trend_up", "trend_down", "range", "high_volatility"}
    confidence ∈ [0, 100]

Also exposes `apply_regime_bias(weights, regime)` which tilts the ensemble
weights toward the model best suited for the detected regime — small tilt
(≤ 20%) so accuracy-based weighting from `ensemble_weights.py` still
dominates.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Sequence

import numpy as np

logger = logging.getLogger(__name__)


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, n: int = 14) -> float:
    """Wilder-style ATR over the last n bars (simple mean fallback)."""
    if len(closes) < 2:
        return 0.0
    tr = np.maximum.reduce([
        highs[1:] - lows[1:],
        np.abs(highs[1:] - closes[:-1]),
        np.abs(lows[1:] - closes[:-1]),
    ])
    if len(tr) == 0:
        return 0.0
    return float(np.mean(tr[-n:]))


def _ema(vals: np.ndarray, period: int) -> np.ndarray:
    if len(vals) == 0:
        return vals
    alpha = 2.0 / (period + 1)
    out = np.empty_like(vals, dtype=float)
    out[0] = vals[0]
    for i in range(1, len(vals)):
        out[i] = alpha * vals[i] + (1 - alpha) * out[i - 1]
    return out


def _body_wick_ratios(candles: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """Return avg body/range and wick/range over the window.

    High wick/range → indecision (range/reversal).
    High body/range → strong directional moves (trend).
    """
    if not candles:
        return {"avg_body_ratio": 0.0, "avg_wick_ratio": 0.0}
    bodies, wicks = [], []
    for c in candles:
        o = float(c.get("open", 0.0)); cl = float(c.get("close", 0.0))
        h = float(c.get("high", 0.0)); lo = float(c.get("low", 0.0))
        rng = h - lo
        if rng <= 0:
            continue
        body = abs(cl - o)
        wick = max(0.0, rng - body)
        bodies.append(body / rng)
        wicks.append(wick / rng)
    if not bodies:
        return {"avg_body_ratio": 0.0, "avg_wick_ratio": 0.0}
    return {"avg_body_ratio": float(np.mean(bodies)),
            "avg_wick_ratio": float(np.mean(wicks))}


def _volume_imbalance(candles: Sequence[Dict[str, Any]]) -> float:
    """Ratio in [-1, 1]: >0 = up-volume dominates, <0 = down-volume."""
    up_v = 0.0; dn_v = 0.0
    for c in candles:
        o = float(c.get("open", 0.0)); cl = float(c.get("close", 0.0))
        v = float(c.get("volume", 0.0))
        if v <= 0:
            continue
        if cl > o:
            up_v += v
        elif cl < o:
            dn_v += v
    tot = up_v + dn_v
    if tot <= 0:
        return 0.0
    return float((up_v - dn_v) / tot)


def classify_regime(
    candles: Sequence[Dict[str, Any]],
    lookback: int = 50,
) -> Dict[str, Any]:
    """
    Classify the most recent `lookback` candles into a regime.

    Args:
        candles: iterable of dicts with keys open/high/low/close/(volume).
        lookback: number of most-recent bars to analyse (default 50).

    Returns:
        {
          "regime": "trend_up" | "trend_down" | "range" | "high_volatility",
          "confidence": 0..100,
          "features": { ... underlying numbers ... },
          "insufficient_data": bool
        }
    """
    if not candles or len(candles) < 10:
        return {"regime": "range", "confidence": 0.0, "features": {}, "insufficient_data": True}

    window = list(candles)[-lookback:]
    closes = np.array([float(c["close"]) for c in window], dtype=float)
    highs  = np.array([float(c["high"])  for c in window], dtype=float)
    lows   = np.array([float(c["low"])   for c in window], dtype=float)

    returns = np.diff(closes) / (closes[:-1] + 1e-10)
    if len(returns) == 0:
        return {"regime": "range", "confidence": 0.0, "features": {}, "insufficient_data": True}

    mean_ret     = float(np.mean(returns))
    abs_mean_ret = abs(mean_ret)
    mean_abs_ret = float(np.mean(np.abs(returns)))
    std_ret      = float(np.std(returns))

    # Directional strength — 1.0 = pure trend, 0.0 = pure chop.
    directional_strength = (
        abs_mean_ret / (mean_abs_ret + 1e-10) if mean_abs_ret > 0 else 0.0
    )

    ema20 = _ema(closes, 20)
    ema_slope = (
        (ema20[-1] - ema20[max(0, len(ema20) - 6)]) / (ema20[-1] + 1e-10)
        if len(ema20) >= 6 else 0.0
    )

    atr = _atr(highs, lows, closes, n=min(14, len(closes) - 1))
    atr_pct = atr / (closes[-1] + 1e-10)

    # Volatility spike detection
    recent_std = float(np.std(returns[-10:])) if len(returns) >= 10 else std_ret
    vol_pct = recent_std / (std_ret + 1e-10) if std_ret > 0 else 1.0

    bw = _body_wick_ratios(window)
    vol_imb = _volume_imbalance(window)

    features = {
        "mean_return": round(mean_ret, 6),
        "abs_mean_return": round(abs_mean_ret, 6),
        "mean_abs_return": round(mean_abs_ret, 6),
        "std_return": round(std_ret, 6),
        "directional_strength": round(directional_strength, 3),
        "ema_slope_pct": round(ema_slope, 5),
        "atr_pct": round(atr_pct, 5),
        "recent_vol_ratio": round(vol_pct, 3),
        "avg_body_ratio": round(bw["avg_body_ratio"], 3),
        "avg_wick_ratio": round(bw["avg_wick_ratio"], 3),
        "volume_imbalance": round(vol_imb, 3),
        "sample_size": len(window),
    }

    # 1) HIGH_VOLATILITY — takes precedence
    if vol_pct > 1.6 or (atr_pct > 0.004 and directional_strength < 0.25):
        conf = min(100.0, 40 + (vol_pct - 1.0) * 40 + atr_pct * 5000)
        return {"regime": "high_volatility",
                "confidence": round(float(conf), 1),
                "features": features}

    # 2) TREND — strong directional + confirming slope
    if directional_strength >= 0.35 and abs(ema_slope) >= 0.0006:
        conf = 40 + directional_strength * 40 + min(20, abs(ema_slope) * 20000)
        if bw["avg_body_ratio"] > 0.55:
            conf += 8
        conf = min(95.0, conf)
        regime = "trend_up" if (mean_ret > 0 and ema_slope > 0) else "trend_down"
        return {"regime": regime,
                "confidence": round(float(conf), 1),
                "features": features}

    # 3) Everything else = RANGE
    conf = 40 + (1.0 - directional_strength) * 40 + bw["avg_wick_ratio"] * 15
    conf = min(95.0, max(20.0, conf))
    return {"regime": "range",
            "confidence": round(float(conf), 1),
            "features": features}


# ---------------------------------------------------------------------------
# Regime → ensemble bias
# ---------------------------------------------------------------------------
REGIME_WEIGHT_BIAS: Dict[str, Dict[str, float]] = {
    # LSTM/GRU + PPO are sequence-aware and shine in trending markets.
    # Stacking (XGBoost) is generally better at range/mean-reversion setups
    # because tabular features capture the "not moving" signal well.
    "trend_up":        {"lstm_gru": 1.15, "ppo": 1.10, "stacking": 1.00},
    "trend_down":      {"lstm_gru": 1.15, "ppo": 1.10, "stacking": 1.00},
    "range":           {"stacking": 1.20, "lstm_gru": 0.90, "ppo": 0.85},
    # In vol spikes every model gets uncertain — dampen ensemble confidence
    "high_volatility": {"stacking": 0.85, "lstm_gru": 0.85, "ppo": 0.75},
}


def apply_regime_bias(weights: Dict[str, float], regime: str) -> Dict[str, float]:
    """
    Multiply each model's weight by its regime-specific bias, then re-normalise.
    Small tilt (≤ 20%) so it doesn't override accuracy-based weighting.
    """
    bias = REGIME_WEIGHT_BIAS.get(regime, {})
    tilted = {k: max(0.0, weights.get(k, 0.0)) * bias.get(k, 1.0)
              for k in weights}
    total = sum(tilted.values())
    if total <= 0:
        return weights
    return {k: round(v / total, 4) for k, v in tilted.items()}
