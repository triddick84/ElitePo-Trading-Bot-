"""
TradingView Webhook Integration Service
========================================

Receives webhook alerts from TradingView and converts them to trading signals.
Supports:
- Pine Script alert messages
- Custom JSON payloads
- Signal routing to MT5, Pocket Option, or internal signal generator
- Alert history and logging
"""

import os
import hmac
import hashlib
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AlertAction(Enum):
    BUY = "buy"
    SELL = "sell"
    CALL = "call"
    PUT = "put"
    CLOSE = "close"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class AlertSource(Enum):
    TRADINGVIEW = "tradingview"
    CUSTOM = "custom"
    INTERNAL = "internal"


class DestinationBroker(Enum):
    MT5 = "mt5"
    POCKET_OPTION = "pocket_option"
    INTERNAL = "internal"
    ALL = "all"


class TradingViewAlertModel(BaseModel):
    """Standard TradingView webhook alert format"""
    # Required fields
    action: str = Field(..., description="buy, sell, call, put, close")
    symbol: str = Field(..., description="Trading symbol e.g. EURUSD, BTC/USD")
    
    # Optional fields
    price: Optional[float] = Field(None, description="Current price")
    quantity: Optional[float] = Field(None, description="Trade quantity/lot size")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    expiry: Optional[int] = Field(60, description="Expiry in seconds (for binary options)")
    
    # Authentication
    passphrase: Optional[str] = Field(None, description="Security passphrase")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    
    # Metadata
    strategy: Optional[str] = Field(None, description="Strategy name")
    timeframe: Optional[str] = Field(None, description="Chart timeframe")
    exchange: Optional[str] = Field(None, description="Exchange name")
    comment: Optional[str] = Field(None, description="Additional comment")
    
    # Alert info from TradingView
    ticker: Optional[str] = Field(None, description="TradingView ticker")
    interval: Optional[str] = Field(None, description="TradingView interval")
    time: Optional[str] = Field(None, description="Alert timestamp")
    
    # Routing
    destination: Optional[str] = Field("internal", description="mt5, pocket_option, internal, all")


@dataclass
class ProcessedAlert:
    """Processed and validated alert ready for execution"""
    alert_id: str
    action: AlertAction
    symbol: str
    price: float
    quantity: float
    take_profit: Optional[float]
    stop_loss: Optional[float]
    expiry_seconds: int
    destination: DestinationBroker
    source: AlertSource
    strategy: str
    timestamp: datetime
    raw_data: Dict
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    execution_status: str = "pending"
    execution_result: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "action": self.action.value,
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "expiry_seconds": self.expiry_seconds,
            "destination": self.destination.value,
            "source": self.source.value,
            "strategy": self.strategy,
            "timestamp": self.timestamp.isoformat(),
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "execution_status": self.execution_status,
            "execution_result": self.execution_result
        }


class TradingViewWebhookService:
    """
    Service to handle TradingView webhook alerts
    """
    
    def __init__(self):
        self.secret_key = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET", "gpt-signal-bot-secret")
        self.allowed_passphrases = set(os.environ.get("TRADINGVIEW_PASSPHRASES", "gpt-signal,trading-bot").split(","))
        self.alert_history: List[ProcessedAlert] = []
        self.max_history = 1000
        
        # Symbol mappings (TradingView to broker formats)
        self.symbol_mappings = {
            # Forex
            "EURUSD": {"mt5": "EURUSD", "pocket_option": "EURUSD_OTC", "oanda": "EUR_USD"},
            "GBPUSD": {"mt5": "GBPUSD", "pocket_option": "GBPUSD_OTC", "oanda": "GBP_USD"},
            "USDJPY": {"mt5": "USDJPY", "pocket_option": "USDJPY_OTC", "oanda": "USD_JPY"},
            "AUDUSD": {"mt5": "AUDUSD", "pocket_option": "AUDUSD_OTC", "oanda": "AUD_USD"},
            "USDCAD": {"mt5": "USDCAD", "pocket_option": "USDCAD_OTC", "oanda": "USD_CAD"},
            "USDCHF": {"mt5": "USDCHF", "pocket_option": "USDCHF_OTC", "oanda": "USD_CHF"},
            "NZDUSD": {"mt5": "NZDUSD", "pocket_option": "NZDUSD_OTC", "oanda": "NZD_USD"},
            "EURJPY": {"mt5": "EURJPY", "pocket_option": "EURJPY_OTC", "oanda": "EUR_JPY"},
            "GBPJPY": {"mt5": "GBPJPY", "pocket_option": "GBPJPY_OTC", "oanda": "GBP_JPY"},
            "EURGBP": {"mt5": "EURGBP", "pocket_option": "EURGBP_OTC", "oanda": "EUR_GBP"},
            # Crypto
            "BTCUSD": {"mt5": "BTCUSD", "pocket_option": "BTCUSD_OTC", "oanda": "BTC_USD"},
            "ETHUSD": {"mt5": "ETHUSD", "pocket_option": "ETHUSD_OTC", "oanda": "ETH_USD"},
            # Indices
            "US30": {"mt5": "US30", "pocket_option": "US30_OTC", "oanda": "US30_USD"},
            "US500": {"mt5": "US500", "pocket_option": "US500_OTC", "oanda": "SPX500_USD"},
            "NAS100": {"mt5": "NAS100", "pocket_option": "NAS100_OTC", "oanda": "NAS100_USD"},
        }
        
        logger.info("TradingView Webhook Service initialized")
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature for security"""
        expected = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def verify_passphrase(self, passphrase: Optional[str]) -> bool:
        """Verify passphrase authentication"""
        if not passphrase:
            return False
        return passphrase in self.allowed_passphrases
    
    def normalize_symbol(self, symbol: str, destination: str = "internal") -> str:
        """Normalize symbol for destination broker"""
        # Clean symbol
        clean_symbol = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
        
        # Remove common suffixes
        for suffix in [".PRO", ".STD", "OTC", "OANDA", "PERP"]:
            clean_symbol = clean_symbol.replace(suffix, "")
        
        # Look up mapping
        if clean_symbol in self.symbol_mappings:
            mapping = self.symbol_mappings[clean_symbol]
            return mapping.get(destination, mapping.get("mt5", clean_symbol))
        
        return clean_symbol
    
    def parse_action(self, action_str: str) -> Optional[AlertAction]:
        """Parse action string to AlertAction enum"""
        action_map = {
            "buy": AlertAction.BUY,
            "long": AlertAction.BUY,
            "call": AlertAction.CALL,
            "sell": AlertAction.SELL,
            "short": AlertAction.SELL,
            "put": AlertAction.PUT,
            "close": AlertAction.CLOSE,
            "close_long": AlertAction.CLOSE_LONG,
            "close_short": AlertAction.CLOSE_SHORT,
            "exit": AlertAction.CLOSE,
        }
        return action_map.get(action_str.lower().strip())
    
    def parse_destination(self, dest_str: Optional[str]) -> DestinationBroker:
        """Parse destination string to enum"""
        if not dest_str:
            return DestinationBroker.INTERNAL
        
        dest_map = {
            "mt5": DestinationBroker.MT5,
            "metatrader": DestinationBroker.MT5,
            "metatrader5": DestinationBroker.MT5,
            "pocket_option": DestinationBroker.POCKET_OPTION,
            "pocketoption": DestinationBroker.POCKET_OPTION,
            "po": DestinationBroker.POCKET_OPTION,
            "internal": DestinationBroker.INTERNAL,
            "signal": DestinationBroker.INTERNAL,
            "all": DestinationBroker.ALL,
        }
        return dest_map.get(dest_str.lower().strip(), DestinationBroker.INTERNAL)
    
    def process_alert(self, alert_data: Dict, source: AlertSource = AlertSource.TRADINGVIEW) -> ProcessedAlert:
        """
        Process incoming webhook alert
        
        Expected TradingView alert message format:
        {
            "action": "buy",
            "symbol": "EURUSD",
            "price": 1.0850,
            "quantity": 0.1,
            "take_profit": 1.0900,
            "stop_loss": 1.0800,
            "passphrase": "your-secret",
            "destination": "mt5"
        }
        """
        import uuid
        
        alert_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc)
        validation_errors = []
        
        # Extract and validate action
        action_str = alert_data.get("action", "")
        action = self.parse_action(action_str)
        if not action:
            validation_errors.append(f"Invalid action: {action_str}")
            action = AlertAction.BUY  # Default
        
        # Extract symbol
        symbol = alert_data.get("symbol") or alert_data.get("ticker") or ""
        if not symbol:
            validation_errors.append("Missing symbol")
        
        # Extract destination
        destination = self.parse_destination(alert_data.get("destination"))
        
        # Normalize symbol for destination
        normalized_symbol = self.normalize_symbol(symbol, destination.value)
        
        # Extract price (handle None values)
        price_val = alert_data.get("price")
        price = float(price_val) if price_val is not None else 0.0
        
        # Extract quantity/lot size (handle None values)
        qty_val = alert_data.get("quantity") or alert_data.get("qty") or alert_data.get("lot")
        quantity = float(qty_val) if qty_val is not None else 0.01
        
        # Extract TP/SL
        take_profit = alert_data.get("take_profit") or alert_data.get("tp")
        stop_loss = alert_data.get("stop_loss") or alert_data.get("sl")
        
        if take_profit:
            take_profit = float(take_profit)
        if stop_loss:
            stop_loss = float(stop_loss)
        
        # Extract expiry for binary options
        expiry = int(alert_data.get("expiry", 60))
        
        # Extract strategy name
        strategy = alert_data.get("strategy", "tradingview_alert")
        
        # Validate passphrase if provided
        passphrase = alert_data.get("passphrase")
        if passphrase and not self.verify_passphrase(passphrase):
            validation_errors.append("Invalid passphrase")
        
        # Create processed alert
        processed = ProcessedAlert(
            alert_id=alert_id,
            action=action,
            symbol=normalized_symbol,
            price=price,
            quantity=quantity,
            take_profit=take_profit,
            stop_loss=stop_loss,
            expiry_seconds=expiry,
            destination=destination,
            source=source,
            strategy=strategy,
            timestamp=timestamp,
            raw_data=alert_data,
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors
        )
        
        # Add to history
        self.alert_history.append(processed)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        logger.info(f"Processed TradingView alert: {alert_id} - {action.value} {normalized_symbol} -> {destination.value}")
        
        return processed
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return [a.to_dict() for a in self.alert_history[-limit:]]
    
    def get_alert_stats(self) -> Dict:
        """Get alert statistics"""
        total = len(self.alert_history)
        valid = sum(1 for a in self.alert_history if a.is_valid)
        executed = sum(1 for a in self.alert_history if a.execution_status == "executed")
        
        by_action = {}
        by_destination = {}
        by_symbol = {}
        
        for alert in self.alert_history:
            # By action
            action = alert.action.value
            by_action[action] = by_action.get(action, 0) + 1
            
            # By destination
            dest = alert.destination.value
            by_destination[dest] = by_destination.get(dest, 0) + 1
            
            # By symbol
            symbol = alert.symbol
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
        
        return {
            "total_alerts": total,
            "valid_alerts": valid,
            "executed_alerts": executed,
            "by_action": by_action,
            "by_destination": by_destination,
            "by_symbol": by_symbol
        }
    
    def generate_pine_script_template(self) -> str:
        """Generate Pine Script template for TradingView alerts"""
        return '''
// Pine Script Alert Template for GPT Signal Bot
// Add this to your strategy to send webhooks

// Alert message format (JSON)
alertMessage = '{"action": "' + (strategy.position_size > 0 ? "buy" : "sell") + '", "symbol": "' + syminfo.ticker + '", "price": ' + str.tostring(close) + ', "quantity": 0.1, "passphrase": "gpt-signal", "destination": "mt5"}'

// Create alert condition
if strategy.position_size != strategy.position_size[1]
    alert(alertMessage, alert.freq_once_per_bar_close)

// Or use built-in alert placeholders:
// {{strategy.order.action}} - buy or sell
// {{ticker}} - symbol
// {{close}} - current price
// {{time}} - timestamp
// {{interval}} - timeframe

// Example manual alert message:
// {"action": "{{strategy.order.action}}", "symbol": "{{ticker}}", "price": {{close}}, "passphrase": "gpt-signal", "destination": "mt5"}
'''
    
    def get_webhook_setup_instructions(self, base_url: str) -> Dict:
        """Get instructions for setting up TradingView webhooks"""
        return {
            "webhook_url": f"{base_url}/api/tradingview/webhook",
            "method": "POST",
            "content_type": "application/json",
            "required_fields": ["action", "symbol"],
            "optional_fields": ["price", "quantity", "take_profit", "stop_loss", "expiry", "passphrase", "destination"],
            "example_message": {
                "action": "buy",
                "symbol": "EURUSD",
                "price": 1.0850,
                "quantity": 0.1,
                "take_profit": 1.0900,
                "stop_loss": 1.0800,
                "passphrase": "gpt-signal",
                "destination": "mt5"
            },
            "pine_script_template": self.generate_pine_script_template(),
            "notes": [
                "Webhook URL requires TradingView Pro subscription",
                "Use passphrase for authentication",
                "destination can be: mt5, pocket_option, internal, or all",
                "For binary options, use action: call/put and set expiry in seconds"
            ]
        }


# Global instance
tradingview_webhook_service = TradingViewWebhookService()


def get_tradingview_service() -> TradingViewWebhookService:
    return tradingview_webhook_service
