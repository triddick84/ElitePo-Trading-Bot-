"""
Elite Screener Service — Iter 109 (Feb 2026)

Proprietary composite indicator combining Smart Money Concepts (SMC)
techniques with microstructure signals into a single "Elite Score" (0-100).

Sub-scores (each 0-100):
  1. smt_score      — Smart Money Trap (false-breakout + Fib 0.618-1.0 retrace)
  2. sweep_score    — Liquidity Sweep (swing sweep + rejection wick + close-back)
  3. atr_band_score — ICT AI ATR-band mean-reversion signal strength
  4. ob_fvg_score   — Order-Block / Fair-Value-Gap proximity
  5. micro_score    — Kyle λ + Glosten-Milgrom adverse-selection health

Combined elite_score = weighted sum of the sub-scores, capped [0,100].
Direction (CALL / PUT / NEUTRAL) is derived from the majority sub-score bias.

Pure numpy — no scipy / statsmodels / TA-Lib. Safe under thin data (returns
"insufficient_data" with neutral values rather than raising).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weights — carefully tuned so no single sub-score dominates. Sum = 1.0.
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "smt":      0.24,   # false-breakout traps are strong reversal fuel
    "sweep":    0.22,   # liquidity sweeps precede most reversals
    "atr_band": 0.18,   # volatility-envelope reversion — steady signal
    "ob_fvg":   0.16,   # supply/demand-zone proximity — supporting cast
    "micro":    0.20,   # institutional flow — trust when signal is toxic
}


# ---------------------------------------------------------------------------
# Sub-score primitives
# ---------------------------------------------------------------------------
def _swing_points(highs: np.ndarray, lows: np.ndarray, period: int = 5
                  ) -> Tuple[List[int], List[int]]:
    """Return indexes of swing-highs and swing-lows using a fractal window."""
    n = len(highs)
    if n < 2 * period + 1:
        return [], []
    swing_highs, swing_lows = [], []
    for i in range(period, n - period):
        window_h = highs[i - period:i + period + 1]
        window_l = lows[i - period:i + period + 1]
        if highs[i] == np.max(window_h) and np.argmax(window_h) == period:
            swing_highs.append(i)
        if lows[i] == np.min(window_l) and np.argmin(window_l) == period:
            swing_lows.append(i)
    return swing_highs, swing_lows


def score_smart_money_trap(highs: np.ndarray, lows: np.ndarray,
                           closes: np.ndarray, opens: np.ndarray
                           ) -> Tuple[float, str, Dict[str, Any]]:
    """
    Detect false breakouts of the last swing high/low + a 0.618-1.0 Fib
    retracement into the broken level within the last 5-10 bars.

    Returns (score 0-100, direction {'CALL','PUT','NEUTRAL'}, detail).
    """
    n = len(closes)
    if n < 25:
        return 0.0, "NEUTRAL", {"reason": "insufficient_data"}

    swing_h, swing_l = _swing_points(highs, lows, period=4)
    if not swing_h and not swing_l:
        return 0.0, "NEUTRAL", {"reason": "no_swings"}

    last_close = float(closes[-1])
    detail: Dict[str, Any] = {}
    score = 0.0
    direction = "NEUTRAL"

    # Look for a false breakout in the last 10 bars.
    # PUT setup: price briefly broke above a recent swing high, then closed
    # back below it. Enter on a Fib pullback back into the [0.618, 1.0] zone.
    if swing_h:
        sh_idx = swing_h[-1]
        sh_val = float(highs[sh_idx])
        # Check bars after the swing: did any bar break above and then close back?
        after = highs[sh_idx + 1:]
        if len(after) >= 2 and len(after) <= 15:
            breached = np.where(after > sh_val)[0]
            if len(breached) > 0:
                first_break = int(breached[0]) + sh_idx + 1
                # Did the close come back below sh_val within 5 bars?
                back_window = closes[first_break:first_break + 6]
                if len(back_window) > 0 and float(np.min(back_window)) < sh_val:
                    # false-breakout confirmed → measure retrace to Fib zone
                    high_after = float(np.max(highs[sh_idx:first_break + 2]))
                    low_after = float(np.min(lows[first_break:]))
                    rng = high_after - low_after
                    if rng > 0:
                        # Bearish Fib: 1.0 at high, 0.0 at low
                        fib_618 = high_after - 0.382 * rng
                        fib_100 = high_after
                        # Is the last close in [0.618, 1.0]?
                        if fib_618 <= last_close <= fib_100:
                            depth = (last_close - fib_618) / max(1e-9, fib_100 - fib_618)
                            score = 60.0 + 40.0 * depth
                            direction = "PUT"
                            detail = {
                                "type": "bearish_false_breakout",
                                "swing_high": sh_val,
                                "fib_618": fib_618, "fib_100": fib_100,
                                "retrace_depth": round(depth, 3),
                            }

    # CALL setup: mirror image, swing-low break + close-back-above + Fib retrace
    if score < 30 and swing_l:
        sl_idx = swing_l[-1]
        sl_val = float(lows[sl_idx])
        after = lows[sl_idx + 1:]
        if len(after) >= 2 and len(after) <= 15:
            breached = np.where(after < sl_val)[0]
            if len(breached) > 0:
                first_break = int(breached[0]) + sl_idx + 1
                back_window = closes[first_break:first_break + 6]
                if len(back_window) > 0 and float(np.max(back_window)) > sl_val:
                    low_after = float(np.min(lows[sl_idx:first_break + 2]))
                    high_after = float(np.max(highs[first_break:]))
                    rng = high_after - low_after
                    if rng > 0:
                        # Bullish Fib: 1.0 at low, 0.0 at high
                        fib_618 = low_after + 0.382 * rng
                        fib_100 = low_after
                        if fib_100 <= last_close <= fib_618:
                            depth = (fib_618 - last_close) / max(1e-9, fib_618 - fib_100)
                            score = 60.0 + 40.0 * depth
                            direction = "CALL"
                            detail = {
                                "type": "bullish_false_breakout",
                                "swing_low": sl_val,
                                "fib_618": fib_618, "fib_100": fib_100,
                                "retrace_depth": round(depth, 3),
                            }

    return round(min(100.0, score), 2), direction, detail


def score_liquidity_sweep(highs: np.ndarray, lows: np.ndarray,
                          closes: np.ndarray, opens: np.ndarray
                          ) -> Tuple[float, str, Dict[str, Any]]:
    """
    Detect a liquidity sweep: price wick pierces a recent swing high/low but
    the candle closes back inside the range (rejection). Confirmation from
    a doji-ish or small-body candle within the reaction zone.
    """
    n = len(closes)
    if n < 25:
        return 0.0, "NEUTRAL", {"reason": "insufficient_data"}

    swing_h, swing_l = _swing_points(highs, lows, period=5)
    last_h, last_l = float(highs[-1]), float(lows[-1])
    last_c, last_o = float(closes[-1]), float(opens[-1])
    body = abs(last_c - last_o)
    total_range = max(1e-9, last_h - last_l)
    body_pct = body / total_range  # small body → more rejection

    score = 0.0
    direction = "NEUTRAL"
    detail: Dict[str, Any] = {}

    # PUT sweep: current bar wicked ABOVE recent swing high but closed below
    if swing_h:
        recent_sh = float(np.max(highs[max(0, swing_h[-1] - 2):swing_h[-1] + 1]))
        if last_h > recent_sh and last_c < recent_sh:
            wick_size = last_h - max(last_o, last_c)
            wick_ratio = wick_size / total_range
            if wick_ratio > 0.3:
                score = 55.0 + 30.0 * wick_ratio + 15.0 * (1.0 - body_pct)
                direction = "PUT"
                detail = {
                    "type": "bearish_sweep",
                    "swept_level": recent_sh,
                    "wick_ratio": round(wick_ratio, 3),
                    "body_pct": round(body_pct, 3),
                }

    if score < 30 and swing_l:
        recent_sl = float(np.min(lows[max(0, swing_l[-1] - 2):swing_l[-1] + 1]))
        if last_l < recent_sl and last_c > recent_sl:
            wick_size = min(last_o, last_c) - last_l
            wick_ratio = wick_size / total_range
            if wick_ratio > 0.3:
                score = 55.0 + 30.0 * wick_ratio + 15.0 * (1.0 - body_pct)
                direction = "CALL"
                detail = {
                    "type": "bullish_sweep",
                    "swept_level": recent_sl,
                    "wick_ratio": round(wick_ratio, 3),
                    "body_pct": round(body_pct, 3),
                }

    return round(min(100.0, score), 2), direction, detail


def score_atr_band(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                   ma_period: int = 20, atr_period: int = 14,
                   multiplier: float = 2.0
                   ) -> Tuple[float, str, Dict[str, Any]]:
    """
    ICT AI ATR bands: MA ± multiplier·ATR. Signal when price extends beyond
    a band AND closes back inside.
    """
    n = len(closes)
    if n < ma_period + atr_period:
        return 0.0, "NEUTRAL", {"reason": "insufficient_data"}

    ma = float(np.mean(closes[-ma_period:]))
    # True Range calc
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr = float(np.mean(tr[-atr_period:]))
    if atr <= 0:
        return 0.0, "NEUTRAL", {"reason": "zero_atr"}

    upper = ma + multiplier * atr
    lower = ma - multiplier * atr
    last_c = float(closes[-1])
    last_h = float(highs[-1])
    last_l = float(lows[-1])

    score = 0.0
    direction = "NEUTRAL"
    detail: Dict[str, Any] = {
        "ma": ma, "atr": atr, "upper": upper, "lower": lower,
    }

    # PUT: last high pushed above upper band but close came back below
    if last_h > upper and last_c < upper:
        pierce = (last_h - upper) / atr  # pierce depth in ATR units
        recovery = (upper - last_c) / atr
        score = 55.0 + min(45.0, 20.0 * pierce + 20.0 * recovery)
        direction = "PUT"
        detail["signal"] = "upper_pierce_rejection"

    # CALL: last low pushed below lower band but close came back above
    elif last_l < lower and last_c > lower:
        pierce = (lower - last_l) / atr
        recovery = (last_c - lower) / atr
        score = 55.0 + min(45.0, 20.0 * pierce + 20.0 * recovery)
        direction = "CALL"
        detail["signal"] = "lower_pierce_rejection"

    return round(min(100.0, score), 2), direction, detail


def score_ob_fvg(highs: np.ndarray, lows: np.ndarray,
                 closes: np.ndarray, opens: np.ndarray
                 ) -> Tuple[float, str, Dict[str, Any]]:
    """
    Detect proximity to an unmitigated Fair Value Gap (3-candle imbalance)
    or Order Block (last opposing candle before a strong impulse).

    FVG bullish: high[i-2] < low[i]  → gap between them
    FVG bearish: low[i-2] > high[i]
    """
    n = len(closes)
    if n < 20:
        return 0.0, "NEUTRAL", {"reason": "insufficient_data"}

    last_c = float(closes[-1])
    score = 0.0
    direction = "NEUTRAL"
    detail: Dict[str, Any] = {}

    # Scan last 15 bars for unmitigated FVGs
    for i in range(n - 15, n - 2):
        if i < 2:
            continue
        # Bullish FVG: 3-bar imbalance with gap up
        if highs[i - 2] < lows[i]:
            gap_lo = float(highs[i - 2])
            gap_hi = float(lows[i])
            # Unmitigated if closes since haven't dipped back into the gap
            since_lows = lows[i + 1:]
            if len(since_lows) == 0 or float(np.min(since_lows)) > gap_lo:
                # Is price now close to or inside the gap? (potential retest)
                if gap_lo <= last_c <= gap_hi + (gap_hi - gap_lo) * 0.5:
                    proximity = 1.0 - abs(last_c - (gap_lo + gap_hi) / 2) / max(1e-9, gap_hi - gap_lo)
                    proximity = max(0.0, min(1.0, proximity))
                    s = 50.0 + 40.0 * proximity
                    if s > score:
                        score = s
                        direction = "CALL"
                        detail = {"type": "bullish_fvg_retest",
                                  "gap_lo": gap_lo, "gap_hi": gap_hi,
                                  "proximity": round(proximity, 3)}
        # Bearish FVG
        if lows[i - 2] > highs[i]:
            gap_hi = float(lows[i - 2])
            gap_lo = float(highs[i])
            since_highs = highs[i + 1:]
            if len(since_highs) == 0 or float(np.max(since_highs)) < gap_hi:
                if gap_lo - (gap_hi - gap_lo) * 0.5 <= last_c <= gap_hi:
                    proximity = 1.0 - abs(last_c - (gap_lo + gap_hi) / 2) / max(1e-9, gap_hi - gap_lo)
                    proximity = max(0.0, min(1.0, proximity))
                    s = 50.0 + 40.0 * proximity
                    if s > score:
                        score = s
                        direction = "PUT"
                        detail = {"type": "bearish_fvg_retest",
                                  "gap_lo": gap_lo, "gap_hi": gap_hi,
                                  "proximity": round(proximity, 3)}

    return round(min(100.0, score), 2), direction, detail


def score_microstructure(kyle_result: Optional[Dict[str, Any]],
                         gm_result: Optional[Dict[str, Any]]
                         ) -> Tuple[float, str, Dict[str, Any]]:
    """
    Score based on the Kyle / GM outputs already computed by Iter 105.

    Healthy microstructure (low λ, low adverse selection) → HIGH score, meaning
    it's SAFE to trade this asset. Toxic flow (high adverse selection) drops
    the score sharply — you're being adversely selected against.

    Direction stays NEUTRAL — microstructure is a health check, not a bias.
    """
    if not kyle_result or not kyle_result.get("success"):
        return 50.0, "NEUTRAL", {"reason": "no_kyle"}
    if not gm_result or not gm_result.get("success"):
        return 50.0, "NEUTRAL", {"reason": "no_gm"}

    illiq_bps = float(kyle_result.get("kyle", {}).get("illiquidity_bps", 0.0))
    adv_pct = float(gm_result.get("gm", {}).get("adverse_selection_pct", 50.0))

    # Illiquidity: 0-30 bps healthy, 30-100 warning, >100 toxic
    if illiq_bps <= 30.0:
        illiq_score = 100.0
    elif illiq_bps <= 100.0:
        illiq_score = 100.0 - (illiq_bps - 30.0) * (60.0 / 70.0)
    else:
        illiq_score = max(0.0, 40.0 - (illiq_bps - 100.0) * 0.4)

    # Adverse selection: 0-30% healthy, 30-60% warning, >60% toxic
    if adv_pct <= 30.0:
        adv_score = 100.0
    elif adv_pct <= 60.0:
        adv_score = 100.0 - (adv_pct - 30.0) * (60.0 / 30.0)
    else:
        adv_score = max(0.0, 40.0 - (adv_pct - 60.0) * 1.0)

    score = round((illiq_score + adv_score) / 2.0, 2)
    return score, "NEUTRAL", {
        "illiq_bps": round(illiq_bps, 2),
        "adverse_selection_pct": round(adv_pct, 2),
        "illiq_score": round(illiq_score, 2),
        "adv_score": round(adv_score, 2),
    }


# ---------------------------------------------------------------------------
# Combined Elite Score
# ---------------------------------------------------------------------------
@dataclass
class EliteScoreResult:
    asset: str
    timeframe: str
    elite_score: float
    direction: str
    sub_scores: Dict[str, float]
    sub_details: Dict[str, Any]
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    n_candles: int = 0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _combine_direction(sub_dirs: Dict[str, str],
                       sub_scores: Dict[str, float]) -> str:
    """Weighted majority vote — CALL vs PUT based on the score-weighted count."""
    call_weight = 0.0
    put_weight = 0.0
    for k, d in sub_dirs.items():
        w = sub_scores.get(k, 0.0)
        if d == "CALL":
            call_weight += w
        elif d == "PUT":
            put_weight += w
    if call_weight > put_weight * 1.15:
        return "CALL"
    if put_weight > call_weight * 1.15:
        return "PUT"
    return "NEUTRAL"


def compute_elite_score(candles: List[Dict[str, Any]],
                        asset: str,
                        timeframe: str = "1m",
                        kyle_result: Optional[Dict[str, Any]] = None,
                        gm_result: Optional[Dict[str, Any]] = None,
                        weights: Optional[Dict[str, float]] = None,
                        ) -> EliteScoreResult:
    """
    Main entry point. Computes all 5 sub-scores and combines them.
    """
    weights = weights or DEFAULT_WEIGHTS
    if not candles or len(candles) < 25:
        return EliteScoreResult(
            asset=asset, timeframe=timeframe,
            elite_score=0.0, direction="NEUTRAL",
            sub_scores={}, sub_details={},
            n_candles=len(candles) if candles else 0,
            reason="insufficient_data",
        )

    highs = np.array([float(c.get("high", c.get("close", 0.0))) for c in candles])
    lows = np.array([float(c.get("low", c.get("close", 0.0))) for c in candles])
    closes = np.array([float(c.get("close", 0.0)) for c in candles])
    opens = np.array([float(c.get("open", closes[0])) for c in candles])

    smt_s, smt_d, smt_det = score_smart_money_trap(highs, lows, closes, opens)
    sw_s, sw_d, sw_det = score_liquidity_sweep(highs, lows, closes, opens)
    atr_s, atr_d, atr_det = score_atr_band(closes, highs, lows)
    obfvg_s, obfvg_d, obfvg_det = score_ob_fvg(highs, lows, closes, opens)
    micro_s, _, micro_det = score_microstructure(kyle_result, gm_result)

    sub_scores = {
        "smt": smt_s, "sweep": sw_s, "atr_band": atr_s,
        "ob_fvg": obfvg_s, "micro": micro_s,
    }
    sub_dirs = {
        "smt": smt_d, "sweep": sw_d, "atr_band": atr_d,
        "ob_fvg": obfvg_d, "micro": "NEUTRAL",
    }
    sub_details = {
        "smt": smt_det, "sweep": sw_det, "atr_band": atr_det,
        "ob_fvg": obfvg_det, "micro": micro_det,
    }

    # Elite score = weighted sum, capped [0, 100]
    elite = sum(sub_scores[k] * weights[k] for k in sub_scores)
    elite = round(min(100.0, max(0.0, elite)), 2)

    direction = _combine_direction(sub_dirs, sub_scores)

    # Rough entry/stop/target from ATR-band details when possible
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    try:
        entry = float(closes[-1])
        atr = float(atr_det.get("atr", 0.0))
        if atr > 0 and direction in ("CALL", "PUT"):
            if direction == "CALL":
                stop = round(entry - 1.5 * atr, 6)
                target = round(entry + 2.5 * atr, 6)
            else:
                stop = round(entry + 1.5 * atr, 6)
                target = round(entry - 2.5 * atr, 6)
    except Exception:
        pass

    return EliteScoreResult(
        asset=asset, timeframe=timeframe,
        elite_score=elite, direction=direction,
        sub_scores=sub_scores, sub_details=sub_details,
        entry=entry, stop=stop, target=target,
        n_candles=int(len(candles)),
        reason="",
    )


# ---------------------------------------------------------------------------
# Async data adapter — pulls candles + microstructure per asset
# ---------------------------------------------------------------------------
async def score_asset(asset: str, timeframe: str = "1m",
                      lookback: int = 60) -> Dict[str, Any]:
    """
    Full pipeline for one asset: fetch candles → compute Kyle + GM → compute
    Elite Score. Returns a JSON-safe dict.
    """
    candles: List[Dict[str, Any]] = []
    kyle_result: Optional[Dict[str, Any]] = None
    gm_result: Optional[Dict[str, Any]] = None

    # Reuse existing microstructure fetch pipeline
    try:
        from microstructure_models import (
            kyle_for_asset, glosten_milgrom_for_asset, _fetch_recent_candles
        )
        try:
            from microstructure import microstructure  # singleton
            candles = await _fetch_recent_candles(microstructure, asset, lookback)
        except Exception as e:
            logger.debug("[elite] candle fetch fail for %s: %s", asset, e)
            candles = []

        kyle_result = await kyle_for_asset(asset, candles=candles, lookback=lookback)
        gm_result = await glosten_milgrom_for_asset(
            asset, candles=candles, lookback=lookback,
        )
    except Exception as e:
        logger.warning("[elite] microstructure fetch failed: %s", e)

    result = compute_elite_score(
        candles=candles, asset=asset, timeframe=timeframe,
        kyle_result=kyle_result, gm_result=gm_result,
    )
    return result.to_dict()


async def scan_assets(assets: List[str], timeframe: str = "1m",
                      lookback: int = 60,
                      min_score: float = 0.0) -> Dict[str, Any]:
    """Scan a list of assets in parallel — returns sorted, filtered results."""
    import asyncio
    if not assets:
        return {"success": True, "count": 0, "results": []}

    tasks = [score_asset(a.strip().upper(), timeframe=timeframe,
                         lookback=lookback) for a in assets if a and a.strip()]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: List[Dict[str, Any]] = []
    for r in raw:
        if isinstance(r, Exception):
            continue
        if r.get("elite_score", 0.0) >= min_score:
            results.append(r)

    # Sort by elite_score desc, then n_candles desc so populated rows win ties
    results.sort(key=lambda x: (-x.get("elite_score", 0.0),
                                -x.get("n_candles", 0)))
    return {"success": True, "count": len(results), "results": results}
