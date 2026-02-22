"""
Pocket Option Local Trading Bot v2.0
====================================

This script runs on YOUR LOCAL MACHINE to execute trades on Pocket Option.
Since the cloud server cannot connect to Pocket Option directly, this local
script bridges the gap.

HOW TO USE:
1. Install requirements: pip install playwright requests aiohttp
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
import re
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
CLOUD_SERVER_URL = "https://algo-signal-hub-2.preview.emergentagent.com"

# Account type: "demo" or "live"
ACCOUNT_TYPE = "live"

# Trade settings
DEFAULT_TRADE_AMOUNT = 1.0  # dollars
MIN_CONFIDENCE = 80.0  # minimum signal confidence to trade

# Run headless (no visible browser window)
HEADLESS = False  # Set to True to hide browser

# =============================================================================
# DO NOT EDIT BELOW THIS LINE
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pocket Option URLs - multiple domains for fallback
PO_DOMAINS = [
    "https://pocketoption.com",
    "https://pocket2.click",
    "https://po.trade"
]

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
        self.base_url = None
        
        # Browser components
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """Start the bot"""
        logger.info("🚀 Starting Pocket Option Local Bot v2.0...")
        
        try:
            # Start browser
            await self._start_browser()
            
            # Find working domain
            await self._find_working_domain()
            
            # Login to Pocket Option
            await self._login()
            
            # Navigate to trading page
            await self._navigate_to_trading()
            
            # Wait for trading interface to load
            await self._wait_for_trading_interface()
            
            # Start signal polling loop
            await self._signal_loop()
            
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()
    
    async def _start_browser(self):
        """Start Playwright browser"""
        from playwright.async_api import async_playwright
        
        logger.info("🌐 Starting browser...")
        
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=HEADLESS,
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
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)
        
        logger.info("✅ Browser started")
    
    async def _find_working_domain(self):
        """Find a working Pocket Option domain"""
        logger.info("🔍 Finding working Pocket Option domain...")
        
        for domain in PO_DOMAINS:
            try:
                logger.info(f"   Trying {domain}...")
                response = await self.page.goto(domain, wait_until='domcontentloaded', timeout=30000)
                if response and response.status == 200:
                    self.base_url = domain
                    logger.info(f"✅ Using domain: {domain}")
                    return
            except Exception as e:
                logger.warning(f"   {domain} failed: {e}")
                continue
        
        # Default to first domain
        self.base_url = PO_DOMAINS[0]
        logger.warning(f"⚠️ Using default domain: {self.base_url}")
    
    async def _login(self):
        """Login to Pocket Option"""
        logger.info("🔐 Logging into Pocket Option...")
        
        login_url = f"{self.base_url}/en/login/"
        await self.page.goto(login_url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        # Take screenshot for debugging
        await self.page.screenshot(path="login_page.png")
        logger.info("📸 Login page screenshot saved to login_page.png")
        
        # Accept cookies if present
        try:
            cookie_selectors = [
                'button:has-text("Accept")',
                'button:has-text("OK")',
                'button:has-text("I agree")',
                '.cookie-accept',
                '#cookie-accept'
            ]
            for selector in cookie_selectors:
                btn = self.page.locator(selector)
                if await btn.count() > 0:
                    await btn.first.click()
                    logger.info("   Accepted cookies")
                    await asyncio.sleep(1)
                    break
        except:
            pass
        
        # Find and fill login form - try multiple selector patterns
        email_filled = False
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[autocomplete="email"]',
            'input[placeholder*="mail" i]',
            'input[placeholder*="Email" i]',
            '#email',
            '.auth-form input[type="text"]:first-child',
            'form input:first-of-type'
        ]
        
        for selector in email_selectors:
            try:
                el = self.page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    await el.fill('')
                    await el.type(self.email, delay=30)
                    email_filled = True
                    logger.info(f"   Email filled using: {selector}")
                    break
            except Exception as e:
                continue
        
        if not email_filled:
            logger.error("❌ Could not find email input!")
            await self.page.screenshot(path="login_error.png")
            raise Exception("Email input not found")
        
        # Find and fill password
        password_filled = False
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[autocomplete="current-password"]',
            'input[placeholder*="assword" i]',
            '#password'
        ]
        
        for selector in password_selectors:
            try:
                el = self.page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    await el.fill('')
                    await el.type(self.password, delay=30)
                    password_filled = True
                    logger.info(f"   Password filled using: {selector}")
                    break
            except:
                continue
        
        if not password_filled:
            logger.error("❌ Could not find password input!")
            raise Exception("Password input not found")
        
        await asyncio.sleep(1)
        
        # Click login button
        login_selectors = [
            'button[type="submit"]',
            'button:has-text("Log in")',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'button:has-text("Войти")',
            '.btn-login',
            '.auth-form button',
            'form button[type="submit"]'
        ]
        
        login_clicked = False
        for selector in login_selectors:
            try:
                btn = self.page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    login_clicked = True
                    logger.info(f"   Login button clicked using: {selector}")
                    break
            except:
                continue
        
        if not login_clicked:
            # Try pressing Enter as fallback
            await self.page.keyboard.press('Enter')
            logger.info("   Pressed Enter to submit")
        
        # Wait for login to complete
        logger.info("   Waiting for login to complete...")
        await asyncio.sleep(8)
        
        # Take screenshot after login attempt
        await self.page.screenshot(path="after_login.png")
        logger.info("📸 After login screenshot saved to after_login.png")
        
        # Check if login was successful
        current_url = self.page.url
        logger.info(f"   Current URL: {current_url}")
        
        if 'cabinet' in current_url.lower() or 'trade' in current_url.lower():
            self.state.is_logged_in = True
            logger.info("✅ Login successful!")
        elif 'login' not in current_url.lower():
            self.state.is_logged_in = True
            logger.info("✅ Login appears successful (redirected)")
        else:
            # Check for error messages
            error_selectors = ['.error', '.alert-danger', '.auth-error', '.login-error']
            for selector in error_selectors:
                try:
                    el = self.page.locator(selector)
                    if await el.count() > 0:
                        error_text = await el.first.text_content()
                        logger.error(f"❌ Login error: {error_text}")
                        break
                except:
                    continue
            raise Exception("Login failed - still on login page")
    
    async def _navigate_to_trading(self):
        """Navigate to trading page"""
        if self.account_type == "live":
            target_url = f"{self.base_url}/en/cabinet/quick-high-low/"
        else:
            target_url = f"{self.base_url}/en/cabinet/demo-quick-high-low/"
        
        logger.info(f"📊 Navigating to {self.account_type} trading page...")
        logger.info(f"   URL: {target_url}")
        
        await self.page.goto(target_url, wait_until='domcontentloaded')
        await asyncio.sleep(5)
        
        # Take screenshot
        await self.page.screenshot(path="trading_page.png")
        logger.info("📸 Trading page screenshot saved to trading_page.png")
        
        self.state.is_trading_page = True
        await self._update_balance()
        
        logger.info(f"✅ On trading page. Balance: ${self.state.balance:.2f}")
    
    async def _wait_for_trading_interface(self):
        """Wait for trading interface elements to load"""
        logger.info("⏳ Waiting for trading interface to load...")
        
        # Wait for key elements
        interface_selectors = [
            '.trading-panel',
            '.chart-container',
            '.deal-container',
            '[class*="trading"]',
            '[class*="chart"]',
            '.btn-call, .btn-put',
            '[class*="call"], [class*="put"]'
        ]
        
        found = False
        for selector in interface_selectors:
            try:
                el = self.page.locator(selector)
                if await el.count() > 0:
                    logger.info(f"   Found trading element: {selector}")
                    found = True
                    break
            except:
                continue
        
        if not found:
            logger.warning("⚠️ Trading interface elements not detected - continuing anyway")
        
        # Additional wait for dynamic content
        await asyncio.sleep(3)
        
        # Debug: Print page structure
        try:
            # Get all buttons
            buttons = await self.page.locator('button').all()
            logger.info(f"   Found {len(buttons)} buttons on page")
            
            for i, btn in enumerate(buttons[:10]):  # First 10 buttons
                try:
                    text = await btn.text_content()
                    classes = await btn.get_attribute('class') or ''
                    logger.info(f"   Button {i}: text='{text[:30] if text else ''}' class='{classes[:50]}'")
                except:
                    pass
        except Exception as e:
            logger.debug(f"   Debug info error: {e}")
    
    async def _update_balance(self):
        """Update balance from page"""
        try:
            balance_selectors = [
                '.balance-value',
                '.user-balance',
                '.js-balance',
                '[class*="balance"]',
                '.header-balance',
                '.balance__value',
                '[data-balance]'
            ]
            
            for selector in balance_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.text_content()
                        if text:
                            # Extract number from text
                            match = re.search(r'[\d,]+\.?\d*', text.replace(',', '').replace(' ', ''))
                            if match:
                                self.state.balance = float(match.group())
                                logger.debug(f"   Balance updated: ${self.state.balance:.2f}")
                                return
                except:
                    continue
        except:
            pass
    
    async def _signal_loop(self):
        """Main loop - poll cloud server for signals and execute trades"""
        logger.info("🔄 Starting signal polling loop...")
        logger.info(f"📡 Cloud server: {self.server_url}")
        logger.info("Press Ctrl+C to stop")
        
        poll_count = 0
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    poll_count += 1
                    
                    # Check for pending trades from cloud server
                    async with session.get(
                        f"{self.server_url}/api/trade-executor/pending",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and data.get('pending_trades'):
                                trades = data['pending_trades']
                                logger.info(f"📋 Found {len(trades)} pending trade(s)")
                                
                                for trade in trades:
                                    if trade.get('order_id') != self.state.last_signal_id:
                                        await self._execute_trade(trade, session)
                                        self.state.last_signal_id = trade.get('order_id', '')
                    
                    # Status update every 30 polls
                    if poll_count % 30 == 0:
                        await self._update_balance()
                        logger.info(f"💰 Balance: ${self.state.balance:.2f} | Trades: {self.state.total_trades}")
                    
                except asyncio.TimeoutError:
                    logger.debug("Server poll timeout")
                except aiohttp.ClientError as e:
                    logger.warning(f"Connection error: {e}")
                except Exception as e:
                    logger.warning(f"Signal poll error: {e}")
                
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
            
            # Step 1: Set trade amount
            await self._set_amount(amount)
            await asyncio.sleep(0.5)
            
            # Step 2: Click trade button
            success = await self._click_trade_button(direction)
            
            if success:
                self.state.total_trades += 1
                logger.info(f"✅ Trade executed! Order: {order_id}")
                
                # Take screenshot of executed trade
                await self.page.screenshot(path=f"trade_{order_id}.png")
                
                # Report execution to cloud server
                await self._report_execution(session, order_id, True)
            else:
                logger.error(f"❌ Trade execution failed - could not find trade button")
                await self.page.screenshot(path=f"trade_failed_{order_id}.png")
                logger.info(f"📸 Failure screenshot saved")
                await self._report_execution(session, order_id, False)
            
        except Exception as e:
            logger.error(f"❌ Trade error: {e}")
            import traceback
            traceback.print_exc()
    
    async def _set_amount(self, amount: float):
        """Set trade amount on the platform"""
        logger.info(f"   Setting amount to ${amount}...")
        
        # Pocket Option amount selectors
        amount_selectors = [
            'input.input-control-cabinet__input',
            'input[class*="amount"]',
            'input[name="amount"]',
            '.deal-amount input',
            '.amount-input',
            'input[type="number"]',
            '.trading-panel input',
            'input[class*="deal"]'
        ]
        
        for selector in amount_selectors:
            try:
                el = self.page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    # Clear and set amount
                    await el.click()
                    await el.fill('')
                    await el.type(str(int(amount)), delay=50)
                    logger.info(f"   Amount set using: {selector}")
                    return True
            except Exception as e:
                continue
        
        # Try clicking amount increase/decrease buttons
        try:
            # Look for amount display and click to edit
            amount_display = self.page.locator('[class*="amount"]').first
            if await amount_display.count() > 0:
                await amount_display.click()
                await asyncio.sleep(0.3)
                # Try typing directly
                await self.page.keyboard.type(str(int(amount)))
                logger.info("   Amount set via keyboard")
                return True
        except:
            pass
        
        logger.warning("   Could not find amount input - using default")
        return False
    
    async def _click_trade_button(self, direction: str) -> bool:
        """Click the CALL (Higher/Up) or PUT (Lower/Down) button"""
        logger.info(f"   Looking for {direction.upper()} button...")
        
        if direction.lower() == 'call':
            # CALL / Higher / Up / Green button selectors
            button_selectors = [
                # Class-based selectors
                'button.btn-call',
                'button.call-btn', 
                'button[class*="call"]',
                'button[class*="higher"]',
                'button[class*="green"]',
                'button[class*="up"]',
                '.btn-call',
                '.call-btn',
                '[class*="call-btn"]',
                '[class*="btn-call"]',
                
                # Data attribute selectors
                'button[data-dir="call"]',
                'button[data-direction="call"]',
                '[data-dir="higher"]',
                
                # Text-based selectors
                'button:has-text("Higher")',
                'button:has-text("HIGHER")',
                'button:has-text("Call")',
                'button:has-text("CALL")',
                'button:has-text("Up")',
                'button:has-text("UP")',
                'button:has-text("Выше")',  # Russian
                
                # SVG/Icon based (green up arrow)
                'button.green',
                '.trading-panel button:first-child',
                '.deal-button--call',
                '.deal-buttons button:first-child'
            ]
        else:
            # PUT / Lower / Down / Red button selectors
            button_selectors = [
                # Class-based selectors
                'button.btn-put',
                'button.put-btn',
                'button[class*="put"]',
                'button[class*="lower"]',
                'button[class*="red"]',
                'button[class*="down"]',
                '.btn-put',
                '.put-btn',
                '[class*="put-btn"]',
                '[class*="btn-put"]',
                
                # Data attribute selectors
                'button[data-dir="put"]',
                'button[data-direction="put"]',
                '[data-dir="lower"]',
                
                # Text-based selectors
                'button:has-text("Lower")',
                'button:has-text("LOWER")',
                'button:has-text("Put")',
                'button:has-text("PUT")',
                'button:has-text("Down")',
                'button:has-text("DOWN")',
                'button:has-text("Ниже")',  # Russian
                
                # SVG/Icon based (red down arrow)
                'button.red',
                '.trading-panel button:last-child',
                '.deal-button--put',
                '.deal-buttons button:last-child'
            ]
        
        # Try each selector
        for selector in button_selectors:
            try:
                btn = self.page.locator(selector).first
                if await btn.count() > 0:
                    # Check if visible and enabled
                    if await btn.is_visible():
                        is_disabled = await btn.get_attribute('disabled')
                        if not is_disabled:
                            await btn.click()
                            logger.info(f"   ✅ Clicked {direction.upper()} button using: {selector}")
                            return True
            except Exception as e:
                continue
        
        # Fallback: Try to find buttons by visual position
        try:
            logger.info("   Trying visual button detection...")
            
            # Get all buttons
            buttons = await self.page.locator('button').all()
            
            for btn in buttons:
                try:
                    classes = await btn.get_attribute('class') or ''
                    text = await btn.text_content() or ''
                    
                    # Check for call/put indicators
                    if direction.lower() == 'call':
                        if any(x in classes.lower() for x in ['call', 'higher', 'green', 'up']):
                            await btn.click()
                            logger.info(f"   ✅ Clicked CALL button (fallback)")
                            return True
                        if any(x in text.lower() for x in ['call', 'higher', 'up', 'выше']):
                            await btn.click()
                            logger.info(f"   ✅ Clicked CALL button (text fallback)")
                            return True
                    else:
                        if any(x in classes.lower() for x in ['put', 'lower', 'red', 'down']):
                            await btn.click()
                            logger.info(f"   ✅ Clicked PUT button (fallback)")
                            return True
                        if any(x in text.lower() for x in ['put', 'lower', 'down', 'ниже']):
                            await btn.click()
                            logger.info(f"   ✅ Clicked PUT button (text fallback)")
                            return True
                except:
                    continue
        except Exception as e:
            logger.error(f"   Visual detection failed: {e}")
        
        logger.error(f"   ❌ Could not find {direction.upper()} button!")
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
                    logger.debug(f"   Execution reported: {order_id}")
        except Exception as e:
            logger.warning(f"   Failed to report execution: {e}")
    
    async def _cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up...")
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


async def test_manual_trade():
    """Test function to manually verify trade execution"""
    print("\n🧪 MANUAL TRADE TEST MODE")
    print("This will open Pocket Option and attempt to execute a test trade")
    print("-" * 50)
    
    bot = PocketOptionLocalBot(
        email=PO_EMAIL,
        password=PO_PASSWORD,
        server_url=CLOUD_SERVER_URL,
        account_type="demo"  # Always use demo for testing
    )
    
    try:
        await bot._start_browser()
        await bot._find_working_domain()
        await bot._login()
        await bot._navigate_to_trading()
        await bot._wait_for_trading_interface()
        
        print("\n📊 Trading interface loaded!")
        print("Attempting test CALL trade...")
        
        # Try to execute a test trade
        await bot._set_amount(1)
        await asyncio.sleep(1)
        success = await bot._click_trade_button('call')
        
        if success:
            print("✅ Test trade executed successfully!")
        else:
            print("❌ Test trade failed - check screenshots")
        
        print("\nScreenshots saved:")
        print("  - login_page.png")
        print("  - after_login.png")
        print("  - trading_page.png")
        
        # Wait before closing
        print("\nBrowser will close in 30 seconds...")
        await asyncio.sleep(30)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot._cleanup()


async def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║        Pocket Option Local Trading Bot v2.0               ║
    ║                                                           ║
    ║  This bot runs on YOUR computer and executes trades on    ║
    ║  Pocket Option based on signals from the cloud server.    ║
    ║                                                           ║
    ║  Press Ctrl+C to stop the bot.                            ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Check for test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        await test_manual_trade()
        return
    
    bot = PocketOptionLocalBot(
        email=PO_EMAIL,
        password=PO_PASSWORD,
        server_url=CLOUD_SERVER_URL,
        account_type=ACCOUNT_TYPE
    )
    
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
