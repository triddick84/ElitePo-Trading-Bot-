import asyncio
from datetime import datetime, timezone, timedelta
import pytz
from typing import Dict, List, Optional, Tuple
import logging
from models import TradingSignal, SignalDirection

logger = logging.getLogger(__name__)

class PocketOptionTimingSync:
    """
    Precision timing synchronization with Pocket Option trading platform
    Chicago/Central timezone alignment for accurate candle formation signals
    """
    
    def __init__(self):
        # Pocket Option uses Chicago/Central timezone
        self.pocket_option_tz = pytz.timezone('America/Chicago')
        
        # Pocket Option timeframe mappings (in seconds)
        self.timeframe_seconds = {
            '5s': 5,      # 5 seconds
            '15s': 15,    # 15 seconds
            '30s': 30,    # 30 seconds
            '1m': 60,
            '2m': 120,
            '3m': 180,
            '5m': 300,
            '10m': 600,
            '15m': 900,
            '30m': 1800,
            '1h': 3600
        }
        
        # Market open times for different asset types (Chicago time)
        self.market_schedules = {
            'forex': {
                'open': {'hour': 17, 'minute': 0, 'second': 0},  # Sunday 5:00 PM CT
                'close': {'hour': 16, 'minute': 0, 'second': 0}   # Friday 4:00 PM CT
            },
            'crypto': {
                'open': None,  # 24/7
                'close': None
            },
            'otc': {
                'open': None,  # 24/7
                'close': None
            }
        }
    
    def get_chicago_time(self) -> datetime:
        """Get current time in Chicago/Central timezone"""
        return datetime.now(self.pocket_option_tz)
    
    def get_next_candle_formation_time(self, timeframe: str, market_type: str = "regular") -> datetime:
        """
        Calculate the exact next candle formation time for Pocket Option
        This is when the signal should be generated for maximum accuracy
        """
        try:
            if timeframe not in self.timeframe_seconds:
                logger.warning(f"Unknown timeframe {timeframe}, using 5m default")
                timeframe = '5m'
            
            interval_seconds = self.timeframe_seconds[timeframe]
            current_time = self.get_chicago_time()
            
            # Calculate seconds since midnight Chicago time
            chicago_midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_since_midnight = (current_time - chicago_midnight).total_seconds()
            
            # Calculate next candle boundary
            seconds_into_current_candle = seconds_since_midnight % interval_seconds
            seconds_to_next_candle = interval_seconds - seconds_into_current_candle
            
            # Add small buffer for network latency (2 seconds before candle forms)
            if market_type == "otc":
                # OTC markets - signal 1 second before candle forms
                signal_time = current_time + timedelta(seconds=seconds_to_next_candle - 1)
            else:
                # Regular markets - signal 2 seconds before candle forms
                signal_time = current_time + timedelta(seconds=seconds_to_next_candle - 2)
            
            return signal_time
            
        except Exception as e:
            logger.error(f"Error calculating next candle formation time: {e}")
            # Fallback: next minute boundary
            current_time = self.get_chicago_time()
            return current_time.replace(second=58, microsecond=0) + timedelta(minutes=1)
    
    def calculate_optimal_expiration_time(self, timeframe: str, entry_time: datetime, market_type: str = "regular") -> int:
        """
        Calculate optimal expiration time based on Pocket Option's candle patterns
        """
        try:
            base_seconds = self.timeframe_seconds.get(timeframe, 300)  # Default 5m
            
            if market_type == "otc":
                # OTC markets: 2-3 candles for optimal accuracy
                if base_seconds <= 60:  # 1m or less
                    return 3  # 3 minutes for short timeframes
                elif base_seconds <= 300:  # Up to 5m
                    return 10  # 10 minutes
                else:
                    return 15  # 15 minutes for longer timeframes
            else:
                # Regular markets: 3-5 candles for optimal accuracy
                if base_seconds <= 60:  # 1m or less
                    return 5  # 5 minutes
                elif base_seconds <= 300:  # Up to 5m
                    return 15  # 15 minutes
                else:
                    return 30  # 30 minutes for longer timeframes
                    
        except Exception as e:
            logger.error(f"Error calculating expiration time: {e}")
            return 15  # Safe default
    
    def is_market_open(self, asset_type: str, current_time: Optional[datetime] = None) -> bool:
        """
        Check if the market is open for the given asset type in Chicago time
        """
        try:
            if current_time is None:
                current_time = self.get_chicago_time()
            
            # Crypto and OTC are always open
            if asset_type.lower() in ['crypto', 'otc']:
                return True
            
            # Forex market schedule (Sunday 5 PM CT to Friday 4 PM CT)
            if asset_type.lower() == 'forex':
                weekday = current_time.weekday()  # 0=Monday, 6=Sunday
                hour = current_time.hour
                
                # Friday 4 PM CT to Sunday 5 PM CT is closed
                if weekday == 4 and hour >= 16:  # Friday after 4 PM
                    return False
                if weekday == 5:  # Saturday
                    return False
                if weekday == 6 and hour < 17:  # Sunday before 5 PM
                    return False
                
                return True
            
            # Default to open for other asset types
            return True
            
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return True  # Default to open
    
    def sync_signal_with_pocket_option_timing(self, signal: TradingSignal, user_timeframes: List[str]) -> TradingSignal:
        """
        Synchronize signal timing with Pocket Option's exact candle formation
        """
        try:
            # Use the first selected timeframe from user preferences
            target_timeframe = user_timeframes[0] if user_timeframes else '5m'
            
            # Ensure timeframe is supported by Pocket Option
            if target_timeframe not in self.timeframe_seconds:
                logger.warning(f"Unsupported timeframe {target_timeframe}, using 5m")
                target_timeframe = '5m'
            
            # Get market type from symbol
            market_type = "otc" if "_OTC" in signal.symbol else "regular"
            
            # Calculate precise entry timing
            optimal_entry_time = self.get_next_candle_formation_time(target_timeframe, market_type)
            
            # Calculate optimal expiration based on timeframe and market type
            optimal_expiration = self.calculate_optimal_expiration_time(
                target_timeframe, optimal_entry_time, market_type
            )
            
            # Update signal with Pocket Option synchronized timing
            signal.timeframe = target_timeframe
            signal.precision_entry_time = optimal_entry_time
            signal.expiration_minutes = optimal_expiration
            
            # Add timing synchronization info to technical analysis
            if not hasattr(signal, 'technical_analysis') or signal.technical_analysis is None:
                signal.technical_analysis = {}
            
            signal.technical_analysis.update({
                'pocket_option_sync': True,
                'chicago_timezone': True,
                'target_timeframe': target_timeframe,
                'candle_formation_sync': True,
                'market_type': market_type,
                'optimal_entry_time': optimal_entry_time.isoformat(),
                'seconds_to_entry': (optimal_entry_time - self.get_chicago_time()).total_seconds()
            })
            
            # Update justification with timing info
            seconds_to_entry = (optimal_entry_time - self.get_chicago_time()).total_seconds()
            
            signal.justification += f" | 🕐 POCKET OPTION SYNC: {target_timeframe} timeframe, " \
                                  f"Chicago timezone, Entry in {int(seconds_to_entry)}s at next candle formation. " \
                                  f"Expiration: {optimal_expiration}min for {market_type} market."
            
            logger.info(f"Signal synchronized with Pocket Option timing: {signal.symbol} "
                       f"{target_timeframe} entry in {int(seconds_to_entry)}s")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error synchronizing signal timing: {e}")
            return signal  # Return original signal if sync fails
    
    def get_pocket_option_compatible_timeframes(self) -> List[str]:
        """Get list of timeframes supported by Pocket Option"""
        return list(self.timeframe_seconds.keys())
    
    def calculate_signal_accuracy_window(self, timeframe: str, market_type: str = "regular") -> Dict:
        """
        Calculate the accuracy window for signal execution on Pocket Option
        """
        try:
            base_seconds = self.timeframe_seconds.get(timeframe, 300)
            
            if market_type == "otc":
                # OTC markets have tighter windows
                return {
                    'pre_entry_buffer': 1,  # 1 second before candle
                    'optimal_window': 3,    # 3 seconds optimal execution window
                    'late_entry_buffer': 2, # 2 seconds after candle formation
                    'max_accuracy_period': base_seconds * 0.1  # 10% of timeframe
                }
            else:
                # Regular markets
                return {
                    'pre_entry_buffer': 2,  # 2 seconds before candle
                    'optimal_window': 5,    # 5 seconds optimal execution window
                    'late_entry_buffer': 3, # 3 seconds after candle formation
                    'max_accuracy_period': base_seconds * 0.15  # 15% of timeframe
                }
                
        except Exception as e:
            logger.error(f"Error calculating accuracy window: {e}")
            return {
                'pre_entry_buffer': 2,
                'optimal_window': 5,
                'late_entry_buffer': 3,
                'max_accuracy_period': 30
            }
    
    async def wait_for_optimal_entry_time(self, target_time: datetime) -> bool:
        """
        Wait until the optimal entry time for maximum accuracy
        """
        try:
            current_time = self.get_chicago_time()
            wait_seconds = (target_time - current_time).total_seconds()
            
            if wait_seconds > 0:
                logger.info(f"Waiting {wait_seconds:.1f} seconds for optimal Pocket Option entry time")
                await asyncio.sleep(wait_seconds)
                return True
            else:
                logger.warning("Target entry time has already passed")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for optimal entry time: {e}")
            return False


# Global instance
pocket_option_sync = PocketOptionTimingSync()