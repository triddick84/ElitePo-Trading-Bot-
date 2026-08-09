"""
Signal Pre-generation Buffer — Iter 89.

Purpose
-------
`/api/signals/latest` was doing 3 potentially-slow things on every TM poll:
  1. Mongo find_one on `trading_signals` (fast, ~5-20ms).
  2. `enhanced_oanda.generate_trend_signal(...)` when latest signal is stale
     (SLOW — 300-1500ms because it fetches candles + runs TA).
  3. AccuracyEngine / Microstructure / Latency / Pair-Confluence decorators.

By pre-computing (2) in a background loop for the top-N most-active
(asset, timeframe) combos and stashing the result in an in-memory dict,
we can serve `/signals/latest` in ~5-30ms even when the DB is empty for
that asset — a 300-1500ms saving per fire.

Design
------
* In-memory (single-process, single-node). No Redis dependency — we run in
  one FastAPI worker. Bounded to top 50 combos to keep RAM tiny.
* TTL default 3s. Configurable via env `SIGNAL_PREWARM_TTL_SECONDS`.
* Refresh cadence: every 2s for combos that appeared in a `/signals/latest`
  call in the last 30s (LRU tracking).
* Falls back cleanly: if the prewarm loop crashes or hasn't populated for a
  given (asset, tf), `/signals/latest` uses its existing DB-or-generate path.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

TTL_SECONDS = float(os.environ.get("SIGNAL_PREWARM_TTL_SECONDS", "3.0"))
REFRESH_INTERVAL_SECONDS = float(os.environ.get("SIGNAL_PREWARM_REFRESH_SECONDS", "2.0"))
ACTIVE_WINDOW_SECONDS = float(os.environ.get("SIGNAL_PREWARM_ACTIVE_WINDOW_SECONDS", "30.0"))
MAX_TRACKED_COMBOS = int(os.environ.get("SIGNAL_PREWARM_MAX_COMBOS", "50"))


@dataclass
class _Entry:
    signal: Dict[str, Any]
    generated_at: float  # monotonic seconds
    generator: str  # "enhanced_oanda" | "force_v2" | "external"

    def age_seconds(self) -> float:
        return time.monotonic() - self.generated_at

    def is_fresh(self, ttl: Optional[float] = None) -> bool:
        eff = TTL_SECONDS if ttl is None else ttl
        return self.age_seconds() < eff


class SignalPrewarmBuffer:
    """
    Small in-memory buffer keyed by (asset_upper, timeframe).

    Public surface:
      - .get(asset, tf) → Optional[dict]  (only if fresh)
      - .set(asset, tf, signal, generator)
      - .touch(asset, tf)                 (mark active — LRU tracking)
      - .stats() → dict                    (for /latency dashboard)
    """

    def __init__(self) -> None:
        self._buf: Dict[Tuple[str, str], _Entry] = {}
        # LRU tracking: (asset, tf) → last-touched monotonic timestamp
        self._touched: Dict[Tuple[str, str], float] = {}
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def _norm(asset: str, tf: Optional[str]) -> Tuple[str, str]:
        a = (asset or "").strip().upper()
        # Normalise "EURUSD_OTC" / "EURUSDOTC" / "EURUSD_otc"
        if a.endswith("OTC") and not a.endswith("_OTC"):
            a = a[:-3] + "_OTC"
        t = (tf or "5s").strip().lower()
        return (a, t)

    def touch(self, asset: str, tf: Optional[str]) -> None:
        key = self._norm(asset, tf)
        self._touched[key] = time.monotonic()
        # Cap tracked combos — evict oldest touch
        if len(self._touched) > MAX_TRACKED_COMBOS:
            oldest = min(self._touched.items(), key=lambda kv: kv[1])[0]
            self._touched.pop(oldest, None)

    def get(self, asset: str, tf: Optional[str]) -> Optional[Dict[str, Any]]:
        key = self._norm(asset, tf)
        entry = self._buf.get(key)
        if entry is None:
            self._misses += 1
            return None
        if not entry.is_fresh():
            self._misses += 1
            return None
        self._hits += 1
        # Return a shallow copy so callers can mutate without polluting cache
        return dict(entry.signal)

    def set(self, asset: str, tf: Optional[str], signal: Dict[str, Any],
            generator: str = "unknown") -> None:
        if not signal or not isinstance(signal, dict):
            return
        key = self._norm(asset, tf)
        self._buf[key] = _Entry(signal=signal, generated_at=time.monotonic(),
                                generator=generator)
        self._writes += 1
        # Cap buffer size — evict oldest by generated_at
        if len(self._buf) > MAX_TRACKED_COMBOS:
            oldest_key = min(self._buf.items(),
                             key=lambda kv: kv[1].generated_at)[0]
            self._buf.pop(oldest_key, None)

    def active_combos(self) -> list:
        """Return combos touched within ACTIVE_WINDOW_SECONDS."""
        now = time.monotonic()
        cutoff = now - ACTIVE_WINDOW_SECONDS
        return [k for k, ts in self._touched.items() if ts >= cutoff]

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._buf),
            "tracked_active": len(self._touched),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(100.0 * self._hits / max(1, total), 2),
            "writes": self._writes,
            "ttl_seconds": TTL_SECONDS,
            "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
            "entries": [
                {
                    "asset": a, "timeframe": tf,
                    "age_sec": round(entry.age_seconds(), 2),
                    "generator": entry.generator,
                    "direction": entry.signal.get("direction"),
                    "confidence": entry.signal.get("confidence"),
                }
                for (a, tf), entry in list(self._buf.items())[:20]
            ],
        }


# Singleton
_buffer: Optional[SignalPrewarmBuffer] = None


def get_buffer() -> SignalPrewarmBuffer:
    global _buffer
    if _buffer is None:
        _buffer = SignalPrewarmBuffer()
    return _buffer


# ---------------------------------------------------------------------------
# Background refresher — runs one loop per FastAPI worker.
# ---------------------------------------------------------------------------
_refresh_task: Optional[asyncio.Task] = None


async def _refresh_one(asset: str, tf: str) -> None:
    """Try to pre-generate a signal for (asset, tf) and stash it."""
    try:
        # Late import to avoid circular reference at module load.
        from enhanced_oanda_service import enhanced_oanda
        if not getattr(enhanced_oanda, "is_configured", False):
            return
        # Convert to OANDA format
        raw = asset.replace("_OTC", "").replace("OTC", "")
        if "_" not in raw and len(raw) == 6:
            oanda_asset = f"{raw[:3]}_{raw[3:]}"
        else:
            oanda_asset = raw
        # Map our short-TF codes to OANDA TFs the generator understands.
        # `generate_trend_signal` accepts M1/M5/etc; for sub-minute we still
        # ask M1 (cheapest signal that fits the freshness budget).
        signal = enhanced_oanda.generate_trend_signal(oanda_asset, "M1")
        if not signal or getattr(signal, "recommended_action", "HOLD") == "HOLD":
            return
        # Build the same shape `/signals/latest` returns
        from datetime import datetime, timezone
        payload = {
            "id": f"PREWARM_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S%f')}_{oanda_asset}",
            "symbol": oanda_asset.replace("_", ""),
            "asset": oanda_asset.replace("_", ""),
            "direction": signal.recommended_action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": float(getattr(signal, "confidence", 60)),
            "probability": float(getattr(signal, "confidence", 60)),
            "strategy": "prewarm_enhanced_oanda",
            "timeframe": tf,
            "source": "signal_prewarm_service",
        }
        get_buffer().set(asset, tf, payload, generator="enhanced_oanda")
    except Exception as e:
        logger.debug(f"prewarm_one({asset},{tf}) failed: {e}")


async def _refresh_loop() -> None:
    logger.info(f"[signal_prewarm] loop started (ttl={TTL_SECONDS}s, "
                f"interval={REFRESH_INTERVAL_SECONDS}s, "
                f"max_combos={MAX_TRACKED_COMBOS})")
    buf = get_buffer()
    while True:
        try:
            combos = buf.active_combos()
            for asset, tf in combos[:MAX_TRACKED_COMBOS]:
                await _refresh_one(asset, tf)
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("[signal_prewarm] loop cancelled")
            raise
        except Exception as e:
            logger.warning(f"[signal_prewarm] loop iter error: {e}")
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


def start_background_refresher() -> None:
    """Kick off the loop. Idempotent — safe to call from server startup."""
    global _refresh_task
    if _refresh_task is not None and not _refresh_task.done():
        return
    loop = asyncio.get_event_loop()
    _refresh_task = loop.create_task(_refresh_loop())
    logger.info("[signal_prewarm] background refresher scheduled")


def stop_background_refresher() -> None:
    global _refresh_task
    if _refresh_task is not None:
        _refresh_task.cancel()
        _refresh_task = None


# ---------------------------------------------------------------------------
# Runtime settings — mutated by /api/latency/settings POST (Iter 94)
# ---------------------------------------------------------------------------
def get_settings() -> Dict[str, Any]:
    return {
        "ttl_seconds": TTL_SECONDS,
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "active_window_seconds": ACTIVE_WINDOW_SECONDS,
        "max_tracked_combos": MAX_TRACKED_COMBOS,
    }


def update_settings(
    ttl_seconds: Optional[float] = None,
    refresh_interval_seconds: Optional[float] = None,
    active_window_seconds: Optional[float] = None,
    max_tracked_combos: Optional[int] = None,
) -> Dict[str, Any]:
    global TTL_SECONDS, REFRESH_INTERVAL_SECONDS, ACTIVE_WINDOW_SECONDS, MAX_TRACKED_COMBOS
    if ttl_seconds is not None:
        TTL_SECONDS = max(0.5, min(30.0, float(ttl_seconds)))
    if refresh_interval_seconds is not None:
        REFRESH_INTERVAL_SECONDS = max(0.5, min(15.0, float(refresh_interval_seconds)))
    if active_window_seconds is not None:
        ACTIVE_WINDOW_SECONDS = max(5.0, min(600.0, float(active_window_seconds)))
    if max_tracked_combos is not None:
        MAX_TRACKED_COMBOS = max(1, min(500, int(max_tracked_combos)))
    logger.info(f"[signal_prewarm] settings updated: {get_settings()}")
    return get_settings()
