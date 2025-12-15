"""
Enhanced Pocket Option Connection Manager
- Auto-reconnection on disconnection
- Periodic ping/pong to keep session alive
- SSID refresh using Selenium when expired
- Connection health monitoring
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from pocketoptionapi_async import AsyncPocketOptionClient
import os

logger = logging.getLogger(__name__)


class PersistentPocketOptionConnection:
    """
    Manages a persistent connection to Pocket Option with:
    - Automatic reconnection
    - Keep-alive pings
    - SSID refresh on expiration
    - Health monitoring
    """
    
    def __init__(
        self,
        ssid: str,
        uid: int,
        is_demo: bool = True,
        ping_interval: int = 25,
        enable_auto_refresh: bool = True
    ):
        """
        Initialize persistent connection manager
        
        Args:
            ssid: Session ID
            uid: User ID
            is_demo: Demo or live account
            ping_interval: Seconds between pings (default 25s)
            enable_auto_refresh: Enable automatic SSID refresh via Selenium
        """
        self.ssid = ssid
        self.uid = uid
        self.is_demo = is_demo
        self.ping_interval = ping_interval
        self.enable_auto_refresh = enable_auto_refresh
        
        self.client: Optional[AsyncPocketOptionClient] = None
        self.is_running = False
        self.last_ping = None
        self.last_pong = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # Background tasks
        self._ping_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.total_reconnects = 0
        self.uptime_start = None
        
    async def start(self) -> bool:
        """
        Start the persistent connection
        
        Returns:
            True if connection established
        """
        logger.info("🔌 Starting persistent Pocket Option connection...")
        
        if await self.connect():
            self.is_running = True
            self.uptime_start = datetime.now(timezone.utc)
            
            # Start background tasks
            self._ping_task = asyncio.create_task(self._keep_alive_loop())
            self._monitor_task = asyncio.create_task(self._health_monitor_loop())
            
            logger.info("✅ Persistent connection started successfully")
            return True
        else:
            logger.error("❌ Failed to start persistent connection")
            return False
    
    async def connect(self) -> bool:
        """
        Connect or reconnect to Pocket Option
        
        Returns:
            True if connected
        """
        try:
            # Close existing connection if any
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            
            # Create new client
            self.client = AsyncPocketOptionClient(
                ssid=self.ssid,
                uid=self.uid,
                is_demo=self.is_demo,
                enable_logging=False
            )
            
            logger.info(f"🔌 Connecting to Pocket Option (Demo: {self.is_demo})...")
            connected = await self.client.connect()
            
            if connected:
                logger.info("✅ Connected successfully!")
                self.reconnect_attempts = 0
                self.last_pong = datetime.now(timezone.utc)
                return True
            else:
                logger.error("❌ Connection failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    async def _refresh_ssid(self) -> Optional[str]:
        """
        Refresh SSID using Selenium auto-login
        
        Returns:
            New SSID if successful
        """
        if not self.enable_auto_refresh:
            logger.warning("⚠️ Auto-refresh disabled")
            return None
        
        try:
            logger.info("🔄 Attempting to refresh SSID via Selenium...")
            from pocket_option_auth import auto_login_and_get_ssid
            
            email = os.getenv('POCKET_OPTION_EMAIL')
            password = os.getenv('POCKET_OPTION_PASSWORD')
            
            if not email or not password:
                logger.error("❌ Missing credentials for SSID refresh")
                return None
            
            new_ssid = auto_login_and_get_ssid(email, password)
            
            if new_ssid:
                logger.info("✅ SSID refreshed successfully")
                self.ssid = new_ssid
                
                # Update .env file
                self._update_env_ssid(new_ssid)
                
                return new_ssid
            else:
                logger.error("❌ Failed to refresh SSID")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error refreshing SSID: {e}")
            return None
    
    def _update_env_ssid(self, new_ssid: str):
        """Update SSID in .env file"""
        try:
            env_path = '/app/backend/.env'
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('POCKET_OPTION_SSID='):
                    lines[i] = f'POCKET_OPTION_SSID={new_ssid}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'POCKET_OPTION_SSID={new_ssid}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
                
            logger.info("✅ Updated SSID in .env file")
        except Exception as e:
            logger.error(f"❌ Failed to update .env: {e}")
    
    async def _keep_alive_loop(self):
        """
        Background task to send periodic pings
        Keeps the connection alive and detects disconnections
        """
        logger.info(f"🔄 Keep-alive loop started (interval: {self.ping_interval}s)")
        
        while self.is_running:
            try:
                await asyncio.sleep(self.ping_interval)
                
                if self.client and self.client.is_connected:
                    # Send ping
                    try:
                        await self.client._websocket.send('2')  # Socket.IO ping
                        self.last_ping = datetime.now(timezone.utc)
                        logger.debug("📡 Ping sent")
                    except Exception as e:
                        logger.warning(f"⚠️ Ping failed: {e}")
                        await self._handle_disconnection()
                else:
                    logger.warning("⚠️ Client not connected, attempting reconnection...")
                    await self._handle_disconnection()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Keep-alive loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in keep-alive loop: {e}")
                await asyncio.sleep(5)
    
    async def _health_monitor_loop(self):
        """
        Background task to monitor connection health
        Checks for stale connections and triggers recovery
        """
        logger.info("🏥 Health monitor started")
        
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if self.last_pong:
                    time_since_pong = (datetime.now(timezone.utc) - self.last_pong).total_seconds()
                    
                    if time_since_pong > 300:  # 5 minutes without response
                        logger.warning(f"⚠️ Stale connection detected ({time_since_pong:.0f}s since last pong)")
                        await self._handle_disconnection()
                        
            except asyncio.CancelledError:
                logger.info("🛑 Health monitor cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in health monitor: {e}")
                await asyncio.sleep(10)
    
    async def _handle_disconnection(self):
        """
        Handle disconnection and attempt recovery
        """
        logger.warning("🔄 Handling disconnection...")
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts reached ({self.max_reconnect_attempts})")
            
            # Try SSID refresh as last resort
            new_ssid = await self._refresh_ssid()
            if new_ssid:
                self.reconnect_attempts = 0
                logger.info("🔄 Retrying with refreshed SSID...")
            else:
                logger.error("❌ SSID refresh failed. Connection cannot be recovered.")
                self.is_running = False
                return
        
        # Exponential backoff
        delay = min(2 ** self.reconnect_attempts, 60)
        logger.info(f"⏳ Waiting {delay}s before reconnection attempt {self.reconnect_attempts + 1}...")
        await asyncio.sleep(delay)
        
        self.reconnect_attempts += 1
        self.total_reconnects += 1
        
        if await self.connect():
            logger.info("✅ Reconnection successful!")
            self.reconnect_attempts = 0
        else:
            logger.error(f"❌ Reconnection attempt {self.reconnect_attempts} failed")
    
    async def stop(self):
        """
        Stop the persistent connection
        """
        logger.info("🛑 Stopping persistent connection...")
        self.is_running = False
        
        # Cancel background tasks
        if self._ping_task:
            self._ping_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        
        # Disconnect client
        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
        
        logger.info("✅ Persistent connection stopped")
    
    def get_stats(self) -> dict:
        """Get connection statistics"""
        uptime = None
        if self.uptime_start:
            uptime = (datetime.now(timezone.utc) - self.uptime_start).total_seconds()
        
        return {
            "is_running": self.is_running,
            "is_connected": self.client.is_connected if self.client else False,
            "reconnect_attempts": self.reconnect_attempts,
            "total_reconnects": self.total_reconnects,
            "uptime_seconds": uptime,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
        }
    
    async def get_balance(self) -> float:
        """Get account balance"""
        if self.client and self.client.is_connected:
            try:
                balance = await self.client.get_balance()
                self.last_pong = datetime.now(timezone.utc)
                return balance
            except Exception as e:
                logger.error(f"Error getting balance: {e}")
                await self._handle_disconnection()
                return 0.0
        return 0.0
    
    async def get_candles(self, asset: str, timeframe: int, count: int = 100):
        """Get candle data"""
        if self.client and self.client.is_connected:
            try:
                candles = await self.client.get_candles(asset, timeframe, count)
                self.last_pong = datetime.now(timezone.utc)
                return candles
            except Exception as e:
                logger.error(f"Error getting candles: {e}")
                await self._handle_disconnection()
                return []
        return []
    
    async def place_trade(self, asset: str, amount: float, direction: str, duration: int):
        """Place a trade"""
        if self.client and self.client.is_connected:
            try:
                result = await self.client.buy(asset, amount, direction, duration)
                self.last_pong = datetime.now(timezone.utc)
                return result
            except Exception as e:
                logger.error(f"Error placing trade: {e}")
                await self._handle_disconnection()
                return None
        return None
