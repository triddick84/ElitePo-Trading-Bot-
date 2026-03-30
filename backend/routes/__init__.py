"""
Shared dependencies for route modules.
All global state, services, and helpers used across routes.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import math

load_dotenv()
ROOT_DIR = Path(__file__).parent.parent

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

logger = logging.getLogger("server")

# -------------------------------------------------------------------
# Numpy JSON serializer (used across many routes)
# -------------------------------------------------------------------
def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    import numpy as np

    def safe_float(value):
        try:
            f_val = float(value)
            if math.isnan(f_val) or math.isinf(f_val):
                return 0.0
            return f_val
        except (ValueError, TypeError):
            return 0.0

    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return safe_float(obj)
    elif isinstance(obj, np.ndarray):
        return [convert_numpy_types(item) for item in obj.tolist()]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, float):
        return safe_float(obj)
    elif hasattr(obj, 'item'):
        try:
            item_val = obj.item()
            if isinstance(item_val, float):
                return safe_float(item_val)
            return item_val
        except Exception:
            return 0.0
    else:
        return obj

# -------------------------------------------------------------------
# Lazy service accessors (avoid circular imports with server.py)
# -------------------------------------------------------------------
def get_enhanced_oanda():
    """Get the OANDA service instance."""
    from enhanced_oanda_service import enhanced_oanda
    return enhanced_oanda

def get_trading_bot():
    """Get the TradingBotService instance."""
    try:
        from server import trading_bot
        return trading_bot
    except ImportError:
        return None

def get_ssid_service():
    """Get the SSID service instance."""
    try:
        from ssid_session_service import get_ssid_service as _get
        return _get()
    except ImportError:
        return None

def get_telegram_notifier():
    """Get the Telegram notifier instance."""
    try:
        from telegram_signal_notifier import get_telegram_notifier as _get
        return _get()
    except ImportError:
        return None

def get_realtime_market_hub():
    """Get the RealtimeMarketDataHub instance from server."""
    try:
        from server import realtime_market_hub
        return realtime_market_hub
    except ImportError:
        return None
