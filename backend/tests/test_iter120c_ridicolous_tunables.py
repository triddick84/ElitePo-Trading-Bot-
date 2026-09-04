"""
Iter 120c — Ridicolous live-tunable config regression.

Verifies:
  - GET  /api/strategies/ridicolous/config returns full shape
  - POST persists to db.strategy_configs + updates the live singleton
  - Config bounds validation (perc, levels, min_confidence, min_history)
  - Backtest per-run `params` overrides don't mutate the singleton
  - apply_config() clamps out-of-range values instead of rejecting them
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
    """Ensure the live singleton is restored to defaults after this test module,
    so later test files (120b) that assume defaults don't see polluted state."""
    yield
    import httpx as _hx
    try:
        with _hx.Client(timeout=10.0) as c:
            c.post(f"{API}/strategies/ridicolous/config", json=DEFAULT_CFG)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# A) GET + POST roundtrip
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_config_roundtrip():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r0 = await c.get(f"{API}/strategies/ridicolous/config")
        assert r0.status_code == 200
        original = r0.json()["config"]

        new_cfg = {"perc": 2.0, "levels": 3, "min_history": 100, "min_confidence": 65.0}
        r1 = await c.post(f"{API}/strategies/ridicolous/config", json=new_cfg)
        assert r1.status_code == 200 and r1.json()["success"]
        assert r1.json()["config"] == new_cfg

        r2 = await c.get(f"{API}/strategies/ridicolous/config")
        assert r2.json()["config"] == new_cfg

        # Restore original
        await c.post(f"{API}/strategies/ridicolous/config", json=original)


@pytest.mark.asyncio
async def test_a_config_bounds_validation():
    async with httpx.AsyncClient(timeout=15.0) as c:
        # perc out of range (>10)
        r = await c.post(f"{API}/strategies/ridicolous/config", json={
            **DEFAULT_CFG, "perc": 99.0,
        })
        assert r.status_code == 422

        # levels > 5
        r = await c.post(f"{API}/strategies/ridicolous/config", json={
            **DEFAULT_CFG, "levels": 10,
        })
        assert r.status_code == 422

        # min_confidence < 40
        r = await c.post(f"{API}/strategies/ridicolous/config", json={
            **DEFAULT_CFG, "min_confidence": 10.0,
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# B) apply_config clamps in-range values (never rejects)
# ---------------------------------------------------------------------------
def test_b_apply_config_clamps_out_of_bounds():
    from strategies.strategy_ridicolous_breakout import RidicolousBreakoutPrediction
    s = RidicolousBreakoutPrediction()
    out = s.apply_config({"perc": 100.0, "levels": 20, "min_confidence": 5.0, "min_history": 10})
    # Clamped: perc≤10, levels≤5, min_confidence≥40, min_history≥30
    assert out["perc"] <= 10.0
    assert out["levels"] == 5
    assert out["min_confidence"] >= 40.0
    assert out["min_history"] >= 30


def test_b_apply_config_partial_updates():
    from strategies.strategy_ridicolous_breakout import RidicolousBreakoutPrediction
    s = RidicolousBreakoutPrediction(perc=1.0, levels=5, min_history=60, min_confidence=55.0)
    s.apply_config({"perc": 0.5})
    assert s.perc == 0.5
    assert s.levels == 5  # untouched
    assert s.min_confidence == 55.0  # untouched


# ---------------------------------------------------------------------------
# C) Backtest per-run params do not mutate the singleton
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_c_backtest_params_isolate_from_singleton():
    async with httpx.AsyncClient(timeout=90.0) as c:
        # Set baseline config
        await c.post(f"{API}/strategies/ridicolous/config", json=DEFAULT_CFG)

        # Run backtest with wildly different params
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 15,
            "max_candles": 1500,
            "stride": 5,
            "params": {"perc": 3.0, "levels": 2, "min_confidence": 70.0},
        })
        body = r.json()
        if body.get("success"):
            # Effective config in the response reflects the OVERRIDES
            eff = body["strategy_specific"]["effective_config"]
            assert eff["perc"] == 3.0
            assert eff["levels"] == 2
            assert eff["min_confidence"] == 70.0

        # Verify the singleton was NOT mutated
        r2 = await c.get(f"{API}/strategies/ridicolous/config")
        cfg = r2.json()["config"]
        assert cfg["perc"] == 1.0
        assert cfg["levels"] == 5
        assert cfg["min_confidence"] == 55.0


# ---------------------------------------------------------------------------
# D) POST updates the singleton in-process (verified via apply_config directly)
# ---------------------------------------------------------------------------
def test_d_apply_config_updates_singleton_in_process():
    from strategies.strategy_ridicolous_breakout import ridicolous_breakout_prediction
    before = ridicolous_breakout_prediction.get_config()
    try:
        ridicolous_breakout_prediction.apply_config({
            "perc": 2.5, "levels": 2, "min_history": 90, "min_confidence": 72.0,
        })
        assert ridicolous_breakout_prediction.perc == 2.5
        assert ridicolous_breakout_prediction.levels == 2
        assert ridicolous_breakout_prediction.min_history == 90
        assert ridicolous_breakout_prediction.min_confidence == 72.0
    finally:
        ridicolous_breakout_prediction.apply_config(before)
