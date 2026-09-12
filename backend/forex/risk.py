"""Iter 142 — Forex risk & sizing helpers.

Pure functions so they're trivial to test. All prices are in **quote units**
(e.g. 1.10500 for EURUSD). `pip_size(symbol)` handles the JPY-pair 2-decimal
quirk automatically.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .models import ExitConfig, ExitMode, OrderSide, SizingConfig, SizingMode


# ---------------------------------------------------------------------------
# Pip helpers
# ---------------------------------------------------------------------------

def pip_size(symbol: str) -> float:
    """Return the size of one pip for the given symbol.

    JPY-quoted pairs (`*JPY`) use 0.01. Everything else uses 0.0001.
    Metals (XAU / XAG) use 0.10 as the convention.
    """
    s = (symbol or "").upper().replace("_OTC", "").replace("_", "")
    if s.startswith("XAU") or s.endswith("XAU"):
        return 0.10
    if s.startswith("XAG") or s.endswith("XAG"):
        return 0.01
    if s.endswith("JPY"):
        return 0.01
    return 0.0001


def pip_value_usd(symbol: str, lots: float) -> float:
    """USD value of one pip for `lots` size (standard 100k lot).

    Simplified: assumes account is USD-denominated and quote currency close
    enough that 1 pip ≈ (pip_size × lots × 100000) / (quote_price ≈ 1). For
    JPY pairs this over-estimates slightly but is fine for sizing decisions.
    """
    if lots <= 0:
        return 0.0
    return pip_size(symbol) * lots * 100_000


def to_pips(symbol: str, price_diff: float) -> float:
    ps = pip_size(symbol)
    return 0.0 if ps == 0 else price_diff / ps


def from_pips(symbol: str, pips: float) -> float:
    return pip_size(symbol) * pips


# ---------------------------------------------------------------------------
# SL / TP calculators
# ---------------------------------------------------------------------------

def compute_sl_tp(
    symbol: str,
    side: OrderSide,
    entry: float,
    exit_cfg: ExitConfig,
    atr: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Return `(stop_loss, take_profit)` as absolute prices.

    * FIXED → uses `sl_pips` / `tp_pips`.
    * ATR   → uses `sl_atr_mult × atr` etc. Returns (None, None) if `atr`
              is None.
    * TRAILING → SL is set at `trail_pips` below entry initially; TP is
              None (position closes when trail fires). If `trail_activate_pips`
              is set, the trail only starts arming after that much move.
    """
    if exit_cfg.mode == ExitMode.FIXED:
        sl = tp = None
        if exit_cfg.sl_pips is not None:
            offset = from_pips(symbol, exit_cfg.sl_pips)
            sl = entry - offset if side == OrderSide.BUY else entry + offset
        if exit_cfg.tp_pips is not None:
            offset = from_pips(symbol, exit_cfg.tp_pips)
            tp = entry + offset if side == OrderSide.BUY else entry - offset
        return sl, tp

    if exit_cfg.mode == ExitMode.ATR:
        if atr is None or atr <= 0:
            return None, None
        sl_offset = exit_cfg.sl_atr_mult * atr
        tp_offset = exit_cfg.tp_atr_mult * atr
        if side == OrderSide.BUY:
            return entry - sl_offset, entry + tp_offset
        return entry + sl_offset, entry - tp_offset

    if exit_cfg.mode == ExitMode.TRAILING:
        if exit_cfg.trail_pips is None:
            return None, None
        offset = from_pips(symbol, exit_cfg.trail_pips)
        sl = entry - offset if side == OrderSide.BUY else entry + offset
        return sl, None

    return None, None


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

def compute_lots(
    symbol: str,
    entry: float,
    stop_loss: Optional[float],
    equity_usd: float,
    sizing: SizingConfig,
    signal_confidence: float = 0.5,
) -> float:
    """Return the lot size to trade, clamped to `[min_lots, max_lots]`.

    * FIXED_LOTS  → returns `sizing.fixed_lots`.
    * RISK_PCT    → sizes so that `SL distance in USD ≈ equity × risk_pct%`.
                    Falls back to fixed_lots when SL is not provided.
    * KELLY       → treats `signal_confidence` as the edge probability. Uses
                    `f* = (bp - q) / b` where `b = TP/SL ratio` (assumed 2:1
                    when unknown), scaled by `kelly_scale`. Falls back to
                    fixed if edge ≤ 0.
    """
    def _clamp(x: float) -> float:
        x = max(sizing.min_lots, min(sizing.max_lots, x))
        # Round to 0.01 lot precision — MT5 minimum step
        return round(x, 2)

    if sizing.mode == SizingMode.FIXED_LOTS:
        return _clamp(sizing.fixed_lots)

    if sizing.mode == SizingMode.RISK_PCT:
        if stop_loss is None or entry == stop_loss or equity_usd <= 0:
            return _clamp(sizing.fixed_lots)
        sl_pips = abs(to_pips(symbol, entry - stop_loss))
        if sl_pips <= 0:
            return _clamp(sizing.fixed_lots)
        risk_usd = equity_usd * (sizing.risk_pct / 100.0)
        # lots ≈ risk_usd / (sl_pips × pip_value_per_lot)
        pip_val_per_lot = pip_value_usd(symbol, 1.0)
        if pip_val_per_lot <= 0:
            return _clamp(sizing.fixed_lots)
        lots = risk_usd / (sl_pips * pip_val_per_lot)
        return _clamp(lots)

    if sizing.mode == SizingMode.KELLY:
        p = max(0.0, min(1.0, signal_confidence))
        q = 1.0 - p
        b = 2.0  # assumed reward:risk
        edge = p * b - q
        if edge <= 0:
            return _clamp(sizing.fixed_lots)
        f_star = (edge / b) * sizing.kelly_scale
        # Convert fraction of equity to lots via the RISK_PCT path.
        pseudo_risk_pct = f_star * 100.0
        clone = SizingConfig(
            mode=SizingMode.RISK_PCT,
            fixed_lots=sizing.fixed_lots,
            risk_pct=pseudo_risk_pct,
            min_lots=sizing.min_lots,
            max_lots=sizing.max_lots,
        )
        return compute_lots(
            symbol=symbol, entry=entry, stop_loss=stop_loss,
            equity_usd=equity_usd, sizing=clone,
            signal_confidence=signal_confidence,
        )

    return _clamp(sizing.fixed_lots)


# ---------------------------------------------------------------------------
# Live-position management (trailing stop tick)
# ---------------------------------------------------------------------------

def update_trailing_stop(
    symbol: str,
    side: OrderSide,
    entry: float,
    current_sl: Optional[float],
    current_price: float,
    trail_pips: float,
    trail_activate_pips: Optional[float] = None,
) -> Optional[float]:
    """Return the new SL if the trail should tighten it, else `current_sl`.

    Never widens the SL. Never activates until `trail_activate_pips` of
    unrealised profit exists (if configured).
    """
    if trail_pips is None or trail_pips <= 0:
        return current_sl

    profit_pips = (
        to_pips(symbol, current_price - entry) if side == OrderSide.BUY
        else to_pips(symbol, entry - current_price)
    )
    if trail_activate_pips is not None and profit_pips < trail_activate_pips:
        return current_sl

    trail_offset = from_pips(symbol, trail_pips)
    if side == OrderSide.BUY:
        candidate = current_price - trail_offset
        if current_sl is None or candidate > current_sl:
            return candidate
    else:
        candidate = current_price + trail_offset
        if current_sl is None or candidate < current_sl:
            return candidate
    return current_sl


# ---------------------------------------------------------------------------
# P&L calculator
# ---------------------------------------------------------------------------

def compute_pnl(
    symbol: str,
    side: OrderSide,
    entry: float,
    exit_price: float,
    lots: float,
) -> Tuple[float, float]:
    """Return `(pnl_usd, pnl_pips)`."""
    diff = exit_price - entry if side == OrderSide.BUY else entry - exit_price
    pips = to_pips(symbol, diff)
    pnl_usd = pips * pip_value_usd(symbol, lots)
    return pnl_usd, pips
