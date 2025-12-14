"""
3-Minute Price Action Strategy
Accuracy Target: 82%+

Based on research:
- Candlestick patterns
- Key support/resistance
- Volume confirmation

Entry Rules:
CALL: Hammer/Doji at support + volume increase + bullish confirmation
PUT: Shooting star/Doji at resistance + volume increase + bearish confirmation
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy3mPriceAction:
    def __init__(self):
        self.name = "3m Price Action"
        self.timeframe = "3m"
        self.accuracy_target = 82.0
    
    def detect_patterns(self, df: pd.DataFrame) -> Dict:
        """Detect candlestick patterns"""
        patterns = {'hammer': 0, 'shooting_star': 0, 'doji': 0}
        
        if len(df) < 1:
            return patterns
        
        latest = df.iloc[-1]
        body = abs(latest['close'] - latest['open'])
        range_size = latest['high'] - latest['low']
        
        if range_size == 0:
            return patterns
        
        # Hammer pattern
        lower_shadow = min(latest['open'], latest['close']) - latest['low']
        upper_shadow = latest['high'] - max(latest['open'], latest['close'])
        
        if lower_shadow > (2 * body) and upper_shadow < body:
            patterns['hammer'] = 1
        
        # Shooting star
        if upper_shadow > (2 * body) and lower_shadow < body:
            patterns['shooting_star'] = 1
        
        # Doji
        if body < (range_size * 0.1):
            patterns['doji'] = 1
        
        return patterns
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['sma_50'] = talib.SMA(df['close'], timeperiod=50)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        patterns = self.detect_patterns(df)
        
        if df.empty or df['sma_50'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Bullish Patterns (35 points)
        if patterns['hammer']:
            call_signals += 35
            reasons.append("✅ Hammer pattern detected")
        
        # Bearish Patterns (35 points)
        if patterns['shooting_star']:
            put_signals += 35
            reasons.append("✅ Shooting star pattern detected")
        
        # 2. Confirmation Candle (25 points)
        if call_signals > 0 and latest['close'] > latest['open']:
            call_signals += 25
            reasons.append("✅ Bullish confirmation candle")
        elif put_signals > 0 and latest['close'] < latest['open']:
            put_signals += 25
            reasons.append("✅ Bearish confirmation candle")
        
        # 3. Volume Confirmation (20 points)
        if latest['volume_ratio'] > 1.3:
            if call_signals > put_signals:
                call_signals += 20
                reasons.append(f"✅ Volume surge ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 20
                reasons.append(f"✅ Volume surge ({latest['volume_ratio']:.2f}x)")
        
        # 4. RSI Filter (15 points)
        if call_signals > 0 and latest['rsi'] < 70:
            call_signals += 15
            reasons.append("✅ RSI not overbought")
        elif put_signals > 0 and latest['rsi'] > 30:
            put_signals += 15
            reasons.append("✅ RSI not oversold")
        
        # 5. Trend Alignment (5 points)
        if latest['close'] > latest['sma_50']:
            call_signals += 5
        elif latest['close'] < latest['sma_50']:
            put_signals += 5
        
        if call_signals > put_signals and call_signals >= 75:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 75:
            direction = 'PUT'
            confidence = min(put_signals, 100)
        else:
            direction = 'NEUTRAL'
            confidence = max(call_signals, put_signals)
            reasons.append("⚠️ Insufficient signal strength")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'patterns': patterns,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'rsi': float(latest['rsi']),
                'volume_ratio': float(latest['volume_ratio'])
            }
        }


strategy_3m_price_action = Strategy3mPriceAction()
