"""
Pocket Option Selenium Trading Bot
===================================

Uses Selenium WebDriver to automate trading on Pocket Option.
This approach uses a real browser session which is more reliable than API connections.

Features:
- Automatic login with credentials
- Real browser session (less likely to be blocked)
- Trade execution via DOM manipulation
- Balance monitoring
- Trade result tracking
"""

import asyncio
import logging
import os
import time
import re
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from threading import Thread, Lock
import queue

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

logger = logging.getLogger(__name__)

# Pocket Option URLs
PO_LOGIN_URL = "https://pocketoption.com/en/login/"
PO_DEMO_URL = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
PO_LIVE_URL = "https://pocketoption.com/en/cabinet/quick-high-low/"

# Alternative domains
PO_DOMAINS = [
    "https://pocketoption.com",
    "https://po.trade",
    "https://pocket2.click"
]


@dataclass
class BotState:
    """Bot state tracking"""
    is_running: bool = False
    is_logged_in: bool = False
    is_on_trading_page: bool = False
    balance: float = 0.0
    is_demo: bool = True
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    last_error: Optional[str] = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SeleniumTradingBot:
    """
    Selenium-based trading bot for Pocket Option
    
    This bot runs in a separate thread and processes trade commands from a queue.
    """
    
    def __init__(
        self,
        email: str,
        password: str,
        demo: bool = True,
        headless: bool = True
    ):
        """
        Initialize the trading bot
        
        Args:
            email: Pocket Option login email
            password: Pocket Option password
            demo: True for demo account, False for real
            headless: Run browser in headless mode
        """
        self.email = email
        self.password = password
        self.demo = demo
        self.headless = headless
        
        self.state = BotState(is_demo=demo)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Thread-safe command queue
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Threading
        self._lock = Lock()
        self._bot_thread: Optional[Thread] = None
        self._running = False
        
        logger.info(f"🤖 Selenium Trading Bot initialized (demo={demo}, headless={headless})")
    
    def start(self) -> Dict:
        """Start the bot in a background thread"""
        with self._lock:
            if self._running:
                return {"success": True, "message": "Bot already running"}
            
            try:
                self._running = True
                self._bot_thread = Thread(target=self._run_bot_loop, daemon=True)
                self._bot_thread.start()
                
                # Wait for initialization
                time.sleep(2)
                
                if self.state.is_running:
                    return {
                        "success": True,
                        "message": "Bot started successfully",
                        "state": self._get_state_dict()
                    }
                else:
                    return {
                        "success": False,
                        "error": self.state.last_error or "Failed to start bot"
                    }
                    
            except Exception as e:
                self._running = False
                logger.error(f"Failed to start bot: {e}")
                return {"success": False, "error": str(e)}
    
    def _run_bot_loop(self):
        """Main bot loop running in background thread"""
        try:
            # Initialize browser
            self._init_browser()
            
            # Login
            if not self._login():
                self.state.last_error = "Login failed"
                self._running = False
                return
            
            # Navigate to trading page
            if not self._navigate_to_trading():
                self.state.last_error = "Failed to navigate to trading page"
                self._running = False
                return
            
            self.state.is_running = True
            logger.info("✅ Bot is running and ready for trades")
            
            # Main command processing loop
            while self._running:
                try:
                    # Check for commands (non-blocking with timeout)
                    try:
                        cmd = self.command_queue.get(timeout=1)
                        result = self._process_command(cmd)
                        self.result_queue.put(result)
                    except queue.Empty:
                        pass
                    
                    # Periodic balance update
                    self._update_balance()
                    self.state.last_activity = datetime.now(timezone.utc)
                    
                except Exception as e:
                    logger.error(f"Error in bot loop: {e}")
                    self.state.last_error = str(e)
                    
        except Exception as e:
            logger.error(f"Fatal bot error: {e}")
            self.state.last_error = str(e)
        finally:
            self._cleanup()
            self._running = False
            self.state.is_running = False
    
    def _init_browser(self):
        """Initialize Selenium browser"""
        logger.info("🌐 Initializing browser...")
        
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # Essential options for running in container
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--remote-debugging-port=9222")
        
        # Set binary location to chromium
        options.binary_location = "/usr/bin/chromium"
        
        # Anti-detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # User agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Create driver with explicit chromedriver path
        service = Service(executable_path="/usr/bin/chromedriver")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Set timeouts
        self.driver.set_page_load_timeout(60)
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 30)
        
        # Anti-detection script
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """
        })
        
        logger.info("✅ Browser initialized")
    
    def _login(self) -> bool:
        """Login to Pocket Option"""
        logger.info("🔐 Logging into Pocket Option...")
        
        try:
            # Try different domains
            for base_url in PO_DOMAINS:
                try:
                    login_url = f"{base_url}/en/login/"
                    logger.info(f"Trying: {login_url}")
                    self.driver.get(login_url)
                    time.sleep(3)
                    
                    # Check if page loaded
                    if "login" in self.driver.current_url.lower() or "pocketoption" in self.driver.current_url.lower():
                        break
                except Exception as e:
                    logger.warning(f"Failed to load {base_url}: {e}")
                    continue
            
            # Accept cookies if present
            try:
                cookie_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'OK') or contains(text(), 'agree')]")
                if cookie_btns:
                    cookie_btns[0].click()
                    time.sleep(1)
            except:
                pass
            
            # Find email input
            email_selectors = [
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='email']"),
                (By.CSS_SELECTOR, "input[autocomplete='email']"),
                (By.XPATH, "//input[@placeholder[contains(., 'mail')]]"),
            ]
            
            email_input = None
            for by, selector in email_selectors:
                try:
                    email_input = self.wait.until(EC.presence_of_element_located((by, selector)))
                    if email_input.is_displayed():
                        break
                except:
                    continue
            
            if not email_input:
                logger.error("Could not find email input")
                return False
            
            # Find password input
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            # Fill form
            email_input.clear()
            email_input.send_keys(self.email)
            time.sleep(0.5)
            
            password_input.clear()
            password_input.send_keys(self.password)
            time.sleep(0.5)
            
            # Click login button
            login_selectors = [
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Log in') or contains(text(), 'Login') or contains(text(), 'Sign in')]"),
                (By.CSS_SELECTOR, ".btn-login"),
            ]
            
            for by, selector in login_selectors:
                try:
                    btn = self.driver.find_element(by, selector)
                    if btn.is_displayed():
                        btn.click()
                        break
                except:
                    continue
            
            # Wait for login to complete
            time.sleep(8)
            
            # Check if login was successful
            current_url = self.driver.current_url.lower()
            if "cabinet" in current_url or "trade" in current_url or "login" not in current_url:
                self.state.is_logged_in = True
                logger.info("✅ Login successful!")
                return True
            else:
                logger.error("Login failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def _navigate_to_trading(self) -> bool:
        """Navigate to trading page"""
        try:
            target_url = PO_DEMO_URL if self.demo else PO_LIVE_URL
            logger.info(f"📊 Navigating to {'demo' if self.demo else 'real'} trading page...")
            
            self.driver.get(target_url)
            time.sleep(5)
            
            # Wait for trading interface to load
            trading_selectors = [
                ".chart-container",
                "[class*='trading']",
                "[class*='chart']",
                ".deal-container"
            ]
            
            for selector in trading_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue
            
            self.state.is_on_trading_page = True
            self._update_balance()
            
            logger.info(f"✅ On trading page. Balance: ${self.state.balance:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False
    
    def _update_balance(self):
        """Update balance from page"""
        try:
            balance_selectors = [
                "[class*='balance']",
                ".user-balance",
                ".header-balance",
                "[data-balance]"
            ]
            
            for selector in balance_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        text = el.text
                        if text:
                            match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                            if match:
                                self.state.balance = float(match.group())
                                return
                except:
                    continue
        except:
            pass
    
    def _process_command(self, cmd: Dict) -> Dict:
        """Process a trade command"""
        action = cmd.get('action')
        
        if action == 'trade':
            return self._execute_trade(
                direction=cmd.get('direction', 'call'),
                amount=cmd.get('amount', 1),
                asset=cmd.get('asset', 'EURUSD_otc'),
                duration=cmd.get('duration', 60)
            )
        elif action == 'balance':
            self._update_balance()
            return {"success": True, "balance": self.state.balance}
        elif action == 'status':
            return {"success": True, "state": self._get_state_dict()}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    def _execute_trade(
        self,
        direction: str,
        amount: float,
        asset: str,
        duration: int
    ) -> Dict:
        """Execute a trade"""
        try:
            logger.info(f"🎯 Executing: {direction.upper()} ${amount} on {asset}")
            
            # Set amount
            self._set_amount(amount)
            time.sleep(0.3)
            
            # Click trade button
            success = self._click_trade_button(direction)
            
            if success:
                self.state.total_trades += 1
                order_id = f"SEL_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                logger.info(f"✅ Trade executed! Order: {order_id}")
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "direction": direction,
                    "amount": amount,
                    "asset": asset,
                    "duration": duration,
                    "execution_time": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {"success": False, "error": "Could not find trade button"}
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def _set_amount(self, amount: float):
        """Set trade amount"""
        try:
            amount_selectors = [
                "input[class*='amount']",
                "input[name='amount']",
                ".amount-input input",
                "input[type='number']"
            ]
            
            for selector in amount_selectors:
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for inp in inputs:
                        if inp.is_displayed():
                            inp.clear()
                            inp.send_keys(str(int(amount)))
                            logger.debug(f"Set amount to ${amount}")
                            return True
                except:
                    continue
        except:
            pass
        return False
    
    def _click_trade_button(self, direction: str) -> bool:
        """Click CALL or PUT button"""
        try:
            is_call = direction.lower() in ['call', 'up', 'higher', 'buy']
            
            if is_call:
                selectors = [
                    (By.CSS_SELECTOR, "button[class*='call']"),
                    (By.CSS_SELECTOR, "button[class*='higher']"),
                    (By.CSS_SELECTOR, "button[class*='green']"),
                    (By.CSS_SELECTOR, ".btn-call"),
                    (By.XPATH, "//button[contains(text(), 'Higher') or contains(text(), 'CALL') or contains(text(), 'Call')]"),
                ]
            else:
                selectors = [
                    (By.CSS_SELECTOR, "button[class*='put']"),
                    (By.CSS_SELECTOR, "button[class*='lower']"),
                    (By.CSS_SELECTOR, "button[class*='red']"),
                    (By.CSS_SELECTOR, ".btn-put"),
                    (By.XPATH, "//button[contains(text(), 'Lower') or contains(text(), 'PUT') or contains(text(), 'Put')]"),
                ]
            
            for by, selector in selectors:
                try:
                    buttons = self.driver.find_elements(by, selector)
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            logger.info(f"✅ Clicked {direction.upper()} button")
                            return True
                except:
                    continue
            
            # Fallback: Try to find by visual inspection
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in all_buttons:
                try:
                    classes = btn.get_attribute("class") or ""
                    text = btn.text.lower()
                    
                    if is_call:
                        if any(x in classes.lower() for x in ['call', 'higher', 'green', 'up']):
                            btn.click()
                            return True
                        if any(x in text for x in ['call', 'higher', 'up']):
                            btn.click()
                            return True
                    else:
                        if any(x in classes.lower() for x in ['put', 'lower', 'red', 'down']):
                            btn.click()
                            return True
                        if any(x in text for x in ['put', 'lower', 'down']):
                            btn.click()
                            return True
                except:
                    continue
            
            logger.error(f"Could not find {direction} button")
            return False
            
        except Exception as e:
            logger.error(f"Click button error: {e}")
            return False
    
    def execute_trade(
        self,
        direction: str,
        amount: float = 1.0,
        asset: str = "EURUSD_otc",
        duration: int = 60
    ) -> Dict:
        """
        Queue a trade for execution (thread-safe)
        
        Args:
            direction: 'call' or 'put'
            amount: Trade amount
            asset: Asset symbol
            duration: Trade duration in seconds
        
        Returns:
            Trade execution result
        """
        if not self._running or not self.state.is_running:
            return {"success": False, "error": "Bot not running"}
        
        # Queue the command
        cmd = {
            "action": "trade",
            "direction": direction,
            "amount": amount,
            "asset": asset,
            "duration": duration
        }
        
        self.command_queue.put(cmd)
        
        # Wait for result
        try:
            result = self.result_queue.get(timeout=30)
            return result
        except queue.Empty:
            return {"success": False, "error": "Trade execution timeout"}
    
    def get_balance(self) -> Dict:
        """Get current balance"""
        if not self._running:
            return {"success": False, "error": "Bot not running"}
        
        self.command_queue.put({"action": "balance"})
        
        try:
            result = self.result_queue.get(timeout=10)
            return result
        except queue.Empty:
            return {"success": True, "balance": self.state.balance}
    
    def get_status(self) -> Dict:
        """Get bot status"""
        return {
            "success": True,
            "state": self._get_state_dict()
        }
    
    def _get_state_dict(self) -> Dict:
        """Get state as dictionary"""
        return {
            "is_running": self.state.is_running,
            "is_logged_in": self.state.is_logged_in,
            "is_on_trading_page": self.state.is_on_trading_page,
            "balance": self.state.balance,
            "is_demo": self.state.is_demo,
            "total_trades": self.state.total_trades,
            "wins": self.state.wins,
            "losses": self.state.losses,
            "last_error": self.state.last_error,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None
        }
    
    def stop(self) -> Dict:
        """Stop the bot"""
        logger.info("🛑 Stopping bot...")
        self._running = False
        
        if self._bot_thread:
            self._bot_thread.join(timeout=10)
        
        return {"success": True, "message": "Bot stopped"}
    
    def _cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except:
            pass
        
        logger.info("✅ Bot cleanup complete")


# Global bot instance
_selenium_bot: Optional[SeleniumTradingBot] = None


def get_selenium_bot(
    email: str = None,
    password: str = None,
    demo: bool = True,
    headless: bool = True
) -> SeleniumTradingBot:
    """Get or create Selenium bot instance"""
    global _selenium_bot
    
    if _selenium_bot is None:
        if not email or not password:
            # Default credentials
            email = os.environ.get('PO_EMAIL', 'thomas.riddick84@gmail.com')
            password = os.environ.get('PO_PASSWORD', 'Tonyistheman#1')
        
        _selenium_bot = SeleniumTradingBot(
            email=email,
            password=password,
            demo=demo,
            headless=headless
        )
    
    return _selenium_bot


def stop_selenium_bot():
    """Stop and clear bot instance"""
    global _selenium_bot
    
    if _selenium_bot:
        _selenium_bot.stop()
        _selenium_bot = None
