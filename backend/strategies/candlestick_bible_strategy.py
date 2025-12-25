"""
Candlestick Bible Trading Strategy
===================================
Based on "The Candlestick Trading Bible" patterns and rules.

Implements:
- Bullish Patterns: Engulfing, Hammer, Morning Star, Dragonfly Doji, Tweezers Bottom, Bullish Harami
- Bearish Patterns: Engulfing, Shooting Star, Evening Star, Gravestone Doji, Tweezers Top, Bearish Harami
- Inside Bar patterns with false breakout detection
- Support/Resistance confirmation
- Risk/Reward optimization (minimum 1:2)

Pattern Success Rates (from research):
- Inside Bar bearish reversal in bull market: ~65%
- Inside Bar bullish continuation: ~52%
- Bullish Abandoned Baby: ~70% in bull, ~55% in bear
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    # Bullish Patterns
    BULLISH_ENGULFING = "bullish_engulfing"
    HAMMER = "hammer"
    MORNING_STAR = "morning_star"
    DRAGONFLY_DOJI = "dragonfly_doji"
    TWEEZERS_BOTTOM = "tweezers_bottom"
    BULLISH_HARAMI = "bullish_harami"
    BULLISH_INSIDE_BAR_BREAKOUT = "bullish_inside_bar_breakout"
    
    # Bearish Patterns
    BEARISH_ENGULFING = "bearish_engulfing"
    SHOOTING_STAR = "shooting_star"
    EVENING_STAR = "evening_star"
    GRAVESTONE_DOJI = "gravestone_doji"
    TWEEZERS_TOP = "tweezers_top"
    BEARISH_HARAMI = "bearish_harami"
    BEARISH_INSIDE_BAR_BREAKOUT = "bearish_inside_bar_breakout"
    
    # Neutral/Reversal
    DOJI = "doji"
    INSIDE_BAR = "inside_bar"


@dataclass
class CandlestickPattern:
    """Represents a detected candlestick pattern"""
    pattern_type: PatternType
    signal: str  # 'BUY', 'SELL', 'NEUTRAL'
    confidence: float  # 0-100
    strength: str  # 'STRONG', 'MODERATE', 'WEAK'
    at_key_level: bool
    trend_alignment: bool
    description: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float


class CandlestickBibleStrategy:
    """
    Advanced candlestick pattern recognition based on The Candlestick Trading Bible.
    
    Key Principles:
    1. Trade with confluence (trend + level + signal)
    2. Minimum 1:2 risk/reward ratio
    3. Pattern must form at key support/resistance levels
    4. Trend confirmation required for high-probability trades
    """
    
    def __init__(self, 
                 min_risk_reward: float = 2.0,
                 body_to_shadow_ratio: float = 2.0,  # For pin bars
                 doji_threshold: float = 0.1,  # Max body size as % of range
                 lookback_period: int = 20):  # For S/R detection
        
        self.min_risk_reward = min_risk_reward
        self.body_to_shadow_ratio = body_to_shadow_ratio
        self.doji_threshold = doji_threshold
        self.lookback_period = lookback_period
        
        # Pattern success probabilities (from research)
        self.pattern_probabilities = {
            PatternType.BULLISH_ENGULFING: 0.68,
            PatternType.BEARISH_ENGULFING: 0.68,
            PatternType.HAMMER: 0.65,
            PatternType.SHOOTING_STAR: 0.65,
            PatternType.MORNING_STAR: 0.72,
            PatternType.EVENING_STAR: 0.72,
            PatternType.DRAGONFLY_DOJI: 0.60,
            PatternType.GRAVESTONE_DOJI: 0.60,
            PatternType.TWEEZERS_BOTTOM: 0.62,
            PatternType.TWEEZERS_TOP: 0.62,
            PatternType.BULLISH_HARAMI: 0.55,
            PatternType.BEARISH_HARAMI: 0.55,
            PatternType.BULLISH_INSIDE_BAR_BREAKOUT: 0.65,
            PatternType.BEARISH_INSIDE_BAR_BREAKOUT: 0.65,
            PatternType.DOJI: 0.50,
            PatternType.INSIDE_BAR: 0.52,
        }
        
        logger.info("📕 Candlestick Bible Strategy initialized")
    
    def _get_candle_metrics(self, candle: Dict) -> Dict:
        """Calculate key metrics for a candlestick"""
        open_price = candle['open']
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        body = abs(close - open_price)
        range_size = high - low
        upper_shadow = high - max(open_price, close)
        lower_shadow = min(open_price, close) - low
        
        is_bullish = close > open_price
        is_bearish = close < open_price
        
        body_percent = (body / range_size * 100) if range_size > 0 else 0
        
        return {
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'body': body,
            'range': range_size,
            'upper_shadow': upper_shadow,
            'lower_shadow': lower_shadow,
            'is_bullish': is_bullish,
            'is_bearish': is_bearish,
            'body_percent': body_percent,
            'midpoint': (high + low) / 2,
            'body_midpoint': (open_price + close) / 2
        }
    
    def _detect_trend(self, candles: List[Dict], period: int = 20) -> str:
        """
        Detect market trend based on higher highs/higher lows or lower highs/lower lows.
        Returns: 'UPTREND', 'DOWNTREND', 'RANGING'
        """
        if len(candles) < period:
            return 'RANGING'
        
        recent = candles[-period:]
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        
        # Check for higher highs and higher lows (uptrend)
        higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
        
        # Check for lower highs and lower lows (downtrend)
        lower_highs = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
        lower_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        
        uptrend_score = (higher_highs + higher_lows) / (2 * (period - 1))
        downtrend_score = (lower_highs + lower_lows) / (2 * (period - 1))
        
        if uptrend_score > 0.6:
            return 'UPTREND'
        elif downtrend_score > 0.6:
            return 'DOWNTREND'
        else:
            return 'RANGING'
    
    def _find_support_resistance(self, candles: List[Dict], tolerance: float = 0.002) -> Tuple[List[float], List[float]]:
        """
        Find key support and resistance levels from price action.
        Returns: (support_levels, resistance_levels)
        """
        if len(candles) < 10:
            return [], []
        
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        
        # Find swing highs (resistance) and swing lows (support)
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(candles) - 2):
            # Swing high: higher than 2 candles on each side
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append(highs[i])
            
            # Swing low: lower than 2 candles on each side
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append(lows[i])
        
        # Cluster similar levels
        def cluster_levels(levels, tol):
            if not levels:
                return []
            levels = sorted(levels)
            clusters = [[levels[0]]]
            for level in levels[1:]:
                if abs(level - clusters[-1][-1]) / clusters[-1][-1] < tol:
                    clusters[-1].append(level)
                else:
                    clusters.append([level])
            return [sum(c) / len(c) for c in clusters]
        
        resistance = cluster_levels(swing_highs, tolerance)
        support = cluster_levels(swing_lows, tolerance)
        
        return support, resistance
    
    def _is_near_key_level(self, price: float, supports: List[float], resistances: List[float], tolerance: float = 0.003) -> Tuple[bool, str]:
        """Check if price is near a key support or resistance level"""
        for support in supports:
            if abs(price - support) / support < tolerance:
                return True, 'support'
        
        for resistance in resistances:
            if abs(price - resistance) / resistance < tolerance:
                return True, 'resistance'
        
        return False, 'none'
    
    # ==================== PATTERN DETECTION METHODS ====================
    
    def _detect_doji(self, candle: Dict) -> bool:
        """Detect Doji pattern - open and close are same or very close"""
        metrics = self._get_candle_metrics(candle)
        return metrics['body_percent'] < self.doji_threshold * 100
    
    def _detect_hammer(self, candle: Dict) -> bool:
        """
        Detect Hammer (Bullish Pin Bar):
        - Small body near the high
        - Long lower shadow (at least 2x body)
        - Little to no upper shadow
        """
        m = self._get_candle_metrics(candle)
        if m['range'] == 0:
            return False
        
        # Lower shadow should be at least 2x the body
        lower_shadow_ratio = m['lower_shadow'] / m['body'] if m['body'] > 0 else float('inf')
        
        # Upper shadow should be small
        upper_shadow_ratio = m['upper_shadow'] / m['range']
        
        # Body should be in upper third
        body_position = (min(m['open'], m['close']) - m['low']) / m['range']
        
        return (lower_shadow_ratio >= self.body_to_shadow_ratio and 
                upper_shadow_ratio < 0.15 and 
                body_position > 0.6)
    
    def _detect_shooting_star(self, candle: Dict) -> bool:
        """
        Detect Shooting Star (Bearish Pin Bar):
        - Small body near the low
        - Long upper shadow (at least 2x body)
        - Little to no lower shadow
        """
        m = self._get_candle_metrics(candle)
        if m['range'] == 0:
            return False
        
        # Upper shadow should be at least 2x the body
        upper_shadow_ratio = m['upper_shadow'] / m['body'] if m['body'] > 0 else float('inf')
        
        # Lower shadow should be small
        lower_shadow_ratio = m['lower_shadow'] / m['range']
        
        # Body should be in lower third
        body_position = (m['high'] - max(m['open'], m['close'])) / m['range']
        
        return (upper_shadow_ratio >= self.body_to_shadow_ratio and 
                lower_shadow_ratio < 0.15 and 
                body_position > 0.6)
    
    def _detect_dragonfly_doji(self, candle: Dict) -> bool:
        """
        Detect Dragonfly Doji:
        - Open, high, and close are same or very close
        - Long lower tail
        """
        m = self._get_candle_metrics(candle)
        if m['range'] == 0:
            return False
        
        # Body should be very small (Doji-like)
        is_doji = m['body_percent'] < 10
        
        # Lower shadow should be significant
        lower_shadow_pct = m['lower_shadow'] / m['range']
        
        # Upper shadow should be minimal
        upper_shadow_pct = m['upper_shadow'] / m['range']
        
        return is_doji and lower_shadow_pct > 0.6 and upper_shadow_pct < 0.1
    
    def _detect_gravestone_doji(self, candle: Dict) -> bool:
        """
        Detect Gravestone Doji:
        - Open, low, and close are same or very close
        - Long upper tail
        """
        m = self._get_candle_metrics(candle)
        if m['range'] == 0:
            return False
        
        # Body should be very small (Doji-like)
        is_doji = m['body_percent'] < 10
        
        # Upper shadow should be significant
        upper_shadow_pct = m['upper_shadow'] / m['range']
        
        # Lower shadow should be minimal
        lower_shadow_pct = m['lower_shadow'] / m['range']
        
        return is_doji and upper_shadow_pct > 0.6 and lower_shadow_pct < 0.1
    
    def _detect_engulfing(self, candles: List[Dict]) -> Tuple[bool, str]:
        """
        Detect Engulfing Pattern (needs 2 candles):
        - Bullish: Second candle completely engulfs first (at downtrend end)
        - Bearish: Second candle completely engulfs first (at uptrend end)
        Returns: (is_engulfing, 'bullish'/'bearish'/None)
        """
        if len(candles) < 2:
            return False, None
        
        first = self._get_candle_metrics(candles[-2])
        second = self._get_candle_metrics(candles[-1])
        
        # Bullish engulfing: bearish first, bullish second that engulfs
        if first['is_bearish'] and second['is_bullish']:
            if second['body'] > first['body'] and \
               second['close'] > first['open'] and second['open'] < first['close']:
                return True, 'bullish'
        
        # Bearish engulfing: bullish first, bearish second that engulfs
        if first['is_bullish'] and second['is_bearish']:
            if second['body'] > first['body'] and \
               second['close'] < first['open'] and second['open'] > first['close']:
                return True, 'bearish'
        
        return False, None
    
    def _detect_morning_star(self, candles: List[Dict]) -> bool:
        """
        Detect Morning Star (needs 3 candles):
        1. First: Bearish candle
        2. Second: Small candle (consolidation)
        3. Third: Bullish candle closing above first candle's midpoint
        """
        if len(candles) < 3:
            return False
        
        first = self._get_candle_metrics(candles[-3])
        second = self._get_candle_metrics(candles[-2])
        third = self._get_candle_metrics(candles[-1])
        
        # First candle must be bearish with decent body
        if not first['is_bearish'] or first['body_percent'] < 50:
            return False
        
        # Second candle must be small (star)
        if second['body_percent'] > 40:
            return False
        
        # Third candle must be bullish and close above first's midpoint
        if not third['is_bullish']:
            return False
        
        first_midpoint = (first['open'] + first['close']) / 2
        return third['close'] > first_midpoint
    
    def _detect_evening_star(self, candles: List[Dict]) -> bool:
        """
        Detect Evening Star (needs 3 candles):
        1. First: Bullish candle
        2. Second: Small candle (consolidation)
        3. Third: Bearish candle closing below first candle's midpoint
        """
        if len(candles) < 3:
            return False
        
        first = self._get_candle_metrics(candles[-3])
        second = self._get_candle_metrics(candles[-2])
        third = self._get_candle_metrics(candles[-1])
        
        # First candle must be bullish with decent body
        if not first['is_bullish'] or first['body_percent'] < 50:
            return False
        
        # Second candle must be small (star)
        if second['body_percent'] > 40:
            return False
        
        # Third candle must be bearish and close below first's midpoint
        if not third['is_bearish']:
            return False
        
        first_midpoint = (first['open'] + first['close']) / 2
        return third['close'] < first_midpoint
    
    def _detect_tweezers(self, candles: List[Dict]) -> Tuple[bool, str]:
        """
        Detect Tweezers Tops/Bottoms (needs 2 candles):
        - Tweezers Bottom: Bearish then bullish, same lows
        - Tweezers Top: Bullish then bearish, same highs
        """
        if len(candles) < 2:
            return False, None
        
        first = self._get_candle_metrics(candles[-2])
        second = self._get_candle_metrics(candles[-1])
        
        tolerance = 0.001  # 0.1% tolerance for "same" price
        
        # Tweezers Bottom
        if first['is_bearish'] and second['is_bullish']:
            if abs(first['low'] - second['low']) / first['low'] < tolerance:
                return True, 'bottom'
        
        # Tweezers Top
        if first['is_bullish'] and second['is_bearish']:
            if abs(first['high'] - second['high']) / first['high'] < tolerance:
                return True, 'top'
        
        return False, None
    
    def _detect_harami(self, candles: List[Dict]) -> Tuple[bool, str]:
        """
        Detect Harami Pattern (needs 2 candles):
        - Mother candle followed by smaller baby candle within mother's body
        """
        if len(candles) < 2:
            return False, None
        
        mother = self._get_candle_metrics(candles[-2])
        baby = self._get_candle_metrics(candles[-1])
        
        # Baby must be smaller and contained within mother's body
        mother_top = max(mother['open'], mother['close'])
        mother_bottom = min(mother['open'], mother['close'])
        baby_top = max(baby['open'], baby['close'])
        baby_bottom = min(baby['open'], baby['close'])
        
        if baby_top <= mother_top and baby_bottom >= mother_bottom:
            if mother['is_bearish'] and baby['is_bullish']:
                return True, 'bullish'
            elif mother['is_bullish'] and baby['is_bearish']:
                return True, 'bearish'
        
        return False, None
    
    def _detect_inside_bar(self, candles: List[Dict]) -> bool:
        """
        Detect Inside Bar:
        - Current candle's high is lower than previous high
        - Current candle's low is higher than previous low
        """
        if len(candles) < 2:
            return False
        
        mother = candles[-2]
        inside = candles[-1]
        
        return inside['high'] < mother['high'] and inside['low'] > mother['low']
    
    def _detect_inside_bar_false_breakout(self, candles: List[Dict]) -> Tuple[bool, str]:
        """
        Detect Inside Bar False Breakout:
        - Inside bar setup
        - Price breaks out but reverses back within mother bar range
        """
        if len(candles) < 3:
            return False, None
        
        mother = candles[-3]
        inside = candles[-2]
        current = candles[-1]
        
        # Check if previous candle was inside bar
        if not (inside['high'] < mother['high'] and inside['low'] > mother['low']):
            return False, None
        
        # Bullish false breakout: broke below then closed back inside
        if current['low'] < mother['low'] and current['close'] > mother['low']:
            return True, 'bullish'
        
        # Bearish false breakout: broke above then closed back inside
        if current['high'] > mother['high'] and current['close'] < mother['high']:
            return True, 'bearish'
        
        return False, None
    
    # ==================== MAIN ANALYSIS METHOD ====================
    
    def analyze(self, candles: List[Dict]) -> Optional[CandlestickPattern]:
        """
        Analyze candles and return the detected pattern with trading signal.
        
        Args:
            candles: List of OHLC candle dicts with keys: open, high, low, close, volume
            
        Returns:
            CandlestickPattern if a valid pattern is found, None otherwise
        """
        if len(candles) < 3:
            return None
        
        current_candle = candles[-1]
        current_price = current_candle['close']
        
        # Detect trend
        trend = self._detect_trend(candles)
        
        # Find support/resistance levels
        supports, resistances = self._find_support_resistance(candles[:-1])
        
        # Check if near key level
        near_level, level_type = self._is_near_key_level(current_price, supports, resistances)
        
        # Detect patterns (order by priority)
        patterns_found = []
        
        # 3-candle patterns (highest priority)
        if self._detect_morning_star(candles):
            patterns_found.append((PatternType.MORNING_STAR, 'BUY'))
        
        if self._detect_evening_star(candles):
            patterns_found.append((PatternType.EVENING_STAR, 'SELL'))
        
        # Inside bar false breakout
        ib_fb, ib_fb_dir = self._detect_inside_bar_false_breakout(candles)
        if ib_fb:
            if ib_fb_dir == 'bullish':
                patterns_found.append((PatternType.BULLISH_INSIDE_BAR_BREAKOUT, 'BUY'))
            else:
                patterns_found.append((PatternType.BEARISH_INSIDE_BAR_BREAKOUT, 'SELL'))
        
        # 2-candle patterns
        is_engulfing, eng_dir = self._detect_engulfing(candles)
        if is_engulfing:
            if eng_dir == 'bullish':
                patterns_found.append((PatternType.BULLISH_ENGULFING, 'BUY'))
            else:
                patterns_found.append((PatternType.BEARISH_ENGULFING, 'SELL'))
        
        is_tweezers, tw_type = self._detect_tweezers(candles)
        if is_tweezers:
            if tw_type == 'bottom':
                patterns_found.append((PatternType.TWEEZERS_BOTTOM, 'BUY'))
            else:
                patterns_found.append((PatternType.TWEEZERS_TOP, 'SELL'))
        
        is_harami, har_dir = self._detect_harami(candles)
        if is_harami:
            if har_dir == 'bullish':
                patterns_found.append((PatternType.BULLISH_HARAMI, 'BUY'))
            else:
                patterns_found.append((PatternType.BEARISH_HARAMI, 'SELL'))
        
        # 1-candle patterns
        if self._detect_hammer(current_candle):
            patterns_found.append((PatternType.HAMMER, 'BUY'))
        
        if self._detect_shooting_star(current_candle):
            patterns_found.append((PatternType.SHOOTING_STAR, 'SELL'))
        
        if self._detect_dragonfly_doji(current_candle):
            patterns_found.append((PatternType.DRAGONFLY_DOJI, 'BUY'))
        
        if self._detect_gravestone_doji(current_candle):
            patterns_found.append((PatternType.GRAVESTONE_DOJI, 'SELL'))
        
        if not patterns_found:
            return None
        
        # Select the best pattern (highest probability with confluence)
        best_pattern = None
        best_score = 0
        
        for pattern_type, signal in patterns_found:
            base_prob = self.pattern_probabilities.get(pattern_type, 0.5)
            
            # Calculate confluence score
            score = base_prob * 100
            
            # Bonus for being at key level
            if near_level:
                score += 15
                if (signal == 'BUY' and level_type == 'support') or \
                   (signal == 'SELL' and level_type == 'resistance'):
                    score += 10  # Extra bonus for correct level type
            
            # Bonus/penalty for trend alignment
            if (signal == 'BUY' and trend == 'UPTREND') or \
               (signal == 'SELL' and trend == 'DOWNTREND'):
                score += 10  # Trading with trend
            elif (signal == 'BUY' and trend == 'DOWNTREND') or \
                 (signal == 'SELL' and trend == 'UPTREND'):
                # Counter-trend trade at key level is OK (reversal)
                if near_level:
                    score += 5
                else:
                    score -= 10
            
            if score > best_score:
                best_score = score
                best_pattern = (pattern_type, signal, score)
        
        if not best_pattern:
            return None
        
        pattern_type, signal, confidence = best_pattern
        
        # Calculate stop loss and take profit
        atr = self._calculate_atr(candles)
        
        if signal == 'BUY':
            # Stop below recent low or pattern low
            stop_loss = min(c['low'] for c in candles[-3:]) - atr * 0.5
            take_profit = current_price + (current_price - stop_loss) * self.min_risk_reward
        else:
            # Stop above recent high or pattern high
            stop_loss = max(c['high'] for c in candles[-3:]) + atr * 0.5
            take_profit = current_price - (stop_loss - current_price) * self.min_risk_reward
        
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Determine strength
        if confidence >= 80:
            strength = 'STRONG'
        elif confidence >= 65:
            strength = 'MODERATE'
        else:
            strength = 'WEAK'
        
        # Determine trend alignment
        trend_alignment = (signal == 'BUY' and trend != 'DOWNTREND') or \
                         (signal == 'SELL' and trend != 'UPTREND')
        
        return CandlestickPattern(
            pattern_type=pattern_type,
            signal=signal,
            confidence=min(confidence, 95),  # Cap at 95%
            strength=strength,
            at_key_level=near_level,
            trend_alignment=trend_alignment,
            description=self._get_pattern_description(pattern_type, signal, trend, near_level, level_type),
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=rr_ratio
        )
    
    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(candles) < period + 1:
            # Fallback: use average range
            return sum(c['high'] - c['low'] for c in candles) / len(candles)
        
        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        
        return sum(tr_list[-period:]) / period
    
    def _get_pattern_description(self, pattern_type: PatternType, signal: str, 
                                  trend: str, near_level: bool, level_type: str) -> str:
        """Generate human-readable description of the pattern"""
        pattern_names = {
            PatternType.BULLISH_ENGULFING: "Bullish Engulfing",
            PatternType.BEARISH_ENGULFING: "Bearish Engulfing",
            PatternType.HAMMER: "Hammer (Bullish Pin Bar)",
            PatternType.SHOOTING_STAR: "Shooting Star (Bearish Pin Bar)",
            PatternType.MORNING_STAR: "Morning Star",
            PatternType.EVENING_STAR: "Evening Star",
            PatternType.DRAGONFLY_DOJI: "Dragonfly Doji",
            PatternType.GRAVESTONE_DOJI: "Gravestone Doji",
            PatternType.TWEEZERS_BOTTOM: "Tweezers Bottom",
            PatternType.TWEEZERS_TOP: "Tweezers Top",
            PatternType.BULLISH_HARAMI: "Bullish Harami",
            PatternType.BEARISH_HARAMI: "Bearish Harami",
            PatternType.BULLISH_INSIDE_BAR_BREAKOUT: "Bullish Inside Bar False Breakout",
            PatternType.BEARISH_INSIDE_BAR_BREAKOUT: "Bearish Inside Bar False Breakout",
        }
        
        name = pattern_names.get(pattern_type, pattern_type.value)
        desc = f"📊 {name} pattern detected"
        
        if near_level:
            desc += f" at {level_type}"
        
        desc += f" | Trend: {trend}"
        
        if signal == 'BUY':
            desc += " | Signal: 🟢 BUY (CALL)"
        else:
            desc += " | Signal: 🔴 SELL (PUT)"
        
        return desc


# Singleton instance
candlestick_bible_strategy = CandlestickBibleStrategy()


def analyze_candles(candles: List[Dict]) -> Optional[Dict]:
    """
    Public function to analyze candles using the Candlestick Bible Strategy.
    
    Args:
        candles: List of OHLC candle dicts
        
    Returns:
        Dict with pattern info and trading signal, or None
    """
    pattern = candlestick_bible_strategy.analyze(candles)
    
    if pattern is None:
        return None
    
    return {
        'pattern': pattern.pattern_type.value,
        'signal': pattern.signal,
        'confidence': pattern.confidence,
        'strength': pattern.strength,
        'at_key_level': pattern.at_key_level,
        'trend_alignment': pattern.trend_alignment,
        'description': pattern.description,
        'entry_price': pattern.entry_price,
        'stop_loss': pattern.stop_loss,
        'take_profit': pattern.take_profit,
        'risk_reward_ratio': pattern.risk_reward_ratio
    }
