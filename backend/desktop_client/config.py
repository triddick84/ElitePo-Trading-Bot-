"""
Desktop Trading Client Configuration
====================================

Default configuration values.
Actual settings are saved to bot_settings.json by the GUI.
"""

# === DEFAULT VALUES ===
# These are used if no settings file exists

# Account Settings
DEFAULT_ACCOUNT_TYPE = "demo"  # "demo" or "live"
DEFAULT_TRADE_AMOUNT = 1
DEFAULT_MIN_PAYOUT = 80

# Strategy Settings  
DEFAULT_FAST_MA = 3
DEFAULT_SLOW_MA = 8
DEFAULT_RSI_PERIOD = 14
DEFAULT_MIN_CONFIDENCE = 65
DEFAULT_MIN_STRATEGY_VOTES = 2

# Risk Management
DEFAULT_MARTINGALE_LIST = [1, 3, 7, 15, 32, 67]
DEFAULT_MAX_TRADES_PER_HOUR = 30
DEFAULT_TAKE_PROFIT = 100
DEFAULT_STOP_LOSS = 50

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "trading_bot.log"
