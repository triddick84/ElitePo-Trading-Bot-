"""
Heikin-Ashi Confluence Gate (Iter 115b).

A signal must be confirmed by Heikin-Ashi candle color continuity — the last
`min_streak` HA candles must agree with the signal direction. Optional wick
strictness enforces "no opposing wick" (very strong trend).

Uses `heikin_ashi.transform_to_heikin_ashi` under the hood so we don't
duplicate the transformation math.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from heikin_ashi import transform_to_heikin_ashi


def evaluate_ha_confluence(
    candles: Sequence[Dict[str, Any]],
    signal_direction: Optional[str],
    min_streak: int = 2,
    require_no_opposing_wick: bool = False,
) -> Dict[str, Any]:
    """
    Check whether the latest HA candles agree with `signal_direction`.

    Args:
        candles: list of OHLC candle dicts, oldest first.
        signal_direction: "UP" / "CALL" / "BUY" or "DOWN" / "PUT" / "SELL".
        min_streak: how many consecutive HA candles must match the direction.
        require_no_opposing_wick: if True, the most recent HA candle must
            have no opposing wick (very strong trend).

    Returns:
        {
          gated: bool,                # True if should abstain
          reason: str,
          ha_streak: int,             # consecutive matching HA candles
          ha_color: "GREEN"|"RED"|"DOJI",
          direction_match: bool,
        }
    """
    if not candles or len(candles) < min_streak + 1:
        return {
            "gated": False,
            "reason": "insufficient_data",
            "ha_streak": 0,
            "ha_color": "NONE",
            "direction_match": False,
        }

    if not signal_direction:
        return {
            "gated": False,
            "reason": "no_direction",
            "ha_streak": 0,
            "ha_color": "NONE",
            "direction_match": False,
        }

    sig_up = str(signal_direction).lower() in ("up", "call", "buy")
    sig_down = str(signal_direction).lower() in ("down", "put", "sell")
    if not (sig_up or sig_down):
        return {
            "gated": False,
            "reason": "unknown_direction",
            "ha_streak": 0,
            "ha_color": "NONE",
            "direction_match": False,
        }

    df = pd.DataFrame(list(candles))
    for c in ("open", "high", "low", "close"):
        if c not in df.columns:
            return {
                "gated": False,
                "reason": "missing_ohlc",
                "ha_streak": 0,
                "ha_color": "NONE",
                "direction_match": False,
            }
    ha = transform_to_heikin_ashi(df.copy())

    if ha is None or ha.empty:
        return {
            "gated": False,
            "reason": "ha_transform_failed",
            "ha_streak": 0,
            "ha_color": "NONE",
            "direction_match": False,
        }

    # Compute streak from the most recent candle backwards
    streak_bull = 0
    streak_bear = 0
    for i in range(len(ha) - 1, -1, -1):
        row = ha.iloc[i]
        if row["close"] > row["open"]:
            if streak_bear > 0:
                break
            streak_bull += 1
        elif row["close"] < row["open"]:
            if streak_bull > 0:
                break
            streak_bear += 1
        else:
            break

    last = ha.iloc[-1]
    ha_color = "GREEN" if last["close"] > last["open"] else (
        "RED" if last["close"] < last["open"] else "DOJI"
    )

    if sig_up:
        direction_match = streak_bull >= min_streak
        streak_val = streak_bull
    else:
        direction_match = streak_bear >= min_streak
        streak_val = streak_bear

    # Wick strictness
    wick_ok = True
    if require_no_opposing_wick:
        body_top = max(float(last["open"]), float(last["close"]))
        body_bot = min(float(last["open"]), float(last["close"]))
        upper_wick = float(last["high"]) - body_top
        lower_wick = body_bot - float(last["low"])
        body = max(1e-10, body_top - body_bot)
        # opposing wick > 30% of body → fail
        if sig_up and lower_wick > 0.3 * body:
            wick_ok = False
        if sig_down and upper_wick > 0.3 * body:
            wick_ok = False

    gated = not direction_match or not wick_ok
    if not direction_match:
        reason = (
            f"HA streak {streak_val} < min {min_streak} "
            f"in signal direction ({ha_color} last)"
        )
    elif not wick_ok:
        reason = "HA has opposing wick > 30% of body"
    else:
        reason = "ok"

    return {
        "gated": bool(gated),
        "reason": reason,
        "ha_streak": int(streak_val),
        "ha_color": ha_color,
        "direction_match": bool(direction_match),
    }
