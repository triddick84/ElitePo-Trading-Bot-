"""
Pocket Option Desktop Client - Browser Driver
==============================================

Uses undetected_chromedriver to bypass bot detection.
Based on VitalySvyatyuk's approach.
"""

import os
import platform
import logging

logger = logging.getLogger(__name__)

def get_driver(headless: bool = False, profile_name: str = "GPT Signal Bot Profile"):
    """
    Initialize Chrome driver with undetected_chromedriver
    
    Args:
        headless: Run browser in headless mode (not recommended for trading)
        profile_name: Chrome profile name for persistent login
    
    Returns:
        Chrome driver instance
    """
    try:
        import undetected_chromedriver as uc
    except ImportError:
        logger.error("undetected_chromedriver not installed. Run: pip install undetected-chromedriver")
        raise
    
    options = uc.ChromeOptions()
    
    # Enable performance logging for WebSocket capture
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    # SSL and certificate handling
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--disable-build-check')
    
    # Performance optimizations
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    if headless:
        options.add_argument('--headless=new')
    
    # Get username and OS for profile path
    username = os.environ.get('USER', os.environ.get('USERNAME', 'user'))
    os_platform = platform.platform().lower()
    
    # Set Chrome profile path based on OS
    if 'macos' in os_platform or 'darwin' in os_platform:
        path_default = f'/Users/{username}/Library/Application Support/Google/Chrome/{profile_name}'
    elif 'windows' in os_platform:
        path_default = f'C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data\\{profile_name}'
    elif 'linux' in os_platform:
        path_default = f'/home/{username}/.config/google-chrome/{profile_name}'
    else:
        path_default = ''
    
    if path_default:
        options.add_argument(f'--user-data-dir={path_default}')
        logger.info(f"Using Chrome profile: {path_default}")
    
    try:
        driver = uc.Chrome(options=options)
        logger.info("Chrome driver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        raise


# Asset mappings for Pocket Option
ASSET_SYMBOLS = {
    # Forex OTC
    'EURUSD_otc': 'EUR/USD OTC',
    'GBPUSD_otc': 'GBP/USD OTC',
    'USDJPY_otc': 'USD/JPY OTC',
    'AUDUSD_otc': 'AUD/USD OTC',
    'EURGBP_otc': 'EUR/GBP OTC',
    'EURJPY_otc': 'EUR/JPY OTC',
    'GBPJPY_otc': 'GBP/JPY OTC',
    'USDCHF_otc': 'USD/CHF OTC',
    'USDCAD_otc': 'USD/CAD OTC',
    'NZDUSD_otc': 'NZD/USD OTC',
    
    # Regular Forex
    'EURUSD': 'EUR/USD',
    'GBPUSD': 'GBP/USD',
    'USDJPY': 'USD/JPY',
    'AUDUSD': 'AUD/USD',
    
    # Crypto OTC
    'BTCUSD_otc': 'BTC/USD OTC',
    'ETHUSD_otc': 'ETH/USD OTC',
    
    # Stocks OTC
    '#AAPL_otc': 'Apple OTC',
    '#TSLA_otc': 'Tesla OTC',
    '#MSFT_otc': 'Microsoft OTC',
    '#AMZN_otc': 'Amazon OTC',
    '#GOOGL_otc': 'Google OTC',
    'AMZN_otc': 'Amazon OTC',
    'VISA_otc': 'VISA OTC',
    'NFLX_otc': 'Netflix OTC',
    'BABA_otc': 'Alibaba OTC',
}

# Reverse mapping
SYMBOL_TO_ASSET = {v: k for k, v in ASSET_SYMBOLS.items()}
