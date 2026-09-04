"""
Iter 120 — Ridicolous Breakout Prediction (Pine-script port) regression.

Verifies:
  A) Strategy loads into registry + is executable
  B) generate_signal returns the shape all other 1m strategies do
  C) A synthetic dataset with strong "green → new high" bias emits CALL
  D) A synthetic dataset with strong "red → new low" bias emits PUT
  E) Insufficient history returns NEUTRAL (no lookahead-crash)
  F) /api/tampermonkey/strategies?timeframe=1m exposes the new entry
"""

import re
import sys
import os

import numpy as np
import pandas as pd
import pytest
import httpx


sys.path.insert(0, "/app/backend")

from strategies.strategy_ridicolous_breakout import (  # noqa: E402
    RidicolousBreakoutPrediction,
    ridicolous_breakout_prediction,
)


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mk_candles_bull_after_green(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Every green candle is followed by a new-high candle. Every red candle
    is followed by a new-low candle. Perfectly aligned prior → both
    conditional probabilities are 100% and the LAST candle drives direction.
    """
    rng = np.random.default_rng(seed)
    rows = []
    price = 100.0
    prev_color = None
    for i in range(n):
        # alternate colors deterministically so both green/red buckets fill
        if i == 0:
            color = "GREEN"
        elif prev_color == "GREEN":
            # After green → make a NEW HIGH candle. Force high > prev_high + big step.
            color = rng.choice(["GREEN", "RED"], p=[0.5, 0.5])
        elif prev_color == "RED":
            color = rng.choice(["GREEN", "RED"], p=[0.5, 0.5])
        else:
            color = "GREEN"

        # Base body
        if color == "GREEN":
            open_p = price
            close_p = price + 0.5
        else:
            open_p = price
            close_p = price - 0.5

        high_p = max(open_p, close_p) + 0.05
        low_p = min(open_p, close_p) - 0.05

        # If PREVIOUS was GREEN → this candle makes a NEW HIGH >> prev_high + 1%
        if prev_color == "GREEN" and rows:
            prev_high = rows[-1]["high"]
            high_p = prev_high + price * 0.02  # +2%, well past the 1% step level 0
            close_p = max(close_p, high_p - 0.02)
        # If PREVIOUS was RED → this candle makes a NEW LOW << prev_low - 1%
        if prev_color == "RED" and rows:
            prev_low = rows[-1]["low"]
            low_p = prev_low - price * 0.02
            close_p = min(close_p, low_p + 0.02)

        rows.append({
            "open": open_p, "high": high_p, "low": low_p, "close": close_p,
        })
        price = close_p
        prev_color = color
    return pd.DataFrame(rows)


def _force_last_color(df: pd.DataFrame, color: str) -> pd.DataFrame:
    """Rewrite the last row so its color matches `color` without breaking prior stats."""
    df = df.copy()
    last = df.iloc[-1].copy()
    if color == "GREEN":
        last["open"] = last["close"] - 0.5
    else:
        last["open"] = last["close"] + 0.5
    last["high"] = max(last["open"], last["close"]) + 0.05
    last["low"] = min(last["open"], last["close"]) - 0.05
    df.iloc[-1] = last
    return df


# ---------------------------------------------------------------------------
# A) Registry + executable
# ---------------------------------------------------------------------------
def test_a_registry_loads_strategy():
    from strategy_registry import strategy_registry
    s = strategy_registry.get_strategy("ridicolous_breakout_prediction")
    assert s is not None
    assert s.timeframe == "1m"
    assert "ridicolous" in s.name.lower()


def test_a_executable_via_registry():
    from strategy_registry import strategy_registry
    df = _mk_candles_bull_after_green(n=200)
    result = strategy_registry.execute_strategy("ridicolous_breakout_prediction", df)
    assert result is not None
    assert result["strategy"] == ridicolous_breakout_prediction.name
    assert result["direction"] in ("CALL", "PUT", "NEUTRAL")


# ---------------------------------------------------------------------------
# B) Signal shape
# ---------------------------------------------------------------------------
def test_b_signal_shape():
    df = _mk_candles_bull_after_green(n=200)
    sig = ridicolous_breakout_prediction.generate_signal(df)
    for k in ("direction", "confidence", "reason", "strategy",
              "timeframe", "indicators", "meta"):
        assert k in sig, f"missing key {k}"
    assert sig["timeframe"] == "1m"
    assert isinstance(sig["confidence"], (int, float))
    assert 0 <= sig["confidence"] <= 99


# ---------------------------------------------------------------------------
# C) Bullish bias — last candle GREEN in a "green→new-high" world → CALL
# ---------------------------------------------------------------------------
def test_c_bullish_after_green_yields_call():
    df = _mk_candles_bull_after_green(n=250)
    df = _force_last_color(df, "GREEN")
    sig = ridicolous_breakout_prediction.generate_signal(df)
    # With green → new-high always, hh_pct_lvl0 should dominate
    assert sig["direction"] == "CALL", (
        f"expected CALL got {sig['direction']} · reason={sig['reason']} "
        f"indicators={sig['indicators']}"
    )
    assert sig["meta"]["bias"] == "BULLISH"
    assert sig["indicators"]["last_candle_color"] == "GREEN"


# ---------------------------------------------------------------------------
# D) Bearish bias — last candle RED in a "red→new-low" world → PUT
# ---------------------------------------------------------------------------
def test_d_bearish_after_red_yields_put():
    df = _mk_candles_bull_after_green(n=250)
    df = _force_last_color(df, "RED")
    sig = ridicolous_breakout_prediction.generate_signal(df)
    assert sig["direction"] == "PUT", (
        f"expected PUT got {sig['direction']} · reason={sig['reason']} "
        f"indicators={sig['indicators']}"
    )
    assert sig["meta"]["bias"] == "BEARISH"
    assert sig["indicators"]["last_candle_color"] == "RED"


# ---------------------------------------------------------------------------
# E) Not enough history → NEUTRAL (no crash)
# ---------------------------------------------------------------------------
def test_e_insufficient_history_neutral():
    df = _mk_candles_bull_after_green(n=10)
    sig = ridicolous_breakout_prediction.generate_signal(df)
    assert sig["direction"] == "NEUTRAL"
    assert "insufficient" in sig["reason"].lower()


def test_e_missing_ohlc_column_neutral():
    df = pd.DataFrame({"close": [1.0] * 100})
    sig = ridicolous_breakout_prediction.generate_signal(df)
    assert sig["direction"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# F) Endpoint exposes the strategy
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f_endpoint_lists_strategy_for_1m():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/tampermonkey/strategies", params={"timeframe": "1m"})
    assert r.status_code == 200
    body = r.json()
    strategies = body.get("strategies") or body.get("data") or []
    ids = [s.get("id") for s in strategies]
    assert "ridicolous_breakout_prediction" in ids


# ---------------------------------------------------------------------------
# G) Min confidence gate
# ---------------------------------------------------------------------------
def test_g_min_confidence_gate_forces_neutral():
    """A random-walk dataset should not clear the 55% min-confidence gate."""
    rng = np.random.default_rng(7)
    n = 250
    rets = rng.normal(0, 0.001, size=n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0.0, 0.05, size=n)
    low = np.minimum(open_, close) - rng.uniform(0.0, 0.05, size=n)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})

    strat = RidicolousBreakoutPrediction(perc=1.0, levels=5, min_history=60, min_confidence=90.0)
    sig = strat.generate_signal(df)
    # With a very high gate (90%) on random-walk data, we should abstain.
    assert sig["direction"] == "NEUTRAL"
    assert "min_confidence" in sig["reason"] or "below" in sig["reason"].lower()
