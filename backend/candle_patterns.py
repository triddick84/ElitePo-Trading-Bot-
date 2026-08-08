"""
Candlestick Pattern Recognition + Historical Outcome Analysis — Iter 94.

Purpose
-------
The Force-Generate ("Go") button response currently gives the user a
direction + confidence number. Users report low confidence *in* the button
because they can't see WHY the bot picked that direction.

This module provides:
  1. Pattern recognition — 15 classic + 3 modern candlestick patterns on
     the last N candles (default 20).
  2. Historical outcome lookup — for each detected pattern, computes the
     rolling win-rate of that pattern on THIS asset from the last M
     candles (default 500). "How often did a Bullish Engulfing on
     EURUSD_OTC 1m actually predict UP?"
  3. Behavioural summary — a plain-English 1-2 sentence commentary of
     what the recent 3-5 candles suggest.

No third-party TA library. Uses raw OHLC arrays. Fast enough to run inline
on `/api/signals/force-generate-v2`.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
@dataclass
class Candle:
    o: float
    h: float
    l: float
    c: float

    @property
    def body(self) -> float:
        return abs(self.c - self.o)

    @property
    def range(self) -> float:
        return max(1e-12, self.h - self.l)

    @property
    def upper_wick(self) -> float:
        return self.h - max(self.o, self.c)

    @property
    def lower_wick(self) -> float:
        return min(self.o, self.c) - self.l

    @property
    def is_bull(self) -> bool:
        return self.c > self.o

    @property
    def is_bear(self) -> bool:
        return self.c < self.o

    @property
    def body_ratio(self) -> float:
        """Body / total range — 1.0 = marubozu, 0.0 = doji."""
        return self.body / self.range


def _to_candles(o: List[float], h: List[float], l: List[float],
                c: List[float]) -> List[Candle]:
    n = min(len(o), len(h), len(l), len(c))
    return [Candle(o[i], h[i], l[i], c[i]) for i in range(n)]


# ---------------------------------------------------------------------------
# Individual pattern detectors — each returns True/False on the LAST candle
# (or the last N candles) of the sliced series.
#
# All detectors are self-contained + defensive against short input.
# Direction convention: "bullish" = expects price UP next; "bearish" = DOWN.
# ---------------------------------------------------------------------------

def _atr(candles: List[Candle], n: int = 14) -> float:
    if not candles: return 0.0
    xs = candles[-n:] if len(candles) >= n else candles
    trs = []
    for i, c in enumerate(xs):
        if i == 0:
            trs.append(c.range)
        else:
            prev = xs[i-1]
            trs.append(max(
                c.h - c.l,
                abs(c.h - prev.c),
                abs(c.l - prev.c),
            ))
    return statistics.mean(trs) if trs else 0.0


# ---------- Single-candle patterns ----------
def _is_doji(c: Candle, atr_ref: float) -> bool:
    """Very small body relative to range and ATR."""
    if atr_ref <= 0:
        return c.body_ratio < 0.05
    return c.body_ratio < 0.10 and c.body < 0.15 * atr_ref


def _is_hammer(c: Candle, atr_ref: float) -> bool:
    """Small body near top, long lower wick (>= 2× body), tiny upper wick."""
    if c.range < 0.5 * atr_ref: return False
    return (c.lower_wick >= 2 * c.body
            and c.upper_wick <= 0.5 * c.body
            and c.body_ratio > 0.05)


def _is_shooting_star(c: Candle, atr_ref: float) -> bool:
    """Small body near bottom, long upper wick (>= 2× body), tiny lower wick."""
    if c.range < 0.5 * atr_ref: return False
    return (c.upper_wick >= 2 * c.body
            and c.lower_wick <= 0.5 * c.body
            and c.body_ratio > 0.05)


def _is_marubozu_bull(c: Candle) -> bool:
    return c.is_bull and c.body_ratio > 0.9


def _is_marubozu_bear(c: Candle) -> bool:
    return c.is_bear and c.body_ratio > 0.9


# ---------- Two-candle patterns ----------
def _is_bullish_engulfing(a: Candle, b: Candle) -> bool:
    return (a.is_bear and b.is_bull
            and b.o <= a.c and b.c >= a.o
            and b.body > a.body)


def _is_bearish_engulfing(a: Candle, b: Candle) -> bool:
    return (a.is_bull and b.is_bear
            and b.o >= a.c and b.c <= a.o
            and b.body > a.body)


def _is_piercing(a: Candle, b: Candle) -> bool:
    """Bull reversal — a is bear, b is bull, opens below a.l, closes above midpoint of a's body."""
    mid = (a.o + a.c) / 2.0
    return (a.is_bear and b.is_bull
            and b.o < a.l and b.c > mid and b.c < a.o)


def _is_dark_cloud(a: Candle, b: Candle) -> bool:
    """Bear reversal — mirror of piercing."""
    mid = (a.o + a.c) / 2.0
    return (a.is_bull and b.is_bear
            and b.o > a.h and b.c < mid and b.c > a.o)


def _is_tweezer_top(a: Candle, b: Candle) -> bool:
    return (a.is_bull and b.is_bear
            and abs(a.h - b.h) < 0.05 * max(a.range, b.range))


def _is_tweezer_bottom(a: Candle, b: Candle) -> bool:
    return (a.is_bear and b.is_bull
            and abs(a.l - b.l) < 0.05 * max(a.range, b.range))


# ---------- Three-candle patterns ----------
def _is_morning_star(a: Candle, b: Candle, c: Candle) -> bool:
    """Bull reversal — long bear, small body (gap down or doji), long bull closing >= a's midpoint."""
    if not (a.is_bear and c.is_bull): return False
    small_middle = b.body < 0.5 * a.body
    close_above_mid = c.c > (a.o + a.c) / 2.0
    return small_middle and close_above_mid


def _is_evening_star(a: Candle, b: Candle, c: Candle) -> bool:
    """Bear reversal — mirror of morning star."""
    if not (a.is_bull and c.is_bear): return False
    small_middle = b.body < 0.5 * a.body
    close_below_mid = c.c < (a.o + a.c) / 2.0
    return small_middle and close_below_mid


def _is_three_white_soldiers(a: Candle, b: Candle, c: Candle) -> bool:
    return (a.is_bull and b.is_bull and c.is_bull
            and b.o > a.o and c.o > b.o
            and b.c > a.c and c.c > b.c
            and a.body_ratio > 0.5 and b.body_ratio > 0.5 and c.body_ratio > 0.5)


def _is_three_black_crows(a: Candle, b: Candle, c: Candle) -> bool:
    return (a.is_bear and b.is_bear and c.is_bear
            and b.o < a.o and c.o < b.o
            and b.c < a.c and c.c < b.c
            and a.body_ratio > 0.5 and b.body_ratio > 0.5 and c.body_ratio > 0.5)


def _is_three_line_strike_bull(a: Candle, b: Candle, c: Candle, d: Candle) -> bool:
    """Four-candle: 3 bears down + one bull engulfing all three."""
    return (a.is_bear and b.is_bear and c.is_bear
            and d.is_bull
            and d.o < c.c and d.c > a.o)


def _is_three_line_strike_bear(a: Candle, b: Candle, c: Candle, d: Candle) -> bool:
    return (a.is_bull and b.is_bull and c.is_bull
            and d.is_bear
            and d.o > c.c and d.c < a.o)


# ---------------------------------------------------------------------------
# Master dispatcher
# ---------------------------------------------------------------------------

# Registry: (id, human name, direction, min_candles_needed, detector_fn)
# direction: "bullish" | "bearish" | "neutral"
_PATTERN_REGISTRY: List[Tuple[str, str, str, int, Any]] = [
    ("doji",              "Doji",                    "neutral", 1,
     lambda cs, a: _is_doji(cs[-1], a)),
    ("hammer",            "Hammer",                  "bullish", 1,
     lambda cs, a: _is_hammer(cs[-1], a)),
    ("shooting_star",     "Shooting Star",           "bearish", 1,
     lambda cs, a: _is_shooting_star(cs[-1], a)),
    ("marubozu_bull",     "Bullish Marubozu",        "bullish", 1,
     lambda cs, a: _is_marubozu_bull(cs[-1])),
    ("marubozu_bear",     "Bearish Marubozu",        "bearish", 1,
     lambda cs, a: _is_marubozu_bear(cs[-1])),
    ("engulfing_bull",    "Bullish Engulfing",       "bullish", 2,
     lambda cs, a: _is_bullish_engulfing(cs[-2], cs[-1])),
    ("engulfing_bear",    "Bearish Engulfing",       "bearish", 2,
     lambda cs, a: _is_bearish_engulfing(cs[-2], cs[-1])),
    ("piercing",          "Piercing Line",           "bullish", 2,
     lambda cs, a: _is_piercing(cs[-2], cs[-1])),
    ("dark_cloud",        "Dark Cloud Cover",        "bearish", 2,
     lambda cs, a: _is_dark_cloud(cs[-2], cs[-1])),
    ("tweezer_bottom",    "Tweezer Bottom",          "bullish", 2,
     lambda cs, a: _is_tweezer_bottom(cs[-2], cs[-1])),
    ("tweezer_top",       "Tweezer Top",             "bearish", 2,
     lambda cs, a: _is_tweezer_top(cs[-2], cs[-1])),
    ("morning_star",      "Morning Star",            "bullish", 3,
     lambda cs, a: _is_morning_star(cs[-3], cs[-2], cs[-1])),
    ("evening_star",      "Evening Star",            "bearish", 3,
     lambda cs, a: _is_evening_star(cs[-3], cs[-2], cs[-1])),
    ("three_white",       "Three White Soldiers",    "bullish", 3,
     lambda cs, a: _is_three_white_soldiers(cs[-3], cs[-2], cs[-1])),
    ("three_black",       "Three Black Crows",       "bearish", 3,
     lambda cs, a: _is_three_black_crows(cs[-3], cs[-2], cs[-1])),
    ("three_line_bull",   "Three-Line Strike (Bull)","bullish", 4,
     lambda cs, a: _is_three_line_strike_bull(cs[-4], cs[-3], cs[-2], cs[-1])),
    ("three_line_bear",   "Three-Line Strike (Bear)","bearish", 4,
     lambda cs, a: _is_three_line_strike_bear(cs[-4], cs[-3], cs[-2], cs[-1])),
]


@dataclass
class DetectedPattern:
    id: str
    name: str
    direction: str  # "bullish" | "bearish" | "neutral"
    icon: str = ""
    # Historical outcome on this asset (computed lazily below)
    historical_wins: int = 0
    historical_total: int = 0
    historical_win_rate: Optional[float] = None
    # Confidence weight in [0, 1] — combines historical win-rate + direction agreement
    confidence: float = 0.5


_ICONS = {
    "bullish": "▲", "bearish": "▼", "neutral": "◇",
}


def detect_patterns(o: List[float], h: List[float], l: List[float],
                    c: List[float]) -> List[DetectedPattern]:
    """
    Run every pattern detector against the tail of the candle series and
    return all that fire. Order is deterministic (registry order).
    """
    candles = _to_candles(o, h, l, c)
    if not candles:
        return []
    atr_ref = _atr(candles, n=14)
    detected: List[DetectedPattern] = []
    for pid, pname, pdir, need, fn in _PATTERN_REGISTRY:
        if len(candles) < need:
            continue
        try:
            if fn(candles, atr_ref):
                detected.append(DetectedPattern(
                    id=pid, name=pname, direction=pdir,
                    icon=_ICONS[pdir],
                ))
        except Exception as e:  # defensive — one broken detector shouldn't nuke the rest
            logger.debug(f"pattern {pid} raised: {e}")
    return detected


# ---------------------------------------------------------------------------
# Historical outcome lookup — did this pattern actually predict correctly
# on this asset in the recent past?
# ---------------------------------------------------------------------------
def score_historical_outcomes(
    detected: List[DetectedPattern],
    o: List[float], h: List[float], l: List[float], c: List[float],
    lookahead_bars: int = 3,
    window_bars: int = 500,
) -> List[DetectedPattern]:
    """
    Walk BACKWARDS through the candle series (up to `window_bars`), checking
    every historical occurrence of each detected pattern and whether the
    close `lookahead_bars` later moved in the pattern's predicted direction.

    Sets `historical_wins`, `historical_total`, `historical_win_rate`, and
    `confidence` on each DetectedPattern.
    """
    candles = _to_candles(o, h, l, c)
    if not candles:
        return detected

    # For each detected pattern, replay the detector across historical windows
    for det in detected:
        entry = next((r for r in _PATTERN_REGISTRY if r[0] == det.id), None)
        if entry is None:
            continue
        _, _, direction, need, fn = entry
        wins = 0
        total = 0
        # Slide through history — exclude the very last window (that's the
        # current-fire we already counted) and require `lookahead_bars` of
        # future data to score the outcome.
        start = max(need, len(candles) - window_bars)
        end = len(candles) - lookahead_bars - 1
        for i in range(start, end):
            window = candles[i - need + 1 : i + 1]
            if len(window) < need:
                continue
            atr_ref = _atr(candles[max(0, i - 14): i + 1], n=14)
            try:
                if not fn(window, atr_ref):
                    continue
            except Exception:
                continue
            entry_close = candles[i].c
            future_close = candles[i + lookahead_bars].c
            went_up = future_close > entry_close
            went_down = future_close < entry_close
            total += 1
            if direction == "bullish" and went_up:
                wins += 1
            elif direction == "bearish" and went_down:
                wins += 1
            elif direction == "neutral":
                # For a doji-like neutral pattern, "win" is 'either direction
                # decisively' — measure absolute move against ATR at the entry
                atr_at = _atr(candles[max(0, i - 14): i + 1], n=14) or 1e-9
                if abs(future_close - entry_close) > 0.6 * atr_at:
                    wins += 1
        det.historical_wins = wins
        det.historical_total = total
        det.historical_win_rate = (wins / total) if total > 0 else None
        # Confidence blends historical win-rate with a sample-size penalty
        if total >= 10 and det.historical_win_rate is not None:
            wr = det.historical_win_rate
            sample_conf = min(1.0, total / 30.0)  # full weight at 30+ samples
            det.confidence = round(wr * sample_conf + 0.5 * (1 - sample_conf), 3)
        else:
            det.confidence = 0.5  # no data → neutral
    return detected


# ---------------------------------------------------------------------------
# Behavioural summary — plain-English narrative for the last 3-5 candles.
# ---------------------------------------------------------------------------
def build_behavioural_summary(
    o: List[float], h: List[float], l: List[float], c: List[float],
    detected: List[DetectedPattern],
) -> Dict[str, Any]:
    candles = _to_candles(o, h, l, c)
    if len(candles) < 3:
        return {
            "narrative": "Not enough data to describe recent behaviour.",
            "trend_last_5": "unknown",
            "volatility": "unknown",
            "momentum": "unknown",
        }

    last5 = candles[-5:] if len(candles) >= 5 else candles
    bulls = sum(1 for c in last5 if c.is_bull)
    bears = sum(1 for c in last5 if c.is_bear)
    trend = "bullish" if bulls > bears else "bearish" if bears > bulls else "sideways"

    atr_now = _atr(candles[-14:], n=14)
    atr_hist = _atr(candles[-100:] if len(candles) >= 100 else candles, n=14)
    if atr_hist > 0:
        vol_ratio = atr_now / atr_hist
        if vol_ratio > 1.4:
            volatility = "elevated"
        elif vol_ratio < 0.6:
            volatility = "compressed"
        else:
            volatility = "normal"
    else:
        volatility = "unknown"

    # Momentum — direction of the last close vs the SMA(5) of closes
    if len(candles) >= 6:
        sma5_prev = sum(c.c for c in candles[-6:-1]) / 5.0
        last_close = candles[-1].c
        if last_close > sma5_prev * 1.001:
            momentum = "accelerating up"
        elif last_close < sma5_prev * 0.999:
            momentum = "accelerating down"
        else:
            momentum = "flat"
    else:
        momentum = "unknown"

    # Compose narrative
    pattern_names = [d.name for d in detected[:2]]
    if pattern_names:
        pat_str = " and ".join(pattern_names)
        narrative = (
            f"Last 5 candles: {bulls} bull / {bears} bear, {trend} bias. "
            f"Volatility {volatility}, momentum {momentum}. "
            f"Pattern signal: {pat_str}."
        )
    else:
        narrative = (
            f"Last 5 candles: {bulls} bull / {bears} bear, {trend} bias. "
            f"Volatility {volatility}, momentum {momentum}. "
            f"No classic pattern fired — trade on indicator confluence only."
        )
    return {
        "narrative": narrative,
        "trend_last_5": trend,
        "volatility": volatility,
        "momentum": momentum,
        "bull_count_last_5": bulls,
        "bear_count_last_5": bears,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def analyze(
    o: List[float], h: List[float], l: List[float], c: List[float],
    lookahead_bars: int = 3,
    window_bars: int = 500,
) -> Dict[str, Any]:
    """
    One-shot: detect + historical-score + narrative. Returns a plain dict
    ready to embed in the /signals/force-generate-v2 response.
    """
    detected = detect_patterns(o, h, l, c)
    detected = score_historical_outcomes(
        detected, o, h, l, c,
        lookahead_bars=lookahead_bars, window_bars=window_bars,
    )
    summary = build_behavioural_summary(o, h, l, c, detected)

    # Aggregate direction bias (weighted by confidence)
    bull_score = sum(d.confidence for d in detected if d.direction == "bullish")
    bear_score = sum(d.confidence for d in detected if d.direction == "bearish")
    total_w = bull_score + bear_score
    if total_w > 0:
        pattern_bias = "bullish" if bull_score > bear_score else "bearish"
        pattern_bias_strength = round(abs(bull_score - bear_score) / total_w, 3)
    else:
        pattern_bias = "neutral"
        pattern_bias_strength = 0.0

    return {
        "patterns": [
            {
                "id": d.id, "name": d.name, "direction": d.direction, "icon": d.icon,
                "historical_win_rate": d.historical_win_rate,
                "historical_wins": d.historical_wins,
                "historical_total": d.historical_total,
                "confidence": d.confidence,
            }
            for d in detected
        ],
        "pattern_count": len(detected),
        "pattern_bias": pattern_bias,
        "pattern_bias_strength": pattern_bias_strength,
        "behavioural_summary": summary,
        "lookahead_bars": lookahead_bars,
        "window_bars": window_bars,
    }
