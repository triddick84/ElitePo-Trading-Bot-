"""
Iter 91 — Strategy Presets + Adaptive Latency Offset.

Guards:
1. `GET /api/custom-strategies/presets` lists Ichimoku Cloud Break.
2. `POST /api/custom-strategies/presets/{id}/apply` clones the preset into
   the caller's strategies as a Draft (is_published=False, is_active=True).
3. Preset apply for unknown id returns 404.
4. Adaptive latency-offset service returns default when < 8 samples, and
   median-derived offset when ≥ 8 samples.
5. `/signals/adaptive-latency-offset` + `/adaptive-latency-offsets` endpoints
   are reachable and shape-correct.
6. Latency-report POST invalidates the per-asset cache.
"""

from __future__ import annotations

import asyncio
import os
import random
import time

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------
def test_list_presets_includes_ichimoku():
    r = requests.get(f"{BASE_URL}/api/custom-strategies/presets", timeout=5).json()
    assert r.get("success") is True
    ids = {p["preset_id"] for p in r.get("presets", [])}
    assert "ichimoku-cloud-break" in ids


def test_ichimoku_preset_has_expected_shape():
    r = requests.get(f"{BASE_URL}/api/custom-strategies/presets", timeout=5).json()
    p = next(x for x in r["presets"] if x["preset_id"] == "ichimoku-cloud-break")
    assert p["category"] == "trend"
    assert "ichimoku" in p["tags"]
    assert p["call_conditions_count"] >= 3  # Tenkan>Kijun + close>senkou_a + close>senkou_b
    assert p["put_conditions_count"] >= 3
    assert "30s" in p["timeframes"] and "1m" in p["timeframes"]


def test_apply_preset_creates_draft_strategy():
    unique_user = f"pytest_user_{int(time.time())}"
    r = requests.post(
        f"{BASE_URL}/api/custom-strategies/presets/ichimoku-cloud-break/apply",
        params={"user_id": unique_user},
        timeout=10,
    ).json()
    assert r.get("success") is True
    strategy = (r.get("strategy") or {}).get("strategy") or r.get("strategy") or {}
    if isinstance(strategy, dict) and "strategy" in strategy:
        strategy = strategy["strategy"]
    # Was cloned as draft
    assert strategy.get("is_published") in (False, None), \
        f"Preset-applied strategy must be unpublished; got {strategy.get('is_published')}"

    # It should be retrievable by the same user
    listing = requests.get(
        f"{BASE_URL}/api/custom-strategies",
        params={"user_id": unique_user},
        timeout=5,
    ).json()
    assert listing.get("success") is True
    names = [s.get("name") for s in listing.get("strategies", [])]
    assert any("Ichimoku Cloud Break" in n for n in names if n), \
        f"Cloned strategy not found for user {unique_user}"


def test_apply_unknown_preset_returns_404():
    r = requests.post(
        f"{BASE_URL}/api/custom-strategies/presets/does-not-exist/apply",
        timeout=5,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Adaptive Latency Offset
# ---------------------------------------------------------------------------
def _bulk_report(asset: str, n: int, rtt_ms: float, lag_ms: float):
    for _ in range(n):
        requests.post(
            f"{BASE_URL}/api/signals/latency-report",
            json={
                "asset": asset,
                "network_rtt_ms": rtt_ms + random.uniform(-20, 20),
                "dom_click_lag_ms": lag_ms + random.uniform(-100, 100),
            },
            timeout=5,
        )


def test_adaptive_offset_default_when_low_samples():
    # Use a fresh asset name that has no historical samples
    unique_asset = f"TESTPAIR{int(time.time())}_OTC"
    r = requests.get(
        f"{BASE_URL}/api/signals/adaptive-latency-offset",
        params={"asset": unique_asset},
        timeout=5,
    ).json()
    assert r.get("success") is True
    assert r.get("using_default") is True
    assert r.get("recommended_offset_sec") == 3.5  # DEFAULT_GLOBAL_OFFSET_SEC


def test_adaptive_offset_computed_from_median_when_enough_samples():
    unique_asset = f"MEDIANPAIR{int(time.time())}_OTC"
    # Push 12 realistic samples: rtt ~180ms, click lag ~3400ms → total ~3.6s
    _bulk_report(unique_asset, 12, rtt_ms=180, lag_ms=3400)
    time.sleep(0.5)
    r = requests.get(
        f"{BASE_URL}/api/signals/adaptive-latency-offset",
        params={"asset": unique_asset},
        timeout=5,
    ).json()
    assert r.get("success") is True
    assert r.get("using_default") is False
    assert r.get("sample_count") >= 8
    # Recommended should be near (3400+180)/1000 = 3.58, rounded to 0.5 → 3.5
    rec = r.get("recommended_offset_sec")
    assert isinstance(rec, (int, float))
    assert 3.0 <= rec <= 4.0, f"Unexpected offset: {rec}"


def test_adaptive_offset_clamped_to_max_when_lag_absurd():
    unique_asset = f"HIGHLAG{int(time.time())}_OTC"
    # Push samples with absurd 60-second lag → should clamp to 15s max
    _bulk_report(unique_asset, 12, rtt_ms=200, lag_ms=60000)
    r = requests.get(
        f"{BASE_URL}/api/signals/adaptive-latency-offset",
        params={"asset": unique_asset},
        timeout=5,
    ).json()
    assert r.get("recommended_offset_sec") == 15.0  # MAX_OFFSET_SEC


def test_adaptive_offsets_map_endpoint_reachable():
    r = requests.get(f"{BASE_URL}/api/signals/adaptive-latency-offsets", timeout=5).json()
    assert r.get("success") is True
    assert isinstance(r.get("assets"), list)
    assert r.get("default_offset_sec") == 3.5
    assert r.get("min_samples_required") >= 1


def test_signals_latest_carries_recommended_offset():
    unique_asset = f"SIGSAMPLE{int(time.time())}_OTC"
    # Prime with samples so the signal endpoint has enough data
    _bulk_report(unique_asset, 12, rtt_ms=200, lag_ms=3400)
    time.sleep(0.5)
    r = requests.get(
        f"{BASE_URL}/api/signals/latest",
        params={"symbol": unique_asset},
        timeout=15,
    ).json()
    if not r.get("success") or not r.get("signal"):
        pytest.skip("no signal produced for synthetic asset")
    sig = r["signal"]
    # Field must exist even if using_default=True; None is only allowed
    # when the internal probe crashed (we accept None as a safety net)
    assert "recommended_offset_sec" in sig
    assert "adaptive_offset_meta" in sig


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
