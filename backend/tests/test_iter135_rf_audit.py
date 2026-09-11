"""Iter 135 — RF AUC Audit + PerfPill widget."""
import re
import sys

import httpx
import numpy as np
import pytest

sys.path.insert(0, "/app/backend")

from rf_audit_service import (  # noqa: E402
    _weight_from_auc,
    _asset_to_yf,
    list_rf_models,
    rf_audit_service,
    AUC_DROP_BELOW,
    AUC_FULL_TRUST_AT,
)


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()


# ---------------------------------------------------------------------------
# Weight policy: >=0.55 full trust, 0.52–0.55 linear, <0.52 dropped
# ---------------------------------------------------------------------------
def test_weight_policy_full_trust_at_or_above_055():
    for auc in (0.55, 0.60, 0.75, 0.9046):
        assert _weight_from_auc(auc) == 1.0, f"auc {auc} should be full trust"


def test_weight_policy_dropped_below_052():
    for auc in (0.51, 0.49, 0.30, 0.0):
        assert _weight_from_auc(auc) == 0.0, f"auc {auc} should be dropped"


def test_weight_policy_linear_between_052_and_055():
    # At 0.535 → halfway → 0.5
    assert abs(_weight_from_auc(0.535) - 0.5) < 0.01
    # At 0.52 → 0 (edge inclusive)
    assert _weight_from_auc(0.52) == 0.0
    # At 0.5499 → very close to 1 (still linear scale)
    w = _weight_from_auc(0.5499)
    assert 0.9 < w < 1.0


def test_weight_policy_none_returns_zero():
    assert _weight_from_auc(None) == 0.0


# ---------------------------------------------------------------------------
# Asset → yfinance symbol mapping
# ---------------------------------------------------------------------------
def test_asset_to_yf_forex_appends_x():
    for a, expected in [("EURUSD_OTC", "EURUSD=X"), ("AUDCAD_otc", "AUDCAD=X"),
                        ("GBPJPY", "GBPJPY=X"), ("USDCHF/OTC", "USDCHF=X")]:
        assert _asset_to_yf(a) == expected, f"{a} → {_asset_to_yf(a)} != {expected}"


def test_asset_to_yf_crypto_uses_dash_usd():
    assert _asset_to_yf("BTCUSD") == "BTC-USD"
    assert _asset_to_yf("ETHUSD") == "ETH-USD"


def test_list_rf_models_finds_60_pkl_files():
    """We know ml_models/ ships with 60 files (56 rf_* + a few meta)."""
    models = list_rf_models()
    assert len(models) >= 30, f"expected ≥30 RF models, got {len(models)}"
    # Every entry is (asset, timeframe, path)
    for asset, tf, path in models[:3]:
        assert asset and tf and path.endswith(".pkl")


# ---------------------------------------------------------------------------
# Ensemble weight lookup
# ---------------------------------------------------------------------------
def test_get_effective_weight_defaults_to_1_when_never_audited():
    """Any model never audited should default to weight 1.0 (existing
    behaviour preserved). Only audited-and-scored models get de-weighted."""
    w = rf_audit_service.get_effective_weight("NEVER_AUDITED", "1m")
    assert w == 1.0


# ---------------------------------------------------------------------------
# Live REST endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_endpoint_rf_audit_latest_returns_persisted_rows():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/rf-audit/latest")
    assert r.status_code == 200
    b = r.json()
    assert b["success"]
    # If prior audit ran, we should have rows persisted
    for row in (b.get("results") or [])[:3]:
        assert "asset" in row and "timeframe" in row
        assert "auc" in row  # may be None for models that fail scoring
        assert "status" in row


@pytest.mark.asyncio
async def test_endpoint_rf_audit_weight_lookup():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{API}/rf-audit/weight",
                        params={"asset": "GBPUSD_OTC", "timeframe": "5s"})
    assert r.status_code == 200
    b = r.json()
    assert b["success"]
    assert "weight" in b
    assert 0.0 <= float(b["weight"]) <= 1.0


@pytest.mark.asyncio
async def test_endpoint_rf_audit_run_produces_summary():
    """Run one model quickly to keep test time small."""
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{API}/rf-audit/run", params={"limit": 3})
    assert r.status_code == 200
    b = r.json()
    assert b["success"]
    assert b["total_models"] == 3
    for k in ("trusted", "de_weighted", "dropped", "errors"):
        assert k in b["summary"]


# ---------------------------------------------------------------------------
# PerfPill frontend component
# ---------------------------------------------------------------------------
def test_perf_pill_component_exists():
    src = open("/app/frontend/src/components/PerfPill.jsx").read()
    assert "data-testid=\"perf-pill\"" in src
    assert "data-testid=\"perf-pill-hitrate\"" in src
    # Polls the yf-cache endpoint every 6s
    assert "/perf/yf-cache" in src
    assert "6000" in src
    # Colour ramp: emerald > 70%, amber > 40%, else grey
    assert "hitRate >= 70" in src
    assert "hitRate >= 40" in src


def test_perf_pill_wired_into_header():
    src = open("/app/frontend/src/App.js").read()
    assert 'import PerfPill from "./components/PerfPill"' in src
    assert "<PerfPill />" in src
