"""Iter 137 — Pattern detectors + Confluence engine tests."""

import numpy as np
import pandas as pd
import pytest

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pattern_detector import (
    find_swings,
    detect_head_and_shoulders,
    detect_wedge,
    detect_break_and_retest,
    detect_gap,
    detect_all,
    PatternHit,
)
from confluence_service import (
    score_confluence,
    should_fire,
    signals_from_patterns,
    _base_weight_for,
    DEFAULT_THRESHOLD,
    DEFAULT_MIN_SOURCES,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic OHLCV frames
# ---------------------------------------------------------------------------

def _bar(o, h, l, c, v=1000.0):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _flat_series(n, price=100.0, jitter=0.05):
    """Random-walk-ish flat prices (used as filler in synthetic patterns)."""
    rng = np.random.default_rng(42)
    return [
        _bar(price + rng.uniform(-jitter, jitter),
             price + jitter,
             price - jitter,
             price + rng.uniform(-jitter, jitter))
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# ZigZag / swings
# ---------------------------------------------------------------------------

def test_find_swings_detects_peaks_and_troughs():
    bars = []
    prices = [100, 101, 103, 102, 100, 98, 96, 98, 101, 104, 103, 102, 100]  # peak at idx 2, trough at 6, peak at 9
    for p in prices:
        bars.append(_bar(p, p + 0.2, p - 0.2, p))
    df = pd.DataFrame(bars)
    swings = find_swings(df, left=2, right=2)
    kinds = [(s["idx"], s["kind"]) for s in swings]
    assert (2, "H") in kinds
    assert (6, "L") in kinds
    assert (9, "H") in kinds


def test_find_swings_handles_short_frame():
    df = pd.DataFrame([_bar(100, 101, 99, 100) for _ in range(3)])
    assert find_swings(df, left=3, right=3) == []


# ---------------------------------------------------------------------------
# Head & Shoulders
# ---------------------------------------------------------------------------

def _build_head_and_shoulders(broken=True):
    """Classic H&S: LS peak 105 → dip 100 → head 110 → dip 100 → RS peak 105 → break below 100."""
    bars = _flat_series(5, price=100)
    # left shoulder up-down
    bars += [_bar(100, 102, 100, 102), _bar(102, 105, 101, 105), _bar(105, 105, 103, 103), _bar(103, 103, 100, 100)]
    # head up-down
    bars += [_bar(100, 103, 100, 103), _bar(103, 108, 102, 108), _bar(108, 110, 106, 110), _bar(110, 110, 104, 104), _bar(104, 104, 100, 100)]
    # right shoulder up-down
    bars += [_bar(100, 103, 100, 103), _bar(103, 105, 102, 105), _bar(105, 105, 102, 102)]
    if broken:
        bars += [_bar(102, 102, 98, 98)]  # break below neckline (~100)
    else:
        bars += [_bar(102, 103, 101, 102)]  # no break
    # add filler to trigger swings safely
    bars += _flat_series(3, price=99 if broken else 102)
    return pd.DataFrame(bars)


def test_head_and_shoulders_broken_fires_put():
    df = _build_head_and_shoulders(broken=True)
    hits = detect_head_and_shoulders(df, tolerance=0.10)
    hs = [h for h in hits if h.pattern == "head_and_shoulders"]
    assert hs, "expected at least one H&S hit"
    # at least one hit should have direction PUT (broken)
    assert any(h.direction == "PUT" for h in hs)
    fired = next(h for h in hs if h.direction == "PUT")
    assert fired.confidence >= 0.7
    assert fired.target is not None and fired.target < fired.entry


def test_inverse_head_and_shoulders_broken_fires_call():
    """Mirror pattern: LS trough 95, head 90, RS trough 95, break up through neckline."""
    bars = _flat_series(5, price=100)
    bars += [_bar(100, 100, 98, 98), _bar(98, 98, 95, 95), _bar(95, 97, 95, 97), _bar(97, 100, 97, 100)]  # left trough
    bars += [_bar(100, 100, 97, 97), _bar(97, 97, 92, 92), _bar(92, 92, 90, 90), _bar(90, 96, 90, 96), _bar(96, 100, 96, 100)]  # head trough
    bars += [_bar(100, 100, 97, 97), _bar(97, 97, 95, 95), _bar(95, 98, 95, 98)]  # right trough
    bars += [_bar(98, 102, 98, 102)]  # break UP through neckline
    bars += _flat_series(3, price=102)
    df = pd.DataFrame(bars)
    hits = detect_head_and_shoulders(df, tolerance=0.10)
    inv = [h for h in hits if h.pattern == "inverse_head_and_shoulders"]
    assert inv, "expected inverse H&S detection"
    fired = [h for h in inv if h.direction == "CALL"]
    assert fired, "expected bullish CALL fire on inverse H&S break"


# ---------------------------------------------------------------------------
# Wedges
# ---------------------------------------------------------------------------

def test_rising_wedge_fires_put_on_break():
    """Two rising trend lines converging, then break below lower line."""
    # Build clear alternating peaks and troughs where each is separated by filler.
    bars = _flat_series(3, price=100, jitter=0.02)
    # 4 rising highs and 4 rising (steeper) lows
    highs = [102.0, 104.0, 106.0, 107.0]
    lows = [100.0, 101.5, 103.5, 105.0]
    for hi, lo in zip(highs, lows):
        mid = (hi + lo) / 2
        # push up to swing high
        bars.append(_bar(mid, hi, mid - 0.1, hi - 0.05))
        # single high pivot bar
        bars.append(_bar(hi - 0.05, hi, hi - 0.1, hi - 0.2))
        # pull back to swing low
        bars.append(_bar(hi - 0.2, hi - 0.1, lo + 0.1, lo + 0.2))
        # single low pivot bar
        bars.append(_bar(lo + 0.2, lo + 0.3, lo, lo + 0.1))
        # filler between
        bars.append(_bar(lo + 0.1, mid, lo, mid - 0.1))
    # break DOWN below lower trend line (which ends ~105)
    bars.append(_bar(106, 106, 100, 100))
    bars += _flat_series(3, price=100, jitter=0.02)
    df = pd.DataFrame(bars)
    hits = detect_wedge(df)
    rw = [h for h in hits if h.pattern == "rising_wedge"]
    assert rw, f"expected a rising_wedge detection, got: {[h.pattern for h in hits]}"


def test_falling_wedge_fires_call_on_break():
    """Two falling trend lines converging, break upward."""
    bars = _flat_series(3, price=110, jitter=0.02)
    highs = [108.0, 106.0, 104.0, 103.0]
    lows = [102.0, 101.5, 101.0, 100.5]
    for hi, lo in zip(highs, lows):
        mid = (hi + lo) / 2
        bars.append(_bar(mid, hi, mid - 0.1, hi - 0.05))
        bars.append(_bar(hi - 0.05, hi, hi - 0.1, hi - 0.2))
        bars.append(_bar(hi - 0.2, hi - 0.1, lo + 0.1, lo + 0.2))
        bars.append(_bar(lo + 0.2, lo + 0.3, lo, lo + 0.1))
        bars.append(_bar(lo + 0.1, mid, lo, mid - 0.1))
    # break UP through upper line (which ends ~103)
    bars.append(_bar(102, 108, 102, 108))
    bars += _flat_series(3, price=108, jitter=0.02)
    df = pd.DataFrame(bars)
    hits = detect_wedge(df)
    fw = [h for h in hits if h.pattern == "falling_wedge"]
    assert fw, f"expected a falling_wedge detection, got: {[h.pattern for h in hits]}"


def test_wedge_ignores_parallel_channel():
    """Two lines with identical slope — not a wedge, should not fire."""
    bars = []
    for i in range(30):
        base = 100 + i * 0.2
        bars.append(_bar(base, base + 2, base, base + 2))
        bars.append(_bar(base + 2, base + 2, base, base))
    df = pd.DataFrame(bars)
    hits = detect_wedge(df)
    # slopes equal → no wedge
    assert not any(h.pattern in ("rising_wedge", "falling_wedge") for h in hits)


# ---------------------------------------------------------------------------
# Break & Retest
# ---------------------------------------------------------------------------

def test_break_and_retest_up_fires_call():
    """50 bars ranging 95-100, then bar closes above 100 (break), pull back to 100, hold, close above."""
    bars = []
    rng = np.random.default_rng(1)
    for _ in range(60):
        p = 97.5 + rng.uniform(-1.5, 1.5)  # range 96-99
        bars.append(_bar(p, min(100, p + 0.5), max(95, p - 0.5), p))
    # break above 100
    bars.append(_bar(99, 102, 99, 102))
    # retest — dip to 100 but hold
    bars.append(_bar(102, 102, 100.1, 100.5))
    bars.append(_bar(100.5, 101.5, 100.2, 101))
    bars.append(_bar(101, 102, 100.5, 101.8))
    df = pd.DataFrame(bars)
    hits = detect_break_and_retest(df, lookback=50, retest_bars=6, tolerance_atr=1.0)
    up = [h for h in hits if h.pattern == "break_and_retest_up"]
    assert up, "expected break_and_retest_up hit"
    assert up[0].direction == "CALL"


def test_break_and_retest_none_on_range():
    """Pure range — no break should be detected."""
    bars = []
    rng = np.random.default_rng(2)
    for _ in range(70):
        p = 100 + rng.uniform(-0.5, 0.5)
        bars.append(_bar(p, p + 0.3, p - 0.3, p))
    df = pd.DataFrame(bars)
    hits = detect_break_and_retest(df, lookback=50, retest_bars=6)
    assert not hits


# ---------------------------------------------------------------------------
# Gap
# ---------------------------------------------------------------------------

def test_gap_up_fires_put_for_fill():
    """20 flat bars then a big open gap up — expect PUT (gap-fill hypothesis)."""
    bars = _flat_series(20, price=100, jitter=0.05)
    bars.append(_bar(103, 103.5, 102.9, 103.2))  # open gap-up from ~100
    df = pd.DataFrame(bars)
    hits = detect_gap(df, min_gap_atr=0.5)
    assert hits
    assert hits[0].pattern == "gap_fill"
    assert hits[0].direction == "PUT"


def test_gap_down_fires_call_for_fill():
    bars = _flat_series(20, price=100, jitter=0.05)
    bars.append(_bar(97, 97.5, 96.9, 97.2))  # open gap-down
    df = pd.DataFrame(bars)
    hits = detect_gap(df, min_gap_atr=0.5)
    assert hits
    assert hits[0].direction == "CALL"


def test_gap_ignores_small_gap():
    bars = _flat_series(20, price=100, jitter=0.05)
    bars.append(_bar(100.05, 100.2, 100.0, 100.1))  # tiny gap
    df = pd.DataFrame(bars)
    hits = detect_gap(df, min_gap_atr=1.0)
    assert not hits


# ---------------------------------------------------------------------------
# detect_all wrapper
# ---------------------------------------------------------------------------

def test_detect_all_empty_frame_returns_empty():
    assert detect_all(pd.DataFrame()) == []


def test_detect_all_missing_columns_returns_empty():
    df = pd.DataFrame({"open": [1, 2, 3]})
    assert detect_all(df) == []


def test_detect_all_returns_pattern_hit_objects():
    df = _build_head_and_shoulders(broken=True)
    hits = detect_all(df)
    for h in hits:
        assert isinstance(h, PatternHit)
        d = h.to_dict()
        assert set(d.keys()) >= {"pattern", "direction", "confidence", "meta"}


# ---------------------------------------------------------------------------
# Confluence engine
# ---------------------------------------------------------------------------

def test_base_weight_lookup_by_family():
    assert _base_weight_for("rsi") == 0.6
    assert _base_weight_for("pattern:head_and_shoulders") == 1.0
    assert _base_weight_for("ml:rf") == 1.2
    assert _base_weight_for("unknown_source_xxx") == 0.5  # default


def test_confluence_neutral_when_no_signals():
    r = score_confluence([])
    assert r["direction"] == "NEUTRAL"
    assert r["confluence_score"] == 0.0


def test_confluence_all_call_produces_call():
    signals = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.8, "timeframe": "1m"},
        {"source": "macd", "direction": "CALL", "confidence": 0.7, "timeframe": "1m"},
        {"source": "pattern:falling_wedge", "direction": "CALL", "confidence": 0.9, "timeframe": "1m"},
    ]
    r = score_confluence(signals, min_sources=2)
    assert r["direction"] == "CALL"
    assert r["confluence_score"] > 0.5
    assert r["put_score"] == 0.0


def test_confluence_conflicting_signals_reduce_score():
    signals = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.9},
        {"source": "macd", "direction": "PUT", "confidence": 0.9},
    ]
    r = score_confluence(signals)
    # score is normalised: neither side dominates
    assert r["confluence_score"] < 0.75


def test_confluence_multi_timeframe_bonus():
    single_tf = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.8, "timeframe": "1m"},
        {"source": "macd", "direction": "CALL", "confidence": 0.8, "timeframe": "1m"},
    ]
    multi_tf = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.8, "timeframe": "1m"},
        {"source": "macd", "direction": "CALL", "confidence": 0.8, "timeframe": "5m"},
    ]
    s1 = score_confluence(single_tf, min_sources=2)
    s2 = score_confluence(multi_tf, min_sources=2)
    assert s2["confluence_score"] > s1["confluence_score"]


def test_confluence_stack_bonus_for_many_sources():
    few = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.7},
        {"source": "macd", "direction": "CALL", "confidence": 0.7},
    ]
    many = few + [
        {"source": "pattern:falling_wedge", "direction": "CALL", "confidence": 0.7},
        {"source": "ml:rf", "direction": "CALL", "confidence": 0.7},
    ]
    r_few = score_confluence(few, min_sources=3)
    r_many = score_confluence(many, min_sources=3)
    assert r_many["confluence_score"] >= r_few["confluence_score"]


def test_should_fire_respects_threshold():
    signals = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.55},
    ]
    r = score_confluence(signals, min_sources=1)
    # low score — must NOT fire
    assert not should_fire(r, threshold=0.8, min_sources=1)


def test_should_fire_requires_min_sources():
    signals = [
        {"source": "rsi", "direction": "CALL", "confidence": 1.0},
    ]
    r = score_confluence(signals, min_sources=3)
    # only 1 source — even at max conf, min_sources gate blocks
    assert not should_fire(r, threshold=0.1, min_sources=3)


def test_should_fire_positive_case():
    signals = [
        {"source": "rsi", "direction": "CALL", "confidence": 0.9, "timeframe": "1m"},
        {"source": "macd", "direction": "CALL", "confidence": 0.9, "timeframe": "5m"},
        {"source": "pattern:falling_wedge", "direction": "CALL", "confidence": 0.9, "timeframe": "1m"},
    ]
    r = score_confluence(signals, min_sources=2)
    assert should_fire(r, threshold=0.4, min_sources=2)


def test_signals_from_patterns_filters_neutral():
    hits = [
        {"pattern": "gap_fill", "direction": "CALL", "confidence": 0.7},
        {"pattern": "wedge", "direction": "NEUTRAL", "confidence": 0.5},
    ]
    out = signals_from_patterns(hits, asset="EURUSD_OTC", timeframe="1m")
    assert len(out) == 1
    assert out[0]["source"] == "pattern:gap_fill"
    assert out[0]["direction"] == "CALL"
    assert out[0]["asset"] == "EURUSD_OTC"


def test_signals_from_patterns_handles_empty():
    assert signals_from_patterns([]) == []
    assert signals_from_patterns(None) == []


# ---------------------------------------------------------------------------
# REST endpoint smoke — direct import (not going through server)
# ---------------------------------------------------------------------------

def test_route_module_imports_and_exposes_config():
    from routes import confluence_routes
    cfg = confluence_routes.get_confluence_config()
    assert "threshold" in cfg and "min_sources" in cfg
    assert cfg["threshold"] == DEFAULT_THRESHOLD
    assert cfg["min_sources"] == DEFAULT_MIN_SOURCES
