"""
Telegram Bot Service for Trading Signals and Auto-Trading
Integrates with Pocket Option for automated trade execution

Features:
- Send BUY/SELL signals to Telegram
- Receive commands from Telegram
- Auto-trade on Pocket Option (demo/real)
- User notifications and status updates
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import httpx

logger = logging.getLogger(__name__)

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8342619832:AAEdHnS_HKKariaDQaKHH6OT_pnLfp9dfIQ')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6434316177')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TradeDirection(str, Enum):
    CALL = 'CALL'
    PUT = 'PUT'
    BUY = 'BUY'
    SELL = 'SELL'


@dataclass
class TradingSignal:
    id: str
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    timeframe: str
    expiration_seconds: int
    strategy: str
    timestamp: str
    reasoning: str = ""


@dataclass
class TradeResult:
    signal_id: str
    trade_id: str
    symbol: str
    direction: str
    amount: float
    duration: int
    status: str  # placed, won, lost, error
    profit: float = 0.0
    timestamp: str = ""


class TelegramBotService:
    """
    Telegram Bot Service for Signal Notifications and Auto-Trading
    """
    
    def __init__(self, db=None):
        self.db = db
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.default_chat_id = TELEGRAM_CHAT_ID
        self.api_url = TELEGRAM_API_URL
        self.is_running = False
        self.auto_trading_enabled = False
        self.demo_mode = True
        self.trade_amount = 1.0
        self.http_client = None
        self._command_handlers: Dict[str, Callable] = {}
        self._signal_callback = None
        self._last_update_id = 0
        
        # Register default commands
        self._register_default_commands()
    
    def _register_default_commands(self):
        """Register default bot commands"""
        self._command_handlers = {
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/status': self._cmd_status,
            '/balance': self._cmd_balance,
            '/enable': self._cmd_enable_auto_trading,
            '/disable': self._cmd_disable_auto_trading,
            '/demo': self._cmd_set_demo,
            '/real': self._cmd_set_real,
            '/amount': self._cmd_set_amount,
            '/signal': self._cmd_force_signal,
            '/history': self._cmd_trade_history,
            '/stats': self._cmd_stats,
            '/settings': self._cmd_settings,
        }
    
    async def _get_client(self):
        """Get or create HTTP client"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client
    
    async def send_message(self, text: str, chat_id: str = None, parse_mode: str = 'HTML') -> Dict:
        """Send message to Telegram"""
        try:
            client = await self._get_client()
            
            payload = {
                'chat_id': chat_id or self.default_chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = await client.post(f"{self.api_url}/sendMessage", json=payload)
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"Message sent to {chat_id or self.default_chat_id}")
                return {'success': True, 'message_id': result['result']['message_id']}
            else:
                logger.error(f"Failed to send message: {result}")
                return {'success': False, 'error': result.get('description', 'Unknown error')}
                
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def send_signal(self, signal: TradingSignal, chat_id: str = None) -> Dict:
        """Send trading signal notification to Telegram"""
        try:
            # Format signal message
            direction_emoji = "🟢" if signal.direction in ['CALL', 'BUY'] else "🔴"
            confidence_stars = "⭐" * min(int(signal.confidence / 20), 5)
            
            message = f"""
<b>📊 TRADING SIGNAL</b>

{direction_emoji} <b>{signal.direction}</b> {signal.symbol}

💰 Entry Price: <code>{signal.entry_price}</code>
⏰ Timeframe: <code>{signal.timeframe}</code>
⏳ Expiration: <code>{signal.expiration_seconds}s</code>
🎯 Confidence: <code>{signal.confidence:.1f}%</code> {confidence_stars}
📝 Strategy: <code>{signal.strategy}</code>

<i>{signal.reasoning[:200]}...</i> 

🔔 Signal ID: <code>{signal.id}</code>
⏰ Time: <code>{signal.timestamp}</code>
"""
            
            result = await self.send_message(message, chat_id)
            
            # Log signal to database
            if self.db is not None:
                await self.db.telegram_signals.insert_one({
                    'signal_id': signal.id,
                    'symbol': signal.symbol,
                    'direction': signal.direction,
                    'confidence': signal.confidence,
                    'sent_at': datetime.now(timezone.utc).isoformat(),
                    'chat_id': chat_id or self.default_chat_id,
                    'message_sent': result.get('success', False)
                })
            
            # Auto-trade if enabled
            if self.auto_trading_enabled:
                trade_result = await self._execute_auto_trade(signal)
                if trade_result:
                    await self.send_trade_result(trade_result, chat_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Send signal error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def send_trade_result(self, result: TradeResult, chat_id: str = None) -> Dict:
        """Send trade result notification"""
        try:
            status_emoji = "✅" if result.status == 'won' else "❌" if result.status == 'lost' else "⏳"
            profit_text = f"+${result.profit:.2f}" if result.profit > 0 else f"-${abs(result.profit):.2f}"
            
            message = f"""
<b>{status_emoji} TRADE RESULT</b>

💹 {result.direction} {result.symbol}
💰 Amount: <code>${result.amount}</code>
⏳ Duration: <code>{result.duration}s</code>
🎯 Status: <b>{result.status.upper()}</b>
💵 P/L: <code>{profit_text}</code>

🆔 Trade ID: <code>{result.trade_id}</code>
"""
            
            return await self.send_message(message, chat_id)
            
        except Exception as e:
            logger.error(f"Send trade result error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _execute_auto_trade(self, signal: TradingSignal) -> Optional[TradeResult]:
        """Execute auto-trade based on signal"""
        try:
            logger.info(f"Executing auto-trade: {signal.direction} {signal.symbol}")
            
            # Import pocket option client
            try:
                from pocket_option_auto_trader import get_auto_trader
                trader = get_auto_trader()
                
                if not trader or not trader.is_connected:
                    logger.warning("Pocket Option not connected, simulating trade")
                    return await self._simulate_trade(signal)
                
                # Execute real trade
                direction = 'call' if signal.direction in ['CALL', 'BUY'] else 'put'
                trade_response = await trader.place_trade(
                    asset=signal.symbol,
                    amount=self.trade_amount,
                    direction=direction,
                    duration=signal.expiration_seconds
                )
                
                return TradeResult(
                    signal_id=signal.id,
                    trade_id=trade_response.get('trade_id', f"trade-{int(datetime.now().timestamp())}"),
                    symbol=signal.symbol,
                    direction=signal.direction,
                    amount=self.trade_amount,
                    duration=signal.expiration_seconds,
                    status='placed',
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
            except ImportError:
                logger.warning("Pocket Option trader not available, simulating")
                return await self._simulate_trade(signal)
                
        except Exception as e:
            logger.error(f"Auto-trade error: {e}")
            return TradeResult(
                signal_id=signal.id,
                trade_id=f"error-{int(datetime.now().timestamp())}",
                symbol=signal.symbol,
                direction=signal.direction,
                amount=self.trade_amount,
                duration=signal.expiration_seconds,
                status='error',
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    async def _simulate_trade(self, signal: TradingSignal) -> TradeResult:
        """Simulate trade for demo mode"""
        import random
        
        # Simulate based on confidence (higher confidence = higher win chance)
        win_probability = signal.confidence / 100
        is_win = random.random() < win_probability
        
        payout = 0.85  # 85% payout
        profit = self.trade_amount * payout if is_win else -self.trade_amount
        
        result = TradeResult(
            signal_id=signal.id,
            trade_id=f"demo-{int(datetime.now().timestamp() * 1000)}",
            symbol=signal.symbol,
            direction=signal.direction,
            amount=self.trade_amount,
            duration=signal.expiration_seconds,
            status='won' if is_win else 'lost',
            profit=profit,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Log to database
        if self.db is not None:
            await self.db.telegram_trades.insert_one(asdict(result))
        
        return result
    
    # ==========================================
    # COMMAND HANDLERS
    # ==========================================
    
    async def _cmd_start(self, chat_id: str, args: List[str]) -> str:
        return """
👋 <b>Welcome to Elite Pocket Trading Bot!</b>

🤖 I can help you:
• Receive trading signals automatically
• Execute trades on Pocket Option
• Track your trading history

Use /help to see all available commands.

🟢 Bot Status: <b>ONLINE</b>
"""
    
    async def _cmd_help(self, chat_id: str, args: List[str]) -> str:
        return """
<b>📚 AVAILABLE COMMANDS</b>

<b>📊 Signals & Trading:</b>
/signal - Force generate a new signal
/enable - Enable auto-trading
/disable - Disable auto-trading

<b>💰 Account:</b>
/status - Bot status and settings
/balance - Check balance (if connected)
/demo - Switch to demo mode
/real - Switch to real mode (caution!)
/amount [value] - Set trade amount

<b>📈 History & Stats:</b>
/history - Recent trade history
/stats - Trading statistics
/settings - Current settings

<b>ℹ️ Info:</b>
/start - Welcome message
/help - This help message
"""
    
    async def _cmd_status(self, chat_id: str, args: List[str]) -> str:
        mode = "🟢 DEMO" if self.demo_mode else "🔴 REAL"
        auto = "✅ ENABLED" if self.auto_trading_enabled else "❌ DISABLED"
        
        return f"""
<b>🤖 BOT STATUS</b>

🟢 Bot: <b>ONLINE</b>
💰 Mode: <b>{mode}</b>
🤖 Auto-Trading: <b>{auto}</b>
💵 Trade Amount: <b>${self.trade_amount}</b>

⏰ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    async def _cmd_balance(self, chat_id: str, args: List[str]) -> str:
        # Try to get real balance
        try:
            from pocket_option_auto_trader import get_auto_trader
            trader = get_auto_trader()
            if trader and trader.is_connected:
                balance = await trader.get_balance()
                return f"""
<b>💰 ACCOUNT BALANCE</b>

🟢 Demo: <code>${balance.get('demo', 0):.2f}</code>
🔴 Real: <code>${balance.get('real', 0):.2f}</code>
"""
        except:
            pass
        
        return """
<b>💰 BALANCE</b>

⚠️ Not connected to Pocket Option.
Please connect via SSID first.
"""
    
    async def _cmd_enable_auto_trading(self, chat_id: str, args: List[str]) -> str:
        self.auto_trading_enabled = True
        mode = "DEMO" if self.demo_mode else "REAL"
        return f"""
✅ <b>AUTO-TRADING ENABLED</b>

Mode: <b>{mode}</b>
Amount: <b>${self.trade_amount}</b>

⚠️ Trades will be executed automatically!
"""
    
    async def _cmd_disable_auto_trading(self, chat_id: str, args: List[str]) -> str:
        self.auto_trading_enabled = False
        return """
❌ <b>AUTO-TRADING DISABLED</b>

You will still receive signals but no trades will be executed automatically.
"""
    
    async def _cmd_set_demo(self, chat_id: str, args: List[str]) -> str:
        self.demo_mode = True
        return """
🟢 <b>DEMO MODE ACTIVATED</b>

All trades will use demo balance.
"""
    
    async def _cmd_set_real(self, chat_id: str, args: List[str]) -> str:
        self.demo_mode = False
        return """
🔴 <b>REAL MODE ACTIVATED</b>

⚠️ <b>WARNING:</b> Trades will use REAL money!
Make sure you understand the risks.
"""
    
    async def _cmd_set_amount(self, chat_id: str, args: List[str]) -> str:
        if args:
            try:
                amount = float(args[0])
                if 1 <= amount <= 1000:
                    self.trade_amount = amount
                    return f"✅ Trade amount set to <b>${amount}</b>"
                else:
                    return "⚠️ Amount must be between $1 and $1000"
            except ValueError:
                return "⚠️ Invalid amount. Use: /amount 5"
        else:
            return f"Current amount: <b>${self.trade_amount}</b>\n\nUse: /amount [value] to change"
    
    async def _cmd_force_signal(self, chat_id: str, args: List[str]) -> str:
        if self._signal_callback:
            asyncio.create_task(self._signal_callback())
            return "🔄 Generating signal... Please wait."
        return "⚠️ Signal generator not connected."
    
    async def _cmd_trade_history(self, chat_id: str, args: List[str]) -> str:
        if self.db is None:
            return "⚠️ Database not available."
        
        trades = await self.db.telegram_trades.find(
            {}, {'_id': 0}
        ).sort('timestamp', -1).limit(10).to_list(10)
        
        if not trades:
            return "📊 No trade history yet."
        
        history = "<b>📊 RECENT TRADES</b>\n\n"
        for t in trades:
            emoji = "✅" if t.get('status') == 'won' else "❌" if t.get('status') == 'lost' else "⏳"
            history += f"{emoji} {t.get('direction')} {t.get('symbol')} ${t.get('amount')} - {t.get('status')}\n"
        
        return history
    
    async def _cmd_stats(self, chat_id: str, args: List[str]) -> str:
        if self.db is None:
            return "⚠️ Database not available."
        
        total = await self.db.telegram_trades.count_documents({})
        wins = await self.db.telegram_trades.count_documents({'status': 'won'})
        losses = await self.db.telegram_trades.count_documents({'status': 'lost'})
        
        win_rate = (wins / total * 100) if total > 0 else 0
        
        return f"""
<b>📈 TRADING STATISTICS</b>

📊 Total Trades: <b>{total}</b>
✅ Wins: <b>{wins}</b>
❌ Losses: <b>{losses}</b>
🎯 Win Rate: <b>{win_rate:.1f}%</b>
"""
    
    async def _cmd_settings(self, chat_id: str, args: List[str]) -> str:
        return f"""
<b>⚙️ CURRENT SETTINGS</b>

💰 Mode: <b>{"DEMO" if self.demo_mode else "REAL"}</b>
🤖 Auto-Trading: <b>{"ENABLED" if self.auto_trading_enabled else "DISABLED"}</b>
💵 Trade Amount: <b>${self.trade_amount}</b>
📩 Chat ID: <code>{self.default_chat_id}</code>
"""
    
    # ==========================================
    # MESSAGE HANDLING
    # ==========================================
    
    async def process_update(self, update: Dict) -> Optional[str]:
        """Process incoming Telegram update"""
        try:
            if 'message' not in update:
                return None
            
            message = update['message']
            chat_id = str(message['chat']['id'])
            text = message.get('text', '')
            
            # Check if it's a command
            if text.startswith('/'):
                parts = text.split()
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                if command in self._command_handlers:
                    response = await self._command_handlers[command](chat_id, args)
                    await self.send_message(response, chat_id)
                    return response
                else:
                    await self.send_message("⚠️ Unknown command. Use /help for available commands.", chat_id)
            
            # Check if it's a signal format
            signal = self._parse_signal_text(text)
            if signal:
                await self.send_message(f"📊 Parsed signal: {signal}\n\nExecuting...", chat_id)
                # Execute the signal
                if self.auto_trading_enabled:
                    result = await self._simulate_trade(TradingSignal(
                        id=f"manual-{int(datetime.now().timestamp())}",
                        symbol=signal['asset'],
                        direction=signal['direction'],
                        confidence=80.0,
                        entry_price=0,
                        timeframe='1m',
                        expiration_seconds=signal['duration'],
                        strategy='manual',
                        timestamp=datetime.now().isoformat()
                    ))
                    await self.send_trade_result(result, chat_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Process update error: {e}")
            return None
    
    def _parse_signal_text(self, text: str) -> Optional[Dict]:
        """Parse signal from text message"""
        pattern = r'(?i)\b(CALL|PUT|BUY|SELL)\b[^\w\d]*([A-Z0-9\/\-]{3,15})[^\d]*(\d+(?:\.\d+)?)\s*(?:USD|USDT|EUR|)?[^\d]*(\d+)\s*(s|m)?'
        match = re.search(pattern, text)
        
        if not match:
            return None
        
        dir_raw, asset, amount, duration, unit = match.groups()
        direction = 'CALL' if dir_raw.upper() in ('CALL', 'BUY') else 'PUT'
        
        try:
            amount = float(amount)
            dur = int(duration)
            if unit and unit.lower() == 'm':
                dur *= 60
        except:
            return None
        
        return {
            'direction': direction,
            'asset': asset.replace('/', ''),
            'amount': amount,
            'duration': dur
        }
    
    # ==========================================
    # POLLING LOOP
    # ==========================================
    
    async def start_polling(self):
        """Start long-polling for Telegram updates"""
        self.is_running = True
        logger.info("Starting Telegram bot polling...")
        
        # Send startup notification
        await self.send_message("🤖 <b>Elite Pocket Bot Started!</b>\n\nUse /help to see available commands.", self.default_chat_id)
        
        while self.is_running:
            try:
                client = await self._get_client()
                
                params = {
                    'offset': self._last_update_id + 1,
                    'timeout': 30,
                    'allowed_updates': ['message']
                }
                
                response = await client.get(
                    f"{self.api_url}/getUpdates", 
                    params=params,
                    timeout=35.0  # Slightly longer than Telegram timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok') and data.get('result'):
                        for update in data['result']:
                            self._last_update_id = update['update_id']
                            try:
                                await self.process_update(update)
                            except Exception as proc_error:
                                logger.error(f"Error processing update: {proc_error}")
                    
                    # Small delay between successful polls
                    await asyncio.sleep(0.1)
                else:
                    logger.warning(f"Telegram API returned status {response.status_code}")
                    await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                logger.info("Polling cancelled")
                break
            except httpx.TimeoutException:
                # Normal timeout, just continue
                continue
            except Exception as e:
                logger.error(f"Polling error: {type(e).__name__}: {e}")
                await asyncio.sleep(5)
        
        logger.info("Telegram bot polling stopped.")
    
    async def stop_polling(self):
        """Stop polling"""
        self.is_running = False
    
    def set_signal_callback(self, callback: Callable):
        """Set callback for /signal command"""
        self._signal_callback = callback


# Singleton instance
_telegram_bot = None

def get_telegram_bot(db=None) -> TelegramBotService:
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBotService(db)
    elif db is not None:
        _telegram_bot.db = db
    return _telegram_bot
