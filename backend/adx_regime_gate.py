"""
ADX-filtered Regime Gate (Iter 115a).

Global gate that blocks:
- Trend strategies when the market is choppy (ADX < 20)
- Mean-reversion strategies when the market is trending (ADX > 25)

Between 20-25 = NEUTRAL — no gate applied.

ADX is Wilder's Average Directional Index computed on (high, low, close).
This gate is intentionally light-weight (no talib dependency) and works on
any candle dict list with `high`, `low`, `close` keys.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Strategy family tags — how each strategy behaves relative to trend.
# TREND family: prefers trending markets (ADX > 25)
# MEAN_REV family: prefers ranging markets (ADX < 20)
# NEUTRAL / HYBRID: accepted in all regimes
# ---------------------------------------------------------------------------
STRATEGY_FAMILY: Dict[str, str] = {
    # Trend followers
    "supertrend": "TREND",
    "ema_cascade": "TREND",
    "ema_crossover": "TREND",
    "triple_ema": "TREND",
    "quad_crossover": "TREND",
    "trend_momentum": "TREND",
    "trend_following": "TREND",
    "ichimoku": "TREND",
    "daily_bias": "TREND",
    "wyckoff": "TREND",
    "position_trading": "TREND",
    "momentum_breakout": "TREND",
    "supertrend_reversal": "TREND",
    "fast_supertrend_catch": "TREND",
    "vwap_momentum": "TREND",
    "macd_keltner": "TREND",
    "ema20_pullback_reversal": "TREND",
    # Mean-reversion
    "rsi_stochastic": "MEAN_REV",
    "rsi_divergence": "MEAN_REV",
    "bollinger_rsi": "MEAN_REV",
    "51s_reversal": "MEAN_REV",
    "21s_reversal": "MEAN_REV",
    "momentum_exhaustion": "MEAN_REV",
    "support_resistance": "MEAN_REV",
    "price_action": "MEAN_REV",
    "volume_profile": "MEAN_REV",
    "candlestick_bible": "MEAN_REV",
    "heikin_fractal": "MEAN_REV",
    "keltner_macd": "MEAN_REV",
    # Confluence / hybrid — always allowed
    "triple_confluence": "NEUTRAL",
    "multi_timeframe": "NEUTRAL",
    "williams_adx_atr": "NEUTRAL",
    "breakout": "NEUTRAL",
    "swing_trading": "NEUTRAL",
    "five_second_breakout": "NEUTRAL",
    "1m_scalping": "NEUTRAL",
    "5s_pro": "NEUTRAL",
    "algo_pack": "NEUTRAL",
}


def _wilder_smooth(vals: np.ndarray, n: int) -> np.ndarray:
    """Wilder's smoothing (equivalent to RMA)."""
    out = np.zeros_like(vals, dtype=float)
    if len(vals) < n:
        return out
    out[n - 1] = float(np.sum(vals[:n]))
    for i in range(n, len(vals)):
        out[i] = out[i - 1] - (out[i - 1] / n) + vals[i]
    return out


def compute_adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Dict[str, float]:
    """
    Compute Wilder's ADX(period). Returns adx, plus_di, minus_di as floats.
    Returns {"adx": 0.0, ...} if insufficient data.
    """
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)
    if len(c) < period * 2 + 1:
        return {"adx": 0.0, "plus_di": 0.0, "minus_di": 0.0, "insufficient_data": True}

    up_move = h[1:] - h[:-1]
    down_move = l[:-1] - l[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.maximum.reduce([
        h[1:] - l[1:],
        np.abs(h[1:] - c[:-1]),
        np.abs(l[1:] - c[:-1]),
    ])

    atr = _wilder_smooth(tr, period)
    plus_dm_s = _wilder_smooth(plus_dm, period)
    minus_dm_s = _wilder_smooth(minus_dm, period)

    # Avoid divide-by-zero
    atr_safe = np.where(atr == 0, 1e-10, atr)
    plus_di = 100.0 * plus_dm_s / atr_safe
    minus_di = 100.0 * minus_dm_s / atr_safe

    di_sum = plus_di + minus_di
    di_sum_safe = np.where(di_sum == 0, 1e-10, di_sum)
    dx = 100.0 * np.abs(plus_di - minus_di) / di_sum_safe

    # ADX = Wilder-smoothed DX (starting at index 2*period - 1)
    adx_arr = np.zeros_like(dx)
    start = 2 * period - 1
    if start < len(dx):
        adx_arr[start] = float(np.mean(dx[period - 1:start + 1]))
        for i in range(start + 1, len(dx)):
            adx_arr[i] = (adx_arr[i - 1] * (period - 1) + dx[i]) / period

    return {
        "adx": float(adx_arr[-1]) if len(adx_arr) else 0.0,
        "plus_di": float(plus_di[-1]) if len(plus_di) else 0.0,
        "minus_di": float(minus_di[-1]) if len(minus_di) else 0.0,
        "insufficient_data": False,
    }


def classify_adx_regime(adx: float, plus_di: float = 0.0, minus_di: float = 0.0) -> Dict[str, Any]:
    """
    Classify market state from ADX:
    - CHOPPY:  ADX < 20 (no directional strength — mean-reversion favoured)
    - NEUTRAL: 20 <= ADX <= 25 (transition zone — everything allowed)
    - TREND:   ADX > 25 (trending — trend-following favoured)
    Direction bias derived from +DI vs -DI.
    """
    if adx <= 0:
        return {"regime": "NEUTRAL", "direction": "NONE", "adx": 0.0}
    if adx < 20:
        regime = "CHOPPY"
    elif adx <= 25:
        regime = "NEUTRAL"
    else:
        regime = "TREND"
    direction = "UP" if plus_di > minus_di else ("DOWN" if minus_di > plus_di else "NONE")
    return {
        "regime": regime,
        "direction": direction,
        "adx": round(float(adx), 2),
        "plus_di": round(float(plus_di), 2),
        "minus_di": round(float(minus_di), 2),
    }


def _strategy_family(strategy_id: str) -> str:
    """Derive family (TREND/MEAN_REV/NEUTRAL) from strategy id string."""
    if not strategy_id:
        return "NEUTRAL"
    sid = str(strategy_id).lower()
    # exact key match first
    if sid in STRATEGY_FAMILY:
        return STRATEGY_FAMILY[sid]
    # substring match — strategy names in DB may be "rsi_divergence_1m" etc.
    for key, fam in STRATEGY_FAMILY.items():
        if key in sid:
            return fam
    return "NEUTRAL"


def evaluate_regime_gate(
    strategy_id: Optional[str],
    signal_direction: Optional[str],
    candles: Sequence[Dict[str, Any]],
    period: int = 14,
) -> Dict[str, Any]:
    """
    Return dict describing whether the gate would block this signal.

    Output keys:
      gated: bool  — True if should abstain
      reason: str  — human-readable reason
      regime: dict — ADX regime info
      strategy_family: str — resolved family
    """
    if not candles or len(candles) < period * 2 + 2:
        return {
            "gated": False,
            "reason": "insufficient_data",
            "regime": {"regime": "NEUTRAL", "adx": 0.0},
            "strategy_family": _strategy_family(strategy_id),
        }
    highs = [float(c.get("high", c.get("close", 0.0))) for c in candles]
    lows = [float(c.get("low", c.get("close", 0.0))) for c in candles]
    closes = [float(c.get("close", 0.0)) for c in candles]
    adx_info = compute_adx(highs, lows, closes, period=period)
    regime_info = classify_adx_regime(
        adx_info["adx"], adx_info["plus_di"], adx_info["minus_di"]
    )
    family = _strategy_family(strategy_id)

    gated = False
    reason = ""
    if family == "TREND" and regime_info["regime"] == "CHOPPY":
        gated = True
        reason = f"Trend strategy blocked in CHOPPY regime (ADX={regime_info['adx']} < 20)"
    elif family == "MEAN_REV" and regime_info["regime"] == "TREND":
        gated = True
        reason = f"Mean-reversion strategy blocked in TREND regime (ADX={regime_info['adx']} > 25)"

    # Direction disagreement in strong trend — also block if signal direction
    # opposes the +DI/-DI dominant side and family isn't MEAN_REV.
    if not gated and regime_info["regime"] == "TREND" and family != "MEAN_REV":
        if signal_direction and regime_info["direction"] != "NONE":
            sig_up = str(signal_direction).lower() in ("up", "call", "buy")
            reg_up = regime_info["direction"] == "UP"
            if sig_up != reg_up:
                gated = True
                reason = (
                    f"Signal direction opposes ADX trend "
                    f"(+DI={regime_info['plus_di']}, -DI={regime_info['minus_di']})"
                )

    return {
        "gated": gated,
        "reason": reason or "ok",
        "regime": regime_info,
        "strategy_family": family,
    }
