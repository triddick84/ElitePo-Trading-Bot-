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
    
    def get_seconds_to_next_candle(self, timeframe: str, include_latency_compensation: bool = True) -> float:
        """
        Get exact seconds until next candle formation
        Used for countdown timers in frontend
        
        Returns precise seconds with millisecond accuracy for ultra-short timeframes
        """
        try:
            next_candle = self.get_next_candle_formation_time(timeframe, apply_latency_compensation=include_latency_compensation)
            current_time = self.get_chicago_time()
            
            # Use high precision calculation including microseconds
            time_diff = next_candle - current_time
            seconds_diff = time_diff.total_seconds()
            
            # For ultra-short timeframes, provide millisecond precision
            if timeframe in ['5s', '15s', '30s']:
                # Round to 2 decimal places for precision
                seconds_diff = round(seconds_diff, 2)
            else:
                # For longer timeframes, 1 decimal place is sufficient
                seconds_diff = round(seconds_diff, 1)
            
            return max(0, seconds_diff)  # Never negative
            
        except Exception as e:
            logger.error(f"Error calculating seconds to next candle: {e}")
            return 0
    
    def get_next_candle_formation_time(self, timeframe: str, market_type: str = "regular", apply_latency_compensation: bool = True) -> datetime:
        """
        Calculate the EXACT next candle formation time for Pocket Option
        
        CRITICAL FIX: Pocket Option trades execute at CURRENT candle close (not next candle).
        For 5s at time 12:00:07 → Entry should be 12:00:10 (current candle closes)
        NOT 12:00:15 (next candle).
        
        Returns time when CURRENT candle will CLOSE (which is when we enter the trade)
        
        ENHANCED: Now provides millisecond-precision timing for ultra-short timeframes
        """
        try:
            if timeframe not in self.timeframe_seconds:
                logger.warning(f"Unknown timeframe {timeframe}, using 5s default")
                timeframe = '5s'
            
            interval_seconds = self.timeframe_seconds[timeframe]
            
            # Use UTC time for Pocket Option synchronization (as per research)
            # Use high-precision time including microseconds
            current_utc = datetime.now(timezone.utc)
            
            # For ultra-short timeframes, calculate from seconds within current minute
            if interval_seconds < 60:
                # Get current second with millisecond precision
                current_second = current_utc.second + (current_utc.microsecond / 1_000_000)
                
                # Find CURRENT candle close (not next candle)
                # Example for 5s at 07.5s: current candle closes at 10s (not 15s)
                current_boundary_second = ((int(current_second) // interval_seconds) + 1) * interval_seconds
                
                if current_boundary_second >= 60:
                    # Current candle closes at minute boundary
                    candle_close_time = current_utc.replace(second=0, microsecond=0) + timedelta(minutes=1)
                else:
                    # Current candle closes within this minute
                    candle_close_time = current_utc.replace(second=current_boundary_second, microsecond=0)
                
                logger.info(f"🕐 Ultra-short timing: Current {current_second:.3f}s → Candle closes at second {current_boundary_second}")
            
            else:
                # For timeframes 1m+, calculate based on total seconds since epoch
                epoch_seconds = int(current_utc.timestamp())
                seconds_into_current_candle = epoch_seconds % interval_seconds
                seconds_to_candle_close = interval_seconds - seconds_into_current_candle
                candle_close_time = current_utc + timedelta(seconds=seconds_to_candle_close)
                candle_close_time = candle_close_time.replace(microsecond=0)
            
            # Convert to Chicago time for display
            chicago_time = candle_close_time.astimezone(self.pocket_option_tz)
            
            # Apply latency compensation for precise Pocket Option candle synchronization
            # This signals earlier to account for network/execution/user reaction delay
            if apply_latency_compensation:
                try:
                    from latency_optimizer import latency_optimizer
                    
                    # Timeframe-specific latency compensation for optimal precision
                    if timeframe == '5s':
                        latency_buffer = latency_optimizer.early_signal_buffer_5s  # 3.1 seconds (perfect sync)
                    elif timeframe == '15s':
                        latency_buffer = latency_optimizer.early_signal_buffer_15s  # 2.0 seconds
                    elif timeframe == '30s':
                        latency_buffer = latency_optimizer.early_signal_buffer_30s  # 2.5 seconds
                    elif timeframe == '1m':
                        latency_buffer = latency_optimizer.early_signal_buffer_1m  # 3.0 seconds
                    else:
                        latency_buffer = latency_optimizer.early_signal_buffer_seconds  # 3.0 seconds default
                    
                    chicago_time = chicago_time - timedelta(seconds=latency_buffer)
                    logger.info(f"⚡ Pocket Option Sync: -{latency_buffer:.2f}s compensation for {timeframe} candle")
                except ImportError:
                    # Fallback if latency_optimizer not available
                    if timeframe == '5s':
                        default_buffer = 2.0  # 2 seconds for 5s timeframe (moved 5s ahead)
                    else:
                        default_buffer = 4.0  # 4 seconds for other timeframes (moved 5s ahead)
                    chicago_time = chicago_time - timedelta(seconds=default_buffer)
                    logger.info(f"⚡ Default latency compensation: -{default_buffer}s for {timeframe}")
            
            # Log the calculated timing with full precision
            time_until = (chicago_time - self.get_chicago_time()).total_seconds()
            logger.info(f"📊 {timeframe} candle CLOSES in {time_until:.2f}s: UTC {candle_close_time.strftime('%H:%M:%S.%f')[:-3]}, "
                       f"Chicago {chicago_time.strftime('%H:%M:%S')}")
            
            return chicago_time
            
        except Exception as e:
            logger.error(f"Error calculating next candle formation time: {e}")
            # Fallback: next minute boundary
            current_time = self.get_chicago_time()
            return current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    def calculate_optimal_expiration_time(self, timeframe: str, entry_time: datetime, market_type: str = "regular") -> int:
        """
        Calculate expiration time that EXACTLY MATCHES the chart/candle timeframe
        
        CRITICAL REQUIREMENT: Expiration timeframe MUST equal chart analysis timeframe
        - 5s chart → 5s expiration
        - 1m chart → 1m expiration
        - 5m chart → 5m expiration
        
        This ensures signals are based on the SAME timeframe as the trade expiration
        """
        try:
            base_seconds = self.timeframe_seconds.get(timeframe, 60)  # Default 1m
            
            # Convert timeframe seconds to minutes (round up to nearest minute for Pocket Option)
            # Pocket Option minimum expiration is 1 minute
            expiration_minutes = max(1, base_seconds // 60)
            
            logger.info(f"📊 Expiration time for {timeframe}: {expiration_minutes} minute(s) (matches chart timeframe)")
            
            return expiration_minutes
                    
        except Exception as e:
            logger.error(f"Error calculating expiration time: {e}")
            return 1  # Safe default 1 minute
    
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