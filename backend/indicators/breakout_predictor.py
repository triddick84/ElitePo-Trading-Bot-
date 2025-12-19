"""
Enhanced Breakout Predictor with Alerts
Multi-timeframe Breakout Detection with Probability Scoring
Optimized for 5-second timeframe trading strategies

Features:
- Bullish/Bearish breakout detection
- Probability scoring engine
- Multi-level support/resistance
- Real-time signal generation < 100ms latency
- Webhook integration for external APIs
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
import logging
import time
from collections import deque
import asyncio

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION CLASSES
# ============================================================================

@dataclass
class BreakoutSettings:
    """Breakout detection configuration"""
    enabled: bool = True
    bullish_alerts: bool = True
    bearish_alerts: bool = True
    lookback_period: int = 20
    percentage_step: float = 1.0
    number_of_lines: int = 5
    # 5-second optimization
    buffer_size: int = 5000  # max bars to keep in memory
    min_breakout_strength: float = 0.5  # minimum strength to trigger signal
    confirmation_bars: int = 1  # bars to confirm breakout (1 for 5s speed)
    

@dataclass
class WebhookSettings:
    """Webhook integration configuration"""
    enabled: bool = False
    webhook_url: str = ""
    json_format: bool = True
    mt_integration: bool = False
    retry_attempts: int = 3
    timeout_ms: int = 100  # Ultra-low latency requirement


@dataclass
class AlertSettings:
    """Alert message configuration"""
    include_ticker: bool = True
    include_price: bool = True
    include_timestamp: bool = True
    include_confidence: bool = True
    custom_message_template: str = ""


@dataclass
class BreakoutSignal:
    """Breakout signal output structure"""
    ticker: str
    signal: str  # "BUY" or "SELL"
    price: float
    timestamp: str
    message: str
    timeframe: str
    breakout_level: float
    confidence_score: float
    breakout_type: str  # "bullish" or "bearish"
    strength: float
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    win_probability: float = 0.0
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json_webhook(self) -> Dict:
        """Format for JSON webhook"""
        return {
            "ticker": self.ticker,
            "signal": self.signal,
            "price": self.price,
            "timestamp": self.timestamp,
            "message": self.message,
            "timeframe": self.timeframe,
            "breakout_level": self.breakout_level,
            "confidence_score": self.confidence_score,
            "strength": self.strength,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels
        }
    
    def to_mt4_format(self) -> str:
        """Format for MT4/MT5 integration"""
        return f"{self.signal}|{self.ticker}|{self.price}|{self.breakout_level}|{self.confidence_score}|{self.timestamp}"


# ============================================================================
# BREAKOUT LEVEL CALCULATOR
# ============================================================================

class BreakoutLevelCalculator:
    """Calculates dynamic support/resistance levels using percentage steps"""
    
    def __init__(self, percentage_step: float = 1.0, num_levels: int = 5):
        self.percentage_step = percentage_step
        self.num_levels = num_levels
    
    def calculate_levels(self, current_price: float) -> Tuple[List[float], List[float]]:
        """
        Calculate support and resistance levels based on percentage steps
        
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        step = current_price * (self.percentage_step / 100)
        
        support_levels = []
        resistance_levels = []
        
        for i in range(1, self.num_levels + 1):
            support_levels.append(round(current_price - (step * i), 5))
            resistance_levels.append(round(current_price + (step * i), 5))
        
        return support_levels, resistance_levels
    
    def calculate_dynamic_levels(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[List[float], List[float]]:
        """
        Calculate dynamic S/R levels based on price action
        Uses swing highs/lows and volume-weighted levels
        """
        if len(df) < lookback:
            return [], []
        
        recent = df.tail(lookback)
        
        # Find swing highs (resistance)
        highs = recent['high'].values
        resistance_levels = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_levels.append(highs[i])
        
        # Find swing lows (support)
        lows = recent['low'].values
        support_levels = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_levels.append(lows[i])
        
        # Sort and limit
        support_levels = sorted(set(support_levels), reverse=True)[:self.num_levels]
        resistance_levels = sorted(set(resistance_levels))[:self.num_levels]
        
        return support_levels, resistance_levels


# ============================================================================
# PROBABILITY SCORING ENGINE
# ============================================================================

class ProbabilityScoringEngine:
    """
    Advanced probability scoring for breakout signals
    Considers multiple factors for win probability estimation
    """
    
    def __init__(self):
        self.win_history: deque = deque(maxlen=100)  # Track last 100 signals
        self.bullish_wins = 0
        self.bullish_losses = 0
        self.bearish_wins = 0
        self.bearish_losses = 0
    
    def calculate_breakout_strength(self, df: pd.DataFrame, breakout_type: str, 
                                     lookback: int = 20) -> float:
        """
        Calculate breakout strength (0.0 to 1.0)
        
        Factors:
        - Distance from breakout level
        - Volume confirmation
        - Momentum alignment
        - Candle body strength
        """
        if len(df) < lookback + 1:
            return 0.5
        
        current = df.iloc[-1]
        recent = df.tail(lookback + 1)
        
        strength_factors = []
        
        # 1. Distance factor (how far price moved beyond breakout level)
        if breakout_type == "bullish":
            highest = recent['high'].iloc[:-1].max()
            distance = (current['close'] - highest) / highest if highest > 0 else 0
            distance_factor = min(max(distance * 100, 0), 1.0)  # Normalize
        else:
            lowest = recent['low'].iloc[:-1].min()
            distance = (lowest - current['close']) / lowest if lowest > 0 else 0
            distance_factor = min(max(distance * 100, 0), 1.0)
        
        strength_factors.append(distance_factor * 0.3)  # 30% weight
        
        # 2. Volume confirmation (if available)
        if 'volume' in df.columns and df['volume'].iloc[-1] > 0:
            avg_volume = recent['volume'].mean()
            current_volume = current['volume']
            volume_factor = min(current_volume / avg_volume if avg_volume > 0 else 1.0, 2.0) / 2
            strength_factors.append(volume_factor * 0.2)  # 20% weight
        else:
            strength_factors.append(0.1)  # Default 50% of 20%
        
        # 3. Candle body strength
        body = abs(current['close'] - current['open'])
        wick_upper = current['high'] - max(current['close'], current['open'])
        wick_lower = min(current['close'], current['open']) - current['low']
        total_range = current['high'] - current['low']
        
        if total_range > 0:
            body_ratio = body / total_range
            if breakout_type == "bullish":
                # Bullish: prefer green candle with small upper wick
                is_bullish_candle = current['close'] > current['open']
                body_factor = body_ratio if is_bullish_candle else body_ratio * 0.5
            else:
                # Bearish: prefer red candle with small lower wick
                is_bearish_candle = current['close'] < current['open']
                body_factor = body_ratio if is_bearish_candle else body_ratio * 0.5
            strength_factors.append(body_factor * 0.25)  # 25% weight
        else:
            strength_factors.append(0.125)
        
        # 4. Momentum alignment (using simple momentum)
        if len(df) >= 5:
            momentum = (current['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close'] if df.iloc[-5]['close'] > 0 else 0
            if breakout_type == "bullish":
                momentum_factor = 0.5 + (momentum * 10) if momentum > 0 else 0.3
            else:
                momentum_factor = 0.5 + (-momentum * 10) if momentum < 0 else 0.3
            momentum_factor = min(max(momentum_factor, 0), 1.0)
            strength_factors.append(momentum_factor * 0.25)  # 25% weight
        else:
            strength_factors.append(0.125)
        
        return min(sum(strength_factors) / 0.9, 1.0)  # Normalize to max 1.0
    
    def calculate_confidence_score(self, strength: float, breakout_type: str,
                                    support_levels: List[float], 
                                    resistance_levels: List[float],
                                    current_price: float) -> float:
        """
        Calculate overall confidence score (0-100%)
        
        Combines:
        - Breakout strength
        - Historical win rate
        - S/R level proximity
        """
        # Base confidence from strength
        base_confidence = strength * 60  # Max 60% from strength
        
        # Historical performance bonus
        if breakout_type == "bullish":
            total = self.bullish_wins + self.bullish_losses
            if total > 10:
                win_rate = self.bullish_wins / total
                history_bonus = win_rate * 20  # Max 20% from history
            else:
                history_bonus = 10  # Default 10% when insufficient data
        else:
            total = self.bearish_wins + self.bearish_losses
            if total > 10:
                win_rate = self.bearish_wins / total
                history_bonus = win_rate * 20
            else:
                history_bonus = 10
        
        # S/R level confirmation bonus
        sr_bonus = 0
        if breakout_type == "bullish" and resistance_levels:
            # Check if price broke through a resistance level
            for level in resistance_levels:
                if current_price > level:
                    sr_bonus = min(sr_bonus + 5, 20)  # Max 20% from S/R
        elif breakout_type == "bearish" and support_levels:
            for level in support_levels:
                if current_price < level:
                    sr_bonus = min(sr_bonus + 5, 20)
        
        total_confidence = min(base_confidence + history_bonus + sr_bonus, 95)
        return round(total_confidence, 1)
    
    def record_result(self, breakout_type: str, is_win: bool):
        """Record signal result for win rate tracking"""
        self.win_history.append((breakout_type, is_win))
        
        if breakout_type == "bullish":
            if is_win:
                self.bullish_wins += 1
            else:
                self.bullish_losses += 1
        else:
            if is_win:
                self.bearish_wins += 1
            else:
                self.bearish_losses += 1
    
    def get_statistics(self) -> Dict:
        """Get current win/loss statistics"""
        bullish_total = self.bullish_wins + self.bullish_losses
        bearish_total = self.bearish_wins + self.bearish_losses
        
        return {
            "bullish_win_rate": self.bullish_wins / bullish_total if bullish_total > 0 else 0.5,
            "bearish_win_rate": self.bearish_wins / bearish_total if bearish_total > 0 else 0.5,
            "total_bullish": bullish_total,
            "total_bearish": bearish_total,
            "overall_win_rate": (self.bullish_wins + self.bearish_wins) / 
                               (bullish_total + bearish_total) if (bullish_total + bearish_total) > 0 else 0.5
        }


# ============================================================================
# MAIN BREAKOUT PREDICTOR CLASS
# ============================================================================

class EnhancedBreakoutPredictor:
    """
    Enhanced Breakout Predictor with Alerts
    Optimized for 5-second timeframe trading
    
    Features:
    - Ultra-low latency signal processing (<100ms)
    - Multi-level S/R detection
    - Probability scoring
    - Webhook/MT4 alert integration
    """
    
    def __init__(self, 
                 breakout_settings: BreakoutSettings = None,
                 webhook_settings: WebhookSettings = None,
                 alert_settings: AlertSettings = None):
        
        self.breakout_settings = breakout_settings or BreakoutSettings()
        self.webhook_settings = webhook_settings or WebhookSettings()
        self.alert_settings = alert_settings or AlertSettings()
        
        # Initialize components
        self.level_calculator = BreakoutLevelCalculator(
            percentage_step=self.breakout_settings.percentage_step,
            num_levels=self.breakout_settings.number_of_lines
        )
        self.scoring_engine = ProbabilityScoringEngine()
        
        # Data buffers for efficient processing
        self.data_buffer: Dict[str, deque] = {}  # symbol -> price data
        self.signal_history: Dict[str, List[BreakoutSignal]] = {}
        self.breakout_levels: Dict[str, Dict] = {}  # Cached levels per symbol
        
        # Performance tracking
        self.processing_times: deque = deque(maxlen=100)
        
        logger.info("🚀 Enhanced Breakout Predictor initialized")
        logger.info(f"   Lookback: {self.breakout_settings.lookback_period}")
        logger.info(f"   Buffer size: {self.breakout_settings.buffer_size}")
        logger.info(f"   Min strength: {self.breakout_settings.min_breakout_strength}")
    
    def detect_breakout(self, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
        """
        Detect bullish or bearish breakout
        
        Returns:
            Dict with breakout info or None if no breakout
        """
        lookback = self.breakout_settings.lookback_period
        
        if len(df) < lookback + 1:
            return None
        
        current = df.iloc[-1]
        historical = df.iloc[-(lookback + 1):-1]
        
        highest_high = historical['high'].max()
        lowest_low = historical['low'].min()
        
        current_close = current['close']
        current_high = current['high']
        current_low = current['low']
        
        breakout_info = None
        
        # Bullish Breakout Detection
        if self.breakout_settings.bullish_alerts:
            if current_high > highest_high:
                # Confirm with close above previous high
                if current_close > historical['high'].iloc[-1]:
                    breakout_info = {
                        'type': 'bullish',
                        'signal': 'BUY',
                        'breakout_level': highest_high,
                        'current_price': current_close,
                        'exceeded_by': current_high - highest_high,
                        'exceeded_pct': ((current_high - highest_high) / highest_high) * 100
                    }
        
        # Bearish Breakout Detection (only if no bullish breakout)
        if breakout_info is None and self.breakout_settings.bearish_alerts:
            if current_low < lowest_low:
                # Confirm with close below previous low
                if current_close < historical['low'].iloc[-1]:
                    breakout_info = {
                        'type': 'bearish',
                        'signal': 'SELL',
                        'breakout_level': lowest_low,
                        'current_price': current_close,
                        'exceeded_by': lowest_low - current_low,
                        'exceeded_pct': ((lowest_low - current_low) / lowest_low) * 100
                    }
        
        return breakout_info
    
    def calculate_signals(self, df: pd.DataFrame, symbol: str, 
                          timeframe: str = "5s") -> Optional[BreakoutSignal]:
        """
        Main signal calculation method
        Optimized for ultra-low latency (<100ms)
        
        Args:
            df: OHLCV DataFrame
            symbol: Trading symbol
            timeframe: Timeframe string (default "5s")
        
        Returns:
            BreakoutSignal if breakout detected, None otherwise
        """
        start_time = time.time()
        
        if not self.breakout_settings.enabled:
            return None
        
        # Detect breakout
        breakout = self.detect_breakout(df, symbol)
        
        if breakout is None:
            return None
        
        # Calculate strength and confidence
        strength = self.scoring_engine.calculate_breakout_strength(
            df, breakout['type'], self.breakout_settings.lookback_period
        )
        
        # Check minimum strength threshold
        if strength < self.breakout_settings.min_breakout_strength:
            logger.debug(f"Breakout strength {strength:.2f} below threshold {self.breakout_settings.min_breakout_strength}")
            return None
        
        # Calculate S/R levels
        support_levels, resistance_levels = self.level_calculator.calculate_dynamic_levels(
            df, self.breakout_settings.lookback_period
        )
        
        # If no dynamic levels found, use percentage-based
        if not support_levels and not resistance_levels:
            support_levels, resistance_levels = self.level_calculator.calculate_levels(
                breakout['current_price']
            )
        
        # Calculate confidence score
        confidence = self.scoring_engine.calculate_confidence_score(
            strength, breakout['type'],
            support_levels, resistance_levels,
            breakout['current_price']
        )
        
        # Generate timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build message
        direction = "above" if breakout['type'] == "bullish" else "below"
        message = (f"{'BULLISH' if breakout['type'] == 'bullish' else 'BEARISH'} BREAKOUT: "
                   f"Price broke {direction} {self.breakout_settings.lookback_period}-bar "
                   f"{'high' if breakout['type'] == 'bullish' else 'low'} "
                   f"({breakout['exceeded_pct']:.2f}% move)")
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        self.processing_times.append(processing_time)
        
        # Create signal
        signal = BreakoutSignal(
            ticker=symbol,
            signal=breakout['signal'],
            price=round(breakout['current_price'], 5),
            timestamp=timestamp,
            message=message,
            timeframe=timeframe,
            breakout_level=round(breakout['breakout_level'], 5),
            confidence_score=confidence,
            breakout_type=breakout['type'],
            strength=round(strength, 3),
            support_levels=[round(l, 5) for l in support_levels],
            resistance_levels=[round(l, 5) for l in resistance_levels],
            win_probability=confidence / 100,
            processing_time_ms=round(processing_time, 2)
        )
        
        # Store in history
        if symbol not in self.signal_history:
            self.signal_history[symbol] = []
        self.signal_history[symbol].append(signal)
        
        logger.info(f"🎯 BREAKOUT SIGNAL: {symbol} {signal.signal} @ {signal.price}")
        logger.info(f"   Type: {signal.breakout_type}, Confidence: {signal.confidence_score}%")
        logger.info(f"   Strength: {signal.strength}, Processing: {signal.processing_time_ms}ms")
        
        return signal
    
    def get_performance_metrics(self) -> Dict:
        """Get predictor performance metrics"""
        if not self.processing_times:
            return {"avg_processing_ms": 0, "max_processing_ms": 0}
        
        times = list(self.processing_times)
        return {
            "avg_processing_ms": round(np.mean(times), 2),
            "max_processing_ms": round(max(times), 2),
            "min_processing_ms": round(min(times), 2),
            "signals_generated": sum(len(s) for s in self.signal_history.values()),
            "statistics": self.scoring_engine.get_statistics()
        }
    
    def get_current_levels(self, symbol: str, current_price: float) -> Dict:
        """Get current S/R levels for a symbol"""
        support, resistance = self.level_calculator.calculate_levels(current_price)
        return {
            "symbol": symbol,
            "current_price": current_price,
            "support_levels": support,
            "resistance_levels": resistance,
            "percentage_step": self.breakout_settings.percentage_step
        }


# ============================================================================
# 5-SECOND OPTIMIZED STRATEGY CLASS
# ============================================================================

class BreakoutPredictor5s(EnhancedBreakoutPredictor):
    """
    5-Second timeframe optimized breakout predictor
    
    Optimizations:
    - Reduced lookback period for faster signals
    - Lower confirmation bars
    - Aggressive signal generation
    - Memory-efficient buffer management
    """
    
    def __init__(self):
        # 5s-optimized settings
        breakout_settings = BreakoutSettings(
            enabled=True,
            bullish_alerts=True,
            bearish_alerts=True,
            lookback_period=15,  # Reduced for 5s (vs 20 for longer timeframes)
            percentage_step=0.5,  # Tighter levels for 5s
            number_of_lines=3,  # Fewer levels for speed
            buffer_size=3000,  # Smaller buffer for 5s
            min_breakout_strength=0.4,  # Lower threshold for more signals
            confirmation_bars=1  # Immediate confirmation
        )
        
        webhook_settings = WebhookSettings(
            enabled=False,
            timeout_ms=50  # Even faster for 5s
        )
        
        alert_settings = AlertSettings(
            include_ticker=True,
            include_price=True,
            include_timestamp=True,
            include_confidence=True
        )
        
        super().__init__(breakout_settings, webhook_settings, alert_settings)
        
        self.timeframe = "5s"
        logger.info("⚡ 5-Second Breakout Predictor initialized with optimized settings")
    
    def generate_signal(self, symbol: str, df: pd.DataFrame = None,
                        chart_type: str = "japanese_candles") -> Optional[Dict]:
        """
        Generate trading signal for 5-second timeframe
        
        Compatible with existing strategy interface
        """
        if df is None:
            logger.warning(f"No data provided for {symbol}")
            return None
        
        signal = self.calculate_signals(df, symbol, self.timeframe)
        
        if signal is None:
            return None
        
        # Convert to standard strategy output format
        return {
            'direction': signal.signal,
            'signal': signal.signal,
            'confidence': signal.confidence_score,
            'probability': signal.confidence_score,
            'symbol': symbol,
            'timeframe': self.timeframe,
            'strategy': 'enhanced_breakout_5s',
            'breakout_type': signal.breakout_type,
            'breakout_level': signal.breakout_level,
            'strength': signal.strength,
            'reasoning': signal.message,
            'support_levels': signal.support_levels,
            'resistance_levels': signal.resistance_levels,
            'technical_analysis': {
                'breakout': {
                    'type': signal.breakout_type,
                    'level': signal.breakout_level,
                    'strength': signal.strength,
                    'exceeded_by': round(abs(signal.price - signal.breakout_level), 5)
                },
                'support_resistance': {
                    'support': signal.support_levels,
                    'resistance': signal.resistance_levels
                },
                'win_probability': signal.win_probability,
                'processing_time_ms': signal.processing_time_ms
            }
        }


# ============================================================================
# FACTORY AND CONVENIENCE FUNCTIONS
# ============================================================================

# Global instances
_breakout_predictor_5s: Optional[BreakoutPredictor5s] = None
_breakout_predictors: Dict[str, EnhancedBreakoutPredictor] = {}


def get_breakout_predictor_5s() -> BreakoutPredictor5s:
    """Get singleton 5s breakout predictor instance"""
    global _breakout_predictor_5s
    if _breakout_predictor_5s is None:
        _breakout_predictor_5s = BreakoutPredictor5s()
    return _breakout_predictor_5s


def get_breakout_predictor(timeframe: str = "5s") -> EnhancedBreakoutPredictor:
    """Get breakout predictor for specific timeframe"""
    global _breakout_predictors
    
    if timeframe == "5s":
        return get_breakout_predictor_5s()
    
    if timeframe not in _breakout_predictors:
        # Adjust settings based on timeframe
        if timeframe in ["15s", "30s"]:
            lookback = 18
            percentage_step = 0.75
        elif timeframe in ["1m", "2m", "3m"]:
            lookback = 20
            percentage_step = 1.0
        else:
            lookback = 25
            percentage_step = 1.5
        
        settings = BreakoutSettings(
            lookback_period=lookback,
            percentage_step=percentage_step
        )
        _breakout_predictors[timeframe] = EnhancedBreakoutPredictor(breakout_settings=settings)
    
    return _breakout_predictors[timeframe]


def generate_breakout_signal(symbol: str, df: pd.DataFrame, 
                              timeframe: str = "5s") -> Optional[Dict]:
    """Convenience function to generate breakout signal"""
    predictor = get_breakout_predictor(timeframe)
    
    if isinstance(predictor, BreakoutPredictor5s):
        return predictor.generate_signal(symbol, df)
    else:
        signal = predictor.calculate_signals(df, symbol, timeframe)
        if signal:
            return signal.to_dict()
        return None
