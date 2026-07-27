"""
Iter 79 regression guard: /signal Telegram command must never surface
"conditions not met" to the user when a high-priority signal generation
was requested. It should route through the v2 pipeline which is
documented to always return a directional signal.
"""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, "/app/backend")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "trading_bot_db")


def test_integrations_signal_callback_uses_v2_pipeline():
    """The callback source must invoke `force_generate_signal_v2`, not the
    older `force_signal_generator.force_generate_signal` which could
    silently fall through to the 'conditions not met' branch."""
    with open("/app/backend/routes/integrations.py", "r", encoding="utf-8") as fh:
        src = fh.read()
    assert "from routes.signals import force_generate_signal_v2" in src, (
        "signal_callback must import force_generate_signal_v2"
    )
    assert "await force_generate_signal_v2(" in src, (
        "signal_callback must call force_generate_signal_v2"
    )
    # Verify the buggy branch that emitted "conditions not met" via
    # telegram_bot.send_message was removed from the callback.
    assert 'send_message("⚠️ No signal generated - conditions not met' not in src, (
        "Legacy 'conditions not met' Telegram surface must be removed"
    )


def test_v2_pipeline_returns_signal_payload():
    """v2 must return a non-empty signal payload for a known asset."""
    from routes.signals import force_generate_signal_v2

    resp = asyncio.run(force_generate_signal_v2(
        asset="EURUSD_OTC",
        expiry_seconds=60,
        preferred_direction=None,
        min_conf_confluence=0.0,
        min_conf_improved_v2=0.0,
        min_conf_maximized_v3=0.0,
        min_conf_iq720=0.0,
    ))
    assert resp.get("success") is True
    signal = resp.get("signal")
    assert signal, "v2 must always return a signal object"
    assert signal.get("direction") in ("CALL", "PUT", "BUY", "SELL"), (
        f"Unexpected direction: {signal.get('direction')}"
    )
    assert signal.get("confidence") is not None
