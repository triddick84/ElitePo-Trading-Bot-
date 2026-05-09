"""
Iteration 53 — Regression tests for the post-Iter-52 follow-up fixes:

  1. POST /api/custom-strategies/{id}/test no longer 500s (RealMarketDataService /
     AssetType / get_strategy_executor are imported lazily in the handler).
  2. /api/strategies/available auto-discovers strategies registered in
     strategy_registry that aren't in the curated AVAILABLE_STRATEGIES list.
  3. POST /api/ml/scheduler/trigger returns instantly (fire-and-forget) instead
     of blocking for the 2-3 min retrain.
  4. New strategy-aware abstain endpoints (get/set/list/optimize/effective).

Run: pytest -xvs backend/tests/test_iter53_followups.py
"""
import os
import time
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"


def test_custom_strategies_test_endpoint_no_500():
    """Verify POST /api/custom-strategies/{id}/test is not 500 anymore."""
    # Find any existing custom strategy
    r = requests.get(f"{API}/custom-strategies", timeout=10)
    assert r.status_code == 200, f"list strategies failed: {r.status_code}"
    strategies = r.json().get("strategies", [])
    if not strategies:
        pytest.skip("no custom strategies in DB to test against")
    sid = strategies[0]["id"]

    r = requests.post(
        f"{API}/custom-strategies/{sid}/test",
        params={"asset": "EURUSD", "timeframe": "1m"},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    # Either it returns a signal or gracefully reports no market data.
    # Both are acceptable; what matters is that we don't hit the old
    # 'RealMarketDataService is not defined' NameError.
    assert "success" in body
    assert "RealMarketDataService" not in body.get("error", "")


def test_strategies_available_auto_discovers_registry_entries():
    """
    The selection service should now expose every strategy_registry entry
    in addition to the curated list. Prior to Iter 53 this was hard-coded;
    new strategies (e.g. 5s_momentum_breakout) wouldn't appear.
    """
    r = requests.get(f"{API}/strategies/available", timeout=10)
    assert r.status_code == 200
    strategies = r.json()["strategies"]

    # 5s_heikin_fractal is curated AND registered — must appear
    ids_5s = {s["id"] for s in strategies.get("5s", [])}
    assert "5s_heikin_fractal" in ids_5s

    # 5s_momentum_breakout / 5s_price_action are ONLY in the registry, not
    # curated. The auto-discovery layer should surface them.
    assert "5s_momentum_breakout" in ids_5s
    assert "5s_price_action" in ids_5s


def test_scheduler_trigger_returns_immediately():
    """
    Manual retrain trigger must respond in well under the ingress timeout
    (Kubernetes default ~60s). Retrain itself runs in background.
    """
    t0 = time.time()
    r = requests.post(f"{API}/ml/scheduler/trigger", timeout=10)
    elapsed = time.time() - t0

    assert r.status_code == 200
    body = r.json()
    # Either accepted (kick-off) or rejected with a clear message (cooldown /
    # already running). Both are non-blocking.
    assert "success" in body or "accepted" in body
    assert elapsed < 5.0, f"trigger should be fire-and-forget, took {elapsed:.2f}s"


def test_strategy_abstain_endpoints():
    """All five strategy-aware abstain endpoints respond with valid shape."""
    sid = "5s_heikin_fractal"
    asset = "EURUSD_OTC"

    # 1) GET strategy threshold (default fallback)
    r = requests.get(
        f"{API}/ml/abstain/strategy-threshold",
        params={"strategy_id": sid, "asset": asset},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["strategy_id"] == sid
    assert 0.5 <= body["threshold"] <= 0.95

    # 2) POST manual override
    r = requests.post(
        f"{API}/ml/abstain/strategy-threshold",
        params={"strategy_id": sid, "asset": asset, "threshold": 0.71},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["threshold"] == 0.71

    # 3) GET strategy threshold again — should return stored manual value
    r = requests.get(
        f"{API}/ml/abstain/strategy-threshold",
        params={"strategy_id": sid, "asset": asset},
        timeout=10,
    )
    body = r.json()
    assert body["threshold"] == 0.71
    assert body["method"] == "manual"

    # 4) GET effective threshold — should resolve to strategy source
    r = requests.get(
        f"{API}/ml/abstain/effective-threshold",
        params={"strategy_id": sid, "asset": asset},
        timeout=10,
    )
    body = r.json()
    assert body["source"] == "strategy"
    assert body["threshold"] == 0.71

    # 5) GET list, filtered by strategy
    r = requests.get(
        f"{API}/ml/abstain/strategy-thresholds",
        params={"strategy_id": sid},
        timeout=10,
    )
    body = r.json()
    assert any(t["strategy_id"] == sid and t["asset"] == asset for t in body["thresholds"])
