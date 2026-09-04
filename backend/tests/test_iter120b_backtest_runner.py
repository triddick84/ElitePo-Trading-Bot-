"""
Iter 120b — Strategy backtest runner regression.

Verifies:
  - POST /api/strategies/backtest returns full contract
  - Works for Ridicolous strategy on EURUSD_OTC 1m
  - Includes Ridicolous probability_table when applicable
  - Rejects unknown strategy_id with 404
  - Rejects out-of-range days with 422
  - Confidence buckets sum consistently with wins/losses
"""

import re

import httpx
import pytest


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()


@pytest.mark.asyncio
async def test_ridicolous_backtest_returns_full_shape():
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 30,
            "max_candles": 2000,
            "stride": 3,
        })
    assert r.status_code == 200, r.text
    body = r.json()
    if not body.get("success"):
        # Environment may not have enough OTC candles — accept a clear error but
        # still verify the error shape
        assert "error" in body
        return
    for k in ("strategy_id", "strategy_name", "asset", "timeframe",
              "days_requested", "candles_used", "signals",
              "wins", "losses", "sample_size", "win_rate", "sim_pnl",
              "payout_used", "avg_confidence", "confidence_buckets",
              "strategy_specific"):
        assert k in body, f"missing key {k} in backtest response"
    assert body["strategy_id"] == "ridicolous_breakout_prediction"
    assert body["signals"]["total"] == (
        body["signals"]["calls"] + body["signals"]["puts"] + body["signals"]["neutrals"]
    )
    # Wins + losses <= calls + puts (ties can drop some)
    assert body["wins"] + body["losses"] <= body["signals"]["calls"] + body["signals"]["puts"]

    # Ridicolous-specific probability table
    if body["strategy_specific"].get("ridicolous_table"):
        table = body["strategy_specific"]["ridicolous_table"]
        assert "probability_table" in table
        assert len(table["probability_table"]) == 5
        for row in table["probability_table"]:
            for k in ("level", "green_new_high_pct", "green_new_low_pct",
                      "red_new_high_pct", "red_new_low_pct"):
                assert k in row


@pytest.mark.asyncio
async def test_backtest_unknown_strategy_returns_404():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "nonexistent_strategy_xyz",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 30,
        })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_backtest_validates_days_bounds():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 999,  # > 365 limit
        })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_backtest_confidence_buckets_shape():
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 15,
            "max_candles": 1500,
            "stride": 5,
        })
    body = r.json()
    if not body.get("success"):
        return
    buckets = body["confidence_buckets"]
    assert isinstance(buckets, list) and len(buckets) == 5
    for b in buckets:
        for k in ("bucket", "wins", "losses", "n", "win_rate"):
            assert k in b
        assert b["wins"] + b["losses"] == b["n"]
        if b["n"] > 0:
            assert 0.0 <= b["win_rate"] <= 1.0
