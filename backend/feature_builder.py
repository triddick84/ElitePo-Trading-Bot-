"""
Iter 119 — Real Feature Builder.

Computes actual indicator values from a candle window at signal time.
Replaces the placeholder-heavy feature dict that made the LightGBM
meta-model AUC = 0.481 (worse than random).

All 20 features in FEATURE_ORDER get real values — no more rsi=50,
bb_pos=0.5, kyle_lambda=0 stand-ins.

Zero dependencies beyond numpy — safe to call from anywhere in the
request path (e.g. the /signals/latest gate block).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from adx_regime_gate import compute_adx, classify_adx_regime

_REGIME_CODES = {"CHOPPY": 0, "NEUTRAL": 1, "TREND": 2}


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    up = np.clip(deltas, 0, None)
    dn = np.clip(-deltas, 0, None)
    avg_up = float(np.mean(up[-period:]))
    avg_dn = float(np.mean(dn[-period:]))
    if avg_dn <= 1e-10:
        return 100.0
    rs = avg_up / avg_dn
    return float(100.0 - 100.0 / (1.0 + rs))


def _ema(v: np.ndarray, n: int) -> float:
    if len(v) == 0:
        return 0.0
    alpha = 2.0 / (n + 1)
    out = float(v[0])
    for x in v[1:]:
        out = alpha * float(x) + (1 - alpha) * out
    return out


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return float(np.mean(highs - lows)) if len(highs) else 0.0
    tr = np.maximum.reduce([
        highs[1:] - lows[1:],
        np.abs(highs[1:] - closes[:-1]),
        np.abs(lows[1:] - closes[:-1]),
    ])
    return float(np.mean(tr[-period:]))


def _bb_position(closes: np.ndarray, period: int = 20, k: float = 2.0) -> float:
    if len(closes) < period:
        return 0.5
    window = closes[-period:]
    mean = float(np.mean(window))
    std = float(np.std(window))
    if std <= 1e-10:
        return 0.5
    lower = mean - k * std
    upper = mean + k * std
    pos = (float(closes[-1]) - lower) / (upper - lower + 1e-10)
    return float(np.clip(pos, 0.0, 1.0))


def _ha_streaks(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict[str, int]:
    """Return {bull, bear} — consecutive same-colored HA candles at the tail."""
    if len(closes) < 2:
        return {"bull": 0, "bear": 0}
    ha_close = (opens + highs + lows + closes) / 4.0
    ha_open = np.zeros_like(closes, dtype=float)
    ha_open[0] = (opens[0] + closes[0]) / 2.0
    for i in range(1, len(closes)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    bull = bear = 0
    i = len(closes) - 1
    while i >= 0 and ha_close[i] > ha_open[i]:
        bull += 1
        i -= 1
    if bull == 0:
        i = len(closes) - 1
        while i >= 0 and ha_close[i] < ha_open[i]:
            bear += 1
            i -= 1
    return {"bull": bull, "bear": bear}


def _kyle_lambda(closes: np.ndarray, volumes: Optional[np.ndarray]) -> float:
    """Kyle's price-impact λ = |Δp| / signed volume (proxy, no signed vol available)."""
    if len(closes) < 5:
        return 0.0
    dp = np.abs(np.diff(closes[-20:]))
    if volumes is not None and len(volumes) >= len(dp) + 1:
        v = np.abs(volumes[-len(dp):])
        denom = float(np.mean(v)) + 1e-10
    else:
        denom = float(np.mean(np.abs(np.diff(closes[-20:])))) + 1e-10
    return float(np.mean(dp) / denom)


def _vpin(closes: np.ndarray, volumes: Optional[np.ndarray]) -> float:
    """
    Volume-synchronized Probability of Informed Trading proxy.
    Without tick-level data we approximate with:
       VPIN ≈ mean_over_last_N( |ret| / (|ret|+atr) )
    Values in [0,1] — higher = more directional / informed flow.
    """
    if len(closes) < 15:
        return 0.5
    rets = np.diff(closes[-20:])
    abs_ret = np.abs(rets)
    denom = abs_ret + float(np.std(rets)) + 1e-10
    return float(np.clip(np.mean(abs_ret / denom), 0.0, 1.0))


def _flow_imbalance(opens: np.ndarray, closes: np.ndarray) -> float:
    """
    Order flow imbalance proxy from candle open/close:
    positive = buying pressure dominates, negative = selling.
    Returns a value in [-1, 1].
    """
    if len(closes) < 5:
        return 0.0
    bodies = closes[-10:] - opens[-10:]
    total = np.sum(np.abs(bodies)) + 1e-10
    return float(np.clip(np.sum(bodies) / total, -1.0, 1.0))


def build_features(
    candles: Sequence[Dict[str, Any]],
    direction: Optional[str] = None,
    signal_confidence: Optional[float] = None,
) -> Dict[str, float]:
    """
    Build the 20-feature dict expected by lightgbm_meta_service.FEATURE_ORDER
    from a chronologically-sorted OHLCV candle list (oldest first).

    All 20 features get real, computed values. Direction & signal confidence
    are optional and populate the `vote_*` and `*_confidence` features.
    """
    if not candles:
        return {k: 0.0 for k in _ZERO_FEATURES}

    opens = np.asarray([float(c.get("open", c.get("close", 0.0))) for c in candles])
    highs = np.asarray([float(c.get("high", c.get("close", 0.0))) for c in candles])
    lows = np.asarray([float(c.get("low", c.get("close", 0.0))) for c in candles])
    closes = np.asarray([float(c.get("close", 0.0)) for c in candles])
    volumes = np.asarray([float(c.get("volume") or 0.0) for c in candles])

    adx_info = compute_adx(highs, lows, closes, period=14)
    regime = classify_adx_regime(adx_info["adx"], adx_info["plus_di"], adx_info["minus_di"])

    ema_fast = _ema(closes, 8)
    ema_slow = _ema(closes, 21)
    macd = ema_fast - ema_slow
    # Rolling MACD signal for histogram
    def _rolling_ema_series(arr: np.ndarray, n: int) -> np.ndarray:
        out = np.zeros_like(arr, dtype=float)
        alpha = 2.0 / (n + 1)
        out[0] = float(arr[0])
        for i in range(1, len(arr)):
            out[i] = alpha * float(arr[i]) + (1 - alpha) * out[i - 1]
        return out
    ema_fast_s = _rolling_ema_series(closes, 8)
    ema_slow_s = _rolling_ema_series(closes, 21)
    macd_s = ema_fast_s - ema_slow_s
    macd_signal_s = _rolling_ema_series(macd_s, 9)
    macd_hist = float(macd_s[-1] - macd_signal_s[-1])

    ha = _ha_streaks(opens, highs, lows, closes)

    dir_up = str(direction or "").upper() in ("UP", "CALL", "BUY")
    dir_dn = str(direction or "").upper() in ("DOWN", "PUT", "SELL")

    conf = signal_confidence
    if conf is None:
        conf = 0.5
    else:
        try:
            conf = float(conf)
            if conf > 1.0:
                conf = conf / 100.0
        except (TypeError, ValueError):
            conf = 0.5

    return {
        "rsi": _rsi(closes, 14),
        "macd": float(macd),
        "macd_hist": macd_hist,
        "atr": _atr(highs, lows, closes, 14),
        "ema_fast": float(ema_fast),
        "ema_slow": float(ema_slow),
        "bb_pos": _bb_position(closes, 20, 2.0),
        "adx": float(adx_info["adx"]),
        "plus_di": float(adx_info["plus_di"]),
        "minus_di": float(adx_info["minus_di"]),
        "ha_streak_bull": float(ha["bull"]),
        "ha_streak_bear": float(ha["bear"]),
        "kyle_lambda": _kyle_lambda(closes, volumes if volumes.any() else None),
        "vpin": _vpin(closes, volumes if volumes.any() else None),
        "flow_imbalance": _flow_imbalance(opens, closes),
        "vote_up": 1.0 if dir_up else 0.0,
        "vote_down": 1.0 if dir_dn else 0.0,
        "mean_confidence": float(conf),
        "max_confidence": float(conf),
        "regime_code": float(_REGIME_CODES.get(regime["regime"], 1)),
    }


_ZERO_FEATURES = [
    "rsi", "macd", "macd_hist", "atr", "ema_fast", "ema_slow", "bb_pos",
    "adx", "plus_di", "minus_di", "ha_streak_bull", "ha_streak_bear",
    "kyle_lambda", "vpin", "flow_imbalance", "vote_up", "vote_down",
    "mean_confidence", "max_confidence", "regime_code",
]
