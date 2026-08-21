"""
Auto-Scan & Route REST endpoints — Iter 112.

Exposes the AutoScanService singleton behind clean HTTP endpoints.
The frontend Dashboard drives all of this via the `Auto-Scan & Route` panel.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from auto_scan_service import auto_scan_service

logger = logging.getLogger(__name__)
router = APIRouter()


class StrategyBlock(BaseModel):
    sma_fast: Optional[int] = None
    sma_slow: Optional[int] = None
    supertrend_atr_period: Optional[int] = None
    supertrend_multiplier: Optional[float] = None
    ao_short_period: Optional[int] = None
    ao_long_period: Optional[int] = None


class AutoScanConfigPayload(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(None, ge=3, le=600)
    chart_timeframe: Optional[str] = None
    trade_duration_seconds: Optional[int] = Field(None, ge=5, le=3600)
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_elite_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    prefer_elite_on_tie: Optional[bool] = None
    assets: Optional[List[str]] = None
    strategy: Optional[StrategyBlock] = None
    force_signal: Optional[bool] = None
    target_ttl_seconds: Optional[int] = Field(None, ge=10, le=600)


class ScanOncePayload(BaseModel):
    assets: Optional[List[str]] = None
    config: Optional[AutoScanConfigPayload] = None


@router.get("/signals/auto-scan/status")
async def auto_scan_status() -> Dict[str, Any]:
    return {"success": True, **auto_scan_service.status()}


@router.get("/signals/auto-scan/config")
async def auto_scan_get_config() -> Dict[str, Any]:
    return {"success": True, "config": auto_scan_service.get_config()}


@router.post("/signals/auto-scan/config")
async def auto_scan_set_config(payload: AutoScanConfigPayload = Body(...)
                               ) -> Dict[str, Any]:
    cfg = payload.dict(exclude_none=True)
    if "strategy" in cfg and isinstance(cfg["strategy"], dict):
        cfg["strategy"] = {k: v for k, v in cfg["strategy"].items() if v is not None}
    updated = await auto_scan_service.set_config(cfg)
    return {"success": True, "config": updated}


@router.post("/signals/auto-scan/start")
async def auto_scan_start(payload: Optional[AutoScanConfigPayload] = Body(None)
                          ) -> Dict[str, Any]:
    cfg = payload.dict(exclude_none=True) if payload else None
    if cfg and "strategy" in cfg and isinstance(cfg["strategy"], dict):
        cfg["strategy"] = {k: v for k, v in cfg["strategy"].items() if v is not None}
    return await auto_scan_service.start(cfg)


@router.post("/signals/auto-scan/stop")
async def auto_scan_stop() -> Dict[str, Any]:
    return await auto_scan_service.stop()


@router.post("/signals/auto-scan/scan-now")
async def auto_scan_run_once(payload: Optional[ScanOncePayload] = Body(None)
                             ) -> Dict[str, Any]:
    """One-shot scan. Uses the currently persisted config unless overridden."""
    assets = payload.assets if payload else None
    cfg = None
    if payload and payload.config:
        cfg = payload.config.dict(exclude_none=True)
        if "strategy" in cfg and isinstance(cfg["strategy"], dict):
            cfg["strategy"] = {k: v for k, v in cfg["strategy"].items() if v is not None}
    return await auto_scan_service.scan_once(assets=assets, cfg_override=cfg)
