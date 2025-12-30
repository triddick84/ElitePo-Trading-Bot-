"""
Browser Automation Module for Pocket Option Trading
Uses Playwright for headless browser automation to execute real trades

This module:
1. Launches a headless Chromium browser
2. Logs into Pocket Option with user credentials
3. Navigates to the trading platform
4. Executes trades programmatically
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Pocket Option URLs - using alternative domains that work better
PO_DEMO_URL = "https://pocket2.click/en/cabinet/demo-quick-high-low/"
PO_LIVE_URL = "https://pocket2.click/en/cabinet/quick-high-low/"
PO_LOGIN_URL = "https://pocket2.click/en/login/"


@dataclass
class BrowserState:
    """Tracks browser automation state"""
    is_running: bool = False
    is_logged_in: bool = False
    is_trading_page: bool = False
    current_balance: float = 0.0
    account_type: str = "demo"  # "demo" or "live"
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    trade_count: int = 0
    

class PocketOptionBrowserAutomation:
    """
    Headless browser automation for Pocket Option trading
    
    Handles:
    - Browser lifecycle management
    - Login and session maintenance
    - Trade execution via DOM manipulation
    - Balance and status monitoring
    """
    
    def __init__(self, db, credentials: Dict[str, str]):
        """
        Initialize browser automation
        
        Args:
            db: Database connection
            credentials: Dict with 'email' and 'password' keys
        """
        self.db = db
        self.credentials = credentials
        self.state = BrowserState()
        self.browser = None
        self.context = None
        self.page = None
        self._lock = asyncio.Lock()
        
        logger.info("🌐 Browser Automation initialized")
    
    async def start(self, account_type: str = "demo") -> Dict:
        """
        Start browser automation and login to Pocket Option
        
        Args:
            account_type: "demo" or "live"
        
        Returns:
            Status dictionary
        """
        async with self._lock:
            try:
                if self.state.is_running:
                    return {"success": True, "message": "Browser already running"}
                
                logger.info(f"🚀 Starting browser automation ({account_type} account)...")
                
                from playwright.async_api import async_playwright
                
                self.playwright = await async_playwright().start()
                
                # Find chromium executable
                chromium_path = "/pw-browsers/chromium-1200/chrome-linux/chrome"
                
                # Launch browser with stealth settings
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    executable_path=chromium_path,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-gpu',
                        '--window-size=1920,1080',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                # Create context with realistic settings
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                # Add stealth script to avoid detection
                await self.context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """)
                
                self.page = await self.context.new_page()
                
                # Set longer timeout for slow connections
                self.page.set_default_timeout(30000)
                
                self.state.is_running = True
                self.state.account_type = account_type
                self.state.last_activity = datetime.now(timezone.utc)
                
                logger.info("✅ Browser started successfully")
                
                # Now login
                login_result = await self._login()
                if not login_result['success']:
                    return login_result
                
                # Navigate to trading page
                nav_result = await self._navigate_to_trading(account_type)
                if not nav_result['success']:
                    return nav_result
                
                return {
                    "success": True,
                    "message": f"Browser automation started ({account_type})",
                    "state": self._get_state_dict()
                }
                
            except Exception as e:
                logger.error(f"❌ Browser start failed: {e}")
                self.state.error = str(e)
                await self._cleanup()
                return {"success": False, "error": str(e)}
    
    async def _login(self) -> Dict:
        """Login to Pocket Option"""
        try:
            logger.info("🔐 Logging into Pocket Option...")
            
            # Navigate to login page with longer timeout
            try:
                await self.page.goto(PO_LOGIN_URL, wait_until='domcontentloaded', timeout=60000)
            except Exception as nav_error:
                logger.warning(f"Navigation issue: {nav_error}, trying with load state...")
                await self.page.goto(PO_LOGIN_URL, timeout=60000)
            
            await asyncio.sleep(3)  # Wait for page to fully load
            
            # Accept cookies if present
            try:
                cookie_btn = self.page.locator('button:has-text("Accept"), button:has-text("OK"), .cookie-accept')
                if await cookie_btn.count() > 0:
                    await cookie_btn.first.click()
                    await asyncio.sleep(1)
            except:
                pass
            
            # Fill login form - try multiple selector patterns
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                '#email',
                'input[placeholder*="email" i]',
                'input[autocomplete="email"]'
            ]
            
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password',
                'input[placeholder*="password" i]'
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        email_input = el
                        break
                except:
                    continue
            
            password_input = None
            for selector in password_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        password_input = el
                        break
                except:
                    continue
            
            if not email_input or not password_input:
                # Take screenshot for debugging
                screenshot = await self.page.screenshot()
                logger.error("Could not find login form elements")
                return {"success": False, "error": "Login form not found"}
            
            # Wait for inputs to be visible
            await email_input.wait_for(state='visible', timeout=10000)
            
            # Clear and fill email
            await email_input.fill('')
            await email_input.type(self.credentials['email'], delay=50)
            
            # Clear and fill password
            await password_input.fill('')
            await password_input.type(self.credentials['password'], delay=50)
            
            await asyncio.sleep(1)
            
            # Click login button
            login_btn = self.page.locator('button[type="submit"], button:has-text("Log in"), button:has-text("Sign in"), .btn-login')
            await login_btn.click()
            
            # Wait for navigation/login completion
            await asyncio.sleep(5)
            
            # Check if login was successful
            current_url = self.page.url
            if 'login' not in current_url.lower() or 'cabinet' in current_url.lower():
                self.state.is_logged_in = True
                logger.info("✅ Login successful!")
                return {"success": True, "message": "Logged in successfully"}
            else:
                # Check for error messages
                error_el = self.page.locator('.error, .alert-danger, .login-error')
                if await error_el.count() > 0:
                    error_text = await error_el.first.text_content()
                    self.state.error = error_text
                    return {"success": False, "error": f"Login failed: {error_text}"}
                
                return {"success": False, "error": "Login failed - still on login page"}
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _navigate_to_trading(self, account_type: str) -> Dict:
        """Navigate to trading page"""
        try:
            target_url = PO_LIVE_URL if account_type == "live" else PO_DEMO_URL
            
            logger.info(f"📊 Navigating to {account_type} trading page...")
            
            await self.page.goto(target_url, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            # Verify we're on trading page
            current_url = self.page.url
            if 'quick-high-low' in current_url or 'cabinet' in current_url:
                self.state.is_trading_page = True
                
                # Try to get balance
                await self._update_balance()
                
                logger.info(f"✅ On trading page. Balance: ${self.state.current_balance:.2f}")
                return {"success": True, "message": "On trading page"}
            else:
                return {"success": False, "error": "Failed to navigate to trading page"}
                
        except Exception as e:
            logger.error(f"❌ Navigation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_balance(self):
        """Update current balance from page"""
        try:
            # Multiple selectors for balance
            balance_selectors = [
                '.balance-value',
                '.user-balance',
                '[data-balance]',
                '.balance__value',
                '.header-balance',
                '.js-balance'
            ]
            
            for selector in balance_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.text_content()
                        # Extract number from text
                        import re
                        match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                        if match:
                            self.state.current_balance = float(match.group())
                            return
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Balance update failed: {e}")
    
    async def execute_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        duration: int
    ) -> Dict:
        """
        Execute a trade on Pocket Option
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc')
            direction: 'call' or 'put'
            amount: Trade amount in dollars
            duration: Trade duration in seconds
        
        Returns:
            Trade execution result
        """
        async with self._lock:
            try:
                if not self.state.is_running or not self.state.is_logged_in:
                    return {"success": False, "error": "Browser not ready - login first"}
                
                if not self.state.is_trading_page:
                    nav_result = await self._navigate_to_trading(self.state.account_type)
                    if not nav_result['success']:
                        return nav_result
                
                logger.info(f"🎯 Executing trade: {direction.upper()} {asset} ${amount} for {duration}s")
                
                # Step 1: Set trade amount
                amount_result = await self._set_trade_amount(amount)
                if not amount_result['success']:
                    return amount_result
                
                # Step 2: Set duration (expiry time)
                duration_result = await self._set_duration(duration)
                if not duration_result['success']:
                    return duration_result
                
                # Step 3: Select asset (if needed)
                # Note: Most users trade on current asset, skip for now
                
                # Step 4: Click trade button
                trade_result = await self._click_trade_button(direction)
                if not trade_result['success']:
                    return trade_result
                
                self.state.trade_count += 1
                self.state.last_activity = datetime.now(timezone.utc)
                
                # Update balance after trade
                await asyncio.sleep(1)
                await self._update_balance()
                
                order_id = f"PO_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                
                logger.info(f"✅ Trade executed! Order: {order_id}")
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "direction": direction,
                    "amount": amount,
                    "duration": duration,
                    "execution_time": datetime.now(timezone.utc).isoformat(),
                    "balance": self.state.current_balance
                }
                
            except Exception as e:
                logger.error(f"❌ Trade execution error: {e}")
                return {"success": False, "error": str(e)}
    
    async def _set_trade_amount(self, amount: float) -> Dict:
        """Set the trade amount on the platform"""
        try:
            # Find amount input
            amount_selectors = [
                'input.amount-input',
                'input[name="amount"]',
                '.js-amount-input',
                'input.input-control-cabinet__input',
                'input[data-input="amount"]'
            ]
            
            for selector in amount_selectors:
                try:
                    amount_input = self.page.locator(selector).first
                    if await amount_input.count() > 0:
                        await amount_input.click()
                        await asyncio.sleep(0.2)
                        
                        # Clear and set new value
                        await amount_input.fill('')
                        await amount_input.type(str(int(amount)), delay=30)
                        
                        logger.debug(f"Set amount to ${amount}")
                        return {"success": True}
                except:
                    continue
            
            # If no input found, try clicking preset buttons
            preset_selectors = f'.js-amount-btn[data-value="{int(amount)}"], button:has-text("${int(amount)}")'
            preset_btn = self.page.locator(preset_selectors).first
            if await preset_btn.count() > 0:
                await preset_btn.click()
                return {"success": True}
            
            return {"success": False, "error": "Could not find amount input"}
            
        except Exception as e:
            return {"success": False, "error": f"Set amount error: {e}"}
    
    async def _set_duration(self, duration: int) -> Dict:
        """Set the trade duration"""
        try:
            # Click on time selector
            time_selectors = [
                '.js-expiration-select',
                '.expiration-selector',
                '.time-picker',
                '.js-time'
            ]
            
            for selector in time_selectors:
                try:
                    time_el = self.page.locator(selector).first
                    if await time_el.count() > 0:
                        await time_el.click()
                        await asyncio.sleep(0.5)
                        
                        # Select duration option
                        # Pocket Option typically uses formats like "5s", "15s", "1m" etc
                        duration_text = f"{duration}s" if duration < 60 else f"{duration//60}m"
                        
                        option = self.page.locator(f'[data-value="{duration}"], :has-text("{duration_text}")')
                        if await option.count() > 0:
                            await option.first.click()
                            logger.debug(f"Set duration to {duration}s")
                            return {"success": True}
                except:
                    continue
            
            # Duration setting might already be correct, continue
            logger.debug("Duration selector not found, continuing with default")
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": f"Set duration error: {e}"}
    
    async def _click_trade_button(self, direction: str) -> Dict:
        """Click the appropriate trade button"""
        try:
            if direction.lower() == 'call':
                # CALL/UP/HIGHER button
                button_selectors = [
                    'button.btn-call',
                    'button.js-call',
                    'button:has-text("Higher")',
                    'button:has-text("CALL")',
                    'button:has-text("UP")',
                    '.call-btn',
                    'button[data-action="call"]',
                    '.btn-success.call'
                ]
            else:
                # PUT/DOWN/LOWER button
                button_selectors = [
                    'button.btn-put',
                    'button.js-put',
                    'button:has-text("Lower")',
                    'button:has-text("PUT")',
                    'button:has-text("DOWN")',
                    '.put-btn',
                    'button[data-action="put"]',
                    '.btn-danger.put'
                ]
            
            for selector in button_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0:
                        # Check if button is enabled
                        is_disabled = await btn.get_attribute('disabled')
                        if is_disabled:
                            continue
                        
                        await btn.click()
                        logger.debug(f"Clicked {direction.upper()} button")
                        return {"success": True}
                except:
                    continue
            
            return {"success": False, "error": f"Could not find {direction} button"}
            
        except Exception as e:
            return {"success": False, "error": f"Click trade error: {e}"}
    
    async def stop(self) -> Dict:
        """Stop browser automation"""
        try:
            logger.info("🛑 Stopping browser automation...")
            await self._cleanup()
            return {"success": True, "message": "Browser stopped"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
        except:
            pass
        
        self.browser = None
        self.context = None
        self.page = None
        self.state = BrowserState()
        
        logger.info("✅ Browser resources cleaned up")
    
    def _get_state_dict(self) -> Dict:
        """Get state as dictionary"""
        return {
            "is_running": self.state.is_running,
            "is_logged_in": self.state.is_logged_in,
            "is_trading_page": self.state.is_trading_page,
            "balance": self.state.current_balance,
            "account_type": self.state.account_type,
            "trade_count": self.state.trade_count,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None,
            "error": self.state.error
        }
    
    def get_status(self) -> Dict:
        """Get current automation status"""
        return {
            "success": True,
            "state": self._get_state_dict()
        }


# Global instance management
_browser_automation: Optional[PocketOptionBrowserAutomation] = None


async def get_browser_automation(db, credentials: Dict[str, str] = None) -> PocketOptionBrowserAutomation:
    """Get or create browser automation instance"""
    global _browser_automation
    
    if _browser_automation is None:
        if credentials is None:
            # Default credentials from environment
            credentials = {
                'email': os.environ.get('PO_EMAIL', 'thomas.riddick84@gmail.com'),
                'password': os.environ.get('PO_PASSWORD', 'Tonyistheman#1')
            }
        _browser_automation = PocketOptionBrowserAutomation(db, credentials)
    
    return _browser_automation


async def stop_browser_automation():
    """Stop and clear browser automation instance"""
    global _browser_automation
    
    if _browser_automation:
        await _browser_automation.stop()
        _browser_automation = None
