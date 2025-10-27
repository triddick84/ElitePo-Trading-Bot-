"""
Advanced Candlestick Pattern Recognition for Pocket Option
Based on proven high-accuracy patterns from Pocket Option strategies

Implements:
1. Engulfing Pattern (Trend Reversal)
2. Squatting Candlestick / Doji (Market Uncertainty)
3. Tweezers (Strong Reversal)
4. Three Methods (Trend Continuation)

Each pattern includes confidence scoring and trade signal generation.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class AdvancedCandlestickPatterns:
    """
    Advanced candlestick pattern recognition optimized for binary options
    """
    
    def __init__(self):
        # Pattern detection sensitivity
        self.engulfing_min_body_ratio = 1.1  # New candle must be 110% of previous
        self.doji_body_ratio = 0.1  # Body < 10% of total range
        self.tweezer_tolerance_pct = 0.002  # 0.2% tolerance for matching extremes
        
    def detect_all_patterns(self, df: pd.DataFrame) -> Dict:
        """
        Detect all candlestick patterns in the data
        
        Returns:
            Dict with pattern names and their presence/strength
        """
        if df is None or len(df) < 3:
            return self._empty_patterns()
        
        try:
            patterns = {
                'engulfing': self.detect_engulfing_pattern(df),
                'squatting_doji': self.detect_squatting_doji(df),
                'tweezers': self.detect_tweezers(df),
                'three_methods': self.detect_three_methods(df),
                'hammer': self.detect_hammer_shooting_star(df, pattern_type='hammer'),
                'shooting_star': self.detect_hammer_shooting_star(df, pattern_type='shooting_star')
            }
            
            # Determine strongest pattern
            strongest = self._get_strongest_pattern(patterns)
            patterns['strongest'] = strongest
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")
            return self._empty_patterns()
    
    def detect_engulfing_pattern(self, df: pd.DataFrame) -> Dict:
        """
        Engulfing Pattern: One candlestick fully overlaps the previous one
        
        Bullish Engulfing:
        - Previous candle: bearish (close < open)
        - Current candle: bullish (close > open)
        - Current body > previous body
        - Current low < previous low
        - Current high > previous high
        
        Trade Signal: Strong reversal signal
        
        Returns:
            Dict with pattern type, confidence, and trade signal
        """
        if len(df) < 2:
            return {'detected': False, 'type': None, 'confidence': 0}
        
        try:
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Calculate body sizes
            prev_body = abs(previous['open'] - previous['close'])
            curr_body = abs(current['open'] - current['close'])
            
            # Bullish Engulfing
            if (previous['close'] < previous['open'] and  # Previous bearish
                current['close'] > current['open'] and    # Current bullish
                curr_body >= prev_body * self.engulfing_min_body_ratio and  # Body ratio
                current['low'] <= previous['low'] and     # Engulfs low
                current['high'] >= previous['high']):     # Engulfs high
                
                # Calculate confidence based on body ratio
                body_ratio = curr_body / prev_body if prev_body > 0 else 1
                confidence = min(70 + (body_ratio - 1) * 20, 95)
                
                return {
                    'detected': True,
                    'type': 'bullish_engulfing',
                    'confidence': round(confidence, 1),
                    'trade_signal': 'CALL',
                    'description': 'Bullish engulfing pattern - strong reversal up',
                    'body_ratio': round(body_ratio, 2)
                }
            
            # Bearish Engulfing
            elif (previous['close'] > previous['open'] and  # Previous bullish
                  current['close'] < current['open'] and    # Current bearish
                  curr_body >= prev_body * self.engulfing_min_body_ratio and
                  current['low'] <= previous['low'] and
                  current['high'] >= previous['high']):
                
                body_ratio = curr_body / prev_body if prev_body > 0 else 1
                confidence = min(70 + (body_ratio - 1) * 20, 95)
                
                return {
                    'detected': True,
                    'type': 'bearish_engulfing',
                    'confidence': round(confidence, 1),
                    'trade_signal': 'PUT',
                    'description': 'Bearish engulfing pattern - strong reversal down',
                    'body_ratio': round(body_ratio, 2)
                }
            
            return {'detected': False, 'type': None, 'confidence': 0}
            
        except Exception as e:
            logger.error(f"Error detecting engulfing: {e}")
            return {'detected': False, 'type': None, 'confidence': 0}
    
    def detect_squatting_doji(self, df: pd.DataFrame) -> Dict:
        """
        Squatting Candlestick / Doji: Small body with long shadows
        Indicates market uncertainty and possible reversal
        
        Characteristics:
        - Small body (< 10% of total range)
        - Long shadows (both upper and lower)
        - Signals indecision
        
        Trade Signal: Wait for confirmation from next candle
        
        Returns:
            Dict with pattern detection and uncertainty level
        """
        if len(df) < 1:
            return {'detected': False, 'uncertainty_level': 0}
        
        try:
            current = df.iloc[-1]
            
            # Calculate ranges
            total_range = current['high'] - current['low']
            body_size = abs(current['close'] - current['open'])
            
            if total_range == 0:
                return {'detected': False, 'uncertainty_level': 0}
            
            body_ratio = body_size / total_range
            
            # Detect Doji/Squatting pattern
            if body_ratio <= self.doji_body_ratio:
                # Calculate shadow lengths
                upper_shadow = current['high'] - max(current['open'], current['close'])
                lower_shadow = min(current['open'], current['close']) - current['low']
                
                # Uncertainty level based on shadow balance
                shadow_balance = 1 - abs(upper_shadow - lower_shadow) / total_range
                uncertainty_level = min(shadow_balance * 100, 95)
                
                # Determine bias (if any)
                if upper_shadow > lower_shadow * 1.5:
                    bias = 'bearish_bias'
                    next_signal_hint = 'PUT'
                elif lower_shadow > upper_shadow * 1.5:
                    bias = 'bullish_bias'
                    next_signal_hint = 'CALL'
                else:
                    bias = 'neutral'
                    next_signal_hint = 'WAIT'
                
                return {
                    'detected': True,
                    'type': 'squatting_doji',
                    'uncertainty_level': round(uncertainty_level, 1),
                    'body_ratio': round(body_ratio, 3),
                    'bias': bias,
                    'next_signal_hint': next_signal_hint,
                    'description': 'Market uncertainty - wait for next candle confirmation',
                    'upper_shadow_pct': round((upper_shadow / total_range) * 100, 1),
                    'lower_shadow_pct': round((lower_shadow / total_range) * 100, 1)
                }
            
            return {'detected': False, 'uncertainty_level': 0}
            
        except Exception as e:
            logger.error(f"Error detecting doji: {e}")
            return {'detected': False, 'uncertainty_level': 0}
    
    def detect_tweezers(self, df: pd.DataFrame) -> Dict:
        """
        Tweezers: Two candlesticks with identical extremes but opposite directions
        Strong reversal signal when combined with other patterns
        
        Tweezer Top (Bearish):
        - Two candles with matching highs
        - Opposite directions
        - Signal: Reversal down
        
        Tweezer Bottom (Bullish):
        - Two candles with matching lows
        - Opposite directions
        - Signal: Reversal up
        
        Returns:
            Dict with pattern type and reversal strength
        """
        if len(df) < 2:
            return {'detected': False, 'type': None, 'confidence': 0}
        
        try:
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Calculate tolerance based on price level
            avg_price = (current['high'] + current['low']) / 2
            tolerance = avg_price * self.tweezer_tolerance_pct
            
            # Check if candles are opposite directions
            prev_is_bullish = previous['close'] > previous['open']
            curr_is_bullish = current['close'] > current['open']
            opposite_directions = prev_is_bullish != curr_is_bullish
            
            # Tweezer Top (matching highs)
            if opposite_directions and abs(current['high'] - previous['high']) <= tolerance:
                confidence = 75 + min((1 - abs(current['high'] - previous['high']) / tolerance) * 20, 20)
                
                return {
                    'detected': True,
                    'type': 'tweezer_top',
                    'confidence': round(confidence, 1),
                    'trade_signal': 'PUT',
                    'description': 'Tweezer top - strong reversal down',
                    'high_match_diff': round(abs(current['high'] - previous['high']), 5)
                }
            
            # Tweezer Bottom (matching lows)
            elif opposite_directions and abs(current['low'] - previous['low']) <= tolerance:
                confidence = 75 + min((1 - abs(current['low'] - previous['low']) / tolerance) * 20, 20)
                
                return {
                    'detected': True,
                    'type': 'tweezer_bottom',
                    'confidence': round(confidence, 1),
                    'trade_signal': 'CALL',
                    'description': 'Tweezer bottom - strong reversal up',
                    'low_match_diff': round(abs(current['low'] - previous['low']), 5)
                }
            
            return {'detected': False, 'type': None, 'confidence': 0}
            
        except Exception as e:
            logger.error(f"Error detecting tweezers: {e}")
            return {'detected': False, 'type': None, 'confidence': 0}
    
    def detect_three_methods(self, df: pd.DataFrame) -> Dict:
        """
        Three Methods: Small candlesticks after a long one within the current trend
        Signals trend continuation when new long candlestick appears
        
        Bullish Three Methods:
        - Long bullish candle
        - 2-3 small candles within range (consolidation)
        - New long bullish candle (continuation)
        
        Bearish Three Methods:
        - Long bearish candle
        - 2-3 small candles within range
        - New long bearish candle (continuation)
        
        Returns:
            Dict with pattern type and continuation confidence
        """
        if len(df) < 5:
            return {'detected': False, 'type': None, 'confidence': 0}
        
        try:
            # Check last 5 candles
            candles = df.iloc[-5:]
            
            first = candles.iloc[0]
            middle_candles = candles.iloc[1:4]
            last = candles.iloc[4]
            
            # Calculate body sizes
            first_body = abs(first['close'] - first['open'])
            last_body = abs(last['close'] - last['open'])
            first_range = first['high'] - first['low']
            
            # Check if middle candles are small
            middle_bodies = [abs(c['close'] - c['open']) for _, c in middle_candles.iterrows()]
            avg_middle_body = np.mean(middle_bodies)
            
            # Bullish Three Methods
            if (first['close'] > first['open'] and  # First bullish
                last['close'] > last['open'] and    # Last bullish
                last_body >= first_body * 0.8 and   # Last candle strong
                avg_middle_body < first_body * 0.3 and  # Middle candles small
                all(first['low'] <= c['low'] and c['high'] <= first['high'] 
                    for _, c in middle_candles.iterrows())):  # Middle within range
                
                return {
                    'detected': True,
                    'type': 'bullish_three_methods',
                    'confidence': 80,
                    'trade_signal': 'CALL',
                    'description': 'Bullish three methods - trend continuation up',
                    'consolidation_candles': len(middle_candles)
                }
            
            # Bearish Three Methods
            elif (first['close'] < first['open'] and  # First bearish
                  last['close'] < last['open'] and    # Last bearish
                  last_body >= first_body * 0.8 and
                  avg_middle_body < first_body * 0.3 and
                  all(first['low'] <= c['low'] and c['high'] <= first['high']
                      for _, c in middle_candles.iterrows())):
                
                return {
                    'detected': True,
                    'type': 'bearish_three_methods',
                    'confidence': 80,
                    'trade_signal': 'PUT',
                    'description': 'Bearish three methods - trend continuation down',
                    'consolidation_candles': len(middle_candles)
                }
            
            return {'detected': False, 'type': None, 'confidence': 0}
            
        except Exception as e:
            logger.error(f"Error detecting three methods: {e}")
            return {'detected': False, 'type': None, 'confidence': 0}
    
    def detect_hammer_shooting_star(self, df: pd.DataFrame, pattern_type: str = 'hammer') -> Dict:
        """
        Detect Hammer or Shooting Star patterns
        """
        if len(df) < 1:
            return {'detected': False}
        
        try:
            current = df.iloc[-1]
            
            total_range = current['high'] - current['low']
            body_size = abs(current['close'] - current['open'])
            
            if total_range == 0:
                return {'detected': False}
            
            upper_shadow = current['high'] - max(current['open'], current['close'])
            lower_shadow = min(current['open'], current['close']) - current['low']
            
            if pattern_type == 'hammer':
                # Hammer: small body, long lower shadow, small upper shadow
                if (body_size < total_range * 0.25 and
                    lower_shadow > body_size * 2 and
                    upper_shadow < body_size * 0.5):
                    return {
                        'detected': True,
                        'type': 'hammer',
                        'confidence': 70,
                        'trade_signal': 'CALL',
                        'description': 'Hammer pattern - potential reversal up'
                    }
            
            elif pattern_type == 'shooting_star':
                # Shooting Star: small body, long upper shadow, small lower shadow
                if (body_size < total_range * 0.25 and
                    upper_shadow > body_size * 2 and
                    lower_shadow < body_size * 0.5):
                    return {
                        'detected': True,
                        'type': 'shooting_star',
                        'confidence': 70,
                        'trade_signal': 'PUT',
                        'description': 'Shooting star - potential reversal down'
                    }
            
            return {'detected': False}
            
        except Exception as e:
            logger.error(f"Error detecting {pattern_type}: {e}")
            return {'detected': False}
    
    def _get_strongest_pattern(self, patterns: Dict) -> Dict:
        """
        Determine the strongest detected pattern
        """
        strongest = {'pattern': None, 'confidence': 0, 'signal': None}
        
        for pattern_name, pattern_data in patterns.items():
            if isinstance(pattern_data, dict) and pattern_data.get('detected'):
                confidence = pattern_data.get('confidence', 0)
                if confidence > strongest['confidence']:
                    strongest = {
                        'pattern': pattern_name,
                        'confidence': confidence,
                        'signal': pattern_data.get('trade_signal'),
                        'description': pattern_data.get('description')
                    }
        
        return strongest
    
    def _empty_patterns(self) -> Dict:
        """Return empty patterns dict"""
        return {
            'engulfing': {'detected': False},
            'squatting_doji': {'detected': False},
            'tweezers': {'detected': False},
            'three_methods': {'detected': False},
            'hammer': {'detected': False},
            'shooting_star': {'detected': False},
            'strongest': {'pattern': None, 'confidence': 0, 'signal': None}
        }


# Global instance
advanced_patterns = AdvancedCandlestickPatterns()
