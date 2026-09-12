"""Iter 137 — Chart-Pattern Detection Suite.

Ports the pattern-recognition ideas from the PocketOption research links:
- Head & Shoulders (classic + inverse) with neckline + measured-move target
- Rising / Falling Wedge (converging trend lines + volume-fade check)
- Break & Retest (S/R break followed by rejection on retest)
- Gap (opening / candle gap vs ATR)

Each detector consumes a normalised OHLCV pandas DataFrame and returns a
list of `PatternHit` dicts. Hits feed the Confluence Engine as high-weight
signals.

Design notes
------------
* Everything is pure-python / numpy so it runs in-process alongside the
  existing indicators. No new heavy deps.
* Swing points come from a small ZigZag detector (percent + bar-window
  filter). This is the shared building block for H&S and Wedge.
* All detectors are STATELESS — pass the DataFrame in, get hits out. State
  belongs to the caller (confluence engine, backtester, live scanner).
* Confidence is deliberately bounded to [0.0, 1.0] so it composes cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class PatternHit:
    """Single pattern detection with entry/stop/target hints."""

    pattern: str            # e.g. "head_and_shoulders", "rising_wedge"
    direction: str          # "CALL" (bullish) | "PUT" (bearish) | "NEUTRAL"
    confidence: float       # [0, 1]
    entry: Optional[float]  # suggested entry price (nullable)
    stop: Optional[float]
    target: Optional[float]
    anchor_bar: int         # bar index (last bar or breakout bar)
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ZigZag swing points (shared building block)
# ---------------------------------------------------------------------------

def find_swings(
    df: pd.DataFrame,
    left: int = 2,
    right: int = 2,
) -> List[Dict[str, Any]]:
    """Return swing highs/lows using a pivot filter.

    A bar at index ``i`` is a swing-high iff its ``high`` is strictly
    greater than every ``high`` in the ``left`` bars before and the
    ``right`` bars after. Analogous rule for swing-lows on ``low``.
    """
    if len(df) < left + right + 1:
        return []
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    swings: List[Dict[str, Any]] = []
    for i in range(left, n - right):
        # Strict on the RIGHT (no equal or higher bar in the next `right`
        # bars) so we always pick the FIRST occurrence of a flat top/bottom
        # and later ties don't produce duplicate swings.
        window_h_left = highs[i - left : i]
        window_h_right = highs[i + 1 : i + right + 1]
        window_l_left = lows[i - left : i]
        window_l_right = lows[i + 1 : i + right + 1]
        is_high = (
            (len(window_h_left) == 0 or highs[i] >= window_h_left.max())
            and (len(window_h_right) == 0 or highs[i] > window_h_right.max())
        )
        is_low = (
            (len(window_l_left) == 0 or lows[i] <= window_l_left.min())
            and (len(window_l_right) == 0 or lows[i] < window_l_right.min())
        )
        if is_high and not is_low:
            swings.append({"idx": int(i), "price": float(highs[i]), "kind": "H"})
        elif is_low and not is_high:
            swings.append({"idx": int(i), "price": float(lows[i]), "kind": "L"})
    return swings


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    """Simple ATR — used to normalise thresholds across assets."""
    if len(df) < period + 1:
        return float(df["high"].sub(df["low"]).mean() or 1e-6)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1] or 1e-6)


# ---------------------------------------------------------------------------
# 1. Head & Shoulders (classic + inverse)
# ---------------------------------------------------------------------------

def detect_head_and_shoulders(
    df: pd.DataFrame,
    tolerance: float = 0.05,
    left: int = 2,
    right: int = 2,
) -> List[PatternHit]:
    """Detect H&S and inverse-H&S using the last 3 same-kind swings.

    Classic (bearish):
        Left-Shoulder H  →  Head H  →  Right-Shoulder H
        head > both shoulders; shoulders within ``tolerance`` of each other.
        neckline = the two intervening swing-Lows.
        Trigger: last close breaks below neckline.

    Inverse (bullish): mirror on swing-Lows.
    """
    swings = find_swings(df, left=left, right=right)
    if len(swings) < 5:
        return []

    hits: List[PatternHit] = []
    highs = [s for s in swings if s["kind"] == "H"]
    lows = [s for s in swings if s["kind"] == "L"]
    last_close = float(df["close"].iloc[-1])

    # --- Classic bearish ---
    if len(highs) >= 3 and len(lows) >= 2:
        ls, hd, rs = highs[-3], highs[-2], highs[-1]
        # find the two lows between them
        between_lows = [l for l in lows if ls["idx"] < l["idx"] < rs["idx"]]
        if (
            hd["price"] > ls["price"]
            and hd["price"] > rs["price"]
            and abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"]) < tolerance
            and len(between_lows) >= 2
        ):
            neckline = (between_lows[0]["price"] + between_lows[-1]["price"]) / 2
            broken = last_close < neckline
            head_height = hd["price"] - neckline
            confidence = 0.55
            if broken:
                confidence += 0.25
            # shoulder-symmetry bonus
            sym = 1 - abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"])
            confidence += 0.20 * sym
            confidence = min(0.95, confidence)
            hits.append(
                PatternHit(
                    pattern="head_and_shoulders",
                    direction="PUT" if broken else "NEUTRAL",
                    confidence=confidence,
                    entry=neckline if broken else None,
                    stop=rs["price"],
                    target=neckline - head_height if broken else None,
                    anchor_bar=len(df) - 1,
                    meta={
                        "left_shoulder": ls,
                        "head": hd,
                        "right_shoulder": rs,
                        "neckline": neckline,
                        "broken": broken,
                        "head_height": head_height,
                    },
                )
            )

    # --- Inverse bullish ---
    if len(lows) >= 3 and len(highs) >= 2:
        ls, hd, rs = lows[-3], lows[-2], lows[-1]
        between_highs = [h for h in highs if ls["idx"] < h["idx"] < rs["idx"]]
        if (
            hd["price"] < ls["price"]
            and hd["price"] < rs["price"]
            and abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"]) < tolerance
            and len(between_highs) >= 2
        ):
            neckline = (between_highs[0]["price"] + between_highs[-1]["price"]) / 2
            broken = last_close > neckline
            head_depth = neckline - hd["price"]
            confidence = 0.55
            if broken:
                confidence += 0.25
            sym = 1 - abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"])
            confidence += 0.20 * sym
            confidence = min(0.95, confidence)
            hits.append(
                PatternHit(
                    pattern="inverse_head_and_shoulders",
                    direction="CALL" if broken else "NEUTRAL",
                    confidence=confidence,
                    entry=neckline if broken else None,
                    stop=rs["price"],
                    target=neckline + head_depth if broken else None,
                    anchor_bar=len(df) - 1,
                    meta={
                        "left_shoulder": ls,
                        "head": hd,
                        "right_shoulder": rs,
                        "neckline": neckline,
                        "broken": broken,
                        "head_depth": head_depth,
                    },
                )
            )

    return hits


# ---------------------------------------------------------------------------
# 2. Rising / Falling Wedge
# ---------------------------------------------------------------------------

def _fit_line(idxs: List[int], prices: List[float]) -> Tuple[float, float]:
    """Least-squares slope + intercept."""
    xs = np.asarray(idxs, dtype=float)
    ys = np.asarray(prices, dtype=float)
    if len(xs) < 2 or xs.std() == 0:
        return 0.0, float(ys.mean()) if len(ys) else 0.0
    slope, intercept = np.polyfit(xs, ys, 1)
    return float(slope), float(intercept)


def detect_wedge(
    df: pd.DataFrame,
    min_touches: int = 2,
    left: int = 2,
    right: int = 2,
) -> List[PatternHit]:
    """Detect rising/falling wedges from the last swing highs and lows.

    * Rising wedge: both trend lines slope UP, upper slope < lower slope (converging).
      Bearish break on the LOWER line.
    * Falling wedge: both slopes DOWN, upper slope > lower slope (converging).
      Bullish break on the UPPER line.

    Volume-fade bonus is applied if pandas Series `volume` is present and the
    mean of the last 20% of the wedge is < mean of the first 20%.
    """
    swings = find_swings(df, left=left, right=right)
    highs = [s for s in swings if s["kind"] == "H"][-4:]
    lows = [s for s in swings if s["kind"] == "L"][-4:]
    if len(highs) < min_touches or len(lows) < min_touches:
        return []

    upper_slope, upper_int = _fit_line([h["idx"] for h in highs], [h["price"] for h in highs])
    lower_slope, lower_int = _fit_line([l["idx"] for l in lows], [l["price"] for l in lows])

    last_idx = len(df) - 1
    last_close = float(df["close"].iloc[-1])
    # Evaluate the wedge lines at the LAST SWING index (not the tail of the
    # frame). Wedges often break near or past the apex where the two lines
    # cross — evaluating at the tail would return degenerate values.
    ref_idx = max(highs[-1]["idx"], lows[-1]["idx"])
    upper_ref = upper_slope * ref_idx + upper_int
    lower_ref = lower_slope * ref_idx + lower_int
    # Also compute the current values so we can still detect the break.
    upper_now = upper_slope * last_idx + upper_int
    lower_now = lower_slope * last_idx + lower_int
    if upper_ref <= lower_ref:
        return []  # degenerate — the fitted lines never form a valid wedge

    hits: List[PatternHit] = []
    # width of the wedge — measured at the last swing (before apex crossing)
    wedge_width = max(0.0, upper_ref - lower_ref)

    # --- Rising wedge (bearish): both slopes positive, converging (upper < lower) ---
    if upper_slope > 0 and lower_slope > 0 and upper_slope < lower_slope:
        broken = last_close < lower_now
        confidence = 0.50
        if broken:
            confidence += 0.25
        # convergence quality — how much the range has narrowed vs pattern start
        first_idx = min(highs[0]["idx"], lows[0]["idx"])
        start_width = (upper_slope * first_idx + upper_int) - (lower_slope * first_idx + lower_int)
        if start_width > 0:
            narrowing = 1 - min(1.0, wedge_width / start_width)
            confidence += 0.20 * narrowing
        # volume fade bonus
        if "volume" in df.columns and len(df) >= 20:
            v = df["volume"].astype(float)
            head_mean = v.iloc[: max(1, len(v) // 5)].mean()
            tail_mean = v.iloc[-max(1, len(v) // 5):].mean()
            if head_mean > 0 and tail_mean < head_mean:
                confidence += 0.10 * (1 - tail_mean / head_mean)
        confidence = min(0.95, confidence)
        hits.append(
            PatternHit(
                pattern="rising_wedge",
                direction="PUT" if broken else "NEUTRAL",
                confidence=confidence,
                entry=lower_now if broken else None,
                stop=upper_ref,
                target=lower_now - wedge_width if broken else None,
                anchor_bar=last_idx,
                meta={
                    "upper_slope": upper_slope,
                    "lower_slope": lower_slope,
                    "upper_now": upper_now,
                    "lower_now": lower_now,
                    "broken": broken,
                    "touches_high": len(highs),
                    "touches_low": len(lows),
                },
            )
        )

    # --- Falling wedge (bullish): both slopes negative, converging (upper more negative) ---
    if upper_slope < 0 and lower_slope < 0 and upper_slope < lower_slope:
        broken = last_close > upper_now
        confidence = 0.50
        if broken:
            confidence += 0.25
        first_idx = min(highs[0]["idx"], lows[0]["idx"])
        start_width = (upper_slope * first_idx + upper_int) - (lower_slope * first_idx + lower_int)
        if start_width > 0:
            narrowing = 1 - min(1.0, wedge_width / start_width)
            confidence += 0.20 * narrowing
        if "volume" in df.columns and len(df) >= 20:
            v = df["volume"].astype(float)
            head_mean = v.iloc[: max(1, len(v) // 5)].mean()
            tail_mean = v.iloc[-max(1, len(v) // 5):].mean()
            if head_mean > 0 and tail_mean < head_mean:
                confidence += 0.10 * (1 - tail_mean / head_mean)
        confidence = min(0.95, confidence)
        hits.append(
            PatternHit(
                pattern="falling_wedge",
                direction="CALL" if broken else "NEUTRAL",
                confidence=confidence,
                entry=upper_now if broken else None,
                stop=lower_ref,
                target=upper_now + wedge_width if broken else None,
                anchor_bar=last_idx,
                meta={
                    "upper_slope": upper_slope,
                    "lower_slope": lower_slope,
                    "upper_now": upper_now,
                    "lower_now": lower_now,
                    "broken": broken,
                    "touches_high": len(highs),
                    "touches_low": len(lows),
                },
            )
        )

    return hits


# ---------------------------------------------------------------------------
# 3. Break & Retest
# ---------------------------------------------------------------------------

def detect_break_and_retest(
    df: pd.DataFrame,
    lookback: int = 50,
    retest_bars: int = 12,
    tolerance_atr: float = 0.5,
) -> List[PatternHit]:
    """Detect a horizontal S/R break followed by a rejection retest.

    Method:
        1. Pick the highest-high and lowest-low over ``lookback`` bars.
        2. If a bar between then and now closed above the resistance
           (break-up) or below the support (break-down), remember it.
        3. Within the next ``retest_bars`` bars, price must come back
           to within ``tolerance_atr`` ATRs of the broken level AND fail
           to reclose beyond it — that's the retest.
        4. The last bar's close, on the correct side of the level, fires
           the pattern in that direction.
    """
    if len(df) < lookback + retest_bars + 2:
        return []

    hits: List[PatternHit] = []
    atr = _atr(df, period=14)
    tol = atr * tolerance_atr

    # Level = max/min of the "structure window" that precedes the possible break
    struct = df.iloc[-lookback - retest_bars - 2 : -retest_bars - 2]
    if len(struct) < 5:
        return []
    resistance = float(struct["high"].max())
    support = float(struct["low"].min())

    recent = df.iloc[-retest_bars - 2 :]
    last_close = float(df["close"].iloc[-1])

    # --- Resistance broken & retested from above ---
    breakup_bar = None
    for i, row in enumerate(recent.itertuples()):
        if row.close > resistance:
            breakup_bar = i
            break
    if breakup_bar is not None:
        after = recent.iloc[breakup_bar + 1 :]
        touched = (after["low"] <= resistance + tol).any()
        held = bool(after["close"].iloc[-1] > resistance) if len(after) else False
        if touched and held and last_close > resistance:
            hits.append(
                PatternHit(
                    pattern="break_and_retest_up",
                    direction="CALL",
                    confidence=min(0.90, 0.60 + 0.10 * len(after)),
                    entry=resistance + tol,
                    stop=resistance - tol,
                    target=resistance + (resistance - support),
                    anchor_bar=len(df) - 1,
                    meta={
                        "level": resistance,
                        "atr": atr,
                        "retest_bars": int(len(after)),
                    },
                )
            )

    # --- Support broken & retested from below ---
    breakdown_bar = None
    for i, row in enumerate(recent.itertuples()):
        if row.close < support:
            breakdown_bar = i
            break
    if breakdown_bar is not None:
        after = recent.iloc[breakdown_bar + 1 :]
        touched = (after["high"] >= support - tol).any()
        held = bool(after["close"].iloc[-1] < support) if len(after) else False
        if touched and held and last_close < support:
            hits.append(
                PatternHit(
                    pattern="break_and_retest_down",
                    direction="PUT",
                    confidence=min(0.90, 0.60 + 0.10 * len(after)),
                    entry=support - tol,
                    stop=support + tol,
                    target=support - (resistance - support),
                    anchor_bar=len(df) - 1,
                    meta={
                        "level": support,
                        "atr": atr,
                        "retest_bars": int(len(after)),
                    },
                )
            )

    return hits


# ---------------------------------------------------------------------------
# 4. Gap detection
# ---------------------------------------------------------------------------

def detect_gap(df: pd.DataFrame, min_gap_atr: float = 1.0) -> List[PatternHit]:
    """Detect the most recent significant open-vs-prev-close gap.

    Trades the gap-fill direction: gap-up → PUT (expect fade back),
    gap-down → CALL. This is the classic "gap-fill" playbook — deliberately
    simple. For continuation setups, invert in the confluence layer.
    """
    if len(df) < 20:
        return []
    atr = _atr(df, period=14)
    if atr <= 0:
        return []

    last = df.iloc[-1]
    prev = df.iloc[-2]
    gap = float(last["open"]) - float(prev["close"])
    if abs(gap) < min_gap_atr * atr:
        return []

    magnitude = min(1.0, abs(gap) / (2 * atr))  # scales 0.5→full at 2×ATR
    direction = "PUT" if gap > 0 else "CALL"
    hit = PatternHit(
        pattern="gap_fill",
        direction=direction,
        confidence=min(0.85, 0.50 + 0.35 * magnitude),
        entry=float(last["open"]),
        stop=float(last["open"]) + (0.5 * atr if gap > 0 else -0.5 * atr),
        target=float(prev["close"]),
        anchor_bar=len(df) - 1,
        meta={
            "gap_size": gap,
            "gap_atr_multiple": abs(gap) / atr,
            "atr": atr,
        },
    )
    return [hit]


# ---------------------------------------------------------------------------
# Public entry point: run all detectors
# ---------------------------------------------------------------------------

def detect_all(df: pd.DataFrame) -> List[PatternHit]:
    """Run every detector and return the merged hit list."""
    if df is None or len(df) == 0:
        return []
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return []
    hits: List[PatternHit] = []
    hits.extend(detect_head_and_shoulders(df))
    hits.extend(detect_wedge(df))
    hits.extend(detect_break_and_retest(df))
    hits.extend(detect_gap(df))
    return hits
