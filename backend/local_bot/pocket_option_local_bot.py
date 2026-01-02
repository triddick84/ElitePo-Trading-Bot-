#!/usr/bin/env python3
"""
Pocket Option Local Trading Bot
================================

A standalone bot that runs on YOUR local machine for:
- Better connection stability (closer to Pocket Option servers)
- Automatic SSID extraction from local browser
- Real-time trade execution
- Local monitoring and alerts

REQUIREMENTS:
- Python 3.8+
- Chrome or Firefox browser
- pip install websockets aiohttp requests

USAGE:
1. Save this file to your computer
2. Install dependencies: pip install websockets aiohttp requests pyperclip
3. Run: python pocket_option_local_bot.py
4. Follow the prompts to connect

The bot will:
- Guide you to get SSID from browser
- Connect to Pocket Option
- Fetch signals from your cloud server
- Execute trades locally
- Monitor connection and alert on issues
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pocket_option_bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not installed. Run: pip install websockets")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed. Run: pip install aiohttp")

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


class Colors:
    """Terminal colors for better UX"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_banner():
    """Print welcome banner"""
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   {Colors.BOLD}🤖 POCKET OPTION LOCAL TRADING BOT{Colors.END}{Colors.CYAN}                            ║
║                                                                    ║
║   Automated trading with local execution for better reliability    ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def print_ssid_instructions():
    """Print SSID extraction instructions"""
    instructions = f"""
{Colors.WARNING}════════════════════════════════════════════════════════════════════
{Colors.BOLD}📋 HOW TO GET YOUR SSID:{Colors.END}
════════════════════════════════════════════════════════════════════

{Colors.GREEN}Step 1:{Colors.END} Open Pocket Option in your browser
        URL: https://pocketoption.com

{Colors.GREEN}Step 2:{Colors.END} Login to your account (demo or real)

{Colors.GREEN}Step 3:{Colors.END} Open Developer Tools
        • Chrome/Edge: Press {Colors.BOLD}F12{Colors.END} or {Colors.BOLD}Ctrl+Shift+I{Colors.END}
        • Firefox: Press {Colors.BOLD}F12{Colors.END}
        • Safari: Press {Colors.BOLD}Cmd+Option+I{Colors.END}

{Colors.GREEN}Step 4:{Colors.END} Go to the {Colors.BOLD}Network{Colors.END} tab

{Colors.GREEN}Step 5:{Colors.END} Click on {Colors.BOLD}WS{Colors.END} filter (WebSocket)

{Colors.GREEN}Step 6:{Colors.END} Refresh the page ({Colors.BOLD}F5{Colors.END})

{Colors.GREEN}Step 7:{Colors.END} Look for WebSocket connection (wss://...)

{Colors.GREEN}Step 8:{Colors.END} Click on it → Go to {Colors.BOLD}Messages{Colors.END} tab

{Colors.GREEN}Step 9:{Colors.END} Find message starting with: {Colors.CYAN}42["auth",{{"session":"...{Colors.END}

{Colors.GREEN}Step 10:{Colors.END} {Colors.BOLD}Copy the ENTIRE message{Colors.END} (including 42["auth"...)

════════════════════════════════════════════════════════════════════{Colors.END}
"""
    print(instructions)


class PocketOptionLocalBot:
    """
    Local trading bot for Pocket Option
    Runs on user's machine for better connectivity
    """
    
    def __init__(self, cloud_server_url: str = None):
        self.cloud_server_url = cloud_server_url
        self.ssid: Optional[str] = None
        self.is_demo: bool = True
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected: bool = False
        self.balance: float = 0
        self.running: bool = False
        
        # Connection settings
        self.ws_url = "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket"
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10
        self.heartbeat_interval = 25
        
        # Trading state
        self.pending_trades: Dict = {}
        self.trade_history: List[Dict] = []
        self.last_signal_check: Optional[datetime] = None
        self.signal_check_interval = 5  # seconds
        
        # Session tracking
        self.session_start: Optional[datetime] = None
        self.ssid_set_time: Optional[datetime] = None
        self.estimated_ssid_expiry: Optional[datetime] = None
        
        # Statistics
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_profit": 0
        }
    
    def set_ssid(self, ssid: str, is_demo: bool = True):
        """Set the SSID for authentication"""
        self.ssid = ssid.strip()
        self.is_demo = is_demo
        self.ssid_set_time = datetime.now(timezone.utc)
        # Estimate expiry (conservative 4 hours)
        self.estimated_ssid_expiry = self.ssid_set_time + timedelta(hours=4)
        
        logger.info(f"✅ SSID set (demo={is_demo})")
        logger.info(f"📅 Estimated expiry: {self.estimated_ssid_expiry.strftime('%H:%M:%S')}")
    
    async def connect(self) -> bool:
        """Connect to Pocket Option WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library required. Install: pip install websockets")
            return False
        
        if not self.ssid:
            logger.error("No SSID configured")
            return False
        
        logger.info(f"🔌 Connecting to Pocket Option...")
        
        try:
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )
            
            # Wait for connection acknowledgment
            response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            logger.debug(f"Initial response: {response}")
            
            # Send auth
            if self.ssid.startswith('42["auth"'):
                auth_message = self.ssid
            else:
                auth_message = f'42["auth",{{"session":"{self.ssid}","isDemo":{1 if self.is_demo else 0}}}]'
            
            await self.ws.send("40")  # Socket.IO connect
            await asyncio.sleep(0.5)
            await self.ws.send(auth_message)
            
            # Wait for auth response
            for _ in range(10):
                response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                if '"profile"' in response or '"balance"' in response:
                    self.connected = True
                    self._parse_profile(response)
                    logger.info(f"✅ Connected! Balance: ${self.balance:.2f}")
                    return True
            
            logger.error("❌ Authentication failed - no profile received")
            return False
            
        except asyncio.TimeoutError:
            logger.error("❌ Connection timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    def _parse_profile(self, response: str):
        """Parse profile/balance from response"""
        try:
            if '"balance"' in response:
                import re
                balance_match = re.search(r'"balance[^"]*":\s*([\d.]+)', response)
                if balance_match:
                    self.balance = float(balance_match.group(1))
        except Exception as e:
            logger.warning(f"Could not parse balance: {e}")
    
    async def place_trade(self, asset: str, direction: str, amount: float, expiration: int = 60) -> Dict:
        """
        Place a trade on Pocket Option
        
        Args:
            asset: Asset symbol (e.g., "EURUSD_otc")
            direction: "call" or "put"
            amount: Trade amount in dollars
            expiration: Expiration time in seconds
        
        Returns:
            Trade result dictionary
        """
        if not self.connected or not self.ws:
            return {"success": False, "error": "Not connected"}
        
        try:
            # Generate trade ID
            trade_id = int(time.time() * 1000)
            
            # Build trade message
            trade_data = {
                "asset": asset,
                "amount": amount,
                "action": direction.lower(),
                "isDemo": self.is_demo,
                "requestId": trade_id,
                "optionType": 100,  # Turbo option
                "time": expiration
            }
            
            trade_message = f'42["openOption",{json.dumps(trade_data)}]'
            
            logger.info(f"📊 Placing trade: {direction.upper()} {asset} ${amount} ({expiration}s)")
            
            await self.ws.send(trade_message)
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < 10:
                try:
                    response = await asyncio.wait_for(self.ws.recv(), timeout=2)
                    if '"openOption"' in response or str(trade_id) in response:
                        logger.info(f"✅ Trade placed successfully!")
                        self.stats["total_trades"] += 1
                        return {"success": True, "trade_id": trade_id, "response": response}
                except asyncio.TimeoutError:
                    continue
            
            return {"success": False, "error": "Trade response timeout"}
            
        except Exception as e:
            logger.error(f"Trade error: {e}")
            return {"success": False, "error": str(e)}
    
    async def fetch_signal_from_cloud(self) -> Optional[Dict]:
        """Fetch trading signal from cloud server"""
        if not self.cloud_server_url or not AIOHTTP_AVAILABLE:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.cloud_server_url}/api/strategy/1m-high-probability/generate"
                params = {"asset": "EURUSD", "strategy": "best"}
                
                async with session.post(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") and data.get("signal"):
                            return data
            return None
        except Exception as e:
            logger.warning(f"Could not fetch signal: {e}")
            return None
    
    async def heartbeat_loop(self):
        """Send periodic heartbeats to keep connection alive"""
        while self.running and self.connected:
            try:
                if self.ws:
                    await self.ws.send("2")  # Socket.IO ping
                    await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                self.connected = False
                break
    
    async def signal_loop(self):
        """Check for trading signals and execute"""
        while self.running:
            try:
                if self.connected:
                    signal_data = await self.fetch_signal_from_cloud()
                    
                    if signal_data and signal_data.get("should_trade"):
                        signal = signal_data["signal"]
                        direction = signal["direction"].lower()
                        confidence = signal["confidence"]
                        
                        if confidence >= 70:
                            logger.info(f"🎯 Signal received: {direction.upper()} (confidence: {confidence}%)")
                            
                            # Execute trade
                            result = await self.place_trade(
                                asset="EURUSD_otc",
                                direction=direction,
                                amount=1,  # $1 per trade
                                expiration=60
                            )
                            
                            if result["success"]:
                                logger.info(f"✅ Trade executed successfully")
                            else:
                                logger.error(f"❌ Trade failed: {result.get('error')}")
                
                await asyncio.sleep(self.signal_check_interval)
                
            except Exception as e:
                logger.error(f"Signal loop error: {e}")
                await asyncio.sleep(5)
    
    async def monitor_ssid_expiry(self):
        """Monitor SSID expiry and warn user"""
        while self.running:
            try:
                if self.estimated_ssid_expiry:
                    time_left = self.estimated_ssid_expiry - datetime.now(timezone.utc)
                    minutes_left = time_left.total_seconds() / 60
                    
                    if minutes_left <= 30 and minutes_left > 0:
                        logger.warning(f"⏰ SSID expiring in {int(minutes_left)} minutes!")
                        logger.warning("   Please prepare a new SSID from your browser")
                    elif minutes_left <= 0:
                        logger.critical("❌ SSID has EXPIRED! Please update with new SSID")
                        self.connected = False
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Expiry monitor error: {e}")
                await asyncio.sleep(60)
    
    async def run(self):
        """Main bot loop"""
        self.running = True
        self.session_start = datetime.now(timezone.utc)
        
        logger.info("🚀 Starting bot...")
        
        # Connect
        if not await self.connect():
            logger.error("Failed to connect. Please check SSID and try again.")
            return
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.signal_loop()),
            asyncio.create_task(self.monitor_ssid_expiry())
        ]
        
        try:
            # Monitor connection and reconnect if needed
            while self.running:
                if not self.connected:
                    logger.warning("Connection lost. Attempting reconnect...")
                    if await self.connect():
                        logger.info("Reconnected successfully!")
                    else:
                        logger.error("Reconnection failed. Waiting before retry...")
                        await asyncio.sleep(self.reconnect_delay)
                
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
            if self.ws:
                await self.ws.close()
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        return {
            "connected": self.connected,
            "is_demo": self.is_demo,
            "balance": self.balance,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "ssid_set_time": self.ssid_set_time.isoformat() if self.ssid_set_time else None,
            "estimated_ssid_expiry": self.estimated_ssid_expiry.isoformat() if self.estimated_ssid_expiry else None,
            "stats": self.stats
        }


async def interactive_setup():
    """Interactive setup for the bot"""
    print_banner()
    
    # Check dependencies
    missing_deps = []
    if not WEBSOCKETS_AVAILABLE:
        missing_deps.append("websockets")
    if not AIOHTTP_AVAILABLE:
        missing_deps.append("aiohttp")
    
    if missing_deps:
        print(f"{Colors.FAIL}❌ Missing dependencies: {', '.join(missing_deps)}{Colors.END}")
        print(f"   Install with: pip install {' '.join(missing_deps)}")
        return None
    
    # Get cloud server URL
    print(f"\n{Colors.CYAN}📡 Cloud Server Configuration{Colors.END}")
    cloud_url = input("Enter your cloud server URL (or press Enter to skip): ").strip()
    
    if cloud_url and not cloud_url.startswith("http"):
        cloud_url = f"https://{cloud_url}"
    
    # Get SSID
    print_ssid_instructions()
    
    # Open browser option
    open_browser = input(f"\n{Colors.GREEN}Open Pocket Option in browser? (y/n): {Colors.END}").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://pocketoption.com")
        print(f"{Colors.CYAN}Browser opened. Follow the instructions above to get your SSID.{Colors.END}")
    
    print(f"\n{Colors.BOLD}Paste your SSID below (the 42[\"auth\",...] message):{Colors.END}")
    ssid = input().strip()
    
    if not ssid:
        print(f"{Colors.FAIL}❌ No SSID provided{Colors.END}")
        return None
    
    # Demo or real account
    account_type = input(f"\n{Colors.GREEN}Account type - Demo (d) or Real (r)? [d]: {Colors.END}").strip().lower()
    is_demo = account_type != 'r'
    
    if not is_demo:
        confirm = input(f"{Colors.WARNING}⚠️ You selected REAL account. Are you sure? (yes/no): {Colors.END}").strip().lower()
        if confirm != 'yes':
            print("Switched to demo account for safety.")
            is_demo = True
    
    # Create bot
    bot = PocketOptionLocalBot(cloud_server_url=cloud_url if cloud_url else None)
    bot.set_ssid(ssid, is_demo)
    
    return bot


async def main():
    """Main entry point"""
    try:
        bot = await interactive_setup()
        
        if bot:
            print(f"\n{Colors.GREEN}{'='*60}{Colors.END}")
            print(f"{Colors.GREEN}Starting bot... Press Ctrl+C to stop{Colors.END}")
            print(f"{Colors.GREEN}{'='*60}{Colors.END}\n")
            
            await bot.run()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}Bot stopped by user{Colors.END}")
    except Exception as e:
        print(f"{Colors.FAIL}Error: {e}{Colors.END}")
        raise


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher required")
        sys.exit(1)
    
    asyncio.run(main())
