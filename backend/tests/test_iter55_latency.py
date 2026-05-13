"""
Iteration 55 — Latency monitoring regression tests.

Covers:
  1. /api/signals/force-generate-v2 surfaces a `latency` block on every signal.
  2. /api/signals/latency-budgets returns per-timeframe budgets.
  3. /api/signals/latency-health reports green/yellow/red/grey state.
  4. /api/signals/latency-stats aggregates correctly (count, percentiles, phase means).
  5. /api/signals/latency-report stores client-side timings.
  6. Auto-abstain triggers when total_ms > budget (via direct unit test on the
     LatencyTracker since we can't easily simulate >1500ms in CI).

Run: pytest -xvs backend/tests/test_iter55_latency.py
"""
import os
import time
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"


def test_force_generate_v2_includes_latency_block():
    """Every signal must carry a `latency` dict with total_ms, budget_ms, exceeded, phases."""
    r = requests.post(
        f"{API}/signals/force-generate-v2",
        params={"asset": "EURUSD_OTC", "expiry_seconds": 60},
        timeout=30,
    )
    assert r.status_code == 200
    sig = r.json().get("signal", {})
    lat = sig.get("latency")
    assert lat is not None, "signal.latency block missing"
    for key in ("total_ms", "budget_ms", "exceeded", "headroom_ms", "phases"):
        assert key in lat, f"latency.{key} missing"
    assert lat["total_ms"] > 0
    assert lat["budget_ms"] >= 1500
    assert isinstance(lat["phases"], dict)
    # At minimum we expect otc_fetch + abstain_gate (ml_prediction only if models trained)
    assert any(p in lat["phases"] for p in ("otc_fetch", "abstain_gate"))


def test_latency_budgets_endpoint():
    r = requests.get(f"{API}/signals/latency-budgets", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    budgets = body["budgets_ms"]
    # Spot-check the timeframe budgets
    assert budgets["5s"] == 1500
    assert budgets["15s"] == 3000
    assert budgets["1m"] == 8000
    assert budgets["default"] == 5000


def test_latency_health_chip_states():
    """Health endpoint should return a coloured status snapshot."""
    # Generate at least one signal to populate the window
    requests.post(
        f"{API}/signals/force-generate-v2",
        params={"asset": "EURUSD_OTC", "expiry_seconds": 5},
        timeout=30,
    )
    time.sleep(0.5)
    r = requests.get(f"{API}/signals/latency-health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["color"] in ("green", "yellow", "red", "grey")
    assert body["status"] in ("healthy", "warning", "degraded", "no_data")


def test_latency_stats_aggregates():
    # Fire a few signals to populate stats
    for asset in ("EURUSD_OTC", "GBPUSD_OTC", "AUDCHF_OTC"):
        requests.post(
            f"{API}/signals/force-generate-v2",
            params={"asset": asset, "expiry_seconds": 60},
            timeout=30,
        )
    time.sleep(0.5)
    r = requests.get(
        f"{API}/signals/latency-stats",
        params={"since_minutes": 60},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["count"] >= 3
    stats = body["stats"]
    assert stats is not None
    for key in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "min_ms",
                "exceeded_count", "exceeded_rate", "phase_means_ms"):
        assert key in stats
    # Percentile invariants
    assert stats["p50_ms"] <= stats["p95_ms"] <= stats["p99_ms"] <= stats["max_ms"]


def test_client_latency_report_endpoint():
    r = requests.post(
        f"{API}/signals/latency-report",
        json={
            "signal_id": "test-iter55-sig",
            "asset": "EURUSD_OTC",
            "strategy": "5s_heikin_fractal",
            "network_rtt_ms": 50.5,
            "dom_click_lag_ms": 22.0,
            "exec_lag_ms": 215.0,
            "notes": "iter55 regression",
        },
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["stored"] is True


def test_latency_tracker_auto_abstain_on_budget_exceeded():
    """Unit-level: LatencyTracker exceeded flag flips when budget < total."""
    from latency_monitor import LatencyTracker, budget_for
    tracker = LatencyTracker(asset="EURUSD_OTC", timeframe="5s")
    # Sleep just over the 5s budget (1500ms) — small actual sleep + manual addition
    with tracker.phase("otc_fetch"):
        time.sleep(0.05)
    tracker.add_phase_ms("ml_prediction", 1800)  # synthetic overage
    # Force total above budget by setting start time backwards
    tracker.start_ts -= 1.6  # subtract 1600ms from "now"
    report = tracker.finalize()
    assert report["budget_ms"] == 1500
    assert report["total_ms"] > 1500
    assert report["exceeded"] is True
    assert report["headroom_ms"] < 0
    assert "otc_fetch" in report["phases"]
    assert report["phases"]["ml_prediction"] >= 1800

    # budget_for fallback
    assert budget_for("nonexistent_tf") == 5000  # default
