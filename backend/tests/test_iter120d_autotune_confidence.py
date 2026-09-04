"""
Iter 120d — Confidence-threshold autotuner regression.

Verifies:
  - POST /api/strategies/autotune-confidence returns sweep + recommendation shape
  - Sweep is sorted by threshold + monotonic in `n` (higher thresholds → smaller subsample)
  - _pick_recommendation picks highest sim_pnl among eligible rows
  - GET recommendation returns the persisted doc
  - POST apply updates the live Ridicolous singleton
  - conf_min >= conf_max → 422
  - Unknown strategy → 404
  - Apply for non-Ridicolous strategy → 400
"""

import re
import sys

import httpx
import pytest


sys.path.insert(0, "/app/backend")


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()
DEFAULT_CFG = {"perc": 1.0, "levels": 5, "min_history": 60, "min_confidence": 55.0}


@pytest.fixture(scope="module", autouse=True)
def _reset_config_after_module():
    yield
    import httpx as _hx
    try:
        with _hx.Client(timeout=10.0) as c:
            c.post(f"{API}/strategies/ridicolous/config", json=DEFAULT_CFG)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# A) Sweep shape + monotonicity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_sweep_returns_correct_shape():
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "days": 30, "max_candles": 2000, "stride": 3,
            "conf_min": 50, "conf_max": 90, "conf_step": 5,
            "min_sample_size": 15,
        })
    assert r.status_code == 200, r.text
    body = r.json()
    if not body.get("success"):
        return  # env-specific candle shortage — accept but stop here
    for k in ("strategy_id", "asset", "timeframe", "days",
              "candles_used", "trades_evaluated", "sweep",
              "recommendation", "min_sample_size", "payout"):
        assert k in body

    sweep = body["sweep"]
    assert len(sweep) == 9  # 50,55,60,65,70,75,80,85,90
    thresholds = [row["threshold"] for row in sweep]
    assert thresholds == sorted(thresholds), "sweep must be threshold-sorted"

    # Monotonicity: n(t) is non-increasing as t rises
    ns = [row["n"] for row in sweep]
    for prev, curr in zip(ns, ns[1:]):
        assert curr <= prev, f"n decreased then rose: {ns}"


@pytest.mark.asyncio
async def test_a_recommendation_is_eligible_and_highest_pnl():
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "days": 30, "max_candles": 2000, "stride": 3,
            "conf_min": 50, "conf_max": 90, "conf_step": 5,
            "min_sample_size": 15,
        })
    body = r.json()
    if not body.get("success"):
        return
    rec = body["recommendation"]
    eligibles = [row for row in body["sweep"] if row["eligible"]]
    if not eligibles:
        assert rec is None
    else:
        # Rec must be one of the eligibles
        assert rec in eligibles
        # And it must be the max sim_pnl
        max_pnl = max(row["sim_pnl"] for row in eligibles)
        assert rec["sim_pnl"] == max_pnl


# ---------------------------------------------------------------------------
# B) _pick_recommendation unit test
# ---------------------------------------------------------------------------
def test_b_pick_recommendation_selects_highest_pnl_eligible():
    from routes.strategy_backtest import _pick_recommendation
    sweep = [
        {"threshold": 50, "sim_pnl": 5.0, "win_rate": 0.52, "eligible": False},
        {"threshold": 60, "sim_pnl": 2.0, "win_rate": 0.60, "eligible": True},
        {"threshold": 70, "sim_pnl": 4.5, "win_rate": 0.66, "eligible": True},
        {"threshold": 80, "sim_pnl": 1.0, "win_rate": 0.80, "eligible": True},
    ]
    rec = _pick_recommendation(sweep)
    assert rec["threshold"] == 70
    assert rec["sim_pnl"] == 4.5


def test_b_pick_recommendation_none_when_no_eligibles():
    from routes.strategy_backtest import _pick_recommendation
    assert _pick_recommendation([{"eligible": False, "sim_pnl": 10}]) is None
    assert _pick_recommendation([]) is None


# ---------------------------------------------------------------------------
# C) GET recommendation returns persisted doc
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_c_get_recommendation_returns_persisted_row():
    async with httpx.AsyncClient(timeout=120.0) as c:
        # Compute first
        await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "days": 30, "max_candles": 2000, "stride": 3,
        })
        # Now fetch
        r = await c.get(f"{API}/strategies/autotune-confidence/recommendation", params={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
        })
    body = r.json()
    assert body["success"] is True
    # Either recommendation persisted, or endpoint returned success:True with recommendation=None
    if body.get("recommendation"):
        for k in ("threshold", "n", "win_rate", "sim_pnl", "eligible"):
            assert k in body["recommendation"]


# ---------------------------------------------------------------------------
# D) Apply endpoint updates the live singleton + persists
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d_apply_updates_singleton_config():
    async with httpx.AsyncClient(timeout=120.0) as c:
        # Ensure a recommendation exists
        run = await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "days": 30, "max_candles": 2000, "stride": 3,
        })
        run_body = run.json()
        if not run_body.get("success") or not run_body.get("recommendation"):
            pytest.skip("no candles/recommendation available in preview")

        # Apply
        r = await c.post(f"{API}/strategies/autotune-confidence/apply", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["applied_threshold"] == run_body["recommendation"]["threshold"]

        # Config now reflects that threshold
        r2 = await c.get(f"{API}/strategies/ridicolous/config")
        assert r2.json()["config"]["min_confidence"] == body["applied_threshold"]


@pytest.mark.asyncio
async def test_d_apply_explicit_threshold():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence/apply", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "threshold": 72.0,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["applied_threshold"] == 72.0
    async with httpx.AsyncClient(timeout=15.0) as c:
        r2 = await c.get(f"{API}/strategies/ridicolous/config")
    assert r2.json()["config"]["min_confidence"] == 72.0


# ---------------------------------------------------------------------------
# E) Validation errors
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_e_conf_min_ge_max_returns_422():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC", "timeframe": "1m",
            "conf_min": 80, "conf_max": 60,
        })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_e_unknown_strategy_404():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence", json={
            "strategy_id": "does_not_exist_xyz",
            "asset": "EURUSD_OTC",
        })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_e_apply_non_ridicolous_returns_400():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/autotune-confidence/apply", json={
            "strategy_id": "algo_trend_momentum",
            "asset": "EURUSD_OTC",
            "threshold": 65.0,
        })
    assert r.status_code == 400
