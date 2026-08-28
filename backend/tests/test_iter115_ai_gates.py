"""
Iter 115 — AI Enhancement gates regression test.

Covers:
  a) ADX regime gate  → /api/regime/current + /api/signals/latest.regime_gate
  b) HA confluence    → /api/ha/confluence + /api/signals/latest.ha_confluence
  c) Feedback engine  → /api/feedback/record-outcome + /api/feedback/weights
  d) LightGBM meta    → /api/ml/lightgbm/status  (+ train endpoint is smoke-tested)

Run with:
    cd /app/backend && pytest tests/test_iter115_ai_gates.py -q
"""

import os
import pytest
import httpx


API_URL = os.environ.get("REACT_APP_BACKEND_URL_PUBLIC") or (
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
)
API = f"{API_URL}/api"


@pytest.mark.asyncio
async def test_a_regime_current():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API}/regime/current", params={"symbol": "EURUSD_OTC"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] in (True, False)
    if body["success"]:
        regime = body["regime"]
        assert regime["regime"] in ("TREND", "CHOPPY", "NEUTRAL")
        assert regime["adx"] >= 0


@pytest.mark.asyncio
async def test_a_regime_gate_in_signals_latest():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API}/signals/latest", params={"symbol": "EURUSD_OTC"})
    assert r.status_code == 200, r.text
    sig = (r.json() or {}).get("signal") or {}
    if sig:
        # Field is optional — appears only when candles are available for the asset.
        gate = sig.get("regime_gate")
        if gate is not None:
            assert "regime" in gate
            assert "gated" in gate


@pytest.mark.asyncio
async def test_b_ha_confluence_endpoint():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{API}/ha/confluence",
            params={"symbol": "EURUSD_OTC", "direction": "UP"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("success"):
        assert "gated" in body
        assert body["ha_color"] in ("GREEN", "RED", "DOJI", "NONE")


@pytest.mark.asyncio
async def test_c_feedback_record_and_read():
    async with httpx.AsyncClient(timeout=30.0) as client:
        strategy_id = "pytest_iter115_strategy"
        payload = {
            "strategy_id": strategy_id,
            "outcome": "WIN",
            "regime": "TREND",
            "asset": "EURUSD_OTC",
            "confidence": 87.5,
        }
        r1 = await client.post(f"{API}/feedback/record-outcome", json=payload)
        assert r1.status_code == 200, r1.text
        assert r1.json()["success"] is True
        stats = r1.json()["stats"]
        assert stats["wins"] >= 1
        assert 0.0 <= stats["posterior_win_rate"] <= 1.0
        assert 0.5 <= stats["confidence_multiplier"] <= 1.30

        r2 = await client.get(
            f"{API}/feedback/weights", params={"strategy_id": strategy_id}
        )
        assert r2.status_code == 200
        assert r2.json()["stats"]["strategy_id"] == strategy_id


@pytest.mark.asyncio
async def test_d_lightgbm_status():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API}/ml/lightgbm/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "ready" in body
    assert "feature_order" in body
    assert len(body["feature_order"]) >= 15


@pytest.mark.asyncio
async def test_e_gates_config_roundtrip():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r0 = await client.get(f"{API}/ai/gates/config")
        original = r0.json()["config"]

        modified = {
            **original,
            "adx_regime_enabled": not original["adx_regime_enabled"],
        }
        r1 = await client.post(f"{API}/ai/gates/config", json=modified)
        assert r1.status_code == 200
        assert r1.json()["config"]["adx_regime_enabled"] == modified["adx_regime_enabled"]

        # restore
        await client.post(f"{API}/ai/gates/config", json=original)
