"""
1-Minute Triple EMA Strategy
Accuracy Target: 78%+

Based on research:
- 3 EMA alignment for trend
- Volume confirmation
- MACD momentum

Entry Rules:
CALL: EMA(9) > EMA(21) > EMA(50), price crosses above EMA(9), MACD bullish
PUT: EMA(9) < EMA(21) < EMA(50), price crosses below EMA(9), MACD bearish
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy1mTripleEMA:
    def __init__(self):
        self.name = "1m Triple EMA"
        self.timeframe = "1m"
        self.accuracy_target = 78.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['ema_9'] = talib.EMA(df['close'], timeperiod=9)
            df['ema_21'] = talib.EMA(df['close'], timeperiod=21)
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['ema_9'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. EMA Alignment (35 points)
        if latest['ema_9'] > latest['ema_21'] > latest['ema_50']:
            call_signals += 35
            reasons.append("✅ Bullish EMA alignment")
        elif latest['ema_9'] < latest['ema_21'] < latest['ema_50']:
            put_signals += 35
            reasons.append("✅ Bearish EMA alignment")
        
        # 2. Price Cross EMA(9) (30 points)
        if latest['close'] > latest['ema_9'] and prev['close'] <= prev['ema_9']:
            call_signals += 30
            reasons.append("✅ Price crossed above EMA(9)")
        elif latest['close'] < latest['ema_9'] and prev['close'] >= prev['ema_9']:
            put_signals += 30
            reasons.append("✅ Price crossed below EMA(9)")
        
        # 3. MACD Confirmation (20 points)
        if latest['macd'] > latest['macd_signal']:
            call_signals += 20
            reasons.append("✅ MACD bullish")
        elif latest['macd'] < latest['macd_signal']:
            put_signals += 20
            reasons.append("✅ MACD bearish")
        
        # 4. Volume Confirmation (10 points)
        if latest['volume_ratio'] > 1.2:
            if call_signals > put_signals:
                call_signals += 10
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 10
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
        
        # 5. RSI Filter (5 points)
        if 40 < latest['rsi'] < 70:
            call_signals += 5
        elif 30 < latest['rsi'] < 60:
            put_signals += 5
        
        if call_signals > put_signals and call_signals >= 70:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 70:
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
                'ema_9': float(latest['ema_9']),
                'ema_21': float(latest['ema_21']),
                'ema_50': float(latest['ema_50']),
                'macd': float(latest['macd'])
            }
        }


strategy_1m_triple_ema = Strategy1mTripleEMA()
