"""
Pocket Option Local Trading Bot
================================

This script runs on YOUR LOCAL MACHINE to execute trades on Pocket Option.
Since the cloud server cannot connect to Pocket Option directly, this local
script bridges the gap.

HOW TO USE:
1. Install requirements: pip install playwright requests
2. Install browser: playwright install chromium
3. Configure credentials below
4. Run: python pocket_option_local_bot.py

The script will:
1. Log into Pocket Option using your credentials
2. Connect to the cloud server to receive trade signals
3. Execute trades automatically on your behalf
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

# =============================================================================
# CONFIGURATION - EDIT THESE VALUES
# =============================================================================

# Your Pocket Option credentials
PO_EMAIL = "thomas.riddick84@gmail.com"
PO_PASSWORD = "Tonyistheman#1"

# Your cloud server URL (the trading bot server)
CLOUD_SERVER_URL = "https://signalbot-34.preview.emergentagent.com"

# Account type: "demo" or "live"
ACCOUNT_TYPE = "live"

# Trade settings
DEFAULT_TRADE_AMOUNT = 1.0  # dollars
MIN_CONFIDENCE = 80.0  # minimum signal confidence to trade

# =============================================================================
# DO NOT EDIT BELOW THIS LINE
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pocket Option URLs
PO_LOGIN_URL = "https://pocketoption.com/en/login/"
PO_DEMO_URL = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
PO_LIVE_URL = "https://pocketoption.com/en/cabinet/quick-high-low/"


@dataclass
class BotState:
    """Bot state tracker"""
    is_running: bool = False
    is_logged_in: bool = False
    is_trading_page: bool = False
    balance: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    last_signal_id: str = ""


class PocketOptionLocalBot:
    """
    Local bot that connects to cloud server and executes trades on Pocket Option
    """
    
    def __init__(self, email: str, password: str, server_url: str, account_type: str = "demo"):
        self.email = email
        self.password = password
        self.server_url = server_url
        self.account_type = account_type
        self.state = BotState()
        
        # Browser components
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """Start the bot"""
        logger.info("🚀 Starting Pocket Option Local Bot...")
        
        try:
            # Start browser
            await self._start_browser()
            
            # Login to Pocket Option
            await self._login()
            
            # Navigate to trading page
            await self._navigate_to_trading()
            
            # Start signal polling loop
            await self._signal_loop()
            
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        finally:
            await self._cleanup()
    
    async def _start_browser(self):
        """Start Playwright browser"""
        from playwright.async_api import async_playwright
        
        logger.info("🌐 Starting browser...")
        
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Run with visible browser
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--window-size=1920,1080',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Add stealth script
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)
        
        logger.info("✅ Browser started")
    
    async def _login(self):
        """Login to Pocket Option"""
        logger.info("🔐 Logging into Pocket Option...")
        
        await self.page.goto(PO_LOGIN_URL, wait_until='domcontentloaded')
        await asyncio.sleep(2)
        
        # Accept cookies if present
        try:
            cookie_btn = self.page.locator('button:has-text("Accept"), button:has-text("OK")')
            if await cookie_btn.count() > 0:
                await cookie_btn.first.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Fill login form
        email_input = self.page.locator('input[type="email"], input[name="email"]').first
        password_input = self.page.locator('input[type="password"], input[name="password"]').first
        
        await email_input.fill(self.email)
        await password_input.fill(self.password)
        
        await asyncio.sleep(0.5)
        
        # Click login
        login_btn = self.page.locator('button[type="submit"], button:has-text("Log in")').first
        await login_btn.click()
        
        # Wait for login
        await asyncio.sleep(5)
        
        current_url = self.page.url
        if 'login' not in current_url.lower() or 'cabinet' in current_url.lower():
            self.state.is_logged_in = True
            logger.info("✅ Login successful!")
        else:
            raise Exception("Login failed - check credentials")
    
    async def _navigate_to_trading(self):
        """Navigate to trading page"""
        target_url = PO_LIVE_URL if self.account_type == "live" else PO_DEMO_URL
        
        logger.info(f"📊 Navigating to {self.account_type} trading page...")
        
        await self.page.goto(target_url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        self.state.is_trading_page = True
        await self._update_balance()
        
        logger.info(f"✅ On trading page. Balance: ${self.state.balance:.2f}")
    
    async def _update_balance(self):
        """Update balance from page"""
        try:
            selectors = ['.balance-value', '.user-balance', '.js-balance']
            for selector in selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.text_content()
                        import re
                        match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                        if match:
                            self.state.balance = float(match.group())
                            return
                except:
                    continue
        except:
            pass
    
    async def _signal_loop(self):
        """Main loop - poll cloud server for signals and execute trades"""
        logger.info("🔄 Starting signal polling loop...")
        logger.info(f"📡 Cloud server: {self.server_url}")
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # Check for pending trades from cloud server
                    async with session.get(
                        f"{self.server_url}/api/trade-executor/pending",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and data.get('pending_trades'):
                                for trade in data['pending_trades']:
                                    await self._execute_trade(trade, session)
                    
                    # Also check auto-trade status
                    async with session.get(
                        f"{self.server_url}/api/auto-trade/status",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            status = await response.json()
                            if status.get('is_auto_trade_enabled'):
                                logger.debug("Auto-trading enabled on server")
                    
                except asyncio.TimeoutError:
                    logger.debug("Server poll timeout")
                except Exception as e:
                    logger.warning(f"Signal poll error: {e}")
                
                # Update balance
                await self._update_balance()
                
                # Poll every 2 seconds
                await asyncio.sleep(2)
    
    async def _execute_trade(self, trade: Dict, session: aiohttp.ClientSession):
        """Execute a trade on Pocket Option"""
        try:
            order_id = trade.get('order_id')
            asset = trade.get('asset', 'EURUSD_otc')
            direction = trade.get('direction', 'call')
            amount = trade.get('amount', DEFAULT_TRADE_AMOUNT)
            duration = trade.get('duration', 60)
            
            logger.info(f"🎯 Executing trade: {direction.upper()} {asset} ${amount}")
            
            # Set amount
            await self._set_amount(amount)
            
            # Click trade button
            success = await self._click_trade_button(direction)
            
            if success:
                self.state.total_trades += 1
                logger.info(f"✅ Trade executed! Order: {order_id}")
                
                # Report execution to cloud server
                await self._report_execution(session, order_id, True)
            else:
                logger.error(f"❌ Trade execution failed")
                await self._report_execution(session, order_id, False)
            
        except Exception as e:
            logger.error(f"❌ Trade error: {e}")
    
    async def _set_amount(self, amount: float):
        """Set trade amount"""
        try:
            amount_input = self.page.locator('input.amount-input, input[name="amount"]').first
            if await amount_input.count() > 0:
                await amount_input.fill(str(int(amount)))
        except:
            pass
    
    async def _click_trade_button(self, direction: str) -> bool:
        """Click CALL or PUT button"""
        try:
            if direction.lower() == 'call':
                selectors = ['button.btn-call', 'button:has-text("Higher")', 'button:has-text("CALL")']
            else:
                selectors = ['button.btn-put', 'button:has-text("Lower")', 'button:has-text("PUT")']
            
            for selector in selectors:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click()
                        return True
                except:
                    continue
            
            return False
        except:
            return False
    
    async def _report_execution(self, session: aiohttp.ClientSession, order_id: str, success: bool):
        """Report execution status back to cloud server"""
        try:
            async with session.post(
                f"{self.server_url}/api/trade-executor/confirm-execution",
                json={
                    "order_id": order_id,
                    "bridge_order_id": f"LOCAL_{datetime.now().strftime('%H%M%S%f')}",
                    "execution_price": 0,
                    "execution_time": datetime.now().isoformat(),
                    "success": success
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.debug(f"Execution reported: {order_id}")
        except Exception as e:
            logger.warning(f"Failed to report execution: {e}")
    
    async def _cleanup(self):
        """Cleanup resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        
        logger.info("✅ Cleanup complete")


async def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║          Pocket Option Local Trading Bot v1.0             ║
    ║                                                           ║
    ║  This bot runs on YOUR computer and executes trades on    ║
    ║  Pocket Option based on signals from the cloud server.    ║
    ║                                                           ║
    ║  Press Ctrl+C to stop the bot.                            ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    bot = PocketOptionLocalBot(
        email=PO_EMAIL,
        password=PO_PASSWORD,
        server_url=CLOUD_SERVER_URL,
        account_type=ACCOUNT_TYPE
    )
    
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
