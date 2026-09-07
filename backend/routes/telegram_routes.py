"""Iter 126 — Telegram REST endpoints (send test + received-signals log)."""

from __future__ import annotations

import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field

from routes import db
from telegram_service import send_message, telegram_app, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)
router = APIRouter()


class TelegramSendPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    chat_id: int | None = None


@router.get("/telegram/status")
async def telegram_status():
    return {
        "success": True,
        "configured": telegram_app is not None,
        "chat_id": TELEGRAM_CHAT_ID,
    }


@router.post("/telegram/send")
async def telegram_send(payload: TelegramSendPayload):
    """Manual send-test endpoint. Also usable by other backend features to
    notify the user of auto-scan winners, elite screener hits, etc."""
    res = await send_message(payload.text, chat_id=payload.chat_id)
    return {"success": res is not None, "sent": res is not None}


@router.get("/telegram/received-signals")
async def telegram_received(limit: int = 50):
    limit = max(1, min(200, int(limit)))
    try:
        cursor = db.telegram_signals_received.find(
            {}, {"_id": 0}
        ).sort("logged_at", -1).limit(limit)
        rows = await cursor.to_list(length=limit)
    except Exception as e:
        return {"success": False, "error": str(e), "signals": []}
    return {"success": True, "count": len(rows), "signals": rows}
