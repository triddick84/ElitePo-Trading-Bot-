"""
Signal Pre-generation Buffer REST — Iter 89.

Read-only introspection so the Latency Dashboard can show hit/miss counts.
"""

from __future__ import annotations

from fastapi import APIRouter

from signal_prewarm_service import get_buffer

router = APIRouter()


@router.get("/signal-prewarm/stats")
async def stats():
    return {"success": True, **get_buffer().stats()}
