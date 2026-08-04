"""
Microstructure REST endpoints — Iter 86.

Exposes VPIN + Kyle's λ + order-flow-imbalance stats and gating decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from microstructure import microstructure

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/microstructure/status")
async def status() -> Dict[str, Any]:
    await microstructure.refresh()
    return {"success": True, **microstructure.status()}


@router.get("/microstructure/stats")
async def all_stats(limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    await microstructure.refresh()
    entries = microstructure.all_entries()
    entries.sort(key=lambda e: -e.get("vpin", 0.0))
    return {"success": True, "count": len(entries), "entries": entries[:limit]}


@router.get("/microstructure/stats/one")
async def one_stat(asset: str) -> Dict[str, Any]:
    return {"success": True, "stat": await microstructure.get_stats_full(asset)}


@router.get("/microstructure/should-gate")
async def should_gate(asset: str) -> Dict[str, Any]:
    decision = await microstructure.should_gate(asset)
    return {"success": True, "decision": decision}


@router.get("/microstructure/multiplier")
async def multiplier(asset: str) -> Dict[str, Any]:
    """Confidence multiplier this asset would currently apply to the ensemble."""
    await microstructure.refresh()
    return {"success": True, "asset": asset,
            "multiplier": microstructure.confidence_multiplier(asset)}


@router.get("/microstructure/config")
async def get_config() -> Dict[str, Any]:
    return {"success": True, "config": microstructure.get_config()}


@router.post("/microstructure/config")
async def set_config(patch: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    updated = await microstructure.save_config(patch)
    await microstructure.invalidate()
    return {"success": True, "config": updated}


@router.post("/microstructure/refresh")
async def refresh() -> Dict[str, Any]:
    result = await microstructure.refresh(force=True)
    return {"success": True, **result}
