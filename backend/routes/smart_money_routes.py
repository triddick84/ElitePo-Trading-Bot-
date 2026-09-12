"""Iter 139 — Smart-Money & Mean-Reversion REST endpoints.

    POST /api/smart-money/detect            — payload of candles
    GET  /api/smart-money/detect            — live from Mongo candle stores
    POST /api/strategies/mean-reversion     — payload of candles
    GET  /api/strategies/mean-reversion     — live signal for asset+timeframe

Both endpoints emit output shapes compatible with the Iter 137 confluence
engine — clients can post `hits` / `signal` straight into `POST /api/confluence/score`
as new `smart_money:*` and `strategy:mean_reversion` sources.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import smart_money as sm_mod
from strategies.mean_reversion import mean_reversion_signal
from routes.confluence_routes import Candle, _load_candles_from_db, _candles_to_df


router = APIRouter(tags=["smart_money"])


class SmartMoneyDetectRequest(BaseModel):
    candles: List[Candle]


class MeanReversionRequest(BaseModel):
    candles: List[Candle]
    ema_period: int = Field(default=20, ge=5, le=200)
    z_threshold: float = Field(default=2.0, ge=0.5, le=5.0)
    adx_max: float = Field(default=20.0, ge=5.0, le=50.0)


@router.post("/smart-money/detect")
async def smart_money_detect(req: SmartMoneyDetectRequest) -> Dict[str, Any]:
    df = _candles_to_df(req.candles)
    if df.empty:
        raise HTTPException(status_code=400, detail="No candles provided")
    hits = sm_mod.detect_all_smart_money(df)
    return {
        "n_candles": len(df),
        "n_hits": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.get("/smart-money/detect")
async def smart_money_detect_live(
    asset: str = Query(...),
    timeframe: str = Query("1m"),
    limit: int = Query(200, ge=30, le=2000),
) -> Dict[str, Any]:
    df = await _load_candles_from_db(asset, timeframe, limit)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No candles for {asset} @ {timeframe}")
    hits = sm_mod.detect_all_smart_money(df)
    return {
        "asset": asset,
        "timeframe": timeframe,
        "n_candles": len(df),
        "n_hits": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.post("/strategies/mean-reversion")
async def mean_reversion_score(req: MeanReversionRequest) -> Dict[str, Any]:
    df = _candles_to_df(req.candles)
    if df.empty:
        raise HTTPException(status_code=400, detail="No candles provided")
    signal = mean_reversion_signal(
        df,
        ema_period=req.ema_period,
        z_threshold=req.z_threshold,
        adx_max=req.adx_max,
    )
    return {"n_candles": len(df), "signal": signal.to_dict()}


@router.get("/strategies/mean-reversion")
async def mean_reversion_live(
    asset: str = Query(...),
    timeframe: str = Query("1m"),
    limit: int = Query(200, ge=30, le=2000),
    ema_period: int = Query(20, ge=5, le=200),
    z_threshold: float = Query(2.0, ge=0.5, le=5.0),
    adx_max: float = Query(20.0, ge=5.0, le=50.0),
) -> Dict[str, Any]:
    df = await _load_candles_from_db(asset, timeframe, limit)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No candles for {asset} @ {timeframe}")
    signal = mean_reversion_signal(
        df, ema_period=ema_period, z_threshold=z_threshold, adx_max=adx_max,
    )
    return {
        "asset": asset,
        "timeframe": timeframe,
        "n_candles": len(df),
        "signal": signal.to_dict(),
    }
