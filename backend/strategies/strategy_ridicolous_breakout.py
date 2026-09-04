"""
Ridicolous Breakout Prediction — 1m strategy port from a TradingView Pine
Script indicator (© Ridicolous Trader, v2.2).

The original Pine script builds two 5-level probability tables:

  Given the previous candle was GREEN → what fraction of the time did the
  NEXT candle:
      • make a NEW HIGH ≥ prev_high + step*i     (call it "hh_i")
      • make a NEW LOW  ≤ prev_low  - step*i     (call it "ll_i")

  Same table for RED previous candles.

At bar-close the winning percentage decides:
    bias = green ? (max(hh0, ll0) == hh0 ? BULLISH : BEARISH)
                 : (max(hh0, ll0) == hh0 ? BULLISH : BEARISH)   (same test)

And the confidence is the winning percentage itself.

Because Pocket Option binaries fire on the NEXT bar after we observe the
signal, this port evaluates the tables at every generate_signal() call using
the entire candle window available in the passed dataframe (no lookahead —
we only look at the last CLOSED candle and stats built from all bars up to
and including the current one).

The port slots into the existing 1m strategy family and follows the
{direction, confidence, reason, strategy, timeframe, indicators, meta}
contract shared by strategy_algo_pack.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RidicolousBreakoutPrediction:
    """Statistical breakout-bias predictor from the "Ridicolous Breakout
    Predication v2.2" indicator (1-min candle · 2-min trade window).

    Direction logic:
      - The LAST CLOSED candle's color selects the stats bucket (green/red).
      - We compare P(new high ≥ prev_high + step) vs P(new low ≤ prev_low - step).
      - Higher probability wins → CALL if new-high dominates, PUT if new-low.
      - Confidence = winning probability (0-100).

    Tunables mirror the Pine inputs:
      - perc:  percentage step size (default 1.0 → 1%)
      - levels: how many probability levels to compute (5 max as in Pine)
      - min_history: minimum candles required before firing a signal
      - min_confidence: minimum winning probability required to fire
    """

    name = "🎯 Ridicolous Breakout Prediction [Iter 120]"
    timeframe = "1m"
    accuracy_target = 68.0
    beta = True

    def __init__(
        self,
        perc: float = 1.0,
        levels: int = 5,
        min_history: int = 60,
        min_confidence: float = 55.0,
    ) -> None:
        self.perc = float(perc)
        self.levels = int(np.clip(levels, 1, 5))
        self.min_history = int(min_history)
        self.min_confidence = float(min_confidence)

    # ------------------------------------------------------------------
    # Core stats build
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_stats(
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        step: float,
        levels: int,
    ) -> Dict[str, Any]:
        """Replicates the Pine `Score()` accumulator across the full history.

        Returns:
            {
              green_total, red_total,
              green_hh[levels], green_ll[levels],  → counts (int)
              red_hh[levels],   red_ll[levels],
              green_hh_pct[levels], green_ll_pct[levels],   → percentages 0-100
              red_hh_pct[levels],   red_ll_pct[levels],
            }
        """
        n = len(closes)
        # `prev` = candle i-1, current = candle i. Loop i from 1..n-1.
        prev_close = closes[:-1]
        prev_open = opens[:-1]
        prev_high = highs[:-1]
        prev_low = lows[:-1]
        cur_high = highs[1:]
        cur_low = lows[1:]

        green_prev = prev_close > prev_open  # bool array length n-1
        red_prev = prev_close < prev_open

        green_total = int(green_prev.sum())
        red_total = int(red_prev.sum())

        green_hh = np.zeros(levels, dtype=int)
        green_ll = np.zeros(levels, dtype=int)
        red_hh = np.zeros(levels, dtype=int)
        red_ll = np.zeros(levels, dtype=int)

        for i in range(levels):
            hh = cur_high >= (prev_high + step * i)
            ll = cur_low <= (prev_low - step * i)
            green_hh[i] = int(np.count_nonzero(green_prev & hh))
            green_ll[i] = int(np.count_nonzero(green_prev & ll))
            red_hh[i] = int(np.count_nonzero(red_prev & hh))
            red_ll[i] = int(np.count_nonzero(red_prev & ll))

        def _pct(counts: np.ndarray, total: int) -> np.ndarray:
            if total <= 0:
                return np.zeros_like(counts, dtype=float)
            return np.round(counts / total * 100.0, 2)

        return {
            "green_total": green_total,
            "red_total": red_total,
            "green_hh": green_hh.tolist(),
            "green_ll": green_ll.tolist(),
            "red_hh": red_hh.tolist(),
            "red_ll": red_ll.tolist(),
            "green_hh_pct": _pct(green_hh, green_total).tolist(),
            "green_ll_pct": _pct(green_ll, green_total).tolist(),
            "red_hh_pct": _pct(red_hh, red_total).tolist(),
            "red_ll_pct": _pct(red_ll, red_total).tolist(),
        }

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < self.min_history:
            return self._neutral("insufficient history "
                                 f"({0 if df is None else len(df)} < {self.min_history})")

        try:
            opens = df["open"].astype(float).to_numpy()
            highs = df["high"].astype(float).to_numpy()
            lows = df["low"].astype(float).to_numpy()
            closes = df["close"].astype(float).to_numpy()
        except Exception as e:
            return self._neutral(f"missing OHLC column: {e}")

        # Reference price for step sizing = latest close, matches Pine (`c * perc/100`)
        ref_close = float(closes[-1])
        step = ref_close * (self.perc / 100.0)
        if step <= 0 or not np.isfinite(step):
            return self._neutral("invalid step")

        stats = self._compute_stats(opens, highs, lows, closes, step, self.levels)

        # Last CLOSED candle (index -1 is "just closed" — same semantics as Pine's [1] applied at bar_open)
        last_open = float(opens[-1])
        last_close = float(closes[-1])
        last_green = last_close > last_open
        last_red = last_close < last_open
        if not (last_green or last_red):
            return self._neutral("doji — no color bias", extra={
                "ref_close": ref_close, "step": step, "stats": stats,
            })

        if last_green:
            hh_pct = stats["green_hh_pct"][0]
            ll_pct = stats["green_ll_pct"][0]
            total = stats["green_total"]
        else:
            hh_pct = stats["red_hh_pct"][0]
            ll_pct = stats["red_ll_pct"][0]
            total = stats["red_total"]

        # Both sides at 0 means the color bucket is empty — abstain
        if hh_pct <= 0 and ll_pct <= 0:
            return self._neutral(
                f"no historical prior in {'GREEN' if last_green else 'RED'} bucket",
                extra={"stats": stats, "step": step, "ref_close": ref_close},
            )

        # BULLISH = new-high dominates; BEARISH = new-low dominates.
        if hh_pct >= ll_pct:
            direction = "CALL"
            confidence = float(hh_pct)
            bias_label = "BULLISH"
            other_pct = float(ll_pct)
        else:
            direction = "PUT"
            confidence = float(ll_pct)
            bias_label = "BEARISH"
            other_pct = float(hh_pct)

        if confidence < self.min_confidence:
            return self._neutral(
                f"below min_confidence ({round(confidence, 2)}% < {self.min_confidence}%)",
                extra={
                    "stats": stats, "step": step, "ref_close": ref_close,
                    "last_candle_color": "GREEN" if last_green else "RED",
                    "hh_pct": hh_pct, "ll_pct": ll_pct,
                },
            )

        # 5-level pyramid preview (top 3 levels for the UI/AI-tab)
        pct_source_hh = (
            stats["green_hh_pct"] if last_green else stats["red_hh_pct"]
        )
        pct_source_ll = (
            stats["green_ll_pct"] if last_green else stats["red_ll_pct"]
        )

        reason = (
            f"Prev {('GREEN' if last_green else 'RED')} · "
            f"hh0={round(hh_pct, 2)}% · ll0={round(ll_pct, 2)}% → {bias_label}"
        )

        return {
            "direction": direction,
            "confidence": round(min(confidence, 99.0), 2),
            "reason": reason,
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "last_candle_color": "GREEN" if last_green else "RED",
                "step_size": round(step, 6),
                "step_pct": round(self.perc, 3),
                "ref_close": ref_close,
                "hh_pct_lvl0": round(hh_pct, 2),
                "ll_pct_lvl0": round(ll_pct, 2),
                "hh_pct_pyramid": [round(x, 2) for x in pct_source_hh],
                "ll_pct_pyramid": [round(x, 2) for x in pct_source_ll],
                "sample_size": int(total),
                "green_total": stats["green_total"],
                "red_total": stats["red_total"],
            },
            "meta": {
                "family": "statistical_breakout",
                "bias": bias_label,
                "winning_pct": round(confidence, 2),
                "losing_pct": round(other_pct, 2),
                "levels": self.levels,
                "min_history": self.min_history,
                "min_confidence": self.min_confidence,
                "source": "pinescript_port__ridicolous_v2.2",
            },
        }

    # ------------------------------------------------------------------
    def _neutral(self, reason: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "direction": "NEUTRAL",
            "confidence": 0,
            "reason": reason,
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": (extra or {}),
            "meta": {"family": "statistical_breakout",
                     "source": "pinescript_port__ridicolous_v2.2"},
        }


# ---------------------------------------------------------------------------
# Public singleton (imported by strategy_registry)
# ---------------------------------------------------------------------------
ridicolous_breakout_prediction = RidicolousBreakoutPrediction()

RIDICOLOUS_STRATEGIES = {
    "ridicolous_breakout_prediction": ridicolous_breakout_prediction,
}
