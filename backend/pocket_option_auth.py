"""
Pocket Option Authentication Helper
Automates SSID extraction using Selenium
"""
import os
import time
import logging
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class PocketOptionAuthenticator:
    """
    Automates SSID extraction from Pocket Option
    Uses Selenium to login and extract session cookie
    """
    
    def __init__(self, email: str = None, password: str = None):
        """
        Initialize authenticator
        
        Args:
            email: Pocket Option email
            password: Pocket Option password
        """
        self.email = email or os.getenv('POCKET_OPTION_EMAIL')
        self.password = password or os.getenv('POCKET_OPTION_PASSWORD')
        self.driver = None
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Setup headless Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Use webdriver-manager to auto-download chromedriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def extract_ssid(self) -> Optional[str]:
        """
        Login to Pocket Option and extract SSID cookie
        
        Returns:
            SSID string if successful, None otherwise
        """
        if not self.email or not self.password:
            logger.error("❌ Email or password not provided")
            return None
        
        try:
            logger.info("🌐 Opening Pocket Option login page...")
            self.driver = self._setup_driver()
            self.driver.get("https://pocketoption.com/en/login/")
            
            # Wait for page load
            time.sleep(3)
            
            # Find and fill email field
            logger.info("📧 Entering email...")
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Find and fill password field
            logger.info("🔒 Entering password...")
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Click login button
            logger.info("🔐 Clicking login button...")
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for successful login (redirect or dashboard)
            logger.info("⏳ Waiting for login to complete...")
            time.sleep(5)
            
            # Check if we're logged in (URL should change)
            current_url = self.driver.current_url
            if 'login' in current_url.lower():
                # Still on login page - might be reCAPTCHA or error
                logger.warning("⚠️ Still on login page - may require manual intervention")
                
                # Try to detect error messages
                try:
                    error_msg = self.driver.find_element(By.CLASS_NAME, "error")
                    logger.error(f"❌ Login error: {error_msg.text}")
                    return None
                except NoSuchElementException:
                    pass
            
            # Extract SSID cookie (lowercase 'ssid', not 'SSID')
            logger.info("🍪 Extracting SSID cookie...")
            cookies = self.driver.get_cookies()
            
            ssid = None
            for cookie in cookies:
                # Check both lowercase and uppercase variants
                if cookie['name'].lower() == 'ssid':
                    ssid = cookie['value']
                    logger.info(f"✅ SSID extracted successfully: {ssid}")
                    logger.info(f"   Cookie name: {cookie['name']}")
                    logger.info(f"   Domain: {cookie.get('domain', 'N/A')}")
                    logger.info(f"   Expires: {cookie.get('expiry', 'Session')}")
                    break
            
            if not ssid:
                logger.warning("⚠️ SSID cookie not found. Available cookies:")
                for cookie in cookies:
                    logger.info(f"  - {cookie['name']}: {cookie['value'][:30]}... (domain: {cookie.get('domain', 'N/A')})")
            
            return ssid
        
        except TimeoutException as e:
            logger.error(f"❌ Timeout during login: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error during SSID extraction: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if self.driver:
                self.driver.quit()
    
    def get_all_cookies(self) -> Dict[str, str]:
        """
        Get all cookies from Pocket Option
        
        Returns:
            Dictionary of cookie name -> value pairs
        """
        if not self.driver:
            return {}
        
        cookies = self.driver.get_cookies()
        return {cookie['name']: cookie['value'] for cookie in cookies}


def auto_login_and_get_ssid(email: str = None, password: str = None) -> Optional[str]:
    """
    Convenience function to auto-login and get SSID
    
    Args:
        email: Pocket Option email (or from env)
        password: Pocket Option password (or from env)
    
    Returns:
        SSID string if successful
    """
    auth = PocketOptionAuthenticator(email, password)
    ssid = auth.extract_ssid()
    
    if ssid:
        logger.info("✅ Successfully obtained SSID")
        # Optionally save to .env
        env_path = '/app/backend/.env'
        try:
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update or add SSID line
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('POCKET_OPTION_SSID='):
                    lines[i] = f'POCKET_OPTION_SSID={ssid}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'POCKET_OPTION_SSID={ssid}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            logger.info("✅ SSID saved to .env file")
        except Exception as e:
            logger.warning(f"Could not save SSID to .env: {e}")
    else:
        logger.error("❌ Failed to obtain SSID")
    
    return ssid


if __name__ == "__main__":
    # Test the authenticator
    logging.basicConfig(level=logging.INFO)
    
    email = os.getenv('POCKET_OPTION_EMAIL', 'thomas.riddick84@gmail.com')
    password = os.getenv('POCKET_OPTION_PASSWORD', 'Tonyistheman#1')
    
    ssid = auto_login_and_get_ssid(email, password)
    
    if ssid:
        print(f"\n✅ Success! SSID: {ssid}")
    else:
        print("\n❌ Failed to extract SSID")
