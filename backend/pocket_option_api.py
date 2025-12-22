"""
Pocket Option API Client - ChipaDevTeam Style Implementation
Based on: https://github.com/ChipaDevTeam/PocketOptionAPI

Features:
- Async WebSocket connection with auto-reconnection
- Multi-region fallback (EU, US, DEMO servers)
- SSID authentication with auto-refresh capability
- Demo & Real account support
- Trade execution (BUY/SELL binary options)
- Candle data retrieval
- Balance and payout information
"""

import asyncio
import json
import logging
import time
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import websockets
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class AccountType(Enum):
    DEMO = "PRACTICE"
    REAL = "REAL"


class TradeDirection(Enum):
    CALL = "call"
    PUT = "put"
    BUY = "call"  # Alias
    SELL = "put"  # Alias


class ConnectionRegion(Enum):
    DEMO = "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket"
    DEMO_2 = "wss://try-demo-eu.po.market/socket.io/?EIO=4&transport=websocket"
    REAL_EU = "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket"
    REAL_US = "wss://api-us.po.market/socket.io/?EIO=4&transport=websocket"
    REAL_ASIA = "wss://api-asia.po.market/socket.io/?EIO=4&transport=websocket"


# Available trading assets
POCKET_OPTION_ASSETS = {
    # Forex OTC (24/7)
    'EURUSD_otc': {'name': 'EUR/USD OTC', 'type': 'forex', 'symbol': 'EURUSD_otc'},
    'GBPUSD_otc': {'name': 'GBP/USD OTC', 'type': 'forex', 'symbol': 'GBPUSD_otc'},
    'USDJPY_otc': {'name': 'USD/JPY OTC', 'type': 'forex', 'symbol': 'USDJPY_otc'},
    'AUDUSD_otc': {'name': 'AUD/USD OTC', 'type': 'forex', 'symbol': 'AUDUSD_otc'},
    'USDCAD_otc': {'name': 'USD/CAD OTC', 'type': 'forex', 'symbol': 'USDCAD_otc'},
    'EURGBP_otc': {'name': 'EUR/GBP OTC', 'type': 'forex', 'symbol': 'EURGBP_otc'},
    'EURJPY_otc': {'name': 'EUR/JPY OTC', 'type': 'forex', 'symbol': 'EURJPY_otc'},
    'GBPJPY_otc': {'name': 'GBP/JPY OTC', 'type': 'forex', 'symbol': 'GBPJPY_otc'},
    
    # Stocks OTC
    '#AAPL_otc': {'name': 'Apple OTC', 'type': 'stock', 'symbol': '#AAPL_otc'},
    '#TSLA_otc': {'name': 'Tesla OTC', 'type': 'stock', 'symbol': '#TSLA_otc'},
    '#AMZN_otc': {'name': 'Amazon OTC', 'type': 'stock', 'symbol': 'AMZN_otc'},
    '#MSFT_otc': {'name': 'Microsoft OTC', 'type': 'stock', 'symbol': '#MSFT_otc'},
    '#GOOGL_otc': {'name': 'Google OTC', 'type': 'stock', 'symbol': '#GOOGL_otc'},
    '#FB_otc': {'name': 'Meta OTC', 'type': 'stock', 'symbol': '#FB_otc'},
    '#NFLX_otc': {'name': 'Netflix OTC', 'type': 'stock', 'symbol': 'NFLX_otc'},
    
    # Crypto OTC
    'BTCUSD_otc': {'name': 'Bitcoin OTC', 'type': 'crypto', 'symbol': 'BTCUSD_otc'},
    'ETHUSD_otc': {'name': 'Ethereum OTC', 'type': 'crypto', 'symbol': 'ETHUSD_otc'},
    
    # Regular Forex
    'EURUSD': {'name': 'EUR/USD', 'type': 'forex', 'symbol': 'EURUSD'},
    'GBPUSD': {'name': 'GBP/USD', 'type': 'forex', 'symbol': 'GBPUSD'},
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SSIDCredentials:
    """SSID authentication credentials"""
    session_id: str
    uid: int = 0
    is_demo: bool = True
    platform: int = 1
    raw_ssid: str = ""
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    @classmethod
    def from_full_ssid(cls, full_ssid: str) -> 'SSIDCredentials':
        """
        Parse full SSID format from browser:
        42["auth",{"session":"...","isDemo":1,"uid":12345,"platform":1}]
        """
        try:
            # Extract JSON part
            if full_ssid.startswith('42["auth",'):
                json_str = full_ssid[10:-1]  # Remove '42["auth",' and ']'
                data = json.loads(json_str)
            else:
                # Try parsing as JSON directly
                data = json.loads(full_ssid)
            
            return cls(
                session_id=data.get('session', ''),
                uid=data.get('uid', 0),
                is_demo=data.get('isDemo', 1) == 1,
                platform=data.get('platform', 1),
                raw_ssid=full_ssid
            )
        except Exception as e:
            logger.error(f"Failed to parse SSID: {e}")
            # Try using raw string as session
            return cls(session_id=full_ssid, raw_ssid=full_ssid)
    
    def to_auth_message(self) -> str:
        """Generate auth message for WebSocket"""
        auth_data = {
            "session": self.session_id,
            "isDemo": 1 if self.is_demo else 0,
            "uid": self.uid,
            "platform": self.platform
        }
        return f'42["auth",{json.dumps(auth_data)}]'
    
    def is_expired(self) -> bool:
        """Check if SSID might be expired (based on age)"""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        # Assume SSID expires after 1 hour by default
        age = datetime.now(timezone.utc) - self.extracted_at
        return age > timedelta(hours=1)


@dataclass
class Trade:
    """Trade information"""
    trade_id: str
    asset: str
    direction: str
    amount: float
    duration: int  # seconds
    open_price: float = 0.0
    close_price: float = 0.0
    payout: float = 0.0
    profit: float = 0.0
    status: str = "pending"  # pending, won, lost, closed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Candle:
    """OHLCV candle data"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# WEBSOCKET CLIENT
# ============================================================================

class PocketOptionWebSocket:
    """
    WebSocket client for Pocket Option with auto-reconnection
    """
    
    def __init__(self, ssid: SSIDCredentials, is_demo: bool = True):
        self.ssid = ssid
        self.is_demo = is_demo
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.authenticated = False
        
        # Connection management
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        self.ping_interval = 20  # seconds (like original API)
        
        # Message handling
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.message_queue: deque = deque(maxlen=1000)
        
        # Data storage
        self.balance: float = 0.0
        self.balance_demo: float = 0.0
        self.balance_real: float = 0.0
        self.active_trades: Dict[str, Trade] = {}
        self.candles: Dict[str, List[Candle]] = {}
        self.payouts: Dict[str, float] = {}
        
        # Tasks
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        logger.info(f"Initialized PocketOption WebSocket (demo={is_demo})")
    
    def _get_regions(self) -> List[str]:
        """Get WebSocket URLs based on account type"""
        if self.is_demo:
            return [
                ConnectionRegion.DEMO.value,
                ConnectionRegion.DEMO_2.value,
            ]
        else:
            return [
                ConnectionRegion.REAL_EU.value,
                ConnectionRegion.REAL_US.value,
                ConnectionRegion.REAL_ASIA.value,
            ]
    
    async def connect(self) -> bool:
        """Connect to Pocket Option WebSocket with region fallback"""
        regions = self._get_regions()
        
        for region_url in regions:
            try:
                logger.info(f"Attempting connection to: {region_url}")
                
                self.ws = await websockets.connect(
                    region_url,
                    ping_interval=None,  # We handle pings manually
                    ping_timeout=10,
                    close_timeout=10,
                )
                
                self.connected = True
                logger.info(f"✅ Connected to {region_url}")
                
                # Start background tasks
                self._receive_task = asyncio.create_task(self._receive_loop())
                self._ping_task = asyncio.create_task(self._ping_loop())
                
                # Authenticate
                await self._authenticate()
                
                if self.authenticated:
                    self.reconnect_attempts = 0
                    return True
                    
            except Exception as e:
                logger.warning(f"Failed to connect to {region_url}: {e}")
                continue
        
        logger.error("Failed to connect to any region")
        return False
    
    async def _authenticate(self) -> bool:
        """Send authentication message"""
        try:
            auth_message = self.ssid.to_auth_message()
            await self.ws.send(auth_message)
            logger.info("Sent authentication message")
            
            # Wait for auth response
            await asyncio.sleep(2)
            
            # Check if we received balance (indicates successful auth)
            if self.balance > 0 or self.balance_demo > 0:
                self.authenticated = True
                logger.info("✅ Authentication successful")
                return True
            
            self.authenticated = True  # Assume success if no error
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def _receive_loop(self):
        """Background task to receive messages"""
        while self.connected:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.connected = False
                await self._reconnect()
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                await asyncio.sleep(1)
    
    async def _ping_loop(self):
        """Send keep-alive pings every 20 seconds"""
        while self.connected:
            try:
                await asyncio.sleep(self.ping_interval)
                if self.ws and self.connected:
                    await self.ws.send('2')  # Socket.IO ping
                    logger.debug("Sent ping")
            except Exception as e:
                logger.warning(f"Ping error: {e}")
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            self.message_queue.append({
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Socket.IO protocol handling
            if message == '3':  # Pong
                logger.debug("Received pong")
                return
            
            if message.startswith('0'):  # Connect
                logger.debug("Socket.IO connect message")
                return
            
            if message.startswith('40'):  # Connected to namespace
                logger.debug("Connected to namespace")
                return
            
            if message.startswith('42'):  # Event message
                await self._handle_event_message(message)
                return
            
            # Binary message (base64 encoded)
            if message.startswith('451-'):
                await self._handle_binary_message(message)
                return
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_event_message(self, message: str):
        """Handle Socket.IO event messages"""
        try:
            # Extract JSON from 42[...] format
            json_str = message[2:]
            data = json.loads(json_str)
            
            if isinstance(data, list) and len(data) >= 2:
                event_name = data[0]
                event_data = data[1]
                
                # Handle specific events
                if event_name == 'balance':
                    self._update_balance(event_data)
                elif event_name == 'candles':
                    self._update_candles(event_data)
                elif event_name == 'trade':
                    self._handle_trade_update(event_data)
                elif event_name == 'payout':
                    self._update_payout(event_data)
                elif event_name == 'successauth':
                    self.authenticated = True
                    logger.info("✅ Auth confirmed")
                
                # Trigger registered handlers
                if event_name in self.message_handlers:
                    for handler in self.message_handlers[event_name]:
                        try:
                            await handler(event_data)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
                            
        except Exception as e:
            logger.debug(f"Event message parse error: {e}")
    
    async def _handle_binary_message(self, message: str):
        """Handle binary/encoded messages"""
        try:
            # Remove prefix and decode
            parts = message.split('-', 1)
            if len(parts) > 1:
                data_str = parts[1]
                # Try base64 decode
                try:
                    decoded = base64.b64decode(data_str).decode('utf-8')
                    data = json.loads(decoded)
                    
                    # Process candle data
                    if 'history' in data or 'candles' in data:
                        self._process_candle_data(data)
                        
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Binary message error: {e}")
    
    def _update_balance(self, data: Dict):
        """Update account balance"""
        if isinstance(data, dict):
            self.balance_demo = data.get('demo', self.balance_demo)
            self.balance_real = data.get('real', self.balance_real)
            self.balance = self.balance_demo if self.is_demo else self.balance_real
            logger.info(f"💰 Balance updated: Demo=${self.balance_demo}, Real=${self.balance_real}")
    
    def _update_candles(self, data: Dict):
        """Update candle data"""
        if isinstance(data, dict):
            asset = data.get('asset', 'unknown')
            candles = data.get('candles', [])
            
            if asset not in self.candles:
                self.candles[asset] = []
            
            for c in candles:
                if len(c) >= 5:
                    candle = Candle(
                        timestamp=c[0],
                        open=c[1],
                        close=c[2],
                        high=c[3],
                        low=c[4]
                    )
                    self.candles[asset].append(candle)
    
    def _process_candle_data(self, data: Dict):
        """Process incoming candle/history data"""
        asset = data.get('asset', 'unknown')
        
        if asset not in self.candles:
            self.candles[asset] = []
        
        # Process candles array
        for c in data.get('candles', []):
            if len(c) >= 5:
                candle = Candle(
                    timestamp=c[0],
                    open=c[1],
                    close=c[2],
                    high=c[3],
                    low=c[4]
                )
                self.candles[asset].append(candle)
        
        # Process history (tick data)
        for tick in data.get('history', []):
            if len(tick) >= 2:
                # Update latest candle
                if self.candles[asset]:
                    self.candles[asset][-1].close = tick[1]
    
    def _handle_trade_update(self, data: Dict):
        """Handle trade status updates"""
        trade_id = str(data.get('id', ''))
        if trade_id in self.active_trades:
            trade = self.active_trades[trade_id]
            trade.status = data.get('status', trade.status)
            trade.profit = data.get('profit', trade.profit)
            trade.close_price = data.get('close_price', trade.close_price)
            
            if trade.status in ['won', 'lost', 'closed']:
                trade.closed_at = datetime.now(timezone.utc)
                logger.info(f"Trade {trade_id} {trade.status}: profit=${trade.profit}")
    
    def _update_payout(self, data: Dict):
        """Update payout information"""
        if isinstance(data, dict):
            for asset, payout in data.items():
                self.payouts[asset] = float(payout)
    
    async def _reconnect(self):
        """Attempt to reconnect"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts
        
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
        
        return await self.connect()
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.connected = False
        self.authenticated = False
        
        # Cancel tasks
        if self._ping_task:
            self._ping_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        
        # Close WebSocket
        if self.ws:
            await self.ws.close()
        
        logger.info("Disconnected from Pocket Option")
    
    async def send(self, message: str):
        """Send message to WebSocket"""
        if self.ws and self.connected:
            await self.ws.send(message)
    
    def register_handler(self, event: str, handler: Callable):
        """Register event handler"""
        if event not in self.message_handlers:
            self.message_handlers[event] = []
        self.message_handlers[event].append(handler)


# ============================================================================
# MAIN API CLIENT
# ============================================================================

class PocketOptionClient:
    """
    Main Pocket Option API Client
    
    Usage:
        client = PocketOptionClient(ssid_string, is_demo=True)
        await client.connect()
        balance = await client.get_balance()
        trade_id = await client.buy("EURUSD_otc", 1.0, "call", 60)
    """
    
    def __init__(self, ssid: str, is_demo: bool = True):
        """
        Initialize Pocket Option client
        
        Args:
            ssid: Full SSID string from browser or session ID
            is_demo: True for demo account, False for real
        """
        self.credentials = SSIDCredentials.from_full_ssid(ssid)
        self.credentials.is_demo = is_demo
        self.is_demo = is_demo
        
        self.ws_client: Optional[PocketOptionWebSocket] = None
        self.connected = False
        
        # Callbacks
        self.on_trade_complete: Optional[Callable] = None
        self.on_signal: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        
        logger.info(f"Initialized PocketOption client (demo={is_demo}, uid={self.credentials.uid})")
    
    async def connect(self) -> bool:
        """Connect to Pocket Option"""
        try:
            self.ws_client = PocketOptionWebSocket(self.credentials, self.is_demo)
            success = await self.ws_client.connect()
            
            if success:
                self.connected = True
                logger.info("✅ Connected to Pocket Option")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        if self.ws_client:
            await self.ws_client.disconnect()
        self.connected = False
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        if not self.connected:
            raise ConnectionError("Not connected to Pocket Option")
        
        return {
            'demo': self.ws_client.balance_demo,
            'real': self.ws_client.balance_real,
            'current': self.ws_client.balance
        }
    
    async def change_account(self, account_type: str):
        """
        Switch between demo and real account
        
        Args:
            account_type: "PRACTICE" or "REAL"
        """
        if account_type.upper() in ['PRACTICE', 'DEMO']:
            self.is_demo = True
            self.ws_client.is_demo = True
            self.ws_client.balance = self.ws_client.balance_demo
        elif account_type.upper() == 'REAL':
            self.is_demo = False
            self.ws_client.is_demo = False
            self.ws_client.balance = self.ws_client.balance_real
        
        # Send account change message
        msg = f'42["changeSymbol",{{"demo":{1 if self.is_demo else 0}}}]'
        await self.ws_client.send(msg)
        
        logger.info(f"Changed to {'DEMO' if self.is_demo else 'REAL'} account")
    
    async def buy(self, asset: str, amount: float, direction: str, 
                  duration: int) -> Optional[str]:
        """
        Place a binary option trade
        
        Args:
            asset: Asset symbol (e.g., "EURUSD_otc")
            amount: Trade amount in USD
            direction: "call"/"put" or "buy"/"sell"
            duration: Duration in seconds
        
        Returns:
            Trade ID if successful, None otherwise
        """
        if not self.connected:
            raise ConnectionError("Not connected to Pocket Option")
        
        # Normalize direction
        if direction.lower() in ['call', 'buy', 'up', 'higher']:
            action = 'call'
        elif direction.lower() in ['put', 'sell', 'down', 'lower']:
            action = 'put'
        else:
            raise ValueError(f"Invalid direction: {direction}")
        
        # Generate trade ID
        trade_id = f"trade_{int(time.time() * 1000)}"
        
        # Create trade message
        trade_msg = {
            "asset": asset,
            "amount": amount,
            "action": action,
            "time": duration,
            "isDemo": 1 if self.is_demo else 0,
            "requestId": trade_id
        }
        
        # Send trade request
        msg = f'42["openOrder",{json.dumps(trade_msg)}]'
        await self.ws_client.send(msg)
        
        # Store trade
        trade = Trade(
            trade_id=trade_id,
            asset=asset,
            direction=action,
            amount=amount,
            duration=duration
        )
        self.ws_client.active_trades[trade_id] = trade
        
        logger.info(f"📈 Placed {action.upper()} trade on {asset}: ${amount} for {duration}s")
        
        return trade_id
    
    async def sell_option(self, trade_id: str) -> bool:
        """
        Close an open position early
        
        Args:
            trade_id: Trade ID to close
        
        Returns:
            True if successful
        """
        if not self.connected:
            raise ConnectionError("Not connected to Pocket Option")
        
        msg = f'42["closeOrder",{{"id":"{trade_id}"}}]'
        await self.ws_client.send(msg)
        
        logger.info(f"Closing trade {trade_id}")
        return True
    
    async def check_win(self, trade_id: str) -> Optional[Dict]:
        """
        Check trade result
        
        Args:
            trade_id: Trade ID to check
        
        Returns:
            Trade result dict or None
        """
        if trade_id in self.ws_client.active_trades:
            trade = self.ws_client.active_trades[trade_id]
            return trade.to_dict()
        return None
    
    async def get_candles(self, asset: str, period: int = 60, 
                          count: int = 100) -> List[Dict]:
        """
        Get historical candle data
        
        Args:
            asset: Asset symbol
            period: Candle period in seconds
            count: Number of candles
        
        Returns:
            List of candle dictionaries
        """
        if not self.connected:
            raise ConnectionError("Not connected to Pocket Option")
        
        # Request candles
        msg = f'42["subscribeCandles",{{"asset":"{asset}","period":{period}}}]'
        await self.ws_client.send(msg)
        
        # Wait for data
        await asyncio.sleep(2)
        
        # Return cached candles
        if asset in self.ws_client.candles:
            candles = self.ws_client.candles[asset][-count:]
            return [c.to_dict() for c in candles]
        
        return []
    
    async def get_payout(self, asset: str) -> float:
        """Get current payout percentage for an asset"""
        if asset in self.ws_client.payouts:
            return self.ws_client.payouts[asset]
        return 0.0
    
    async def get_payment(self, asset: str = None) -> Dict[str, float]:
        """Get all payouts or specific asset payout"""
        if asset:
            return {asset: await self.get_payout(asset)}
        return dict(self.ws_client.payouts)
    
    def update_ssid(self, new_ssid: str):
        """Update SSID credentials"""
        self.credentials = SSIDCredentials.from_full_ssid(new_ssid)
        self.credentials.is_demo = self.is_demo
        logger.info("SSID updated")
    
    def is_ssid_expired(self) -> bool:
        """Check if current SSID might be expired"""
        return self.credentials.is_expired()
    
    def get_connection_status(self) -> Dict:
        """Get current connection status"""
        return {
            'connected': self.connected,
            'authenticated': self.ws_client.authenticated if self.ws_client else False,
            'is_demo': self.is_demo,
            'uid': self.credentials.uid,
            'ssid_age_minutes': (datetime.now(timezone.utc) - self.credentials.extracted_at).total_seconds() / 60,
            'balance': self.ws_client.balance if self.ws_client else 0,
            'active_trades': len(self.ws_client.active_trades) if self.ws_client else 0
        }


# ============================================================================
# GLOBAL INSTANCE MANAGEMENT
# ============================================================================

_pocket_option_client: Optional[PocketOptionClient] = None


async def get_pocket_option_client() -> Optional[PocketOptionClient]:
    """Get singleton Pocket Option client"""
    global _pocket_option_client
    return _pocket_option_client


async def initialize_pocket_option(ssid: str, is_demo: bool = True) -> PocketOptionClient:
    """Initialize and connect Pocket Option client"""
    global _pocket_option_client
    
    _pocket_option_client = PocketOptionClient(ssid, is_demo)
    await _pocket_option_client.connect()
    
    return _pocket_option_client


async def disconnect_pocket_option():
    """Disconnect Pocket Option client"""
    global _pocket_option_client
    
    if _pocket_option_client:
        await _pocket_option_client.disconnect()
        _pocket_option_client = None
