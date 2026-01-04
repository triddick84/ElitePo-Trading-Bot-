"""
Desktop Client Strategy Integration
====================================

Integrates both simple strategies and advanced strategies from the backend.
"""

import sys
import os
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Add backend to path for strategy imports
BACKEND_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)


class SimpleMAStrategy:
    """
    Simple Moving Average Crossover Strategy
    Based on VitalySvyatyuk's original approach
    """
    
    def __init__(self, fast_ma: int = 3, slow_ma: int = 8):
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.name = "Simple MA Crossover"
    
    def calculate_sma(self, values: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(values) < period:
            return 0
        return sum(values[-period:]) / period
    
    def calculate_ema(self, values: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(values) < period:
            return 0
        
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period  # Start with SMA
        
        for price in values[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def generate_signal(self, candles: List[Dict]) -> Optional[Dict]:
        """
        Generate signal based on MA crossover
        
        Args:
            candles: List of candle data [{timestamp, open, close, high, low}, ...]
        
        Returns:
            Signal dict or None
        """
        if len(candles) < self.slow_ma + 2:
            return None
        
        # Extract close prices
        closes = [c['close'] for c in candles]
        
        # Calculate current and previous MAs
        fast_ma_current = self.calculate_sma(closes, self.fast_ma)
        slow_ma_current = self.calculate_sma(closes, self.slow_ma)
        
        fast_ma_prev = self.calculate_sma(closes[:-1], self.fast_ma)
        slow_ma_prev = self.calculate_sma(closes[:-1], self.slow_ma)
        
        signal = None
        
        # Bullish crossover (fast crosses above slow)
        if fast_ma_prev <= slow_ma_prev and fast_ma_current > slow_ma_current:
            signal = {
                'direction': 'CALL',
                'confidence': 70,
                'strategy': self.name,
                'reasoning': f'Fast MA ({self.fast_ma}) crossed above Slow MA ({self.slow_ma})'
            }
        
        # Bearish crossover (fast crosses below slow)
        elif fast_ma_prev >= slow_ma_prev and fast_ma_current < slow_ma_current:
            signal = {
                'direction': 'PUT',
                'confidence': 70,
                'strategy': self.name,
                'reasoning': f'Fast MA ({self.fast_ma}) crossed below Slow MA ({self.slow_ma})'
            }
        
        return signal


class SimpleRSIStrategy:
    """
    Simple RSI Overbought/Oversold Strategy
    """
    
    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = "Simple RSI"
    
    def calculate_rsi(self, closes: List[float]) -> float:
        """Calculate RSI"""
        if len(closes) < self.period + 1:
            return 50
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas[-self.period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-self.period:]]
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, candles: List[Dict]) -> Optional[Dict]:
        """Generate signal based on RSI levels"""
        if len(candles) < self.period + 2:
            return None
        
        closes = [c['close'] for c in candles]
        rsi = self.calculate_rsi(closes)
        
        signal = None
        
        if rsi < self.oversold:
            signal = {
                'direction': 'CALL',
                'confidence': 65 + (self.oversold - rsi),
                'strategy': self.name,
                'reasoning': f'RSI={rsi:.1f} < {self.oversold} (oversold)'
            }
        elif rsi > self.overbought:
            signal = {
                'direction': 'PUT',
                'confidence': 65 + (rsi - self.overbought),
                'strategy': self.name,
                'reasoning': f'RSI={rsi:.1f} > {self.overbought} (overbought)'
            }
        
        return signal


class EnhancedStrategyWrapper:
    """
    Wrapper for advanced strategies from the backend
    """
    
    def __init__(self, strategy_name: str = 'enhanced_divergence', timeframe: str = '1m'):
        self.strategy_name = strategy_name
        self.timeframe = timeframe
        self.strategy = None
        self._load_strategy()
    
    def _load_strategy(self):
        """Load the advanced strategy from backend"""
        try:
            if self.strategy_name == 'enhanced_divergence':
                from enhanced_ultra_short_strategy import EnhancedUltraShortStrategy
                self.strategy = EnhancedUltraShortStrategy(self.timeframe)
                self.name = self.strategy.name
            elif self.strategy_name == 'professional_scalping':
                from professional_scalping_strategy import ProfessionalScalpingStrategy
                self.strategy = ProfessionalScalpingStrategy(self.timeframe)
                self.name = self.strategy.name
            else:
                logger.warning(f"Unknown strategy: {self.strategy_name}")
                self.name = f"Unknown ({self.strategy_name})"
        except ImportError as e:
            logger.warning(f"Could not import strategy {self.strategy_name}: {e}")
            self.name = "Fallback Strategy"
    
    def candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert candle list to pandas DataFrame"""
        df = pd.DataFrame(candles)
        
        # Ensure required columns
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in df.columns:
                df[col] = df.get('close', 0)
        
        if 'volume' not in df.columns:
            df['volume'] = 1.0
        
        # Convert to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def generate_signal(self, candles: List[Dict], symbol: str = "UNKNOWN") -> Optional[Dict]:
        """Generate signal using advanced strategy"""
        if not self.strategy:
            return None
        
        if len(candles) < 50:
            return None
        
        try:
            df = self.candles_to_dataframe(candles)
            signal = self.strategy.generate_signal(df, symbol)
            return signal
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return None


class CombinedStrategyEngine:
    """
    Combines multiple strategies and generates consensus signals
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.strategies = []
        self._init_strategies()
    
    def _init_strategies(self):
        """Initialize selected strategies based on config"""
        # Simple strategies (always available)
        if self.config.get('use_ma_crossover', True):
            fast = self.config.get('fast_ma', 3)
            slow = self.config.get('slow_ma', 8)
            self.strategies.append(SimpleMAStrategy(fast, slow))
        
        if self.config.get('use_rsi', True):
            period = self.config.get('rsi_period', 14)
            self.strategies.append(SimpleRSIStrategy(period))
        
        # Advanced strategies (if available)
        if self.config.get('use_enhanced_divergence', True):
            try:
                timeframe = self.config.get('timeframe', '1m')
                self.strategies.append(EnhancedStrategyWrapper('enhanced_divergence', timeframe))
            except Exception as e:
                logger.warning(f"Could not load enhanced_divergence strategy: {e}")
        
        if self.config.get('use_professional_scalping', False):
            try:
                timeframe = self.config.get('timeframe', '1m')
                self.strategies.append(EnhancedStrategyWrapper('professional_scalping', timeframe))
            except Exception as e:
                logger.warning(f"Could not load professional_scalping strategy: {e}")
        
        logger.info(f"Initialized {len(self.strategies)} strategies: {[s.name for s in self.strategies]}")
    
    def generate_signal(self, candles: List[Dict], symbol: str = "UNKNOWN") -> Optional[Dict]:
        """
        Generate consensus signal from all strategies
        
        Requires majority agreement for signal generation
        """
        if len(candles) < 50:
            return None
        
        call_votes = []
        put_votes = []
        all_signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(candles, symbol) if hasattr(strategy, 'generate_signal') else strategy.generate_signal(candles)
                
                if signal:
                    all_signals.append({
                        'strategy': strategy.name,
                        'direction': signal['direction'],
                        'confidence': signal.get('confidence', 50)
                    })
                    
                    if signal['direction'] == 'CALL':
                        call_votes.append(signal)
                    elif signal['direction'] == 'PUT':
                        put_votes.append(signal)
            except Exception as e:
                logger.debug(f"Strategy {strategy.name} error: {e}")
        
        # Determine consensus
        min_votes = self.config.get('min_strategy_votes', 2)
        min_confidence = self.config.get('min_confidence', 65)
        
        direction = None
        confidence = 0
        reasoning = []
        
        if len(call_votes) >= min_votes and len(call_votes) > len(put_votes):
            direction = 'CALL'
            confidence = sum(s['confidence'] for s in call_votes) / len(call_votes)
            reasoning = [s.get('reasoning', s.get('strategy', '')) for s in call_votes]
        elif len(put_votes) >= min_votes and len(put_votes) > len(call_votes):
            direction = 'PUT'
            confidence = sum(s['confidence'] for s in put_votes) / len(put_votes)
            reasoning = [s.get('reasoning', s.get('strategy', '')) for s in put_votes]
        
        if direction and confidence >= min_confidence:
            return {
                'direction': direction,
                'confidence': round(confidence, 1),
                'symbol': symbol,
                'strategy': 'Combined Strategy Engine',
                'votes': {
                    'call': len(call_votes),
                    'put': len(put_votes)
                },
                'all_signals': all_signals,
                'reasoning': '; '.join(reasoning[:3])
            }
        
        return None
