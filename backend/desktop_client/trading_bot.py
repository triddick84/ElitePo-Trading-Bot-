"""
Pocket Option Desktop Trading Bot
==================================

Main trading logic using undetected_chromedriver.
Reads WebSocket data via browser performance logs.
Executes trades by clicking UI elements.

Based on VitalySvyatyuk's pocket_option_trading_bot approach.
"""

import asyncio
import base64
import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

from driver import get_driver, ASSET_SYMBOLS
from strategies import CombinedStrategyEngine

logger = logging.getLogger(__name__)

# Trading URLs
DEMO_URL = 'https://pocketoption.com/en/cabinet/demo-quick-high-low/'
LIVE_URL = 'https://pocketoption.com/en/cabinet/quick-high-low/'

# Keyboard mapping for amount input
NUMBERS = {
    '0': '11', '1': '7', '2': '8', '3': '9',
    '4': '4', '5': '5', '6': '6',
    '7': '1', '8': '2', '9': '3',
}


class PocketOptionTradingBot:
    """
    Desktop trading bot for Pocket Option using Chrome automation
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.driver = None
        self.strategy_engine = None
        
        # Trading state
        self.candles: Dict[str, List] = {}  # {asset: [candles]}
        self.actions: Dict[str, datetime] = {}  # {asset: last_action_time}
        self.current_asset = None
        self.period = 60  # Default period in seconds
        self.balance = 0.0
        self.initial_balance = None
        self.is_running = False
        
        # Martingale state
        self.martingale_list = self.config.get('martingale_list', [1, 3, 7, 15, 32, 67])
        self.martingale_enabled = self.config.get('martingale_enabled', False)
        self.martingale_amount_set = True
        self.martingale_last_action_ends = datetime.now()
        
        # Settings from config
        self.account_type = self.config.get('account_type', 'demo')
        self.min_payout = self.config.get('min_payout', 80)
        self.trade_amount = self.config.get('trade_amount', 1)
        self.max_trades_per_hour = self.config.get('max_trades_per_hour', 30)
        self.take_profit = self.config.get('take_profit', 100)
        self.stop_loss = self.config.get('stop_loss', 50)
        self.take_profit_enabled = self.config.get('take_profit_enabled', False)
        self.stop_loss_enabled = self.config.get('stop_loss_enabled', False)
        self.vice_versa = self.config.get('vice_versa', False)  # Invert signals
        
        # Trade tracking
        self.trades_this_hour = 0
        self.hour_start = time.time()
        self.trading_allowed = True
    
    def initialize(self) -> bool:
        """
        Initialize the browser and strategy engine
        """
        try:
            logger.info("🚀 Initializing Pocket Option Trading Bot...")
            
            # Initialize browser
            headless = self.config.get('headless', False)
            self.driver = get_driver(headless=headless)
            
            # Initialize strategy engine
            strategy_config = {
                'use_ma_crossover': self.config.get('use_ma_crossover', True),
                'use_rsi': self.config.get('use_rsi', True),
                'use_enhanced_divergence': self.config.get('use_enhanced_divergence', True),
                'use_professional_scalping': self.config.get('use_professional_scalping', False),
                'fast_ma': self.config.get('fast_ma', 3),
                'slow_ma': self.config.get('slow_ma', 8),
                'rsi_period': self.config.get('rsi_period', 14),
                'timeframe': '1m' if self.period >= 60 else '5s',
                'min_strategy_votes': self.config.get('min_strategy_votes', 2),
                'min_confidence': self.config.get('min_confidence', 65)
            }
            self.strategy_engine = CombinedStrategyEngine(strategy_config)
            
            # Navigate to trading page
            url = DEMO_URL if self.account_type == 'demo' else LIVE_URL
            logger.info(f"📍 Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            logger.info("✅ Bot initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            return False
    
    def hand_delay(self):
        """Simulate human-like delay between actions"""
        time.sleep(random.choice([0.2, 0.3, 0.4, 0.5, 0.6]))
    
    def get_deposit_value(self) -> float:
        """Get current account balance"""
        try:
            deposit = self.driver.find_element(
                By.CSS_SELECTOR, 
                'body > div.wrapper > div.wrapper__top > header > div.right-block.js-right-block > '
                'div.right-block__item.js-drop-down-modal-open > div > div.balance-info-block__data > '
                'div.balance-info-block__balance > span'
            )
            return float(deposit.text.replace(',', '').replace(' ', ''))
        except Exception as e:
            logger.debug(f"Could not get balance: {e}")
            return 0.0
    
    def get_current_payout(self) -> int:
        """Get current asset payout percentage"""
        try:
            payout = self.driver.find_element(By.CLASS_NAME, 'value__val-start').text
            return int(payout.replace('%', '').strip())
        except:
            return 0
    
    def check_payout(self, asset: str) -> bool:
        """Check if current payout meets minimum requirement"""
        payout = self.get_current_payout()
        if payout >= self.min_payout:
            return True
        logger.info(f"⚠️ Payout {payout}% < {self.min_payout}% for {asset}")
        self.actions[asset] = datetime.now() + timedelta(minutes=1)
        return False
    
    def set_estimation_icon(self):
        """Ensure time estimation is in correct mode"""
        try:
            time_style = self.driver.find_element(
                By.CSS_SELECTOR, 
                '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--expiration-inputs > '
                'div.block__control.control > div.control-buttons__wrapper > div > a > div > div > svg'
            )
            if 'exp-mode-2.svg' in time_style.get_attribute('data-src'):
                time_style.click()
        except:
            pass
    
    def set_amount_icon(self):
        """Ensure amount display shows currency not percentage"""
        try:
            amount_style = self.driver.find_element(
                By.CSS_SELECTOR, 
                '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--bet-amount > '
                'div.block__control.control > div.control-buttons__wrapper > div > a'
            )
            try:
                amount_style.find_element(By.CLASS_NAME, 'currency-icon--usd')
            except NoSuchElementException:
                amount_style.click()
        except:
            pass
    
    def set_trade_amount(self, amount: int):
        """Set the trade amount via keyboard input"""
        try:
            self.set_amount_icon()
            
            amount_input = self.driver.find_element(
                By.CSS_SELECTOR,
                '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--bet-amount > '
                'div.block__control.control > div.control__value.value.value--several-items > div > input[type=text]'
            )
            amount_input.click()
            time.sleep(0.5)
            
            base = '#modal-root > div > div > div > div > div > div:nth-child(2) > div.panel-collapse__body > div > div > div:nth-child(%s) > div'
            
            for digit in str(amount):
                self.driver.find_element(By.CSS_SELECTOR, base % NUMBERS[digit]).click()
                self.hand_delay()
            
            logger.info(f"💰 Trade amount set to ${amount}")
            
        except Exception as e:
            logger.error(f"Could not set trade amount: {e}")
    
    def execute_trade(self, direction: str, asset: str = None) -> bool:
        """
        Execute a trade by clicking the CALL or PUT button
        
        Args:
            direction: 'CALL' or 'PUT'
            asset: Asset being traded (for logging)
        
        Returns:
            True if trade executed successfully
        """
        asset = asset or self.current_asset
        
        # Check if we can trade
        if asset and asset in self.actions:
            if self.actions[asset] + timedelta(seconds=self.period * 2) > datetime.now():
                logger.debug(f"Recent trade on {asset}, waiting...")
                return False
        
        # Check payout
        if not self.check_payout(asset):
            return False
        
        # Check hourly limit
        self._reset_hourly_counter()
        if self.trades_this_hour >= self.max_trades_per_hour:
            logger.warning(f"⚠️ Hourly trade limit reached ({self.max_trades_per_hour})")
            return False
        
        # Apply vice versa if enabled
        if self.vice_versa:
            direction = 'PUT' if direction == 'CALL' else 'CALL'
        
        try:
            button_class = f'btn-{direction.lower()}'
            self.driver.find_element(By.CLASS_NAME, button_class).click()
            
            self.actions[asset] = datetime.now()
            self.trades_this_hour += 1
            self.martingale_amount_set = False
            
            logger.info(f"✅ {direction} executed on {asset} @ {datetime.now().strftime('%H:%M:%S')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to execute trade: {e}")
            return False
    
    def process_websocket_data(self):
        """
        Process WebSocket data from browser performance logs
        This is the core method that reads market data
        """
        try:
            for ws_data in self.driver.get_log('performance'):
                message = json.loads(ws_data['message'])['message']
                response = message.get('params', {}).get('response', {})
                
                if response.get('opcode', 0) == 2:
                    try:
                        payload_str = base64.b64decode(response['payloadData']).decode('utf-8')
                        data = json.loads(payload_str)
                        
                        # Handle history data
                        if 'history' in data:
                            asset = data.get('asset', 'UNKNOWN')
                            self.period = data.get('period', 60)
                            
                            # Build candle list from history
                            candles = []
                            for tstamp, value in data['history']:
                                candles.append({
                                    'timestamp': int(float(tstamp)),
                                    'open': value,
                                    'close': value,
                                    'high': value,
                                    'low': value
                                })
                            
                            # Add candles from data if available
                            if 'candles' in data:
                                for c in data['candles']:
                                    candles.append({
                                        'timestamp': int(c[0]),
                                        'open': c[1],
                                        'close': c[2],
                                        'high': c[3],
                                        'low': c[4]
                                    })
                            
                            self.candles[asset] = candles
                            self.current_asset = asset
                            logger.debug(f"📊 Loaded {len(candles)} candles for {asset}")
                        
                        # Handle real-time updates
                        if isinstance(data, list) and len(data) >= 3:
                            try:
                                asset, timestamp, value = data[0], data[1], data[2]
                                
                                if asset in self.candles:
                                    candles = self.candles[asset]
                                    tstamp = int(float(timestamp))
                                    
                                    # Update last candle or add new one
                                    if candles and tstamp % self.period != 0:
                                        # Update existing candle
                                        candles[-1]['close'] = value
                                        if value > candles[-1]['high']:
                                            candles[-1]['high'] = value
                                        if value < candles[-1]['low']:
                                            candles[-1]['low'] = value
                                    elif tstamp % self.period == 0:
                                        # New candle
                                        if not candles or tstamp != candles[-1]['timestamp']:
                                            candles.append({
                                                'timestamp': tstamp,
                                                'open': value,
                                                'close': value,
                                                'high': value,
                                                'low': value
                                            })
                                            # Trigger strategy check on new candle
                                            self._check_strategies(asset)
                            except (ValueError, IndexError):
                                pass
                    
                    except Exception as e:
                        logger.debug(f"Error processing WS data: {e}")
        
        except Exception as e:
            logger.debug(f"Error reading performance logs: {e}")
    
    def _check_strategies(self, asset: str):
        """Check strategies and execute trade if signal found"""
        if not self.trading_allowed:
            return
        
        candles = self.candles.get(asset, [])
        if len(candles) < 50:
            return
        
        # Generate signal from strategy engine
        signal = self.strategy_engine.generate_signal(candles, asset)
        
        if signal:
            logger.info(f"📡 Signal: {signal['direction']} on {asset} ({signal['confidence']:.0f}% confidence)")
            logger.info(f"   Reasoning: {signal.get('reasoning', 'N/A')}")
            
            # Execute trade
            if self.execute_trade(signal['direction'], asset):
                # Update martingale
                if self.martingale_enabled:
                    self.martingale_last_action_ends = datetime.now() + timedelta(seconds=self.period + 5)
    
    def _reset_hourly_counter(self):
        """Reset hourly trade counter"""
        if time.time() - self.hour_start >= 3600:
            self.trades_this_hour = 0
            self.hour_start = time.time()
    
    def handle_martingale(self):
        """Handle Martingale bet progression"""
        if not self.martingale_enabled:
            return
        
        if self.martingale_last_action_ends > datetime.now():
            return
        
        if self.martingale_amount_set:
            return
        
        try:
            # Check closed trades tab
            closed_tab = self.driver.find_element(
                By.CSS_SELECTOR,
                '#bar-chart > div > div > div.right-widget-container > div > div.widget-slot__header > '
                'div.divider > ul > li:nth-child(2) > a'
            )
            closed_tab_parent = closed_tab.find_element(By.XPATH, '..')
            if closed_tab_parent.get_attribute('class') == '':
                closed_tab_parent.click()
            
            self.set_amount_icon()
            
            closed_trades = self.driver.find_elements(By.CLASS_NAME, 'deals-list__item')
            if not closed_trades:
                self.martingale_amount_set = True
                return
            
            last_trade = closed_trades[0].text.split('\n')
            
            amount_input = self.driver.find_element(
                By.CSS_SELECTOR,
                '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--bet-amount > '
                'div.block__control.control > div.control__value.value.value--several-items > div > input[type=text]'
            )
            current_amount = int(float(amount_input.get_attribute('value').replace(',', '')))
            
            base = '#modal-root > div > div > div > div > div > div:nth-child(2) > div.panel-collapse__body > div > div > div:nth-child(%s) > div'
            
            # Check if win or loss
            if '$0' not in last_trade[4] and '$\u202f0' not in last_trade[4]:  # Win
                if current_amount > self.martingale_list[0]:
                    # Reset to initial amount
                    amount_input.click()
                    self.hand_delay()
                    for digit in str(self.martingale_list[0]):
                        self.driver.find_element(By.CSS_SELECTOR, base % NUMBERS[digit]).click()
                        self.hand_delay()
                    logger.info(f"🎉 WIN! Reset to ${self.martingale_list[0]}")
            
            elif '$0' in last_trade[3] or '$\u202f0' in last_trade[3]:  # Loss
                # Increase bet
                amount_input.click()
                time.sleep(0.5)
                
                if current_amount in self.martingale_list:
                    idx = self.martingale_list.index(current_amount)
                    if idx + 1 < len(self.martingale_list):
                        next_amount = self.martingale_list[idx + 1]
                        
                        # Check if we have enough balance
                        balance = self.get_deposit_value()
                        if next_amount > balance:
                            logger.warning(f"⚠️ Martingale ${next_amount} exceeds balance ${balance}")
                        else:
                            for digit in str(next_amount):
                                self.driver.find_element(By.CSS_SELECTOR, base % NUMBERS[digit]).click()
                                self.hand_delay()
                            logger.info(f"📈 LOSS! Martingale to ${next_amount}")
                else:
                    # Reset to initial
                    for digit in str(self.martingale_list[0]):
                        self.driver.find_element(By.CSS_SELECTOR, base % NUMBERS[digit]).click()
                        self.hand_delay()
            
            closed_tab_parent.click()
            self.martingale_amount_set = True
            
        except Exception as e:
            logger.debug(f"Martingale handling error: {e}")
            self.martingale_amount_set = True
    
    def check_take_profit_stop_loss(self):
        """Check take profit and stop loss conditions"""
        balance = self.get_deposit_value()
        
        if balance == 0:
            return
        
        if self.initial_balance is None:
            self.initial_balance = balance
            logger.info(f"💰 Initial balance: ${self.initial_balance:.2f}")
            return
        
        self.balance = balance
        profit = balance - self.initial_balance
        
        if self.take_profit_enabled and profit >= self.take_profit:
            logger.info(f"🎯 Take profit reached! Profit: ${profit:.2f}")
            self.trading_allowed = False
        
        if self.stop_loss_enabled and profit <= -self.stop_loss:
            logger.info(f"🛑 Stop loss reached! Loss: ${abs(profit):.2f}")
            self.trading_allowed = False
    
    def run(self):
        """Main bot loop"""
        if not self.driver:
            if not self.initialize():
                return
        
        logger.info("🤖 Bot started - monitoring for signals...")
        self.is_running = True
        
        try:
            while self.is_running:
                # Process WebSocket data
                self.process_websocket_data()
                
                # Handle Martingale
                if self.martingale_enabled:
                    self.handle_martingale()
                
                # Check take profit / stop loss
                self.check_take_profit_stop_loss()
                
                # Small delay to prevent CPU overuse
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("👋 Stopping bot...")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the bot and clean up"""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        logger.info("🛑 Bot stopped")


def main():
    """Entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pocket Option Trading Bot')
    parser.add_argument('--demo', action='store_true', help='Use demo account')
    parser.add_argument('--live', action='store_true', help='Use live account')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--amount', type=int, default=1, help='Trade amount')
    parser.add_argument('--martingale', action='store_true', help='Enable Martingale')
    
    args = parser.parse_args()
    
    config = {
        'account_type': 'live' if args.live else 'demo',
        'headless': args.headless,
        'trade_amount': args.amount,
        'martingale_enabled': args.martingale,
        'use_ma_crossover': True,
        'use_rsi': True,
        'use_enhanced_divergence': True,
        'min_confidence': 65
    }
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    bot = PocketOptionTradingBot(config)
    bot.run()


if __name__ == '__main__':
    main()
