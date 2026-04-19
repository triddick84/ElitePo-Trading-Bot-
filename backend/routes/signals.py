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

# Import LSTM/GRU and PPO ML systems for advanced predictions
try:
    from lstm_gru_system import lstm_gru_system, FeatureEngine
    LSTM_GRU_AVAILABLE = lstm_gru_system is not None
except ImportError:
    lstm_gru_system = None
    FeatureEngine = None
    LSTM_GRU_AVAILABLE = False

try:
    from rl_ppo_agent import ppo_agent
    PPO_AVAILABLE = ppo_agent is not None
except ImportError:
    ppo_agent = None
    PPO_AVAILABLE = False

# Re-use the main api_router — routes are registered via include in server.py
# This module uses a local router that gets included by server.py
router = APIRouter()
from trading_models import TradingSignal, FlexibleStrategyRequest, TradingStrategy, AssetType, SignalDirection
from deep_market_analyzer import get_deep_analysis_signal
from high_accuracy_strategies import high_accuracy_generator, get_high_accuracy_signal
from advanced_signal_strategies import advanced_signal_generator as iq720_generator, generate_iq720_signal
from enhanced_oanda_service import enhanced_oanda
from signal_validator import signal_validator
from advanced_signal_generator import advanced_signal_generator
from force_signal_generator import force_signal_generator
from pocket_option_client import get_pocket_option_client
from routes import get_realtime_market_hub
from signal_routing_service import get_signal_router
from real_market_data_service import RealMarketDataService
from platform_integrations import platform_integration
from continuous_scanner import ContinuousMarketScanner
from adaptive_strategy_service import AdaptiveStrategyService
from premium_signal_generator import (
    session_analyzer, market_condition_analyzer, asset_tracker,
    get_time_filter, should_trade_now, get_market_condition,
    apply_premium_filters
)

import math
import time

# Initialize services
adaptive_strategy_service_instance = AdaptiveStrategyService(db)
continuous_scanner = ContinuousMarketScanner(force_signal_generator, db)


async def _route_and_dispatch(signal: Dict) -> Optional[Dict]:
    """
    Route a signal through the signal routing engine and dispatch to matched destinations.
    Returns routing result or None if routing is not configured.
    """
    try:
        router = get_signal_router(db)
        routing = await router.route_signal(signal)
        destinations = routing.get("destinations", [])

        dispatch_results = {}

        for dest in destinations:
            if dest == "telegram":
                try:
                    from telegram_signal_notifier import get_telegram_notifier
                    notifier = get_telegram_notifier()
                    if notifier and notifier.config.bot_token and notifier.config.chat_id:
                        direction = signal.get("direction", "?")
                        symbol = signal.get("symbol", "?")
                        confidence = signal.get("confidence", 0)
                        strategy = signal.get("strategy") or signal.get("analysis_type") or "Auto"
                        msg = (
                            f"*Signal Routed*\n"
                            f"{direction} {symbol}\n"
                            f"Confidence: {confidence}%\n"
                            f"Strategy: {strategy}"
                        )
                        sent = await notifier.send_message(msg)
                        dispatch_results["telegram"] = {"sent": sent}
                except Exception as e:
                    dispatch_results["telegram"] = {"sent": False, "error": str(e)}

            elif dest == "mt5":
                try:
                    from mt5_trading_service import mt5_service as _mt5
                    if _mt5 and _mt5.connection.is_connected():
                        direction = signal.get("direction", "CALL").upper()
                        mt5_dir = "BUY" if direction in ("CALL", "BUY") else "SELL"
                        sym = signal.get("symbol", "EURUSD").replace("_OTC", "").replace("OTC", "")
                        result = _mt5.execute_order(symbol=sym, direction=mt5_dir, volume=0.01, comment="Auto-routed")
                        dispatch_results["mt5"] = {"executed": result.success, "ticket": result.ticket}
                    else:
                        dispatch_results["mt5"] = {"executed": False, "reason": "not_connected"}
                except Exception as e:
                    dispatch_results["mt5"] = {"executed": False, "error": str(e)}

            elif dest == "pocket_option":
                dispatch_results["pocket_option"] = {"queued": True}

        routing["dispatch_results"] = dispatch_results
        return routing

    except Exception as e:
        logger.warning(f"Signal routing error (non-fatal): {e}")
        return None


def get_advanced_ml_ensemble_validation(candles: List[Dict], deep_signal: Optional[Dict] = None) -> Dict:
    """
    Get validation from advanced ML models (LSTM/GRU + PPO + Stacking).
    Returns agreement status and confidence from each model.
    """
    result = {
        "models_checked": 0,
        "models_agreeing": 0,
        "total_confidence": 0,
        "ensemble_direction": None,
        "predictions": {}
    }
    
    if not candles or len(candles) < 30:
        return result
    
    target_direction = deep_signal.get("direction", "").upper() if deep_signal else None
    
    # 1. LSTM/GRU Time-Series Prediction
    try:
        if LSTM_GRU_AVAILABLE and lstm_gru_system:
            candle_dicts = [{'open': float(c.get('open', c.get('Open', 0))),
                            'high': float(c.get('high', c.get('High', 0))),
                            'low': float(c.get('low', c.get('Low', 0))),
                            'close': float(c.get('close', c.get('Close', 0))),
                            'volume': float(c.get('volume', c.get('Volume', 0)))}
                           for c in candles]
            lstm_pred = lstm_gru_system.predict(candle_dicts)
            if lstm_pred:
                result["models_checked"] += 1
                result["predictions"]["lstm_gru"] = lstm_pred
                lstm_dir = lstm_pred.get("direction", "HOLD").upper()
                lstm_conf = lstm_pred.get("confidence", 0)
                result["total_confidence"] += lstm_conf
                
                if target_direction:
                    if (target_direction in ("CALL", "BUY") and lstm_dir == "BUY") or \
                       (target_direction in ("PUT", "SELL") and lstm_dir == "SELL"):
                        result["models_agreeing"] += 1
    except Exception as e:
        logger.debug(f"LSTM/GRU prediction error: {e}")
    
    # 2. PPO Reinforcement Learning Prediction
    try:
        if PPO_AVAILABLE and ppo_agent and ppo_agent.is_trained and FeatureEngine:
            candle_dicts = [{'open': float(c.get('open', c.get('Open', 0))),
                            'high': float(c.get('high', c.get('High', 0))),
                            'low': float(c.get('low', c.get('Low', 0))),
                            'close': float(c.get('close', c.get('Close', 0))),
                            'volume': float(c.get('volume', c.get('Volume', 0)))}
                           for c in candles]
            features = FeatureEngine.compute(candle_dicts)
            if features is not None:
                ppo_pred = ppo_agent.predict(features)
                if ppo_pred:
                    result["models_checked"] += 1
                    result["predictions"]["ppo_rl"] = ppo_pred
                    ppo_dir = ppo_pred.get("direction", "HOLD").upper()
                    ppo_conf = ppo_pred.get("confidence", 0)
                    result["total_confidence"] += ppo_conf
                    
                    if target_direction:
                        if (target_direction in ("CALL", "BUY") and ppo_dir == "BUY") or \
                           (target_direction in ("PUT", "SELL") and ppo_dir == "SELL"):
                            result["models_agreeing"] += 1
    except Exception as e:
        logger.debug(f"PPO RL prediction error: {e}")
    
    # 3. Determine ensemble direction (majority vote)
    if result["models_checked"] > 0:
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for pred in result["predictions"].values():
            d = pred.get("direction", "HOLD").upper()
            conf = pred.get("confidence", 50)
            if d == "BUY":
                votes["BUY"] += conf
            elif d == "SELL":
                votes["SELL"] += conf
            else:
                votes["HOLD"] += conf
        
        result["ensemble_direction"] = max(votes, key=votes.get)
        result["average_confidence"] = result["total_confidence"] / result["models_checked"]
    
    return result

# Helper function to convert numpy types for JSON serialization
def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    return convert_numpy_types(obj)


# Signal Endpoints
@router.get("/signals/active", response_model=List[TradingSignal])
async def get_active_signals():
    """Get currently active trading signals"""
    try:
        from server import trading_bot
        signals = await trading_bot.get_active_signals()
        return signals
        
    except Exception as e:
        logging.error(f"Error getting active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/signals/clear-all")
async def clear_all_signals():
    """Clear all generated signals from database"""
    try:
        result = await db.trading_signals.delete_many({})
        
        return {
            "status": "success",
            "message": f"Cleared {result.deleted_count} signals",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logging.error(f"Error clearing signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/signals/history")
async def get_signal_history(limit: int = 100):
    """Get historical trading signals"""
    try:
        signals = await db.trading_signals.find().sort("timestamp", -1).limit(limit).to_list(length=None)
        
        # Convert MongoDB ObjectIds and timestamps for JSON serialization
        for signal in signals:
            if '_id' in signal:
                del signal['_id']  # Remove MongoDB ObjectId
            if 'timestamp' in signal and hasattr(signal['timestamp'], 'isoformat'):
                signal['timestamp'] = signal['timestamp'].isoformat()
            if 'closed_at' in signal and signal['closed_at'] and hasattr(signal['closed_at'], 'isoformat'):
                signal['closed_at'] = signal['closed_at'].isoformat()
            if 'precision_entry_time' in signal and signal['precision_entry_time'] and hasattr(signal['precision_entry_time'], 'isoformat'):
                signal['precision_entry_time'] = signal['precision_entry_time'].isoformat()
        
        return {"signals": signals}
        
    except Exception as e:
        logging.error(f"Error getting signal history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Market Data Endpoints
@router.get("/market/data")


@router.post("/signals/{signal_id}/execute")
async def execute_signal_on_platform(signal_id: str):
    """Execute a specific signal on Pocket Option platform"""
    try:
        # Get signal from database
        signal_doc = await db.trading_signals.find_one({"id": signal_id})
        if not signal_doc:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Convert to TradingSignal object
        signal_doc['timestamp'] = datetime.fromisoformat(signal_doc['timestamp'].replace('Z', '+00:00'))
        signal = TradingSignal(**signal_doc)
        
        # Execute trade on Pocket Option
        result = await platform_integration.execute_pocket_option_trade(signal)
        
        return {"execution_result": result}
        
    except Exception as e:
        logging.error(f"Error executing signal {signal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/invert/{signal_id}")
async def invert_signal(signal_id: str):
    """Invert a signal (BUY becomes SELL and vice versa)"""
    try:
        # Get signal from database
        signal_doc = await db.trading_signals.find_one({"id": signal_id})
        if not signal_doc:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Invert the signal direction
        original_direction = signal_doc['direction']
        inverted_direction = 'SELL' if original_direction == 'BUY' else 'BUY'
        
        # Update signal in database
        await db.trading_signals.update_one(
            {"id": signal_id},
            {"$set": {
                "direction": inverted_direction,
                "original_direction": original_direction,
                "inverted": True
            }}
        )
        
        return {
            "message": "Signal inverted successfully",
            "original_direction": original_direction,
            "new_direction": inverted_direction
        }
        
    except Exception as e:
        logging.error(f"Error inverting signal {signal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/signals/toggle-invert")
async def toggle_global_signal_inversion():
    """
    Toggle global signal inversion setting.
    When enabled, ALL generated signals will have their direction inverted (BUY -> SELL, SELL -> BUY).
    This is useful when the bot is experiencing a losing streak.
    """
    try:
        # Get current config
        config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
        current_invert = config_doc.get('invert_signals', False) if config_doc else False
        
        # Toggle the value
        new_invert = not current_invert
        
        # Update in database
        await db.trading_configurations.update_one(
            {"user_id": "default_user"},
            {"$set": {
                "invert_signals": new_invert,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
        # Also update the trading bot config
        from server import trading_bot
        trading_bot.config.invert_signals = new_invert
        
        logger.info(f"🔄 Global signal inversion {'ENABLED' if new_invert else 'DISABLED'}")
        
        return {
            "success": True,
            "invert_signals": new_invert,
            "message": f"Signal inversion {'enabled' if new_invert else 'disabled'}. All signals will now be {'inverted' if new_invert else 'normal'}.",
            "note": "BUY signals become SELL, SELL signals become BUY" if new_invert else "Signals generated as normal"
        }
        
    except Exception as e:
        logging.error(f"Error toggling signal inversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/invert-status")
async def get_signal_inversion_status():
    """Get the current global signal inversion status"""
    try:
        config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
        invert_enabled = config_doc.get('invert_signals', False) if config_doc else False
        
        return {
            "success": True,
            "invert_signals": invert_enabled,
            "status": "ACTIVE - Signals are being inverted" if invert_enabled else "INACTIVE - Normal signal direction"
        }
        
    except Exception as e:
        logging.error(f"Error getting inversion status: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/generate/single")
async def generate_single_signal():
    """Generate a single trading signal on-demand"""
    try:
        from server import trading_bot
        if not trading_bot.is_running:
            raise HTTPException(status_code=400, detail="Trading bot is not running. Please start the bot first.")
        
        # Get current market data for configured assets
        market_data = await trading_bot._get_relevant_market_data()
        
        if not market_data:
            raise HTTPException(status_code=404, detail="No market data available for configured assets")
        
        # Generate signal for the first available asset
        signal = await trading_bot._generate_signal_for_asset(market_data[0])
        
        if signal:
            await trading_bot._process_new_signal(signal)
            return {
                "success": True,
                "message": "Signal generated successfully",
                "signal": {
                    "id": signal.id,
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "entry_price": signal.entry_price,
                    "probability": signal.probability,
                    "timestamp": signal.timestamp.isoformat()
                }
            }
        else:
            return {
                "success": False,
                "message": "No high-probability signal found for current market conditions",
                "signal": None
            }
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        logging.error(f"Error generating single signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/auto-generate/start")
async def start_auto_signal_generation():
    """Start automated signal generation mode"""
    try:
        from server import trading_bot
        if not trading_bot.is_running:
            raise HTTPException(status_code=400, detail="Trading bot is not running. Please start the bot first.")
        
        # Set auto signal generation flag
        trading_bot.auto_signal_generation = True
        
        return {
            "success": True,
            "message": "Automated signal generation started",
            "status": "active"
        }
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        logging.error(f"Error starting auto signal generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/auto-generate/enhanced")
async def enhanced_auto_generate(
    scan_all_assets: bool = False,
    selected_assets: Optional[List[str]] = None,
    min_payout: float = 80.0,
    min_accuracy: float = 75.0,
    max_signals: int = 5,
    continuous: bool = True  # NEW: Enable continuous scanning
):
    """
    Enhanced auto-generate with asset scanning and filtering
    
    Args:
        scan_all_assets: If True, scan all available assets
        selected_assets: List of specific assets to scan (used if scan_all_assets=False)
        min_payout: Minimum payout percentage to consider
        min_accuracy: Minimum accuracy threshold for signal generation
        max_signals: Maximum number of signals to generate
        continuous: If True, keep scanning until signals are found (up to 100 cycles)
    """
    try:
        # Define available assets (common trading pairs)
        ALL_AVAILABLE_ASSETS = [
            'EURUSD', 'EURUSD_otc', 'GBPUSD', 'GBPUSD_otc', 
            'USDJPY', 'USDJPY_otc', 'AUDUSD', 'AUDUSD_otc',
            'USDCAD', 'USDCAD_otc', 'USDCHF', 'USDCHF_otc',
            'BTCUSD', 'ETHUSD', 'LTCUSD',
            'EURJPY', 'EURJPY_otc', 'GBPJPY', 'GBPJPY_otc',
            'AUDJPY', 'AUDJPY_otc', 'NZDUSD', 'NZDUSD_otc'
        ]
        
        # Determine which assets to scan
        assets_to_scan = []
        if scan_all_assets:
            # Use all available assets (payout filtering not implemented - would need broker API)
            assets_to_scan = ALL_AVAILABLE_ASSETS
        elif selected_assets:
            assets_to_scan = selected_assets
        else:
            # Use configured assets
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            assets_to_scan = config_doc.get("selected_assets", []) if config_doc else []
        
        if not assets_to_scan:
            return {
                "success": False,
                "message": "No assets to scan",
                "signals": []
            }
        
        # Use continuous scanner if enabled
        if continuous:
            result = await continuous_scanner.start_continuous_scan(
                assets=assets_to_scan[:20],  # Limit to 20 assets
                min_accuracy=min_accuracy,
                max_signals=max_signals,
                scan_interval=60,  # Scan every 60 seconds
                max_scans=100  # Up to 100 scan cycles
            )
            return result
        else:
            # Single-pass scan (legacy behavior)
            generated_signals = []
            for asset_id in assets_to_scan[:20]:  # Limit to 20 assets to avoid timeout
                try:
                    # Parse asset (format: SYMBOL_market)
                    if '_' in asset_id:
                        symbol, market_type = asset_id.rsplit('_', 1)
                    else:
                        symbol, market_type = asset_id, 'regular'
                    
                    # Generate signal for this asset
                    signal_result = await force_signal_generator.generate_force_signal(
                        asset_symbol=symbol,
                        market_type=market_type,
                        selected_timeframe='1m',
                        selected_strategy='enhanced_rsi_bb_volume',
                        force_signal=False  # Don't force, only generate if conditions met
                    )
                    
                    # Check if signal meets accuracy threshold
                    if signal_result.get('signal') and signal_result['signal'].get('probability', 0) >= min_accuracy:
                        generated_signals.append(signal_result['signal'])
                        
                        # Stop if we've reached max signals
                        if len(generated_signals) >= max_signals:
                            break
                            
                except Exception as e:
                    logging.error(f"Error generating signal for {asset_id}: {e}")
                    continue
            
            return {
                "success": True,
                "message": f"Generated {len(generated_signals)} signals from {len(assets_to_scan)} assets scanned",
                "signals": generated_signals,
                "assets_scanned": len(assets_to_scan)
            }
        
    except Exception as e:
        logging.error(f"Error in enhanced auto-generate: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/auto-generate/stop")
async def stop_auto_signal_generation():
    """Stop automated signal generation mode"""
    try:
        from server import trading_bot
        # Set auto signal generation flag to False
        trading_bot.auto_signal_generation = False
        
        return {
            "success": True,
            "message": "Automated signal generation stopped",
            "status": "stopped"
        }
        
    except Exception as e:
        logging.error(f"Error stopping auto signal generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/signals/auto-generate/status")
async def get_auto_signal_generation_status():
    """Get current automated signal generation status"""
    try:
        from server import trading_bot
        status = getattr(trading_bot, 'auto_signal_generation', False)
        return {
            "auto_generation_active": status,
            "bot_running": trading_bot.is_running,
            "status": "active" if status and trading_bot.is_running else "stopped"
        }
        
    except Exception as e:
        logging.error(f"Error getting auto signal generation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# LATEST SIGNAL ENDPOINT (for Mobile Auto-Trader Userscript)
# ============================================================================

@router.get("/signals/latest")
async def get_latest_signal(use_enhanced: bool = Query(True, description="Use enhanced AI signal if no recent signal")):
    """
    Get the most recent trading signal for the auto-trader userscript
    
    This endpoint is polled by the Tampermonkey userscript running on 
    the user's mobile device (Kiwi Browser) to auto-execute trades.
    
    Returns the latest signal if it was generated within the last 5 minutes.
    If use_enhanced=True and no recent signal exists, generates a new one.
    """
    try:
        # Get the most recent signal from database (check trading_signals collection)
        latest_signal = await db.trading_signals.find_one(
            {},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        
        signal_is_stale = False
        age_seconds = 999999
        
        if latest_signal:
            # Check if signal is recent (within last 5 minutes)
            signal_time = latest_signal.get('timestamp')
            if signal_time:
                try:
                    if isinstance(signal_time, str):
                        from dateutil import parser
                        signal_dt = parser.parse(signal_time)
                    else:
                        signal_dt = signal_time
                    
                    # Make timezone-aware if needed
                    if signal_dt.tzinfo is None:
                        signal_dt = signal_dt.replace(tzinfo=timezone.utc)
                    
                    age_seconds = (datetime.now(timezone.utc) - signal_dt).total_seconds()
                    signal_is_stale = age_seconds > 300  # 5 minutes
                except Exception as parse_error:
                    logger.warning(f"Could not parse signal timestamp: {parse_error}")
                    signal_is_stale = True
        else:
            signal_is_stale = True
        
        # If signal is stale and enhanced mode is enabled, generate new signal
        if signal_is_stale and use_enhanced and enhanced_oanda.is_configured:
            try:
                # Get the default trading asset from config
                config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
                default_asset = "EUR_USD"
                if config_doc and config_doc.get('selected_assets'):
                    # Get first selected asset, convert to OANDA format
                    first_asset = config_doc['selected_assets'][0]
                    if '_' not in first_asset:
                        # Convert EURUSD to EUR_USD
                        if len(first_asset) == 6:
                            default_asset = f"{first_asset[:3]}_{first_asset[3:]}"
                        else:
                            default_asset = first_asset.replace("_OTC", "").replace("-", "_")
                    else:
                        default_asset = first_asset.replace("_OTC", "")
                
                # Generate enhanced signal
                trend_signal = enhanced_oanda.generate_trend_signal(default_asset, "M1")
                
                if trend_signal and trend_signal.recommended_action != "HOLD":
                    # Create signal record
                    new_signal = {
                        "id": f"ENHANCED_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{default_asset}",
                        "symbol": default_asset.replace("_", ""),
                        "direction": trend_signal.recommended_action,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "confidence": trend_signal.confidence,
                        "probability": trend_signal.confidence,
                        "expiration_minutes": 1,
                        "strategy": "Enhanced AI + Technical",
                        "trend_direction": trend_signal.direction,
                        "trend_strength": trend_signal.strength.value,
                        "entry_price": trend_signal.entry_price,
                        "stop_loss": trend_signal.stop_loss,
                        "take_profit": trend_signal.take_profit,
                        "supporting_indicators": trend_signal.supporting_indicators,
                        "source": "enhanced_oanda"
                    }
                    
                    # Save to database
                    signal_doc = {**new_signal}
                    signal_doc.pop('_id', None)
                    await db.trading_signals.insert_one(signal_doc)
                    
                    # Remove _id before returning
                    if "_id" in new_signal:
                        del new_signal["_id"]
                    
                    logger.info(f"Generated enhanced signal: {new_signal['direction']} {new_signal['symbol']} ({new_signal['confidence']:.1f}%)")
                    
                    return {
                        "success": True,
                        "signal": new_signal,
                        "message": "Enhanced signal generated for auto-trading",
                        "auto_generated": True
                    }
                else:
                    return {
                        "success": False,
                        "message": "Market conditions unclear - no signal generated (HOLD recommended)",
                        "signal": None,
                        "recommendation": "HOLD"
                    }
                    
            except Exception as enhanced_error:
                logger.error(f"Enhanced signal generation failed: {enhanced_error}")
                # Fall through to return stale signal info
        
        if not latest_signal:
            return {
                "success": False,
                "message": "No signals generated yet. Use Dashboard to generate a signal.",
                "signal": None
            }
        
        if signal_is_stale:
            return {
                "success": False,
                "message": f"No recent signals (last signal is {int(age_seconds)}s old). Generate a new signal from Dashboard.",
                "signal": None,
                "last_signal_age_seconds": age_seconds
            }
        
        # Add unique ID if not present
        if 'id' not in latest_signal:
            latest_signal['id'] = f"sig_{latest_signal.get('symbol', 'UNK')}_{signal_time}"
        
        # Normalize direction for userscript
        direction = latest_signal.get('direction', 'CALL')
        if isinstance(direction, str):
            if 'BUY' in direction.upper() or 'CALL' in direction.upper():
                latest_signal['direction'] = 'CALL'
            else:
                latest_signal['direction'] = 'PUT'
        
        # Add confidence for display
        latest_signal['confidence'] = latest_signal.get('probability', 85)
        
        return {
            "success": True,
            "signal": latest_signal,
            "message": "Signal available for auto-trading"
        }
        
    except Exception as e:
        logger.error(f"Error getting latest signal: {e}")
        return {
            "success": False,
            "error": str(e),
            "signal": None
        }




@router.post("/signals/force-generate")
async def force_generate_signals(wait_for_candle: bool = Query(False)):
    """
    Force generate trading signals for ALL selected assets using maximum analysis depth
    Bypasses all thresholds and uses advanced multi-strategy analysis
    
    Args:
        wait_for_candle: Whether to wait for next candle formation for Pocket Option sync (default: False for speed, set True for perfect timing)
    """
    try:
        # Get user's configuration for selected assets and timeframes
        try:
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            selected_assets = config_doc.get('selected_assets', []) if config_doc else []
            user_expirations = config_doc.get('selected_expirations', []) if config_doc else []
            chart_type = config_doc.get('chart_type', 'japanese_candles') if config_doc else 'japanese_candles'
            invert_signals = config_doc.get('invert_signals', False) if config_doc else False
            
            # Load adaptive strategy configuration
            adaptive_config = await adaptive_strategy_service_instance.get_config("default_user")
            logger.info(f"🎯 Adaptive Strategy: {'Enabled' if adaptive_config.enabled else 'Disabled'}")
            
            # FORCE GENERATE ALWAYS USES wait_for_candle=False for fast response (~10s target)
            # User can explicitly pass wait_for_candle=true in query parameter if timing is critical
            logger.info(f"⚡ Force generation mode: wait_for_candle={wait_for_candle} (target: fast ~10s response)")
            
            # If no assets selected, return error - require user to select assets
            if not selected_assets or len(selected_assets) == 0:
                logger.warning("⚠️ No assets selected for force signal generation")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "No assets selected",
                        "message": "⚠️ Please select at least one asset from the Market Assets section on the Dashboard before generating signals."
                    }
                )
            
            # If no expirations are selected, return error - require user to select expiration
            if not user_expirations or len(user_expirations) == 0:
                logger.warning("⚠️ No expirations selected for force signal generation")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "No expirations selected",
                        "message": "⚠️ Please select at least one expiration time from the Trade Expiration section on the Dashboard before generating signals."
                    }
                )
                
        except Exception as e:
            logger.error(f"Error getting user configuration: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Configuration error",
                    "message": f"Error retrieving configuration: {str(e)}"
                }
            )
        
        logger.info(f"📊 Force generating signals for {len(selected_assets)} selected assets: {selected_assets}")
        logger.info(f"⏱️ Using expirations: {user_expirations}")
        logger.info(f"🎴 Using chart type: {chart_type}")
        
        all_forced_signals = []
        
        # Generate signals for ALL selected assets
        logger.info(f"📊 Generating signals for {len(selected_assets)} selected assets: {selected_assets}")
        
        # Generate signals for each selected asset
        for asset in selected_assets:
            # Extract base symbol (remove _regular or _otc suffix)
            base_symbol = asset.replace('_regular', '').replace('_otc', '')
            market_type = 'otc' if '_otc' in asset.lower() else 'regular'
            
            logger.info(f"🚀 FORCE GENERATING SIGNAL for {asset} (base: {base_symbol}, market: {market_type})")
            
            # CRITICAL: Fetch REAL market data from OANDA before generating signal
            from trading_models import MarketData, AssetType
            from enhanced_oanda_service import enhanced_oanda
            
            # Normalize symbol for OANDA (EURUSD -> EUR_USD)
            oanda_symbol = base_symbol
            if len(base_symbol) == 6 and '_' not in base_symbol:
                oanda_symbol = f"{base_symbol[:3]}_{base_symbol[3:]}"
            
            # Fetch real-time price and candles from OANDA
            current_price = 1.0500  # Default fallback
            try:
                oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 5)
                if oanda_df is not None and len(oanda_df) > 0:
                    current_price = float(oanda_df['close'].iloc[-1])
                    logger.info(f"📊 OANDA real-time price for {base_symbol}: {current_price:.5f}")
                else:
                    logger.warning(f"⚠️ No OANDA data for {oanda_symbol}, using fallback price")
            except Exception as e:
                logger.warning(f"⚠️ OANDA fetch failed for {oanda_symbol}: {e}")
            
            target_asset = MarketData(
                symbol=base_symbol,
                price=current_price,  # Use REAL price from OANDA
                timestamp=datetime.now(timezone.utc),
                asset_type=AssetType.FOREX,  # Will be determined by symbol
                volume=0
            )
            
            # Dynamic timeout based on candle synchronization setting
            # If waiting for candle, allow up to 65 seconds (max 60s wait + 5s processing)
            # Otherwise use 10-second timeout for fast response (optimized)
            timeout_seconds = 65.0 if wait_for_candle else 10.0
            
            try:
                forced_signals = await asyncio.wait_for(
                    force_signal_generator.force_generate_signal(
                        base_symbol, target_asset, user_expirations, chart_type=chart_type, wait_for_candle=wait_for_candle, adaptive_config=adaptive_config
                    ),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"❌ Signal generation timeout for {asset} after {timeout_seconds} seconds")
                forced_signals = None
            
            if forced_signals:
                # Tag signals with the selected asset info
                for signal in forced_signals:
                    signal.symbol = asset  # Use full asset name with suffix
                    signal.market_type = market_type
                
                all_forced_signals.extend(forced_signals)
                logger.info(f"✅ Generated {len(forced_signals)} signals for {asset}")
            else:
                logger.warning(f"⚠️ No signals generated for {asset}")
        
        if all_forced_signals:
            stored_signals = []
            
            # Store all forced signals in database
            for signal in all_forced_signals:
                try:
                    signal_dict = signal.dict()
                    signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
                    signal_dict['precision_entry_time'] = signal_dict['precision_entry_time'].isoformat() if signal_dict['precision_entry_time'] else None
                    # Convert numpy types for JSON serialization
                    signal_dict = _convert_numpy_types(signal_dict)
                    
                    result = await db.trading_signals.insert_one(signal_dict)
                    logger.info(f"Signal {signal_dict.get('id')} stored successfully in database")
                        
                except Exception as e:
                    logger.error(f"Error storing signal {signal.id} in database: {e}")
                    # Continue with other signals even if one fails
                
                # Apply signal inversion if enabled in configuration
                if invert_signals:
                    original_direction = signal.direction
                    if signal.direction in [SignalDirection.BUY, SignalDirection.CALL]:
                        signal.direction = SignalDirection.SELL
                        logger.info(f"🔄 SIGNAL INVERTED: {original_direction} → SELL for {signal.symbol}")
                    else:
                        signal.direction = SignalDirection.BUY
                        logger.info(f"🔄 SIGNAL INVERTED: {original_direction} → BUY for {signal.symbol}")
                    
                    # Add inversion note to justification
                    signal.justification = f"[INVERTED - Original: {original_direction.value if hasattr(original_direction, 'value') else original_direction}] {signal.justification}"
                
                # Calculate seconds to entry for countdown timer
                seconds_to_entry = 0
                if signal.precision_entry_time:
                    from pocket_option_timing_sync import pocket_option_sync
                    chicago_time = pocket_option_sync.get_chicago_time()
                    seconds_to_entry = max(0, (signal.precision_entry_time - chicago_time).total_seconds())
                
                stored_signals.append({
                    "id": str(signal.id),
                    "symbol": str(signal.symbol),
                    "direction": signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
                    "entry_price": float(signal.entry_price),
                    "probability": float(signal.probability),
                    "expiration_minutes": float(signal.expiration_minutes),  # Keep as float for sub-minute expirations
                    "timeframe": str(signal.timeframe),
                    "market_type": str(signal.market_type),
                    "suggested_stake": float(signal.suggested_stake),
                    "justification": str(signal.justification),
                    "strategy_used": str(signal.strategy_used),
                    "confidence_level": str(signal.confidence_level),
                    "precision_entry_time": signal.precision_entry_time.isoformat() if signal.precision_entry_time else None,
                    "seconds_to_entry": float(seconds_to_entry),  # For countdown timer synchronization
                    "technical_analysis": _convert_numpy_types(signal.technical_analysis) if signal.technical_analysis else {},
                    "forced_generation": True,
                    "timestamp": signal.timestamp.isoformat()
                })
                
                # ✨ NEW: Process signal through automated trading service
                try:
                    await process_signal_for_automated_trading({
                        "symbol": stored_signals[-1]["symbol"],
                        "direction": "call" if "BUY" in str(signal.direction).upper() or "CALL" in str(signal.direction).upper() else "put",
                        "probability": stored_signals[-1]["probability"],
                        "timeframe": int(signal.expiration_minutes * 60),  # Convert to seconds
                        "strategy": stored_signals[-1]["strategy_used"]
                    })
                except Exception as e:
                    logger.error(f"Error processing signal through automated trading: {e}")
                
                # Send to platforms if enabled
                try:
                    await platform_integration.send_signal_to_all_platforms(signal)
                except Exception as e:
                    logger.warning(f"Could not send forced signal to platforms: {e}")
                
                # Schedule signal validation (will check if signal was WIN/LOSS after expiration)
                try:
                    await signal_validator.schedule_signal_validation(stored_signals[-1])
                    logger.info(f"📅 Scheduled validation for signal {signal.id}")
                except Exception as e:
                    logger.warning(f"Could not schedule signal validation: {e}")
            
            # Extract analysis details with OTC boost information
            analysis_details = forced_signals[0].technical_analysis if forced_signals else {}
            otc_signal = next((s for s in forced_signals if s.market_type == 'otc'), None)
            if otc_signal:
                analysis_details["otc_boost_applied"] = otc_signal.technical_analysis.get('otc_boost_applied', 0)
            
            # Return ALL signals for selected assets
            num_signals = len(stored_signals)
            
            if num_signals == 1:
                # Single signal response
                best_signal = stored_signals[0]
                market_type = best_signal.get("market_type", "otc")
                timeframe = best_signal.get("timeframe", "5s")
                
                response = {
                    "success": True,
                    "message": f"🎯 Signal generated for {best_signal.get('symbol')} - {market_type.upper()} {timeframe} timeframe",
                    "signal": best_signal,
                    "signals": stored_signals,
                    "market_type": market_type,
                    "timeframe": timeframe,
                    "analysis_details": analysis_details
                }
            else:
                # Multiple signals response
                timeframes_used = list(set(s.get("timeframe", "5s") for s in stored_signals))
                assets_list = [s.get("symbol") for s in stored_signals]
                
                response = {
                    "success": True,
                    "message": f"🎯 {num_signals} signals generated for {', '.join(assets_list)} - Timeframes: {', '.join(timeframes_used)}",
                    "signal": stored_signals[0],  # First signal for backward compatibility
                    "signals": stored_signals,  # All signals
                    "count": num_signals,
                    "assets": assets_list,
                    "timeframes": timeframes_used,
                    "analysis_details": analysis_details
                }
            
            return _convert_numpy_types(response)
        else:
            return {
                "success": False,
                "message": "Unable to force generate signal - system error occurred",
                "signal": None
            }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in force signal generation: {e}")
        raise HTTPException(status_code=500, detail=f"Force signal generation failed: {str(e)}")



@router.post("/signals/force-generate/asset/{asset_symbol}")
async def force_generate_signal_for_asset(asset_symbol: str, wait_for_candle: bool = False):
    """
    Force generate a signal for a specific asset
    Uses maximum analysis depth and bypasses all thresholds
    
    Args:
        asset_symbol: The trading symbol to generate signal for
        wait_for_candle: Whether to wait for the next candle formation before generating signal (default: True)
    """
    try:
        # Get market data for the specific asset
        # Strip _OTC/_regular suffix for data lookup
        base_symbol = asset_symbol.replace('_OTC', '').replace('_otc', '').replace('_regular', '').replace('_REGULAR', '')
        
        # Determine asset type from symbol
        asset_type = AssetType.FOREX  # Default
        if any(crypto in asset_symbol.upper() for crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'BNB']):
            asset_type = AssetType.CRYPTO
        elif asset_symbol.upper() in ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA']:
            asset_type = AssetType.STOCKS
        elif any(commodity in asset_symbol.upper() for commodity in ['XAU', 'XAG', 'OIL', 'GOLD', 'SILVER']):
            asset_type = AssetType.COMMODITIES
        elif any(index in asset_symbol.upper() for index in ['SPX', 'NAS', 'DJ', 'FTSE', 'DAX']):
            asset_type = AssetType.INDICES
        
        # PRIMARY: Try OANDA data (most reliable for forex)
        target_data = None
        try:
            oanda_symbol = base_symbol
            if len(base_symbol) == 6 and '_' not in base_symbol:
                oanda_symbol = f"{base_symbol[:3]}_{base_symbol[3:]}"
            
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 5)
            if oanda_df is not None and len(oanda_df) > 0:
                current_price = float(oanda_df['close'].iloc[-1])
                logger.info(f"📊 OANDA price for {base_symbol}: {current_price:.5f}")
                from trading_models import MarketData
                target_data = MarketData(
                    symbol=base_symbol,
                    price=current_price,
                    timestamp=datetime.now(timezone.utc),
                    asset_type=asset_type,
                    volume=0
                )
        except Exception as e:
            logger.warning(f"OANDA fetch failed for {base_symbol}: {e}")
        
        # FALLBACK: Try RealMarketDataService
        if not target_data:
            try:
                market_data_service = RealMarketDataService()
                data_dict = market_data_service.get_real_time_data(base_symbol, asset_type.value)
                if data_dict:
                    from trading_models import MarketData
                    target_data = MarketData(
                        symbol=base_symbol,
                        price=data_dict.get('price', 0.0),
                        timestamp=datetime.now(timezone.utc),
                        asset_type=asset_type,
                        volume=data_dict.get('volume', 0)
                    )
            except Exception as e:
                logger.warning(f"RealMarketDataService failed for {base_symbol}: {e}")
        
        # FALLBACK 2: yfinance (wrapped in try/except)
        if not target_data:
            try:
                import yfinance as yf
                yf_symbol = base_symbol
                if base_symbol == 'BTCUSD':
                    yf_symbol = 'BTC-USD'
                elif base_symbol == 'ETHUSD':
                    yf_symbol = 'ETH-USD'
                elif len(base_symbol) == 6:
                    yf_symbol = base_symbol + '=X'
                
                ticker = yf.Ticker(yf_symbol)
                hist = ticker.history(period="1d", interval="1m")
                
                if not hist.empty:
                    from trading_models import MarketData
                    target_data = MarketData(
                        symbol=base_symbol,
                        price=float(hist['Close'].iloc[-1]),
                        timestamp=datetime.now(timezone.utc),
                        asset_type=asset_type,
                        volume=float(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
                    )
            except Exception as e:
                logger.warning(f"yfinance failed for {base_symbol}: {e}")
        
        # EMERGENCY: Create default market data - NEVER fail
        if not target_data:
            logger.warning(f"No market data for {base_symbol} - using emergency defaults")
            from trading_models import MarketData
            target_data = MarketData(
                symbol=base_symbol,
                price=1.0000 if asset_type == AssetType.FOREX else 100.0,
                timestamp=datetime.now(timezone.utc),
                asset_type=asset_type,
                volume=0
            )
        
        logger.info(f"🚀 FORCE GENERATING SIGNAL for specific asset: {asset_symbol}")
        
        # Get user's selected expirations from current configuration
        try:
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            user_expirations = config_doc.get('selected_expirations', ['5s']) if config_doc else ['5s']
            invert_signals = config_doc.get('invert_signals', False) if config_doc else False
            
            # Load adaptive strategy configuration
            adaptive_config = await adaptive_strategy_service_instance.get_config("default_user")
            
            # If no expirations are selected, use ultra-short default
            if not user_expirations or len(user_expirations) == 0:
                user_expirations = ['5s']  # Default to ultra-short 5 second expiration
                logger.info("No expirations selected, using ultra-short 5s default")
        except Exception as e:
            logger.warning(f"Could not get user expirations, using default: {e}")
            user_expirations = ['5s']
            invert_signals = False
        
        logger.info(f"Using user selected expirations for {asset_symbol}: {user_expirations}")
        
        # Force generate signals (both regular and OTC)
        forced_signals = await force_signal_generator.force_generate_signal(
            target_data.symbol, target_data, user_expirations, wait_for_candle=wait_for_candle, adaptive_config=adaptive_config
        )
        
        if forced_signals:
            stored_signals = []
            
            # Store all forced signals
            for signal in forced_signals:
                signal_dict = signal.dict()
                signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
                signal_dict['precision_entry_time'] = signal_dict['precision_entry_time'].isoformat() if signal_dict['precision_entry_time'] else None
                # Convert numpy types for JSON serialization
                signal_dict = _convert_numpy_types(signal_dict)
                await db.trading_signals.insert_one(signal_dict)
                
                # Apply signal inversion if enabled in configuration
                if invert_signals:
                    original_direction = signal.direction
                    if signal.direction in [SignalDirection.BUY, SignalDirection.CALL]:
                        signal.direction = SignalDirection.SELL
                        logger.info(f"🔄 SIGNAL INVERTED: {original_direction} → SELL for {signal.symbol}")
                    else:
                        signal.direction = SignalDirection.BUY
                        logger.info(f"🔄 SIGNAL INVERTED: {original_direction} → BUY for {signal.symbol}")
                    
                    # Add inversion note to justification
                    signal.justification = f"[INVERTED - Original: {original_direction.value if hasattr(original_direction, 'value') else original_direction}] {signal.justification}"
                
                # Calculate seconds to entry for countdown timer
                seconds_to_entry = 0
                if signal.precision_entry_time:
                    from pocket_option_timing_sync import pocket_option_sync
                    chicago_time = pocket_option_sync.get_chicago_time()
                    seconds_to_entry = max(0, (signal.precision_entry_time - chicago_time).total_seconds())
                
                stored_signals.append({
                    "id": str(signal.id),
                    "symbol": str(signal.symbol),
                    "direction": signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
                    "entry_price": float(signal.entry_price),
                    "probability": float(signal.probability),
                    "expiration_minutes": float(signal.expiration_minutes),  # Keep as float for sub-minute expirations
                    "timeframe": str(signal.timeframe),
                    "market_type": str(signal.market_type),
                    "suggested_stake": float(signal.suggested_stake),
                    "justification": str(signal.justification),
                    "strategy_used": str(signal.strategy_used),
                    "confidence_level": str(signal.confidence_level),
                    "precision_entry_time": signal.precision_entry_time.isoformat() if signal.precision_entry_time else None,
                    "seconds_to_entry": float(seconds_to_entry),  # For countdown timer synchronization
                    "technical_analysis": _convert_numpy_types(signal.technical_analysis) if signal.technical_analysis else {},
                    "forced_generation": True,
                    "timestamp": signal.timestamp.isoformat()
                })
                
                # Send to platforms
                try:
                    await platform_integration.send_signal_to_all_platforms(signal)
                except Exception as e:
                    logger.warning(f"Could not send forced signal to platforms: {e}")
            
            # Extract analysis details from the single best signal
            best_signal_obj = forced_signals[0] if forced_signals else None
            analysis_details = best_signal_obj.technical_analysis if best_signal_obj else {}
            
            # Get best signal from stored signals
            best_signal = stored_signals[0] if stored_signals else None
            market_type = best_signal.get("market_type", "otc") if best_signal else "otc"
            timeframe = best_signal.get("timeframe", "5s") if best_signal else "5s"
            
            response = {
                "success": True,
                "message": f"🎯 Single {market_type.upper()} signal generated for {asset_symbol} at {timeframe} timeframe",
                "asset": asset_symbol,
                "signal": best_signal,  # Single best signal
                "signals": stored_signals,  # Keep for compatibility
                "market_type": market_type,
                "timeframe": timeframe,
                "analysis_details": analysis_details
            }
            return _convert_numpy_types(response)
        else:
            raise HTTPException(status_code=500, detail="Force signal generation failed")
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in force signal generation for {asset_symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Force signal generation failed: {str(e)}")




@router.post("/signals/flexible-generate")
async def flexible_signal_generation(request: FlexibleStrategyRequest):
    """
    Generate signal using flexible crossover strategy with custom parameters
    Allows independent selection of chart timeframe and trade duration
    """
    try:
        from flexible_crossover_strategy import get_flexible_strategy
        
        logger.info("🎯 Flexible Strategy Signal Generation Request:")
        logger.info(f"   Asset: {request.asset_symbol}")
        logger.info(f"   Market Type: {request.market_type}")
        logger.info(f"   Chart Timeframe: {request.chart_timeframe}")
        logger.info(f"   Trade Duration: {request.trade_duration_seconds}s")
        logger.info(f"   Force Signal: {request.force_signal}")
        logger.info(f"   Indicators: SMA({request.sma_fast}/{request.sma_slow}), ST(ATR:{request.supertrend_atr_period}, M:{request.supertrend_multiplier}), AO({request.ao_short_period}/{request.ao_long_period})")
        
        # Create flexible strategy instance with custom parameters
        strategy = get_flexible_strategy(
            chart_timeframe=request.chart_timeframe,
            sma_fast=request.sma_fast,
            sma_slow=request.sma_slow,
            supertrend_atr_period=request.supertrend_atr_period,
            supertrend_multiplier=request.supertrend_multiplier,
            ao_short_period=request.ao_short_period,
            ao_long_period=request.ao_long_period
        )
        
        # Convert symbol format if needed (for yfinance compatibility)
        # Remove OTC suffix if present for yfinance
        base_symbol = request.asset_symbol.replace('_OTC', '').replace('_otc', '')
        yf_symbol = base_symbol
        
        # Forex pairs
        if base_symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD',
                           'EURGBP', 'EURJPY', 'EURCHF', 'GBPJPY', 'GBPCHF', 'CHFJPY', 
                           'CADJPY', 'AUDJPY', 'AUDCHF', 'NZDJPY']:
            yf_symbol = f'{base_symbol}=X'
        # Crypto
        elif base_symbol == 'BTCUSD':
            yf_symbol = 'BTC-USD'
        elif base_symbol == 'ETHUSD':
            yf_symbol = 'ETH-USD'
        elif base_symbol == 'LTCUSD':
            yf_symbol = 'LTC-USD'
        elif base_symbol == 'ADAUSD':
            yf_symbol = 'ADA-USD'
        elif base_symbol == 'DOGEUSD':
            yf_symbol = 'DOGE-USD'
        elif base_symbol == 'SOLUSD':
            yf_symbol = 'SOL-USD'
        
        # Generate signal
        result = strategy.generate_signal(yf_symbol, trade_duration_seconds=request.trade_duration_seconds, force_signal=request.force_signal)
        
        if not result:
            return {
                "success": False,
                "message": f"No signal generated for {request.asset_symbol} ({request.market_type.upper()}) on {request.chart_timeframe} chart - market conditions not met",
                "signal": None
            }
        
        # Convert to TradingSignal model
        signal_direction = SignalDirection.CALL if result['signal'] == 'CALL' else SignalDirection.PUT
        
        # Determine asset type
        asset_type = AssetType.FOREX
        if any(crypto in base_symbol.upper() for crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE', 'SOL', 'AVAX', 'MATIC']):
            asset_type = AssetType.CRYPTO
        elif base_symbol.upper() in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA', 'JPM', 'BAC']:
            asset_type = AssetType.STOCKS
        elif base_symbol.upper() in ['XAUUSD', 'XAGUSD', 'BRENTOIL', 'WTIUSD', 'NATGAS', 'XPTUSD', 'XPDUSD']:
            asset_type = AssetType.COMMODITIES
        elif base_symbol.upper() in ['US100', 'US30', 'SPX500', 'GER40', 'UK100', 'JPN225']:
            asset_type = AssetType.INDICES
        
        # Add market type suffix to symbol for display
        display_symbol = f"{request.asset_symbol}_{request.market_type.upper()}" if request.market_type == 'otc' else request.asset_symbol
        
        # Create TradingSignal object
        trading_signal = TradingSignal(
            symbol=display_symbol,
            asset_type=asset_type,
            direction=signal_direction,
            entry_price=result['analysis'].get('current_price', result['analysis']['sma_fast']),  # Use actual current price
            expiration_minutes=request.trade_duration_seconds // 60,
            timeframe=request.chart_timeframe,
            market_type=request.market_type,
            probability=result['confidence'],
            confidence_level=result.get('confidence_level', "HIGH" if result['confidence'] >= 90 else ("MEDIUM" if result['confidence'] >= 80 else "LOW")),
            strategy_used=TradingStrategy.EMA_CROSSOVER,  # Using crossover strategy
            technical_analysis={
                "current_price": result['analysis'].get('current_price', 0),
                "sma_fast": result['analysis']['sma_fast'],
                "sma_slow": result['analysis']['sma_slow'],
                "sma_cross": result['analysis']['sma_cross'],
                "supertrend": result['analysis']['supertrend'],
                "awesome_oscillator": result['analysis']['awesome_oscillator'],
                "ao_direction": result['analysis']['ao_direction'],
                "chart_timeframe": result['chart_timeframe'],
                "trade_duration_text": result['trade_duration_text'],
                "trade_duration_seconds": request.trade_duration_seconds
            },
            market_analysis_summary=f"Flexible Crossover Strategy on {request.chart_timeframe} chart ({request.market_type.upper()} market)",
            justification="\n".join(result['reasoning']),
            risk_assessment=f"Confidence: {result['confidence']}% - {result.get('confidence_level', 'HIGH')}",
            suggested_stake=10.0  # Default stake
        )
        
        # Store signal in database
        signal_dict = trading_signal.dict()
        signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
        signal_dict['precision_entry_time'] = None
        signal_dict = _convert_numpy_types(signal_dict)
        await db.trading_signals.insert_one(signal_dict)
        
        logger.info(f"✅ Flexible signal generated and stored: {signal_direction.value} for {display_symbol} ({request.market_type.upper()})")
        
        return {
            "success": True,
            "message": f"Signal generated for {request.market_type.upper()} market using {request.chart_timeframe} chart with {result['trade_duration_text']} expiration",
            "signal": {
                "id": trading_signal.id,
                "symbol": trading_signal.symbol,
                "direction": trading_signal.direction.value,
                "entry_price": float(trading_signal.entry_price),
                "probability": float(trading_signal.probability),
                "confidence_level": trading_signal.confidence_level,
                "timeframe": trading_signal.timeframe,
                "expiration_minutes": trading_signal.expiration_minutes,
                "trade_duration_text": result['trade_duration_text'],
                "justification": trading_signal.justification,
                "technical_analysis": trading_signal.technical_analysis,
                "timestamp": trading_signal.timestamp.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error in flexible signal generation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Flexible signal generation failed: {str(e)}")





@router.post("/signals/micro-momentum-5s-otc")
async def micro_momentum_5s_otc_signal_generation(asset_symbol: str, trade_duration_seconds: int = 5):
    """
    Generate signal using Micro-Momentum Scalp strategy for 5-second OTC markets
    
    Strategy: EMA20 + RSI(2) + Stochastic(3,1,1) + Bollinger Bands(5,2.5)
    Target: 65-75% win rate through micro-trend confluence
    Markets: OTC Forex only (EUR/USD_OTC, GBP/USD_OTC, etc.)
    """
    try:
        from micro_momentum_scalp_5s_otc import get_micro_momentum_5s_otc_strategy
        
        logger.info("🚀 Micro-Momentum 5s OTC Signal Generation:")
        logger.info(f"   Asset: {asset_symbol}")
        logger.info(f"   Trade Duration: {trade_duration_seconds}s")
        
        # Ensure it's an OTC market
        if "_OTC" not in asset_symbol.upper() and "_otc" not in asset_symbol:
            logger.warning(f"⚠️ {asset_symbol} is not OTC market, appending _OTC suffix")
            display_symbol = f"{asset_symbol}_OTC"
        else:
            display_symbol = asset_symbol
        
        # Get strategy instance
        strategy = get_micro_momentum_5s_otc_strategy()
        
        # Convert symbol for yfinance
        base_symbol = asset_symbol.replace('_OTC', '').replace('_otc', '')
        yf_symbol = base_symbol
        
        # Forex pairs
        if base_symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD',
                           'EURGBP', 'EURJPY', 'EURCHF', 'GBPJPY', 'GBPCHF', 'CHFJPY',
                           'CADJPY', 'AUDJPY', 'AUDCHF', 'NZDJPY', 'EURAUD', 'EURCAD', 'GBPCAD']:
            yf_symbol = f'{base_symbol}=X'
        
        # Generate signal
        result = strategy.generate_signal(yf_symbol, trade_duration_seconds=trade_duration_seconds)
        
        if not result:
            return {
                "success": False,
                "message": f"No signal generated for {display_symbol} on 5s OTC - market conditions not met",
                "signal": None
            }
        
        # Convert to TradingSignal model
        signal_direction = SignalDirection.CALL if result['signal'] == 'CALL' else SignalDirection.PUT
        
        # Create TradingSignal object
        trading_signal = TradingSignal(
            symbol=display_symbol,
            asset_type=AssetType.FOREX,  # OTC is primarily Forex
            direction=signal_direction,
            entry_price=result['analysis']['current_price'],
            expiration_minutes=trade_duration_seconds // 60 if trade_duration_seconds >= 60 else 0,
            timeframe="5s",
            market_type="otc",  # Always OTC
            probability=result['confidence'],
            confidence_level=result['confidence_level'],
            strategy_used=TradingStrategy.EMA_CROSSOVER,  # Closest match
            technical_analysis={
                "current_price": result['analysis']['current_price'],
                "ema20": result['analysis']['ema20'],
                "rsi2": result['analysis']['rsi2'],
                "stoch_k": result['analysis']['stoch_k'],
                "stoch_d": result['analysis']['stoch_d'],
                "bb_upper": result['analysis']['bb_upper'],
                "bb_lower": result['analysis']['bb_lower'],
                "bb_width": result['analysis']['bb_width'],
                "trend": result['analysis']['trend'],
                "volatility": result['analysis']['volatility'],
                "trade_duration_seconds": trade_duration_seconds,
                "trade_duration_text": result['trade_duration_text']
            },
            market_analysis_summary=f"Micro-Momentum Scalp 5s OTC for {display_symbol}",
            justification="\n".join(result['reasoning']),
            risk_assessment=f"Confidence: {result['confidence']}% - {result['confidence_level']} (5s OTC scalping)",
            suggested_stake=10.0  # Default stake
        )
        
        # Store signal in database
        signal_dict = trading_signal.dict()
        signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
        signal_dict['precision_entry_time'] = None
        signal_dict = _convert_numpy_types(signal_dict)
        await db.trading_signals.insert_one(signal_dict)
        
        logger.info(f"✅ Micro-Momentum 5s OTC signal generated: {signal_direction.value} for {display_symbol}")
        
        return {
            "success": True,
            "message": f"5-second OTC signal generated for {display_symbol} with {result['confidence']}% confidence",
            "signal": {
                "id": trading_signal.id,
                "symbol": trading_signal.symbol,
                "direction": trading_signal.direction.value,
                "entry_price": float(trading_signal.entry_price),
                "probability": float(trading_signal.probability),
                "confidence_level": trading_signal.confidence_level,
                "timeframe": "5s",
                "market_type": "otc",
                "expiration_minutes": trading_signal.expiration_minutes,
                "trade_duration_text": result['trade_duration_text'],
                "justification": trading_signal.justification,
                "technical_analysis": trading_signal.technical_analysis,
                "timestamp": trading_signal.timestamp.isoformat(),
                "strategy": "Micro-Momentum Scalp 5s OTC"
            }
        }
        
    except Exception as e:
        logger.error(f"Error in micro-momentum 5s OTC signal generation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Micro-momentum signal generation failed: {str(e)}")


@router.post("/signals/keltner-macd-5s")
async def keltner_macd_5s_signal(
    symbol: str = Query("EURUSD_OTC", description="Asset symbol"),
    background_tasks: BackgroundTasks = None
):
    """
    5-Second Keltner Channel + MACD Strategy
    
    Indicators:
    - Keltner Channel: EMA(20), ATR(60), Multiplier 4
    - MACD: Fast(13), Slow(24), Signal(11)
    
    BUY (CALL): Price breaks above KC middle + MACD bullish cross
    SELL (PUT): Price breaks below KC middle + MACD bearish cross
    """
    try:
        from high_accuracy_strategies import keltner_macd_strategy
        
        # Get candle data (need at least 65 candles for ATR(60))
        candles = []
        
        # Try OANDA first
        try:
            oanda_symbol = symbol.replace("_OTC", "").replace("/", "_")
            if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
            
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, granularity="S5", count=100)
            if oanda_df is not None and len(oanda_df) > 0:
                candles = oanda_df.to_dict('records')
        except Exception as e:
            logger.debug(f"OANDA fetch failed: {e}")
        
        # Fallback to DB
        if len(candles) < 65:
            db_ref = router.app_state.get("db") if hasattr(router, 'app_state') else None
            if not db_ref:
                from server import db as server_db
                db_ref = server_db
            
            if db_ref is not None:
                cursor = db_ref.historical_candles.find(
                    {"symbol": symbol.replace("_OTC", "").replace("_", "/")},
                    {"_id": 0}
                ).sort("timestamp", -1).limit(100)
                db_candles = await cursor.to_list(100)
                if len(db_candles) > len(candles):
                    candles = list(reversed(db_candles))
        
        if len(candles) < 65:
            return {
                "success": False,
                "error": "Insufficient data",
                "candles_available": len(candles),
                "candles_required": 65
            }
        
        # Get current price
        current_price = float(candles[-1].get('close', candles[-1].get('Close', 0)))
        
        # Analyze with Keltner-MACD strategy
        signal = keltner_macd_strategy.analyze(candles, current_price)
        
        # Get indicator values for display
        indicators = keltner_macd_strategy.get_indicator_values(candles)
        
        if signal:
            return {
                "success": True,
                "signal": {
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "strategy": signal.strategy_name,
                    "timeframe": "5s",
                    "expiry_seconds": 5,
                    "confirmations": signal.confirmations,
                    "entry_price": signal.entry_price,
                    "timestamp": signal.timestamp.isoformat()
                },
                "indicators": indicators,
                "symbol": symbol
            }
        else:
            return {
                "success": True,
                "signal": None,
                "message": "No valid signal - conditions not met",
                "indicators": indicators,
                "symbol": symbol
            }
    
    except Exception as e:
        logger.error(f"Keltner-MACD 5s signal error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/keltner-macd-indicators")
async def get_keltner_macd_indicators(
    symbol: str = Query("EURUSD_OTC", description="Asset symbol")
):
    """
    Get current Keltner Channel and MACD indicator values
    """
    try:
        from high_accuracy_strategies import keltner_macd_strategy
        
        candles = []
        
        # Get candles from OANDA
        try:
            oanda_symbol = symbol.replace("_OTC", "").replace("/", "_")
            if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
            
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, granularity="S5", count=100)
            if oanda_df is not None and len(oanda_df) > 0:
                candles = oanda_df.to_dict('records')
        except:
            pass
        
        if len(candles) < 65:
            return {
                "success": False,
                "error": "Insufficient data"
            }
        
        indicators = keltner_macd_strategy.get_indicator_values(candles)
        
        return {
            "success": True,
            "symbol": symbol,
            "indicators": indicators,
            "settings": {
                "keltner": {
                    "ema_period": 20,
                    "atr_period": 60,
                    "multiplier": 4
                },
                "macd": {
                    "fast_period": 13,
                    "slow_period": 24,
                    "signal_period": 11
                }
            }
        }
    
    except Exception as e:
        logger.error(f"Keltner-MACD indicators error: {e}")
        return {"success": False, "error": str(e)}


# Legacy endpoints for compatibility
@router.get("/")



# =====================================================
# SIGNAL VALIDATION ENDPOINTS
# =====================================================

@router.get("/signals/statistics")
async def get_signal_statistics(
    timeframe: Optional[str] = Query(None, description="Filter by timeframe (5s, 1m, etc.)"),
    hours: int = Query(24, description="Look back period in hours")
):
    """
    Get signal validation statistics
    Shows win/loss rate, accuracy, etc.
    """
    try:
        stats = await signal_validator.get_signal_statistics(timeframe=timeframe, hours=hours)
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting signal statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/signals/validations/recent")
async def get_recent_validations(limit: int = Query(20, description="Number of results")):
    """
    Get recent signal validation results
    """
    try:
        validations = await signal_validator.get_recent_validations(limit=limit)
        return {
            "success": True,
            "count": len(validations),
            "validations": validations
        }
    except Exception as e:
        logger.error(f"Error getting recent validations: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/signals/{signal_id}/validate")
async def manually_validate_signal(signal_id: str):
    """
    Manually trigger validation for a specific signal
    """
    try:
        # Fetch signal from database
        signal = await db.trading_signals.find_one({'id': signal_id}, {'_id': 0})
        
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Validate the signal
        result = await signal_validator.validate_signal(signal)
        
        if result:
            return {
                "success": True,
                "validation": result
            }
        else:
            return {
                "success": False,
                "message": "Could not validate signal - insufficient data"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error manually validating signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== HIGH ACCURACY SIGNAL GENERATION ====================

@router.post("/signals/high-accuracy/generate")
async def generate_high_accuracy_signal(
    symbol: str = Query("EURUSD", description="Trading symbol"),
    expiry: int = Query(None, description="Preferred expiry in seconds (5, 15, 30, 60)"),
    use_pocket_option: bool = Query(True, description="Use Pocket Option real-time data if available")
):
    """
    Generate high-accuracy trading signal using advanced multi-confirmation strategies
    
    Strategies by expiry:
    - 5s: Ultra Scalping (RSI + BB + MACD + Price Patterns)
    - 15s: Momentum Breakout (S/R Breakout + Volume + Momentum)
    - 30s: Mean Reversion (Extreme RSI + Stochastic + BB)
    - 60s: Trend Confirmation (EMA Alignment + ADX + Pullbacks)
    
    Returns signal only if confidence >= 65% with 4+ confirmations
    """
    try:
        candles = []
        current_price = 0
        
        # Try Pocket Option data first
        if use_pocket_option and po_market_data.connection and po_market_data.connection.state.connected:
            po_symbol = symbol.upper().replace("_", "")
            market_data = po_market_data.get_market_data(po_symbol)
            
            if market_data:
                current_price = market_data.current_price
                
                # Get candles from PO
                if po_symbol in po_market_data.candle_history:
                    if "1m" in po_market_data.candle_history[po_symbol]:
                        candles = [c.to_dict() for c in po_market_data.candle_history[po_symbol]["1m"]]
        
        # Fallback to OANDA if no PO data
        if not candles or not current_price:
            oanda_symbol = symbol if "_" in symbol else f"{symbol[:3]}_{symbol[3:]}" if len(symbol) == 6 else symbol
            try:
                # Use the OANDA service to fetch candles - returns DataFrame
                oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 100)
                
                if oanda_df is not None and not oanda_df.empty:
                    # Convert DataFrame to list of dicts
                    candles = oanda_df.reset_index().to_dict('records')
                    # Ensure proper column names
                    for c in candles:
                        if 'timestamp' not in c and oanda_df.index.name == 'timestamp':
                            pass  # index was reset, timestamp should be in dict
                    
                    if candles:
                        last_candle = candles[-1]
                        current_price = float(last_candle.get("close", 0))
            except Exception as e:
                logger.debug(f"OANDA candle fetch error: {e}")
        
        if not candles or not current_price:
            return {
                "success": False,
                "message": "No market data available. Connect to Pocket Option or ensure OANDA is configured."
            }
        
        # Generate high-accuracy signal
        signal = get_high_accuracy_signal(candles, current_price, expiry)
        
        if signal:
            # Save to database
            signal_doc = {
                "id": f"HA_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{symbol}",
                "symbol": symbol,
                "direction": signal["direction"],
                "confidence": signal["confidence"],
                "probability": signal["confidence"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "expiration_minutes": signal["expiry_seconds"] / 60,
                "strategy": signal["strategy_name"],
                "confirmations": signal["confirmations"],
                "confirmations_count": signal["confirmations_count"],
                "market_condition": signal["market_condition"],
                "entry_price": signal["entry_price"],
                "strength": signal["strength"],
                "is_high_probability": signal["is_high_probability"],
                "source": "high_accuracy_generator"
            }
            
            await db.trading_signals.insert_one({**signal_doc})
            
            return {
                "success": True,
                "signal": signal,
                "message": f"High accuracy {signal['direction']} signal generated with {signal['confirmations_count']} confirmations"
            }
        else:
            return {
                "success": False,
                "message": "No high-probability setup found. Waiting for better conditions.",
                "signal": None
            }
            
    except Exception as e:
        logger.error(f"High accuracy signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/high-accuracy/performance")
async def get_high_accuracy_performance():
    """
    Get performance statistics for high-accuracy strategies
    """
    try:
        performance = high_accuracy_generator.get_performance()
        
        return {
            "success": True,
            "strategies": performance,
            "total_signals_generated": len(high_accuracy_generator.signal_history)
        }
    except Exception as e:
        logger.error(f"Performance stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/signals/high-accuracy/record-result")
async def record_high_accuracy_result(
    signal_timestamp: str,
    won: bool
):
    """
    Record trade result for high-accuracy strategy performance tracking
    """
    try:
        high_accuracy_generator.record_result(signal_timestamp, won)
        
        return {
            "success": True,
            "message": f"Result recorded: {'WIN' if won else 'LOSS'}"
        }
    except Exception as e:
        logger.error(f"Record result error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/high-accuracy/strategies")
async def get_high_accuracy_strategies():
    """
    Get list of available high-accuracy strategies with descriptions
    """
    return {
        "success": True,
        "strategies": [
            {
                "id": "ultra_scalper",
                "name": "Ultra Scalper",
                "description": "Aggressive scalping strategy for 5-15s timeframes",
                "timeframes": ["5s", "15s"],
                "target_accuracy": "85%+"
            },
            {
                "id": "micro_trend",
                "name": "Micro Trend",
                "description": "Micro trend following for 30s-1m timeframes",
                "timeframes": ["30s", "1m"],
                "target_accuracy": "80%+"
            },
            {
                "id": "reversal_hunter",
                "name": "Reversal Hunter",
                "description": "Mean reversion strategy for overbought/oversold conditions",
                "timeframes": ["15s", "30s", "1m"],
                "target_accuracy": "82%+"
            },
            {
                "id": "momentum_burst",
                "name": "Momentum Burst",
                "description": "Captures strong momentum moves",
                "timeframes": ["5s", "15s", "30s"],
                "target_accuracy": "78%+"
            },
            {
                "id": "deep_confluence",
                "name": "Deep Confluence Analysis",
                "description": "Multi-indicator confluence with divergence detection, support/resistance, and pattern recognition",
                "timeframes": ["30s", "1m", "2m", "5m"],
                "target_accuracy": "75-85%",
                "features": ["RSI/MACD Divergence", "Support/Resistance", "Candlestick Patterns", "Volume Confirmation"]
            }
        ]
    }




@router.get("/signals/deep-analysis")
async def get_deep_analysis_signal_endpoint(
    symbol: str = Query("EUR_USD", description="Trading symbol"),
    expiry: int = Query(60, ge=5, le=300, description="Expiry in seconds")
):
    """
    Generate a deep market analysis signal with:
    - Multi-indicator confluence (4+ confirmations required)
    - RSI/MACD divergence detection
    - Support/Resistance levels
    - Candlestick pattern recognition
    - Volume confirmation
    - Market structure analysis
    """
    try:
        # Normalize symbol for OANDA
        oanda_symbol = symbol.replace('_OTC', '').replace('OTC', '')
        if '_' not in oanda_symbol and len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
        
        # Get candles from OANDA (need more for deep analysis)
        candles = []
        current_price = 0
        
        try:
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 100)
            if oanda_df is not None and not oanda_df.empty:
                candles = oanda_df.reset_index().to_dict('records')
                if candles:
                    current_price = float(candles[-1].get("close", 0))
        except Exception as e:
            logger.error(f"OANDA fetch error for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Data fetch error: {e}")
        
        if not candles or not current_price:
            raise HTTPException(status_code=404, detail="No market data available")
        
        # Generate deep analysis signal
        signal = get_deep_analysis_signal(candles, current_price, expiry)
        
        if signal:
            signal["symbol"] = symbol
            return {
                "success": True,
                "signal": signal,
                "analysis_type": "deep_confluence",
                "message": f"Signal generated with {signal.get('confirmations_count', 0)} confirmations"
            }
        else:
            return {
                "success": False,
                "signal": None,
                "message": "No high-confidence signal found. Market conditions may be unclear or lacking sufficient confirmations."
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deep analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/scan-markets-deep")
async def scan_markets_deep_analysis(
    assets: str = Query("EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC", description="Comma-separated list of assets to scan"),
    min_confidence: int = Query(70, ge=50, le=95, description="Minimum confidence threshold"),
    max_signals: int = Query(10, ge=1, le=20, description="Maximum number of signals to return"),
    preferred_expiry: int = Query(60, description="Preferred expiry in seconds")
):
    """
    Scan multiple markets using DEEP ANALYSIS for highest quality signals.
    
    Uses multi-indicator confluence, divergence detection, support/resistance,
    candlestick patterns, and volume confirmation.
    
    Returns only HIGH or PREMIUM quality signals.
    """
    try:
        asset_list = [a.strip() for a in assets.split(',') if a.strip()]
        signals_found = []
        
        for asset in asset_list:
            try:
                # Normalize asset symbol for OANDA
                oanda_symbol = asset.replace('_OTC', '').replace('OTC', '')
                if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                    oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
                
                # Get candles from OANDA
                candles = []
                current_price = 0
                
                try:
                    oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 100)
                    if oanda_df is not None and not oanda_df.empty:
                        candles = oanda_df.reset_index().to_dict('records')
                        if candles:
                            current_price = float(candles[-1].get("close", 0))
                except Exception as e:
                    logger.debug(f"OANDA fetch for {asset} failed: {e}")
                    continue
                
                if not candles or not current_price:
                    continue
                
                # Generate DEEP analysis signal
                signal = get_deep_analysis_signal(candles, current_price, preferred_expiry)
                
                if signal and signal.get("confidence", 0) >= min_confidence:
                    # Only include HIGH or PREMIUM quality signals
                    if signal.get("quality") in ["high", "premium"]:
                        signal["symbol"] = asset
                        signal["oanda_symbol"] = oanda_symbol
                        signals_found.append(signal)
                    
            except Exception as e:
                logger.debug(f"Deep scan error for {asset}: {e}")
                continue
        
        # Sort by confidence (highest first)
        signals_found.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        # Limit results
        top_signals = signals_found[:max_signals]
        
        # Apply premium filters
        for i, sig in enumerate(top_signals):
            symbol = sig.get("symbol", "")
            top_signals[i] = apply_premium_filters(sig, symbol)
        
        top_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        time_filter_info = get_time_filter()
        
        # === SIGNAL ROUTING: Route top signal through rules engine ===
        routing_result = None
        if top_signals:
            try:
                routing_result = await _route_and_dispatch(top_signals[0])
            except Exception as e:
                logger.warning(f"Signal routing failed (non-fatal): {e}")
        
        return {
            "success": True,
            "analysis_type": "deep_confluence",
            "scanned_assets": len(asset_list),
            "signals_found": len(signals_found),
            "top_signals": top_signals,
            "time_filter": time_filter_info,
            "routing": routing_result,
            "message": f"Found {len(signals_found)} high-quality signals above {min_confidence}% confidence"
        }
        
    except Exception as e:
        logger.error(f"Deep market scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/scan-markets")
async def scan_markets_for_signals(
    assets: str = Query("EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC", description="Comma-separated list of assets to scan"),
    min_confidence: int = Query(70, ge=50, le=95, description="Minimum confidence threshold"),
    max_signals: int = Query(10, ge=1, le=20, description="Maximum number of signals to return"),
    preferred_expiry: int = Query(None, description="Preferred expiry in seconds (5, 15, 30, 60). If not set, best strategy is auto-selected"),
    use_deep_analysis: bool = Query(True, description="Use deep market analysis for better accuracy (recommended)"),
    strategy_id: str = Query(None, description="Override: use specific strategy ID (e.g. ema20_pullback_reversal)")
):
    """
    Scan multiple markets for high-probability trading signals.
    
    Uses DEEP ANALYSIS by default for improved win rate:
    - Multi-indicator confluence (4+ confirmations)
    - RSI/MACD divergence detection
    - Support/Resistance levels
    - Candlestick pattern recognition
    - Volume confirmation
    
    Returns signals sorted by confidence (highest first).
    Each signal includes expiry_seconds for timeframe synchronization.
    """
    try:
        asset_list = [a.strip() for a in assets.split(',') if a.strip()]
        signals_found = []
        
        # Use preferred expiry or default to 60
        expiry_to_use = preferred_expiry if preferred_expiry in [5, 15, 30, 60, 120, 180, 300] else 60
        
        # Get session/time filter info upfront
        time_filter_info = get_time_filter()
        
        # Resolve active strategy: param > user selection > default
        active_strategy_id = strategy_id
        if not active_strategy_id:
            try:
                from strategy_selection_service import strategy_selection_service
                selections = await strategy_selection_service.get_selected_strategies()
                # Match expiry to timeframe
                timeframe_map = {5: '5s', 15: '15s', 30: '30s', 60: '1m', 120: '2m', 180: '3m', 300: '5m'}
                tf_key = timeframe_map.get(expiry_to_use, '5s')
                active_strategy_id = selections.get(tf_key, 'default')
            except Exception:
                active_strategy_id = 'default'
        
        for asset in asset_list:
            try:
                # Normalize asset symbol for OANDA
                oanda_symbol = asset.replace('_OTC', '').replace('OTC', '')
                if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                    oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
                
                # Get candles from OANDA
                candles = []
                current_price = 0
                
                try:
                    oanda_df = enhanced_oanda.get_candles(oanda_symbol, "M1", 100)
                    if oanda_df is not None and not oanda_df.empty:
                        candles = oanda_df.reset_index().to_dict('records')
                        if candles:
                            current_price = float(candles[-1].get("close", 0))
                except Exception as e:
                    logger.debug(f"OANDA fetch for {asset} failed: {e}")
                    continue
                
                if not candles or not current_price:
                    continue
                
                # PRIORITY: If user selected a specific strategy, try it FIRST
                if active_strategy_id and active_strategy_id != 'default':
                    try:
                        from strategy_registry import strategy_registry
                        registry_key_map = {
                            'ema20_pullback_reversal': '5s_ema20_pullback_reversal',
                            'holly_crossover_5s': None,
                            'turbo_precision_5s': 'turbo_precision_5s',
                            'keltner_breakout': None,
                            'golden_one_moment': None,
                            'momentum_buster_15s': None,
                        }
                        registry_key = registry_key_map.get(active_strategy_id, active_strategy_id)
                        if registry_key:
                            strat = strategy_registry.get_strategy(registry_key)
                            if strat:
                                oanda_df_for_strat = pd.DataFrame(candles)
                                for col in ['open', 'high', 'low', 'close']:
                                    if col in oanda_df_for_strat.columns:
                                        oanda_df_for_strat[col] = pd.to_numeric(oanda_df_for_strat[col], errors='coerce')
                                strat_signal = strat.generate_signal(oanda_df_for_strat)
                                if strat_signal and strat_signal.get("confidence", 0) >= min_confidence and strat_signal.get("direction", "NEUTRAL") != "NEUTRAL":
                                    strat_signal["symbol"] = asset
                                    strat_signal["oanda_symbol"] = oanda_symbol
                                    strat_signal["expiry_seconds"] = expiry_to_use
                                    strat_signal["analysis_type"] = f"selected_{active_strategy_id}"
                                    for k, v in strat_signal.get("indicators", {}).items():
                                        if hasattr(v, 'item'):
                                            strat_signal["indicators"][k] = float(v)
                                    signals_found.append(strat_signal)
                                    continue
                    except Exception as e:
                        logger.debug(f"Selected strategy {active_strategy_id} failed for {asset}: {e}")
                
                # Use DEEP ANALYSIS for better accuracy (default)
                if use_deep_analysis:
                    signal = get_deep_analysis_signal(candles, current_price, expiry_to_use)
                    
                    # Try ML system for cross-validation (Stacking Ensemble)
                    ml_agrees = False
                    ml_confidence = 0
                    try:
                        from maximized_ai_ml_system import maximized_ai_ml
                        if maximized_ai_ml and maximized_ai_ml.is_trained:
                            ml_df = pd.DataFrame(candles)
                            for col in ['open', 'high', 'low', 'close']:
                                if col in ml_df.columns:
                                    ml_df[col] = pd.to_numeric(ml_df[col], errors='coerce')
                            ml_pred = maximized_ai_ml.predict(ml_df)
                            if ml_pred:
                                ml_confidence = ml_pred.get('confidence', 0)
                                ml_direction = ml_pred.get('direction', '')
                                if signal and ml_direction == signal.get('direction', ''):
                                    ml_agrees = True
                    except Exception:
                        pass
                    
                    # Advanced ML Ensemble Validation (LSTM/GRU + PPO)
                    advanced_ml = get_advanced_ml_ensemble_validation(candles, signal)
                    
                    if signal and signal.get("confidence", 0) >= min_confidence:
                        quality = signal.get("quality", "low")
                        # Include all qualities that meet confidence threshold (including low)
                        if quality in ["high", "premium", "medium", "low"]:
                            # ML confluence bonus: boost confidence when systems agree
                            total_ml_agreements = 0
                            
                            # Stacking ensemble agreement
                            if ml_agrees and ml_confidence >= 70:
                                signal["confidence"] = min(95, signal["confidence"] + 5)
                                signal["ml_validated"] = True
                                signal["ml_confidence"] = ml_confidence
                                total_ml_agreements += 1
                            elif ml_agrees:
                                signal["ml_validated"] = True
                                signal["ml_confidence"] = ml_confidence
                            else:
                                signal["ml_validated"] = False
                            
                            # Advanced ML (LSTM/GRU + PPO) agreement bonus
                            if advanced_ml.get("models_agreeing", 0) > 0:
                                signal["advanced_ml_validation"] = {
                                    "models_checked": advanced_ml.get("models_checked", 0),
                                    "models_agreeing": advanced_ml.get("models_agreeing", 0),
                                    "ensemble_direction": advanced_ml.get("ensemble_direction"),
                                    "average_confidence": advanced_ml.get("average_confidence", 0)
                                }
                                total_ml_agreements += advanced_ml.get("models_agreeing", 0)
                                
                                # Extra confidence boost for multi-model agreement
                                if advanced_ml.get("models_agreeing", 0) >= 2:
                                    signal["confidence"] = min(95, signal["confidence"] + 3)
                                elif advanced_ml.get("models_agreeing", 0) >= 1:
                                    signal["confidence"] = min(95, signal["confidence"] + 1)
                            
                            signal["total_ml_agreements"] = total_ml_agreements
                            signal["symbol"] = asset
                            signal["oanda_symbol"] = oanda_symbol
                            signal["expiry_seconds"] = expiry_to_use
                            signal["analysis_type"] = "deep_confluence"
                            signals_found.append(signal)
                            continue
                    
                    # Fallback: Try Holly Crossover strategy
                    try:
                        from strategies.strategy_holly_crossover import holly_crossover_5s
                        candle_dicts = [{'open': float(c.get('open', c.get('Open', 0))),
                                        'high': float(c.get('high', c.get('High', 0))),
                                        'low': float(c.get('low', c.get('Low', 0))),
                                        'close': float(c.get('close', c.get('Close', 0)))}
                                       for c in candles]
                        hc_signal = holly_crossover_5s.generate_signal(candle_dicts)
                        if hc_signal and hc_signal.get("confidence", 0) >= min_confidence:
                            hc_signal["symbol"] = asset
                            hc_signal["oanda_symbol"] = oanda_symbol
                            hc_signal["expiry_seconds"] = 5
                            hc_signal["analysis_type"] = "holly_crossover"
                            signals_found.append(hc_signal)
                            continue
                    except Exception:
                        pass

                    # Fallback: Try Golden One Moment (30s) strategy
                    try:
                        from strategies.strategy_golden_one_moment import golden_one_moment
                        candle_dicts = [{'open': float(c.get('open', c.get('Open', 0))), 
                                        'high': float(c.get('high', c.get('High', 0))),
                                        'low': float(c.get('low', c.get('Low', 0))), 
                                        'close': float(c.get('close', c.get('Close', 0)))} 
                                       for c in candles]
                        gom_signal = golden_one_moment.generate_signal(candle_dicts)
                        if gom_signal and gom_signal.get("confidence", 0) >= min_confidence:
                            gom_signal["symbol"] = asset
                            gom_signal["oanda_symbol"] = oanda_symbol
                            gom_signal["expiry_seconds"] = 30
                            gom_signal["analysis_type"] = "golden_one_moment"
                            # Cast numpy types
                            for k, v in gom_signal.get("indicators", {}).items():
                                if hasattr(v, 'item'):
                                    gom_signal["indicators"][k] = float(v)
                            signals_found.append(gom_signal)
                            continue
                    except Exception:
                        pass
                    
                    # Fallback: Try Momentum Buster (15s) strategy
                    try:
                        from strategies.strategy_momentum_buster_15s import momentum_buster_15s
                        candle_dicts = [{'open': float(c.get('open', c.get('Open', 0))), 
                                        'high': float(c.get('high', c.get('High', 0))),
                                        'low': float(c.get('low', c.get('Low', 0))), 
                                        'close': float(c.get('close', c.get('Close', 0)))} 
                                       for c in candles]
                        mb_signal = momentum_buster_15s.generate_signal(candle_dicts)
                        if mb_signal and mb_signal.get("confidence", 0) >= min_confidence:
                            mb_signal["symbol"] = asset
                            mb_signal["oanda_symbol"] = oanda_symbol
                            mb_signal["expiry_seconds"] = 15
                            mb_signal["analysis_type"] = "momentum_buster_15s"
                            signals_found.append(mb_signal)
                            continue
                    except Exception:
                        pass

                    # Fallback: Try IQ-720 Ensemble strategy (advanced multi-indicator)
                    try:
                        iq720_signal = generate_iq720_signal(candles)
                        if iq720_signal and iq720_signal.get("confidence", 0) >= min_confidence:
                            iq720_signal["symbol"] = asset
                            iq720_signal["oanda_symbol"] = oanda_symbol
                            iq720_signal["expiry_seconds"] = iq720_signal.get("expiry", 5)
                            iq720_signal["analysis_type"] = "iq720_ensemble"
                            signals_found.append(_convert_numpy_types(iq720_signal))
                            continue
                    except Exception:
                        pass
                else:
                    # Fallback to old high-accuracy signal
                    signal = get_high_accuracy_signal(candles, current_price, expiry=expiry_to_use)
                    
                    if signal and signal.get("confidence", 0) >= min_confidence:
                        signal["symbol"] = asset
                        signal["oanda_symbol"] = oanda_symbol
                        if "expiry_seconds" not in signal:
                            signal["expiry_seconds"] = expiry_to_use
                        signal["analysis_type"] = "high_accuracy"
                        signals_found.append(signal)
                    
            except Exception as e:
                logger.debug(f"Scan error for {asset}: {e}")
                continue
        
        # Sort by confidence (highest first)
        signals_found.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        # Limit results
        top_signals = signals_found[:max_signals]
        
        # Apply premium filters to top signals
        for i, sig in enumerate(top_signals):
            symbol = sig.get("symbol", "")
            top_signals[i] = apply_premium_filters(sig, symbol)
        
        # Re-sort after premium adjustments
        top_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        # === SIGNAL ROUTING: Route top signal through rules engine ===
        routing_result = None
        if top_signals:
            try:
                routing_result = await _route_and_dispatch(top_signals[0])
            except Exception as e:
                logger.warning(f"Signal routing failed (non-fatal): {e}")
        
        return {
            "success": True,
            "analysis_type": "deep_confluence" if use_deep_analysis else "high_accuracy",
            "active_strategy": active_strategy_id,
            "scanned_assets": len(asset_list),
            "signals_found": len(signals_found),
            "top_signals": top_signals,
            "preferred_expiry": expiry_to_use,
            "time_filter": time_filter_info,
            "routing": routing_result,
            "message": f"Found {len(signals_found)} signals above {min_confidence}% confidence"
        }
        
    except Exception as e:
        logger.error(f"Market scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== ADVANCED SIGNAL GENERATOR ENDPOINTS ====================

@router.post("/signals/advanced/generate")
async def generate_advanced_signal(
    asset: str,
    timeframe: int = 60,
    strategy: str = 'ENSEMBLE',
    invert_signals: bool = None
):
    """
    Generate signal using advanced strategies from top-performing bots
    
    Args:
        asset: Asset symbol
        timeframe: Timeframe in seconds  
        strategy: Strategy type ('TREND_MOMENTUM', 'VOLATILITY', 'ML', 'MULTI', 'ENSEMBLE')
        invert_signals: Invert signal direction (optional, uses config if not provided)
    
    Returns:
        Advanced signal with multiple strategy analysis
    """
    try:
        # Get invert_signals from config if not provided
        if invert_signals is None:
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            invert_signals = config_doc.get('invert_signals', False) if config_doc else False
        
        # Try PocketOptionV2 first (if connected)
        client = await get_pocket_option_v2_client()
        
        if not client or not client.is_connected():
            # Fallback to realtime market data hub
            candles = await get_realtime_market_hub().get_historical_candles(
                asset.replace('_otc', '').replace('_regular', ''),
                interval='1m',
                limit=200
            )
        else:
            # Get candles from Pocket Option
            candles = await client.get_candles(asset, timeframe, 200)
        
        if not candles:
            raise HTTPException(status_code=404, detail="No candle data available")
        
        # Generate signal with advanced strategies
        signal = advanced_signal_generator.generate_signal(candles, strategy, invert_signals)
        
        return {
            "success": True,
            "asset": asset,
            "timeframe": timeframe,
            **signal
        }
        
    except Exception as e:
        logger.error(f"Error generating advanced signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/signals/advanced/strategies")
async def get_available_strategies():
    """Get list of available advanced strategies"""
    return {
        "success": True,
        "strategies": [
            {
                "name": "TREND_MOMENTUM",
                "description": "Trend-following with momentum confirmation",
                "win_rate": "68%",
                "indicators": ["200 EMA", "MACD", "RSI"]
            },
            {
                "name": "VOLATILITY",
                "description": "Volatility breakout strategy",
                "win_rate": "65%",
                "indicators": ["Bollinger Bands", "ATR", "Volume"]
            },
            {
                "name": "ML",
                "description": "Machine Learning prediction using Random Forest",
                "win_rate": "60-70%",
                "indicators": ["EMA", "Awesome Oscillator", "PSAR", "CCI", "MACD"]
            },
            {
                "name": "MULTI",
                "description": "Multi-indicator combination with weighted scoring",
                "win_rate": "73%",
                "indicators": ["RSI", "MACD", "EMA", "Bollinger Bands", "ATR", "Volume"]
            },
            {
                "name": "ENSEMBLE",
                "description": "Combines all strategies with voting",
                "win_rate": "75-80%",
                "indicators": ["All of the above"]
            }
        ]
    }




@router.post("/signals/advanced/backtest")
async def backtest_strategy(
    asset: str,
    strategy: str,
    timeframe: int = 60,
    candles: int = 500
):
    """
    Backtest a strategy on historical data
    
    Args:
        asset: Asset symbol
        strategy: Strategy to backtest
        timeframe: Timeframe in seconds
        candles: Number of historical candles to test on
    
    Returns:
        Backtest results with win rate and performance metrics
    """
    try:
        # Get historical candles
        client = await get_pocket_option_v2_client()
        
        if not client or not client.is_connected():
            historical_candles = await get_realtime_market_hub().get_historical_candles(
                asset.replace('_otc', '').replace('_regular', ''),
                interval='1m',
                limit=candles
            )
        else:
            historical_candles = await client.get_candles(asset, timeframe, candles)
        
        if not historical_candles or len(historical_candles) < 100:
            raise HTTPException(status_code=404, detail="Insufficient historical data")
        
        # Run backtest
        wins = 0
        losses = 0
        signals = []
        
        # Test on sliding windows
        for i in range(100, len(historical_candles) - 1, 10):  # Every 10 candles
            test_candles = historical_candles[max(0, i-100):i]
            signal = advanced_signal_generator.generate_signal(test_candles, strategy)
            
            if signal['direction'] != 'NEUTRAL':
                # Check if signal was correct
                actual_direction = 'CALL' if historical_candles[i]['close'] < historical_candles[i+1]['close'] else 'PUT'
                
                if signal['direction'] == actual_direction:
                    wins += 1
                else:
                    losses += 1
                
                signals.append({
                    'index': i,
                    'predicted': signal['direction'],
                    'actual': actual_direction,
                    'confidence': signal['confidence'],
                    'correct': signal['direction'] == actual_direction
                })
        
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        
        return {
            "success": True,
            "asset": asset,
            "strategy": strategy,
            "backtest_results": {
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "sample_signals": signals[:10]  # First 10 signals as example
            }
        }
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ========== INTEGRATED SIGNAL + TELEGRAM FLOW ENDPOINTS ==========

@router.post("/signals/generate-and-notify")
async def generate_and_notify_signal(
    asset: str = Query(..., description="Asset symbol (e.g., EURUSD_OTC)"),
    timeframe: str = Query("5s", description="Timeframe (e.g., 5s, 1m)"),
    send_telegram: bool = Query(True, description="Send signal to Telegram")
):
    """
    Generate a trading signal and send to Telegram in one call
    Should generate a signal and send to Telegram (telegram_sent=true)
    """
    try:
        # Parse asset
        if '_' in asset:
            symbol, market_type = asset.rsplit('_', 1)
        else:
            symbol, market_type = asset, 'regular'
        
        logger.info(f"🚀 Generating signal for {asset} ({timeframe}) with Telegram: {send_telegram}")
        
        # Create market data object
        from trading_models import MarketData, AssetType
        market_data = MarketData(
            symbol=symbol,
            price=1.0500,  # Default price - will be fetched by strategy
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.FOREX,  # Will be determined by symbol
            volume=0
        )
        
        # Generate signal using force signal generator
        signals = await force_signal_generator.force_generate_signal(
            symbol=symbol,
            market_data=market_data,
            user_expirations=[timeframe],
            wait_for_candle=False  # Fast generation
        )
        
        telegram_sent = False
        
        if signals and len(signals) > 0:
            signal = signals[0]  # Get first signal
            
            # Store signal in database
            try:
                signal_dict = signal.dict() if hasattr(signal, 'dict') else signal
                signal_dict['timestamp'] = signal_dict['timestamp'].isoformat() if hasattr(signal_dict['timestamp'], 'isoformat') else signal_dict['timestamp']
                signal_dict['precision_entry_time'] = signal_dict['precision_entry_time'].isoformat() if signal_dict.get('precision_entry_time') and hasattr(signal_dict['precision_entry_time'], 'isoformat') else signal_dict.get('precision_entry_time')
                signal_dict = _convert_numpy_types(signal_dict)
                await db.trading_signals.insert_one(signal_dict)
                logger.info(f"Signal stored in database: {signal_dict.get('id')}")
            except Exception as e:
                logger.warning(f"Could not store signal in database: {e}")
            
            # Send to Telegram if requested
            if send_telegram:
                try:
                    telegram_notifier = get_telegram_notifier()
                    telegram_sent = await telegram_notifier.send_signal(signal_dict)
                    logger.info(f"Telegram notification {'sent' if telegram_sent else 'failed'}")
                except Exception as e:
                    logger.warning(f"Could not send Telegram notification: {e}")
                    telegram_sent = False
            
            return {
                "success": True,
                "message": f"Signal generated for {asset}",
                "signal": {
                    "id": str(signal_dict.get('id')),
                    "symbol": str(signal_dict.get('symbol')),
                    "direction": signal_dict.get('direction'),
                    "probability": float(signal_dict.get('probability', 0)),
                    "timeframe": str(signal_dict.get('timeframe')),
                    "market_type": str(signal_dict.get('market_type')),
                    "timestamp": signal_dict.get('timestamp')
                },
                "telegram_sent": telegram_sent
            }
        else:
            return {
                "success": False,
                "message": f"Could not generate signal for {asset}",
                "signal": None,
                "telegram_sent": False
            }
            
    except Exception as e:
        logger.error(f"Error in generate-and-notify: {e}")
        return {
            "success": False,
            "message": f"Error generating signal: {str(e)}",
            "signal": None,
            "telegram_sent": False
        }



@router.post("/signals/auto/start")
async def start_auto_signal_generation(
    instruments: str = Query("EUR_USD", description="Comma-separated instruments"),
    timeframe: str = Query("M1", description="Timeframe for analysis"),
    interval_seconds: int = Query(15, ge=10, le=300, description="Interval between signal checks (default 15s)"),
    min_confidence: int = Query(70, ge=50, le=95, description="Minimum confidence to generate signal")
):
    """
    Start automatic signal generation in the background.
    Signals will be continuously generated and available for the auto-trader.
    """
    global auto_signal_state
    
    if auto_signal_state["enabled"]:
        return {"success": False, "message": "Auto signal generator already running"}
    
    if not enhanced_oanda.is_configured:
        return {"success": False, "message": "OANDA not configured"}
    
    # Configure
    auto_signal_state["enabled"] = True
    auto_signal_state["instruments"] = [i.strip() for i in instruments.split(",")]
    auto_signal_state["timeframe"] = timeframe
    auto_signal_state["interval_seconds"] = interval_seconds
    auto_signal_state["min_confidence"] = min_confidence
    
    # Start background task
    auto_signal_state["task"] = asyncio.create_task(auto_signal_generator_task())
    
    return {
        "success": True,
        "message": "Auto signal generator started",
        "config": {
            "instruments": auto_signal_state["instruments"],
            "timeframe": timeframe,
            "interval_seconds": interval_seconds,
            "min_confidence": min_confidence
        }
    }



@router.post("/signals/auto/stop")
async def stop_auto_signal_generation():
    """Stop automatic signal generation"""
    global auto_signal_state
    
    auto_signal_state["enabled"] = False
    
    if auto_signal_state["task"]:
        auto_signal_state["task"].cancel()
        auto_signal_state["task"] = None
    
    return {
        "success": True,
        "message": "Auto signal generator stopped",
        "stats": {
            "signals_generated": auto_signal_state["signals_generated"],
            "last_signal_time": auto_signal_state["last_signal_time"]
        }
    }



@router.get("/signals/auto/status")
async def get_auto_signal_status():
    """Get auto signal generator status"""
    global auto_signal_state
    
    return {
        "enabled": auto_signal_state["enabled"],
        "instruments": auto_signal_state["instruments"],
        "timeframe": auto_signal_state["timeframe"],
        "interval_seconds": auto_signal_state["interval_seconds"],
        "min_confidence": auto_signal_state["min_confidence"],
        "signals_generated": auto_signal_state["signals_generated"],
        "last_signal_time": auto_signal_state["last_signal_time"]
    }




# ========================================
# COMBINED AI + OANDA SIGNAL GENERATION
# ========================================

@router.post("/signals/generate-enhanced")
async def generate_enhanced_signal(
    instrument: str = "EUR_USD",
    timeframe: str = "M1",
    use_custom_strategy: bool = False,
    strategy_id: Optional[str] = None
):
    """
    Generate enhanced trading signal combining:
    - OANDA real-time data with technical indicators
    - AI/ML ensemble predictions
    - Custom strategy (optional)
    
    Returns comprehensive signal with high confidence.
    """
    try:
        result = {
            "success": True,
            "instrument": instrument,
            "timeframe": timeframe,
            "signals": {},
            "final_recommendation": None,
            "confidence": 0
        }
        
        # 1. Get trend signal from enhanced OANDA service
        trend_signal = enhanced_oanda.generate_trend_signal(instrument, timeframe)
        if trend_signal:
            result["signals"]["trend_analysis"] = trend_signal.to_dict()
        
        # 2. Get AI ensemble signal
        if oanda_service.is_configured:
            candles = await oanda_service.get_candles(instrument, timeframe, count=100)
            if candles:
                import numpy as np
                ohlcv_data = {
                    "open": np.array([c.open for c in candles]),
                    "high": np.array([c.high for c in candles]),
                    "low": np.array([c.low for c in candles]),
                    "close": np.array([c.close for c in candles]),
                    "volume": np.array([c.volume for c in candles])
                }
                
                # Load custom strategy if requested
                custom_strategy = None
                if use_custom_strategy and strategy_id:
                    strategy_doc = await db.custom_strategies.find_one({"id": strategy_id})
                    if strategy_doc:
                        custom_strategy = {
                            "name": strategy_doc.get("name"),
                            "conditions": strategy_doc.get("conditions", [])
                        }
                
                ai_signal = await enhanced_ai_system.generate_signal(ohlcv_data, custom_strategy)
                if ai_signal:
                    result["signals"]["ai_ensemble"] = _convert_numpy_types(ai_signal.to_dict())
        
        # 3. Combine signals for final recommendation
        call_votes = 0
        put_votes = 0
        total_confidence = 0
        vote_count = 0
        
        if trend_signal:
            vote_count += 1
            total_confidence += trend_signal.confidence
            if trend_signal.recommended_action == "CALL":
                call_votes += trend_signal.confidence
            elif trend_signal.recommended_action == "PUT":
                put_votes += trend_signal.confidence
        
        if "ai_ensemble" in result["signals"]:
            ai_data = result["signals"]["ai_ensemble"]
            vote_count += 1
            total_confidence += ai_data.get("final_confidence", 0)
            if ai_data.get("final_direction") == "CALL":
                call_votes += ai_data.get("final_confidence", 0)
            elif ai_data.get("final_direction") == "PUT":
                put_votes += ai_data.get("final_confidence", 0)
        
        # Determine final recommendation
        if vote_count > 0:
            avg_confidence = total_confidence / vote_count
            
            if call_votes > put_votes:
                result["final_recommendation"] = "CALL"
                result["confidence"] = (call_votes / (call_votes + put_votes)) * 100 if (call_votes + put_votes) > 0 else 0
            elif put_votes > call_votes:
                result["final_recommendation"] = "PUT"
                result["confidence"] = (put_votes / (call_votes + put_votes)) * 100 if (call_votes + put_votes) > 0 else 0
            else:
                result["final_recommendation"] = "HOLD"
                result["confidence"] = 50
            
            # Risk assessment
            if result["confidence"] >= 75:
                result["risk_level"] = "LOW"
            elif result["confidence"] >= 60:
                result["risk_level"] = "MEDIUM"
            else:
                result["risk_level"] = "HIGH"
        
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        
        return result
        
    except Exception as e:
        logger.error(f"Enhanced signal generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== PREMIUM SIGNAL FILTER ENDPOINTS ====================

@router.get("/signals/session-info")
async def get_session_info(symbol: str = Query(None, description="Optional symbol to check session compatibility")):
    """
    Get current trading session information including quality score,
    recommended pairs, and time-based trading recommendation.
    """
    try:
        time_filter = get_time_filter(symbol)
        session_info = session_analyzer.get_session_info()
        
        return {
            "success": True,
            "time_filter": time_filter,
            "session_details": {
                "session": session_info.session.value,
                "is_active": session_info.is_active,
                "quality_score": session_info.quality_score,
                "recommended_pairs": session_info.recommended_pairs,
                "avoid_pairs": session_info.avoid_pairs,
                "notes": session_info.notes
            }
        }
    except Exception as e:
        logger.error(f"Session info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/best-hours")
async def get_best_trading_hours(top_n: int = Query(8, ge=1, le=24)):
    """Get the best hours to trade based on historical win rate data."""
    try:
        best = session_analyzer.get_best_hours(top_n)
        avoid = session_analyzer.get_hours_to_avoid()
        
        return {
            "success": True,
            "best_hours": best,
            "hours_to_avoid": avoid,
            "total_hours_tracked": len(session_analyzer.hourly_performance),
            "note": "Hours are in UTC. Best hours require minimum 10 trades recorded."
        }
    except Exception as e:
        logger.error(f"Best hours error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/hourly-stats")
async def get_hourly_stats():
    """Get win rate statistics broken down by hour (UTC)."""
    try:
        stats = []
        for hour in range(24):
            data = session_analyzer.hourly_performance.get(hour, {})
            total = data.get("total", 0)
            wins = data.get("wins", 0)
            session = session_analyzer.get_current_session(hour)
            quality = session_analyzer.SESSION_QUALITY.get(session, 50)
            
            stats.append({
                "hour_utc": hour,
                "session": session.value,
                "session_quality": quality,
                "total_trades": total,
                "wins": wins,
                "win_rate": round(wins / total * 100, 1) if total > 0 else None,
                "is_best_hour": hour in session_analyzer.BEST_HOURS_UTC,
                "is_bad_hour": hour in session_analyzer.BAD_HOURS_UTC
            })
        
        return {
            "success": True,
            "hourly_stats": stats
        }
    except Exception as e:
        logger.error(f"Hourly stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TradeResultRequest(BaseModel):
    symbol: str
    direction: str  # CALL or PUT
    is_win: bool
    confidence: float = 0
    session: str = ""
    hour_utc: int = -1


@router.post("/signals/record-premium-result")
async def record_premium_trade_result(req: TradeResultRequest):
    """
    Record a trade result for premium signal tracking.
    Updates hourly stats and asset-level performance for future filtering.
    """
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        hour = req.hour_utc if req.hour_utc >= 0 else now.hour
        
        current_session = session_analyzer.get_current_session(hour)
        session_name = req.session if req.session else current_session.value
        
        # Record hourly stats
        session_analyzer.record_trade_result(hour, req.is_win)
        
        # Record asset-level stats
        asset_tracker.record_result(
            symbol=req.symbol,
            direction=req.direction,
            is_win=req.is_win,
            hour_utc=hour,
            session=session_name
        )
        
        # Get updated stats
        asset_wr = asset_tracker.get_asset_win_rate(req.symbol)
        hour_data = session_analyzer.hourly_performance.get(hour, {})
        
        return {
            "success": True,
            "recorded": {
                "symbol": req.symbol,
                "direction": req.direction,
                "is_win": req.is_win,
                "hour_utc": hour,
                "session": session_name
            },
            "updated_stats": {
                "asset_win_rate": asset_wr.get("win_rate", 50.0),
                "asset_total_trades": asset_wr.get("total", 0),
                "hour_win_rate": round(hour_data.get("win_rate", 50.0), 1),
                "hour_total_trades": hour_data.get("total", 0)
            }
        }
    except Exception as e:
        logger.error(f"Record premium result error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/asset-performance")
async def get_asset_performance(symbol: str = Query(None, description="Specific asset, or omit for all")):
    """Get performance statistics per asset, including hourly breakdown."""
    try:
        if symbol:
            asset_wr = asset_tracker.get_asset_win_rate(symbol)
            hourly = asset_tracker.get_asset_hour_performance(symbol)
            return {
                "success": True,
                "asset_stats": asset_wr,
                "hourly_breakdown": hourly
            }
        else:
            all_stats = asset_tracker.get_all_asset_stats()
            worst = asset_tracker.get_worst_assets()
            return {
                "success": True,
                "all_assets": all_stats,
                "worst_assets": worst,
                "total_tracked": len(all_stats)
            }
    except Exception as e:
        logger.error(f"Asset performance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/should-trade")
async def should_trade_check(
    symbol: str = Query(None, description="Symbol to check"),
    min_quality: float = Query(50.0, description="Minimum session quality to allow trading")
):
    """Quick endpoint to check if now is a good time to trade."""
    try:
        can_trade, reason = should_trade_now(symbol, min_quality)
        time_filter = get_time_filter(symbol)
        
        return {
            "success": True,
            "should_trade": can_trade,
            "reason": reason,
            "time_filter": time_filter
        }
    except Exception as e:
        logger.error(f"Should trade check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/signals/momentum-check")
async def momentum_check(symbol: str = "EURUSD_OTC", timeframe: str = "5s"):
    """
    Quick momentum/trend analysis for auto-invert decisions.
    Returns whether momentum has shifted (suggesting inversion) or trend is intact.
    Used by Tampermonkey script after a loss to decide whether to invert.
    """
    try:
        import numpy as np
        
        # Get recent candle data from DB
        db = router.app_state.get("db") if hasattr(router, 'app_state') else None
        if not db:
            from server import db as server_db
            db = server_db
        
        candles = []
        if db is not None:
            cursor = db.historical_candles.find(
                {"symbol": symbol.replace("_OTC", "").replace("_", "/")},
                {"_id": 0}
            ).sort("timestamp", -1).limit(50)
            candles = await cursor.to_list(50)
            candles.reverse()
        
        if len(candles) < 10:
            # Not enough data — return neutral (don't invert)
            return {
                "success": True,
                "should_invert": False,
                "momentum": "NEUTRAL",
                "trend": "UNKNOWN",
                "confidence": 0,
                "reason": "Insufficient candle data",
                "rsi": None,
                "ema_slope": None,
                "price_velocity": None,
            }
        
        closes = np.array([c.get("close", c.get("price", 0)) for c in candles], dtype=float)
        
        # Calculate RSI (14-period)
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        period = min(14, len(deltas) - 1)
        avg_gain = np.mean(gains[-period:]) if len(gains) >= period else 0
        avg_loss = np.mean(losses[-period:]) if len(losses) >= period else 0.0001
        rs = avg_gain / max(avg_loss, 0.0001)
        rsi = 100 - (100 / (1 + rs))
        
        # Calculate short EMA slope (5-period)
        def ema(data, period):
            alpha = 2 / (period + 1)
            result = [data[0]]
            for i in range(1, len(data)):
                result.append(alpha * data[i] + (1 - alpha) * result[-1])
            return result
        
        ema5 = ema(closes.tolist(), 5)
        ema20 = ema(closes.tolist(), 20)
        
        # EMA slope: positive = uptrend, negative = downtrend
        ema_slope_short = (ema5[-1] - ema5[-3]) / max(abs(ema5[-3]), 0.0001) * 100 if len(ema5) >= 3 else 0
        ema_slope_long = (ema20[-1] - ema20[-5]) / max(abs(ema20[-5]), 0.0001) * 100 if len(ema20) >= 5 else 0
        
        # Price velocity (rate of change over last 5 candles)
        price_velocity = (closes[-1] - closes[-5]) / max(abs(closes[-5]), 0.0001) * 100 if len(closes) >= 5 else 0
        
        # Determine trend
        if ema5[-1] > ema20[-1] and ema_slope_short > 0:
            trend = "BULLISH"
        elif ema5[-1] < ema20[-1] and ema_slope_short < 0:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"
        
        # Determine momentum shift
        # A momentum shift = RSI extreme + EMA slope reversal + price velocity change
        momentum_shifted = False
        invert_confidence = 0
        reasons = []
        
        # Check for pullback/reversal indicators
        if rsi > 70:
            reasons.append(f"RSI overbought ({rsi:.1f})")
            invert_confidence += 30
        elif rsi < 30:
            reasons.append(f"RSI oversold ({rsi:.1f})")
            invert_confidence += 30
        
        # EMA crossover or slope reversal
        if len(ema5) >= 2 and len(ema20) >= 2:
            prev_above = ema5[-2] > ema20[-2]
            curr_above = ema5[-1] > ema20[-1]
            if prev_above != curr_above:
                reasons.append("EMA 5/20 crossover detected")
                invert_confidence += 35
        
        # Sharp price velocity change (spike/reversal)
        if abs(price_velocity) > 0.1:  # > 0.1% move in 5 candles
            if (price_velocity > 0 and ema_slope_short < 0) or (price_velocity < 0 and ema_slope_short > 0):
                reasons.append(f"Price/EMA divergence (velocity={price_velocity:.3f}%)")
                invert_confidence += 25
        
        # Short-term slope reversal
        if abs(ema_slope_short) > 0.01:
            if (ema_slope_short > 0 and ema_slope_long < 0) or (ema_slope_short < 0 and ema_slope_long > 0):
                reasons.append("Short vs long EMA slope divergence")
                invert_confidence += 20
        
        should_invert = invert_confidence >= 50
        
        if should_invert:
            momentum = "SHIFTED"
        elif invert_confidence >= 30:
            momentum = "WEAKENING"
        else:
            momentum = "INTACT"
        
        return {
            "success": True,
            "should_invert": should_invert,
            "momentum": momentum,
            "trend": trend,
            "confidence": min(invert_confidence, 100),
            "reason": " | ".join(reasons) if reasons else "Trend intact, no inversion needed",
            "rsi": round(rsi, 1),
            "ema_slope": round(ema_slope_short, 4),
            "price_velocity": round(price_velocity, 4),
        }
    except Exception as e:
        logger.error(f"Momentum check error: {e}")
        return {
            "success": True,
            "should_invert": False,
            "momentum": "ERROR",
            "trend": "UNKNOWN",
            "confidence": 0,
            "reason": str(e),
            "rsi": None,
            "ema_slope": None,
            "price_velocity": None,
        }


@router.get("/signals/momentum-indicator")
async def momentum_indicator_analysis(
    symbol: str = "EURUSD_OTC",
    period: int = Query(14, ge=1, le=50, description="Momentum period"),
    threshold: float = Query(0, ge=-50, le=50, description="Signal threshold"),
    smoothing: int = Query(3, ge=1, le=20, description="EMA smoothing period")
):
    """
    Advanced momentum indicator analysis using configurable parameters.
    
    Returns:
    - momentum_value: Current smoothed momentum
    - momentum_slope: Rate of change of momentum (acceleration/deceleration)
    - signal: Trading signal (CALL/PUT/NEUTRAL) with confidence
    - conditions: List of met conditions for strategy integration
    """
    try:
        from high_accuracy_strategies import MomentumIndicator
        import numpy as np
        
        closes = None
        candle_count = 0
        
        # Try OANDA first (most reliable)
        try:
            oanda_symbol = symbol.replace("_OTC", "").replace("/", "_")
            # Ensure proper format (EURUSD -> EUR_USD)
            if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
            
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, granularity="S5", count=100)
            if oanda_df is not None and len(oanda_df) > 0:
                closes = oanda_df['close'] if 'close' in oanda_df.columns else oanda_df['Close']
                candle_count = len(closes)
        except Exception as e:
            logger.debug(f"OANDA fetch failed: {e}")
        
        # Fallback to DB historical candles
        if closes is None or len(closes) < period + smoothing + 5:
            db_ref = router.app_state.get("db") if hasattr(router, 'app_state') else None
            if not db_ref:
                from server import db as server_db
                db_ref = server_db
            
            if db_ref is not None:
                cursor = db_ref.historical_candles.find(
                    {"symbol": symbol.replace("_OTC", "").replace("_", "/")},
                    {"_id": 0}
                ).sort("timestamp", -1).limit(100)
                candles = await cursor.to_list(100)
                candles.reverse()
                
                if len(candles) >= period + smoothing + 5:
                    closes = pd.Series([float(c.get("close", c.get("Close", c.get("price", 0)))) for c in candles])
                    candle_count = len(closes)
        
        if closes is None or len(closes) < period + smoothing + 5:
            return {
                "success": False,
                "error": "Insufficient data",
                "candles_available": candle_count,
                "candles_required": period + smoothing + 5
            }
        
        # Ensure closes is a pandas Series
        if not isinstance(closes, pd.Series):
            closes = pd.Series(closes)
        
        # Initialize momentum indicator
        mom_indicator = MomentumIndicator(period=period, threshold=threshold, smoothing=smoothing)
        
        # Calculate momentum values
        result = mom_indicator.calculate(closes)
        if result is None:
            return {
                "success": False,
                "error": "Could not calculate momentum"
            }
        
        # Get trading signal
        signal = mom_indicator.get_signal(closes)
        
        # Check all conditions and return which are met
        conditions_status = {}
        condition_types = [
            'crosses_above_zero', 'crosses_below_zero',
            'strong_positive', 'strong_negative',
            'momentum_increasing', 'momentum_decreasing',
            'bullish_divergence', 'bearish_divergence'
        ]
        
        for cond in condition_types:
            met, boost, desc = mom_indicator.check_condition(closes, cond)
            conditions_status[cond] = {
                "met": bool(met),  # Convert numpy.bool to Python bool
                "confidence_boost": float(boost),
                "description": str(desc)
            }
        
        return {
            "success": True,
            "symbol": symbol,
            "candles_used": int(len(closes)),
            "parameters": {
                "period": int(period),
                "threshold": float(threshold),
                "smoothing": int(smoothing)
            },
            "momentum": {
                "raw": float(result['momentum']) if not np.isnan(result['momentum']) else 0.0,
                "smoothed": float(result['smoothed']) if not np.isnan(result['smoothed']) else 0.0,
                "slope": float(result['slope']) if not np.isnan(result['slope']) else 0.0,
                "previous": float(result['previous']) if not np.isnan(result['previous']) else 0.0
            },
            "signal": {
                "direction": str(signal['direction']) if signal else "NEUTRAL",
                "confidence": float(signal['confidence']) if signal else 0,
                "confirmations": list(signal['confirmations']) if signal else []
            } if signal else {"direction": "NEUTRAL", "confidence": 0, "confirmations": []},
            "conditions": conditions_status
        }
        
    except Exception as e:
        logger.error(f"Momentum indicator analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/signals/evaluate-momentum-condition")
async def evaluate_momentum_condition(
    symbol: str = Query(..., description="Asset symbol"),
    condition_type: str = Query(..., description="Condition type to check"),
    period: int = Query(14, ge=1, le=50),
    threshold: float = Query(0, ge=-50, le=50),
    smoothing: int = Query(3, ge=1, le=20)
):
    """
    Evaluate a specific momentum condition for Strategy Builder integration.
    
    Used when a custom strategy includes a MOMENTUM indicator condition.
    
    Condition types:
    - crosses_above_zero
    - crosses_below_zero
    - strong_positive
    - strong_negative
    - momentum_increasing
    - momentum_decreasing
    - bullish_divergence
    - bearish_divergence
    """
    try:
        from high_accuracy_strategies import MomentumIndicator
        
        closes = None
        
        # Try OANDA first
        try:
            oanda_symbol = symbol.replace("_OTC", "").replace("/", "_")
            if '_' not in oanda_symbol and len(oanda_symbol) == 6:
                oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"
            
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, granularity="S5", count=100)
            if oanda_df is not None and len(oanda_df) > 0:
                closes = oanda_df['close'] if 'close' in oanda_df.columns else oanda_df['Close']
        except Exception as e:
            logger.debug(f"OANDA fetch failed: {e}")
        
        # Fallback to DB
        if closes is None or len(closes) < period + smoothing + 5:
            db_ref = router.app_state.get("db") if hasattr(router, 'app_state') else None
            if not db_ref:
                from server import db as server_db
                db_ref = server_db
            
            if db_ref is not None:
                cursor = db_ref.historical_candles.find(
                    {"symbol": symbol.replace("_OTC", "").replace("_", "/")},
                    {"_id": 0}
                ).sort("timestamp", -1).limit(100)
                candles = await cursor.to_list(100)
                candles.reverse()
                
                if len(candles) >= period + smoothing + 5:
                    closes = pd.Series([float(c.get("close", c.get("Close", c.get("price", 0)))) for c in candles])
        
        if closes is None or len(closes) < period + smoothing + 5:
            return {
                "success": False,
                "condition_met": False,
                "error": "Insufficient data"
            }
        
        if not isinstance(closes, pd.Series):
            closes = pd.Series(closes)
        
        mom_indicator = MomentumIndicator(period=period, threshold=threshold, smoothing=smoothing)
        met, confidence_boost, description = mom_indicator.check_condition(closes, condition_type)
        
        return {
            "success": True,
            "symbol": str(symbol),
            "condition_type": str(condition_type),
            "condition_met": bool(met),  # Convert numpy.bool to Python bool
            "confidence_boost": float(confidence_boost),
            "description": str(description),
            "parameters": {
                "period": int(period),
                "threshold": float(threshold),
                "smoothing": int(smoothing)
            }
        }
        
    except Exception as e:
        logger.error(f"Momentum condition evaluation error: {e}")
        return {
            "success": False,
            "condition_met": False,
            "error": str(e)
        }


# =====================================================
# TIMING SYNC ENDPOINTS
# =====================================================

@router.get("/signals/timing-config")
async def get_timing_config():
    """
    Get recommended timing configuration for Tampermonkey script
    to sync with Pocket Option platform.
    """
    return {
        "success": True,
        "timing": {
            "bet_deduction_delay_ms": 2000,      # Wait for bet to be deducted
            "post_expiry_buffer_ms": 3000,       # Wait after expiry for balance update
            "balance_poll_interval_ms": 500,     # Balance polling frequency
            "balance_stability_checks": 2,        # Required stable readings
            "max_balance_polls": 20,              # Max polls before timeout
            "immediate_retry_delay_ms": 1500,     # Delay before inverted retry
            "trade_cooldown_ms": 5000,            # Min time between trades
        },
        "expiry_times": {
            "5s": {"total_wait": 8, "description": "5s trade + 3s buffer"},
            "15s": {"total_wait": 18, "description": "15s trade + 3s buffer"},
            "30s": {"total_wait": 33, "description": "30s trade + 3s buffer"},
            "60s": {"total_wait": 63, "description": "60s trade + 3s buffer"},
        },
        "server_time": datetime.now(timezone.utc).isoformat(),
        "recommendations": [
            "Use BET_DEDUCTION_DELAY of 2000ms - PO needs time to process the bet",
            "POST_EXPIRY_BUFFER of 3000ms handles PO's balance update delay",
            "Increase RESULT_LATENCY_OFFSET if results are being missed",
            "Decrease if detecting wrong trades"
        ]
    }


@router.post("/signals/sync-timing")
async def sync_timing(
    client_timestamp: float = Body(..., description="Client timestamp for latency calculation"),
    trade_expiry: int = Body(5, description="Trade expiry in seconds")
):
    """
    Sync timing between client and server.
    Returns recommended wait times adjusted for network latency.
    """
    try:
        server_time = datetime.now(timezone.utc).timestamp()
        latency_ms = (server_time * 1000) - client_timestamp
        
        # Calculate recommended timing based on latency
        base_buffer = 3000  # 3 seconds base buffer
        
        # Add extra buffer for high latency
        if latency_ms > 500:
            latency_adjustment = min(latency_ms, 2000)  # Cap at 2s extra
        else:
            latency_adjustment = 0
        
        total_buffer = base_buffer + latency_adjustment
        total_wait = (trade_expiry * 1000) + total_buffer
        
        return {
            "success": True,
            "sync": {
                "server_time": server_time,
                "client_time": client_timestamp / 1000,
                "latency_ms": round(latency_ms),
                "latency_adjustment_ms": round(latency_adjustment),
            },
            "recommended_timing": {
                "trade_expiry_ms": trade_expiry * 1000,
                "post_expiry_buffer_ms": total_buffer,
                "total_wait_ms": total_wait,
                "bet_deduction_delay_ms": 2000,
            },
            "message": f"With {round(latency_ms)}ms latency, wait {round(total_wait/1000)}s after trade for result"
        }
    
    except Exception as e:
        logger.error(f"Timing sync error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# IQ-720 ADVANCED STRATEGY ENDPOINTS
# ============================================================================

@router.post("/signals/iq720-ensemble")
async def generate_iq720_ensemble_signal(
    symbol: str = Body("EURUSD", description="Trading symbol"),
    timeframe: str = Body("M1", description="OANDA timeframe"),
    candle_count: int = Body(100, description="Number of candles to fetch")
):
    """
    Generate an IQ-720 inspired ensemble signal.
    
    Combines: Market Regime Detection + Session Awareness + 
    8 weighted technical sub-strategies + Confidence Calibration + 60+ features
    """
    try:
        oanda_symbol = symbol.replace('_OTC', '').replace('OTC', '')
        if '_' not in oanda_symbol and len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"

        candles = []
        try:
            oanda_df = enhanced_oanda.get_candles(oanda_symbol, timeframe, candle_count)
            if oanda_df is not None and not oanda_df.empty:
                candles = oanda_df.reset_index().to_dict('records')
        except Exception as e:
            logger.warning(f"OANDA fetch failed for IQ720: {e}")

        if len(candles) < 60:
            return {
                "success": False,
                "message": f"Insufficient data for IQ-720 analysis (need 60+, got {len(candles)})",
                "signal": None
            }

        signal = generate_iq720_signal(candles)

        if signal:
            signal["symbol"] = symbol
            
            # === SIGNAL ROUTING: Route IQ-720 signal through rules engine ===
            routing_result = None
            try:
                routing_result = await _route_and_dispatch(signal)
            except Exception as e:
                logger.warning(f"IQ-720 signal routing failed (non-fatal): {e}")
            
            return {
                "success": True,
                "signal": _convert_numpy_types(signal),
                "routing": routing_result,
                "message": f"IQ-720 Ensemble: {signal['direction']} with {signal['confidence']}% confidence"
            }
        else:
            return {
                "success": False,
                "message": "No IQ-720 signal — conditions not met (confidence below threshold or no clear direction)",
                "signal": None,
                "market_regime": iq720_generator.detect_market_regime(
                    pd.Series([float(c.get('close', c.get('Close', 0))) for c in candles]),
                    pd.Series([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles]),
                    pd.Series([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])
                ).value,
                "session": iq720_generator.get_current_session().value
            }

    except Exception as e:
        logger.error(f"IQ-720 ensemble error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/iq720-market-regime")
async def get_iq720_market_regime(
    symbol: str = Query("EURUSD", description="Trading symbol"),
    timeframe: str = Query("M1", description="OANDA timeframe")
):
    """
    Get current market regime detection from IQ-720 system.
    Returns: trending_up, trending_down, ranging, high_volatility, low_volatility, unknown
    """
    try:
        oanda_symbol = symbol.replace('_OTC', '').replace('OTC', '')
        if '_' not in oanda_symbol and len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"

        oanda_df = enhanced_oanda.get_candles(oanda_symbol, timeframe, 100)
        if oanda_df is None or oanda_df.empty:
            return {"success": False, "message": "No market data available", "regime": "unknown"}

        closes = pd.to_numeric(oanda_df['close'], errors='coerce')
        highs = pd.to_numeric(oanda_df['high'], errors='coerce') if 'high' in oanda_df else closes
        lows = pd.to_numeric(oanda_df['low'], errors='coerce') if 'low' in oanda_df else closes

        regime = iq720_generator.detect_market_regime(closes, highs, lows)
        session = iq720_generator.get_current_session()

        return {
            "success": True,
            "symbol": symbol,
            "regime": regime.value,
            "session": session.value,
            "session_weight": iq720_generator.session_weights.get(session, 1.0),
            "regime_adjustments": iq720_generator.regime_adjustments.get(regime, {}),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Market regime detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signals/iq720-kelly")
async def calculate_iq720_kelly(
    win_rate: float = Body(0.65, description="Historical win rate (0-1)"),
    avg_win: float = Body(0.82, description="Average win amount (payout ratio)"),
    avg_loss: float = Body(1.0, description="Average loss amount (usually 1.0 for binary)")
):
    """
    Calculate Kelly Criterion optimal position sizing.
    Returns fraction of capital to risk per trade (half-Kelly for safety).
    """
    try:
        kelly = iq720_generator.calculate_kelly_criterion(win_rate, avg_win, avg_loss)
        
        return {
            "success": True,
            "kelly_fraction": round(kelly, 4),
            "kelly_percent": round(kelly * 100, 2),
            "risk_per_trade": f"{round(kelly * 100, 2)}%",
            "inputs": {
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss
            },
            "note": "Half-Kelly applied for safety. Capped at 12.5% of capital."
        }
    except Exception as e:
        logger.error(f"Kelly criterion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signals/iq720-features")
async def get_iq720_features(
    symbol: str = Body("EURUSD", description="Trading symbol"),
    timeframe: str = Body("M1", description="OANDA timeframe")
):
    """
    Get 60+ technical features computed by the IQ-720 system.
    Useful for ML model input, dashboards, or advanced analysis.
    """
    try:
        oanda_symbol = symbol.replace('_OTC', '').replace('OTC', '')
        if '_' not in oanda_symbol and len(oanda_symbol) == 6:
            oanda_symbol = f"{oanda_symbol[:3]}_{oanda_symbol[3:]}"

        oanda_df = enhanced_oanda.get_candles(oanda_symbol, timeframe, 100)
        if oanda_df is None or oanda_df.empty:
            return {"success": False, "message": "No market data available", "features": {}}

        candles = oanda_df.reset_index().to_dict('records')
        features = iq720_generator.generate_60_features(candles)

        if not features:
            return {"success": False, "message": "Insufficient data for feature generation", "features": {}}

        return {
            "success": True,
            "symbol": symbol,
            "feature_count": len(features),
            "features": _convert_numpy_types(features),
            "categories": {
                "price": [k for k in features if k.startswith(('return_', 'high_low', 'close_pos', 'gap', 'volatility_', 'price_'))],
                "moving_averages": [k for k in features if k.startswith(('sma_', 'ema_'))],
                "momentum": [k for k in features if k.startswith(('rsi_', 'stoch_', 'roc_', 'williams_', 'momentum_'))],
                "trend": [k for k in features if k.startswith(('macd', 'adx', 'ema_aligned', 'higher_', 'lower_'))],
                "volatility": [k for k in features if k.startswith(('atr', 'bb_', 'kc_'))],
                "patterns": [k for k in features if k in ('doji', 'hammer', 'shooting_star', 'bullish_engulfing', 'bearish_engulfing', 'three_white_soldiers')]
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"IQ-720 features error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
