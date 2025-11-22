from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone

# Import our trading bot components
from models import (
    TradingSignal, MarketData, TechnicalIndicators, TradingConfiguration,
    PerformanceMetrics, BacktestResult, TradingStrategy, TradingMode, AssetType, SignalDirection,
    FlexibleStrategyRequest
)
from trading_bot_service import TradingBotService
from real_market_data_service import RealMarketDataService
from platform_integrations import platform_integration
from force_signal_generator import force_signal_generator
from pocket_option_assets import pocket_option_assets
from timezone_utils import get_chicago_time, utc_to_chicago, format_chicago_time
from latency_accuracy_tester import latency_tester
from live_accuracy_tester import live_accuracy_tester

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Helper function to convert numpy types for JSON serialization
def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    import numpy as np
    import math
    
    def safe_float(value):
        """Convert to float and handle NaN/infinity values"""
        try:
            f_val = float(value)
            if math.isnan(f_val) or math.isinf(f_val):
                return 0.0
            return f_val
        except (ValueError, TypeError):
            return 0.0
    
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return safe_float(obj)
    elif isinstance(obj, np.ndarray):
        return [_convert_numpy_types(item) for item in obj.tolist()]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, float):
        return safe_float(obj)
    elif hasattr(obj, 'item'):  # Handle numpy scalars
        try:
            item_val = obj.item()
            if isinstance(item_val, float):
                return safe_float(item_val)
            return item_val
        except:
            return 0.0
    else:
        return obj

# Initialize trading bot service
trading_bot = TradingBotService(db)

# Create the main app without a prefix
app = FastAPI(
    title="GPT Signal Bot API",
    description="Advanced AI-powered trading signal bot for Pocket Option",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Request/Response Models
class BotStartRequest(BaseModel):
    trading_mode: TradingMode = TradingMode.DEMO
    active_strategies: List[TradingStrategy] = [TradingStrategy.HYBRID]
    target_assets: List[AssetType] = [AssetType.FOREX, AssetType.CRYPTO]
    selected_assets: List[str] = ['EURUSD_regular', 'BTCUSD_regular']
    selected_timeframes: List[str] = ['1m', '5m']
    risk_tolerance: str = "medium"
    max_stake_per_trade: float = 10.0
    max_daily_trades: int = 50
    min_probability_threshold: float = Field(default=85.0, ge=50.0, le=99.0)
    auto_trading_enabled: bool = False
    invert_signals: bool = False
    sound_alerts_enabled: bool = True

class BotStatusResponse(BaseModel):
    is_running: bool
    current_mode: str
    active_strategies: List[str]
    signals_today: int
    performance: Dict[str, Any]
    auto_signal_generation: bool = False

class BacktestRequest(BaseModel):
    strategy: TradingStrategy
    symbol: str
    days: int = 30

# Bot Control Endpoints
@api_router.post("/bot/start")
async def start_bot(config: BotStartRequest):
    """Start the trading bot with specified configuration"""
    try:
        trading_config = TradingConfiguration(
            trading_mode=config.trading_mode,
            active_strategies=config.active_strategies,
            target_assets=config.target_assets,
            selected_assets=config.selected_assets,
            selected_timeframes=config.selected_timeframes,
            risk_tolerance=config.risk_tolerance,
            max_stake_per_trade=config.max_stake_per_trade,
            max_daily_trades=config.max_daily_trades,
            min_probability_threshold=config.min_probability_threshold,
            auto_trading_enabled=config.auto_trading_enabled,
            invert_signals=config.invert_signals,
            sound_alerts_enabled=config.sound_alerts_enabled
        )
        
        await trading_bot.start_bot(trading_config)
        
        return {
            "status": "success",
            "message": f"Trading bot started in {config.trading_mode} mode",
            "config": trading_config.dict()
        }
        
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/stop")
async def stop_bot():
    """Stop the trading bot and all related processes"""
    try:
        await trading_bot.stop_bot()
        return {
            "status": "success", 
            "message": "Trading bot stopped successfully",
            "bot_running": False,
            "candle_sync_stopped": True,
            "auto_generation_stopped": True
        }
        
    except Exception as e:
        logging.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/clear-all")
async def clear_all_sessions():
    """
    Clear all active trading sessions and reset bot state
    This performs a hard reset of all bot components
    """
    try:
        result = await trading_bot.clear_all_sessions()
        
        return {
            "status": "success" if result.get("success") else "warning",
            "message": result.get("message"),
            "details": {
                "bot_running": result.get("bot_running"),
                "candle_sync_enabled": result.get("candle_sync_enabled"),
                "auto_signal_generation": result.get("auto_signal_generation"),
                "active_signals_cleared": result.get("active_signals_cleared", True)
            }
        }
        
    except Exception as e:
        logging.error(f"Error clearing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/restart")
async def restart_bot():
    """
    Restart the bot with current configuration
    Clears all sessions and restarts fresh
    """
    try:
        result = await trading_bot.restart_bot()
        
        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message"),
                "bot_running": result.get("bot_running"),
                "configuration_loaded": True
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message"))
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error restarting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/candle-sync/enable")
async def enable_candle_sync():
    """
    Enable candle formation synchronization mode
    Signals will be generated precisely when new candles form on Pocket Option
    """
    try:
        result = await trading_bot.enable_candle_synchronization()
        
        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message"),
                "timeframes": result.get("timeframes", []),
                "assets_count": result.get("assets_count", 0)
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error enabling candle sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/candle-sync/disable")
async def disable_candle_sync():
    """Disable candle formation synchronization mode"""
    try:
        result = await trading_bot.disable_candle_synchronization()
        
        return {
            "status": "success",
            "message": result.get("message")
        }
        
    except Exception as e:
        logging.error(f"Error disabling candle sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/candle-sync/status")
async def get_candle_sync_status():
    """Get current candle synchronization status and next candle times"""
    try:
        status = await trading_bot.get_candle_sync_status()
        return status
        
    except Exception as e:
        logging.error(f"Error getting candle sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# LATENCY & ACCURACY TESTING ENDPOINTS
# ============================================================================

@api_router.post("/testing/latency/signal-generation")
async def test_signal_generation_latency(timeframe: str = '5s', iterations: int = 10):
    """
    Test signal generation lag time
    Measures how fast signals can be generated
    """
    try:
        result = await latency_tester.test_signal_generation_lag(timeframe, iterations)
        return result
    except Exception as e:
        logging.error(f"Error in signal generation latency test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/testing/latency/candle-timing")
async def test_candle_timing_accuracy(timeframe: str = '5s', samples: int = 5):
    """
    Test candle formation timing accuracy
    Measures how accurately we predict Pocket Option candle times
    """
    try:
        result = await latency_tester.test_candle_timing_accuracy(timeframe, samples)
        return result
    except Exception as e:
        logging.error(f"Error in candle timing accuracy test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/testing/latency/network")
async def test_network_latency(iterations: int = 10):
    """
    Test network latency
    Simulates API call round-trip time
    """
    try:
        result = await latency_tester.test_network_latency(iterations)
        return result
    except Exception as e:
        logging.error(f"Error in network latency test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/testing/latency/end-to-end")
async def test_end_to_end_timing(timeframe: str = '5s'):
    """
    Test complete end-to-end timing
    Measures total time from signal generation to platform execution
    """
    try:
        result = await latency_tester.test_end_to_end_timing(timeframe)
        return result
    except Exception as e:
        logging.error(f"Error in end-to-end timing test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/testing/comprehensive")
async def run_comprehensive_test_suite():
    """
    Run comprehensive latency and accuracy test suite
    Tests all aspects and provides recommendations
    """
    try:
        results = await latency_tester.run_comprehensive_test_suite()
        return results
    except Exception as e:
        logging.error(f"Error in comprehensive test suite: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# LIVE ACCURACY TESTING ENDPOINTS
# ============================================================================

@api_router.post("/testing/accuracy/verify-signal/{signal_id}")
async def verify_signal_outcome(signal_id: str, exit_price: float):
    """
    Manually verify a signal's outcome with actual exit price
    Used to track real win/loss performance
    """
    try:
        result = await live_accuracy_tester.verify_signal_outcome(signal_id, exit_price)
        return result
    except Exception as e:
        logging.error(f"Error verifying signal outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/testing/accuracy/stats")
async def get_accuracy_stats(
    strategy: Optional[str] = None,
    timeframe: Optional[str] = None,
    time_range_hours: int = 24
):
    """
    Get accuracy statistics for signals
    
    Query params:
        strategy: Filter by strategy name (optional)
        timeframe: Filter by timeframe (optional)
        time_range_hours: Time range in hours (default: 24)
    """
    try:
        stats = live_accuracy_tester.calculate_accuracy_stats(
            strategy=strategy,
            timeframe=timeframe,
            time_range_hours=time_range_hours
        )
        return stats
    except Exception as e:
        logging.error(f"Error getting accuracy stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/testing/accuracy/pending")
async def get_pending_signals():
    """
    Get all signals awaiting verification
    """
    try:
        signals = live_accuracy_tester.get_pending_signals()
        return {"pending_signals": signals, "count": len(signals)}
    except Exception as e:
        logging.error(f"Error getting pending signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/testing/accuracy/recent")
async def get_recent_results(limit: int = 20):
    """
    Get recent verified signal results
    """
    try:
        results = live_accuracy_tester.get_recent_results(limit=limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logging.error(f"Error getting recent results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/status", response_model=BotStatusResponse)
async def get_bot_status():
    """Get current bot status and performance"""
    try:
        performance = await trading_bot.get_performance_metrics()
        
        return BotStatusResponse(
            is_running=trading_bot.is_running,
            current_mode=trading_bot.config.trading_mode.value,
            active_strategies=[s.value for s in trading_bot.config.active_strategies],
            signals_today=performance.get("total_signals", 0),
            performance=performance,
            auto_signal_generation=getattr(trading_bot, 'auto_signal_generation', False)
        )
        
    except Exception as e:
        logging.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Signal Endpoints
@api_router.get("/signals/active", response_model=List[TradingSignal])
async def get_active_signals():
    """Get currently active trading signals"""
    try:
        signals = await trading_bot.get_active_signals()
        return signals
        
    except Exception as e:
        logging.error(f"Error getting active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/signals/history")
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
@api_router.get("/market/data")
async def get_market_data():
    """Get current market data for all tracked assets"""
    try:
        market_service = RealMarketDataService()
        all_data = await market_service.get_all_market_data()
        return all_data
        
    except Exception as e:
        logging.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/market/data/{symbol}")
async def get_symbol_data(symbol: str, asset_type: AssetType):
    """Get market data for a specific symbol"""
    try:
        market_service = RealMarketDataService()
        data = await market_service.get_market_data(symbol, asset_type)
        return data.dict() if data else {"error": "No data found"}
        
    except Exception as e:
        logging.error(f"Error getting data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/market/data/selected")
async def get_selected_assets_data(selected_assets: List[str]):
    """Get market data for selected Pocket Option assets"""
    try:
        market_service = RealMarketDataService()
        results = []
        
        for asset_id in selected_assets:
            # Parse asset_id (format: SYMBOL_market)
            if '_' in asset_id:
                symbol, market_type = asset_id.rsplit('_', 1)
            else:
                symbol, market_type = asset_id, 'regular'
            
            # Determine asset type from symbol
            asset_type = AssetType.FOREX  # Default
            if any(crypto in symbol.upper() for crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'BNB']):
                asset_type = AssetType.CRYPTO
            elif symbol.upper() in ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA']:
                asset_type = AssetType.STOCKS
            elif any(commodity in symbol.upper() for commodity in ['XAU', 'XAG', 'OIL', 'GOLD', 'SILVER']):
                asset_type = AssetType.COMMODITIES
            elif any(index in symbol.upper() for index in ['SPX', 'NAS', 'DJ', 'FTSE', 'DAX']):
                asset_type = AssetType.INDICES
            
            data = await market_service.get_market_data(symbol, asset_type)
            if data:
                result = data.dict()
                result['market_type'] = market_type
                result['asset_id'] = asset_id
                results.append(result)
        
        return {"selected_assets": results}
        
    except Exception as e:
        logging.error(f"Error getting selected assets data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Performance & Analytics
@api_router.get("/performance/metrics")
async def get_performance_metrics():
    """Get current performance metrics"""
    try:
        metrics = await trading_bot.get_performance_metrics()
        return metrics
        
    except Exception as e:
        logging.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/performance/history")
async def get_performance_history(days: int = 30):
    """Get historical performance metrics"""
    try:
        from datetime import timedelta
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        metrics = await db.performance_metrics.find({
            "date": {"$gte": start_date}
        }).sort("date", -1).to_list(length=None)
        
        return {"metrics": metrics}
        
    except Exception as e:
        logging.error(f"Error getting performance history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Backtesting
@api_router.post("/backtest/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Run backtesting for a specific strategy"""
    try:
        result = await trading_bot.run_backtest(
            request.strategy, 
            request.symbol, 
            request.days
        )
        return result
        
    except Exception as e:
        logging.error(f"Error running backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/backtest/history")
async def get_backtest_history():
    """Get historical backtest results"""
    try:
        results = await db.backtest_results.find().sort("created_at", -1).limit(20).to_list(length=None)
        return {"results": results}
        
    except Exception as e:
        logging.error(f"Error getting backtest history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration
@api_router.get("/config")
async def get_config():
    """Get current bot configuration"""
    try:
        config = trading_bot.config.dict()
        return config
        
    except Exception as e:
        logging.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/config")
async def update_config(config: BotStartRequest):
    """Update bot configuration"""
    try:
        new_config = TradingConfiguration(
            trading_mode=config.trading_mode,
            active_strategies=config.active_strategies,
            target_assets=config.target_assets,
            selected_assets=config.selected_assets,
            selected_timeframes=config.selected_timeframes,
            risk_tolerance=config.risk_tolerance,
            max_stake_per_trade=config.max_stake_per_trade,
            max_daily_trades=config.max_daily_trades,
            min_probability_threshold=config.min_probability_threshold,
            auto_trading_enabled=config.auto_trading_enabled,
            invert_signals=config.invert_signals,
            sound_alerts_enabled=config.sound_alerts_enabled
        )
        
        trading_bot.config = new_config
        await trading_bot._save_config()
        
        return {"status": "success", "message": "Configuration updated"}
        
    except Exception as e:
        logging.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health Check
@api_router.get("/health")
async def api_health_check():
    """API health check endpoint with bot status"""
    return {
        "status": "healthy",
        "service": "GPT Signal Bot API",
        "bot_running": trading_bot.is_running,
        "app_initialized": globals().get('app_initialized', False),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Platform Integration Endpoints
@api_router.get("/integrations/status")
async def get_integration_status():
    """Get status of all platform integrations"""
    try:
        status = platform_integration.get_integration_status()
        return {"integrations": status}
    except Exception as e:
        logging.error(f"Error getting integration status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/integrations/test")
async def test_integrations():
    """Test all platform integrations"""
    try:
        await platform_integration.initialize_integrations()
        status = platform_integration.get_integration_status()
        return {"message": "Integration tests completed", "results": status}
    except Exception as e:
        logging.error(f"Error testing integrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/signals/{signal_id}/execute")
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

@api_router.post("/signals/invert/{signal_id}")
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

@api_router.post("/signals/generate/single")
async def generate_single_signal():
    """Generate a single trading signal on-demand"""
    try:
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

@api_router.post("/signals/auto-generate/start")
async def start_auto_signal_generation():
    """Start automated signal generation mode"""
    try:
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

@api_router.post("/signals/auto-generate/stop")
async def stop_auto_signal_generation():
    """Stop automated signal generation mode"""
    try:
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

@api_router.get("/signals/auto-generate/status")
async def get_auto_signal_generation_status():
    """Get current automated signal generation status"""
    try:
        status = getattr(trading_bot, 'auto_signal_generation', False)
        return {
            "auto_generation_active": status,
            "bot_running": trading_bot.is_running,
            "status": "active" if status and trading_bot.is_running else "stopped"
        }
        
    except Exception as e:
        logging.error(f"Error getting auto signal generation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/signals/force-generate")
async def force_generate_signal(wait_for_candle: bool = False):
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
            user_timeframes = config_doc.get('selected_timeframes', []) if config_doc else []
            chart_type = config_doc.get('chart_type', 'japanese_candles') if config_doc else 'japanese_candles'
            invert_signals = config_doc.get('invert_signals', False) if config_doc else False
            candle_sync_enabled = config_doc.get('candle_sync_enabled', False) if config_doc else False
            
            # Use config setting if not explicitly set in request
            if not wait_for_candle:
                wait_for_candle = candle_sync_enabled
            
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
            
            # If no timeframes are selected, return error - require user to select timeframe
            if not user_timeframes or len(user_timeframes) == 0:
                logger.warning("⚠️ No timeframes selected for force signal generation")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "No timeframes selected",
                        "message": "⚠️ Please select at least one timeframe from the Trading Timeframes section on the Dashboard before generating signals."
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
        logger.info(f"⏱️ Using timeframes: {user_timeframes}")
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
            
            # Create market data object for this asset
            from models import MarketData, AssetType
            target_asset = MarketData(
                symbol=base_symbol,
                price=1.0500,  # Default price - will be fetched by strategy
                timestamp=datetime.now(timezone.utc),
                asset_type=AssetType.FOREX,  # Will be determined by symbol
                volume=0
            )
            
            # Dynamic timeout based on candle synchronization setting
            # If waiting for candle, allow up to 65 seconds (max 60s wait + 5s processing)
            # Otherwise use 12-second timeout for fast response
            timeout_seconds = 65.0 if wait_for_candle else 12.0
            
            try:
                forced_signals = await asyncio.wait_for(
                    force_signal_generator.force_generate_signal(
                        base_symbol, target_asset, user_timeframes, chart_type=chart_type, wait_for_candle=wait_for_candle
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
                    "expiration_minutes": int(signal.expiration_minutes),
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
                
                # Send to platforms if enabled
                try:
                    await platform_integration.send_signal_to_all_platforms(signal)
                except Exception as e:
                    logger.warning(f"Could not send forced signal to platforms: {e}")
            
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

@api_router.post("/signals/force-generate/asset/{asset_symbol}")
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
        market_data_service = RealMarketDataService()
        
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
        
        # Try to get real-time data for the asset
        target_data = None
        try:
            data_dict = market_data_service.get_real_time_data(asset_symbol, asset_type.value)
            if data_dict:
                # Convert dictionary to MarketData object
                from models import MarketData
                target_data = MarketData(
                    symbol=asset_symbol,
                    price=data_dict.get('price', 0.0),
                    timestamp=datetime.now(timezone.utc),
                    asset_type=asset_type,
                    volume=data_dict.get('volume', 0)
                )
        except Exception as e:
            logger.warning(f"Could not get real-time data for {asset_symbol}: {e}")
            target_data = None
        
        if not target_data:
            # Create fallback market data using yfinance
            import yfinance as yf
            
            # Convert symbol to yfinance format
            yf_symbol = asset_symbol
            if asset_symbol == 'BTCUSD':
                yf_symbol = 'BTC-USD'
            elif asset_symbol == 'ETHUSD':
                yf_symbol = 'ETH-USD'
            elif asset_symbol == 'EURUSD':
                yf_symbol = 'EURUSD=X'
            elif asset_symbol == 'GBPUSD':
                yf_symbol = 'GBPUSD=X'
            elif '/' in asset_symbol:
                # Handle format like EUR/USD
                yf_symbol = asset_symbol.replace('/', '') + '=X'
            
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="1d", interval="1m")
            
            if not hist.empty:
                from models import MarketData
                current_price = float(hist['Close'].iloc[-1])
                
                target_data = MarketData(
                    symbol=asset_symbol,
                    price=current_price,
                    timestamp=datetime.now(timezone.utc),
                    asset_type=asset_type,
                    volume=float(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
                )
        
        if not target_data:
            # Create emergency market data for force generation - NEVER fail
            logger.warning(f"No market data available for {asset_symbol} - creating emergency market data for force generation")
            from models import MarketData
            target_data = MarketData(
                symbol=asset_symbol,
                price=1.0000 if asset_type == AssetType.FOREX else 100.0,  # Default price based on asset type
                timestamp=datetime.now(timezone.utc),
                asset_type=asset_type,
                volume=0
            )
        
        logger.info(f"🚀 FORCE GENERATING SIGNAL for specific asset: {asset_symbol}")
        
        # Get user's selected timeframes from current configuration
        try:
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            user_timeframes = config_doc.get('selected_timeframes', ['5m']) if config_doc else ['5m']
            invert_signals = config_doc.get('invert_signals', False) if config_doc else False
            
            # If no timeframes are selected, use ultra-short default
            if not user_timeframes or len(user_timeframes) == 0:
                user_timeframes = ['5s']  # Default to ultra-short 5 second timeframe
                logger.info("No timeframes selected, using ultra-short 5s default")
        except Exception as e:
            logger.warning(f"Could not get user timeframes, using default: {e}")
            user_timeframes = ['5s']
            invert_signals = False
        
        logger.info(f"Using user selected timeframes for {asset_symbol}: {user_timeframes}")
        
        # Force generate signals (both regular and OTC)
        forced_signals = await force_signal_generator.force_generate_signal(
            target_data.symbol, target_data, user_timeframes, wait_for_candle=wait_for_candle
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
                    "expiration_minutes": int(signal.expiration_minutes),
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


@api_router.post("/signals/flexible-generate")
async def flexible_signal_generation(request: FlexibleStrategyRequest):
    """
    Generate signal using flexible crossover strategy with custom parameters
    Allows independent selection of chart timeframe and trade duration
    """
    try:
        from flexible_crossover_strategy import get_flexible_strategy
        
        logger.info(f"🎯 Flexible Strategy Signal Generation Request:")
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



@api_router.get("/integrations/settings")
async def get_integration_settings():
    """Get all platform integration settings"""
    try:
        settings = await db.integration_settings.find_one({"type": "platform_integrations"})
        
        if not settings:
            # Return default settings
            default_settings = {
                "telegram": {
                    "enabled": False,
                    "bot_token": "",
                    "chat_id": "",
                    "username": ""
                },
                "autobot": {
                    "enabled": False,
                    "webhook_url": "",
                    "signal_key": "",
                    "buy_message_template": json.dumps({
                        "action": "BUY",
                        "symbol": "{{symbol}}",
                        "price": "{{price}}",
                        "confidence": "{{confidence}}",
                        "timeframe": "{{timeframe}}",
                        "timestamp": "{{timestamp}}"
                    }, indent=2),
                    "sell_message_template": json.dumps({
                        "action": "SELL",
                        "symbol": "{{symbol}}",
                        "price": "{{price}}",
                        "confidence": "{{confidence}}",
                        "timeframe": "{{timeframe}}",
                        "timestamp": "{{timestamp}}"
                    }, indent=2)
                },
                "pocket_option": {
                    "enabled": False,
                    "email": "",
                    "password": "",
                    "ssid": "",
                    "demo_mode": True
                },
                "mt4": {
                    "enabled": False,
                    "server": "",
                    "login": "",
                    "password": "",
                    "account_type": "demo"
                },
                "mt5": {
                    "enabled": False,
                    "server": "",
                    "login": "",
                    "password": "",
                    "account_type": "demo"
                }
            }
            return {"success": True, "data": default_settings}
        
        # Remove MongoDB _id field
        settings.pop('_id', None)
        settings.pop('type', None)
        
        return {"success": True, "data": settings}
        
    except Exception as e:
        logger.error(f"Error fetching integration settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/integrations/settings")
async def save_integration_settings(settings: dict):
    """Save platform integration settings"""
    try:
        settings["type"] = "platform_integrations"
        settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Upsert settings
        await db.integration_settings.update_one(
            {"type": "platform_integrations"},
            {"$set": settings},
            upsert=True
        )
        
        logger.info("✅ Integration settings saved successfully")
        return {"success": True, "message": "Settings saved successfully"}
        
    except Exception as e:
        logger.error(f"Error saving integration settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/integrations/test/{platform}")
async def test_integration_connection(platform: str, credentials: dict):
    """Test connection to specific platform"""
    try:
        logger.info(f"🧪 Testing {platform} connection")
        
        if platform == "telegram":
            # Test Telegram bot
            if not credentials.get("bot_token") or not credentials.get("chat_id"):
                return {"success": False, "message": "Bot token and chat ID are required"}
            
            import requests
            url = f"https://api.telegram.org/bot{credentials['bot_token']}/sendMessage"
            payload = {
                "chat_id": credentials["chat_id"],
                "text": "🧪 Test message from Trading Bot - Connection successful!"
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return {"success": True, "message": "Telegram connection successful! Test message sent."}
            else:
                return {"success": False, "message": f"Telegram API error: {response.text}"}
        
        elif platform == "autobot":
            # Test AutobotSignal.io webhook
            if not credentials.get("webhook_url"):
                return {"success": False, "message": "Webhook URL is required"}
            
            import requests
            test_payload = {
                "action": "TEST",
                "message": "Connection test from Trading Bot",
                "signal_key": credentials.get("signal_key", ""),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            response = requests.post(
                credentials["webhook_url"],
                json=test_payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {"success": True, "message": "AutobotSignal.io connection successful!"}
            else:
                return {"success": False, "message": f"Webhook error: {response.text}"}
        
        elif platform == "pocket_option":
            # Test Pocket Option connection
            if not credentials.get("email") or not credentials.get("password"):
                return {"success": False, "message": "Email and password are required"}
            
            # TODO: Implement Pocket Option API connection test
            return {"success": True, "message": "Pocket Option credentials saved (connection test not yet implemented)"}
        
        elif platform == "mt4":
            # Test MT4 connection
            if not credentials.get("server") or not credentials.get("login") or not credentials.get("password"):
                return {"success": False, "message": "Server, login, and password are required"}
            
            # TODO: Implement MT4 connection test
            return {"success": True, "message": "MT4 credentials saved (connection test not yet implemented)"}
        
        elif platform == "mt5":
            # Test MT5 connection
            if not credentials.get("server") or not credentials.get("login") or not credentials.get("password"):
                return {"success": False, "message": "Server, login, and password are required"}
            
            # TODO: Implement MT5 connection test
            return {"success": True, "message": "MT5 credentials saved (connection test not yet implemented)"}
        
        else:
            return {"success": False, "message": f"Unknown platform: {platform}"}
            
    except Exception as e:
        logger.error(f"Error testing {platform} connection: {e}")
        return {"success": False, "message": f"Connection test failed: {str(e)}"}



@api_router.get("/alpha-vantage/exchange-rate")
async def get_alpha_vantage_exchange_rate(from_currency: str, to_currency: str):
    """
    Get real-time exchange rate from Alpha Vantage
    
    Example: /api/alpha-vantage/exchange-rate?from_currency=EUR&to_currency=USD
    """
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        
        logger.info(f"📊 Alpha Vantage Exchange Rate Request: {from_currency}/{to_currency}")
        
        service = get_alpha_vantage_service()
        rate_data = service.get_exchange_rate(from_currency, to_currency)
        
        if rate_data is None:
            return {
                "success": False,
                "message": f"Failed to fetch exchange rate for {from_currency}/{to_currency}",
                "data": None
            }
        
        return {
            "success": True,
            "message": f"Exchange rate fetched successfully",
            "data": rate_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage data: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Alpha Vantage request failed: {str(e)}")

@api_router.get("/alpha-vantage/price/{symbol}")
async def get_alpha_vantage_price(symbol: str):
    """
    Get current price for trading symbol using Alpha Vantage
    
    Example: /api/alpha-vantage/price/EURUSD
    """
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        
        logger.info(f"💰 Alpha Vantage Price Request: {symbol}")
        
        service = get_alpha_vantage_service()
        price = service.get_current_price(symbol)
        
        if price is None:
            return {
                "success": False,
                "message": f"Failed to fetch price for {symbol}",
                "price": None
            }
        
        return {
            "success": True,
            "message": f"Price fetched successfully",
            "symbol": symbol,
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage price: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Alpha Vantage price request failed: {str(e)}")



@api_router.post("/signals/micro-momentum-5s-otc")
async def micro_momentum_5s_otc_signal_generation(asset_symbol: str, trade_duration_seconds: int = 5):
    """
    Generate signal using Micro-Momentum Scalp strategy for 5-second OTC markets
    
    Strategy: EMA20 + RSI(2) + Stochastic(3,1,1) + Bollinger Bands(5,2.5)
    Target: 65-75% win rate through micro-trend confluence
    Markets: OTC Forex only (EUR/USD_OTC, GBP/USD_OTC, etc.)
    """
    try:
        from micro_momentum_scalp_5s_otc import get_micro_momentum_5s_otc_strategy
        
        logger.info(f"🚀 Micro-Momentum 5s OTC Signal Generation:")
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


# Legacy endpoints for compatibility
@api_router.get("/")
async def root():
    return {"message": "GPT Signal Bot API - Advanced AI Trading System"}

# Asset Management Routes
@api_router.get("/assets/all")
async def get_all_assets():
    """Get all Pocket Option assets (Regular + OTC)"""
    try:
        assets = pocket_option_assets.get_all_assets_formatted()
        
        # Add summary statistics
        total_count = sum(len(category_assets) for category_assets in assets.values())
        summary = {
            "forex_count": len(assets["forex"]),
            "crypto_count": len(assets["crypto"]),
            "stocks_count": len(assets["stocks"]),
            "commodities_count": len(assets["commodities"]),
            "indices_count": len(assets["indices"]),
            "total_assets": total_count
        }
        
        return {
            "success": True,
            "assets": assets,
            "summary": summary,
            "last_updated": "2025-01-01"
        }
    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        return {"success": False, "error": str(e)}

@api_router.get("/assets/symbols")
async def get_asset_symbols():
    """Get simple list of all asset symbols"""
    try:
        symbols = pocket_option_assets.get_symbols_list()
        otc_symbols = pocket_option_assets.get_otc_symbols()
        
        return {
            "success": True,
            "regular_symbols": symbols,
            "otc_symbols": otc_symbols,
            "total_regular": len(symbols),
            "total_otc": len(otc_symbols)
        }
    except Exception as e:
        logger.error(f"Error getting asset symbols: {e}")
        return {"success": False, "error": str(e)}

@api_router.get("/assets/category/{category}")
async def get_assets_by_category(category: str):
    """Get assets by category (forex, crypto, stocks, commodities, indices)"""
    try:
        assets = pocket_option_assets.get_all_assets_formatted()
        
        if category.lower() not in assets:
            return {"success": False, "error": f"Invalid category: {category}"}
        
        category_assets = assets[category.lower()]
        
        return {
            "success": True,
            "category": category.lower(),
            "assets": category_assets,
            "count": len(category_assets)
        }
    except Exception as e:
        logger.error(f"Error getting assets for category {category}: {e}")
        return {"success": False, "error": str(e)}

# Strategy Selection API Endpoints
@api_router.get("/strategies/available")
async def get_available_strategies():
    """Get all available strategies for all timeframes"""
    try:
        from strategy_selection_service import strategy_selection_service
        strategies = strategy_selection_service.get_all_available_strategies()
        
        return {
            "success": True,
            "strategies": strategies
        }
    except Exception as e:
        logger.error(f"Error getting available strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/strategies/available/{timeframe}")
async def get_available_strategies_for_timeframe(timeframe: str):
    """Get available strategies for a specific timeframe"""
    try:
        from strategy_selection_service import strategy_selection_service
        strategies = strategy_selection_service.get_available_strategies(timeframe)
        
        if not strategies:
            raise HTTPException(status_code=404, detail=f"No strategies found for timeframe {timeframe}")
        
        return {
            "success": True,
            "timeframe": timeframe,
            "strategies": strategies
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategies for {timeframe}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/strategies/selected")
async def get_selected_strategies():
    """Get user's currently selected strategies for all timeframes"""
    try:
        from strategy_selection_service import strategy_selection_service
        selections = await strategy_selection_service.get_selected_strategies()
        
        return {
            "success": True,
            "selections": selections
        }
    except Exception as e:
        logger.error(f"Error getting selected strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class StrategySelectionRequest(BaseModel):
    timeframe: str
    strategy_id: str

@api_router.post("/strategies/select")
async def update_strategy_selection(request: StrategySelectionRequest):
    """Update strategy selection for a specific timeframe"""
    try:
        from strategy_selection_service import strategy_selection_service
        
        success = await strategy_selection_service.update_strategy_selection(
            request.timeframe,
            request.strategy_id
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe or strategy ID"
            )
        
        return {
            "success": True,
            "message": f"Strategy updated for {request.timeframe}",
            "timeframe": request.timeframe,
            "strategy_id": request.strategy_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/strategies/details/{timeframe}/{strategy_id}")
async def get_strategy_details(timeframe: str, strategy_id: str):
    """Get details for a specific strategy"""
    try:
        from strategy_selection_service import strategy_selection_service
        details = await strategy_selection_service.get_strategy_details(timeframe, strategy_id)
        
        if not details:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy {strategy_id} not found for timeframe {timeframe}"
            )
        
        return {
            "success": True,
            "strategy": details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Latency Adjustment Endpoints
@api_router.get("/latency/settings")
async def get_latency_settings():
    """Get current user latency adjustment settings"""
    try:
        settings = await db.latency_settings.find_one({'type': 'user_latency_offset'})
        
        if settings:
            return {
                "success": True,
                "latency_offset": settings.get('latency_offset', 0.0),
                "updated_at": settings.get('updated_at')
            }
        
        # Return defaults if no settings exist
        return {
            "success": True,
            "latency_offset": 0.0,
            "updated_at": None
        }
    except Exception as e:
        logger.error(f"Error getting latency settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/latency/settings")
async def update_latency_settings(latency_offset: float):
    """
    Update user latency adjustment offset
    
    Args:
        latency_offset: Latency offset in seconds (-10 to +10)
            - Negative values: signals arrive earlier
            - Positive values: signals arrive later
            - 0: automatic timing (default)
    """
    try:
        # Validate range
        if latency_offset < -10 or latency_offset > 10:
            raise HTTPException(
                status_code=400,
                detail="Latency offset must be between -10 and +10 seconds"
            )
        
        # Update latency optimizer with new offset
        from latency_optimizer import latency_optimizer
        latency_optimizer.set_user_latency_offset(latency_offset)
        
        # Save to database
        await db.latency_settings.update_one(
            {'type': 'user_latency_offset'},
            {
                '$set': {
                    'type': 'user_latency_offset',
                    'latency_offset': latency_offset,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ Latency offset updated to {latency_offset}s")
        
        return {
            "success": True,
            "message": f"Latency offset updated to {latency_offset}s",
            "latency_offset": latency_offset
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating latency settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint (responds immediately for Kubernetes readiness probes)
@app.get("/health")
async def health_check():
    """Health check endpoint that always returns 200 OK during startup and runtime"""
    return {
        "status": "healthy",
        "service": "GPT Signal Bot API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track initialization status
app_initialized = False

@app.on_event("startup")
async def startup_event():
    """
    Startup event - load configuration in background task to avoid blocking server startup
    This prevents nginx health checks from failing during initialization
    """
    global app_initialized
    
    async def initialize_app():
        """Background initialization task"""
        global app_initialized
        try:
            logger.info("🚀 Starting background initialization...")
            # Load trading bot configuration
            await trading_bot._load_config()
            app_initialized = True
            logger.info("✅ Application initialization complete")
        except Exception as e:
            logger.error(f"❌ Error during initialization: {e}")
            app_initialized = False
    
    # Start initialization in background (non-blocking)
    import asyncio
    asyncio.create_task(initialize_app())
    
    # Return immediately so server can start accepting health checks
    logger.info("⚡ Server startup complete - initialization running in background")

@app.on_event("shutdown")
async def shutdown_db_client():
    # Stop trading bot
    await trading_bot.stop_bot()
    # Close database connection
    client.close()