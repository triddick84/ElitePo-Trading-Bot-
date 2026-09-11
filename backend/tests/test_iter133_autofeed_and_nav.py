"""Iter 133 — Auto-feed RiskGuard from TM trade reports + nav emoji sweep."""
import re
import sys

import httpx
import pytest
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()
TEST_USER = "default"  # Auto-feed hard-codes user_id="default"


def _mongo():
    env = open("/app/backend/.env").read()
    mongo_url = re.search(r'MONGO_URL="([^"]+)"', env).group(1)
    db_name = re.search(r'DB_NAME="([^"]+)"', env).group(1)
    c = MongoClient(mongo_url)
    return c[db_name]


@pytest.fixture(autouse=True)
def _clean_env():
    db = _mongo()
    # Aggressive cleanup — auto-feed hard-codes user_id="default" so any
    # leaked session from a previous test (in this file or other files) can
    # cause cross-test interference. We wipe every session for the default
    # user that carries our capital=999 test marker OR the auto-fed notes.
    q = {"user_id": TEST_USER, "capital": 999}
    db.risk_guard_sessions.delete_many(q)
    db.tm_trade_reports.delete_many({"asset": "TESTAUTO_OTC"})
    yield
    db.risk_guard_sessions.delete_many(q)
    db.tm_trade_reports.delete_many({"asset": "TESTAUTO_OTC"})
    # Also close any other active default-user sessions that our
    # auto-feed accidentally touched so downstream test files aren't
    # affected.
    try:
        import httpx as _hx
        _hx.post(f"{API}/riskguard/session/close",
                 json={"user_id": TEST_USER}, timeout=5.0)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auto-feed via /trades/report (initial ingest already has outcome)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_trade_report_with_outcome_feeds_riskguard_session():
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Start a session (capital=999 marks it as ours)
        r = await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 999, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        assert r.status_code == 200

        # Fire a TM trade report with outcome=win, amount=50
        r2 = await c.post(f"{API}/trades/report", json={
            "asset": "TESTAUTO_OTC", "direction": "CALL",
            "amount": 50.0, "outcome": "win",
            "source": "tm-autofeed-test",
        })
        assert r2.status_code == 200
        assert r2.json().get("stored") is True

        # RiskGuard's active session should now have the trade recorded
        r3 = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        session = r3.json()["session"]
        assert session["trades_taken"] == 1
        assert session["wins"] == 1
        # +50 * 0.85 = +42.50 P&L
        assert abs(session["current_pnl"] - 42.5) < 0.01
        # Trade note tagged as auto-fed
        assert any("auto" in (t.get("note") or "") for t in session["trades"])


@pytest.mark.asyncio
async def test_trade_report_loss_flips_pnl_negative():
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 999, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        await c.post(f"{API}/trades/report", json={
            "asset": "TESTAUTO_OTC", "direction": "PUT",
            "amount": 25.0, "outcome": "loss",
        })
        r = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        s = r.json()["session"]
        assert s["losses"] == 1
        assert abs(s["current_pnl"] - (-25.0)) < 0.01


@pytest.mark.asyncio
async def test_trade_report_without_outcome_does_not_feed():
    """A /trades/report with no outcome (pending trade) must NOT create a
    trade row in the RiskGuard session — otherwise we'd double-count when
    the outcome arrives later via /trades/outcome."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 999, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        await c.post(f"{API}/trades/report", json={
            "asset": "TESTAUTO_OTC", "direction": "CALL",
            "amount": 30.0,  # NO outcome field
        })
        r = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        s = r.json()["session"]
        assert s["trades_taken"] == 0


@pytest.mark.asyncio
async def test_trade_report_with_no_active_session_is_noop():
    """A trade report firing when there's no active RiskGuard session must
    not error — the auto-feed must be silently no-op."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Make sure no session is active
        await c.post(f"{API}/riskguard/session/close", json={"user_id": TEST_USER})
        r = await c.post(f"{API}/trades/report", json={
            "asset": "TESTAUTO_OTC", "direction": "CALL",
            "amount": 40.0, "outcome": "win",
        })
        # Report still stored successfully even without active session
        assert r.status_code == 200
        assert r.json().get("stored") is True


# ---------------------------------------------------------------------------
# Auto-feed via /trades/outcome (two-stage: report → later outcome)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outcome_endpoint_feeds_riskguard_when_matched():
    async with httpx.AsyncClient(timeout=15.0) as c:
        await c.post(f"{API}/riskguard/session/start", json={
            "user_id": TEST_USER, "capital": 999, "payout_pct": 0.85,
            "target_profit": 500, "stop_loss": 300, "max_trades": 5,
        })
        # Stage 1: outcomeless report
        await c.post(f"{API}/trades/report", json={
            "asset": "TESTAUTO_OTC", "direction": "CALL",
            "amount": 60.0,
        })
        # Stage 2: outcome arrives
        r = await c.post(f"{API}/trades/outcome", json={
            "asset": "TESTAUTO_OTC", "outcome": "WIN",
        })
        assert r.status_code == 200
        assert r.json().get("matched_trade") is not False

        r2 = await c.get(f"{API}/riskguard/session/current", params={"user_id": TEST_USER})
        s = r2.json()["session"]
        assert s["trades_taken"] == 1
        assert s["wins"] == 1
        # +60 * 0.85 = +51
        assert abs(s["current_pnl"] - 51.0) < 0.01


# ---------------------------------------------------------------------------
# Frontend nav emoji sweep
# ---------------------------------------------------------------------------
def test_nav_uses_lucide_icons_not_emojis():
    src = open("/app/frontend/src/App.js").read()
    # Every nav item should be `{ id, label, Icon }` where Icon is a lucide component
    nav_block_match = re.search(
        r"const navigation = \[(.*?)\];", src, re.DOTALL,
    )
    assert nav_block_match, "navigation array not found"
    nav_block = nav_block_match.group(1)

    # No emoji `icon: "…"` entries remain
    assert 'icon: "📊"' not in nav_block
    assert 'icon: "📱"' not in nav_block
    assert 'icon: "🎰"' not in nav_block
    assert 'icon: "🛡️"' not in nav_block
    assert 'icon: "🧠"' not in nav_block

    # Every entry has an `Icon:` component reference
    icon_refs = re.findall(r"Icon:\s*([A-Z][A-Za-z]+)", nav_block)
    assert len(icon_refs) >= 17, f"expected 17+ Icon entries, got {len(icon_refs)}"


def test_nav_icons_are_imported_from_lucide():
    src = open("/app/frontend/src/App.js").read()
    # Verify the lucide-react import declares every icon used
    lucide_match = re.search(
        r'from "lucide-react";', src,
    )
    assert lucide_match, "lucide-react import not found"
    for name in ("LayoutDashboard", "Send", "LineChart", "Smartphone",
                 "Shield", "Waves", "SearchCode", "Plug", "Route",
                 "UserCheck", "Target", "Brain", "FlaskConical", "Zap",
                 "Users", "BarChart3"):
        assert re.search(rf"\b{name}\b", src), f"lucide icon {name} not imported/used"


def test_active_nav_uses_cyan_theme_not_purple():
    """Active-state must have moved off the old purple theme to the new
    cyan-based palette that matches the modern bot logo."""
    src = open("/app/frontend/src/App.js").read()
    # The sidebar button block must contain the cyan active class AND the
    # nav-<id> testid — order in source is className then data-testid.
    m = re.search(r"bg-cyan-500/15 text-cyan-300[\s\S]{0,500}nav-\$\{item\.id\}", src)
    assert m, "active nav item must use cyan theme (bg-cyan-500/15 text-cyan-300)"
    # And no purple active state remains
    assert "bg-purple-600/20 text-purple-400" not in src
