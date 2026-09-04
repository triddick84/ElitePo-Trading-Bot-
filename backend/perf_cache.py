"""
Iter 121 — Performance optimizations: in-process TTL caches + helpers.

- `TTLCache` is a tiny threadsafe TTL cache with async-safe get/set.
- `active_target_cache` short-TTL cache for the TM hot endpoint.
- `backtest_result_cache` medium-TTL cache for `/strategies/backtest`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    """Minimal in-process TTL cache.

    Not shared across workers — that's OK: our staleness budget is 0.5-5 s and
    we run a single uvicorn worker for the trading bot.
    """

    def __init__(self, ttl_seconds: float, max_entries: int = 128) -> None:
        self.ttl = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    def get_sync(self, key: str) -> Optional[Any]:
        row = self._store.get(key)
        if row is None:
            return None
        expires_at, value = row
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set_sync(self, key: str, value: Any) -> None:
        if len(self._store) >= self.max_entries:
            # cheap eviction: drop the earliest-expiring entry
            oldest = min(self._store.items(), key=lambda kv: kv[1][0], default=None)
            if oldest:
                self._store.pop(oldest[0], None)
        self._store[key] = (time.monotonic() + self.ttl, value)

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self.get_sync(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self.set_sync(key, value)

    def invalidate(self, key: Optional[str] = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    def stats(self) -> Dict[str, Any]:
        return {"size": len(self._store), "ttl_seconds": self.ttl, "max_entries": self.max_entries}


# ---------------------------------------------------------------------------
# Shared caches
# ---------------------------------------------------------------------------
# Very short TTL — TM script polls this every timing beat. 0.75 s means:
# - At most 1.3 db hits/second even under 20 rps of TM traffic
# - Freshness is fine because a user changing the active target sees it
#   propagate within 0.75 s (and the POST route invalidates immediately).
active_target_cache = TTLCache(ttl_seconds=0.75, max_entries=8)

# Medium TTL — backtest is deterministic on (strategy, asset, tf, days, params).
# 5 min lets the user click "Run backtest" back-to-back for instant results.
backtest_result_cache = TTLCache(ttl_seconds=300.0, max_entries=64)


def stable_hash(payload: Any) -> str:
    """Deterministic hash suitable as a cache key."""
    try:
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
    except Exception:
        blob = repr(payload).encode()
    return hashlib.sha1(blob).hexdigest()[:16]
