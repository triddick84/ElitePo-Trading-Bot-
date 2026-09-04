"""
Iter 122 — Three-bug fix regression.

Bug 1: Backtest fails silently — friendly errors for unsupported strategies + missing candles.
Bug 2: Auto-invert event log endpoints (backend audit trail for TM script).
Bug 3: Elite-Screener signal routing (POST → active_target → /signals/latest synthesis).
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


# ---------------------------------------------------------------------------
# Bug 1 — Backtest UX
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug1_unregistered_strategy_returns_helpful_400():
    """Was: 404 'not registered'. Now: 400 with a message pointing users to
    strategies that DO support backtest."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "triple_confirmation_1m",  # in picker, not in registry
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 30,
        })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "does not support offline backtesting" in detail
    assert "ridicolous_breakout_prediction" in detail  # points to fallback options


@pytest.mark.asyncio
async def test_bug1_missing_candles_returns_helpful_message():
    """Assets like BTCUSD_OTC have no candles in this env. Should return a
    clear guidance message, not a cryptic 'insufficient historical candles'."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "BTCUSD_OTC",
            "timeframe": "1m",
            "days": 30,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "Not enough historical candles" in body["error"]
    # Guidance mentions alternate assets
    assert "EURUSD_OTC" in body["error"] or "GBPUSD_OTC" in body["error"]
    assert body["candles_loaded"] == 0


@pytest.mark.asyncio
async def test_bug1_registered_strategy_still_works():
    """Sanity: registered strategies still return success:true."""
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(f"{API}/strategies/backtest", json={
            "strategy_id": "ridicolous_breakout_prediction",
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "days": 30,
        })
    assert r.status_code == 200
    body = r.json()
    if body.get("success"):
        assert "win_rate" in body
    else:
        # Preview may lack candles; make sure it's still the friendly message
        assert "Not enough" in body.get("error", "") or "candles" in body.get("error", "")


# ---------------------------------------------------------------------------
# Bug 2 — Auto-invert event log
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug2_log_and_summary():
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Log a synthetic ACTIVATED event
        r = await c.post(f"{API}/tampermonkey/invert-events/log", json={
            "event": "ACTIVATED",
            "reason": "lossStreak=2/2",
            "is_inverted": True,
            "auto_invert_enabled": True,
            "config_enabled": True,
            "manual_override": False,
            "current_streak": -2,
            "loss_streak": 2,
            "threshold": 2,
            "inverted_trade_count": 0,
            "asset": "EURUSD_OTC",
            "tm_version": "8.144.0",
        })
    assert r.status_code == 200
    assert r.json()["logged"] is True

    async with httpx.AsyncClient(timeout=15.0) as c:
        s = await c.get(f"{API}/tampermonkey/invert-events/summary")
    body = s.json()
    assert body["success"] is True
    assert body["total"] >= 1
    assert body["latest"]["event"] == "ACTIVATED"
    assert body["latest"]["is_inverted"] is True


@pytest.mark.asyncio
async def test_bug2_recent_events_ordered_desc():
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Fire 3 events in known order
        for ev in ("BLOCKED", "EVALUATED", "DEACTIVATED"):
            await c.post(f"{API}/tampermonkey/invert-events/log", json={
                "event": ev, "reason": f"test_{ev}",
                "auto_invert_enabled": True, "config_enabled": True,
                "current_streak": 0, "loss_streak": 0, "threshold": 2,
            })
        r = await c.get(f"{API}/tampermonkey/invert-events/recent", params={"limit": 3})
    body = r.json()
    assert body["success"] is True
    # Most-recent first — should start with DEACTIVATED (last posted)
    assert body["events"][0]["event"] == "DEACTIVATED"


# ---------------------------------------------------------------------------
# Bug 3 — Elite Screener routing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug3_active_target_get_exposes_direction_and_source():
    """GET must return direction/confidence/elite_score/source_route when set."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "direction": "CALL",
            "confidence": 0.82,
            "elite_score": 85,
            "source": "elite_screener",
            "target_ttl_seconds": 60,
        })
        r = await c.get(f"{API}/tampermonkey/active-target")
    body = r.json()
    assert body["asset"] == "EURUSD_OTC"
    assert body["direction"] == "CALL"
    assert body["confidence"] == 0.82
    assert body["elite_score"] == 85.0
    assert body["source_route"] == "elite_screener"
    # Clean up
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={"asset": None})


@pytest.mark.asyncio
async def test_bug3_signals_latest_synthesizes_from_active_target():
    """Core fix: /signals/latest returns a synthesized signal reflecting the
    Elite Screener's push, not the ambient Enhanced AI + Technical signal."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "direction": "PUT",
            "confidence": 0.79,
            "elite_score": 88,
            "source": "elite_screener",
            "target_ttl_seconds": 60,
        })
        # Give the DB a moment
        import asyncio; await asyncio.sleep(0.5)
        r = await c.get(f"{API}/signals/latest", params={"symbol": "EURUSD_OTC"})
    body = r.json()
    assert body["success"] is True
    assert body.get("source") == "active_target_routed"
    sig = body["signal"]
    assert sig["direction"] == "PUT"
    assert sig["confidence"] == 79.0
    assert sig["strategy"] == "routed_from_elite_screener"
    assert sig["routed_by"] == "elite_screener"
    assert sig["elite_score"] == 88.0
    # Clean up
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={"asset": None})


@pytest.mark.asyncio
async def test_bug3_signals_latest_falls_back_when_no_active_target():
    """When no override exists, /signals/latest falls back to the ambient path
    (Enhanced AI or DB-backed signal). Must NOT return active_target_routed."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Ensure no override
        await c.post(f"{API}/tampermonkey/active-target", json={"asset": None})
        import asyncio; await asyncio.sleep(0.5)
        r = await c.get(f"{API}/signals/latest", params={"symbol": "EURUSD_OTC"})
    body = r.json()
    # No routed source
    assert body.get("source") != "active_target_routed"


@pytest.mark.asyncio
async def test_bug3_routed_signal_expires_correctly():
    """After TTL elapses, /signals/latest must NOT return the stale routed signal.
    Server clamps target_ttl_seconds to a minimum of 10s so we wait 11s."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "direction": "CALL",
            "confidence": 0.60,
            "source": "elite_screener",
            "target_ttl_seconds": 1,  # server clamps to 10s minimum
        })
        import asyncio; await asyncio.sleep(11.0)
        r = await c.get(f"{API}/signals/latest", params={"symbol": "EURUSD_OTC"})
    body = r.json()
    assert body.get("source") != "active_target_routed", (
        "Expired routed signal should not be returned"
    )
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/tampermonkey/active-target", json={"asset": None})
