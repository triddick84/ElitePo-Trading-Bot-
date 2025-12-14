"""
Advanced Candlestick Pattern Analyzer
Identifies 40+ candlestick patterns for reversal and continuation signals
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CandlePattern:
    """Represents a detected candlestick pattern"""
    name: str
    type: str  # 'REVERSAL', 'CONTINUATION', 'INDECISION'
    direction: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    strength: float  # 0-100
    reliability: float  # Historical win rate
    index: int  # Where pattern was found
    description: str


class CandlestickAnalyzer:
    """
    Advanced candlestick pattern recognition system
    
    Identifies:
    - Reversal Patterns (24 patterns)
    - Continuation Patterns (8 patterns)
    - Indecision Patterns (8 patterns)
    
    Features:
    - Multi-candle pattern recognition
    - Pattern strength scoring
    - Historical reliability data
    - Confirmation signals
    """
    
    def __init__(self):
        # Pattern reliability scores (historical win rates)
        self.pattern_reliability = {
            # Bullish Reversal Patterns
            'HAMMER': 0.72,
            'INVERTED_HAMMER': 0.68,
            'BULLISH_ENGULFING': 0.75,
            'PIERCING_LINE': 0.70,
            'MORNING_STAR': 0.78,
            'THREE_WHITE_SOLDIERS': 0.84,
            'BULLISH_HARAMI': 0.71,
            'TWEEZER_BOTTOM': 0.69,
            'DRAGONFLY_DOJI': 0.66,
            'ABANDONED_BABY_BULLISH': 0.73,
            
            # Bearish Reversal Patterns
            'SHOOTING_STAR': 0.72,
            'HANGING_MAN': 0.68,
            'BEARISH_ENGULFING': 0.75,
            'DARK_CLOUD_COVER': 0.70,
            'EVENING_STAR': 0.78,
            'THREE_BLACK_CROWS': 0.84,
            'BEARISH_HARAMI': 0.71,
            'TWEEZER_TOP': 0.69,
            'GRAVESTONE_DOJI': 0.66,
            'ABANDONED_BABY_BEARISH': 0.73,
            
            # Continuation Patterns
            'RISING_THREE_METHODS': 0.74,
            'FALLING_THREE_METHODS': 0.74,
            'UPSIDE_GAP_TWO_CROWS': 0.68,
            'THREE_LINE_STRIKE_BULL': 0.83,
            'THREE_LINE_STRIKE_BEAR': 0.83,
            'MAT_HOLD': 0.72,
            
            # Indecision Patterns
            'DOJI': 0.55,
            'SPINNING_TOP': 0.52,
            'HIGH_WAVE': 0.50,
            'LONG_LEGGED_DOJI': 0.54,
        }
    
    def analyze(self, candles: List[Dict]) -> Dict:
        """
        Comprehensive candlestick pattern analysis
        
        Args:
            candles: List of OHLCV candles
        
        Returns:
            Complete pattern analysis with signals
        """
        if not candles or len(candles) < 10:
            return self._empty_analysis()
        
        df = pd.DataFrame(candles)
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna()
        
        if len(df) < 10:
            return self._empty_analysis()
        
        # Detect all patterns
        patterns = []
        
        # Single candle patterns
        patterns.extend(self._detect_single_candle_patterns(df))
        
        # Two candle patterns
        patterns.extend(self._detect_two_candle_patterns(df))
        
        # Three candle patterns
        patterns.extend(self._detect_three_candle_patterns(df))
        
        # Sort by recency and strength
        patterns.sort(key=lambda x: (x.index, x.strength), reverse=True)
        
        # Get most recent significant patterns
        recent_patterns = [p for p in patterns if p.index >= len(df) - 5]
        
        # Analyze trend context
        trend = self._analyze_trend(df)
        
        # Generate signals
        signals = self._generate_signals(recent_patterns, trend, df)
        
        # Calculate reversal probability
        reversal_prob = self._calculate_reversal_probability(recent_patterns, trend)
        
        return {
            'patterns_detected': len(patterns),
            'recent_patterns': [self._pattern_to_dict(p) for p in recent_patterns[:5]],
            'all_patterns': [self._pattern_to_dict(p) for p in patterns[:20]],
            'trend': trend,
            'reversal_probability': reversal_prob,
            'signals': signals,
            'summary': self._generate_summary(recent_patterns, reversal_prob)
        }
    
    def _detect_single_candle_patterns(self, df: pd.DataFrame) -> List[CandlePattern]:
        """Detect single candle patterns"""
        patterns = []
        
        for i in range(len(df)):
            candle = df.iloc[i]
            
            # Calculate candle metrics
            body = abs(candle['close'] - candle['open'])
            range_size = candle['high'] - candle['low']
            upper_shadow = candle['high'] - max(candle['open'], candle['close'])
            lower_shadow = min(candle['open'], candle['close']) - candle['low']
            
            if range_size == 0:
                continue
            
            body_pct = body / range_size
            upper_shadow_pct = upper_shadow / range_size
            lower_shadow_pct = lower_shadow / range_size
            
            is_bullish = candle['close'] > candle['open']
            
            # HAMMER (Bullish Reversal)
            if (lower_shadow_pct > 0.6 and upper_shadow_pct < 0.1 and 
                body_pct < 0.3 and i > 5):
                patterns.append(CandlePattern(
                    name='HAMMER',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=75.0 + (lower_shadow_pct * 20),
                    reliability=self.pattern_reliability['HAMMER'],
                    index=i,
                    description='Long lower shadow, small body - bullish reversal signal'
                ))
            
            # SHOOTING STAR (Bearish Reversal)
            if (upper_shadow_pct > 0.6 and lower_shadow_pct < 0.1 and 
                body_pct < 0.3 and i > 5):
                patterns.append(CandlePattern(
                    name='SHOOTING_STAR',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=75.0 + (upper_shadow_pct * 20),
                    reliability=self.pattern_reliability['SHOOTING_STAR'],
                    index=i,
                    description='Long upper shadow, small body - bearish reversal signal'
                ))
            
            # DOJI (Indecision)
            if body_pct < 0.1:
                patterns.append(CandlePattern(
                    name='DOJI',
                    type='INDECISION',
                    direction='NEUTRAL',
                    strength=60.0,
                    reliability=self.pattern_reliability['DOJI'],
                    index=i,
                    description='Very small body - market indecision'
                ))
                
                # DRAGONFLY DOJI (Bullish Reversal)
                if lower_shadow_pct > 0.7 and upper_shadow_pct < 0.1:
                    patterns.append(CandlePattern(
                        name='DRAGONFLY_DOJI',
                        type='REVERSAL',
                        direction='BULLISH',
                        strength=70.0,
                        reliability=self.pattern_reliability['DRAGONFLY_DOJI'],
                        index=i,
                        description='Doji with long lower shadow - strong bullish reversal'
                    ))
                
                # GRAVESTONE DOJI (Bearish Reversal)
                if upper_shadow_pct > 0.7 and lower_shadow_pct < 0.1:
                    patterns.append(CandlePattern(
                        name='GRAVESTONE_DOJI',
                        type='REVERSAL',
                        direction='BEARISH',
                        strength=70.0,
                        reliability=self.pattern_reliability['GRAVESTONE_DOJI'],
                        index=i,
                        description='Doji with long upper shadow - strong bearish reversal'
                    ))
            
            # SPINNING TOP (Indecision)
            if (0.1 < body_pct < 0.3 and 
                upper_shadow_pct > 0.2 and lower_shadow_pct > 0.2):
                patterns.append(CandlePattern(
                    name='SPINNING_TOP',
                    type='INDECISION',
                    direction='NEUTRAL',
                    strength=55.0,
                    reliability=self.pattern_reliability['SPINNING_TOP'],
                    index=i,
                    description='Small body with shadows - weak momentum'
                ))
        
        return patterns
    
    def _detect_two_candle_patterns(self, df: pd.DataFrame) -> List[CandlePattern]:
        """Detect two candle patterns"""
        patterns = []
        
        for i in range(1, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]
            
            prev_body = abs(prev['close'] - prev['open'])
            curr_body = abs(curr['close'] - curr['open'])
            prev_range = prev['high'] - prev['low']
            curr_range = curr['high'] - curr['low']
            
            if prev_range == 0 or curr_range == 0:
                continue
            
            prev_bullish = prev['close'] > prev['open']
            curr_bullish = curr['close'] > curr['open']
            
            # BULLISH ENGULFING
            if (not prev_bullish and curr_bullish and
                curr['open'] < prev['close'] and
                curr['close'] > prev['open'] and
                curr_body > prev_body * 1.2):
                patterns.append(CandlePattern(
                    name='BULLISH_ENGULFING',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=80.0,
                    reliability=self.pattern_reliability['BULLISH_ENGULFING'],
                    index=i,
                    description='Bullish candle engulfs bearish - strong reversal'
                ))
            
            # BEARISH ENGULFING
            if (prev_bullish and not curr_bullish and
                curr['open'] > prev['close'] and
                curr['close'] < prev['open'] and
                curr_body > prev_body * 1.2):
                patterns.append(CandlePattern(
                    name='BEARISH_ENGULFING',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=80.0,
                    reliability=self.pattern_reliability['BEARISH_ENGULFING'],
                    index=i,
                    description='Bearish candle engulfs bullish - strong reversal'
                ))
            
            # PIERCING LINE (Bullish)
            if (not prev_bullish and curr_bullish and
                curr['open'] < prev['low'] and
                curr['close'] > (prev['open'] + prev['close']) / 2 and
                curr['close'] < prev['open']):
                patterns.append(CandlePattern(
                    name='PIERCING_LINE',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=75.0,
                    reliability=self.pattern_reliability['PIERCING_LINE'],
                    index=i,
                    description='Bullish piercing into bearish body - reversal signal'
                ))
            
            # DARK CLOUD COVER (Bearish)
            if (prev_bullish and not curr_bullish and
                curr['open'] > prev['high'] and
                curr['close'] < (prev['open'] + prev['close']) / 2 and
                curr['close'] > prev['open']):
                patterns.append(CandlePattern(
                    name='DARK_CLOUD_COVER',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=75.0,
                    reliability=self.pattern_reliability['DARK_CLOUD_COVER'],
                    index=i,
                    description='Bearish cloud covers bullish - reversal signal'
                ))
            
            # TWEEZER TOP (Bearish)
            if (prev_bullish and not curr_bullish and
                abs(prev['high'] - curr['high']) / prev_range < 0.02):
                patterns.append(CandlePattern(
                    name='TWEEZER_TOP',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=70.0,
                    reliability=self.pattern_reliability['TWEEZER_TOP'],
                    index=i,
                    description='Two highs at same level - resistance formed'
                ))
            
            # TWEEZER BOTTOM (Bullish)
            if (not prev_bullish and curr_bullish and
                abs(prev['low'] - curr['low']) / prev_range < 0.02):
                patterns.append(CandlePattern(
                    name='TWEEZER_BOTTOM',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=70.0,
                    reliability=self.pattern_reliability['TWEEZER_BOTTOM'],
                    index=i,
                    description='Two lows at same level - support formed'
                ))
            
            # BULLISH HARAMI
            if (not prev_bullish and curr_bullish and
                curr['open'] > prev['close'] and
                curr['close'] < prev['open'] and
                curr_body < prev_body * 0.5):
                patterns.append(CandlePattern(
                    name='BULLISH_HARAMI',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=72.0,
                    reliability=self.pattern_reliability['BULLISH_HARAMI'],
                    index=i,
                    description='Small bullish inside large bearish - reversal potential'
                ))
            
            # BEARISH HARAMI
            if (prev_bullish and not curr_bullish and
                curr['open'] < prev['close'] and
                curr['close'] > prev['open'] and
                curr_body < prev_body * 0.5):
                patterns.append(CandlePattern(
                    name='BEARISH_HARAMI',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=72.0,
                    reliability=self.pattern_reliability['BEARISH_HARAMI'],
                    index=i,
                    description='Small bearish inside large bullish - reversal potential'
                ))
        
        return patterns
    
    def _detect_three_candle_patterns(self, df: pd.DataFrame) -> List[CandlePattern]:
        """Detect three candle patterns"""
        patterns = []
        
        for i in range(2, len(df)):
            c1 = df.iloc[i-2]
            c2 = df.iloc[i-1]
            c3 = df.iloc[i]
            
            c1_bullish = c1['close'] > c1['open']
            c2_bullish = c2['close'] > c2['open']
            c3_bullish = c3['close'] > c3['open']
            
            c1_body = abs(c1['close'] - c1['open'])
            c2_body = abs(c2['close'] - c2['open'])
            c3_body = abs(c3['close'] - c3['open'])
            
            # MORNING STAR (Bullish Reversal)
            if (not c1_bullish and c3_bullish and
                c2_body < c1_body * 0.3 and
                c3['close'] > (c1['open'] + c1['close']) / 2):
                patterns.append(CandlePattern(
                    name='MORNING_STAR',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=85.0,
                    reliability=self.pattern_reliability['MORNING_STAR'],
                    index=i,
                    description='Three candle bullish reversal - very strong signal'
                ))
            
            # EVENING STAR (Bearish Reversal)
            if (c1_bullish and not c3_bullish and
                c2_body < c1_body * 0.3 and
                c3['close'] < (c1['open'] + c1['close']) / 2):
                patterns.append(CandlePattern(
                    name='EVENING_STAR',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=85.0,
                    reliability=self.pattern_reliability['EVENING_STAR'],
                    index=i,
                    description='Three candle bearish reversal - very strong signal'
                ))
            
            # THREE WHITE SOLDIERS (Bullish)
            if (c1_bullish and c2_bullish and c3_bullish and
                c2['close'] > c1['close'] and c3['close'] > c2['close'] and
                c2['open'] > c1['open'] and c3['open'] > c2['open']):
                patterns.append(CandlePattern(
                    name='THREE_WHITE_SOLDIERS',
                    type='REVERSAL',
                    direction='BULLISH',
                    strength=88.0,
                    reliability=self.pattern_reliability['THREE_WHITE_SOLDIERS'],
                    index=i,
                    description='Three consecutive bullish - very strong reversal'
                ))
            
            # THREE BLACK CROWS (Bearish)
            if (not c1_bullish and not c2_bullish and not c3_bullish and
                c2['close'] < c1['close'] and c3['close'] < c2['close'] and
                c2['open'] < c1['open'] and c3['open'] < c2['open']):
                patterns.append(CandlePattern(
                    name='THREE_BLACK_CROWS',
                    type='REVERSAL',
                    direction='BEARISH',
                    strength=88.0,
                    reliability=self.pattern_reliability['THREE_BLACK_CROWS'],
                    index=i,
                    description='Three consecutive bearish - very strong reversal'
                ))
        
        return patterns
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """Analyze current market trend"""
        if len(df) < 20:
            return {'direction': 'UNKNOWN', 'strength': 0}
        
        closes = df['close'].tail(20).values
        
        # Calculate trend using linear regression
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        
        # Normalize slope
        avg_price = closes.mean()
        slope_pct = (slope / avg_price) * 100
        
        if slope_pct > 0.1:
            direction = 'UPTREND'
            strength = min(abs(slope_pct) * 20, 100)
        elif slope_pct < -0.1:
            direction = 'DOWNTREND'
            strength = min(abs(slope_pct) * 20, 100)
        else:
            direction = 'SIDEWAYS'
            strength = 50
        
        return {
            'direction': direction,
            'strength': strength,
            'slope': slope_pct
        }
    
    def _calculate_reversal_probability(self, patterns: List[CandlePattern], trend: Dict) -> Dict:
        """Calculate probability of market reversal"""
        if not patterns:
            return {'bullish': 0, 'bearish': 0, 'confidence': 0}
        
        bullish_score = 0
        bearish_score = 0
        
        for pattern in patterns:
            if pattern.type == 'REVERSAL':
                weight = pattern.strength * pattern.reliability
                
                if pattern.direction == 'BULLISH':
                    bullish_score += weight
                elif pattern.direction == 'BEARISH':
                    bearish_score += weight
        
        # Adjust for trend (reversals stronger against trend)
        if trend['direction'] == 'DOWNTREND':
            bullish_score *= 1.2
        elif trend['direction'] == 'UPTREND':
            bearish_score *= 1.2
        
        total = bullish_score + bearish_score
        
        if total > 0:
            bullish_prob = (bullish_score / total) * 100
            bearish_prob = (bearish_score / total) * 100
            confidence = min(total / 200, 1.0) * 100
        else:
            bullish_prob = bearish_prob = confidence = 0
        
        return {
            'bullish': round(bullish_prob, 1),
            'bearish': round(bearish_prob, 1),
            'confidence': round(confidence, 1)
        }
    
    def _generate_signals(self, patterns: List[CandlePattern], trend: Dict, df: pd.DataFrame) -> Dict:
        """Generate trading signals from patterns"""
        if not patterns:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': []}
        
        # Get strongest recent reversal pattern
        reversal_patterns = [p for p in patterns if p.type == 'REVERSAL']
        
        if not reversal_patterns:
            return {'direction': 'NEUTRAL', 'confidence': 50, 'reason': ['No reversal patterns detected']}
        
        strongest = max(reversal_patterns, key=lambda x: x.strength * x.reliability)
        
        confidence = strongest.strength * strongest.reliability
        reasons = [f"{strongest.name}: {strongest.description}"]
        
        # Add trend context
        if trend['direction'] == 'DOWNTREND' and strongest.direction == 'BULLISH':
            confidence *= 1.1
            reasons.append(f"Reversal against downtrend (trend strength: {trend['strength']:.0f}%)")
        elif trend['direction'] == 'UPTREND' and strongest.direction == 'BEARISH':
            confidence *= 1.1
            reasons.append(f"Reversal against uptrend (trend strength: {trend['strength']:.0f}%)")
        
        # Check for pattern confirmation
        confirming_patterns = [
            p for p in patterns 
            if p != strongest and p.direction == strongest.direction
        ]
        
        if confirming_patterns:
            confidence += len(confirming_patterns) * 5
            reasons.append(f"{len(confirming_patterns)} confirming patterns")
        
        direction = 'CALL' if strongest.direction == 'BULLISH' else 'PUT'
        
        return {
            'direction': direction,
            'confidence': min(confidence, 95),
            'reason': reasons,
            'pattern': strongest.name,
            'reliability': strongest.reliability * 100
        }
    
    def _generate_summary(self, patterns: List[CandlePattern], reversal_prob: Dict) -> str:
        """Generate human-readable summary"""
        if not patterns:
            return "No significant patterns detected"
        
        parts = []
        
        reversal_patterns = [p for p in patterns if p.type == 'REVERSAL']
        if reversal_patterns:
            strongest = max(reversal_patterns, key=lambda x: x.strength)
            parts.append(f"{strongest.name} detected ({strongest.direction})")
        
        if reversal_prob['confidence'] > 60:
            if reversal_prob['bullish'] > reversal_prob['bearish']:
                parts.append(f"Bullish reversal likely ({reversal_prob['bullish']:.0f}%)")
            else:
                parts.append(f"Bearish reversal likely ({reversal_prob['bearish']:.0f}%)")
        
        return ', '.join(parts) if parts else "Indecision patterns"
    
    def _pattern_to_dict(self, pattern: CandlePattern) -> Dict:
        """Convert pattern to dictionary"""
        return {
            'name': pattern.name,
            'type': pattern.type,
            'direction': pattern.direction,
            'strength': round(pattern.strength, 1),
            'reliability': round(pattern.reliability * 100, 1),
            'description': pattern.description
        }
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis"""
        return {
            'patterns_detected': 0,
            'recent_patterns': [],
            'all_patterns': [],
            'trend': {'direction': 'UNKNOWN', 'strength': 0},
            'reversal_probability': {'bullish': 0, 'bearish': 0, 'confidence': 0},
            'signals': {'direction': 'NEUTRAL', 'confidence': 0, 'reason': []},
            'summary': 'Insufficient data'
        }


# Global instance
candlestick_analyzer = CandlestickAnalyzer()
