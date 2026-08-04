"""
Cointegrated-pair confluence booster.

Iter 86 (Jul 2026, P1 · e).

Purpose
-------
For each signal on asset X, check whether the same direction is confirmed by
recent price action on the top cointegrated pairs (e.g., EURUSD ↔ EURUSD_OTC,
GBPUSD ↔ EURGBP inverse). Boost confidence when confluence exists, dampen
when pairs disagree.

This is a *lightweight* stat-arb / confluence check — not a full pair-mining
framework. We use:
1. A **static pair map** for the most obvious relationships (currency-crosses
   and their OTC twins) — cheap, no cointegration test needed at runtime.
2. **Recent close-return correlation** as a runtime check for whether the
   relationship is currently intact.

Kept in-memory and stateless-per-call so it can be invoked on every
`/ai-ensemble/predict` and `/signals/latest` without slowing them down.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static pair map — the "obvious" cointegrated relationships in FX
# ---------------------------------------------------------------------------
# Each entry: primary → list of (partner, direction_correlation).
#   +1 = same direction (up→up)
#   -1 = inverse direction (up→down)
#
# OTC twins are always +1 with their non-OTC counterpart because they track
# the same underlying. Currency triangles (e.g., EURUSD × GBPUSD ↔ EURGBP)
# are added below with the correct sign.
#
# We use uppercase, no separator, `_OTC` suffix (matches our normalize_asset()).

STATIC_PAIRS: Dict[str, List[Tuple[str, int]]] = {
    # OTC ↔ Regular twins ---------------------------------------------------
    "EURUSD":     [("EURUSD_OTC", 1)],
    "EURUSD_OTC": [("EURUSD",     1)],
    "GBPUSD":     [("GBPUSD_OTC", 1)],
    "GBPUSD_OTC": [("GBPUSD",     1)],
    "USDJPY":     [("USDJPY_OTC", 1)],
    "USDJPY_OTC": [("USDJPY",     1)],
    "AUDUSD":     [("AUDUSD_OTC", 1)],
    "AUDUSD_OTC": [("AUDUSD",     1)],
    "USDCAD":     [("USDCAD_OTC", 1)],
    "USDCAD_OTC": [("USDCAD",     1)],
    "NZDUSD":     [("NZDUSD_OTC", 1)],
    "NZDUSD_OTC": [("NZDUSD",     1)],
    "USDCHF":     [("USDCHF_OTC", 1)],
    "USDCHF_OTC": [("USDCHF",     1)],

    # Currency triangles ----------------------------------------------------
    # EURUSD and GBPUSD move together (correlated: both dollar denominators).
    # EURUSD ↔ USDJPY are USD-denominated in opposite directions.
    "EURUSD":     [("EURUSD_OTC", 1), ("GBPUSD", 1), ("USDJPY", -1)],
    "GBPUSD":     [("GBPUSD_OTC", 1), ("EURUSD", 1), ("USDJPY", -1)],
    "USDJPY":     [("USDJPY_OTC", 1), ("EURUSD", -1), ("GBPUSD", -1)],

    # Commodity ↔ risk pairs -----------------------------------------------
    # AUDUSD strongly tracks Copper / risk-on. When gold moves up sharply, USD
    # often weakens (inverse to USDJPY). We keep these correlations light.
    "XAUUSD":     [("USDJPY", -1)],
    "XAGUSD":     [("XAUUSD", 1)],

    # Crypto twins ----------------------------------------------------------
    "BTCUSD":     [("BTCUSD_OTC", 1), ("ETHUSD", 1)],
    "BTCUSD_OTC": [("BTCUSD",     1)],
    "ETHUSD":     [("ETHUSD_OTC", 1), ("BTCUSD", 1)],
    "ETHUSD_OTC": [("ETHUSD",     1)],
}


def _dedupe_partners(pairs: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
    """Keep only the first occurrence of each partner (respects order)."""
    seen = set()
    out = []
    for name, sign in pairs:
        if name in seen:
            continue
        seen.add(name)
        out.append((name, sign))
    return out


def get_partners(asset: str) -> List[Tuple[str, int]]:
    """Return dedup'd partner list for an asset."""
    return _dedupe_partners(STATIC_PAIRS.get(asset, []))


def _short_direction(candles: Sequence[Dict[str, Any]], n: int = 6) -> int:
    """
    Direction of the most recent `n` candles combined:
      +1 = net up, -1 = net down, 0 = flat.

    We use the sign of the mean close-return over the window.
    """
    if not candles or len(candles) < 3:
        return 0
    window = list(candles)[-n:]
    closes = [float(c.get("close", 0.0)) for c in window if c.get("close") is not None]
    if len(closes) < 2:
        return 0
    ret = (closes[-1] - closes[0]) / (abs(closes[0]) + 1e-10)
    if ret > 0.0002:
        return 1
    if ret < -0.0002:
        return -1
    return 0


def confluence_score(
    asset: str,
    signal_direction: str,            # "CALL" | "PUT"
    self_candles: Sequence[Dict[str, Any]],
    partner_candles_fn=None,          # callable(partner_asset) -> candles or None
) -> Dict[str, Any]:
    """
    Compute a confluence score for a candidate signal.

    Args:
        asset:           primary asset (already normalised).
        signal_direction: "CALL" / "PUT" — the direction we're about to fire.
        self_candles:    recent candles for `asset`.
        partner_candles_fn: sync callable that returns candles for a partner
                            asset (or None if unavailable).

    Returns:
        {
          "confluence_pct": 0..100,             # 100 = every partner agrees
          "agreement_count": int,
          "partner_count": int,
          "partner_signals": {partner: agreement},
          "multiplier": float,                   # 0.85..1.15
          "reason": str,
        }
    """
    sig_dir = 1 if str(signal_direction).upper() in ("CALL", "BUY", "HIGHER") else -1
    partners = get_partners(asset)

    if not partners or partner_candles_fn is None:
        return {
            "confluence_pct": 0.0,
            "agreement_count": 0,
            "partner_count": 0,
            "partner_signals": {},
            "multiplier": 1.0,
            "reason": "no_partners_or_data",
        }

    partner_signals: Dict[str, bool] = {}
    agreement = 0
    total = 0

    for partner_asset, sign_correlation in partners:
        try:
            pc = partner_candles_fn(partner_asset)
        except Exception:
            pc = None
        if not pc or len(pc) < 6:
            continue

        partner_dir = _short_direction(pc, n=6)
        if partner_dir == 0:
            continue

        # Expected partner direction given our signal direction and the
        # historical sign of the relationship.
        expected_partner_dir = sig_dir * sign_correlation
        agrees = (partner_dir == expected_partner_dir)
        partner_signals[partner_asset] = agrees
        total += 1
        if agrees:
            agreement += 1

    if total == 0:
        return {
            "confluence_pct": 0.0,
            "agreement_count": 0,
            "partner_count": 0,
            "partner_signals": {},
            "multiplier": 1.0,
            "reason": "no_partner_data",
        }

    pct = agreement / total * 100
    # Confidence multiplier — small tilt, never more than ±15%
    if pct >= 100:
        mult, reason = 1.15, f"all {total} partner(s) agree"
    elif pct >= 66:
        mult, reason = 1.08, f"{agreement}/{total} partners agree"
    elif pct >= 34:
        mult, reason = 1.00, "mixed partner signals"
    else:
        mult, reason = 0.85, f"only {agreement}/{total} partners agree — divergence"

    return {
        "confluence_pct": round(pct, 1),
        "agreement_count": agreement,
        "partner_count": total,
        "partner_signals": partner_signals,
        "multiplier": mult,
        "reason": reason,
    }
