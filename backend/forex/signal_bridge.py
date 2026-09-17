"""Iter 143 — Signal Auto-Bridge.

Reuses the whole existing brain (pattern detectors, smart-money detectors,
mean-reversion strategy, confluence engine) and produces a `ForexSignal`
whenever the confluence gate fires.

Public API:
    * `bridge_symbol(symbol, timeframe, ...)` — one-shot: build signals,
      score them, translate to a ForexSignal, emit to `forex.engine`.
    * `BridgeLoop.start()/stop()` — background scheduler ticking every N s.

Nothing here reimplements signal logic — every ingredient is imported from
its existing module. That's the whole point of the "auto-bridge": the same
brain drives both binary and forex execution.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

from .engine import get_engine
from .models import ExecutionSurface, ForexSignal, OrderSide

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Symbol normalisation between the binary/OTC universe and MT5's plain FX pairs
# ---------------------------------------------------------------------------

def _mt5_symbol(asset: str) -> str:
    """Strip the `_OTC` suffix and any separators — MT5 uses plain `EURUSD`."""
    s = (asset or "").upper()
    for suffix in ("_OTC", "-OTC", " OTC"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.replace("_", "").replace("-", "").replace("/", "")


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period + 1:
        return 0.0
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    val = tr.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else 0.0


# ---------------------------------------------------------------------------
# Core: one-shot bridge
# ---------------------------------------------------------------------------

async def bridge_symbol(
    symbol: str,
    timeframe: str = "1m",
    limit: int = 200,
    equity_usd: float = 10_000.0,
    surface: Optional[ExecutionSurface] = None,
    emit: bool = True,
) -> Dict[str, Any]:
    """Load candles → run all detectors → score confluence → emit ForexSignal.

    Returns a dict with the decision + (if emitted) the position result.

    Never raises on missing data / detector errors — returns a
    `skipped` result instead so callers can safely fire-and-forget.
    """
    # Late imports so a broken detector can't crash import-time
    from routes.confluence_routes import _load_candles_from_db, get_confluence_config
    from confluence_service import score_confluence, should_fire, signals_from_patterns
    from pattern_detector import detect_all as detect_patterns
    from smart_money import detect_all_smart_money
    from strategies.mean_reversion import mean_reversion_signal

    df = await _load_candles_from_db(_normalize_for_candles(symbol), timeframe, limit)
    if df is None or df.empty:
        return {"symbol": symbol, "accepted": False, "reason": "no_candles"}

    signals: List[Dict[str, Any]] = []

    # 1. Chart patterns
    try:
        pattern_hits = [h.to_dict() for h in detect_patterns(df)]
        signals.extend(signals_from_patterns(pattern_hits, asset=symbol, timeframe=timeframe))
    except Exception as e:
        logger.debug(f"[bridge] patterns skipped for {symbol}: {e}")

    # 2. Smart money
    try:
        for h in detect_all_smart_money(df):
            d = (h.direction or "").upper()
            if d in ("CALL", "PUT"):
                signals.append({
                    "source": f"smart_money:{h.pattern}",
                    "direction": d,
                    "confidence": float(h.confidence or 0.0),
                    "asset": symbol, "timeframe": timeframe,
                })
    except Exception as e:
        logger.debug(f"[bridge] smart_money skipped for {symbol}: {e}")

    # 3. Mean reversion
    try:
        mr = mean_reversion_signal(df)
        if mr.direction in ("CALL", "PUT"):
            signals.append({
                "source": "strategy:mean_reversion",
                "direction": mr.direction,
                "confidence": float(mr.confidence or 0.0),
                "asset": symbol, "timeframe": timeframe,
            })
    except Exception as e:
        logger.debug(f"[bridge] mean_reversion skipped for {symbol}: {e}")

    # 4. TQNet — Iter 146. RevIN + Temporal Query attention. Cheap,
    # deterministic, adds a distribution-shift-robust view on top of the
    # classical detectors above. Signals with confidence < 0.05 are dropped
    # so we don't fatten the source count with near-flat forecasts.
    try:
        from tqnet_service import tqnet_score_for_df
        tq_sig = tqnet_score_for_df(
            df, t=int(len(df)), asset=symbol, timeframe=timeframe, window=30,
        )
        if tq_sig.get("direction") in ("CALL", "PUT") and float(tq_sig.get("confidence") or 0.0) >= 0.05:
            signals.append(tq_sig)
    except Exception as e:
        logger.debug(f"[bridge] tqnet skipped for {symbol}: {e}")

    if not signals:
        return {"symbol": symbol, "accepted": False, "reason": "no_signals", "n_signals": 0}

    # Score
    cfg = get_confluence_config()
    threshold = float(cfg.get("threshold", 0.65))
    min_sources = int(cfg.get("min_sources", 3))
    result = score_confluence(signals, min_sources=min_sources)
    fires = should_fire(result, threshold=threshold, min_sources=min_sources)
    if not fires:
        return {
            "symbol": symbol,
            "accepted": False,
            "reason": "confluence_gate_blocked",
            "n_signals": len(signals),
            "confluence_score": result.get("confluence_score"),
            "direction": result.get("direction"),
        }

    # Translate to ForexSignal
    direction = result["direction"]
    side = OrderSide.BUY if direction == "CALL" else OrderSide.SELL
    entry = float(df["close"].iloc[-1])
    atr = _atr(df, 14)
    mt5_sym = _mt5_symbol(symbol)
    fx_signal = ForexSignal(
        signal_id=str(uuid.uuid4()),
        symbol=mt5_sym,
        side=side,
        entry=entry,
        confidence=float(result.get("confluence_score") or 0.0),
        confluence_score=float(result.get("confluence_score") or 0.0),
        sources=list(dict.fromkeys(
            result.get("sources_call" if direction == "CALL" else "sources_put") or []
        )),
        timeframe=timeframe,
        atr=atr if atr > 0 else None,
    )
    if not emit:
        return {
            "symbol": symbol, "accepted": True, "would_fire": True,
            "forex_signal": fx_signal.model_dump(mode="json"),
            "confluence": result,
        }
    engine = get_engine()
    emission = await engine.on_signal(
        fx_signal, equity_usd=equity_usd, surface=surface,
    )
    return {
        "symbol": symbol,
        "mt5_symbol": mt5_sym,
        "accepted": emission.get("accepted", False),
        "reason": emission.get("reason"),
        "n_signals": len(signals),
        "confluence": result,
        "forex_signal": fx_signal.model_dump(mode="json"),
        "emission": emission,
    }


def _normalize_for_candles(symbol: str) -> str:
    """Our candle stores use the OTC-suffixed key. If the caller passed a
    bare FX symbol (EURUSD), try that first; else pass through."""
    return symbol.upper()


# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

class BridgeLoop:
    """Optional scheduler — ticks `bridge_symbol` for every configured
    symbol on a fixed interval. Off by default (surface stays PAPER)."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.interval_s = 30
        self.symbols: List[str] = []
        self.timeframe = "1m"

    def is_running(self) -> bool:
        return self._running

    def configure(self, *, symbols: List[str], interval_s: int = 30, timeframe: str = "1m") -> None:
        self.symbols = symbols
        self.interval_s = max(5, int(interval_s))
        self.timeframe = timeframe

    async def start(self) -> None:
        if self._running: return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[bridge] loop started · symbols={self.symbols} · every {self.interval_s}s")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
            self._task = None
        logger.info("[bridge] loop stopped")

    async def _loop(self) -> None:
        while self._running:
            for s in list(self.symbols):
                try:
                    await bridge_symbol(s, timeframe=self.timeframe)
                except Exception as e:
                    logger.warning(f"[bridge] {s} tick failed: {e}")
            try:
                await asyncio.sleep(self.interval_s)
            except asyncio.CancelledError:
                break


_loop_singleton: Optional[BridgeLoop] = None


def get_bridge_loop() -> BridgeLoop:
    global _loop_singleton
    if _loop_singleton is None:
        _loop_singleton = BridgeLoop()
    return _loop_singleton
