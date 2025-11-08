"""
Pocket Option Timezone Synchronization Module

Ensures all trading signals are synchronized with Pocket Option's platform timezone:
- Primary Timezone: America/Chicago (Central Time)
- Handles CST (UTC-6) and CDT (UTC-5) automatically
- Provides precise candle-close timing for binary options
"""

import pytz
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class PocketOptionTimeSync:
    """
    Pocket Option Time Synchronization Manager
    
    Ensures all signals are generated and delivered in sync with Pocket Option's
    platform timezone (America/Chicago - Central Time)
    """
    
    def __init__(self):
        self.utc_tz = pytz.UTC
        self.chicago_tz = pytz.timezone('America/Chicago')
        
        logger.info("✅ Pocket Option Time Sync initialized")
        logger.info(f"   Platform Timezone: America/Chicago (Central Time)")
        
        # Log current time in both timezones
        now_utc = datetime.now(self.utc_tz)
        now_chicago = now_utc.astimezone(self.chicago_tz)
        logger.info(f"   UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   Chicago Time: {now_chicago.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    def get_current_chicago_time(self) -> datetime:
        """Get current time in Chicago timezone"""
        return datetime.now(self.chicago_tz)
    
    def get_current_utc_time(self) -> datetime:
        """Get current time in UTC"""
        return datetime.now(self.utc_tz)
    
    def convert_utc_to_chicago(self, utc_time: datetime) -> datetime:
        """Convert UTC time to Chicago time"""
        if utc_time.tzinfo is None:
            utc_time = self.utc_tz.localize(utc_time)
        return utc_time.astimezone(self.chicago_tz)
    
    def convert_chicago_to_utc(self, chicago_time: datetime) -> datetime:
        """Convert Chicago time to UTC"""
        if chicago_time.tzinfo is None:
            chicago_time = self.chicago_tz.localize(chicago_time)
        return chicago_time.astimezone(self.utc_tz)
    
    def get_next_candle_close(self, timeframe_seconds: int) -> Tuple[datetime, datetime]:
        """
        Calculate next candle close time for given timeframe
        
        Args:
            timeframe_seconds: Candle timeframe in seconds (e.g., 5 for 5-second candles)
        
        Returns:
            Tuple of (chicago_time, utc_time) for next candle close
        """
        now_chicago = self.get_current_chicago_time()
        
        # Calculate seconds since epoch
        epoch = datetime(1970, 1, 1, tzinfo=self.utc_tz)
        now_utc = now_chicago.astimezone(self.utc_tz)
        seconds_since_epoch = (now_utc - epoch).total_seconds()
        
        # Calculate next candle close
        current_candle_start = (seconds_since_epoch // timeframe_seconds) * timeframe_seconds
        next_candle_close = current_candle_start + timeframe_seconds
        
        # Convert back to datetime
        next_close_utc = epoch + timedelta(seconds=next_candle_close)
        next_close_chicago = next_close_utc.astimezone(self.chicago_tz)
        
        return next_close_chicago, next_close_utc
    
    def calculate_precise_entry_time(self, timeframe_seconds: int, 
                                     trade_duration_seconds: int) -> Dict:
        """
        Calculate precise entry time for Pocket Option signal
        
        For binary options, we need to enter at the START of a candle and
        the option expires after N candles
        
        Args:
            timeframe_seconds: Chart timeframe (e.g., 5 for 5-second)
            trade_duration_seconds: Option duration (e.g., 82 for 1m 22s)
        
        Returns:
            Dict with entry and expiration times in both timezones
        """
        # Get next candle close (which is start of next candle)
        entry_chicago, entry_utc = self.get_next_candle_close(timeframe_seconds)
        
        # Calculate expiration time
        expiration_utc = entry_utc + timedelta(seconds=trade_duration_seconds)
        expiration_chicago = expiration_utc.astimezone(self.chicago_tz)
        
        # Calculate how many candles this represents
        num_candles = trade_duration_seconds / timeframe_seconds
        
        return {
            'entry_time_chicago': entry_chicago,
            'entry_time_utc': entry_utc,
            'entry_time_chicago_str': entry_chicago.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'entry_time_utc_str': entry_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'entry_time_iso': entry_utc.isoformat(),
            
            'expiration_time_chicago': expiration_chicago,
            'expiration_time_utc': expiration_utc,
            'expiration_time_chicago_str': expiration_chicago.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'expiration_time_utc_str': expiration_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'expiration_time_iso': expiration_utc.isoformat(),
            
            'duration_seconds': trade_duration_seconds,
            'duration_candles': num_candles,
            'timeframe_seconds': timeframe_seconds
        }
    
    def get_time_until_next_candle(self, timeframe_seconds: int) -> float:
        """
        Get seconds until next candle close
        
        Useful for knowing when to generate/send signal
        """
        next_close_chicago, _ = self.get_next_candle_close(timeframe_seconds)
        now_chicago = self.get_current_chicago_time()
        
        time_diff = (next_close_chicago - now_chicago).total_seconds()
        return time_diff
    
    def format_signal_timing(self, timeframe_seconds: int, 
                            trade_duration_seconds: int) -> Dict:
        """
        Format complete timing information for signal display
        
        Returns all timing info needed for UI display and AutobotSignal.io
        """
        timing = self.calculate_precise_entry_time(timeframe_seconds, trade_duration_seconds)
        time_until_entry = self.get_time_until_next_candle(timeframe_seconds)
        
        # Format duration in human-readable form
        duration_minutes = trade_duration_seconds // 60
        duration_seconds = trade_duration_seconds % 60
        duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_minutes > 0 else f"{duration_seconds}s"
        
        return {
            **timing,
            'time_until_entry_seconds': time_until_entry,
            'duration_text': duration_text,
            'platform_timezone': 'America/Chicago',
            'current_chicago_time': self.get_current_chicago_time().strftime('%Y-%m-%d %H:%M:%S %Z'),
            'current_utc_time': self.get_current_utc_time().strftime('%Y-%m-%d %H:%M:%S %Z')
        }
    
    def is_market_open(self) -> bool:
        """
        Check if Pocket Option OTC market is open
        
        OTC markets are 24/7, but this can be extended for specific market hours
        """
        # OTC markets are always open
        return True
    
    def get_timezone_offset(self) -> str:
        """Get current timezone offset for Chicago"""
        chicago_time = self.get_current_chicago_time()
        offset = chicago_time.strftime('%z')
        # Format as UTC-6 or UTC-5
        hours = int(offset[:3])
        return f"UTC{hours:+d}"


# Global instance
_time_sync = None


def get_pocket_option_time_sync() -> PocketOptionTimeSync:
    """Get or create Pocket Option Time Sync instance"""
    global _time_sync
    if _time_sync is None:
        _time_sync = PocketOptionTimeSync()
    return _time_sync
