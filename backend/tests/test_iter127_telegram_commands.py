"""Iter 127 — Telegram command menu (/pause /resume /status /stake) regression."""
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "/app/backend")


def _fake_update(chat_id: int, text: str = "", args=None):
    """Build a minimal Update stub good enough for the command handlers."""
    chat = SimpleNamespace(id=chat_id)
    msg = SimpleNamespace(text=text, caption=None)
    return SimpleNamespace(effective_chat=chat, effective_message=msg,
                            message=msg)


def _fake_context(args=None):
    return SimpleNamespace(args=list(args or []), error=None)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def test_command_handlers_are_registered_in_start():
    """start_telegram_bot must attach /pause /resume /status /stake /help."""
    import telegram_service as ts
    src = open(ts.__file__).read()
    assert 'CommandHandler("pause"' in src
    assert 'CommandHandler("resume"' in src
    assert 'CommandHandler("status"' in src
    assert 'CommandHandler("stake"' in src
    # Telegram menu registration
    assert "set_my_commands" in src


# ---------------------------------------------------------------------------
# Authorization guard
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_chat_is_ignored():
    import telegram_service as ts
    with patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        update = _fake_update(chat_id=999999)  # not the authorized chat
        await ts._cmd_status(update, _fake_context())
        send.assert_not_called()


# ---------------------------------------------------------------------------
# /pause and /resume delegate to auto_scan_service
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cmd_pause_stops_auto_scan_and_confirms():
    import telegram_service as ts
    fake_service = MagicMock()
    fake_service.stop = AsyncMock(return_value={"success": True})
    with patch.dict("sys.modules", {"auto_scan_service": MagicMock(auto_scan_service=fake_service)}), \
         patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_pause(_fake_update(chat_id=6434316177), _fake_context())
    fake_service.stop.assert_awaited_once()
    assert send.await_count == 1
    assert "paused" in send.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_cmd_resume_starts_auto_scan_and_confirms():
    import telegram_service as ts
    fake_service = MagicMock()
    fake_service.start = AsyncMock(return_value={"success": True})
    with patch.dict("sys.modules", {"auto_scan_service": MagicMock(auto_scan_service=fake_service)}), \
         patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_resume(_fake_update(chat_id=6434316177), _fake_context())
    fake_service.start.assert_awaited_once()
    assert "resumed" in send.await_args.args[0].lower()


# ---------------------------------------------------------------------------
# /stake validates and writes to db
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cmd_stake_updates_fallback_amount():
    import telegram_service as ts
    fake_db = MagicMock()
    fake_db.tampermonkey_settings.update_one = AsyncMock(return_value=None)
    fake_cache = MagicMock()
    fake_cache.invalidate = MagicMock()
    with patch.dict("sys.modules", {
            "routes": MagicMock(db=fake_db),
            "perf_cache": MagicMock(active_target_cache=fake_cache),
         }), \
         patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_stake(_fake_update(chat_id=6434316177), _fake_context(args=["2.5"]))
    fake_db.tampermonkey_settings.update_one.assert_awaited_once()
    call_args = fake_db.tampermonkey_settings.update_one.await_args
    assert call_args.args[0] == {"_id": "default"}
    assert call_args.args[1]["$set"]["stake_tiers_fallback"] == 2.5
    assert call_args.kwargs.get("upsert") is True
    assert "2.50" in send.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_stake_rejects_bad_input():
    import telegram_service as ts
    with patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_stake(_fake_update(chat_id=6434316177), _fake_context(args=["not_a_number"]))
    assert "/stake failed" in send.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_stake_rejects_out_of_range():
    import telegram_service as ts
    with patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_stake(_fake_update(chat_id=6434316177), _fake_context(args=["99999"]))
    assert "/stake failed" in send.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_stake_no_args_shows_usage():
    import telegram_service as ts
    with patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_stake(_fake_update(chat_id=6434316177), _fake_context(args=[]))
    assert "Usage" in send.await_args.args[0]


# ---------------------------------------------------------------------------
# /status renders running state + stake + target
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cmd_status_renders_running_state():
    import telegram_service as ts
    fake_service = MagicMock()
    fake_service.status = MagicMock(return_value={
        "running": True,
        "config": {"interval_seconds": 5, "assets": ["EURUSD_OTC", "GBPUSD_OTC"]},
        "stats": {"total_scans": 42, "total_routed": 7, "error_count": 0},
        "last_winner": {"asset": "EURUSD_OTC", "direction": "CALL", "confidence": 0.87},
    })
    fake_db = MagicMock()
    fake_db.tampermonkey_settings.find_one = AsyncMock(return_value={
        "stake_tiers_fallback": 2.5,
        "active_target": {"asset": "EURUSD_OTC", "direction": "CALL",
                          "expiry_seconds": 60, "confidence": 0.87},
    })
    with patch.dict("sys.modules", {
            "auto_scan_service": MagicMock(auto_scan_service=fake_service),
            "routes": MagicMock(db=fake_db),
         }), \
         patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_status(_fake_update(chat_id=6434316177), _fake_context())
    body = send.await_args.args[0]
    assert "RUNNING" in body
    assert "$2.50" in body
    assert "EURUSD_OTC" in body
    assert "42" in body  # total_scans


# ---------------------------------------------------------------------------
# /help exposes command list
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cmd_help_lists_all_commands():
    import telegram_service as ts
    with patch.object(ts, "TELEGRAM_CHAT_ID", 6434316177), \
         patch.object(ts, "send_message", new=AsyncMock()) as send:
        await ts._cmd_help(_fake_update(chat_id=6434316177), _fake_context())
    body = send.await_args.args[0]
    for cmd in ("/status", "/pause", "/resume", "/stake"):
        assert cmd in body
