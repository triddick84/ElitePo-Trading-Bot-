"""
Iteration 56c — TM script latency-report wiring regression tests.

Covers:
  1. /api/signals/latency-report stores valid TM-style payloads
  2. /api/signals/latency-stats now returns a `client` summary block with
     network RTT / DOM click lag / exec lag means + notes breakdown
  3. The latency endpoint rejects empty payloads gracefully (no crash)
  4. Stored client docs persist asset/strategy/signal_id correctly
  5. Empty client-side history still returns count=0 cleanly

Run: pytest -xvs backend/tests/test_iter56c_latency_report.py
"""
import os
import time
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"


def _post_report(**kwargs):
    """Helper that posts a latency report and returns the response body."""
    default = {
        "signal_id": kwargs.get("signal_id", f"iter56c-{int(time.time() * 1000)}"),
        "asset": "EURUSD_OTC",
        "strategy": "5s_heikin_fractal",
        "network_rtt_ms": 45.0,
        "dom_click_lag_ms": 18.0,
        "exec_lag_ms": 220.0,
        "notes": "executed:app",
    }
    default.update(kwargs)
    r = requests.post(f"{API}/signals/latency-report", json=default, timeout=10)
    return r


def test_latency_report_stores_tm_payload():
    """TM-style latency report must be accepted and persisted."""
    r = _post_report(notes="iter56c:test_store")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["stored"] is True


def test_latency_stats_includes_client_block():
    """/signals/latency-stats must surface a `client` aggregate block."""
    # Push at least 2 distinct TM-style reports
    _post_report(notes="executed:app", network_rtt_ms=40, exec_lag_ms=210)
    _post_report(notes="gated:cooldown", network_rtt_ms=55, exec_lag_ms=None)
    time.sleep(0.2)
    
    r = requests.get(f"{API}/signals/latency-stats", params={"since_minutes": 60}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    client = body.get("client")
    assert client is not None
    assert client["count"] >= 2
    # At least one of the means must be populated
    assert any(client[k] is not None for k in
               ("network_rtt_mean_ms", "dom_click_lag_mean_ms", "exec_lag_mean_ms"))
    assert isinstance(client["notes_breakdown"], dict)


def test_latency_stats_empty_window_still_returns_client_block():
    """Filter by an asset that we never report on — client block still present."""
    r = requests.get(
        f"{API}/signals/latency-stats",
        params={"since_minutes": 60, "asset": "NEVER_SEEN_OTC"},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "client" in body
    # When asset filter matches nothing, count should be 0
    assert body["client"]["count"] == 0


def test_latency_report_persists_correct_fields():
    """Round-trip: post a report and verify fields land in the stats aggregate."""
    sid = f"iter56c-roundtrip-{int(time.time() * 1000)}"
    _post_report(
        signal_id=sid,
        asset="EURUSD_OTC",
        strategy="iter56c-test-strategy",
        network_rtt_ms=99.9,
        dom_click_lag_ms=11.1,
        exec_lag_ms=222.2,
        notes="executed:roundtrip",
    )
    time.sleep(0.2)
    r = requests.get(
        f"{API}/signals/latency-stats",
        params={"since_minutes": 60, "strategy": "iter56c-test-strategy"},
        timeout=10,
    )
    body = r.json()
    client = body["client"]
    # All three TM-side metrics should be reflected
    assert client["count"] >= 1
    assert client["network_rtt_mean_ms"] == 99.9
    assert client["dom_click_lag_mean_ms"] == 11.1
    assert client["exec_lag_mean_ms"] == 222.2
    assert "executed" in client["notes_breakdown"]


def test_latency_report_skips_completely_empty_payload():
    """Empty payload should still 200 (server stores `notes`-only records)."""
    r = requests.post(
        f"{API}/signals/latency-report",
        json={"signal_id": "iter56c-empty"},
        timeout=10,
    )
    # Server logic accepts the call (stores doc), so success=True with metric-less doc
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
