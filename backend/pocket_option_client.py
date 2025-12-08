"""
Pocket Option API Client
Real-time integration with Pocket Option trading platform
Uses ChipaDevTeam PocketOptionAPI for live trading and data
"""
import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import os
from pocketoptionapi_async import AsyncPocketOptionClient, OrderDirection

logger = logging.getLogger(__name__)

class PocketOptionClient:
    """
    Wrapper for Pocket Option API with enhanced features
    - Real-time candle data streaming
    - Order execution (CALL/PUT)
    - Balance monitoring
    - Trade result tracking
    """
    
    def __init__(self, ssid: str = None, account_id: str = None, is_demo: bool = True):
        """
        Initialize Pocket Option client
        
        Args:
            ssid: Session ID from Pocket Option
            account_id: Trading account ID
            is_demo: True for demo account, False for live trading
        """
        # Get credentials from environment if not provided
        self.ssid = ssid or os.getenv('POCKET_OPTION_SSID')
        self.account_id = account_id or os.getenv('POCKET_OPTION_ACCOUNT_ID')
        self.is_demo = is_demo
        
        if not self.ssid:
            logger.warning("⚠️ No SSID provided - Pocket Option client will not connect")
            self.client = None
            return
        
        # Initialize API client
        self.client = PocketOptionAsync(
            ssid=self.ssid,
            is_demo=self.is_demo,
            enable_logging=True
        )
        
        self.connected = False
        logger.info(f"🔧 Pocket Option client initialized (Demo: {self.is_demo})")
    
    async def connect(self) -> bool:
        """
        Connect to Pocket Option platform
        
        Returns:
            True if connected successfully, False otherwise
        """
        if not self.client:
            logger.error("❌ Client not initialized - missing SSID")
            return False
        
        try:
            logger.info("🔌 Connecting to Pocket Option...")
            self.connected = await self.client.connect()
            
            if self.connected:
                balance = await self.get_balance()
                logger.info(f"✅ Connected successfully! Balance: ${balance:.2f}")
            else:
                logger.error("❌ Connection failed")
            
            return self.connected
        
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        if self.client and self.connected:
            try:
                await self.client.disconnect()
                self.connected = False
                logger.info("👋 Disconnected from Pocket Option")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    async def get_balance(self) -> float:
        """
        Get current account balance
        
        Returns:
            Balance amount
        """
        if not self.connected:
            await self.connect()
        
        try:
            balance = await self.client.get_balance()
            return float(balance)
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0
    
    async def get_candles(self, asset: str, timeframe: int, count: int = 100) -> List[Dict]:
        """
        Get historical candles for an asset
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc', 'BTCUSD')
            timeframe: Timeframe in seconds (60, 300, 900, etc.)
            count: Number of candles to retrieve
        
        Returns:
            List of candle dictionaries with OHLCV data
        """
        if not self.connected:
            await self.connect()
        
        try:
            # Clean asset name - add _otc suffix if not present
            if '_otc' not in asset.lower() and '_regular' not in asset.lower():
                asset = f"{asset}_otc"
            
            candles = await self.client.get_candles(asset, timeframe, count)
            
            # Convert to dict format
            candle_list = []
            for candle in candles:
                candle_list.append({
                    'timestamp': candle.timestamp,
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': getattr(candle, 'volume', 0)
                })
            
            logger.info(f"📊 Retrieved {len(candle_list)} candles for {asset} ({timeframe}s)")
            return candle_list
        
        except Exception as e:
            logger.error(f"Error getting candles for {asset}: {e}")
            return []
    
    async def place_order(
        self, 
        asset: str, 
        direction: str, 
        amount: float, 
        duration: int
    ) -> Dict[str, Any]:
        """
        Place a binary options order
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc')
            direction: 'CALL' or 'PUT' / 'BUY' or 'SELL'
            amount: Investment amount in dollars
            duration: Trade duration in seconds (min 5)
        
        Returns:
            Order result dictionary
        """
        if not self.connected:
            await self.connect()
        
        try:
            # Normalize direction
            direction = direction.upper()
            if direction in ['BUY', 'CALL']:
                order_direction = OrderDirection.CALL
            elif direction in ['SELL', 'PUT']:
                order_direction = OrderDirection.PUT
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            # Clean asset name
            if '_otc' not in asset.lower() and '_regular' not in asset.lower():
                asset = f"{asset}_otc"
            
            # Place order
            logger.info(f"📤 Placing {direction} order: {asset} ${amount} for {duration}s")
            order = await self.client.place_order(
                asset=asset,
                amount=amount,
                direction=order_direction,
                duration=duration
            )
            
            result = {
                'order_id': order.order_id,
                'status': order.status,
                'profit': order.profit if hasattr(order, 'profit') else None,
                'asset': asset,
                'direction': direction,
                'amount': amount,
                'duration': duration,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"✅ Order placed: ID={order.order_id}, Status={order.status}")
            return result
        
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    async def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions
        
        Returns:
            List of open position dictionaries
        """
        if not self.connected:
            await self.connect()
        
        try:
            positions = await self.client.get_open_positions()
            return [pos.__dict__ for pos in positions] if positions else []
        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.connected
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health status dictionary
        """
        status = {
            'connected': self.connected,
            'is_demo': self.is_demo,
            'account_id': self.account_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if self.connected:
            try:
                status['balance'] = await self.get_balance()
            except:
                status['balance'] = None
        
        return status


# Global client instance
pocket_option_client = None


async def get_pocket_option_client(is_demo: bool = True) -> Optional[PocketOptionClient]:
    """
    Get or create Pocket Option client instance
    
    Args:
        is_demo: Use demo account (True) or live account (False)
    
    Returns:
        PocketOptionClient instance or None if credentials missing
    """
    global pocket_option_client
    
    if pocket_option_client is None:
        ssid = os.getenv('POCKET_OPTION_SSID')
        account_id = os.getenv('POCKET_OPTION_ACCOUNT_ID')
        
        if not ssid:
            logger.warning("⚠️ POCKET_OPTION_SSID not found in environment")
            return None
        
        pocket_option_client = PocketOptionClient(
            ssid=ssid,
            account_id=account_id,
            is_demo=is_demo
        )
        
        # Connect on first initialization
        await pocket_option_client.connect()
    
    return pocket_option_client
