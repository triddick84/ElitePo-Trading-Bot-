import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
import json

from motor.motor_asyncio import AsyncIOMotorDatabase
from models import (
    TradingSignal, MarketData, TechnicalIndicators, SentimentAnalysis,
    TradingConfiguration, PerformanceMetrics, BacktestResult, 
    TradingStrategy, TradingMode, AssetType, SignalDirection
)
from real_market_data_service import RealMarketDataService
from advanced_technical_analysis import AdvancedTechnicalAnalysis
from enhanced_signal_generator import enhanced_signal_generator
from force_signal_generator import force_signal_generator
from pocket_option_timing_sync import pocket_option_sync
from llm_service import LLMTradingService
from platform_integrations import PlatformIntegrationService
from timezone_utils import get_chicago_time

logger = logging.getLogger(__name__)

class TradingBotService:
    """Main trading bot orchestration service"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.market_service = RealMarketDataService()
        self.technical_engine = AdvancedTechnicalAnalysis()
        self.llm_service = LLMTradingService()
        self.platform_integration = PlatformIntegrationService()
        
        self.is_running = False
        self.current_signals = []
        self.performance_metrics = {}
        self.auto_signal_generation = False  # Flag for automated signal generation
        self.candle_sync_enabled = False  # Flag for candle formation synchronization
        self.candle_scheduler = None  # Will be set when candle sync is enabled
        
        # Default configuration - will be loaded from database if available
        self.config = TradingConfiguration()
        
        # Load saved configuration on initialization
        asyncio.create_task(self._load_config())
    
    async def start_bot(self, config: Optional[TradingConfiguration] = None):
        """Start the trading bot with given configuration"""
        if config:
            self.config = config
            await self._save_config()
        
        if self.is_running:
            logger.info("Bot is already running")
            return
            
        self.is_running = True
        logger.info(f"Starting trading bot in {self.config.trading_mode} mode")
        
        # Initialize platform integrations
        await self.platform_integration.initialize_integrations()
        
        # Start main trading loop in background
        asyncio.create_task(self._trading_loop())
    
    async def stop_bot(self):
        """Stop the trading bot"""
        self.is_running = False
        logger.info("Trading bot stopped")
    
    async def _trading_loop(self):
        """Main trading loop - runs continuously when bot is active"""
        signal_count = 0
        
        while self.is_running:
            try:
                # Only generate signals automatically if auto_signal_generation is enabled
                if not self.auto_signal_generation:
                    await asyncio.sleep(5)  # Check every 5 seconds if auto generation should start
                    continue
                
                # Check daily trading limits
                today_signals = await self._get_today_signals_count()
                if today_signals >= self.config.max_daily_trades:
                    logger.info(f"Daily trading limit reached ({today_signals}/{self.config.max_daily_trades})")
                    await asyncio.sleep(3600)  # Wait 1 hour before checking again
                    continue
                
                # Get market data for configured assets
                market_data = await self._get_relevant_market_data()
                
                # Generate signals for each asset
                for asset_data in market_data:
                    try:
                        signal = await self._generate_signal_for_asset(asset_data)
                        if signal:
                            await self._process_new_signal(signal)
                            signal_count += 1
                            logger.info(f"Generated signal #{signal_count}: {signal.symbol} {signal.direction} at {signal.entry_price}")
                    
                    except Exception as e:
                        logger.error(f"Error processing asset {asset_data.symbol}: {e}")
                
                # Update performance metrics
                await self._update_performance_metrics()
                
                # Wait before next cycle (adjust based on strategy)
                await asyncio.sleep(self._get_cycle_interval())
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _generate_signal_for_asset(self, market_data: MarketData) -> Optional[TradingSignal]:
        """Generate trading signal for a specific asset using enhanced algorithms"""
        try:
            logger.info(f"Analyzing {market_data.symbol} at {market_data.price} using enhanced algorithms")
            
            # Step 1: Technical Analysis
            technical_indicators = await self.technical_engine.analyze_symbol_comprehensive(market_data.symbol, market_data)
            
            # Step 2: Enhanced Signal Generation (Primary)
            # Use advanced multi-strategy algorithm for high accuracy
            enhanced_signal = await enhanced_signal_generator.generate_enhanced_signal(
                market_data.symbol, market_data, technical_indicators
            )
            
            # Apply Pocket Option timing synchronization if signal was generated
            if enhanced_signal:
                enhanced_signal = pocket_option_sync.sync_signal_with_pocket_option_timing(
                    enhanced_signal, self.config.selected_timeframes
                )
            
            if enhanced_signal and enhanced_signal.probability >= self.config.min_probability_threshold:
                logger.info(f"Enhanced algorithm generated high-confidence signal: {enhanced_signal.symbol} "
                           f"{enhanced_signal.direction} at {enhanced_signal.probability}%")
                return enhanced_signal
            
            # Step 3: Fallback to LLM-assisted analysis if enhanced algorithm doesn't find high-confidence signal
            logger.info(f"Enhanced algorithm didn't generate signal above threshold ({self.config.min_probability_threshold}%), "
                       f"trying LLM-assisted analysis")
            
            # Analyze sentiment with technical indicators
            sentiment = await self.llm_service.analyze_sentiment(market_data.symbol, market_data, technical_indicators)
            
            # Generate signal for each configured strategy
            best_signal = None
            highest_probability = 0
            
            for strategy in self.config.active_strategies:
                signal = await self.llm_service.generate_trading_signal(
                    market_data, technical_indicators, sentiment, strategy
                )
                
                if signal and signal.probability > highest_probability:
                    best_signal = signal
                    highest_probability = signal.probability
            
            # Step 4: Generate signal based on combined analysis (fallback)
            if best_signal and best_signal.probability >= self.config.min_probability_threshold:
                # Mark as fallback signal
                best_signal.strategy_used = f"llm_fallback_{best_signal.strategy_used}"
                best_signal.justification = f"[FALLBACK] {best_signal.justification}"
                
                # Apply Pocket Option timing synchronization to fallback signal
                best_signal = pocket_option_sync.sync_signal_with_pocket_option_timing(
                    best_signal, self.config.selected_timeframes
                )
                
                logger.info(f"Fallback LLM signal generated: {best_signal.symbol} "
                           f"{best_signal.direction} at {best_signal.probability}%")
                return best_signal
            
            logger.info(f"No signals above threshold for {market_data.symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error generating signal for {market_data.symbol}: {e}")
            return None
    
    async def _get_relevant_market_data(self) -> List[MarketData]:
        """Get market data for configured asset types"""
        all_data = await self.market_service.get_all_market_data()
        
        relevant_data = []
        for asset_type in self.config.target_assets:
            asset_key = asset_type.value
            if asset_key in all_data:
                relevant_data.extend(all_data[asset_key])
        
        return relevant_data
    
    async def _process_new_signal(self, signal: TradingSignal):
        """Process and store new trading signal"""
        try:
            # Apply signal inversion if enabled in configuration
            if self.config.invert_signals:
                original_direction = signal.direction
                if signal.direction in [SignalDirection.BUY, SignalDirection.CALL]:
                    signal.direction = SignalDirection.SELL
                else:
                    signal.direction = SignalDirection.BUY
                
                # Add inversion note to justification
                signal.justification = f"[INVERTED SIGNAL - Original: {original_direction}] " + signal.justification
                logger.info(f"Signal inverted: {original_direction} -> {signal.direction} for {signal.symbol}")
            
            # Store signal in database
            signal_dict = signal.dict()
            signal_dict['timestamp'] = signal_dict['timestamp'].isoformat()
            await self.db.trading_signals.insert_one(signal_dict)
            
            # Add to current signals list
            self.current_signals.append(signal)
            
            # Send signal to all integrated platforms (Telegram, AutobotSignal, etc.)
            await self.platform_integration.send_signal_to_all_platforms(signal)
            
            # If auto-trading is enabled and in demo mode, simulate trade execution
            if self.config.auto_trading_enabled and self.config.trading_mode == TradingMode.DEMO:
                await self._execute_demo_trade(signal)
                
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _execute_demo_trade(self, signal: TradingSignal):
        """Simulate trade execution for demo mode"""
        try:
            # Simulate trade execution after expiration time
            await asyncio.sleep(signal.expiration_minutes * 60)  # Convert to seconds
            
            # Simulate trade outcome (for demo - use probability for success rate)
            import random
            success_rate = signal.probability / 100.0
            is_winner = random.random() < success_rate
            
            # Calculate P&L
            stake = min(signal.suggested_stake, self.config.max_stake_per_trade)
            if is_winner:
                profit = stake * 0.85  # 85% payout (typical for binary options)
                signal.profit_loss = profit
                signal.actual_outcome = "WIN"
            else:
                signal.profit_loss = -stake
                signal.actual_outcome = "LOSS"
            
            signal.closed_at = datetime.now(timezone.utc)
            
            # Update signal in database
            await self.db.trading_signals.update_one(
                {"id": signal.id},
                {"$set": {
                    "actual_outcome": signal.actual_outcome,
                    "profit_loss": signal.profit_loss,
                    "closed_at": signal.closed_at.isoformat()
                }}
            )
            
            logger.info(f"Demo trade completed: {signal.symbol} {signal.direction} - {signal.actual_outcome} (P&L: ${signal.profit_loss:.2f})")
            
        except Exception as e:
            logger.error(f"Error executing demo trade: {e}")
    
    async def get_active_signals(self) -> List[TradingSignal]:
        """Get currently active trading signals"""
        try:
            # Get recent signals from database
            recent_signals = await self.db.trading_signals.find({
                "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()}
            }).sort("timestamp", -1).limit(50).to_list(length=None)
            
            # Convert to TradingSignal objects
            signals = []
            for signal_data in recent_signals:
                # Convert timestamp back to datetime
                signal_data['timestamp'] = datetime.fromisoformat(signal_data['timestamp'].replace('Z', '+00:00'))
                if signal_data.get('closed_at'):
                    signal_data['closed_at'] = datetime.fromisoformat(signal_data['closed_at'].replace('Z', '+00:00'))
                
                signals.append(TradingSignal(**signal_data))
            
            return signals
            
        except Exception as e:
            logger.error(f"Error getting active signals: {e}")
            return []
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            # Calculate metrics from recent signals
            recent_signals = await self.get_active_signals()
            completed_signals = [s for s in recent_signals if s.actual_outcome is not None]
            
            if not completed_signals:
                return {
                    "total_signals": 0,
                    "win_rate": 0.0,
                    "profit_loss": 0.0,
                    "total_wins": 0,
                    "total_losses": 0
                }
            
            total_signals = len(completed_signals)
            winning_signals = [s for s in completed_signals if s.actual_outcome == "WIN"]
            total_wins = len(winning_signals)
            total_losses = total_signals - total_wins
            
            win_rate = (total_wins / total_signals) * 100 if total_signals > 0 else 0
            total_pnl = sum(s.profit_loss or 0 for s in completed_signals)
            
            # Calculate profit factor
            gross_profits = sum(s.profit_loss for s in winning_signals if s.profit_loss > 0)
            gross_losses = abs(sum(s.profit_loss for s in completed_signals if s.profit_loss < 0))
            profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
            
            return {
                "total_signals": total_signals,
                "win_rate": round(win_rate, 2),
                "profit_loss": round(total_pnl, 2),
                "total_wins": total_wins,
                "total_losses": total_losses,
                "profit_factor": round(profit_factor, 2),
                "average_probability": round(sum(s.probability for s in recent_signals) / len(recent_signals), 2),
                "active_strategies": [s.value for s in self.config.active_strategies],
                "trading_mode": self.config.trading_mode.value
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {"error": str(e)}
    
    async def run_backtest(self, strategy: TradingStrategy, symbol: str, days: int = 30) -> BacktestResult:
        """Run backtesting for a specific strategy"""
        try:
            # Get historical data
            historical_data = await self.market_service.get_historical_data(symbol, days)
            
            if not historical_data:
                raise ValueError(f"No historical data available for {symbol}")
            
            signals_generated = 0
            winning_signals = 0
            total_return = 0.0
            
            # Simulate trading on historical data
            for i in range(len(historical_data) - 1):
                current_data = historical_data[i]
                next_data = historical_data[i + 1]
                
                # Create market data object
                market_data = MarketData(
                    symbol=symbol,
                    asset_type=AssetType.FOREX,  # Default
                    price=current_data['close'],
                    timestamp=datetime.fromisoformat(current_data['timestamp'])
                )
                
                # Generate technical indicators
                technical_indicators = self.technical_engine.analyze_market_data(market_data)
                
                # Generate signal using LLM (with simplified sentiment)
                sentiment = SentimentAnalysis(
                    symbol=symbol,
                    timestamp=market_data.timestamp,
                    sentiment_score=0.0,
                    confidence=0.5
                )
                
                signal = await self.llm_service.generate_trading_signal(
                    market_data, technical_indicators, sentiment, strategy
                )
                
                if signal:
                    signals_generated += 1
                    
                    # Simulate trade outcome
                    entry_price = current_data['close']
                    exit_price = next_data['close']
                    
                    if signal.direction == SignalDirection.BUY and exit_price > entry_price:
                        winning_signals += 1
                        total_return += 0.85  # 85% payout
                    elif signal.direction == SignalDirection.SELL and exit_price < entry_price:
                        winning_signals += 1
                        total_return += 0.85
                    else:
                        total_return -= 1.0  # Loss
            
            # Calculate metrics
            win_rate = (winning_signals / signals_generated) * 100 if signals_generated > 0 else 0
            profit_factor = (winning_signals * 0.85) / ((signals_generated - winning_signals) * 1.0) if (signals_generated - winning_signals) > 0 else float('inf')
            
            backtest_result = BacktestResult(
                strategy=strategy,
                symbol=symbol,
                start_date=datetime.fromisoformat(historical_data[0]['timestamp']),
                end_date=datetime.fromisoformat(historical_data[-1]['timestamp']),
                total_signals=signals_generated,
                winning_signals=winning_signals,
                losing_signals=signals_generated - winning_signals,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_return=total_return
            )
            
            # Store backtest result
            await self.db.backtest_results.insert_one(backtest_result.dict())
            
            return backtest_result
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            raise e
    
    async def _get_today_signals_count(self) -> int:
        """Get count of signals generated today"""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        count = await self.db.trading_signals.count_documents({
            "timestamp": {"$gte": today_start.isoformat()}
        })
        
        return count
    
    async def _save_config(self):
        """Save current configuration to database"""
        try:
            config_dict = self.config.dict()
            config_dict['updated_at'] = config_dict['updated_at'].isoformat()
            
            await self.db.trading_configurations.replace_one(
                {"user_id": self.config.user_id},
                config_dict,
                upsert=True
            )
            logger.info("Configuration saved successfully to database")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    async def _load_config(self):
        """Load saved configuration from database"""
        try:
            # Try to load existing configuration for the user
            saved_config = await self.db.trading_configurations.find_one(
                {"user_id": self.config.user_id}
            )
            
            if saved_config:
                # Remove MongoDB _id field
                saved_config.pop('_id', None)
                
                # Convert updated_at back to datetime
                if 'updated_at' in saved_config:
                    saved_config['updated_at'] = datetime.fromisoformat(saved_config['updated_at'])
                
                # Create new configuration from saved data
                self.config = TradingConfiguration(**saved_config)
                logger.info("Configuration loaded successfully from database")
            else:
                logger.info("No saved configuration found, using defaults")
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Keep using default configuration on error
    
    async def _update_performance_metrics(self):
        """Update performance metrics in database"""
        metrics = await self.get_performance_metrics()
        
        if "error" not in metrics:
            performance_metric = PerformanceMetrics(
                date=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
                total_signals=metrics["total_signals"],
                winning_signals=metrics["total_wins"],
                losing_signals=metrics["total_losses"],
                win_rate=metrics["win_rate"],
                profit_loss=metrics["profit_loss"]
            )
            
            # Store daily metrics
            await self.db.performance_metrics.replace_one(
                {"date": performance_metric.date.isoformat()},
                performance_metric.dict(),
                upsert=True
            )
    
    def _get_cycle_interval(self) -> int:
        """Get trading cycle interval based on strategy"""
        # More aggressive strategies check more frequently
        if TradingStrategy.RSI_5 in self.config.active_strategies:
            return 30  # 30 seconds for scalping
        elif TradingStrategy.HYBRID in self.config.active_strategies:
            return 60  # 1 minute for hybrid
        else:
            return 120  # 2 minutes for conservative strategies