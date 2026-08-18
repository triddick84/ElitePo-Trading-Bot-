"""
Elite Screener REST endpoints — Iter 109.

Multi-asset scanner exposing the proprietary Elite Score composite.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from elite_screener_service import score_asset, scan_assets

logger = logging.getLogger(__name__)
router = APIRouter()


# Default OTC-forex universe for the screener
DEFAULT_UNIVERSE = [
    "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "AUDUSD_OTC", "EURJPY_OTC",
    "GBPJPY_OTC", "AUDCAD_OTC", "NZDUSD_OTC", "CADCHF_OTC", "EURGBP_OTC",
]


def _parse_assets(assets: Optional[str]) -> List[str]:
    if not assets:
        return DEFAULT_UNIVERSE
    parts = [a.strip().upper() for a in assets.replace(";", ",").split(",")
             if a and a.strip()]
    return parts or DEFAULT_UNIVERSE


@router.get("/screener/scan")
async def screener_scan(
    assets: Optional[str] = Query(
        None, description="Comma-separated asset list. If omitted, "
                          "scans the default 10-pair OTC forex universe."),
    timeframe: str = Query("1m", description="Timeframe label — cosmetic."),
    lookback: int = Query(60, ge=25, le=500,
                          description="Candles to pull per asset."),
    min_score: float = Query(0.0, ge=0.0, le=100.0,
                             description="Filter out rows with Elite Score "
                                         "below this threshold."),
) -> Dict[str, Any]:
    """
    Multi-asset scanner. Returns rows sorted by Elite Score desc.

    Response shape (per row):
      {
        asset, timeframe, elite_score, direction,
        sub_scores: {smt, sweep, atr_band, ob_fvg, micro},
        sub_details: {...},
        entry, stop, target, n_candles, reason
      }
    """
    asset_list = _parse_assets(assets)
    return await scan_assets(
        assets=asset_list, timeframe=timeframe,
        lookback=lookback, min_score=float(min_score),
    )


@router.get("/screener/score")
async def screener_score_one(
    asset: str = Query(..., description="Asset symbol e.g. EURUSD_OTC"),
    timeframe: str = Query("1m"),
    lookback: int = Query(60, ge=25, le=500),
) -> Dict[str, Any]:
    """Elite Score for a single asset — used by the TM Elite-Gate check."""
    result = await score_asset(asset.strip().upper(),
                               timeframe=timeframe, lookback=lookback)
    return {"success": True, "result": result}


@router.get("/screener/universe")
async def screener_universe() -> Dict[str, Any]:
    """Return the default asset universe scanned when no `assets=` is given."""
    return {"success": True, "universe": DEFAULT_UNIVERSE,
            "count": len(DEFAULT_UNIVERSE)}
