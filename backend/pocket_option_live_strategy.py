"""
Pocket Option Live Trading Strategy Integration
Connects live Pocket Option data with our signal generation strategies

Based on the bot's trading strategies:
- Moving Averages Crossing (SMA/EMA/WMA)
- RSI Strategy
- Combined confirmations
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Optional, List, Callable
import logging

from pocket_option_live import (
    PocketOptionBridge, 
    PocketOptionAsset,
    get_pocket_option_bridge
)

logger = logging.getLogger(__name__)


# ============================================================================
# MOVING AVERAGES CALCULATIONS
# ============================================================================

def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return None
    
    multiplier = 2 / (period + 1)
    sma = sum(prices[:period]) / period
    ema = sma
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def calculate_wma(prices: List[float], period: int) -> Optional[float]:
    """Calculate Weighted Moving Average"""
    if len(prices) < period:
        return None
    
    weights = list(range(1, period + 1))
    weighted_prices = [prices[i] * weights[i] for i in range(-period, 0)]
    return sum(weighted_prices) / sum(weights)


def calculate_ma(prices: List[float], period: int, ma_type: str = 'SMA') -> Optional[float]:
    """Calculate Moving Average of specified type"""
    if ma_type == 'EMA':
        return calculate_ema(prices, period)
    elif ma_type == 'WMA':
        return calculate_wma(prices, period)
    else:  # SMA
        return calculate_sma(prices, period)


# ============================================================================
# RSI CALCULATION
# ============================================================================

def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """Calculate RSI (Relative Strength Index)"""
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    gains = []
    losses = []
    
    # Calculate initial gains and losses
    for i in range(1, period + 1):
        delta = prices[i] - prices[i - 1]
        if delta > 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))
    
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    
    rsi_values = [None] * period
    
    # Calculate first RSI
    if avg_loss == 0:
        rsi_values.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    
    # Calculate subsequent RSI values
    for i in range(period + 1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))
        
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_values.append(rsi)
    
    return rsi_values


# ============================================================================
# POCKET OPTION LIVE STRATEGY
# ============================================================================

class PocketOptionLiveStrategy:
    """
    Live trading strategy using Pocket Option data
    
    Strategies implemented:
    1. Moving Averages Crossing
    2. RSI Confirmation
    3. Combined signals
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.bridge = get_pocket_option_bridge()
        
        # Register callback for live signals
        self.bridge.register_signal_callback(self._on_new_data)
        
        # Signal tracking
        self.last_signals: Dict[str, Dict] = {}
        self.signal_callbacks: List[Callable] = []
        
        logger.info("📡 Pocket Option Live Strategy initialized")
        logger.info(f"   MA Settings: Fast={self.config['fast_ma']} {self.config['fast_ma_type']}, "
                    f"Slow={self.config['slow_ma']} {self.config['slow_ma_type']}")
        if self.config['rsi_enabled']:
            logger.info(f"   RSI Settings: Period={self.config['rsi_period']}, "
                        f"Upper={self.config['rsi_upper']}, Lower={100-self.config['rsi_upper']}")
    
    def _default_config(self) -> Dict:
        """Default strategy configuration"""
        return {
            'fast_ma': 3,
            'fast_ma_type': 'SMA',
            'slow_ma': 8,
            'slow_ma_type': 'SMA',
            'rsi_enabled': True,
            'rsi_period': 14,
            'rsi_upper': 70,
            'rsi_call_sign': '>',  # Call when RSI > upper
            'vice_versa': False,
            'min_payout': 80,
            'min_confidence': 75
        }
    
    def register_signal_callback(self, callback: Callable):
        """Register callback for new signals"""
        self.signal_callbacks.append(callback)
    
    def _on_new_data(self, asset: str, asset_data: PocketOptionAsset):
        """Called when new data arrives from bridge"""
        signal = self.analyze_asset(asset)
        
        if signal and signal.get('action'):
            # Notify callbacks
            for callback in self.signal_callbacks:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"Signal callback error: {e}")
    
    def moving_averages_cross(self, prices: List[float]) -> Optional[str]:
        """
        Detect Moving Averages crossing signal
        
        Returns:
            'call' for bullish cross, 'put' for bearish cross, None otherwise
        """
        fast_ma = self.config['fast_ma']
        slow_ma = self.config['slow_ma']
        fast_type = self.config['fast_ma_type']
        slow_type = self.config['slow_ma_type']
        
        if fast_ma >= slow_ma:
            logger.warning("Fast MA period must be less than Slow MA period")
            return None
        
        if len(prices) < slow_ma + 2:
            return None
        
        # Calculate current and previous MAs
        fast_current = calculate_ma(prices, fast_ma, fast_type)
        fast_previous = calculate_ma(prices[:-1], fast_ma, fast_type)
        slow_current = calculate_ma(prices, slow_ma, slow_type)
        slow_previous = calculate_ma(prices[:-1], slow_ma, slow_type)
        
        if None in [fast_current, fast_previous, slow_current, slow_previous]:
            return None
        
        # Detect crossover
        if fast_previous < slow_previous and fast_current > slow_current:
            return 'call'  # Bullish cross
        elif fast_previous > slow_previous and fast_current < slow_current:
            return 'put'  # Bearish cross
        
        return None
    
    def rsi_confirmation(self, prices: List[float], action: str) -> Optional[str]:
        """
        Confirm signal with RSI
        
        Returns:
            Original action if confirmed, None otherwise
        """
        if not self.config['rsi_enabled']:
            return action
        
        rsi_values = calculate_rsi(prices, self.config['rsi_period'])
        
        if not rsi_values or rsi_values[-1] is None:
            return action  # Return action if RSI can't be calculated
        
        current_rsi = rsi_values[-1]
        upper = self.config['rsi_upper']
        lower = 100 - upper
        call_sign = self.config['rsi_call_sign']
        
        if action == 'call':
            if call_sign == '>':
                if current_rsi > upper:
                    return 'call'
            else:  # '<'
                if current_rsi < lower:
                    return 'call'
        elif action == 'put':
            if call_sign == '>':
                if current_rsi < lower:
                    return 'put'
            else:  # '<'
                if current_rsi > upper:
                    return 'put'
        
        return None
    
    def analyze_asset(self, asset: str) -> Optional[Dict]:
        """
        Analyze an asset for trading signals
        
        Returns:
            Signal dictionary or None
        """
        try:
            # Get candle data from bridge
            candles = self.bridge.get_candles(asset)
            
            if not candles or len(candles) < self.config['slow_ma'] + 10:
                return None
            
            # Extract close prices
            prices = [c['close'] for c in candles]
            
            # Check for MA crossover
            action = self.moving_averages_cross(prices)
            
            if not action:
                return None
            
            # RSI confirmation
            if self.config['rsi_enabled']:
                action = self.rsi_confirmation(prices, action)
                if not action:
                    return None
            
            # Apply vice versa if enabled
            if self.config['vice_versa']:
                action = 'call' if action == 'put' else 'put'
            
            # Calculate confidence based on indicators
            rsi_values = calculate_rsi(prices, self.config['rsi_period'])
            current_rsi = rsi_values[-1] if rsi_values else 50
            
            # Confidence calculation
            confidence = 75  # Base confidence
            
            # RSI extremes boost confidence
            if current_rsi and (current_rsi < 30 or current_rsi > 70):
                confidence += 5
            if current_rsi and (current_rsi < 20 or current_rsi > 80):
                confidence += 5
            
            # MA divergence boost
            fast_ma_val = calculate_ma(prices, self.config['fast_ma'], self.config['fast_ma_type'])
            slow_ma_val = calculate_ma(prices, self.config['slow_ma'], self.config['slow_ma_type'])
            
            if fast_ma_val and slow_ma_val:
                divergence = abs(fast_ma_val - slow_ma_val) / slow_ma_val * 100
                if divergence > 0.1:
                    confidence += 3
                if divergence > 0.2:
                    confidence += 2
            
            confidence = min(confidence, 95)
            
            # Build signal
            signal = {
                'action': action,
                'direction': 'BUY' if action == 'call' else 'SELL',
                'asset': asset,
                'confidence': confidence,
                'probability': confidence,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'strategy': 'pocket_option_live_ma_rsi',
                'timeframe': 'live',
                'current_price': prices[-1],
                'indicators': {
                    'rsi': round(current_rsi, 2) if current_rsi else None,
                    'fast_ma': round(fast_ma_val, 5) if fast_ma_val else None,
                    'slow_ma': round(slow_ma_val, 5) if slow_ma_val else None,
                    'ma_divergence_pct': round(divergence, 4) if fast_ma_val and slow_ma_val else None
                },
                'config': {
                    'fast_ma': f"{self.config['fast_ma']} {self.config['fast_ma_type']}",
                    'slow_ma': f"{self.config['slow_ma']} {self.config['slow_ma_type']}",
                    'rsi_enabled': self.config['rsi_enabled']
                },
                'source': 'pocket_option_live'
            }
            
            self.last_signals[asset] = signal
            
            logger.info(f"🎯 LIVE SIGNAL: {action.upper()} {asset} @ {prices[-1]} ({confidence}%)")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing {asset}: {e}")
            return None
    
    def analyze_all_assets(self) -> List[Dict]:
        """Analyze all tracked assets for signals"""
        signals = []
        
        for asset in self.bridge.parser.assets.keys():
            signal = self.analyze_asset(asset)
            if signal:
                signals.append(signal)
        
        return signals
    
    def get_dataframe(self, asset: str) -> Optional[pd.DataFrame]:
        """Get candle data as DataFrame for advanced analysis"""
        return self.bridge.get_dataframe(asset)
    
    def update_config(self, new_config: Dict) -> bool:
        """Update strategy configuration"""
        for key, value in new_config.items():
            if key in self.config:
                self.config[key] = value
        logger.info(f"📝 Live strategy config updated: {new_config}")
        return True
    
    def get_status(self) -> Dict:
        """Get strategy status"""
        return {
            'config': self.config,
            'bridge_connected': self.bridge.is_connected,
            'assets_tracked': list(self.bridge.parser.assets.keys()),
            'last_signals': self.last_signals
        }


# ============================================================================
# INTEGRATION WITH EXISTING STRATEGIES
# ============================================================================

class PocketOptionSignalIntegration:
    """
    Integration layer between Pocket Option live data and our signal system
    """
    
    def __init__(self):
        self.live_strategy = PocketOptionLiveStrategy()
        self.bridge = get_pocket_option_bridge()
        
        # Track integration status
        self.integration_active = False
        self.signals_generated = 0
    
    def start_integration(self):
        """Start the live integration"""
        self.integration_active = True
        logger.info("🚀 Pocket Option live integration started")
    
    def stop_integration(self):
        """Stop the live integration"""
        self.integration_active = False
        logger.info("⏹️ Pocket Option live integration stopped")
    
    def get_live_signal(self, asset: str) -> Optional[Dict]:
        """
        Get signal using live Pocket Option data
        
        Falls back to standard data if live not available
        """
        if not self.bridge.is_connected:
            logger.debug(f"Bridge not connected, cannot get live signal for {asset}")
            return None
        
        signal = self.live_strategy.analyze_asset(asset)
        
        if signal:
            self.signals_generated += 1
            signal['signal_number'] = self.signals_generated
        
        return signal
    
    def get_all_live_signals(self) -> List[Dict]:
        """Get signals from all tracked assets"""
        return self.live_strategy.analyze_all_assets()
    
    def get_status(self) -> Dict:
        """Get integration status"""
        return {
            'integration_active': self.integration_active,
            'bridge_status': self.bridge.get_status(),
            'strategy_status': self.live_strategy.get_status(),
            'signals_generated': self.signals_generated
        }


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_live_strategy: Optional[PocketOptionLiveStrategy] = None
_signal_integration: Optional[PocketOptionSignalIntegration] = None


def get_live_strategy() -> PocketOptionLiveStrategy:
    """Get singleton live strategy instance"""
    global _live_strategy
    if _live_strategy is None:
        _live_strategy = PocketOptionLiveStrategy()
    return _live_strategy


def get_signal_integration() -> PocketOptionSignalIntegration:
    """Get singleton signal integration instance"""
    global _signal_integration
    if _signal_integration is None:
        _signal_integration = PocketOptionSignalIntegration()
    return _signal_integration
