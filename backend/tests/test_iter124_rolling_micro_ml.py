"""
Iter 124 — Rolling Micro-ML strategy regression.

Verifies:
  A) Strategy loads into registry + is executable
  B) generate_signal returns the full signal contract
  C) Insufficient history / missing OHLC → NEUTRAL (no crash)
  D) High holdout_acc_floor → NEUTRAL even when confidence high
  E) apply_config bounds enforced
  F) Backtest endpoint works end-to-end
  G) 1m picker exposes the new strategy
"""

import re
import sys

import numpy as np
import pandas as pd
import pytest
import httpx


sys.path.insert(0, "/app/backend")

from strategies.strategy_rolling_micro_ml import (  # noqa: E402
    RollingMicroML,
    rolling_micro_ml,
)


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()


def _synth_candles(n: int = 250, seed: int = 3) -> pd.DataFrame:
    """Random walk with mild momentum bias — enough for RF to learn something."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.0015, size=n)  # mild positive drift
    close = 1.10 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[1.10], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0, 0.0005, size=n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.0005, size=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


# ---------------------------------------------------------------------------
# A) Registry load
# ---------------------------------------------------------------------------
def test_a_registry_loads():
    from strategy_registry import strategy_registry
    s = strategy_registry.get_strategy("rolling_micro_ml")
    assert s is not None
    assert s.timeframe == "1m"


def test_a_executable_via_registry():
    from strategy_registry import strategy_registry
    df = _synth_candles(250)
    result = strategy_registry.execute_strategy("rolling_micro_ml", df)
    assert result is not None
    assert result["strategy"] == rolling_micro_ml.name
    assert result["direction"] in ("CALL", "PUT", "NEUTRAL")


# ---------------------------------------------------------------------------
# B) Signal shape
# ---------------------------------------------------------------------------
def test_b_signal_shape():
    df = _synth_candles(250)
    sig = rolling_micro_ml.generate_signal(df)
    for k in ("direction", "confidence", "reason", "strategy", "timeframe", "indicators", "meta"):
        assert k in sig
    assert sig["meta"]["family"] == "ml_rolling"


# ---------------------------------------------------------------------------
# C) Robustness
# ---------------------------------------------------------------------------
def test_c_insufficient_history_neutral():
    df = _synth_candles(20)
    sig = rolling_micro_ml.generate_signal(df)
    assert sig["direction"] == "NEUTRAL"
    assert "insufficient history" in sig["reason"].lower() or "window too small" in sig["reason"].lower()


def test_c_missing_ohlc_column_neutral():
    df = pd.DataFrame({"close": [1.0] * 200})
    sig = rolling_micro_ml.generate_signal(df)
    assert sig["direction"] == "NEUTRAL"


def test_c_empty_dataframe_neutral():
    sig = rolling_micro_ml.generate_signal(pd.DataFrame())
    assert sig["direction"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# D) Gates
# ---------------------------------------------------------------------------
def test_d_high_holdout_floor_forces_neutral_on_noise():
    """A pure random walk shouldn't beat a very tight holdout floor of 0.85."""
    strict = RollingMicroML(min_history=80, min_confidence=55.0, holdout_acc_floor=0.85)
    df = _synth_candles(250, seed=17)
    sig = strict.generate_signal(df)
    assert sig["direction"] == "NEUTRAL"


def test_d_high_min_confidence_forces_neutral():
    strict = RollingMicroML(min_history=80, min_confidence=98.0, holdout_acc_floor=0.5)
    df = _synth_candles(250, seed=42)
    sig = strict.generate_signal(df)
    # p_up / p_dn from a 100-tree RF on random-walk noise will not clear 98%
    assert sig["direction"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# E) apply_config clamps and updates
# ---------------------------------------------------------------------------
def test_e_apply_config_clamps():
    s = RollingMicroML()
    out = s.apply_config({
        "lookback": 10000,           # clamp to 1000
        "n_estimators": 5,           # clamp to 20
        "min_confidence": 200,       # clamp to 95
        "holdout_acc_floor": 0.1,    # clamp to 0.5
    })
    assert out["lookback"] == 1000
    assert out["n_estimators"] == 20
    assert out["min_confidence"] == 95.0
    assert out["holdout_acc_floor"] == 0.5


def test_e_apply_config_partial():
    s = RollingMicroML(lookback=200, min_confidence=60.0)
    s.apply_config({"min_confidence": 70.0})
    assert s.lookback == 200
    assert s.min_confidence == 70.0


# ---------------------------------------------------------------------------
# F) Backtest endpoint integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f_backtest_endpoint_supports_strategy():
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "rolling_micro_ml",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 15,
            "max_candles": 1200,
            "stride": 5,
            "min_history": 150,
        })
    assert r.status_code == 200, r.text
    body = r.json()
    # Success (or friendly candles error). We only assert the shape.
    for k in ("strategy_id", "asset", "timeframe"):
        assert k in body
    if body.get("success"):
        assert "win_rate" in body
        assert "sim_pnl" in body


# ---------------------------------------------------------------------------
# G) 1m picker exposes it
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_g_1m_picker_lists_rolling_micro_ml():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/tampermonkey/strategies", params={"timeframe": "1m"})
    body = r.json()
    strategies = body.get("strategies") or body.get("data") or []
    ids = [s.get("id") for s in strategies]
    assert "rolling_micro_ml" in ids
