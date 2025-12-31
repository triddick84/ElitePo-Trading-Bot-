"""
Pocket Option API Client using BinaryOptionsToolsV2
====================================================

This module provides direct API access to Pocket Option for automated trading.
Uses the BinaryOptionsToolsV2 library which connects via WebSocket to Pocket Option.

Requirements:
- BinaryOptionsToolsV2 must be installed
- Valid SSID from Pocket Option account
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Trade execution result"""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    profit: float = 0.0
    result: Optional[str] = None  # "win", "loss", "draw"


@dataclass
class ConnectionState:
    """API connection state"""
    is_connected: bool = False
    is_demo: bool = True
    balance: float = 0.0
    ssid: str = ""
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    trades_executed: int = 0


class PocketOptionAPIClient:
    """
    Pocket Option API Client using BinaryOptionsToolsV2
    
    This provides direct WebSocket-based trading without needing browser automation.
    """
    
    def __init__(self, ssid: str, demo: bool = True):
        """
        Initialize Pocket Option API client
        
        Args:
            ssid: Session ID from Pocket Option (get from browser cookies)
            demo: True for demo account, False for real account
        """
        self.ssid = ssid
        self.demo = demo
        self.state = ConnectionState(ssid=ssid, is_demo=demo)
        self.client = None
        self._lock = asyncio.Lock()
        
        logger.info(f"🎯 PocketOption API Client initialized (demo={demo})")
    
    async def connect(self) -> Dict:
        """
        Connect to Pocket Option API
        
        Returns:
            Connection result with status
        """
        async with self._lock:
            try:
                if self.client and self.state.is_connected:
                    return {"success": True, "message": "Already connected"}
                
                logger.info("🔌 Connecting to Pocket Option API...")
                
                from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
                
                # Initialize the async client with SSID
                self.client = PocketOptionAsync(ssid=self.ssid, demo=self.demo)
                
                # Get initial balance to verify connection
                try:
                    balance = await asyncio.wait_for(
                        self.client.balance(),
                        timeout=30.0
                    )
                    self.state.balance = float(balance)
                    
                    # Check if session is valid (balance -1 means expired/invalid)
                    if self.state.balance < 0:
                        self.state.error = "SSID expired or invalid. Please get a fresh SSID from Pocket Option."
                        self.state.is_connected = False
                        logger.error("❌ SSID appears to be expired (balance: -1)")
                        return {
                            "success": False,
                            "error": "SSID expired or invalid. Please get a fresh SSID from Pocket Option browser.",
                            "instructions": [
                                "1. Close and reopen Pocket Option in browser",
                                "2. Login again if needed",
                                "3. Open Developer Tools (F12) → Network → WS",
                                "4. Refresh the page",
                                "5. Find the 'auth' message and copy it",
                                "6. Try connecting again with the new SSID"
                            ]
                        }
                    
                    self.state.is_connected = True
                    self.state.last_activity = datetime.now(timezone.utc)
                    self.state.error = None
                    
                    logger.info(f"✅ Connected! Balance: ${self.state.balance:.2f}")
                    
                    return {
                        "success": True,
                        "message": "Connected to Pocket Option",
                        "balance": self.state.balance,
                        "is_demo": self.demo
                    }
                    
                except asyncio.TimeoutError:
                    self.state.error = "Connection timeout"
                    logger.error("❌ Connection timeout")
                    return {"success": False, "error": "Connection timeout"}
                    
            except Exception as e:
                self.state.error = str(e)
                self.state.is_connected = False
                logger.error(f"❌ Connection failed: {e}")
                return {"success": False, "error": str(e)}
    
    async def disconnect(self) -> Dict:
        """Disconnect from Pocket Option API"""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
            
            self.state.is_connected = False
            logger.info("🔌 Disconnected from Pocket Option")
            return {"success": True, "message": "Disconnected"}
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_balance(self) -> Dict:
        """Get current account balance"""
        try:
            if not self.client or not self.state.is_connected:
                await self.connect()
            
            balance = await asyncio.wait_for(
                self.client.balance(),
                timeout=10.0
            )
            self.state.balance = float(balance)
            self.state.last_activity = datetime.now(timezone.utc)
            
            return {
                "success": True,
                "balance": self.state.balance
            }
            
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        duration: int = 60
    ) -> Dict:
        """
        Execute a trade on Pocket Option
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc', '#AAPL_otc')
            direction: 'call' or 'put'
            amount: Trade amount in dollars
            duration: Trade duration in seconds (min 5, usually 60, 120, 300, etc.)
        
        Returns:
            Trade execution result
        """
        async with self._lock:
            try:
                if not self.client or not self.state.is_connected:
                    conn_result = await self.connect()
                    if not conn_result['success']:
                        return conn_result
                
                logger.info(f"🎯 Executing trade: {direction.upper()} {asset} ${amount} for {duration}s")
                
                # Map direction to action
                action = "call" if direction.lower() in ["call", "up", "higher", "buy"] else "put"
                
                # Execute trade
                try:
                    order_id = await asyncio.wait_for(
                        self.client.trade(
                            asset=asset,
                            action=action,
                            amount=amount,
                            duration=duration
                        ),
                        timeout=30.0
                    )
                    
                    self.state.trades_executed += 1
                    self.state.last_activity = datetime.now(timezone.utc)
                    
                    logger.info(f"✅ Trade placed! Order ID: {order_id}")
                    
                    return {
                        "success": True,
                        "order_id": str(order_id),
                        "asset": asset,
                        "direction": direction,
                        "amount": amount,
                        "duration": duration,
                        "execution_time": datetime.now(timezone.utc).isoformat()
                    }
                    
                except asyncio.TimeoutError:
                    logger.error("❌ Trade execution timeout")
                    return {"success": False, "error": "Trade execution timeout"}
                
            except Exception as e:
                logger.error(f"❌ Trade error: {e}")
                return {"success": False, "error": str(e)}
    
    async def check_trade_result(self, order_id: str, timeout: float = None) -> Dict:
        """
        Check the result of a trade
        
        Args:
            order_id: The order ID from execute_trade
            timeout: Maximum time to wait for result (None for default)
        
        Returns:
            Trade result (win/loss/draw and profit)
        """
        try:
            if not self.client or not self.state.is_connected:
                return {"success": False, "error": "Not connected"}
            
            logger.info(f"🔍 Checking trade result for order: {order_id}")
            
            # Wait for trade result
            if timeout:
                result = await asyncio.wait_for(
                    self.client.check_win(order_id),
                    timeout=timeout
                )
            else:
                result = await self.client.check_win(order_id)
            
            # Parse result
            profit = float(result) if result else 0.0
            
            if profit > 0:
                outcome = "win"
            elif profit < 0:
                outcome = "loss"
            else:
                outcome = "draw"
            
            logger.info(f"📊 Trade result: {outcome} (profit: ${profit:.2f})")
            
            return {
                "success": True,
                "order_id": order_id,
                "result": outcome,
                "profit": profit
            }
            
        except asyncio.TimeoutError:
            return {"success": False, "error": "Result check timeout"}
        except Exception as e:
            logger.error(f"Check result error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_candles(
        self,
        asset: str,
        timeframe: int = 60,
        count: int = 100
    ) -> Dict:
        """
        Get historical candle data
        
        Args:
            asset: Asset symbol
            timeframe: Candle timeframe in seconds (1, 5, 15, 30, 60, 300)
            count: Number of candles to retrieve
        
        Returns:
            Candle data
        """
        try:
            if not self.client or not self.state.is_connected:
                await self.connect()
            
            candles = await asyncio.wait_for(
                self.client.candles(asset, timeframe, count),
                timeout=30.0
            )
            
            return {
                "success": True,
                "asset": asset,
                "timeframe": timeframe,
                "candles": candles
            }
            
        except Exception as e:
            logger.error(f"Candles error: {e}")
            return {"success": False, "error": str(e)}
    
    async def subscribe_candles(
        self,
        asset: str,
        timeframe: int = 60,
        callback = None
    ):
        """
        Subscribe to real-time candle updates
        
        Args:
            asset: Asset symbol
            timeframe: Candle timeframe in seconds
            callback: Function to call with each new candle
        """
        try:
            if not self.client or not self.state.is_connected:
                await self.connect()
            
            subscription = await self.client.subscribe_symbol(asset, timeframe)
            
            async for candle in subscription:
                if callback:
                    await callback(candle)
                yield candle
                
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            raise
    
    def get_status(self) -> Dict:
        """Get current connection status"""
        return {
            "success": True,
            "is_connected": self.state.is_connected,
            "is_demo": self.state.is_demo,
            "balance": self.state.balance,
            "trades_executed": self.state.trades_executed,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None,
            "error": self.state.error
        }


# Global client instance
_api_client: Optional[PocketOptionAPIClient] = None


async def get_api_client(ssid: str = None, demo: bool = True) -> PocketOptionAPIClient:
    """
    Get or create API client instance
    
    Args:
        ssid: Session ID (required on first call)
        demo: True for demo, False for real
    """
    global _api_client
    
    if _api_client is None:
        if not ssid:
            raise ValueError("SSID required for first connection")
        _api_client = PocketOptionAPIClient(ssid=ssid, demo=demo)
    
    return _api_client


async def reset_api_client():
    """Reset/disconnect the API client"""
    global _api_client
    
    if _api_client:
        await _api_client.disconnect()
        _api_client = None
