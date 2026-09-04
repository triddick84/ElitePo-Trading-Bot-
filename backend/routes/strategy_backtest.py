"""
Iter 120 — Strategy backtest runner.

POST /api/strategies/backtest

Runs any registered strategy chronologically over the last N days of candles
for a given asset+timeframe, simulates the very next-bar outcome for each
CALL/PUT signal, and returns:

  {
    success, strategy_id, asset, timeframe,
    days_requested, candles_used, min_history,
    signals: {total, calls, puts, neutrals},
    wins, losses, win_rate, sample_size,
    sim_pnl,  simulated at `payout` (default 0.85) per $1 stake
    avg_confidence, confidence_bucket_win_rate: {50-60, 60-70, ...},
    strategy_specific: {}   # e.g. Ridicolous stats table
  }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from routes import db

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Candle loader — reuses the same 3-collection fallback as ai_enhancements
# ---------------------------------------------------------------------------
async def _load_candles(asset: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    if not asset:
        return []
    sym = asset.strip().upper()
    variants = list({sym,
                     sym.replace("_OTC", ""),
                     sym.replace("OTC", ""),
                     sym + "_OTC" if not sym.endswith("_OTC") else sym})
    for coll_name, key in (
        ("otc_candles_5s", "symbol"),
        ("candles", "symbol"),
        ("historical_candles", "asset"),
    ):
        try:
            query = {key: {"$in": variants}}
            if timeframe:
                query["timeframe"] = timeframe
            docs = await db[coll_name].find(
                query,
                {"_id": 0, "open": 1, "high": 1, "low": 1,
                 "close": 1, "volume": 1, "timestamp": 1},
            ).sort("timestamp", -1).limit(limit).to_list(length=limit)
            if not docs and timeframe:
                # retry without timeframe filter (some collections don't tag it)
                docs = await db[coll_name].find(
                    {key: {"$in": variants}},
                    {"_id": 0, "open": 1, "high": 1, "low": 1,
                     "close": 1, "volume": 1, "timestamp": 1},
                ).sort("timestamp", -1).limit(limit).to_list(length=limit)
            if docs and len(docs) >= 60:
                return list(reversed(docs))
        except Exception as e:
            logger.debug("_load_candles %s failed: %s", coll_name, e)
    return []


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
class BacktestPayload(BaseModel):
    strategy_id: str
    asset: str = "EURUSD_OTC"
    timeframe: str = "1m"
    days: int = Field(30, ge=1, le=365)
    max_candles: int = Field(3000, ge=100, le=20000)
    min_history: int = Field(60, ge=20, le=1000)
    payout: float = Field(0.85, ge=0.5, le=0.99)
    stride: int = Field(1, ge=1, le=20,
                        description="Evaluate every Nth candle (speeds up long backtests)")
    params: Optional[Dict[str, Any]] = Field(
        None,
        description="Strategy-specific override params (e.g. Ridicolous {perc, levels, min_confidence, min_history})",
    )


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------
def _simulate(
    strategy: Any,
    df: pd.DataFrame,
    min_history: int,
    payout: float,
    stride: int,
) -> Dict[str, Any]:
    """Walk chronologically, run generate_signal on candles[:i+1], score against candles[i+1]."""
    n = len(df)
    total = calls = puts = neutrals = wins = losses = 0
    conf_sum = 0.0
    conf_by_bucket: Dict[str, Dict[str, int]] = {
        "50-60": {"w": 0, "l": 0}, "60-70": {"w": 0, "l": 0},
        "70-80": {"w": 0, "l": 0}, "80-90": {"w": 0, "l": 0},
        "90-100": {"w": 0, "l": 0},
    }

    def _bucket(c: float) -> Optional[str]:
        if c < 50:
            return None
        if c < 60:
            return "50-60"
        if c < 70:
            return "60-70"
        if c < 80:
            return "70-80"
        if c < 90:
            return "80-90"
        return "90-100"

    closes = df["close"].astype(float).to_numpy()

    for i in range(min_history, n - 1, stride):
        window = df.iloc[: i + 1]
        try:
            sig = strategy.generate_signal(window)
        except Exception as e:
            logger.debug("strategy raised on i=%d: %s", i, e)
            continue
        direction = str(sig.get("direction", "NEUTRAL")).upper()
        conf = float(sig.get("confidence") or 0)

        total += 1
        if direction in ("CALL", "UP", "BUY"):
            calls += 1
            side = "CALL"
        elif direction in ("PUT", "DOWN", "SELL"):
            puts += 1
            side = "PUT"
        else:
            neutrals += 1
            continue

        # Score against NEXT bar close
        next_close = closes[i + 1]
        cur_close = closes[i]
        if next_close == cur_close:
            # tie — do not count in win/loss (binary options usually refund ties)
            continue
        went_up = next_close > cur_close
        won = (side == "CALL" and went_up) or (side == "PUT" and not went_up)

        conf_sum += conf
        if won:
            wins += 1
        else:
            losses += 1
        b = _bucket(conf)
        if b:
            conf_by_bucket[b]["w" if won else "l"] += 1

    resolved = wins + losses
    win_rate = round(wins / resolved, 4) if resolved else None
    sim_pnl = round(wins * payout - losses, 2)

    # Format bucket table with win-rate
    bucket_table = []
    for key, row in conf_by_bucket.items():
        n_b = row["w"] + row["l"]
        wr = round(row["w"] / n_b, 4) if n_b else None
        bucket_table.append({
            "bucket": key,
            "wins": row["w"],
            "losses": row["l"],
            "n": n_b,
            "win_rate": wr,
        })

    return {
        "signals": {
            "total": total, "calls": calls, "puts": puts, "neutrals": neutrals,
        },
        "wins": wins,
        "losses": losses,
        "sample_size": resolved,
        "win_rate": win_rate,
        "sim_pnl": sim_pnl,
        "payout_used": payout,
        "avg_confidence": round(conf_sum / (calls + puts), 2) if (calls + puts) else None,
        "confidence_buckets": bucket_table,
    }


# ---------------------------------------------------------------------------
# Ridicolous — extra probability tables (mirrors the on-chart TradingView table)
# ---------------------------------------------------------------------------
def _ridicolous_stats(df: pd.DataFrame, levels: int = 5, perc: float = 1.0) -> Dict[str, Any]:
    try:
        from strategies.strategy_ridicolous_breakout import RidicolousBreakoutPrediction
    except Exception:
        return {}
    if len(df) < 60:
        return {}
    opens = df["open"].astype(float).to_numpy()
    highs = df["high"].astype(float).to_numpy()
    lows = df["low"].astype(float).to_numpy()
    closes = df["close"].astype(float).to_numpy()
    step = float(closes[-1]) * (perc / 100.0)
    stats = RidicolousBreakoutPrediction._compute_stats(
        opens, highs, lows, closes, step, levels
    )
    # Build a level-by-level table for the UI
    table = []
    for i in range(levels):
        table.append({
            "level": i,
            "green_new_high_pct": stats["green_hh_pct"][i],
            "green_new_low_pct": stats["green_ll_pct"][i],
            "red_new_high_pct": stats["red_hh_pct"][i],
            "red_new_low_pct": stats["red_ll_pct"][i],
        })
    return {
        "step_pct": perc,
        "step_size": round(step, 6),
        "levels": levels,
        "green_total": stats["green_total"],
        "red_total": stats["red_total"],
        "probability_table": table,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/strategies/backtest")
async def backtest_strategy(payload: BacktestPayload):
    """Run a strategy chronologically over recent candles + simulate PnL."""
    from strategy_registry import strategy_registry

    base_strategy = strategy_registry.get_strategy(payload.strategy_id)
    if base_strategy is None:
        raise HTTPException(status_code=404,
                            detail=f"strategy '{payload.strategy_id}' not registered")

    # Iter 120c — When per-run params are supplied for Ridicolous, use a
    # fresh instance so we don't mutate the live singleton used by the
    # signal pipeline. Other strategies ignore `params`.
    strategy = base_strategy
    override_perc: Optional[float] = None
    override_levels: Optional[int] = None
    if payload.params and payload.strategy_id == "ridicolous_breakout_prediction":
        try:
            from strategies.strategy_ridicolous_breakout import RidicolousBreakoutPrediction
            strategy = RidicolousBreakoutPrediction()
            strategy.apply_config(payload.params)
            override_perc = strategy.perc
            override_levels = strategy.levels
        except Exception as e:
            logger.warning("failed to apply ridicolous params: %s", e)
            strategy = base_strategy

    # Estimate candle count from timeframe seconds × days
    tf_seconds = {
        "5s": 5, "15s": 15, "30s": 30,
        "1m": 60, "2m": 120, "3m": 180, "5m": 300,
    }.get(payload.timeframe, 60)
    est_candles = int(payload.days * 86400 // tf_seconds)
    limit = min(payload.max_candles, max(est_candles, 300))

    candles = await _load_candles(payload.asset, payload.timeframe, limit)
    if not candles or len(candles) < payload.min_history + 10:
        return {
            "success": False,
            "error": "insufficient historical candles",
            "candles_loaded": len(candles),
            "asset": payload.asset,
            "timeframe": payload.timeframe,
        }

    df = pd.DataFrame(candles)
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            return {"success": False, "error": f"missing {col} column in candles"}

    sim = _simulate(
        strategy, df,
        min_history=payload.min_history,
        payout=payload.payout,
        stride=payload.stride,
    )

    extra: Dict[str, Any] = {}
    if payload.strategy_id == "ridicolous_breakout_prediction":
        # Use the effective params for the probability table (per-run override
        # if provided, else the live singleton config)
        _perc = override_perc if override_perc is not None else getattr(strategy, "perc", 1.0)
        _levels = override_levels if override_levels is not None else getattr(strategy, "levels", 5)
        extra["ridicolous_table"] = _ridicolous_stats(df, levels=_levels, perc=_perc)
        extra["effective_config"] = {
            "perc": _perc, "levels": _levels,
            "min_history": getattr(strategy, "min_history", 60),
            "min_confidence": getattr(strategy, "min_confidence", 55.0),
        }

    return {
        "success": True,
        "strategy_id": payload.strategy_id,
        "strategy_name": getattr(strategy, "name", payload.strategy_id),
        "asset": payload.asset,
        "timeframe": payload.timeframe,
        "days_requested": payload.days,
        "candles_used": len(df),
        "min_history": payload.min_history,
        "stride": payload.stride,
        **sim,
        "strategy_specific": extra,
    }



# ---------------------------------------------------------------------------
# Iter 120c — Ridicolous live-tunable config
# ---------------------------------------------------------------------------
_RIDI_CFG_DOC_ID = "ridicolous_breakout_prediction"


class RidicolousConfig(BaseModel):
    perc: float = Field(1.0, ge=0.05, le=10.0,
                        description="Percentage step size between probability levels")
    levels: int = Field(5, ge=1, le=5,
                        description="Number of probability levels (1-5)")
    min_history: int = Field(60, ge=30, le=500,
                             description="Minimum candles required before firing")
    min_confidence: float = Field(55.0, ge=40.0, le=95.0,
                                  description="Minimum winning percentage to fire")


async def restore_ridicolous_config_from_db() -> Dict[str, Any]:
    """Called from server startup to reapply the last saved config to the singleton."""
    try:
        doc = await db.strategy_configs.find_one({"_id": _RIDI_CFG_DOC_ID})
        if doc:
            doc.pop("_id", None)
            from strategies.strategy_ridicolous_breakout import ridicolous_breakout_prediction
            return ridicolous_breakout_prediction.apply_config(doc)
    except Exception as e:
        logger.warning("ridicolous config restore failed: %s", e)
    return {}


@router.get("/strategies/ridicolous/config")
async def get_ridicolous_config():
    from strategies.strategy_ridicolous_breakout import ridicolous_breakout_prediction
    return {"success": True, "config": ridicolous_breakout_prediction.get_config()}


@router.post("/strategies/ridicolous/config")
async def set_ridicolous_config(payload: RidicolousConfig):
    from strategies.strategy_ridicolous_breakout import ridicolous_breakout_prediction
    effective = ridicolous_breakout_prediction.apply_config(payload.model_dump())
    await db.strategy_configs.replace_one(
        {"_id": _RIDI_CFG_DOC_ID},
        {"_id": _RIDI_CFG_DOC_ID, **effective},
        upsert=True,
    )
    return {"success": True, "config": effective}
