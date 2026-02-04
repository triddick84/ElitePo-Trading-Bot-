"""
3Commas Signal Bot Integration Service

Sends trading signals to 3Commas signal bots via webhook.
Supports enter_long/enter_short/exit_long/exit_short actions.
"""

import aiohttp
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 3Commas webhook URL
THREECOMMAS_WEBHOOK_URL = "https://api.3commas.io/signal_bots/webhooks"


@dataclass
class ThreeCommasConfig:
    """Configuration for 3Commas signal bot"""
    secret: str  # JWT secret from 3Commas
    bot_uuid: str  # Bot UUID from 3Commas
    max_lag: str = "300"  # Max lag in seconds
    tv_exchange: str = "BINANCE"  # Default exchange
    enabled: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "secret": self.secret,
            "bot_uuid": self.bot_uuid,
            "max_lag": self.max_lag,
            "tv_exchange": self.tv_exchange,
            "enabled": self.enabled
        }


@dataclass 
class ThreeCommasSignal:
    """Signal to send to 3Commas"""
    action: str  # enter_long, enter_short, exit_long, exit_short
    ticker: str  # Trading pair (e.g., BTCUSDT)
    trigger_price: float  # Current price
    exchange: str = "BINANCE"  # Exchange name
    
    def to_webhook_payload(self, config: ThreeCommasConfig) -> Dict:
        """Convert signal to 3Commas webhook payload"""
        return {
            "secret": config.secret,
            "max_lag": config.max_lag,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "trigger_price": str(self.trigger_price),
            "tv_exchange": self.exchange,
            "tv_instrument": self.ticker,
            "action": self.action,
            "bot_uuid": config.bot_uuid
        }


class ThreeCommasService:
    """Service for sending signals to 3Commas"""
    
    def __init__(self, db=None):
        self.db = db
        self.config: Optional[ThreeCommasConfig] = None
        self._is_enabled = False
        
    async def initialize(self):
        """Load configuration from database"""
        if self.db is not None:
            try:
                config_doc = await self.db.threecommas_config.find_one(
                    {"type": "config"}, 
                    {"_id": 0}
                )
                if config_doc and config_doc.get("secret") and config_doc.get("bot_uuid"):
                    self.config = ThreeCommasConfig(
                        secret=config_doc.get("secret", ""),
                        bot_uuid=config_doc.get("bot_uuid", ""),
                        max_lag=config_doc.get("max_lag", "300"),
                        tv_exchange=config_doc.get("tv_exchange", "BINANCE"),
                        enabled=config_doc.get("enabled", True)
                    )
                    self._is_enabled = self.config.enabled
                    logger.info("✅ 3Commas configuration loaded")
            except Exception as e:
                logger.error(f"Error loading 3Commas config: {e}")
    
    async def save_config(self, config: Dict) -> bool:
        """Save configuration to database"""
        if self.db:
            try:
                config["type"] = "config"
                config["updated_at"] = datetime.now(timezone.utc).isoformat()
                
                await self.db.threecommas_config.update_one(
                    {"type": "config"},
                    {"$set": config},
                    upsert=True
                )
                
                # Update local config
                if config.get("secret") and config.get("bot_uuid"):
                    self.config = ThreeCommasConfig(
                        secret=config.get("secret", ""),
                        bot_uuid=config.get("bot_uuid", ""),
                        max_lag=config.get("max_lag", "300"),
                        tv_exchange=config.get("tv_exchange", "BINANCE"),
                        enabled=config.get("enabled", True)
                    )
                    self._is_enabled = self.config.enabled
                
                logger.info("✅ 3Commas configuration saved")
                return True
            except Exception as e:
                logger.error(f"Error saving 3Commas config: {e}")
                return False
        return False
    
    async def get_config(self) -> Dict:
        """Get current configuration"""
        if self.config:
            return self.config.to_dict()
        return {
            "secret": "",
            "bot_uuid": "",
            "max_lag": "300",
            "tv_exchange": "BINANCE",
            "enabled": False
        }
    
    @property
    def is_configured(self) -> bool:
        """Check if 3Commas is properly configured"""
        return (
            self.config is not None and 
            bool(self.config.secret) and 
            bool(self.config.bot_uuid)
        )
    
    @property
    def is_enabled(self) -> bool:
        """Check if 3Commas integration is enabled"""
        return self._is_enabled and self.is_configured
    
    def convert_signal_direction(self, direction: str) -> str:
        """Convert our signal direction to 3Commas action"""
        direction_upper = direction.upper() if isinstance(direction, str) else str(direction).upper()
        
        if direction_upper in ['BUY', 'CALL', 'LONG']:
            return "enter_long"
        elif direction_upper in ['SELL', 'PUT', 'SHORT']:
            return "enter_short"
        else:
            return "enter_long"  # Default
    
    def convert_ticker(self, symbol: str, exchange: str = "BINANCE") -> str:
        """Convert our symbol format to 3Commas ticker format"""
        # Remove _otc, _regular suffixes
        clean_symbol = symbol.replace('_otc', '').replace('_regular', '').replace('_OTC', '')
        
        # Convert forex pairs (EURUSD -> EURUSDT for crypto exchanges)
        # For forex on crypto exchanges, we might need to adjust
        forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD']
        
        if clean_symbol in forex_pairs:
            # For crypto exchanges, forex isn't directly available
            # User should configure appropriate crypto pairs
            return clean_symbol + "T"  # Append T for Tether pairs
        
        # For crypto pairs, ensure proper format
        if 'USD' in clean_symbol and not clean_symbol.endswith('T'):
            return clean_symbol + "T"  # BTCUSD -> BTCUSDT
        
        return clean_symbol
    
    async def send_signal(self, signal: Any) -> Dict:
        """
        Send a trading signal to 3Commas
        
        Args:
            signal: Trading signal object with direction, symbol, entry_price
            
        Returns:
            Dict with success status and message
        """
        if not self.is_enabled:
            return {
                "success": False,
                "error": "3Commas integration not enabled or not configured"
            }
        
        try:
            # Extract signal data
            direction = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
            symbol = signal.symbol if hasattr(signal, 'symbol') else str(signal.get('symbol', ''))
            price = float(signal.entry_price) if hasattr(signal, 'entry_price') else float(signal.get('entry_price', 0))
            
            # Create 3Commas signal
            tc_signal = ThreeCommasSignal(
                action=self.convert_signal_direction(direction),
                ticker=self.convert_ticker(symbol, self.config.tv_exchange),
                trigger_price=price,
                exchange=self.config.tv_exchange
            )
            
            # Create webhook payload
            payload = tc_signal.to_webhook_payload(self.config)
            
            logger.info(f"📤 Sending signal to 3Commas: {tc_signal.action} {tc_signal.ticker} @ {tc_signal.trigger_price}")
            
            # Send to 3Commas webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    THREECOMMAS_WEBHOOK_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        logger.info(f"✅ 3Commas signal sent successfully: {tc_signal.action} {tc_signal.ticker}")
                        return {
                            "success": True,
                            "message": f"Signal sent to 3Commas: {tc_signal.action} {tc_signal.ticker}",
                            "action": tc_signal.action,
                            "ticker": tc_signal.ticker,
                            "response": response_text
                        }
                    else:
                        logger.error(f"❌ 3Commas webhook failed: {response.status} - {response_text}")
                        return {
                            "success": False,
                            "error": f"Webhook returned {response.status}: {response_text}"
                        }
                        
        except Exception as e:
            logger.error(f"❌ Error sending 3Commas signal: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def test_connection(self) -> Dict:
        """Test 3Commas webhook connection"""
        if not self.is_configured:
            return {
                "success": False,
                "error": "3Commas not configured. Please set secret and bot_uuid."
            }
        
        # Create a test payload (won't execute a trade, just tests connectivity)
        test_payload = {
            "secret": self.config.secret,
            "max_lag": "1",  # Very short lag so it won't execute
            "timestamp": "2020-01-01T00:00:00Z",  # Old timestamp
            "trigger_price": "0",
            "tv_exchange": self.config.tv_exchange,
            "tv_instrument": "TEST",
            "action": "enter_long",
            "bot_uuid": self.config.bot_uuid
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    THREECOMMAS_WEBHOOK_URL,
                    json=test_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()
                    
                    # 3Commas returns 200 even for invalid signals
                    # It validates the secret and bot_uuid
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "3Commas webhook connection successful",
                            "response": response_text
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Connection failed: {response.status} - {response_text}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }


# Global instance
_threecommas_service: Optional[ThreeCommasService] = None


def get_threecommas_service() -> Optional[ThreeCommasService]:
    """Get the global 3Commas service instance"""
    return _threecommas_service


async def initialize_threecommas_service(db) -> ThreeCommasService:
    """Initialize and return the 3Commas service"""
    global _threecommas_service
    _threecommas_service = ThreeCommasService(db)
    await _threecommas_service.initialize()
    return _threecommas_service
