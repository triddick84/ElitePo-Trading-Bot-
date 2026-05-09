"""
5-Second Heikin Ashi Fractal Strategy (v8.62.0)

A focused, single-indicator strategy that operates on Heikin Ashi candles
(constructed from the underlying OHLC) and uses Williams Fractal detection
with period 3. Designed for the 5-second chart with 5-second expiry.

Per user spec:
    - Red fractal signal (up fractal at price peak)   → BUY (CALL)
    - Green fractal signal (down fractal at price low) → SELL (PUT)

Why this works on PO:
    Heikin Ashi smooths noise and exposes the trend direction between bars,
    while a tight 3-bar Williams Fractal pinpoints micro pivots. On a 5s
    chart the bot reacts to short-term reversals/continuations within the
    same 5s expiry window — the directionality of the fractal tells the bot
    whether the next 5s candle is more likely to extend the move (per user
    interpretation: red/peak ⇒ CALL).

Indicator math:
    Heikin Ashi:
        HA_close = (open + high + low + close) / 4
        HA_open  = (prev_HA_open + prev_HA_close) / 2     (seed = (open+close)/2)
        HA_high  = max(high, HA_open, HA_close)
        HA_low   = min(low,  HA_open, HA_close)

    Williams Fractal (period N, default 3):
        Up fractal   at center idx c if HA_high[c] > HA_high[i] for every i
                     in [c-N, c+N] and i != c  (center is the strict max).
        Down fractal at c if HA_low[c] < HA_low[i] for the same window
                     (strict min).
        Latest confirmable fractal sits at index `len-1-N`.

Output contract (matches strategy_registry interface):
    generate_signal(df) -> {
        direction: 'CALL' | 'PUT',
        confidence: 50-90,
        reasoning: str,
        timeframe: '5s',
        expiry_seconds: 5,
        strategy: '5s Heikin Ashi Fractal',
    }
    Returns None when the latest confirmed bar is neither an up nor a down
    fractal (no signal). Confidence reflects how dominant the center bar
    is over its neighbors.

Registered as `5s_heikin_fractal` in `strategy_registry.py`.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Heikin Ashi conversion — vectorised, O(n)
# -----------------------------------------------------------------------------
def to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert a standard OHLC DataFrame to Heikin Ashi. Returns a NEW DataFrame
    with columns `ha_open`, `ha_high`, `ha_low`, `ha_close` aligned to the
    original index. Caller's `df` is not mutated.
    """
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise ValueError("df must have open/high/low/close columns")
    if len(df) == 0:
        return df.copy()

    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    low = df["low"].astype(float).values
    c = df["close"].astype(float).values

    n = len(df)
    ha_close = (o + h + low + c) / 4.0
    ha_open = np.empty(n)
    # Seed first HA open as midpoint of first real open/close (industry-standard)
    ha_open[0] = (o[0] + c[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    ha_high = np.maximum.reduce([h, ha_open, ha_close])
    ha_low = np.minimum.reduce([low, ha_open, ha_close])

    out = df.copy()
    out["ha_open"] = ha_open
    out["ha_high"] = ha_high
    out["ha_low"] = ha_low
    out["ha_close"] = ha_close
    return out


# -----------------------------------------------------------------------------
# Williams Fractal (period N) detector
# -----------------------------------------------------------------------------
def latest_fractal(
    highs: np.ndarray, lows: np.ndarray, period: int = 3
) -> Optional[Dict]:
    """
    Return the most recently CONFIRMED fractal in the series, or None if no
    fractal exists at the latest confirmable index.

    A confirmed fractal sits at index `c = len - 1 - period` because we need
    `period` bars on the right side to validate strict max/min.

    Returns:
        {
            kind: 'up' | 'down',
            center_idx: int,
            center_value: float,
            dominance: float,   # how dominant the center is vs neighbors (0..1)
        }
        or None.
    """
    if period < 1:
        period = 1
    n = len(highs)
    if n < 2 * period + 1:
        return None
    c = n - 1 - period
    if c < period:
        return None

    window_lo, window_hi = c - period, c + period + 1
    nbr_h = np.concatenate([highs[window_lo:c], highs[c + 1: window_hi]])
    nbr_l = np.concatenate([lows[window_lo:c], lows[c + 1: window_hi]])
    h_c, l_c = highs[c], lows[c]

    is_up = bool(np.all(h_c > nbr_h))
    is_dn = bool(np.all(l_c < nbr_l))

    if is_up:
        # dominance: how much higher the center is than the second-highest
        second = float(np.max(nbr_h)) if len(nbr_h) else h_c
        dom = (h_c - second) / max(abs(h_c), 1e-9)
        return {"kind": "up", "center_idx": c, "center_value": float(h_c), "dominance": float(dom)}
    if is_dn:
        second = float(np.min(nbr_l)) if len(nbr_l) else l_c
        dom = (second - l_c) / max(abs(l_c), 1e-9)
        return {"kind": "down", "center_idx": c, "center_value": float(l_c), "dominance": float(dom)}
    return None


# -----------------------------------------------------------------------------
# Strategy class
# -----------------------------------------------------------------------------
class Strategy5sHeikinFractal:
    """
    5s Heikin Ashi Fractal Strategy.

    Per user spec:
      - UP fractal (peak / "red signal")  → CALL  (buy)
      - DOWN fractal (trough / "green sig.") → PUT (sell)
    """

    def __init__(self, fractal_period: int = 3):
        self.name = "5s Heikin Ashi Fractal"
        self.timeframe = "5s"
        self.expiry_seconds = 5
        self.accuracy_target = 70.0
        self.fractal_period = fractal_period

    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        if df is None or len(df) < 2 * self.fractal_period + 5:
            return None

        try:
            ha = to_heikin_ashi(df)
        except Exception as e:
            logger.warning(f"Heikin Ashi conversion failed: {e}")
            return None

        highs = ha["ha_high"].values
        lows = ha["ha_low"].values
        frac = latest_fractal(highs, lows, period=self.fractal_period)
        if not frac:
            return None

        # User-specified mapping: peak (red) ⇒ CALL, trough (green) ⇒ PUT
        if frac["kind"] == "up":
            direction = "CALL"
            color = "RED"
            reasoning = (
                f"HA up-fractal (red, peak) at idx {frac['center_idx']}, "
                f"period={self.fractal_period}, dominance={frac['dominance']:.4f} — BUY"
            )
        else:
            direction = "PUT"
            color = "GREEN"
            reasoning = (
                f"HA down-fractal (green, trough) at idx {frac['center_idx']}, "
                f"period={self.fractal_period}, dominance={frac['dominance']:.4f} — SELL"
            )

        # Confidence from dominance: scale [0..0.001] → [55..82]
        # (a fractal dominating its neighbors by 1bp+ is a strong pivot)
        dom = frac["dominance"]
        # Map 0 → 55, 0.001 → 82 (clamped)
        confidence = max(55.0, min(82.0, 55.0 + dom * 27_000.0))

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "reasoning": reasoning,
            "timeframe": self.timeframe,
            "expiry_seconds": self.expiry_seconds,
            "strategy": self.name,
            "indicator": "fractal",
            "fractal_period": self.fractal_period,
            "fractal_color": color,
            "fractal_kind": frac["kind"],
            "fractal_dominance": round(dom, 6),
        }


# Module-level singleton (registry consumes this)
strategy_5s_heikin_fractal = Strategy5sHeikinFractal(fractal_period=3)
