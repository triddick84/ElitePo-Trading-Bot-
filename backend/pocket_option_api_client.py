"""
Pocket Option API Client
Modern async implementation using pocketoptionapi-async library
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from collections import deque

# Import library components - use absolute imports to avoid conflicts with local models.py
from pocketoptionapi_async.client import AsyncPocketOptionClient
from pocketoptionapi_async.models import (
    OrderDirection,
    OrderStatus,
    ConnectionStatus,
    Asset,
    Balance,
    Candle,
    Order,
    OrderResult
)
from pocketoptionapi_async.exceptions import (
    PocketOptionError,
    AuthenticationError,
    ConnectionError as POConnectionError,
    TimeoutError as POTimeoutError
)

logger = logging.getLogger(__name__)


class PocketOptionAPIService:
    """
    Professional Pocket Option trading service
    Features: Live trading, real-time candles, balance tracking, order management
    """
    
    def __init__(self, ssid: str, is_demo: bool = True):
        """
        Initialize Pocket Option API Service
        
        Args:
            ssid: Session ID from Pocket Option (SSID format)
            is_demo: Use demo account (default: True)
        """
        self.ssid = ssid
        self.is_demo = is_demo
        self.client: Optional[AsyncPocketOptionClient] = None
        self.is_connected = False
        
        # State tracking
        self.balance: float = 0.0
        self.open_orders: Dict[str, Order] = {}
        self.completed_orders: deque = deque(maxlen=100)
        self.candle_streams: Dict[str, Dict] = {}
        
        # Statistics
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        
        logger.info(f"🔧 PocketOptionAPIService initialized ({'Demo' if is_demo else 'Real'} mode)")
    
    async def connect(self) -> bool:
        """
        Connect to Pocket Option
        
        Returns:
            bool: True if connection successful
        """
        try:
            logger.info("🔌 Connecting to Pocket Option...")
            
            # Initialize client
            self.client = AsyncPocketOptionClient(
                ssid=self.ssid,
                is_demo=self.is_demo,
                auto_reconnect=True,
                persistent_connection=True
            )
            
            # Connect
            await self.client.connect()
            
            # Verify connection
            if self.client.connection_status == ConnectionStatus.CONNECTED:
                self.is_connected = True
                
                # Get initial balance
                balance_info = await self.client.get_balance()
                if balance_info:
                    self.balance = float(balance_info.amount)
                
                logger.info(f"✅ Connected to Pocket Option!")
                logger.info(f"💰 Balance: ${self.balance:.2f} ({'Demo' if self.is_demo else 'Real'})")
                
                return True
            else:
                logger.error("❌ Connection failed - status not CONNECTED")
                return False
                
        except AuthenticationError as e:
            logger.error(f"❌ Authentication failed: {e}")
            logger.error("Check your SSID - it may be expired or invalid")
            self.is_connected = False
            return False
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        try:
            if self.client:
                await self.client.disconnect()
            
            self.is_connected = False
            logger.info("🔌 Disconnected from Pocket Option")
            
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    async def get_balance(self) -> float:
        """
        Get current account balance
        
        Returns:
            float: Current balance
        """
        if not self.is_connected or not self.client:
            return 0.0
        
        try:
            balance_info = await self.client.get_balance()
            if balance_info:
                self.balance = float(balance_info.amount)
            return self.balance
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return self.balance
    
    async def place_order(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int
    ) -> Optional[Dict]:
        """
        Place a trading order
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD', 'EURUSD_otc')
            amount: Trade amount in dollars
            direction: 'call' or 'put'
            duration: Trade duration in seconds
        
        Returns:
            dict: Order information with id, status, etc.
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Pocket Option")
            return None
        
        try:
            logger.info(f"📊 Placing {direction.upper()} order: {asset} ${amount} for {duration}s")
            
            # Convert direction
            order_direction = OrderDirection.CALL if direction.lower() == 'call' else OrderDirection.PUT
            
            # Place order
            order = await self.client.place_order(
                asset=asset,
                amount=amount,
                direction=order_direction,
                duration=duration
            )
            
            if order:
                # Track order
                self.open_orders[order.id] = order
                self.total_trades += 1
                
                logger.info(f"✅ Order placed: ID={order.id}")
                
                return {
                    "id": order.id,
                    "asset": asset,
                    "amount": amount,
                    "direction": direction,
                    "duration": duration,
                    "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                    "open_time": order.open_time.isoformat() if hasattr(order, 'open_time') else datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error("❌ Order placement failed - no order returned")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return None
    
    async def check_order_result(self, order_id: str) -> Optional[Dict]:
        """
        Check order result
        
        Args:
            order_id: Order ID
        
        Returns:
            dict: Order result with win/loss status and profit
        """
        if not self.is_connected or not self.client:
            return None
        
        try:
            # Get order result
            result = await self.client.get_order_result(order_id)
            
            if result:
                # Update statistics
                if result.status == OrderStatus.WON:
                    self.wins += 1
                elif result.status == OrderStatus.LOST:
                    self.losses += 1
                
                # Move to completed
                if order_id in self.open_orders:
                    self.completed_orders.append(self.open_orders[order_id])
                    del self.open_orders[order_id]
                
                return {
                    "order_id": order_id,
                    "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                    "result": "win" if result.status == OrderStatus.WON else "loss" if result.status == OrderStatus.LOST else "draw",
                    "profit": float(result.profit) if hasattr(result, 'profit') else 0.0,
                    "win_rate": (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking order result: {e}")
            return None
    
    async def get_candles(
        self,
        asset: str,
        period: int = 60,
        count: int = 100
    ) -> List[Dict]:
        """
        Get historical candles
        
        Args:
            asset: Asset symbol
            period: Candle period in seconds
            count: Number of candles
        
        Returns:
            list: List of candle dictionaries with OHLC data
        """
        if not self.is_connected or not self.client:
            return []
        
        try:
            candles = await self.client.get_candles(
                asset=asset,
                period=period,
                count=count
            )
            
            if candles:
                result = []
                for candle in candles:
                    result.append({
                        "time": candle.time.isoformat() if hasattr(candle, 'time') else None,
                        "open": float(candle.open),
                        "high": float(candle.high),
                        "low": float(candle.low),
                        "close": float(candle.close),
                        "volume": int(candle.volume) if hasattr(candle, 'volume') else 0
                    })
                
                logger.info(f"📊 Fetched {len(result)} candles for {asset}")
                return result
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            return []
    
    async def subscribe_candles(
        self,
        asset: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Subscribe to real-time candles
        
        Args:
            asset: Asset symbol
            callback: Optional callback function for new candles
        
        Returns:
            bool: Success status
        """
        if not self.is_connected or not self.client:
            return False
        
        try:
            logger.info(f"📊 Subscribing to real-time candles: {asset}")
            
            # Subscribe
            await self.client.subscribe_candles(asset)
            
            # Track subscription
            self.candle_streams[asset] = {
                "subscribed": True,
                "callback": callback,
                "last_candle": None
            }
            
            logger.info(f"✅ Subscribed to {asset}")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to candles: {e}")
            return False
    
    async def unsubscribe_candles(self, asset: str):
        """Unsubscribe from real-time candles"""
        try:
            if asset in self.candle_streams:
                await self.client.unsubscribe_candles(asset)
                del self.candle_streams[asset]
                logger.info(f"✅ Unsubscribed from {asset}")
                
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
    
    async def get_payout(self, asset: str) -> int:
        """
        Get payout percentage for an asset
        
        Args:
            asset: Asset symbol
        
        Returns:
            int: Payout percentage
        """
        if not self.is_connected or not self.client:
            return 0
        
        try:
            payouts = await self.client.get_payouts()
            if payouts and asset in payouts:
                return int(payouts[asset])
            return 0
            
        except Exception as e:
            logger.error(f"Error getting payout: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
        
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": win_rate,
            "balance": self.balance,
            "open_orders": len(self.open_orders),
            "is_demo": self.is_demo
        }
    
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            "is_connected": self.is_connected,
            "balance": self.balance,
            "is_demo": self.is_demo,
            "open_orders": len(self.open_orders),
            "subscribed_assets": list(self.candle_streams.keys()),
            "statistics": self.get_statistics()
        }


# Global instance
_api_service: Optional[PocketOptionAPIService] = None


async def get_api_service() -> Optional[PocketOptionAPIService]:
    """Get or create the global API service instance"""
    global _api_service
    
    if _api_service is None:
        ssid = os.environ.get('POCKET_OPTION_SSID', '')
        if not ssid:
            logger.error("POCKET_OPTION_SSID not found in environment")
            return None
        
        _api_service = PocketOptionAPIService(ssid=ssid, is_demo=True)
        await _api_service.connect()
    
    return _api_service


async def shutdown_api_service():
    """Shutdown the global API service"""
    global _api_service
    
    if _api_service:
        await _api_service.disconnect()
        _api_service = None
        logger.info("🛑 API Service shutdown complete")


# Example usage and testing
async def test_api_service():
    """Test the API service with live trading"""
    ssid = os.environ.get('POCKET_OPTION_SSID', '')
    if not ssid:
        logger.error("POCKET_OPTION_SSID not set")
        return
    
    service = PocketOptionAPIService(ssid=ssid, is_demo=True)
    
    # Connect
    if not await service.connect():
        logger.error("Failed to connect")
        return
    
    # Get balance
    balance = await service.get_balance()
    print(f"💰 Balance: ${balance}")
    
    # Get historical candles
    candles = await service.get_candles("EURUSD_otc", 60, 10)
    print(f"📊 Fetched {len(candles)} candles")
    
    # Place a test order (only in demo!)
    if service.is_demo:
        order = await service.place_order(
            asset="EURUSD_otc",
            amount=1.0,
            direction="call",
            duration=60
        )
        
        if order:
            print(f"✅ Order placed: {order['id']}")
            
            # Wait for result
            await asyncio.sleep(65)
            
            result = await service.check_order_result(order['id'])
            if result:
                print(f"📊 Result: {result['result']} - Profit: ${result['profit']}")
    
    # Get statistics
    stats = service.get_statistics()
    print(f"📈 Stats: {stats}")
    
    # Cleanup
    await service.disconnect()


if __name__ == "__main__":
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_api_service())
