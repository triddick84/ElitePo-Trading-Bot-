from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone

# Import our trading bot components
from models import (
    TradingSignal, MarketData, TechnicalIndicators, TradingConfiguration,
    PerformanceMetrics, BacktestResult, TradingStrategy, TradingMode, AssetType
)
from trading_bot_service import TradingBotService
from real_market_data_service import RealMarketDataService
from platform_integrations import platform_integration
from force_signal_generator import force_signal_generator

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
    """Stop the trading bot"""
    try:
        await trading_bot.stop_bot()
        return {"status": "success", "message": "Trading bot stopped"}
        
    except Exception as e:
        logging.error(f"Error stopping bot: {e}")
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
            performance=performance
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
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "bot_running": trading_bot.is_running,
        "timestamp": datetime.utcnow().isoformat()
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
async def force_generate_signal():
    """
    Force generate a trading signal using maximum analysis depth
    Bypasses all thresholds and uses advanced multi-strategy analysis
    """
    try:
        # Get current market data for configured assets
        market_data = await trading_bot._get_relevant_market_data()
        
        if not market_data:
            # Create emergency market data for force generation
            from models import MarketData, AssetType
            logger.warning("No market data available - creating emergency market data for force generation")
            target_asset = MarketData(
                symbol="EURUSD",
                price=1.0500,  # Default price
                timestamp=datetime.now(timezone.utc),
                asset_type=AssetType.FOREX,
                volume=0
            )
        else:
            # Use the first available asset for force generation
            target_asset = market_data[0]
        
        logger.info(f"🚀 FORCE GENERATING SIGNAL for {target_asset.symbol} using maximum analysis depth")
        
        # Get user's selected timeframes from current configuration
        try:
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            user_timeframes = config_doc.get('selected_timeframes', ['5m']) if config_doc else ['5m']
            
            # If no timeframes are selected, use ultra-short default
            if not user_timeframes or len(user_timeframes) == 0:
                user_timeframes = ['5s']  # Default to ultra-short 5 second timeframe
                logger.info("No timeframes selected, using ultra-short 5s default")
        except Exception as e:
            logger.warning(f"Could not get user timeframes, using default: {e}")
            user_timeframes = ['5s']
        
        logger.info(f"Using user selected timeframes: {user_timeframes}")
        
        # Force generate signals using advanced algorithms (both regular and OTC)
        forced_signals = await force_signal_generator.force_generate_signal(
            target_asset.symbol, target_asset, user_timeframes
        )
        
        if forced_signals:
            stored_signals = []
            
            # Store all forced signals in database
            for signal in forced_signals:
                signal_dict = signal.dict()
                signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
                signal_dict['precision_entry_time'] = signal_dict['precision_entry_time'].isoformat() if signal_dict['precision_entry_time'] else None
                # Convert numpy types for JSON serialization
                signal_dict = _convert_numpy_types(signal_dict)
                await db.trading_signals.insert_one(signal_dict)
                
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
            
            response = {
                "success": True,
                "message": f"🚀 {len(forced_signals)} Force signals generated with maximum analysis depth",
                "signals": stored_signals,
                "regular_signal": next((s for s in stored_signals if "regular" in s["symbol"]), None),
                "otc_signal": next((s for s in stored_signals if "OTC" in s["symbol"]), None),
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
async def force_generate_signal_for_asset(asset_symbol: str):
    """
    Force generate a signal for a specific asset
    Uses maximum analysis depth and bypasses all thresholds
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
            target_data = market_data_service.get_real_time_data(asset_symbol, asset_type.value)
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
            
            # If no timeframes are selected, use ultra-short default
            if not user_timeframes or len(user_timeframes) == 0:
                user_timeframes = ['5s']  # Default to ultra-short 5 second timeframe
                logger.info("No timeframes selected, using ultra-short 5s default")
        except Exception as e:
            logger.warning(f"Could not get user timeframes, using default: {e}")
            user_timeframes = ['5s']
        
        logger.info(f"Using user selected timeframes for {asset_symbol}: {user_timeframes}")
        
        # Force generate signals (both regular and OTC)
        forced_signals = await force_signal_generator.force_generate_signal(
            target_data.symbol, target_data, user_timeframes
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
                    "technical_analysis": _convert_numpy_types(signal.technical_analysis) if signal.technical_analysis else {},
                    "forced_generation": True,
                    "timestamp": signal.timestamp.isoformat()
                })
                
                # Send to platforms
                try:
                    await platform_integration.send_signal_to_all_platforms(signal)
                except Exception as e:
                    logger.warning(f"Could not send forced signal to platforms: {e}")
            
            # Extract analysis details with OTC boost information
            analysis_details = forced_signals[0].technical_analysis if forced_signals else {}
            otc_signal = next((s for s in forced_signals if s.market_type == 'otc'), None)
            if otc_signal:
                analysis_details["otc_boost_applied"] = otc_signal.technical_analysis.get('otc_boost_applied', 0)
            
            response = {
                "success": True,
                "message": f"🚀 {len(forced_signals)} Force signals generated for {asset_symbol} (Regular + OTC)",
                "asset": asset_symbol,
                "signals": stored_signals,
                "regular_signal": next((s for s in stored_signals if "regular" in s["symbol"]), None),
                "otc_signal": next((s for s in stored_signals if "OTC" in s["symbol"]), None),
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

# Legacy endpoints for compatibility
@api_router.get("/")
async def root():
    return {"message": "GPT Signal Bot API - Advanced AI Trading System"}

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

@app.on_event("startup")
async def startup_event():
    # Ensure trading bot configuration is loaded
    await trading_bot._load_config()

@app.on_event("shutdown")
async def shutdown_db_client():
    # Stop trading bot
    await trading_bot.stop_bot()
    # Close database connection
    client.close()