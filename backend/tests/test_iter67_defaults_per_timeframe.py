"""
Iter 67 — Default-per-timeframe strategies are empirical winners

A1. DEFAULT_STRATEGY_PER_TIMEFRAME contains all critical timeframes
A2. resolve_default('5s') returns '5s_heikin_fractal' (winner from May 29 eval)
A3. resolve_default('15s') returns '15s_ema_cascade'
A4. resolve_default('30s') returns 'momentum_buster'
A5. resolve_default('1m') returns '1m_triple_ema'
A6. /api/backtest/run is happy with the new defaults (they're real registered strategies)
"""
import os
import sys
import pytest

sys.path.insert(0, "/app/backend")

import requests
from strategy_selection_service import strategy_selection_service

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


def test_defaults_map_present():
    m = strategy_selection_service.DEFAULT_STRATEGY_PER_TIMEFRAME
    assert isinstance(m, dict)
    for tf in ("5s", "15s", "30s", "1m"):
        assert tf in m, f"timeframe {tf} missing from defaults map"


def test_5s_default_is_heikin_fractal():
    assert strategy_selection_service.resolve_default("5s") == "5s_heikin_fractal"


def test_15s_default_is_ema_cascade():
    assert strategy_selection_service.resolve_default("15s") == "15s_ema_cascade"


def test_30s_default_is_momentum_buster():
    assert strategy_selection_service.resolve_default("30s") == "momentum_buster"


def test_1m_default_is_triple_ema():
    assert strategy_selection_service.resolve_default("1m") == "1m_triple_ema"


def test_unknown_timeframe_returns_default_literal():
    """`resolve_default` is a hot path — guarantee it never raises."""
    assert strategy_selection_service.resolve_default("not-a-real-tf") == "default"


@pytest.mark.parametrize("strategy,tf", [
    ("5s_heikin_fractal", "5s"),
    ("15s_ema_cascade", "15s"),
    ("momentum_buster", "30s"),
    ("1m_triple_ema", "M1"),
])
def test_default_strategy_is_backtest_compatible(strategy, tf):
    """Smoke: each new default must be backtest-runnable (no `Unknown strategy` error)."""
    r = requests.post(
        f"{API}/api/backtest/run",
        json={"strategy": strategy, "symbol": "EURUSD_OTC", "timeframe": tf, "days": 1, "min_confidence": 50},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    res = (r.json() or {}).get("results") or [{}]
    err = res[0].get("error") or ""
    assert "Unknown strategy" not in err, f"{strategy} on {tf} returned: {err}"
