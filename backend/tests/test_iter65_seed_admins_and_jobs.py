"""
Iter 65 — SEED_ADMINS + Background Job pattern

A1. POST /api/auth/login with the SEED_ADMINS-provisioned admin account works
A2. GET /api/jobs returns success:true with a list
A3. POST /api/backtest/run-async returns a job_id immediately (<1s)
A4. The submitted job reaches status='completed' within 30s
A5. POST /api/ml/train-from-otc-async returns a job_id immediately
A6. GET /api/jobs/{bad} returns 404
"""
import os
import time
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


def test_seed_admin_login():
    r = requests.post(
        f"{API}/api/auth/login",
        json={"username": "seedtest", "password": "SeedPass123!"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True
    assert j["user"]["role"] == "admin"
    assert j.get("token")


def test_jobs_endpoint_lists_recent():
    r = requests.get(f"{API}/api/jobs?limit=20", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    assert isinstance(j.get("jobs"), list)


def test_backtest_run_async_returns_job_id_immediately():
    t0 = time.time()
    r = requests.post(
        f"{API}/api/backtest/run-async",
        json={
            "strategy": "deep_confluence",
            "symbol": "EURUSD_OTC",
            "timeframe": "5s",
            "days": 1,
        },
        timeout=10,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True
    assert j.get("job_id")
    # The point of the async pattern: the submit must return fast
    assert elapsed < 3.0, f"async submit took {elapsed:.2f}s (should be <3s)"

    job_id = j["job_id"]
    # Poll for completion
    completed = False
    for _ in range(30):
        r2 = requests.get(f"{API}/api/jobs/{job_id}", timeout=10)
        assert r2.status_code == 200
        doc = r2.json()["job"]
        if doc["status"] in ("completed", "failed", "cancelled"):
            completed = True
            assert doc["status"] == "completed", doc
            assert doc["progress"] == 100
            assert doc.get("result") is not None
            break
        time.sleep(1)
    assert completed, "backtest async job didn't finish within 30s"


def test_train_from_otc_async_returns_immediately():
    """Submit only — don't poll for completion (training can take 5+ min)."""
    t0 = time.time()
    r = requests.post(
        f"{API}/api/ml/train-from-otc-async",
        json={"model": "improved", "min_samples": 200},
        timeout=10,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("job_id")
    assert elapsed < 3.0, f"async submit took {elapsed:.2f}s (should be <3s)"
    # Cancel it so it doesn't waste GPU/CPU for the rest of the suite
    requests.delete(f"{API}/api/jobs/{j['job_id']}", timeout=10)


def test_get_unknown_job_404():
    r = requests.get(f"{API}/api/jobs/this-id-does-not-exist", timeout=10)
    assert r.status_code == 404
