"""Iter 142 — MT5 Python bridge (graceful fallback).

Wraps the official `MetaTrader5` package. On non-Windows or when the
package is unavailable, every method returns a `MT5Result(ok=False, ...)`
so callers can still function (they'll fall back to PAPER execution).

Nothing in the engine depends on MT5 being installed — this module is
only imported through the executor layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as _mt5     # type: ignore
    _MT5_AVAILABLE = True
except Exception as _e:                            # pragma: no cover — dep may be absent
    _mt5 = None                                    # type: ignore
    _MT5_AVAILABLE = False


@dataclass
class MT5Result:
    ok: bool
    data: Any = None
    error: Optional[str] = None


class MT5Bridge:
    """Thin, testable facade over `MetaTrader5`.

    Usage:
        bridge = MT5Bridge()
        if bridge.available:
            bridge.connect(login=..., password=..., server=...)
            bridge.market_order("EURUSD", "BUY", lots=0.01, sl=..., tp=...)
    """

    def __init__(self) -> None:
        self._connected = False

    @property
    def available(self) -> bool:
        return _MT5_AVAILABLE

    # -----------------------------------------------------------------
    # Session
    # -----------------------------------------------------------------
    def connect(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
    ) -> MT5Result:
        if not _MT5_AVAILABLE:
            return MT5Result(ok=False, error="MetaTrader5 package not installed")
        try:
            init_kwargs: Dict[str, Any] = {}
            if path: init_kwargs["path"] = path
            if login: init_kwargs["login"] = login
            if password: init_kwargs["password"] = password
            if server: init_kwargs["server"] = server
            if not _mt5.initialize(**init_kwargs):
                return MT5Result(ok=False, error=f"initialize failed: {_mt5.last_error()}")
            self._connected = True
            return MT5Result(ok=True, data=_mt5.account_info()._asdict()
                             if _mt5.account_info() else {})
        except Exception as e:
            return MT5Result(ok=False, error=str(e))

    def shutdown(self) -> None:
        if _MT5_AVAILABLE and self._connected:
            try: _mt5.shutdown()
            except Exception: pass
            self._connected = False

    # -----------------------------------------------------------------
    # Data
    # -----------------------------------------------------------------
    def account_info(self) -> MT5Result:
        if not (_MT5_AVAILABLE and self._connected):
            return MT5Result(ok=False, error="not connected")
        info = _mt5.account_info()
        if info is None:
            return MT5Result(ok=False, error=str(_mt5.last_error()))
        return MT5Result(ok=True, data=info._asdict())

    def symbol_tick(self, symbol: str) -> MT5Result:
        if not (_MT5_AVAILABLE and self._connected):
            return MT5Result(ok=False, error="not connected")
        tick = _mt5.symbol_info_tick(symbol)
        if tick is None:
            return MT5Result(ok=False, error=f"no tick for {symbol}")
        return MT5Result(ok=True, data={"bid": tick.bid, "ask": tick.ask, "time": tick.time})

    # -----------------------------------------------------------------
    # Orders
    # -----------------------------------------------------------------
    def market_order(
        self,
        symbol: str,
        side: str,   # "BUY" | "SELL"
        lots: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        magic: int = 20260212,
        comment: str = "EPB-Forex",
    ) -> MT5Result:
        if not (_MT5_AVAILABLE and self._connected):
            return MT5Result(ok=False, error="not connected")
        tick = _mt5.symbol_info_tick(symbol)
        if tick is None:
            return MT5Result(ok=False, error="no tick")
        price = tick.ask if side == "BUY" else tick.bid
        request = {
            "action": _mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": _mt5.ORDER_TYPE_BUY if side == "BUY" else _mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_filling": _mt5.ORDER_FILLING_IOC,
        }
        if sl is not None: request["sl"] = float(sl)
        if tp is not None: request["tp"] = float(tp)
        result = _mt5.order_send(request)
        if result is None or result.retcode != _mt5.TRADE_RETCODE_DONE:
            return MT5Result(
                ok=False,
                error=f"retcode={getattr(result, 'retcode', '?')} last_err={_mt5.last_error()}",
            )
        return MT5Result(ok=True, data={
            "order": result.order, "deal": result.deal, "price": result.price,
            "volume": result.volume, "comment": result.comment,
        })

    def modify_sl(self, ticket: int, symbol: str, new_sl: float, tp: Optional[float] = None) -> MT5Result:
        if not (_MT5_AVAILABLE and self._connected):
            return MT5Result(ok=False, error="not connected")
        req = {
            "action": _mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": float(new_sl),
        }
        if tp is not None: req["tp"] = float(tp)
        r = _mt5.order_send(req)
        if r is None or r.retcode != _mt5.TRADE_RETCODE_DONE:
            return MT5Result(ok=False, error=f"retcode={getattr(r, 'retcode', '?')}")
        return MT5Result(ok=True, data={"ticket": ticket, "new_sl": new_sl})

    def close_position(self, ticket: int, symbol: str, lots: float, side: str) -> MT5Result:
        if not (_MT5_AVAILABLE and self._connected):
            return MT5Result(ok=False, error="not connected")
        tick = _mt5.symbol_info_tick(symbol)
        if tick is None:
            return MT5Result(ok=False, error="no tick")
        opposite = "SELL" if side == "BUY" else "BUY"
        price = tick.bid if opposite == "SELL" else tick.ask
        req = {
            "action": _mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": _mt5.ORDER_TYPE_SELL if opposite == "SELL" else _mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "type_filling": _mt5.ORDER_FILLING_IOC,
            "comment": "EPB-Forex close",
        }
        r = _mt5.order_send(req)
        if r is None or r.retcode != _mt5.TRADE_RETCODE_DONE:
            return MT5Result(ok=False, error=f"retcode={getattr(r, 'retcode', '?')}")
        return MT5Result(ok=True, data={"close_price": r.price, "volume": r.volume})


# Module-level singleton so callers share the same MT5 session.
_bridge_singleton: Optional[MT5Bridge] = None


def get_bridge() -> MT5Bridge:
    global _bridge_singleton
    if _bridge_singleton is None:
        _bridge_singleton = MT5Bridge()
    return _bridge_singleton
