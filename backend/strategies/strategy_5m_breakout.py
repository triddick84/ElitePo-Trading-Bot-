"""
5-Minute Breakout Strategy
Accuracy Target: 81%+

Based on research:
- Range consolidation
- Volatility squeeze
- Breakout with volume

Entry Rules:
CALL: Price breaks above range high + ATR expanding + volume spike
PUT: Price breaks below range low + ATR expanding + volume spike
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy5mBreakout:
    def __init__(self):
        self.name = "5m Breakout"
        self.timeframe = "5m"
        self.accuracy_target = 81.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
            )
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            # Range high/low (last 20 candles)
            df['range_high'] = df['high'].rolling(window=20).max()
            df['range_low'] = df['low'].rolling(window=20).min()
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['atr'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Breakout Detection (40 points)
        if latest['close'] > prev['range_high']:
            call_signals += 40
            reasons.append("✅ Breakout above range high")
        elif latest['close'] < prev['range_low']:
            put_signals += 40
            reasons.append("✅ Breakout below range low")
        
        # 2. BB Squeeze (20 points)
        if latest['bb_width'] < df['bb_width'].mean():
            if call_signals > 0:
                call_signals += 20
                reasons.append("✅ BB squeeze - low volatility breakout")
            elif put_signals > 0:
                put_signals += 20
                reasons.append("✅ BB squeeze - low volatility breakout")
        
        # 3. ATR Expansion (20 points)
        if latest['atr'] > prev['atr']:
            if call_signals > put_signals:
                call_signals += 20
                reasons.append("✅ ATR expanding (volatility increase)")
            elif put_signals > call_signals:
                put_signals += 20
                reasons.append("✅ ATR expanding (volatility increase)")
        
        # 4. Volume Confirmation (15 points)
        if latest['volume_ratio'] > 1.5:
            if call_signals > put_signals:
                call_signals += 15
                reasons.append(f"✅ Volume spike ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 15
                reasons.append(f"✅ Volume spike ({latest['volume_ratio']:.2f}x)")
        
        # 5. RSI Filter (5 points)
        if 40 < latest['rsi'] < 75:
            call_signals += 5
        elif 25 < latest['rsi'] < 60:
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
            reasons.append("⚠️ Insufficient signal strength or no breakout")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'atr': float(latest['atr']),
                'bb_width': float(latest['bb_width']),
                'volume_ratio': float(latest['volume_ratio']),
                'rsi': float(latest['rsi'])
            }
        }


strategy_5m_breakout = Strategy5mBreakout()
