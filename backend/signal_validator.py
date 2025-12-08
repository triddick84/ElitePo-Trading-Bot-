"""
Signal Validator - Tracks and validates signal predictions
Automatically checks if signals were winning or losing after expiration
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class SignalValidator:
    def __init__(self):
        self.mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.environ.get('DB_NAME', 'trading_bot')
        self.client = None
        self.db = None
        self.validation_tasks = {}  # Track running validation tasks
        self.is_running = False
        
    async def initialize(self):
        """Initialize MongoDB connection"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_url)
            self.db = self.client[self.db_name]
            logger.info("✅ Signal Validator initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Signal Validator: {e}")
    
    async def schedule_signal_validation(self, signal_data: Dict):
        """
        Schedule a signal for validation after it expires
        
        Args:
            signal_data: Signal dictionary with id, direction, entry_price, expiration_minutes, etc.
        """
        try:
            signal_id = signal_data['id']
            expiration_minutes = signal_data.get('expiration_minutes', 1)
            
            # Convert fractional minutes to seconds
            expiration_seconds = expiration_minutes * 60
            
            # Add buffer time (30 seconds after expiration to ensure data is available)
            validation_delay = expiration_seconds + 30
            
            logger.info(f"📅 Scheduled validation for signal {signal_id} in {validation_delay:.0f} seconds")
            
            # Create validation task
            task = asyncio.create_task(self._validate_signal_after_delay(signal_data, validation_delay))
            self.validation_tasks[signal_id] = task
            
        except Exception as e:
            logger.error(f"❌ Error scheduling signal validation: {e}")
    
    async def _validate_signal_after_delay(self, signal_data: Dict, delay_seconds: float):
        """Wait for expiration then validate the signal"""
        try:
            signal_id = signal_data['id']
            
            # Wait for expiration + buffer
            await asyncio.sleep(delay_seconds)
            
            # Now validate the signal
            result = await self.validate_signal(signal_data)
            
            if result:
                logger.info(f"✅ Signal {signal_id} validated: {result['result']}")
            else:
                logger.warning(f"⚠️ Could not validate signal {signal_id}")
                
            # Clean up task
            if signal_id in self.validation_tasks:
                del self.validation_tasks[signal_id]
                
        except asyncio.CancelledError:
            logger.info(f"🛑 Validation cancelled for signal {signal_id}")
        except Exception as e:
            logger.error(f"❌ Error in delayed validation: {e}")
    
    async def validate_signal(self, signal_data: Dict) -> Optional[Dict]:
        """
        Validate a signal by comparing prediction with actual market movement
        
        Returns:
            Dict with validation results or None if validation failed
        """
        try:
            signal_id = signal_data['id']
            symbol = signal_data['symbol']
            direction = signal_data['direction']  # BUY or SELL
            entry_price = signal_data['entry_price']
            expiration_minutes = signal_data.get('expiration_minutes', 1)
            entry_time = signal_data.get('precision_entry_time') or signal_data.get('timestamp')
            
            logger.info(f"🔍 Validating signal {signal_id}: {direction} {symbol} @ {entry_price}")
            
            # Parse entry time
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            
            # Calculate expiration time
            expiration_seconds = expiration_minutes * 60
            expiration_time = entry_time + timedelta(seconds=expiration_seconds)
            
            # Fetch actual market data at expiration
            exit_price = await self._get_price_at_time(symbol, expiration_time)
            
            if exit_price is None:
                logger.warning(f"⚠️ Could not fetch exit price for {symbol}")
                return None
            
            # Calculate price movement
            price_change = exit_price - entry_price
            price_change_percent = (price_change / entry_price) * 100
            
            # Determine if signal was correct
            if direction in ['BUY', 'CALL']:
                # For BUY: We win if exit_price > entry_price
                is_win = exit_price > entry_price
            else:  # SELL or PUT
                # For SELL: We win if exit_price < entry_price
                is_win = exit_price < entry_price
            
            result = 'WIN' if is_win else 'LOSS'
            
            # Prepare validation result
            validation_result = {
                'signal_id': signal_id,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'price_change': price_change,
                'price_change_percent': price_change_percent,
                'result': result,
                'is_win': is_win,
                'entry_time': entry_time.isoformat(),
                'expiration_time': expiration_time.isoformat(),
                'validated_at': datetime.now(timezone.utc).isoformat(),
                'expiration_minutes': expiration_minutes
            }
            
            # Store validation result in database
            await self._store_validation_result(validation_result)
            
            # Update original signal with result
            await self._update_signal_result(signal_id, result, exit_price, price_change_percent)
            
            logger.info(f"✅ Signal {signal_id} - {result}: Entry ${entry_price:.5f} → Exit ${exit_price:.5f} ({price_change_percent:+.2f}%)")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"❌ Error validating signal: {e}")
            return None
    
    async def _get_price_at_time(self, symbol: str, target_time: datetime) -> Optional[float]:
        """
        Fetch the market price at a specific time
        Uses real-time market data hub or historical data
        """
        try:
            # Try to get from real-time market data hub from server.py
            from server import realtime_market_hub
            
            # Clean symbol (remove _OTC or _regular suffix)
            clean_symbol = symbol.replace('_OTC', '').replace('_regular', '')
            
            # Get historical candles around the target time
            # We need data from target time ± 5 minutes
            candles = await realtime_market_hub.get_historical_candles(
                clean_symbol,
                interval='1m',
                limit=10
            )
            
            if candles and len(candles) > 0:
                # Find the candle closest to target time
                target_timestamp = target_time.timestamp()
                closest_candle = None
                min_time_diff = float('inf')
                
                for candle in candles:
                    candle_time = candle.get('timestamp')
                    if isinstance(candle_time, str):
                        candle_time = datetime.fromisoformat(candle_time.replace('Z', '+00:00')).timestamp()
                    elif isinstance(candle_time, datetime):
                        candle_time = candle_time.timestamp()
                    
                    time_diff = abs(candle_time - target_timestamp)
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_candle = candle
                
                if closest_candle:
                    # Use close price of the closest candle
                    close_price = closest_candle.get('close')
                    logger.info(f"📊 Found price for {symbol} at {target_time}: ${close_price:.5f}")
                    return float(close_price)
            
            # Fallback: Use current price if we can't get historical
            logger.warning(f"⚠️ Using fallback price method for {symbol}")
            current_data = await realtime_market_data_hub.get_latest_price(clean_symbol)
            if current_data:
                return current_data.get('price')
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching price at time: {e}")
            return None
    
    async def _store_validation_result(self, validation_result: Dict):
        """Store validation result in database"""
        try:
            await self.db.signal_validations.insert_one(validation_result)
            logger.info(f"💾 Stored validation result for signal {validation_result['signal_id']}")
        except Exception as e:
            logger.error(f"❌ Error storing validation result: {e}")
    
    async def _update_signal_result(self, signal_id: str, result: str, exit_price: float, change_percent: float):
        """Update the original signal with validation result"""
        try:
            await self.db.trading_signals.update_one(
                {'id': signal_id},
                {
                    '$set': {
                        'validation_result': result,
                        'exit_price': exit_price,
                        'price_change_percent': change_percent,
                        'validated_at': datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"📝 Updated signal {signal_id} with result: {result}")
        except Exception as e:
            logger.error(f"❌ Error updating signal result: {e}")
    
    async def get_signal_statistics(self, timeframe: Optional[str] = None, hours: int = 24) -> Dict:
        """
        Get statistics for validated signals
        
        Args:
            timeframe: Optional filter by timeframe (5s, 1m, etc.)
            hours: Look back period in hours
        """
        try:
            # Build query
            query = {
                'validated_at': {
                    '$gte': (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                }
            }
            
            if timeframe:
                query['expiration_minutes'] = self._timeframe_to_minutes(timeframe)
            
            # Fetch all validations
            validations = await self.db.signal_validations.find(query).to_list(1000)
            
            if not validations:
                return {
                    'total_signals': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0,
                    'avg_change_percent': 0
                }
            
            # Calculate statistics
            total = len(validations)
            wins = sum(1 for v in validations if v['result'] == 'WIN')
            losses = total - wins
            win_rate = (wins / total) * 100 if total > 0 else 0
            avg_change = sum(v['price_change_percent'] for v in validations) / total if total > 0 else 0
            
            # Group by direction
            buy_signals = [v for v in validations if v['direction'] in ['BUY', 'CALL']]
            sell_signals = [v for v in validations if v['direction'] in ['SELL', 'PUT']]
            
            buy_wins = sum(1 for v in buy_signals if v['result'] == 'WIN')
            sell_wins = sum(1 for v in sell_signals if v['result'] == 'WIN')
            
            buy_rate = (buy_wins / len(buy_signals) * 100) if buy_signals else 0
            sell_rate = (sell_wins / len(sell_signals) * 100) if sell_signals else 0
            
            return {
                'total_signals': total,
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 2),
                'avg_change_percent': round(avg_change, 4),
                'buy_signals': {
                    'total': len(buy_signals),
                    'wins': buy_wins,
                    'win_rate': round(buy_rate, 2)
                },
                'sell_signals': {
                    'total': len(sell_signals),
                    'wins': sell_wins,
                    'win_rate': round(sell_rate, 2)
                },
                'period_hours': hours,
                'timeframe': timeframe or 'all'
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting signal statistics: {e}")
            return {}
    
    def _timeframe_to_minutes(self, timeframe: str) -> float:
        """Convert timeframe string to minutes"""
        tf_map = {
            '5s': 0.083,
            '15s': 0.25,
            '30s': 0.5,
            '1m': 1,
            '2m': 2,
            '3m': 3,
            '5m': 5
        }
        return tf_map.get(timeframe, 1)
    
    async def get_recent_validations(self, limit: int = 20) -> List[Dict]:
        """Get recent validation results"""
        try:
            validations = await self.db.signal_validations.find(
                {},
                {'_id': 0}
            ).sort('validated_at', -1).limit(limit).to_list(limit)
            
            return validations
        except Exception as e:
            logger.error(f"❌ Error fetching recent validations: {e}")
            return []
    
    async def cleanup(self):
        """Cleanup resources"""
        # Cancel all pending validation tasks
        for signal_id, task in self.validation_tasks.items():
            task.cancel()
            logger.info(f"🛑 Cancelled validation task for {signal_id}")
        
        self.validation_tasks.clear()
        
        if self.client:
            self.client.close()
            logger.info("✅ Signal Validator cleaned up")

# Global instance
signal_validator = SignalValidator()
