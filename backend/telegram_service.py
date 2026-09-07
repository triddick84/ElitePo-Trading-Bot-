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
    CommandHandler,
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


# ---------------------------------------------------------------------------
# Iter 127 — Command menu: /pause /resume /status /stake  (pilot from phone)
# ---------------------------------------------------------------------------
def _authorized(update: Update) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    if TELEGRAM_CHAT_ID and chat.id != TELEGRAM_CHAT_ID:
        logger.warning(f"[telegram] ignore unauthorized chat_id={chat.id}")
        return False
    return True


async def _cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    try:
        from auto_scan_service import auto_scan_service
        await auto_scan_service.stop()
        await send_message("⏸ <b>Auto-scan paused</b>\nUse /resume to start again.")
    except Exception as e:
        logger.warning(f"[telegram] /pause failed: {e}")
        await send_message(f"❌ /pause failed: <code>{html.escape(str(e))}</code>")


async def _cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    try:
        from auto_scan_service import auto_scan_service
        await auto_scan_service.start()
        await send_message("▶️ <b>Auto-scan resumed</b>\nScanning across configured assets.")
    except Exception as e:
        logger.warning(f"[telegram] /resume failed: {e}")
        await send_message(f"❌ /resume failed: <code>{html.escape(str(e))}</code>")


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    try:
        from auto_scan_service import auto_scan_service
        from routes import db
        st = auto_scan_service.status()
        cfg = st.get("config") or {}
        stats = st.get("stats") or {}
        winner = st.get("last_winner") or {}
        settings = await db.tampermonkey_settings.find_one({"_id": "default"}) or {}
        stake = settings.get("stake_tiers_fallback", 1.0)
        target = settings.get("active_target") or {}
        running = "🟢 RUNNING" if st.get("running") else "🔴 PAUSED"
        assets = cfg.get("assets") or []
        text = (
            f"<b>Elite PO Trader — Status</b>\n"
            f"State: {running}\n"
            f"Interval: {cfg.get('interval_seconds', '?')}s\n"
            f"Assets: {len(assets)}"
            f"{' · ' + ', '.join(assets[:4]) + ('…' if len(assets) > 4 else '') if assets else ''}\n"
            f"Fallback stake: <b>${float(stake):.2f}</b>\n"
            f"Scans: {stats.get('total_scans', 0)} · Routed: {stats.get('total_routed', 0)} · Err: {stats.get('error_count', 0)}\n"
        )
        if target:
            text += (
                f"\n<b>Active target</b>\n"
                f"{html.escape(str(target.get('asset', '?')))} "
                f"<b>{html.escape(str(target.get('direction', '?')))}</b> "
                f"@ {target.get('expiry_seconds', '?')}s "
                f"(conf {float(target.get('confidence', 0)) * 100:.0f}%)"
            )
        if winner:
            text += (
                f"\n<b>Last winner</b>\n"
                f"{html.escape(str(winner.get('asset', '?')))} "
                f"{html.escape(str(winner.get('direction', '?')))} "
                f"({float(winner.get('confidence', 0)) * 100:.0f}%)"
            )
        await send_message(text)
    except Exception as e:
        logger.warning(f"[telegram] /status failed: {e}")
        await send_message(f"❌ /status failed: <code>{html.escape(str(e))}</code>")


async def _cmd_stake(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    args = context.args or []
    if not args:
        await send_message(
            "Usage: <code>/stake &lt;amount&gt;</code>\n"
            "Example: <code>/stake 2.5</code> sets fallback stake to $2.50."
        )
        return
    try:
        amount = float(args[0])
        if not 0.1 <= amount <= 10000:
            raise ValueError("amount out of range 0.1..10000")
        from routes import db
        from perf_cache import active_target_cache
        now = datetime.now(timezone.utc).isoformat()
        await db.tampermonkey_settings.update_one(
            {"_id": "default"},
            {"$set": {"stake_tiers_fallback": amount, "last_updated": now}},
            upsert=True,
        )
        try:
            active_target_cache.invalidate("default")
        except Exception:
            pass
        await send_message(f"💰 <b>Stake updated</b>\nFallback stake set to <b>${amount:.2f}</b>.")
    except Exception as e:
        await send_message(f"❌ /stake failed: <code>{html.escape(str(e))}</code>")


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await send_message(
        "<b>Elite PO Trader — commands</b>\n"
        "/status — running state, active target, stake\n"
        "/pause — pause auto-scan\n"
        "/resume — resume auto-scan\n"
        "/stake &lt;amt&gt; — set fallback stake (e.g. <code>/stake 2.5</code>)\n\n"
        "Or send a free-text signal like <code>EURUSD_OTC CALL 60s</code>."
    )


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
    # Iter 127 — command menu (must be registered BEFORE the free-text handler
    # so /commands are not misparsed as trading signals).
    app.add_handler(CommandHandler(["start", "help"], _cmd_help))
    app.add_handler(CommandHandler("pause", _cmd_pause))
    app.add_handler(CommandHandler("resume", _cmd_resume))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("stake", _cmd_stake))
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
    # Iter 127 — expose the command menu inside Telegram's UI (the "/" button).
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([
            BotCommand("status", "Show bot state, active target, stake"),
            BotCommand("pause", "Pause the auto-scan loop"),
            BotCommand("resume", "Resume the auto-scan loop"),
            BotCommand("stake", "Set fallback stake amount (e.g. /stake 2.5)"),
            BotCommand("help", "Show all commands"),
        ])
    except Exception as e:
        logger.warning(f"[telegram] set_my_commands failed: {e}")
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
