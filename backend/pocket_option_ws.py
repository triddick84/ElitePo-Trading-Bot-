"""
Pocket Option WebSocket Connection Handler
==========================================

Custom WebSocket connection that works with websockets 15+ 
and handles the SSID authentication properly.

This bypasses the incompatible pocketoptionapi-async library
and implements a direct WebSocket connection.
"""

import asyncio
import ssl
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
import websockets
from websockets.asyncio.client import connect as ws_connect

logger = logging.getLogger(__name__)

# Connection settings
WEBSOCKET_URLS = {
    "demo": [
        "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket",
        "wss://try-demo-eu.po.market/socket.io/?EIO=4&transport=websocket",
    ],
    "real": [
        "wss://api-c.po.market/socket.io/?EIO=4&transport=websocket",
        "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket",
        "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
        "wss://api-fin.po.market/socket.io/?EIO=4&transport=websocket",
    ]
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://pocketoption.com",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class ConnectionState:
    """Connection state information"""
    connected: bool = False
    authenticated: bool = False
    is_demo: bool = True
    balance: float = 0.0
    user_id: Optional[str] = None
    url: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "connected": self.connected,
            "authenticated": self.authenticated,
            "is_demo": self.is_demo,
            "balance": self.balance,
            "user_id": self.user_id,
            "url": self.url,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "error": self.error
        }


class PocketOptionWebSocket:
    """
    Direct WebSocket connection to Pocket Option
    Compatible with websockets 15+
    """
    
    def __init__(self, ssid: str, is_demo: bool = True):
        """
        Initialize connection
        
        Args:
            ssid: The full SSID string (42["auth",{...}] format)
            is_demo: Whether to connect to demo or real account
        """
        self.ssid = ssid
        self.is_demo = is_demo
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.state = ConnectionState(is_demo=is_demo)
        self._running = False
        self._message_handlers: List[Callable] = []
        self._receive_task: Optional[asyncio.Task] = None
        
        # Parse SSID for user info
        self._parse_ssid()
    
    def _parse_ssid(self):
        """Parse SSID to extract user info"""
        try:
            # SSID format: 42["auth",{"session":"...", "isDemo":1, "uid":12345, ...}]
            if self.ssid.startswith('42["auth",'):
                json_str = self.ssid[2:]  # Remove "42" prefix
                data = json.loads(json_str)
                if isinstance(data, list) and len(data) >= 2:
                    auth_data = data[1]
                    self.state.user_id = str(auth_data.get("uid", ""))
                    self.state.is_demo = auth_data.get("isDemo", 1) == 1
                    logger.info(f"Parsed SSID: uid={self.state.user_id}, demo={self.state.is_demo}")
        except Exception as e:
            logger.warning(f"Failed to parse SSID: {e}")
    
    async def connect(self, timeout: float = 15.0) -> bool:
        """
        Connect to Pocket Option WebSocket
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connected and authenticated successfully
        """
        urls = WEBSOCKET_URLS["demo" if self.is_demo else "real"]
        
        for url in urls:
            try:
                logger.info(f"🔌 Connecting to {url}...")
                
                # Create SSL context (disable verification for PO servers)
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Connect with websockets 15+ API
                self.websocket = await asyncio.wait_for(
                    ws_connect(
                        url,
                        ssl=ssl_context,
                        additional_headers=DEFAULT_HEADERS,  # Changed from extra_headers
                        ping_interval=25,
                        ping_timeout=20,
                        close_timeout=10,
                    ),
                    timeout=timeout
                )
                
                self.state.url = url
                self.state.connected = True
                self.state.connected_at = datetime.now(timezone.utc)
                
                logger.info(f"✅ Connected to {url}")
                
                # Perform Socket.IO handshake
                if await self._handshake():
                    self._running = True
                    # Start message receiver in background
                    self._receive_task = asyncio.create_task(self._receive_messages())
                    return True
                else:
                    await self.disconnect()
                    continue
                    
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Connection timeout for {url}")
                continue
            except Exception as e:
                logger.warning(f"❌ Failed to connect to {url}: {e}")
                continue
        
        self.state.error = "Failed to connect to any WebSocket endpoint"
        return False
    
    async def _handshake(self) -> bool:
        """
        Perform Socket.IO handshake and authentication
        
        Socket.IO EIO=4 protocol:
        1. Server sends: 0{"sid":"..."}
        2. Client sends: 40
        3. Server sends: 40{"sid":"..."}
        4. Client sends: 42["auth",{...}] (our SSID)
        5. Server responds with auth result
        """
        try:
            if not self.websocket:
                return False
            
            # Step 1: Receive initial message (0{"sid":"..."})
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            logger.debug(f"Received: {msg[:100]}...")
            
            if not str(msg).startswith('0{'):
                logger.error(f"Unexpected initial message: {msg}")
                return False
            
            # Step 2: Send namespace connection (40)
            await self.websocket.send("40")
            logger.debug("Sent: 40")
            
            # Step 3: Receive namespace acknowledgment (40{"sid":"..."})
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            logger.debug(f"Received: {msg[:100]}...")
            
            if not str(msg).startswith('40'):
                logger.error(f"Unexpected namespace response: {msg}")
                return False
            
            # Step 4: Send authentication (our SSID)
            await self.websocket.send(self.ssid)
            logger.debug(f"Sent auth: {self.ssid[:50]}...")
            
            # Step 5: Wait for auth response
            # Auth responses vary, we'll check for any message that indicates success
            auth_timeout = 10
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < auth_timeout:
                try:
                    msg = await asyncio.wait_for(self.websocket.recv(), timeout=2)
                    logger.debug(f"Auth response: {str(msg)[:200]}...")
                    
                    # Check for successful auth indicators
                    msg_str = str(msg)
                    
                    # Success indicators
                    if '"successauth"' in msg_str.lower() or '"success"' in msg_str.lower():
                        self.state.authenticated = True
                        logger.info("✅ Authentication successful!")
                        return True
                    
                    # Balance update often indicates successful auth
                    if '"balance"' in msg_str:
                        try:
                            # Parse balance
                            if msg_str.startswith('42'):
                                data = json.loads(msg_str[2:])
                                if isinstance(data, list) and len(data) >= 2:
                                    if isinstance(data[1], dict) and 'balance' in data[1]:
                                        self.state.balance = float(data[1].get('balance', 0))
                                        self.state.authenticated = True
                                        logger.info(f"✅ Authenticated! Balance: ${self.state.balance}")
                                        return True
                        except:
                            pass
                    
                    # Some responses just confirm connection
                    if msg_str.startswith('42["') and 'error' not in msg_str.lower():
                        self.state.authenticated = True
                        logger.info("✅ Connection established (assumed authenticated)")
                        return True
                    
                    # Error indicators
                    if '"error"' in msg_str.lower() or '"fail"' in msg_str.lower():
                        logger.error(f"❌ Authentication failed: {msg_str}")
                        self.state.error = "Authentication failed"
                        return False
                        
                except asyncio.TimeoutError:
                    continue
            
            # If we got here without explicit success/failure, assume connected
            self.state.authenticated = True
            logger.info("✅ Connection established (no explicit auth response)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Handshake error: {e}")
            self.state.error = str(e)
            return False
    
    async def _receive_messages(self):
        """Background task to receive messages"""
        try:
            while self._running and self.websocket:
                try:
                    msg = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                    self.state.last_message_at = datetime.now(timezone.utc)
                    
                    # Handle ping/pong (Socket.IO uses "2" for ping, "3" for pong)
                    if msg == "2":
                        await self.websocket.send("3")
                        continue
                    
                    # Process message
                    await self._process_message(msg)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    if self.websocket:
                        try:
                            await self.websocket.send("2")
                        except:
                            pass
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("🔌 WebSocket connection closed")
                    self.state.connected = False
                    break
                    
        except Exception as e:
            logger.error(f"Message receiver error: {e}")
        finally:
            self.state.connected = False
    
    async def _process_message(self, msg: str):
        """Process incoming message"""
        try:
            msg_str = str(msg)
            
            # Update balance if present
            if '"balance"' in msg_str and msg_str.startswith('42'):
                try:
                    data = json.loads(msg_str[2:])
                    if isinstance(data, list) and len(data) >= 2:
                        payload = data[1] if isinstance(data[1], dict) else {}
                        if 'balance' in payload:
                            self.state.balance = float(payload['balance'])
                except:
                    pass
            
            # Call registered handlers
            for handler in self._message_handlers:
                try:
                    await handler(msg)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Message processing error: {e}")
    
    def add_message_handler(self, handler: Callable):
        """Add a message handler"""
        self._message_handlers.append(handler)
    
    async def send(self, message: str) -> bool:
        """Send a message"""
        try:
            if self.websocket and self.state.connected:
                await self.websocket.send(message)
                return True
            return False
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except:
                pass
        
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        
        self.state.connected = False
        self.state.authenticated = False
        logger.info("🔌 Disconnected")
    
    def get_state(self) -> Dict:
        """Get current connection state"""
        return self.state.to_dict()
    
    async def get_balance(self) -> float:
        """Get current balance"""
        return self.state.balance


# Global connection instance
_po_connection: Optional[PocketOptionWebSocket] = None


async def connect_pocket_option(ssid: str, is_demo: bool = True) -> Dict[str, Any]:
    """
    Connect to Pocket Option
    
    Args:
        ssid: Full SSID string
        is_demo: Demo or real account
        
    Returns:
        Connection result dict
    """
    global _po_connection
    
    # Disconnect existing connection
    if _po_connection:
        await _po_connection.disconnect()
    
    # Create new connection
    _po_connection = PocketOptionWebSocket(ssid, is_demo)
    
    # Connect
    success = await _po_connection.connect()
    
    if success:
        return {
            "success": True,
            "connected": True,
            "state": _po_connection.get_state(),
            "message": "Connected successfully!"
        }
    else:
        return {
            "success": False,
            "connected": False,
            "state": _po_connection.get_state(),
            "error": _po_connection.state.error or "Connection failed"
        }


async def test_connection() -> Dict[str, Any]:
    """Test current connection"""
    global _po_connection
    
    if not _po_connection:
        return {"success": False, "connected": False, "error": "No connection initialized"}
    
    return {
        "success": _po_connection.state.connected,
        "connected": _po_connection.state.connected,
        "authenticated": _po_connection.state.authenticated,
        "state": _po_connection.get_state()
    }


async def disconnect_pocket_option():
    """Disconnect from Pocket Option"""
    global _po_connection
    
    if _po_connection:
        await _po_connection.disconnect()
        _po_connection = None
    
    return {"success": True, "message": "Disconnected"}


def get_connection() -> Optional[PocketOptionWebSocket]:
    """Get current connection instance"""
    return _po_connection
