"""
AccuracyEngine — rolling per-(asset, strategy) win-rate tracker for signal gating.

Purpose
-------
Every trade the TM script fires is reported back via `POST /api/trades/report`
with the strategy that generated it and its WIN/LOSS outcome. AccuracyEngine
aggregates those outcomes into a rolling win-rate per (asset, strategy) pair
and exposes a `should_gate()` decision function that `/api/signals/latest`
calls before returning a signal.

If a (asset, strategy) combo has fired ≥ `min_trades_for_gating` trades and
its rolling win-rate is below `min_win_rate_pct`, the next signal from that
combo is flagged `abstain=True` with `abstain_source="accuracy_engine"` so the
TM script can safely skip it.

Cold-start safe: combos with fewer than `min_trades_for_gating` samples are
NEVER gated (returns `gated=False, reason="cold_start"`).

State
-----
- **Cache**: dict keyed by `(asset_normalized, strategy_normalized)` → dict
  `{win_rate, n_trades, wins, losses, last_updated, sample_size_ok}`.
- **TTL**: cache refreshes every `cache_ttl_seconds` (default 60s) OR
  immediately when `invalidate()` is called from `/trades/report`.
- **Config**: persisted in Mongo `accuracy_engine_config` collection so admin
  can tweak thresholds without redeploy.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "min_trades_for_gating": 8,          # need ≥ N outcomes before gating
    "min_win_rate_pct": 45.0,            # combos below this get gated
    "rolling_window": 30,                # most recent N trades per (asset, strategy)
    "cache_ttl_seconds": 60,             # in-memory cache refresh interval
    "gate_action": "abstain",            # "abstain" (default) | "block" (drop signal entirely)
}


# ---------------------------------------------------------------------------
# Normalisation helpers — must match what routes/signals.py stores
# ---------------------------------------------------------------------------
def normalize_asset(asset: Optional[str]) -> str:
    if not asset:
        return ""
    a = str(asset).strip().replace(" ", "").replace("/", "").upper()
    if a.endswith("OTC") and not a.endswith("_OTC"):
        a = a[:-3] + "_OTC"
    return a


def normalize_strategy(strategy: Optional[str]) -> str:
    if not strategy:
        return "unknown"
    return str(strategy).strip().lower().replace(" ", "_")


def _outcome_to_win(outcome: Any) -> Optional[bool]:
    """Coerce a raw outcome field to a strict bool. None if unclear."""
    if isinstance(outcome, bool):
        return outcome
    if isinstance(outcome, str):
        up = outcome.upper()
        if up in ("WIN", "TRUE", "1"):
            return True
        if up in ("LOSS", "LOSE", "FALSE", "0"):
            return False
    return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class AccuracyEntry:
    asset: str
    strategy: str
    n_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "strategy": self.strategy,
            "n_trades": self.n_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 2),
            "last_updated": self.last_updated,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class AccuracyEngine:
    """Rolling per-(asset, strategy) win-rate + signal gate."""

    def __init__(self):
        self._cache: Dict[Tuple[str, str], AccuracyEntry] = {}
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._last_full_refresh: float = 0.0
        self._lock = asyncio.Lock()
        self._db = None

    # --- lazy DB handle so import stays cheap ------------------------------
    def _get_db(self):
        if self._db is None:
            # Load .env explicitly to match routes/__init__.py behaviour so
            # we hit the same physical database as /trades/report writes to.
            from dotenv import load_dotenv
            from pathlib import Path
            load_dotenv(Path(__file__).parent / ".env")
            mongo_url = os.environ["MONGO_URL"]
            db_name = os.environ["DB_NAME"]
            client = AsyncIOMotorClient(mongo_url)
            self._db = client[db_name]
        return self._db

    # --- config -----------------------------------------------------------
    async def load_config(self) -> Dict[str, Any]:
        try:
            db = self._get_db()
            doc = await db.accuracy_engine_config.find_one({"_id": "default"})
            if doc:
                for k, default_val in DEFAULT_CONFIG.items():
                    if k in doc:
                        self._config[k] = doc[k]
        except Exception as exc:
            logger.warning("[AccuracyEngine] load_config failed: %s", exc)
        return dict(self._config)

    async def save_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        # Only accept known keys with valid types
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
            db = self._get_db()
            await db.accuracy_engine_config.update_one(
                {"_id": "default"},
                {"$set": {**self._config, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("[AccuracyEngine] save_config persist failed: %s", exc)
        return dict(self._config)

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    # --- refresh ----------------------------------------------------------
    async def refresh(self, force: bool = False) -> Dict[str, Any]:
        """
        Rebuild the in-memory cache from `tm_trade_reports`. Idempotent.
        Called by the periodic scheduler and by `/trades/report` on new outcomes.
        """
        now = time.time()
        ttl = float(self._config.get("cache_ttl_seconds", 60))
        if not force and (now - self._last_full_refresh) < ttl and self._cache:
            return {"cached": True, "keys": len(self._cache)}

        async with self._lock:
            try:
                db = self._get_db()
                window = int(self._config.get("rolling_window", 30))

                # Pull the last 5 000 outcome-tagged trade reports (bounded).
                # We aggregate client-side into per-(asset, strategy) deques.
                cursor = (
                    db.tm_trade_reports.find(
                        {"outcome": {"$in": ["WIN", "LOSS", "win", "loss", True, False]}},
                        {
                            "_id": 0,
                            "outcome": 1,
                            "asset_normalized": 1,
                            "asset": 1,
                            "strategy": 1,
                            "server_received_at": 1,
                        },
                    )
                    .sort("server_received_at", -1)
                    .limit(5000)
                )

                buckets: Dict[Tuple[str, str], deque] = defaultdict(
                    lambda: deque(maxlen=window)
                )
                async for doc in cursor:
                    asset = doc.get("asset_normalized") or normalize_asset(doc.get("asset"))
                    strategy = normalize_strategy(doc.get("strategy"))
                    if not asset:
                        continue
                    win = _outcome_to_win(doc.get("outcome"))
                    if win is None:
                        continue
                    # docs are newest-first — deque holds `window` newest samples
                    buckets[(asset, strategy)].append(win)

                new_cache: Dict[Tuple[str, str], AccuracyEntry] = {}
                for (asset, strategy), samples in buckets.items():
                    n = len(samples)
                    wins = sum(1 for s in samples if s)
                    losses = n - wins
                    wr = (wins / n) * 100 if n else 0.0
                    new_cache[(asset, strategy)] = AccuracyEntry(
                        asset=asset,
                        strategy=strategy,
                        n_trades=n,
                        wins=wins,
                        losses=losses,
                        win_rate=wr,
                    )

                self._cache = new_cache
                self._last_full_refresh = now
                return {"cached": False, "keys": len(self._cache), "refreshed_at": now}
            except Exception as exc:
                logger.warning("[AccuracyEngine] refresh failed: %s", exc)
                return {"cached": False, "error": str(exc), "keys": len(self._cache)}

    async def invalidate(self) -> None:
        """Force next refresh call to rebuild — used from /trades/report."""
        self._last_full_refresh = 0.0

    # --- lookups ----------------------------------------------------------
    def get_entry(self, asset: str, strategy: str) -> Optional[AccuracyEntry]:
        return self._cache.get((normalize_asset(asset), normalize_strategy(strategy)))

    async def get_stats(self, asset: str, strategy: str) -> Dict[str, Any]:
        await self.refresh()  # respects TTL
        entry = self.get_entry(asset, strategy)
        if entry is None:
            return {
                "asset": normalize_asset(asset),
                "strategy": normalize_strategy(strategy),
                "n_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": None,
                "cold_start": True,
            }
        d = entry.to_dict()
        d["cold_start"] = entry.n_trades < int(self._config.get("min_trades_for_gating", 8))
        return d

    # --- gate decision ----------------------------------------------------
    async def should_gate(
        self, asset: str, strategy: str
    ) -> Dict[str, Any]:
        """
        Decide whether a signal for this (asset, strategy) should be gated.

        Returns:
            {
              "gated": bool,
              "reason": str,           # human-readable
              "win_rate": float|None,  # % over rolling window, or None if cold
              "n_trades": int,
              "action": str,           # "abstain" | "block" | "pass"
              "threshold_wr": float,
            }
        """
        if not self._config.get("enabled", True):
            return {
                "gated": False,
                "reason": "engine_disabled",
                "win_rate": None,
                "n_trades": 0,
                "action": "pass",
                "threshold_wr": float(self._config.get("min_win_rate_pct", 45.0)),
            }

        await self.refresh()

        min_trades = int(self._config.get("min_trades_for_gating", 8))
        min_wr = float(self._config.get("min_win_rate_pct", 45.0))
        action = str(self._config.get("gate_action", "abstain"))
        threshold_wr = min_wr

        entry = self.get_entry(asset, strategy)
        if entry is None or entry.n_trades < min_trades:
            return {
                "gated": False,
                "reason": "cold_start",
                "win_rate": entry.win_rate if entry else None,
                "n_trades": entry.n_trades if entry else 0,
                "action": "pass",
                "threshold_wr": threshold_wr,
            }

        if entry.win_rate < min_wr:
            return {
                "gated": True,
                "reason": (
                    f"win_rate {entry.win_rate:.1f}% < threshold {min_wr:.1f}% "
                    f"over last {entry.n_trades} trades"
                ),
                "win_rate": entry.win_rate,
                "n_trades": entry.n_trades,
                "action": action,
                "threshold_wr": threshold_wr,
            }

        return {
            "gated": False,
            "reason": (
                f"win_rate {entry.win_rate:.1f}% ≥ threshold {min_wr:.1f}% "
                f"over last {entry.n_trades} trades"
            ),
            "win_rate": entry.win_rate,
            "n_trades": entry.n_trades,
            "action": "pass",
            "threshold_wr": threshold_wr,
        }

    # --- introspection ----------------------------------------------------
    def all_entries(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._cache.values()]

    def status(self) -> Dict[str, Any]:
        gated = [
            e for e in self._cache.values()
            if e.n_trades >= int(self._config.get("min_trades_for_gating", 8))
            and e.win_rate < float(self._config.get("min_win_rate_pct", 45.0))
        ]
        active = [
            e for e in self._cache.values()
            if e.n_trades >= int(self._config.get("min_trades_for_gating", 8))
        ]
        return {
            "config": dict(self._config),
            "total_keys": len(self._cache),
            "active_keys": len(active),
            "gated_keys": len(gated),
            "last_refresh": self._last_full_refresh,
            "gated_sample": [
                {"asset": e.asset, "strategy": e.strategy,
                 "win_rate": round(e.win_rate, 2), "n": e.n_trades}
                for e in gated[:20]
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
accuracy_engine = AccuracyEngine()
