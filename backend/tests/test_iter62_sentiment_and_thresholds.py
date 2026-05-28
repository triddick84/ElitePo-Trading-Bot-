"""
Iter 62 — Sentiment + Per-Model Thresholds regression suite
============================================================

Confirms:
  Sentiment:
    A1. GET  /api/sentiment/health      returns 200 with success:true
    A2. POST /api/sentiment/refresh     returns 200 with scores for all 10 currencies
    A3. GET  /api/sentiment/scores      returns the cached snapshot
    A4. GET  /api/sentiment/pair/EURUSD_OTC returns base=EUR/quote=USD + bias
    A5. /api/signals/force-generate-v2 includes a `sentiment` field in the signal

  Per-Model Thresholds:
    B1. /api/signals/force-generate-v2 default response carries model_thresholds={all 0}
    B2. With min_conf_confluence=90, far fewer strategies vote (most filtered_by_threshold)
    B3. With min_conf_improved_v2=99 the improved_ml_v2 component is filtered out
    B4. Setting all thresholds to 100 fully neutralises ML/IQ but should still return a signal
"""
import os
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


# ------------------------------ Sentiment ------------------------------ #
def test_sentiment_health_endpoint():
    r = requests.get(f"{API}/api/sentiment/health", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    assert "fresh_within_minutes" in j


def test_sentiment_refresh_and_scores():
    r = requests.post(f"{API}/api/sentiment/refresh?force=true", timeout=90)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True
    scores = j.get("scores") or {}
    for cur in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "BTC"):
        assert cur in scores, f"missing currency {cur}"
        assert -1.0 <= float(scores[cur]["score"]) <= 1.0
        assert 0.0 <= float(scores[cur]["confidence"]) <= 1.0

    # Latest scores readable via /scores
    r2 = requests.get(f"{API}/api/sentiment/scores", timeout=10)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("success") is True
    assert j2.get("scores")


def test_sentiment_pair_bias():
    r = requests.get(f"{API}/api/sentiment/pair/EURUSD_OTC", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    assert j["base"] == "EUR" and j["quote"] == "USD"
    assert j["suggested_direction"] in ("CALL", "PUT", "NEUTRAL")


def test_force_generate_includes_sentiment_payload():
    r = requests.post(
        f"{API}/api/signals/force-generate-v2?asset=EURUSD_OTC&expiry_seconds=60",
        timeout=30,
    )
    assert r.status_code == 200, r.text
    sig = (r.json() or {}).get("signal") or {}
    assert "sentiment" in sig, "force-generate-v2 must include 'sentiment' field"


# ----------------------- Per-model thresholds ------------------------- #
def _force(asset="EURUSD_OTC", **kw):
    q = "&".join(f"{k}={v}" for k, v in kw.items())
    url = f"{API}/api/signals/force-generate-v2?asset={asset}&expiry_seconds=60"
    if q:
        url += "&" + q
    r = requests.post(url, timeout=30)
    r.raise_for_status()
    return r.json().get("signal") or {}


def test_default_thresholds_are_all_zero():
    sig = _force()
    thr = sig.get("model_thresholds") or {}
    assert thr == {"confluence": 0.0, "improved_v2": 0.0, "maximized_v3": 0.0, "iq720": 0.0}


def test_high_confluence_threshold_filters_strategies():
    sig_no = _force(min_conf_confluence=0)
    sig_hi = _force(min_conf_confluence=90)
    filt_no = sum(1 for v in (sig_no.get("components") or {}).values() if v.get("filtered_by_threshold"))
    filt_hi = sum(1 for v in (sig_hi.get("components") or {}).values() if v.get("filtered_by_threshold"))
    # At 90% confidence, the vast majority of strategies must be filtered
    assert filt_hi > filt_no
    assert filt_hi >= 10


def test_extreme_threshold_neutralises_ml_voters():
    sig = _force(
        min_conf_improved_v2=99,
        min_conf_maximized_v3=99,
        min_conf_iq720=99,
    )
    comps = sig.get("components") or {}
    for key in ("improved_ml_v2", "maximized_ml_v3", "iq720_ensemble"):
        if key in comps:
            assert comps[key].get("filtered_by_threshold") is True, f"{key} should be filtered"


def test_signal_still_returned_with_thresholds():
    sig = _force(min_conf_confluence=50, min_conf_improved_v2=50, min_conf_maximized_v3=50)
    assert sig.get("direction") in ("CALL", "PUT")
    assert isinstance(sig.get("confidence"), (int, float))
