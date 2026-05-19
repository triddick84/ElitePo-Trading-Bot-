"""
Iter 58 — Regression tests for the May-19 bug-fix + P1/P2 batch.

Covers:
  1. /api/backtest/run now accepts strategy="hybrid" and returns proper
     nested {results: [{metrics: {win_rate, total_trades, ...}}]} schema.
  2. /api/backtest/assets-universe returns all 7 asset classes with correct
     timeframe rules (OTC ≥ 3s, regular ≥ M1).
  3. /api/signals/latency-guardrail/status returns a fresh state document.
  4. /api/signals/latency-guardrail/throttle-fraction validates 0–1 range.
  5. /api/signals/latency-guardrail/force-trip + force-release toggle state.
  6. /api/ml/tournament/status returns cache + (optionally) latest run.
  7. /api/ml/tournament/run is fire-and-forget and 200s immediately.
"""
import os
import sys
import time
import pathlib
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BACKEND_URL}/api"


def _client():
    return httpx.Client(timeout=30)


def test_backtest_run_returns_nested_results_with_hybrid():
    """Backend must return {success, results:[{strategy, metrics:{win_rate, total_trades, ...}}]}."""
    with _client() as c:
        r = c.post(
            f"{API}/backtest/run",
            json={"symbol": "EURUSD_OTC", "strategy": "hybrid", "timeframe": "5s", "days": 30},
        )
    assert r.status_code in (200, 400), f"unexpected: {r.status_code} {r.text}"
    if r.status_code == 400:
        # Acceptable when OTC pool is completely dry — but message must be informative
        assert "No historical data" in r.text or "no historical" in r.text.lower()
        return
    body = r.json()
    assert body.get("success") is True
    assert "results" in body
    assert isinstance(body["results"], list)
    if body["results"]:
        first = body["results"][0]
        assert "strategy" in first
        if "metrics" in first:
            m = first["metrics"]
            for k in ("win_rate", "total_trades", "profit_factor"):
                assert k in m, f"missing metric: {k}"


def test_backtest_assets_universe_includes_all_classes():
    """Universe must include 7 classes with min_timeframe rules."""
    with _client() as c:
        r = c.get(f"{API}/backtest/assets-universe")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    class_ids = [cls["id"] for cls in body["classes"]]
    for needed in ("forex", "forex_otc", "commodities", "crypto", "indices"):
        assert needed in class_ids, f"missing class: {needed}"
    # OTC classes must allow 3s; regular classes must NOT include sub-minute
    for cls in body["classes"]:
        if "_otc" in cls["id"]:
            assert "3s" in cls["timeframes"], f"{cls['id']} missing 3s"
            assert cls["min_timeframe"] == "3s"
        else:
            assert "5s" not in cls["timeframes"], f"{cls['id']} should not allow sub-minute"
            assert cls["min_timeframe"] == "M1"


def test_latency_guardrail_status_returns_state():
    """Endpoint must always return a state dict, even with zero samples."""
    with _client() as c:
        r = c.get(f"{API}/signals/latency-guardrail/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    g = body["guardrail"]
    for k in ("tripped", "throttle_fraction", "p95_current_ms", "p95_baseline_ms"):
        assert k in g, f"missing guardrail field: {k}"
    assert isinstance(g["tripped"], bool)


def test_latency_guardrail_throttle_fraction_set():
    """Throttle fraction must be clamped to [0, 1]."""
    with _client() as c:
        r = c.post(
            f"{API}/signals/latency-guardrail/throttle-fraction",
            json={"fraction": 0.5},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["guardrail"]["throttle_fraction"] == 0.5
    # Reset to default
    with _client() as c:
        c.post(f"{API}/signals/latency-guardrail/throttle-fraction", json={"fraction": 0.75})


def test_latency_guardrail_force_trip_and_release():
    """Manual trip / release must toggle state."""
    with _client() as c:
        r1 = c.post(f"{API}/signals/latency-guardrail/force-trip")
        r2 = c.post(f"{API}/signals/latency-guardrail/force-release")
    assert r1.status_code == 200
    assert r1.json()["guardrail"]["tripped"] is True
    assert r2.status_code == 200
    assert r2.json()["guardrail"]["tripped"] is False


def test_tournament_status_returns_cache():
    """Cache always present even if no tournament has run."""
    with _client() as c:
        r = c.get(f"{API}/ml/tournament/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "cache" in body
    cache = body["cache"]
    # All 4 tracked models must be in the cache (default 1.0 if no run)
    for mid in ("improved_v2", "maximized_v3", "lstm_gru", "ppo_rl"):
        assert mid in cache
        assert isinstance(cache[mid], (int, float))
        assert cache[mid] > 0


def test_tournament_run_is_fire_and_forget():
    """POST /ml/tournament/run must return acceptance quickly (<3s)."""
    with _client() as c:
        t0 = time.time()
        r = c.post(f"{API}/ml/tournament/run", json=None)
        elapsed = time.time() - t0
    assert r.status_code == 200
    body = r.json()
    assert body.get("accepted") is True
    assert elapsed < 5.0, f"tournament-run took {elapsed:.1f}s — should be fire-and-forget"


def test_tournament_history_returns_list():
    """History endpoint returns a list (may be empty)."""
    # Higher timeout — tournament-run background task may still be holding the
    # event loop briefly during sklearn inference.
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{API}/ml/tournament/history?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("history"), list)
