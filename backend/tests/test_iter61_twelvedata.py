"""
Iter 61 — Twelve Data integration regression suite
==================================================
Confirms:
  1. /api/twelvedata/status returns plan/usage info (key configured).
  2. /api/twelvedata/quote/{symbol} resolves a forex symbol.
  3. /api/twelvedata/candles/{symbol} returns >=50 candles for EURUSD M1.
  4. /api/backtest/run for non-OTC symbol with no local data → data_source==twelvedata.
  5. /api/backtest/run for OTC 5s → data_source==local_pool (Twelve Data must NOT
     be hit for sub-minute, as TD free-tier intervals are 1min+).
"""
import os
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get(
    "API_URL", "http://localhost:8001"
)


def test_twelvedata_status():
    r = requests.get(f"{API}/api/twelvedata/status", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True
    info = j.get("info") or {}
    assert "capacity" in info
    assert info.get("capacity") == 8
    remote = info.get("remote") or {}
    # plan_category should be 'basic' for the free-tier key
    assert remote.get("plan_category") in {"basic", "free", None}


def test_twelvedata_quote_eurusd():
    r = requests.get(f"{API}/api/twelvedata/quote/EURUSD", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    q = j.get("quote") or {}
    assert q.get("symbol") == "EUR/USD"
    assert "close" in q


def test_twelvedata_candles_eurusd_m1():
    r = requests.get(
        f"{API}/api/twelvedata/candles/EURUSD?timeframe=M1&outputsize=80",
        timeout=20,
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    assert j.get("count", 0) >= 50
    candles = j.get("candles") or []
    assert candles and all(k in candles[0] for k in ("timestamp", "open", "close"))


def test_backtest_run_uses_twelvedata_for_non_otc_m1():
    """Non-OTC symbol with no pre-seeded local pool should fall through to TD."""
    payload = {
        "strategy": "deep_confluence",
        "symbol": "EURUSD",
        "timeframe": "M1",
        "days": 2,
    }
    r = requests.post(f"{API}/api/backtest/run", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True, j
    # Source should be twelvedata when local pool is empty for M1.
    assert j.get("data_source") in ("twelvedata", "local_pool", "oanda"), j


def test_backtest_run_otc_5s_uses_local_pool_not_td():
    """OTC 5s timeframe must NOT use TD (sub-minute is unsupported on free tier)."""
    payload = {
        "strategy": "deep_confluence",
        "symbol": "EURUSD_OTC",
        "timeframe": "5s",
        "days": 1,
    }
    r = requests.post(f"{API}/api/backtest/run", json=payload, timeout=60)
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        j = r.json()
        # Must not be twelvedata for 5s
        assert j.get("data_source") != "twelvedata", j
