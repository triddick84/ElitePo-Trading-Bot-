"""
Pocket Option Automated Login Service (v3 - Playwright)
========================================================

Uses Playwright for ARM64 compatibility with 2Captcha integration.

Based on research from:
- https://2captcha.com/blog/captcha-bypass-in-selenium
- https://www.zenrows.com/blog/avoid-captcha

Author: GPT Signal Bot
"""

import os
import asyncio
import logging
import json
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any
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


class PlaywrightLoginHandler:
    """
    Handles Pocket Option login using Playwright with 2Captcha
    Works on ARM64 architecture
    """
    
    POCKET_OPTION_LOGIN_URL = "https://pocketoption.com/en/login"
    POCKET_OPTION_TRADE_URL = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
    
    def __init__(self, captcha_api_key: Optional[str] = None):
        self.captcha_api_key = captcha_api_key or os.environ.get("TWOCAPTCHA_API_KEY")
        self.solver = None
        
        if self.captcha_api_key:
            try:
                from twocaptcha import TwoCaptcha
                self.solver = TwoCaptcha(self.captcha_api_key)
                logger.info("✅ 2Captcha solver initialized")
            except ImportError:
                logger.warning("⚠️ 2captcha-python not installed")
    
    def _get_random_user_agent(self) -> str:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)
    
    async def login(self, email: str, password: str) -> LoginResult:
        """
        Login using Playwright + 2Captcha
        """
        captcha_cost = 0.0
        browser = None
        
        try:
            from playwright.async_api import async_playwright
            
            # Set browser path
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'
            
            # Try to import stealth (different versions have different APIs)
            stealth_instance = None
            try:
                from playwright_stealth import Stealth
                stealth_instance = Stealth()
            except ImportError:
                pass
            
            logger.info("🔐 Starting Playwright login with 2Captcha...")
            
            async with async_playwright() as p:
                # Launch browser with explicit executable path
                browser = await p.chromium.launch(
                    headless=True,
                    executable_path='/pw-browsers/chromium-1200/chrome-linux/chrome',
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-gpu'
                    ]
                )
                
                # Create context with stealth settings
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent(),
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US'
                )
                
                page = await context.new_page()
                
                # Apply stealth if available
                if stealth_instance:
                    try:
                        await stealth_instance.apply_stealth_async(page)
                    except Exception as e:
                        logger.warning(f"Stealth application failed: {e}")
                
                # Intercept WebSocket to capture auth message
                captured_auth = []
                
                async def handle_websocket(ws):
                    async def on_message(msg):
                        if '"auth"' in str(msg):
                            captured_auth.append(str(msg))
                            logger.info(f"📨 Captured auth message!")
                    
                    ws.on("framereceived", lambda f: asyncio.create_task(on_message(f)))
                    ws.on("framesent", lambda f: asyncio.create_task(on_message(f)))
                
                page.on("websocket", handle_websocket)
                
                # Navigate to login page
                logger.info(f"📍 Navigating to {self.POCKET_OPTION_LOGIN_URL}")
                await page.goto(self.POCKET_OPTION_LOGIN_URL, wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(random.uniform(3, 5))
                
                # Fill email
                logger.info("📝 Filling login form...")
                email_field = await page.wait_for_selector(
                    "input[type='email'], input[name='email'], input[placeholder*='mail']",
                    timeout=10000
                )
                await email_field.click()
                for char in email:
                    await email_field.type(char, delay=random.randint(50, 100))
                
                await asyncio.sleep(random.uniform(0.5, 1))
                
                # Fill password
                password_field = await page.query_selector("input[type='password']")
                await password_field.click()
                for char in password:
                    await password_field.type(char, delay=random.randint(50, 100))
                
                await asyncio.sleep(random.uniform(0.5, 1))
                
                # Check for reCAPTCHA
                captcha_solved = False
                site_key = await self._find_recaptcha_site_key(page)
                
                if site_key and self.solver:
                    logger.info(f"🧩 reCAPTCHA detected! Site key: {site_key[:20]}...")
                    logger.info("🔄 Sending to 2Captcha for solving (this may take 30-60 seconds)...")
                    
                    try:
                        # Solve using 2Captcha
                        response = self.solver.recaptcha(
                            sitekey=site_key,
                            url=self.POCKET_OPTION_LOGIN_URL
                        )
                        captcha_code = response['code']
                        captcha_cost = 0.00299
                        
                        logger.info(f"✅ CAPTCHA solved! Injecting response...")
                        
                        # Inject CAPTCHA response
                        await page.evaluate(f'''() => {{
                            // Set g-recaptcha-response
                            let el = document.getElementById('g-recaptcha-response');
                            if (el) {{
                                el.style.display = 'block';
                                el.value = "{captcha_code}";
                            }}
                            
                            // Also try textareas
                            document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(ta => {{
                                ta.style.display = 'block';
                                ta.value = "{captcha_code}";
                            }});
                            
                            // Try callback
                            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                                Object.entries(___grecaptcha_cfg.clients || {{}}).forEach(([k, client]) => {{
                                    try {{
                                        if (client?.Z?.Z?.callback) {{
                                            client.Z.Z.callback("{captcha_code}");
                                        }}
                                    }} catch(e) {{}}
                                }});
                            }}
                        }}''')
                        
                        captcha_solved = True
                        await asyncio.sleep(1)
                        
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
                login_button = await page.query_selector(
                    "button[type='submit'], .btn-login, button.login-btn"
                )
                if login_button:
                    await login_button.click()
                else:
                    await page.evaluate("document.querySelector('form')?.submit()")
                
                logger.info("🔄 Waiting for login response...")
                await asyncio.sleep(random.uniform(5, 7))
                
                # Check if login successful
                current_url = page.url
                logger.info(f"📍 Current URL: {current_url}")
                
                if "cabinet" in current_url or "trade" in current_url or "quick-high-low" in current_url:
                    logger.info("✅ Login successful! Extracting SSID...")
                    
                    # Navigate to trading page to get WebSocket
                    if "quick-high-low" not in current_url:
                        await page.goto(self.POCKET_OPTION_TRADE_URL, wait_until='domcontentloaded', timeout=60000)
                        await asyncio.sleep(5)
                    
                    # Check captured auth messages
                    ssid = None
                    if captured_auth:
                        ssid = captured_auth[0]
                        logger.info(f"✅ Got SSID from WebSocket: {ssid[:50]}...")
                    
                    if not ssid:
                        # Try cookies
                        cookies = await context.cookies()
                        for cookie in cookies:
                            if 'ssid' in cookie['name'].lower() or 'session' in cookie['name'].lower():
                                ssid = cookie['value']
                                break
                    
                    if ssid:
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
                    # Get error message
                    error_text = await page.evaluate('''() => {
                        const selectors = ['.error-message', '.alert-danger', '[class*="error"]'];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el && el.textContent) return el.textContent.trim();
                        }
                        return null;
                    }''')
                    
                    return LoginResult(
                        success=False,
                        status=LoginStatus.LOGIN_FAILED,
                        method_used=LoginMethod.CAPTCHA_SOLVER if self.solver else LoginMethod.STEALTH_BROWSER,
                        error=error_text or f"Login failed. URL: {current_url}",
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
            if browser:
                await browser.close()
    
    async def _find_recaptcha_site_key(self, page) -> Optional[str]:
        """Find reCAPTCHA site key on page"""
        try:
            site_key = await page.evaluate('''() => {
                // From data-sitekey attribute
                const el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                
                // From g-recaptcha
                const gre = document.querySelector('.g-recaptcha');
                if (gre) return gre.getAttribute('data-sitekey');
                
                // From iframe src
                const iframe = document.querySelector('iframe[src*="recaptcha"]');
                if (iframe) {
                    const src = iframe.src;
                    const match = src.match(/[?&]k=([^&]+)/);
                    if (match) return match[1];
                }
                
                // From page source
                const html = document.documentElement.outerHTML;
                const match1 = html.match(/data-sitekey=["']([^"']+)["']/);
                if (match1) return match1[1];
                
                const match2 = html.match(/sitekey["\\s:]+["']([^"']+)["']/);
                if (match2) return match2[1];
                
                return null;
            }''')
            return site_key
        except Exception as e:
            logger.warning(f"Error finding site key: {e}")
            return None


class AutoLoginService:
    """Main service that orchestrates login attempts"""
    
    def __init__(self, captcha_api_key: Optional[str] = None):
        self.captcha_api_key = captcha_api_key or os.environ.get("TWOCAPTCHA_API_KEY")
        self.handler = PlaywrightLoginHandler(self.captcha_api_key)
        
        self._login_attempts: list = []
        self._last_successful_ssid: Optional[str] = None
        self._last_login_time: Optional[datetime] = None
        
        if self.captcha_api_key:
            logger.info(f"✅ AutoLoginService initialized with 2Captcha: {self.captcha_api_key[:8]}...")
        else:
            logger.warning("⚠️ No 2Captcha API key")
    
    async def auto_login(self, email: str, password: str) -> LoginResult:
        """Attempt automated login"""
        logger.info("🚀 Starting automated login process...")
        
        result = await self.handler.login(email, password)
        
        if result.success:
            self._last_successful_ssid = result.ssid
            self._last_login_time = datetime.now(timezone.utc)
        
        self._login_attempts.append(result)
        return result
    
    def get_login_stats(self) -> Dict[str, Any]:
        """Get login statistics"""
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
        """Get last successful SSID"""
        return self._last_successful_ssid


# Global instance
_auto_login_service: Optional[AutoLoginService] = None


def get_auto_login_service(captcha_api_key: Optional[str] = None) -> AutoLoginService:
    """Get or create auto login service"""
    global _auto_login_service
    if _auto_login_service is None or captcha_api_key:
        _auto_login_service = AutoLoginService(captcha_api_key)
    return _auto_login_service
