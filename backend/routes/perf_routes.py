"""Iter 134 — Performance & cache stats surface."""
from fastapi import APIRouter, Query

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


# ---------------------------------------------------------------------------
# Iter 135 — RF AUC Audit
# ---------------------------------------------------------------------------
@router.post("/rf-audit/run")
async def rf_audit_run(limit: int = Query(0, ge=0, le=200)):
    """Score every rf_*.pkl model on fresh holdout data. Returns summary +
    per-model AUC/status."""
    from rf_audit_service import rf_audit_service
    result = await rf_audit_service.run_audit(limit=limit or None)
    return {"success": True, **result}


@router.get("/rf-audit/latest")
async def rf_audit_latest():
    """Return the most recent audit rows sorted by AUC desc."""
    from rf_audit_service import rf_audit_service
    rows = await rf_audit_service.latest()
    return {"success": True, "count": len(rows), "results": rows}


@router.get("/rf-audit/weight")
async def rf_audit_weight(asset: str, timeframe: str):
    """Return the current effective ensemble weight for a single model."""
    from rf_audit_service import rf_audit_service
    return {
        "success": True,
        "asset": asset, "timeframe": timeframe,
        "weight": rf_audit_service.get_effective_weight(asset, timeframe),
    }
