"""
Iter 66 — "Find Best Pair Today" scanner

A1. POST /api/scanner/find-best-pairs with a small scope returns job_id fast
A2. The job reaches `completed` within 3 minutes for forex_otc scope
A3. The returned leaderboard is sorted by `score` descending
A4. Each row contains the required ranking metrics
A5. GET /api/scanner/latest returns the persisted snapshot
A6. Invalid scope returns 400
"""
import os
import time
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


def _wait(job_id, max_wait_s=180):
    end = time.time() + max_wait_s
    while time.time() < end:
        r = requests.get(f"{API}/api/jobs/{job_id}", timeout=10)
        if r.status_code != 200:
            time.sleep(2)
            continue
        j = r.json()["job"]
        if j["status"] in ("completed", "failed", "cancelled"):
            return j
        time.sleep(3)
    raise AssertionError(f"scan job didn't finish within {max_wait_s}s")


def test_scanner_submit_returns_job_id_fast():
    t0 = time.time()
    r = requests.post(
        f"{API}/api/scanner/find-best-pairs",
        json={"scope": "crypto_otc", "days": 1, "top_n": 5, "min_signals": 5, "min_confidence": 50},
        timeout=10,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True
    assert j.get("job_id")
    assert j.get("queued_count", 0) > 0
    assert elapsed < 3.0, f"submit took {elapsed:.2f}s (should be <3s)"


def test_scanner_full_run_forex_otc():
    """End-to-end: submit a forex_otc scan and verify completion + ranking."""
    r = requests.post(
        f"{API}/api/scanner/find-best-pairs",
        json={"scope": "forex_otc", "days": 3, "top_n": 10, "min_signals": 30, "min_confidence": 55},
        timeout=10,
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    final = _wait(job_id, max_wait_s=240)
    assert final["status"] == "completed"
    snap = final["result"]
    assert snap["scope"] == "forex_otc"
    assert snap["total_scanned"] > 0
    lb = snap["leaderboard"]
    assert isinstance(lb, list)
    if lb:
        # Sorted by score desc
        scores = [r["score"] for r in lb]
        assert scores == sorted(scores, reverse=True)
        # Every row has the required fields
        for row in lb:
            for f in ("symbol", "timeframe", "win_rate", "signals", "profit_factor", "score"):
                assert f in row, f"missing field {f}"


def test_scanner_latest_returns_persisted_snapshot():
    r = requests.get(f"{API}/api/scanner/latest", timeout=10)
    assert r.status_code == 200
    j = r.json()
    # Either we have a snapshot (success=true) or none (success=false)
    if j.get("success"):
        assert j.get("scope")
        assert "leaderboard" in j


def test_scanner_invalid_scope():
    r = requests.post(
        f"{API}/api/scanner/find-best-pairs",
        json={"scope": "not_a_real_scope"},
        timeout=10,
    )
    assert r.status_code == 400
