import asyncio
import aiohttp
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone
import os
from models import TradingSignal, SignalDirection

logger = logging.getLogger(__name__)

class PlatformIntegrationService:
    """Service for integrating with external trading platforms and notification services"""
    
    def __init__(self):
        # Load credentials from environment variables
        self.pocket_option_ssid = os.getenv('POCKET_OPTION_SSID')
        self.pocket_option_account_id = os.getenv('POCKET_OPTION_ACCOUNT_ID')
        self.pocket_option_email = os.getenv('POCKET_OPTION_EMAIL')
        self.pocket_option_password = os.getenv('POCKET_OPTION_PASSWORD')
        
        # Telegram Bot credentials
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.telegram_bot_username = os.getenv('TELEGRAM_BOT_USERNAME')
        
        # AutobotSignal.io webhook credentials
        self.autobot_webhook_url = os.getenv('AUTOBOT_WEBHOOK_URL')
        self.autobot_signal_key = os.getenv('AUTOBOT_SIGNAL_KEY')
        
        # Integration status tracking
        self.integration_status = {
            'pocket_option': {'connected': False, 'last_error': None},
            'telegram': {'connected': False, 'last_error': None},
            'autobot_signal': {'connected': False, 'last_error': None}
        }

    async def initialize_integrations(self):
        """Initialize all platform integrations"""
        try:
            # Test Telegram bot connection
            await self._test_telegram_connection()
            
            # Test AutobotSignal webhook
            await self._test_autobot_connection()
            
            # Note: Pocket Option integration requires the pocketoptionapi library
            # which we'll install if needed
            await self._test_pocket_option_connection()
            
            logger.info("Platform integrations initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing integrations: {e}")

    async def _test_telegram_connection(self):
        """Test Telegram bot connection"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getMe"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            self.integration_status['telegram']['connected'] = True
                            logger.info("Telegram bot connection successful")
                        else:
                            raise Exception(f"Telegram API error: {data}")
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            self.integration_status['telegram']['last_error'] = str(e)
            logger.error(f"Telegram connection failed: {e}")

    async def _test_autobot_connection(self):
        """Test AutobotSignal.io webhook connection"""
        try:
            test_payload = {
                "side": "test",
                "symbol": "TEST",
                "key": self.autobot_signal_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.autobot_webhook_url,
                    json=test_payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status in [200, 201, 202]:
                        self.integration_status['autobot_signal']['connected'] = True
                        logger.info("AutobotSignal.io webhook connection successful")
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            self.integration_status['autobot_signal']['last_error'] = str(e)
            logger.error(f"AutobotSignal connection failed: {e}")

    async def _test_pocket_option_connection(self):
        """Test Pocket Option API connection using SSID"""
        try:
            from pocketoptionapi_async import AsyncPocketOptionClient
            
            # Initialize the Pocket Option API with credentials
            self.pocket_option_api = AsyncPocketOptionClient(
                ssid=self.pocket_option_ssid,
                is_demo=True,  # Start with demo mode for testing
                enable_logging=True
            )
            
            # Test connection
            connection_result = await self._connect_pocket_option()
            if connection_result:
                self.integration_status['pocket_option']['connected'] = True
                logger.info("Pocket Option API connection successful")
            else:
                raise Exception("Failed to establish connection")
            
        except Exception as e:
            self.integration_status['pocket_option']['last_error'] = str(e)
            logger.error(f"Pocket Option connection failed: {e}")
            self.integration_status['pocket_option']['connected'] = False

    async def send_signal_to_all_platforms(self, signal: TradingSignal):
        """Send trading signal to all configured platforms"""
        try:
            # Send to Telegram (always, regardless of thresholds as requested)
            await self.send_telegram_signal(signal)
            
            # Send to AutobotSignal.io
            await self.send_autobot_signal(signal)
            
            # Send to Pocket Option for automated trading (if enabled)
            await self.send_pocket_option_signal(signal)
            
            logger.info(f"Signal {signal.id} sent to all platforms")
            
        except Exception as e:
            logger.error(f"Error sending signal to platforms: {e}")

    async def send_telegram_signal(self, signal: TradingSignal):
        """Send signal to Telegram bot"""
        try:
            # Format signal message for Telegram
            direction_emoji = "🟢 📈" if signal.direction in ['BUY', 'CALL'] else "🔴 📉"
            
            message = f"""
🚨 **ELITE POCKET TRADING SIGNAL** 🚨

{direction_emoji} **{signal.direction}** {signal.symbol}

💰 **Entry Price:** ${signal.entry_price}
⏱️ **Expiration:** {signal.expiration_minutes} minutes
⚡ **Probability:** {signal.probability}%
🎯 **Strategy:** {signal.strategy_used.value.replace('_', ' ').title()}

📊 **Analysis Summary:**
{signal.market_analysis_summary[:200]}...

🔥 **Justification:**
{signal.justification[:300]}...

⚠️ **Risk Assessment:**
{signal.risk_assessment[:200]}...

💡 **Suggested Stake:** ${signal.suggested_stake}

🕐 **Generated:** {signal.timestamp.strftime('%H:%M:%S UTC')}

#ElitePocketSignals #TradingAlert #{signal.symbol.replace('/', '')}
            """.strip()

            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Signal sent to Telegram successfully: {signal.id}")
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram send failed: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Error sending Telegram signal: {e}")

    async def send_autobot_signal(self, signal: TradingSignal):
        """Send signal to AutobotSignal.io webhook"""
        try:
            # Format signal for AutobotSignal.io
            side = "buy" if signal.direction in ['BUY', 'CALL'] else "sell"
            
            # Clean symbol for AutobotSignal (remove _OTC, _regular suffixes)
            clean_symbol = signal.symbol.replace('_OTC', '').replace('_regular', '')
            
            payload = {
                "side": side,
                "symbol": clean_symbol,
                "key": self.autobot_signal_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.autobot_webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status in [200, 201, 202]:
                        logger.info(f"Signal sent to AutobotSignal.io: {signal.id}")
                    else:
                        error_text = await response.text()
                        logger.error(f"AutobotSignal send failed: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Error sending AutobotSignal: {e}")

    async def _connect_pocket_option(self):
        """Connect to Pocket Option API"""
        try:
            if hasattr(self, 'pocket_option_api'):
                # Attempt to connect and authenticate
                await self.pocket_option_api.connect()
                return True
            return False
        except Exception as e:
            logger.error(f"Pocket Option connection error: {e}")
            return False

    async def send_pocket_option_signal(self, signal: TradingSignal):
        """Send signal to Pocket Option for automated trading"""
        try:
            if not hasattr(self, 'pocket_option_api'):
                logger.warning("Pocket Option API not initialized")
                return
            
            # Clean symbol name for Pocket Option
            clean_symbol = signal.symbol.replace('_OTC', '').replace('_regular', '')
            
            # Convert signal direction
            direction = "call" if signal.direction in ['BUY', 'CALL'] else "put"
            
            # Execute trade
            trade_result = await self.pocket_option_api.buy_binary_option(
                asset=clean_symbol,
                amount=float(signal.suggested_stake),
                direction=direction,
                duration=signal.expiration_minutes * 60  # Convert to seconds
            )
            
            if trade_result and trade_result.get('success', False):
                logger.info(f"Pocket Option trade executed successfully: {signal.id}")
                logger.info(f"Trade ID: {trade_result.get('trade_id')}")
            else:
                error_msg = trade_result.get('message', 'Unknown error') if trade_result else 'No response from API'
                logger.error(f"Pocket Option trade failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error sending Pocket Option signal: {e}")

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status for all platforms"""
        return {
            "pocket_option": {
                "status": "ready" if self.integration_status['pocket_option']['connected'] else "error",
                "account_id": self.pocket_option_account_id,
                "email": self.pocket_option_email,
                "ssid": self.pocket_option_ssid[:20] + "..." if self.pocket_option_ssid else None,
                "last_error": self.integration_status['pocket_option']['last_error']
            },
            "telegram": {
                "status": "connected" if self.integration_status['telegram']['connected'] else "error",
                "bot_username": self.telegram_bot_username,
                "chat_id": self.telegram_chat_id,
                "last_error": self.integration_status['telegram']['last_error']
            },
            "autobot_signal": {
                "status": "connected" if self.integration_status['autobot_signal']['connected'] else "error",
                "webhook_url": self.autobot_webhook_url,
                "signal_key": self.autobot_signal_key,
                "last_error": self.integration_status['autobot_signal']['last_error']
            }
        }

    async def execute_pocket_option_trade(self, signal: TradingSignal) -> Dict[str, Any]:
        """Execute trade directly on Pocket Option platform"""
        try:
            if not hasattr(self, 'pocket_option_api'):
                return {
                    "success": False,
                    "message": "Pocket Option API not initialized",
                    "trade_id": None,
                    "signal_id": signal.id
                }
            
            # Connect if not already connected
            if not await self._connect_pocket_option():
                return {
                    "success": False,
                    "message": "Failed to connect to Pocket Option",
                    "trade_id": None,
                    "signal_id": signal.id
                }
            
            # Clean symbol name for Pocket Option
            clean_symbol = signal.symbol.replace('_OTC', '').replace('_regular', '')
            
            # Convert signal direction
            direction = "call" if signal.direction in ['BUY', 'CALL'] else "put"
            
            # Execute the trade
            trade_result = await self.pocket_option_api.buy_binary_option(
                asset=clean_symbol,
                amount=float(signal.suggested_stake),
                direction=direction,
                duration=signal.expiration_minutes * 60  # Convert to seconds
            )
            
            if trade_result and trade_result.get('success', False):
                return {
                    "success": True,
                    "message": "Trade executed successfully on Pocket Option",
                    "trade_id": trade_result.get('trade_id'),
                    "signal_id": signal.id,
                    "balance_before": trade_result.get("balance_before"),
                    "balance_after": trade_result.get("balance_after")
                }
            else:
                error_msg = trade_result.get('message', 'Unknown error') if trade_result else 'No response from API'
                return {
                    "success": False,
                    "message": f"Trade execution failed: {error_msg}",
                    "trade_id": None,
                    "signal_id": signal.id
                }
            
        except Exception as e:
            logger.error(f"Error executing Pocket Option trade: {e}")
            return {
                "success": False,
                "message": f"Trade execution failed: {str(e)}",
                "trade_id": None,
                "signal_id": signal.id
            }

# Global instance
platform_integration = PlatformIntegrationService()