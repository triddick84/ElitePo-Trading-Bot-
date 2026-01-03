"""
Pocket Option Automated Login Service
=====================================

Multi-layered approach to bypass CAPTCHA and maintain persistent sessions:

1. STEALTH BROWSER (Primary) - Uses undetected-chromedriver with anti-detection
2. CAPTCHA SOLVER (Fallback) - Uses 2Captcha/Anti-Captcha services
3. SESSION PERSISTENCE - Monitors and auto-refreshes sessions

Author: GPT Signal Bot
"""

import os
import asyncio
import logging
import json
import time
import random
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


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
    account_type: str = "demo"  # "demo" or "real"
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


class StealthBrowserLogin:
    """
    Stealth browser login using undetected-chromedriver
    with anti-detection techniques to bypass reCAPTCHA
    """
    
    POCKET_OPTION_LOGIN_URL = "https://pocketoption.com/en/login"
    POCKET_OPTION_DEMO_URL = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
    
    def __init__(self):
        self.driver = None
        self._setup_complete = False
    
    def _get_stealth_options(self) -> Dict[str, Any]:
        """Get Chrome options for stealth mode"""
        options = {
            "headless": True,
            "disable_gpu": True,
            "no_sandbox": True,
            "disable_dev_shm_usage": True,
            "window_size": "1920,1080",
            "user_agent": self._get_random_user_agent(),
        }
        return options
    
    def _get_random_user_agent(self) -> str:
        """Get random realistic user agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        return random.choice(user_agents)
    
    async def login(self, email: str, password: str) -> LoginResult:
        """
        Attempt login using stealth browser with anti-detection
        """
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.action_chains import ActionChains
            
            logger.info("🔐 Starting stealth browser login...")
            
            # Configure undetected chromedriver
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument(f"--user-agent={self._get_random_user_agent()}")
            options.add_argument("--window-size=1920,1080")
            
            # Use undetected chromedriver
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            
            # Navigate to login page
            logger.info("📍 Navigating to Pocket Option login page...")
            self.driver.get(self.POCKET_OPTION_LOGIN_URL)
            
            # Random delay to mimic human behavior
            await asyncio.sleep(random.uniform(2, 4))
            
            # Wait for page load
            wait = WebDriverWait(self.driver, 20)
            
            # Check for CAPTCHA
            captcha_detected = self._check_for_captcha()
            if captcha_detected:
                logger.warning("⚠️ CAPTCHA detected on page load")
                return LoginResult(
                    success=False,
                    status=LoginStatus.CAPTCHA_DETECTED,
                    method_used=LoginMethod.STEALTH_BROWSER,
                    error="CAPTCHA detected - stealth browser could not bypass"
                )
            
            # Find and fill email field with human-like typing
            logger.info("📝 Filling login form...")
            email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']")))
            await self._human_type(email_field, email)
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Find and fill password field
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
            await self._human_type(password_field, password)
            
            await asyncio.sleep(random.uniform(0.5, 1))
            
            # Move mouse randomly before clicking
            actions = ActionChains(self.driver)
            actions.move_by_offset(random.randint(-100, 100), random.randint(-50, 50))
            actions.perform()
            
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            # Find and click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn-login, .login-btn")
            
            # Scroll to button if needed
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", login_button)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            login_button.click()
            
            logger.info("🔄 Waiting for login response...")
            await asyncio.sleep(random.uniform(3, 5))
            
            # Check for CAPTCHA after login attempt
            if self._check_for_captcha():
                logger.warning("⚠️ CAPTCHA appeared after login attempt")
                return LoginResult(
                    success=False,
                    status=LoginStatus.CAPTCHA_DETECTED,
                    method_used=LoginMethod.STEALTH_BROWSER,
                    error="CAPTCHA triggered during login - need CAPTCHA solver"
                )
            
            # Check if login was successful by looking for dashboard elements or cookies
            await asyncio.sleep(2)
            current_url = self.driver.current_url
            
            if "cabinet" in current_url or "trade" in current_url:
                logger.info("✅ Login successful! Extracting SSID...")
                ssid = await self._extract_ssid()
                
                if ssid:
                    return LoginResult(
                        success=True,
                        status=LoginStatus.SUCCESS,
                        ssid=ssid,
                        method_used=LoginMethod.STEALTH_BROWSER,
                        account_type="demo"
                    )
                else:
                    return LoginResult(
                        success=False,
                        status=LoginStatus.LOGIN_FAILED,
                        method_used=LoginMethod.STEALTH_BROWSER,
                        error="Login seemed successful but could not extract SSID"
                    )
            else:
                # Check for error messages
                error_msg = self._get_error_message()
                return LoginResult(
                    success=False,
                    status=LoginStatus.LOGIN_FAILED,
                    method_used=LoginMethod.STEALTH_BROWSER,
                    error=error_msg or "Login failed - unknown error"
                )
                
        except Exception as e:
            logger.error(f"❌ Stealth browser login error: {e}")
            return LoginResult(
                success=False,
                status=LoginStatus.NETWORK_ERROR,
                method_used=LoginMethod.STEALTH_BROWSER,
                error=str(e)
            )
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
    
    def _check_for_captcha(self) -> bool:
        """Check if CAPTCHA is present on page"""
        try:
            captcha_indicators = [
                "g-recaptcha",
                "grecaptcha",
                "recaptcha",
                "captcha-container",
                "cf-turnstile"
            ]
            
            page_source = self.driver.page_source.lower()
            
            for indicator in captcha_indicators:
                if indicator in page_source:
                    return True
            
            # Also check for CAPTCHA iframe
            try:
                self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
                return True
            except:
                pass
            
            return False
        except:
            return False
    
    async def _human_type(self, element, text: str):
        """Type text with human-like delays"""
        for char in text:
            element.send_keys(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    
    async def _extract_ssid(self) -> Optional[str]:
        """Extract SSID from browser session"""
        try:
            # Get all cookies
            cookies = self.driver.get_cookies()
            
            # Look for session-related cookies
            for cookie in cookies:
                if 'ssid' in cookie['name'].lower() or 'session' in cookie['name'].lower():
                    return cookie['value']
            
            # Try to get from local storage
            ssid = self.driver.execute_script("return localStorage.getItem('ssid') || sessionStorage.getItem('ssid');")
            if ssid:
                return ssid
            
            # Try to intercept WebSocket auth message
            # This requires monitoring network traffic
            ws_messages = self.driver.execute_script("""
                return window.__wsMessages || [];
            """)
            
            for msg in ws_messages:
                if '"auth"' in str(msg):
                    return str(msg)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting SSID: {e}")
            return None
    
    def _get_error_message(self) -> Optional[str]:
        """Get any error message displayed on page"""
        try:
            error_selectors = [
                ".error-message",
                ".alert-danger",
                ".login-error",
                "[class*='error']"
            ]
            
            for selector in error_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        return element.text
                except:
                    continue
            
            return None
        except:
            return None


class CaptchaSolverLogin:
    """
    Login using CAPTCHA solving services (2Captcha/Anti-Captcha)
    as fallback when stealth browser fails
    """
    
    POCKET_OPTION_LOGIN_URL = "https://pocketoption.com/en/login"
    RECAPTCHA_SITE_KEY = "6LfBixYTAAAAABHq2gGpAQFPbHCoVbgJd45i3qUa"  # Pocket Option's reCAPTCHA key
    
    def __init__(self, api_key: str, service: str = "2captcha"):
        """
        Initialize CAPTCHA solver
        
        Args:
            api_key: API key for the CAPTCHA solving service
            service: "2captcha" or "anticaptcha"
        """
        self.api_key = api_key
        self.service = service
        self.solver = None
        
        if service == "2captcha":
            from twocaptcha import TwoCaptcha
            self.solver = TwoCaptcha(api_key)
        else:
            # Anti-Captcha integration would go here
            pass
    
    async def login(self, email: str, password: str) -> LoginResult:
        """
        Login using CAPTCHA solver service
        """
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            logger.info("🔐 Starting CAPTCHA solver login...")
            
            # Setup browser
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            driver = uc.Chrome(options=options, use_subprocess=True)
            
            try:
                # Navigate to login page
                driver.get(self.POCKET_OPTION_LOGIN_URL)
                await asyncio.sleep(3)
                
                wait = WebDriverWait(driver, 20)
                
                # Fill email
                email_field = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[type='email'], input[name='email']")
                ))
                email_field.clear()
                email_field.send_keys(email)
                
                await asyncio.sleep(0.5)
                
                # Fill password
                password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                password_field.clear()
                password_field.send_keys(password)
                
                # Solve CAPTCHA
                logger.info("🧩 Solving CAPTCHA via 2Captcha...")
                captcha_cost = 0.0
                
                try:
                    # Find reCAPTCHA site key on page
                    site_key = self._find_recaptcha_site_key(driver)
                    
                    if not site_key:
                        site_key = self.RECAPTCHA_SITE_KEY  # Fallback to known key
                    
                    # Solve reCAPTCHA using 2Captcha
                    result = self.solver.recaptcha(
                        sitekey=site_key,
                        url=self.POCKET_OPTION_LOGIN_URL
                    )
                    
                    captcha_token = result['code']
                    captcha_cost = 0.00299  # Approximate cost per solve
                    
                    logger.info("✅ CAPTCHA solved successfully!")
                    
                    # Inject CAPTCHA response
                    driver.execute_script(f"""
                        document.getElementById('g-recaptcha-response').innerHTML = '{captcha_token}';
                        if (typeof ___grecaptcha_cfg !== 'undefined') {{
                            Object.entries(___grecaptcha_cfg.clients).forEach(([key, client]) => {{
                                if (client && client.Z && client.Z.Z) {{
                                    client.Z.Z.callback('{captcha_token}');
                                }}
                            }});
                        }}
                    """)
                    
                except Exception as e:
                    logger.error(f"CAPTCHA solving failed: {e}")
                    return LoginResult(
                        success=False,
                        status=LoginStatus.CAPTCHA_FAILED,
                        method_used=LoginMethod.CAPTCHA_SOLVER,
                        error=f"CAPTCHA solving failed: {e}",
                        captcha_cost=captcha_cost
                    )
                
                # Click login button
                await asyncio.sleep(1)
                login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
                await asyncio.sleep(5)
                
                # Check if login successful
                current_url = driver.current_url
                
                if "cabinet" in current_url or "trade" in current_url:
                    logger.info("✅ Login successful with CAPTCHA solver!")
                    
                    # Extract SSID from WebSocket
                    ssid = await self._extract_ssid_from_websocket(driver)
                    
                    return LoginResult(
                        success=True,
                        status=LoginStatus.CAPTCHA_SOLVED,
                        ssid=ssid,
                        method_used=LoginMethod.CAPTCHA_SOLVER,
                        captcha_cost=captcha_cost
                    )
                else:
                    return LoginResult(
                        success=False,
                        status=LoginStatus.LOGIN_FAILED,
                        method_used=LoginMethod.CAPTCHA_SOLVER,
                        error="Login failed after CAPTCHA solve",
                        captcha_cost=captcha_cost
                    )
                    
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"❌ CAPTCHA solver login error: {e}")
            return LoginResult(
                success=False,
                status=LoginStatus.NETWORK_ERROR,
                method_used=LoginMethod.CAPTCHA_SOLVER,
                error=str(e)
            )
    
    def _find_recaptcha_site_key(self, driver) -> Optional[str]:
        """Find reCAPTCHA site key on page"""
        try:
            # Try to find from g-recaptcha element
            element = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha[data-sitekey]")
            return element.get_attribute("data-sitekey")
        except:
            pass
        
        try:
            # Try to find from iframe src
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
            src = iframe.get_attribute("src")
            if "k=" in src:
                return src.split("k=")[1].split("&")[0]
        except:
            pass
        
        return None
    
    async def _extract_ssid_from_websocket(self, driver) -> Optional[str]:
        """Extract SSID by monitoring WebSocket traffic"""
        try:
            # Navigate to trading page to trigger WebSocket connection
            driver.get("https://pocketoption.com/en/cabinet/demo-quick-high-low/")
            await asyncio.sleep(5)
            
            # Inject script to capture WebSocket messages
            driver.execute_script("""
                window.__capturedWsMessages = [];
                const originalSend = WebSocket.prototype.send;
                WebSocket.prototype.send = function(data) {
                    window.__capturedWsMessages.push(data);
                    return originalSend.apply(this, arguments);
                };
            """)
            
            await asyncio.sleep(3)
            
            # Get captured messages
            messages = driver.execute_script("return window.__capturedWsMessages || [];")
            
            for msg in messages:
                if '"auth"' in str(msg) and '"session"' in str(msg):
                    return str(msg)
            
            # Fallback: get from cookies/storage
            cookies = driver.get_cookies()
            for cookie in cookies:
                if 'session' in cookie['name'].lower():
                    return cookie['value']
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting SSID: {e}")
            return None


class AutoLoginService:
    """
    Main service that orchestrates login attempts across multiple methods
    """
    
    def __init__(self, captcha_api_key: Optional[str] = None):
        """
        Initialize auto login service
        
        Args:
            captcha_api_key: 2Captcha API key (optional, enables CAPTCHA solving)
        """
        self.captcha_api_key = captcha_api_key or os.environ.get("TWOCAPTCHA_API_KEY")
        self.stealth_login = StealthBrowserLogin()
        self.captcha_login = None
        
        if self.captcha_api_key:
            self.captcha_login = CaptchaSolverLogin(self.captcha_api_key)
            logger.info("✅ 2Captcha integration enabled")
        else:
            logger.warning("⚠️ No CAPTCHA API key - only stealth browser available")
        
        self._login_attempts = []
        self._last_successful_ssid = None
        self._last_login_time = None
    
    async def auto_login(self, email: str, password: str, 
                         use_stealth_first: bool = True) -> LoginResult:
        """
        Attempt automated login with fallback strategy
        
        Strategy:
        1. Try stealth browser first (free)
        2. If CAPTCHA detected, use CAPTCHA solver (paid)
        3. Return manual SSID instructions if all else fails
        """
        logger.info("🚀 Starting automated login process...")
        
        # Method 1: Stealth Browser
        if use_stealth_first:
            logger.info("📍 Attempting stealth browser login...")
            result = await self.stealth_login.login(email, password)
            
            if result.success:
                self._last_successful_ssid = result.ssid
                self._last_login_time = datetime.now(timezone.utc)
                self._login_attempts.append(result)
                return result
            
            logger.info(f"Stealth browser result: {result.status.value}")
            
            # If CAPTCHA detected and we have solver, try that
            if result.status == LoginStatus.CAPTCHA_DETECTED and self.captcha_login:
                logger.info("📍 CAPTCHA detected - falling back to CAPTCHA solver...")
                result = await self.captcha_login.login(email, password)
                
                if result.success:
                    self._last_successful_ssid = result.ssid
                    self._last_login_time = datetime.now(timezone.utc)
                
                self._login_attempts.append(result)
                return result
        
        # Method 2: Direct CAPTCHA Solver (if stealth skipped)
        elif self.captcha_login:
            logger.info("📍 Attempting CAPTCHA solver login...")
            result = await self.captcha_login.login(email, password)
            
            if result.success:
                self._last_successful_ssid = result.ssid
                self._last_login_time = datetime.now(timezone.utc)
            
            self._login_attempts.append(result)
            return result
        
        # Fallback: Manual SSID instructions
        return LoginResult(
            success=False,
            status=LoginStatus.CAPTCHA_FAILED,
            method_used=LoginMethod.MANUAL_SSID,
            error="Automated login failed. Please use manual SSID extraction."
        )
    
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
            "methods_available": {
                "stealth_browser": True,
                "captcha_solver": self.captcha_login is not None
            }
        }
    
    def get_last_ssid(self) -> Optional[str]:
        """Get the last successfully obtained SSID"""
        return self._last_successful_ssid


# Global service instance
_auto_login_service: Optional[AutoLoginService] = None


def get_auto_login_service(captcha_api_key: Optional[str] = None) -> AutoLoginService:
    """Get or create auto login service"""
    global _auto_login_service
    if _auto_login_service is None:
        _auto_login_service = AutoLoginService(captcha_api_key)
    return _auto_login_service


# Test function
async def test_login():
    """Test the auto login service"""
    service = get_auto_login_service()
    result = await service.auto_login(
        email="test@example.com",
        password="testpassword"
    )
    print(f"Login result: {result.to_dict()}")
    print(f"Stats: {service.get_login_stats()}")


if __name__ == "__main__":
    asyncio.run(test_login())
