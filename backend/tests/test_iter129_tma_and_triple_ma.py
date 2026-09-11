"""Iter 129 — Strategy Builder: TMA + 3-MA Crossover indicators."""
import sys

import numpy as np
import pytest

sys.path.insert(0, "/app/backend")

from custom_strategy_executor import IndicatorCalculator, CustomStrategyExecutor  # noqa: E402
from custom_strategy_service import AVAILABLE_INDICATORS as INDICATOR_LIBRARY  # noqa: E402


# ---------------------------------------------------------------------------
# Backend schema registration
# ---------------------------------------------------------------------------
def test_tma_indicator_registered_in_library():
    assert "TMA" in INDICATOR_LIBRARY
    tma = INDICATOR_LIBRARY["TMA"]
    assert "period" in tma["parameters"]
    assert tma["parameters"]["period"]["default"] == 14


def test_triple_ma_crossover_registered_in_library():
    assert "TRIPLE_MA_CROSSOVER" in INDICATOR_LIBRARY
    tri = INDICATOR_LIBRARY["TRIPLE_MA_CROSSOVER"]
    for k in ("fast_type", "fast_period", "medium_type", "medium_period",
              "slow_type", "slow_period"):
        assert k in tri["parameters"], f"missing param {k}"
    # All 4 MA types must be selectable for each line
    for slot in ("fast_type", "medium_type", "slow_type"):
        opts = set(tri["parameters"][slot]["options"])
        assert opts == {"SMA", "EMA", "WMA", "TMA"}, f"{slot} options: {opts}"


# ---------------------------------------------------------------------------
# TMA math
# ---------------------------------------------------------------------------
def test_tma_matches_double_sma_definition():
    calc = IndicatorCalculator()
    # Build a synthetic linearly-increasing series so the answer is easy to hand-check
    prices = [float(i) for i in range(1, 51)]  # 1..50
    period = 5
    tma = calc._calculate_tma(prices, period)
    # Reference: SMA of the last `period` SMAs
    arr = np.array(prices)
    smas = [arr[i-period:i].mean() for i in range(len(arr) - period + 1, len(arr) + 1)]
    expected = float(np.mean(smas[-period:]))
    assert abs(tma - expected) < 1e-6, f"TMA={tma} expected={expected}"


def test_tma_smoother_than_sma_on_noisy_data():
    """TMA should have LOWER volatility than SMA on the same period."""
    calc = IndicatorCalculator()
    rng = np.random.default_rng(42)
    # 200 points of noisy random walk
    noise = rng.normal(0, 1, 300).cumsum() + 100
    period = 20
    tmas = [calc._calculate_tma(list(noise[:i]), period) for i in range(30, 300)]
    smas = [calc._calculate_sma(list(noise[:i]), period) for i in range(30, 300)]
    assert np.std(np.diff(tmas)) < np.std(np.diff(smas)), "TMA must smooth more than SMA"


def test_tma_short_input_does_not_crash():
    calc = IndicatorCalculator()
    # Fewer prices than period → must return mean fallback, not crash
    v = calc._calculate_tma([1.0, 2.0, 3.0], 20)
    assert v == 2.0


# ---------------------------------------------------------------------------
# TRIPLE_MA_CROSSOVER
# ---------------------------------------------------------------------------
def test_triple_ma_bull_alignment_on_uptrend():
    """Strong uptrend → fast > medium > slow → alignment = +1"""
    calc = IndicatorCalculator()
    prices = [100 + i * 0.5 for i in range(200)]  # steady uptrend
    result = calc._calculate_triple_ma_crossover(
        prices, "EMA", 5, "WMA", 13, "TMA", 34,
    )
    assert result["alignment"] == 1.0
    assert result["fast"] > result["medium"] > result["slow"]


def test_triple_ma_bear_alignment_on_downtrend():
    calc = IndicatorCalculator()
    prices = [200 - i * 0.5 for i in range(200)]  # steady downtrend
    result = calc._calculate_triple_ma_crossover(
        prices, "EMA", 5, "SMA", 13, "WMA", 34,
    )
    assert result["alignment"] == -1.0
    assert result["fast"] < result["medium"] < result["slow"]


def test_triple_ma_supports_all_type_combinations():
    """Every combination of MA types must produce valid finite output."""
    calc = IndicatorCalculator()
    prices = [100 + np.sin(i / 10) for i in range(200)]
    types = ["SMA", "EMA", "WMA", "TMA"]
    for t1 in types:
        for t2 in types:
            for t3 in types:
                r = calc._calculate_triple_ma_crossover(prices, t1, 5, t2, 13, t3, 34)
                for k in ("fast", "medium", "slow", "alignment"):
                    assert np.isfinite(r[k]), f"non-finite {k} for {t1}/{t2}/{t3}"


def test_triple_ma_unknown_type_falls_back_to_ema():
    """An unknown MA type must not raise — falls back to EMA default."""
    calc = IndicatorCalculator()
    prices = [100 + i for i in range(50)]
    r = calc._calculate_triple_ma_crossover(
        prices, "HULL", 5, "EMA", 13, "SMA", 34,
    )
    assert np.isfinite(r["fast"])


# ---------------------------------------------------------------------------
# Executor dispatcher (top-level `calculate` must route TMA + TRIPLE_MA)
# ---------------------------------------------------------------------------
def test_calculator_dispatches_tma():
    calc = IndicatorCalculator()
    prices = [100 + i * 0.1 for i in range(100)]
    v = calc.calculate("TMA", {"period": 14}, {"close": prices}, "value")
    assert v is not None and np.isfinite(v)


def test_calculator_dispatches_triple_ma_crossover_with_all_outputs():
    calc = IndicatorCalculator()
    prices = [100 + i * 0.1 for i in range(200)]
    params = {
        "fast_type": "EMA", "fast_period": 5,
        "medium_type": "WMA", "medium_period": 13,
        "slow_type": "TMA", "slow_period": 34,
    }
    for out in ("fast", "medium", "slow", "alignment"):
        v = calc.calculate("TRIPLE_MA_CROSSOVER", params, {"close": prices}, out)
        assert v is not None and np.isfinite(v), f"output {out} is None/NaN"


# ---------------------------------------------------------------------------
# Frontend schema — Iter 129 declares TMA + TRIPLE_MA_CROSSOVER templates
# ---------------------------------------------------------------------------
def test_frontend_strategy_builder_registers_new_indicators():
    src = open("/app/frontend/src/components/StrategyBuilder.jsx").read()
    # Template names/keys present
    assert "  TMA: {" in src, "TMA template missing in StrategyBuilder.jsx"
    assert "  TRIPLE_MA_CROSSOVER: {" in src, "TRIPLE_MA_CROSSOVER template missing"
    # Selectable MA types in triple crossover
    assert "options: ['SMA', 'EMA', 'WMA', 'TMA']" in src
    # Param renderer supports the new `select` type
    assert "param.type === 'select'" in src
