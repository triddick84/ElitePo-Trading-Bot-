"""Iter 134 — Performance & cache stats surface."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/perf/yf-cache")
async def yf_cache_stats():
    """Yfinance TTL cache stats — hits, misses, size, hit rate."""
    try:
        import yf_cache
        return {"success": True, **yf_cache.stats()}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/perf/yf-cache/invalidate")
async def yf_cache_invalidate(ticker: str = None):
    """Flush the yfinance cache — either a single ticker or the whole cache."""
    try:
        import yf_cache
        n = yf_cache.invalidate(ticker)
        return {"success": True, "invalidated": n}
    except Exception as e:
        return {"success": False, "error": str(e)}
