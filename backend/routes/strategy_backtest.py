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
from datetime import datetime, timezone
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
    return_trades: bool = False,
) -> Dict[str, Any]:
    """Walk chronologically, run generate_signal on candles[:i+1], score against candles[i+1]."""
    n = len(df)
    total = calls = puts = neutrals = wins = losses = 0
    conf_sum = 0.0
    trades: List[Dict[str, Any]] = []
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
        if return_trades:
            trades.append({"confidence": conf, "won": bool(won), "side": side})

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
        "trades": trades if return_trades else None,
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
    # Iter 121 — result cache keyed by the full payload
    try:
        from perf_cache import backtest_result_cache, stable_hash
        cache_key = stable_hash(payload.model_dump())
        cached = await backtest_result_cache.get(cache_key)
        if cached is not None:
            return {**cached, "cached": True}
    except Exception:
        backtest_result_cache = None  # noqa: F841 (defensive)
        cache_key = None

    base_strategy = strategy_registry.get_strategy(payload.strategy_id)
    if base_strategy is None:
        # Iter 122 — Friendly message for picker-only strategies. Many 1m/5s
        # picker entries route to the LIVE signal pipeline (no `generate_signal`),
        # so they can't be walked chronologically.
        raise HTTPException(
            status_code=400,
            detail=(
                f"Strategy '{payload.strategy_id}' does not support offline backtesting. "
                f"It runs through the live signal pipeline only. "
                f"Try 'ridicolous_breakout_prediction', 'algo_trend_momentum', "
                f"'algo_mean_reversion', or 'algo_volatility_regime' — those all support backtesting."
            ),
        )

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
            "error": (
                f"Not enough historical candles for {payload.asset} @ {payload.timeframe}. "
                f"Loaded {len(candles)}, need at least {payload.min_history + 10}. "
                f"Try a different asset (EURUSD_OTC / GBPUSD_OTC / AUDCAD_OTC usually have the most data), "
                f"a shorter day window, or a coarser timeframe."
            ),
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
    # Internal-only field; drop from public response
    sim.pop("trades", None)

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

    response = {
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
    # Iter 121 — cache the result for repeated identical requests
    try:
        if cache_key:
            from perf_cache import backtest_result_cache
            await backtest_result_cache.set(cache_key, response)
    except Exception:
        pass
    return response



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



# ---------------------------------------------------------------------------
# Iter 120d — Confidence-threshold autotuner
# ---------------------------------------------------------------------------
class AutotunePayload(BaseModel):
    strategy_id: str
    asset: str = "EURUSD_OTC"
    timeframe: str = "1m"
    days: int = Field(30, ge=1, le=365)
    max_candles: int = Field(3000, ge=100, le=20000)
    min_history: int = Field(60, ge=20, le=1000)
    payout: float = Field(0.85, ge=0.5, le=0.99)
    stride: int = Field(3, ge=1, le=20)
    # Sweep range
    conf_min: float = Field(50.0, ge=40.0, le=95.0)
    conf_max: float = Field(90.0, ge=40.0, le=99.0)
    conf_step: float = Field(5.0, ge=1.0, le=25.0)
    min_sample_size: int = Field(20, ge=5, le=1000,
                                 description="Reject thresholds that produce fewer than N resolved trades")
    # Strategy params passthrough (Ridicolous perc/levels stay fixed for the sweep)
    params: Optional[Dict[str, Any]] = None


def _sweep_thresholds(trades: List[Dict[str, Any]], thresholds: List[float],
                       payout: float, min_sample: int) -> List[Dict[str, Any]]:
    """For each threshold, count trades whose confidence >= t and compute WR + sim_pnl."""
    out = []
    for t in thresholds:
        subset = [tr for tr in trades if tr["confidence"] >= t]
        w = sum(1 for tr in subset if tr["won"])
        l = len(subset) - w
        n = w + l
        wr = round(w / n, 4) if n else None
        pnl = round(w * payout - l, 2)
        # Break-even at 85% payout ≈ 54.05% WR. Round up to a comfy 55.6%.
        break_even = 1.0 / (1.0 + payout)  # e.g. 0.5405
        eligible = (n >= min_sample) and (wr is not None) and (wr > break_even)
        out.append({
            "threshold": round(t, 1),
            "n": n,
            "wins": w,
            "losses": l,
            "win_rate": wr,
            "sim_pnl": pnl,
            "eligible": eligible,
        })
    return out


def _pick_recommendation(sweep: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Highest sim_pnl among eligible rows; tiebreaker = higher WR, then lower threshold."""
    eligibles = [r for r in sweep if r["eligible"]]
    if not eligibles:
        return None
    eligibles.sort(
        key=lambda r: (-r["sim_pnl"], -(r["win_rate"] or 0), r["threshold"])
    )
    return eligibles[0]


@router.post("/strategies/autotune-confidence")
async def autotune_confidence(payload: AutotunePayload):
    """Sweep min_confidence to find the EV-maximising threshold for a strategy+asset."""
    from strategy_registry import strategy_registry

    base_strategy = strategy_registry.get_strategy(payload.strategy_id)
    if base_strategy is None:
        raise HTTPException(status_code=404,
                            detail=f"strategy '{payload.strategy_id}' not registered")

    # For Ridicolous, we need to lower the strategy's own min_confidence to 40
    # (below every sweep step) so the raw trade stream includes low-conf signals
    # for post-hoc filtering.
    strategy = base_strategy
    if payload.strategy_id == "ridicolous_breakout_prediction":
        try:
            from strategies.strategy_ridicolous_breakout import RidicolousBreakoutPrediction
            strategy = RidicolousBreakoutPrediction()
            base_cfg = base_strategy.get_config()
            override = {**base_cfg, "min_confidence": 40.0}
            if payload.params:
                override.update(payload.params)
                override["min_confidence"] = 40.0  # force wide net for sweep
            strategy.apply_config(override)
        except Exception as e:
            logger.warning("autotune ridicolous override failed: %s", e)
            strategy = base_strategy

    tf_seconds = {"5s": 5, "15s": 15, "30s": 30, "1m": 60, "2m": 120, "3m": 180, "5m": 300}.get(payload.timeframe, 60)
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
    sim = _simulate(strategy, df,
                    min_history=payload.min_history,
                    payout=payload.payout,
                    stride=payload.stride,
                    return_trades=True)
    trades = sim.get("trades") or []

    if payload.conf_min >= payload.conf_max:
        raise HTTPException(status_code=422, detail="conf_min must be < conf_max")
    thresholds: List[float] = []
    t = payload.conf_min
    while t <= payload.conf_max + 1e-9:
        thresholds.append(round(t, 2))
        t += payload.conf_step

    sweep = _sweep_thresholds(trades, thresholds, payload.payout, payload.min_sample_size)
    recommendation = _pick_recommendation(sweep)

    # Persist the winner for later apply
    doc_id = f"{payload.strategy_id}::{payload.asset}::{payload.timeframe}"
    if recommendation:
        try:
            await db.strategy_autotune_recs.replace_one(
                {"_id": doc_id},
                {
                    "_id": doc_id,
                    "strategy_id": payload.strategy_id,
                    "asset": payload.asset,
                    "timeframe": payload.timeframe,
                    "recommendation": recommendation,
                    "days": payload.days,
                    "candles_used": len(df),
                    "trades_evaluated": len(trades),
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning("autotune persistence failed: %s", e)

    return {
        "success": True,
        "strategy_id": payload.strategy_id,
        "asset": payload.asset,
        "timeframe": payload.timeframe,
        "days": payload.days,
        "candles_used": len(df),
        "trades_evaluated": len(trades),
        "sweep": sweep,
        "recommendation": recommendation,
        "min_sample_size": payload.min_sample_size,
        "payout": payload.payout,
    }


@router.get("/strategies/autotune-confidence/recommendation")
async def get_autotune_recommendation(
    strategy_id: str, asset: str, timeframe: str = "1m",
):
    doc_id = f"{strategy_id}::{asset}::{timeframe}"
    doc = await db.strategy_autotune_recs.find_one({"_id": doc_id})
    if not doc:
        return {"success": True, "recommendation": None}
    doc.pop("_id", None)
    return {"success": True, **doc}


class ApplyAutotunePayload(BaseModel):
    strategy_id: str = "ridicolous_breakout_prediction"
    asset: str = "EURUSD_OTC"
    timeframe: str = "1m"
    threshold: Optional[float] = Field(None, ge=40.0, le=95.0,
                                       description="Explicit override; otherwise use the saved recommendation")


@router.post("/strategies/autotune-confidence/apply")
async def apply_autotune_recommendation(payload: ApplyAutotunePayload):
    """Apply the recommended min_confidence to the live Ridicolous singleton + persist to config."""
    if payload.strategy_id != "ridicolous_breakout_prediction":
        raise HTTPException(
            status_code=400,
            detail="apply-autotune currently supports ridicolous_breakout_prediction only"
        )

    threshold = payload.threshold
    if threshold is None:
        doc_id = f"{payload.strategy_id}::{payload.asset}::{payload.timeframe}"
        doc = await db.strategy_autotune_recs.find_one({"_id": doc_id})
        rec = (doc or {}).get("recommendation")
        if not rec:
            raise HTTPException(status_code=404, detail="no recommendation stored — run autotune first")
        threshold = float(rec["threshold"])

    from strategies.strategy_ridicolous_breakout import ridicolous_breakout_prediction
    effective = ridicolous_breakout_prediction.apply_config({"min_confidence": threshold})
    await db.strategy_configs.replace_one(
        {"_id": _RIDI_CFG_DOC_ID},
        {"_id": _RIDI_CFG_DOC_ID, **effective},
        upsert=True,
    )
    return {"success": True, "applied_threshold": threshold, "config": effective}
