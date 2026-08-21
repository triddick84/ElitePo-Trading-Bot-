"""
Microstructure Models Service — Iter 105 (Feb 2026)

Two classical market-microstructure models exposed as REST endpoints for
diagnostic + signal-confidence adjustment:

1. **Kyle (1985)** — Linear equilibrium price-impact model.
     Informed trader observes V ~ N(μ, σ_v²), noise u ~ N(0, σ_u²),
     order flow y = x + u, price P = μ + λy.
     Equilibrium: λ = σ_v / (2·σ_u),   β = σ_u / σ_v.
     Informed profit = σ_v·σ_u / 2.

2. **Glosten-Milgrom (1985)** — Sequential-trade spread model.
     Given priors of high (V_H) vs low (V_L) value, informed-trader
     probability α, and Bayesian quote updates:
       Ask = E[V | buy_next],   Bid = E[V | sell_next]
     Spread compensates for adverse selection.

Inputs (per asset):
  • Recent OHLC candles or trade tape (via microstructure singleton's
    existing data plumbing).
  • Estimated σ_v (informed variance) from candle close-return std over
    N bars, σ_u (noise variance) as the residual after subtracting the
    signed-flow-explained part.
  • For GM: prior high/low values from BB(2σ), α from the fraction of
    same-side trades in the recent bucket.

Design:
  • Pure numpy — no scipy / statsmodels.
  • Deterministic given inputs (no randomness).
  • Bounded output: all probabilities ∈ [0,1], λ ≥ 0.
  • Safe under thin data — returns "insufficient_data" reason and neutral
    values rather than raising.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure math primitives
# ---------------------------------------------------------------------------
@dataclass
class KyleModelResult:
    lambda_: float          # price-impact coefficient (illiquidity)
    beta: float             # informed trader intensity σ_u / σ_v
    sigma_v: float          # signal variance (informed uncertainty)
    sigma_u: float          # noise trader variance
    informed_profit: float  # σ_v · σ_u / 2
    illiquidity_bps: float  # λ scaled to basis points of mid price
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lambda": round(self.lambda_, 8),
            "beta": round(self.beta, 6),
            "sigma_v": round(self.sigma_v, 8),
            "sigma_u": round(self.sigma_u, 8),
            "informed_profit": round(self.informed_profit, 8),
            "illiquidity_bps": round(self.illiquidity_bps, 4),
            "interpretation": self.interpretation,
        }


@dataclass
class GlostenMilgromResult:
    v_high: float           # Bayesian expectation of V | buy
    v_low: float            # Bayesian expectation of V | sell
    ask: float              # equal to v_high in the risk-neutral quote
    bid: float              # equal to v_low
    spread_abs: float
    spread_bps: float
    alpha_informed: float   # fraction of informed traders (input parameter)
    p_high_prior: float     # prior P(V = V_H)
    adverse_selection_pct: float  # % of spread attributed to informed flow
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v_high": round(self.v_high, 8),
            "v_low": round(self.v_low, 8),
            "ask": round(self.ask, 8),
            "bid": round(self.bid, 8),
            "spread_abs": round(self.spread_abs, 8),
            "spread_bps": round(self.spread_bps, 4),
            "alpha_informed": round(self.alpha_informed, 4),
            "p_high_prior": round(self.p_high_prior, 4),
            "adverse_selection_pct": round(self.adverse_selection_pct, 3),
            "interpretation": self.interpretation,
        }


def compute_kyle_from_returns(
    log_returns: Sequence[float],
    signed_flow: Sequence[float],
    mid_price: Optional[float] = None,
) -> KyleModelResult:
    """
    Estimate Kyle-model parameters from a recent window.

    Args:
        log_returns:  Δlog(price) per bar — proxy for value-signal moves.
        signed_flow:  +1 (buy pressure) / -1 (sell pressure) per bar,
                      already aligned in time with log_returns.
        mid_price:    optional current price used to scale λ to bps.

    Returns:
        KyleModelResult with λ, β, σ_v, σ_u, informed profit, interpretation.
    """
    n = min(len(log_returns), len(signed_flow))
    if n < 20:
        return KyleModelResult(
            lambda_=0.0, beta=0.0, sigma_v=0.0, sigma_u=0.0,
            informed_profit=0.0, illiquidity_bps=0.0,
            interpretation="insufficient_data",
        )

    r = np.asarray(log_returns[:n], dtype=float)
    x = np.asarray(signed_flow[:n], dtype=float)

    if np.std(r) < 1e-9 or np.std(x) < 1e-9:
        return KyleModelResult(
            lambda_=0.0, beta=0.0, sigma_v=0.0, sigma_u=0.0,
            informed_profit=0.0, illiquidity_bps=0.0,
            interpretation="flat_data",
        )

    # σ_v — total return volatility over the window (unit = log-return).
    sigma_v = float(np.std(r))
    # σ_u — order-flow volatility (unit = same as x, i.e. dimensionless ±1).
    sigma_u = float(np.std(x))
    # Kyle equilibrium: λ = σ_v / (2·σ_u). β = σ_u / σ_v.
    lambda_ = sigma_v / (2.0 * sigma_u) if sigma_u > 1e-9 else 0.0
    beta = sigma_u / sigma_v if sigma_v > 1e-9 else 0.0
    informed_profit = 0.5 * sigma_v * sigma_u

    # Scale λ to bps of the current mid so the trader can compare across pairs
    illiquidity_bps = 0.0
    if mid_price is not None and mid_price > 0 and lambda_ > 0:
        illiquidity_bps = float(lambda_ * 10_000.0)  # already in returns/flow-unit

    # Interpretation buckets
    if illiquidity_bps == 0.0 or lambda_ == 0.0:
        interp = "no_impact"
    elif illiquidity_bps < 5:
        interp = "low_impact (liquid)"
    elif illiquidity_bps < 15:
        interp = "moderate_impact"
    else:
        interp = "high_impact (informed / illiquid)"

    return KyleModelResult(
        lambda_=lambda_, beta=beta, sigma_v=sigma_v, sigma_u=sigma_u,
        informed_profit=informed_profit,
        illiquidity_bps=illiquidity_bps,
        interpretation=interp,
    )


def compute_glosten_milgrom(
    v_center: float,
    v_high: float,
    v_low: float,
    alpha_informed: float,
    p_high_prior: float = 0.5,
) -> GlostenMilgromResult:
    """
    Compute GM ask/bid quotes given:
      • v_center: mid or expected value (e.g. current mid or SMA)
      • v_high, v_low: high/low value scenarios (e.g. Bollinger ±2σ bands)
      • alpha_informed ∈ [0,1]: probability the next trader is informed
      • p_high_prior ∈ [0,1]: prior P(V = v_high)

    Model math (with π = p_high_prior, α = alpha_informed):
      P(buy | V_H) = α·1 + (1-α)·½ = ½ + ½α
      P(buy | V_L) = (1-α)·½       = ½ − ½α
      P(buy)      = π·P(buy|V_H) + (1-π)·P(buy|V_L)
      P(V_H|buy)  = π·P(buy|V_H) / P(buy)
      E[V|buy]    = P(V_H|buy)·V_H + (1 − P(V_H|buy))·V_L      → Ask
      E[V|sell]   = symmetric with sell probabilities            → Bid
      Spread      = Ask − Bid

    Returns:
        GlostenMilgromResult with quotes, spread, adverse-selection %.
    """
    # Guard rails
    alpha = float(max(0.0, min(1.0, alpha_informed)))
    pi = float(max(0.001, min(0.999, p_high_prior)))
    if v_high <= v_low:
        return GlostenMilgromResult(
            v_high=v_high, v_low=v_low, ask=v_center, bid=v_center,
            spread_abs=0.0, spread_bps=0.0,
            alpha_informed=alpha, p_high_prior=pi,
            adverse_selection_pct=0.0,
            interpretation="degenerate_prices (v_high <= v_low)",
        )

    p_buy_given_h = 0.5 + 0.5 * alpha
    p_buy_given_l = 0.5 - 0.5 * alpha
    p_sell_given_h = 1.0 - p_buy_given_h
    p_sell_given_l = 1.0 - p_buy_given_l

    p_buy = pi * p_buy_given_h + (1 - pi) * p_buy_given_l
    p_sell = pi * p_sell_given_h + (1 - pi) * p_sell_given_l

    if p_buy < 1e-9:
        p_h_given_buy = pi
    else:
        p_h_given_buy = pi * p_buy_given_h / p_buy
    if p_sell < 1e-9:
        p_h_given_sell = pi
    else:
        p_h_given_sell = pi * p_sell_given_h / p_sell

    ask = p_h_given_buy * v_high + (1 - p_h_given_buy) * v_low
    bid = p_h_given_sell * v_high + (1 - p_h_given_sell) * v_low
    spread = max(0.0, ask - bid)
    spread_bps = 0.0 if v_center <= 0 else spread / v_center * 10_000.0

    # Adverse-selection %: proportion of the spread attributable to informed
    # trading. When α=0, spread=0 → 0%. When α=1, spread = v_high − v_low → 100%.
    max_spread = v_high - v_low
    adv_pct = 0.0 if max_spread <= 0 else 100.0 * spread / max_spread

    if alpha <= 0.05:
        interp = "no_adverse_selection (mostly noise traders)"
    elif alpha < 0.30:
        interp = "moderate_adverse_selection"
    elif alpha < 0.60:
        interp = "high_adverse_selection"
    else:
        interp = "toxic_flow (mostly informed)"

    return GlostenMilgromResult(
        v_high=v_high, v_low=v_low, ask=ask, bid=bid,
        spread_abs=spread, spread_bps=spread_bps,
        alpha_informed=alpha, p_high_prior=pi,
        adverse_selection_pct=adv_pct,
        interpretation=interp,
    )


# ---------------------------------------------------------------------------
# Data adapters — pull inputs from PO candle cache and produce model results
# ---------------------------------------------------------------------------
async def kyle_for_asset(asset: str, candles: Optional[List[Dict[str, Any]]] = None,
                         lookback: int = 60) -> Dict[str, Any]:
    """
    Compute Kyle-model result for an asset.

    Pulls the most recent `lookback` candles from `microstructure_service`'s
    candle cache (falls back to what the caller provides). Derives:
      • log_returns  = Δlog(close)
      • signed_flow  = sign(close - open), i.e. bar-body direction
    """
    if candles is None:
        try:
            from microstructure import microstructure  # existing singleton
            candles = await _fetch_recent_candles(microstructure, asset, lookback)
        except Exception as e:
            logger.debug("[kyle] fallback fetch failed: %s", e)
            candles = []

    if not candles or len(candles) < 20:
        return {"success": False, "reason": "insufficient_data",
                "asset": asset, "n_candles": len(candles) if candles else 0}

    closes = np.array([float(c.get("close", 0.0)) for c in candles], dtype=float)
    opens = np.array([float(c.get("open", 0.0)) for c in candles], dtype=float)
    # Skip zeros / non-positive prices before taking log
    mask = (closes > 0) & (opens > 0)
    closes = closes[mask]
    opens = opens[mask]
    if len(closes) < 20:
        return {"success": False, "reason": "insufficient_valid_candles",
                "asset": asset, "n_candles": len(closes)}

    log_returns = np.diff(np.log(closes))
    signed_flow = np.sign(closes[1:] - opens[1:])  # align w/ log_returns

    mid = float(closes[-1])
    result = compute_kyle_from_returns(log_returns.tolist(), signed_flow.tolist(),
                                       mid_price=mid)
    return {"success": True, "asset": asset, "mid_price": mid,
            "n_candles": int(len(closes)),
            "kyle": result.to_dict()}


async def glosten_milgrom_for_asset(
    asset: str,
    candles: Optional[List[Dict[str, Any]]] = None,
    lookback: int = 40,
    alpha_informed: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute GM model result. Estimates:
      • v_center = SMA(close, lookback)
      • v_high, v_low = Bollinger ±2σ bands
      • alpha_informed defaults to fraction of same-side bar bodies in the
        last `lookback` bars (a proxy for informed one-sided flow)
      • p_high_prior = last close position within the BB band, clipped
    """
    if candles is None:
        try:
            from microstructure import microstructure
            candles = await _fetch_recent_candles(microstructure, asset, lookback)
        except Exception as e:
            logger.debug("[gm] fallback fetch failed: %s", e)
            candles = []

    if not candles or len(candles) < 20:
        return {"success": False, "reason": "insufficient_data",
                "asset": asset, "n_candles": len(candles) if candles else 0}

    closes = np.array([float(c.get("close", 0.0)) for c in candles], dtype=float)
    opens = np.array([float(c.get("open", 0.0)) for c in candles], dtype=float)
    valid = (closes > 0) & (opens > 0)
    closes = closes[valid]
    opens = opens[valid]
    if len(closes) < 20:
        return {"success": False, "reason": "insufficient_valid_candles",
                "asset": asset, "n_candles": int(len(closes))}

    v_center = float(np.mean(closes[-lookback:]))
    sd = float(np.std(closes[-lookback:]))
    v_high = v_center + 2.0 * sd
    v_low = max(1e-9, v_center - 2.0 * sd)

    # Prior P(V=v_high) — where does the last close sit inside the ±2σ band?
    last = float(closes[-1])
    if v_high > v_low:
        pi = (last - v_low) / (v_high - v_low)
    else:
        pi = 0.5
    pi = max(0.05, min(0.95, pi))

    # α estimate — fraction of same-side bodies in the last lookback bars.
    # 0.5 means perfectly balanced (all noise); 1.0 means one-sided.
    signs = np.sign(closes[-lookback:] - opens[-lookback:])
    n_up = int(np.sum(signs > 0))
    n_dn = int(np.sum(signs < 0))
    tot = max(1, n_up + n_dn)
    dominant_pct = max(n_up, n_dn) / tot  # 0.5..1.0
    # Map to α ∈ [0, 1]: 50% one-sided → α=0, 100% one-sided → α=1
    alpha_est = float(max(0.0, min(1.0, 2 * (dominant_pct - 0.5))))
    if alpha_informed is not None:
        alpha_est = float(max(0.0, min(1.0, alpha_informed)))

    result = compute_glosten_milgrom(v_center, v_high, v_low, alpha_est, pi)
    return {"success": True, "asset": asset,
            "n_candles": int(len(closes)),
            "mid_price": last,
            "sma": v_center,
            "n_up_bars": n_up, "n_down_bars": n_dn,
            "gm": result.to_dict()}


async def _fetch_recent_candles(microstructure_svc, asset: str, n: int) -> List[Dict[str, Any]]:
    """Best-effort candle fetch — tries the microstructure service's cache
    first, then falls back to the OTC candle collection in MongoDB.

    Iter 111 — `otc_candles_5s` stores rows under the `symbol` field (NOT
    `asset`). Previous code queried the wrong field and every asset came
    back empty. Now we try both fields with case variants so both the Elite
    Screener and the Microstructure Dashboard actually see live data.
    """
    try:
        import os
        mongo_url = os.environ.get("MONGO_URL")
        if not mongo_url:
            return []
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        db_name = os.environ.get("DB_NAME", "trading_bot")
        db = client[db_name]

        # Build name variants: with / without _OTC suffix, upper / lower case
        base = asset.upper()
        stripped = base.replace("_OTC", "")
        variants = list(dict.fromkeys([
            asset, base, base.lower(),
            stripped, stripped + "_OTC",
            (stripped + "_OTC").lower(),
        ]))

        # otc_candles_5s uses `symbol` field (populated by realtime OTC
        # collector + auto-retrain scheduler + BotAI simulator).
        cursor = db.otc_candles_5s.find(
            {"symbol": {"$in": variants}}
        ).sort("timestamp", -1).limit(n)
        docs = await cursor.to_list(length=n)

        # Legacy: some older docs used `asset` — fall through if none matched
        if not docs:
            cursor2 = db.otc_candles_5s.find(
                {"asset": {"$in": variants}}
            ).sort("timestamp", -1).limit(n)
            docs = await cursor2.to_list(length=n)

        # Also fall back to `historical_candles` (asset+timeframe schema)
        # so 1m/5m data trained by the ML pipeline is reusable here.
        if not docs:
            cursor3 = db.historical_candles.find(
                {"asset": {"$in": variants}}
            ).sort("timestamp", -1).limit(n)
            docs = await cursor3.to_list(length=n)

        # Normalise timestamps: Kyle/GM expects Unix seconds (int/float).
        # otc_candles_5s stores ISO strings, historical_candles stores int.
        from datetime import datetime as _dt
        norm: List[Dict[str, Any]] = []
        for d in docs:
            ts = d.get("timestamp")
            if hasattr(ts, "timestamp"):
                ts_num = float(ts.timestamp())
            elif isinstance(ts, str):
                try:
                    ts_num = float(_dt.fromisoformat(
                        ts.replace("Z", "+00:00")).timestamp())
                except Exception:
                    continue
            elif isinstance(ts, (int, float)):
                ts_num = float(ts)
            else:
                continue
            norm.append({
                "timestamp": ts_num,
                "open":   d.get("open"),
                "high":   d.get("high"),
                "low":    d.get("low"),
                "close":  d.get("close"),
                "volume": d.get("volume", 0),
            })
        norm.reverse()  # oldest first
        return norm
    except Exception:
        return []
