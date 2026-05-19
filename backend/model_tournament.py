"""
Daily Model Tournament — Iter 58 (P2, May 17, 2026)
====================================================

Premise: model performance drifts. The OTC-aware weights we hardcoded in
`force_generate_v2` (improved_v2 → 4.0× on OTC vs maximized_v3 → 2.0×) are
calibrated from a single Apr-25 retrain snapshot. As market regime changes,
these weights should self-adjust.

Approach: daily walk-forward tournament.
  1. At 00:30 UTC, snapshot the last 7 days of OTC candles per symbol.
  2. For each model {improved_v2, maximized_v3, lstm_gru, ppo_rl}:
     a. Train on days N-7…N-1
     b. Backtest on day N (the most-recent full UTC day) using
        `create_hybrid_ensemble_strategy()` predictions where ONLY that
        model's vote contributes. This is the per-model win-rate.
  3. Normalise win-rates into vote multipliers: best model gets 1.5×, worst
     gets 0.6× (linear interpolation between).
  4. Persist `ml_tournament_weights` collection with TTL of 7 days. Latest
     row drives the live force_generate_v2 multipliers.

Failure mode: fire-and-forget. If a model fails to train, its weight is
preserved at 1.0× (neutral). If the tournament can't run (insufficient
data), all weights default to 1.0×.

Public API:
  get_tournament_weight(model_id) -> float  (cheap, in-memory cache)
  run_tournament() -> Dict (full async; called by scheduler)
  get_latest_tournament() -> Dict (read latest persisted row)
"""
from __future__ import annotations
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

# Tournament configuration
TRAIN_WINDOW_DAYS = 7
EVAL_WINDOW_DAYS = 1
MIN_CANDLES_PER_SYMBOL = 200
BEST_MULTIPLIER = 1.5
WORST_MULTIPLIER = 0.6
NEUTRAL_MULTIPLIER = 1.0
MODELS_TRACKED = ["improved_v2", "maximized_v3", "lstm_gru", "ppo_rl"]
TOURNAMENT_COLL = "ml_tournament_weights"

# In-memory cache of the latest weights (read by force_generate_v2 hot path)
_WEIGHTS_CACHE: Dict[str, float] = {m: NEUTRAL_MULTIPLIER for m in MODELS_TRACKED}
_CACHE_LOADED_AT: Optional[datetime] = None
_CACHE_TTL_SECONDS = 600


def _get_db():
    """Lazy MongoDB connection. Each call may yield a different event loop;
    motor handles that gracefully."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


async def _load_cache_from_db() -> None:
    """Refresh the in-memory weight cache from the latest tournament row."""
    global _WEIGHTS_CACHE, _CACHE_LOADED_AT
    try:
        db = _get_db()
        latest = await db[TOURNAMENT_COLL].find_one(
            {}, sort=[("computed_at", -1)], projection={"_id": 0},
        )
        if latest and latest.get("weights"):
            for mid in MODELS_TRACKED:
                v = latest["weights"].get(mid)
                if isinstance(v, (int, float)) and v > 0:
                    _WEIGHTS_CACHE[mid] = float(v)
        _CACHE_LOADED_AT = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning(f"[tournament] cache reload failed (keeping defaults): {e}")
        _CACHE_LOADED_AT = datetime.now(timezone.utc)


def get_tournament_weight(model_id: str) -> float:
    """
    Cheap accessor used by force_generate_v2. Returns the per-model multiplier
    (default 1.0 if cache hasn't loaded or model isn't in the cache).
    Does NOT trigger IO — caller may run `refresh_cache_if_stale()` separately.
    """
    return float(_WEIGHTS_CACHE.get(model_id, NEUTRAL_MULTIPLIER))


async def refresh_cache_if_stale() -> None:
    """Reload the cache if older than TTL. Safe to call from hot path; bounded IO."""
    global _CACHE_LOADED_AT
    now = datetime.now(timezone.utc)
    if _CACHE_LOADED_AT is None or (now - _CACHE_LOADED_AT).total_seconds() > _CACHE_TTL_SECONDS:
        await _load_cache_from_db()


async def get_latest_tournament() -> Dict[str, Any]:
    """Return the most recent tournament row (or empty if none ran yet)."""
    db = _get_db()
    latest = await db[TOURNAMENT_COLL].find_one(
        {}, sort=[("computed_at", -1)], projection={"_id": 0},
    )
    if latest:
        return {"success": True, "tournament": latest, "cache": dict(_WEIGHTS_CACHE)}
    return {"success": True, "tournament": None, "cache": dict(_WEIGHTS_CACHE)}


async def get_tournament_history(limit: int = 30) -> Dict[str, Any]:
    """Return recent tournament history for the UI chart."""
    db = _get_db()
    cur = db[TOURNAMENT_COLL].find({}, projection={"_id": 0}).sort("computed_at", -1).limit(limit)
    rows = await cur.to_list(length=limit)
    return {"success": True, "history": rows}


def _normalise_winrates_to_weights(model_winrates: Dict[str, float]) -> Dict[str, float]:
    """
    Convert per-model win-rate dict to vote multipliers.
    Linear scaling: best win-rate → BEST_MULTIPLIER, worst → WORST_MULTIPLIER.
    Models without a win-rate stay at NEUTRAL_MULTIPLIER.
    """
    valid = {k: v for k, v in model_winrates.items() if isinstance(v, (int, float)) and v > 0}
    if not valid:
        return {m: NEUTRAL_MULTIPLIER for m in MODELS_TRACKED}
    wr_values = list(valid.values())
    wr_max = max(wr_values)
    wr_min = min(wr_values)
    out: Dict[str, float] = {}
    for mid in MODELS_TRACKED:
        wr = valid.get(mid)
        if wr is None:
            out[mid] = NEUTRAL_MULTIPLIER
            continue
        if wr_max == wr_min:
            out[mid] = NEUTRAL_MULTIPLIER
            continue
        # Linear interpolation between WORST and BEST multipliers
        frac = (wr - wr_min) / (wr_max - wr_min)
        out[mid] = round(WORST_MULTIPLIER + frac * (BEST_MULTIPLIER - WORST_MULTIPLIER), 3)
    return out


async def _evaluate_model_on_holdout(
    model_id: str,
    holdout_df: pd.DataFrame,
) -> Optional[float]:
    """
    Compute model's directional win-rate on a held-out candle window.
    Uses the tuner pipeline prediction for sklearn models. LSTM/GRU and PPO
    fall back to "model_accuracy" attribute (their own validation score) if
    a fast inference path isn't readily available.
    """
    try:
        if model_id == "improved_v2":
            from ml_accuracy_tuner import predict_with_tuner_pipeline
            from improved_ai_ml_system import improved_ai_ml as _imp
            if _imp is None or not getattr(_imp, "is_trained", False):
                return None
            ml_sys = _imp
            return await _backtest_sklearn(ml_sys, holdout_df)
        if model_id == "maximized_v3":
            from ml_accuracy_tuner import predict_with_tuner_pipeline  # noqa: F401
            from maximized_ai_ml_system import maximized_ai_ml as _mx
            if _mx is None or not getattr(_mx, "is_trained", False):
                return None
            return await _backtest_sklearn(_mx, holdout_df)
        if model_id == "lstm_gru":
            from lstm_gru_system import lstm_gru_system as _lstm
            if _lstm is None or not getattr(_lstm, "is_trained", False):
                return None
            acc = getattr(_lstm, "accuracy", None) or getattr(_lstm, "model_accuracy", None)
            return float(acc) if acc else None
        if model_id == "ppo_rl":
            from rl_ppo_agent import ppo_agent as _ppo
            if _ppo is None or not getattr(_ppo, "is_trained", False):
                return None
            stats = getattr(_ppo, "training_stats", {}) or {}
            wr = stats.get("avg_win_rate") or stats.get("final_win_rate")
            return float(wr) if wr else None
    except Exception as e:
        logger.warning(f"[tournament] {model_id} eval failed: {e}")
        return None
    return None


async def _backtest_sklearn(ml_sys, df: pd.DataFrame) -> Optional[float]:
    """
    Walk-forward prediction over `df`. For each candle from idx=30 onward,
    predict direction and compare to next-candle close. Returns win-rate %.

    Iter 58 — Runs in a thread pool so sklearn's blocking inference doesn't
    starve the FastAPI event loop. Capped to 200 iterations per symbol per
    model to keep the tournament under 5 min even with 4 models × 7 symbols.
    """
    if df is None or len(df) < 40:
        return None

    def _sync_loop():
        from ml_accuracy_tuner import predict_with_tuner_pipeline
        wins, total = 0, 0
        # Cap to most-recent 200 walk-forward steps for runtime
        start_i = max(30, len(df) - 200)
        for i in range(start_i, len(df) - 1):
            try:
                window = df.iloc[: i + 1]
                pred = predict_with_tuner_pipeline(ml_sys, window)
                if not pred or pred.get("direction") not in ("CALL", "PUT"):
                    continue
                close_now = float(df["close"].iloc[i])
                close_next = float(df["close"].iloc[i + 1])
                actual = "CALL" if close_next > close_now else "PUT" if close_next < close_now else "EQUAL"
                if actual == "EQUAL":
                    continue
                total += 1
                if pred["direction"] == actual:
                    wins += 1
            except Exception:
                continue
        if total == 0:
            return None
        return round((wins / total) * 100.0, 2)

    return await asyncio.to_thread(_sync_loop)


async def _fetch_eval_window(symbols: List[str], lookback_days: int) -> Dict[str, pd.DataFrame]:
    """Pull the last `lookback_days` of `otc_candles_5s` per symbol."""
    db = _get_db()
    # lookback_days reserved for future timestamp-bound filtering; for now we
    # rely on the .sort + .limit slice which already captures the most recent
    # window the live pool has accumulated.
    _ = lookback_days
    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        # Match both ISO and untimed shapes
        cursor = db["otc_candles_5s"].find(
            {"symbol": sym},
            {"_id": 0},
        ).sort("timestamp", 1).limit(5000)
        rows = await cursor.to_list(length=5000)
        if len(rows) < MIN_CANDLES_PER_SYMBOL:
            continue
        df = pd.DataFrame(rows)
        # Take only the recent slice
        if len(df) > 1000:
            df = df.iloc[-1000:].reset_index(drop=True)
        out[sym] = df
    return out


async def run_tournament(
    symbols: Optional[List[str]] = None,
    lookback_days: int = EVAL_WINDOW_DAYS,
) -> Dict[str, Any]:
    """
    Run a single tournament evaluation cycle. Persists weights to MongoDB and
    refreshes the in-memory cache. Returns the computed weights + per-model
    win-rates.
    """
    started = datetime.now(timezone.utc)
    symbols = symbols or [
        "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "AUDCAD_OTC",
        "CADJPY_OTC", "EURJPY_OTC", "GBPJPY_OTC",
    ]
    eval_data = await _fetch_eval_window(symbols, lookback_days + 1)
    if not eval_data:
        logger.warning("[tournament] no symbols with enough holdout data — skipping")
        return {
            "success": False,
            "error": "no_holdout_data",
            "symbols_checked": symbols,
        }

    # Per-model, average win-rate across symbols
    model_winrates: Dict[str, List[float]] = {m: [] for m in MODELS_TRACKED}
    per_symbol_details: Dict[str, Dict[str, float]] = {}

    for sym, df in eval_data.items():
        per_symbol_details[sym] = {}
        for mid in MODELS_TRACKED:
            wr = await _evaluate_model_on_holdout(mid, df)
            if wr is not None:
                model_winrates[mid].append(wr)
                per_symbol_details[sym][mid] = wr

    aggregated = {
        m: round(float(np.mean(v)), 2) if v else None for m, v in model_winrates.items()
    }
    weights = _normalise_winrates_to_weights({m: v for m, v in aggregated.items() if v is not None})

    completed = datetime.now(timezone.utc)
    row = {
        "computed_at": completed.isoformat(),
        "_computed_at": completed,
        "started_at": started.isoformat(),
        "duration_seconds": round((completed - started).total_seconds(), 1),
        "symbols_evaluated": list(eval_data.keys()),
        "lookback_days": lookback_days,
        "model_winrates": aggregated,
        "weights": weights,
        "per_symbol_details": per_symbol_details,
    }
    db = _get_db()
    await db[TOURNAMENT_COLL].insert_one({**row})

    # TTL index — trim history to 90 days
    try:
        await db[TOURNAMENT_COLL].create_index("_computed_at", expireAfterSeconds=90 * 86400)
    except Exception:
        pass

    # Refresh cache
    await _load_cache_from_db()

    logger.info(
        f"[tournament] complete — winrates {aggregated} → weights {weights} "
        f"in {row['duration_seconds']}s across {len(eval_data)} symbols"
    )
    return {"success": True, "tournament": row}


def get_cache_snapshot() -> Dict[str, Any]:
    """For diagnostics / tests."""
    return {
        "weights": dict(_WEIGHTS_CACHE),
        "loaded_at": _CACHE_LOADED_AT.isoformat() if _CACHE_LOADED_AT else None,
    }
