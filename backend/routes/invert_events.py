"""
Iter 122 — Auto-Invert Event Log (Bug 2 diagnostic).

The Tampermonkey script triggers auto-invert locally when `state.stats.currentStreak`
crosses the threshold. When users report "it says it's working but doesn't switch",
we have no server-side audit trail to verify. This route lets the TM script POST
every inversion state change (activate + deactivate + evaluation-blocked reason)
so we can prove what really happened.

Also exposes a GET so the Mobile Auto-Trader page can render a
"last 10 auto-invert events" panel for the user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from routes import db

router = APIRouter()


class InvertEvent(BaseModel):
    event: str = Field(..., description="'ACTIVATED' | 'DEACTIVATED' | 'BLOCKED' | 'EVALUATED'")
    reason: Optional[str] = ""
    is_inverted: bool = False
    auto_invert_enabled: bool = True
    config_enabled: bool = True
    manual_override: bool = False
    current_streak: int = 0
    loss_streak: int = 0
    threshold: int = 2
    inverted_trade_count: int = 0
    inverted_wins: int = 0
    inverted_losses: int = 0
    asset: Optional[str] = None
    tm_version: Optional[str] = None
    blockers: Optional[List[str]] = None


@router.post("/tampermonkey/invert-events/log")
async def log_invert_event(payload: InvertEvent):
    doc = payload.model_dump()
    doc["logged_at"] = datetime.now(timezone.utc).isoformat()
    try:
        await db.tm_invert_events.insert_one(doc)
    except Exception:
        # Never fail the TM script over a logging hiccup
        return {"success": False, "logged": False}
    return {"success": True, "logged": True}


@router.get("/tampermonkey/invert-events/recent")
async def get_recent_invert_events(limit: int = 50):
    limit = max(1, min(200, int(limit)))
    try:
        cursor = db.tm_invert_events.find({}, {"_id": 0}).sort("logged_at", -1).limit(limit)
        rows = await cursor.to_list(length=limit)
    except Exception as e:
        return {"success": False, "error": str(e), "events": []}
    return {"success": True, "count": len(rows), "events": rows}


@router.get("/tampermonkey/invert-events/summary")
async def get_invert_events_summary():
    """Quick counts for a health-check card in the dashboard."""
    try:
        pipeline: List[Dict[str, Any]] = [
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        cursor = db.tm_invert_events.aggregate(pipeline)
        groups = await cursor.to_list(length=20)
        latest = await db.tm_invert_events.find(
            {}, {"_id": 0}
        ).sort("logged_at", -1).limit(1).to_list(length=1)
        return {
            "success": True,
            "total": sum(g["count"] for g in groups),
            "by_event": {g["_id"]: g["count"] for g in groups if g.get("_id")},
            "latest": latest[0] if latest else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
