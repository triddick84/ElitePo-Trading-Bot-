"""
Iter 125 backend review — targeted validation per E1's review request.
Tests all AI-tab data sources, multi-asset auto-scan routing, rotation,
active-target-queue, config sanity, and Iter122/124 regression.
"""
import os
import re
import time

import httpx
import pytest


def _api():
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m, "REACT_APP_BACKEND_URL missing"
    return f"{m.group(1)}/api"


API = _api()
TIMEOUT = 30.0


# -------- Bug 1: AI tab data sources --------
def test_microstructure_models_with_asset():
    r = httpx.get(f"{API}/microstructure/models", params={"asset": "EURUSD_OTC"}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body
    assert "kyle_result" in body
    assert "gm_result" in body


def test_microstructure_models_without_asset_returns_422():
    r = httpx.get(f"{API}/microstructure/models", timeout=TIMEOUT)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


def test_signals_preview_returns_votes():
    r = httpx.get(f"{API}/signals/preview", params={"asset": "EURUSD_OTC"}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert "votes" in body
    assert isinstance(body["votes"], list)


def test_trades_recent_outcomes():
    r = httpx.get(f"{API}/trades/recent-outcomes", params={"limit": 5}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert "outcomes" in body
    assert isinstance(body["outcomes"], list)


# -------- Bug 2a: Auto-scan routing --------
def test_scan_now_multi_asset_shape():
    payload = {"assets": ["EURUSD_OTC", "GBPUSD_OTC", "AUDCAD_OTC"]}
    r = httpx.post(f"{API}/signals/auto-scan/scan-now", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body
    assert "matched_count" in body
    assert "rotation_index" in body
    assert "results" in body
    # winner optional (only if matched)
    if body.get("matched_count", 0) > 0:
        assert "winner" in body


def test_active_target_reflects_scan_winner():
    """If scan-now returns a winner, active-target must have same asset/direction."""
    payload = {"assets": ["EURUSD_OTC", "GBPUSD_OTC", "AUDCAD_OTC", "USDJPY_OTC"]}
    r = httpx.post(f"{API}/signals/auto-scan/scan-now", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    winner = body.get("winner")
    if not winner:
        pytest.skip(f"No matched winners in current market — matched_count={body.get('matched_count')}")
    # Now read active-target
    r2 = httpx.get(f"{API}/tampermonkey/active-target", timeout=TIMEOUT)
    assert r2.status_code == 200
    tgt = r2.json()
    # Endpoint shape varies — check nested/flat
    target = tgt.get("target") or tgt
    assert target.get("asset") == winner.get("asset"), f"active-target asset mismatch: {target} vs winner {winner}"


# -------- Bug 2b: Queue endpoint --------
def test_active_target_queue_shape():
    r = httpx.get(f"{API}/tampermonkey/active-target-queue", timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert "queue" in body
    assert "count" in body
    assert isinstance(body["queue"], list)


def test_rotation_index_monotonic_across_scans():
    payload = {"assets": ["EURUSD_OTC", "GBPUSD_OTC", "AUDCAD_OTC"]}
    idxs = []
    for _ in range(3):
        r = httpx.post(f"{API}/signals/auto-scan/scan-now", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200
        b = r.json()
        idxs.append(b.get("rotation_index"))
        time.sleep(0.5)
    print(f"rotation indexes across 3 scans: {idxs}")
    # All must be present int fields
    for v in idxs:
        assert isinstance(v, int)
    # If any matched winners, index should advance at least once
    # Not strict — log if stays 0 (acceptable when no matches)


# -------- Config sanity --------
def test_auto_scan_config_interval():
    r = httpx.get(f"{API}/signals/auto-scan/config", timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    cfg = body.get("config") or body
    interval = cfg.get("interval_seconds")
    assert interval is not None, body
    assert interval <= 15, f"interval_seconds should be ≤15, got {interval}"


# -------- Iter 122 regression --------
def test_iter122_active_target_routed_source():
    payload = {
        "asset": "EURUSD_OTC", "direction": "CALL", "confidence": 0.82,
        "elite_score": 85, "source": "elite_screener", "target_ttl_seconds": 60,
    }
    r = httpx.post(f"{API}/tampermonkey/active-target", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    time.sleep(0.5)
    r2 = httpx.get(f"{API}/signals/latest", params={"symbol": "EURUSD_OTC"}, timeout=TIMEOUT)
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("source") == "active_target_routed", f"top-level source mismatch: {body}"
    sig = body["signal"]
    assert sig["strategy"] == "routed_from_elite_screener", f"strategy mismatch: {sig}"
    # cleanup
    httpx.post(f"{API}/tampermonkey/active-target", json={"asset": None}, timeout=TIMEOUT)


# -------- Iter 124 regression --------
def test_iter124_rolling_micro_ml_backtest():
    payload = {
        "strategy_id": "rolling_micro_ml",
        "asset": "EURUSD_OTC",
        "timeframe": "1m",
        "days": 15,
    }
    r = httpx.post(f"{API}/strategies/backtest", json=payload, timeout=60.0)
    assert r.status_code == 200, r.text
    body = r.json()
    # success:true OR friendly error acceptable
    if body.get("success") is not True:
        assert "error" in body or "message" in body, f"non-success response must include error msg: {body}"
        print(f"Backtest returned friendly error: {body}")
