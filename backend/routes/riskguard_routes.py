"""Iter 131 — RiskGuard REST endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from risk_guard_service import (
    risk_guard_service,
    calculate_next_trade,
)

router = APIRouter()


# ---- schemas ----
class CalcRequest(BaseModel):
    capital: float = Field(..., gt=0)
    payout_pct: float = Field(..., gt=0, le=5.0, description="Payout as decimal, e.g. 0.85 for 85%")
    target_profit: float = Field(..., ge=0)
    stop_loss: float = Field(..., ge=0, description="Absolute $ stop-loss")
    max_trades: int = Field(..., gt=0, le=200)
    trades_taken: int = Field(0, ge=0)
    current_pnl: float = Field(0.0)


class StartSessionRequest(BaseModel):
    user_id: str = "default"
    capital: float = Field(..., gt=0)
    payout_pct: float = Field(..., gt=0, le=5.0)
    target_profit: float = Field(..., ge=0)
    stop_loss: float = Field(..., ge=0)
    max_trades: int = Field(..., gt=0, le=200)


class RecordTradeRequest(BaseModel):
    user_id: str = "default"
    outcome: str = Field(..., description="win | loss | draw")
    amount: float = Field(..., gt=0)
    note: Optional[str] = None


class CloseSessionRequest(BaseModel):
    user_id: str = "default"


# ---- endpoints ----
@router.post("/riskguard/calculate")
async def riskguard_calculate(payload: CalcRequest):
    result = calculate_next_trade(
        capital=payload.capital,
        payout_pct=payload.payout_pct,
        target_profit=payload.target_profit,
        stop_loss=payload.stop_loss,
        max_trades=payload.max_trades,
        trades_taken=payload.trades_taken,
        current_pnl=payload.current_pnl,
    )
    return {"success": True, **result}


@router.post("/riskguard/session/start")
async def riskguard_start(payload: StartSessionRequest):
    session = await risk_guard_service.start_session(
        user_id=payload.user_id,
        capital=payload.capital,
        payout_pct=payload.payout_pct,
        target_profit=payload.target_profit,
        stop_loss=payload.stop_loss,
        max_trades=payload.max_trades,
    )
    return {"success": True, "session": session}


@router.get("/riskguard/session/current")
async def riskguard_current(user_id: str = "default"):
    session = await risk_guard_service.get_active_session(user_id)
    return {"success": True, "session": session}


@router.post("/riskguard/session/record-trade")
async def riskguard_record(payload: RecordTradeRequest):
    result = await risk_guard_service.record_trade(
        user_id=payload.user_id,
        outcome=payload.outcome,
        amount=payload.amount,
        note=payload.note,
    )
    return result


@router.post("/riskguard/session/close")
async def riskguard_close(payload: CloseSessionRequest):
    return await risk_guard_service.close_session(payload.user_id)


@router.get("/riskguard/sessions/history")
async def riskguard_history(user_id: str = "default", limit: int = 50):
    sessions = await risk_guard_service.get_history(user_id, limit=limit)
    return {"success": True, "count": len(sessions), "sessions": sessions}


@router.get("/riskguard/stats/summary")
async def riskguard_summary(user_id: str = "default"):
    stats = await risk_guard_service.summary(user_id)
    return {"success": True, **stats}
