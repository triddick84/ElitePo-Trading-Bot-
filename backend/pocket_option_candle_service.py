"""
Pocket Option Real-Time Candle Service
Fetches actual candle data from Pocket Option platform for perfect synchronization
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
import os

logger = logging.getLogger(__name__)


class PocketOptionCandleService:
    """Service to fetch real-time candle data from Pocket Option platform"""
    
    def __init__(self):
        self.ssid = os.environ.get('POCKET_OPTION_SSID', None)
        self.connected = False
        self.candle_cache = {}  # Cache recent candles for quick access
        
        # Timeframe mapping (seconds to Pocket Option format)
        self.timeframe_map = {
            '5s': 5,
            '15s': 15,
            '30s': 30,
            '1m': 60,
            '3m': 180,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600
        }
        
        logger.info("🔌 Pocket Option Candle Service initialized")
    
    def set_ssid(self, ssid: str):
        """Set Pocket Option SSID for authentication"""
        self.ssid = ssid
        logger.info("✅ Pocket Option SSID configured")
    
    async def connect(self) -> bool:
        """
        Connect to Pocket Option API
        Returns True if connection successful
        """
        try:
            if not self.ssid:
                logger.warning("⚠️ No SSID configured - using fallback timing calculation")
                return False
            
            # Try to import Pocket Option API library
            try:
                from pocketoptionapi import PocketOption
                
                self.api = PocketOption(self.ssid)
                check_connect, message = self.api.connect()
                
                if check_connect:
                    self.connected = True
                    logger.info(f"✅ Connected to Pocket Option API: {message}")
                    return True
                else:
                    logger.error(f"❌ Failed to connect to Pocket Option: {message}")
                    return False
                    
            except ImportError:
                logger.warning("⚠️ PocketOptionAPI library not installed - using fallback")
                logger.info("💡 Install with: pip install pocketoptionapi")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error connecting to Pocket Option: {e}")
            return False
    
    async def get_latest_candle(self, asset: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest candle from Pocket Option
        
        Args:
            asset: Trading asset (e.g., "EURUSD", "BTCUSD")
            timeframe: Timeframe string (e.g., "1m", "5s")
            
        Returns:
            Dict with candle data including actual close time, or None if unavailable
        """
        try:
            if not self.connected:
                logger.debug("Not connected to Pocket Option - using fallback")
                return None
            
            # Convert asset format (remove _otc, _regular suffixes)
            clean_asset = asset.split('_')[0]
            
            # Get timeframe in seconds
            tf_seconds = self.timeframe_map.get(timeframe, 60)
            
            # Fetch candle data from Pocket Option
            candles = self.api.get_candles(clean_asset, tf_seconds, count=1)
            
            if candles and len(candles) > 0:
                latest_candle = candles[-1]
                
                # Extract candle data
                candle_data = {
                    'open': latest_candle.get('open'),
                    'high': latest_candle.get('max'),
                    'low': latest_candle.get('min'),
                    'close': latest_candle.get('close'),
                    'timestamp': latest_candle.get('time'),  # Unix timestamp
                    'close_time': datetime.fromtimestamp(latest_candle.get('time'), tz=timezone.utc),
                    'timeframe': timeframe,
                    'asset': asset
                }
                
                # Cache for quick access
                cache_key = f"{asset}_{timeframe}"
                self.candle_cache[cache_key] = candle_data
                
                logger.debug(f"📊 Fetched {timeframe} candle for {asset}: close at {candle_data['close_time']}")
                
                return candle_data
            else:
                logger.warning(f"⚠️ No candle data returned from Pocket Option for {asset} {timeframe}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching candle from Pocket Option: {e}")
            return None
    
    async def get_next_candle_close_time(self, asset: str, timeframe: str) -> Optional[datetime]:
        """
        Get the ACTUAL next candle close time from Pocket Option
        This is the ground truth for synchronization
        
        Args:
            asset: Trading asset
            timeframe: Timeframe string
            
        Returns:
            Datetime of next candle close, or None if unavailable
        """
        try:
            # Fetch latest candle
            latest_candle = await self.get_latest_candle(asset, timeframe)
            
            if latest_candle:
                # Calculate next candle close based on actual Pocket Option timing
                current_close_time = latest_candle['close_time']
                tf_seconds = self.timeframe_map.get(timeframe, 60)
                
                # Next candle closes after the interval
                next_close_time = current_close_time + timedelta(seconds=tf_seconds)
                
                logger.info(f"🕐 Next {timeframe} candle close for {asset}: {next_close_time.strftime('%H:%M:%S')} UTC")
                
                return next_close_time
            else:
                logger.warning(f"⚠️ Could not determine next candle close time for {asset} {timeframe}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error calculating next candle close time: {e}")
            return None
    
    async def get_candle_formation_schedule(self, asset: str, timeframe: str, count: int = 10) -> List[datetime]:
        """
        Get the schedule of upcoming candle formation times
        Based on actual Pocket Option timing
        
        Args:
            asset: Trading asset
            timeframe: Timeframe string
            count: Number of future candle times to calculate
            
        Returns:
            List of datetime objects representing candle close times
        """
        try:
            next_close = await self.get_next_candle_close_time(asset, timeframe)
            
            if not next_close:
                return []
            
            tf_seconds = self.timeframe_map.get(timeframe, 60)
            schedule = [next_close]
            
            # Generate future candle times
            for i in range(1, count):
                next_time = next_close + timedelta(seconds=tf_seconds * i)
                schedule.append(next_time)
            
            logger.info(f"📅 Generated {count} candle formation times for {asset} {timeframe}")
            
            return schedule
            
        except Exception as e:
            logger.error(f"❌ Error generating candle schedule: {e}")
            return []
    
    async def is_synchronized(self, asset: str, timeframe: str, tolerance_seconds: float = 1.0) -> bool:
        """
        Check if we are synchronized with Pocket Option candles
        
        Args:
            asset: Trading asset
            timeframe: Timeframe string
            tolerance_seconds: Acceptable time difference in seconds
            
        Returns:
            True if synchronized within tolerance
        """
        try:
            latest_candle = await self.get_latest_candle(asset, timeframe)
            
            if not latest_candle:
                return False
            
            # Check time difference between our current time and last candle close
            current_time = datetime.now(timezone.utc)
            last_close_time = latest_candle['close_time']
            tf_seconds = self.timeframe_map.get(timeframe, 60)
            
            # Calculate expected position within current candle
            time_since_close = (current_time - last_close_time).total_seconds()
            position_in_candle = time_since_close % tf_seconds
            
            # We're synchronized if position is close to 0 (just after close) or close to tf_seconds (just before close)
            is_synced = position_in_candle < tolerance_seconds or position_in_candle > (tf_seconds - tolerance_seconds)
            
            if is_synced:
                logger.debug(f"✅ Synchronized with Pocket Option {timeframe} candles for {asset}")
            else:
                logger.debug(f"⚠️ Not synchronized - {position_in_candle:.1f}s into {timeframe} candle")
            
            return is_synced
            
        except Exception as e:
            logger.error(f"❌ Error checking synchronization: {e}")
            return False
    
    async def close(self):
        """Close connection to Pocket Option"""
        try:
            if self.connected and hasattr(self, 'api'):
                self.api.close()
                self.connected = False
                logger.info("🔌 Disconnected from Pocket Option API")
        except Exception as e:
            logger.error(f"❌ Error closing Pocket Option connection: {e}")


# Global instance
pocket_option_candle_service = PocketOptionCandleService()
