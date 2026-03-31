# Force CPU-only mode for ML libraries BEFORE any imports
try:
    import ml_config  # This must be imported FIRST to set env vars
except ImportError:
    pass

from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Query, Request, Body
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables BEFORE any other imports that might need them
load_dotenv()

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
import pandas as pd

# Import our trading bot components
from trading_models import (
    TradingSignal, MarketData, TechnicalIndicators, TradingConfiguration,
    PerformanceMetrics, BacktestResult, TradingStrategy, TradingMode, AssetType, SignalDirection,
    FlexibleStrategyRequest, AdaptiveStrategyConfig, AdaptiveStrategyUpdateRequest
)
from trading_bot_service import TradingBotService
from real_market_data_service import RealMarketDataService
from platform_integrations import platform_integration
from force_signal_generator import force_signal_generator
from pocket_option_assets import pocket_option_assets
from timezone_utils import get_chicago_time, utc_to_chicago, format_chicago_time
from latency_optimizer import latency_optimizer
from signal_accuracy_optimizer import SignalAccuracyOptimizer
from adaptive_strategy_service import AdaptiveStrategyService
from signal_validator import signal_validator
from ai_learning_system import ai_learning_system
from pocket_option_client import get_pocket_option_client, pocket_option_client
from multi_timeframe_analyzer import multi_timeframe_analyzer
# Import LSTM predictor (optional - will use fallback if ML not available)
try:
    from ai_lstm_predictor import lstm_predictor
except ImportError as e:
    print(f"LSTM predictor not available: {e}")
    lstm_predictor = None
# Import Ultra High Accuracy 5s Strategy
try:
    from ultra_high_accuracy_5s_strategy import ultra_high_accuracy_5s, get_ultra_high_accuracy_signal
    print("✅ Ultra High Accuracy 5s Strategy loaded")
except ImportError as e:
    print(f"Ultra High Accuracy 5s Strategy not available: {e}")
    ultra_high_accuracy_5s = None

# Import Enhanced AI ML System
try:
    from enhanced_ai_ml_system import enhanced_ai_ml
    print("✅ Enhanced AI ML System loaded")
except ImportError as e:
    print(f"Enhanced AI ML System not available: {e}")
    enhanced_ai_ml = None

# Import Improved AI ML System v2.0
try:
    from improved_ai_ml_system import improved_ai_ml
    print("✅ Improved AI ML System v2.0 loaded")
except ImportError as e:
    print(f"Improved AI ML System not available: {e}")
    improved_ai_ml = None

# Import Maximized AI ML System v3.0
try:
    from maximized_ai_ml_system import maximized_ai_ml
    print("✅ Maximized AI ML System v3.0 loaded")
except ImportError as e:
    print(f"Maximized AI ML System not available: {e}")
    maximized_ai_ml = None

from pocket_option_auth import auto_login_and_get_ssid
from advanced_signal_generator import advanced_signal_generator
from enhanced_sr_analyzer import enhanced_sr_analyzer
from candlestick_analyzer import candlestick_analyzer
# Import SSID and Telegram services
from ssid_auto_refresh_service import (
    SSIDAutoRefreshService, get_ssid_service, 
    initialize_ssid_service, shutdown_ssid_service
)
from telegram_signal_notifier import (
    TelegramSignalNotifier, get_telegram_notifier,
    initialize_telegram_notifier, shutdown_telegram_notifier
)
# Import Auto Trading Service
from pocket_option_auto_trader import (
    get_auto_trading_service, initialize_auto_trading, 
    shutdown_auto_trading, TradeDirection
)
# Import AI ML Trading System
from ai_ml_trading_system import ai_ml_trading_system, get_ai_prediction
from money_management_system import money_management, get_optimal_stake, run_risk_checks

# Import Auth and Telegram Bot Services
from auth_service import get_auth_service, UserRole
from telegram_bot_service import get_telegram_bot, TradingSignal as TelegramTradingSignal

# Import 3Commas Service
from threecommas_service import (
    get_threecommas_service, initialize_threecommas_service,
    ThreeCommasService
)

# Import Market Regime Detector
from market_regime_detector import (
    get_regime_detector, initialize_regime_detector,
    MarketRegimeDetector
)

# Import Enhanced AI Trading System and OANDA Market Data
from enhanced_ai_trading_system import enhanced_ai_system
from oanda_market_data_service import oanda_service
from enhanced_oanda_service import enhanced_oanda, TechnicalAnalyzer

# Import Pocket Option Real-Time Market Data
from pocket_option_market_data import po_market_data, get_po_market_data_service

# Import High Accuracy Trading Strategies
from high_accuracy_strategies import high_accuracy_generator, get_high_accuracy_signal

# Import Deep Market Analyzer for improved signal accuracy
from deep_market_analyzer import deep_analyzer, get_deep_analysis_signal

# Import MetaTrader 5 Trading Service
from mt5_trading_service import mt5_service, get_mt5_service

# Import MT5 ZeroMQ Bridge for remote MT5 connections
from mt5_zeromq_bridge import mt5_zmq_bridge, mt5_integration, get_mt5_bridge, get_mt5_integration

# Import TradingView Webhook Service
from tradingview_webhook_service import tradingview_webhook_service, TradingViewAlertModel, get_tradingview_service

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

# Initialize adaptive strategy service
adaptive_strategy_service_instance = AdaptiveStrategyService(db)

# Persistent Pocket Option connection
persistent_po_connection = None

# Initialize continuous scanner
from continuous_scanner import ContinuousMarketScanner
continuous_scanner = ContinuousMarketScanner(force_signal_generator, db)

# Initialize Real-Time Market Data Hub
from realtime_market_data_hub import RealtimeMarketDataHub
finnhub_key = os.environ.get('FINNHUB_API_KEY', '')
alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_API_KEY', os.environ.get('ALPHAVANTAGE_API_KEY', ''))
realtime_market_hub = RealtimeMarketDataHub(finnhub_key, alpha_vantage_key)

# Connect real-time hub to force signal generator
force_signal_generator.set_realtime_hub(realtime_market_hub)

# Create the main app without a prefix
app = FastAPI(
    title="GPT Signal Bot API",
    description="Advanced AI-powered trading signal bot for Pocket Option",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Helper function to process signal through automated trading
async def process_signal_for_automated_trading(signal_dict: Dict[str, Any]):
    """
    Process a generated signal through the automated trading service
    
    Args:
        signal_dict: Signal dictionary with symbol, direction, probability, etc.
    """
    try:
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        
        if service.is_enabled:
            result = await service.process_signal(signal_dict)
            
            if result:
                logger.info(f"🤖 Automated trade executed: {result['order_id']}")
            else:
                logger.debug("Signal not executed by automated trading")
        
    except Exception as e:
        logger.error(f"Error in automated trading: {e}")


# Request/Response Models
class BotStartRequest(BaseModel):
    trading_mode: TradingMode = TradingMode.DEMO
    active_strategies: List[TradingStrategy] = [TradingStrategy.HYBRID]
    target_assets: List[AssetType] = [AssetType.FOREX, AssetType.CRYPTO]
    selected_assets: List[str] = ['EURUSD_regular', 'BTCUSD_regular']
    selected_expirations: List[str] = ['1m', '2m']
    risk_tolerance: str = "medium"
    max_stake_per_trade: float = 10.0
    max_daily_trades: int = 50
    min_probability_threshold: float = Field(default=80.0, ge=50.0, le=99.0)
    auto_trading_enabled: bool = False
    invert_signals: bool = False
    sound_alerts_enabled: bool = True
    popup_notifications: bool = True
    selected_timeframe: Optional[str] = '1m'
    selected_strategy: Optional[str] = ''
    chart_config: Optional[Dict[str, Any]] = None
    flexible_config: Optional[Dict[str, Any]] = None

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
async def start_bot(config: Optional[BotStartRequest] = None):
    """Start the trading bot with specified configuration (or defaults)"""
    try:
        # Use provided config or create default
        if config is None:
            config = BotStartRequest()
        
        trading_config = TradingConfiguration(
            trading_mode=config.trading_mode,
            active_strategies=config.active_strategies,
            target_assets=config.target_assets,
            selected_assets=config.selected_assets,
            selected_expirations=config.selected_expirations,
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
    Works for both auto-generate (bot running) and manual Force Generate
    """
    try:
        # Save candle sync setting to config (works without bot running)
        await db.trading_configurations.update_one(
            {"user_id": "default_user"},
            {"$set": {"candle_sync_enabled": True}},
            upsert=True
        )
        
        # If bot is running, also enable the scheduler
        if trading_bot.is_running:
            result = await trading_bot.enable_candle_synchronization()
            return {
                "status": "success",
                "message": "Candle sync enabled for auto-generate mode",
                "timeframes": result.get("timeframes", []),
                "assets_count": result.get("assets_count", 0),
                "enabled": True
            }
        else:
            # Bot not running, but config saved for manual Force Generate
            return {
                "status": "success",
                "message": "Candle sync enabled for manual Force Generate",
                "enabled": True,
                "note": "Start bot for auto-generate sync"
            }
        
    except Exception as e:
        logging.error(f"Error enabling candle sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bot/candle-sync/disable")
async def disable_candle_sync():
    """Disable candle formation synchronization mode"""
    try:
        # Update config
        await db.trading_configurations.update_one(
            {"user_id": "default_user"},
            {"$set": {"candle_sync_enabled": False}},
            upsert=True
        )
        
        # If bot is running, also disable the scheduler
        if trading_bot.is_running:
            await trading_bot.disable_candle_synchronization()
        
        return {
            "status": "success",
            "message": "Candle synchronization disabled",
            "enabled": False
        }
        
    except Exception as e:
        logging.error(f"Error disabling candle sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/candle-sync/status")
async def get_candle_sync_status():
    """Get current candle synchronization status and next candle times"""
    try:
        # Get config setting - default to True (enabled) if not set
        config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
        candle_sync_enabled = config_doc.get("candle_sync_enabled", True) if config_doc else True
        
        # If bot is running, get detailed status from scheduler
        if trading_bot.is_running and candle_sync_enabled:
            status = await trading_bot.get_candle_sync_status()
            return status
        else:
            # Bot not running or sync disabled, return basic status
            return {
                "enabled": candle_sync_enabled,
                "bot_running": trading_bot.is_running,
                "next_candle_times": {},
                "message": "Candle sync ready for Force Generate" if candle_sync_enabled else "Disabled"
            }
        
    except Exception as e:
        logging.error(f"Error getting candle sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# LATENCY & ACCURACY TESTING ENDPOINTS - TEMPORARILY DISABLED
# ============================================================================
# Note: These endpoints are temporarily disabled due to missing modules
# They can be re-enabled once the required testing modules are available

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

@api_router.get("/config")
async def get_config():
    """Get current bot configuration with proper defaults"""
    try:
        # Get config from database
        config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
        
        # Define default startup values
        default_config = {
            "trading_mode": "demo",              # Demo account by default
            "selected_expirations": ["5s"],      # 5 seconds by default
            "selected_assets": [],               # Nothing selected - user must select
            "selected_timeframe": "5s",          # 5 seconds by default
            "selected_strategy": "",
            "min_probability_threshold": 85.0,
            "invert_signals": False,
            "sound_alerts_enabled": True,
            "popup_notifications": True,
            "auto_trading_enabled": False,
            "candle_sync_enabled": True          # Pocket Option sync enabled by default
        }
        
        # Merge with database config if exists
        if config_doc:
            # Remove MongoDB _id field
            config_doc.pop('_id', None)
            
            # Merge defaults with database values
            for key, default_value in default_config.items():
                if key not in config_doc or config_doc[key] is None:
                    config_doc[key] = default_value
            
            return config_doc
        else:
            # No config in database - return defaults and save them
            default_config["user_id"] = "default_user"
            default_config["updated_at"] = datetime.now(timezone.utc)
            
            await db.trading_configurations.insert_one(default_config)
            default_config.pop('_id', None)
            
            return default_config
        
    except Exception as e:
        logging.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/config")
async def update_config(config: BotStartRequest):
    """Update bot configuration - merges with existing config to preserve unspecified fields"""
    try:
        # First, fetch existing config from database to preserve fields not being updated
        existing_config = await db.trading_configurations.find_one({"user_id": "default_user"})
        
        # Build merged config - existing values as base, new values override
        merged_selected_expirations = config.selected_expirations
        merged_selected_assets = config.selected_assets
        merged_candle_sync = config.candle_sync_enabled if hasattr(config, 'candle_sync_enabled') else True
        
        # If the request has default values that look like they weren't intentionally set,
        # prefer the existing database values
        if existing_config:
            # Only use existing expiration if new one appears to be default and existing is different
            if (config.selected_expirations == ['1m', '2m'] or config.selected_expirations == ['1m']) and \
               existing_config.get('selected_expirations') and \
               existing_config.get('selected_expirations') != config.selected_expirations:
                # Check if the update is ONLY for trading_mode (account switch)
                # In this case, preserve the existing expirations
                logger.info(f"🔄 Preserving existing expirations: {existing_config.get('selected_expirations')}")
                merged_selected_expirations = existing_config.get('selected_expirations')
            
            # NOTE: We now allow empty arrays to clear assets (user explicitly selected nothing)
            # Only preserve existing assets if the request truly has no assets AND it's not a deliberate clear
            # Empty array [] is now treated as "user wants no assets selected"
        
        # Update main trading configuration
        new_config = TradingConfiguration(
            trading_mode=config.trading_mode,
            active_strategies=config.active_strategies,
            target_assets=config.target_assets,
            selected_assets=merged_selected_assets,
            selected_expirations=merged_selected_expirations,
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
        
        # Also save strategy-specific configuration to database
        config_doc = {
            "user_id": "default_user",
            "selected_timeframe": config.selected_timeframe,
            "selected_strategy": config.selected_strategy,
            "chart_config": config.chart_config or {},
            "flexible_config": config.flexible_config or {},
            "selected_assets": merged_selected_assets,
            "selected_expirations": merged_selected_expirations,
            "min_probability_threshold": config.min_probability_threshold,
            "trading_mode": config.trading_mode.value if hasattr(config.trading_mode, 'value') else config.trading_mode,
            "invert_signals": config.invert_signals,
            "sound_alerts_enabled": config.sound_alerts_enabled,
            "popup_notifications": config.popup_notifications,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Upsert configuration to database
        await db.trading_configurations.update_one(
            {"user_id": "default_user"},
            {"$set": config_doc},
            upsert=True
        )
        
        logger.info(f"✅ Configuration saved: timeframe={config.selected_timeframe}, expirations={merged_selected_expirations}")
        
        return {
            "status": "success", 
            "message": "Configuration updated and saved",
            "saved_config": {
                "timeframe": config.selected_timeframe,
                "strategy": config.selected_strategy,
                "selected_expirations": merged_selected_expirations
            }
        }
        
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

@api_router.get("/data-sources/verify")
async def verify_data_sources():
    """Verify real-time data sources for OTC and Regular markets"""
    try:
        from enhanced_oanda_service import enhanced_oanda
        
        pairs = ['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'EUR_JPY']
        results = {
            "oanda_connected": enhanced_oanda.is_configured if enhanced_oanda else False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prices": {},
            "data_quality": {}
        }
        
        for pair in pairs:
            try:
                df = enhanced_oanda.get_candles(pair, "M1", 5)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    results["prices"][pair] = {
                        "bid": float(latest['close']),
                        "timestamp": str(latest.name) if hasattr(latest, 'name') else str(df.index[-1]),
                        "candles_fetched": len(df),
                        "source": "OANDA_LIVE"
                    }
                    # Also show OTC mapping
                    otc_symbol = pair.replace('_', '') + '_OTC'
                    results["prices"][otc_symbol] = {
                        "bid": float(latest['close']),
                        "note": "OTC uses same price data from OANDA",
                        "source": "OANDA_LIVE"
                    }
                    results["data_quality"][pair] = "REAL_TIME"
                else:
                    results["prices"][pair] = {"error": "No data", "source": "UNAVAILABLE"}
                    results["data_quality"][pair] = "NO_DATA"
            except Exception as e:
                results["prices"][pair] = {"error": str(e), "source": "ERROR"}
                results["data_quality"][pair] = "ERROR"
        
        return results
    except Exception as e:
        logger.error(f"Data source verification failed: {e}")
        return {"error": str(e), "oanda_connected": False}

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

# =====================================================
# GENERAL SETTINGS ENDPOINTS
# =====================================================

@api_router.get("/settings")
async def get_settings():
    """Get general application settings"""
    try:
        settings = await db.app_settings.find_one({"type": "general"}, {"_id": 0})
        
        if not settings:
            # Return default settings
            default_settings = {
                "type": "general",
                "defaultTimeframe": "1m",
                "defaultAsset": "EURUSD_otc",
                "soundEnabled": True,
                "notificationsEnabled": True,
                "minimumConfidence": 70,
                "signalCooldown": 30,
                "telegramBotToken": "",
                "telegramChatId": ""
            }
            return default_settings
        
        return settings
        
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        return {
            "defaultTimeframe": "1m",
            "defaultAsset": "EURUSD_otc",
            "soundEnabled": True,
            "notificationsEnabled": True,
            "minimumConfidence": 70,
            "signalCooldown": 30
        }


@api_router.post("/settings")
async def save_settings(settings: dict):
    """Save general application settings"""
    try:
        settings["type"] = "general"
        settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Upsert settings
        await db.app_settings.update_one(
            {"type": "general"},
            {"$set": settings},
            upsert=True
        )
        
        logger.info(f"✅ Settings saved successfully")
        return {"success": True, "message": "Settings saved successfully"}
        
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


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
            "message": "Exchange rate fetched successfully",
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
            "message": "Price fetched successfully",
            "symbol": symbol,
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage price: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Alpha Vantage price request failed: {str(e)}")
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
class StrategySelectionRequest(BaseModel):
    timeframe: str
    strategy_id: str
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
        latency_offset: Latency offset in seconds (-30 to +30)
            - Negative values: signals arrive earlier (for early entry)
            - Positive values: signals arrive later (for confirmation)
            - 0: automatic timing (default)
    """
    try:
        # Validate extended range (-30 to +30)
        if latency_offset < -30 or latency_offset > 30:
            raise HTTPException(
                status_code=400,
                detail="Latency offset must be between -30 and +30 seconds"
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

# =====================================================
# RISK MANAGEMENT & DRAWDOWN PROTECTION ENDPOINTS
# =====================================================

@api_router.get("/risk-management/status")
async def get_risk_management_status():
    """Get current risk management status including Sharpe ratio and drawdown."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        return {"success": True, "risk_management": rm.to_dict()}
    except Exception as e:
        logger.error(f"Error getting risk status: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/risk-management/configure")
async def configure_risk_management(
    initial_balance: float = Query(1000.0),
    max_risk_per_trade: float = Query(0.02),
    max_drawdown_limit: float = Query(0.15),
    daily_loss_limit: float = Query(0.05),
    max_trades_per_day: int = Query(50),
    max_consecutive_losses: int = Query(5)
):
    """Configure risk management parameters."""
    try:
        from risk_management_system import RiskManager, risk_manager
        
        # Update risk manager settings
        risk_manager.initial_balance = initial_balance
        risk_manager.current_balance = initial_balance
        risk_manager.peak_balance = initial_balance
        risk_manager.max_risk_per_trade = max_risk_per_trade
        risk_manager.max_drawdown_limit = max_drawdown_limit
        risk_manager.daily_loss_limit = daily_loss_limit
        risk_manager.max_trades_per_day = max_trades_per_day
        risk_manager.max_consecutive_losses = max_consecutive_losses
        
        logger.info(f"🛡️ Risk management configured: Balance ${initial_balance}, "
                   f"Max DD {max_drawdown_limit*100}%, Daily limit {daily_loss_limit*100}%")
        
        return {
            "success": True,
            "message": "Risk management configured",
            "config": {
                "initial_balance": initial_balance,
                "max_risk_per_trade_pct": max_risk_per_trade * 100,
                "max_drawdown_limit_pct": max_drawdown_limit * 100,
                "daily_loss_limit_pct": daily_loss_limit * 100,
                "max_trades_per_day": max_trades_per_day,
                "max_consecutive_losses": max_consecutive_losses
            }
        }
    except Exception as e:
        logger.error(f"Error configuring risk management: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/risk-management/record-trade")
async def record_trade_result(
    direction: str = Query(..., description="CALL or PUT"),
    amount: float = Query(..., description="Trade amount in dollars"),
    pnl: float = Query(..., description="Profit/Loss in dollars"),
    win: bool = Query(..., description="Was the trade a win?"),
    asset: str = Query("UNKNOWN", description="Asset symbol"),
    confidence: float = Query(0.0, description="Signal confidence (0-100)")
):
    """Record a trade result for risk tracking."""
    try:
        from risk_management_system import get_risk_manager, TradeResult
        from datetime import datetime, timezone
        
        rm = get_risk_manager()
        
        trade = TradeResult(
            timestamp=datetime.now(timezone.utc),
            direction=direction.upper(),
            amount=amount,
            pnl=pnl,
            win=win,
            asset=asset,
            confidence=confidence / 100 if confidence > 1 else confidence
        )
        
        rm.record_trade(trade)
        
        return {
            "success": True,
            "trade_recorded": {
                "direction": trade.direction,
                "amount": trade.amount,
                "pnl": trade.pnl,
                "win": trade.win,
                "asset": trade.asset
            },
            "current_status": {
                "balance": rm.current_balance,
                "drawdown_pct": round(rm.get_current_drawdown() * 100, 2),
                "risk_level": rm.risk_level.value,
                "consecutive_losses": rm.consecutive_losses,
                "can_trade": rm.can_trade()[0]
            }
        }
    except Exception as e:
        logger.error(f"Error recording trade: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/risk-management/can-trade")
async def check_can_trade(confidence: float = Query(0.5, description="Signal confidence (0-1)")):
    """Check if trading is allowed based on current risk conditions."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        
        can_trade, reason = rm.can_trade(confidence)
        
        return {
            "success": True,
            "can_trade": can_trade,
            "reason": reason,
            "risk_level": rm.risk_level.value,
            "recommended_position_size": rm.get_recommended_position_size(confidence),
            "current_drawdown_pct": round(rm.get_current_drawdown() * 100, 2)
        }
    except Exception as e:
        logger.error(f"Error checking trade status: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/risk-management/position-size")
async def get_position_size(confidence: float = Query(0.7, description="Signal confidence (0-1)")):
    """Get recommended position size based on Kelly criterion and risk conditions."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        
        position_size = rm.get_recommended_position_size(confidence)
        kelly = rm.calculate_kelly_fraction()
        
        return {
            "success": True,
            "recommended_amount": round(position_size, 2),
            "kelly_fraction_pct": round(kelly * 100, 2),
            "current_balance": round(rm.current_balance, 2),
            "risk_level": rm.risk_level.value,
            "risk_adjustment_applied": rm.risk_level != "normal"
        }
    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/risk-management/metrics")
async def get_risk_metrics():
    """Get comprehensive risk metrics including Sharpe ratio, Sortino ratio, etc."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        metrics = rm.get_metrics()
        
        return {
            "success": True,
            "metrics": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "max_drawdown_pct": metrics.max_drawdown,
                "current_drawdown_pct": metrics.current_drawdown,
                "win_rate_pct": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "avg_win": metrics.avg_win,
                "avg_loss": metrics.avg_loss,
                "kelly_fraction_pct": metrics.kelly_fraction,
                "recommended_risk_pct": metrics.recommended_risk_pct,
                "trades_today": metrics.trades_today,
                "daily_pnl": metrics.daily_pnl,
                "weekly_pnl": metrics.weekly_pnl,
                "risk_level": metrics.risk_level.value
            },
            "interpretation": {
                "sharpe_quality": "Excellent" if metrics.sharpe_ratio > 2 else ("Good" if metrics.sharpe_ratio > 1 else ("Fair" if metrics.sharpe_ratio > 0 else "Poor")),
                "drawdown_status": "Safe" if metrics.current_drawdown < 5 else ("Warning" if metrics.current_drawdown < 10 else "Critical"),
                "profit_factor_quality": "Excellent" if metrics.profit_factor > 2 else ("Good" if metrics.profit_factor > 1.5 else ("Fair" if metrics.profit_factor > 1 else "Losing"))
            }
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/risk-management/reset-daily")
async def reset_daily_counters():
    """Reset daily trading counters."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        rm.reset_daily()
        return {"success": True, "message": "Daily counters reset", "daily_start_balance": rm.daily_start_balance}
    except Exception as e:
        return {"success": False, "error": str(e)}


@api_router.post("/risk-management/force-resume")
async def force_resume_trading():
    """Force resume trading after a pause (use with caution)."""
    try:
        from risk_management_system import get_risk_manager
        rm = get_risk_manager()
        rm.force_resume()
        return {"success": True, "message": "Trading force resumed - use caution!", "risk_level": rm.risk_level.value}
    except Exception as e:
        return {"success": False, "error": str(e)}

# =====================================================
# REAL-TIME MARKET DATA ENDPOINTS
# =====================================================

@api_router.get("/market/realtime/{symbol}")
async def get_realtime_market_data(symbol: str):
    """
    Get real-time market data for a symbol
    Returns current price, bid, ask, volume with data quality metrics
    """
    try:
        data = await realtime_market_hub.get_realtime_price(symbol)
        
        if data:
            return {
                "success": True,
                "data": data,
                "message": f"Real-time data from {data['source']}"
            }
        else:
            return {
                "success": False,
                "error": "No real-time data available",
                "message": f"Unable to fetch data for {symbol} from any source"
            }
    except Exception as e:
        logger.error(f"Error getting real-time data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/market/candles/{symbol}")
async def get_market_candles(symbol: str, interval: str = "1m", limit: int = 100):
    """
    Get historical candlestick data
    interval: 1m, 5m, 15m, 1h, 4h, 1d
    limit: number of candles (default 100, max 1000)
    """
    try:
        if limit > 1000:
            limit = 1000
        
        candles = await realtime_market_hub.get_historical_candles(symbol, interval, limit)
        
        if candles:
            return {
                "success": True,
                "symbol": symbol,
                "interval": interval,
                "count": len(candles),
                "candles": [
                    {
                        'timestamp': c['timestamp'].isoformat(),
                        'open': c['open'],
                        'high': c['high'],
                        'low': c['low'],
                        'close': c['close'],
                        'volume': c['volume']
                    } for c in candles
                ]
            }
        else:
            return {
                "success": False,
                "error": "No candle data available",
                "message": f"Unable to fetch candles for {symbol}"
            }
    except Exception as e:
        logger.error(f"Error getting candles for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/market/depth/{symbol}")
async def get_market_depth(symbol: str):
    """
    Get order book depth and volume analysis
    Only available for cryptocurrencies
    """
    try:
        depth = await realtime_market_hub.get_market_depth(symbol)
        
        if depth:
            return {
                "success": True,
                "symbol": symbol,
                "data": depth
            }
        else:
            return {
                "success": False,
                "error": "Market depth not available",
                "message": f"Order book data not available for {symbol}"
            }
    except Exception as e:
        logger.error(f"Error getting market depth for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/market/analytics/{symbol}")
async def get_market_analytics(symbol: str):
    """
    Get comprehensive market analytics
    - Real-time price
    - Recent candles with technical indicators
    - Volume analysis
    - Trend detection
    """
    try:
        # Get real-time price
        price_data = await realtime_market_hub.get_realtime_price(symbol)
        
        # Get recent candles for analysis
        candles = await realtime_market_hub.get_historical_candles(symbol, '5m', 50)
        
        if not price_data or not candles:
            return {
                "success": False,
                "error": "Insufficient data",
                "message": "Unable to generate analytics"
            }
        
        # Calculate technical indicators
        df = pd.DataFrame(candles)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Moving averages
        ma20 = df['close'].rolling(20).mean()
        ma50 = df['close'].rolling(50).mean() if len(df) >= 50 else None
        
        # Volume analysis
        avg_volume = df['volume'].mean()
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Trend detection
        current_price = df['close'].iloc[-1]
        trend = "bullish" if current_price > ma20.iloc[-1] else "bearish"
        
        # Volatility (ATR)
        high_low = df['high'] - df['low']
        atr = high_low.rolling(14).mean()
        
        analytics = {
            "price": {
                "current": price_data['price'],
                "bid": price_data['bid'],
                "ask": price_data['ask'],
                "spread": price_data.get('spread', 0),
                "quality": price_data.get('quality', 'unknown')
            },
            "indicators": {
                "rsi": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
                "ma20": float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else None,
                "ma50": float(ma50.iloc[-1]) if ma50 is not None and not pd.isna(ma50.iloc[-1]) else None,
                "atr": float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None
            },
            "volume": {
                "current": float(current_volume),
                "average": float(avg_volume),
                "ratio": float(volume_ratio),
                "signal": "high" if volume_ratio > 1.5 else "normal" if volume_ratio > 0.7 else "low"
            },
            "trend": {
                "direction": trend,
                "strength": "strong" if abs(current_price - ma20.iloc[-1]) / ma20.iloc[-1] > 0.02 else "weak"
            },
            "data_source": price_data['source'],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "success": True,
            "symbol": symbol,
            "analytics": analytics
        }
        
    except Exception as e:
        logger.error(f"Error generating analytics for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/market/quality-report")
async def get_data_quality_report():
    """
    Get data quality report
    Shows API usage, cache status, and data source health
    """
    try:
        report = realtime_market_hub.get_quality_report()
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        logger.error(f"Error getting quality report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/market/multi-symbol")
async def get_multi_symbol_data(symbols: str):
    """
    Get real-time data for multiple symbols
    symbols: comma-separated list (e.g., "BTCUSD,ETHUSD,EURUSD")
    """
    try:
        symbol_list = [s.strip() for s in symbols.split(',')]
        
        results = {}
        tasks = [realtime_market_hub.get_realtime_price(symbol) for symbol in symbol_list]
        data_list = await asyncio.gather(*tasks)
        
        for symbol, data in zip(symbol_list, data_list):
            if data:
                results[symbol] = data
            else:
                results[symbol] = {"error": "No data available"}
        
        return {
            "success": True,
            "count": len(results),
            "data": results
        }
    except Exception as e:
        logger.error(f"Error getting multi-symbol data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== POCKET OPTION API ENDPOINTS ====================


class QuickAuthTestRequest(BaseModel):
    auth_message: str

# =============================================================================

# ============================================================================
# MARKET REGIME DETECTOR & TRADE RESULT TRACKING
# ============================================================================

@api_router.post("/trading/record-result")
async def trading_record_result(request: Request):
    """
    Record a trade result to update the Market Regime Detector
    
    This endpoint is critical for the streak-breaking logic. Call it after each trade:
    - win: true/false
    - signal_id: optional - the signal ID that generated this trade
    - direction: CALL/PUT or BUY/SELL
    - symbol: trading symbol
    
    The regime detector will use this to:
    1. Track win/loss streaks
    2. Automatically invert signals after consecutive losses
    3. Adapt to market regime changes
    """
    try:
        data = await request.json()
        
        direction = data.get('direction', 'CALL')
        symbol = data.get('symbol', 'EURUSD')
        is_win = data.get('win', False)
        signal_id = data.get('signal_id', None)
        
        # Get regime detector
        regime_detector = get_regime_detector()
        
        if not regime_detector:
            return {
                "success": False,
                "error": "Market Regime Detector not initialized"
            }
        
        # Record the trade result
        regime_detector.record_trade_result(direction, symbol, is_win)
        
        # Get updated status
        status = regime_detector.get_status()
        
        # Log the result
        result_emoji = "✅" if is_win else "❌"
        logger.info(f"{result_emoji} Trade result recorded: {symbol} {direction} = {'WIN' if is_win else 'LOSS'}")
        logger.info(f"📊 Streak: {status['current_streak']} | Inversion: {'ACTIVE' if status['streak_inversion_active'] else 'inactive'} | Win Rate: {status['recent_win_rate']:.1f}%")
        
        # Save to database for persistence
        await db.trade_results.insert_one({
            "signal_id": signal_id,
            "direction": direction,
            "symbol": symbol,
            "is_win": is_win,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "streak_at_time": status['current_streak'],
            "win_rate_at_time": status['recent_win_rate']
        })
        
        return {
            "success": True,
            "message": f"Trade result recorded: {'WIN' if is_win else 'LOSS'}",
            "regime_status": status,
            "streak_inversion_active": status['streak_inversion_active'],
            "current_streak": status['current_streak'],
            "recent_win_rate": status['recent_win_rate']
        }
        
    except Exception as e:
        logger.error(f"Error recording trade result: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.get("/trading/regime-status")
async def trading_regime_status():
    """
    Get current Market Regime Detector status
    
    Returns:
    - current_regime: bullish/bearish/neutral
    - current_streak: positive = wins, negative = losses
    - streak_inversion_active: true if signals are being auto-inverted
    - recent_win_rate: win rate of last 10 trades
    """
    try:
        regime_detector = get_regime_detector()
        
        if not regime_detector:
            return {
                "success": False,
                "error": "Market Regime Detector not initialized",
                "status": None
            }
        
        status = regime_detector.get_status()
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting regime status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.post("/trading/reset-streak")
async def trading_reset_streak():
    """
    Manually reset the streak counter and disable streak inversion
    Use this when you want to start fresh
    """
    try:
        regime_detector = get_regime_detector()
        
        if not regime_detector:
            return {
                "success": False,
                "error": "Market Regime Detector not initialized"
            }
        
        # Reset streak tracking
        regime_detector.current_streak = 0
        regime_detector.streak_inversion_active = False
        regime_detector.win_loss_history.clear()
        
        logger.info("🔄 Market Regime Detector streak reset manually")
        
        return {
            "success": True,
            "message": "Streak reset successfully",
            "new_status": regime_detector.get_status()
        }
        
    except Exception as e:
        logger.error(f"Error resetting streak: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.get("/trading/accuracy-stats")
async def get_accuracy_statistics():
    """
    Get comprehensive accuracy statistics based on recorded trade results
    
    Returns:
    - overall_win_rate: Win rate across all trades
    - recent_win_rate: Win rate of last 20 trades
    - by_direction: Win rate breakdown by CALL/PUT
    - by_symbol: Win rate breakdown by trading symbol
    - streak_history: Recent streak patterns
    - recommendations: AI-generated trading recommendations
    """
    try:
        # Get regime detector status
        regime_detector = get_regime_detector()
        regime_status = regime_detector.get_status() if regime_detector else {}
        
        # Get historical trade results from database
        trade_results = await db.trade_results.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(100).to_list(100)
        
        if not trade_results:
            return {
                "success": True,
                "total_trades": 0,
                "message": "No trade results recorded yet. Use /api/trading/record-result to track your trades.",
                "regime_status": regime_status
            }
        
        # Calculate statistics
        total_trades = len(trade_results)
        wins = sum(1 for t in trade_results if t.get('is_win', False))
        overall_win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Recent win rate (last 20)
        recent_trades = trade_results[:20]
        recent_wins = sum(1 for t in recent_trades if t.get('is_win', False))
        recent_win_rate = (recent_wins / len(recent_trades) * 100) if recent_trades else 0
        
        # By direction
        calls = [t for t in trade_results if t.get('direction', '').upper() in ['CALL', 'BUY']]
        puts = [t for t in trade_results if t.get('direction', '').upper() in ['PUT', 'SELL']]
        
        call_wins = sum(1 for t in calls if t.get('is_win', False))
        put_wins = sum(1 for t in puts if t.get('is_win', False))
        
        by_direction = {
            'CALL': {
                'total': len(calls),
                'wins': call_wins,
                'win_rate': (call_wins / len(calls) * 100) if calls else 0
            },
            'PUT': {
                'total': len(puts),
                'wins': put_wins,
                'win_rate': (put_wins / len(puts) * 100) if puts else 0
            }
        }
        
        # By symbol
        symbols = {}
        for trade in trade_results:
            symbol = trade.get('symbol', 'UNKNOWN')
            if symbol not in symbols:
                symbols[symbol] = {'total': 0, 'wins': 0}
            symbols[symbol]['total'] += 1
            if trade.get('is_win', False):
                symbols[symbol]['wins'] += 1
        
        by_symbol = {
            sym: {
                **data,
                'win_rate': (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
            }
            for sym, data in symbols.items()
        }
        
        # Generate recommendations
        recommendations = []
        
        if overall_win_rate < 50:
            recommendations.append("⚠️ Win rate below 50%. Consider: 1) Using higher confidence signals only, 2) Inverting signal direction")
        elif overall_win_rate >= 70:
            recommendations.append("✅ Strong win rate! Continue current strategy.")
        
        if by_direction['CALL']['win_rate'] > by_direction['PUT']['win_rate'] + 15:
            recommendations.append(f"📈 CALL signals performing better ({by_direction['CALL']['win_rate']:.1f}% vs {by_direction['PUT']['win_rate']:.1f}%)")
        elif by_direction['PUT']['win_rate'] > by_direction['CALL']['win_rate'] + 15:
            recommendations.append(f"📉 PUT signals performing better ({by_direction['PUT']['win_rate']:.1f}% vs {by_direction['CALL']['win_rate']:.1f}%)")
        
        if regime_status.get('streak_inversion_active'):
            recommendations.append("🔄 Streak inversion is ACTIVE - signals are being auto-inverted due to recent losses")
        
        return {
            "success": True,
            "total_trades": total_trades,
            "overall_win_rate": round(overall_win_rate, 1),
            "recent_win_rate": round(recent_win_rate, 1),
            "by_direction": by_direction,
            "by_symbol": by_symbol,
            "regime_status": regime_status,
            "recommendations": recommendations,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting accuracy stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# LATENCY CORRECTION CONTROL ENDPOINTS
# ============================================================================

@api_router.get("/latency/status")
async def get_latency_status():
    """
    Get current latency correction status and settings
    
    Returns mode, offsets, and per-timeframe effective buffers
    """
    try:
        from latency_optimizer import latency_optimizer
        
        return {
            "success": True,
            "mode": latency_optimizer.correction_mode.value,
            "auto_correction_offset": latency_optimizer.auto_correction_offset,
            "manual_offset": latency_optimizer.manual_offset_seconds,
            "effective_buffers": {
                "5s": latency_optimizer.get_effective_buffer("5s"),
                "15s": latency_optimizer.get_effective_buffer("15s"),
                "30s": latency_optimizer.get_effective_buffer("30s"),
                "1m": latency_optimizer.get_effective_buffer("1m"),
                "2m": latency_optimizer.get_effective_buffer("2m")
            },
            "timeframe_accuracy": latency_optimizer.timeframe_accuracy,
            "total_latency_ms": latency_optimizer.total_latency_ms,
            "latency_stats": latency_optimizer.get_latency_stats()
        }
        
    except Exception as e:
        logger.error(f"Error getting latency status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.post("/latency/set-mode")
async def set_latency_mode(request: Request):
    """
    Set latency correction mode
    
    Body:
    - mode: 'auto' (default, auto-correction), 'manual', or 'disabled'
    
    AUTO mode (default): System automatically learns from trade results and adjusts timing
    MANUAL mode: User sets a fixed offset for fine-tuning
    DISABLED mode: No latency correction applied
    """
    try:
        data = await request.json()
        mode = data.get('mode', 'auto')
        
        from latency_optimizer import latency_optimizer
        
        result = latency_optimizer.set_mode(mode)
        
        logger.info(f"🔧 Latency mode changed to: {mode}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error setting latency mode: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.post("/latency/set-manual-offset")
async def set_latency_manual_offset(request: Request):
    """
    Set manual latency offset (switches to MANUAL mode)
    
    Body:
    - offset_seconds: Offset in seconds (-10 to +10)
        - Positive: signals arrive later (wait longer before executing)
        - Negative: signals arrive earlier (more lead time for execution)
        - 0: neutral timing
    
    Example: If signals are consistently arriving too late, set a negative offset (e.g., -2.0)
    """
    try:
        data = await request.json()
        offset = float(data.get('offset_seconds', 0.0))
        
        from latency_optimizer import latency_optimizer
        
        result = latency_optimizer.set_manual_offset(offset)
        
        logger.info(f"🎛️ Manual latency offset set to: {offset}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Error setting manual offset: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.post("/latency/record-timing-feedback")
async def record_latency_timing_feedback(request: Request):
    """
    Record timing feedback to improve auto-correction (AUTO mode only)
    
    Body:
    - timeframe: '5s', '15s', '30s', '1m', etc.
    - was_early: true if signal arrived too early (price moved away)
    - was_late: true if signal arrived too late (missed entry)
    - was_win: true if the trade was successful
    
    This feedback helps the system learn optimal timing for each timeframe
    """
    try:
        data = await request.json()
        timeframe = data.get('timeframe', '5s')
        was_early = data.get('was_early', False)
        was_late = data.get('was_late', False)
        was_win = data.get('was_win', False)
        
        from latency_optimizer import latency_optimizer
        
        latency_optimizer.record_trade_timing_feedback(
            timeframe=timeframe,
            was_early=was_early,
            was_late=was_late,
            was_win=was_win
        )
        
        return {
            "success": True,
            "message": "Timing feedback recorded",
            "mode": latency_optimizer.correction_mode.value,
            "auto_correction_offset": latency_optimizer.auto_correction_offset,
            "timeframe_accuracy": latency_optimizer.timeframe_accuracy.get(timeframe, {})
        }
        
    except Exception as e:
        logger.error(f"Error recording timing feedback: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@api_router.post("/latency/reset")
async def reset_latency_corrections():
    """
    Reset latency corrections to default values
    
    Clears auto-correction history and resets to base values
    """
    try:
        from latency_optimizer import latency_optimizer, LatencyCorrectionMode
        
        # Reset auto-correction
        latency_optimizer.auto_correction_offset = 0.0
        latency_optimizer.manual_offset_seconds = 0.0
        latency_optimizer.auto_correction_history = []
        latency_optimizer.correction_mode = LatencyCorrectionMode.AUTO
        
        # Reset accuracy tracking
        for tf in latency_optimizer.timeframe_accuracy:
            latency_optimizer.timeframe_accuracy[tf] = {
                'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0
            }
        
        logger.info("🔄 Latency corrections reset to defaults")
        
        return {
            "success": True,
            "message": "Latency corrections reset to defaults",
            "mode": "auto",
            "auto_correction_offset": 0.0,
            "manual_offset": 0.0
        }
        
    except Exception as e:
        logger.error(f"Error resetting latency: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# BINARYOPTIONSTOOLS V2 API ENDPOINTS - Direct WebSocket Trading
# ============================================================================

from pydantic import BaseModel
from typing import Optional

class SSIDConnectRequest(BaseModel):
    ssid: str
    demo: bool = False

# =====================================================
# DESKTOP CLIENT BRIDGE ENDPOINTS
# =====================================================
# These endpoints allow the desktop trading client to communicate
# with the cloud server for signals and trade reporting


# Store for pending signals and desktop client status
_desktop_client_state = {
    "connected": False,
    "balance": 0.0,
    "account_type": "demo",
    "last_seen": None,
    "pending_signals": [],
    "executed_trades": []
}

# =====================================================
# AUTO LOGIN SERVICE ENDPOINTS
# =====================================================

from auto_login_service import get_auto_login_service, LoginResult, LoginMethod

# =====================================================
# CUSTOM STRATEGY BUILDER ENDPOINTS
# =====================================================

from custom_strategy_service import get_custom_strategy_service, AVAILABLE_INDICATORS
from custom_strategy_executor import get_strategy_executor

# Initialize custom strategy service
custom_strategy_service = None

async def get_strategy_service():
    """Get or initialize the custom strategy service"""
    global custom_strategy_service
    if custom_strategy_service is None:
        custom_strategy_service = get_custom_strategy_service(db)
    return custom_strategy_service

@api_router.post("/custom-strategies")
async def create_custom_strategy(strategy_data: Dict[str, Any]):
    """
    Create a new custom trading strategy
    
    Example body:
    {
        "name": "RSI Oversold Bounce",
        "description": "Buy when RSI is oversold and crosses above 30",
        "call_conditions": [
            {
                "conditions": [
                    {
                        "indicator": "RSI",
                        "parameters": {"period": 14},
                        "output": "value",
                        "operator": "crosses_above",
                        "compare_to": "value",
                        "compare_value": 30
                    }
                ],
                "logical_operator": "AND"
            }
        ],
        "put_conditions": [
            {
                "conditions": [
                    {
                        "indicator": "RSI",
                        "parameters": {"period": 14},
                        "output": "value",
                        "operator": "crosses_below",
                        "compare_to": "value",
                        "compare_value": 70
                    }
                ],
                "logical_operator": "AND"
            }
        ],
        "timeframes": ["1m", "5m"],
        "assets": ["EURUSD", "BTCUSD"],
        "markets": ["regular"],
        "min_confidence": 75
    }
    """
    try:
        service = await get_strategy_service()
        result = await service.create_strategy(strategy_data)
        return result
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/custom-strategies")
async def get_all_custom_strategies(user_id: str = "default_user"):
    """Get all custom strategies for a user"""
    try:
        service = await get_strategy_service()
        strategies = await service.get_all_strategies(user_id)
        return {
            "success": True,
            "count": len(strategies),
            "strategies": strategies
        }
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# SSID HEALTH MONITOR ENDPOINTS
# =====================================================

from ssid_health_monitor import get_health_monitor, start_health_monitor

# ===============================
# HISTORICAL DATA COLLECTION API
# ===============================
# These endpoints support collecting real market data from Pocket Option
# for training high-accuracy AI/ML models

from historical_data_collector import (
    get_historical_data_collector, 
    initialize_data_collector,
    HistoricalDataCollector
)

# Global data collector instance
_data_collector: Optional[HistoricalDataCollector] = None

async def get_data_collector() -> HistoricalDataCollector:
    """Get or initialize the data collector"""
    global _data_collector
    if _data_collector is None:
        _data_collector = await initialize_data_collector(db)
    return _data_collector


class DataCollectionStartRequest(BaseModel):
    """Request to start data collection"""
    assets: Optional[List[str]] = None
    timeframes: Optional[List[str]] = None


@api_router.post("/data-collector/start")
async def start_data_collection(request: DataCollectionStartRequest = None):
    """
    Start collecting historical market data.
    
    Args:
        assets: List of assets to collect (e.g., ['EURUSD_otc', 'GBPUSD_otc'])
        timeframes: List of timeframes (e.g., ['5s', '1m', '5m'])
    """
    try:
        collector = await get_data_collector()
        
        assets = request.assets if request else None
        timeframes = request.timeframes if request else None
        
        collector.start_collection(assets=assets, timeframes=timeframes)
        
        return {
            "success": True,
            "message": "Data collection started",
            "collecting_assets": collector.collecting_assets or "ALL",
            "collecting_timeframes": collector.collecting_timeframes
        }
    except Exception as e:
        logger.error(f"Error starting data collection: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/data-collector/stop")
async def stop_data_collection():
    """Stop collecting historical market data"""
    try:
        collector = await get_data_collector()
        collector.stop_collection()
        
        return {
            "success": True,
            "message": "Data collection stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping data collection: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/data-collector/tick")
async def receive_tick_data(data: Dict[str, Any]):
    """
    Receive tick data from desktop client.
    
    Expected payload:
    {
        "asset": "EURUSD_otc",
        "timestamp": 1704067200,
        "price": 1.0523
    }
    """
    try:
        collector = await get_data_collector()
        
        await collector.process_tick(
            asset=data.get('asset', 'UNKNOWN'),
            timestamp=data.get('timestamp', 0),
            price=data.get('price', 0.0),
            volume=data.get('volume', 0.0)
        )
        
        return {"success": True}
    except Exception as e:
        logger.debug(f"Error processing tick: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/data-collector/history")
async def receive_history_data(data: Dict[str, Any]):
    """
    Receive historical data batch from desktop client.
    
    Expected payload:
    {
        "asset": "EURUSD_otc",
        "period": 60,
        "history": [[timestamp, price], ...],
        "candles": [[ts, open, close, high, low], ...]
    }
    """
    try:
        collector = await get_data_collector()
        
        saved_count = await collector.process_history(
            asset=data.get('asset', 'UNKNOWN'),
            history_data=data.get('history', []),
            candles_data=data.get('candles', []),
            period=data.get('period', 60)
        )
        
        return {
            "success": True,
            "candles_saved": saved_count
        }
    except Exception as e:
        logger.error(f"Error processing history: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/data-collector/candle")
async def receive_candle_data(data: Dict[str, Any]):
    """
    Receive a complete candle from desktop client.
    
    Expected payload:
    {
        "asset": "EURUSD_otc",
        "timeframe": "1m",
        "candle": {
            "timestamp": 1704067200,
            "open": 1.0520,
            "high": 1.0525,
            "low": 1.0518,
            "close": 1.0523
        }
    }
    """
    try:
        collector = await get_data_collector()
        
        await collector.process_candle(
            asset=data.get('asset', 'UNKNOWN'),
            candle=data.get('candle', {}),
            timeframe=data.get('timeframe', '1m')
        )
        
        return {"success": True}
    except Exception as e:
        logger.debug(f"Error processing candle: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/data-collector/stats")
async def get_collection_stats():
    """Get statistics about collected data"""
    try:
        collector = await get_data_collector()
        stats = await collector.get_collection_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/data-collector/candles/{asset}/{timeframe}")
async def get_collected_candles(
    asset: str,
    timeframe: str,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=1000, ge=1, le=50000)
):
    """
    Retrieve collected candles for an asset/timeframe.
    
    Args:
        asset: Asset symbol (e.g., 'EURUSD_otc')
        timeframe: Timeframe ('5s', '1m', '5m', etc.)
        days: Number of days to retrieve (default 7, max 90)
        limit: Maximum candles to return (default 1000)
    """
    try:
        collector = await get_data_collector()
        
        from datetime import datetime, timezone, timedelta
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        candles = await collector.get_candles(
            asset=asset,
            timeframe=timeframe,
            start_time=start_time,
            limit=limit
        )
        
        return {
            "success": True,
            "asset": asset,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        logger.error(f"Error getting candles: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/data-collector/training-data/{asset}/{timeframe}")
async def get_training_data(
    asset: str,
    timeframe: str,
    days: int = Query(default=7, ge=1, le=90)
):
    """
    Get data formatted for ML training.
    
    Returns arrays suitable for pandas DataFrame construction.
    """
    try:
        collector = await get_data_collector()
        
        data = await collector.get_training_data(
            asset=asset,
            timeframe=timeframe,
            days=days
        )
        
        if not data:
            return {
                "success": False,
                "error": f"Insufficient data for {asset} {timeframe}"
            }
        
        return {
            "success": True,
            **data
        }
    except Exception as e:
        logger.error(f"Error getting training data: {e}")
        return {"success": False, "error": str(e)}


@api_router.get("/data-collector/quality/{asset}/{timeframe}")
async def get_data_quality_report(
    asset: str,
    timeframe: str,
    days: int = Query(default=1, ge=1, le=7)
):
    """
    Get data quality report for an asset/timeframe.
    
    Checks for gaps, anomalies, and completeness.
    """
    try:
        collector = await get_data_collector()
        
        report = await collector.get_data_quality_report(
            asset=asset,
            timeframe=timeframe,
            days=days
        )
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        logger.error(f"Error getting quality report: {e}")
        return {"success": False, "error": str(e)}


@api_router.delete("/data-collector/cleanup")
async def cleanup_old_data(days_to_keep: int = Query(default=30, ge=1, le=365)):
    """Remove data older than specified days"""
    try:
        collector = await get_data_collector()
        deleted_count = await collector.cleanup_old_data(days_to_keep=days_to_keep)
        
        return {
            "success": True,
            "message": f"Removed {deleted_count} old candles",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up data: {e}")
        return {"success": False, "error": str(e)}


# ===============================
# REAL DATA ML TRAINING API
# ===============================
# Endpoints for training high-accuracy models using collected real data

from real_data_trainer import get_real_data_trainer, RealDataTrainer

_ml_trainer: Optional[RealDataTrainer] = None

def get_ml_trainer() -> RealDataTrainer:
    """Get or create ML trainer"""
    global _ml_trainer
    if _ml_trainer is None:
        _ml_trainer = get_real_data_trainer(db)
    return _ml_trainer


class TrainModelRequest(BaseModel):
    """Request to train a model"""
    asset: str
    timeframe: str
    confidence_threshold: Optional[float] = 0.75
    min_samples: Optional[int] = 500

class GenerateSignalRequest(BaseModel):
    """Request to generate a signal"""
    asset: str
    timeframe: str
    candles: List[Dict[str, Any]]

# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class UserLoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    settings: Optional[Dict] = None

# ==========================================
# TELEGRAM BOT ENDPOINTS
# ==========================================

class TelegramMessageRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None

class TelegramSettingsRequest(BaseModel):
    auto_trading_enabled: Optional[bool] = None
    demo_mode: Optional[bool] = None
    trade_amount: Optional[float] = None

# ========================================
# OANDA MARKET DATA ENDPOINTS
# ========================================

class OandaConfigRequest(BaseModel):
    access_token: str
    account_id: str
    environment: str = "practice"

@api_router.post("/oanda/configure")
async def configure_oanda(config: OandaConfigRequest):
    """Configure OANDA API credentials"""
    try:
        oanda_service.access_token = config.access_token
        oanda_service.account_id = config.account_id
        oanda_service.environment = config.environment
        
        if config.environment == "live":
            oanda_service.api_url = "https://api-fxtrade.oanda.com"
            oanda_service.stream_url = "https://stream-fxtrade.oanda.com"
        else:
            oanda_service.api_url = "https://api-fxpractice.oanda.com"
            oanda_service.stream_url = "https://stream-fxpractice.oanda.com"
        
        oanda_service.is_configured = True
        
        # Test connection
        test_result = await oanda_service.test_connection()
        
        return {
            "success": test_result.get("success", False),
            "message": "OANDA configured successfully" if test_result.get("success") else "Configuration saved but connection test failed",
            "connection_test": test_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/status")
async def get_oanda_status():
    """Get OANDA connection status"""
    try:
        if not oanda_service.is_configured:
            return {
                "configured": False,
                "connected": False,
                "message": "OANDA not configured. Please provide API credentials."
            }
        
        test_result = await oanda_service.test_connection()
        
        return {
            "configured": True,
            "connected": test_result.get("success", False),
            "environment": oanda_service.environment,
            "account_info": test_result if test_result.get("success") else None
        }
    except Exception as e:
        return {
            "configured": oanda_service.is_configured,
            "connected": False,
            "error": str(e)
        }

@api_router.get("/oanda/candles/{instrument}")
async def get_oanda_candles(
    instrument: str,
    granularity: str = Query("M1", description="Timeframe (S5, M1, H1, D, etc)"),
    count: int = Query(100, ge=1, le=5000),
    include_indicators: bool = Query(False)
):
    """Fetch historical candlestick data from OANDA"""
    try:
        candles = await oanda_service.get_candles(
            instrument=instrument,
            granularity=granularity,
            count=count
        )
        
        result = {
            "instrument": instrument,
            "granularity": granularity,
            "count": len(candles),
            "candles": [c.to_dict() for c in candles]
        }
        
        if include_indicators and candles:
            ohlcv_data = {
                "open": [c.open for c in candles],
                "high": [c.high for c in candles],
                "low": [c.low for c in candles],
                "close": [c.close for c in candles],
                "volume": [c.volume for c in candles]
            }
            import numpy as np
            for key in ohlcv_data:
                ohlcv_data[key] = np.array(ohlcv_data[key])
            
            indicators = oanda_service.calculate_technical_indicators(candles)
            result["indicators"] = _convert_numpy_types(indicators)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/price/{instrument}")
async def get_oanda_price(instrument: str):
    """Get current price for an instrument"""
    try:
        price = await oanda_service.get_current_price(instrument)
        if price:
            return {"success": True, "price": price}
        else:
            return {"success": False, "error": "Could not fetch price"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/market-snapshot/{instrument}")
async def get_market_snapshot(instrument: str, timeframe: str = "1m"):
    """Get complete market snapshot with price and indicators"""
    try:
        snapshot = await oanda_service.get_market_snapshot(instrument, timeframe)
        if snapshot:
            return {
                "success": True,
                "symbol": snapshot.symbol,
                "timeframe": snapshot.timeframe,
                "current_price": float(snapshot.current_price) if snapshot.current_price else None,
                "bid": float(snapshot.bid) if snapshot.bid else None,
                "ask": float(snapshot.ask) if snapshot.ask else None,
                "spread": float(snapshot.spread) if snapshot.spread else None,
                "indicators": {
                    "sma_20": float(snapshot.sma_20) if snapshot.sma_20 is not None else None,
                    "sma_50": float(snapshot.sma_50) if snapshot.sma_50 is not None else None,
                    "ema_12": float(snapshot.ema_12) if snapshot.ema_12 is not None else None,
                    "ema_26": float(snapshot.ema_26) if snapshot.ema_26 is not None else None,
                    "rsi_14": float(snapshot.rsi_14) if snapshot.rsi_14 is not None else None,
                    "macd": float(snapshot.macd) if snapshot.macd is not None else None,
                    "macd_signal": float(snapshot.macd_signal) if snapshot.macd_signal is not None else None,
                    "bb_upper": float(snapshot.bb_upper) if snapshot.bb_upper is not None else None,
                    "bb_middle": float(snapshot.bb_middle) if snapshot.bb_middle is not None else None,
                    "bb_lower": float(snapshot.bb_lower) if snapshot.bb_lower is not None else None,
                    "atr_14": float(snapshot.atr_14) if snapshot.atr_14 is not None else None
                },
                "trend": {
                    "direction": snapshot.trend_direction,
                    "strength": float(snapshot.trend_strength) if snapshot.trend_strength is not None else None
                },
                "mean_reversion": {
                    "is_overbought": bool(snapshot.is_overbought),
                    "is_oversold": bool(snapshot.is_oversold),
                    "distance_from_mean": float(snapshot.distance_from_mean) if snapshot.distance_from_mean is not None else None
                }
            }
        return {"success": False, "error": "Could not get market snapshot"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class AITrainingRequest(BaseModel):
    instrument: str = "EUR_USD"
    timeframe: str = "M1"
    candle_count: int = 500
class AISignalRequest(BaseModel):
    instrument: str = "EUR_USD"
    timeframe: str = "M1"
    custom_strategy_id: Optional[str] = None
class TradeResultRequest(BaseModel):
    signal_id: str
    outcome: str  # "WIN" or "LOSS"

# ========================================
# ENHANCED OANDA SERVICE ENDPOINTS (oandapyV20)
# ========================================

@api_router.get("/oanda/enhanced/status")
async def get_enhanced_oanda_status():
    """Get enhanced OANDA service status with account details"""
    try:
        result = enhanced_oanda.test_connection()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/enhanced/candles/{instrument}")
async def get_enhanced_candles(
    instrument: str,
    granularity: str = Query("M1", description="Timeframe: S5, M1, M5, M15, H1, H4, D"),
    count: int = Query(100, ge=10, le=5000)
):
    """
    Get candles with full technical analysis using oandapyV20.
    Returns OHLCV data with all indicators pre-calculated.
    """
    try:
        df = enhanced_oanda.get_candles(instrument, granularity, count)
        
        if df.empty:
            return {"success": False, "error": "No data returned"}
        
        # Convert DataFrame to list of dicts with proper serialization
        candles = []
        for idx, row in df.iterrows():
            candle = {
                "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": int(row['volume']),
                "indicators": {}
            }
            
            # Add indicators (handle NaN values)
            indicator_cols = ['sma_10', 'sma_20', 'sma_50', 'ema_12', 'ema_26', 'rsi',
                            'macd', 'macd_signal', 'macd_histogram', 'bb_upper', 'bb_middle',
                            'bb_lower', 'bb_percent', 'atr', 'adx', 'stochastic_k', 'stochastic_d']
            
            for col in indicator_cols:
                if col in row and not pd.isna(row[col]):
                    candle["indicators"][col] = float(row[col])
            
            candles.append(candle)
        
        return {
            "success": True,
            "instrument": instrument,
            "granularity": granularity,
            "count": len(candles),
            "candles": candles[-50:],  # Return last 50 with indicators
            "summary": {
                "latest_close": float(df['close'].iloc[-1]),
                "latest_rsi": float(df['rsi'].iloc[-1]) if 'rsi' in df and not pd.isna(df['rsi'].iloc[-1]) else None,
                "latest_macd": float(df['macd'].iloc[-1]) if 'macd' in df and not pd.isna(df['macd'].iloc[-1]) else None,
                "trend_sma": "BULLISH" if df['close'].iloc[-1] > df['sma_20'].iloc[-1] else "BEARISH" if 'sma_20' in df and not pd.isna(df['sma_20'].iloc[-1]) else "UNKNOWN"
            }
        }
    except Exception as e:
        logger.error(f"Enhanced candles error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class LargeDataRequest(BaseModel):
    instrument: str = "EUR_USD"
    granularity: str = "H1"
    from_time: str  # ISO format: "2024-01-01T00:00:00Z"
    to_time: str    # ISO format: "2024-12-31T23:59:59Z"

@api_router.post("/oanda/enhanced/candles-large")
async def get_large_historical_data(request: LargeDataRequest):
    """
    Fetch large amounts of historical data (>5000 candles).
    Uses InstrumentsCandlesFactory for automatic batching.
    Ideal for AI model training.
    """
    try:
        df = enhanced_oanda.get_candles_large(
            instrument=request.instrument,
            granularity=request.granularity,
            from_time=request.from_time,
            to_time=request.to_time
        )
        
        if df.empty:
            return {"success": False, "error": "No data returned"}
        
        return {
            "success": True,
            "instrument": request.instrument,
            "granularity": request.granularity,
            "total_candles": len(df),
            "date_range": {
                "from": df.index[0].isoformat() if hasattr(df.index[0], 'isoformat') else str(df.index[0]),
                "to": df.index[-1].isoformat() if hasattr(df.index[-1], 'isoformat') else str(df.index[-1])
            },
            "message": f"Fetched {len(df)} candles for AI training"
        }
    except Exception as e:
        logger.error(f"Large data fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/enhanced/prices")
async def get_multi_instrument_prices(
    instruments: str = Query("EUR_USD,GBP_USD,USD_JPY", description="Comma-separated instruments")
):
    """
    Get current prices for multiple instruments.
    Useful for correlation analysis and arbitrage detection.
    """
    try:
        instrument_list = [i.strip() for i in instruments.split(",")]
        prices = enhanced_oanda.get_current_prices(instrument_list)
        
        return {
            "success": True,
            "prices": prices,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/oanda/enhanced/trend-signal/{instrument}")
async def get_trend_signal(
    instrument: str,
    timeframe: str = Query("M1", description="Timeframe for analysis")
):
    """
    Generate comprehensive trend signal using multiple indicators.
    Returns direction, strength, confidence, and trade recommendations.
    """
    try:
        signal = enhanced_oanda.generate_trend_signal(instrument, timeframe)
        
        if signal is None:
            return {"success": False, "error": "Could not generate signal - insufficient data"}
        
        return {
            "success": True,
            "instrument": instrument,
            "timeframe": timeframe,
            "signal": signal.to_dict(),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Trend signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/oanda/enhanced/stream/start")
async def start_price_stream(
    instruments: str = Query("EUR_USD,GBP_USD", description="Comma-separated instruments to stream")
):
    """
    Start real-time price streaming (background thread).
    Prices are cached and can be fetched via /oanda/enhanced/prices
    """
    try:
        instrument_list = [i.strip() for i in instruments.split(",")]
        success = enhanced_oanda.start_price_stream(instrument_list)
        
        return {
            "success": success,
            "message": "Price stream started" if success else "Failed to start stream",
            "instruments": instrument_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/oanda/enhanced/stream/stop")
async def stop_price_stream():
    """Stop the real-time price streaming"""
    try:
        enhanced_oanda.stop_price_stream()
        return {"success": True, "message": "Price stream stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# AUTO SIGNAL GENERATION SYSTEM
# ========================================

# Global state for auto-signal generation
auto_signal_state = {
    "enabled": False,
    "interval_seconds": 15,  # Changed from 60 to 15 seconds for faster signal generation
    "instruments": ["EUR_USD"],
    "timeframe": "M1",
    "min_confidence": 70,
    "last_signal_time": None,
    "signals_generated": 0,
    "task": None
}

async def auto_signal_generator_task():
    """Background task that continuously generates signals using OANDA, Pocket Option, and High-Accuracy strategies"""
    global auto_signal_state
    
    logger.info("🚀 Auto Signal Generator started with High-Accuracy Strategies")
    
    while auto_signal_state["enabled"]:
        try:
            for instrument in auto_signal_state["instruments"]:
                if not auto_signal_state["enabled"]:
                    break
                
                candles = []
                current_price = 0
                
                # Try Pocket Option data first if connected
                po_signal = None
                try:
                    if po_market_data.connection and po_market_data.connection.state.connected:
                        po_symbol = instrument.replace("_", "")
                        market_data = po_market_data.get_market_data(po_symbol)
                        
                        if market_data:
                            current_price = market_data.current_price
                            
                            # Get candles from PO for high-accuracy analysis
                            if po_symbol in po_market_data.candle_history:
                                if "1m" in po_market_data.candle_history[po_symbol]:
                                    candles = [c.to_dict() for c in po_market_data.candle_history[po_symbol]["1m"]]
                        
                        po_result = po_market_data.generate_signal(po_symbol, "1m")
                        if po_result.get("success") and po_result.get("direction") != "HOLD":
                            po_signal = po_result
                            logger.info(f"📊 PO Signal: {po_signal.get('direction')} {po_symbol} ({po_signal.get('confidence', 0):.1f}%)")
                except Exception as e:
                    logger.debug(f"PO signal generation skipped: {e}")
                
                # Generate OANDA trend signal and get candles
                oanda_signal = None
                try:
                    oanda_data = enhanced_oanda.get_candles_with_analysis(instrument, "M1", 100)
                    if oanda_data.get("candles"):
                        if not candles:
                            candles = oanda_data["candles"]
                        if not current_price and candles:
                            current_price = candles[-1].get("close", 0)
                    
                    trend_signal = enhanced_oanda.generate_trend_signal(
                        instrument, 
                        auto_signal_state["timeframe"]
                    )
                    if trend_signal and trend_signal.recommended_action != "HOLD":
                        oanda_signal = {
                            "direction": trend_signal.recommended_action,
                            "confidence": trend_signal.confidence,
                            "entry_price": trend_signal.entry_price,
                            "supporting_indicators": trend_signal.supporting_indicators
                        }
                        logger.info(f"📊 OANDA Signal: {oanda_signal['direction']} {instrument} ({oanda_signal['confidence']:.1f}%)")
                except Exception as e:
                    logger.debug(f"OANDA signal generation skipped: {e}")
                
                # Generate HIGH-ACCURACY signal using advanced strategies
                ha_signal = None
                try:
                    if candles and current_price:
                        ha_result = get_high_accuracy_signal(candles, current_price, expiry=60)
                        if ha_result and ha_result.get("confidence", 0) >= 65:
                            ha_signal = ha_result
                            logger.info(f"🎯 HIGH-ACCURACY Signal: {ha_signal['direction']} ({ha_signal['confidence']:.1f}%) [{ha_signal['confirmations_count']} confirmations]")
                except Exception as e:
                    logger.debug(f"High-accuracy signal generation skipped: {e}")
                
                # Combine all signals using voting and confidence weighting
                final_signal = None
                source = "auto_generator"
                
                signals_available = []
                if ha_signal:
                    signals_available.append(("high_accuracy", ha_signal.get("direction"), ha_signal.get("confidence", 0)))
                if po_signal:
                    signals_available.append(("pocket_option", po_signal.get("direction"), po_signal.get("confidence", 0)))
                if oanda_signal:
                    signals_available.append(("oanda", oanda_signal.get("direction"), oanda_signal.get("confidence", 0)))
                
                if signals_available:
                    # Count votes for each direction
                    call_votes = sum(1 for s in signals_available if s[1] in ["CALL", "BUY"])
                    put_votes = sum(1 for s in signals_available if s[1] in ["PUT", "SELL"])
                    
                    call_conf = sum(s[2] for s in signals_available if s[1] in ["CALL", "BUY"]) / max(1, call_votes) if call_votes else 0
                    put_conf = sum(s[2] for s in signals_available if s[1] in ["PUT", "SELL"]) / max(1, put_votes) if put_votes else 0
                    
                    # Prioritize HIGH-ACCURACY signal if available and strong
                    if ha_signal and ha_signal.get("is_high_probability"):
                        final_signal = {
                            "direction": ha_signal["direction"],
                            "confidence": ha_signal["confidence"],
                            "entry_price": ha_signal.get("entry_price", current_price),
                            "supporting_indicators": ha_signal.get("confirmations", []),
                            "strategy": ha_signal.get("strategy_name", "high_accuracy")
                        }
                        source = "high_accuracy"
                        logger.info(f"✨ Using HIGH-ACCURACY signal with {ha_signal['confirmations_count']} confirmations")
                    
                    # Otherwise use consensus/voting
                    elif call_votes > put_votes and call_conf >= auto_signal_state["min_confidence"]:
                        confidence_boost = 5 if call_votes >= 2 else 0
                        final_signal = {
                            "direction": "CALL",
                            "confidence": min(95, call_conf + confidence_boost),
                            "entry_price": current_price,
                            "supporting_indicators": [f"{s[0]}:{s[1]}" for s in signals_available],
                            "strategy": "consensus"
                        }
                        source = f"consensus_{call_votes}_sources"
                        
                    elif put_votes > call_votes and put_conf >= auto_signal_state["min_confidence"]:
                        confidence_boost = 5 if put_votes >= 2 else 0
                        final_signal = {
                            "direction": "PUT",
                            "confidence": min(95, put_conf + confidence_boost),
                            "entry_price": current_price,
                            "supporting_indicators": [f"{s[0]}:{s[1]}" for s in signals_available],
                            "strategy": "consensus"
                        }
                        source = f"consensus_{put_votes}_sources"
                    
                    # Single source fallback
                    elif len(signals_available) == 1:
                        best = signals_available[0]
                        final_signal = {
                            "direction": best[1],
                            "confidence": best[2],
                            "entry_price": current_price,
                            "supporting_indicators": [],
                            "strategy": best[0]
                        }
                        source = best[0]
                
                # Save signal if meets confidence threshold
                if final_signal and final_signal["confidence"] >= auto_signal_state["min_confidence"]:
                    new_signal = {
                        "id": f"AUTO_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{instrument.replace('_', '')}",
                        "symbol": instrument.replace("_", ""),
                        "direction": final_signal["direction"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "confidence": final_signal["confidence"],
                        "probability": final_signal["confidence"],
                        "expiration_minutes": 1,
                        "strategy": final_signal.get("strategy", "Auto Signal Generator"),
                        "entry_price": final_signal.get("entry_price", 0),
                        "supporting_indicators": final_signal.get("supporting_indicators", []),
                        "source": source
                    }
                    
                    await db.trading_signals.insert_one({**new_signal})
                    auto_signal_state["signals_generated"] += 1
                    auto_signal_state["last_signal_time"] = datetime.now(timezone.utc).isoformat()
                    
                    logger.info(f"📊 Auto-generated signal: {new_signal['direction']} {new_signal['symbol']} ({new_signal['confidence']:.1f}%) [source: {source}]")
            
            # Wait for next interval
            await asyncio.sleep(auto_signal_state["interval_seconds"])
            
        except Exception as e:
            logger.error(f"Auto signal generator error: {e}")
            await asyncio.sleep(10)  # Wait before retrying
    
    logger.info("🛑 Auto Signal Generator stopped")

# ========================================
# TRADINGVIEW WEBHOOK INTEGRATION
# ========================================

class TradingViewAlert(BaseModel):
    """Model for TradingView webhook alerts"""
    ticker: str
    action: str  # "buy", "sell", "call", "put"
    price: Optional[float] = None
    timeframe: Optional[str] = "1m"
    strategy: Optional[str] = "TradingView Alert"
    message: Optional[str] = ""

# ========================================
# METATRADER 5 INTEGRATION (Placeholder)
# ========================================

class MT5Config(BaseModel):
    """MetaTrader 5 configuration"""
    login: int
    password: str
    server: str
    path: Optional[str] = None

class MT5TradeRequest(BaseModel):
    """MT5 trade request"""
    symbol: str
    order_type: str  # "BUY" or "SELL"
    volume: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# MT5 state
mt5_state = {
    "configured": False,
    "connected": False,
    "login": None,
    "server": None
}
class ArbitrageCheckRequest(BaseModel):
    pairs: List[List[str]] = [["EUR_USD", "GBP_USD"], ["EUR_USD", "USD_JPY"]]

@api_router.post("/oanda/enhanced/arbitrage/detect")
async def detect_arbitrage_opportunities(request: ArbitrageCheckRequest):
    """
    Detect potential arbitrage opportunities between correlated pairs.
    """
    try:
        # Convert list of lists to list of tuples
        pairs = [tuple(p) for p in request.pairs]
        opportunities = enhanced_oanda.detect_arbitrage(pairs)
        
        return {
            "success": True,
            "opportunities_found": len(opportunities),
            "opportunities": [o.to_dict() for o in opportunities],
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# TAMPERMONKEY REMOTE CONTROL ENDPOINTS
# ============================================================================

# In-memory storage for Tampermonkey settings (persisted to DB)
tampermonkey_settings = {
    "invert_signals": True,  # DEFAULT: Always invert signals
    "scan_mode": False,
    "auto_trade": True,
    "switch_mode": False,  # Asset switching
    "preferred_expiry": 60,  # Default 60 seconds
    "min_payout": 65,
    "selected_timeframes": ["5s", "15s", "30s", "1m"],
    "auto_generate_enabled": False,
    # NEW: Enhanced control settings
    "selected_strategy": "auto",  # auto, micro_compression, keltner_breakout, etc.
    "signal_source": "app_ai",  # app_ai, tradingview, mt4, mt5, tampermonkey_scan
    "connection_active": False,  # Updated by Tampermonkey heartbeat
    "last_heartbeat": None,  # Last time Tampermonkey checked in
    "favorites_list": [],  # User's favorite assets from PO
    "last_updated": None
}

@api_router.get("/tampermonkey/settings")
async def get_tampermonkey_settings():
    """
    Get current Tampermonkey settings for remote control.
    The Tampermonkey script polls this endpoint to sync settings from the app.
    """
    try:
        # Load from database if available
        stored_settings = await db.tampermonkey_settings.find_one({"_id": "default"})
        if stored_settings:
            for key in tampermonkey_settings:
                if key in stored_settings:
                    tampermonkey_settings[key] = stored_settings[key]
        
        return {
            "success": True,
            "settings": tampermonkey_settings,
            "message": "Tampermonkey settings retrieved"
        }
    except Exception as e:
        logger.error(f"Error getting Tampermonkey settings: {e}")
        return {
            "success": True,
            "settings": tampermonkey_settings,
            "message": "Using default settings"
        }

@api_router.post("/tampermonkey/settings")
async def update_tampermonkey_settings(settings: dict = Body(...)):
    """
    Update Tampermonkey settings from the application UI.
    These settings will be synced to the Tampermonkey script.
    """
    try:
        global tampermonkey_settings
        
        # Update settings
        for key in settings:
            if key in tampermonkey_settings:
                tampermonkey_settings[key] = settings[key]
        
        tampermonkey_settings["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Persist to database
        await db.tampermonkey_settings.update_one(
            {"_id": "default"},
            {"$set": tampermonkey_settings},
            upsert=True
        )
        
        logger.info(f"Tampermonkey settings updated: {settings}")
        
        return {
            "success": True,
            "settings": tampermonkey_settings,
            "message": "Settings updated and will sync to Tampermonkey"
        }
    except Exception as e:
        logger.error(f"Error updating Tampermonkey settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tampermonkey/force-generate")
async def tampermonkey_force_generate(
    timeframe: str = Query("1m", description="Timeframe: 5s, 15s, 30s, 1m, 2m, 3m, 5m"),
    asset: str = Query(None, description="Optional specific asset")
):
    """
    Force generate a signal for Tampermonkey to execute.
    Signal will be inverted based on current invert_signals setting.
    """
    try:
        # Map timeframe to expiry seconds
        timeframe_to_seconds = {
            "5s": 5, "15s": 15, "30s": 30,
            "1m": 60, "2m": 120, "3m": 180, "5m": 300
        }
        
        expiry_seconds = timeframe_to_seconds.get(timeframe, 60)
        
        # Default OTC assets for signal generation
        otc_assets = [
            "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "AUDUSD_OTC",
            "EURJPY_OTC", "GBPJPY_OTC", "EURGBP_OTC", "USDCAD_OTC",
            "USDCHF_OTC", "NZDUSD_OTC", "AUDCAD_OTC"
        ]
        
        # Select asset - use provided or random OTC
        import random
        target_asset = asset if asset else random.choice(otc_assets)
        
        # Generate simple signal (random direction based on time)
        import hashlib
        time_hash = hashlib.md5(f"{datetime.now(timezone.utc).isoformat()}{target_asset}".encode()).hexdigest()
        raw_direction = "CALL" if int(time_hash[0], 16) > 7 else "PUT"
        
        # Create signal
        signal = {
            "id": f"TM_FORCE_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{target_asset}",
            "symbol": target_asset,
            "direction": raw_direction,
            "confidence": 85.0,
            "probability": 85.0,
            "entry_price": 1.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "tampermonkey_force_generate",
            "timeframe": timeframe
        }
        
        # Apply inversion if enabled in settings (DEFAULT: ON)
        if tampermonkey_settings.get("invert_signals", True):
            original_direction = signal["direction"]
            signal["direction"] = "PUT" if original_direction == "CALL" else "CALL"
            signal["inverted"] = True
            signal["original_direction"] = original_direction
            logger.info(f"Signal inverted: {original_direction} -> {signal['direction']}")
        else:
            signal["inverted"] = False
        
        # Set expiry based on timeframe
        signal["expiry_seconds"] = expiry_seconds
        signal["expiration_minutes"] = expiry_seconds / 60
        
        # Save to database for /signals/latest to pick up
        signal_doc = {**signal, "timestamp": datetime.now(timezone.utc).isoformat()}
        signal_doc.pop('_id', None)
        await db.trading_signals.insert_one(signal_doc)
        
        logger.info(f"Force generated signal: {signal['direction']} {signal['symbol']} @ {timeframe}")
        
        return {
            "success": True,
            "signal": signal,
            "inverted": signal.get("inverted", False),
            "message": f"Signal generated for {timeframe} - {'INVERTED' if signal.get('inverted') else 'NORMAL'}"
        }
            
    except Exception as e:
        logger.error(f"Force generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tampermonkey/toggle-inversion")
async def toggle_signal_inversion():
    """
    Toggle signal inversion on/off. When ON, all CALL signals become PUT and vice versa.
    """
    try:
        global tampermonkey_settings
        
        tampermonkey_settings["invert_signals"] = not tampermonkey_settings.get("invert_signals", False)
        tampermonkey_settings["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Persist to database
        await db.tampermonkey_settings.update_one(
            {"_id": "default"},
            {"$set": tampermonkey_settings},
            upsert=True
        )
        
        status = "ENABLED" if tampermonkey_settings["invert_signals"] else "DISABLED"
        logger.info(f"Signal inversion toggled: {status}")
        
        return {
            "success": True,
            "invert_signals": tampermonkey_settings["invert_signals"],
            "message": f"Signal inversion {status}"
        }
    except Exception as e:
        logger.error(f"Error toggling inversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/tampermonkey/status")
async def get_tampermonkey_status():
    """
    Get full Tampermonkey integration status including settings and recent signals.
    """
    try:
        # Get recent signals
        recent_signals = await db.trading_signals.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(5).to_list(5)
        
        # Check connection status (active if heartbeat within 30 seconds)
        connection_active = False
        if tampermonkey_settings.get("last_heartbeat"):
            try:
                last_hb = datetime.fromisoformat(tampermonkey_settings["last_heartbeat"].replace('Z', '+00:00'))
                connection_active = (datetime.now(timezone.utc) - last_hb).total_seconds() < 30
            except:
                pass
        
        return {
            "success": True,
            "settings": tampermonkey_settings,
            "connection_active": connection_active,
            "recent_signals": recent_signals,
            "endpoints": {
                "settings": "/api/tampermonkey/settings",
                "force_generate": "/api/tampermonkey/force-generate",
                "toggle_inversion": "/api/tampermonkey/toggle-inversion",
                "heartbeat": "/api/tampermonkey/heartbeat",
                "script_url": "https://pocket-option-auto-2.preview.emergentagent.com/pocket-option-auto-trader.user.js"
            }
        }
    except Exception as e:
        logger.error(f"Error getting Tampermonkey status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tampermonkey/heartbeat")
async def tampermonkey_heartbeat(data: dict = Body(default={})):
    """
    Heartbeat endpoint for Tampermonkey to report its status and sync settings.
    Called every 10 seconds by the userscript.
    """
    try:
        global tampermonkey_settings
        
        # Update heartbeat timestamp
        tampermonkey_settings["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        tampermonkey_settings["connection_active"] = True
        
        # Update favorites list if provided
        if "favorites" in data:
            tampermonkey_settings["favorites_list"] = data["favorites"]
        
        # Update current asset if provided
        if "current_asset" in data:
            tampermonkey_settings["current_asset"] = data["current_asset"]
        
        # Persist to database
        await db.tampermonkey_settings.update_one(
            {"_id": "default"},
            {"$set": tampermonkey_settings},
            upsert=True
        )
        
        return {
            "success": True,
            "settings": tampermonkey_settings,
            "message": "Heartbeat received"
        }
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        return {"success": False, "message": str(e)}

@api_router.get("/tampermonkey/strategies")
async def get_tampermonkey_strategies():
    """
    Get available strategies for Tampermonkey to use.
    """
    try:
        strategies = [
            {"id": "auto", "name": "Auto (AI Selection)", "description": "AI automatically selects best strategy"},
            {"id": "micro_compression", "name": "Micro Compression", "timeframes": ["5s"], "description": "Quick 5s scalping"},
            {"id": "keltner_breakout", "name": "Keltner Breakout", "timeframes": ["5s", "15s"], "description": "Volatility breakouts"},
            {"id": "candlestick_patterns", "name": "Candlestick Patterns", "timeframes": ["5s", "15s", "30s"], "description": "Classic patterns"},
            {"id": "triple_supertrend", "name": "Triple SuperTrend", "timeframes": ["1m", "2m"], "description": "Multi-timeframe trend"},
            {"id": "ema_pullback", "name": "EMA Pullback", "timeframes": ["1m", "3m"], "description": "Trend pullbacks"},
            {"id": "zigzag_double_ma", "name": "ZigZag + Double MA", "timeframes": ["1m", "5m"], "description": "Swing reversals"},
            {"id": "rsi_divergence", "name": "RSI Divergence", "timeframes": ["15s", "30s", "1m"], "description": "Momentum divergence"},
            {"id": "macd_crossover", "name": "MACD Crossover", "timeframes": ["30s", "1m", "2m"], "description": "Trend momentum"},
            {"id": "bollinger_squeeze", "name": "Bollinger Squeeze", "timeframes": ["15s", "30s", "1m"], "description": "Volatility expansion"}
        ]
        
        return {
            "success": True,
            "strategies": strategies
        }
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        return {"success": False, "strategies": []}

# Tampermonkey win/loss stats storage
tampermonkey_stats = {
    "wins": 0,
    "losses": 0,
    "consecutive_wins": 0,
    "consecutive_losses": 0,
    "session_profit": 0,
    "last_result": None,
    "auto_invert_active": False,
    "trade_history": [],
    "last_updated": None
}

@api_router.post("/tampermonkey/stats")
async def update_tampermonkey_stats(stats: dict = Body(...)):
    """
    Receive and store win/loss stats from Tampermonkey.
    """
    try:
        global tampermonkey_stats
        
        # Update stats
        for key in stats:
            if key in tampermonkey_stats:
                tampermonkey_stats[key] = stats[key]
        
        tampermonkey_stats["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Persist to database
        await db.tampermonkey_stats.update_one(
            {"_id": "session"},
            {"$set": tampermonkey_stats},
            upsert=True
        )
        
        logger.info(f"Tampermonkey stats updated: W:{stats.get('wins', 0)} L:{stats.get('losses', 0)} P/L:${stats.get('session_profit', 0):.2f}")
        
        return {
            "success": True,
            "stats": tampermonkey_stats,
            "message": "Stats updated"
        }
    except Exception as e:
        logger.error(f"Stats update error: {e}")
        return {"success": False, "message": str(e)}

@api_router.get("/tampermonkey/stats")
async def get_tampermonkey_stats():
    """
    Get current win/loss stats from Tampermonkey.
    """
    try:
        # Load from database if available
        stored_stats = await db.tampermonkey_stats.find_one({"_id": "session"}, {"_id": 0})
        if stored_stats:
            for key in tampermonkey_stats:
                if key in stored_stats:
                    tampermonkey_stats[key] = stored_stats[key]
        
        return {
            "success": True,
            "stats": tampermonkey_stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"success": True, "stats": tampermonkey_stats}

@api_router.post("/tampermonkey/stats/reset")
async def reset_tampermonkey_stats():
    """
    Reset win/loss stats.
    """
    try:
        global tampermonkey_stats
        
        tampermonkey_stats = {
            "wins": 0,
            "losses": 0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "session_profit": 0,
            "last_result": None,
            "auto_invert_active": False,
            "trade_history": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        await db.tampermonkey_stats.update_one(
            {"_id": "session"},
            {"$set": tampermonkey_stats},
            upsert=True
        )
        
        return {
            "success": True,
            "stats": tampermonkey_stats,
            "message": "Stats reset"
        }
    except Exception as e:
        logger.error(f"Error resetting stats: {e}")
        return {"success": False, "message": str(e)}


# Include the router in the main app
# ============================================================================
# INCLUDE MODULAR ROUTE FILES
# ============================================================================
from routes.strategies import router as strategies_router
from routes.signals import router as signals_router
from routes.ml import router as ml_router
from routes.backtest import router as backtest_router
from routes.auth import router as auth_router
from routes.pocket_option import router as pocket_option_router
from routes.integrations import router as integrations_router
from routes.trading import router as trading_router

api_router.include_router(strategies_router)
api_router.include_router(signals_router)
api_router.include_router(ml_router)
api_router.include_router(backtest_router)
api_router.include_router(auth_router)
api_router.include_router(pocket_option_router)
api_router.include_router(integrations_router)
api_router.include_router(trading_router)

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
            # Initialize signal validator
            await signal_validator.initialize()
            # Initialize AI learning system
            await ai_learning_system.initialize()
            # Initialize Telegram notifier
            await initialize_telegram_notifier()
            logger.info("📱 Telegram notifier initialized")
            
            # Create default admin user
            auth_service = get_auth_service(db)
            await auth_service.create_default_admin()
            logger.info("👤 Auth service initialized")
            
            # Initialize Telegram bot service
            telegram_bot = get_telegram_bot(db)
            logger.info("🤖 Telegram bot service initialized")
            
            # Initialize 3Commas service
            await initialize_threecommas_service(db)
            logger.info("📊 3Commas service initialized")
            
            # Initialize Market Regime Detector
            await initialize_regime_detector(db)
            logger.info("📈 Market Regime Detector initialized")
            
            app_initialized = True
            logger.info("✅ Application initialization complete")
        except Exception as e:
            logger.error(f"❌ Error during initialization: {e}")
            app_initialized = False
    
    # Start initialization in background (non-blocking)
    import asyncio
    asyncio.create_task(initialize_app())
    
    # Start AI learning scheduler (runs every hour)
    async def ai_learning_scheduler():
        """Background task that runs AI learning every hour"""
        await asyncio.sleep(60)  # Wait 1 minute after startup
        while True:
            try:
                logger.info("🧠 Running scheduled AI learning cycle...")
                await ai_learning_system.analyze_and_learn()
                logger.info("✅ Scheduled AI learning completed")
            except Exception as e:
                logger.error(f"❌ Error in scheduled AI learning: {e}")
            
            # Wait 1 hour before next cycle
            await asyncio.sleep(3600)
    
    asyncio.create_task(ai_learning_scheduler())
    
    # Return immediately so server can start accepting health checks
    logger.info("⚡ Server startup complete - initialization running in background")

@app.on_event("shutdown")
async def shutdown_db_client():
    # Stop trading bot
    await trading_bot.stop_bot()
    # Cleanup signal validator
    await signal_validator.cleanup()
    # Cleanup AI learning system
    await ai_learning_system.cleanup()
    # Shutdown SSID service
    await shutdown_ssid_service()
    # Shutdown Telegram notifier
    await shutdown_telegram_notifier()
    # Close database connection
    client.close()