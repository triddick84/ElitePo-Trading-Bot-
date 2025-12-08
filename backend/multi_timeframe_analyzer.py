"""
Multi-Timeframe Analysis System
Industry best practice for binary options trading
Analyzes higher, mid, and lower timeframes for maximum accuracy
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TimeframeAnalysis:
    """Analysis result for a single timeframe"""
    timeframe: str
    trend: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    strength: float  # 0-100
    momentum: float  # -100 to 100
    signals: Dict[str, any]
    confidence: float  # 0-100


class MultiTimeframeAnalyzer:
    """
    Multi-timeframe analysis for high-accuracy trading signals
    
    Strategy:
    1. Higher timeframe (H1/H4) - Identify overall trend
    2. Mid timeframe (M15/M30) - Confirm momentum
    3. Lower timeframe (M1/M5) - Precise entry timing
    
    Only generates signals when all timeframes align
    """
    
    # Timeframe hierarchy for analysis
    TIMEFRAME_HIERARCHY = {
        'higher': ['1h', '4h'],
        'mid': ['15m', '30m'],
        'lower': ['1m', '5m']
    }
    
    # Timeframe mapping: seconds to label
    TIMEFRAME_MAP = {
        60: '1m',
        300: '5m',
        900: '15m',
        1800: '30m',
        3600: '1h',
        14400: '4h'
    }
    
    def __init__(self):
        self.analysis_cache = {}
    
    def analyze_candles(self, candles: List[Dict], timeframe: str) -> TimeframeAnalysis:
        """
        Analyze candles for a single timeframe
        
        Args:
            candles: List of OHLCV candle data
            timeframe: Timeframe label (e.g., '1m', '5m', '1h')
        
        Returns:
            TimeframeAnalysis object
        """
        if not candles or len(candles) < 20:
            logger.warning(f"Insufficient candles for {timeframe} analysis")
            return TimeframeAnalysis(
                timeframe=timeframe,
                trend='NEUTRAL',
                strength=0,
                momentum=0,
                signals={},
                confidence=0
            )
        
        df = pd.DataFrame(candles)
        
        # Calculate indicators
        signals = {}
        
        # 1. Moving Averages for trend
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean() if len(df) >= 50 else df['close']
        
        # 2. RSI for momentum
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 3. MACD for trend confirmation
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['signal_line']
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        signals['ema_9'] = float(latest['ema_9'])
        signals['ema_21'] = float(latest['ema_21'])
        signals['ema_50'] = float(latest['ema_50'])
        signals['rsi'] = float(latest['rsi'])
        signals['macd'] = float(latest['macd'])
        signals['macd_signal'] = float(latest['signal_line'])
        signals['macd_histogram'] = float(latest['macd_histogram'])
        signals['close'] = float(latest['close'])
        
        # Determine trend
        trend = self._determine_trend(signals)
        
        # Calculate trend strength
        strength = self._calculate_strength(signals, df)
        
        # Calculate momentum
        momentum = self._calculate_momentum(signals)
        
        # Calculate confidence
        confidence = self._calculate_confidence(trend, strength, momentum, signals)
        
        return TimeframeAnalysis(
            timeframe=timeframe,
            trend=trend,
            strength=strength,
            momentum=momentum,
            signals=signals,
            confidence=confidence
        )
    
    def _determine_trend(self, signals: Dict) -> str:
        """Determine trend from signals"""
        bullish_count = 0
        bearish_count = 0
        
        # EMA alignment
        if signals['ema_9'] > signals['ema_21'] > signals['ema_50']:
            bullish_count += 2
        elif signals['ema_9'] < signals['ema_21'] < signals['ema_50']:
            bearish_count += 2
        
        # Price vs EMA
        if signals['close'] > signals['ema_21']:
            bullish_count += 1
        else:
            bearish_count += 1
        
        # MACD
        if signals['macd'] > signals['macd_signal'] and signals['macd_histogram'] > 0:
            bullish_count += 1
        elif signals['macd'] < signals['macd_signal'] and signals['macd_histogram'] < 0:
            bearish_count += 1
        
        # RSI
        if signals['rsi'] > 50:
            bullish_count += 1
        elif signals['rsi'] < 50:
            bearish_count += 1
        
        if bullish_count > bearish_count + 1:
            return 'BULLISH'
        elif bearish_count > bullish_count + 1:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _calculate_strength(self, signals: Dict, df: pd.DataFrame) -> float:
        """Calculate trend strength 0-100"""
        strength = 50.0  # Base
        
        # EMA separation
        ema_separation = abs(signals['ema_9'] - signals['ema_21']) / signals['close'] * 100
        strength += min(ema_separation * 10, 20)
        
        # MACD histogram strength
        macd_strength = abs(signals['macd_histogram']) / signals['close'] * 1000
        strength += min(macd_strength * 5, 15)
        
        # RSI extremity
        if signals['rsi'] > 70 or signals['rsi'] < 30:
            strength += 15
        elif signals['rsi'] > 60 or signals['rsi'] < 40:
            strength += 10
        
        return min(strength, 100.0)
    
    def _calculate_momentum(self, signals: Dict) -> float:
        """Calculate momentum -100 to 100"""
        momentum = 0.0
        
        # RSI-based momentum
        momentum += (signals['rsi'] - 50) * 1.5
        
        # MACD-based momentum
        if signals['macd'] > 0:
            momentum += min(signals['macd_histogram'] * 100, 25)
        else:
            momentum += max(signals['macd_histogram'] * 100, -25)
        
        return max(min(momentum, 100.0), -100.0)
    
    def _calculate_confidence(
        self, 
        trend: str, 
        strength: float, 
        momentum: float, 
        signals: Dict
    ) -> float:
        """Calculate overall confidence 0-100"""
        if trend == 'NEUTRAL':
            return 40.0
        
        confidence = 50.0
        
        # Add strength component
        confidence += (strength - 50) * 0.4
        
        # Add momentum alignment
        if (trend == 'BULLISH' and momentum > 0) or (trend == 'BEARISH' and momentum < 0):
            confidence += 20
        
        # RSI confirmation
        if trend == 'BULLISH' and 40 < signals['rsi'] < 70:
            confidence += 10
        elif trend == 'BEARISH' and 30 < signals['rsi'] < 60:
            confidence += 10
        
        # MACD confirmation
        if (trend == 'BULLISH' and signals['macd_histogram'] > 0) or \
           (trend == 'BEARISH' and signals['macd_histogram'] < 0):
            confidence += 10
        
        return max(min(confidence, 100.0), 0.0)
    
    async def analyze_multi_timeframe(
        self, 
        candles_data: Dict[str, List[Dict]]
    ) -> Dict[str, any]:
        """
        Perform multi-timeframe analysis
        
        Args:
            candles_data: Dict with timeframe keys and candle lists
                Example: {'1m': [...], '5m': [...], '15m': [...], '1h': [...]}
        
        Returns:
            Comprehensive analysis with alignment and recommended action
        """
        analyses = {}
        
        # Analyze each timeframe
        for timeframe, candles in candles_data.items():
            if candles:
                analyses[timeframe] = self.analyze_candles(candles, timeframe)
        
        # Check timeframe alignment
        alignment = self._check_alignment(analyses)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(analyses, alignment)
        
        return {
            'analyses': {tf: {
                'trend': a.trend,
                'strength': a.strength,
                'momentum': a.momentum,
                'confidence': a.confidence,
                'signals': a.signals
            } for tf, a in analyses.items()},
            'alignment': alignment,
            'recommendation': recommendation,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _check_alignment(self, analyses: Dict[str, TimeframeAnalysis]) -> Dict:
        """Check if timeframes are aligned"""
        if not analyses:
            return {'aligned': False, 'score': 0, 'direction': 'NEUTRAL'}
        
        trends = [a.trend for a in analyses.values()]
        
        # Count bullish vs bearish
        bullish = trends.count('BULLISH')
        bearish = trends.count('BEARISH')
        total = len(trends)
        
        if bullish >= total * 0.75:  # 75% or more bullish
            return {
                'aligned': True,
                'score': (bullish / total) * 100,
                'direction': 'BULLISH'
            }
        elif bearish >= total * 0.75:  # 75% or more bearish
            return {
                'aligned': True,
                'score': (bearish / total) * 100,
                'direction': 'BEARISH'
            }
        else:
            return {
                'aligned': False,
                'score': 50,
                'direction': 'NEUTRAL'
            }
    
    def _generate_recommendation(
        self, 
        analyses: Dict[str, TimeframeAnalysis],
        alignment: Dict
    ) -> Dict:
        """Generate trading recommendation"""
        if not alignment['aligned']:
            return {
                'action': 'WAIT',
                'reason': 'Timeframes not aligned',
                'confidence': 30,
                'direction': None
            }
        
        # Calculate average confidence
        avg_confidence = np.mean([a.confidence for a in analyses.values()])
        
        # Calculate average strength
        avg_strength = np.mean([a.strength for a in analyses.values()])
        
        # Overall confidence
        overall_confidence = (avg_confidence + avg_strength + alignment['score']) / 3
        
        if overall_confidence >= 70:
            return {
                'action': 'TRADE',
                'direction': alignment['direction'],
                'confidence': overall_confidence,
                'reason': f"Strong {alignment['direction'].lower()} alignment across timeframes",
                'avg_strength': avg_strength,
                'alignment_score': alignment['score']
            }
        elif overall_confidence >= 60:
            return {
                'action': 'CONSIDER',
                'direction': alignment['direction'],
                'confidence': overall_confidence,
                'reason': f"Moderate {alignment['direction'].lower()} alignment",
                'avg_strength': avg_strength,
                'alignment_score': alignment['score']
            }
        else:
            return {
                'action': 'WAIT',
                'reason': 'Low confidence, wait for better setup',
                'confidence': overall_confidence,
                'direction': alignment['direction']
            }


# Global instance
multi_timeframe_analyzer = MultiTimeframeAnalyzer()
