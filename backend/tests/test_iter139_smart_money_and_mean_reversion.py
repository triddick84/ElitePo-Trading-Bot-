"""Iter 139 — Smart-Money detectors + Mean-Reversion strategy tests."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smart_money import (
    detect_liquidity_sweep,
    detect_stop_hunt,
    detect_order_block,
    detect_breaker_block,
    detect_all_smart_money,
    _nearest_round_level,
)
from strategies.mean_reversion import (
    mean_reversion_signal,
    _adx,
    _rsi,
    _bollinger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(o, h, l, c, v=1000.0):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _flat(n, price=100.0, jitter=0.05, seed=42):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        o = price + rng.uniform(-jitter, jitter)
        c = price + rng.uniform(-jitter, jitter)
        out.append(_bar(o, max(o, c) + 0.05, min(o, c) - 0.05, c))
    return out


# ---------------------------------------------------------------------------
# Liquidity Sweep
# ---------------------------------------------------------------------------

def test_liquidity_sweep_low_fires_call():
    """Build a clear swing low at ~99, then a sweep bar wicks below it and closes back."""
    bars = _flat(6, price=100)
    bars.append(_bar(100, 100.1, 99.9, 99.9))
    bars.append(_bar(99.9, 99.95, 99.0, 99.05))   # swing low at 99
    bars.append(_bar(99.05, 100.2, 99.0, 100.2))
    bars += _flat(15, price=100.5, jitter=0.05)   # enough bars to satisfy lookback>=30
    bars.append(_bar(100.0, 100.1, 98.5, 100.0))  # sweep bar
    bars.append(_bar(100.0, 100.3, 99.8, 100.2))
    df = pd.DataFrame(bars)
    hits = detect_liquidity_sweep(df, lookback=25, max_bars_since_sweep=2)
    fired = [h for h in hits if h.pattern == "liquidity_sweep_low"]
    assert fired, f"expected liquidity_sweep_low, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "CALL"
    assert fired[0].confidence >= 0.55


def test_liquidity_sweep_high_fires_put():
    bars = _flat(6, price=100)
    bars.append(_bar(100, 100.9, 100.0, 100.9))
    bars.append(_bar(100.9, 101.0, 100.5, 100.5))
    bars.append(_bar(100.5, 100.6, 99.8, 99.8))
    bars += _flat(15, price=99.5, jitter=0.05)
    bars.append(_bar(100.0, 101.8, 99.9, 100.0))
    bars.append(_bar(100.0, 100.3, 99.6, 99.7))
    df = pd.DataFrame(bars)
    hits = detect_liquidity_sweep(df, lookback=25, max_bars_since_sweep=2)
    fired = [h for h in hits if h.pattern == "liquidity_sweep_high"]
    assert fired, f"expected liquidity_sweep_high, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "PUT"


def test_liquidity_sweep_no_signal_when_close_beyond():
    bars = _flat(6, price=100)
    bars.append(_bar(100, 100.9, 100.0, 100.9))
    bars.append(_bar(100.9, 101.0, 100.5, 100.5))
    bars.append(_bar(100.5, 100.6, 99.8, 99.8))
    bars += _flat(15, price=99.5, jitter=0.05)
    bars.append(_bar(100.0, 101.8, 99.9, 101.5))   # closes ABOVE — real breakout
    bars.append(_bar(101.5, 102.0, 101.2, 101.9))
    df = pd.DataFrame(bars)
    hits = detect_liquidity_sweep(df, lookback=25)
    assert not any(h.pattern == "liquidity_sweep_high" for h in hits)


# ---------------------------------------------------------------------------
# Stop Hunt
# ---------------------------------------------------------------------------

def test_stop_hunt_high_fires_put():
    """20-bar high at 101, current bar wicks above with big rejection."""
    bars = []
    rng = np.random.default_rng(1)
    for _ in range(25):  # enough for lookback+2
        p = 100 + rng.uniform(-0.5, 0.5)
        bars.append(_bar(p, min(101, p + 0.4), max(99, p - 0.4), p))
    bars.append(_bar(100.5, 102.5, 100.2, 100.3))
    df = pd.DataFrame(bars)
    hits = detect_stop_hunt(df, lookback=20, wick_atr_multiple=0.5)
    fired = [h for h in hits if h.pattern == "stop_hunt_high"]
    assert fired, f"expected stop_hunt_high, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "PUT"


def test_stop_hunt_low_fires_call():
    bars = []
    rng = np.random.default_rng(2)
    for _ in range(25):
        p = 100 + rng.uniform(-0.5, 0.5)
        bars.append(_bar(p, min(101, p + 0.4), max(99, p - 0.4), p))
    bars.append(_bar(99.5, 99.8, 97.5, 99.7))
    df = pd.DataFrame(bars)
    hits = detect_stop_hunt(df, lookback=20, wick_atr_multiple=0.5)
    fired = [h for h in hits if h.pattern == "stop_hunt_low"]
    assert fired
    assert fired[0].direction == "CALL"


def test_stop_hunt_ignores_tiny_wick():
    bars = []
    rng = np.random.default_rng(3)
    for _ in range(25):
        p = 100 + rng.uniform(-0.5, 0.5)
        bars.append(_bar(p, min(101, p + 0.4), max(99, p - 0.4), p))
    bars.append(_bar(100.5, 101.05, 100.2, 100.3))
    df = pd.DataFrame(bars)
    hits = detect_stop_hunt(df, lookback=20, wick_atr_multiple=1.5)
    assert not hits


def test_nearest_round_level():
    assert _nearest_round_level(1.10012, 0.001) == pytest.approx(1.100, abs=1e-3)
    assert _nearest_round_level(142.51, 0.5) == pytest.approx(142.5, abs=1e-2)
    # Beyond 2×ATR, no match
    assert _nearest_round_level(1.5, 0.001) is not None  # step 0.001 finds it
    assert _nearest_round_level(0, 0.001) is None


# ---------------------------------------------------------------------------
# Order Block
# ---------------------------------------------------------------------------

def test_bullish_order_block_fires_call():
    """Bearish candle, then 3-candle rally of 3+ ATR, then price returns to OB."""
    bars = _flat(20, price=100)   # enough prior bars
    bars.append(_bar(100.5, 100.8, 99.8, 99.9))
    bars.append(_bar(99.9, 101.5, 99.9, 101.5))
    bars.append(_bar(101.5, 103.0, 101.5, 103.0))
    bars.append(_bar(103.0, 104.5, 103.0, 104.5))
    bars.append(_bar(104.5, 104.5, 100.7, 101.0))
    df = pd.DataFrame(bars)
    hits = detect_order_block(df, displacement_atr=1.5, lookback=20, retest_tolerance_atr=1.0)
    fired = [h for h in hits if h.pattern == "bullish_order_block"]
    assert fired, f"expected bullish_order_block, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "CALL"


def test_bearish_order_block_fires_put():
    bars = _flat(20, price=100)
    bars.append(_bar(99.5, 100.5, 99.4, 100.3))
    bars.append(_bar(100.3, 100.3, 99.0, 99.0))
    bars.append(_bar(99.0, 99.0, 97.5, 97.5))
    bars.append(_bar(97.5, 97.5, 96.0, 96.0))
    bars.append(_bar(96.0, 99.5, 96.0, 99.0))
    df = pd.DataFrame(bars)
    hits = detect_order_block(df, displacement_atr=1.5, lookback=20, retest_tolerance_atr=1.0)
    fired = [h for h in hits if h.pattern == "bearish_order_block"]
    assert fired, f"expected bearish_order_block, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "PUT"


def test_order_block_ignores_weak_displacement():
    bars = _flat(20, price=100)
    bars.append(_bar(100.5, 100.8, 99.8, 99.9))
    bars.append(_bar(99.9, 100.1, 99.9, 100.05))
    bars.append(_bar(100.05, 100.2, 100.0, 100.15))
    bars.append(_bar(100.15, 100.2, 100.1, 100.15))
    df = pd.DataFrame(bars)
    hits = detect_order_block(df, displacement_atr=2.0, lookback=20)
    assert not any(h.pattern == "bullish_order_block" for h in hits)


# ---------------------------------------------------------------------------
# Breaker Block
# ---------------------------------------------------------------------------

def test_bullish_breaker_fires_call():
    """Bearish OB gets broken UP → becomes bullish breaker → retest fires CALL."""
    bars = _flat(25, price=100)  # enough for lookback+5
    bars.append(_bar(99.0, 100.0, 98.9, 99.8))
    bars.append(_bar(99.8, 99.8, 98.5, 98.5))
    bars.append(_bar(98.5, 98.5, 97.0, 97.0))
    bars.append(_bar(97.0, 97.0, 95.5, 95.5))
    bars.append(_bar(95.5, 96.5, 95.5, 96.5))
    bars.append(_bar(96.5, 98.0, 96.5, 98.0))
    bars.append(_bar(98.0, 100.5, 98.0, 100.5))
    bars.append(_bar(100.5, 100.5, 99.8, 100.2))
    df = pd.DataFrame(bars)
    hits = detect_breaker_block(df, displacement_atr=1.5, lookback=30)
    fired = [h for h in hits if h.pattern == "bullish_breaker"]
    assert fired, f"expected bullish_breaker, got: {[h.pattern for h in hits]}"
    assert fired[0].direction == "CALL"


# ---------------------------------------------------------------------------
# detect_all wrapper
# ---------------------------------------------------------------------------

def test_detect_all_smart_money_empty_frame():
    assert detect_all_smart_money(pd.DataFrame()) == []
    assert detect_all_smart_money(None) == []


def test_detect_all_smart_money_missing_columns():
    df = pd.DataFrame({"close": [1, 2, 3]})
    assert detect_all_smart_money(df) == []


# ---------------------------------------------------------------------------
# Mean Reversion Strategy
# ---------------------------------------------------------------------------

def _build_range_market(n=80, mid=100.0, amp=0.5, seed=7):
    """A stationary mean-reverting series — low ADX."""
    rng = np.random.default_rng(seed)
    bars = []
    price = mid
    for _ in range(n):
        # OU-ish process: pulled back to mid
        price += (mid - price) * 0.4 + rng.uniform(-amp, amp)
        o = price + rng.uniform(-0.05, 0.05)
        c = price + rng.uniform(-0.05, 0.05)
        bars.append(_bar(o, max(o, c) + 0.05, min(o, c) - 0.05, c))
    return pd.DataFrame(bars)


def test_mean_reversion_neutral_when_trending():
    """Strongly trending series → ADX > 20 → NEUTRAL."""
    bars = []
    for i in range(80):
        p = 100 + i * 0.5
        bars.append(_bar(p, p + 0.2, p - 0.2, p + 0.1))
    df = pd.DataFrame(bars)
    sig = mean_reversion_signal(df, adx_max=20)
    assert sig.direction == "NEUTRAL"
    assert "trending" in sig.reason


def test_mean_reversion_fires_put_at_upper_extreme():
    """Range market, drop a spike at the top so z-score/RSI/BB all extreme."""
    df = _build_range_market()
    # Force the last bar to be an upper extreme
    spike_price = df["close"].iloc[-2] + 3.0
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [
        spike_price - 0.1, spike_price + 0.1, spike_price - 0.2, spike_price,
    ]
    sig = mean_reversion_signal(df, adx_max=50)  # very permissive regime filter
    assert sig.direction == "PUT", f"expected PUT, got {sig.direction} ({sig.reason})"
    assert sig.confidence >= 0.55


def test_mean_reversion_fires_call_at_lower_extreme():
    df = _build_range_market()
    spike_price = df["close"].iloc[-2] - 3.0
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [
        spike_price + 0.1, spike_price + 0.2, spike_price - 0.1, spike_price,
    ]
    sig = mean_reversion_signal(df, adx_max=50)
    assert sig.direction == "CALL"


def test_mean_reversion_neutral_on_short_data():
    df = pd.DataFrame([_bar(100, 100.5, 99.5, 100) for _ in range(10)])
    sig = mean_reversion_signal(df)
    assert sig.direction == "NEUTRAL"
    assert "insufficient" in sig.reason


def test_mean_reversion_neutral_when_only_one_filter_hits():
    """Only RSI extreme, but no z-score / BB tag → NEUTRAL."""
    df = _build_range_market(n=80, amp=0.05)  # very tight range
    # Slightly elevated last bar — high RSI but low z-score, no BB tag
    df.loc[df.index[-1], ["close"]] = df["close"].iloc[-2] + 0.05
    sig = mean_reversion_signal(df, adx_max=50)
    assert sig.direction == "NEUTRAL"


def test_indicators_smoke():
    """Sanity-check the internal indicators return sensible ranges."""
    df = _build_range_market()
    close = df["close"].astype(float)
    rsi = _rsi(close)
    assert (rsi >= 0).all() and (rsi <= 100).all()
    ma, upper, lower = _bollinger(close)
    assert (upper.dropna() >= lower.dropna()).all()
    adx = _adx(df)
    assert 0 <= adx <= 100


# ---------------------------------------------------------------------------
# Route module smoke
# ---------------------------------------------------------------------------

def test_smart_money_route_module_imports():
    from routes import smart_money_routes  # noqa: F401
    assert smart_money_routes.router is not None
