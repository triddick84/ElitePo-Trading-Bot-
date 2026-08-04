"""
Microstructure signal filters — VPIN, Kyle's λ, order-flow imbalance.

Iter 86 (Jul 2026).

Purpose
-------
Adds three complementary microstructure signals derived from our own
executed-trade history (`tm_trade_reports`) + recent candles:

1. **VPIN** (Volume-Synchronized Probability of Informed Trading) proxy.
   Kyle/Easley/O'Hara-style: high VPIN → recent flow is dominated by
   directional/informed activity → higher adverse-selection risk → abstain.

2. **Kyle's λ (price impact)** proxy per asset.
   Estimated from the covariance of signed order flow with subsequent price
   moves. High λ → market is illiquid/informed, low λ → noise-trader camouflage
   dominates. We use λ as an **ensemble confidence multiplier**: extra weight
   in low-λ regimes, dampening in high-λ.

3. **Order-flow imbalance streak** — up-volume vs down-volume ratio over
   the last N bars. Sustained one-side flow signals momentum; alternating
   flow signals indecision.

Everything derived from data we already have — no order-book access required
(PO doesn't expose one anyway). Kept intentionally lightweight: no scipy /
statsmodels, pure numpy.

Design note
-----------
This is a **filter/gate** service, not a signal generator. It composes with
AccuracyEngine: a signal must pass BOTH gates before being surfaced to TM.
Different gates catch different pathologies:

    AccuracyEngine     — chronically-losing (asset, strategy) combos.
    Microstructure     — real-time regime toxicity + adverse-selection.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config (persistable via /api/microstructure/config, mirrors AccuracyEngine)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    # VPIN — window is measured in TRADE COUNT (not time) per Easley et al.
    "vpin_bucket_size": 20,          # trades per volume bucket
    "vpin_num_buckets": 20,          # rolling window (400 trades)
    "vpin_gate_threshold": 0.72,     # abstain when vpin > 0.72
    # Kyle λ
    "lambda_lookback": 100,          # trades used for the λ estimate
    "lambda_high_pct": 0.85,         # top 15% λ across assets = high impact
    # Order-flow imbalance
    "flow_streak_lookback": 30,      # bars
    # General
    "cache_ttl_seconds": 45,
    "gate_action": "abstain",        # "abstain" | "block"
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class MicrostructureStats:
    asset: str
    n_trades: int = 0
    vpin: float = 0.0                # 0..1 — higher = more toxic
    kyle_lambda: float = 0.0         # >0, higher = more informed impact
    flow_imbalance: float = 0.0      # -1..1, sign = direction, mag = strength
    flow_streak: int = 0             # consecutive same-side bars
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "n_trades": self.n_trades,
            "vpin": round(self.vpin, 4),
            "kyle_lambda": round(self.kyle_lambda, 6),
            "flow_imbalance": round(self.flow_imbalance, 3),
            "flow_streak": self.flow_streak,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Pure numeric primitives (unit-tested in isolation)
# ---------------------------------------------------------------------------
def normalize_asset(asset: Optional[str]) -> str:
    if not asset:
        return ""
    a = str(asset).strip().replace(" ", "").replace("/", "").upper()
    if a.endswith("OTC") and not a.endswith("_OTC"):
        a = a[:-3] + "_OTC"
    return a


def compute_vpin(
    outcomes: Sequence[str],
    bucket_size: int = 20,
    num_buckets: int = 20,
) -> float:
    """
    Volume-Synchronized Probability of Informed Trading (proxy for our
    single-trade context).

    Args:
        outcomes: newest-first sequence of "WIN"/"LOSS" (or "BUY"/"SELL")
                  outcomes for a given asset.
        bucket_size:  N trades per volume bucket.
        num_buckets:  # rolling buckets (window = bucket_size × num_buckets).

    Returns:
        VPIN ∈ [0, 1]. Higher = flow more one-sided/informed.

    Interpretation for binary options:
      • Bucket the last ~400 trades into 20 equal-size buckets.
      • Within each bucket, count buy-side vs sell-side imbalance.
      • VPIN = mean( |buys - sells| / bucket_size ) across buckets.
      • VPIN ≈ 0.5 is neutral; > 0.72 signals dangerous one-sided flow.
    """
    if not outcomes or bucket_size < 4 or num_buckets < 1:
        return 0.0

    total_needed = bucket_size * num_buckets
    sample = list(outcomes)[:total_needed]
    if len(sample) < bucket_size:
        return 0.0

    imbalances: List[float] = []
    for i in range(0, len(sample) - bucket_size + 1, bucket_size):
        bucket = sample[i:i + bucket_size]
        if len(bucket) < bucket_size:
            break
        # Encode outcomes as +1 (win/buy-side) or -1 (loss/sell-side)
        signed = [
            1 if str(x).upper() in ("WIN", "BUY", "CALL", "TRUE", "1") else -1
            for x in bucket
        ]
        # Bucket imbalance |Σsign| / N; normalises to [0, 1]
        imbalances.append(abs(sum(signed)) / len(bucket))

    if not imbalances:
        return 0.0
    return float(np.mean(imbalances))


def compute_kyle_lambda(
    signed_flow: Sequence[float],
    price_moves: Sequence[float],
) -> float:
    """
    Kyle's λ price-impact estimator: OLS regression of price move on
    signed order flow (or equivalent).

        Δprice_t = λ · signed_flow_t + noise

    We use trade-outcome direction as signed flow (+1 for buy-side win,
    -1 for sell-side win, etc.) and the subsequent short-horizon price
    move as Δprice. This is a *proxy* — with a real order book you'd use
    signed traded quantity.

    Returns:
        λ ≥ 0. Higher means each unit of signed flow moved the price more.
        Higher λ = more informed / less liquid market.
    """
    n = min(len(signed_flow), len(price_moves))
    if n < 8:
        return 0.0

    x = np.asarray(signed_flow[:n], dtype=float)
    y = np.asarray(price_moves[:n], dtype=float)

    if np.std(x) < 1e-9 or np.std(y) < 1e-9:
        return 0.0

    # OLS slope = Cov(x, y) / Var(x). Force ≥ 0 (sign is captured in flow).
    cov = float(np.mean(x * y) - np.mean(x) * np.mean(y))
    var_x = float(np.var(x))
    if var_x < 1e-12:
        return 0.0
    return max(0.0, abs(cov / var_x))


def compute_flow_imbalance(
    candles: Sequence[Dict[str, Any]],
    lookback: int = 30,
) -> Tuple[float, int]:
    """
    Order-flow-imbalance proxy from candles (no order book required).

    Uses close-vs-open direction weighted by volume — Chaikin-style flow.
    Returns:
        (imbalance ∈ [-1, +1], streak)
    """
    if not candles:
        return 0.0, 0

    window = list(candles)[-lookback:]
    up_v = 0.0
    dn_v = 0.0
    for c in window:
        o = float(c.get("open", 0.0))
        cl = float(c.get("close", 0.0))
        v = float(c.get("volume", 0.0)) or 1.0
        if cl > o:
            up_v += v
        elif cl < o:
            dn_v += v
    tot = up_v + dn_v
    imbalance = 0.0 if tot <= 0 else (up_v - dn_v) / tot

    # Streak = # consecutive bars of the same colour from the newest end
    streak = 0
    last_sign = 0
    for c in reversed(window):
        o = float(c.get("open", 0.0))
        cl = float(c.get("close", 0.0))
        s = 1 if cl > o else (-1 if cl < o else 0)
        if s == 0:
            break
        if last_sign == 0:
            last_sign = s
            streak = 1
        elif s == last_sign:
            streak += 1
        else:
            break

    return float(imbalance), streak


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------
class MicrostructureService:
    """Per-asset microstructure stats + filter decisions."""

    def __init__(self):
        self._cache: Dict[str, MicrostructureStats] = {}
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._last_refresh: float = 0.0
        self._lock = asyncio.Lock()
        self._db = None

    # --- DB ---------------------------------------------------------
    def _get_db(self):
        if self._db is None:
            from dotenv import load_dotenv
            from pathlib import Path
            from motor.motor_asyncio import AsyncIOMotorClient
            load_dotenv(Path(__file__).parent / ".env")
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            self._db = client[os.environ["DB_NAME"]]
        return self._db

    # --- config -----------------------------------------------------
    async def load_config(self) -> Dict[str, Any]:
        try:
            doc = await self._get_db().microstructure_config.find_one(
                {"_id": "default"}
            )
            if doc:
                for k in DEFAULT_CONFIG:
                    if k in doc:
                        self._config[k] = doc[k]
        except Exception as e:
            logger.debug(f"[microstructure] load_config skipped: {e}")
        return dict(self._config)

    async def save_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in patch.items():
            if k not in DEFAULT_CONFIG:
                continue
            default_v = DEFAULT_CONFIG[k]
            if isinstance(default_v, bool):
                self._config[k] = bool(v)
            elif isinstance(default_v, int):
                self._config[k] = int(v)
            elif isinstance(default_v, float):
                self._config[k] = float(v)
            else:
                self._config[k] = str(v)
        try:
            from datetime import datetime, timezone
            await self._get_db().microstructure_config.update_one(
                {"_id": "default"},
                {"$set": {**self._config,
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[microstructure] save_config skipped: {e}")
        return dict(self._config)

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    # --- refresh ----------------------------------------------------
    async def refresh(self, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        ttl = float(self._config.get("cache_ttl_seconds", 45))
        if not force and (now - self._last_refresh) < ttl and self._cache:
            return {"cached": True, "keys": len(self._cache)}

        async with self._lock:
            try:
                db = self._get_db()
                bucket_size = int(self._config["vpin_bucket_size"])
                num_buckets = int(self._config["vpin_num_buckets"])
                lambda_lookback = int(self._config["lambda_lookback"])

                # Pull recent trade reports (bounded) with outcome + confidence
                cursor = (
                    db.tm_trade_reports.find(
                        {"outcome": {"$in": ["WIN", "LOSS", "win", "loss"]}},
                        {
                            "_id": 0,
                            "asset_normalized": 1,
                            "asset": 1,
                            "direction": 1,
                            "outcome": 1,
                            "confidence": 1,
                            "server_received_at": 1,
                            "entry_price": 1,
                            "exit_price": 1,
                        },
                    )
                    .sort("server_received_at", -1)
                    .limit(8000)
                )

                by_asset: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                async for doc in cursor:
                    asset = (
                        doc.get("asset_normalized")
                        or normalize_asset(doc.get("asset"))
                    )
                    if not asset:
                        continue
                    by_asset[asset].append(doc)

                new_cache: Dict[str, MicrostructureStats] = {}
                for asset, trades in by_asset.items():
                    outcomes = [t.get("outcome") for t in trades]
                    # signed flow = trade direction as +1/-1
                    signed_flow = [
                        1.0 if str(t.get("direction", "")).upper() in ("CALL", "BUY", "HIGHER") else -1.0
                        for t in trades[:lambda_lookback]
                    ]
                    # price move = (exit - entry) / entry, with fallback 0
                    price_moves = []
                    for t in trades[:lambda_lookback]:
                        entry = float(t.get("entry_price") or 0.0)
                        exit_ = float(t.get("exit_price") or 0.0)
                        if entry > 0 and exit_ > 0:
                            price_moves.append((exit_ - entry) / entry)
                        else:
                            # Fallback: 1 for WIN, -1 for LOSS (still gives sign)
                            price_moves.append(
                                0.001 if str(t.get("outcome", "")).upper() == "WIN" else -0.001
                            )

                    vpin = compute_vpin(outcomes, bucket_size, num_buckets)
                    lam = compute_kyle_lambda(signed_flow, price_moves)

                    stats = MicrostructureStats(
                        asset=asset,
                        n_trades=len(trades),
                        vpin=vpin,
                        kyle_lambda=lam,
                    )
                    new_cache[asset] = stats

                self._cache = new_cache
                self._last_refresh = now
                return {"cached": False, "keys": len(self._cache), "refreshed_at": now}
            except Exception as exc:
                logger.warning(f"[microstructure] refresh failed: {exc}")
                return {"cached": False, "error": str(exc), "keys": len(self._cache)}

    async def invalidate(self) -> None:
        self._last_refresh = 0.0

    # --- lookups ----------------------------------------------------
    def get_stats(self, asset: str) -> Optional[MicrostructureStats]:
        return self._cache.get(normalize_asset(asset))

    async def get_stats_full(
        self, asset: str, candles: Optional[Sequence[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Fetch VPIN/λ from cache, compute live flow-imbalance from candles."""
        await self.refresh()
        entry = self.get_stats(asset)
        base = entry.to_dict() if entry else {
            "asset": normalize_asset(asset),
            "n_trades": 0,
            "vpin": 0.0,
            "kyle_lambda": 0.0,
            "cold_start": True,
        }
        if candles:
            imb, streak = compute_flow_imbalance(
                candles, int(self._config["flow_streak_lookback"])
            )
            base["flow_imbalance"] = round(imb, 3)
            base["flow_streak"] = streak
        return base

    # --- gate decision ---------------------------------------------
    async def should_gate(
        self, asset: str, candles: Optional[Sequence[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Decide whether a signal on `asset` should be gated by microstructure.

        Returns:
            {
              "gated": bool,
              "reason": str,
              "vpin": float,
              "kyle_lambda": float,
              "flow_imbalance": float,
              "flow_streak": int,
              "action": "abstain" | "block" | "pass",
            }
        """
        if not self._config.get("enabled", True):
            return {"gated": False, "reason": "engine_disabled", "action": "pass"}

        await self.refresh()
        vpin_thresh = float(self._config["vpin_gate_threshold"])
        action = str(self._config["gate_action"])

        entry = self.get_stats(asset)
        if entry is None or entry.n_trades < 30:
            # cold start — never gate
            return {
                "gated": False,
                "reason": "cold_start",
                "vpin": entry.vpin if entry else 0.0,
                "kyle_lambda": entry.kyle_lambda if entry else 0.0,
                "action": "pass",
                "vpin_threshold": vpin_thresh,
            }

        imb = 0.0
        streak = 0
        if candles:
            imb, streak = compute_flow_imbalance(
                candles, int(self._config["flow_streak_lookback"])
            )

        if entry.vpin > vpin_thresh:
            return {
                "gated": True,
                "reason": (
                    f"VPIN {entry.vpin:.2f} > threshold {vpin_thresh:.2f} — "
                    f"one-sided flow ({entry.n_trades} trades)"
                ),
                "vpin": entry.vpin,
                "kyle_lambda": entry.kyle_lambda,
                "flow_imbalance": imb,
                "flow_streak": streak,
                "action": action,
                "vpin_threshold": vpin_thresh,
            }

        return {
            "gated": False,
            "reason": (
                f"VPIN {entry.vpin:.2f} ≤ threshold {vpin_thresh:.2f} — "
                f"flow neutral"
            ),
            "vpin": entry.vpin,
            "kyle_lambda": entry.kyle_lambda,
            "flow_imbalance": imb,
            "flow_streak": streak,
            "action": "pass",
            "vpin_threshold": vpin_thresh,
        }

    # --- ensemble multiplier ---------------------------------------
    def confidence_multiplier(self, asset: str) -> float:
        """
        Multiplier ∈ [0.7, 1.15] to apply to ensemble confidence.

        High-λ (top decile) regimes → dampen confidence by up to 30%.
        Low-λ (bottom decile) regimes → boost confidence by up to 15%.
        """
        entry = self.get_stats(asset)
        if entry is None or entry.kyle_lambda <= 0:
            return 1.0

        # Cross-asset percentile of λ
        all_lambdas = [s.kyle_lambda for s in self._cache.values() if s.kyle_lambda > 0]
        if len(all_lambdas) < 5:
            return 1.0

        all_lambdas.sort()
        rank = sum(1 for x in all_lambdas if x <= entry.kyle_lambda)
        pct = rank / len(all_lambdas)

        if pct >= 0.90:
            return 0.70   # deep dampening — high adverse selection
        if pct >= 0.80:
            return 0.85
        if pct <= 0.10:
            return 1.15
        if pct <= 0.20:
            return 1.05
        return 1.0

    # --- introspection ---------------------------------------------
    def all_entries(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._cache.values()]

    def status(self) -> Dict[str, Any]:
        vt = float(self._config["vpin_gate_threshold"])
        toxic = [e for e in self._cache.values() if e.vpin > vt]
        return {
            "config": dict(self._config),
            "total_keys": len(self._cache),
            "toxic_keys": len(toxic),
            "last_refresh": self._last_refresh,
            "toxic_sample": [
                {"asset": e.asset, "vpin": round(e.vpin, 3),
                 "kyle_lambda": round(e.kyle_lambda, 6), "n": e.n_trades}
                for e in sorted(toxic, key=lambda x: -x.vpin)[:15]
            ],
        }


# Module-level singleton
microstructure = MicrostructureService()
