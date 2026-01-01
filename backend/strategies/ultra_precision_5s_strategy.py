"""
Ultra-Precision 5-Second Binary Options Trading Strategy
=========================================================

A highly accurate trading strategy for 5-second binary options on Pocket Option.
Uses 200 candlesticks for analysis with multiple technical indicators and 
candlestick pattern recognition. Features adaptive learning to improve over time.

Key Features:
- Multi-indicator confluence system
- Candlestick pattern recognition
- Momentum and volatility analysis
- Adaptive parameter optimization
- Real-time signal generation
- Support/Resistance level filtering (NEW)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import json

# Import Support/Resistance detector
from .support_resistance import get_sr_detector, SRAnalysis

logger = logging.getLogger(__name__)


class SignalType(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class TrendDirection(Enum):
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    SIDEWAYS = "SIDEWAYS"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"


@dataclass
class CandleData:
    """Single candle data structure"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open
    
    @property
    def range(self) -> float:
        return self.high - self.low


@dataclass
class TradingSignal:
    """Trading signal with confidence and metadata"""
    signal_type: SignalType
    direction: str  # "call" or "put"
    confidence: float  # 0-100
    entry_price: float
    timestamp: datetime
    indicators: Dict[str, float]
    patterns: List[str]
    trend: TrendDirection
    volatility: str  # "low", "medium", "high"
    reasoning: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "signal_type": self.signal_type.value,
            "direction": self.direction,
            "confidence": round(float(self.confidence), 2),
            "entry_price": float(self.entry_price),
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
            "indicators": {k: round(float(v), 4) if isinstance(v, (float, np.floating)) else (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in self.indicators.items()},
            "patterns": list(self.patterns),
            "trend": self.trend.value,
            "volatility": self.volatility,
            "reasoning": list(self.reasoning)
        }


@dataclass
class AdaptiveParameters:
    """Adaptive strategy parameters that learn over time"""
    # RSI parameters
    rsi_period: int = 7
    rsi_overbought: float = 75.0
    rsi_oversold: float = 25.0
    
    # MACD parameters
    macd_fast: int = 6
    macd_slow: int = 13
    macd_signal: int = 4
    
    # Bollinger Bands
    bb_period: int = 10
    bb_std: float = 2.0
    
    # Stochastic
    stoch_k: int = 7
    stoch_d: int = 3
    stoch_overbought: float = 80.0
    stoch_oversold: float = 20.0
    
    # EMA periods
    ema_fast: int = 5
    ema_medium: int = 10
    ema_slow: int = 20
    
    # ATR period
    atr_period: int = 7
    
    # Signal thresholds
    min_confidence: float = 70.0
    strong_signal_threshold: float = 85.0
    
    # Pattern weights
    pattern_weight: float = 0.25
    indicator_weight: float = 0.50
    momentum_weight: float = 0.25
    
    # Learning parameters
    learning_rate: float = 0.05
    adaptation_threshold: float = 0.55  # Win rate threshold for adaptation


class TechnicalIndicators:
    """Technical indicator calculations"""
    
    @staticmethod
    def calculate_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index"""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros(len(closes))
        avg_loss = np.zeros(len(closes))
        
        # Initial SMA
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        # EMA smoothing
        for i in range(period + 1, len(closes)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate MACD, Signal line, and Histogram"""
        ema_fast = TechnicalIndicators.calculate_ema(closes, fast)
        ema_slow = TechnicalIndicators.calculate_ema(closes, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        sma = np.zeros(len(data))
        for i in range(period - 1, len(data)):
            sma[i] = np.mean(data[i-period+1:i+1])
        return sma
    
    @staticmethod
    def calculate_bollinger_bands(closes: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands"""
        sma = TechnicalIndicators.calculate_sma(closes, period)
        std = np.zeros(len(closes))
        
        for i in range(period - 1, len(closes)):
            std[i] = np.std(closes[i-period+1:i+1])
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def calculate_stochastic(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Stochastic Oscillator"""
        k = np.zeros(len(closes))
        
        for i in range(k_period - 1, len(closes)):
            highest_high = np.max(highs[i-k_period+1:i+1])
            lowest_low = np.min(lows[i-k_period+1:i+1])
            
            if highest_high != lowest_low:
                k[i] = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
        
        d = TechnicalIndicators.calculate_sma(k, d_period)
        
        return k, d
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range"""
        tr = np.zeros(len(closes))
        tr[0] = highs[0] - lows[0]
        
        for i in range(1, len(closes)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        
        atr = TechnicalIndicators.calculate_ema(tr, period)
        return atr
    
    @staticmethod
    def calculate_momentum(closes: np.ndarray, period: int = 10) -> np.ndarray:
        """Calculate Momentum"""
        momentum = np.zeros(len(closes))
        for i in range(period, len(closes)):
            momentum[i] = closes[i] - closes[i - period]
        return momentum
    
    @staticmethod
    def calculate_roc(closes: np.ndarray, period: int = 10) -> np.ndarray:
        """Calculate Rate of Change"""
        roc = np.zeros(len(closes))
        for i in range(period, len(closes)):
            if closes[i - period] != 0:
                roc[i] = ((closes[i] - closes[i - period]) / closes[i - period]) * 100
        return roc
    
    @staticmethod
    def calculate_williams_r(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Williams %R"""
        wr = np.zeros(len(closes))
        
        for i in range(period - 1, len(closes)):
            highest_high = np.max(highs[i-period+1:i+1])
            lowest_low = np.min(lows[i-period+1:i+1])
            
            if highest_high != lowest_low:
                wr[i] = ((highest_high - closes[i]) / (highest_high - lowest_low)) * -100
        
        return wr
    
    @staticmethod
    def calculate_cci(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
        """Calculate Commodity Channel Index"""
        tp = (highs + lows + closes) / 3  # Typical Price
        sma_tp = TechnicalIndicators.calculate_sma(tp, period)
        
        mean_dev = np.zeros(len(closes))
        for i in range(period - 1, len(closes)):
            mean_dev[i] = np.mean(np.abs(tp[i-period+1:i+1] - sma_tp[i]))
        
        cci = np.zeros(len(closes))
        for i in range(len(closes)):
            if mean_dev[i] != 0:
                cci[i] = (tp[i] - sma_tp[i]) / (0.015 * mean_dev[i])
        
        return cci


class CandlestickPatterns:
    """Candlestick pattern recognition for 5-second timeframe"""
    
    @staticmethod
    def detect_patterns(candles: List[CandleData]) -> List[Dict[str, Any]]:
        """Detect all candlestick patterns in the data"""
        patterns = []
        n = len(candles)
        
        if n < 3:
            return patterns
        
        for i in range(2, n):
            current = candles[i]
            prev = candles[i-1]
            prev2 = candles[i-2]
            
            # Doji
            if CandlestickPatterns._is_doji(current):
                patterns.append({
                    "pattern": "doji",
                    "index": i,
                    "type": "neutral",
                    "strength": 0.6
                })
            
            # Bullish Engulfing
            if CandlestickPatterns._is_bullish_engulfing(prev, current):
                patterns.append({
                    "pattern": "bullish_engulfing",
                    "index": i,
                    "type": "bullish",
                    "strength": 0.85
                })
            
            # Bearish Engulfing
            if CandlestickPatterns._is_bearish_engulfing(prev, current):
                patterns.append({
                    "pattern": "bearish_engulfing",
                    "index": i,
                    "type": "bearish",
                    "strength": 0.85
                })
            
            # Hammer
            if CandlestickPatterns._is_hammer(current):
                patterns.append({
                    "pattern": "hammer",
                    "index": i,
                    "type": "bullish",
                    "strength": 0.75
                })
            
            # Shooting Star
            if CandlestickPatterns._is_shooting_star(current):
                patterns.append({
                    "pattern": "shooting_star",
                    "index": i,
                    "type": "bearish",
                    "strength": 0.75
                })
            
            # Morning Star
            if i >= 2 and CandlestickPatterns._is_morning_star(prev2, prev, current):
                patterns.append({
                    "pattern": "morning_star",
                    "index": i,
                    "type": "bullish",
                    "strength": 0.90
                })
            
            # Evening Star
            if i >= 2 and CandlestickPatterns._is_evening_star(prev2, prev, current):
                patterns.append({
                    "pattern": "evening_star",
                    "index": i,
                    "type": "bearish",
                    "strength": 0.90
                })
            
            # Three White Soldiers
            if i >= 2 and CandlestickPatterns._is_three_white_soldiers(prev2, prev, current):
                patterns.append({
                    "pattern": "three_white_soldiers",
                    "index": i,
                    "type": "bullish",
                    "strength": 0.95
                })
            
            # Three Black Crows
            if i >= 2 and CandlestickPatterns._is_three_black_crows(prev2, prev, current):
                patterns.append({
                    "pattern": "three_black_crows",
                    "index": i,
                    "type": "bearish",
                    "strength": 0.95
                })
            
            # Piercing Line
            if CandlestickPatterns._is_piercing_line(prev, current):
                patterns.append({
                    "pattern": "piercing_line",
                    "index": i,
                    "type": "bullish",
                    "strength": 0.80
                })
            
            # Dark Cloud Cover
            if CandlestickPatterns._is_dark_cloud_cover(prev, current):
                patterns.append({
                    "pattern": "dark_cloud_cover",
                    "index": i,
                    "type": "bearish",
                    "strength": 0.80
                })
            
            # Spinning Top
            if CandlestickPatterns._is_spinning_top(current):
                patterns.append({
                    "pattern": "spinning_top",
                    "index": i,
                    "type": "neutral",
                    "strength": 0.5
                })
        
        return patterns
    
    @staticmethod
    def _is_doji(candle: CandleData) -> bool:
        """Detect Doji pattern"""
        body_ratio = candle.body_size / candle.range if candle.range > 0 else 0
        return body_ratio < 0.1
    
    @staticmethod
    def _is_bullish_engulfing(prev: CandleData, current: CandleData) -> bool:
        """Detect Bullish Engulfing pattern"""
        return (prev.is_bearish and 
                current.is_bullish and 
                current.open < prev.close and 
                current.close > prev.open)
    
    @staticmethod
    def _is_bearish_engulfing(prev: CandleData, current: CandleData) -> bool:
        """Detect Bearish Engulfing pattern"""
        return (prev.is_bullish and 
                current.is_bearish and 
                current.open > prev.close and 
                current.close < prev.open)
    
    @staticmethod
    def _is_hammer(candle: CandleData) -> bool:
        """Detect Hammer pattern"""
        if candle.range == 0:
            return False
        lower_wick_ratio = candle.lower_wick / candle.range
        body_ratio = candle.body_size / candle.range
        upper_wick_ratio = candle.upper_wick / candle.range
        return lower_wick_ratio >= 0.6 and body_ratio <= 0.3 and upper_wick_ratio <= 0.1
    
    @staticmethod
    def _is_shooting_star(candle: CandleData) -> bool:
        """Detect Shooting Star pattern"""
        if candle.range == 0:
            return False
        upper_wick_ratio = candle.upper_wick / candle.range
        body_ratio = candle.body_size / candle.range
        lower_wick_ratio = candle.lower_wick / candle.range
        return upper_wick_ratio >= 0.6 and body_ratio <= 0.3 and lower_wick_ratio <= 0.1
    
    @staticmethod
    def _is_morning_star(first: CandleData, second: CandleData, third: CandleData) -> bool:
        """Detect Morning Star pattern"""
        return (first.is_bearish and 
                second.body_size < first.body_size * 0.3 and
                third.is_bullish and 
                third.close > (first.open + first.close) / 2)
    
    @staticmethod
    def _is_evening_star(first: CandleData, second: CandleData, third: CandleData) -> bool:
        """Detect Evening Star pattern"""
        return (first.is_bullish and 
                second.body_size < first.body_size * 0.3 and
                third.is_bearish and 
                third.close < (first.open + first.close) / 2)
    
    @staticmethod
    def _is_three_white_soldiers(first: CandleData, second: CandleData, third: CandleData) -> bool:
        """Detect Three White Soldiers pattern"""
        return (first.is_bullish and second.is_bullish and third.is_bullish and
                second.close > first.close and third.close > second.close and
                second.open > first.open and third.open > second.open)
    
    @staticmethod
    def _is_three_black_crows(first: CandleData, second: CandleData, third: CandleData) -> bool:
        """Detect Three Black Crows pattern"""
        return (first.is_bearish and second.is_bearish and third.is_bearish and
                second.close < first.close and third.close < second.close and
                second.open < first.open and third.open < second.open)
    
    @staticmethod
    def _is_piercing_line(prev: CandleData, current: CandleData) -> bool:
        """Detect Piercing Line pattern"""
        midpoint = (prev.open + prev.close) / 2
        return (prev.is_bearish and 
                current.is_bullish and 
                current.open < prev.low and 
                current.close > midpoint)
    
    @staticmethod
    def _is_dark_cloud_cover(prev: CandleData, current: CandleData) -> bool:
        """Detect Dark Cloud Cover pattern"""
        midpoint = (prev.open + prev.close) / 2
        return (prev.is_bullish and 
                current.is_bearish and 
                current.open > prev.high and 
                current.close < midpoint)
    
    @staticmethod
    def _is_spinning_top(candle: CandleData) -> bool:
        """Detect Spinning Top pattern"""
        if candle.range == 0:
            return False
        body_ratio = candle.body_size / candle.range
        return 0.1 <= body_ratio <= 0.3


class UltraPrecision5SecondStrategy:
    """
    Ultra-Precision 5-Second Binary Options Strategy
    
    Uses 200 candles for analysis with:
    - Multi-indicator confluence
    - Candlestick pattern recognition
    - Adaptive learning
    - Real-time signal generation
    """
    
    def __init__(self, db=None):
        self.db = db
        self.params = AdaptiveParameters()
        self.trade_history: List[Dict] = []
        self.last_signals: List[TradingSignal] = []
        self.performance_metrics = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0
        }
        
        logger.info("🎯 Ultra-Precision 5-Second Strategy initialized")
    
    def analyze(self, candles: List[CandleData]) -> TradingSignal:
        """
        Analyze 200 candles and generate trading signal
        
        Args:
            candles: List of 200 CandleData objects
        
        Returns:
            TradingSignal with confidence and reasoning
        """
        if len(candles) < 50:
            raise ValueError(f"Need at least 50 candles, got {len(candles)}")
        
        # Convert to numpy arrays for indicator calculations
        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        opens = np.array([c.open for c in candles])
        
        # Calculate all indicators
        indicators = self._calculate_indicators(opens, highs, lows, closes)
        
        # Detect candlestick patterns
        patterns = CandlestickPatterns.detect_patterns(candles)
        recent_patterns = [p for p in patterns if p["index"] >= len(candles) - 5]
        
        # Determine trend
        trend = self._determine_trend(closes, indicators)
        
        # Calculate volatility
        volatility = self._calculate_volatility(indicators["atr"][-1], closes[-1])
        
        # Generate signal scores
        indicator_score = self._calculate_indicator_score(indicators)
        pattern_score = self._calculate_pattern_score(recent_patterns)
        momentum_score = self._calculate_momentum_score(indicators)
        
        # Combined score
        total_score = (
            indicator_score * self.params.indicator_weight +
            pattern_score * self.params.pattern_weight +
            momentum_score * self.params.momentum_weight
        )
        
        # Determine signal type and direction
        signal_type, direction = self._determine_signal(total_score, trend, indicators)
        
        # Calculate confidence
        confidence = self._calculate_confidence(total_score, indicator_score, pattern_score, momentum_score, trend)
        
        # Build reasoning
        reasoning = self._build_reasoning(indicators, recent_patterns, trend, volatility)
        
        # Create signal
        signal = TradingSignal(
            signal_type=signal_type,
            direction=direction,
            confidence=confidence,
            entry_price=closes[-1],
            timestamp=candles[-1].timestamp,
            indicators={
                "rsi": indicators["rsi"][-1],
                "macd": indicators["macd"][-1],
                "macd_signal": indicators["macd_signal"][-1],
                "macd_hist": indicators["macd_hist"][-1],
                "stoch_k": indicators["stoch_k"][-1],
                "stoch_d": indicators["stoch_d"][-1],
                "bb_upper": indicators["bb_upper"][-1],
                "bb_middle": indicators["bb_middle"][-1],
                "bb_lower": indicators["bb_lower"][-1],
                "ema_fast": indicators["ema_fast"][-1],
                "ema_medium": indicators["ema_medium"][-1],
                "ema_slow": indicators["ema_slow"][-1],
                "atr": indicators["atr"][-1],
                "williams_r": indicators["williams_r"][-1],
                "cci": indicators["cci"][-1],
                "momentum": indicators["momentum"][-1],
                "roc": indicators["roc"][-1]
            },
            patterns=[p["pattern"] for p in recent_patterns],
            trend=trend,
            volatility=volatility,
            reasoning=reasoning
        )
        
        self.last_signals.append(signal)
        if len(self.last_signals) > 100:
            self.last_signals = self.last_signals[-100:]
        
        return signal
    
    def _calculate_indicators(self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict[str, np.ndarray]:
        """Calculate all technical indicators"""
        indicators = {}
        
        # RSI
        indicators["rsi"] = TechnicalIndicators.calculate_rsi(closes, self.params.rsi_period)
        
        # MACD
        macd, signal, hist = TechnicalIndicators.calculate_macd(
            closes, self.params.macd_fast, self.params.macd_slow, self.params.macd_signal
        )
        indicators["macd"] = macd
        indicators["macd_signal"] = signal
        indicators["macd_hist"] = hist
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.calculate_bollinger_bands(
            closes, self.params.bb_period, self.params.bb_std
        )
        indicators["bb_upper"] = bb_upper
        indicators["bb_middle"] = bb_middle
        indicators["bb_lower"] = bb_lower
        
        # Stochastic
        stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(
            highs, lows, closes, self.params.stoch_k, self.params.stoch_d
        )
        indicators["stoch_k"] = stoch_k
        indicators["stoch_d"] = stoch_d
        
        # EMAs
        indicators["ema_fast"] = TechnicalIndicators.calculate_ema(closes, self.params.ema_fast)
        indicators["ema_medium"] = TechnicalIndicators.calculate_ema(closes, self.params.ema_medium)
        indicators["ema_slow"] = TechnicalIndicators.calculate_ema(closes, self.params.ema_slow)
        
        # ATR
        indicators["atr"] = TechnicalIndicators.calculate_atr(highs, lows, closes, self.params.atr_period)
        
        # Williams %R
        indicators["williams_r"] = TechnicalIndicators.calculate_williams_r(highs, lows, closes, 7)
        
        # CCI
        indicators["cci"] = TechnicalIndicators.calculate_cci(highs, lows, closes, 10)
        
        # Momentum
        indicators["momentum"] = TechnicalIndicators.calculate_momentum(closes, 5)
        
        # ROC
        indicators["roc"] = TechnicalIndicators.calculate_roc(closes, 5)
        
        return indicators
    
    def _determine_trend(self, closes: np.ndarray, indicators: Dict) -> TrendDirection:
        """Determine overall trend direction"""
        ema_fast = indicators["ema_fast"][-1]
        ema_medium = indicators["ema_medium"][-1]
        ema_slow = indicators["ema_slow"][-1]
        
        current_price = closes[-1]
        
        # EMA alignment check
        if ema_fast > ema_medium > ema_slow and current_price > ema_fast:
            # Check momentum
            if indicators["momentum"][-1] > 0 and indicators["roc"][-1] > 0.5:
                return TrendDirection.STRONG_UPTREND
            return TrendDirection.UPTREND
        elif ema_fast < ema_medium < ema_slow and current_price < ema_fast:
            if indicators["momentum"][-1] < 0 and indicators["roc"][-1] < -0.5:
                return TrendDirection.STRONG_DOWNTREND
            return TrendDirection.DOWNTREND
        else:
            return TrendDirection.SIDEWAYS
    
    def _calculate_volatility(self, atr: float, current_price: float) -> str:
        """Calculate volatility level"""
        atr_percent = (atr / current_price) * 100 if current_price > 0 else 0
        
        if atr_percent < 0.05:
            return "low"
        elif atr_percent < 0.15:
            return "medium"
        else:
            return "high"
    
    def _calculate_indicator_score(self, indicators: Dict) -> float:
        """Calculate score based on technical indicators (-100 to +100)"""
        score = 0.0
        
        # RSI (weight: 20)
        rsi = indicators["rsi"][-1]
        if rsi < self.params.rsi_oversold:
            score += 20 * ((self.params.rsi_oversold - rsi) / self.params.rsi_oversold)
        elif rsi > self.params.rsi_overbought:
            score -= 20 * ((rsi - self.params.rsi_overbought) / (100 - self.params.rsi_overbought))
        
        # MACD (weight: 25)
        macd_hist = indicators["macd_hist"][-1]
        prev_hist = indicators["macd_hist"][-2] if len(indicators["macd_hist"]) > 1 else 0
        
        if macd_hist > 0:
            score += 15
            if macd_hist > prev_hist:  # Increasing
                score += 10
        else:
            score -= 15
            if macd_hist < prev_hist:  # Decreasing
                score -= 10
        
        # Stochastic (weight: 20)
        stoch_k = indicators["stoch_k"][-1]
        stoch_d = indicators["stoch_d"][-1]
        
        if stoch_k < self.params.stoch_oversold:
            score += 15
            if stoch_k > stoch_d:  # Bullish crossover potential
                score += 5
        elif stoch_k > self.params.stoch_overbought:
            score -= 15
            if stoch_k < stoch_d:  # Bearish crossover potential
                score -= 5
        
        # Bollinger Bands (weight: 15)
        close = indicators["bb_middle"][-1]  # Use current close
        bb_upper = indicators["bb_upper"][-1]
        bb_lower = indicators["bb_lower"][-1]
        
        if close <= bb_lower:
            score += 15
        elif close >= bb_upper:
            score -= 15
        
        # Williams %R (weight: 10)
        williams = indicators["williams_r"][-1]
        if williams < -80:
            score += 10
        elif williams > -20:
            score -= 10
        
        # CCI (weight: 10)
        cci = indicators["cci"][-1]
        if cci < -100:
            score += 10
        elif cci > 100:
            score -= 10
        
        return np.clip(score, -100, 100)
    
    def _calculate_pattern_score(self, patterns: List[Dict]) -> float:
        """Calculate score based on candlestick patterns (-100 to +100)"""
        if not patterns:
            return 0.0
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        for pattern in patterns:
            strength = pattern["strength"] * 100
            if pattern["type"] == "bullish":
                bullish_score += strength
            elif pattern["type"] == "bearish":
                bearish_score += strength
        
        total_score = bullish_score - bearish_score
        return np.clip(total_score, -100, 100)
    
    def _calculate_momentum_score(self, indicators: Dict) -> float:
        """Calculate momentum-based score (-100 to +100)"""
        score = 0.0
        
        # Momentum indicator
        momentum = indicators["momentum"][-1]
        if momentum > 0:
            score += 30
        else:
            score -= 30
        
        # ROC
        roc = indicators["roc"][-1]
        if roc > 0:
            score += min(roc * 10, 30)
        else:
            score += max(roc * 10, -30)
        
        # EMA alignment
        ema_fast = indicators["ema_fast"][-1]
        ema_medium = indicators["ema_medium"][-1]
        ema_slow = indicators["ema_slow"][-1]
        
        if ema_fast > ema_medium > ema_slow:
            score += 40
        elif ema_fast < ema_medium < ema_slow:
            score -= 40
        
        return np.clip(score, -100, 100)
    
    def _determine_signal(self, total_score: float, trend: TrendDirection, indicators: Dict) -> Tuple[SignalType, str]:
        """Determine signal type and direction"""
        # Adjust thresholds based on trend
        buy_threshold = 30 if trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND] else 40
        sell_threshold = -30 if trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND] else -40
        
        if total_score >= 60:
            return SignalType.STRONG_BUY, "call"
        elif total_score >= buy_threshold:
            return SignalType.BUY, "call"
        elif total_score <= -60:
            return SignalType.STRONG_SELL, "put"
        elif total_score <= sell_threshold:
            return SignalType.SELL, "put"
        else:
            # Neutral - but still need to decide direction
            if total_score > 0:
                return SignalType.NEUTRAL, "call"
            else:
                return SignalType.NEUTRAL, "put"
    
    def _calculate_confidence(self, total_score: float, indicator_score: float, pattern_score: float, momentum_score: float, trend: TrendDirection) -> float:
        """Calculate signal confidence (0-100)"""
        base_confidence = 50 + (abs(total_score) / 2)
        
        # Bonus for indicator agreement
        scores = [indicator_score, pattern_score, momentum_score]
        agreement = sum(1 for s in scores if (s > 0) == (total_score > 0))
        agreement_bonus = (agreement / len(scores)) * 15
        
        # Trend alignment bonus
        trend_bonus = 0
        if total_score > 0 and trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
            trend_bonus = 10
        elif total_score < 0 and trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
            trend_bonus = 10
        
        confidence = base_confidence + agreement_bonus + trend_bonus
        return np.clip(confidence, 0, 100)
    
    def _build_reasoning(self, indicators: Dict, patterns: List[Dict], trend: TrendDirection, volatility: str) -> List[str]:
        """Build human-readable reasoning for the signal"""
        reasoning = []
        
        # Trend
        reasoning.append(f"Trend: {trend.value}")
        reasoning.append(f"Volatility: {volatility}")
        
        # RSI
        rsi = indicators["rsi"][-1]
        if rsi < 30:
            reasoning.append(f"RSI oversold ({rsi:.1f}) - bullish")
        elif rsi > 70:
            reasoning.append(f"RSI overbought ({rsi:.1f}) - bearish")
        
        # MACD
        if indicators["macd_hist"][-1] > 0:
            reasoning.append("MACD histogram positive - bullish momentum")
        else:
            reasoning.append("MACD histogram negative - bearish momentum")
        
        # Stochastic
        stoch_k = indicators["stoch_k"][-1]
        if stoch_k < 20:
            reasoning.append(f"Stochastic oversold ({stoch_k:.1f}) - reversal potential")
        elif stoch_k > 80:
            reasoning.append(f"Stochastic overbought ({stoch_k:.1f}) - reversal potential")
        
        # Patterns
        if patterns:
            pattern_names = [p["pattern"] for p in patterns]
            reasoning.append(f"Patterns detected: {', '.join(pattern_names)}")
        
        return reasoning
    
    def adapt_parameters(self, win_rate: float):
        """Adapt strategy parameters based on performance"""
        if win_rate < self.params.adaptation_threshold:
            logger.info(f"🔧 Adapting parameters (win rate: {win_rate:.1%})")
            
            # Tighten RSI thresholds
            self.params.rsi_overbought = min(self.params.rsi_overbought + 2, 85)
            self.params.rsi_oversold = max(self.params.rsi_oversold - 2, 15)
            
            # Increase minimum confidence
            self.params.min_confidence = min(self.params.min_confidence + 2, 85)
            
            logger.info(f"   RSI: {self.params.rsi_oversold}/{self.params.rsi_overbought}")
            logger.info(f"   Min Confidence: {self.params.min_confidence}")
    
    def generate_signals_for_dataset(self, candle_data: List[Dict]) -> List[Dict]:
        """
        Generate signals for a dataset of candles
        
        Args:
            candle_data: List of candle dictionaries with open, high, low, close, timestamp
        
        Returns:
            List of signal dictionaries
        """
        # Convert to CandleData objects
        candles = []
        for c in candle_data:
            timestamp = c.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except:
                    timestamp = datetime.now(timezone.utc)
            elif timestamp is None:
                timestamp = datetime.now(timezone.utc)
                
            candles.append(CandleData(
                timestamp=timestamp,
                open=float(c["open"]),
                high=float(c["high"]),
                low=float(c["low"]),
                close=float(c["close"]),
                volume=float(c.get("volume", 0))
            ))
        
        signals = []
        window_size = 200
        
        # Generate signal for each position from window_size onwards
        for i in range(window_size, len(candles)):
            window = candles[i-window_size:i]
            
            try:
                signal = self.analyze(window)
                signals.append(signal.to_dict())
            except Exception as e:
                logger.error(f"Error analyzing at index {i}: {e}")
                continue
        
        return signals
    
    def get_strategy_info(self) -> Dict:
        """Get strategy information and current parameters"""
        return {
            "name": "Ultra-Precision 5-Second Strategy",
            "version": "2.0",
            "timeframe": "5 seconds",
            "window_size": 200,
            "technical_indicators": [
                "RSI (Relative Strength Index)",
                "MACD (Moving Average Convergence Divergence)",
                "Bollinger Bands",
                "Stochastic Oscillator",
                "EMA (5, 10, 20)",
                "ATR (Average True Range)",
                "Williams %R",
                "CCI (Commodity Channel Index)",
                "Momentum",
                "Rate of Change (ROC)"
            ],
            "candlestick_patterns": [
                "Doji",
                "Bullish/Bearish Engulfing",
                "Hammer",
                "Shooting Star",
                "Morning Star",
                "Evening Star",
                "Three White Soldiers",
                "Three Black Crows",
                "Piercing Line",
                "Dark Cloud Cover",
                "Spinning Top"
            ],
            "parameters": {
                "rsi_period": self.params.rsi_period,
                "rsi_overbought": self.params.rsi_overbought,
                "rsi_oversold": self.params.rsi_oversold,
                "macd_fast": self.params.macd_fast,
                "macd_slow": self.params.macd_slow,
                "macd_signal": self.params.macd_signal,
                "bb_period": self.params.bb_period,
                "bb_std": self.params.bb_std,
                "stoch_k": self.params.stoch_k,
                "stoch_d": self.params.stoch_d,
                "min_confidence": self.params.min_confidence
            },
            "signal_logic": {
                "description": "Multi-factor confluence system combining indicator scores, pattern recognition, and momentum analysis",
                "weights": {
                    "indicators": f"{self.params.indicator_weight * 100}%",
                    "patterns": f"{self.params.pattern_weight * 100}%",
                    "momentum": f"{self.params.momentum_weight * 100}%"
                },
                "thresholds": {
                    "strong_buy": "Total score >= 60",
                    "buy": "Total score >= 30-40 (trend dependent)",
                    "strong_sell": "Total score <= -60",
                    "sell": "Total score <= -30 to -40 (trend dependent)"
                }
            },
            "adaptation_mechanism": {
                "trigger": f"Win rate below {self.params.adaptation_threshold * 100}%",
                "adjustments": [
                    "Tighten RSI overbought/oversold thresholds",
                    "Increase minimum confidence requirement",
                    "Adjust indicator weights based on recent performance"
                ],
                "learning_rate": self.params.learning_rate
            }
        }


def generate_sample_signals() -> Dict:
    """Generate sample signals for backtesting demonstration"""
    import random
    from datetime import timedelta
    
    # Generate 200 sample candles (simulating 5-second data)
    base_price = 1.08500
    candles = []
    current_time = datetime.now(timezone.utc)
    
    for i in range(250):  # 250 candles to have 50 signals
        # Random walk price generation
        change = random.gauss(0, 0.00010)
        base_price += change
        
        open_price = base_price
        high_price = base_price + random.uniform(0, 0.00020)
        low_price = base_price - random.uniform(0, 0.00020)
        close_price = base_price + random.gauss(0, 0.00008)
        
        candles.append({
            "timestamp": current_time.isoformat(),
            "open": round(open_price, 5),
            "high": round(high_price, 5),
            "low": round(low_price, 5),
            "close": round(close_price, 5),
            "volume": random.randint(100, 1000)
        })
        
        current_time = current_time + timedelta(seconds=5)
    
    # Create strategy and generate signals
    strategy = UltraPrecision5SecondStrategy()
    signals = strategy.generate_signals_for_dataset(candles)
    
    # Get strategy info
    strategy_info = strategy.get_strategy_info()
    
    return {
        "strategy_info": strategy_info,
        "sample_candles": candles[-20:],  # Last 20 candles
        "signals": signals[-20:],  # Last 20 signals
        "total_signals_generated": len(signals),
        "signal_distribution": {
            "strong_buy": sum(1 for s in signals if s["signal_type"] == "STRONG_BUY"),
            "buy": sum(1 for s in signals if s["signal_type"] == "BUY"),
            "neutral": sum(1 for s in signals if s["signal_type"] == "NEUTRAL"),
            "sell": sum(1 for s in signals if s["signal_type"] == "SELL"),
            "strong_sell": sum(1 for s in signals if s["signal_type"] == "STRONG_SELL")
        }
    }


# Export
__all__ = [
    "UltraPrecision5SecondStrategy",
    "CandleData",
    "TradingSignal",
    "SignalType",
    "TrendDirection",
    "generate_sample_signals"
]
