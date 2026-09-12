"""Iter 142 — Forex module tests (models, risk, executor, engine)."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from forex.models import (
    ExecutionSurface, ExitConfig, ExitMode, ForexEngineConfig, ForexOrder,
    ForexSignal, OrderSide, OrderType, PositionStatus, SizingConfig, SizingMode,
)
from forex.risk import (
    compute_lots, compute_pnl, compute_sl_tp, from_pips, pip_size,
    pip_value_usd, to_pips, update_trailing_stop,
)
from forex.executor import ForexExecutor
from forex.engine import ForexEngine


# ---------------------------------------------------------------------------
# Pip helpers
# ---------------------------------------------------------------------------

def test_pip_size_major():
    assert pip_size("EURUSD") == 0.0001


def test_pip_size_jpy():
    assert pip_size("USDJPY") == 0.01


def test_pip_size_xau():
    assert pip_size("XAUUSD") == 0.10


def test_to_and_from_pips_roundtrip():
    assert to_pips("EURUSD", from_pips("EURUSD", 20)) == pytest.approx(20.0)
    assert to_pips("USDJPY", from_pips("USDJPY", 30)) == pytest.approx(30.0)


def test_pip_value_std_lot():
    # 1 lot (100k) × 0.0001 = $10 per pip on EURUSD
    assert pip_value_usd("EURUSD", 1.0) == pytest.approx(10.0)
    assert pip_value_usd("EURUSD", 0.01) == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# SL/TP calculators
# ---------------------------------------------------------------------------

def test_fixed_sl_tp_long():
    cfg = ExitConfig(mode=ExitMode.FIXED, sl_pips=20, tp_pips=40)
    sl, tp = compute_sl_tp("EURUSD", OrderSide.BUY, 1.10000, cfg)
    assert sl == pytest.approx(1.09800, abs=1e-5)
    assert tp == pytest.approx(1.10400, abs=1e-5)


def test_fixed_sl_tp_short():
    cfg = ExitConfig(mode=ExitMode.FIXED, sl_pips=20, tp_pips=40)
    sl, tp = compute_sl_tp("EURUSD", OrderSide.SELL, 1.10000, cfg)
    assert sl == pytest.approx(1.10200, abs=1e-5)
    assert tp == pytest.approx(1.09600, abs=1e-5)


def test_atr_sl_tp_long():
    cfg = ExitConfig(mode=ExitMode.ATR, sl_atr_mult=1.5, tp_atr_mult=3.0)
    sl, tp = compute_sl_tp("EURUSD", OrderSide.BUY, 1.10000, cfg, atr=0.001)
    assert sl == pytest.approx(1.10000 - 0.0015, abs=1e-6)
    assert tp == pytest.approx(1.10000 + 0.003, abs=1e-6)


def test_atr_returns_none_without_atr():
    cfg = ExitConfig(mode=ExitMode.ATR)
    sl, tp = compute_sl_tp("EURUSD", OrderSide.BUY, 1.10000, cfg, atr=None)
    assert sl is None and tp is None


def test_trailing_initial_sl_buy():
    cfg = ExitConfig(mode=ExitMode.TRAILING, trail_pips=15)
    sl, tp = compute_sl_tp("EURUSD", OrderSide.BUY, 1.10000, cfg)
    assert sl == pytest.approx(1.09850, abs=1e-5)
    assert tp is None


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

def test_fixed_lots_sizing():
    s = SizingConfig(mode=SizingMode.FIXED_LOTS, fixed_lots=0.05)
    assert compute_lots("EURUSD", 1.10, 1.098, 10_000, s) == pytest.approx(0.05)


def test_risk_pct_sizing_scales_with_sl():
    s = SizingConfig(mode=SizingMode.RISK_PCT, risk_pct=1.0)
    # 20-pip SL, 1% of $10k = $100 → 100/(20*10) = 0.5 lots
    lots = compute_lots("EURUSD", 1.10000, 1.09800, 10_000, s)
    assert lots == pytest.approx(0.5, abs=0.01)


def test_risk_pct_sizing_falls_back_on_no_sl():
    s = SizingConfig(mode=SizingMode.RISK_PCT, risk_pct=1.0, fixed_lots=0.03)
    assert compute_lots("EURUSD", 1.10, None, 10_000, s) == pytest.approx(0.03)


def test_lot_clamping():
    s = SizingConfig(mode=SizingMode.RISK_PCT, risk_pct=100.0, max_lots=2.0)
    lots = compute_lots("EURUSD", 1.10000, 1.09900, 100_000, s)
    assert lots <= 2.0


def test_kelly_negative_edge_falls_back():
    s = SizingConfig(mode=SizingMode.KELLY, fixed_lots=0.02)
    # Very low confidence → negative edge → fallback
    assert compute_lots("EURUSD", 1.10, 1.098, 10_000, s, signal_confidence=0.1) == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# Trailing stop
# ---------------------------------------------------------------------------

def test_trailing_moves_stop_up_on_buy():
    # BUY at 1.10, current price 1.1030 (30 pips profit), trail 15 pips
    new = update_trailing_stop("EURUSD", OrderSide.BUY, 1.10000, 1.09900, 1.10300, 15)
    assert new == pytest.approx(1.10150, abs=1e-5)


def test_trailing_does_not_widen():
    # SL already tight — trail can only tighten more, never widen
    new = update_trailing_stop("EURUSD", OrderSide.BUY, 1.10000, 1.10250, 1.10300, 15)
    # trail candidate = 1.10300-0.0015 = 1.10150 < current 1.10250 → keep current
    assert new == 1.10250


def test_trailing_respects_activation_threshold():
    # Only 5 pips profit, activation requires 20 → keep SL unchanged
    new = update_trailing_stop(
        "EURUSD", OrderSide.BUY, 1.10000, 1.09900, 1.10050, 15,
        trail_activate_pips=20,
    )
    assert new == 1.09900


# ---------------------------------------------------------------------------
# P&L
# ---------------------------------------------------------------------------

def test_pnl_long_winner():
    pnl, pips = compute_pnl("EURUSD", OrderSide.BUY, 1.10000, 1.10200, lots=0.10)
    assert pips == pytest.approx(20.0, abs=0.5)
    assert pnl == pytest.approx(20 * pip_value_usd("EURUSD", 0.10), abs=0.5)


def test_pnl_short_loser():
    pnl, pips = compute_pnl("EURUSD", OrderSide.SELL, 1.10000, 1.10100, lots=0.10)
    assert pips < 0
    assert pnl < 0


# ---------------------------------------------------------------------------
# Executor (paper path — no DB required)
# ---------------------------------------------------------------------------

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_paper_executor_opens_and_closes():
    ex = ForexExecutor(db=None)
    order = ForexOrder(
        signal_id="s1", symbol="EURUSD", side=OrderSide.BUY,
        lots=0.1, stop_loss=1.098, take_profit=1.104,
        surface=ExecutionSurface.PAPER,
    )
    pos = _run(ex.execute(order, current_price=1.10000))
    assert pos.status == PositionStatus.OPEN
    assert pos.entry == 1.10000
    assert pos.surface == ExecutionSurface.PAPER
    closed = _run(ex.close(pos, exit_price=1.10200, reason="tp"))
    assert closed.status == PositionStatus.CLOSED
    assert closed.pnl is not None and closed.pnl > 0
    assert closed.close_reason == "tp"


# ---------------------------------------------------------------------------
# Engine (mocked db)
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, docs): self._docs = docs
    def sort(self, *a, **kw): return self
    def to_list(self, length=None): return _wrap_await(self._docs[:length] if length else self._docs)
    def __aiter__(self):
        async def gen():
            for d in self._docs: yield d
        return gen()


def _wrap_await(val):
    async def _co(): return val
    return _co()


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
    def find(self, *a, **kw): return _FakeCursor(self.docs)
    async def find_one(self, *a, **kw): return None
    async def update_one(self, *a, **kw): return MagicMock(matched_count=1)
    async def insert_one(self, *a, **kw): return MagicMock(inserted_id="fake")
    async def create_index(self, *a, **kw): return None


class _FakeDB:
    def __init__(self):
        self.forex_positions = _FakeCollection()
        self.forex_signals = _FakeCollection()
        self.forex_orders_pending = _FakeCollection()
        self.forex_config = _FakeCollection()


def test_engine_paper_signal_end_to_end():
    db = _FakeDB()
    eng = ForexEngine(db=db)
    eng._config = ForexEngineConfig(
        execution_surface=ExecutionSurface.PAPER,
        allowed_symbols=["EURUSD"],
    )
    signal = ForexSignal(
        signal_id="sig-1", symbol="EURUSD", side=OrderSide.BUY, entry=1.10000,
        confidence=0.8, atr=0.001, timeframe="5m",
    )
    result = _run(eng.on_signal(signal, equity_usd=10_000))
    assert result["accepted"] is True
    assert result["position"]["surface"] == ExecutionSurface.PAPER.value
    # Should have calculated SL/TP via ATR mode default
    assert result["position"]["stop_loss"] is not None
    assert result["position"]["take_profit"] is not None


def test_engine_rejects_disallowed_symbol():
    db = _FakeDB()
    eng = ForexEngine(db=db)
    eng._config = ForexEngineConfig(allowed_symbols=["EURUSD"])
    signal = ForexSignal(
        signal_id="sig-2", symbol="AUDNZD", side=OrderSide.SELL, entry=1.09,
        confidence=0.8, atr=0.001,
    )
    result = _run(eng.on_signal(signal))
    assert result["accepted"] is False
    assert result["reason"] == "symbol_not_allowed"


# ---------------------------------------------------------------------------
# Route module imports (no live server)
# ---------------------------------------------------------------------------

def test_forex_routes_module_imports():
    from routes import forex_routes
    assert forex_routes.router is not None
    # Must have prefix /forex — server prepends /api
    assert forex_routes.router.prefix == "/forex"


def test_mt5_bridge_falls_back_gracefully():
    """On a non-Windows dev pod, MT5 pkg won't be installed. Bridge must
    NOT crash — every method returns MT5Result(ok=False)."""
    from forex.mt5_bridge import get_bridge
    b = get_bridge()
    # `available` is a hard boolean based on import success
    assert isinstance(b.available, bool)
    r = b.connect()
    # Either succeeds (if MT5 installed) or fails cleanly
    if not b.available:
        assert r.ok is False
        assert "not installed" in (r.error or "").lower() or "initialize" in (r.error or "").lower()
