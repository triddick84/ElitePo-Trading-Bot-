"""
Telegram Signal Notifier for Pocket Option Trading Bot
Sends formatted trading signals to Telegram

Features:
- Formatted signal messages with all details
- Signal inversion support
- Configurable notifications
- Alert type filtering (signals, errors, status updates)
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class AlertType(Enum):
    SIGNAL = "signal"
    ERROR = "error"
    STATUS = "status"
    SSID_REFRESH = "ssid_refresh"
    CONNECTION = "connection"


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True
    send_signals: bool = True
    send_errors: bool = True
    send_status_updates: bool = True
    send_ssid_alerts: bool = True
    
    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        return cls(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            enabled=True,
            send_signals=True,
            send_errors=True,
            send_status_updates=True,
            send_ssid_alerts=True
        )
    
    def is_valid(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class TelegramSignalNotifier:
    """
    Sends trading signals and notifications to Telegram
    """
    
    def __init__(self, config: TelegramConfig = None):
        """
        Initialize Telegram notifier
        
        Args:
            config: Telegram configuration (or load from env)
        """
        self.config = config or TelegramConfig.from_env()
        self._session: Optional[aiohttp.ClientSession] = None
        self._message_queue: List[Dict] = []
        self._is_sending = False
        
        if self.config.is_valid():
            logger.info(f"📱 Telegram notifier initialized (chat: {self.config.chat_id})")
        else:
            logger.warning("⚠️ Telegram not configured (missing token or chat_id)")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _format_signal_message(self, signal: Dict) -> str:
        """
        Format a trading signal for Telegram
        
        Args:
            signal: Signal dictionary with all fields
        
        Returns:
            Formatted message string
        """
        # Extract signal details
        symbol = signal.get('symbol', signal.get('asset', 'UNKNOWN'))
        direction = signal.get('direction', 'UNKNOWN').upper()
        probability = signal.get('probability', signal.get('confidence', 0))
        timeframe = signal.get('timeframe', '5s')
        market_type = signal.get('market_type', 'regular').upper()
        entry_time = signal.get('precision_entry_time', '')
        expiration = signal.get('expiration_minutes', 1)
        strategy = signal.get('strategy_used', signal.get('strategy', 'HYBRID'))
        
        # Direction emoji
        direction_emoji = "🟢 CALL" if direction in ['BUY', 'CALL', 'UP'] else "🔴 PUT"
        
        # Confidence level
        if probability >= 85:
            confidence_emoji = "🔥 HIGH"
        elif probability >= 75:
            confidence_emoji = "⚡ MEDIUM"
        else:
            confidence_emoji = "💡 LOW"
        
        # Format message
        message = f"""
🚀 *TRADING SIGNAL* 🚀
━━━━━━━━━━━━━━━━━━━━━━

📊 *Asset:* `{symbol}`
{direction_emoji} *Direction:* `{direction}`
📈 *Probability:* `{probability:.1f}%`
{confidence_emoji}

⏱️ *Timeframe:* `{timeframe}`
⏳ *Expiration:* `{expiration} min`
🏷️ *Market:* `{market_type}`
📋 *Strategy:* `{strategy}`

🎯 *Entry Time:* `{entry_time}`

━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Trade Responsibly!*
@ElitePocket\_bot
"""
        return message
    
    def _format_error_message(self, error: str, context: str = "") -> str:
        """
        Format an error message for Telegram
        
        Args:
            error: Error message
            context: Additional context
        
        Returns:
            Formatted message string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        message = f"""
❌ *ERROR ALERT* ❌
━━━━━━━━━━━━━━━━━━━━━━

🕐 *Time:* `{timestamp}`
📝 *Context:* `{context}`
💬 *Error:* `{error[:200]}`

━━━━━━━━━━━━━━━━━━━━━━
@ElitePocket\_bot
"""
        return message
    
    def _format_status_message(self, status: str, details: Dict = None) -> str:
        """
        Format a status update message
        
        Args:
            status: Status message
            details: Additional details
        
        Returns:
            Formatted message string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        details_str = ""
        if details:
            details_str = "\n".join([f"• *{k}:* `{v}`" for k, v in details.items()])
        
        message = f"""
📢 *STATUS UPDATE* 📢
━━━━━━━━━━━━━━━━━━━━━━

🕐 *Time:* `{timestamp}`
📋 *Status:* `{status}`

{details_str}

━━━━━━━━━━━━━━━━━━━━━━
@ElitePocket\_bot
"""
        return message
    
    def _format_ssid_message(self, event: str, ssid_preview: str = "", error: str = "") -> str:
        """
        Format SSID refresh notification
        
        Args:
            event: 'refreshed' or 'failed'
            ssid_preview: Preview of new SSID
            error: Error message if failed
        
        Returns:
            Formatted message string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if event == 'refreshed':
            message = f"""
🔄 *SSID REFRESHED* ✅
━━━━━━━━━━━━━━━━━━━━━━

🕐 *Time:* `{timestamp}`
🔑 *New SSID:* `{ssid_preview}...`
✅ *Status:* Connection Active

━━━━━━━━━━━━━━━━━━━━━━
@ElitePocket\_bot
"""
        else:
            message = f"""
⚠️ *SSID REFRESH FAILED* ❌
━━━━━━━━━━━━━━━━━━━━━━

🕐 *Time:* `{timestamp}`
❌ *Error:* `{error[:100]}`
⚠️ *Action:* Check credentials

━━━━━━━━━━━━━━━━━━━━━━
@ElitePocket\_bot
"""
        return message
    
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to Telegram
        
        Args:
            text: Message text
            parse_mode: Telegram parse mode (Markdown or HTML)
        
        Returns:
            True if successful
        """
        if not self.config.is_valid():
            logger.warning("⚠️ Telegram not configured, skipping message")
            return False
        
        if not self.config.enabled:
            logger.debug("Telegram notifications disabled")
            return False
        
        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.config.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.debug("✅ Telegram message sent")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Telegram API error: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False
    
    async def send_signal(self, signal: Dict) -> bool:
        """
        Send a trading signal notification
        
        Args:
            signal: Signal dictionary
        
        Returns:
            True if successful
        """
        if not self.config.send_signals:
            return False
        
        message = self._format_signal_message(signal)
        return await self.send_message(message)
    
    async def send_error(self, error: str, context: str = "") -> bool:
        """
        Send an error notification
        
        Args:
            error: Error message
            context: Additional context
        
        Returns:
            True if successful
        """
        if not self.config.send_errors:
            return False
        
        message = self._format_error_message(error, context)
        return await self.send_message(message)
    
    async def send_status(self, status: str, details: Dict = None) -> bool:
        """
        Send a status update notification
        
        Args:
            status: Status message
            details: Additional details
        
        Returns:
            True if successful
        """
        if not self.config.send_status_updates:
            return False
        
        message = self._format_status_message(status, details)
        return await self.send_message(message)
    
    async def send_ssid_refreshed(self, ssid: str) -> bool:
        """
        Send SSID refresh success notification
        
        Args:
            ssid: New SSID (will be truncated for preview)
        
        Returns:
            True if successful
        """
        if not self.config.send_ssid_alerts:
            return False
        
        preview = ssid[:15] if len(ssid) > 15 else ssid
        message = self._format_ssid_message('refreshed', preview)
        return await self.send_message(message)
    
    async def send_ssid_failed(self, error: str) -> bool:
        """
        Send SSID refresh failure notification
        
        Args:
            error: Error message
        
        Returns:
            True if successful
        """
        if not self.config.send_ssid_alerts:
            return False
        
        message = self._format_ssid_message('failed', error=error)
        return await self.send_message(message)
    
    async def send_bot_started(self, config: Dict = None) -> bool:
        """
        Send bot started notification
        
        Args:
            config: Bot configuration
        
        Returns:
            True if successful
        """
        details = {
            'Mode': config.get('account_type', 'demo').upper() if config else 'DEMO',
            'Strategies': str(len(config.get('selected_strategies', []))) if config else '0',
            'Auto-Trade': 'ON' if config and config.get('auto_trade') else 'OFF'
        }
        return await self.send_status("🤖 Trading Bot Started", details)
    
    async def send_bot_stopped(self) -> bool:
        """
        Send bot stopped notification
        
        Returns:
            True if successful
        """
        return await self.send_status("🛑 Trading Bot Stopped")
    
    def update_config(self, **kwargs):
        """
        Update notification configuration
        
        Args:
            **kwargs: Configuration options to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"📱 Telegram config updated: {kwargs}")
    
    def get_status(self) -> Dict:
        """
        Get notifier status
        
        Returns:
            Status dictionary
        """
        return {
            'enabled': self.config.enabled,
            'configured': self.config.is_valid(),
            'chat_id': self.config.chat_id,
            'send_signals': self.config.send_signals,
            'send_errors': self.config.send_errors,
            'send_status_updates': self.config.send_status_updates,
            'send_ssid_alerts': self.config.send_ssid_alerts
        }


# Global instance
_telegram_notifier: Optional[TelegramSignalNotifier] = None


def get_telegram_notifier() -> TelegramSignalNotifier:
    """Get global Telegram notifier instance"""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramSignalNotifier()
    return _telegram_notifier


async def initialize_telegram_notifier() -> TelegramSignalNotifier:
    """Initialize the Telegram notifier"""
    global _telegram_notifier
    _telegram_notifier = TelegramSignalNotifier()
    return _telegram_notifier


async def shutdown_telegram_notifier():
    """Shutdown the Telegram notifier"""
    global _telegram_notifier
    if _telegram_notifier:
        await _telegram_notifier.close()
        _telegram_notifier = None
