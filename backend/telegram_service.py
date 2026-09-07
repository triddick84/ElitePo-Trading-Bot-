"""
Iter 126 — Telegram integration (bidirectional).

SEND: post notifications to TELEGRAM_CHAT_ID (auto-scan winners, alerts)
RECEIVE: bot listens to the same chat for signal messages, parses them,
         and routes them into the app's active_target queue so the TM
         script executes them on Pocket Option.

Signal format (case-insensitive, flexible):
    EURUSD_OTC CALL 60s
    GBPUSD PUT 5m
    signal: XAUUSD CALL expiry=120
"""

from __future__ import annotations

import html
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0") or "0")

telegram_app: Optional[Application] = None


@dataclass(frozen=True)
class TradingSignal:
    asset: str
    direction: str
    expiry_seconds: int
    raw_text: str


SIGNAL_RE = re.compile(
    r"(?P<asset>[A-Za-z0-9][A-Za-z0-9/_-]{1,19})"
    r"\s+(?P<direction>CALL|PUT|UP|DOWN|BUY|SELL)\b"
    r"(?:\s+|.*?)(?:expiry\s*[=:]?\s*)?"
    r"(?P<expiry>\d+)\s*(?P<unit>s|sec|secs|seconds|m|min|mins|minutes)?\b",
    re.IGNORECASE,
)

_DIR_MAP = {"CALL": "CALL", "UP": "CALL", "BUY": "CALL",
            "PUT": "PUT", "DOWN": "PUT", "SELL": "PUT"}


def parse_signal(text: str) -> Optional[TradingSignal]:
    if not text:
        return None
    m = SIGNAL_RE.search(text)
    if not m:
        return None
    unit = (m.group("unit") or "s").lower()
    mult = 60 if unit.startswith("m") else 1
    expiry = int(m.group("expiry")) * mult
    if not 5 <= expiry <= 3600:
        return None
    direction = _DIR_MAP.get(m.group("direction").upper())
    if not direction:
        return None
    asset = m.group("asset").upper()
    # Normalize suffix: EURUSDOTC → EURUSD_OTC
    if asset.endswith("OTC") and not asset.endswith("_OTC"):
        asset = asset[:-3] + "_OTC"
    return TradingSignal(asset=asset, direction=direction,
                         expiry_seconds=expiry, raw_text=text[:200])


async def _route_to_active_target(sig: TradingSignal) -> bool:
    """Push a parsed signal into tampermonkey_settings.active_target so TM fires it."""
    try:
        from routes import db
        from perf_cache import active_target_cache
        expires = (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat()
        target = {
            "asset": sig.asset,
            "timeframe": "1m",
            "direction": sig.direction,
            "confidence": 0.75,
            "expiry_seconds": sig.expiry_seconds,
            "source": "telegram",
            "expires_at": expires,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tampermonkey_settings.update_one(
            {"_id": "default"},
            {"$set": {"active_target": target,
                      "last_updated": target["set_at"]}},
            upsert=True,
        )
        try:
            active_target_cache.invalidate("default")
        except Exception:
            pass
        # Log for audit trail
        await db.telegram_signals_received.insert_one({
            "asset": sig.asset, "direction": sig.direction,
            "expiry_seconds": sig.expiry_seconds,
            "raw_text": sig.raw_text,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except Exception as e:
        logger.warning(f"[telegram] route_to_active_target failed: {e}")
        return False


async def _msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    if TELEGRAM_CHAT_ID and chat.id != TELEGRAM_CHAT_ID:
        logger.warning(f"[telegram] ignore unauthorized chat_id={chat.id}")
        return
    text = msg.text or msg.caption or ""
    sig = parse_signal(text)
    if not sig:
        logger.info(f"[telegram] unrecognized: {text[:120]}")
        return
    ok = await _route_to_active_target(sig)
    if ok:
        await send_message(
            f"✅ <b>Signal routed</b>\n"
            f"Asset: <code>{html.escape(sig.asset)}</code>\n"
            f"Direction: <b>{sig.direction}</b>\n"
            f"Expiry: {sig.expiry_seconds}s"
        )


async def _err_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("[telegram] handler error", exc_info=context.error)


async def send_message(text: str, chat_id: Optional[int] = None):
    """SEND: post HTML-formatted message. Safe no-op if telegram not configured."""
    if telegram_app is None or not TELEGRAM_BOT_TOKEN:
        return None
    try:
        return await telegram_app.bot.send_message(
            chat_id=chat_id or TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"[telegram] send failed: {e}")
        return None


async def start_telegram_bot() -> None:
    """Called from FastAPI @app.on_event('startup')."""
    global telegram_app
    if not TELEGRAM_BOT_TOKEN:
        logger.info("[telegram] TELEGRAM_BOT_TOKEN not set — bot disabled")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
        _msg_handler,
    ))
    app.add_error_handler(_err_handler)
    await app.initialize()
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await app.start()
    await app.updater.start_polling(
        poll_interval=0.5,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=["message", "channel_post"],
    )
    telegram_app = app
    logger.info(f"[telegram] ✅ bot polling started · chat_id={TELEGRAM_CHAT_ID}")


async def stop_telegram_bot() -> None:
    global telegram_app
    if telegram_app is None:
        return
    try:
        if telegram_app.updater and telegram_app.updater.running:
            await telegram_app.updater.stop()
        if telegram_app.running:
            await telegram_app.stop()
        await telegram_app.shutdown()
    except Exception as e:
        logger.warning(f"[telegram] shutdown failed: {e}")
    telegram_app = None
