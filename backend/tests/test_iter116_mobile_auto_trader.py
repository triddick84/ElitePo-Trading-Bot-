"""
Iter 116 — Mobile Auto-Trader page fixes regression.

Covers:
  A) /api/tampermonkey/strategies returns >= 40 strategies from the real
     registry (was hard-coded to 10)
  B) /api/tampermonkey/version returns live version.txt + features list
  C) /api/tampermonkey/stats POST/GET roundtrips with the new fields
     (last_result, auto_invert_active, trade_history)
  D) TM bundle at /pocket-option-auto-trader-modular.user.js:
       - version header matches version.txt
       - contains the /api/tampermonkey/stats POST snippet
"""

import os
import re
import pytest
import httpx


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m, "REACT_APP_BACKEND_URL missing"
    return f"{m.group(1)}/api"


API = _api()
BUNDLE_URL = _api().rsplit("/api", 1)[0] + "/pocket-option-auto-trader-modular.user.js"


@pytest.mark.asyncio
async def test_a_strategies_dynamic_and_large():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/tampermonkey/strategies")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["strategies"], list)
    assert len(body["strategies"]) >= 40, f"Only {len(body['strategies'])} strategies"
    # "Auto (AI Selection)" is always first
    assert body["strategies"][0]["id"] == "auto"
    # Every entry has an id and name
    for s in body["strategies"]:
        assert s.get("id") and s.get("name")


@pytest.mark.asyncio
async def test_a_strategies_timeframe_filter():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/tampermonkey/strategies", params={"timeframe": "5s"})
    assert r.status_code == 200
    body = r.json()
    # Every non-Auto entry should list 5s in timeframes
    non_auto = [s for s in body["strategies"] if s["id"] != "auto"]
    assert non_auto, "No 5s strategies returned"
    for s in non_auto:
        assert "5s" in (s.get("timeframes") or []), f"Missing 5s: {s['name']}"


@pytest.mark.asyncio
async def test_b_version_endpoint():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/tampermonkey/version")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # Must match version.txt
    with open("/app/tampermonkey-src/version.txt") as fh:
        expected = fh.read().strip()
    assert body["version"] == expected
    assert isinstance(body["features"], list) and len(body["features"]) >= 5


@pytest.mark.asyncio
async def test_c_stats_roundtrip_new_fields():
    payload = {
        "wins": 7,
        "losses": 3,
        "consecutive_wins": 2,
        "consecutive_losses": 0,
        "session_profit": 5.55,
        "last_result": "win",
        "auto_invert_active": True,
        "trade_history": [
            {"result": "win", "direction": "UP", "amount": 1, "asset": "EURUSD_OTC", "profit": 0.85, "ts": 1},
            {"result": "loss", "direction": "DOWN", "amount": 1, "asset": "EURUSD_OTC", "profit": -1, "ts": 2},
        ],
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r1 = await c.post(f"{API}/tampermonkey/stats", json=payload)
        assert r1.status_code == 200 and r1.json()["success"]
        r2 = await c.get(f"{API}/tampermonkey/stats")
        assert r2.status_code == 200
        stats = r2.json()["stats"]
        assert stats["wins"] == 7
        assert stats["losses"] == 3
        assert stats["last_result"] == "win"
        assert stats["auto_invert_active"] is True
        assert len(stats["trade_history"]) == 2


@pytest.mark.asyncio
async def test_d_tm_bundle_matches_version_and_has_stats_push():
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
        r = await c.get(BUNDLE_URL)
    assert r.status_code == 200, f"Bundle unreachable: {r.status_code}"
    src = r.text
    with open("/app/tampermonkey-src/version.txt") as fh:
        expected = fh.read().strip()
    # Header @version must match version.txt exactly
    assert f"@version      {expected}" in src or f"@version {expected}" in src, (
        f"version.txt is {expected} but bundle header doesn't include it"
    )
    # Iter 116 — Session Statistics push must be present
    assert "/api/tampermonkey/stats" in src, "Bundle missing /api/tampermonkey/stats POST"
