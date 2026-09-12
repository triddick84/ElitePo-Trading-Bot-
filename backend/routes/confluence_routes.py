"""Iter 137 — Pattern Detection + Confluence REST endpoints.

Endpoints
---------
POST /api/patterns/detect
    Detect chart patterns on a payload of OHLCV candles.

GET  /api/patterns/detect
    Detect on the last N candles of a live asset+timeframe pulled from
    MongoDB (`otc_candles_5s` or `historical_candles`).

POST /api/confluence/score
    Score a list of raw signals into a single confluence result.

GET  /api/confluence/config
POST /api/confluence/config
    Read / update the auto-scan confluence gate (threshold + min sources).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import pattern_detector as pd_mod
import confluence_service as conf_mod


router = APIRouter(tags=["confluence"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0.0
    timestamp: Optional[float] = None


class PatternDetectRequest(BaseModel):
    candles: List[Candle]


class ConfluenceSignal(BaseModel):
    source: str
    direction: str
    confidence: float = Field(ge=0.0, le=1.0)
    weight: Optional[float] = None
    asset: Optional[str] = None
    timeframe: Optional[str] = None


class ConfluenceScoreRequest(BaseModel):
    signals: List[ConfluenceSignal]
    min_sources: int = Field(default=conf_mod.DEFAULT_MIN_SOURCES, ge=1, le=10)
    threshold: float = Field(default=conf_mod.DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class ConfluenceConfig(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)
    min_sources: int = Field(ge=1, le=10)


# In-process singleton so auto-scan can read the current gate without hitting Mongo.
_config: Dict[str, Any] = {
    "threshold": conf_mod.DEFAULT_THRESHOLD,
    "min_sources": conf_mod.DEFAULT_MIN_SOURCES,
}


def get_confluence_config() -> Dict[str, Any]:
    """Public accessor so auto_scan_service can hard-gate on the live config."""
    return dict(_config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candles_to_df(candles: List[Candle]) -> pd.DataFrame:
    rows = [c.model_dump() for c in candles]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


async def _load_candles_from_db(asset: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Best-effort candle loader — 5s uses `otc_candles_5s`, everything else
    falls back to `historical_candles`."""
    import server  # late import to avoid circular init
    db = getattr(server, "db", None)
    if db is None:
        return pd.DataFrame()
    if timeframe == "5s":
        cur = db.otc_candles_5s.find({"symbol": asset}).sort("timestamp", -1).limit(limit)
    else:
        cur = db.historical_candles.find(
            {"asset": asset, "timeframe": timeframe}
        ).sort("timestamp", -1).limit(limit)
    rows = await cur.to_list(length=limit)
    if not rows:
        return pd.DataFrame()
    rows = list(reversed(rows))  # oldest first
    df = pd.DataFrame(rows)
    # normalise column names
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            return pd.DataFrame()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[["open", "high", "low", "close", "volume"]].astype(float)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/patterns/detect")
async def patterns_detect(req: PatternDetectRequest) -> Dict[str, Any]:
    df = _candles_to_df(req.candles)
    if df.empty:
        raise HTTPException(status_code=400, detail="No candles provided")
    hits = pd_mod.detect_all(df)
    return {
        "n_candles": len(df),
        "n_hits": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.get("/patterns/detect")
async def patterns_detect_live(
    asset: str = Query(..., description="Asset symbol, e.g. EURUSD_OTC"),
    timeframe: str = Query("1m", description="Candle timeframe (5s, 1m, 5m, ...)"),
    limit: int = Query(200, ge=30, le=2000),
) -> Dict[str, Any]:
    df = await _load_candles_from_db(asset, timeframe, limit)
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No candles found for {asset} @ {timeframe}",
        )
    hits = pd_mod.detect_all(df)
    return {
        "asset": asset,
        "timeframe": timeframe,
        "n_candles": len(df),
        "n_hits": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.post("/confluence/score")
async def confluence_score(req: ConfluenceScoreRequest) -> Dict[str, Any]:
    result = conf_mod.score_confluence(
        [s.model_dump() for s in req.signals],
        min_sources=req.min_sources,
    )
    fires = conf_mod.should_fire(result, threshold=req.threshold, min_sources=req.min_sources)
    return {
        "result": result,
        "fires": fires,
        "threshold": req.threshold,
        "min_sources": req.min_sources,
    }


@router.get("/confluence/config")
async def confluence_config_get() -> Dict[str, Any]:
    return get_confluence_config()


@router.post("/confluence/config")
async def confluence_config_set(cfg: ConfluenceConfig) -> Dict[str, Any]:
    _config["threshold"] = float(cfg.threshold)
    _config["min_sources"] = int(cfg.min_sources)
    # Persist to Mongo for restart-safety.
    try:
        import server
        db = getattr(server, "db", None)
        if db is not None:
            await db.strategy_configs.update_one(
                {"_id": "confluence_gate"},
                {"$set": {**_config, "_id": "confluence_gate"}},
                upsert=True,
            )
    except Exception:
        pass
    return get_confluence_config()


async def restore_confluence_config_from_db() -> None:
    """Called on server startup to re-apply the persisted gate."""
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            return
        doc = await db.strategy_configs.find_one({"_id": "confluence_gate"})
        if not doc:
            return
        _config["threshold"] = float(doc.get("threshold", conf_mod.DEFAULT_THRESHOLD))
        _config["min_sources"] = int(doc.get("min_sources", conf_mod.DEFAULT_MIN_SOURCES))
    except Exception:
        pass
