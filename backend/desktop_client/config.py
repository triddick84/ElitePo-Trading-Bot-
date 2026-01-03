"""
Desktop Trading Client Configuration
====================================

Edit these settings before running the bot.
"""

# ===========================================
# POCKET OPTION CREDENTIALS
# ===========================================
POCKET_OPTION_EMAIL = "thomas.riddick84@gmail.com"
POCKET_OPTION_PASSWORD = "Tonyistheman#1"

# Account type: "demo" or "real"
ACCOUNT_TYPE = "demo"

# ===========================================
# 2CAPTCHA API KEY
# ===========================================
# Get your key from https://2captcha.com
TWOCAPTCHA_API_KEY = "c987655ee4a7359530d3558bd6fbe5a9"

# ===========================================
# CLOUD SERVER CONNECTION
# ===========================================
# Your GPT Signal Bot cloud server URL
# Replace with your actual deployed URL
CLOUD_SERVER_URL = "https://bottrader-14.preview.emergentagent.com"

# How often to poll for new signals (seconds)
SIGNAL_POLL_INTERVAL = 2

# ===========================================
# TRADING SETTINGS
# ===========================================
# Default trade amount (can be overridden by signals)
DEFAULT_TRADE_AMOUNT = 1.0

# Maximum trades per hour
MAX_TRADES_PER_HOUR = 30

# Minimum confidence to execute trade
MIN_CONFIDENCE = 70

# Enable auto-trading (set False to only monitor)
AUTO_TRADE_ENABLED = True

# ===========================================
# TELEGRAM NOTIFICATIONS (Optional)
# ===========================================
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"

# ===========================================
# BROWSER SETTINGS
# ===========================================
# Run browser in headless mode (no visible window)
HEADLESS = True

# Show browser for debugging (overrides HEADLESS)
DEBUG_MODE = False

# ===========================================
# LOGGING
# ===========================================
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "trading_bot.log"
