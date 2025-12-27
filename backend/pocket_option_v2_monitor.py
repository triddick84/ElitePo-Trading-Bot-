"""
Pocket Option V2 Live Data Monitor
Uses BinaryOptionsToolsV2 library for real-time candle monitoring
"""

import asyncio
import logging
import os
import sys
from datetime import timedelta, datetime, timezone
from typing import Dict, Any, Optional, Callable
from collections import deque

# Add BinaryOptionsToolsV2 to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'BinaryOptionsToolsV2'))

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

logger = logging.getLogger(__name__)


class PocketOptionV2Monitor:
    """
    Real-time candle monitor using BinaryOptionsToolsV2
    Provides live data streaming for trading strategies
    """
    
    def __init__(self, ssid: str):
        """Initialize with SSID from environment"""
        self.ssid = ssid
        self.client: Optional[PocketOptionAsync] = None
        self.is_connected = False
        self.subscriptions: Dict[str, Any] = {}
        self.latest_candles: Dict[str, Dict] = {}
        self.candle_callbacks: Dict[str, list] = {}
        self.monitoring_task = None
        logger.info("🔧 PocketOptionV2Monitor initialized")
    
    async def connect(self) -> bool:
        """
        Establish connection to Pocket Option via BinaryOptionsToolsV2
        """
        try:
            logger.info("🔌 Connecting to Pocket Option...")
            self.client = PocketOptionAsync(ssid=self.ssid)
            
            # Wait for API to initialize
            await asyncio.sleep(2)
            
            # Verify connection by checking balance
            balance = await self.client.balance()
            is_demo = self.client.is_demo()
            
            self.is_connected = True
            logger.info(f"✅ Connected to Pocket Option ({'Demo' if is_demo else 'Real'} Account)")
            logger.info(f"💰 Balance: ${balance:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Pocket Option: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        try:
            # Unsubscribe from all assets
            for asset in list(self.subscriptions.keys()):
                await self.unsubscribe(asset)
            
            if self.client:
                await self.client.disconnect()
            
            self.is_connected = False
            logger.info("🔌 Disconnected from Pocket Option")
            
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    async def subscribe_candles(
        self, 
        asset: str, 
        timeframe_seconds: int = 60,
        callback: Optional[Callable] = None
    ):
        """
        Subscribe to time-aligned candles for an asset
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc')
            timeframe_seconds: Candle timeframe in seconds (default: 60)
            callback: Optional callback function to call on new candle
        """
        if not self.is_connected:
            logger.warning("Not connected. Call connect() first.")
            return False
        
        try:
            logger.info(f"📊 Subscribing to {asset} ({timeframe_seconds}s candles)...")
            
            # Subscribe to time-aligned candles
            subscription = await self.client.subscribe_symbol_time_aligned(
                asset,
                timedelta(seconds=timeframe_seconds)
            )
            
            self.subscriptions[asset] = subscription
            
            # Register callback if provided
            if callback:
                if asset not in self.candle_callbacks:
                    self.candle_callbacks[asset] = []
                self.candle_callbacks[asset].append(callback)
            
            # Start monitoring task for this asset
            asyncio.create_task(self._monitor_asset_candles(asset))
            
            logger.info(f"✅ Subscribed to {asset}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to {asset}: {e}")
            return False
    
    async def _monitor_asset_candles(self, asset: str):
        """
        Internal task to monitor candles for an asset
        """
        try:
            subscription = self.subscriptions.get(asset)
            if not subscription:
                return
            
            async for candle in subscription:
                # Store latest candle
                self.latest_candles[asset] = candle
                
                # Log candle data
                logger.debug(
                    f"📈 {asset} | "
                    f"Time: {candle['time']} | "
                    f"O: {candle['open']:.5f} | "
                    f"H: {candle['high']:.5f} | "
                    f"L: {candle['low']:.5f} | "
                    f"C: {candle['close']:.5f}"
                )
                
                # Call registered callbacks
                if asset in self.candle_callbacks:
                    for callback in self.candle_callbacks[asset]:
                        try:
                            await callback(asset, candle)
                        except Exception as cb_error:
                            logger.error(f"Error in callback for {asset}: {cb_error}")
                
        except Exception as e:
            logger.error(f"Error monitoring {asset}: {e}")
            # Attempt to resubscribe
            await asyncio.sleep(5)
            if asset in self.subscriptions:
                logger.info(f"🔄 Attempting to resubscribe to {asset}...")
                await self.subscribe_candles(asset)
    
    async def unsubscribe(self, asset: str):
        """Unsubscribe from an asset"""
        try:
            if asset in self.subscriptions:
                await self.client.unsubscribe(asset)
                del self.subscriptions[asset]
                logger.info(f"✅ Unsubscribed from {asset}")
            
            if asset in self.candle_callbacks:
                del self.candle_callbacks[asset]
                
        except Exception as e:
            logger.error(f"Error unsubscribing from {asset}: {e}")
    
    def get_latest_candle(self, asset: str) -> Optional[Dict]:
        """Get the most recent candle for an asset"""
        return self.latest_candles.get(asset)
    
    async def get_historical_candles(
        self, 
        asset: str, 
        period: int = 60, 
        count: int = 100
    ) -> list:
        """
        Get historical candles
        
        Args:
            asset: Asset symbol
            period: Candle period in seconds
            count: Number of candles to fetch
        
        Returns:
            List of candle dictionaries
        """
        if not self.is_connected:
            logger.warning("Not connected. Call connect() first.")
            return []
        
        try:
            candles = await self.client.get_candles(asset, period, count)
            logger.info(f"📊 Fetched {len(candles)} historical candles for {asset}")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching historical candles for {asset}: {e}")
            return []
    
    async def get_balance(self) -> float:
        """Get current account balance"""
        if not self.is_connected or not self.client:
            return 0.0
        
        try:
            return await self.client.balance()
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0
    
    async def get_payout(self, asset: str) -> int:
        """Get payout percentage for an asset"""
        if not self.is_connected or not self.client:
            return 0
        
        try:
            return await self.client.payout(asset)
        except Exception as e:
            logger.error(f"Error getting payout for {asset}: {e}")
            return 0
    
    def is_demo_account(self) -> bool:
        """Check if using demo account"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            return self.client.is_demo()
        except:
            return False


# Global instance
_monitor_instance: Optional[PocketOptionV2Monitor] = None


async def get_monitor() -> Optional[PocketOptionV2Monitor]:
    """Get or create the global monitor instance"""
    global _monitor_instance
    
    if _monitor_instance is None:
        ssid = os.environ.get('POCKET_OPTION_SSID', '')
        if not ssid:
            logger.error("POCKET_OPTION_SSID not found in environment")
            return None
        
        _monitor_instance = PocketOptionV2Monitor(ssid)
        await _monitor_instance.connect()
    
    return _monitor_instance


async def shutdown_monitor():
    """Shutdown the global monitor instance"""
    global _monitor_instance
    
    if _monitor_instance:
        await _monitor_instance.disconnect()
        _monitor_instance = None
        logger.info("🛑 Monitor shutdown complete")


# Example usage and testing
async def test_monitor():
    """Test the monitor with live data"""
    ssid = os.environ.get('POCKET_OPTION_SSID', '')
    if not ssid:
        logger.error("POCKET_OPTION_SSID not set")
        return
    
    monitor = PocketOptionV2Monitor(ssid)
    
    # Connect
    if not await monitor.connect():
        logger.error("Failed to connect")
        return
    
    # Define callback
    async def on_candle(asset: str, candle: Dict):
        print(f"🕯️ New {asset} candle: Close={candle['close']:.5f}")
    
    # Subscribe to EURUSD_OTC with 60-second candles
    await monitor.subscribe_candles("EURUSD_otc", 60, on_candle)
    
    # Monitor for 5 minutes
    await asyncio.sleep(300)
    
    # Cleanup
    await monitor.disconnect()


if __name__ == "__main__":
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_monitor())
