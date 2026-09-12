"""Iter 142 — Forex order executor.

Chooses PAPER / MT5_PYTHON / TAMPERMONKEY based on the config. The
Tampermonkey path just persists the order to `forex_orders_pending`
so the TM userscript can poll and execute it (DOM injection on PO's
web-MT5 UI — TM-side selectors ship in Iter 143).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    ExecutionSurface, ForexOrder, ForexPosition, OrderSide, PositionStatus,
)
from .mt5_bridge import get_bridge
from .risk import compute_pnl

logger = logging.getLogger(__name__)


class ForexExecutor:
    """Dispatches a `ForexOrder` and returns a `ForexPosition`."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None) -> None:
        self.db = db

    async def execute(self, order: ForexOrder, current_price: float) -> ForexPosition:
        if order.surface == ExecutionSurface.MT5_PYTHON:
            return await self._execute_mt5(order, current_price)
        if order.surface == ExecutionSurface.TAMPERMONKEY:
            return await self._execute_tampermonkey(order, current_price)
        return await self._execute_paper(order, current_price)

    # -----------------------------------------------------------------
    async def _execute_paper(self, order: ForexOrder, current_price: float) -> ForexPosition:
        pos = ForexPosition(
            position_id=str(uuid.uuid4()),
            signal_id=order.signal_id,
            symbol=order.symbol,
            side=order.side,
            lots=order.lots,
            entry=current_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            trail_pips=order.trail_pips,
            surface=ExecutionSurface.PAPER,
            status=PositionStatus.OPEN,
            meta={"paper": True},
        )
        await self._persist_position(pos)
        logger.info(f"[forex/paper] OPEN {pos.side} {pos.symbol} {pos.lots} @ {pos.entry}")
        return pos

    # -----------------------------------------------------------------
    async def _execute_mt5(self, order: ForexOrder, current_price: float) -> ForexPosition:
        bridge = get_bridge()
        if not bridge.available:
            logger.warning("[forex/mt5] MetaTrader5 package unavailable — falling back to paper")
            return await self._execute_paper(order, current_price)
        res = bridge.market_order(
            symbol=order.symbol,
            side=order.side.value,
            lots=order.lots,
            sl=order.stop_loss,
            tp=order.take_profit,
            magic=order.magic,
        )
        if not res.ok:
            logger.error(f"[forex/mt5] order_send failed: {res.error}")
            pos = ForexPosition(
                position_id=str(uuid.uuid4()),
                signal_id=order.signal_id,
                symbol=order.symbol,
                side=order.side,
                lots=order.lots,
                entry=current_price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                surface=order.surface,
                status=PositionStatus.REJECTED,
                closed_at=datetime.now(timezone.utc),
                close_reason=f"mt5_error:{res.error}",
            )
            await self._persist_position(pos)
            return pos
        data = res.data or {}
        pos = ForexPosition(
            position_id=str(data.get("order", uuid.uuid4())),
            signal_id=order.signal_id,
            symbol=order.symbol,
            side=order.side,
            lots=order.lots,
            entry=float(data.get("price", current_price)),
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            trail_pips=order.trail_pips,
            surface=ExecutionSurface.MT5_PYTHON,
            status=PositionStatus.OPEN,
            meta={"mt5_deal": data.get("deal"), "mt5_order": data.get("order")},
        )
        await self._persist_position(pos)
        logger.info(f"[forex/mt5] OPEN {pos.side} {pos.symbol} {pos.lots} @ {pos.entry}  order={data.get('order')}")
        return pos

    # -----------------------------------------------------------------
    async def _execute_tampermonkey(self, order: ForexOrder, current_price: float) -> ForexPosition:
        """Persist a PENDING order + queue for the TM script to poll.

        The full TM-side DOM click flow ships in Iter 143 once we've probed
        PO's web-MT5 markup. For now we register the pending order so the
        state machine + audit trail exist end-to-end.
        """
        pos = ForexPosition(
            position_id=str(uuid.uuid4()),
            signal_id=order.signal_id,
            symbol=order.symbol,
            side=order.side,
            lots=order.lots,
            entry=current_price,      # tentative — TM will overwrite on fill
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            trail_pips=order.trail_pips,
            surface=ExecutionSurface.TAMPERMONKEY,
            status=PositionStatus.PENDING,
            meta={"queued_for_tm": True},
        )
        await self._persist_position(pos)
        if self.db is not None:
            await self.db.forex_orders_pending.insert_one(
                {**order.model_dump(mode="json"), "position_id": pos.position_id,
                 "queued_at": datetime.now(timezone.utc).isoformat()}
            )
        logger.info(f"[forex/tm] QUEUED {pos.side} {pos.symbol} {pos.lots} — awaiting TM pickup")
        return pos

    # -----------------------------------------------------------------
    async def close(
        self,
        pos: ForexPosition,
        exit_price: float,
        reason: str = "manual",
    ) -> ForexPosition:
        """Close an OPEN position. Idempotent — already-closed is a no-op."""
        if pos.status != PositionStatus.OPEN:
            return pos
        if pos.surface == ExecutionSurface.MT5_PYTHON:
            bridge = get_bridge()
            if bridge.available:
                try:
                    ticket = int(pos.position_id)
                except ValueError:
                    ticket = 0
                if ticket:
                    r = bridge.close_position(
                        ticket=ticket, symbol=pos.symbol,
                        lots=pos.lots, side=pos.side.value,
                    )
                    if r.ok and r.data:
                        exit_price = float(r.data.get("close_price", exit_price))

        pnl_usd, pnl_pips = compute_pnl(
            symbol=pos.symbol, side=pos.side,
            entry=pos.entry, exit_price=exit_price, lots=pos.lots,
        )
        pos.status = PositionStatus.CLOSED
        pos.closed_at = datetime.now(timezone.utc)
        pos.exit_price = exit_price
        pos.pnl = pnl_usd
        pos.pnl_pips = pnl_pips
        pos.close_reason = reason
        await self._persist_position(pos)
        logger.info(f"[forex] CLOSE {pos.symbol} {pos.side} → pnl=${pnl_usd:.2f} ({pnl_pips:.1f}p) reason={reason}")
        return pos

    # -----------------------------------------------------------------
    async def _persist_position(self, pos: ForexPosition) -> None:
        if self.db is None:
            return
        await self.db.forex_positions.update_one(
            {"position_id": pos.position_id},
            {"$set": pos.model_dump(mode="json")},
            upsert=True,
        )
