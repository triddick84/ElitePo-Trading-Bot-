"""
SSID Auto-Refresh Manager for Pocket Option
Supports both Selenium automation and manual update fallback

Features:
- Automatic SSID extraction using Selenium
- Manual SSID update endpoint fallback
- SSID health monitoring and expiration detection
- Persistent storage of credentials
"""

import asyncio
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import base64

logger = logging.getLogger(__name__)


# ============================================================================
# SSID STORAGE
# ============================================================================

@dataclass
class SSIDStorage:
    """Persistent storage for SSID credentials"""
    session_id: str
    uid: int = 0
    is_demo: bool = True
    platform: int = 1
    raw_ssid: str = ""
    extracted_at: str = ""
    expires_at: str = ""
    extraction_method: str = "manual"  # manual, selenium, browser_bridge
    email: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SSIDStorage':
        return cls(**data)


class SSIDManager:
    """
    Manages SSID extraction, storage, and auto-refresh
    
    Supports:
    1. Manual SSID update via API
    2. Selenium-based automatic extraction
    3. Browser bridge forwarding
    """
    
    STORAGE_PATH = "/app/backend/.ssid_storage.json"
    DEFAULT_EXPIRY_HOURS = 1  # Assume SSID expires after 1 hour
    
    def __init__(self):
        self.current_ssid: Optional[SSIDStorage] = None
        self.last_refresh_attempt: Optional[datetime] = None
        self.refresh_in_progress = False
        self.auto_refresh_enabled = True
        
        # Selenium settings
        self.selenium_available = False
        self.po_email: Optional[str] = None
        self.po_password: Optional[str] = None
        
        # Callbacks
        self.on_ssid_updated: Optional[Callable] = None
        self.on_ssid_expired: Optional[Callable] = None
        
        # Load stored SSID
        self._load_from_storage()
        
        # Check Selenium availability
        self._check_selenium()
        
        logger.info("🔑 SSID Manager initialized")
    
    def _load_from_storage(self):
        """Load SSID from persistent storage"""
        try:
            if os.path.exists(self.STORAGE_PATH):
                with open(self.STORAGE_PATH, 'r') as f:
                    data = json.load(f)
                    self.current_ssid = SSIDStorage.from_dict(data)
                    logger.info(f"Loaded stored SSID (extracted: {self.current_ssid.extracted_at})")
        except Exception as e:
            logger.warning(f"Could not load stored SSID: {e}")
    
    def _save_to_storage(self):
        """Save SSID to persistent storage"""
        try:
            if self.current_ssid:
                with open(self.STORAGE_PATH, 'w') as f:
                    json.dump(self.current_ssid.to_dict(), f)
                logger.debug("SSID saved to storage")
        except Exception as e:
            logger.error(f"Could not save SSID: {e}")
    
    def _check_selenium(self):
        """Check if Selenium is available"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            self.selenium_available = True
            logger.info("✅ Selenium available for auto-refresh")
        except ImportError:
            self.selenium_available = False
            logger.warning("⚠️ Selenium not available - manual SSID update only")
    
    def set_credentials(self, email: str, password: str):
        """Set Pocket Option login credentials for Selenium"""
        self.po_email = email
        self.po_password = password
        logger.info(f"Credentials set for: {email}")
    
    def update_ssid_manual(self, ssid: str, is_demo: bool = True) -> bool:
        """
        Manually update SSID
        
        Args:
            ssid: Full SSID string from browser
            is_demo: Whether this is a demo account
        
        Returns:
            True if successful
        """
        try:
            # Parse SSID
            uid = 0
            session_id = ssid
            
            # Try to extract UID from full SSID format
            if '42["auth"' in ssid:
                try:
                    json_str = ssid.split('42["auth",')[1].rstrip(']')
                    data = json.loads(json_str)
                    session_id = data.get('session', ssid)
                    uid = data.get('uid', 0)
                    is_demo = data.get('isDemo', 1) == 1
                except Exception:
                    pass
            
            self.current_ssid = SSIDStorage(
                session_id=session_id,
                uid=uid,
                is_demo=is_demo,
                raw_ssid=ssid,
                extracted_at=datetime.now(timezone.utc).isoformat(),
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=self.DEFAULT_EXPIRY_HOURS)).isoformat(),
                extraction_method="manual"
            )
            
            self._save_to_storage()
            
            # Trigger callback
            if self.on_ssid_updated:
                self.on_ssid_updated(self.current_ssid)
            
            logger.info(f"✅ SSID updated manually (uid={uid}, demo={is_demo})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update SSID: {e}")
            return False
    
    async def refresh_ssid_selenium(self) -> bool:
        """
        Automatically refresh SSID using Selenium
        
        Returns:
            True if successful
        """
        if not self.selenium_available:
            logger.warning("Selenium not available for auto-refresh")
            return False
        
        if not self.po_email or not self.po_password:
            logger.warning("Credentials not set for Selenium refresh")
            return False
        
        if self.refresh_in_progress:
            logger.warning("Refresh already in progress")
            return False
        
        self.refresh_in_progress = True
        self.last_refresh_attempt = datetime.now(timezone.utc)
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            
            logger.info("🔄 Starting Selenium SSID extraction...")
            
            # Configure Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            # Initialize driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            try:
                # Navigate to Pocket Option
                driver.get("https://pocketoption.com/en/login/")
                await asyncio.sleep(3)
                
                # Wait for login form
                wait = WebDriverWait(driver, 15)
                
                # Find and fill email
                email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
                email_input.clear()
                email_input.send_keys(self.po_email)
                
                # Find and fill password
                password_input = driver.find_element(By.NAME, "password")
                password_input.clear()
                password_input.send_keys(self.po_password)
                
                # Click login button
                login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
                # Wait for redirect to trading page
                await asyncio.sleep(5)
                
                # Navigate to trading interface to trigger WebSocket
                driver.get("https://pocketoption.com/en/trade/")
                await asyncio.sleep(5)
                
                # Get performance logs to find WebSocket auth message
                logs = driver.get_log('performance')
                
                ssid = None
                for log in logs:
                    message = json.loads(log['message'])['message']
                    
                    # Look for WebSocket messages
                    if message.get('method') == 'Network.webSocketFrameSent':
                        payload = message.get('params', {}).get('response', {}).get('payloadData', '')
                        if '42["auth"' in payload:
                            ssid = payload
                            logger.info("Found auth message in WebSocket")
                            break
                
                # Try cookies as fallback
                if not ssid:
                    cookies = driver.get_cookies()
                    for cookie in cookies:
                        if cookie['name'].lower() == 'ssid':
                            ssid = cookie['value']
                            logger.info("Found SSID in cookies")
                            break
                
                if ssid:
                    self.update_ssid_manual(ssid, is_demo=True)
                    self.current_ssid.extraction_method = "selenium"
                    self._save_to_storage()
                    
                    logger.info("✅ SSID extracted successfully via Selenium")
                    return True
                else:
                    logger.warning("Could not find SSID in browser data")
                    return False
                    
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Selenium SSID extraction failed: {e}")
            return False
        
        finally:
            self.refresh_in_progress = False
    
    def is_ssid_valid(self) -> bool:
        """Check if current SSID is valid (not expired)"""
        if not self.current_ssid:
            return False
        
        if not self.current_ssid.expires_at:
            return True
        
        try:
            expires = datetime.fromisoformat(self.current_ssid.expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) < expires
        except Exception:
            return True
    
    def is_ssid_expiring_soon(self, minutes: int = 10) -> bool:
        """Check if SSID will expire within given minutes"""
        if not self.current_ssid or not self.current_ssid.expires_at:
            return False
        
        try:
            expires = datetime.fromisoformat(self.current_ssid.expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > (expires - timedelta(minutes=minutes))
        except Exception:
            return False
    
    async def auto_refresh_if_needed(self) -> bool:
        """
        Automatically refresh SSID if expiring soon
        
        Returns:
            True if SSID is valid (refreshed or still valid)
        """
        if not self.auto_refresh_enabled:
            return self.is_ssid_valid()
        
        if self.is_ssid_valid() and not self.is_ssid_expiring_soon():
            return True
        
        # Try Selenium refresh first
        if self.selenium_available and self.po_email and self.po_password:
            logger.info("SSID expiring soon, attempting auto-refresh...")
            success = await self.refresh_ssid_selenium()
            if success:
                return True
        
        # Trigger expired callback for manual intervention
        if self.on_ssid_expired:
            self.on_ssid_expired()
        
        logger.warning("⚠️ SSID expired and auto-refresh failed - manual update required")
        return False
    
    def get_current_ssid(self) -> Optional[str]:
        """Get current session ID"""
        if self.current_ssid:
            return self.current_ssid.session_id
        return None
    
    def get_full_ssid(self) -> Optional[str]:
        """Get full SSID string (42["auth",...] format)"""
        if self.current_ssid:
            return self.current_ssid.raw_ssid
        return None
    
    def get_status(self) -> Dict:
        """Get SSID manager status"""
        return {
            'has_ssid': self.current_ssid is not None,
            'is_valid': self.is_ssid_valid(),
            'is_expiring_soon': self.is_ssid_expiring_soon(),
            'extraction_method': self.current_ssid.extraction_method if self.current_ssid else None,
            'extracted_at': self.current_ssid.extracted_at if self.current_ssid else None,
            'expires_at': self.current_ssid.expires_at if self.current_ssid else None,
            'uid': self.current_ssid.uid if self.current_ssid else None,
            'is_demo': self.current_ssid.is_demo if self.current_ssid else None,
            'selenium_available': self.selenium_available,
            'credentials_set': bool(self.po_email and self.po_password),
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'refresh_in_progress': self.refresh_in_progress
        }
    
    def extend_expiry(self, hours: int = 1):
        """Manually extend SSID expiry time"""
        if self.current_ssid:
            self.current_ssid.expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
            self._save_to_storage()
            logger.info(f"SSID expiry extended by {hours} hours")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_ssid_manager: Optional[SSIDManager] = None


def get_ssid_manager() -> SSIDManager:
    """Get singleton SSID manager instance"""
    global _ssid_manager
    if _ssid_manager is None:
        _ssid_manager = SSIDManager()
    return _ssid_manager


async def auto_refresh_ssid_task():
    """Background task to auto-refresh SSID"""
    manager = get_ssid_manager()
    
    while True:
        try:
            await manager.auto_refresh_if_needed()
        except Exception as e:
            logger.error(f"Auto-refresh task error: {e}")
        
        # Check every 5 minutes
        await asyncio.sleep(300)
