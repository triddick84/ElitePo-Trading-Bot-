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


# ---------------------------------------------------------------------------
# Iter 143 — Signal Auto-Bridge
# ---------------------------------------------------------------------------

class BridgeRequest(BaseModel):
    symbol: str
    timeframe: str = "1m"
    limit: int = Field(default=200, ge=30, le=2000)
    equity_usd: float = 10_000.0
    surface: Optional[ExecutionSurface] = None
    emit: bool = True


class BridgeLoopConfig(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    interval_s: int = Field(default=30, ge=5, le=600)
    timeframe: str = "1m"


@router.post("/bridge/once")
async def bridge_once(req: BridgeRequest) -> Dict[str, Any]:
    """Run the auto-bridge for a single symbol synchronously and return
    the decision + (if emitted) the resulting position."""
    from forex.signal_bridge import bridge_symbol
    return await bridge_symbol(
        req.symbol,
        timeframe=req.timeframe,
        limit=req.limit,
        equity_usd=req.equity_usd,
        surface=req.surface,
        emit=req.emit,
    )


@router.post("/bridge/loop/configure")
async def bridge_loop_configure(cfg: BridgeLoopConfig) -> Dict[str, Any]:
    from forex.signal_bridge import get_bridge_loop
    loop = get_bridge_loop()
    loop.configure(symbols=cfg.symbols, interval_s=cfg.interval_s, timeframe=cfg.timeframe)
    return {"symbols": loop.symbols, "interval_s": loop.interval_s, "timeframe": loop.timeframe, "running": loop.is_running()}


@router.post("/bridge/loop/start")
async def bridge_loop_start() -> Dict[str, Any]:
    from forex.signal_bridge import get_bridge_loop
    loop = get_bridge_loop()
    await loop.start()
    return {"running": loop.is_running(), "symbols": loop.symbols, "interval_s": loop.interval_s}


@router.post("/bridge/loop/stop")
async def bridge_loop_stop() -> Dict[str, Any]:
    from forex.signal_bridge import get_bridge_loop
    loop = get_bridge_loop()
    await loop.stop()
    return {"running": loop.is_running()}


@router.get("/bridge/status")
async def bridge_status() -> Dict[str, Any]:
    from forex.signal_bridge import get_bridge_loop
    loop = get_bridge_loop()
    return {
        "running": loop.is_running(),
        "symbols": loop.symbols,
        "interval_s": loop.interval_s,
        "timeframe": loop.timeframe,
    }


# ---------------------------------------------------------------------------
# Iter 145 — TM-side order queue (Tampermonkey executes MT5 orders in the PO UI)
# ---------------------------------------------------------------------------

class TMOrderResult(BaseModel):
    fill_price: Optional[float] = None
    fill_lots: Optional[float] = None
    error: Optional[str] = None
    dom_matches: Optional[Dict[str, Any]] = None    # what TM saw when it clicked


@router.get("/orders/pending")
async def list_pending_orders(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    """Orders the Python engine queued for the Tampermonkey userscript to
    execute inside PO's web-MT5 UI. TM should long-poll this endpoint.

    Returns oldest-first so races don't skip stale orders. Each entry includes
    both the raw ForexOrder fields and its `position_id`.
    """
    eng = get_engine()
    if eng.db is None:
        return {"count": 0, "orders": []}
    cursor = eng.db.forex_orders_pending.find({"status": {"$ne": "picked"}}).sort("queued_at", 1)
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d.pop("_id", None)
    return {"count": len(docs), "orders": docs}


@router.post("/orders/{position_id}/mark-picked")
async def mark_order_picked(position_id: str) -> Dict[str, Any]:
    """TM claims an order so no second TM instance also fires it."""
    eng = get_engine()
    if eng.db is None:
        raise HTTPException(500, "db unavailable")
    r = await eng.db.forex_orders_pending.update_one(
        {"position_id": position_id, "status": {"$ne": "picked"}},
        {"$set": {"status": "picked"}},
    )
    return {"position_id": position_id, "claimed": r.modified_count == 1}


@router.post("/orders/{position_id}/mark-filled")
async def mark_order_filled(position_id: str, result: TMOrderResult) -> Dict[str, Any]:
    """TM reports the DOM click succeeded and the trade is now live in
    PO's web-MT5. We update the tentative PENDING position → OPEN with
    the actual fill price if reported."""
    eng = get_engine()
    if eng.db is None:
        raise HTTPException(500, "db unavailable")
    upd = {"status": "OPEN"}
    if result.fill_price is not None:
        upd["entry"] = float(result.fill_price)
    if result.fill_lots is not None:
        upd["lots"] = float(result.fill_lots)
    if result.dom_matches is not None:
        upd["meta.dom_matches"] = result.dom_matches
    r = await eng.db.forex_positions.update_one(
        {"position_id": position_id},
        {"$set": upd},
    )
    # Clear pending queue entry
    await eng.db.forex_orders_pending.delete_one({"position_id": position_id})
    return {"position_id": position_id, "updated": r.modified_count == 1}


@router.post("/orders/{position_id}/mark-rejected")
async def mark_order_rejected(position_id: str, result: TMOrderResult) -> Dict[str, Any]:
    """TM couldn't place the trade (buttons missing, iframe not loaded,
    lot input rejected, etc). Position → REJECTED, pending queue cleared."""
    eng = get_engine()
    if eng.db is None:
        raise HTTPException(500, "db unavailable")
    upd = {
        "status": "REJECTED",
        "close_reason": (result.error or "tm_rejected")[:200],
    }
    if result.dom_matches is not None:
        upd["meta.dom_matches"] = result.dom_matches
    r = await eng.db.forex_positions.update_one(
        {"position_id": position_id},
        {"$set": upd},
    )
    await eng.db.forex_orders_pending.delete_one({"position_id": position_id})
    return {"position_id": position_id, "updated": r.modified_count == 1}


@router.get("/orders/queue-stats")
async def order_queue_stats() -> Dict[str, Any]:
    """Handy diag: how many pending, how many picked-not-yet-filled."""
    eng = get_engine()
    if eng.db is None:
        return {"pending": 0, "picked": 0}
    pending = await eng.db.forex_orders_pending.count_documents({"status": {"$ne": "picked"}})
    picked = await eng.db.forex_orders_pending.count_documents({"status": "picked"})
    return {"pending": pending, "picked": picked}
