"""
Iteration 47 — Fibonacci Confluence + Triple Confirmation BETA strategies.

Covers:
  • /api/strategies/available/{30s,1m,5m} surfaces new BETA entries
  • /api/signals/force-generate-v2 exposes component.beta and signal.beta
  • Confidence quality clamps (LOW ≤ 65, MEDIUM ≤ 75, HIGH ≤ 82)
  • Direct strategy_registry.execute_strategy on a crafted DataFrame
  • Regression: /api/trades/report + /api/trades/outcome + /api/signals/win-rate-stats
"""
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback only for local shell (CI will provide it)
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")

# Allow `import strategy_registry` for the direct-execution test.
sys.path.insert(0, "/app/backend")

NEW_FIB_IDS = {"30s_fibonacci_confluence", "1m_fibonacci_confluence", "5m_fibonacci_confluence"}
NEW_TRIPLE_IDS = {"30s_triple_confirmation", "1m_triple_confirmation", "5m_triple_confirmation"}
ALL_NEW_IDS = NEW_FIB_IDS | NEW_TRIPLE_IDS


# ─────────────────────────────────────────────────────────────
# Feature: /api/strategies/available/{timeframe} — BETA entries
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tf,expected_ids", [
    ("30s", {"30s_fibonacci_confluence", "30s_triple_confirmation"}),
    ("1m", {"1m_fibonacci_confluence", "1m_triple_confirmation"}),
    ("5m", {"5m_fibonacci_confluence", "5m_triple_confirmation"}),
])
def test_available_strategies_include_beta(tf, expected_ids):
    r = requests.get(f"{BASE_URL}/api/strategies/available/{tf}", timeout=20)
    assert r.status_code == 200, f"{tf}: status {r.status_code} body={r.text[:300]}"
    body = r.json()
    assert body.get("success") is True
    strategies = body.get("strategies") or []
    assert isinstance(strategies, list) and len(strategies) > 0
    ids = {s.get("id") for s in strategies}
    missing = expected_ids - ids
    assert not missing, f"{tf}: missing {missing}. got={sorted(ids)}"
    # The new entries must have beta:true
    for s in strategies:
        if s.get("id") in expected_ids:
            assert s.get("beta") is True, f"{tf}/{s.get('id')} must carry beta:true, got {s}"


# ─────────────────────────────────────────────────────────────
# Feature: force-generate-v2 — components carry new keys + beta
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def force_signal():
    r = requests.post(
        f"{BASE_URL}/api/signals/force-generate-v2",
        params={"asset": "EURUSD_OTC", "expiry_seconds": 60},
        timeout=60,
    )
    assert r.status_code == 200, f"status {r.status_code} body={r.text[:400]}"
    body = r.json()
    assert body.get("success") is True
    assert "signal" in body and isinstance(body["signal"], dict)
    return body


def test_force_generate_components_contain_new_strategies(force_signal):
    signal = force_signal["signal"]
    components = signal.get("components") or {}
    # If candles were insufficient we accept the fallback but we still want
    # to flag it loudly so the main agent knows data was missing.
    if signal.get("analysis_type") == "force_fallback":
        pytest.skip(f"OANDA candles unavailable in preview env — got fallback: {signal.get('reason')}")
    missing = ALL_NEW_IDS - set(components.keys())
    assert not missing, f"components missing {missing}. got={sorted(components.keys())}"


def test_force_generate_components_have_beta_flag(force_signal):
    signal = force_signal["signal"]
    if signal.get("analysis_type") == "force_fallback":
        pytest.skip("fallback path — no components")
    components = signal["components"]
    for sid in ALL_NEW_IDS:
        comp = components.get(sid)
        assert comp is not None, f"component {sid} missing"
        assert "beta" in comp, f"component {sid} missing 'beta' key"
        assert comp["beta"] is True, f"component {sid} beta must be True, got {comp}"


def test_force_generate_signal_beta_is_boolean(force_signal):
    """signal.beta MUST be boolean (true/false) — never None/missing."""
    signal = force_signal["signal"]
    if signal.get("analysis_type") == "force_fallback":
        pytest.skip("fallback path")
    assert "beta" in signal, (
        "signal.beta is MISSING from /api/signals/force-generate-v2 response. "
        "Review request requires it to be boolean (true if all directionally-agreeing "
        "strategies are beta, else false)."
    )
    assert isinstance(signal["beta"], bool), (
        f"signal.beta must be bool, got {type(signal['beta']).__name__}={signal['beta']}"
    )


def test_force_generate_confidence_clamps(force_signal):
    signal = force_signal["signal"]
    if signal.get("analysis_type") == "force_fallback":
        pytest.skip("fallback path")
    quality = signal.get("quality")
    conf = float(signal.get("confidence", 0))
    assert quality in {"LOW", "MEDIUM", "HIGH"}, f"unexpected quality={quality}"
    if quality == "LOW":
        assert conf <= 65.0 + 1e-6, f"LOW conf={conf} must be ≤ 65"
    elif quality == "MEDIUM":
        assert conf <= 75.0 + 1e-6, f"MEDIUM conf={conf} must be ≤ 75"
    else:  # HIGH
        assert conf <= 82.0 + 1e-6, f"HIGH conf={conf} must be ≤ 82"


# ─────────────────────────────────────────────────────────────
# Feature: strategy_registry — direct execution on crafted df
# ─────────────────────────────────────────────────────────────
def _synthetic_downtrend_pullback_df(n: int = 60) -> pd.DataFrame:
    """
    Craft a DF with: strong downtrend → pullback up to ~0.5 Fib → bearish engulfing with volume spike.
    Aim to make FibonacciConfluenceStrategy fire PUT.
    """
    rng = np.random.default_rng(42)
    # Start high and drift down for the first 40 bars (impulse down)
    base = 1.2000
    closes = []
    highs = []
    lows = []
    opens = []
    vols = []
    price = base
    # Downtrend leg
    for _ in range(40):
        o = price
        price -= 0.0010 + rng.uniform(0, 0.0003)
        c = price
        h = max(o, c) + rng.uniform(0, 0.0002)
        l_ = min(o, c) - rng.uniform(0, 0.0002)
        opens.append(o); closes.append(c); highs.append(h); lows.append(l_); vols.append(rng.uniform(800, 1200))
    swing_lo = price
    # Pullback up ~50% of the move
    impulse = base - swing_lo
    target = swing_lo + impulse * 0.5
    steps = 15
    for i in range(steps):
        o = price
        price += impulse * 0.5 / steps + rng.uniform(-0.0001, 0.0002)
        c = price
        h = max(o, c) + rng.uniform(0, 0.0002)
        l_ = min(o, c) - rng.uniform(0, 0.0002)
        opens.append(o); closes.append(c); highs.append(h); lows.append(l_); vols.append(rng.uniform(800, 1200))
    # Bearish engulfing at Fib 0.5 with volume spike
    o1 = price
    c1 = price + 0.0003  # small bull
    opens.append(o1); closes.append(c1)
    highs.append(c1 + 0.0001); lows.append(o1 - 0.0001); vols.append(1000)
    # big bearish bar engulfing previous
    o2 = c1 + 0.0002
    c2 = o1 - 0.0008
    opens.append(o2); closes.append(c2)
    highs.append(o2 + 0.0001); lows.append(c2 - 0.0001); vols.append(3500)  # volume spike
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols,
    })
    return df


def test_registry_has_all_new_keys():
    from strategy_registry import strategy_registry
    missing = ALL_NEW_IDS - set(strategy_registry.strategies.keys())
    assert not missing, f"strategy_registry missing: {missing}"


def test_registry_execute_fibonacci_1m_on_crafted_df():
    from strategy_registry import strategy_registry
    df = _synthetic_downtrend_pullback_df()
    result = strategy_registry.execute_strategy("1m_fibonacci_confluence", df)
    assert isinstance(result, dict)
    # Required keys regardless of direction
    for k in ("direction", "confidence", "reason", "strategy", "beta", "timeframe"):
        assert k in result, f"result missing key '{k}'. got={result}"
    assert result["beta"] is True
    assert result["timeframe"] == "1m"
    # Must be a valid direction label
    assert result["direction"] in {"CALL", "PUT", "NEUTRAL"}
    # expiry_seconds is required when strategy fires (CALL/PUT) per spec
    if result["direction"] in {"CALL", "PUT"}:
        assert "expiry_seconds" in result
        assert 60 <= float(result["confidence"]) <= 82


def test_registry_execute_triple_confirmation_1m():
    from strategy_registry import strategy_registry
    df = _synthetic_downtrend_pullback_df()
    result = strategy_registry.execute_strategy("1m_triple_confirmation", df)
    assert isinstance(result, dict)
    for k in ("direction", "confidence", "reason", "strategy", "beta", "timeframe"):
        assert k in result, f"result missing key '{k}'. got={result}"
    assert result["beta"] is True


# ─────────────────────────────────────────────────────────────
# Regression: /api/trades/report → /api/trades/outcome → win-rate
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def reported_trade_id():
    trade_id = f"TEST_ITER47_{uuid.uuid4().hex[:10]}"
    payload = {
        "trade_id": trade_id,
        "asset": "EURUSD_OTC",
        "direction": "CALL",
        "amount": 1.0,
        "strategy": "1m_fibonacci_confluence",
        "confidence": 70.0,
        "expiry_seconds": 60,
        "placed_at": datetime.now(timezone.utc).isoformat(),
    }
    r = requests.post(f"{BASE_URL}/api/trades/report", json=payload, timeout=20)
    assert r.status_code == 200, f"report status={r.status_code} body={r.text[:300]}"
    body = r.json()
    assert body.get("success") is True, body
    return trade_id


def test_trades_outcome_records(reported_trade_id):
    payload = {
        "trade_id": reported_trade_id,
        "outcome": "WIN",
        "payout": 1.85,
    }
    r = requests.post(f"{BASE_URL}/api/trades/outcome", json=payload, timeout=20)
    assert r.status_code == 200, f"outcome status={r.status_code} body={r.text[:300]}"
    body = r.json()
    assert body.get("success") is True, body


def test_win_rate_stats_endpoint():
    # Give Mongo a moment to flush the write above
    time.sleep(1.0)
    r = requests.get(f"{BASE_URL}/api/signals/win-rate-stats", timeout=20)
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
    body = r.json()
    # Response shape should include buckets like last_50/last_100/last_500
    assert isinstance(body, dict)
    # Accept either 'success' or presence of buckets
    has_any_bucket = any(k in body for k in ("last_50", "last_100", "last_500", "buckets", "stats"))
    assert has_any_bucket or body.get("success") is not None, f"unexpected shape: {body}"
