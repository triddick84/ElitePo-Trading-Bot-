"""
Pocket Option Desktop Trading Client
====================================

Hybrid trading system - Desktop handles login & trades,
Cloud server handles signals & strategies.

Usage:
    python main.py

Author: GPT Signal Bot
"""

import asyncio
import json
import logging
import os
import sys
import time
import ssl
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import threading

def install_package(package_name, pip_name=None):
    """Install a package using pip"""
    pip_name = pip_name or package_name
    print(f"Installing {pip_name}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, "-q"])

def check_playwright_browsers():
    """Check if Playwright browsers are installed, install if not"""
    try:
        from playwright.sync_api import sync_playwright
        # Try to launch browser to check if it's installed
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "executable doesn't exist" in error_msg or "browser" in error_msg or "chromium" in error_msg:
            print("\n" + "="*60)
            print("🔧 PLAYWRIGHT BROWSER NOT INSTALLED")
            print("="*60)
            print("\nPlaywright needs to download browser binaries.")
            print("This is a one-time setup that takes ~100MB.\n")
            
            response = input("Install Chromium browser now? (y/n): ").strip().lower()
            if response == 'y':
                print("\n📥 Downloading Chromium browser...")
                try:
                    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
                    print("✅ Chromium installed successfully!\n")
                    return True
                except Exception as install_error:
                    print(f"\n❌ Failed to install browser: {install_error}")
                    print("\nPlease run manually:")
                    print("  python -m playwright install chromium")
                    return False
            else:
                print("\n⚠️ Browser installation skipped.")
                print("Run this command to install manually:")
                print("  python -m playwright install chromium\n")
                return False
        else:
            # Some other error
            print(f"Playwright check error: {e}")
            return True  # Continue anyway

try:
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich import print as rprint
except ImportError:
    install_package("requests")
    install_package("rich")
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich import print as rprint

try:
    import websockets
except ImportError:
    install_package("websockets")
    import websockets

try:
    from twocaptcha import TwoCaptcha
except ImportError:
    install_package("twocaptcha", "2captcha-python")
    from twocaptcha import TwoCaptcha

try:
    import playwright
except ImportError:
    install_package("playwright")
    import playwright

# Import config
try:
    from config import *
except ImportError:
    print("ERROR: config.py not found! Please create it from config.py.example")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console()


@dataclass
class TradeResult:
    """Result of a trade execution"""
    signal_id: str
    success: bool
    direction: str
    amount: float
    asset: str
    entry_price: float = 0.0
    exit_price: float = 0.0
    profit: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PocketOptionClient:
    """
    Handles Pocket Option connection and trading
    """
    
    WEBSOCKET_URLS = {
        "demo": [
            "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket",
            "wss://try-demo-eu.po.market/socket.io/?EIO=4&transport=websocket",
        ],
        "real": [
            "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
            "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket",
        ]
    }
    
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self.balance = 0.0
        self.ssid = None
        self.user_id = None
        self._running = False
        self._last_pong = time.time()
        self._trade_queue = asyncio.Queue()
        self._pending_trades: Dict[str, Any] = {}
        
        # 2Captcha solver
        self.solver = TwoCaptcha(TWOCAPTCHA_API_KEY) if TWOCAPTCHA_API_KEY else None
    
    async def login_and_get_ssid(self) -> Optional[str]:
        """
        Login to Pocket Option using browser automation and get SSID
        """
        try:
            from playwright.async_api import async_playwright
            
            console.print("[yellow]🔐 Starting browser login...[/yellow]")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=HEADLESS and not DEBUG_MODE,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # Capture WebSocket auth
                captured_auth = []
                
                def handle_ws(ws):
                    def on_msg(msg):
                        if '"auth"' in str(msg):
                            captured_auth.append(str(msg))
                    ws.on("framesent", on_msg)
                
                page.on("websocket", handle_ws)
                
                # Navigate to login
                console.print("[blue]📍 Navigating to login page...[/blue]")
                await page.goto("https://pocketoption.com/en/login", timeout=60000)
                await asyncio.sleep(3)
                
                # Fill credentials
                console.print("[blue]📝 Filling login form...[/blue]")
                await page.fill("input[type='email']", POCKET_OPTION_EMAIL)
                await asyncio.sleep(0.5)
                await page.fill("input[type='password']", POCKET_OPTION_PASSWORD)
                await asyncio.sleep(0.5)
                
                # Check for CAPTCHA
                site_key = await page.evaluate('''
                    () => {
                        const el = document.querySelector('[data-sitekey]');
                        return el ? el.getAttribute('data-sitekey') : null;
                    }
                ''')
                
                if site_key and self.solver:
                    console.print("[yellow]🧩 CAPTCHA detected! Solving with 2Captcha...[/yellow]")
                    try:
                        result = self.solver.recaptcha(
                            sitekey=site_key,
                            url="https://pocketoption.com/en/login"
                        )
                        captcha_code = result['code']
                        
                        await page.evaluate(f'''
                            () => {{
                                document.getElementById('g-recaptcha-response').value = "{captcha_code}";
                            }}
                        ''')
                        console.print("[green]✅ CAPTCHA solved![/green]")
                    except Exception as e:
                        console.print(f"[red]❌ CAPTCHA solving failed: {e}[/red]")
                
                # Click login
                await page.click("button[type='submit']")
                console.print("[blue]🔄 Waiting for login...[/blue]")
                await asyncio.sleep(5)
                
                # Check if logged in
                if "cabinet" in page.url or "trade" in page.url:
                    console.print("[green]✅ Login successful![/green]")
                    
                    # Go to trading page to get WebSocket
                    await page.goto(
                        "https://pocketoption.com/en/cabinet/demo-quick-high-low/" if ACCOUNT_TYPE == "demo"
                        else "https://pocketoption.com/en/cabinet/quick-high-low/",
                        timeout=60000
                    )
                    await asyncio.sleep(5)
                    
                    if captured_auth:
                        self.ssid = captured_auth[0]
                        console.print(f"[green]✅ Got SSID: {self.ssid[:50]}...[/green]")
                        await browser.close()
                        return self.ssid
                
                await browser.close()
                console.print("[red]❌ Login failed[/red]")
                return None
                
        except Exception as e:
            console.print(f"[red]❌ Login error: {e}[/red]")
            logger.exception("Login error")
            return None
    
    async def connect(self) -> bool:
        """
        Connect to Pocket Option WebSocket
        """
        if not self.ssid:
            self.ssid = await self.login_and_get_ssid()
            if not self.ssid:
                return False
        
        urls = self.WEBSOCKET_URLS.get(ACCOUNT_TYPE, self.WEBSOCKET_URLS["demo"])
        
        for url in urls:
            try:
                console.print(f"[blue]🔌 Connecting to {url}...[/blue]")
                
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        url,
                        ssl=ssl_context,
                        additional_headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Origin": "https://pocketoption.com"
                        },
                        ping_interval=25,
                        ping_timeout=20
                    ),
                    timeout=15
                )
                
                # Socket.IO handshake
                msg = await self.websocket.recv()
                if not str(msg).startswith('0{'):
                    continue
                
                await self.websocket.send("40")
                msg = await self.websocket.recv()
                
                # Send auth
                await self.websocket.send(self.ssid)
                
                # Wait for auth response
                for _ in range(10):
                    msg = await asyncio.wait_for(self.websocket.recv(), timeout=5)
                    msg_str = str(msg)
                    
                    if '"balance"' in msg_str:
                        try:
                            data = json.loads(msg_str[2:])
                            if isinstance(data, list) and len(data) >= 2:
                                self.balance = float(data[1].get('balance', 0))
                        except:
                            pass
                        self.authenticated = True
                        self.connected = True
                        console.print(f"[green]✅ Connected! Balance: ${self.balance:.2f}[/green]")
                        return True
                    
                    if '"error"' in msg_str.lower():
                        break
                        
            except Exception as e:
                console.print(f"[yellow]⚠️ Connection failed: {e}[/yellow]")
                continue
        
        return False
    
    async def execute_trade(self, direction: str, amount: float, asset: str, duration: int = 60) -> TradeResult:
        """
        Execute a trade on Pocket Option
        """
        try:
            if not self.connected or not self.websocket:
                return TradeResult(
                    signal_id="",
                    success=False,
                    direction=direction,
                    amount=amount,
                    asset=asset,
                    error="Not connected"
                )
            
            # Format trade message
            trade_msg = json.dumps([
                "trade",
                {
                    "asset": asset,
                    "amount": amount,
                    "action": "call" if direction.upper() == "CALL" else "put",
                    "time": duration,
                    "isDemo": ACCOUNT_TYPE == "demo"
                }
            ])
            
            await self.websocket.send(f"42{trade_msg}")
            console.print(f"[cyan]📤 Trade sent: {direction} ${amount} on {asset}[/cyan]")
            
            return TradeResult(
                signal_id="",
                success=True,
                direction=direction,
                amount=amount,
                asset=asset
            )
            
        except Exception as e:
            return TradeResult(
                signal_id="",
                success=False,
                direction=direction,
                amount=amount,
                asset=asset,
                error=str(e)
            )
    
    async def keep_alive(self):
        """Keep connection alive with ping/pong"""
        while self._running and self.websocket:
            try:
                if self.websocket:
                    await self.websocket.send("2")
                await asyncio.sleep(25)
            except:
                break
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self._running = False
        if self.websocket:
            await self.websocket.close()
        self.connected = False
        self.authenticated = False


class CloudServerClient:
    """
    Handles communication with cloud server for signals
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self._last_signal_id = None
    
    def get_pending_signals(self) -> List[Dict]:
        """Get pending signals from cloud server"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/desktop-client/signals",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('signals', [])
        except Exception as e:
            logger.warning(f"Failed to get signals: {e}")
        return []
    
    def report_trade_result(self, result: TradeResult):
        """Report trade result back to cloud server"""
        try:
            self.session.post(
                f"{self.base_url}/api/desktop-client/trade-result",
                json={
                    "signal_id": result.signal_id,
                    "success": result.success,
                    "direction": result.direction,
                    "amount": result.amount,
                    "asset": result.asset,
                    "profit": result.profit,
                    "error": result.error,
                    "timestamp": result.timestamp.isoformat()
                },
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to report trade: {e}")
    
    def update_status(self, connected: bool, balance: float):
        """Update desktop client status on cloud server"""
        try:
            self.session.post(
                f"{self.base_url}/api/desktop-client/status",
                json={
                    "connected": connected,
                    "balance": balance,
                    "account_type": ACCOUNT_TYPE,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                timeout=10
            )
        except Exception as e:
            logger.debug(f"Failed to update status: {e}")


class TradingBot:
    """
    Main trading bot orchestrator
    """
    
    def __init__(self):
        self.po_client = PocketOptionClient()
        self.cloud_client = CloudServerClient(CLOUD_SERVER_URL)
        self._running = False
        self._trades_this_hour = 0
        self._hour_start = time.time()
    
    def _reset_hourly_counter(self):
        """Reset hourly trade counter"""
        current_time = time.time()
        if current_time - self._hour_start >= 3600:
            self._trades_this_hour = 0
            self._hour_start = current_time
    
    async def run(self):
        """Main bot loop"""
        console.print(Panel.fit(
            "[bold green]🤖 Pocket Option Desktop Trading Client[/bold green]\n"
            f"Account: {ACCOUNT_TYPE.upper()}\n"
            f"Cloud Server: {CLOUD_SERVER_URL}\n"
            f"Auto-Trade: {'Enabled' if AUTO_TRADE_ENABLED else 'Disabled'}",
            title="Starting Bot"
        ))
        
        self._running = True
        
        # Connect to Pocket Option
        if not await self.po_client.connect():
            console.print("[red]❌ Failed to connect to Pocket Option. Retrying in 30s...[/red]")
            await asyncio.sleep(30)
            return await self.run()  # Retry
        
        # Start keep-alive task
        self.po_client._running = True
        asyncio.create_task(self.po_client.keep_alive())
        
        # Main loop
        while self._running:
            try:
                self._reset_hourly_counter()
                
                # Update status on cloud server
                self.cloud_client.update_status(
                    self.po_client.connected,
                    self.po_client.balance
                )
                
                # Check for signals
                if AUTO_TRADE_ENABLED and self._trades_this_hour < MAX_TRADES_PER_HOUR:
                    signals = self.cloud_client.get_pending_signals()
                    
                    for signal in signals:
                        if signal.get('confidence', 0) >= MIN_CONFIDENCE:
                            console.print(f"[cyan]📨 Signal received: {signal}[/cyan]")
                            
                            result = await self.po_client.execute_trade(
                                direction=signal.get('direction', 'CALL'),
                                amount=signal.get('amount', DEFAULT_TRADE_AMOUNT),
                                asset=signal.get('asset', 'EURUSD'),
                                duration=signal.get('duration', 60)
                            )
                            
                            result.signal_id = signal.get('id', '')
                            self.cloud_client.report_trade_result(result)
                            
                            if result.success:
                                self._trades_this_hour += 1
                                console.print(f"[green]✅ Trade executed![/green]")
                            else:
                                console.print(f"[red]❌ Trade failed: {result.error}[/red]")
                
                await asyncio.sleep(SIGNAL_POLL_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception(f"Bot error: {e}")
                await asyncio.sleep(5)
        
        await self.po_client.disconnect()
        console.print("[yellow]👋 Bot stopped[/yellow]")
    
    def stop(self):
        """Stop the bot"""
        self._running = False


def main():
    """Entry point"""
    console.print("[bold]Pocket Option Desktop Trading Client[/bold]")
    console.print(f"Python {sys.version}")
    console.print()
    
    bot = TradingBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        bot.stop()


if __name__ == "__main__":
    main()
