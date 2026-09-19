"""Iter 150 — Fix pack regression: TM chart-type, Telegram invert, ML retrain
timeout, AI Models optimization determinism, Risk Guard → TM bridge."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper — spin up a minimal FastAPI app with just the fix-pack router
# ---------------------------------------------------------------------------

def _minimal_app():
    from fastapi import FastAPI
    from routes.iter150_fixpack import router
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


# ---------------------------------------------------------------------------
# #2 Telegram invert toggle
# ---------------------------------------------------------------------------

def test_telegram_invert_get_set_toggle():
    from fastapi.testclient import TestClient
    from telegram_bot_service import TelegramBotService

    fake = TelegramBotService()
    with patch("routes.iter150_fixpack._get_tg_service", return_value=fake):
        client = TestClient(_minimal_app())

        # Initial state
        r = client.get("/api/telegram/invert")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        # Set to True
        r = client.post("/api/telegram/invert", json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        assert fake.invert_enabled is True

        # Toggle (True → False)
        r = client.post("/api/telegram/invert/toggle")
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert fake.invert_enabled is False


def test_telegram_send_signal_respects_invert():
    """When invert_enabled=True, CALL becomes PUT in the outgoing message."""
    import asyncio
    from telegram_bot_service import TelegramBotService, TradingSignal
    fake = TelegramBotService()
    fake.default_chat_id = "1"
    fake.bot_token = "fake"

    captured = {}
    async def fake_send_message(text, chat_id=None, parse_mode=None):
        captured["text"] = text
        return {"success": True, "message_id": 1}
    fake.send_message = fake_send_message

    signal = TradingSignal(
        id="sig-1",
        symbol="EURUSD_otc",
        direction="CALL",
        confidence=75.0,
        strategy="test",
        expiration_seconds=60,
        entry_price=1.10,
        timeframe="1m",
        timestamp="2026-02-12T00:00:00Z",
    )

    # Default (not inverted) → CALL wording
    r = asyncio.run(fake.send_signal(signal))
    assert r["success"]
    assert "CALL" in captured["text"]
    assert "INVERTED" not in captured["text"]

    # After enable → PUT wording + INVERTED tag
    fake.invert_enabled = True
    r = asyncio.run(fake.send_signal(signal))
    assert r["success"]
    assert "PUT" in captured["text"]
    assert "INVERTED" in captured["text"]


# ---------------------------------------------------------------------------
# #3 AI Models optimization determinism explainer
# ---------------------------------------------------------------------------

def test_optimization_data_version_reports_row_count(monkeypatch):
    """#3 — the endpoint surfaces backtest_rows so the UI can explain
    why optimization output is identical when data hasn't changed."""
    from fastapi.testclient import TestClient
    import sys

    class FakeCursor:
        def sort(self, *a, **kw): return self
        def limit(self, *a, **kw): return self
        async def to_list(self, *a, **kw): return []

    class FakeColl:
        async def count_documents(self, *a, **kw): return 12
        def find(self, *a, **kw): return FakeCursor()

    class FakeDB:
        backtest_results = FakeColl()

    # Stub the server module BEFORE the endpoint tries to import it.
    # server.py has module-level side effects (asyncio.create_task) that
    # blow up outside an event loop — bypass by injecting a fake.
    fake_srv = type(sys)("server")
    fake_srv.db = FakeDB()
    monkeypatch.setitem(sys.modules, "server", fake_srv)

    client = TestClient(_minimal_app())
    r = client.get("/api/ml-training/optimization-data-version")
    assert r.status_code == 200
    body = r.json()
    assert body["backtest_rows"] == 12
    assert body["eligible_to_optimize"] is True
    assert "deterministic aggregation" in body["note"]


# ---------------------------------------------------------------------------
# #4 ML Lab retrain — per-phase timeout wrapper
# ---------------------------------------------------------------------------

def test_run_phase_with_timeout_success():
    from routes.iter150_fixpack import run_phase_with_timeout
    async def go():
        async def coro(): return "trained"
        return await run_phase_with_timeout(coro(), phase_name="test_phase", timeout_s=5)
    r = asyncio.run(go())
    assert r["success"] is True
    assert r["phase"] == "test_phase"
    assert r["elapsed_s"] < 5
    assert "trained" in r["result"]


def test_run_phase_with_timeout_kills_hung_phase():
    from routes.iter150_fixpack import run_phase_with_timeout
    async def go():
        async def hung():
            await asyncio.sleep(10)  # would hang forever if not timed out
        return await run_phase_with_timeout(hung(), phase_name="hung_phase", timeout_s=1)
    r = asyncio.run(go())
    assert r["success"] is False
    assert "timeout" in r["error"].lower()
    assert r["elapsed_s"] == 1


def test_run_phase_captures_exception_type():
    from routes.iter150_fixpack import run_phase_with_timeout
    async def go():
        async def boom(): raise RuntimeError("boom")
        return await run_phase_with_timeout(boom(), phase_name="err_phase", timeout_s=5)
    r = asyncio.run(go())
    assert r["success"] is False
    assert "RuntimeError" in r["error"]
    assert "boom" in r["error"]


# ---------------------------------------------------------------------------
# #5 Risk Guard → TM bridge
# ---------------------------------------------------------------------------

def test_riskguard_tm_config_uses_active_session(monkeypatch):
    from fastapi.testclient import TestClient
    import sys

    active_session = {
        "user_id": "default",
        "session_id": "sess-1",
        "status": "active",
        "start_amount": 500.0,
        "per_trade_amount": 10.0,
        "max_daily_loss": 50.0,
        "stop_after_losses": 4,
        "confidence_tiers": [
            {"min_confidence": 60, "multiplier": 1.0},
            {"min_confidence": 80, "multiplier": 2.5},
        ],
    }

    class FakeSessions:
        async def find_one(self, query, sort=None):
            return active_session

    class FakeDB:
        riskguard_sessions = FakeSessions()

    fake_srv = type(sys)("server")
    fake_srv.db = FakeDB()
    monkeypatch.setitem(sys.modules, "server", fake_srv)

    client = TestClient(_minimal_app())
    r = client.get("/api/riskguard/tampermonkey/config?user_id=default")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["session_active"] is True
    assert body["session_id"] == "sess-1"
    assert body["per_trade_amount"] == 10.0
    assert body["max_daily_loss"] == 50.0
    assert body["stop_after_losses"] == 4
    assert len(body["confidence_tiers"]) == 2
    assert body["confidence_tiers"][1]["multiplier"] == 2.5


def test_riskguard_tm_config_falls_back_to_safe_defaults_on_error(monkeypatch):
    from fastapi.testclient import TestClient
    import sys

    class FakeSessions:
        async def find_one(self, *a, **kw): raise RuntimeError("db down")

    class FakeDB:
        riskguard_sessions = FakeSessions()

    fake_srv = type(sys)("server")
    fake_srv.db = FakeDB()
    monkeypatch.setitem(sys.modules, "server", fake_srv)

    client = TestClient(_minimal_app())
    r = client.get("/api/riskguard/tampermonkey/config")
    # Must not fail — TM start-session must always get a config.
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["per_trade_amount"] > 0     # safe default
    assert body["stop_after_losses"] >= 1
    assert len(body["confidence_tiers"]) >= 3


def test_riskguard_tm_config_no_session_returns_defaults(monkeypatch):
    from fastapi.testclient import TestClient
    import sys

    class FakeSessions:
        async def find_one(self, *a, **kw): return None

    class FakeDB:
        riskguard_sessions = FakeSessions()

    fake_srv = type(sys)("server")
    fake_srv.db = FakeDB()
    monkeypatch.setitem(sys.modules, "server", fake_srv)

    client = TestClient(_minimal_app())
    r = client.get("/api/riskguard/tampermonkey/config")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["session_active"] is False
    assert body["start_amount"] == 100.0
    assert body["per_trade_amount"] == 2.0    # 2% of 100


# ---------------------------------------------------------------------------
# TM bundle — post-webpack sanity contracts
# ---------------------------------------------------------------------------

def test_bundle_has_iter150_symbols():
    from pathlib import Path
    b = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
    if not b.exists():
        pytest.skip("bundle not built")
    txt = b.read_text()
    for probe in [
        "riskguard/tampermonkey/config",   # bridge fetch URL
        "manualChartType",                 # chart-type GM key
        "onSessionStart",                  # session-start callback
        "__aiEliteRiskGuardSync",          # DevTools helper
        # Iter 151 bumped the header past 8.155 — just assert we're at
        # or past the version that introduced these Iter 150 symbols.
        "@version      8.15",              # 8.155.x / 8.156.x / etc.
    ]:
        assert probe in txt, f"missing bundle probe: {probe}"
