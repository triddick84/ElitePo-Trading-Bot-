"""Iter 142 — Forex engine.

Public surface:
    * `ForexEngine.on_signal(signal)` — turns a ForexSignal into a Position
      (paper / MT5 / TM depending on config).
    * `ForexEngine.tick(symbol, price)` — advance all OPEN positions in
      that symbol: fire SL/TP, update trailing stops. Called by the
      auto-scan loop and any live price feed.
    * `ForexEngine.list_open()` / `list_closed()` — read-only accessors.

Config lives in `forex_config` collection with `_id="singleton"`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from .executor import ForexExecutor
from .models import (
    ExecutionSurface, ExitConfig, ExitMode, ForexEngineConfig, ForexOrder,
    ForexPosition, ForexSignal, OrderSide, OrderType, PositionStatus,
    SizingConfig,
)
from .risk import compute_lots, compute_sl_tp, update_trailing_stop

logger = logging.getLogger(__name__)


class ForexEngine:
    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None) -> None:
        self.db = db
        self.executor = ForexExecutor(db=db)
        self._config: ForexEngineConfig = ForexEngineConfig()

    # -----------------------------------------------------------------
    # Config
    # -----------------------------------------------------------------
    async def load_config(self) -> ForexEngineConfig:
        if self.db is None:
            return self._config
        doc = await self.db.forex_config.find_one({"_id": "singleton"})
        if doc:
            doc.pop("_id", None)
            self._config = ForexEngineConfig(**doc)
        return self._config

    async def save_config(self, cfg: ForexEngineConfig) -> ForexEngineConfig:
        self._config = cfg
        if self.db is not None:
            await self.db.forex_config.update_one(
                {"_id": "singleton"},
                {"$set": {**cfg.model_dump(mode="json"), "_id": "singleton"}},
                upsert=True,
            )
        return cfg

    def config(self) -> ForexEngineConfig:
        return self._config

    async def ensure_indexes(self) -> None:
        if self.db is None: return
        try:
            await self.db.forex_positions.create_index("position_id", unique=True)
            await self.db.forex_positions.create_index([("symbol", 1), ("status", 1)])
            await self.db.forex_signals.create_index("signal_id", unique=True)
            await self.db.forex_orders_pending.create_index("position_id")
        except Exception as e:
            logger.warning(f"[forex/engine] index creation skipped: {e}")

    # -----------------------------------------------------------------
    # Signal → position
    # -----------------------------------------------------------------
    async def on_signal(
        self,
        signal: ForexSignal,
        equity_usd: float = 10_000.0,
        exit_cfg: Optional[ExitConfig] = None,
        sizing: Optional[SizingConfig] = None,
        surface: Optional[ExecutionSurface] = None,
    ) -> Dict[str, Any]:
        cfg = self._config
        exit_cfg = exit_cfg or cfg.default_exit
        sizing = sizing or cfg.default_sizing
        surface = surface or cfg.execution_surface

        # --- Gate: symbol allow-list ---
        if cfg.allowed_symbols and signal.symbol not in cfg.allowed_symbols:
            await self._persist_signal(signal, skipped_reason="symbol_not_allowed")
            return {"accepted": False, "reason": "symbol_not_allowed"}

        # --- Gate: max concurrent positions ---
        open_count = len(await self.list_open())
        if open_count >= cfg.max_concurrent_positions:
            await self._persist_signal(signal, skipped_reason="max_concurrent_reached")
            return {"accepted": False, "reason": "max_concurrent_reached"}

        # --- Gate: daily loss cap ---
        daily_pnl = await self._today_pnl()
        if daily_pnl <= -abs(equity_usd * cfg.max_daily_loss_pct / 100.0):
            await self._persist_signal(signal, skipped_reason="daily_loss_cap")
            return {"accepted": False, "reason": "daily_loss_cap", "daily_pnl": daily_pnl}

        # --- Compute SL/TP (respect signal's own values if provided) ---
        sl = signal.stop_loss
        tp = signal.take_profit
        if sl is None or tp is None:
            calc_sl, calc_tp = compute_sl_tp(
                symbol=signal.symbol, side=signal.side,
                entry=signal.entry, exit_cfg=exit_cfg, atr=signal.atr,
            )
            sl = sl if sl is not None else calc_sl
            tp = tp if tp is not None else calc_tp

        # --- Size ---
        lots = compute_lots(
            symbol=signal.symbol, entry=signal.entry, stop_loss=sl,
            equity_usd=equity_usd, sizing=sizing,
            signal_confidence=signal.confidence,
        )

        order = ForexOrder(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            order_type=OrderType.MARKET,
            lots=lots,
            stop_loss=sl,
            take_profit=tp,
            surface=surface,
            trail_pips=exit_cfg.trail_pips if exit_cfg.mode == ExitMode.TRAILING else None,
        )
        pos = await self.executor.execute(order, current_price=signal.entry)
        await self._persist_signal(signal, position_id=pos.position_id)
        return {"accepted": True, "position": pos.model_dump(mode="json"), "order": order.model_dump(mode="json")}

    # -----------------------------------------------------------------
    # Live tick — check SL/TP + trailing on every OPEN position for a symbol
    # -----------------------------------------------------------------
    async def tick(self, symbol: str, price: float) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        opens = await self.list_open(symbol=symbol)
        for pos in opens:
            # SL hit?
            if pos.stop_loss is not None:
                hit_sl = (
                    price <= pos.stop_loss if pos.side == OrderSide.BUY
                    else price >= pos.stop_loss
                )
                if hit_sl:
                    closed = await self.executor.close(pos, exit_price=pos.stop_loss, reason="sl")
                    actions.append({"position_id": pos.position_id, "action": "closed", "reason": "sl", "pnl": closed.pnl})
                    continue
            # TP hit?
            if pos.take_profit is not None:
                hit_tp = (
                    price >= pos.take_profit if pos.side == OrderSide.BUY
                    else price <= pos.take_profit
                )
                if hit_tp:
                    closed = await self.executor.close(pos, exit_price=pos.take_profit, reason="tp")
                    actions.append({"position_id": pos.position_id, "action": "closed", "reason": "tp", "pnl": closed.pnl})
                    continue
            # Trailing?
            if pos.trail_pips is not None:
                new_sl = update_trailing_stop(
                    symbol=pos.symbol, side=pos.side,
                    entry=pos.entry, current_sl=pos.stop_loss,
                    current_price=price, trail_pips=pos.trail_pips,
                )
                if new_sl != pos.stop_loss:
                    pos.stop_loss = new_sl
                    await self.executor._persist_position(pos)
                    actions.append({"position_id": pos.position_id, "action": "trail_moved", "new_sl": new_sl})
        return actions

    # -----------------------------------------------------------------
    async def close_position(self, position_id: str, price: float, reason: str = "manual") -> Optional[ForexPosition]:
        opens = await self.list_open()
        for p in opens:
            if p.position_id == position_id:
                return await self.executor.close(p, exit_price=price, reason=reason)
        return None

    # -----------------------------------------------------------------
    # Accessors
    # -----------------------------------------------------------------
    async def list_open(self, symbol: Optional[str] = None) -> List[ForexPosition]:
        if self.db is None: return []
        q: Dict[str, Any] = {"status": PositionStatus.OPEN.value}
        if symbol: q["symbol"] = symbol
        docs = await self.db.forex_positions.find(q).to_list(length=200)
        out: List[ForexPosition] = []
        for d in docs:
            d.pop("_id", None)
            try: out.append(ForexPosition(**d))
            except Exception: pass
        return out

    async def list_closed(self, limit: int = 50) -> List[ForexPosition]:
        if self.db is None: return []
        docs = await self.db.forex_positions.find(
            {"status": PositionStatus.CLOSED.value}
        ).sort("closed_at", -1).to_list(length=limit)
        out: List[ForexPosition] = []
        for d in docs:
            d.pop("_id", None)
            try: out.append(ForexPosition(**d))
            except Exception: pass
        return out

    async def _today_pnl(self) -> float:
        if self.db is None: return 0.0
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = self.db.forex_positions.find({
            "status": PositionStatus.CLOSED.value,
            "closed_at": {"$gte": start.isoformat()},
        })
        total = 0.0
        async for d in cursor:
            total += float(d.get("pnl") or 0.0)
        return total

    async def _persist_signal(self, signal: ForexSignal, position_id: Optional[str] = None, skipped_reason: Optional[str] = None) -> None:
        if self.db is None: return
        doc = signal.model_dump(mode="json")
        if position_id: doc["position_id"] = position_id
        if skipped_reason: doc["skipped_reason"] = skipped_reason
        await self.db.forex_signals.update_one({"signal_id": signal.signal_id}, {"$set": doc}, upsert=True)


# ----- module singleton -----
_engine_singleton: Optional[ForexEngine] = None


def get_engine(db: Optional[AsyncIOMotorDatabase] = None) -> ForexEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = ForexEngine(db=db)
    elif db is not None and _engine_singleton.db is None:
        _engine_singleton.db = db
        _engine_singleton.executor.db = db
    return _engine_singleton
