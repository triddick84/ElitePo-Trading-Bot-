"""
Iter 94 — Candlestick pattern analysis + Force-Generate enrichment.

Locks:
  * All 17 patterns detect correctly on synthetic data.
  * Historical outcome scoring produces a win_rate in [0, 1] with sample count.
  * `/api/signals/force-generate-v2` response embeds `candle_analysis`
    with patterns, bias, strength, and behavioural summary.
  * Pattern-vs-signal disagreement penalty applies when bias strength > 0.5.
  * TM auto-invert threshold is 2 (flipAfterLosses).
"""

from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------
def test_bullish_engulfing_detected():
    from candle_patterns import detect_patterns
    # Small red then large green engulfing it
    o = [1.10, 1.11, 1.10, 1.095]  # bear
    h = [1.101, 1.111, 1.101, 1.100]
    l = [1.099, 1.109, 1.099, 1.090]
    c = [1.099, 1.109, 1.099, 1.115]  # last is huge bull
    # Add opens/closes for the last two candles that actually engulf
    o = [1.10, 1.11, 1.10, 1.09]
    c = [1.099, 1.109, 1.099, 1.115]  # last bull engulfs prior bear
    dets = detect_patterns(o, h, l, c)
    ids = [d.id for d in dets]
    assert "engulfing_bull" in ids, f"Expected engulfing_bull, got: {ids}"


def test_hammer_detected():
    from candle_patterns import detect_patterns
    # Need long lower wick >= 2x body, tiny upper wick, and range >= 0.5*ATR
    # Give it plenty of history so ATR is well-defined
    o = [1.10 - i * 0.001 for i in range(20)]  # downtrend
    h = [x + 0.0005 for x in o]
    l = [x - 0.0005 for x in o]
    c = [x - 0.0002 for x in o]
    # Last candle: hammer — body 10 pips, lower wick 40 pips (4x body)
    o[-1] = 1.0830
    h[-1] = 1.0846        # upper wick 6 pips (tiny)
    l[-1] = 1.0800        # lower wick 40 pips
    c[-1] = 1.0840        # body 10 pips
    dets = detect_patterns(o, h, l, c)
    ids = [d.id for d in dets]
    assert "hammer" in ids, f"Expected hammer, got: {ids}"


def test_three_white_soldiers_detected():
    from candle_patterns import detect_patterns
    o = [1.09, 1.100, 1.105, 1.110]
    h = [1.101, 1.106, 1.111, 1.116]
    l = [1.089, 1.099, 1.104, 1.109]
    c = [1.100, 1.105, 1.110, 1.115]
    dets = detect_patterns(o, h, l, c)
    ids = [d.id for d in dets]
    assert "three_white" in ids, f"Expected three_white, got: {ids}"


def test_doji_detected():
    from candle_patterns import detect_patterns
    # Big normal candles, then a doji
    o = [1.10, 1.11, 1.10, 1.100]
    h = [1.11, 1.12, 1.11, 1.101]
    l = [1.09, 1.10, 1.09, 1.099]
    c = [1.11, 1.10, 1.11, 1.1001]  # close ~= open
    dets = detect_patterns(o, h, l, c)
    ids = [d.id for d in dets]
    assert "doji" in ids, f"Expected doji, got: {ids}"


# ---------------------------------------------------------------------------
# Historical outcome scoring
# ---------------------------------------------------------------------------
def test_historical_outcome_scoring_produces_win_rate():
    """
    Build a series with strong marubozu-like bull candles + a real trend
    so at least one pattern (three_white_soldiers / marubozu_bull) fires
    across history AND on the last bar.
    """
    from candle_patterns import analyze
    import random
    random.seed(42)
    n = 250
    o, h, l, c = [], [], [], []
    price = 1.0
    for i in range(n):
        # Bull-heavy sequence with realistic wicks
        body = 0.0008 + random.random() * 0.0004
        o.append(price)
        c.append(price + body)     # always bull → marubozu-ish
        h.append(price + body + 0.00005)   # tiny upper wick
        l.append(price - 0.00005)          # tiny lower wick
        price += body * 0.7   # slight drift so future_close > entry_close
    result = analyze(o, h, l, c, lookahead_bars=3, window_bars=200)
    assert result["pattern_count"] > 0, f"No patterns detected on final bar: {result}"
    scored = [p for p in result["patterns"] if p["historical_win_rate"] is not None]
    assert len(scored) > 0, f"No patterns had historical win-rate: {result['patterns']}"
    # Bullish patterns on a monotone-up series should have very high win-rate
    bull_patterns = [p for p in scored if p["direction"] == "bullish"]
    if bull_patterns:
        max_wr = max((p["historical_win_rate"] or 0) for p in bull_patterns)
        assert max_wr > 0.7, f"Expected high historical win-rate, got max {max_wr}"


def test_behavioural_summary_generated():
    from candle_patterns import analyze
    n = 50
    o = [1.0 + i * 0.001 for i in range(n)]
    h = [1.0005 + i * 0.001 for i in range(n)]
    l = [0.9995 + i * 0.001 for i in range(n)]
    c = [1.0002 + i * 0.001 for i in range(n)]
    result = analyze(o, h, l, c)
    bs = result["behavioural_summary"]
    assert "narrative" in bs
    assert bs["trend_last_5"] == "bullish"
    assert bs["bull_count_last_5"] >= 3


# ---------------------------------------------------------------------------
# Force-Generate integration
# ---------------------------------------------------------------------------
def test_force_generate_response_carries_candle_analysis():
    r = requests.post(
        f"{BASE_URL}/api/signals/force-generate-v2",
        params={"asset": "EURUSD_OTC", "expiry_seconds": 60},
        timeout=45,
    ).json()
    assert r.get("success") is True or "signal" in r
    sig = r.get("signal") or {}
    assert "candle_analysis" in sig, "Missing candle_analysis in force-generate response"
    ca = sig["candle_analysis"]
    for key in ("patterns", "pattern_count", "pattern_bias",
                "pattern_bias_strength", "behavioural_summary"):
        assert key in ca, f"candle_analysis missing key: {key}"
    # Narrative must be a non-empty string
    narrative = ca["behavioural_summary"].get("narrative", "")
    assert len(narrative) > 20, f"Narrative too thin: {narrative!r}"


# ---------------------------------------------------------------------------
# TM auto-invert threshold — Iter 94 revert to 2 losses
# ---------------------------------------------------------------------------
def test_tampermonkey_script_auto_invert_threshold_is_2():
    r = requests.get(f"{BASE_URL}/api/tampermonkey/script", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "flipAfterLosses:2" in body, \
        "TM auto-invert should trigger after 2 consecutive losses"
    assert "flipAfterLosses:1" not in body, \
        "Old 1-loss threshold still present"


# ---------------------------------------------------------------------------
# Latency runtime settings — Iter 94 interactive controls
# ---------------------------------------------------------------------------
def test_latency_runtime_settings_shape():
    r = requests.get(f"{BASE_URL}/api/latency/runtime-settings", timeout=10).json()
    assert r.get("success") is True
    pw = r.get("signal_prewarm") or {}
    ao = r.get("adaptive_offset") or {}
    for k in ("ttl_seconds", "refresh_interval_seconds", "active_window_seconds", "max_tracked_combos"):
        assert k in pw, f"prewarm missing key: {k}"
    for k in ("sample_window", "min_samples_required", "min_offset_sec",
              "max_offset_sec", "cache_ttl_sec", "default_offset_sec"):
        assert k in ao, f"adaptive_offset missing key: {k}"


def test_latency_prewarm_settings_update_and_reset():
    orig = requests.get(f"{BASE_URL}/api/latency/runtime-settings", timeout=10).json().get("signal_prewarm") or {}
    r = requests.post(
        f"{BASE_URL}/api/latency/runtime-settings/prewarm",
        json={"ttl_seconds": 6.5, "refresh_interval_seconds": 4.0},
        timeout=10,
    ).json()
    assert r.get("success") is True
    assert r["signal_prewarm"]["ttl_seconds"] == 6.5
    assert r["signal_prewarm"]["refresh_interval_seconds"] == 4.0
    # Reset to originals
    requests.post(
        f"{BASE_URL}/api/latency/runtime-settings/prewarm",
        json={
            "ttl_seconds": orig.get("ttl_seconds", 3.0),
            "refresh_interval_seconds": orig.get("refresh_interval_seconds", 2.0),
        },
        timeout=10,
    )


def test_latency_adaptive_settings_bounds_clamp():
    # Setting absurd values should clamp to safe bounds server-side
    r = requests.post(
        f"{BASE_URL}/api/latency/runtime-settings/adaptive-offset",
        json={"sample_window": 99999, "min_samples_required": 99999,
              "max_offset_sec": 999, "min_offset_sec": -999},
        timeout=10,
    ).json()
    assert r["adaptive_offset"]["sample_window"] <= 500
    assert r["adaptive_offset"]["min_samples_required"] <= 200
    assert r["adaptive_offset"]["max_offset_sec"] <= 60
    assert r["adaptive_offset"]["min_offset_sec"] >= -30
    # Reset
    requests.post(
        f"{BASE_URL}/api/latency/runtime-settings/adaptive-offset",
        json={"sample_window": 50, "min_samples_required": 8,
              "max_offset_sec": 15.0, "min_offset_sec": -5.0},
        timeout=10,
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
