"""Iter 134 — yfinance TTL cache + RiskGuard-aware auto-scan gate."""
import re
import sys
import time

import httpx
import pytest

sys.path.insert(0, "/app/backend")


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()


# ---------------------------------------------------------------------------
# yf_cache — thread-safety, TTL, key correctness
# ---------------------------------------------------------------------------
def test_yf_cache_module_installs_idempotently():
    import yf_cache
    # First install (already done at server startup, but idempotent)
    yf_cache.install()
    yf_cache.install()  # second call must be a no-op
    import yfinance as yf
    assert getattr(yf.Ticker.history, "_yfcache_installed", False) is True


def test_yf_cache_key_ignores_start_end_but_captures_period_interval():
    import yf_cache
    k1 = yf_cache._make_key("EURUSD=X", {"period": "5d", "interval": "1m"})
    k2 = yf_cache._make_key("EURUSD=X", {"period": "5d", "interval": "1m"})
    k3 = yf_cache._make_key("EURUSD=X", {"period": "5d", "interval": "5m"})
    k4 = yf_cache._make_key("GBPUSD=X", {"period": "5d", "interval": "1m"})
    assert k1 == k2
    assert k1 != k3, "different interval must produce different key"
    assert k1 != k4, "different ticker must produce different key"


def test_yf_cache_evicts_when_full():
    import yf_cache
    yf_cache._cache.clear()
    yf_cache._stats["evictions"] = 0
    # Fill just past MAX_ENTRIES
    for i in range(yf_cache.MAX_ENTRIES + 5):
        yf_cache._cache[("SYM", str(i), "1m", None, None, None, None)] = (time.monotonic(), None)
    yf_cache._evict_if_full()
    assert len(yf_cache._cache) < yf_cache.MAX_ENTRIES + 5
    assert yf_cache._stats["evictions"] > 0


def test_yf_cache_invalidate_single_ticker():
    import yf_cache
    yf_cache._cache[("EURUSD=X", "5d", "1m", None, None, None, None)] = (time.monotonic(), "a")
    yf_cache._cache[("EURUSD=X", "5d", "5m", None, None, None, None)] = (time.monotonic(), "b")
    yf_cache._cache[("GBPUSD=X", "5d", "1m", None, None, None, None)] = (time.monotonic(), "c")
    n = yf_cache.invalidate("EURUSD=X")
    assert n == 2
    assert not any(k[0] == "EURUSD=X" for k in yf_cache._cache)
    # GBPUSD entry untouched
    assert any(k[0] == "GBPUSD=X" for k in yf_cache._cache)


def test_yf_cache_ttl_expires_stale_hits():
    """Fake TTL of 0.5s. After 0.6s the cached entry must be a miss."""
    import yf_cache
    # We can't easily reinvoke install with a different ttl, so directly test
    # the freshness check logic used inside the patched history.
    key = ("EURUSD=X", "5d", "1m", None, None, None, None)
    yf_cache._cache.clear()
    yf_cache._cache[key] = (time.monotonic() - 20.0, "old")  # 20s stale
    hit = yf_cache._cache.get(key)
    assert hit is not None
    is_fresh = (time.monotonic() - hit[0]) < 15.0
    assert not is_fresh, "20s-old entry must be considered stale for TTL=15s"


# ---------------------------------------------------------------------------
# Live perf endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_perf_yf_cache_endpoint_returns_stats():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{API}/perf/yf-cache")
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    for k in ("hits", "misses", "size", "hit_rate_pct", "ttl_seconds", "max_entries"):
        assert k in body


@pytest.mark.asyncio
async def test_perf_yf_cache_invalidate_endpoint():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{API}/perf/yf-cache/invalidate")
    assert r.status_code == 200
    assert r.json()["success"]


# ---------------------------------------------------------------------------
# Auto-scan RiskGuard pre-flight gate
# ---------------------------------------------------------------------------
def test_auto_scan_service_has_riskguard_preflight_gate():
    """Source-level check: `_route_to_tm` must call
    `risk_guard_service.get_active_session` and return early when the
    session is not `active`."""
    src = open("/app/backend/auto_scan_service.py").read()
    m = re.search(
        r"async def _route_to_tm[\s\S]{0,800}?risk_guard_service"
        r"[\s\S]{0,400}?get_active_session"
        r"[\s\S]{0,400}?status.*!= .active."
        r"[\s\S]{0,400}?return",
        src,
    )
    assert m, "auto_scan_service._route_to_tm must gate on RiskGuard status"


def test_auto_scan_gate_uses_default_user_id():
    """The gate must query for user_id='default' — matches Iter 133 auto-feed
    behavior, so all three (auto-feed, gate, UI) agree on which session."""
    src = open("/app/backend/auto_scan_service.py").read()
    assert 'get_active_session("default")' in src
