"""
Microstructure REST endpoints — Iter 86.

Exposes VPIN + Kyle's λ + order-flow-imbalance stats and gating decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from microstructure import microstructure

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/microstructure/status")
async def status() -> Dict[str, Any]:
    await microstructure.refresh()
    return {"success": True, **microstructure.status()}


@router.get("/microstructure/stats")
async def all_stats(limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    await microstructure.refresh()
    entries = microstructure.all_entries()
    entries.sort(key=lambda e: -e.get("vpin", 0.0))
    return {"success": True, "count": len(entries), "entries": entries[:limit]}


@router.get("/microstructure/stats/one")
async def one_stat(asset: str) -> Dict[str, Any]:
    return {"success": True, "stat": await microstructure.get_stats_full(asset)}


@router.get("/microstructure/should-gate")
async def should_gate(asset: str) -> Dict[str, Any]:
    decision = await microstructure.should_gate(asset)
    return {"success": True, "decision": decision}


@router.get("/microstructure/multiplier")
async def multiplier(asset: str) -> Dict[str, Any]:
    """Confidence multiplier this asset would currently apply to the ensemble."""
    await microstructure.refresh()
    return {"success": True, "asset": asset,
            "multiplier": microstructure.confidence_multiplier(asset)}


@router.get("/microstructure/config")
async def get_config() -> Dict[str, Any]:
    return {"success": True, "config": microstructure.get_config()}


@router.post("/microstructure/config")
async def set_config(patch: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    updated = await microstructure.save_config(patch)
    await microstructure.invalidate()
    return {"success": True, "config": updated}


@router.post("/microstructure/refresh")
async def refresh() -> Dict[str, Any]:
    result = await microstructure.refresh(force=True)
    return {"success": True, **result}


# ---------------------------------------------------------------------------
# Iter 105 — Kyle (1985) & Glosten-Milgrom (1985) classical model endpoints
# ---------------------------------------------------------------------------
@router.get("/microstructure/kyle")
async def kyle(
    asset: str = Query(..., description="Asset symbol e.g. EURUSD_OTC"),
    lookback: int = Query(60, ge=20, le=500),
) -> Dict[str, Any]:
    """
    Kyle (1985) linear price-impact estimate for `asset`.

    Returns:
        {
          success, asset, mid_price, n_candles,
          kyle: {
            lambda, beta, sigma_v, sigma_u,
            informed_profit, illiquidity_bps, interpretation
          }
        }
    """
    from microstructure_models import kyle_for_asset
    return await kyle_for_asset(asset, lookback=lookback)


@router.get("/microstructure/glosten_milgrom")
async def glosten_milgrom(
    asset: str = Query(..., description="Asset symbol e.g. EURUSD_OTC"),
    lookback: int = Query(40, ge=20, le=500),
    alpha_informed: Optional[float] = Query(
        None, ge=0.0, le=1.0,
        description="Override the informed-trader probability. If omitted, "
                    "estimated from one-sided body dominance over lookback."
    ),
) -> Dict[str, Any]:
    """
    Glosten-Milgrom (1985) sequential-trade spread model.

    Returns:
        {
          success, asset, mid_price, sma, n_candles, n_up_bars, n_down_bars,
          gm: {
            v_high, v_low, ask, bid, spread_abs, spread_bps,
            alpha_informed, p_high_prior, adverse_selection_pct, interpretation
          }
        }
    """
    from microstructure_models import glosten_milgrom_for_asset
    return await glosten_milgrom_for_asset(
        asset, lookback=lookback, alpha_informed=alpha_informed,
    )


@router.get("/microstructure/models")
async def both_models(
    asset: str = Query(..., description="Asset symbol"),
    lookback: int = Query(60, ge=20, le=500),
) -> Dict[str, Any]:
    """Convenience endpoint returning BOTH Kyle + Glosten-Milgrom in one call."""
    from microstructure_models import kyle_for_asset, glosten_milgrom_for_asset
    k = await kyle_for_asset(asset, lookback=lookback)
    g = await glosten_milgrom_for_asset(asset, lookback=lookback)
    return {"success": True, "asset": asset,
            "kyle_result": k, "gm_result": g}
