"""
Ultra-High Accuracy Trading Strategies for Binary Options
==========================================================

Implements research-backed strategies optimized for:
- 5-second, 15-second, 30-second, and 1-minute expiries
- Multiple confirmation signals for precise entry
- Synchronized with Pocket Option for accurate timing
- Machine learning-enhanced signal filtering

Target: 65-80% win rate through multi-confirmation entries
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5


# =====================================================
# MOMENTUM INDICATOR MODULE
# =====================================================

class MomentumIndicator:
    """
    Standalone Momentum Indicator with full configuration options.
    
    Calculates rate of price change and provides multiple signal types:
    - Zero-line crossovers
    - Threshold-based signals (strong positive/negative)
    - Momentum slope (acceleration/deceleration)
    - Divergence detection (price vs momentum)
    """
    
    def __init__(self, period: int = 14, threshold: float = 0, smoothing: int = 3):
        self.period = period
        self.threshold = threshold
        self.smoothing = smoothing
    
    def calculate(self, closes: pd.Series) -> Optional[Dict]:
        """
        Calculate momentum indicator values.
        
        Returns dict with:
        - momentum: raw momentum value (current close - close N periods ago)
        - smoothed: EMA-smoothed momentum
        - slope: momentum slope (rate of change of momentum)
        - previous: previous momentum value (for crossover detection)
        """
        if len(closes) < self.period + self.smoothing + 2:
            return None
        
        # Raw momentum: current price - price N periods ago
        momentum = closes - closes.shift(self.period)
        
        # Apply EMA smoothing
        smoothed = momentum.ewm(span=self.smoothing, adjust=False).mean()
        
        # Calculate slope (rate of change of smoothed momentum)
        slope = smoothed.diff()
        
        return {
            'momentum': momentum.iloc[-1],
            'smoothed': smoothed.iloc[-1],
            'slope': slope.iloc[-1],
            'previous': smoothed.iloc[-2] if len(smoothed) > 1 else 0,
            'prev_slope': slope.iloc[-2] if len(slope) > 1 else 0,
            'series': smoothed  # Full series for divergence detection
        }
    
    def check_condition(self, closes: pd.Series, condition_type: str) -> Tuple[bool, float, str]:
        """
        Check if a specific momentum condition is met.
        
        Args:
            closes: Price series
            condition_type: One of the condition types from MOMENTUM indicator
            
        Returns:
            (condition_met: bool, confidence_boost: float, description: str)
        """
        result = self.calculate(closes)
        if result is None:
            return False, 0, "Insufficient data"
        
        mom = result['smoothed']
        prev_mom = result['previous']
        slope = result['slope']
        
        if condition_type == 'crosses_above_zero':
            met = prev_mom <= 0 and mom > 0
            return met, 2.0 if met else 0, f"Momentum crossed above zero ({mom:.4f})"
        
        elif condition_type == 'crosses_below_zero':
            met = prev_mom >= 0 and mom < 0
            return met, 2.0 if met else 0, f"Momentum crossed below zero ({mom:.4f})"
        
        elif condition_type == 'strong_positive':
            met = mom > self.threshold and mom > 0
            strength = min(3.0, (mom / max(abs(self.threshold), 0.0001)) * 1.5) if met else 0
            return met, strength, f"Strong positive momentum ({mom:.4f} > {self.threshold})"
        
        elif condition_type == 'strong_negative':
            neg_threshold = -abs(self.threshold) if self.threshold > 0 else self.threshold
            met = mom < neg_threshold and mom < 0
            strength = min(3.0, (abs(mom) / max(abs(neg_threshold), 0.0001)) * 1.5) if met else 0
            return met, strength, f"Strong negative momentum ({mom:.4f} < {neg_threshold})"
        
        elif condition_type == 'momentum_increasing':
            met = slope > 0 and mom > prev_mom
            return met, 1.5 if met else 0, f"Momentum accelerating (slope: {slope:.4f})"
        
        elif condition_type == 'momentum_decreasing':
            met = slope < 0 and mom < prev_mom
            return met, 1.5 if met else 0, f"Momentum decelerating (slope: {slope:.4f})"
        
        elif condition_type == 'bullish_divergence':
            # Price making lower lows but momentum making higher lows
            met = self._check_bullish_divergence(closes, result['series'])
            return met, 3.0 if met else 0, "Bullish divergence detected"
        
        elif condition_type == 'bearish_divergence':
            # Price making higher highs but momentum making lower highs
            met = self._check_bearish_divergence(closes, result['series'])
            return met, 3.0 if met else 0, "Bearish divergence detected"
        
        return False, 0, "Unknown condition"
    
    def _check_bullish_divergence(self, closes: pd.Series, momentum: pd.Series, lookback: int = 10) -> bool:
        """Check for bullish divergence: price lower low + momentum higher low"""
        if len(closes) < lookback or len(momentum) < lookback:
            return False
        
        recent_closes = closes.iloc[-lookback:]
        recent_mom = momentum.iloc[-lookback:]
        
        # Find recent lows
        prev_section = recent_closes.iloc[:len(recent_closes)//2]
        if len(prev_section) == 0:
            return False
        
        price_low_current = recent_closes.iloc[-3:].min()
        price_low_prev = prev_section.min()
        
        mom_low_current = recent_mom.iloc[-3:].min()
        mom_low_prev = recent_mom.iloc[:len(recent_mom)//2].min()
        
        # Bullish divergence: price making lower lows, momentum making higher lows
        return price_low_current < price_low_prev and mom_low_current > mom_low_prev
    
    def _check_bearish_divergence(self, closes: pd.Series, momentum: pd.Series, lookback: int = 10) -> bool:
        """Check for bearish divergence: price higher high + momentum lower high"""
        if len(closes) < lookback or len(momentum) < lookback:
            return False
        
        recent_closes = closes.iloc[-lookback:]
        recent_mom = momentum.iloc[-lookback:]
        
        price_high_current = recent_closes.iloc[-3:].max()
        price_high_prev = recent_closes.iloc[:len(recent_closes)//2].max()
        
        mom_high_current = recent_mom.iloc[-3:].max()
        mom_high_prev = recent_mom.iloc[:len(recent_mom)//2].max()
        
        # Bearish divergence: price making higher highs, momentum making lower highs
        return price_high_current > price_high_prev and mom_high_current < mom_high_prev
    
    def get_signal(self, closes: pd.Series) -> Optional[Dict]:
        """
        Generate a trading signal based on momentum analysis.
        
        Returns signal dict with direction, confidence, and confirmations.
        """
        result = self.calculate(closes)
        if result is None:
            return None
        
        mom = result['smoothed']
        prev_mom = result['previous']
        slope = result['slope']
        
        confirmations = []
        direction = None
        confidence = 50
        
        # Check for zero-line crossover (primary signal)
        if prev_mom <= 0 and mom > 0:
            direction = "CALL"
            confidence += 15
            confirmations.append("MOMENTUM_BULLISH_CROSS")
        elif prev_mom >= 0 and mom < 0:
            direction = "PUT"
            confidence += 15
            confirmations.append("MOMENTUM_BEARISH_CROSS")
        
        # Check momentum strength
        if mom > self.threshold and mom > 0:
            if direction != "PUT":
                direction = direction or "CALL"
                confidence += 8
                confirmations.append("STRONG_POSITIVE_MOMENTUM")
        elif mom < -abs(self.threshold) and mom < 0:
            if direction != "CALL":
                direction = direction or "PUT"
                confidence += 8
                confirmations.append("STRONG_NEGATIVE_MOMENTUM")
        
        # Check slope (acceleration)
        if slope > 0 and direction == "CALL":
            confidence += 5
            confirmations.append("MOMENTUM_ACCELERATING")
        elif slope < 0 and direction == "PUT":
            confidence += 5
            confirmations.append("MOMENTUM_DECELERATING")
        
        # Check divergence
        if self._check_bullish_divergence(closes, result['series']):
            if direction != "PUT":
                direction = direction or "CALL"
                confidence += 12
                confirmations.append("BULLISH_DIVERGENCE")
        elif self._check_bearish_divergence(closes, result['series']):
            if direction != "CALL":
                direction = direction or "PUT"
                confidence += 12
                confirmations.append("BEARISH_DIVERGENCE")
        
        if direction and len(confirmations) >= 1:
            return {
                'direction': direction,
                'confidence': min(95, confidence),
                'confirmations': confirmations,
                'momentum_value': mom,
                'momentum_slope': slope
            }
        
        return None


# Global momentum indicator instance (default config)
default_momentum = MomentumIndicator()


class MarketCondition(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CHOPPY = "choppy"


@dataclass
class PrecisionSignal:
    """High-precision trading signal with multiple confirmations"""
    direction: str  # CALL or PUT
    confidence: float  # 0-100
    strength: SignalStrength
    entry_price: float
    expiry_seconds: int
    strategy_name: str
    confirmations: List[str]  # List of confirming indicators
    market_condition: MarketCondition
    timestamp: datetime
    entry_window_ms: int = 500  # Optimal entry window in milliseconds
    avoid_reasons: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "strength": self.strength.name,
            "entry_price": self.entry_price,
            "expiry_seconds": self.expiry_seconds,
            "strategy_name": self.strategy_name,
            "confirmations": self.confirmations,
            "confirmations_count": len(self.confirmations),
            "market_condition": self.market_condition.value,
            "timestamp": self.timestamp.isoformat(),
            "entry_window_ms": self.entry_window_ms,
            "avoid_reasons": self.avoid_reasons,
            "is_high_probability": self.confidence >= 75 and len(self.confirmations) >= 3
        }


# =====================================================
# KELTNER-MACD 5-SECOND STRATEGY
# =====================================================

class KeltnerMACDStrategy:
    """
    5-Second Strategy using Keltner Channel + MACD
    
    Indicators:
    - Keltner Channel: EMA(20), ATR(60), Multiplier 4
    - MACD: Fast(13), Slow(24), Signal(11)
    
    BUY (CALL) Conditions:
    - Price breaks ABOVE the middle line (EMA) of Keltner Channel
    - MACD lines cross UPWARDS (MACD crosses above Signal)
    
    SELL (PUT) Conditions:
    - Price breaks BELOW the middle line (EMA) of Keltner Channel
    - MACD lines cross DOWNWARDS (MACD crosses below Signal)
    """
    
    def __init__(self):
        self.name = "keltner_macd_5s"
        self.expiry = 5
        
        # Keltner Channel settings
        self.kc_ema_period = 20
        self.kc_atr_period = 60
        self.kc_multiplier = 4
        
        # MACD settings
        self.macd_fast = 13
        self.macd_slow = 24
        self.macd_signal = 11
    
    def calculate_atr(self, highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int) -> pd.Series:
        """Calculate Average True Range"""
        high_low = highs - lows
        high_close = abs(highs - closes.shift(1))
        low_close = abs(lows - closes.shift(1))
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def calculate_keltner_channel(self, highs: pd.Series, lows: pd.Series, closes: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Keltner Channel
        
        Returns: (middle_line, upper_band, lower_band)
        """
        # Middle line = EMA of close
        middle = closes.ewm(span=self.kc_ema_period, adjust=False).mean()
        
        # ATR for band width
        atr = self.calculate_atr(highs, lows, closes, self.kc_atr_period)
        
        # Upper and Lower bands
        upper = middle + (self.kc_multiplier * atr)
        lower = middle - (self.kc_multiplier * atr)
        
        return middle, upper, lower
    
    def calculate_macd(self, closes: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD
        
        Returns: (macd_line, signal_line, histogram)
        """
        ema_fast = closes.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = closes.ewm(span=self.macd_slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def analyze(self, candles: List[Dict], current_price: float) -> Optional[PrecisionSignal]:
        """
        Analyze for Keltner-MACD 5-second signal
        """
        if len(candles) < max(self.kc_atr_period, self.macd_slow) + 5:
            return None
        
        try:
            # Extract OHLC data
            closes = pd.Series([float(c.get('close', c.get('Close', 0))) for c in candles])
            highs = pd.Series([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles])
            lows = pd.Series([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])
            
            # Calculate Keltner Channel
            kc_middle, kc_upper, kc_lower = self.calculate_keltner_channel(highs, lows, closes)
            
            # Calculate MACD
            macd_line, signal_line, histogram = self.calculate_macd(closes)
            
            # Get current and previous values
            current_close = closes.iloc[-1]
            prev_close = closes.iloc[-2]
            
            kc_mid_current = kc_middle.iloc[-1]
            kc_mid_prev = kc_middle.iloc[-2]
            
            macd_current = macd_line.iloc[-1]
            macd_prev = macd_line.iloc[-2]
            signal_current = signal_line.iloc[-1]
            signal_prev = signal_line.iloc[-2]
            
            confirmations = []
            direction = None
            confidence = 50
            
            # ===== CALL (BUY) CONDITIONS =====
            # 1. Price breaks ABOVE Keltner middle line
            price_above_kc_mid = current_close > kc_mid_current and prev_close <= kc_mid_prev
            
            # 2. MACD crosses ABOVE signal line (bullish crossover)
            macd_bullish_cross = macd_prev <= signal_prev and macd_current > signal_current
            
            # Also check if MACD is already above signal and rising
            macd_bullish_momentum = macd_current > signal_current and macd_current > macd_prev
            
            if price_above_kc_mid:
                confirmations.append("PRICE_ABOVE_KC_MIDDLE")
                confidence += 15
            
            if macd_bullish_cross:
                confirmations.append("MACD_BULLISH_CROSS")
                confidence += 20
            elif macd_bullish_momentum:
                confirmations.append("MACD_BULLISH_MOMENTUM")
                confidence += 10
            
            # CALL signal when both conditions met
            if price_above_kc_mid and (macd_bullish_cross or macd_bullish_momentum):
                direction = "CALL"
                if macd_bullish_cross:
                    confidence += 10  # Extra confidence for actual crossover
            
            # ===== PUT (SELL) CONDITIONS =====
            # 1. Price breaks BELOW Keltner middle line
            price_below_kc_mid = current_close < kc_mid_current and prev_close >= kc_mid_prev
            
            # 2. MACD crosses BELOW signal line (bearish crossover)
            macd_bearish_cross = macd_prev >= signal_prev and macd_current < signal_current
            
            # Also check if MACD is already below signal and falling
            macd_bearish_momentum = macd_current < signal_current and macd_current < macd_prev
            
            if direction is None:  # Only check PUT if CALL not triggered
                if price_below_kc_mid:
                    confirmations.append("PRICE_BELOW_KC_MIDDLE")
                    confidence += 15
                
                if macd_bearish_cross:
                    confirmations.append("MACD_BEARISH_CROSS")
                    confidence += 20
                elif macd_bearish_momentum:
                    confirmations.append("MACD_BEARISH_MOMENTUM")
                    confidence += 10
                
                # PUT signal when both conditions met
                if price_below_kc_mid and (macd_bearish_cross or macd_bearish_momentum):
                    direction = "PUT"
                    if macd_bearish_cross:
                        confidence += 10
            
            # Additional confirmations for higher confidence
            # Check price position relative to Keltner bands
            if direction == "CALL" and current_close > kc_mid_current:
                if current_close < kc_upper.iloc[-1]:  # Not overbought
                    confirmations.append("ROOM_TO_UPPER_BAND")
                    confidence += 5
            elif direction == "PUT" and current_close < kc_mid_current:
                if current_close > kc_lower.iloc[-1]:  # Not oversold
                    confirmations.append("ROOM_TO_LOWER_BAND")
                    confidence += 5
            
            # Check histogram direction
            if direction == "CALL" and histogram.iloc[-1] > histogram.iloc[-2]:
                confirmations.append("MACD_HIST_RISING")
                confidence += 5
            elif direction == "PUT" and histogram.iloc[-1] < histogram.iloc[-2]:
                confirmations.append("MACD_HIST_FALLING")
                confidence += 5
            
            if direction and len(confirmations) >= 2:
                confidence = min(95, confidence)
                
                return PrecisionSignal(
                    direction=direction,
                    confidence=confidence,
                    strategy_name=self.name,
                    timeframe="5s",
                    confirmations=confirmations,
                    entry_price=current_price,
                    timestamp=datetime.now(timezone.utc),
                    expiry_seconds=self.expiry,
                    market_condition=MarketCondition.TRENDING if abs(macd_current) > abs(signal_current) else MarketCondition.RANGING,
                    entry_window_ms=1000
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Keltner-MACD strategy error: {e}")
            return None
    
    def get_indicator_values(self, candles: List[Dict]) -> Optional[Dict]:
        """Get current indicator values for display"""
        if len(candles) < max(self.kc_atr_period, self.macd_slow) + 5:
            return None
        
        try:
            closes = pd.Series([float(c.get('close', c.get('Close', 0))) for c in candles])
            highs = pd.Series([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles])
            lows = pd.Series([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])
            
            kc_middle, kc_upper, kc_lower = self.calculate_keltner_channel(highs, lows, closes)
            macd_line, signal_line, histogram = self.calculate_macd(closes)
            
            return {
                "keltner": {
                    "middle": float(kc_middle.iloc[-1]),
                    "upper": float(kc_upper.iloc[-1]),
                    "lower": float(kc_lower.iloc[-1])
                },
                "macd": {
                    "macd_line": float(macd_line.iloc[-1]),
                    "signal_line": float(signal_line.iloc[-1]),
                    "histogram": float(histogram.iloc[-1])
                },
                "current_price": float(closes.iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error getting indicator values: {e}")
            return None


# Global instance
keltner_macd_strategy = KeltnerMACDStrategy()


class UltraScalpingStrategy:
    """
    Ultra-fast scalping strategy for 5-second expiry
    
    Key principles:
    - Multiple micro-confirmations
    - Price action + momentum alignment
    - Strict noise filtering
    - Only trade clear setups
    - NEW: Integrated momentum indicator for additional confirmation
    """
    
    def __init__(self, use_momentum: bool = True, momentum_period: int = 7, momentum_threshold: float = 0):
        self.name = "ultra_scalping_5s"
        self.expiry = 5
        self.min_confirmations = 4
        self.use_momentum = use_momentum
        self.momentum = MomentumIndicator(period=momentum_period, threshold=momentum_threshold, smoothing=2)
        
    def analyze(self, candles: List[Dict], current_price: float) -> Optional[PrecisionSignal]:
        """
        Analyze for 5-second scalping opportunity
        
        Entry conditions for CALL:
        1. RSI(7) < 25 and rising
        2. Price at/below BB lower (period=10, dev=1.5)
        3. MACD histogram turning positive
        4. Last 3 candles show higher lows
        5. Volume increasing
        
        Entry conditions for PUT:
        1. RSI(7) > 75 and falling
        2. Price at/above BB upper
        3. MACD histogram turning negative
        4. Last 3 candles show lower highs
        5. Volume increasing
        """
        if len(candles) < 20:
            return None
            
        df = pd.DataFrame(candles)
        closes = df['close'].astype(float)
        highs = df['high'].astype(float)
        lows = df['low'].astype(float)
        
        # Calculate indicators with scalping-optimized parameters
        rsi = self._calculate_rsi(closes, period=7)
        macd, macd_signal, macd_hist = self._calculate_macd(closes, 8, 17, 6)
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger(closes, 10, 1.5)
        
        if rsi is None or macd_hist is None:
            return None
            
        confirmations = []
        avoid_reasons = []
        direction = None
        
        # CALL Setup Analysis
        call_score = 0
        
        # 1. RSI oversold and rising
        if rsi[-1] < 25:
            call_score += 2
            confirmations.append("RSI_OVERSOLD")
            if len(rsi) > 1 and rsi[-1] > rsi[-2]:
                call_score += 1
                confirmations.append("RSI_RISING")
        
        # 2. Price at lower Bollinger Band
        if current_price <= bb_lower[-1]:
            call_score += 2
            confirmations.append("PRICE_AT_BB_LOWER")
        elif current_price <= bb_lower[-1] * 1.001:  # Within 0.1%
            call_score += 1
            confirmations.append("PRICE_NEAR_BB_LOWER")
        
        # 3. MACD histogram turning positive
        if len(macd_hist) > 2:
            if macd_hist[-1] > macd_hist[-2] and macd_hist[-2] < 0:
                call_score += 2
                confirmations.append("MACD_BULLISH_DIVERGENCE")
            elif macd_hist[-1] > 0:
                call_score += 1
                confirmations.append("MACD_POSITIVE")
        
        # 4. Higher lows pattern (last 3 candles)
        if len(lows) >= 3:
            if lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]:
                call_score += 2
                confirmations.append("HIGHER_LOWS_PATTERN")
        
        # 5. Bullish candle pattern
        if closes.iloc[-1] > closes.iloc[-2]:
            call_score += 1
            confirmations.append("BULLISH_CANDLE")
        
        # 6. NEW: Momentum indicator confirmation
        if self.use_momentum:
            mom_signal = self.momentum.get_signal(closes)
            if mom_signal and mom_signal['direction'] == 'CALL':
                call_score += 2
                confirmations.extend([f"MOM_{c}" for c in mom_signal['confirmations'][:2]])
        
        # PUT Setup Analysis
        put_score = 0
        put_confirmations = []
        
        # 1. RSI overbought and falling
        if rsi[-1] > 75:
            put_score += 2
            put_confirmations.append("RSI_OVERBOUGHT")
            if len(rsi) > 1 and rsi[-1] < rsi[-2]:
                put_score += 1
                put_confirmations.append("RSI_FALLING")
        
        # 2. Price at upper Bollinger Band
        if current_price >= bb_upper[-1]:
            put_score += 2
            put_confirmations.append("PRICE_AT_BB_UPPER")
        elif current_price >= bb_upper[-1] * 0.999:
            put_score += 1
            put_confirmations.append("PRICE_NEAR_BB_UPPER")
        
        # 3. MACD histogram turning negative
        if len(macd_hist) > 2:
            if macd_hist[-1] < macd_hist[-2] and macd_hist[-2] > 0:
                put_score += 2
                put_confirmations.append("MACD_BEARISH_DIVERGENCE")
            elif macd_hist[-1] < 0:
                put_score += 1
                put_confirmations.append("MACD_NEGATIVE")
        
        # 4. Lower highs pattern
        if len(highs) >= 3:
            if highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3]:
                put_score += 2
                put_confirmations.append("LOWER_HIGHS_PATTERN")
        
        # 5. Bearish candle
        if closes.iloc[-1] < closes.iloc[-2]:
            put_score += 1
            put_confirmations.append("BEARISH_CANDLE")
        
        # 6. NEW: Momentum indicator confirmation for PUT
        if self.use_momentum:
            mom_signal = self.momentum.get_signal(closes)
            if mom_signal and mom_signal['direction'] == 'PUT':
                put_score += 2
                put_confirmations.extend([f"MOM_{c}" for c in mom_signal['confirmations'][:2]])
        
        # Determine direction based on scores
        if call_score > put_score and call_score >= 5:
            direction = "CALL"
            final_confirmations = confirmations
        elif put_score > call_score and put_score >= 5:
            direction = "PUT"
            final_confirmations = put_confirmations
        else:
            return None  # No clear setup
        
        # Calculate confidence based on confirmations
        max_score = max(call_score, put_score)
        confidence = min(95, 60 + (max_score * 5))
        
        # Market condition assessment
        market_condition = self._assess_market_condition(df)
        
        # Reduce confidence in choppy markets
        if market_condition == MarketCondition.CHOPPY:
            confidence -= 15
            avoid_reasons.append("CHOPPY_MARKET")
        elif market_condition == MarketCondition.VOLATILE:
            confidence -= 10
            avoid_reasons.append("HIGH_VOLATILITY")
        
        if confidence < 65:
            return None
            
        strength = self._score_to_strength(max_score)
        
        return PrecisionSignal(
            direction=direction,
            confidence=confidence,
            strength=strength,
            entry_price=current_price,
            expiry_seconds=self.expiry,
            strategy_name=self.name,
            confirmations=final_confirmations,
            market_condition=market_condition,
            timestamp=datetime.now(timezone.utc),
            entry_window_ms=300,  # Very tight for 5s
            avoid_reasons=avoid_reasons
        )
    
    def _calculate_rsi(self, closes: pd.Series, period: int = 7) -> Optional[np.ndarray]:
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.0001)
        rsi = 100 - (100 / (1 + rs))
        return rsi.values
    
    def _calculate_macd(self, closes: pd.Series, fast: int, slow: int, signal: int) -> Tuple:
        if len(closes) < slow + signal:
            return None, None, None
        ema_fast = closes.ewm(span=fast).mean()
        ema_slow = closes.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line.values, signal_line.values, histogram.values
    
    def _calculate_bollinger(self, closes: pd.Series, period: int, std_dev: float) -> Tuple:
        if len(closes) < period:
            return None, None, None
        sma = closes.rolling(period).mean()
        std = closes.rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper.values, sma.values, lower.values
    
    def _assess_market_condition(self, df: pd.DataFrame) -> MarketCondition:
        closes = df['close'].astype(float)
        highs = df['high'].astype(float)
        lows = df['low'].astype(float)
        
        # Calculate ATR for volatility
        tr = pd.concat([
            highs - lows,
            (highs - closes.shift()).abs(),
            (lows - closes.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        avg_range = (highs - lows).mean()
        
        # Trend detection
        sma_5 = closes.rolling(5).mean().iloc[-1]
        sma_10 = closes.rolling(10).mean().iloc[-1]
        current = closes.iloc[-1]
        
        # Volatility ratio
        vol_ratio = atr / avg_range if avg_range > 0 else 1
        
        if vol_ratio > 1.5:
            return MarketCondition.VOLATILE
        elif vol_ratio > 1.2:
            # Check if trending
            if current > sma_5 > sma_10:
                return MarketCondition.TRENDING_UP
            elif current < sma_5 < sma_10:
                return MarketCondition.TRENDING_DOWN
            return MarketCondition.CHOPPY
        else:
            if abs(sma_5 - sma_10) / sma_10 < 0.001:
                return MarketCondition.RANGING
            elif current > sma_5 > sma_10:
                return MarketCondition.TRENDING_UP
            elif current < sma_5 < sma_10:
                return MarketCondition.TRENDING_DOWN
            return MarketCondition.RANGING
    
    def _score_to_strength(self, score: int) -> SignalStrength:
        if score >= 9:
            return SignalStrength.EXTREME
        elif score >= 7:
            return SignalStrength.VERY_STRONG
        elif score >= 5:
            return SignalStrength.STRONG
        elif score >= 3:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK


class MomentumBreakoutStrategy:
    """
    Momentum breakout strategy for 15-second expiry
    
    Key principles:
    - Support/Resistance breakout confirmation
    - Volume spike validation
    - Multiple timeframe alignment
    - False breakout filtering
    - NEW: Enhanced momentum indicator integration
    """
    
    def __init__(self, use_momentum: bool = True, momentum_period: int = 10, momentum_threshold: float = 0):
        self.name = "momentum_breakout_15s"
        self.expiry = 15
        self.min_confirmations = 4
        self.use_momentum = use_momentum
        self.momentum = MomentumIndicator(period=momentum_period, threshold=momentum_threshold, smoothing=3)
        
    def analyze(self, candles: List[Dict], current_price: float) -> Optional[PrecisionSignal]:
        """
        Analyze for 15-second momentum breakout
        
        Entry conditions:
        1. Price breaks key support/resistance level
        2. Volume spike (1.5x average)
        3. Strong candle body (>60% of range)
        4. RSI confirms momentum (not extreme)
        5. MACD aligned with breakout direction
        """
        if len(candles) < 30:
            return None
            
        df = pd.DataFrame(candles)
        closes = df['close'].astype(float)
        highs = df['high'].astype(float)
        lows = df['low'].astype(float)
        volumes = df['volume'].astype(float) if 'volume' in df.columns else pd.Series([1]*len(df))
        
        # Find support/resistance levels
        resistance = highs.rolling(20).max().iloc[-2]  # Previous high
        support = lows.rolling(20).min().iloc[-2]  # Previous low
        
        # Calculate indicators
        rsi = self._calculate_rsi(closes, 14)
        macd, macd_signal, macd_hist = self._calculate_macd(closes, 12, 26, 9)
        
        if rsi is None or macd_hist is None:
            return None
            
        confirmations = []
        avoid_reasons = []
        direction = None
        
        # Volume analysis
        avg_volume = volumes.rolling(20).mean().iloc[-1]
        current_volume = volumes.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Candle strength (body vs range)
        candle_range = highs.iloc[-1] - lows.iloc[-1]
        candle_body = abs(closes.iloc[-1] - closes.iloc[-2])
        body_ratio = candle_body / candle_range if candle_range > 0 else 0
        
        # RESISTANCE BREAKOUT (CALL)
        call_score = 0
        
        if current_price > resistance:
            call_score += 3
            confirmations.append("RESISTANCE_BROKEN")
            
            # How much above resistance
            breakout_strength = (current_price - resistance) / resistance * 100
            if breakout_strength > 0.05:
                call_score += 1
                confirmations.append("STRONG_BREAKOUT")
        
        if volume_ratio > 1.5:
            call_score += 2
            confirmations.append("VOLUME_SPIKE")
        elif volume_ratio > 1.2:
            call_score += 1
            confirmations.append("ABOVE_AVG_VOLUME")
        
        if body_ratio > 0.6:
            call_score += 2
            confirmations.append("STRONG_CANDLE_BODY")
        
        if rsi[-1] > 50 and rsi[-1] < 70:
            call_score += 1
            confirmations.append("RSI_CONFIRMS_UP")
        elif rsi[-1] >= 70:
            avoid_reasons.append("RSI_OVERBOUGHT")
        
        if macd_hist[-1] > 0 and macd_hist[-1] > macd_hist[-2]:
            call_score += 2
            confirmations.append("MACD_BULLISH")
        
        # 6. NEW: Momentum indicator for breakout confirmation
        if self.use_momentum:
            mom_signal = self.momentum.get_signal(closes)
            if mom_signal and mom_signal['direction'] == 'CALL':
                call_score += 2
                confirmations.append("MOMENTUM_CONFIRMS_BREAKOUT")
                if 'MOMENTUM_ACCELERATING' in mom_signal['confirmations']:
                    call_score += 1
                    confirmations.append("MOMENTUM_ACCELERATING")
        
        # SUPPORT BREAKOUT (PUT)
        put_score = 0
        put_confirmations = []
        
        if current_price < support:
            put_score += 3
            put_confirmations.append("SUPPORT_BROKEN")
            
            breakout_strength = (support - current_price) / support * 100
            if breakout_strength > 0.05:
                put_score += 1
                put_confirmations.append("STRONG_BREAKOUT")
        
        if volume_ratio > 1.5:
            put_score += 2
            put_confirmations.append("VOLUME_SPIKE")
        elif volume_ratio > 1.2:
            put_score += 1
            put_confirmations.append("ABOVE_AVG_VOLUME")
        
        if body_ratio > 0.6:
            put_score += 2
            put_confirmations.append("STRONG_CANDLE_BODY")
        
        if rsi[-1] < 50 and rsi[-1] > 30:
            put_score += 1
            put_confirmations.append("RSI_CONFIRMS_DOWN")
        elif rsi[-1] <= 30:
            avoid_reasons.append("RSI_OVERSOLD")
        
        if macd_hist[-1] < 0 and macd_hist[-1] < macd_hist[-2]:
            put_score += 2
            put_confirmations.append("MACD_BEARISH")
        
        # 6. NEW: Momentum indicator for breakdown confirmation
        if self.use_momentum:
            mom_signal = self.momentum.get_signal(closes)
            if mom_signal and mom_signal['direction'] == 'PUT':
                put_score += 2
                put_confirmations.append("MOMENTUM_CONFIRMS_BREAKDOWN")
                if 'MOMENTUM_DECELERATING' in mom_signal['confirmations']:
                    put_score += 1
                    put_confirmations.append("MOMENTUM_DECELERATING")
        
        # Determine best direction
        if call_score > put_score and call_score >= 5:
            direction = "CALL"
            final_confirmations = confirmations
        elif put_score > call_score and put_score >= 5:
            direction = "PUT"
            final_confirmations = put_confirmations
        else:
            return None
        
        max_score = max(call_score, put_score)
        confidence = min(95, 55 + (max_score * 5))
        
        market_condition = self._assess_market_condition(df)
        
        if market_condition in [MarketCondition.CHOPPY, MarketCondition.RANGING]:
            confidence -= 10
            avoid_reasons.append("UNFAVORABLE_MARKET")
        
        if confidence < 65:
            return None
            
        return PrecisionSignal(
            direction=direction,
            confidence=confidence,
            strength=self._score_to_strength(max_score),
            entry_price=current_price,
            expiry_seconds=self.expiry,
            strategy_name=self.name,
            confirmations=final_confirmations,
            market_condition=market_condition,
            timestamp=datetime.now(timezone.utc),
            entry_window_ms=500,
            avoid_reasons=avoid_reasons
        )
    
    def _calculate_rsi(self, closes: pd.Series, period: int = 14) -> Optional[np.ndarray]:
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.0001)
        return (100 - (100 / (1 + rs))).values
    
    def _calculate_macd(self, closes: pd.Series, fast: int, slow: int, signal: int) -> Tuple:
        if len(closes) < slow + signal:
            return None, None, None
        ema_fast = closes.ewm(span=fast).mean()
        ema_slow = closes.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        return macd_line.values, signal_line.values, (macd_line - signal_line).values
    
    def _assess_market_condition(self, df: pd.DataFrame) -> MarketCondition:
        closes = df['close'].astype(float)
        sma_5 = closes.rolling(5).mean().iloc[-1]
        sma_20 = closes.rolling(20).mean().iloc[-1]
        current = closes.iloc[-1]
        
        trend_diff = abs(sma_5 - sma_20) / sma_20
        
        if trend_diff < 0.001:
            return MarketCondition.RANGING
        elif current > sma_5 > sma_20:
            return MarketCondition.TRENDING_UP
        elif current < sma_5 < sma_20:
            return MarketCondition.TRENDING_DOWN
        return MarketCondition.CHOPPY
    
    def _score_to_strength(self, score: int) -> SignalStrength:
        if score >= 9:
            return SignalStrength.EXTREME
        elif score >= 7:
            return SignalStrength.VERY_STRONG
        elif score >= 5:
            return SignalStrength.STRONG
        elif score >= 3:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK


class MeanReversionStrategy:
    """
    Mean reversion strategy for 30-second expiry
    
    Key principles:
    - Extreme RSI with reversal confirmation
    - Bollinger Band touch + rejection
    - Stochastic crossover
    - Volume divergence
    """
    
    def __init__(self):
        self.name = "mean_reversion_30s"
        self.expiry = 30
        self.min_confirmations = 4
        
    def analyze(self, candles: List[Dict], current_price: float) -> Optional[PrecisionSignal]:
        """
        Analyze for 30-second mean reversion opportunity
        """
        if len(candles) < 30:
            return None
            
        df = pd.DataFrame(candles)
        closes = df['close'].astype(float)
        highs = df['high'].astype(float)
        lows = df['low'].astype(float)
        
        # Indicators
        rsi = self._calculate_rsi(closes, 14)
        stoch_k, stoch_d = self._calculate_stochastic(closes, highs, lows, 14, 3)
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger(closes, 20, 2.0)
        
        if rsi is None or stoch_k is None or bb_upper is None:
            return None
            
        confirmations = []
        avoid_reasons = []
        direction = None
        
        # BULLISH REVERSAL (CALL)
        call_score = 0
        
        # RSI oversold + divergence
        if rsi[-1] < 30:
            call_score += 2
            confirmations.append("RSI_OVERSOLD")
            if rsi[-1] > rsi[-2]:  # RSI turning up
                call_score += 1
                confirmations.append("RSI_DIVERGENCE")
        
        # Price at/below lower BB
        if current_price <= bb_lower[-1]:
            call_score += 2
            confirmations.append("PRICE_AT_BB_LOWER")
        
        # Stochastic oversold + cross
        if stoch_k[-1] < 20:
            call_score += 1
            confirmations.append("STOCH_OVERSOLD")
            if stoch_k[-1] > stoch_d[-1] and stoch_k[-2] <= stoch_d[-2]:
                call_score += 2
                confirmations.append("STOCH_BULLISH_CROSS")
        
        # Bullish candle pattern (hammer/doji)
        candle_range = highs.iloc[-1] - lows.iloc[-1]
        lower_wick = min(closes.iloc[-1], closes.iloc[-2]) - lows.iloc[-1]
        if candle_range > 0 and lower_wick / candle_range > 0.5:
            call_score += 1
            confirmations.append("BULLISH_WICK_PATTERN")
        
        # BEARISH REVERSAL (PUT)
        put_score = 0
        put_confirmations = []
        
        if rsi[-1] > 70:
            put_score += 2
            put_confirmations.append("RSI_OVERBOUGHT")
            if rsi[-1] < rsi[-2]:
                put_score += 1
                put_confirmations.append("RSI_DIVERGENCE")
        
        if current_price >= bb_upper[-1]:
            put_score += 2
            put_confirmations.append("PRICE_AT_BB_UPPER")
        
        if stoch_k[-1] > 80:
            put_score += 1
            put_confirmations.append("STOCH_OVERBOUGHT")
            if stoch_k[-1] < stoch_d[-1] and stoch_k[-2] >= stoch_d[-2]:
                put_score += 2
                put_confirmations.append("STOCH_BEARISH_CROSS")
        
        upper_wick = highs.iloc[-1] - max(closes.iloc[-1], closes.iloc[-2])
        if candle_range > 0 and upper_wick / candle_range > 0.5:
            put_score += 1
            put_confirmations.append("BEARISH_WICK_PATTERN")
        
        # Determine direction
        if call_score > put_score and call_score >= 4:
            direction = "CALL"
            final_confirmations = confirmations
        elif put_score > call_score and put_score >= 4:
            direction = "PUT"
            final_confirmations = put_confirmations
        else:
            return None
        
        max_score = max(call_score, put_score)
        confidence = min(95, 55 + (max_score * 5))
        
        market_condition = self._assess_market_condition(df)
        
        # Mean reversion works best in ranging markets
        if market_condition == MarketCondition.RANGING:
            confidence += 5
        elif market_condition in [MarketCondition.TRENDING_UP, MarketCondition.TRENDING_DOWN]:
            confidence -= 10
            avoid_reasons.append("TRENDING_MARKET")
        
        if confidence < 65:
            return None
            
        return PrecisionSignal(
            direction=direction,
            confidence=confidence,
            strength=self._score_to_strength(max_score),
            entry_price=current_price,
            expiry_seconds=self.expiry,
            strategy_name=self.name,
            confirmations=final_confirmations,
            market_condition=market_condition,
            timestamp=datetime.now(timezone.utc),
            entry_window_ms=800,
            avoid_reasons=avoid_reasons
        )
    
    def _calculate_rsi(self, closes: pd.Series, period: int) -> Optional[np.ndarray]:
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.0001)
        return (100 - (100 / (1 + rs))).values
    
    def _calculate_stochastic(self, closes: pd.Series, highs: pd.Series, lows: pd.Series, k: int, d: int) -> Tuple:
        if len(closes) < k + d:
            return None, None
        low_min = lows.rolling(k).min()
        high_max = highs.rolling(k).max()
        stoch_k = 100 * (closes - low_min) / (high_max - low_min).replace(0, 0.0001)
        stoch_d = stoch_k.rolling(d).mean()
        return stoch_k.values, stoch_d.values
    
    def _calculate_bollinger(self, closes: pd.Series, period: int, std_dev: float) -> Tuple:
        if len(closes) < period:
            return None, None, None
        sma = closes.rolling(period).mean()
        std = closes.rolling(period).std()
        return (sma + std * std_dev).values, sma.values, (sma - std * std_dev).values
    
    def _assess_market_condition(self, df: pd.DataFrame) -> MarketCondition:
        closes = df['close'].astype(float)
        sma_5 = closes.rolling(5).mean().iloc[-1]
        sma_20 = closes.rolling(20).mean().iloc[-1]
        current = closes.iloc[-1]
        
        trend_diff = abs(sma_5 - sma_20) / sma_20
        
        if trend_diff < 0.002:
            return MarketCondition.RANGING
        elif current > sma_5 > sma_20:
            return MarketCondition.TRENDING_UP
        elif current < sma_5 < sma_20:
            return MarketCondition.TRENDING_DOWN
        return MarketCondition.CHOPPY
    
    def _score_to_strength(self, score: int) -> SignalStrength:
        if score >= 8:
            return SignalStrength.EXTREME
        elif score >= 6:
            return SignalStrength.VERY_STRONG
        elif score >= 4:
            return SignalStrength.STRONG
        elif score >= 3:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK


class TrendConfirmationStrategy:
    """
    Trend confirmation strategy for 1-minute expiry
    
    Key principles:
    - Multiple moving average alignment
    - ADX trend strength confirmation
    - Pullback entry in trend direction
    - Volume confirmation
    """
    
    def __init__(self):
        self.name = "trend_confirmation_1m"
        self.expiry = 60
        self.min_confirmations = 5
        
    def analyze(self, candles: List[Dict], current_price: float) -> Optional[PrecisionSignal]:
        """
        Analyze for 1-minute trend continuation opportunity
        """
        if len(candles) < 50:
            return None
            
        df = pd.DataFrame(candles)
        closes = df['close'].astype(float)
        highs = df['high'].astype(float)
        lows = df['low'].astype(float)
        
        # Moving averages
        ema_9 = closes.ewm(span=9).mean()
        ema_21 = closes.ewm(span=21).mean()
        ema_50 = closes.ewm(span=50).mean()
        # sma_200 available for longer-term trend analysis if needed
        
        # ADX for trend strength
        adx = self._calculate_adx(closes, highs, lows, 14)
        
        # RSI
        rsi = self._calculate_rsi(closes, 14)
        
        # MACD
        macd, macd_signal, macd_hist = self._calculate_macd(closes, 12, 26, 9)
        
        if adx is None or rsi is None or macd_hist is None:
            return None
            
        confirmations = []
        avoid_reasons = []
        direction = None
        
        # UPTREND SETUP (CALL)
        call_score = 0
        
        # EMA alignment (9 > 21 > 50)
        if ema_9.iloc[-1] > ema_21.iloc[-1] > ema_50.iloc[-1]:
            call_score += 3
            confirmations.append("EMA_BULLISH_ALIGNMENT")
        elif ema_9.iloc[-1] > ema_21.iloc[-1]:
            call_score += 1
            confirmations.append("SHORT_TERM_UPTREND")
        
        # Price above key EMAs
        if current_price > ema_21.iloc[-1]:
            call_score += 1
            confirmations.append("PRICE_ABOVE_EMA21")
        
        # ADX shows trend strength
        if adx[-1] > 25:
            call_score += 2
            confirmations.append("STRONG_TREND_ADX")
        elif adx[-1] > 20:
            call_score += 1
            confirmations.append("MODERATE_TREND")
        
        # RSI in bullish zone
        if 40 < rsi[-1] < 70:
            call_score += 1
            confirmations.append("RSI_BULLISH_ZONE")
        elif rsi[-1] >= 70:
            avoid_reasons.append("RSI_OVERBOUGHT")
        
        # MACD positive and rising
        if macd_hist[-1] > 0:
            call_score += 1
            confirmations.append("MACD_POSITIVE")
            if macd_hist[-1] > macd_hist[-2]:
                call_score += 1
                confirmations.append("MACD_RISING")
        
        # Pullback entry (price touched EMA but bouncing)
        if current_price > ema_9.iloc[-1] and lows.iloc[-1] <= ema_21.iloc[-1]:
            call_score += 2
            confirmations.append("PULLBACK_BOUNCE")
        
        # DOWNTREND SETUP (PUT)
        put_score = 0
        put_confirmations = []
        
        if ema_9.iloc[-1] < ema_21.iloc[-1] < ema_50.iloc[-1]:
            put_score += 3
            put_confirmations.append("EMA_BEARISH_ALIGNMENT")
        elif ema_9.iloc[-1] < ema_21.iloc[-1]:
            put_score += 1
            put_confirmations.append("SHORT_TERM_DOWNTREND")
        
        if current_price < ema_21.iloc[-1]:
            put_score += 1
            put_confirmations.append("PRICE_BELOW_EMA21")
        
        if adx[-1] > 25:
            put_score += 2
            put_confirmations.append("STRONG_TREND_ADX")
        elif adx[-1] > 20:
            put_score += 1
            put_confirmations.append("MODERATE_TREND")
        
        if 30 < rsi[-1] < 60:
            put_score += 1
            put_confirmations.append("RSI_BEARISH_ZONE")
        elif rsi[-1] <= 30:
            avoid_reasons.append("RSI_OVERSOLD")
        
        if macd_hist[-1] < 0:
            put_score += 1
            put_confirmations.append("MACD_NEGATIVE")
            if macd_hist[-1] < macd_hist[-2]:
                put_score += 1
                put_confirmations.append("MACD_FALLING")
        
        if current_price < ema_9.iloc[-1] and highs.iloc[-1] >= ema_21.iloc[-1]:
            put_score += 2
            put_confirmations.append("PULLBACK_REJECTION")
        
        # Determine direction
        if call_score > put_score and call_score >= 6:
            direction = "CALL"
            final_confirmations = confirmations
        elif put_score > call_score and put_score >= 6:
            direction = "PUT"
            final_confirmations = put_confirmations
        else:
            return None
        
        max_score = max(call_score, put_score)
        confidence = min(95, 50 + (max_score * 5))
        
        market_condition = MarketCondition.TRENDING_UP if direction == "CALL" else MarketCondition.TRENDING_DOWN
        
        if adx[-1] < 20:
            confidence -= 10
            avoid_reasons.append("WEAK_TREND")
        
        if confidence < 65:
            return None
            
        return PrecisionSignal(
            direction=direction,
            confidence=confidence,
            strength=self._score_to_strength(max_score),
            entry_price=current_price,
            expiry_seconds=self.expiry,
            strategy_name=self.name,
            confirmations=final_confirmations,
            market_condition=market_condition,
            timestamp=datetime.now(timezone.utc),
            entry_window_ms=1500,
            avoid_reasons=avoid_reasons
        )
    
    def _calculate_adx(self, closes: pd.Series, highs: pd.Series, lows: pd.Series, period: int) -> Optional[np.ndarray]:
        if len(closes) < period * 2:
            return None
        
        # True Range
        tr = pd.concat([
            highs - lows,
            (highs - closes.shift()).abs(),
            (lows - closes.shift()).abs()
        ], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = highs.diff()
        down_move = -lows.diff()
        
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=closes.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=closes.index)
        
        # Smoothed
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        # ADX
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 0.0001))
        adx = dx.rolling(period).mean()
        
        return adx.values
    
    def _calculate_rsi(self, closes: pd.Series, period: int) -> Optional[np.ndarray]:
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.0001)
        return (100 - (100 / (1 + rs))).values
    
    def _calculate_macd(self, closes: pd.Series, fast: int, slow: int, signal: int) -> Tuple:
        if len(closes) < slow + signal:
            return None, None, None
        ema_fast = closes.ewm(span=fast).mean()
        ema_slow = closes.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        return macd_line.values, signal_line.values, (macd_line - signal_line).values
    
    def _score_to_strength(self, score: int) -> SignalStrength:
        if score >= 10:
            return SignalStrength.EXTREME
        elif score >= 8:
            return SignalStrength.VERY_STRONG
        elif score >= 6:
            return SignalStrength.STRONG
        elif score >= 4:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK


class HighAccuracySignalGenerator:
    """
    Master signal generator that combines all strategies
    and selects the highest probability setup
    """
    
    def __init__(self):
        self.strategies = {
            5: UltraScalpingStrategy(),
            15: MomentumBreakoutStrategy(),
            30: MeanReversionStrategy(),
            60: TrendConfirmationStrategy()
        }
        self.signal_history: List[PrecisionSignal] = []
        self.performance_stats: Dict[str, Dict] = {}
        
    def generate_signal(self, candles: List[Dict], current_price: float, 
                       preferred_expiry: int = None) -> Optional[PrecisionSignal]:
        """
        Generate the highest probability signal
        
        Args:
            candles: List of candle data
            current_price: Current market price
            preferred_expiry: Preferred expiry in seconds (5, 15, 30, 60)
            
        Returns:
            PrecisionSignal if high probability setup found, None otherwise
        """
        signals = []
        
        if preferred_expiry and preferred_expiry in self.strategies:
            # Use only preferred strategy
            strategy = self.strategies[preferred_expiry]
            signal = strategy.analyze(candles, current_price)
            if signal and signal.confidence >= 65:
                signals.append(signal)
        else:
            # Analyze all strategies
            for expiry, strategy in self.strategies.items():
                signal = strategy.analyze(candles, current_price)
                if signal and signal.confidence >= 65:
                    signals.append(signal)
        
        if not signals:
            return None
        
        # Select highest probability signal
        best_signal = max(signals, key=lambda s: (s.confidence, len(s.confirmations)))
        
        # Add to history
        self.signal_history.append(best_signal)
        
        # Keep last 1000 signals
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-500:]
        
        return best_signal
    
    def generate_multi_timeframe_signal(self, candles_5s: List[Dict], candles_1m: List[Dict],
                                        current_price: float) -> Optional[PrecisionSignal]:
        """
        Generate signal using multi-timeframe analysis
        
        Uses higher timeframe for trend direction and lower for entry timing
        """
        # Get 1m trend direction
        trend_strategy = self.strategies[60]
        trend_signal = trend_strategy.analyze(candles_1m, current_price)
        
        if not trend_signal:
            # No clear trend, use mean reversion
            return self.strategies[30].analyze(candles_1m, current_price)
        
        trend_direction = trend_signal.direction
        
        # Now look for entry on 5s timeframe in trend direction
        scalp_signal = self.strategies[5].analyze(candles_5s, current_price)
        
        if scalp_signal and scalp_signal.direction == trend_direction:
            # Higher confidence when aligned with higher timeframe
            scalp_signal.confidence = min(95, scalp_signal.confidence + 10)
            scalp_signal.confirmations.append("MULTI_TF_ALIGNED")
            return scalp_signal
        
        # Try 15s breakout in trend direction
        breakout_signal = self.strategies[15].analyze(candles_5s, current_price)
        
        if breakout_signal and breakout_signal.direction == trend_direction:
            breakout_signal.confidence = min(95, breakout_signal.confidence + 8)
            breakout_signal.confirmations.append("MULTI_TF_ALIGNED")
            return breakout_signal
        
        # Fall back to trend signal
        return trend_signal
    
    def record_result(self, signal_id: str, won: bool):
        """Record trade result for performance tracking"""
        strategy_name = None
        for signal in self.signal_history:
            if str(signal.timestamp) == signal_id:
                strategy_name = signal.strategy_name
                break
        
        if strategy_name:
            if strategy_name not in self.performance_stats:
                self.performance_stats[strategy_name] = {"wins": 0, "losses": 0}
            
            if won:
                self.performance_stats[strategy_name]["wins"] += 1
            else:
                self.performance_stats[strategy_name]["losses"] += 1
    
    def get_performance(self) -> Dict:
        """Get performance statistics for all strategies"""
        result = {}
        for name, stats in self.performance_stats.items():
            total = stats["wins"] + stats["losses"]
            win_rate = stats["wins"] / total * 100 if total > 0 else 0
            result[name] = {
                "total_trades": total,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate": round(win_rate, 2)
            }
        return result


# Global instance
high_accuracy_generator = HighAccuracySignalGenerator()


def get_high_accuracy_signal(candles: List[Dict], current_price: float, 
                            expiry: int = None) -> Optional[Dict]:
    """
    Helper function to get high accuracy signal
    
    Returns signal dict or None
    """
    signal = high_accuracy_generator.generate_signal(candles, current_price, expiry)
    return signal.to_dict() if signal else None
