"""
AI Enhancements API (Iter 115).

Public endpoints for the four upgrades:
- /api/regime/current         → ADX-regime classification for an asset
- /api/ha/confluence          → HA confluence status for an asset+direction
- /api/feedback/record-outcome → append a trade outcome
- /api/feedback/weights       → get per-strategy multipliers
- /api/ai/gates/config        → GET/POST toggles for the 4 gates
- /api/ml/lightgbm/status
- /api/ml/lightgbm/train
- /api/ml/lightgbm/predict
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from routes import db, logger

from adx_regime_gate import (
    compute_adx,
    classify_adx_regime,
    evaluate_regime_gate,
)
from ha_confluence_gate import evaluate_ha_confluence
import feedback_engine
from lightgbm_meta_service import (
    get_lightgbm_service,
    train_from_historical_candles,
    record_live_sample,
    get_live_samples_stats,
    _retrain_from_live_samples,
    backfill_from_tm_trade_reports,
)


router = APIRouter()


# ---------------------------------------------------------------------------
# Helper — fetch recent candles for an asset (handles both `asset` & `symbol`)
# ---------------------------------------------------------------------------
async def _recent_candles(symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not symbol:
        return []
    sym = symbol.strip().upper()
    variants = {sym, sym.replace("_OTC", ""), sym.replace("OTC", "")}
    # try otc_candles_5s (uses `symbol`), historical_candles (uses `asset`),
    # candles (uses `symbol`)
    for coll_name, key in (
        ("otc_candles_5s", "symbol"),
        ("candles", "symbol"),
        ("historical_candles", "asset"),
    ):
        try:
            docs = await db[coll_name].find(
                {key: {"$in": list(variants)}},
                {"_id": 0, "open": 1, "high": 1, "low": 1, "close": 1,
                 "volume": 1, "timestamp": 1},
            ).sort("timestamp", -1).limit(limit).to_list(length=limit)
            if docs:
                return list(reversed(docs))
        except Exception as e:
            logger.debug("_recent_candles %s failed: %s", coll_name, e)
    return []


# ---------------------------------------------------------------------------
# Gate config
# ---------------------------------------------------------------------------
class GatesConfig(BaseModel):
    adx_regime_enabled: bool = True
    ha_confluence_enabled: bool = True
    ha_min_streak: int = Field(2, ge=1, le=6)
    ha_require_no_opposing_wick: bool = False
    feedback_multiplier_enabled: bool = True
    lightgbm_meta_enabled: bool = False  # opt-in until trained


async def _get_gates_config() -> GatesConfig:
    doc = await db.ai_gates_config.find_one({"_id": "default"})
    if not doc:
        return GatesConfig()
    doc.pop("_id", None)
    try:
        return GatesConfig(**doc)
    except Exception:
        return GatesConfig()


@router.get("/ai/gates/config")
async def get_gates_config():
    cfg = await _get_gates_config()
    return {"success": True, "config": cfg.model_dump()}


@router.post("/ai/gates/config")
async def set_gates_config(payload: GatesConfig):
    await db.ai_gates_config.replace_one(
        {"_id": "default"},
        {"_id": "default", **payload.model_dump()},
        upsert=True,
    )
    return {"success": True, "config": payload.model_dump()}


# Iter 118 — AI Gates Presets (Conservative / Balanced / Aggressive)
_GATE_PRESETS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        # Every gate on, tight thresholds — few but very high-quality signals
        "adx_regime_enabled": True,
        "ha_confluence_enabled": True,
        "ha_min_streak": 3,
        "ha_require_no_opposing_wick": True,
        "feedback_multiplier_enabled": True,
        "lightgbm_meta_enabled": True,
    },
    "balanced": {
        # Default recommended stance — the sweet spot
        "adx_regime_enabled": True,
        "ha_confluence_enabled": True,
        "ha_min_streak": 2,
        "ha_require_no_opposing_wick": False,
        "feedback_multiplier_enabled": True,
        "lightgbm_meta_enabled": False,
    },
    "aggressive": {
        # ADX regime OFF (allow trades in any regime), HA looser — more volume,
        # rely on feedback multiplier to still tune per strategy
        "adx_regime_enabled": False,
        "ha_confluence_enabled": False,
        "ha_min_streak": 1,
        "ha_require_no_opposing_wick": False,
        "feedback_multiplier_enabled": True,
        "lightgbm_meta_enabled": False,
    },
}


@router.get("/ai/gates/presets")
async def get_gate_presets():
    """List the preset gate configurations available."""
    return {
        "success": True,
        "presets": [
            {"id": k, "label": k.capitalize(), "config": v}
            for k, v in _GATE_PRESETS.items()
        ],
    }


class PresetApply(BaseModel):
    preset: str


@router.post("/ai/gates/apply-preset")
async def apply_gate_preset(payload: PresetApply):
    """Overwrite the ai_gates_config with a named preset."""
    preset = _GATE_PRESETS.get(payload.preset.lower())
    if not preset:
        raise HTTPException(
            status_code=400,
            detail=f"unknown preset — choose one of {list(_GATE_PRESETS)}",
        )
    cfg = GatesConfig(**preset)
    await db.ai_gates_config.replace_one(
        {"_id": "default"},
        {"_id": "default", **cfg.model_dump(), "applied_preset": payload.preset.lower()},
        upsert=True,
    )
    return {"success": True, "preset": payload.preset.lower(), "config": cfg.model_dump()}


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------
@router.get("/regime/current")
async def regime_current(
    symbol: str = Query(..., description="Asset symbol e.g. EURUSD_OTC"),
    period: int = Query(14, ge=5, le=50),
):
    candles = await _recent_candles(symbol, limit=max(60, period * 4 + 4))
    if not candles:
        return {"success": False, "reason": "no_candles", "symbol": symbol}
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    adx_info = compute_adx(highs, lows, closes, period=period)
    regime = classify_adx_regime(
        adx_info["adx"], adx_info["plus_di"], adx_info["minus_di"]
    )
    return {
        "success": True,
        "symbol": symbol,
        "regime": regime,
        "sample_size": len(candles),
    }


# ---------------------------------------------------------------------------
# Heikin-Ashi
# ---------------------------------------------------------------------------
@router.get("/ha/confluence")
async def ha_confluence(
    symbol: str = Query(...),
    direction: str = Query(..., description="UP/DOWN/CALL/PUT"),
    min_streak: int = Query(2, ge=1, le=6),
    require_no_opposing_wick: bool = Query(False),
):
    candles = await _recent_candles(symbol, limit=60)
    if not candles:
        return {"success": False, "reason": "no_candles", "symbol": symbol}
    result = evaluate_ha_confluence(
        candles,
        signal_direction=direction,
        min_streak=min_streak,
        require_no_opposing_wick=require_no_opposing_wick,
    )
    return {"success": True, "symbol": symbol, **result}


# ---------------------------------------------------------------------------
# Feedback engine
# ---------------------------------------------------------------------------
class OutcomePayload(BaseModel):
    strategy_id: str
    outcome: str  # WIN / LOSS / TIE
    regime: str = "NEUTRAL"
    asset: Optional[str] = None
    timeframe: Optional[str] = None
    confidence: Optional[float] = None
    signal_id: Optional[str] = None


@router.post("/feedback/record-outcome")
async def feedback_record_outcome(payload: OutcomePayload):
    metadata = {
        k: v for k, v in payload.model_dump().items()
        if k in ("asset", "timeframe", "confidence", "signal_id") and v is not None
    }
    result = await feedback_engine.record_outcome(
        db,
        strategy_id=payload.strategy_id,
        outcome=payload.outcome,
        regime=payload.regime,
        metadata=metadata or None,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/feedback/weights")
async def feedback_weights(strategy_id: Optional[str] = Query(None)):
    if strategy_id:
        stats = await feedback_engine.get_stats(db, strategy_id)
        if stats is None:
            return {"success": True, "stats": None}
        return {"success": True, "stats": stats}
    return {"success": True, "stats": await feedback_engine.list_all(db)}


# ---------------------------------------------------------------------------
# LightGBM meta-model
# ---------------------------------------------------------------------------
@router.get("/ml/lightgbm/status")
async def lightgbm_status():
    return {"success": True, **get_lightgbm_service().status()}


class LightGBMTrainPayload(BaseModel):
    max_samples: int = Field(3000, ge=100, le=50000)
    lookback: int = Field(30, ge=10, le=200)


@router.post("/ml/lightgbm/train")
async def lightgbm_train(payload: Optional[LightGBMTrainPayload] = Body(None)):
    p = payload or LightGBMTrainPayload()
    try:
        result = await train_from_historical_candles(
            db, max_samples=p.max_samples, lookback=p.lookback
        )
        return {"success": bool(result.get("success", False)), **result}
    except Exception as e:
        logger.exception("LightGBM training failed")
        raise HTTPException(status_code=500, detail=str(e))


class LightGBMPredictPayload(BaseModel):
    features: Dict[str, Any]


@router.post("/ml/lightgbm/predict")
async def lightgbm_predict(payload: LightGBMPredictPayload):
    svc = get_lightgbm_service()
    if not svc.is_ready():
        return {"success": False, "reason": "model_not_trained"}
    prob_up = svc.predict_proba(payload.features)
    if prob_up is None:
        return {"success": False, "reason": "predict_failed"}
    direction = "UP" if prob_up >= 0.5 else "DOWN"
    return {
        "success": True,
        "prob_up": prob_up,
        "prob_down": 1.0 - prob_up,
        "direction": direction,
        "confidence": round(abs(prob_up - 0.5) * 200.0, 2),  # 0..100 confidence
    }


# ---------------------------------------------------------------------------
# Iter 118 — Live-trade retrain
# ---------------------------------------------------------------------------
class LiveSamplePayload(BaseModel):
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: str  # WIN / LOSS
    metadata: Optional[Dict[str, Any]] = None


@router.post("/ml/lightgbm/record-live-sample")
async def lightgbm_record_live_sample(payload: LiveSamplePayload):
    """Append a labeled live-trade sample. Auto-triggers retrain on threshold."""
    result = await record_live_sample(
        db, payload.features, payload.outcome, payload.metadata
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/ml/lightgbm/retrain-live")
async def lightgbm_retrain_live():
    """Force a retrain from accumulated live samples."""
    try:
        metrics = await _retrain_from_live_samples(db)
        return metrics
    except Exception as e:
        logger.exception("live retrain failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/lightgbm/live-samples/stats")
async def lightgbm_live_samples_stats():
    stats = await get_live_samples_stats(db)
    return {"success": True, **stats}


# ---------------------------------------------------------------------------
# Iter 119 — Backfill from tm_trade_reports (the 5,006 labeled real trades)
# ---------------------------------------------------------------------------
class BackfillPayload(BaseModel):
    max_samples: int = Field(6000, ge=100, le=50000)
    candle_lookback: int = Field(60, ge=30, le=200)


@router.post("/ml/lightgbm/backfill")
async def lightgbm_backfill(payload: Optional[BackfillPayload] = Body(None)):
    """
    Pull every WIN/LOSS trade from `tm_trade_reports`, build real features
    from the candles preceding each trade, and retrain with walk-forward CV
    + isotonic calibration. Single biggest lift in the AI pipeline — moves
    the meta-model from placeholder-fed random to genuinely trained.
    """
    p = payload or BackfillPayload()
    try:
        result = await backfill_from_tm_trade_reports(
            db, max_samples=p.max_samples, candle_lookback=p.candle_lookback
        )
        return result
    except Exception as e:
        logger.exception("backfill failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Iter 119 — Expected-Value gate config + audit report
# ---------------------------------------------------------------------------
class EVGateConfig(BaseModel):
    enabled: bool = True
    min_ev: float = Field(0.02, ge=-1.0, le=1.0,
                          description="Minimum expected value per $1 stake to fire")
    default_payout: float = Field(0.85, ge=0.0, le=1.0,
                                  description="Fallback payout when signal doesn't have one")


@router.get("/ai/ev-gate/config")
async def get_ev_gate_config():
    doc = await db.ai_ev_gate_config.find_one({"_id": "default"})
    if not doc:
        cfg = EVGateConfig().model_dump()
    else:
        doc.pop("_id", None)
        try:
            cfg = EVGateConfig(**doc).model_dump()
        except Exception:
            cfg = EVGateConfig().model_dump()
    return {"success": True, "config": cfg}


@router.post("/ai/ev-gate/config")
async def set_ev_gate_config(payload: EVGateConfig):
    await db.ai_ev_gate_config.replace_one(
        {"_id": "default"},
        {"_id": "default", **payload.model_dump()},
        upsert=True,
    )
    return {"success": True, "config": payload.model_dump()}


# ---------------------------------------------------------------------------
# Iter 119 — Shadow-mode picks (paper-trade log for A/B comparison)
# ---------------------------------------------------------------------------
@router.get("/ai/shadow-mode/report")
async def shadow_mode_report(hours: int = Query(24, ge=1, le=720)):
    """
    Roll up shadow-mode picks over the last N hours:
      - How many signals passed each gate?
      - How many would have been placed with the new EV gate on?
      - Simulated win-rate and P&L (based on trade outcomes we can look up)
    """
    from datetime import timedelta as _td
    cutoff = (datetime.now(timezone.utc) - _td(hours=hours)).isoformat()
    picks = await db.ai_shadow_picks.find(
        {"created_at": {"$gte": cutoff}}
    ).sort("created_at", 1).to_list(length=20000)

    total = len(picks)
    would_fire = sum(1 for p in picks if p.get("would_fire"))
    passed_ev = sum(1 for p in picks if p.get("ev_gate_passed"))
    passed_lgbm = sum(1 for p in picks if p.get("lgbm_agrees"))
    wins = sum(1 for p in picks if p.get("actual_outcome") == "WIN")
    losses = sum(1 for p in picks if p.get("actual_outcome") == "LOSS")
    resolved = wins + losses
    sim_pnl = 0.0
    for p in picks:
        outcome = p.get("actual_outcome")
        stake = float(p.get("stake") or 1.0)
        payout = float(p.get("payout") or 0.85)
        if outcome == "WIN":
            sim_pnl += stake * payout
        elif outcome == "LOSS":
            sim_pnl -= stake

    return {
        "success": True,
        "hours": hours,
        "total_shadow_picks": total,
        "would_fire": would_fire,
        "passed_ev_gate": passed_ev,
        "passed_lgbm_gate": passed_lgbm,
        "resolved_outcomes": resolved,
        "wins": wins,
        "losses": losses,
        "sim_win_rate": round((wins / resolved), 4) if resolved else None,
        "sim_pnl": round(sim_pnl, 2),
    }
