"""Iter 142 — Forex trade models.

Distinct from binary-options `signals`/`trades` because forex trades:
    * have OPEN + CLOSE times (no fixed expiration)
    * carry position size in lots
    * carry SL / TP that can be moved / trailed
    * P&L is computed continuously from live price × pip value

Kept lean: all-Pydantic v2 + ObjectId helper from server.

Collections created (indexed at startup by `forex_engine.ensure_indexes`):
    * `forex_positions`  — open + closed positions
    * `forex_signals`    — every generated forex signal (accepted or skipped)
    * `forex_config`     — singleton doc for engine config
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderSide(str, Enum):
    BUY = "BUY"      # long / CALL
    SELL = "SELL"    # short / PUT


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class ExitMode(str, Enum):
    FIXED = "FIXED"          # pips or absolute price
    ATR = "ATR"              # 1.5×ATR SL, 3×ATR TP by default
    TRAILING = "TRAILING"    # move SL as price moves in our favour


class SizingMode(str, Enum):
    FIXED_LOTS = "FIXED_LOTS"
    RISK_PCT = "RISK_PCT"    # size from SL distance + risk %
    KELLY = "KELLY"          # Kelly-adjusted by signal confidence


class ExecutionSurface(str, Enum):
    """Where the order gets executed."""
    TAMPERMONKEY = "TAMPERMONKEY"       # PO web-MT5 via TM DOM injection
    MT5_PYTHON = "MT5_PYTHON"           # local Windows MT5 terminal
    PAPER = "PAPER"                     # simulated fills (default until user opts-in)


class PositionStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ExitConfig(BaseModel):
    """Per-signal exit configuration. All three modes can be layered."""
    mode: ExitMode = ExitMode.ATR
    # FIXED-mode
    sl_pips: Optional[float] = None
    tp_pips: Optional[float] = None
    # ATR-mode
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0
    # TRAILING-mode
    trail_pips: Optional[float] = None
    trail_activate_pips: Optional[float] = None


class SizingConfig(BaseModel):
    mode: SizingMode = SizingMode.RISK_PCT
    fixed_lots: float = 0.01
    risk_pct: float = 1.0           # % of equity risked per trade
    kelly_scale: float = 0.25       # fraction of Kelly (0.25 = quarter-Kelly)
    min_lots: float = 0.01
    max_lots: float = 5.0


class ForexEngineConfig(BaseModel):
    """Root config, one document with `_id = "singleton"`."""
    enabled: bool = False
    execution_surface: ExecutionSurface = ExecutionSurface.PAPER
    default_exit: ExitConfig = Field(default_factory=ExitConfig)
    default_sizing: SizingConfig = Field(default_factory=SizingConfig)
    max_concurrent_positions: int = 5
    max_daily_loss_pct: float = 3.0
    allowed_symbols: List[str] = Field(
        default_factory=lambda: [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
            "USDCHF", "USDCAD", "NZDUSD",
        ]
    )
    confluence_min_score: float = 0.65
    confluence_min_sources: int = 3


# ---------------------------------------------------------------------------
# Runtime shapes
# ---------------------------------------------------------------------------

class ForexSignal(BaseModel):
    signal_id: str
    symbol: str
    side: OrderSide
    entry: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)
    confluence_score: Optional[float] = None
    sources: List[str] = Field(default_factory=list)
    timeframe: str = "1m"
    atr: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ForexOrder(BaseModel):
    """What we send to an executor. Executors return a ForexPosition."""
    signal_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    lots: float
    price: Optional[float] = None          # for LIMIT/STOP
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    surface: ExecutionSurface = ExecutionSurface.PAPER
    trail_pips: Optional[float] = None
    magic: int = 20260212                   # MT5 EA "magic number"


class ForexPosition(BaseModel):
    position_id: str
    signal_id: str
    symbol: str
    side: OrderSide
    lots: float
    entry: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trail_pips: Optional[float] = None
    surface: ExecutionSurface
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    close_reason: Optional[str] = None     # "sl" | "tp" | "trail" | "manual" | "reverse"
    meta: Dict[str, Any] = Field(default_factory=dict)
