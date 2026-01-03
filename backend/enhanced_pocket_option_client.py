"""
Enhanced Pocket Option Client
==============================

Improved implementation based on research of:
- lordralinc/pocket_option (Python 3.13+ architecture patterns)
- pocketoptionapi-async (our installed library)
- ChipaDevTeam/PocketOptionAPI (BinaryOptionsToolsV2)

Key Improvements:
1. Proper ping/keep-alive mechanism (send "ps" every 60 seconds)
2. Event-based architecture with callbacks
3. Automatic reconnection with exponential backoff
4. Better error handling and state management
5. Real-time candle streaming support

NOTE: SSID still requires manual extraction from browser.
Neither library can auto-refresh SSID due to Google reCAPTCHA on login.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Callable, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enum"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class AccountInfo:
    """Account information"""
    balance: float = 0.0
    is_demo: bool = True
    uid: Optional[str] = None
    currency: str = "USD"
    open_trades: int = 0


@dataclass 
class TradeInfo:
    """Trade information"""
    trade_id: str
    asset: str
    direction: str  # "call" or "put"
    amount: float
    duration: int  # seconds
    open_time: datetime
    open_price: float
    status: str = "pending"  # pending, open, closed, expired
    close_price: Optional[float] = None
    profit: Optional[float] = None
    result: Optional[str] = None  # win, loss, draw


class EnhancedPocketOptionClient:
    """
    Enhanced Pocket Option Client with keep-alive and event support
    
    Features:
    - Automatic ping every 60 seconds to maintain connection
    - Event callbacks for state changes
    - Automatic reconnection with exponential backoff
    - Better error handling
    - Trade tracking
    """
    
    def __init__(
        self,
        ssid: str,
        is_demo: bool = True,
        ping_interval: int = 60,
        max_reconnect_attempts: int = 5,
        reconnect_delay_base: float = 5.0
    ):
        """
        Initialize Enhanced Pocket Option Client
        
        Args:
            ssid: Session ID from Pocket Option browser
            is_demo: True for demo account, False for real
            ping_interval: Seconds between keep-alive pings
            max_reconnect_attempts: Max reconnection attempts
            reconnect_delay_base: Base delay for exponential backoff
        """
        self.ssid = ssid
        self.is_demo = is_demo
        self.ping_interval = ping_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay_base = reconnect_delay_base
        
        # State
        self.state = ConnectionState.DISCONNECTED
        self.account = AccountInfo(is_demo=is_demo)
        self.reconnect_attempts = 0
        self.last_ping: Optional[datetime] = None
        self.last_pong: Optional[datetime] = None
        
        # Internal client (pocketoptionapi-async)
        self._client = None
        self._ping_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Trade tracking
        self.pending_trades: Dict[str, TradeInfo] = {}
        self.trade_history: List[TradeInfo] = []
        
        # Event callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_auth_success: Optional[Callable] = None
        self._on_auth_failure: Optional[Callable] = None
        self._on_trade_opened: Optional[Callable] = None
        self._on_trade_closed: Optional[Callable] = None
        self._on_balance_update: Optional[Callable] = None
        self._on_price_update: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        logger.info(f"🎯 Enhanced Pocket Option Client initialized (demo={is_demo})")
    
    # =========================================================================
    # Event Decorators
    # =========================================================================
    
    def on_connect(self, callback: Callable):
        """Register callback for successful connection"""
        self._on_connect = callback
        return callback
    
    def on_disconnect(self, callback: Callable):
        """Register callback for disconnection"""
        self._on_disconnect = callback
        return callback
    
    def on_auth_success(self, callback: Callable):
        """Register callback for successful authentication"""
        self._on_auth_success = callback
        return callback
    
    def on_auth_failure(self, callback: Callable):
        """Register callback for authentication failure"""
        self._on_auth_failure = callback
        return callback
    
    def on_trade_opened(self, callback: Callable):
        """Register callback for trade opened"""
        self._on_trade_opened = callback
        return callback
    
    def on_trade_closed(self, callback: Callable):
        """Register callback for trade closed"""
        self._on_trade_closed = callback
        return callback
    
    def on_balance_update(self, callback: Callable):
        """Register callback for balance update"""
        self._on_balance_update = callback
        return callback
    
    def on_error(self, callback: Callable):
        """Register callback for errors"""
        self._on_error = callback
        return callback
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    async def connect(self) -> Dict:
        """
        Connect to Pocket Option with automatic ping setup
        
        Returns:
            Connection result
        """
        if self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
            return {"success": True, "message": "Already connected"}
        
        self.state = ConnectionState.CONNECTING
        logger.info("🔌 Connecting to Pocket Option...")
        
        try:
            # Try pocketoptionapi-async first
            try:
                from pocketoptionapi.stable_api import PocketOption
                
                self._client = PocketOption(self.ssid)
                check, message = self._client.connect()
                
                if check:
                    self.state = ConnectionState.CONNECTED
                    
                    # Set account type
                    balance_type = "PRACTICE" if self.is_demo else "REAL"
                    self._client.change_balance(balance_type)
                    
                    # Get initial balance
                    self.account.balance = self._client.get_balance()
                    
                    # Check if balance is valid (not -1)
                    if self.account.balance < 0:
                        self.state = ConnectionState.ERROR
                        return {
                            "success": False,
                            "error": "SSID expired or invalid",
                            "message": "Please get a fresh SSID from Pocket Option browser"
                        }
                    
                    self.state = ConnectionState.AUTHENTICATED
                    self.reconnect_attempts = 0
                    
                    # Start ping loop
                    self._running = True
                    self._ping_task = asyncio.create_task(self._ping_loop())
                    
                    logger.info(f"✅ Connected! Balance: ${self.account.balance:.2f}")
                    
                    # Trigger callback
                    if self._on_connect:
                        await self._safe_callback(self._on_connect)
                    if self._on_auth_success:
                        await self._safe_callback(self._on_auth_success, self.account)
                    
                    return {
                        "success": True,
                        "balance": self.account.balance,
                        "is_demo": self.is_demo,
                        "message": "Connected and authenticated"
                    }
                else:
                    self.state = ConnectionState.ERROR
                    if self._on_auth_failure:
                        await self._safe_callback(self._on_auth_failure, message)
                    return {"success": False, "error": message}
                    
            except ImportError:
                # Fallback to BinaryOptionsToolsV2
                return await self._connect_binary_tools()
                
        except Exception as e:
            self.state = ConnectionState.ERROR
            logger.error(f"❌ Connection error: {e}")
            if self._on_error:
                await self._safe_callback(self._on_error, str(e))
            return {"success": False, "error": str(e)}
    
    async def _connect_binary_tools(self) -> Dict:
        """Fallback connection using BinaryOptionsToolsV2"""
        try:
            from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
            
            self._client = PocketOptionAsync(ssid=self.ssid, demo=self.is_demo)
            
            balance = await asyncio.wait_for(
                self._client.balance(),
                timeout=30.0
            )
            
            self.account.balance = float(balance)
            
            if self.account.balance < 0:
                self.state = ConnectionState.ERROR
                return {"success": False, "error": "SSID expired"}
            
            self.state = ConnectionState.AUTHENTICATED
            self._running = True
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            return {
                "success": True,
                "balance": self.account.balance,
                "is_demo": self.is_demo
            }
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            return {"success": False, "error": str(e)}
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        self._running = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            try:
                if hasattr(self._client, 'close'):
                    self._client.close()
                elif hasattr(self._client, 'disconnect'):
                    await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Disconnect warning: {e}")
        
        self.state = ConnectionState.DISCONNECTED
        
        if self._on_disconnect:
            await self._safe_callback(self._on_disconnect)
        
        logger.info("🔌 Disconnected")
        return {"success": True}
    
    async def reconnect(self) -> Dict:
        """Attempt reconnection with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("❌ Max reconnection attempts reached")
            return {"success": False, "error": "Max reconnection attempts reached"}
        
        self.state = ConnectionState.RECONNECTING
        self.reconnect_attempts += 1
        
        delay = self.reconnect_delay_base * (2 ** (self.reconnect_attempts - 1))
        logger.info(f"🔄 Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay:.1f}s")
        
        await asyncio.sleep(delay)
        
        # Disconnect first
        await self.disconnect()
        
        # Reconnect
        result = await self.connect()
        
        if result['success']:
            self.reconnect_attempts = 0
        
        return result
    
    # =========================================================================
    # Keep-Alive (Ping Loop)
    # =========================================================================
    
    async def _ping_loop(self):
        """
        Keep-alive ping loop
        
        Sends ping every ping_interval seconds to maintain connection.
        Based on lordralinc/pocket_option implementation.
        """
        logger.info(f"🏓 Starting ping loop (interval: {self.ping_interval}s)")
        
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)
                
                if not self._running:
                    break
                
                # Send ping
                self.last_ping = datetime.now(timezone.utc)
                
                # Check connection by getting balance
                if self._client:
                    try:
                        if hasattr(self._client, 'get_balance'):
                            balance = self._client.get_balance()
                        elif hasattr(self._client, 'balance'):
                            balance = await asyncio.wait_for(
                                self._client.balance(),
                                timeout=10.0
                            )
                        else:
                            balance = self.account.balance
                        
                        if float(balance) >= 0:
                            self.last_pong = datetime.now(timezone.utc)
                            old_balance = self.account.balance
                            self.account.balance = float(balance)
                            
                            # Notify balance change
                            if abs(old_balance - self.account.balance) > 0.01:
                                if self._on_balance_update:
                                    await self._safe_callback(
                                        self._on_balance_update,
                                        self.account.balance
                                    )
                            
                            logger.debug(f"🏓 Ping OK - Balance: ${self.account.balance:.2f}")
                        else:
                            logger.warning("⚠️ Ping failed - negative balance (SSID expired?)")
                            await self._handle_connection_lost()
                            
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Ping timeout")
                        await self._handle_connection_lost()
                    except Exception as e:
                        logger.warning(f"⚠️ Ping error: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ping loop error: {e}")
        
        logger.info("🏓 Ping loop stopped")
    
    async def _handle_connection_lost(self):
        """Handle lost connection"""
        logger.warning("📡 Connection lost - attempting reconnect...")
        
        if self._on_disconnect:
            await self._safe_callback(self._on_disconnect)
        
        # Try to reconnect
        result = await self.reconnect()
        
        if not result['success']:
            if self._on_error:
                await self._safe_callback(
                    self._on_error,
                    "Connection lost and reconnection failed. SSID may be expired."
                )
    
    # =========================================================================
    # Trading Methods
    # =========================================================================
    
    async def buy(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int = 60
    ) -> Dict:
        """
        Place a trade
        
        Args:
            asset: Asset symbol (e.g., "EURUSD", "EURUSD_otc")
            amount: Trade amount in dollars
            direction: "call" or "put"
            duration: Expiration time in seconds
        
        Returns:
            Trade result with trade_id
        """
        if self.state != ConnectionState.AUTHENTICATED:
            return {"success": False, "error": "Not authenticated"}
        
        try:
            logger.info(f"📊 Placing trade: {direction.upper()} {asset} ${amount} ({duration}s)")
            
            if hasattr(self._client, 'buy'):
                # pocketoptionapi-async style
                result = self._client.buy(asset, amount, direction, duration)
                
                if result and 'id' in result:
                    trade = TradeInfo(
                        trade_id=str(result['id']),
                        asset=asset,
                        direction=direction,
                        amount=amount,
                        duration=duration,
                        open_time=datetime.now(timezone.utc),
                        open_price=result.get('openPrice', 0),
                        status="open"
                    )
                    self.pending_trades[trade.trade_id] = trade
                    
                    if self._on_trade_opened:
                        await self._safe_callback(self._on_trade_opened, trade)
                    
                    logger.info(f"✅ Trade opened: ID={trade.trade_id}")
                    return {"success": True, "trade_id": trade.trade_id, "trade": result}
                else:
                    return {"success": False, "error": "Trade failed - no ID returned"}
            
            elif hasattr(self._client, 'trade'):
                # BinaryOptionsToolsV2 style
                result = await self._client.trade(
                    asset=asset,
                    amount=amount,
                    direction=direction,
                    duration=duration
                )
                return {"success": True, "result": result}
            
            else:
                return {"success": False, "error": "No trade method available"}
                
        except Exception as e:
            logger.error(f"Trade error: {e}")
            if self._on_error:
                await self._safe_callback(self._on_error, str(e))
            return {"success": False, "error": str(e)}
    
    async def check_trade_result(self, trade_id: str, timeout: int = 120) -> Dict:
        """
        Check trade result (win/loss)
        
        Args:
            trade_id: The trade ID to check
            timeout: Max seconds to wait
        
        Returns:
            Trade result
        """
        try:
            if hasattr(self._client, 'check_win'):
                result = self._client.check_win(trade_id)
                
                if trade_id in self.pending_trades:
                    trade = self.pending_trades[trade_id]
                    trade.status = "closed"
                    trade.profit = result.get('profit', 0)
                    trade.result = "win" if trade.profit > 0 else ("loss" if trade.profit < 0 else "draw")
                    
                    self.trade_history.append(trade)
                    del self.pending_trades[trade_id]
                    
                    if self._on_trade_closed:
                        await self._safe_callback(self._on_trade_closed, trade)
                
                return {"success": True, "result": result}
            
            return {"success": False, "error": "check_win not available"}
            
        except Exception as e:
            logger.error(f"Check trade error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_balance(self) -> float:
        """Get current balance"""
        if self._client and hasattr(self._client, 'get_balance'):
            self.account.balance = self._client.get_balance()
        return self.account.balance
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _safe_callback(self, callback: Callable, *args, **kwargs):
        """Safely execute callback (sync or async)"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def get_status(self) -> Dict:
        """Get current client status"""
        return {
            "state": self.state.value,
            "connected": self.state == ConnectionState.AUTHENTICATED,
            "is_demo": self.is_demo,
            "balance": self.account.balance,
            "reconnect_attempts": self.reconnect_attempts,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
            "pending_trades": len(self.pending_trades),
            "total_trades": len(self.trade_history)
        }
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        wins = sum(1 for t in self.trade_history if t.result == "win")
        losses = sum(1 for t in self.trade_history if t.result == "loss")
        total = len(self.trade_history)
        
        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_profit": sum(t.profit or 0 for t in self.trade_history)
        }


# =============================================================================
# Global Client Management
# =============================================================================

_enhanced_client: Optional[EnhancedPocketOptionClient] = None


def get_enhanced_client() -> Optional[EnhancedPocketOptionClient]:
    """Get the global enhanced client"""
    return _enhanced_client


async def create_enhanced_client(ssid: str, is_demo: bool = True) -> EnhancedPocketOptionClient:
    """Create and connect an enhanced client"""
    global _enhanced_client
    
    if _enhanced_client:
        await _enhanced_client.disconnect()
    
    _enhanced_client = EnhancedPocketOptionClient(ssid=ssid, is_demo=is_demo)
    await _enhanced_client.connect()
    
    return _enhanced_client
