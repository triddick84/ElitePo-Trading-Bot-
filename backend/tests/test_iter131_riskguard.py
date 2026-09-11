"""Iter 131 — RiskGuard: trade-size calculator + session discipline."""
import re
import sys

import httpx
import pytest

sys.path.insert(0, "/app/backend")

from risk_guard_service import (  # noqa: E402
    calculate_next_trade,
    compute_session_status,
    summarize_session,
    MIN_STAKE,
    MAX_STAKE_FRACTION,
)


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()
TEST_USER = "riskguard_pytest"


# ---------------------------------------------------------------------------
# Pure calculator math
# ---------------------------------------------------------------------------
def test_calc_basic_first_trade_of_session():
    r = calculate_next_trade(
        capital=1000, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=0, current_pnl=0,
    )
    assert r["allowed"]
    # target=500, 5 trades left, 0.85 payout → 500/(5*0.85) = 117.65
    assert abs(r["amount"] - 117.65) < 0.01


def test_calc_target_reached_locks_further_trades():
    r = calculate_next_trade(
        capital=1000, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=3, current_pnl=520,
    )
    assert not r["allowed"]
    assert r["reason"] == "target_reached"


def test_calc_stop_loss_hit_locks_further_trades():
    r = calculate_next_trade(
        capital=1000, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=3, current_pnl=-320,
    )
    assert not r["allowed"]
    assert r["reason"] == "stop_loss_hit"


def test_calc_max_trades_hit_locks_further_trades():
    r = calculate_next_trade(
        capital=1000, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=5, current_pnl=100,
    )
    assert not r["allowed"]
    assert r["reason"] == "max_trades_reached"


def test_calc_never_exceeds_capital_fraction():
    # Absurdly high target relative to capital would blow the account
    r = calculate_next_trade(
        capital=100, payout_pct=0.85, target_profit=5000,
        stop_loss=50, max_trades=5, trades_taken=0, current_pnl=0,
    )
    assert r["allowed"]
    assert r["amount"] <= 100 * MAX_STAKE_FRACTION + 0.01


def test_calc_respects_remaining_loss_budget_after_streak():
    # Already down $250 with $300 stop-loss → only $50 headroom left
    r = calculate_next_trade(
        capital=1000, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=3, current_pnl=-250,
    )
    assert r["allowed"]
    assert r["amount"] <= 50 + 0.01, f"amount {r['amount']} exceeds remaining loss budget"


def test_calc_never_below_min_stake():
    r = calculate_next_trade(
        capital=10_000, payout_pct=0.85, target_profit=1,
        stop_loss=1000, max_trades=100, trades_taken=0, current_pnl=0,
    )
    assert r["amount"] >= MIN_STAKE


def test_calc_rejects_zero_capital():
    r = calculate_next_trade(
        capital=0, payout_pct=0.85, target_profit=500,
        stop_loss=300, max_trades=5, trades_taken=0, current_pnl=0,
    )
    assert not r["allowed"]


# ---------------------------------------------------------------------------
# Session status derivation
# ---------------------------------------------------------------------------
def test_session_status_active_when_within_all_limits():
    s = {"target_profit": 500, "stop_loss": 300, "max_trades": 5,
         "trades": [{"outcome": "win", "amount": 100, "pnl": 85}]}
    assert compute_session_status(s) == "active"


def test_session_status_target_reached():
    s = {"target_profit": 500, "stop_loss": 300, "max_trades": 10,
         "trades": [{"outcome": "win", "amount": 600, "pnl": 510}]}
    assert compute_session_status(s) == "target_reached"


def test_session_status_stop_loss_hit():
    s = {"target_profit": 500, "stop_loss": 300, "max_trades": 10,
         "trades": [{"outcome": "loss", "amount": 320, "pnl": -320}]}
    assert compute_session_status(s) == "stop_loss_hit"


def test_summarize_session_computes_win_rate_and_gain_pct():
    s = {"id": "abc", "user_id": "u", "capital": 1000,
         "payout_pct": 0.85, "target_profit": 500,
         "stop_loss": 300, "max_trades": 5,
         "trades": [{"outcome": "win", "amount": 100, "pnl": 85},
                    {"outcome": "loss", "amount": 100, "pnl": -100},
                    {"outcome": "win", "amount": 200, "pnl": 170}]}
    out = summarize_session(s)
    assert out["wins"] == 2 and out["losses"] == 1
    # win_rate ignores draws → 2 / (2+1) = 66.7%
    assert abs(out["win_rate"] - 66.7) < 0.1
    assert abs(out["current_pnl"] - 155.0) < 0.01
    # account_gain_pct = 155 / 1000 = 15.5%
    assert abs(out["account_gain_pct"] - 15.5) < 0.01


# ---------------------------------------------------------------------------
# Live REST endpoints — full session lifecycle
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _cleanup_test_user():
    """Wipe any leftover sessions for the test user before + after each test
    so runs are independent. Sync fixture using pymongo — pytest-asyncio's
    strict mode doesn't run async autouse fixtures for async tests."""
    from pymongo import MongoClient
    env = open("/app/backend/.env").read()
    mongo_url = re.search(r'MONGO_URL="([^"]+)"', env).group(1)
    db_name = re.search(r'DB_NAME="([^"]+)"', env).group(1)
    c = MongoClient(mongo_url)
    c[db_name].risk_guard_sessions.delete_many({"user_id": TEST_USER})
    yield
    c[db_name].risk_guard_sessions.delete_many({"user_id": TEST_USER})


@pytest.mark.asyncio
async def test_endpoint_calculate_returns_expected_amount():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/riskguard/calculate", json={
            "capital": 1000, "payout_pct": 0.85, "target_profit": 500,
            "stop_loss": 300, "max_trades": 5, "trades_taken": 0, "current_pnl": 0,
        })
    assert r.status_code == 200
    b = r.json()
    assert b["success"] and b["allowed"]
    assert abs(b["amount"] - 117.65) < 0.01


@pytest.mark.asyncio
async def test_endpoint_start_session_creates_active_row():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 1000, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        assert r.status_code == 200
        s = r.json()["session"]
        assert s["status"] == "active"
        assert s["trades_taken"] == 0

        cur = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        assert cur.json()["session"]["id"] == s["id"]


@pytest.mark.asyncio
async def test_endpoint_record_trade_updates_pnl_and_win_rate():
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 1000, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        r1 = await c.post(f"{API}/riskguard/session/record-trade", json={
            "user_id": TEST_USER, "outcome": "win", "amount": 100,
        })
        assert r1.json()["success"] is True
        assert abs(r1.json()["session"]["current_pnl"] - 85.0) < 0.01

        r2 = await c.post(f"{API}/riskguard/session/record-trade", json={
            "user_id": TEST_USER, "outcome": "loss", "amount": 50,
        })
        s = r2.json()["session"]
        assert s["trades_taken"] == 2
        assert s["wins"] == 1 and s["losses"] == 1
        assert abs(s["current_pnl"] - 35.0) < 0.01


@pytest.mark.asyncio
async def test_endpoint_auto_closes_session_on_target_hit():
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 1000, "payout_pct": 1.0,
            "target_profit": 100, "stop_loss": 300, "max_trades": 5,
        })
        r = await c.post(f"{API}/riskguard/session/record-trade", json={
            "user_id": TEST_USER, "outcome": "win", "amount": 100,
        })
        assert r.json()["session"]["status"] == "target_reached"
        # Session must now be inactive
        cur = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        assert cur.json()["session"] is None


@pytest.mark.asyncio
async def test_endpoint_auto_closes_session_on_stop_loss_hit():
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 1000, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 100, "max_trades": 5,
        })
        r = await c.post(f"{API}/riskguard/session/record-trade", json={
            "user_id": TEST_USER, "outcome": "loss", "amount": 120,
        })
        assert r.json()["session"]["status"] == "stop_loss_hit"


@pytest.mark.asyncio
async def test_endpoint_summary_aggregates_across_sessions():
    async with httpx.AsyncClient(timeout=15.0) as c:
        for _ in range(2):
            await c.post(f"{API}/riskguard/session/start", json={
                "user_id": TEST_USER, "capital": 1000, "payout_pct": 0.85,
                "target_profit": 500, "stop_loss": 300, "max_trades": 5,
            })
            await c.post(f"{API}/riskguard/session/record-trade", json={
                "user_id": TEST_USER, "outcome": "win", "amount": 100,
            })
            await c.post(f"{API}/riskguard/session/close", json={"user_id": TEST_USER})
        r = await c.get(f"{API}/riskguard/stats/summary", params={"user_id": TEST_USER})
        s = r.json()
        assert s["total_sessions"] == 2
        assert s["total_trades"] == 2
        assert s["wins"] == 2
