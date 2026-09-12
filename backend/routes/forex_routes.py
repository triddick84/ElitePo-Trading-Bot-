"""Iter 142 — Forex REST endpoints.

Prefix: /api/forex/*
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from forex.engine import get_engine
from forex.models import (
    ExecutionSurface, ExitConfig, ExitMode, ForexEngineConfig, ForexSignal,
    OrderSide, SizingConfig, SizingMode,
)

router = APIRouter(prefix="/forex", tags=["forex"])


# ----- schemas -----
class SignalIn(BaseModel):
    symbol: str
    side: OrderSide
    entry: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    confluence_score: Optional[float] = None
    sources: List[str] = Field(default_factory=list)
    timeframe: str = "1m"
    atr: Optional[float] = None
    equity_usd: float = 10_000.0
    surface: Optional[ExecutionSurface] = None
    exit_cfg: Optional[ExitConfig] = None
    sizing: Optional[SizingConfig] = None


class TickIn(BaseModel):
    symbol: str
    price: float


class CloseIn(BaseModel):
    price: float
    reason: str = "manual"


# ----- endpoints -----
@router.get("/config")
async def get_config() -> Dict[str, Any]:
    eng = get_engine()
    await eng.load_config()
    return eng.config().model_dump(mode="json")


@router.post("/config")
async def set_config(cfg: ForexEngineConfig) -> Dict[str, Any]:
    eng = get_engine()
    saved = await eng.save_config(cfg)
    return saved.model_dump(mode="json")


@router.post("/signal")
async def submit_signal(sig: SignalIn) -> Dict[str, Any]:
    eng = get_engine()
    signal = ForexSignal(
        signal_id=str(uuid.uuid4()),
        symbol=sig.symbol,
        side=sig.side,
        entry=sig.entry,
        stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        confidence=sig.confidence,
        confluence_score=sig.confluence_score,
        sources=sig.sources,
        timeframe=sig.timeframe,
        atr=sig.atr,
    )
    return await eng.on_signal(
        signal,
        equity_usd=sig.equity_usd,
        surface=sig.surface,
        exit_cfg=sig.exit_cfg,
        sizing=sig.sizing,
    )


@router.post("/tick")
async def tick(t: TickIn) -> Dict[str, Any]:
    eng = get_engine()
    actions = await eng.tick(t.symbol, t.price)
    return {"symbol": t.symbol, "price": t.price, "actions": actions}


@router.get("/positions/open")
async def list_open(symbol: Optional[str] = Query(None)) -> Dict[str, Any]:
    eng = get_engine()
    pos = await eng.list_open(symbol=symbol)
    return {"count": len(pos), "positions": [p.model_dump(mode="json") for p in pos]}


@router.get("/positions/closed")
async def list_closed(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    eng = get_engine()
    pos = await eng.list_closed(limit=limit)
    return {"count": len(pos), "positions": [p.model_dump(mode="json") for p in pos]}


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str, req: CloseIn) -> Dict[str, Any]:
    eng = get_engine()
    p = await eng.close_position(position_id, price=req.price, reason=req.reason)
    if p is None:
        raise HTTPException(status_code=404, detail="position not found or already closed")
    return p.model_dump(mode="json")


@router.get("/health")
async def health() -> Dict[str, Any]:
    from forex.mt5_bridge import get_bridge
    bridge = get_bridge()
    eng = get_engine()
    return {
        "ok": True,
        "mt5_available": bridge.available,
        "config": eng.config().model_dump(mode="json"),
        "surface": eng.config().execution_surface.value,
    }
