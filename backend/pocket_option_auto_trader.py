"""
Pocket Option Auto Trading Integration
======================================
Integrates Pocket_Option_v4 WebSocket API with our AI Signal Generation system
for fully automated trading execution.

Features:
- WebSocket connection to Pocket Option
- SSID-based authentication with auto-detection of Demo/Real
- Automatic trade execution based on AI signals
- Real-time balance tracking
- Trade history and statistics
- Integration with Telegram notifications

Based on: https://github.com/Rufus011/Pocket_Option_v4
"""

import os
import json
import time
import asyncio
import logging
import threading
import websockets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


# =============================================================================
# GLOBAL VALUES (Similar to Pocket_Option_v4 global_value.py)
# =============================================================================

class GlobalState:
    """Global state management for the trading system"""
    def __init__(self):
        self.SSID = ""
        self.DEMO = True
        self.balance = 0.0
        self.balance_id = None
        self.balance_updated = False
        self.websocket_is_connected = False
        self.order_data = None
        self.order_open = False
        self.order_closed = set()
        self.result = None
        self.stat = []
        self.asset_manager = None
        self.server_timestamp = None
        
    def reset(self):
        self.balance = 0.0
        self.balance_updated = False
        self.websocket_is_connected = False
        self.order_data = None
        self.result = None

global_state = GlobalState()


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class TradeDirection(Enum):
    CALL = "call"
    PUT = "put"
    BUY = "call"
    SELL = "put"


class TradeStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"
    CANCELLED = "cancelled"


@dataclass
class TradeOrder:
    """Represents a trade order"""
    id: str = ""
    symbol: str = ""
    direction: TradeDirection = TradeDirection.CALL
    amount: float = 1.0
    expiration_seconds: int = 60
    status: TradeStatus = TradeStatus.PENDING
    entry_price: float = 0.0
    exit_price: float = 0.0
    profit: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    signal_id: str = ""
    strategy: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'direction': self.direction.value,
            'amount': self.amount,
            'expiration_seconds': self.expiration_seconds,
            'status': self.status.value,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'profit': self.profit,
            'created_at': self.created_at.isoformat(),
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'signal_id': self.signal_id,
            'strategy': self.strategy
        }


@dataclass 
class TradingStats:
    """Trading statistics"""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    total_profit: float = 0.0
    win_rate: float = 0.0
    
    def update(self, trade: TradeOrder):
        self.total_trades += 1
        if trade.status == TradeStatus.WIN:
            self.wins += 1
            self.total_profit += trade.profit
        elif trade.status == TradeStatus.LOSE:
            self.losses += 1
            self.total_profit += trade.profit  # Will be negative
        else:
            self.draws += 1
        
        if self.wins + self.losses > 0:
            self.win_rate = (self.wins / (self.wins + self.losses)) * 100
    
    def to_dict(self) -> Dict:
        return {
            'total_trades': self.total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'total_profit': self.total_profit,
            'win_rate': f"{self.win_rate:.1f}%"
        }


# =============================================================================
# WEBSOCKET CLIENT
# =============================================================================

class PocketOptionWebSocket:
    """
    WebSocket client for Pocket Option API
    Based on Pocket_Option_v4 implementation
    """
    
    # WebSocket URLs
    DEMO_WS_URL = "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket"
    REAL_WS_URL = "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket"
    
    def __init__(self, ssid: str):
        """
        Initialize WebSocket client
        
        Args:
            ssid: SSID authentication string
        """
        self.ssid = ssid
        self.is_demo = self._parse_demo_status(ssid)
        self.ws_url = self.DEMO_WS_URL if self.is_demo else self.REAL_WS_URL
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_authenticated = False
        
        # Callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_balance_update: Optional[Callable] = None
        self.on_order_update: Optional[Callable] = None
        self.on_candle_update: Optional[Callable] = None
        
        # State
        self.balance = 0.0
        self.balance_id = None
        self.pending_orders: Dict[str, TradeOrder] = {}
        self.message_queue = asyncio.Queue()
        
        # Keep-alive
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        logger.info(f"🔧 PocketOptionWebSocket initialized ({'Demo' if self.is_demo else 'Real'} mode)")
    
    def _parse_demo_status(self, ssid: str) -> bool:
        """
        Parse SSID to determine if it's a demo account
        
        Args:
            ssid: SSID string like '42["auth",{"session":"...","isDemo":1...}]'
        
        Returns:
            True for demo account, False for real account
        """
        try:
            if '["auth",' in ssid:
                json_part = ssid.split('["auth",', 1)[1].strip(']')
                data = json.loads(json_part)
                return bool(data.get('isDemo', 0))
            return True  # Default to demo for safety
        except Exception as e:
            logger.error(f"Error parsing SSID: {e}")
            return True  # Default to demo for safety
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection
        
        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"🔌 Connecting to {self.ws_url}...")
            
            # Use websockets.connect with compatible parameters
            self.websocket = await websockets.connect(
                self.ws_url,
                additional_headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                ping_interval=25,
                ping_timeout=60,
                close_timeout=10
            )
            
            self.is_connected = True
            global_state.websocket_is_connected = True
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Wait for initial handshake
            await asyncio.sleep(1)
            
            # Authenticate
            await self._authenticate()
            
            logger.info("✅ WebSocket connected and authenticated")
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.is_connected = False
            return False
    
    async def _authenticate(self):
        """Send authentication message with SSID"""
        try:
            # Send SSID for authentication
            auth_message = self.ssid
            await self.websocket.send(auth_message)
            
            self.is_authenticated = True
            global_state.SSID = self.ssid
            global_state.DEMO = self.is_demo
            
            logger.info("🔐 Authentication sent")
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise
    
    async def _receive_loop(self):
        """Background task to receive messages"""
        while self.is_connected:
            try:
                if self.websocket is None:
                    break
                    
                message = await self.websocket.recv()
                await self._handle_message(message)
                
            except websockets.ConnectionClosed:
                logger.warning("⚠️ WebSocket connection closed")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                await asyncio.sleep(0.1)
    
    async def _handle_message(self, message: str):
        """
        Handle incoming WebSocket message
        
        Args:
            message: Raw message string
        """
        try:
            # Handle Socket.IO protocol messages
            if message.startswith('0'):
                # Connection established
                logger.debug("Socket.IO connection established")
                return
            elif message.startswith('2'):
                # Ping - respond with pong
                await self.websocket.send('3')
                return
            elif message.startswith('3'):
                # Pong response
                return
            elif message.startswith('40'):
                # Namespace connection
                logger.debug("Namespace connected")
                return
            elif message.startswith('42'):
                # Event message
                await self._handle_event(message[2:])
            elif message.startswith('43'):
                # Ack message
                await self._handle_ack(message[2:])
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_event(self, data: str):
        """Handle Socket.IO event message"""
        try:
            event_data = json.loads(data)
            if not isinstance(event_data, list) or len(event_data) < 2:
                return
            
            event_name = event_data[0]
            event_payload = event_data[1]
            
            logger.debug(f"📩 Event: {event_name}")
            
            # Handle different event types
            if event_name == 'updateBalance':
                await self._handle_balance_update(event_payload)
            elif event_name == 'updateStream':
                await self._handle_stream_update(event_payload)
            elif event_name == 'openOrderResult':
                await self._handle_order_result(event_payload)
            elif event_name == 'deals':
                await self._handle_deals(event_payload)
            elif event_name == 'successauth':
                logger.info("✅ Successfully authenticated")
                self.is_authenticated = True
            elif event_name == 'error':
                logger.error(f"❌ Server error: {event_payload}")
            
            # Call custom callback if set
            if self.on_message_callback:
                await self.on_message_callback(event_name, event_payload)
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in event: {data[:100]}")
        except Exception as e:
            logger.error(f"Event handling error: {e}")
    
    async def _handle_ack(self, data: str):
        """Handle Socket.IO acknowledgment message"""
        try:
            # Ack format: id[data]
            pass
        except Exception as e:
            logger.error(f"Ack handling error: {e}")
    
    async def _handle_balance_update(self, data: Dict):
        """Handle balance update event"""
        try:
            self.balance = data.get('balance', 0)
            self.balance_id = data.get('id')
            
            global_state.balance = self.balance
            global_state.balance_id = self.balance_id
            global_state.balance_updated = True
            
            logger.info(f"💰 Balance updated: ${self.balance:.2f}")
            
            if self.on_balance_update:
                await self.on_balance_update(self.balance)
                
        except Exception as e:
            logger.error(f"Balance update error: {e}")
    
    async def _handle_stream_update(self, data: Dict):
        """Handle real-time price stream update"""
        try:
            if self.on_candle_update:
                await self.on_candle_update(data)
        except Exception as e:
            logger.error(f"Stream update error: {e}")
    
    async def _handle_order_result(self, data: Dict):
        """Handle order execution result"""
        try:
            order_id = data.get('id')
            result = data.get('result')
            error = data.get('error')
            
            global_state.order_data = data
            global_state.result = result
            
            if error:
                logger.error(f"❌ Order error: {error}")
                global_state.result = False
            else:
                logger.info(f"✅ Order placed: {order_id}")
                global_state.result = True
            
            if self.on_order_update:
                await self.on_order_update(data)
                
        except Exception as e:
            logger.error(f"Order result error: {e}")
    
    async def _handle_deals(self, data: Dict):
        """Handle deal updates (trade results)"""
        try:
            deals = data.get('deals', [])
            for deal in deals:
                order_id = deal.get('id')
                profit = deal.get('profit', 0)
                
                if order_id in self.pending_orders:
                    order = self.pending_orders[order_id]
                    order.profit = profit
                    order.status = TradeStatus.WIN if profit > 0 else TradeStatus.LOSE
                    order.closed_at = datetime.now(timezone.utc)
                    
                    logger.info(f"{'✅ WIN' if profit > 0 else '❌ LOSE'}: Order {order_id} - ${profit:.2f}")
                    
        except Exception as e:
            logger.error(f"Deals handling error: {e}")
    
    async def send_message(self, event: str, data: Any):
        """
        Send a message to the WebSocket server
        
        Args:
            event: Event name
            data: Event data
        """
        if not self.is_connected or self.websocket is None:
            logger.error("❌ Cannot send - not connected")
            return False
        
        try:
            message = f'42{json.dumps([event, data])}'
            await self.websocket.send(message)
            logger.debug(f"📤 Sent: {event}")
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    async def place_order(self, symbol: str, direction: TradeDirection, 
                          amount: float, expiration: int) -> Optional[str]:
        """
        Place a trading order
        
        Args:
            symbol: Asset symbol (e.g., "EURUSD_otc")
            direction: Trade direction (CALL/PUT)
            amount: Trade amount
            expiration: Expiration time in seconds
        
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            request_id = f"order_{int(time.time() * 1000)}"
            
            order_data = {
                "asset": symbol,
                "amount": amount,
                "action": direction.value,
                "isDemo": 1 if self.is_demo else 0,
                "requestId": request_id,
                "optionType": 100,
                "time": expiration
            }
            
            # Reset global state for this order
            global_state.order_data = None
            global_state.result = None
            
            # Send order
            await self.send_message("openOrder", order_data)
            
            # Wait for response with timeout
            start_time = time.time()
            while global_state.result is None:
                if time.time() - start_time > 5:
                    logger.error("⏰ Order timeout")
                    return None
                await asyncio.sleep(0.1)
            
            if global_state.result:
                order_id = global_state.order_data.get('id')
                
                # Track the order
                order = TradeOrder(
                    id=order_id,
                    symbol=symbol,
                    direction=direction,
                    amount=amount,
                    expiration_seconds=expiration,
                    status=TradeStatus.OPEN
                )
                self.pending_orders[order_id] = order
                
                logger.info(f"✅ Order placed: {order_id}")
                return order_id
            else:
                error = global_state.order_data.get('error', 'Unknown error')
                logger.error(f"❌ Order failed: {error}")
                return None
                
        except Exception as e:
            logger.error(f"Place order error: {e}")
            return None
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.is_connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
        
        if self.websocket:
            await self.websocket.close()
            
        global_state.websocket_is_connected = False
        logger.info("🔌 WebSocket disconnected")
    
    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance
    
    def is_ready(self) -> bool:
        """Check if client is ready for trading"""
        return self.is_connected and self.is_authenticated


# =============================================================================
# AUTO TRADING SERVICE
# =============================================================================

class AutoTradingService:
    """
    Automated trading service that integrates AI signals with Pocket Option
    """
    
    def __init__(self):
        self.ws_client: Optional[PocketOptionWebSocket] = None
        self.is_running = False
        self.is_auto_trade_enabled = False
        
        # Trading settings
        self.default_amount = 1.0
        self.max_trades_per_minute = 5
        self.min_probability = 75.0
        self.allowed_symbols = ['EURUSD_otc', 'GBPUSD_otc', 'AUDCAD_otc']
        
        # Statistics
        self.stats = TradingStats()
        self.trade_history: List[TradeOrder] = []
        
        # Rate limiting
        self.recent_trades = deque(maxlen=100)
        
        # Callbacks
        self.on_trade_executed: Optional[Callable] = None
        self.on_trade_result: Optional[Callable] = None
        
        logger.info("🤖 AutoTradingService initialized")
    
    async def connect(self, ssid: str) -> bool:
        """
        Connect to Pocket Option
        
        Args:
            ssid: SSID authentication string
        
        Returns:
            True if connected successfully
        """
        try:
            self.ws_client = PocketOptionWebSocket(ssid)
            
            # Set callbacks
            self.ws_client.on_order_update = self._on_order_update
            self.ws_client.on_balance_update = self._on_balance_update
            
            success = await self.ws_client.connect()
            
            if success:
                self.is_running = True
                logger.info("✅ AutoTradingService connected")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        self.is_running = False
        self.is_auto_trade_enabled = False
        
        if self.ws_client:
            await self.ws_client.disconnect()
        
        logger.info("🛑 AutoTradingService disconnected")
    
    async def _on_order_update(self, data: Dict):
        """Handle order update from WebSocket"""
        try:
            order_id = data.get('id')
            profit = data.get('profit')
            
            if order_id and profit is not None:
                # Find and update the trade
                for trade in self.trade_history:
                    if trade.id == order_id:
                        trade.profit = profit
                        trade.status = TradeStatus.WIN if profit > 0 else TradeStatus.LOSE
                        trade.closed_at = datetime.now(timezone.utc)
                        
                        # Update stats
                        self.stats.update(trade)
                        
                        # Call callback
                        if self.on_trade_result:
                            await self.on_trade_result(trade)
                        
                        break
        except Exception as e:
            logger.error(f"Order update error: {e}")
    
    async def _on_balance_update(self, balance: float):
        """Handle balance update"""
        logger.info(f"💰 Balance: ${balance:.2f}")
    
    def _can_trade(self) -> bool:
        """Check if we can place a new trade (rate limiting)"""
        now = time.time()
        
        # Remove old trades from recent_trades
        while self.recent_trades and now - self.recent_trades[0] > 60:
            self.recent_trades.popleft()
        
        return len(self.recent_trades) < self.max_trades_per_minute
    
    async def execute_signal(self, signal: Dict) -> Optional[TradeOrder]:
        """
        Execute a trading signal
        
        Args:
            signal: Signal dictionary with symbol, direction, probability, etc.
        
        Returns:
            TradeOrder if executed, None otherwise
        """
        if not self.is_running or not self.ws_client or not self.ws_client.is_ready():
            logger.warning("⚠️ Not ready to trade")
            return None
        
        if not self._can_trade():
            logger.warning("⚠️ Rate limit reached")
            return None
        
        try:
            # Extract signal info
            symbol = signal.get('symbol', signal.get('asset', 'EURUSD_otc'))
            direction_str = signal.get('direction', 'CALL').upper()
            probability = signal.get('probability', signal.get('confidence', 0))
            amount = signal.get('amount', self.default_amount)
            expiration = signal.get('expiration_seconds', 60)
            strategy = signal.get('strategy', signal.get('strategy_used', 'AI'))
            signal_id = signal.get('id', signal.get('signal_id', ''))
            
            # Validate probability
            if probability < self.min_probability:
                logger.info(f"⏭️ Signal skipped - low probability: {probability}%")
                return None
            
            # Parse direction
            if direction_str in ['CALL', 'BUY', 'UP']:
                direction = TradeDirection.CALL
            else:
                direction = TradeDirection.PUT
            
            # Normalize symbol
            if not symbol.endswith('_otc') and '_otc' not in symbol.lower():
                symbol = f"{symbol}_otc"
            
            logger.info(f"🎯 Executing signal: {symbol} {direction.value} ${amount} ({probability}%)")
            
            # Place order
            order_id = await self.ws_client.place_order(
                symbol=symbol,
                direction=direction,
                amount=amount,
                expiration=expiration
            )
            
            if order_id:
                # Create trade record
                trade = TradeOrder(
                    id=order_id,
                    symbol=symbol,
                    direction=direction,
                    amount=amount,
                    expiration_seconds=expiration,
                    status=TradeStatus.OPEN,
                    signal_id=signal_id,
                    strategy=strategy
                )
                
                self.trade_history.append(trade)
                self.recent_trades.append(time.time())
                
                # Call callback
                if self.on_trade_executed:
                    await self.on_trade_executed(trade)
                
                logger.info(f"✅ Trade executed: {order_id}")
                return trade
            else:
                logger.error("❌ Failed to place order")
                return None
                
        except Exception as e:
            logger.error(f"Execute signal error: {e}")
            return None
    
    def enable_auto_trade(self, enabled: bool = True):
        """Enable or disable auto trading"""
        self.is_auto_trade_enabled = enabled
        logger.info(f"🤖 Auto-trade {'enabled' if enabled else 'disabled'}")
    
    def set_trade_amount(self, amount: float):
        """Set default trade amount"""
        self.default_amount = max(1.0, amount)
        logger.info(f"💵 Trade amount set to ${self.default_amount}")
    
    def set_min_probability(self, probability: float):
        """Set minimum probability threshold"""
        self.min_probability = max(0, min(100, probability))
        logger.info(f"📊 Min probability set to {self.min_probability}%")
    
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            'is_running': self.is_running,
            'is_connected': self.ws_client.is_ready() if self.ws_client else False,
            'is_auto_trade_enabled': self.is_auto_trade_enabled,
            'is_demo': self.ws_client.is_demo if self.ws_client else True,
            'balance': self.ws_client.get_balance() if self.ws_client else 0,
            'default_amount': self.default_amount,
            'min_probability': self.min_probability,
            'max_trades_per_minute': self.max_trades_per_minute,
            'stats': self.stats.to_dict(),
            'recent_trades_count': len(self.recent_trades)
        }
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history"""
        return [t.to_dict() for t in self.trade_history[-limit:]]


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_auto_trading_service: Optional[AutoTradingService] = None


def get_auto_trading_service() -> AutoTradingService:
    """Get the global auto trading service instance"""
    global _auto_trading_service
    if _auto_trading_service is None:
        _auto_trading_service = AutoTradingService()
    return _auto_trading_service


async def initialize_auto_trading(ssid: str) -> bool:
    """Initialize and connect the auto trading service"""
    service = get_auto_trading_service()
    return await service.connect(ssid)


async def shutdown_auto_trading():
    """Shutdown the auto trading service"""
    global _auto_trading_service
    if _auto_trading_service:
        await _auto_trading_service.disconnect()
        _auto_trading_service = None
