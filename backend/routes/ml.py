"""Auto-extracted route module from server.py refactoring."""
from fastapi import APIRouter, HTTPException, Query, Request, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging
import json
import uuid
import os
import asyncio
import pandas as pd
import numpy as np

from routes import db, convert_numpy_types, logger

# Re-use the main api_router — routes are registered via include in server.py
# This module uses a local router that gets included by server.py
router = APIRouter()
from enhanced_oanda_service import enhanced_oanda
from maximized_ai_ml_system import maximized_ai_ml
from ai_learning_system import ai_learning_system
from routes import get_realtime_market_hub
from pocket_option_client import get_pocket_option_client

# Lazy import for ML trainer to avoid circular dependency
def get_ml_trainer():
    """Get ML trainer from server module"""
    from server import get_ml_trainer as _get_ml_trainer
    return _get_ml_trainer()

try:
    from lstm_gru_system import lstm_gru_system
except ImportError:
    lstm_gru_system = None
try:
    from rl_ppo_agent import ppo_agent
except ImportError:
    ppo_agent = None
try:
    from enhanced_ai_ml_system import enhanced_ai_ml
except ImportError:
    enhanced_ai_ml = None
try:
    from improved_ai_ml_system import improved_ai_ml
except ImportError:
    improved_ai_ml = None
try:
    from ai_lstm_predictor import lstm_predictor
except ImportError:
    lstm_predictor = None
try:
    from ai_ml_trading_system import ai_ml_trading_system, TENSORFLOW_AVAILABLE, SKLEARN_AVAILABLE
except ImportError:
    ai_ml_trading_system = None
    TENSORFLOW_AVAILABLE = False
    SKLEARN_AVAILABLE = False

from routes.models import AISignalRequest, AITrainingRequest, GenerateSignalRequest, TradeResultRequest, TrainModelRequest



# =====================================================
# AI LEARNING SYSTEM ENDPOINTS
# =====================================================

@router.get("/ai-learning/config")
async def get_ai_learning_config():
    """Get AI learning system configuration"""
    try:
        config = await db.ai_config.find_one({"type": "learning_config"}, {"_id": 0})
        return config or {
            "model_config": {
                "primary_model": "enhanced_rsi_bb_volume",
                "secondary_model": "support_resistance",
                "use_ensemble": True,
                "ensemble_method": "weighted_average",
                "min_model_agreement": 2,
                "confidence_threshold": 75
            },
            "learning_config": {
                "enabled": True,
                "learning_rate": 0.01,
                "adaptation_speed": "medium",
                "use_market_regime": True,
                "use_volatility_filter": True,
                "lookback_periods": 100,
                "min_samples_for_update": 50
            }
        }
    except Exception as e:
        logger.error(f"Error getting AI learning config: {e}")
        return {"model_config": {}, "learning_config": {}}



@router.post("/ai-learning/config")
async def update_ai_learning_config(config: dict):
    """Update AI learning system configuration"""
    try:
        await db.ai_config.update_one(
            {"type": "learning_config"},
            {"$set": {**config, "type": "learning_config", "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        return {"success": True, "message": "AI learning config updated"}
    except Exception as e:
        logger.error(f"Error updating AI learning config: {e}")
        return {"success": False, "error": str(e)}



@router.get("/ai-learning/performance")
async def get_ai_learning_performance():
    """Get model performance metrics"""
    try:
        # Get performance data from database
        perf_data = await db.model_performance.find({}, {"_id": 0}).to_list(100)
        
        # Calculate average accuracy
        total_acc = 0
        count = 0
        result = {}
        
        for p in perf_data:
            model_id = p.get("model_id")
            if model_id:
                result[model_id] = {
                    "accuracy": p.get("accuracy", 70),
                    "trades": p.get("trades", 0)
                }
                total_acc += p.get("accuracy", 70)
                count += 1
        
        result["average_accuracy"] = total_acc / count if count > 0 else 75
        return result
    except Exception as e:
        logger.error(f"Error getting AI performance: {e}")
        return {"average_accuracy": 75}



@router.get("/ai-learning/stats")
async def get_ai_learning_stats():
    """Get AI learning statistics"""
    try:
        stats = await db.ai_config.find_one({"type": "learning_stats"}, {"_id": 0})
        return stats or {
            "total_cycles": 0,
            "last_retrain": "Never",
            "samples_collected": 0,
            "accuracy_improvement": 0
        }
    except Exception as e:
        logger.error(f"Error getting AI learning stats: {e}")
        return {"total_cycles": 0, "last_retrain": "Never"}



@router.post("/ai-learning/retrain")
async def retrain_ai_models(request: dict):
    """Trigger model retraining"""
    try:
        models = request.get("models", [])
        use_recent_data = request.get("use_recent_data", True)
        epochs = request.get("epochs", 100)
        
        # Update stats
        await db.ai_config.update_one(
            {"type": "learning_stats"},
            {
                "$set": {
                    "type": "learning_stats",
                    "last_retrain": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "retrain_models": models,
                    "epochs": epochs
                },
                "$inc": {"total_cycles": 1}
            },
            upsert=True
        )
        
        return {
            "success": True,
            "message": f"Retraining {len(models)} models with {epochs} epochs",
            "models": models
        }
    except Exception as e:
        logger.error(f"Error retraining models: {e}")
        return {"success": False, "error": str(e)}



@router.post("/ai-learning/reset")
async def reset_ai_learning():
    """Reset all learning parameters"""
    try:
        await db.ai_config.update_one(
            {"type": "learning_stats"},
            {
                "$set": {
                    "type": "learning_stats",
                    "total_cycles": 0,
                    "last_retrain": "Never",
                    "samples_collected": 0,
                    "accuracy_improvement": 0,
                    "reset_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        return {"success": True, "message": "Learning parameters reset"}
    except Exception as e:
        logger.error(f"Error resetting AI learning: {e}")
        return {"success": False, "error": str(e)}


# Global retrain status tracker
_retrain_status = {
    "running": False,
    "phase": "",
    "progress": 0,
    "results": {},
    "started_at": None,
    "completed_at": None,
    "error": None
}


@router.post("/ml/clean-retrain")
async def clean_retrain_all_models(background_tasks: BackgroundTasks):
    """
    Clean retrain ALL ML models with fresh OANDA data.
    Runs as background task — check progress via GET /api/ml/retrain-status
    """
    global _retrain_status
    
    if _retrain_status["running"]:
        return {
            "success": False,
            "message": "Retrain already in progress",
            "status": _retrain_status
        }
    
    _retrain_status = {
        "running": True,
        "phase": "starting",
        "progress": 0,
        "results": {},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None
    }
    
    async def _do_clean_retrain():
        global _retrain_status
        try:
            # Phase 1: Clear corrupted performance data
            _retrain_status["phase"] = "clearing_corrupted_data"
            _retrain_status["progress"] = 5
            
            collections_cleared = {}
            for coll_name in [
                "premium_asset_performance",
                "asset_performance", 
                "asset_hourly_performance",
                "hourly_stats",
                "recent_asset_trades",
                "signal_validations"
            ]:
                try:
                    result = await db[coll_name].delete_many({})
                    collections_cleared[coll_name] = result.deleted_count
                except Exception as e:
                    collections_cleared[coll_name] = f"error: {e}"
            
            _retrain_status["results"]["cleared_collections"] = collections_cleared
            _retrain_status["progress"] = 15
            logger.info(f"Cleared corrupted data: {collections_cleared}")
            
            # Phase 2: Retrain Maximized ML v3.0
            _retrain_status["phase"] = "training_maximized_ml_v3"
            _retrain_status["progress"] = 20
            
            try:
                if maximized_ai_ml is not None:
                    result = await asyncio.to_thread(
                        lambda: asyncio.run(maximized_ai_ml.train_from_oanda(
                            enhanced_oanda,
                            symbols=['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'EUR_JPY'],
                            candle_count=2000,
                            timeframes=['S5', 'S15', 'S30', 'M1']
                        ))
                    )
                    _retrain_status["results"]["maximized_ml"] = {"success": True, "result": "trained"}
                    logger.info(f"Maximized ML retrained")
                else:
                    _retrain_status["results"]["maximized_ml"] = {"skipped": True}
            except Exception as e:
                _retrain_status["results"]["maximized_ml"] = {"error": str(e)}
                logger.error(f"Maximized ML retrain error: {e}")
            
            _retrain_status["progress"] = 45
            
            # Phase 3: Retrain Improved ML v2.0
            _retrain_status["phase"] = "training_improved_ml_v2"
            
            try:
                if improved_ai_ml is not None:
                    result = await asyncio.to_thread(
                        lambda: asyncio.run(improved_ai_ml.train_from_oanda(
                            enhanced_oanda,
                            symbols=['EUR_USD', 'GBP_USD', 'USD_JPY'],
                            candle_count=2000,
                            timeframes=['S5', 'S15', 'S30', 'M1']
                        ))
                    )
                    _retrain_status["results"]["improved_ml"] = {"success": True, "result": "trained"}
                    logger.info(f"Improved ML retrained")
                else:
                    _retrain_status["results"]["improved_ml"] = {"skipped": True}
            except Exception as e:
                _retrain_status["results"]["improved_ml"] = {"error": str(e)}
                logger.error(f"Improved ML retrain error: {e}")
            
            _retrain_status["progress"] = 65
            
            # Phase 4: Retrain LSTM/GRU
            _retrain_status["phase"] = "training_lstm_gru"
            
            try:
                if lstm_gru_system is not None:
                    df = enhanced_oanda.get_candles('EUR_USD', 'M1', 2000)
                    if df is not None and len(df) >= 100:
                        candles = [{'open': float(r['open']), 'high': float(r['high']),
                                    'low': float(r['low']), 'close': float(r['close']),
                                    'volume': float(r.get('volume', 0))}
                                   for _, r in df.iterrows()]
                        result = await asyncio.to_thread(lstm_gru_system.train, candles, 30)
                        _retrain_status["results"]["lstm_gru"] = {"success": True, "result": str(result)[:200]}
                        logger.info(f"LSTM/GRU retrained")
                    else:
                        _retrain_status["results"]["lstm_gru"] = {"error": "Insufficient data"}
                else:
                    _retrain_status["results"]["lstm_gru"] = {"skipped": True}
            except Exception as e:
                _retrain_status["results"]["lstm_gru"] = {"error": str(e)}
                logger.error(f"LSTM/GRU retrain error: {e}")
            
            _retrain_status["progress"] = 85
            
            # Phase 5: Retrain PPO RL
            _retrain_status["phase"] = "training_ppo_rl"
            
            try:
                if ppo_agent is not None:
                    from lstm_gru_system import FeatureEngine
                    df = enhanced_oanda.get_candles('EUR_USD', 'M1', 2000)
                    if df is not None and len(df) >= 100:
                        candles = [{'open': float(r['open']), 'high': float(r['high']),
                                    'low': float(r['low']), 'close': float(r['close']),
                                    'volume': float(r.get('volume', 0))}
                                   for _, r in df.iterrows()]
                        features = FeatureEngine.compute(candles)
                        if features is not None:
                            closes = np.array([float(c['close']) for c in candles])
                            result = await asyncio.to_thread(ppo_agent.train, features, closes, 10)
                            _retrain_status["results"]["ppo_rl"] = {"success": True, "result": str(result)[:200]}
                            logger.info(f"PPO RL retrained")
                        else:
                            _retrain_status["results"]["ppo_rl"] = {"error": "Feature computation failed"}
                    else:
                        _retrain_status["results"]["ppo_rl"] = {"error": "Insufficient data"}
                else:
                    _retrain_status["results"]["ppo_rl"] = {"skipped": True}
            except Exception as e:
                _retrain_status["results"]["ppo_rl"] = {"error": str(e)}
                logger.error(f"PPO RL retrain error: {e}")
            
            # Done
            _retrain_status["phase"] = "complete"
            _retrain_status["progress"] = 100
            _retrain_status["running"] = False
            _retrain_status["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Clean retrain complete")
            
        except Exception as e:
            _retrain_status["phase"] = "error"
            _retrain_status["error"] = str(e)
            _retrain_status["running"] = False
            logger.error(f"Clean retrain failed: {e}")
    
    # Use asyncio.create_task so it runs on the main event loop but doesn't block the response
    asyncio.create_task(_do_clean_retrain())
    
    return {
        "success": True,
        "message": "Clean retrain started. Clearing corrupted data and retraining all 4 ML model types with fresh OANDA data.",
        "check_status": "GET /api/ml/retrain-status"
    }


@router.get("/ml/retrain-status")
async def get_retrain_status():
    """Get the current status of the clean retrain process."""
    return {
        "success": True,
        **_retrain_status
    }




# =====================================================
# ML MODEL TRAINING ENDPOINTS
# =====================================================

@router.post("/ml-training/train-from-backtests")
async def train_ml_from_backtests(request: dict = {}):
    """
    Train ML models using recent backtest results.
    This implements the continuous learning loop.
    """
    try:
        from ml_training_service import get_ml_training_service
        from dataclasses import asdict
        
        service = await get_ml_training_service(db)

        # Get recent backtest results — v8.123.0 now supports asset + timeframe
        # filters so users can scope training to short-TF (5s/15s/30s) buckets
        # instead of averaging the model across an entire mixed corpus.
        limit = int(request.get("limit", 100))
        asset_filter = (request.get("asset") or "all").strip()
        timeframe_filter = (request.get("timeframe") or "all").strip()

        mongo_filter = {}
        if timeframe_filter and timeframe_filter.lower() != "all":
            mongo_filter["timeframe"] = timeframe_filter
        if asset_filter and asset_filter.lower() != "all":
            mongo_filter["asset"] = asset_filter

        results = await db.backtest_results.find(
            mongo_filter, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)

        if len(results) < 10:
            scope_msg = ""
            if mongo_filter:
                parts = []
                if "timeframe" in mongo_filter:
                    parts.append(f"timeframe={mongo_filter['timeframe']}")
                if "asset" in mongo_filter:
                    parts.append(f"asset={mongo_filter['asset']}")
                scope_msg = f" for {' + '.join(parts)}"
            return {
                "success": False,
                "error": (
                    f"Insufficient backtest results{scope_msg} "
                    f"(need ≥10, have {len(results)}). Run more backtests on this "
                    "asset/timeframe from the Backtesting page and try again."
                ),
                "results_count": len(results),
                "asset_filter": asset_filter,
                "timeframe_filter": timeframe_filter,
            }

        # v8.74.0 — Pre-flight check: surface a precise diagnosis instead of
        # the misleading "Trained 0 ML models" success path. Legacy backtest
        # records (written before v8.74.0) only stored aggregate metrics, so
        # the per-trade ML trainer would silently return zero models. Now we
        # tell the user exactly what to do.
        results_with_trades = sum(1 for r in results if isinstance(r.get("trades"), list) and r["trades"])
        total_trades_available = sum(len(r.get("trades") or []) for r in results)
        if total_trades_available < 100:
            return {
                "success": False,
                "error": (
                    f"Not enough per-trade samples to train (need ≥100, have {total_trades_available}). "
                    f"{results_with_trades}/{len(results)} stored backtests carry a `trades[]` array. "
                    "Re-run the backtests from the Backtesting page (v8.74.0+ persists trades) "
                    "and try again, or use AI Models → Real Data Training which trains from live "
                    "candles in MongoDB."
                ),
                "results_count": len(results),
                "results_with_trades": results_with_trades,
                "total_trades_available": total_trades_available,
                "needs_retrain_action": "rerun_backtests",
            }

        # Train models — pass through the same filters the query used so the
        # saved model documents are properly tagged in Mongo.
        asset = asset_filter if asset_filter and asset_filter.lower() != "all" else "all"
        timeframe = timeframe_filter if timeframe_filter and timeframe_filter.lower() != "all" else "all"

        trained_models = await service.train_from_backtest_results(results, asset, timeframe)

        # If the trainer still returns 0 models (e.g. all trades had no
        # `result`/`outcome` label), tell the user what's wrong.
        if not trained_models:
            return {
                "success": False,
                "error": (
                    f"Found {total_trades_available} trades but the trainer rejected them "
                    "(check that each trade has a `result`, `outcome`, or `is_win` field). "
                    "Re-run the latest backtests to populate per-trade labels."
                ),
                "results_count": len(results),
                "total_trades_available": total_trades_available,
            }

        # Convert to serializable format
        models_data = {k: asdict(v) for k, v in trained_models.items()}
        
        return {
            "success": True,
            "message": f"Trained {len(trained_models)} ML models from {len(results)} backtest results ({total_trades_available} trades) — asset={asset}, tf={timeframe}",
            "models": models_data,
            "total_trades_used": total_trades_available,
            "asset_filter": asset,
            "timeframe_filter": timeframe,
        }
        
    except Exception as e:
        logger.error(f"Error training ML models: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}




@router.post("/ml-training/train-on-price-data")
async def train_ml_on_price_data(request: dict):
    """
    Train ML models on historical price data for a specific asset/timeframe.

    Iter 60 — Prefers `otc_candles_5s` (or `historical_candles`) over the
    `BacktestingService` data fetcher, which silently falls back to synthetic
    data when real sources are dry. Synthetic data poisoned every model with
    50% accuracy because the labels were uncorrelated with the random walk.
    """
    try:
        from ml_training_service import get_ml_training_service
        from dataclasses import asdict
        from historical_data_service import historical_data_service

        asset_raw = request.get("asset", "EURUSD")
        timeframe = request.get("timeframe", "M1")
        days = min(int(request.get("days", 30)), 90)

        # Iter 87 — Normalise asset code so OTC lookups aren't case-sensitive.
        # Frontend passes `EURUSD_otc` (lowercase) but `otc_candles_5s` and
        # our OANDA symbol mapper both key on `_OTC` (uppercase). Without
        # this normalisation, every OTC + short-TF request 0-hits both
        # sources and errors as "Insufficient REAL price data".
        asset = str(asset_raw).upper()

        # Prefer the same OTC + OANDA fallback path the backtesting endpoint uses
        price_df = historical_data_service.get_candles_for_backtest(asset, timeframe, days)
        data_source = "otc_pool_or_oanda"

        # Iter 87 — Short-TF resilience: feature engineering (RSI/MACD/ATR
        # warm-up + label-shift) shaves ~40% off the raw candle count. A
        # 110-row OTC-pool result becomes 61 usable samples which trips the
        # `train_on_price_data` 100-sample minimum. Trigger OANDA fallback
        # whenever the pool is thin (< 400 raw candles) instead of only when
        # empty.
        raw_len = 0 if price_df is None else len(price_df)
        needs_oanda = (price_df is None) or price_df.empty or (raw_len < 400)
        if needs_oanda:
            try:
                from enhanced_oanda_service import enhanced_oanda
                oanda_symbol = asset.upper().replace("_OTC", "").replace("OTC", "")
                if "_" not in oanda_symbol and len(oanda_symbol) == 6:
                    oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
                tf_map = {"M1": "M1", "M5": "M5", "M15": "M15", "M30": "M30",
                          "H1": "H1", "H4": "H4", "D1": "D",
                          "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
                          "1h": "H1", "4h": "H4", "1d": "D",
                          "5s": "S5", "10s": "S10", "15s": "S15", "30s": "S30"}
                oanda_tf = tf_map.get(timeframe, "M1")
                df = enhanced_oanda.get_candles(oanda_symbol, oanda_tf, count=1000)
                if df is not None and not df.empty:
                    oanda_df = df.reset_index() if "timestamp" not in df.columns else df
                    # Only override the OTC pool if OANDA gave us MORE data.
                    if len(oanda_df) > raw_len:
                        price_df = oanda_df
                        data_source = "oanda"
            except Exception as _oe:
                logger.warning(f"OANDA fallback for ML training also failed: {_oe}")

        if price_df is None or len(price_df) < 100:
            return {
                "success": False,
                "error": (
                    f"Insufficient REAL price data for {asset} ({timeframe}, last {days}d). "
                    f"Got {0 if price_df is None else len(price_df)} candles. Synthetic-data "
                    "fallback was DISABLED in Iter 60 to prevent training on noise."
                ),
                "data_source": data_source,
            }

        # Train models
        ml_service = await get_ml_training_service(db)
        trained_models = await ml_service.train_on_price_data(price_df, asset, timeframe)

        if not trained_models:
            return {
                "success": False,
                "error": (
                    f"Model training returned zero models. Got {len(price_df)} raw candles "
                    f"but feature engineering left too few samples after indicator warm-up. "
                    f"Try a larger `days` window or a longer timeframe."
                ),
                "data_source": data_source,
                "candles_used": len(price_df),
            }

        models_data = {k: asdict(v) for k, v in trained_models.items()}

        return {
            "success": True,
            "message": f"Trained {len(trained_models)} ML models on {len(price_df)} REAL candles from {data_source}",
            "asset": asset,
            "timeframe": timeframe,
            "data_source": data_source,
            "candles_used": len(price_df),
            "models": models_data,
        }

    except Exception as e:
        logger.error(f"Error training on price data: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}




@router.post("/ml-training/predict")
async def ml_predict_signal(request: dict):
    """
    Use trained ML models to predict signal direction.
    """
    try:
        from ml_training_service import get_ml_training_service
        from backtesting_service import BacktestingService
        
        asset = request.get("asset", "EURUSD")
        timeframe = request.get("timeframe", "1h")
        
        # Fetch recent price data - pass db for real MongoDB data access
        backtest_service = BacktestingService(db=db)
        price_df, _ = await backtest_service.data_fetcher.fetch_historical_data(
            asset,
            backtest_service._determine_asset_type(asset),
            7,  # Last 7 days
            timeframe
        )
        
        if price_df is None or len(price_df) < 50:
            return {
                "success": False,
                "error": "Insufficient price data for prediction"
            }
        
        # Get prediction
        ml_service = await get_ml_training_service(db)
        prediction = await ml_service.predict_signal(price_df, asset, timeframe)
        
        if "error" in prediction:
            return {"success": False, **prediction}
        
        return {
            "success": True,
            "prediction": prediction
        }
        
    except Exception as e:
        logger.error(f"Error making ML prediction: {e}")
        return {"success": False, "error": str(e)}




@router.get("/ml-training/models")
async def get_ml_models():
    """Get all trained ML models and their performance metrics."""
    try:
        from ml_training_service import get_ml_training_service
        
        ml_service = await get_ml_training_service(db)
        models = await ml_service.get_model_performance()
        
        return {
            "success": True,
            "models": models,
            "count": len(models)
        }
        
    except Exception as e:
        logger.error(f"Error getting ML models: {e}")
        return {"success": False, "error": str(e), "models": []}




@router.post("/ml-training/reset-optimization-history")
async def reset_optimization_history(request: dict = None):
    """
    Iter 60 — Wipe contaminated backtest_results so the optimization endpoint
    sees a clean dataset post-fixes. Accepts:
        - `confirm` (required): must equal "yes" — guard against accidental wipes
        - `only_negative` (optional, default false): if true, only delete rows
          with negative `total_profit` (keeps profitable history intact)
        - `older_than_days` (optional): if set, only delete rows older than N days
    Returns the deletion counts. Safe to re-run.
    """
    req = request or {}
    if (req.get("confirm") or "").lower() != "yes":
        return {
            "success": False,
            "error": "Must POST {'confirm': 'yes'} to wipe optimization history. This is irreversible.",
        }
    try:
        from datetime import timedelta as _td
        filt: Dict[str, Any] = {}
        if req.get("only_negative"):
            filt["total_profit"] = {"$lt": 0}
        if req.get("older_than_days"):
            cutoff = (datetime.now(timezone.utc) - _td(days=int(req["older_than_days"]))).isoformat()
            filt["created_at"] = {"$lt": cutoff}

        before_total = await db.backtest_results.count_documents({})
        before_filt = await db.backtest_results.count_documents(filt) if filt else before_total
        res = await db.backtest_results.delete_many(filt) if filt else await db.backtest_results.delete_many({})
        after = await db.backtest_results.count_documents({})

        logger.info(
            f"[reset-optimization-history] deleted {res.deleted_count} rows "
            f"(filter={filt}, before={before_total}, after={after})"
        )
        return {
            "success": True,
            "deleted": res.deleted_count,
            "remaining": after,
            "filter": filt or "ALL",
            "before_total": before_total,
            "matched_filter": before_filt,
        }
    except Exception as e:
        logger.error(f"Error resetting optimization history: {e}")
        return {"success": False, "error": str(e)}


@router.post("/ml-training/run-optimization")
async def run_strategy_optimization(request: dict = None):
    """
    Run ML-based strategy optimization.
    Analyzes backtest results to find optimal strategy parameters.
    """
    try:
        # Get all backtest results
        results = await db.backtest_results.find({}, {"_id": 0}).to_list(500)
        
        if len(results) < 5:
            return {
                "success": False,
                "error": "Need at least 5 backtest results for optimization"
            }
        
        # Analyze results by strategy
        strategy_stats = {}
        for result in results:
            strategy = result.get('strategy', 'unknown')
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_profit': 0,
                    'win_rates': [],
                    'rois': []
                }
            
            stats = strategy_stats[strategy]
            stats['total_trades'] += result.get('total_trades', 0)
            stats['winning_trades'] += result.get('winning_trades', 0)
            stats['total_profit'] += result.get('total_profit', 0)
            stats['win_rates'].append(result.get('win_rate', 0))
            stats['rois'].append(result.get('roi', 0))
        
        # Calculate optimization recommendations
        # Iter 60 — rank by COMPOSITE score (win-rate × profitability × confidence),
        # not just win-rate. Previous code recommended a -$63,827 loss strategy
        # as "HIGH" because it had 57% win-rate — but huge losses per loss trade
        # destroyed it. Composite ranking + profitability gate fix this.
        import math
        MIN_TRADES_FOR_RECOMMENDATION = 30
        recommendations = []
        for strategy, stats in strategy_stats.items():
            if stats['total_trades'] <= 0:
                continue
            avg_win_rate = sum(stats['win_rates']) / len(stats['win_rates'])
            avg_roi = sum(stats['rois']) / len(stats['rois'])
            total_profit = stats['total_profit']
            n_trades = stats['total_trades']

            # Composite score: edge above 50% × log10(trade-count+1)
            # Profitability gate is enforced by tier, not by sign flipping.
            edge = (avg_win_rate - 50.0) / 50.0  # range [-1, +1]
            confidence = math.log10(max(1, n_trades) + 1)
            composite_score = round(edge * confidence, 4)

            # Recommendation tier
            if n_trades < MIN_TRADES_FOR_RECOMMENDATION:
                rec_tier = "INSUFFICIENT_DATA"
            elif total_profit < 0:
                # Anything losing money is AVOID regardless of win-rate
                rec_tier = "AVOID_LOSS_MAKER"
            elif avg_win_rate >= 60 and avg_roi >= 5:
                rec_tier = "HIGH"
            elif avg_win_rate >= 55 and avg_roi >= 0:
                rec_tier = "MEDIUM"
            elif avg_win_rate >= 50:
                rec_tier = "LOW"
            else:
                rec_tier = "AVOID"

            recommendations.append({
                'strategy': strategy,
                'total_trades': n_trades,
                'avg_win_rate': round(avg_win_rate, 2),
                'avg_roi': round(avg_roi, 2),
                'total_profit': round(total_profit, 2),
                'composite_score': composite_score,
                'recommendation': rec_tier,
            })

        # Sort by tier first (HIGH > MEDIUM > LOW > INSUFFICIENT_DATA > AVOID >
        # AVOID_LOSS_MAKER), then by composite score within each tier
        _tier_rank = {
            "HIGH": 0, "MEDIUM": 1, "LOW": 2,
            "INSUFFICIENT_DATA": 3, "AVOID": 4, "AVOID_LOSS_MAKER": 5,
        }
        recommendations.sort(key=lambda x: (_tier_rank.get(x['recommendation'], 99), -x['composite_score']))

        # Best strategy = first profitable HIGH/MEDIUM; fall back to top composite
        best_strategy = next(
            (r for r in recommendations if r['recommendation'] in ('HIGH', 'MEDIUM')),
            recommendations[0] if recommendations else None,
        )
        
        return {
            "success": True,
            "total_results_analyzed": len(results),
            "strategies_analyzed": len(strategy_stats),
            "best_strategy": best_strategy,
            "all_recommendations": recommendations,
            "optimization_tips": [
                f"Best performing strategy: {best_strategy['strategy']} ({best_strategy['avg_win_rate']}% win rate)" if best_strategy else "Run more backtests",
                "Strategies with >55% win rate are recommended for live trading",
                "Consider combining high-performing strategies in ensemble mode"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error running optimization: {e}")
        return {"success": False, "error": str(e)}




@router.post("/ml-training/schedule-daily-retrain")
async def schedule_daily_retrain():
    """Enable daily automatic model retraining."""
    try:
        from ml_training_service import get_ml_training_service
        
        ml_service = await get_ml_training_service(db)
        
        # Start background task for daily retraining
        asyncio.create_task(ml_service.schedule_daily_retrain())
        
        return {
            "success": True,
            "message": "Daily ML retraining scheduled. Models will retrain at midnight UTC."
        }
        
    except Exception as e:
        logger.error(f"Error scheduling retraining: {e}")
        return {"success": False, "error": str(e)}




@router.post("/ml-training/retrain-now")
async def retrain_models_now():
    """Manually trigger immediate model retraining."""
    try:
        from ml_training_service import get_ml_training_service
        
        ml_service = await get_ml_training_service(db)
        await ml_service.run_daily_retrain()
        
        return {
            "success": True,
            "message": "ML models retrained successfully"
        }
        
    except Exception as e:
        logger.error(f"Error retraining models: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# ENHANCED ML SYSTEM ENDPOINTS
# =====================================================

@router.post("/enhanced-ml/train")
async def train_enhanced_ml():
    """Train the enhanced ML model from historical validated signals."""
    try:
        if enhanced_ai_ml is None:
            return {"success": False, "error": "Enhanced ML system not available"}
        
        result = await enhanced_ai_ml.train_from_historical(db, days=30)
        return result
        
    except Exception as e:
        logger.error(f"Error training enhanced ML: {e}")
        return {"success": False, "error": str(e)}



@router.get("/enhanced-ml/stats")
async def get_enhanced_ml_stats():
    """Get enhanced ML system statistics."""
    try:
        if enhanced_ai_ml is None:
            return {"success": False, "error": "Enhanced ML system not available"}
        
        return {
            "success": True,
            "stats": enhanced_ai_ml.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Error getting ML stats: {e}")
        return {"success": False, "error": str(e)}



@router.post("/enhanced-ml/predict/{symbol}")
async def get_enhanced_ml_prediction(symbol: str):
    """Get ML prediction for a symbol."""
    try:
        if enhanced_ai_ml is None:
            return {"success": False, "error": "Enhanced ML system not available"}
        
        # Get market data
        candles = await get_realtime_market_hub().get_historical_candles(symbol, '1m', 100)
        
        if not candles or len(candles) < 50:
            return {"success": False, "error": "Insufficient market data"}
        
        df = pd.DataFrame(candles)
        df = df.rename(columns={'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'})
        
        prediction = enhanced_ai_ml.predict(df)
        
        if prediction:
            return {
                "success": True,
                "symbol": symbol,
                "prediction": prediction
            }
        else:
            return {"success": False, "error": "Could not generate prediction"}
        
    except Exception as e:
        logger.error(f"Error getting ML prediction: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# IMPROVED ML SYSTEM v2.0 ENDPOINTS
# =====================================================

@router.post("/improved-ml/train")
async def train_improved_ml():
    """Train the improved ML model v2.0 using OANDA historical data."""
    try:
        if improved_ai_ml is None:
            return {"success": False, "error": "Improved ML system not available"}
        
        # Debug: Check OANDA status first
        logger.info(f"🔍 OANDA configured: {enhanced_oanda.is_configured}")
        logger.info(f"🔍 OANDA API: {enhanced_oanda.api}")
        
        # Test getting candles directly
        test_df = enhanced_oanda.get_candles('EUR_USD', 'M1', 10)
        logger.info(f"🔍 Test candle fetch: {test_df.shape if test_df is not None and not test_df.empty else 'EMPTY'}")
        
        # Use enhanced OANDA service for training data
        result = await improved_ai_ml.train_from_oanda(
            enhanced_oanda, 
            symbols=['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'EUR_JPY'],
            candle_count=2000
        )
        return result
        
    except Exception as e:
        logger.error(f"Error training improved ML: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}




@router.post("/improved-ml/train-extended")
async def train_improved_ml_extended():
    """Train with extended data (5000 candles per symbol) for better accuracy."""
    try:
        if improved_ai_ml is None:
            return {"success": False, "error": "Improved ML system not available"}
        
        # Train with more data and more symbols
        result = await improved_ai_ml.train_from_oanda(
            enhanced_oanda, 
            symbols=['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'EUR_JPY', 
                    'USD_CHF', 'NZD_USD', 'EUR_GBP', 'EUR_AUD', 'GBP_JPY'],
            candle_count=5000
        )
        return result
        
    except Exception as e:
        logger.error(f"Error training extended ML: {e}")
        return {"success": False, "error": str(e)}



@router.get("/improved-ml/stats")
async def get_improved_ml_stats():
    """Get improved ML system v2.0 statistics."""
    try:
        if improved_ai_ml is None:
            return {"success": False, "error": "Improved ML system not available"}
        
        return {
            "success": True,
            "stats": improved_ai_ml.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Error getting improved ML stats: {e}")
        return {"success": False, "error": str(e)}



@router.post("/improved-ml/predict/{symbol}")
async def get_improved_ml_prediction(symbol: str):
    """Get improved ML v2.0 prediction for a symbol."""
    try:
        if improved_ai_ml is None:
            return {"success": False, "error": "Improved ML system not available"}
        
        # Convert symbol format (EUR_USD -> EURUSD for market hub)
        market_symbol = symbol.replace('_', '')
        
        # Get market data from OANDA (synchronous call)
        df = enhanced_oanda.get_candles(symbol, granularity='M1', count=100)
        
        if df is None or df.empty:
            # Fallback to market hub
            candles = await get_realtime_market_hub().get_historical_candles(market_symbol, '1m', 100)
            if candles and len(candles) >= 50:
                df = pd.DataFrame(candles)
                if 'c' in df.columns:
                    df = df.rename(columns={'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'})
        
        if df is None or df.empty or len(df) < 50:
            return {"success": False, "error": "Insufficient market data"}
        
        # Ensure numeric
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if 'volume' not in df.columns:
            df['volume'] = 1.0
        
        prediction = improved_ai_ml.predict(df)
        
        if prediction:
            return {
                "success": True,
                "symbol": symbol,
                "prediction": prediction
            }
        else:
            return {"success": False, "error": "Could not generate prediction - model may need training"}
        
    except Exception as e:
        logger.error(f"Error getting improved ML prediction: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# MAXIMIZED AI/ML SYSTEM v3.0 ENDPOINTS
# =====================================================

@router.post("/maximized-ml/train")
async def train_maximized_ml():
    """Train the maximized ML model v3.0 with XGBoost + LightGBM stacking ensemble."""
    try:
        if maximized_ai_ml is None:
            return {"success": False, "error": "Maximized ML system not available"}
        
        result = await maximized_ai_ml.train_from_oanda(
            enhanced_oanda,
            symbols=['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'EUR_JPY',
                    'USD_CHF', 'NZD_USD', 'EUR_GBP', 'GBP_JPY', 'AUD_JPY'],
            candle_count=3000
        )
        return result
        
    except Exception as e:
        logger.error(f"Error training maximized ML: {e}")
        return {"success": False, "error": str(e)}




@router.get("/maximized-ml/stats")
async def get_maximized_ml_stats():
    """Get maximized ML system v3.0 statistics."""
    try:
        if maximized_ai_ml is None:
            return {"success": False, "error": "Maximized ML system not available"}
        
        return {"success": True, "stats": maximized_ai_ml.get_stats()}
        
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/maximized-ml/predict/{symbol}")
async def get_maximized_ml_prediction(symbol: str):
    """Get maximized ML v3.0 prediction with regime detection."""
    try:
        if maximized_ai_ml is None:
            return {"success": False, "error": "Maximized ML system not available"}
        
        # Convert symbol format to OANDA format (EUR_USD)
        oanda_symbol = symbol.replace('/', '_')
        if '_' not in oanda_symbol:
            # Convert EURUSD to EUR_USD
            oanda_symbol = oanda_symbol[:3] + '_' + oanda_symbol[3:] if len(oanda_symbol) == 6 else oanda_symbol
        
        df = enhanced_oanda.get_candles(oanda_symbol, granularity='M1', count=100)
        
        if df is None or df.empty:
            # Fallback to market hub with original symbol format
            market_symbol = symbol.replace('_', '').replace('/', '')
            candles = await get_realtime_market_hub().get_historical_candles(market_symbol, '1m', 100)
            if candles and len(candles) >= 60:
                df = pd.DataFrame(candles)
                if 'c' in df.columns:
                    df = df.rename(columns={'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'})
        
        if df is None or df.empty or len(df) < 60:
            return {"success": False, "error": "Insufficient market data (need 60+ candles)"}
        
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if 'volume' not in df.columns:
            df['volume'] = 1.0
        
        prediction = maximized_ai_ml.predict(df)
        
        if prediction:
            return {"success": True, "symbol": symbol, "prediction": prediction}
        else:
            return {"success": False, "error": "Could not generate prediction - model may need training"}
        
    except Exception as e:
        logger.error(f"Error getting maximized ML prediction: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# AI LEARNING SYSTEM ENDPOINTS
# =====================================================

@router.post("/ai/learn")
async def trigger_ai_learning():
    """
    Manually trigger AI learning cycle
    Analyzes recent validations and adjusts strategies
    """
    try:
        await ai_learning_system.analyze_and_learn()
        return {
            "success": True,
            "message": "AI learning cycle completed",
            "adjustments": ai_learning_system.get_current_adjustments()
        }
    except Exception as e:
        logger.error(f"Error in AI learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/ai/report")
async def get_learning_report():
    """
    Get AI learning report with recommendations
    """
    try:
        report = await ai_learning_system.generate_learning_report()
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        logger.error(f"Error generating AI report: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/ai/adjustments")
async def get_current_adjustments():
    """
    Get current AI strategy adjustments
    """
    try:
        adjustments = ai_learning_system.get_current_adjustments()
        return {
            "success": True,
            "adjustments": adjustments
        }
    except Exception as e:
        logger.error(f"Error getting adjustments: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== LSTM AI PREDICTOR ENDPOINTS ====================

@router.post("/ai/lstm/predict")
async def lstm_predict(asset: str, timeframe: int = 60):
    """
    Get LSTM AI prediction for price direction
    
    Args:
        asset: Asset symbol
        timeframe: Timeframe in seconds
    """
    try:
        client = await get_pocket_option_client(is_demo=True)
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Pocket Option not connected")
        
        # Get candles
        candles = await client.get_candles(asset, timeframe, 100)
        
        if not candles:
            raise HTTPException(status_code=404, detail="No candle data available")
        
        # Get LSTM prediction
        prediction = lstm_predictor.predict(candles)
        
        return {
            "success": True,
            "asset": asset,
            "timeframe": timeframe,
            **prediction
        }
    except Exception as e:
        logger.error(f"Error in LSTM prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/ai/lstm/status")
async def get_lstm_status():
    """Get LSTM model training status"""
    return {
        "success": True,
        "is_trained": lstm_predictor.is_trained,
        "model_path": lstm_predictor.model_path,
        "sequence_length": lstm_predictor.sequence_length
    }



@router.post("/ai-ml/predict")
async def get_ai_ml_prediction(symbol: str = Query("EURUSD_OTC")):
    """
    Get AI/ML ensemble prediction for 15-second trading.
    
    Combines LSTM, Random Forest, and Emergent LLM predictions.
    
    Args:
        symbol: Trading symbol (e.g., EURUSD_OTC, BTCUSD)
        
    Returns:
        Ensemble prediction with confidence, direction, and risk assessment
    """
    try:
        import yfinance as yf
        
        # Parse symbol
        base_symbol = symbol.replace('_OTC', '').replace('_otc', '').replace('_regular', '')
        
        # Convert to yfinance format
        yf_symbol = base_symbol
        if base_symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD']:
            yf_symbol = f'{base_symbol}=X'
        elif base_symbol == 'BTCUSD':
            yf_symbol = 'BTC-USD'
        elif base_symbol == 'ETHUSD':
            yf_symbol = 'ETH-USD'
        
        # Fetch candle data
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d", interval="1m")
        
        if hist.empty or len(hist) < 60:
            return {
                "success": False,
                "message": f"Insufficient data for {symbol}",
                "prediction": None
            }
        
        # Convert to candle format
        candles = []
        for idx, row in hist.iterrows():
            candles.append({
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume'])
            })
        
        # Get AI prediction
        prediction = await get_ai_prediction(candles, symbol)
        
        # Send to Telegram if high confidence
        if prediction and prediction.get('final_confidence', 0) >= 75:
            try:
                if telegram_notifier:
                    msg = "🤖 AI/ML PREDICTION\n\n"
                    msg += f"💹 Asset: {symbol}\n"
                    msg += f"📈 Direction: {'🟢 BUY/CALL' if prediction['final_direction'] == 'BUY' else '🔴 SELL/PUT' if prediction['final_direction'] == 'SELL' else '⏸️ HOLD'}\n"
                    msg += f"🎯 Confidence: {prediction['final_confidence']:.1f}%\n"
                    msg += f"📊 Consensus: {prediction['consensus_score']:.0%}\n"
                    msg += f"⚠️ Risk Level: {prediction['risk_level']}\n"
                    msg += f"💰 Recommended Stake: {prediction['recommended_stake_percent']:.2f}%"
                    
                    await telegram_notifier.send_notification(msg)
            except Exception as e:
                logger.warning(f"Telegram notification failed: {e}")
        
        return {
            "success": True,
            "symbol": symbol,
            "prediction": prediction,
            "models_used": len(prediction.get('individual_predictions', [])),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI ML prediction error: {e}")
        return {
            "success": False,
            "error": str(e),
            "prediction": None
        }




@router.get("/ai-ml/status")
async def get_ai_ml_status():
    """
    Get AI ML Trading System status.
    
    Returns availability of each model (LSTM, RandomForest, LLM).
    """
    try:
        from ai_ml_trading_system import TENSORFLOW_AVAILABLE, SKLEARN_AVAILABLE, EMERGENT_LLM_AVAILABLE
        
        return {
            "success": True,
            "system_name": "AI ML Trading System",
            "models": {
                "lstm": {
                    "available": TENSORFLOW_AVAILABLE,
                    "trained": ai_ml_trading_system.lstm_predictor.is_trained if TENSORFLOW_AVAILABLE else False,
                    "description": "LSTM Neural Network for time series prediction"
                },
                "random_forest": {
                    "available": SKLEARN_AVAILABLE,
                    "trained": ai_ml_trading_system.rf_predictor.is_trained if SKLEARN_AVAILABLE else False,
                    "description": "Random Forest classifier for fast inference"
                },
                "emergent_llm": {
                    "available": ai_ml_trading_system.llm_predictor.is_available,
                    "model": "GPT-4o",
                    "description": "Emergent LLM for market analysis and pattern recognition"
                }
            },
            "model_weights": ai_ml_trading_system.model_weights,
            "prediction_history_size": len(ai_ml_trading_system.prediction_history)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/ai-ml/train")
async def train_ai_models(background_tasks: BackgroundTasks, 
                           epochs: int = Query(default=50, ge=10, le=200)):
    """
    Train AI models on historical data (background task).
    
    Args:
        epochs: Number of training epochs for LSTM
    """
    try:
        import yfinance as yf
        
        # Fetch training data
        symbols = ['EURUSD=X', 'GBPUSD=X', 'BTC-USD']
        all_candles = []
        
        for yf_symbol in symbols:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="1mo", interval="1m")
            
            for idx, row in hist.iterrows():
                all_candles.append({
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                })
        
        if len(all_candles) < 1000:
            return {
                "success": False,
                "message": "Insufficient training data"
            }
        
        # Train in background
        def train_task_sync():
            try:
                ai_ml_trading_system.lstm_predictor.train(all_candles, epochs=epochs)
                logger.info("✅ AI models training completed")
            except Exception as e:
                logger.error(f"Training error: {e}")
        
        background_tasks.add_task(train_task_sync)
        
        return {
            "success": True,
            "message": f"Training started with {len(all_candles)} candles, {epochs} epochs",
            "data_points": len(all_candles)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/ml-trainer/train")
async def train_ml_model(request: TrainModelRequest, background_tasks: BackgroundTasks):
    """
    Train a high-accuracy ML model using collected real data.
    
    Args:
        asset: Asset symbol (e.g., 'EURUSD_otc')
        timeframe: Timeframe ('5s', '1m', '5m')
        confidence_threshold: Minimum confidence for signals (0.5-0.95)
        min_samples: Minimum samples required for training
    """
    try:
        trainer = get_ml_trainer()
        
        result = await trainer.train_model(
            asset=request.asset,
            timeframe=request.timeframe,
            confidence_threshold=request.confidence_threshold,
            min_samples=request.min_samples
        )
        
        return result
    except Exception as e:
        logger.error(f"Error training model: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}




@router.post("/ml-trainer/signal")
async def generate_ml_signal(request: GenerateSignalRequest):
    """
    Generate a trading signal using trained model.
    
    Requires model to be trained first via /ml-trainer/train
    """
    try:
        trainer = get_ml_trainer()
        
        signal = await trainer.generate_signal(
            asset=request.asset,
            timeframe=request.timeframe,
            current_data=request.candles
        )
        
        if signal:
            return {
                "success": True,
                "has_signal": True,
                "signal": signal
            }
        else:
            return {
                "success": True,
                "has_signal": False,
                "message": "No signal - confidence below threshold or model not trained"
            }
    except Exception as e:
        logger.error(f"Error generating signal: {e}")
        return {"success": False, "error": str(e)}




@router.get("/ml-trainer/models")
async def get_ml_models_status():
    """Get status of all trained models"""
    try:
        trainer = get_ml_trainer()
        status = trainer.get_model_status()
        history = trainer.get_training_history()
        
        return {
            "success": True,
            "models": status,
            "training_history": history[-10:]  # Last 10 trainings
        }
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        return {"success": False, "error": str(e)}




@router.get("/ml-trainer/performance/{asset}/{timeframe}")
async def get_model_performance(asset: str, timeframe: str):
    """Get detailed performance metrics for a trained model"""
    try:
        trainer = get_ml_trainer()
        model_key = f"{asset}_{timeframe}"
        
        # Try to load model if not in memory
        if model_key not in trainer.models:
            from real_data_trainer import HighAccuracyEnsemble
            model = HighAccuracyEnsemble()
            if model.load(asset, timeframe):
                trainer.models[model_key] = model
            else:
                return {
                    "success": False,
                    "error": f"No trained model found for {asset} {timeframe}"
                }
        
        model = trainer.models[model_key]
        
        return {
            "success": True,
            "asset": asset,
            "timeframe": timeframe,
            "performance": model.performance.to_dict(),
            "feature_importance": model.get_feature_importance(),
            "confidence_threshold": model.confidence_threshold
        }
    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# MARKET REGIME DETECTOR ENDPOINTS
# =====================================================

@router.get("/regime/status")
async def get_regime_status():
    """Get current market regime and streak status"""
    detector = get_regime_detector()
    
    if detector:
        return {
            "success": True,
            **detector.get_status()
        }
    
    return {
        "success": False,
        "error": "Regime detector not initialized"
    }




@router.post("/regime/record-trade")
async def record_trade_result(trade_data: dict):
    """
    Record a trade result for regime tracking
    
    Body: {
        "direction": "CALL" or "PUT",
        "symbol": "EURUSD_otc",
        "is_win": true/false
    }
    """
    detector = get_regime_detector()
    
    if not detector:
        return {
            "success": False,
            "error": "Regime detector not initialized"
        }
    
    direction = trade_data.get("direction", "CALL")
    symbol = trade_data.get("symbol", "UNKNOWN")
    is_win = trade_data.get("is_win", False)
    
    detector.record_trade_result(direction, symbol, is_win)
    
    return {
        "success": True,
        "message": f"Trade recorded: {'WIN' if is_win else 'LOSS'}",
        **detector.get_status()
    }




@router.post("/regime/reset-streak")
async def reset_streak():
    """Reset the streak counter and disable inversion"""
    detector = get_regime_detector()
    
    if not detector:
        return {
            "success": False,
            "error": "Regime detector not initialized"
        }
    
    detector.current_streak = 0
    detector.streak_inversion_active = False
    detector.win_loss_history.clear()
    
    return {
        "success": True,
        "message": "Streak reset successfully",
        **detector.get_status()
    }




@router.post("/regime/toggle-inversion")
async def toggle_streak_inversion(data: dict):
    """Manually toggle streak inversion"""
    detector = get_regime_detector()
    
    if not detector:
        return {
            "success": False,
            "error": "Regime detector not initialized"
        }
    
    enabled = data.get("enabled", not detector.streak_inversion_active)
    detector.streak_inversion_active = enabled
    
    return {
        "success": True,
        "message": f"Streak inversion {'enabled' if enabled else 'disabled'}",
        "streak_inversion_active": detector.streak_inversion_active
    }




# ========================================
# ENHANCED AI/ML TRADING SYSTEM ENDPOINTS
# ========================================

@router.get("/ai-system/status")
async def get_ai_system_status():
    """Get Enhanced AI Trading System status"""
    try:
        status = enhanced_ai_system.get_system_status()
        return {"success": True, **_convert_numpy_types(status)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/ai-system/train")
async def train_ai_models(request: AITrainingRequest):
    """
    Train AI models with historical data.
    Uses OANDA data if configured, otherwise uses cached/simulated data.
    """
    try:
        # Fetch data from OANDA if configured
        if oanda_service.is_configured:
            candles = await oanda_service.get_candles(
                instrument=request.instrument,
                granularity=request.timeframe,
                count=request.candle_count
            )
            
            if candles:
                import numpy as np
                ohlcv_data = {
                    "open": np.array([c.open for c in candles]),
                    "high": np.array([c.high for c in candles]),
                    "low": np.array([c.low for c in candles]),
                    "close": np.array([c.close for c in candles]),
                    "volume": np.array([c.volume for c in candles])
                }
                
                result = await enhanced_ai_system.train_models(ohlcv_data)
                return {
                    "success": result.get("success", False),
                    "data_source": "OANDA",
                    **_convert_numpy_types(result)
                }
        
        # Fallback: Use simulated/cached data for training
        return {
            "success": False,
            "error": "OANDA not configured. Please configure OANDA API to train with real market data.",
            "data_source": "none"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/ai-system/generate-signal")
async def generate_ai_signal(request: AISignalRequest):
    """
    Generate AI-powered trading signal.
    Combines trend following, mean reversion, and pattern recognition.
    """
    try:
        ohlcv_data = None
        
        # Get market data
        if oanda_service.is_configured:
            candles = await oanda_service.get_candles(
                instrument=request.instrument,
                granularity=request.timeframe,
                count=100
            )
            
            if candles:
                import numpy as np
                ohlcv_data = {
                    "open": np.array([c.open for c in candles]),
                    "high": np.array([c.high for c in candles]),
                    "low": np.array([c.low for c in candles]),
                    "close": np.array([c.close for c in candles]),
                    "volume": np.array([c.volume for c in candles])
                }
        
        if ohlcv_data is None:
            return {
                "success": False,
                "error": "No market data available. Configure OANDA API for real market data."
            }
        
        # Load custom strategy if specified
        custom_strategy = None
        if request.custom_strategy_id:
            strategy_doc = await db.custom_strategies.find_one({"id": request.custom_strategy_id})
            if strategy_doc:
                custom_strategy = {
                    "name": strategy_doc.get("name"),
                    "conditions": strategy_doc.get("conditions", [])
                }
        
        # Generate signal
        signal = await enhanced_ai_system.generate_signal(ohlcv_data, custom_strategy)
        
        if signal:
            return {
                "success": True,
                "signal": _convert_numpy_types(signal.to_dict()),
                "custom_strategy_used": request.custom_strategy_id is not None
            }
        
        return {
            "success": False,
            "error": "Could not generate signal. Models may need training."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/ai-system/record-result")
async def record_ai_trade_result(request: TradeResultRequest):
    """Record trade result for continuous learning"""
    try:
        result = await enhanced_ai_system.record_trade_result(
            signal_id=request.signal_id,
            outcome=request.outcome
        )
        return _convert_numpy_types(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================
# LSTM/GRU Time-Series System Endpoints
# ============================================================

@router.get("/lstm-gru/stats")
async def get_lstm_gru_stats():
    """Get LSTM/GRU system status and statistics."""
    if lstm_gru_system is None:
        return {"success": False, "error": "LSTM/GRU system not available"}
    return {"success": True, **lstm_gru_system.get_stats()}


@router.post("/lstm-gru/train")
async def train_lstm_gru(
    symbol: str = Query("EUR_USD"),
    granularity: str = Query("M1"),
    count: int = Query(2000, ge=200, le=5000),
    epochs: int = Query(30, ge=5, le=100),
    background_tasks: BackgroundTasks = None
):
    """Train LSTM/GRU model on OANDA historical data."""
    if lstm_gru_system is None:
        raise HTTPException(400, "LSTM/GRU system not available")

    def _train_sync():
        """Synchronous training function for background task."""
        try:
            df = enhanced_oanda.get_candles(symbol, granularity, count)
            if df is None or len(df) < 100:
                logger.error(f"Insufficient candles for LSTM/GRU training: {len(df) if df is not None else 0}")
                return
            candles = [{'open': float(r['open']), 'high': float(r['high']),
                        'low': float(r['low']), 'close': float(r['close']),
                        'volume': float(r.get('volume', 0))}
                       for _, r in df.iterrows()]
            result = lstm_gru_system.train(candles, epochs=epochs)
            logger.info(f"LSTM/GRU training result: {result}")
        except Exception as e:
            logger.error(f"LSTM/GRU training error: {e}")
            import traceback
            traceback.print_exc()

    background_tasks.add_task(_train_sync)

    return {
        "success": True,
        "message": f"LSTM/GRU training started: {symbol} {granularity} x{count}, {epochs} epochs",
        "status": "training_started"
    }


@router.post("/lstm-gru/predict")
async def predict_lstm_gru(symbol: str = Query("EUR_USD"), granularity: str = Query("M1")):
    """Get LSTM/GRU prediction for a symbol."""
    if lstm_gru_system is None:
        raise HTTPException(400, "LSTM/GRU system not available")

    df = enhanced_oanda.get_candles(symbol, granularity, 100)
    if df is None or len(df) < 30:
        raise HTTPException(400, "Insufficient market data")

    candles = [{'open': float(r['open']), 'high': float(r['high']),
                'low': float(r['low']), 'close': float(r['close']),
                'volume': float(r.get('volume', 0))}
               for _, r in df.iterrows()]

    result = lstm_gru_system.predict(candles)
    return {"success": True, "symbol": symbol, "prediction": result}


# ============================================================
# PPO Reinforcement Learning Endpoints
# ============================================================

@router.get("/ppo-rl/stats")
async def get_ppo_stats():
    """Get PPO RL agent status and statistics."""
    if ppo_agent is None:
        return {"success": False, "error": "PPO agent not available"}
    return {"success": True, **ppo_agent.get_stats()}


@router.post("/ppo-rl/train")
async def train_ppo(
    symbol: str = Query("EUR_USD"),
    granularity: str = Query("M1"),
    count: int = Query(5000, ge=500, le=20000),
    episodes: int = Query(50, ge=5, le=200),
    background_tasks: BackgroundTasks = None
):
    """Train PPO RL agent on OANDA historical data.

    Iter 84 — bumped defaults: 2 000 → 5 000 candles, 20 → 50 episodes.
    The old defaults produced ≤82 trades over training which was nowhere near
    enough for PPO to converge on financial data. Empirically we need at
    least ~500 trades of experience across ≥40 episodes for the policy
    entropy to stabilize.
    """
    if ppo_agent is None:
        raise HTTPException(400, "PPO agent not available")

    def _train_ppo_sync():
        """Synchronous PPO training function for background task."""
        try:
            from lstm_gru_system import FeatureEngine
            df = enhanced_oanda.get_candles(symbol, granularity, count)
            if df is None or len(df) < 100:
                logger.error(f"Insufficient candles for PPO training: {len(df) if df is not None else 0}")
                return
            candles = [{'open': float(r['open']), 'high': float(r['high']),
                        'low': float(r['low']), 'close': float(r['close']),
                        'volume': float(r.get('volume', 0))}
                       for _, r in df.iterrows()]
            features = FeatureEngine.compute(candles)
            if features is None:
                logger.error("Feature computation failed for PPO")
                return
            closes = np.array([float(c['close']) for c in candles])
            result = ppo_agent.train(features, closes, n_episodes=episodes)
            logger.info(f"PPO training result: {result}")
        except Exception as e:
            logger.error(f"PPO training error: {e}")
            import traceback
            traceback.print_exc()

    background_tasks.add_task(_train_ppo_sync)

    return {
        "success": True,
        "message": f"PPO training started: {symbol} {granularity} x{count}, {episodes} episodes",
        "status": "training_started"
    }


@router.post("/ppo-rl/predict")
async def predict_ppo(symbol: str = Query("EUR_USD"), granularity: str = Query("M1")):
    """Get PPO RL prediction for a symbol."""
    if ppo_agent is None:
        raise HTTPException(400, "PPO agent not available")

    from lstm_gru_system import FeatureEngine
    df = enhanced_oanda.get_candles(symbol, granularity, 100)
    if df is None or len(df) < 30:
        raise HTTPException(400, "Insufficient market data")

    candles = [{'open': float(r['open']), 'high': float(r['high']),
                'low': float(r['low']), 'close': float(r['close']),
                'volume': float(r.get('volume', 0))}
               for _, r in df.iterrows()]

    features = FeatureEngine.compute(candles)
    if features is None:
        raise HTTPException(400, "Feature computation failed")

    result = ppo_agent.predict(features)
    return {"success": True, "symbol": symbol, "prediction": result}


# ============================================================
# Combined AI/ML Ensemble Prediction
# ============================================================

@router.post("/ai-ensemble/predict")
async def ensemble_predict(symbol: str = Query("EUR_USD"), granularity: str = Query("M1")):
    """
    Get combined prediction from all ML systems:
    1. Stacking Ensemble (XGBoost/LightGBM/RF/GB)
    2. LSTM/GRU Time-Series
    3. PPO Reinforcement Learning
    """
    from lstm_gru_system import FeatureEngine

    df = enhanced_oanda.get_candles(symbol, granularity, 100)
    if df is None or len(df) < 30:
        raise HTTPException(400, "Insufficient market data")

    candles = [{'open': float(r['open']), 'high': float(r['high']),
                'low': float(r['low']), 'close': float(r['close']),
                'volume': float(r.get('volume', 0))}
               for _, r in df.iterrows()]

    predictions = {}
    votes = {'BUY': 0, 'SELL': 0, 'HOLD': 0}

    # Iter 84 — DYNAMIC ensemble weights based on live per-model accuracy.
    # Old hardcoded {stacking: 0.4, lstm_gru: 0.35, ppo: 0.25} was letting
    # a 29%-accuracy PPO drag the ensemble around. Now weights come from
    # each model's edge above 50% baseline, and any model below the
    # min_trusted threshold (default 45%) is EXCLUDED from the vote.
    try:
        from ensemble_weights import compute_weights as _ew
        _weight_info = _ew(
            stacking_model=maximized_ai_ml,
            lstm_gru=lstm_gru_system,
            ppo=ppo_agent,
        )
        _w = _weight_info["weights"]
        weights = {
            'stacking': _w.get('stacking', 0.0),
            'lstm_gru': _w.get('lstm_gru', 0.0),
            'ppo':      _w.get('ppo', 0.0),
        }
    except Exception as _ew_exc:
        logger.warning(f"[ai-ensemble] dynamic weights failed, falling back: {_ew_exc}")
        weights = {'stacking': 0.4, 'lstm_gru': 0.35, 'ppo': 0.25}
        _weight_info = {"weights": weights, "excluded": [], "reason": {"__fallback__": str(_ew_exc)}}

    # Iter 84 — REGIME-AWARE tilt. Classify the last 50 candles into
    # trend/range/high-vol and nudge weights toward the model best suited
    # for that regime (LSTM/PPO for trends, stacking for ranges).
    try:
        from regime_classifier import classify_regime, apply_regime_bias
        _regime = classify_regime(candles, lookback=50)
        _tilted = apply_regime_bias(weights, _regime.get("regime", "range"))
        weights = {
            'stacking': _tilted.get('stacking', weights.get('stacking', 0.0)),
            'lstm_gru': _tilted.get('lstm_gru', weights.get('lstm_gru', 0.0)),
            'ppo':      _tilted.get('ppo', weights.get('ppo', 0.0)),
        }
    except Exception as _re_exc:
        logger.debug(f"[ai-ensemble] regime bias skipped: {_re_exc}")
        _regime = {"regime": "unknown", "confidence": 0.0}

    # 1. Stacking Ensemble
    try:
        if maximized_ai_ml and maximized_ai_ml.is_trained:
            ml_df = pd.DataFrame(candles)
            for col in ['open', 'high', 'low', 'close']:
                ml_df[col] = pd.to_numeric(ml_df[col], errors='coerce')
            pred = maximized_ai_ml.predict(ml_df)
            if pred:
                predictions['stacking_ensemble'] = pred
                d = pred.get('direction', 'HOLD').upper()
                if d in ('BUY', 'CALL'):
                    votes['BUY'] += weights['stacking'] * pred.get('confidence', 50)
                elif d in ('SELL', 'PUT'):
                    votes['SELL'] += weights['stacking'] * pred.get('confidence', 50)
                else:
                    votes['HOLD'] += weights['stacking'] * 50
    except Exception as e:
        predictions['stacking_ensemble'] = {'error': str(e)}

    # 2. LSTM/GRU
    try:
        if lstm_gru_system:
            pred = lstm_gru_system.predict(candles)
            if pred:
                predictions['lstm_gru'] = pred
                d = pred.get('direction', 'HOLD').upper()
                conf = pred.get('confidence', 50)
                if d in ('BUY', 'CALL'):
                    votes['BUY'] += weights['lstm_gru'] * conf
                elif d in ('SELL', 'PUT'):
                    votes['SELL'] += weights['lstm_gru'] * conf
                else:
                    votes['HOLD'] += weights['lstm_gru'] * 50
    except Exception as e:
        predictions['lstm_gru'] = {'error': str(e)}

    # 3. PPO RL
    try:
        if ppo_agent:
            features = FeatureEngine.compute(candles)
            if features is not None:
                pred = ppo_agent.predict(features)
                if pred:
                    predictions['ppo_rl'] = pred
                    d = pred.get('direction', 'HOLD').upper()
                    conf = pred.get('confidence', 50)
                    if d in ('BUY', 'CALL'):
                        votes['BUY'] += weights['ppo'] * conf
                    elif d in ('SELL', 'PUT'):
                        votes['SELL'] += weights['ppo'] * conf
                    else:
                        votes['HOLD'] += weights['ppo'] * 50
    except Exception as e:
        predictions['ppo_rl'] = {'error': str(e)}

    # Determine ensemble direction
    best_dir = max(votes, key=votes.get)
    total_weight = sum(votes.values()) or 1
    ensemble_conf = round((votes[best_dir] / total_weight) * 100, 2)

    # Agreement bonus
    agreeing = sum(1 for p in predictions.values()
                   if isinstance(p, dict) and p.get('direction', '').upper() in
                   ({'BUY', 'CALL'} if best_dir == 'BUY' else {'SELL', 'PUT'} if best_dir == 'SELL' else {'HOLD'}))

    if agreeing >= 3:
        ensemble_conf = min(95, ensemble_conf + 8)
    elif agreeing >= 2:
        ensemble_conf = min(95, ensemble_conf + 4)

    # Iter 84 — Dampen confidence during high-volatility regimes
    if _regime.get("regime") == "high_volatility":
        ensemble_conf = round(ensemble_conf * 0.85, 2)

    return {
        "success": True,
        "symbol": symbol,
        "ensemble_direction": best_dir,
        "ensemble_confidence": ensemble_conf,
        "agreement": f"{agreeing}/{len(predictions)}",
        "individual_predictions": predictions,
        "votes": {k: round(v, 2) for k, v in votes.items()},
        # Iter 84 — visibility into dynamic weighting + regime
        "ensemble_weights": weights,
        "excluded_models": _weight_info.get("excluded", []),
        "exclusion_reasons": _weight_info.get("reason", {}),
        "live_accuracies": _weight_info.get("accuracies", {}),
        "degraded": _weight_info.get("degraded", False),
        "regime": _regime,
    }


# ============================================================
# TAMPERMONKEY ML DATA COLLECTION ENDPOINTS - v8.5.1
# For real-time trade recording and adaptive model updates
# ============================================================

class TampermonkeyTradeRecord(BaseModel):
    timestamp: str
    symbol: str
    direction: str
    confidence: float = 0
    outcome: str  # WIN or LOSS
    expiry_seconds: int = 60
    actual_elapsed: int = 0
    detection_source: str = 'unknown'
    latency_offset: int = 0
    indicators: Dict[str, Any] = {}
    balance_before: float = 0
    balance_after: float = 0
    invert_active: bool = False
    strategy: str = 'unknown'


@router.post("/ml/record-trade")
async def record_tampermonkey_trade(trade: TampermonkeyTradeRecord):
    """
    Record a trade result from Tampermonkey script for ML training.
    This data is used to train and improve AI models.
    """
    try:
        # Store in database for training
        trade_doc = trade.dict()
        trade_doc['recorded_at'] = datetime.now(timezone.utc).isoformat()
        trade_doc['source'] = 'tampermonkey'
        
        await db.ml_trade_history.insert_one(trade_doc)
        
        # Check if we should trigger model update
        model_update_available = False
        update_reason = None
        
        # Count recent trades
        recent_count = await db.ml_trade_history.count_documents({
            'recorded_at': {'$gte': (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)).isoformat()}
        })
        
        # Check recent win rate
        recent_trades = await db.ml_trade_history.find({
            'recorded_at': {'$gte': (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)).isoformat()}
        }, {'_id': 0}).to_list(100)
        
        if len(recent_trades) >= 20:
            wins = sum(1 for t in recent_trades if t.get('outcome') == 'WIN')
            win_rate = (wins / len(recent_trades)) * 100
            
            if win_rate < 45:
                model_update_available = True
                update_reason = f"Low win rate ({win_rate:.1f}%) - model adjustment recommended"
            elif win_rate > 65:
                model_update_available = True  
                update_reason = f"High win rate ({win_rate:.1f}%) - model performing well, consider saving weights"
        
        # Check if enough data for retraining
        if recent_count >= 50 and recent_count % 50 == 0:
            model_update_available = True
            update_reason = f"Training milestone reached ({recent_count} trades today)"
        
        return {
            "success": True,
            "message": "Trade recorded for ML training",
            "trades_today": recent_count,
            "model_update_available": model_update_available,
            "update_reason": update_reason
        }
        
    except Exception as e:
        logger.error(f"Error recording trade: {e}")
        return {"success": False, "error": str(e)}


class ModelUpdateRequest(BaseModel):
    recent_trades: List[Dict[str, Any]] = []
    current_settings: Dict[str, Any] = {}


@router.post("/ml/request-update")
async def request_model_update(request: ModelUpdateRequest):
    """
    Request adaptive model adjustments based on recent performance.
    Returns recommended parameter changes for the Tampermonkey script.
    """
    try:
        recent_trades = request.recent_trades
        current_settings = request.current_settings
        
        adjustments = {}
        
        if len(recent_trades) >= 10:
            # Analyze recent performance
            wins = sum(1 for t in recent_trades if t.get('outcome') == 'WIN')
            losses = len(recent_trades) - wins
            win_rate = (wins / len(recent_trades)) * 100
            
            # Analyze by confidence level
            high_conf_trades = [t for t in recent_trades if t.get('confidence', 0) >= 75]
            low_conf_trades = [t for t in recent_trades if t.get('confidence', 0) < 75]
            
            high_conf_wr = 0
            if high_conf_trades:
                high_conf_wins = sum(1 for t in high_conf_trades if t.get('outcome') == 'WIN')
                high_conf_wr = (high_conf_wins / len(high_conf_trades)) * 100
            
            # Recommend confidence threshold adjustment
            current_min_conf = current_settings.get('min_confidence', 65)
            
            if win_rate < 45 and high_conf_wr > win_rate + 10:
                # Low overall win rate but high conf trades doing better - raise threshold
                adjustments['min_confidence'] = min(85, current_min_conf + 5)
            elif win_rate > 60 and current_min_conf > 60:
                # Good win rate, can be slightly more aggressive
                adjustments['min_confidence'] = max(55, current_min_conf - 3)
            
            # Analyze timing
            timing_issues = [t for t in recent_trades 
                           if abs(t.get('actual_elapsed', 0) - t.get('expiry_seconds', 60)) > 5]
            
            if len(timing_issues) > len(recent_trades) * 0.3:
                # Many trades have timing issues
                current_offset = current_settings.get('latency_offset', 0)
                avg_diff = sum(t.get('actual_elapsed', 0) - t.get('expiry_seconds', 60) 
                              for t in timing_issues) / len(timing_issues)
                
                if avg_diff > 3:
                    adjustments['latency_offset'] = max(-5, current_offset - 1)
                elif avg_diff < -3:
                    adjustments['latency_offset'] = min(5, current_offset + 1)
            
            # Analyze by symbol performance
            symbol_stats = {}
            for t in recent_trades:
                sym = t.get('symbol', 'UNKNOWN')
                if sym not in symbol_stats:
                    symbol_stats[sym] = {'w': 0, 'l': 0}
                if t.get('outcome') == 'WIN':
                    symbol_stats[sym]['w'] += 1
                else:
                    symbol_stats[sym]['l'] += 1
            
            # Calculate strategy weights based on symbol performance
            strategy_weights = {}
            for sym, stats in symbol_stats.items():
                total = stats['w'] + stats['l']
                if total >= 3:
                    strategy_weights[sym] = round((stats['w'] / total) * 100, 1)
            
            if strategy_weights:
                adjustments['strategy_weights'] = strategy_weights
        
        return {
            "success": True,
            "adjustments": adjustments,
            "analysis": {
                "trades_analyzed": len(recent_trades),
                "win_rate": round((wins / len(recent_trades)) * 100, 1) if recent_trades else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing model update request: {e}")
        return {"success": False, "error": str(e)}


@router.get("/ml/training-data-stats")
async def get_training_data_stats():
    """Get statistics about collected training data."""
    try:
        total_trades = await db.ml_trade_history.count_documents({})
        
        # Get trades from last 24h
        day_ago = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)).isoformat()
        today_trades = await db.ml_trade_history.find(
            {'recorded_at': {'$gte': day_ago}},
            {'_id': 0}
        ).to_list(1000)
        
        # Calculate stats
        wins = sum(1 for t in today_trades if t.get('outcome') == 'WIN')
        losses = len(today_trades) - wins
        
        # By symbol
        by_symbol = {}
        for t in today_trades:
            sym = t.get('symbol', 'UNKNOWN')
            if sym not in by_symbol:
                by_symbol[sym] = {'w': 0, 'l': 0}
            if t.get('outcome') == 'WIN':
                by_symbol[sym]['w'] += 1
            else:
                by_symbol[sym]['l'] += 1
        
        # Calculate win rates
        symbol_performance = {}
        for sym, stats in by_symbol.items():
            total = stats['w'] + stats['l']
            symbol_performance[sym] = {
                'wins': stats['w'],
                'losses': stats['l'],
                'total': total,
                'win_rate': round((stats['w'] / total) * 100, 1) if total > 0 else 0
            }
        
        return {
            "success": True,
            "total_trades_recorded": total_trades,
            "today": {
                "trades": len(today_trades),
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / len(today_trades)) * 100, 1) if today_trades else 0
            },
            "by_symbol": symbol_performance,
            "training_ready": total_trades >= 100
        }
        
    except Exception as e:
        logger.error(f"Error getting training data stats: {e}")
        return {"success": False, "error": str(e)}



# ==================== ML ACCURACY TUNING ENDPOINTS ====================

from ml_accuracy_tuner import get_ml_tuner


@router.get("/ml/tuning-report")
async def get_ml_tuning_report():
    """
    Get ML accuracy tuning report: OTC data availability, model status,
    and configuration for training.
    """
    tuner = get_ml_tuner(db)
    report = await tuner.get_tuning_report()

    # Add current model accuracy
    model_status = {}
    if maximized_ai_ml:
        model_status["maximized_v3"] = {
            "is_trained": maximized_ai_ml.is_trained,
            "accuracy": round(maximized_ai_ml.model_accuracy * 100, 2) if maximized_ai_ml.model_accuracy else 0,
            "features": maximized_ai_ml.selected_feature_count if hasattr(maximized_ai_ml, 'selected_feature_count') else 0,
            "last_trained": maximized_ai_ml.last_training_time.isoformat() if maximized_ai_ml.last_training_time else None,
            # Iter 57 — OOS overfit-detection block (may be None if model was
            # trained before OOS support landed; UI handles null gracefully).
            "oos": getattr(maximized_ai_ml, "tuner_oos_metrics", None),
        }
    if improved_ai_ml:
        model_status["improved_v2"] = {
            "is_trained": improved_ai_ml.is_trained,
            "accuracy": round(improved_ai_ml.model_accuracy * 100, 2) if improved_ai_ml.model_accuracy else 0,
            "last_trained": improved_ai_ml.last_training_time.isoformat() if improved_ai_ml.last_training_time else None,
            "oos": getattr(improved_ai_ml, "tuner_oos_metrics", None),
        }

    # Iter 66: include LSTM/GRU + PPO RL statuses so they surface in the ML Lab
    try:
        from lstm_gru_system import lstm_gru_system
        if lstm_gru_system is not None:
            hist = getattr(lstm_gru_system, 'training_history', {}) or {}
            model_status["lstm_gru"] = {
                "is_trained": bool(getattr(lstm_gru_system, 'is_trained', False)),
                "accuracy": round(float(getattr(lstm_gru_system, 'accuracy', 0) or 0), 2),
                "last_trained": hist.get('trained_at'),
                "samples": hist.get('samples', 0),
            }
    except Exception as e:
        logger.debug(f"lstm_gru status probe: {e}")

    try:
        from rl_ppo_agent import ppo_agent
        if ppo_agent is not None:
            model_status["ppo_rl"] = {
                "is_trained": bool(getattr(ppo_agent, 'is_trained', False)),
                "accuracy": round(float(getattr(ppo_agent, 'accuracy', 0) or 0), 2),
                "last_trained": (ppo_agent.training_stats or {}).get('trained_at') if hasattr(ppo_agent, 'training_stats') else None,
                "episodes": (ppo_agent.training_stats or {}).get('total_episodes', 0) if hasattr(ppo_agent, 'training_stats') else 0,
            }
    except Exception as e:
        logger.debug(f"ppo_rl status probe: {e}")

    report["model_status"] = model_status
    return report


@router.post("/ml/train-from-otc")
async def train_ml_from_otc_data(
    model: str = Body("maximized", description="Which model: maximized, improved, lstm_gru, or ppo_rl"),
    symbols: List[str] = Body(None, description="OTC symbols to train on"),
    min_samples: int = Body(200, description="Minimum samples required"),
    epochs: int = Body(30, description="Epochs for LSTM/GRU"),
    n_episodes: int = Body(20, description="Episodes for PPO RL"),
):
    """
    Train ML model using accumulated OTC 5-second candle data.
    Supports all 4 models:
      - maximized / improved → sklearn stacking + MLAccuracyTuner feature pipeline
      - lstm_gru → Keras sequence model (Iter 66)
      - ppo_rl   → PPO reinforcement learner (Iter 66)
    """
    tuner = get_ml_tuner(db)

    if model == "lstm_gru":
        from lstm_gru_system import lstm_gru_system
        from ml_accuracy_tuner import train_lstm_gru_from_otc
        if lstm_gru_system is None:
            return {"success": False, "error": "lstm_gru_system not available (TensorFlow missing?)"}
        return await train_lstm_gru_from_otc(db, lstm_gru_system, symbols=symbols, epochs=epochs)

    if model == "ppo_rl":
        from rl_ppo_agent import ppo_agent
        from ml_accuracy_tuner import train_ppo_from_otc
        if ppo_agent is None:
            return {"success": False, "error": "ppo_agent not available (TensorFlow missing?)"}
        return await train_ppo_from_otc(db, ppo_agent, symbols=symbols, n_episodes=n_episodes)

    target_system = maximized_ai_ml if model == "maximized" else improved_ai_ml
    if target_system is None:
        return {"success": False, "error": f"ML system '{model}' not available"}

    result = await tuner.train_from_otc(
        ml_system=target_system,
        symbols=symbols,
        min_samples=min_samples
    )
    return result


@router.post("/ml/train-from-trades")
async def train_ml_from_real_trades(
    model: str = Body("maximized", description="Which sklearn ML system: maximized or improved"),
    symbols: Optional[List[str]] = Body(None, description="Optional OTC symbols filter; null = all"),
    min_samples: int = Body(50, description="Minimum matched (trade, candle window) samples"),
    max_age_days: int = Body(90, description="Only use trades closed within the last N days"),
):
    """
    Train an ML model using REAL Tampermonkey trade outcomes as ground truth
    labels (Iter 54). Pulls every closed trade from `tm_trade_reports` within
    `max_age_days`, locates the OTC candle window at the trade entry, extracts
    features at THAT moment, and labels by actual WIN/LOSS rather than the
    synthetic "next candle direction" used by /ml/train-from-otc.

    Fire-and-forget: returns immediately with `accepted: true`. Poll
    GET /api/ml/train-from-trades/status for the final result. Necessary
    because OANDA fallback fetches + sklearn cross-val can take 1-3 min for
    large windows — bypasses Kubernetes ingress timeout.

    Why this matters: the live bot fires at a specific instant and the market
    pays out (or doesn't) on the candle close. Training on the synthetic
    next-candle proxy ignores micro-timing, slippage, and execution latency —
    real-outcome training grounds confidence/accuracy in the same conditions
    the bot will face live. Pairs perfectly with the BOTAI abstain gate.
    """
    global _REAL_TRADE_TRAIN_STATUS
    if _REAL_TRADE_TRAIN_STATUS.get("in_progress"):
        return {
            "success": False,
            "accepted": False,
            "message": "Real-trade training already in progress",
            "started_at": _REAL_TRADE_TRAIN_STATUS.get("started_at"),
        }
    
    tuner = get_ml_tuner(db)
    target_system = maximized_ai_ml if model == "maximized" else improved_ai_ml
    if target_system is None:
        return {"success": False, "error": f"ML system '{model}' not available"}

    async def _bg():
        global _REAL_TRADE_TRAIN_STATUS
        try:
            result = await asyncio.wait_for(
                tuner.train_from_trade_reports(
                    ml_system=target_system,
                    symbols=symbols,
                    min_samples=min_samples,
                    max_age_days=max_age_days,
                ),
                timeout=600,  # 10-min hard ceiling
            )
            _REAL_TRADE_TRAIN_STATUS = {
                "in_progress": False,
                "started_at": _REAL_TRADE_TRAIN_STATUS.get("started_at"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            }
        except asyncio.TimeoutError:
            logger.error("Real-trade training exceeded 10-min timeout — cancelled")
            _REAL_TRADE_TRAIN_STATUS = {
                "in_progress": False,
                "started_at": _REAL_TRADE_TRAIN_STATUS.get("started_at"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": {"success": False, "error": "training exceeded 10-min hard timeout"},
            }
        except Exception as e:
            logger.exception(f"Real-trade training crashed: {e}")
            _REAL_TRADE_TRAIN_STATUS = {
                "in_progress": False,
                "started_at": _REAL_TRADE_TRAIN_STATUS.get("started_at"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": {"success": False, "error": str(e)},
            }
    
    _REAL_TRADE_TRAIN_STATUS = {
        "in_progress": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "result": None,
    }
    asyncio.create_task(_bg())
    return {
        "success": True,
        "accepted": True,
        "message": "Real-trade training started — poll /api/ml/train-from-trades/status for progress",
        "started_at": _REAL_TRADE_TRAIN_STATUS["started_at"],
    }


# In-memory status of the last real-trade training run
_REAL_TRADE_TRAIN_STATUS: Dict[str, Any] = {
    "in_progress": False,
    "started_at": None,
    "completed_at": None,
    "result": None,
}


@router.get("/ml/train-from-trades/status")
async def get_real_trade_training_status():
    """Poll status of the most recent /api/ml/train-from-trades trigger."""
    return {"success": True, **_REAL_TRADE_TRAIN_STATUS}


@router.get("/ml/trade-reports/stats")
async def get_trade_reports_training_stats():
    """
    Diagnostic: how many closed Tampermonkey trade outcomes exist per symbol
    + outcome split, and what max_age_days windows are viable for real-trade
    training. Drives the MLLab UI "Train from Real Trades" button.
    """
    coll = db["tm_trade_reports"]
    pipeline = [
        {"$match": {"outcome": {"$in": ["WIN", "LOSS", "win", "loss"]}}},
        {"$group": {
            "_id": {"asset": "$asset_normalized", "outcome": {"$toUpper": "$outcome"}},
            "n": {"$sum": 1},
        }},
    ]
    raw = await coll.aggregate(pipeline).to_list(length=2000)
    by_symbol: Dict[str, Dict[str, int]] = {}
    total_win = 0
    total_loss = 0
    for row in raw:
        sym = row["_id"].get("asset") or "UNKNOWN"
        out = row["_id"].get("outcome", "")
        by_symbol.setdefault(sym, {"WIN": 0, "LOSS": 0})
        by_symbol[sym][out] = row["n"]
        if out == "WIN":
            total_win += row["n"]
        elif out == "LOSS":
            total_loss += row["n"]
    
    # Windowed counts
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    windows = {}
    for days in (7, 30, 90):
        cutoff = (now - timedelta(days=days)).isoformat()
        windows[f"last_{days}d"] = await coll.count_documents({
            "outcome": {"$in": ["WIN", "LOSS", "win", "loss"]},
            "server_received_at": {"$gte": cutoff},
        })
    
    return {
        "success": True,
        "total_closed_trades": total_win + total_loss,
        "total_wins": total_win,
        "total_losses": total_loss,
        "by_symbol": [
            {"symbol": s, "win": v["WIN"], "loss": v["LOSS"], "total": v["WIN"] + v["LOSS"]}
            for s, v in sorted(by_symbol.items(), key=lambda kv: -(kv[1]["WIN"] + kv[1]["LOSS"]))
        ],
        "windows": windows,
        "min_samples_for_training": 50,
        "ready": (total_win + total_loss) >= 50,
    }


# ==================== OTC BACKFILL FROM OANDA (April 25, 2026) ====================

# OTC pairs that map cleanly to an OANDA forex/commodity/index instrument.
# Iter 63 — expanded with commodities (XAU/XAG/WTI/etc.) and indices that OANDA
# supports natively. Exotics OANDA doesn't carry (SAR/UAH/MAD/YER/VND/PHP/MYR
# /RUB/BRL/MXN/ARS) remain skipped.
OTC_TO_OANDA = {
    # --- Forex (majors + crosses) ---
    "AUDCAD_OTC": "AUD_CAD", "AUDUSD_OTC": "AUD_USD", "AUDJPY_OTC": "AUD_JPY",
    "AUDNZD_OTC": "AUD_NZD", "AUDCHF_OTC": "AUD_CHF", "AUDSGD_OTC": "AUD_SGD",
    "AUDHKD_OTC": "AUD_HKD",
    "CADCHF_OTC": "CAD_CHF", "CADJPY_OTC": "CAD_JPY", "CADSGD_OTC": "CAD_SGD",
    "CHFJPY_OTC": "CHF_JPY", "CHFSGD_OTC": "CHF_SGD",
    "EURAUD_OTC": "EUR_AUD", "EURCAD_OTC": "EUR_CAD", "EURCHF_OTC": "EUR_CHF",
    "EURGBP_OTC": "EUR_GBP", "EURJPY_OTC": "EUR_JPY", "EURNZD_OTC": "EUR_NZD",
    "EURUSD_OTC": "EUR_USD", "EURDKK_OTC": "EUR_DKK", "EURHUF_OTC": "EUR_HUF",
    "EURNOK_OTC": "EUR_NOK", "EURPLN_OTC": "EUR_PLN", "EURSEK_OTC": "EUR_SEK",
    "EURTRY_OTC": "EUR_TRY", "EURZAR_OTC": "EUR_ZAR",
    "GBPAUD_OTC": "GBP_AUD", "GBPCAD_OTC": "GBP_CAD", "GBPCHF_OTC": "GBP_CHF",
    "GBPJPY_OTC": "GBP_JPY", "GBPNZD_OTC": "GBP_NZD", "GBPUSD_OTC": "GBP_USD",
    "GBPPLN_OTC": "GBP_PLN", "GBPSGD_OTC": "GBP_SGD", "GBPZAR_OTC": "GBP_ZAR",
    "NZDCAD_OTC": "NZD_CAD", "NZDCHF_OTC": "NZD_CHF", "NZDJPY_OTC": "NZD_JPY",
    "NZDUSD_OTC": "NZD_USD", "NZDSGD_OTC": "NZD_SGD", "NZDHKD_OTC": "NZD_HKD",
    "USDCAD_OTC": "USD_CAD", "USDCHF_OTC": "USD_CHF", "USDCNH_OTC": "USD_CNH",
    "USDJPY_OTC": "USD_JPY", "USDDKK_OTC": "USD_DKK", "USDHKD_OTC": "USD_HKD",
    "USDHUF_OTC": "USD_HUF", "USDNOK_OTC": "USD_NOK", "USDPLN_OTC": "USD_PLN",
    "USDSEK_OTC": "USD_SEK", "USDSGD_OTC": "USD_SGD", "USDTHB_OTC": "USD_THB",
    "USDTRY_OTC": "USD_TRY", "USDZAR_OTC": "USD_ZAR", "USDINR_OTC": "USD_INR",
    "USDCZK_OTC": "USD_CZK", "USDSAR_OTC": "USD_SAR",
    "TRYJPY_OTC": "TRY_JPY", "ZARJPY_OTC": "ZAR_JPY",
    # --- Commodities (OANDA naming) ---
    "XAUUSD_OTC": "XAU_USD", "XAGUSD_OTC": "XAG_USD",
    "XPTUSD_OTC": "XPT_USD", "XPDUSD_OTC": "XPD_USD",
    "WTI_OTC": "WTICO_USD", "BRENT_OTC": "BCO_USD", "NGAS_OTC": "NATGAS_USD",
    "COPPER_OTC": "XCU_USD",
    "WHEAT_OTC": "WHEAT_USD", "CORN_OTC": "CORN_USD",
    "SOYBEAN_OTC": "SOYBN_USD", "SUGAR_OTC": "SUGAR_USD",
    # --- Indices (OANDA CFD naming) ---
    "SPX500_OTC": "SPX500_USD", "NDX100_OTC": "NAS100_USD",
    "DJI30_OTC": "US30_USD", "RUT2000_OTC": "US2000_USD",
    "DAX40_OTC": "DE30_EUR", "FTSE100_OTC": "UK100_GBP",
    "CAC40_OTC": "FR40_EUR", "AEX25_OTC": "NL25_EUR",
    "STOXX50_OTC": "EU50_EUR", "SMI20_OTC": "CH20_CHF",
    "NIKKEI225_OTC": "JP225_USD", "HSI50_OTC": "HK33_HKD",
    "ASX200_OTC": "AU200_AUD",
}


@router.post("/ml/backfill-otc-from-oanda")
async def backfill_otc_from_oanda(
    symbols: List[str] = Body(None, description="OTC symbols to backfill. None = auto-discover all under-200 mappable pairs."),
    target_count: int = Body(500, description="Target candle count per symbol after backfill"),
    granularity: str = Body("S5", description="OANDA granularity (S5 = 5-second candles)"),
):
    """
    Backfill the otc_candles_5s collection using OANDA S5 forex candles for
    OTC pairs that have a real-forex underlying. Existing TM-collected candles
    are preserved (upsert on symbol+timestamp). Sets `source: 'oanda_backfill'`
    on inserted rows so they can be distinguished from live TM scrapes.
    """
    if not enhanced_oanda or not enhanced_oanda.is_configured:
        return {"success": False, "error": "OANDA not configured. Set OANDA_ACCESS_TOKEN + OANDA_ACCOUNT_ID."}

    # 1) Discover symbols to backfill
    if not symbols:
        # Auto-discover: every OTC symbol with < target_count candles AND in mapping
        pipeline = [{"$group": {"_id": "$symbol", "count": {"$sum": 1}}}]
        existing_counts = {}
        async for doc in db["otc_candles_5s"].aggregate(pipeline):
            existing_counts[doc["_id"]] = doc["count"]
        symbols = [
            s for s in OTC_TO_OANDA
            if existing_counts.get(s, 0) < target_count
        ]

    coll = db["otc_candles_5s"]
    results = {}

    for otc_sym in symbols:
        oanda_pair = OTC_TO_OANDA.get(otc_sym)
        if not oanda_pair:
            results[otc_sym] = {"status": "skipped_no_mapping"}
            continue

        # 2) Fetch from OANDA in a thread (blocking sync API)
        try:
            df = await asyncio.to_thread(
                enhanced_oanda.get_candles,
                instrument=oanda_pair,
                granularity=granularity,
                count=target_count,
            )
        except Exception as e:
            results[otc_sym] = {"status": "oanda_error", "error": str(e)}
            continue

        if df is None or df.empty:
            results[otc_sym] = {"status": "no_data"}
            continue

        # 3) Upsert each candle. Index reset so timestamp is a column.
        df = df.reset_index()
        now_iso = datetime.now(timezone.utc).isoformat()
        ops = []
        for _, row in df.iterrows():
            ts = row.get("timestamp")
            if pd.isna(ts):
                continue
            ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            doc = {
                "symbol": otc_sym,
                "timestamp": ts_iso,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row.get("volume", 0)),
                "timeframe": "5s",
                "source": "oanda_backfill",
                "oanda_pair": oanda_pair,
                "collected_at": now_iso,
            }
            ops.append(doc)

        # Idempotent upsert: skip if (symbol, timestamp) already present
        inserted = 0
        for doc in ops:
            r = await coll.update_one(
                {"symbol": doc["symbol"], "timestamp": doc["timestamp"]},
                {"$setOnInsert": doc},
                upsert=True,
            )
            if r.upserted_id is not None:
                inserted += 1

        total_after = await coll.count_documents({"symbol": otc_sym})
        results[otc_sym] = {
            "status": "ok",
            "oanda_pair": oanda_pair,
            "fetched": len(ops),
            "inserted_new": inserted,
            "total_after": total_after,
            "trainable": total_after >= 200,
        }

    summary = {
        "total_symbols": len(results),
        "succeeded": sum(1 for r in results.values() if r.get("status") == "ok"),
        "newly_trainable": sum(
            1 for r in results.values()
            if r.get("status") == "ok" and r.get("trainable")
            and r.get("inserted_new", 0) > 0
        ),
        "total_inserted": sum(r.get("inserted_new", 0) for r in results.values()),
    }
    return {"success": True, "results": results, "summary": summary,
            "completed_at": datetime.now(timezone.utc).isoformat()}



# ==================== AUTO-RETRAIN SCHEDULER ENDPOINTS ====================

from auto_retrain_scheduler import get_retrain_scheduler


@router.get("/ml/scheduler/status")
async def get_scheduler_status():
    """Get auto-retrain scheduler status, config, and history."""
    scheduler = get_retrain_scheduler(db)
    return {"success": True, **scheduler.get_status()}


@router.post("/ml/scheduler/start")
async def start_scheduler():
    """Start the auto-retrain scheduler."""
    scheduler = get_retrain_scheduler(db)
    scheduler.start()
    return {"success": True, "message": "Auto-retrain scheduler started", "status": scheduler.get_status()}


@router.post("/ml/scheduler/stop")
async def stop_scheduler():
    """Stop the auto-retrain scheduler."""
    scheduler = get_retrain_scheduler(db)
    scheduler.stop()
    return {"success": True, "message": "Auto-retrain scheduler stopped"}


@router.put("/ml/scheduler/config")
async def update_scheduler_config(config: dict = Body(...)):
    """
    Update scheduler config.
    
    Fields: enabled, retrain_hours_utc, retrain_days, min_hours_between_retrain,
    use_otc_data, use_oanda_data, timeframes, symbols_oanda, symbols_otc, min_otc_candles
    """
    scheduler = get_retrain_scheduler(db)
    scheduler.update_config(config)
    return {"success": True, "config": scheduler._config}


@router.post("/ml/scheduler/trigger")
async def trigger_manual_retrain():
    """
    Trigger an immediate retrain (manual override, respects 30min cooldown).
    Returns immediately (202-style accepted) so callers don't hit ingress timeouts.
    Poll GET /api/ml/scheduler/status — `manual_in_progress` flag flips false
    once finished and `recent_history[-1]` carries the result.
    """
    scheduler = get_retrain_scheduler(db)
    result = scheduler.trigger_manual_retrain_async()
    return result


# =============================================================================
# BOTAI-inspired abstain-threshold optimizer (May 2026, v8.55.0 integration)
# =============================================================================
# Port of concepts from https://github.com/RafaelCartenet/BOTAI:
#   - 3-class tendency labeling (UP / DOWN / EQUAL) — the EQUAL "tie" class is
#     excluded from win-rate arithmetic so flat candles don't wash the stats.
#   - Confidence-threshold "Pass" action — only trade when the ensemble is
#     above a per-asset threshold. This typically boosts live win-rate from
#     ~53% to 60-68% at the cost of ~40% fewer trades.
#
# See /app/backend/botai_simulator.py for the full implementation.
from botai_simulator import (
    DEFAULT_THRESHOLD as _ABSTAIN_DEFAULT,
    get_threshold as _abstain_get,
    set_threshold as _abstain_set,
    get_all_thresholds as _abstain_all,
    optimize_asset_threshold as _abstain_optimize,
    get_strategy_threshold as _abstain_get_strategy,
    set_strategy_threshold as _abstain_set_strategy,
    get_all_strategy_thresholds as _abstain_all_strategy,
    optimize_strategy_threshold as _abstain_optimize_strategy,
    get_effective_threshold as _abstain_effective,
)


@router.get("/ml/abstain/threshold")
async def get_abstain_threshold(asset: str = Query(..., description="e.g. EURUSD_OTC")):
    """
    Return the stored per-asset abstain threshold (0..1). Default if unset.
    Used by /api/signals/force-generate-v2 to decide whether to mark a
    signal as `abstain=true` so the bot won't fire on it.
    """
    row = await _abstain_get(asset)
    return {"success": True, **row}


@router.get("/ml/abstain/thresholds")
async def list_abstain_thresholds():
    """Return the full list of stored per-asset thresholds."""
    rows = await _abstain_all()
    return {"success": True, "thresholds": rows, "default": _ABSTAIN_DEFAULT}


@router.post("/ml/abstain/optimize")
async def optimize_abstain_threshold(
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
    lookback_candles: int = Query(500, ge=60, le=5000),
    min_trades: int = Query(20, ge=5, le=500),
    min_winrate: float = Query(0.55, ge=0.5, le=0.9),
):
    """
    Sweep the confidence-threshold grid (0.50..0.82 in 0.02 steps) on the
    last `lookback_candles` of OTC data for `asset`. Replays each candle
    through `MLAccuracyTuner` and compares the predicted vs actual tendency.

    Picks the threshold with the HIGHEST win-rate subject to:
      - at least `min_trades` trades taken (avoids over-fitting to tiny tails)
      - at least `min_winrate` win-rate (break-even for 0.80 payout is 55.6%)

    Persists the result for `asset` so `force-generate-v2` can consult it.
    """
    result = await _abstain_optimize(
        asset=asset,
        lookback_candles=lookback_candles,
        min_trades=min_trades,
        min_winrate=min_winrate,
    )
    return {"success": True, **result}


@router.post("/ml/abstain/threshold")
async def set_abstain_threshold(
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
    threshold: float = Query(..., ge=0.50, le=0.95),
):
    """Manual override: force a per-asset threshold without running the sweep."""
    await _abstain_set(
        asset=asset,
        threshold=threshold,
        winrate=0.0,
        n_trades=0,
        method="manual",
    )
    return {"success": True, "asset": asset, "threshold": threshold, "method": "manual"}


# ============================================================================
# STRATEGY-AWARE ABSTAIN ENDPOINTS (Iter 53 — May 9, 2026)
# Tunes per-(strategy, asset) thresholds independently. Different strategies
# have different confidence calibrations, so the optimal "Pass" threshold for
# the global ensemble may not match e.g. 5s_heikin_fractal or holly_crossover.
# ============================================================================

@router.get("/ml/abstain/strategy-threshold")
async def get_strategy_abstain_threshold(
    strategy_id: str = Query(..., description="e.g. 5s_heikin_fractal"),
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
):
    """Return the stored per-(strategy, asset) abstain threshold."""
    row = await _abstain_get_strategy(strategy_id, asset)
    return {"success": True, **row}


@router.get("/ml/abstain/strategy-thresholds")
async def list_strategy_abstain_thresholds(
    strategy_id: Optional[str] = Query(None, description="Optional filter by strategy"),
):
    """List stored per-(strategy, asset) thresholds, optionally filtered."""
    rows = await _abstain_all_strategy(strategy_id)
    return {"success": True, "thresholds": rows, "default": _ABSTAIN_DEFAULT}


@router.post("/ml/abstain/optimize-strategy")
async def optimize_strategy_abstain_threshold(
    strategy_id: str = Query(..., description="e.g. 5s_heikin_fractal"),
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
    lookback_candles: int = Query(500, ge=60, le=5000),
    min_trades: int = Query(20, ge=5, le=500),
    min_winrate: float = Query(0.55, ge=0.5, le=0.9),
):
    """
    Sweep confidence thresholds for the named strategy on the given asset.
    Replays the strategy via `strategy_registry` against historical OTC
    candles, tuning the threshold that maximises win-rate subject to
    `min_trades` and `min_winrate` constraints. Persists the optimum.

    See /api/ml/abstain/optimize for the asset-only variant (uses ensemble).
    """
    result = await _abstain_optimize_strategy(
        strategy_id=strategy_id,
        asset=asset,
        lookback_candles=lookback_candles,
        min_trades=min_trades,
        min_winrate=min_winrate,
    )
    return {"success": True, **result}


@router.post("/ml/abstain/strategy-threshold")
async def set_strategy_abstain_threshold(
    strategy_id: str = Query(..., description="e.g. 5s_heikin_fractal"),
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
    threshold: float = Query(..., ge=0.50, le=0.95),
):
    """Manual override: force a per-(strategy, asset) threshold."""
    await _abstain_set_strategy(
        strategy_id=strategy_id,
        asset=asset,
        threshold=threshold,
        winrate=0.0,
        n_trades=0,
        method="manual",
    )
    return {
        "success": True,
        "strategy_id": strategy_id,
        "asset": asset,
        "threshold": threshold,
        "method": "manual",
    }


@router.get("/ml/abstain/effective-threshold")
async def get_effective_abstain_threshold(
    asset: str = Query(..., description="e.g. EURUSD_OTC"),
    strategy_id: Optional[str] = Query(None, description="Optional strategy id for stricter lookup"),
):
    """
    Resolve the most specific stored threshold for (strategy, asset). Falls
    back to (asset)-only, then DEFAULT_THRESHOLD. Returns `source` indicating
    which level supplied the value: 'strategy' | 'asset' | 'default'.
    """
    row = await _abstain_effective(strategy_id, asset)
    return {"success": True, **row}
