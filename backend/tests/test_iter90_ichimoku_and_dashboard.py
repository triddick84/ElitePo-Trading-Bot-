"""
Iter 90 — Ichimoku Cloud indicator + Latency Dashboard endpoints.

Guards:
1. `custom_strategy_executor` now handles the `ICHIMOKU` indicator that was
   declared in the schema but never implemented (silent None return).
2. Ichimoku outputs tenkan/kijun/senkou_a/senkou_b/chikou.
3. `/api/latency/stats`, `/api/latency/healthy`, `/api/signal-prewarm/stats`
   are all reachable (surface the dashboard depends on).
"""

from __future__ import annotations

import os
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def test_ichimoku_calculation_matches_spec():
    """Direct call to _calculate_ichimoku with known-input candles."""
    from custom_strategy_executor import IndicatorCalculator
    ex = IndicatorCalculator()
    # Simple 100-candle rising sequence
    highs = [1.10 + i * 0.001 for i in range(100)]
    lows = [1.098 + i * 0.001 for i in range(100)]
    closes = [1.099 + i * 0.001 for i in range(100)]

    out = ex._calculate_ichimoku(highs, lows, closes, 9, 26, 52)
    # All 5 outputs must be present and finite
    for k in ("tenkan", "kijun", "senkou_a", "senkou_b", "chikou"):
        assert k in out, f"Missing output {k}"
        assert isinstance(out[k], float)
        assert out[k] > 0

    # Sanity: tenkan (9-period midrange, most recent) should be > kijun (26)
    # since price is monotonically rising
    assert out["tenkan"] > out["kijun"], \
        f"Expected tenkan > kijun on rising series: {out}"
    # senkou_a is (tenkan+kijun)/2 — must lie between them
    assert out["kijun"] <= out["senkou_a"] <= out["tenkan"]
    # chikou is the last close
    assert out["chikou"] == closes[-1]


def test_ichimoku_handles_empty_candles():
    """Zero candles must not crash — returns zeros, not None."""
    from custom_strategy_executor import IndicatorCalculator
    ex = IndicatorCalculator()
    out = ex._calculate_ichimoku([], [], [])
    for k in ("tenkan", "kijun", "senkou_a", "senkou_b", "chikou"):
        assert out[k] == 0.0


def test_ichimoku_dispatched_from_calculate():
    """The `ICHIMOKU` indicator name must route to _calculate_ichimoku."""
    from custom_strategy_executor import IndicatorCalculator
    ex = IndicatorCalculator()
    ohlcv = {
        "open":   [1.10 + i * 0.001 for i in range(100)],
        "high":   [1.101 + i * 0.001 for i in range(100)],
        "low":    [1.099 + i * 0.001 for i in range(100)],
        "close":  [1.10 + i * 0.001 for i in range(100)],
        "volume": [100] * 100,
    }
    tenkan = ex.calculate(
        "ICHIMOKU",
        {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52},
        ohlcv,
        "tenkan",
    )
    assert tenkan is not None
    assert isinstance(tenkan, float)
    assert tenkan > 0


def test_latency_dashboard_endpoints_reachable():
    for path in ("/api/latency/stats",
                 "/api/latency/healthy?p99_threshold_ms=250",
                 "/api/signal-prewarm/stats"):
        r = requests.get(f"{BASE_URL}{path}", timeout=5)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        body = r.json()
        assert body.get("success") is True, f"{path} not success"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
