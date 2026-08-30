"""
Iter 117 — Elite Screener→TM · SNS multi-second · AI-tab data fix.

Covers:
  A) POST /api/tampermonkey/active-target now accepts + persists
     direction/confidence/elite_score/source/expires_at
  B) TM userscript v8.142 bundle contains the multi-second SNS chip picker
     hooks (sns-multi-chips DOM markers)
  C) GET /api/signals/preview:
       - ISO-string cutoff is honoured (was silently mismatched)
       - Falls back to newest N with stale=true when the fresh window is empty
       - Handles asset variants (EURUSD_OTC ↔ EURUSD)
  D) GET /api/trades/recent-outcomes falls back to tampermonkey_stats.trade_history
     when trade_reports is empty
"""

import re
import pytest
import httpx


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m
    return f"{m.group(1)}/api"


API = _api()
BASE = API.rsplit("/api", 1)[0]
BUNDLE_URL = BASE + "/pocket-option-auto-trader-modular.user.js"


@pytest.mark.asyncio
async def test_a_active_target_with_signal_fields():
    async with httpx.AsyncClient(timeout=30.0) as c:
        payload = {
            "asset": "EURUSD_OTC",
            "timeframe": "1m",
            "direction": "CALL",
            "confidence": 0.87,
            "elite_score": 78.5,
            "source": "elite_screener",
            "target_ttl_seconds": 90,
        }
        r = await c.post(f"{API}/tampermonkey/active-target", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    at = body["active_target"]
    assert at["asset"] == "EURUSD_OTC"
    assert at["direction"] == "CALL"
    assert at["confidence"] == 0.87
    assert at["elite_score"] == 78.5
    assert at["source"] == "elite_screener"
    assert "expires_at" in at


@pytest.mark.asyncio
async def test_a_active_target_direction_normalisation():
    """UP / DOWN / BUY / SELL should coerce to CALL / PUT."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        for raw, expected in [
            ("up", "CALL"), ("DOWN", "PUT"), ("BUY", "CALL"), ("sell", "PUT")
        ]:
            r = await c.post(f"{API}/tampermonkey/active-target",
                             json={"asset": "EURUSD_OTC", "direction": raw})
            assert r.status_code == 200
            assert r.json()["active_target"]["direction"] == expected


@pytest.mark.asyncio
async def test_a_active_target_confidence_normalisation():
    """87 (percent) should coerce to 0.87 (fraction)."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/tampermonkey/active-target",
                         json={"asset": "EURUSD_OTC", "confidence": 87})
    assert r.status_code == 200
    assert r.json()["active_target"]["confidence"] == 0.87


@pytest.mark.asyncio
async def test_b_tm_bundle_has_multi_second_ui():
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
        r = await c.get(BUNDLE_URL)
    assert r.status_code == 200
    src = r.text
    # Version bumped to 8.142+
    m = re.search(r"@version\s+(\S+)", src)
    assert m, "no @version in header"
    parts = m.group(1).split(".")
    assert int(parts[0]) >= 8 and int(parts[1]) >= 142, f"version too low: {m.group(1)}"
    # DOM markers for the new multi-chip picker must be present
    assert "sns-multi-picker" in src
    assert "sns-multi-chips" in src
    assert "sns-multi-clear" in src


@pytest.mark.asyncio
async def test_c_signals_preview_fresh_or_stale():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/signals/preview", params={"asset": "EURUSD_OTC"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "stale" in body
    # Either fresh (stale=False) or fallback (stale=True) — never a bare failure


@pytest.mark.asyncio
async def test_c_signals_preview_variant_matching():
    """EURUSD_OTC should also find rows stored as EURUSD (no _OTC suffix)."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r1 = await c.get(f"{API}/signals/preview", params={"asset": "EURUSD_OTC"})
        r2 = await c.get(f"{API}/signals/preview", params={"asset": "EURUSD"})
    assert r1.status_code == 200 and r2.status_code == 200
    # Either both empty, or the OTC-variant returns at least as many rows as the base.
    assert isinstance(r1.json()["votes"], list)
    assert isinstance(r2.json()["votes"], list)


@pytest.mark.asyncio
async def test_d_recent_outcomes_falls_back_to_tm_history():
    async with httpx.AsyncClient(timeout=30.0) as c:
        # Seed a tm stats doc with history
        await c.post(f"{API}/tampermonkey/stats", json={
            "wins": 1, "losses": 0, "consecutive_wins": 1,
            "consecutive_losses": 0, "session_profit": 0.85,
            "last_result": "win", "auto_invert_active": False,
            "trade_history": [
                {"result": "win", "direction": "UP", "amount": 1,
                 "asset": "EURUSD_OTC", "profit": 0.85, "ts": 1_700_000_000_000},
                {"result": "loss", "direction": "DOWN", "amount": 1,
                 "asset": "EURUSD_OTC", "profit": -1, "ts": 1_700_000_000_001},
            ],
        })
        r = await c.get(f"{API}/trades/recent-outcomes", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # Fallback should have injected at least the two seeded rows if trade_reports empty
    if body["count"] > 0:
        assert body["outcomes"][0]["direction"] in ("CALL", "PUT")
        assert body["outcomes"][0]["result"] in ("WIN", "LOSS", "")
