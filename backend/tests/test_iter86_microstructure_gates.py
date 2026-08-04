"""
Iter 86 (Jul 2026) — Microstructure + Latency + Pair-Confluence gates.

Locks in the four new gates layered on top of `/api/signals/latest`:

  AccuracyEngine (Iter 81) → Microstructure (VPIN + Kyle-λ) → Latency
    → Pair-Confluence (confidence tilt) → λ multiplier

Only reaches the TM script if all abstain-gates pass. Confidence is tilted by
pair-confluence + Kyle-λ regime.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=30, **kwargs)


def _post(path: str, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=30, **kwargs)


# ---------------------------------------------------------------------------
# 1) Microstructure REST surface
# ---------------------------------------------------------------------------
def test_microstructure_status_shape():
    r = _get("/api/microstructure/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "total_keys" in body and isinstance(body["total_keys"], int)
    assert "toxic_keys" in body and isinstance(body["toxic_keys"], int)
    assert "config" in body


def test_microstructure_config_roundtrip():
    orig = _get("/api/microstructure/config").json()["config"]
    try:
        patched = _post("/api/microstructure/config",
                        json={"vpin_gate_threshold": 0.65}).json()["config"]
        assert patched["vpin_gate_threshold"] == 0.65
    finally:
        _post("/api/microstructure/config",
              json={"vpin_gate_threshold": orig["vpin_gate_threshold"]})


def test_microstructure_stats_list():
    r = _get("/api/microstructure/stats?limit=10").json()
    assert r["success"] is True
    assert isinstance(r["entries"], list)


def test_microstructure_cold_start_never_gates():
    r = _get("/api/microstructure/should-gate?asset=___NEVER_TRADED").json()
    d = r["decision"]
    assert d["gated"] is False
    assert d["reason"] in ("cold_start", "engine_disabled")


# ---------------------------------------------------------------------------
# 2) Pure numeric primitives
# ---------------------------------------------------------------------------
def test_compute_vpin_all_wins_is_max():
    from microstructure import compute_vpin
    # 400 identical outcomes = perfectly one-sided flow
    vpin = compute_vpin(["WIN"] * 400, bucket_size=20, num_buckets=20)
    assert vpin >= 0.99


def test_compute_vpin_balanced_is_low():
    from microstructure import compute_vpin
    seq = ["WIN", "LOSS"] * 200
    vpin = compute_vpin(seq, bucket_size=20, num_buckets=20)
    assert vpin < 0.15


def test_compute_kyle_lambda_positive_covariance():
    from microstructure import compute_kyle_lambda
    # Signed flow perfectly explains price move → non-zero λ
    flow = [1, 1, -1, 1, -1, -1, 1, -1, 1, 1] * 3
    moves = [0.001, 0.002, -0.001, 0.001, -0.002, -0.001,
             0.003, -0.002, 0.001, 0.002] * 3
    lam = compute_kyle_lambda(flow, moves)
    assert lam > 0.0


def test_compute_flow_imbalance_direction():
    from microstructure import compute_flow_imbalance
    up = [{"open": 1.0, "close": 1.001, "high": 1.002, "low": 0.999, "volume": 100}] * 10
    imb, streak = compute_flow_imbalance(up, lookback=10)
    assert imb > 0.9
    assert streak == 10

    down = [{"open": 1.001, "close": 1.0, "high": 1.002, "low": 0.999, "volume": 100}] * 10
    imb, streak = compute_flow_imbalance(down, lookback=10)
    assert imb < -0.9
    assert streak == 10


# ---------------------------------------------------------------------------
# 3) Latency middleware
# ---------------------------------------------------------------------------
def test_latency_stats_populated_after_probes():
    # Probe /api/health a few times so the histogram has samples
    for _ in range(5):
        _get("/api/health")
    r = _get("/api/latency/stats").json()
    assert r["success"] is True
    assert r["count"] > 0
    # /api/health should be present
    health_row = next((row for row in r["routes"]
                       if "/api/health" in row["route"]), None)
    assert health_row is not None
    assert health_row["count"] >= 1


def test_latency_healthy_threshold():
    r = _get("/api/latency/healthy?p99_threshold_ms=5000").json()
    assert r["success"] is True
    assert r["ok"] is True  # our server can't have p99 > 5s on local


def test_latency_response_header_present():
    r = _get("/api/health")
    assert "x-server-time-ms" in {k.lower() for k in r.headers.keys()}


# ---------------------------------------------------------------------------
# 4) Pair confluence
# ---------------------------------------------------------------------------
def test_pair_confluence_all_agree_boosts():
    from pair_confluence import confluence_score
    # Rising sequence for self and partner
    self_c = [{"open": 1.10 + i*0.001, "close": 1.101 + i*0.001,
               "high": 1.102 + i*0.001, "low": 1.099 + i*0.001, "volume": 100}
              for i in range(8)]
    partner_up = [{"open": 1.10 + i*0.001, "close": 1.102 + i*0.001,
                   "high": 1.103 + i*0.001, "low": 1.099 + i*0.001, "volume": 100}
                  for i in range(8)]

    def fetch(_partner):
        return partner_up

    out = confluence_score("EURUSD", "CALL", self_c, fetch)
    assert out["multiplier"] >= 1.05
    assert out["agreement_count"] >= 1


def test_pair_confluence_all_disagree_dampens():
    from pair_confluence import confluence_score
    self_c = [{"open": 1.10 - i*0.001, "close": 1.099 - i*0.001,
               "high": 1.101 - i*0.001, "low": 1.098 - i*0.001, "volume": 100}
              for i in range(8)]
    partner_up = [{"open": 1.10 + i*0.001, "close": 1.102 + i*0.001,
                   "high": 1.103 + i*0.001, "low": 1.099 + i*0.001, "volume": 100}
                  for i in range(8)]

    def fetch(_partner):
        return partner_up

    out = confluence_score("EURUSD", "PUT", self_c, fetch)
    assert out["multiplier"] <= 0.90


def test_pair_confluence_no_partners_is_neutral():
    from pair_confluence import confluence_score
    out = confluence_score("XYZ_UNKNOWN", "CALL", [], None)
    assert out["multiplier"] == 1.0


# ---------------------------------------------------------------------------
# 5) End-to-end wiring on /signals/latest
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent / ".env")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.mark.asyncio
async def test_signals_latest_has_microstructure_and_latency_fields(db):
    now = datetime.now(timezone.utc)
    sig_id = f"ITER86_TEST_{now.strftime('%Y%m%d%H%M%S%f')}"
    await db.trading_signals.insert_one({
        "id": sig_id,
        "symbol": "EURUSD_OTC", "asset": "EURUSD_OTC",
        "direction": "CALL", "confidence": 82, "probability": 82,
        "strategy": "5s_mixed_signals",
        "timeframe": "5s",
        "timestamp": now.isoformat(),
        "source": "iter86_regression",
    })
    try:
        r = _get("/api/signals/latest",
                 params={"symbol": "EURUSD_OTC",
                         "timeframe": "5s", "use_enhanced": "false"}).json()
        assert r.get("success") is True
        sig = r["signal"]
        assert sig["id"] == sig_id
        # New Iter 86 fields must all be present
        assert sig.get("microstructure") is not None
        assert sig.get("microstructure_multiplier") is not None
        assert sig.get("pair_confluence") is not None
        assert sig.get("latency_ok") is True
        # Multipliers must be in valid range
        mm = float(sig["microstructure_multiplier"])
        assert 0.7 <= mm <= 1.15
        pc = float(sig["pair_confluence"]["multiplier"])
        assert 0.85 <= pc <= 1.15
    finally:
        await db.trading_signals.delete_one({"id": sig_id})


@pytest.mark.asyncio
async def test_signals_latest_abstains_on_toxic_flow(db):
    """
    Seed a signal for a known-toxic asset (from historical trade data VPIN>0.72)
    and expect microstructure to abstain it.
    """
    # First check that USDEGP_OTC is currently toxic — otherwise skip
    stat = _get("/api/microstructure/should-gate?asset=USDEGP_OTC").json()
    dec = stat.get("decision", {})
    if not dec.get("gated"):
        pytest.skip("No toxic asset available in this env to test with")

    now = datetime.now(timezone.utc)
    sig_id = f"ITER86_TOXIC_{now.strftime('%Y%m%d%H%M%S%f')}"
    await db.trading_signals.insert_one({
        "id": sig_id,
        "symbol": "USDEGP_OTC", "asset": "USDEGP_OTC",
        "direction": "CALL", "confidence": 90, "probability": 90,
        "strategy": "coldstart_never_used_strategy_xyz",
        "timeframe": "5s",
        "timestamp": now.isoformat(),
        "source": "iter86_regression",
    })
    try:
        r = _get("/api/signals/latest",
                 params={"symbol": "USDEGP_OTC",
                         "timeframe": "5s", "use_enhanced": "false"}).json()
        sig = r["signal"]
        assert sig.get("abstain") is True
        assert sig.get("abstain_source") == "microstructure_toxic_flow"
        assert "VPIN" in sig.get("abstain_reason", "")
    finally:
        await db.trading_signals.delete_one({"id": sig_id})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
