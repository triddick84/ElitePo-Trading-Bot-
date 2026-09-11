"""Iter 134 — Cross-strategy yfinance TTL cache.

Every strategy in this codebase calls `yf.Ticker(sym).history(...)` directly
inside its `generate_signal()` method. When the auto-scan loop rotates
through 20+ assets on a 5-second interval, that's dozens of independent
network round-trips per second — most of them re-downloading the exact same
15 seconds of candles because the last bar hasn't closed yet.

This module monkey-patches `yfinance.Ticker.history` with a thread-safe TTL
cache keyed on `(ticker, period, interval, prepost, actions, auto_adjust,
back_adjust)`. Default TTL is 15 seconds — comfortably shorter than a 1-m
candle and long enough to soak up scan-loop bursts.

Import once from `server.py` before any strategy imports; from then on every
strategy transparently benefits.

Cache stats are exposed via `yf_cache.stats()` for the debug UI.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# Default TTL (seconds). Overridable via env `YF_CACHE_TTL`.
import os
DEFAULT_TTL_S = float(os.environ.get("YF_CACHE_TTL", 15.0))
# Hard cap on cache entries so a bug or huge asset universe can't leak.
MAX_ENTRIES = int(os.environ.get("YF_CACHE_MAX", 512))

_lock = threading.Lock()
_cache: Dict[Tuple, Tuple[float, Any]] = {}
_stats = {"hits": 0, "misses": 0, "evictions": 0}


def _make_key(ticker_symbol: str, kwargs: Dict[str, Any]) -> Tuple:
    """Cache key = (ticker, period, interval, prepost, actions, auto_adjust,
    back_adjust). Ignore start/end because those aren't used by the scan
    strategies (they all use period+interval)."""
    return (
        ticker_symbol,
        kwargs.get("period"),
        kwargs.get("interval"),
        kwargs.get("prepost"),
        kwargs.get("actions"),
        kwargs.get("auto_adjust"),
        kwargs.get("back_adjust"),
    )


def _evict_if_full() -> None:
    if len(_cache) < MAX_ENTRIES:
        return
    # Drop the ~10% oldest entries
    n_drop = max(1, MAX_ENTRIES // 10)
    ordered = sorted(_cache.items(), key=lambda kv: kv[1][0])
    for k, _ in ordered[:n_drop]:
        _cache.pop(k, None)
        _stats["evictions"] += 1


def install(ttl_seconds: float = DEFAULT_TTL_S) -> None:
    """Monkey-patch yfinance.Ticker.history with a TTL wrapper.

    Idempotent — calling twice is a no-op.
    """
    try:
        import yfinance as yf
    except Exception as e:  # pragma: no cover — yfinance is a hard dep
        logger.warning(f"[yf_cache] yfinance not importable: {e}")
        return

    if getattr(yf.Ticker.history, "_yfcache_installed", False):
        return

    original = yf.Ticker.history

    def _cached_history(self, *args, **kwargs):
        # Positional args (period,) are also supported by yfinance — normalize
        # them into kwargs so the cache key is consistent.
        if args:
            if len(args) >= 1 and "period" not in kwargs:
                kwargs["period"] = args[0]
            if len(args) >= 2 and "interval" not in kwargs:
                kwargs["interval"] = args[1]
        key = _make_key(getattr(self, "ticker", None), kwargs)
        now = time.monotonic()
        with _lock:
            hit = _cache.get(key)
            if hit and (now - hit[0]) < ttl_seconds:
                _stats["hits"] += 1
                return hit[1]
        # Miss → fetch outside the lock (network call)
        result = original(self, **kwargs)
        with _lock:
            _cache[key] = (now, result)
            _stats["misses"] += 1
            _evict_if_full()
        return result

    _cached_history._yfcache_installed = True
    yf.Ticker.history = _cached_history  # type: ignore[assignment]
    logger.info(f"[yf_cache] Installed TTL cache (ttl={ttl_seconds}s, max={MAX_ENTRIES})")


def stats() -> Dict[str, Any]:
    with _lock:
        total = _stats["hits"] + _stats["misses"]
        hit_rate = round((_stats["hits"] / total) * 100, 1) if total else 0.0
        return {
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "evictions": _stats["evictions"],
            "size": len(_cache),
            "hit_rate_pct": hit_rate,
            "ttl_seconds": DEFAULT_TTL_S,
            "max_entries": MAX_ENTRIES,
        }


def invalidate(ticker_symbol: str = None) -> int:
    """Manually invalidate all entries (or entries for a single ticker).
    Returns the number of entries dropped."""
    with _lock:
        if ticker_symbol is None:
            n = len(_cache)
            _cache.clear()
            return n
        drop = [k for k in _cache if k[0] == ticker_symbol]
        for k in drop:
            _cache.pop(k, None)
        return len(drop)
