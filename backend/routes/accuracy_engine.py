"""
AccuracyEngine REST endpoints.

- GET  /api/accuracy-engine/status         → cache summary, config, gated list.
- GET  /api/accuracy-engine/stats          → all cached (asset, strategy) entries.
- GET  /api/accuracy-engine/stats/one      → single (asset, strategy) lookup.
- POST /api/accuracy-engine/refresh        → force cache rebuild.
- GET  /api/accuracy-engine/config         → current config.
- POST /api/accuracy-engine/config         → update config (persists to Mongo).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Query

from accuracy_engine import accuracy_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/accuracy-engine/status")
async def status() -> Dict[str, Any]:
    await accuracy_engine.refresh()
    return {"success": True, **accuracy_engine.status()}


@router.get("/accuracy-engine/stats")
async def all_stats(limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    await accuracy_engine.refresh()
    entries = accuracy_engine.all_entries()
    # newest-updated first, then most-traded first
    entries.sort(key=lambda e: (-(e.get("last_updated") or 0), -e.get("n_trades", 0)))
    return {"success": True, "count": len(entries), "entries": entries[:limit]}


@router.get("/accuracy-engine/stats/one")
async def one_stat(asset: str, strategy: str) -> Dict[str, Any]:
    return {"success": True, "stat": await accuracy_engine.get_stats(asset, strategy)}


@router.post("/accuracy-engine/refresh")
async def refresh() -> Dict[str, Any]:
    result = await accuracy_engine.refresh(force=True)
    return {"success": True, **result}


@router.get("/accuracy-engine/config")
async def get_config() -> Dict[str, Any]:
    return {"success": True, "config": accuracy_engine.get_config()}


@router.post("/accuracy-engine/config")
async def set_config(patch: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    updated = await accuracy_engine.save_config(patch)
    # Invalidate so gating with the new thresholds takes effect on next call
    await accuracy_engine.invalidate()
    return {"success": True, "config": updated}


@router.get("/accuracy-engine/should-gate")
async def should_gate(asset: str, strategy: str) -> Dict[str, Any]:
    """Diagnostic — see exactly what /signals/latest would decide."""
    decision = await accuracy_engine.should_gate(asset, strategy)
    return {"success": True, "decision": decision}
