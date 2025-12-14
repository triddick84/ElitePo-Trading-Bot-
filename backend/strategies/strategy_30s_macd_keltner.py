"""
30-Second MACD + Keltner Channel Strategy
Accuracy Target: 81%+

Based on research:
- MACD for momentum
- Keltner Channels for volatility
- Breakout confirmation

Entry Rules:
CALL: MACD crosses up + price breaks above Keltner upper
PUT: MACD crosses down + price breaks below Keltner lower
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy30sMACDKeltner:
    def __init__(self):
        self.name = "30s MACD + Keltner"
        self.timeframe = "30s"
        self.accuracy_target = 81.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=20)
            df['keltner_upper'] = df['ema_20'] + (2 * df['atr'])
            df['keltner_lower'] = df['ema_20'] - (2 * df['atr'])
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['macd'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. MACD Crossover (40 points)
        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            call_signals += 40
            reasons.append("✅ MACD bullish crossover")
        elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            put_signals += 40
            reasons.append("✅ MACD bearish crossover")
        
        # 2. Keltner Breakout (35 points)
        if latest['close'] > latest['keltner_upper']:
            call_signals += 35
            reasons.append("✅ Breakout above Keltner upper")
        elif latest['close'] < latest['keltner_lower']:
            put_signals += 35
            reasons.append("✅ Breakout below Keltner lower")
        
        # 3. MACD Histogram Growing (15 points)
        if abs(latest['macd_hist']) > abs(prev['macd_hist']):
            if call_signals > put_signals:
                call_signals += 15
                reasons.append("✅ MACD histogram expanding")
            elif put_signals > call_signals:
                put_signals += 15
                reasons.append("✅ MACD histogram expanding")
        
        # 4. RSI Filter (10 points)
        if 45 < latest['rsi'] < 75:
            call_signals += 10
        elif 25 < latest['rsi'] < 55:
            put_signals += 10
        
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
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'macd': float(latest['macd']),
                'keltner_upper': float(latest['keltner_upper']),
                'keltner_lower': float(latest['keltner_lower']),
                'rsi': float(latest['rsi'])
            }
        }


strategy_30s_macd_keltner = Strategy30sMACDKeltner()
