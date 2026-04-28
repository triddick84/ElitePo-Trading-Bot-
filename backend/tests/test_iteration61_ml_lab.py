"""
Iteration 61 backend regression tests covering:
- /api/ml/tuning-report (model_status, otc_data.by_symbol[].trainable)
- /api/ml/scheduler/status (running:true)
- /api/signals/otc-candle-stats summary fields (po_live_candles, oanda_backfill_candles, overlay_ratio)
- /api/backtest/history results[]
- /api/backtest/assets forex/crypto/stocks
- POST /api/ml/train-from-otc returns total_samples (cv_accuracy may be None when below min_samples)
- TM bundle /pocket-option-auto-trader-modular.user.js contains v8.40.0 + Fiber click bypass markers
"""
import os
import re
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://momentum-trade-test.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# === ML tuning report ===
def test_ml_tuning_report_has_both_models(session):
    r = session.get(f"{BASE_URL}/api/ml/tuning-report", timeout=90)
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    ms = data.get("model_status", {})
    assert isinstance(ms, dict)
    assert "improved_v2" in ms
    assert "maximized_v3" in ms


def test_ml_tuning_report_otc_data_by_symbol_has_trainable(session):
    r = session.get(f"{BASE_URL}/api/ml/tuning-report", timeout=90)
    assert r.status_code == 200
    by_symbol = r.json().get("otc_data", {}).get("by_symbol", [])
    assert isinstance(by_symbol, list) and len(by_symbol) > 0
    sample = by_symbol[0]
    assert "symbol" in sample
    assert "candles" in sample
    assert "trainable" in sample
    assert isinstance(sample["trainable"], bool)


# === Scheduler ===
def test_scheduler_status_running(session):
    r = session.get(f"{BASE_URL}/api/ml/scheduler/status", timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert data.get("running") is True


# === OTC candle stats overlay summary ===
def test_otc_candle_stats_overlay_fields(session):
    r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=60)
    assert r.status_code == 200
    summary = r.json().get("summary", {})
    for key in ("po_live_candles", "oanda_backfill_candles", "overlay_ratio"):
        assert key in summary, f"missing {key} in summary"
    assert isinstance(summary["po_live_candles"], (int, float))
    assert isinstance(summary["oanda_backfill_candles"], (int, float))
    assert isinstance(summary["overlay_ratio"], (int, float))


# === Backtest endpoints ===
def test_backtest_history(session):
    r = session.get(f"{BASE_URL}/api/backtest/history", timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_backtest_assets_groups(session):
    r = session.get(f"{BASE_URL}/api/backtest/assets", timeout=60)
    assert r.status_code == 200
    assets = r.json().get("assets", {})
    for grp in ("forex", "crypto", "stocks"):
        assert grp in assets, f"missing group {grp}"
        assert isinstance(assets[grp], list)
        assert len(assets[grp]) > 0


# === ML train-from-otc smoke ===
def test_train_from_otc_returns_total_samples_improved(session):
    payload = {"model": "improved", "symbols": ["EURUSD_OTC"], "min_samples": 200}
    r = session.post(f"{BASE_URL}/api/ml/train-from-otc", json=payload, timeout=180)
    assert r.status_code == 200
    data = r.json()
    # cv_accuracy may be None when below min_samples; total_samples must be present
    assert "total_samples" in data
    assert isinstance(data["total_samples"], int)
    assert "cv_accuracy" in data  # key always present


# === TM bundle ===
def test_tm_bundle_has_version_and_fiber_markers(session):
    r = session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=60)
    assert r.status_code == 200
    body = r.text
    assert "@version" in body and "8.40.0" in body
    # Fiber click bypass markers (literal $ characters - minifier preserves these as React property names)
    assert "__reactProps$" in body
    assert "__reactFiber$" in body
    assert "memoizedProps" in body


def test_tm_bundle_alias_resolves(session):
    """The single-file alias /pocket-option-auto-trader.user.js should serve the same v8.40.0 bundle."""
    r = session.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=60)
    assert r.status_code == 200
    assert "8.40.0" in r.text
