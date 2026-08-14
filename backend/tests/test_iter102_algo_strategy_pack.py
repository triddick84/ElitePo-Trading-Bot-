"""
Iter 102 — Algorithmic Trading Strategy Pack unit + integration tests.

Covers:
  1. Each of the 4 new strategies loads and produces a well-formed signal
     on synthetic OHLC data
  2. Registry integration — strategies discoverable via strategy_registry
  3. Available-strategy dict wiring — new IDs appear in the 30s / 1m
     picker payloads returned by strategy_selection_service
  4. Endpoint smoke test — /api/strategies/available/1m returns the new
     algo entries
"""

from __future__ import annotations

import os
from typing import List

import numpy as np
import pandas as pd
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def _fake_ohlc(n: int = 220, seed: int = 42, drift: float = 0.0, vol: float = 0.001) -> pd.DataFrame:
    """Synthetic OHLC that mimics 1m OTC candles well enough for signal wiring tests."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, vol, size=n)
    close = 1.10 * np.exp(np.cumsum(steps))
    openp = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(close, openp) * (1 + rng.uniform(0, 0.0004, n))
    low = np.minimum(close, openp) * (1 - rng.uniform(0, 0.0004, n))
    vol_series = rng.uniform(80, 200, size=n)
    idx = pd.date_range("2026-02-01", periods=n, freq="1min")
    return pd.DataFrame(
        {"open": openp, "high": high, "low": low, "close": close, "volume": vol_series},
        index=idx,
    )


class TestAlgoStrategyPack:
    """Unit tests for the four new algo strategies."""

    def test_trend_momentum_returns_wellformed_signal(self):
        from strategies.strategy_algo_pack import algo_trend_momentum
        df = _fake_ohlc(drift=0.0005, vol=0.0008, seed=7)
        sig = algo_trend_momentum.generate_signal(df)
        assert sig["strategy"] == algo_trend_momentum.name
        assert sig["direction"] in {"CALL", "PUT", "NEUTRAL"}
        assert 0 <= sig["confidence"] <= 100
        assert sig["meta"]["family"] == "trend_momentum"
        # Uptrend drift should NOT produce a PUT (either CALL or NEUTRAL)
        assert sig["direction"] != "PUT"

    def test_mean_reversion_returns_wellformed_signal(self):
        from strategies.strategy_algo_pack import algo_mean_reversion
        df = _fake_ohlc(seed=13, vol=0.002)
        sig = algo_mean_reversion.generate_signal(df)
        assert sig["direction"] in {"CALL", "PUT", "NEUTRAL"}
        assert sig["meta"]["family"] == "mean_reversion"
        assert "bb_upper" in sig["indicators"] and "bb_lower" in sig["indicators"]

    def test_order_flow_returns_wellformed_signal(self):
        from strategies.strategy_algo_pack import algo_order_flow_imbalance
        df = _fake_ohlc(drift=-0.0004, vol=0.001, seed=99)
        sig = algo_order_flow_imbalance.generate_signal(df)
        assert sig["direction"] in {"CALL", "PUT", "NEUTRAL"}
        assert sig["meta"]["family"] == "order_flow"
        assert "bar_delta" in sig["indicators"]

    def test_volatility_regime_returns_wellformed_signal(self):
        from strategies.strategy_algo_pack import algo_volatility_regime
        df = _fake_ohlc(seed=21, vol=0.0009)
        sig = algo_volatility_regime.generate_signal(df)
        assert sig["direction"] in {"CALL", "PUT", "NEUTRAL"}
        assert sig["meta"]["family"] in {"volatility_regime", "algo_pack"}
        assert "atr_percentile" in sig["indicators"]

    def test_all_strategies_reject_insufficient_data(self):
        from strategies.strategy_algo_pack import ALGO_STRATEGIES
        tiny = _fake_ohlc(n=10)
        for sid, obj in ALGO_STRATEGIES.items():
            sig = obj.generate_signal(tiny)
            assert sig["direction"] == "NEUTRAL", f"{sid} should be NEUTRAL on 10-bar input"
            assert sig["confidence"] == 0


class TestAlgoStrategyRegistryIntegration:
    def test_all_algo_strategies_are_registered(self):
        # Import registry AFTER strategies to trigger _load_strategies
        from strategy_registry import strategy_registry
        expected = {
            "algo_trend_momentum",
            "algo_mean_reversion",
            "algo_order_flow_imbalance",
            "algo_volatility_regime",
        }
        loaded = set(strategy_registry.strategies.keys())
        missing = expected - loaded
        assert not missing, f"strategy_registry missing: {missing}"

    def test_execute_strategy_via_registry(self):
        from strategy_registry import strategy_registry
        df = _fake_ohlc(drift=0.0006, vol=0.001, seed=3)
        result = strategy_registry.execute_strategy("algo_trend_momentum", df)
        assert result["direction"] in {"CALL", "PUT", "NEUTRAL"}
        assert 0 <= result["confidence"] <= 100


class TestAlgoStrategyPickerWiring:
    def test_30s_picker_lists_order_flow(self):
        from strategy_selection_service import strategy_selection_service
        ids = [s["id"] for s in strategy_selection_service.AVAILABLE_STRATEGIES["30s"]]
        assert "algo_order_flow_imbalance" in ids

    def test_1m_picker_lists_trend_mr_and_vol(self):
        from strategy_selection_service import strategy_selection_service
        ids = [s["id"] for s in strategy_selection_service.AVAILABLE_STRATEGIES["1m"]]
        for sid in ("algo_trend_momentum", "algo_mean_reversion", "algo_volatility_regime"):
            assert sid in ids, f"missing {sid} in 1m picker"


class TestAlgoStrategyEndpoint:
    def test_available_1m_returns_algo_strategies(self):
        try:
            r = requests.get(f"{BASE_URL}/api/strategies/available/1m", timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200, r.status_code
        payload = r.json()
        strategies = payload.get("strategies") or payload.get("data") or []
        # payload shape can vary; extract IDs robustly
        ids: List[str] = []
        for s in strategies:
            if isinstance(s, dict):
                ids.append(s.get("id") or s.get("strategy_id") or "")
        assert "algo_trend_momentum" in ids
        assert "algo_mean_reversion" in ids
        assert "algo_volatility_regime" in ids

    def test_available_30s_returns_order_flow(self):
        try:
            r = requests.get(f"{BASE_URL}/api/strategies/available/30s", timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        payload = r.json()
        strategies = payload.get("strategies") or payload.get("data") or []
        ids = [s.get("id", "") for s in strategies if isinstance(s, dict)]
        assert "algo_order_flow_imbalance" in ids
