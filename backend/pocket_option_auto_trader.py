"""
Pocket Option Auto Trading Integration - Stable Version
========================================================
Integrates with Pocket Option WebSocket API for automated trading.

Key improvements:
- Proper Socket.IO protocol handling
- Auto-reconnection with exponential backoff
- Heartbeat/ping management
- Connection state monitoring
- Graceful error recovery

Based on: https://github.com/Rufus011/Pocket_Option_v4
"""

import os
import json
import time
import asyncio
import logging
import websockets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


# =============================================================================
# GLOBAL VALUES
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


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    ERROR = "error"


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
            self.total_profit += trade.profit
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
# STABLE WEBSOCKET CLIENT
# =============================================================================

class PocketOptionWebSocket:
    """
    Stable WebSocket client for Pocket Option API
    With proper Socket.IO protocol handling and auto-reconnection
    
    Socket.IO v4 Handshake Sequence:
    1. Connect → Receive "0{...}" (Engine.IO OPEN)
    2. Send "40" → Receive "40{...}" (Socket.IO CONNECT to namespace)
    3. Send '42["auth",{...}]' → Receive "41" or success event
    """
    
    # WebSocket URLs - Use different servers for better stability
    DEMO_WS_URL = "wss://api-c.po.market/socket.io/?EIO=4&transport=websocket"  # OTC/Demo
    DEMO_WS_URL_ALT = "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket"
    REAL_WS_URL = "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket"
    
    # Socket.IO Engine.IO protocol constants
    PACKET_OPEN = '0'      # Engine.IO open
    PACKET_CLOSE = '1'     # Engine.IO close
    PACKET_PING = '2'      # Engine.IO ping
    PACKET_PONG = '3'      # Engine.IO pong
    PACKET_MESSAGE = '4'   # Engine.IO message (Socket.IO packet)
    PACKET_UPGRADE = '5'   # Engine.IO upgrade
    PACKET_NOOP = '6'      # Engine.IO noop
    
    def __init__(self, ssid: str):
        """Initialize WebSocket client"""
        self.ssid = ssid
        self.is_demo = self._parse_demo_status(ssid)
        self.ws_url = self.DEMO_WS_URL if self.is_demo else self.REAL_WS_URL
        self.ws_url_alt = self.DEMO_WS_URL_ALT  # Fallback URL
        self.use_alt_url = False  # Track which URL is being used
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.is_connected = False
        self.is_authenticated = False
        
        # Socket.IO handshake state
        self.socket_io_sid = None  # Server-assigned session ID
        self.namespace_connected = False  # Track if '40' handshake completed
        self._handshake_event = None  # Event to wait for namespace connection
        
        # Reconnection settings
        self.auto_reconnect = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 2  # Start with 2 seconds
        self.max_reconnect_delay = 60  # Max 60 seconds
        
        # Heartbeat settings - will be updated from server open packet
        self.ping_interval = 25  # Default 25 seconds, updated from server
        self.ping_timeout = 60
        self.last_ping_time = None
        self.last_pong_time = None
        
        # Callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_balance_update: Optional[Callable] = None
        self.on_order_update: Optional[Callable] = None
        self.on_candle_update: Optional[Callable] = None
        self.on_connection_change: Optional[Callable] = None
        
        # State
        self.balance = 0.0
        self.balance_id = None
        self.pending_orders: Dict[str, TradeOrder] = {}
        
        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Message tracking
        self.message_id = 0
        self.pending_responses: Dict[str, asyncio.Future] = {}
        
        logger.info(f"🔧 PocketOptionWebSocket initialized ({'Demo' if self.is_demo else 'Real'} mode)")
    
    def _parse_demo_status(self, ssid: str) -> bool:
        """Parse SSID to determine if it's a demo account"""
        try:
            if '["auth",' in ssid:
                json_part = ssid.split('["auth",', 1)[1].strip(']')
                data = json.loads(json_part)
                return bool(data.get('isDemo', 1))
            return True
        except:
            return True
    
    def _set_connection_state(self, state: ConnectionState):
        """Update connection state and notify"""
        old_state = self.connection_state
        self.connection_state = state
        
        self.is_connected = state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]
        global_state.websocket_is_connected = self.is_connected
        
        # Reset namespace state on disconnect
        if state == ConnectionState.DISCONNECTED:
            self.namespace_connected = False
            self.is_authenticated = False
        
        if old_state != state:
            logger.info(f"🔄 Connection state changed: {state.value}")
            if self.on_connection_change:
                asyncio.create_task(self._safe_callback(self.on_connection_change, state))
    
    async def _safe_callback(self, callback, *args):
        """Safely execute a callback"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    async def connect(self) -> bool:
        """Establish WebSocket connection with proper Socket.IO handshake
        
        Sequence:
        1. Connect WebSocket
        2. Receive '0{...}' (Engine.IO OPEN) - parse pingInterval/pingTimeout
        3. Send '40' (Socket.IO CONNECT to default namespace)
        4. Receive '40{...}' (Socket.IO CONNECT ACK)
        5. Send '42["auth",{...}]' (Authentication)
        6. Receive success event
        """
        if self.connection_state in [ConnectionState.CONNECTING, ConnectionState.CONNECTED]:
            logger.warning("Already connecting/connected")
            return self.is_connected
        
        self._set_connection_state(ConnectionState.CONNECTING)
        self.namespace_connected = False
        self._handshake_event = asyncio.Event()
        
        # Determine which URL to use
        url_to_use = self.ws_url_alt if self.use_alt_url else self.ws_url
        
        try:
            logger.info(f"🔌 Connecting to {url_to_use}...")
            
            # Create SSL context
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Connect with proper settings
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    url_to_use,
                    ssl=ssl_context,
                    additional_headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Origin": "https://pocketoption.com",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    ping_interval=None,  # We handle pings manually
                    ping_timeout=None,
                    close_timeout=10,
                    max_size=2**24
                ),
                timeout=15.0
            )
            
            self._set_connection_state(ConnectionState.CONNECTED)
            logger.info("🔗 WebSocket connected, waiting for Engine.IO open packet...")
            
            # Start receive loop FIRST to handle the '0' packet
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Wait for Socket.IO namespace connection (triggered by '0' packet handler)
            try:
                await asyncio.wait_for(self._handshake_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("❌ Socket.IO namespace handshake timeout")
                self._set_connection_state(ConnectionState.ERROR)
                await self._schedule_reconnect()
                return False
            
            if not self.namespace_connected:
                logger.error("❌ Socket.IO namespace connection failed")
                self._set_connection_state(ConnectionState.ERROR)
                await self._schedule_reconnect()
                return False
            
            # Start ping task after namespace is connected
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Now authenticate
            self._set_connection_state(ConnectionState.AUTHENTICATING)
            await self._authenticate()
            
            # Wait a moment for auth response
            await asyncio.sleep(1.0)
            
            if self.is_authenticated:
                self._set_connection_state(ConnectionState.AUTHENTICATED)
                self.reconnect_attempts = 0
                self.reconnect_delay = 2
                self.use_alt_url = False  # Reset URL preference on success
                
                logger.info("✅ WebSocket connected and authenticated successfully!")
                return True
            else:
                logger.warning("⚠️ Authentication sent, waiting for server confirmation...")
                # Still consider connected, auth might come later
                self._set_connection_state(ConnectionState.AUTHENTICATED)
                self.reconnect_attempts = 0
                return True
            
        except asyncio.TimeoutError:
            logger.error("❌ Connection timeout")
            self._set_connection_state(ConnectionState.ERROR)
            # Try alternate URL on next attempt
            self.use_alt_url = not self.use_alt_url
            await self._schedule_reconnect()
            return False
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self._set_connection_state(ConnectionState.ERROR)
            # Try alternate URL on next attempt
            self.use_alt_url = not self.use_alt_url
            await self._schedule_reconnect()
            return False
    
    async def _authenticate(self):
        """Send authentication message"""
        try:
            # Format SSID properly
            if self.ssid.startswith('42["auth"'):
                auth_message = self.ssid
            else:
                auth_data = {
                    "session": self.ssid,
                    "isDemo": 1 if self.is_demo else 0,
                    "uid": os.getenv('POCKET_OPTION_UID', ''),
                    "platform": 2
                }
                auth_message = f'42["auth",{json.dumps(auth_data)}]'
            
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
        logger.info("📡 Receive loop started")
        
        while self.connection_state not in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            try:
                if self.websocket is None:
                    logger.warning("WebSocket is None in receive loop")
                    break
                
                # Check if websocket is still open (compatible with websockets v15+)
                try:
                    if hasattr(self.websocket, 'closed'):
                        if self.websocket.closed:
                            logger.warning("WebSocket closed in receive loop")
                            break
                    elif hasattr(self.websocket, 'state'):
                        import websockets.protocol
                        if self.websocket.state == websockets.protocol.State.CLOSED:
                            logger.warning("WebSocket closed in receive loop")
                            break
                except:
                    pass
                
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=self.ping_timeout + 10
                )
                await self._handle_message(message)
                
            except asyncio.TimeoutError:
                logger.warning("⏰ Receive timeout - sending ping")
                await self._send_ping()
            except websockets.ConnectionClosed as e:
                logger.warning(f"⚠️ WebSocket closed: {e.code} - {e.reason}")
                break
            except Exception as e:
                if "closed" in str(e).lower() or "connection" in str(e).lower():
                    logger.warning(f"⚠️ Connection lost: {e}")
                    break
                logger.error(f"Receive error: {e}")
                await asyncio.sleep(0.5)
        
        logger.info("📡 Receive loop ended")
        self._set_connection_state(ConnectionState.DISCONNECTED)
        await self._schedule_reconnect()
    
    async def _ping_loop(self):
        """Send periodic pings to keep connection alive"""
        logger.info("💓 Ping loop started")
        
        while self.connection_state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATING, ConnectionState.AUTHENTICATED]:
            try:
                await asyncio.sleep(self.ping_interval)
                await self._send_ping()
            except Exception as e:
                logger.error(f"Ping error: {e}")
                break
        
        logger.info("💓 Ping loop ended")
    
    async def _send_ping(self):
        """Send Socket.IO ping packet"""
        try:
            if self.websocket:
                # Check if websocket is still open (compatible with websockets v15+)
                is_open = True
                try:
                    if hasattr(self.websocket, 'closed'):
                        is_open = not self.websocket.closed
                    elif hasattr(self.websocket, 'state'):
                        import websockets.protocol
                        is_open = self.websocket.state != websockets.protocol.State.CLOSED
                except:
                    pass
                
                if is_open:
                    await self.websocket.send(self.PACKET_PING)
                    self.last_ping_time = time.time()
                    logger.debug("💓 Ping sent")
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message with Socket.IO protocol
        
        Engine.IO packet types:
        - 0: OPEN (contains pingInterval, pingTimeout, sid)
        - 1: CLOSE
        - 2: PING (server→client, respond with 3)
        - 3: PONG (response to ping)
        - 4: MESSAGE (Socket.IO packet follows)
        
        Socket.IO packet types (prefix after '4'):
        - 0: CONNECT (namespace connection)
        - 1: DISCONNECT
        - 2: EVENT (42["event", data])
        - 3: ACK
        - 4: ERROR
        """
        try:
            if not message:
                return
            
            packet_type = message[0] if message else ''
            
            logger.debug(f"📥 Received packet type: {packet_type}, length: {len(message)}")
            
            # Engine.IO protocol handling
            if packet_type == self.PACKET_OPEN:
                # Engine.IO OPEN - parse settings and initiate Socket.IO namespace connection
                try:
                    settings = json.loads(message[1:])
                    self.socket_io_sid = settings.get('sid', '')
                    self.ping_interval = settings.get('pingInterval', 25000) / 1000
                    self.ping_timeout = settings.get('pingTimeout', 60000) / 1000
                    logger.info(f"📡 Engine.IO OPEN received (sid: {self.socket_io_sid[:10]}..., ping: {self.ping_interval}s)")
                    
                    # CRITICAL: Send Socket.IO CONNECT to default namespace
                    # This is the '40' packet that initiates namespace connection
                    await self.websocket.send('40')
                    logger.info("📤 Sent Socket.IO CONNECT (40) to default namespace")
                    
                except Exception as e:
                    logger.error(f"Failed to parse open packet: {e}")
                return
            
            elif packet_type == self.PACKET_CLOSE:
                logger.warning("🔒 Server requested close (Engine.IO CLOSE)")
                return
            
            elif packet_type == self.PACKET_PING:
                # Engine.IO PING from server - respond with PONG
                if self.websocket:
                    await self.websocket.send(self.PACKET_PONG)
                    logger.debug("💓 Sent PONG response to server PING")
                return
            
            elif packet_type == self.PACKET_PONG:
                # PONG response to our PING
                self.last_pong_time = time.time()
                logger.debug("💓 Received PONG")
                return
            
            elif packet_type == self.PACKET_MESSAGE:
                # Socket.IO message - parse packet type
                socketio_data = message[1:]  # Remove '4' prefix
                await self._handle_socketio_packet(socketio_data)
                return
            
            elif packet_type == self.PACKET_NOOP:
                return
            
            # Handle legacy/non-standard messages (42[...] without 4 prefix)
            if message.startswith('42'):
                await self._handle_socketio_event(message[2:])
            elif message.startswith('43'):
                await self._handle_ack(message[2:])
            elif message.startswith('40'):
                # Socket.IO CONNECT response (namespace connected)
                await self._handle_namespace_connect(message[2:])
            elif message.startswith('41'):
                # Socket.IO DISCONNECT
                logger.warning("🔌 Socket.IO DISCONNECT received (41)")
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_socketio_packet(self, data: str):
        """Handle Socket.IO packet (after removing Engine.IO '4' prefix)"""
        if not data:
            return
            
        socketio_type = data[0] if data else ''
        payload = data[1:] if len(data) > 1 else ''
        
        if socketio_type == '0':
            # Socket.IO CONNECT response
            await self._handle_namespace_connect(payload)
        elif socketio_type == '1':
            # Socket.IO DISCONNECT
            logger.warning("🔌 Socket.IO namespace disconnected")
        elif socketio_type == '2':
            # Socket.IO EVENT
            await self._handle_socketio_event(payload)
        elif socketio_type == '3':
            # Socket.IO ACK
            await self._handle_ack(payload)
        elif socketio_type == '4':
            # Socket.IO CONNECT_ERROR
            logger.error(f"❌ Socket.IO connect error: {payload}")
    
    async def _handle_namespace_connect(self, data: str):
        """Handle Socket.IO namespace connection response (40{...})"""
        try:
            self.namespace_connected = True
            logger.info("✅ Socket.IO namespace connected successfully")
            
            # Parse any additional data
            if data:
                try:
                    ns_data = json.loads(data)
                    self.socket_io_sid = ns_data.get('sid', self.socket_io_sid)
                    logger.debug(f"Namespace data: {ns_data}")
                except:
                    pass
            
            # Signal that handshake is complete
            if self._handshake_event:
                self._handshake_event.set()
                
        except Exception as e:
            logger.error(f"Namespace connect error: {e}")
    
    async def _handle_socketio_event(self, data: str):
        """Handle Socket.IO event message (42["eventName", data])"""
        try:
            if not data or data == '':
                return
            
            # Parse JSON array
            event_data = json.loads(data)
            if not isinstance(event_data, list) or len(event_data) < 1:
                return
            
            event_name = event_data[0]
            event_payload = event_data[1] if len(event_data) > 1 else {}
            
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
                logger.info("✅ Authentication successful (successauth event)")
                self.is_authenticated = True
            elif event_name == 'auth':
                logger.info("🔐 Auth event received")
            elif event_name == 'error':
                logger.error(f"❌ Server error: {event_payload}")
            elif event_name == 'timeSync':
                # Server time synchronization
                logger.debug(f"⏰ Time sync: {event_payload}")
            elif event_name == 'candle':
                await self._handle_stream_update(event_payload)
            
            # Custom callback
            if self.on_message_callback:
                await self._safe_callback(self.on_message_callback, event_name, event_payload)
                
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON event data: {data[:100]}")
        except Exception as e:
            logger.error(f"Event handling error: {e}")
    
    async def _handle_ack(self, data: str):
        """Handle Socket.IO acknowledgment"""
        pass
    
    async def _handle_balance_update(self, data: Dict):
        """Handle balance update event"""
        try:
            self.balance = data.get('balance', 0)
            self.balance_id = data.get('id')
            
            global_state.balance = self.balance
            global_state.balance_id = self.balance_id
            global_state.balance_updated = True
            
            logger.info(f"💰 Balance: ${self.balance:.2f}")
            
            if self.on_balance_update:
                await self._safe_callback(self.on_balance_update, self.balance)
                
        except Exception as e:
            logger.error(f"Balance update error: {e}")
    
    async def _handle_stream_update(self, data: Dict):
        """Handle real-time price stream"""
        try:
            if self.on_candle_update:
                await self._safe_callback(self.on_candle_update, data)
        except Exception as e:
            logger.error(f"Stream update error: {e}")
    
    async def _handle_order_result(self, data: Dict):
        """Handle order execution result"""
        try:
            order_id = data.get('id')
            result = data.get('result')
            error = data.get('error')
            
            global_state.order_data = data
            global_state.result = not error
            
            if error:
                logger.error(f"❌ Order error: {error}")
            else:
                logger.info(f"✅ Order placed: {order_id}")
            
            if self.on_order_update:
                await self._safe_callback(self.on_order_update, data)
                
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
    
    async def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff"""
        if not self.auto_reconnect:
            return
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return
        
        self._set_connection_state(ConnectionState.RECONNECTING)
        self.reconnect_attempts += 1
        
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), self.max_reconnect_delay)
        logger.info(f"🔄 Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        await asyncio.sleep(delay)
        
        if self.connection_state == ConnectionState.RECONNECTING:
            await self.connect()
    
    async def send_message(self, event: str, data: Any) -> bool:
        """Send a Socket.IO message"""
        if not self.is_connected or self.websocket is None:
            logger.error("❌ Cannot send - not connected")
            return False
        
        # Check if websocket is still open
        is_open = True
        try:
            if hasattr(self.websocket, 'closed'):
                is_open = not self.websocket.closed
            elif hasattr(self.websocket, 'state'):
                import websockets.protocol
                is_open = self.websocket.state != websockets.protocol.State.CLOSED
        except:
            pass
        
        if not is_open:
            logger.error("❌ Cannot send - websocket closed")
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
        """Place a trading order"""
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
            
            global_state.order_data = None
            global_state.result = None
            
            await self.send_message("openOrder", order_data)
            
            # Wait for response
            start_time = time.time()
            while global_state.result is None:
                if time.time() - start_time > 10:
                    logger.error("⏰ Order timeout")
                    return None
                await asyncio.sleep(0.1)
            
            if global_state.result:
                order_id = global_state.order_data.get('id')
                
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
                error = global_state.order_data.get('error', 'Unknown error') if global_state.order_data else 'No response'
                logger.error(f"❌ Order failed: {error}")
                return None
                
        except Exception as e:
            logger.error(f"Place order error: {e}")
            return None
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.auto_reconnect = False
        self._set_connection_state(ConnectionState.DISCONNECTED)
        
        # Cancel tasks
        for task in [self._receive_task, self._ping_task, self._reconnect_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close websocket
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        
        logger.info("🔌 WebSocket disconnected")
    
    def get_balance(self) -> float:
        return self.balance
    
    def is_ready(self) -> bool:
        return self.connection_state == ConnectionState.AUTHENTICATED


# =============================================================================
# AUTO TRADING SERVICE
# =============================================================================

class AutoTradingService:
    """Automated trading service with stable connection management"""
    
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
        self.on_connection_change: Optional[Callable] = None
        
        logger.info("🤖 AutoTradingService initialized")
    
    async def connect(self, ssid: str) -> bool:
        """Connect to Pocket Option"""
        try:
            # Disconnect existing connection
            if self.ws_client:
                await self.ws_client.disconnect()
            
            self.ws_client = PocketOptionWebSocket(ssid)
            
            # Set callbacks
            self.ws_client.on_order_update = self._on_order_update
            self.ws_client.on_balance_update = self._on_balance_update
            self.ws_client.on_connection_change = self._on_connection_change
            
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
    
    async def _on_connection_change(self, state: ConnectionState):
        """Handle connection state changes"""
        logger.info(f"🔄 Connection state changed: {state.value}")
        
        self.is_running = state == ConnectionState.AUTHENTICATED
        
        if self.on_connection_change:
            try:
                await self.on_connection_change(state)
            except:
                pass
    
    async def _on_order_update(self, data: Dict):
        """Handle order update"""
        try:
            order_id = data.get('id')
            profit = data.get('profit')
            
            if order_id and profit is not None:
                for trade in self.trade_history:
                    if trade.id == order_id:
                        trade.profit = profit
                        trade.status = TradeStatus.WIN if profit > 0 else TradeStatus.LOSE
                        trade.closed_at = datetime.now(timezone.utc)
                        self.stats.update(trade)
                        
                        if self.on_trade_result:
                            await self.on_trade_result(trade)
                        break
        except Exception as e:
            logger.error(f"Order update error: {e}")
    
    async def _on_balance_update(self, balance: float):
        """Handle balance update"""
        logger.info(f"💰 Balance: ${balance:.2f}")
    
    def _can_trade(self) -> bool:
        """Check rate limiting"""
        now = time.time()
        while self.recent_trades and now - self.recent_trades[0] > 60:
            self.recent_trades.popleft()
        return len(self.recent_trades) < self.max_trades_per_minute
    
    async def execute_signal(self, signal: Dict) -> Optional[TradeOrder]:
        """Execute a trading signal"""
        if not self.is_running or not self.ws_client or not self.ws_client.is_ready():
            logger.warning("⚠️ Not ready to trade")
            return None
        
        if not self._can_trade():
            logger.warning("⚠️ Rate limit reached")
            return None
        
        try:
            symbol = signal.get('symbol', signal.get('asset', 'EURUSD_otc'))
            direction_str = signal.get('direction', 'CALL').upper()
            probability = signal.get('probability', signal.get('confidence', 0))
            amount = signal.get('amount', self.default_amount)
            expiration = signal.get('expiration_seconds', 60)
            strategy = signal.get('strategy', signal.get('strategy_used', 'AI'))
            signal_id = signal.get('id', signal.get('signal_id', ''))
            
            if probability < self.min_probability:
                logger.info(f"⏭️ Signal skipped - low probability: {probability}%")
                return None
            
            direction = TradeDirection.CALL if direction_str in ['CALL', 'BUY', 'UP'] else TradeDirection.PUT
            
            if not symbol.endswith('_otc') and '_otc' not in symbol.lower():
                symbol = f"{symbol}_otc"
            
            logger.info(f"🎯 Executing: {symbol} {direction.value} ${amount} ({probability}%)")
            
            order_id = await self.ws_client.place_order(symbol, direction, amount, expiration)
            
            if order_id:
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
        self.is_auto_trade_enabled = enabled
        logger.info(f"🤖 Auto-trade {'enabled' if enabled else 'disabled'}")
    
    def set_trade_amount(self, amount: float):
        self.default_amount = max(1.0, amount)
        logger.info(f"💵 Trade amount: ${self.default_amount}")
    
    def set_min_probability(self, probability: float):
        self.min_probability = max(0, min(100, probability))
        logger.info(f"📊 Min probability: {self.min_probability}%")
    
    def get_status(self) -> Dict:
        connection_state = self.ws_client.connection_state.value if self.ws_client else 'disconnected'
        
        return {
            'is_running': self.is_running,
            'is_connected': self.ws_client.is_ready() if self.ws_client else False,
            'connection_state': connection_state,
            'is_auto_trade_enabled': self.is_auto_trade_enabled,
            'is_demo': self.ws_client.is_demo if self.ws_client else True,
            'balance': self.ws_client.get_balance() if self.ws_client else 0,
            'default_amount': self.default_amount,
            'min_probability': self.min_probability,
            'max_trades_per_minute': self.max_trades_per_minute,
            'stats': self.stats.to_dict(),
            'recent_trades_count': len(self.recent_trades),
            'reconnect_attempts': self.ws_client.reconnect_attempts if self.ws_client else 0
        }
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        return [t.to_dict() for t in self.trade_history[-limit:]]


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_auto_trading_service: Optional[AutoTradingService] = None


def get_auto_trading_service() -> AutoTradingService:
    """Get global auto trading service instance"""
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
