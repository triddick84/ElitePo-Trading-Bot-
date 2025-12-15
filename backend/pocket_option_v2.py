"""
Improved Pocket Option Client
Based on markosgiassa1/PocketOptionCandles approach
Uses direct WebSocket connection with proper SSID format
"""
import asyncio
import logging
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import websockets
import os

logger = logging.getLogger(__name__)


class PocketOptionV2:
    """
    Simplified Pocket Option client using direct WebSocket
    Compatible with the SSID format from markosgiassa1 repo
    
    Features:
    - Auto-reconnection on disconnection
    - SSID refresh mechanism
    - Connection health monitoring
    """
    
    # All available assets
    ASSETS = [
        'EURUSD', 'EURUSD_otc', 'GBPUSD', 'GBPUSD_otc', 'USDJPY', 'USDJPY_otc',
        'AUDUSD', 'AUDUSD_otc', 'USDCAD', 'USDCAD_otc', 'USDCHF', 'USDCHF_otc',
        'EURJPY', 'EURJPY_otc', 'EURGBP', 'EURGBP_otc', 'GBPJPY', 'GBPJPY_otc',
        'AUDCAD', 'AUDCAD_otc', 'AUDCHF', 'AUDCHF_otc', 'AUDJPY', 'AUDJPY_otc',
        'CADCHF', 'CADCHF_otc', 'CADJPY', 'CADJPY_otc', 'CHFJPY', 'CHFJPY_otc',
        'BTCUSD', 'ETHUSD', 'LTCUSD', 'XRPUSD',
        '#AAPL', '#AAPL_otc', '#TSLA', '#TSLA_otc', '#AMZN', '#MSFT', '#MSFT_otc',
        '#GOOGL', '#FB', '#FB_otc', '#NFLX', '#NFLX_otc'
    ]
    
    # WebSocket URLs for different regions
    WS_URLS = {
        'demo': 'wss://api-us-north.po.market/socket.io/?EIO=4&transport=websocket',
        'demo_eu': 'wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket',
        'demo2': 'wss://try-demo-eu.po.market/socket.io/?EIO=4&transport=websocket',
        'live': 'wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket',
        'live_us': 'wss://api-us-north.po.market/socket.io/?EIO=4&transport=websocket'
    }
    
    def __init__(self, ssid: str, uid: int = None, is_demo: bool = True, auto_refresh: bool = True):
        """
        Initialize client with SSID and UID
        
        Args:
            ssid: Session ID (e.g., 'A4zP7dZSXxYCq0X5z')
            uid: User ID (e.g., 53953294)
            is_demo: Use demo or live account
            auto_refresh: Enable automatic SSID refresh on expiration
        """
        self.ssid = ssid
        self.uid = uid or 0
        self.is_demo = is_demo
        self.auto_refresh = auto_refresh
        self.ws = None
        self.connected = False
        self.sid = None
        self.balance = 0.0
        self.account_id = None
        self.last_heartbeat = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
    async def _refresh_ssid(self) -> Optional[str]:
        """
        Refresh SSID using Selenium authenticator
        
        Returns:
            New SSID if successful, None otherwise
        """
        if not self.auto_refresh:
            logger.warning("⚠️ Auto-refresh disabled")
            return None
        
        try:
            logger.info("🔄 Attempting to refresh SSID...")
            from pocket_option_auth import auto_login_and_get_ssid
            
            email = os.getenv('POCKET_OPTION_EMAIL')
            password = os.getenv('POCKET_OPTION_PASSWORD')
            
            if not email or not password:
                logger.error("❌ Missing email/password for SSID refresh")
                return None
            
            new_ssid = auto_login_and_get_ssid(email, password)
            
            if new_ssid:
                logger.info("✅ SSID refreshed successfully")
                self.ssid = new_ssid
                return new_ssid
            else:
                logger.error("❌ Failed to refresh SSID")
                return None
        except Exception as e:
            logger.error(f"❌ Error refreshing SSID: {e}")
            return None
    
    async def connect(self, retry_on_auth_fail: bool = True) -> bool:
        """
        Connect to Pocket Option WebSocket
        
        Args:
            retry_on_auth_fail: If True, attempt SSID refresh on auth failure
        
        Returns:
            True if connected successfully
        """
        try:
            # Select URL based on mode
            url = self.WS_URLS['demo'] if self.is_demo else self.WS_URLS['live']
            
            logger.info(f"🔌 Connecting to {url}... (Attempt {self.reconnect_attempts + 1})")
            
            self.ws = await websockets.connect(url)
            
            # Step 1: Receive handshake
            handshake = await self.ws.recv()
            logger.info(f"📨 Handshake: {handshake}")
            
            # Extract SID from handshake
            if handshake.startswith('0{'):
                data = json.loads(handshake[1:])
                self.sid = data.get('sid')
                logger.info(f"✅ Got SID: {self.sid}")
            
            # Step 2: Send connection response
            await self.ws.send('40')
            
            # Step 3: Receive connection confirmation
            conn_msg = await self.ws.recv()
            logger.info(f"📨 Connection: {conn_msg}")
            
            # Step 4: Send auth message with exact format from user
            auth_payload = {
                "session": self.ssid,
                "isDemo": 1 if self.is_demo else 0,
                "uid": self.uid,
                "platform": 1
            }
            
            auth_msg = f'42["auth",{json.dumps(auth_payload)}]'
            logger.info(f"🔐 Sending auth: {auth_msg[:50]}...")
            await self.ws.send(auth_msg)
            
            # Step 5: Wait for auth response
            auth_response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            logger.info(f"📨 Auth response: {auth_response[:100]}...")
            
            # Check if authenticated
            if 'profile' in auth_response or 'balance' in auth_response:
                self.connected = True
                self.reconnect_attempts = 0  # Reset on success
                self.last_heartbeat = datetime.now()
                logger.info("✅ Successfully authenticated!")
                
                # Parse response
                try:
                    if auth_response.startswith('42'):
                        data = json.loads(auth_response[2:])
                        if isinstance(data, list) and len(data) > 1:
                            profile = data[1]
                            self.balance = profile.get('balance', 0)
                            self.account_id = profile.get('id')
                            logger.info(f"💰 Balance: ${self.balance}")
                except Exception as e:
                    logger.warning(f"Could not parse auth response: {e}")
                
                return True
            elif 'error' in auth_response.lower() or 'unauthorized' in auth_response.lower():
                logger.error(f"❌ Authentication failed - SSID likely expired")
                
                # Try to refresh SSID if enabled
                if retry_on_auth_fail and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    logger.info("🔄 Attempting to refresh SSID and reconnect...")
                    
                    new_ssid = await self._refresh_ssid()
                    if new_ssid:
                        await self.disconnect()
                        await asyncio.sleep(2)  # Brief delay before retry
                        return await self.connect(retry_on_auth_fail=False)  # Retry once with new SSID
                
                return False
            else:
                logger.error(f"❌ Unexpected auth response: {auth_response}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ Auth timeout - SSID might be invalid or expired")
            
            # Try to refresh SSID if this is first timeout
            if retry_on_auth_fail and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                new_ssid = await self._refresh_ssid()
                if new_ssid:
                    await asyncio.sleep(2)
                    return await self.connect(retry_on_auth_fail=False)
            
            return False
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("👋 Disconnected")
    
    async def get_candles(self, asset: str, timeframe: int, count: int = 100) -> List[Dict]:
        """
        Get historical candles
        
        Args:
            asset: Asset symbol
            timeframe: Timeframe in seconds
            count: Number of candles
        
        Returns:
            List of candle dictionaries
        """
        if not self.connected:
            logger.error("❌ Not connected")
            return []
        
        try:
            # Send candles request
            request = f'42["history",["{asset}",{timeframe}]]'
            await self.ws.send(request)
            
            # Receive response
            response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            
            if response.startswith('42'):
                data = json.loads(response[2:])
                if isinstance(data, list) and len(data) > 1:
                    candles = data[1]
                    logger.info(f"📊 Received {len(candles)} candles for {asset}")
                    return candles[:count]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting candles: {e}")
            return []
    
    async def place_order(
        self, 
        asset: str, 
        direction: str, 
        amount: float, 
        duration: int
    ) -> Dict:
        """
        Place a binary options order
        
        Args:
            asset: Asset symbol
            direction: 'buy' or 'sell' (or 'call'/'put')
            amount: Trade amount
            duration: Duration in seconds
        
        Returns:
            Order result
        """
        if not self.connected:
            return {"error": "Not connected"}
        
        try:
            # Normalize direction
            if direction.lower() in ['buy', 'call']:
                action = 'call'
            elif direction.lower() in ['sell', 'put']:
                action = 'put'
            else:
                return {"error": "Invalid direction"}
            
            # Send order
            order = f'42["{action}",["{asset}",{amount},{duration}]]'
            logger.info(f"📤 Placing order: {order}")
            await self.ws.send(order)
            
            # Wait for response
            response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            logger.info(f"📨 Order response: {response}")
            
            return {
                "success": True,
                "asset": asset,
                "direction": action,
                "amount": amount,
                "duration": duration,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get current balance"""
        if not self.connected:
            return 0.0
        
        try:
            # Send balance request
            await self.ws.send('42["balance"]')
            
            # Wait for response
            response = await asyncio.wait_for(self.ws.recv(), timeout=5)
            
            if response.startswith('42'):
                data = json.loads(response[2:])
                if isinstance(data, list) and len(data) > 1:
                    self.balance = float(data[1])
                    return self.balance
            
            return self.balance
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return self.balance
    
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.connected and self.ws is not None


# Global client
pocket_option_v2_client = None


async def get_pocket_option_v2_client(ssid: str = None, uid: int = None, is_demo: bool = True) -> Optional[PocketOptionV2]:
    """
    Get or create PocketOptionV2 client
    
    Args:
        ssid: Session ID (optional, uses env if not provided)
        uid: User ID (optional, uses env if not provided)
        is_demo: Demo or live account
    
    Returns:
        PocketOptionV2 instance
    """
    global pocket_option_v2_client
    
    ssid = ssid or os.getenv('POCKET_OPTION_SSID')
    uid = uid or int(os.getenv('POCKET_OPTION_UID', '0'))
    
    if not ssid:
        logger.error("❌ No SSID provided")
        return None
    
    if pocket_option_v2_client is None or not pocket_option_v2_client.is_connected():
        pocket_option_v2_client = PocketOptionV2(ssid, uid, is_demo)
        await pocket_option_v2_client.connect()
    
    return pocket_option_v2_client


# Test function
async def test_connection():
    """Test the connection"""
    ssid = os.getenv('POCKET_OPTION_SSID', 'A4zP7dZSXxYCq0X5z')
    uid = int(os.getenv('POCKET_OPTION_UID', '53953294'))
    
    client = PocketOptionV2(ssid, uid, is_demo=True)
    
    if await client.connect():
        print("✅ Connected!")
        
        balance = await client.get_balance()
        print(f"💰 Balance: ${balance}")
        
        candles = await client.get_candles('EURUSD_otc', 60, 10)
        print(f"📊 Got {len(candles)} candles")
        
        await client.disconnect()
    else:
        print("❌ Connection failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_connection())
