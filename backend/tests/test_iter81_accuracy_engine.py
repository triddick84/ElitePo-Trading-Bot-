"""
Iter 81 (Jul 2026) — AccuracyEngine gating on /signals/latest.

Locks in:
- `accuracy_engine.should_gate()` cold-start behaviour (n_trades < min ⇒ pass).
- `accuracy_engine.should_gate()` fires when rolling win-rate is under threshold.
- `/api/accuracy-engine/status` + `/stats` + `/config` REST surface.
- `/api/signals/latest` decorates the response with `accuracy_engine`
  metadata AND marks the signal as `abstain=true, abstain_source=accuracy_engine`
  when the (asset, strategy) combo is gated.
- `/api/trades/report` invalidates the AccuracyEngine cache on new outcomes.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=15, **kwargs)


def _post(path: str, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=15, **kwargs)


@pytest.fixture
def db():
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv(Path(__file__).parent.parent / ".env")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
def test_status_returns_config_and_totals():
    r = _get("/api/accuracy-engine/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert "config" in body
    assert isinstance(body["config"].get("min_win_rate_pct"), (int, float))
    assert isinstance(body.get("total_keys"), int)
    assert isinstance(body.get("active_keys"), int)
    assert isinstance(body.get("gated_keys"), int)


def test_config_get_and_patch_roundtrip():
    orig = _get("/api/accuracy-engine/config").json()["config"]
    try:
        patched = _post(
            "/api/accuracy-engine/config", json={"min_win_rate_pct": 55.0}
        ).json()["config"]
        assert patched["min_win_rate_pct"] == 55.0
    finally:
        _post("/api/accuracy-engine/config", json={"min_win_rate_pct": orig["min_win_rate_pct"]})


def test_cold_start_never_gates():
    r = _get(
        "/api/accuracy-engine/should-gate",
        params={"asset": "___NEVER_TRADED", "strategy": "___NEVER_USED"},
    )
    assert r.status_code == 200
    d = r.json()["decision"]
    assert d["gated"] is False
    assert d["reason"] == "cold_start"
    assert d["action"] == "pass"


def test_stats_all_returns_entries():
    r = _get("/api/accuracy-engine/stats", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("entries"), list)


# ---------------------------------------------------------------------------
# /signals/latest gate wiring
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_signals_latest_gates_known_bad_combo(db):
    """
    Assumes historical `tm_trade_reports` contain enough losses on
    EURRUB_OTC + 1m_21s_reversal to trip the gate. Seed a fresh signal on
    that combo and expect `/signals/latest` to flag `abstain_source=accuracy_engine`.
    """
    # Precondition — engine sees the combo as gated
    dec = _get(
        "/api/accuracy-engine/should-gate",
        params={"asset": "EURRUB_OTC", "strategy": "1m_21s_reversal"},
    ).json()["decision"]
    if not dec["gated"]:
        pytest.skip("No historical loss data to trigger gating in this env")

    # Seed a fresh signal
    now = datetime.now(timezone.utc)
    sig_id = f"AE_TEST_{now.strftime('%Y%m%d%H%M%S%f')}"
    await db.trading_signals.insert_one({
        "id": sig_id,
        "symbol": "EURRUB_OTC",
        "asset": "EURRUB_OTC",
        "direction": "CALL",
        "confidence": 88,
        "probability": 88,
        "strategy": "1m_21s_reversal",
        "timestamp": now.isoformat(),
        "source": "iter81_regression",
    })
    try:
        r = _get("/api/signals/latest", params={
            "symbol": "EURRUB_OTC", "use_enhanced": "false",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        sig = body["signal"]
        assert sig["id"] == sig_id, f"got a different signal back: {sig.get('id')}"
        ae = sig.get("accuracy_engine")
        assert ae is not None
        assert ae["gated"] is True
        assert sig.get("abstain") is True
        assert sig.get("abstain_source") == "accuracy_engine"
    finally:
        await db.trading_signals.delete_one({"id": sig_id})


@pytest.mark.asyncio
async def test_signals_latest_passes_cold_start_combo(db):
    """A never-before-seen (asset, strategy) should NOT be gated."""
    now = datetime.now(timezone.utc)
    sig_id = f"AE_COLD_{now.strftime('%Y%m%d%H%M%S%f')}"
    await db.trading_signals.insert_one({
        "id": sig_id,
        "symbol": "XYZFAKE_OTC",
        "asset": "XYZFAKE_OTC",
        "direction": "PUT",
        "confidence": 80,
        "probability": 80,
        "strategy": "coldstart_strategy_xyz",
        "timestamp": now.isoformat(),
        "source": "iter81_regression",
    })
    try:
        r = _get("/api/signals/latest", params={
            "symbol": "XYZFAKE_OTC", "use_enhanced": "false",
        })
        body = r.json()
        assert body.get("success") is True
        sig = body["signal"]
        assert sig["id"] == sig_id
        ae = sig.get("accuracy_engine")
        assert ae is not None
        assert ae["gated"] is False
        assert sig.get("abstain_source") != "accuracy_engine"
    finally:
        await db.trading_signals.delete_one({"id": sig_id})


# ---------------------------------------------------------------------------
# /trades/report invalidates the cache
# ---------------------------------------------------------------------------
def test_trade_report_with_outcome_invalidates_cache():
    # Force a refresh so we have a baseline last_refresh timestamp
    _post("/api/accuracy-engine/refresh")
    before = _get("/api/accuracy-engine/status").json()["last_refresh"]

    # Report a trade with an outcome — should invalidate the cache
    r = _post("/api/trades/report", json={
        "asset": "EURUSD_OTC",
        "direction": "CALL",
        "strategy": "regression_probe",
        "outcome": "WIN",
        "confidence": 80,
    })
    assert r.status_code == 200
    assert r.json().get("success") is True

    # Sleep briefly to sidestep timing jitter, then next status hit should
    # trigger a rebuild → last_refresh advances.
    time.sleep(0.2)
    after = _get("/api/accuracy-engine/status").json()["last_refresh"]
    assert after > before, f"cache was not invalidated: before={before} after={after}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
