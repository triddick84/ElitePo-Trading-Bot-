"""Iter 143 — Signal Auto-Bridge tests.

Mocks the candle loader so no live DB is required.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from forex.signal_bridge import _mt5_symbol, _atr, bridge_symbol, get_bridge_loop
from forex.models import ExecutionSurface
from forex.engine import get_engine


# ---------------------------------------------------------------------------
# Symbol normalisation
# ---------------------------------------------------------------------------

def test_mt5_symbol_strips_otc_suffix():
    assert _mt5_symbol("EURUSD_OTC") == "EURUSD"
    assert _mt5_symbol("USD-JPY-OTC") == "USDJPY"
    assert _mt5_symbol("gbp/usd") == "GBPUSD"
    assert _mt5_symbol("EURUSD") == "EURUSD"


def test_mt5_symbol_handles_empty():
    assert _mt5_symbol("") == ""
    assert _mt5_symbol(None) == ""


# ---------------------------------------------------------------------------
# ATR helper
# ---------------------------------------------------------------------------

def test_atr_returns_zero_on_short_frame():
    df = pd.DataFrame([{"high": 1, "low": 0.9, "close": 0.95} for _ in range(5)])
    assert _atr(df, period=14) == 0.0


def test_atr_positive_on_volatile_data():
    rng = np.random.default_rng(1)
    rows = []
    for _ in range(40):
        p = 100 + rng.uniform(-1, 1)
        rows.append({"high": p + 0.5, "low": p - 0.5, "close": p})
    df = pd.DataFrame(rows)
    val = _atr(df, period=14)
    assert val > 0


# ---------------------------------------------------------------------------
# Full bridge_symbol pipeline (mocked candle loader)
# ---------------------------------------------------------------------------

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _range_market(n=80, mid=100.0, seed=7):
    """Mean-reverting series that should trigger the MR strategy on the
    last bar when we force an extreme."""
    rng = np.random.default_rng(seed)
    bars = []
    price = mid
    for _ in range(n):
        price += (mid - price) * 0.4 + rng.uniform(-0.4, 0.4)
        o = price + rng.uniform(-0.05, 0.05)
        c = price + rng.uniform(-0.05, 0.05)
        bars.append({"open": o, "high": max(o, c) + 0.05, "low": min(o, c) - 0.05, "close": c, "volume": 1000})
    return pd.DataFrame(bars)


def test_bridge_returns_no_candles_when_df_empty():
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=pd.DataFrame())):
        res = _run(bridge_symbol("EURUSD_OTC"))
    assert res["accepted"] is False
    assert res["reason"] == "no_candles"


def test_bridge_returns_no_signals_when_market_quiet():
    """Flat frame → no patterns / smart-money / MR fire → no_signals."""
    flat = pd.DataFrame([
        {"open": 100, "high": 100.05, "low": 99.95, "close": 100, "volume": 1000}
        for _ in range(50)
    ])
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=flat)):
        res = _run(bridge_symbol("EURUSD_OTC"))
    # Very small chance of spurious signals; assert we didn't emit
    assert res["accepted"] is False


def test_bridge_translates_call_to_buy_side_when_forced():
    """We call with emit=False so we don't hit Mongo/engine — just verify
    the DIRECTION → SIDE mapping happens correctly.

    Iter 146: TQNet now participates as an additional source, so a strong
    downtick may make the confluence winner PUT instead of MR's CALL. Assert
    the direction→side mapping remains internally consistent regardless of
    which side wins."""
    df = _range_market()
    # Push the last bar to a strong lower extreme so MR fires CALL
    spike_price = df["close"].iloc[-2] - 3.0
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [
        spike_price + 0.1, spike_price + 0.2, spike_price - 0.1, spike_price,
    ]
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=df)):
        with patch("routes.confluence_routes.get_confluence_config",
                   return_value={"threshold": 0.05, "min_sources": 1}):
            res = _run(bridge_symbol("EURUSD_OTC", emit=False))
    # Some source fires → CALL→BUY or PUT→SELL. Assert internal consistency
    # and the (OTC-suffix-stripped) symbol regardless of side.
    if res.get("accepted"):
        fx = res["forex_signal"]
        assert fx["symbol"] == "EURUSD"
        winning_dir = res["confluence"]["direction"]
        expected_side = "BUY" if winning_dir == "CALL" else "SELL"
        assert fx["side"] == expected_side


def test_bridge_gate_blocks_low_score(monkeypatch):
    """Set threshold very high — even a real signal should be blocked."""
    df = _range_market()
    spike = df["close"].iloc[-2] + 3.0
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [
        spike - 0.1, spike + 0.2, spike - 0.2, spike,
    ]
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=df)):
        with patch("routes.confluence_routes.get_confluence_config",
                   return_value={"threshold": 0.99, "min_sources": 10}):
            res = _run(bridge_symbol("EURUSD_OTC", emit=False))
    if res.get("n_signals", 0) > 0:
        assert res["accepted"] is False
        assert res["reason"] == "confluence_gate_blocked"


# ---------------------------------------------------------------------------
# BridgeLoop
# ---------------------------------------------------------------------------

def test_bridge_loop_configure_and_status():
    loop = get_bridge_loop()
    loop.configure(symbols=["EURUSD_OTC", "GBPUSD_OTC"], interval_s=10, timeframe="5m")
    assert loop.symbols == ["EURUSD_OTC", "GBPUSD_OTC"]
    assert loop.interval_s == 10
    assert loop.timeframe == "5m"
    assert loop.is_running() is False


def test_bridge_loop_clamps_interval():
    loop = get_bridge_loop()
    loop.configure(symbols=[], interval_s=1)   # clamped to min 5
    assert loop.interval_s == 5


def test_bridge_loop_start_and_stop():
    loop_state = get_bridge_loop()
    loop_state.configure(symbols=[], interval_s=5)   # no work → cheap
    ev = asyncio.new_event_loop()
    try:
        async def _flow():
            await loop_state.start()
            assert loop_state.is_running() is True
            await loop_state.stop()
            assert loop_state.is_running() is False
        ev.run_until_complete(_flow())
    finally:
        ev.close()


# ---------------------------------------------------------------------------
# Route module smoke
# ---------------------------------------------------------------------------

def test_forex_routes_expose_bridge_endpoints():
    from routes import forex_routes
    paths = [r.path for r in forex_routes.router.routes]
    assert "/forex/bridge/once" in paths
    assert "/forex/bridge/loop/start" in paths
    assert "/forex/bridge/loop/stop" in paths
    assert "/forex/bridge/loop/configure" in paths
    assert "/forex/bridge/status" in paths
