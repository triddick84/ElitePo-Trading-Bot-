"""Iter 139 — Smart-Money / ICT-style pattern detectors.

Adds the "retail-trap" filters the user asked for on top of the Iter 137
pattern suite:

* **Liquidity Sweep** — price pierces a prior swing high/low with a wick
  but closes BACK inside the range. Signals the FADE direction (a sweep
  above swing high → PUT; sweep below swing low → CALL).
* **Stop Hunt** — sweep of an obvious retail stop cluster (round-number
  price OR prior-session high/low OR the last-N bar extremes) followed by
  an immediate rejection candle.
* **Order Block** — the LAST opposing candle before a strong displacement
  move. Bullish OB = last bearish candle before a rally of ≥ N × ATR;
  bearish OB = last bullish candle before a drop. When price returns to
  the OB, we fire in the direction of the displacement.
* **Breaker Block** — an order block that FAILED (price closed through
  it), which then becomes flip-side S/R. Same fire logic as OB but
  inverted direction.

All detectors reuse the `PatternHit` dataclass + `find_swings` helper from
`pattern_detector.py` for consistency with Iter 137 and so hits compose
cleanly through the confluence engine (source `smart_money:*`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from pattern_detector import PatternHit, find_swings, _atr


# ---------------------------------------------------------------------------
# 1. Liquidity Sweep
# ---------------------------------------------------------------------------

def detect_liquidity_sweep(
    df: pd.DataFrame,
    lookback: int = 30,
    max_bars_since_sweep: int = 2,
) -> List[PatternHit]:
    """Detect a wick that swept the most recent swing high/low then closed back.

    Rules (bullish sweep-fade → CALL):
        * The last `max_bars_since_sweep+1` bars contain a bar whose LOW
          is below the most recent swing-LOW within `lookback` bars.
        * That same bar's CLOSE is BACK ABOVE the swing low.
        * The current bar's close is still above the swept level.

    Bearish is the mirror image.
    """
    if len(df) < 8:
        return []
    swings = find_swings(df, left=2, right=2)
    if not swings:
        return []
    # Consider ALL swings within the lookback window (not just the most
    # recent). Sweeps often target an older significant high/low, not the
    # last little pivot.
    cutoff = len(df) - max_bars_since_sweep - 1
    min_idx = max(0, len(df) - lookback - max_bars_since_sweep)
    recent_highs = [s for s in swings if s["kind"] == "H" and min_idx <= s["idx"] <= cutoff]
    recent_lows = [s for s in swings if s["kind"] == "L" and min_idx <= s["idx"] <= cutoff]

    hits: List[PatternHit] = []
    atr = _atr(df, period=14) or 1e-6
    last_close = float(df["close"].iloc[-1])
    window = df.iloc[-max_bars_since_sweep - 1 :]

    # --- Bearish sweep of a swing HIGH → PUT ---
    # Try the HIGHEST recent swing high first — that's the primary liquidity target.
    for h in sorted(recent_highs, key=lambda s: -s["price"]):
        pierced = window[(window["high"] > h["price"]) & (window["close"] < h["price"])]
        if not pierced.empty and last_close < h["price"]:
            sweep_bar = pierced.iloc[-1]
            wick_size = float(sweep_bar["high"] - h["price"])
            body_size = abs(float(sweep_bar["close"] - sweep_bar["open"]))
            conf = 0.55 + min(0.30, 0.15 * (wick_size / atr))
            if wick_size > body_size * 1.5:
                conf += 0.10
            hits.append(
                PatternHit(
                    pattern="liquidity_sweep_high",
                    direction="PUT",
                    confidence=min(0.90, conf),
                    entry=last_close,
                    stop=float(sweep_bar["high"]),
                    target=last_close - (wick_size + atr),
                    anchor_bar=len(df) - 1,
                    meta={
                        "swept_swing": h,
                        "sweep_bar_high": float(sweep_bar["high"]),
                        "sweep_bar_close": float(sweep_bar["close"]),
                        "wick_size": wick_size,
                        "atr": atr,
                    },
                )
            )
            break  # one sweep hit is enough per side

    # --- Bullish sweep of a swing LOW → CALL ---
    for l in sorted(recent_lows, key=lambda s: s["price"]):
        pierced = window[(window["low"] < l["price"]) & (window["close"] > l["price"])]
        if not pierced.empty and last_close > l["price"]:
            sweep_bar = pierced.iloc[-1]
            wick_size = float(l["price"] - sweep_bar["low"])
            body_size = abs(float(sweep_bar["close"] - sweep_bar["open"]))
            conf = 0.55 + min(0.30, 0.15 * (wick_size / atr))
            if wick_size > body_size * 1.5:
                conf += 0.10
            hits.append(
                PatternHit(
                    pattern="liquidity_sweep_low",
                    direction="CALL",
                    confidence=min(0.90, conf),
                    entry=last_close,
                    stop=float(sweep_bar["low"]),
                    target=last_close + (wick_size + atr),
                    anchor_bar=len(df) - 1,
                    meta={
                        "swept_swing": l,
                        "sweep_bar_low": float(sweep_bar["low"]),
                        "sweep_bar_close": float(sweep_bar["close"]),
                        "wick_size": wick_size,
                        "atr": atr,
                    },
                )
            )
            break

    return hits


# ---------------------------------------------------------------------------
# 2. Stop Hunt (round-number / N-bar-extreme sweep + reversal)
# ---------------------------------------------------------------------------

def _nearest_round_level(price: float, atr: float) -> Optional[float]:
    """Return the nearest 'psychological' round level within 2×ATR of price.

    Retail traders love stops at round numbers (`1.10000`, `142.50`, etc.).
    We scan common step sizes and pick the closest one.
    """
    if price <= 0:
        return None
    # Choose step size based on price magnitude
    if price < 2:
        steps = [0.001, 0.005, 0.01]         # majors like EURUSD
    elif price < 20:
        steps = [0.01, 0.05, 0.10]           # crosses like GBP-something
    elif price < 200:
        steps = [0.1, 0.5, 1.0]              # JPY pairs, indices
    else:
        steps = [1.0, 5.0, 10.0]              # commodities, high-price
    best: Optional[float] = None
    best_dist = 2 * atr
    for step in steps:
        rounded = round(price / step) * step
        dist = abs(price - rounded)
        if dist < best_dist:
            best_dist = dist
            best = rounded
    return best


def detect_stop_hunt(
    df: pd.DataFrame,
    lookback: int = 20,
    wick_atr_multiple: float = 0.8,
) -> List[PatternHit]:
    """Detect a stop hunt: bar sweeps N-bar high/low or a round level, rejects.

    Requires: wick outside the level ≥ `wick_atr_multiple × ATR` AND close
    back inside. Same fade logic as liquidity_sweep but sourced from the
    obvious retail SL zones (N-bar extremes + round numbers).
    """
    if len(df) < lookback + 2:
        return []
    atr = _atr(df, period=14) or 1e-6
    prior = df.iloc[-lookback - 1 : -1]  # excludes the current bar
    if len(prior) < lookback:
        return []
    prior_high = float(prior["high"].max())
    prior_low = float(prior["low"].min())
    last = df.iloc[-1]
    hits: List[PatternHit] = []

    # ---- Sweep of prior N-bar high ----
    if last["high"] > prior_high and last["close"] < prior_high:
        wick = float(last["high"] - prior_high)
        if wick >= wick_atr_multiple * atr:
            round_lvl = _nearest_round_level(prior_high, atr)
            near_round = round_lvl is not None and abs(prior_high - round_lvl) < 0.5 * atr
            conf = 0.60 + min(0.20, wick / atr * 0.10) + (0.10 if near_round else 0.0)
            hits.append(
                PatternHit(
                    pattern="stop_hunt_high",
                    direction="PUT",
                    confidence=min(0.90, conf),
                    entry=float(last["close"]),
                    stop=float(last["high"]),
                    target=float(last["close"]) - (wick + atr),
                    anchor_bar=len(df) - 1,
                    meta={
                        "prior_n_bar_high": prior_high,
                        "wick_size": wick,
                        "atr": atr,
                        "near_round_level": near_round,
                        "round_level": round_lvl,
                    },
                )
            )

    # ---- Sweep of prior N-bar low ----
    if last["low"] < prior_low and last["close"] > prior_low:
        wick = float(prior_low - last["low"])
        if wick >= wick_atr_multiple * atr:
            round_lvl = _nearest_round_level(prior_low, atr)
            near_round = round_lvl is not None and abs(prior_low - round_lvl) < 0.5 * atr
            conf = 0.60 + min(0.20, wick / atr * 0.10) + (0.10 if near_round else 0.0)
            hits.append(
                PatternHit(
                    pattern="stop_hunt_low",
                    direction="CALL",
                    confidence=min(0.90, conf),
                    entry=float(last["close"]),
                    stop=float(last["low"]),
                    target=float(last["close"]) + (wick + atr),
                    anchor_bar=len(df) - 1,
                    meta={
                        "prior_n_bar_low": prior_low,
                        "wick_size": wick,
                        "atr": atr,
                        "near_round_level": near_round,
                        "round_level": round_lvl,
                    },
                )
            )

    return hits


# ---------------------------------------------------------------------------
# 3. Order Block / Breaker Block
# ---------------------------------------------------------------------------

def detect_order_block(
    df: pd.DataFrame,
    displacement_atr: float = 2.0,
    lookback: int = 20,
    retest_tolerance_atr: float = 0.5,
) -> List[PatternHit]:
    """Detect the last opposing candle before a strong displacement move,
    then look for the current price REVISITING that candle's range.

    Bullish OB (fires CALL):
        * Find a run of consecutive up-candles (close > open) whose total
          displacement is ≥ `displacement_atr × ATR` — this is the "impulse".
        * The candle IMMEDIATELY before the impulse must be bearish
          (close < open). That candle is the bullish OB.
        * If the current bar's low is within `retest_tolerance_atr × ATR`
          of the OB's high AND the current close is above the OB's high,
          the bot has confirmed a retest → fire CALL.

    Bearish OB is the mirror.
    """
    if len(df) < lookback + 5:
        return []
    atr = _atr(df, period=14) or 1e-6
    hits: List[PatternHit] = []
    tol = retest_tolerance_atr * atr
    last = df.iloc[-1]
    # Scan the last `lookback` bars for impulse legs
    window = df.iloc[-lookback:].reset_index(drop=True)
    n = len(window)

    # For efficiency, group consecutive up/down runs
    i = 0
    while i < n - 1:
        # Identify a run of same-direction closes
        j = i + 1
        first_up = window["close"].iloc[i] > window["open"].iloc[i]
        while j < n and (
            (first_up and window["close"].iloc[j] > window["open"].iloc[j])
            or (not first_up and window["close"].iloc[j] < window["open"].iloc[j])
        ):
            j += 1
        run = window.iloc[i:j]
        run_disp = float(run["close"].iloc[-1] - run["open"].iloc[0])
        if abs(run_disp) >= displacement_atr * atr and i > 0:
            ob = window.iloc[i - 1]
            ob_high = float(ob["high"])
            ob_low = float(ob["low"])
            # Bullish OB — impulse UP, OB was down candle
            if first_up and float(ob["close"]) < float(ob["open"]):
                # Retest: current low touches the OB range, current close still above ob_high
                if float(last["low"]) <= ob_high + tol and float(last["close"]) > ob_low:
                    conf = 0.60 + min(0.25, abs(run_disp) / atr * 0.05)
                    hits.append(
                        PatternHit(
                            pattern="bullish_order_block",
                            direction="CALL",
                            confidence=min(0.90, conf),
                            entry=float(last["close"]),
                            stop=ob_low,
                            target=float(last["close"]) + abs(run_disp),
                            anchor_bar=len(df) - 1,
                            meta={
                                "ob_high": ob_high,
                                "ob_low": ob_low,
                                "displacement": run_disp,
                                "atr": atr,
                            },
                        )
                    )
            # Bearish OB — impulse DOWN, OB was up candle
            elif (not first_up) and float(ob["close"]) > float(ob["open"]):
                if float(last["high"]) >= ob_low - tol and float(last["close"]) < ob_high:
                    conf = 0.60 + min(0.25, abs(run_disp) / atr * 0.05)
                    hits.append(
                        PatternHit(
                            pattern="bearish_order_block",
                            direction="PUT",
                            confidence=min(0.90, conf),
                            entry=float(last["close"]),
                            stop=ob_high,
                            target=float(last["close"]) - abs(run_disp),
                            anchor_bar=len(df) - 1,
                            meta={
                                "ob_high": ob_high,
                                "ob_low": ob_low,
                                "displacement": run_disp,
                                "atr": atr,
                            },
                        )
                    )
        i = max(j, i + 1)

    # Keep only the most recent hit per direction — older OBs are stale
    unique: Dict[str, PatternHit] = {}
    for h in hits:
        unique[h.pattern] = h  # last one wins
    return list(unique.values())


def detect_breaker_block(
    df: pd.DataFrame,
    displacement_atr: float = 2.0,
    lookback: int = 30,
) -> List[PatternHit]:
    """Detect a FAILED order block that now acts as flip-side S/R.

    A breaker block is an OB that got completely traded through — its
    role flips. When price returns to the failed OB and gets rejected,
    fire in the OPPOSITE direction to the original OB.
    """
    if len(df) < 10:
        return []
    atr = _atr(df, period=14) or 1e-6
    hits: List[PatternHit] = []
    last = df.iloc[-1]
    window = df.iloc[-lookback:].reset_index(drop=True)
    n = len(window)

    i = 0
    while i < n - 1:
        j = i + 1
        first_up = window["close"].iloc[i] > window["open"].iloc[i]
        while j < n and (
            (first_up and window["close"].iloc[j] > window["open"].iloc[j])
            or (not first_up and window["close"].iloc[j] < window["open"].iloc[j])
        ):
            j += 1
        run = window.iloc[i:j]
        run_disp = float(run["close"].iloc[-1] - run["open"].iloc[0])
        if abs(run_disp) >= displacement_atr * atr and i > 0 and j < n:
            ob = window.iloc[i - 1]
            ob_high = float(ob["high"])
            ob_low = float(ob["low"])
            after = window.iloc[j:]

            # Bullish OB that later got broken DOWN → becomes bearish breaker
            if first_up and float(ob["close"]) < float(ob["open"]):
                broke_down = (after["close"] < ob_low).any()
                if broke_down and float(last["high"]) >= ob_low and float(last["close"]) < ob_low:
                    hits.append(
                        PatternHit(
                            pattern="bearish_breaker",
                            direction="PUT",
                            confidence=0.65,
                            entry=float(last["close"]),
                            stop=ob_high,
                            target=float(last["close"]) - abs(run_disp),
                            anchor_bar=len(df) - 1,
                            meta={"broken_ob_high": ob_high, "broken_ob_low": ob_low, "atr": atr},
                        )
                    )

            # Bearish OB that later got broken UP → becomes bullish breaker
            elif (not first_up) and float(ob["close"]) > float(ob["open"]):
                broke_up = (after["close"] > ob_high).any()
                if broke_up and float(last["low"]) <= ob_high and float(last["close"]) > ob_high:
                    hits.append(
                        PatternHit(
                            pattern="bullish_breaker",
                            direction="CALL",
                            confidence=0.65,
                            entry=float(last["close"]),
                            stop=ob_low,
                            target=float(last["close"]) + abs(run_disp),
                            anchor_bar=len(df) - 1,
                            meta={"broken_ob_high": ob_high, "broken_ob_low": ob_low, "atr": atr},
                        )
                    )
        i = max(j, i + 1)

    unique: Dict[str, PatternHit] = {}
    for h in hits:
        unique[h.pattern] = h
    return list(unique.values())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_all_smart_money(df: pd.DataFrame) -> List[PatternHit]:
    """Run every smart-money detector and return the merged hit list."""
    if df is None or len(df) == 0:
        return []
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return []
    hits: List[PatternHit] = []
    hits.extend(detect_liquidity_sweep(df))
    hits.extend(detect_stop_hunt(df))
    hits.extend(detect_order_block(df))
    hits.extend(detect_breaker_block(df))
    return hits
