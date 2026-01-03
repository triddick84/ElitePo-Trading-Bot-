"""
Pocket Option Automated Login Service (v2)
==========================================

Multi-layered approach to bypass CAPTCHA and maintain persistent sessions:

1. STEALTH BROWSER (Primary) - Uses undetected-chromedriver with anti-detection
2. CAPTCHA SOLVER (Fallback) - Uses 2Captcha service based on official documentation
3. SESSION PERSISTENCE - Monitors and auto-refreshes sessions

Based on research from:
- https://2captcha.com/blog/captcha-bypass-in-selenium
- https://www.zenrows.com/blog/avoid-captcha

Author: GPT Signal Bot
"""

import os
import asyncio
import logging
import json
import time
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for running sync selenium code
_executor = ThreadPoolExecutor(max_workers=2)


class LoginMethod(str, Enum):
    STEALTH_BROWSER = "stealth_browser"
    CAPTCHA_SOLVER = "captcha_solver"
    MANUAL_SSID = "manual_ssid"


class LoginStatus(str, Enum):
    SUCCESS = "success"
    CAPTCHA_DETECTED = "captcha_detected"
    CAPTCHA_SOLVED = "captcha_solved"
    CAPTCHA_FAILED = "captcha_failed"
    LOGIN_FAILED = "login_failed"
    NETWORK_ERROR = "network_error"
    INVALID_CREDENTIALS = "invalid_credentials"


@dataclass
class LoginResult:
    """Result of login attempt"""
    success: bool
    status: LoginStatus
    ssid: Optional[str] = None
    method_used: Optional[LoginMethod] = None
    account_type: str = "demo"
    balance: float = 0.0
    user_id: Optional[str] = None
    error: Optional[str] = None
    captcha_cost: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "status": self.status.value,
            "ssid": self.ssid[:50] + "..." if self.ssid and len(self.ssid) > 50 else self.ssid,
            "method_used": self.method_used.value if self.method_used else None,
            "account_type": self.account_type,
            "balance": self.balance,
            "user_id": self.user_id,
            "error": self.error,
            "captcha_cost": self.captcha_cost,
            "timestamp": self.timestamp.isoformat()
        }


class PocketOptionLoginHandler:
    """
    Handles Pocket Option login with CAPTCHA bypass
    Uses Selenium + 2Captcha based on official documentation
    """
    
    POCKET_OPTION_LOGIN_URL = "https://pocketoption.com/en/login"
    POCKET_OPTION_TRADE_URL = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
    
    # Known reCAPTCHA site key for Pocket Option (may need updating)
    RECAPTCHA_SITE_KEY = "6LfBixYTAAAAABHq2gGpAQFPbHCoVbgJd45i3qUa"
    
    def __init__(self, captcha_api_key: Optional[str] = None):
        """
        Initialize login handler
        
        Args:
            captcha_api_key: 2Captcha API key for CAPTCHA solving
        """
        self.captcha_api_key = captcha_api_key or os.environ.get("TWOCAPTCHA_API_KEY")
        self.solver = None
        
        if self.captcha_api_key:
            try:
                from twocaptcha import TwoCaptcha
                self.solver = TwoCaptcha(self.captcha_api_key)
                logger.info("✅ 2Captcha solver initialized")
            except ImportError:
                logger.warning("⚠️ 2captcha-python not installed, CAPTCHA solving disabled")
    
    def _get_random_user_agent(self) -> str:
        """Get random realistic user agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]
        return random.choice(user_agents)
    
    def _sync_login_with_captcha_solver(self, email: str, password: str) -> LoginResult:
        """
        Synchronous login using Selenium + 2Captcha
        Based on: https://2captcha.com/blog/captcha-bypass-in-selenium
        """
        driver = None
        captcha_cost = 0.0
        
        try:
            # Import selenium components
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.chrome.options import Options
            
            logger.info("🔐 Starting Selenium login with 2Captcha...")
            
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument(f"--user-agent={self._get_random_user_agent()}")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Try undetected-chromedriver first
            try:
                import undetected_chromedriver as uc
                driver = uc.Chrome(options=chrome_options, use_subprocess=True)
                logger.info("✅ Using undetected-chromedriver")
            except Exception as e:
                logger.warning(f"undetected-chromedriver failed: {e}, using regular Selenium")
                from webdriver_manager.chrome import ChromeDriverManager
                driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=chrome_options
                )
            
            # Navigate to login page
            logger.info(f"📍 Navigating to {self.POCKET_OPTION_LOGIN_URL}")
            driver.get(self.POCKET_OPTION_LOGIN_URL)
            time.sleep(random.uniform(2, 4))
            
            wait = WebDriverWait(driver, 20)
            
            # Fill email field with human-like typing
            logger.info("📝 Filling login form...")
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[placeholder*='mail']")
            ))
            email_field.clear()
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.12))
            
            time.sleep(random.uniform(0.5, 1))
            
            # Fill password field
            password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.clear()
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.12))
            
            time.sleep(random.uniform(0.5, 1))
            
            # Check for reCAPTCHA and solve if present
            captcha_solved = False
            site_key = self._find_recaptcha_site_key(driver)
            
            if site_key and self.solver:
                logger.info(f"🧩 reCAPTCHA detected! Site key: {site_key[:20]}...")
                logger.info("🔄 Sending to 2Captcha for solving...")
                
                try:
                    # Solve using 2Captcha API (as per official documentation)
                    response = self.solver.recaptcha(
                        sitekey=site_key,
                        url=self.POCKET_OPTION_LOGIN_URL
                    )
                    captcha_code = response['code']
                    captcha_cost = 0.00299  # Approximate cost per reCAPTCHA solve
                    
                    logger.info(f"✅ CAPTCHA solved! Code: {captcha_code[:30]}...")
                    
                    # Inject the solved CAPTCHA response
                    # Method 1: Set g-recaptcha-response element
                    driver.execute_script(f'''
                        var element = document.getElementById('g-recaptcha-response');
                        if (element) {{
                            element.style.display = 'block';
                            element.value = "{captcha_code}";
                        }}
                        
                        // Also try textarea variant
                        var textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
                        textareas.forEach(function(ta) {{
                            ta.style.display = 'block';
                            ta.value = "{captcha_code}";
                        }});
                    ''')
                    
                    # Method 2: Call the callback function if available
                    driver.execute_script(f'''
                        if (typeof ___grecaptcha_cfg !== 'undefined') {{
                            try {{
                                Object.entries(___grecaptcha_cfg.clients).forEach(function(entry) {{
                                    var client = entry[1];
                                    if (client && client.Z && client.Z.Z && client.Z.Z.callback) {{
                                        client.Z.Z.callback("{captcha_code}");
                                    }}
                                }});
                            }} catch(e) {{ console.log('Callback error:', e); }}
                        }}
                        
                        // Alternative callback methods
                        if (typeof grecaptcha !== 'undefined' && grecaptcha.enterprise) {{
                            try {{
                                grecaptcha.enterprise.execute();
                            }} catch(e) {{}}
                        }}
                    ''')
                    
                    captcha_solved = True
                    logger.info("✅ CAPTCHA response injected")
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ CAPTCHA solving failed: {e}")
                    return LoginResult(
                        success=False,
                        status=LoginStatus.CAPTCHA_FAILED,
                        method_used=LoginMethod.CAPTCHA_SOLVER,
                        error=f"CAPTCHA solving failed: {e}",
                        captcha_cost=captcha_cost
                    )
            
            # Click login button
            logger.info("🖱️ Clicking login button...")
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, 
                    "button[type='submit'], .btn-login, button.login-btn, input[type='submit']"
                )
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", login_button)
                time.sleep(0.5)
                login_button.click()
            except:
                # Try form submit as fallback
                driver.execute_script("document.querySelector('form').submit();")
            
            logger.info("🔄 Waiting for login response...")
            time.sleep(random.uniform(4, 6))
            
            # Check if login was successful
            current_url = driver.current_url
            logger.info(f"📍 Current URL: {current_url}")
            
            if "cabinet" in current_url or "trade" in current_url or "quick-high-low" in current_url:
                logger.info("✅ Login successful! Extracting SSID...")
                
                # Navigate to trading page to get WebSocket auth
                if "quick-high-low" not in current_url:
                    driver.get(self.POCKET_OPTION_TRADE_URL)
                    time.sleep(3)
                
                # Extract SSID from WebSocket messages or cookies
                ssid = self._extract_ssid(driver)
                
                if ssid:
                    logger.info(f"✅ SSID extracted: {ssid[:50]}...")
                    return LoginResult(
                        success=True,
                        status=LoginStatus.CAPTCHA_SOLVED if captcha_solved else LoginStatus.SUCCESS,
                        ssid=ssid,
                        method_used=LoginMethod.CAPTCHA_SOLVER if captcha_solved else LoginMethod.STEALTH_BROWSER,
                        captcha_cost=captcha_cost
                    )
                else:
                    return LoginResult(
                        success=False,
                        status=LoginStatus.LOGIN_FAILED,
                        method_used=LoginMethod.CAPTCHA_SOLVER,
                        error="Login succeeded but could not extract SSID",
                        captcha_cost=captcha_cost
                    )
            else:
                # Check for error messages
                error_msg = self._get_error_message(driver)
                return LoginResult(
                    success=False,
                    status=LoginStatus.LOGIN_FAILED,
                    method_used=LoginMethod.CAPTCHA_SOLVER if self.solver else LoginMethod.STEALTH_BROWSER,
                    error=error_msg or f"Login failed. Current URL: {current_url}",
                    captcha_cost=captcha_cost
                )
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            import traceback
            traceback.print_exc()
            return LoginResult(
                success=False,
                status=LoginStatus.NETWORK_ERROR,
                method_used=LoginMethod.CAPTCHA_SOLVER,
                error=str(e),
                captcha_cost=captcha_cost
            )
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _find_recaptcha_site_key(self, driver) -> Optional[str]:
        """Find reCAPTCHA site key on the page"""
        try:
            # Method 1: From data-sitekey attribute
            elements = driver.find_elements("css selector", "[data-sitekey]")
            for elem in elements:
                key = elem.get_attribute("data-sitekey")
                if key:
                    return key
            
            # Method 2: From g-recaptcha div
            elements = driver.find_elements("css selector", ".g-recaptcha")
            for elem in elements:
                key = elem.get_attribute("data-sitekey")
                if key:
                    return key
            
            # Method 3: From iframe src
            iframes = driver.find_elements("css selector", "iframe[src*='recaptcha']")
            for iframe in iframes:
                src = iframe.get_attribute("src")
                if src and "k=" in src:
                    return src.split("k=")[1].split("&")[0]
            
            # Method 4: Search page source
            page_source = driver.page_source
            import re
            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_source)
            if match:
                return match.group(1)
            
            match = re.search(r'sitekey["\s:]+["\']([^"\']+)["\']', page_source)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding site key: {e}")
            return None
    
    def _extract_ssid(self, driver) -> Optional[str]:
        """Extract SSID from browser session"""
        try:
            # Inject WebSocket interceptor
            driver.execute_script('''
                window.__capturedAuth = null;
                
                // Intercept WebSocket
                const originalWebSocket = window.WebSocket;
                window.WebSocket = function(url, protocols) {
                    const ws = new originalWebSocket(url, protocols);
                    const originalSend = ws.send.bind(ws);
                    ws.send = function(data) {
                        if (data && data.includes && data.includes('"auth"')) {
                            window.__capturedAuth = data;
                            console.log('Captured auth:', data);
                        }
                        return originalSend(data);
                    };
                    return ws;
                };
            ''')
            
            # Wait for WebSocket connection
            time.sleep(5)
            
            # Try to get captured auth message
            auth_msg = driver.execute_script("return window.__capturedAuth;")
            if auth_msg and '"auth"' in str(auth_msg):
                return str(auth_msg)
            
            # Fallback: Get from cookies
            cookies = driver.get_cookies()
            for cookie in cookies:
                name = cookie.get('name', '').lower()
                if 'ssid' in name or 'session' in name:
                    value = cookie.get('value', '')
                    if value:
                        return value
            
            # Fallback: Get from localStorage/sessionStorage
            for storage in ['localStorage', 'sessionStorage']:
                items = driver.execute_script(f'''
                    var items = {{}};
                    for (var i = 0; i < {storage}.length; i++) {{
                        var key = {storage}.key(i);
                        items[key] = {storage}.getItem(key);
                    }}
                    return items;
                ''')
                for key, value in (items or {}).items():
                    if 'auth' in key.lower() or 'ssid' in key.lower() or 'session' in key.lower():
                        if value:
                            return value
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting SSID: {e}")
            return None
    
    def _get_error_message(self, driver) -> Optional[str]:
        """Get error message from page"""
        try:
            selectors = [
                ".error-message", ".alert-danger", ".login-error",
                "[class*='error']", ".notification-error", ".toast-error"
            ]
            for selector in selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text:
                            return text
                except:
                    continue
            return None
        except:
            return None
    
    async def login(self, email: str, password: str) -> LoginResult:
        """
        Async wrapper for login
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self._sync_login_with_captcha_solver,
            email,
            password
        )


class AutoLoginService:
    """
    Main service that orchestrates login attempts
    """
    
    def __init__(self, captcha_api_key: Optional[str] = None):
        """
        Initialize auto login service
        
        Args:
            captcha_api_key: 2Captcha API key (uses env var if not provided)
        """
        self.captcha_api_key = captcha_api_key or os.environ.get("TWOCAPTCHA_API_KEY")
        self.handler = PocketOptionLoginHandler(self.captcha_api_key)
        
        self._login_attempts: list = []
        self._last_successful_ssid: Optional[str] = None
        self._last_login_time: Optional[datetime] = None
        
        if self.captcha_api_key:
            logger.info(f"✅ AutoLoginService initialized with 2Captcha API key: {self.captcha_api_key[:8]}...")
        else:
            logger.warning("⚠️ No 2Captcha API key - CAPTCHA solving disabled")
    
    async def auto_login(self, email: str, password: str) -> LoginResult:
        """
        Attempt automated login
        """
        logger.info("🚀 Starting automated login process...")
        
        result = await self.handler.login(email, password)
        
        if result.success:
            self._last_successful_ssid = result.ssid
            self._last_login_time = datetime.now(timezone.utc)
        
        self._login_attempts.append(result)
        return result
    
    def get_login_stats(self) -> Dict[str, Any]:
        """Get statistics about login attempts"""
        total_attempts = len(self._login_attempts)
        successful = sum(1 for r in self._login_attempts if r.success)
        total_captcha_cost = sum(r.captcha_cost for r in self._login_attempts)
        
        return {
            "total_attempts": total_attempts,
            "successful": successful,
            "success_rate": (successful / total_attempts * 100) if total_attempts > 0 else 0,
            "total_captcha_cost": round(total_captcha_cost, 4),
            "last_login_time": self._last_login_time.isoformat() if self._last_login_time else None,
            "has_valid_ssid": self._last_successful_ssid is not None,
            "captcha_solver_enabled": self.captcha_api_key is not None,
            "api_key_preview": f"{self.captcha_api_key[:8]}..." if self.captcha_api_key else None
        }
    
    def get_last_ssid(self) -> Optional[str]:
        """Get the last successfully obtained SSID"""
        return self._last_successful_ssid


# Global service instance
_auto_login_service: Optional[AutoLoginService] = None


def get_auto_login_service(captcha_api_key: Optional[str] = None) -> AutoLoginService:
    """Get or create auto login service"""
    global _auto_login_service
    if _auto_login_service is None or captcha_api_key:
        _auto_login_service = AutoLoginService(captcha_api_key)
    return _auto_login_service
