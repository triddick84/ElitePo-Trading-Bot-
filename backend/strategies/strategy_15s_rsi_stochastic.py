"""
15-Second RSI + Stochastic Strategy
Accuracy Target: 84%+

Based on research:
- RSI and Stochastic alignment
- Oversold/overbought confirmation
- Momentum validation

Entry Rules:
CALL: RSI < 30 + Stochastic < 20 + both turning up
PUT: RSI > 70 + Stochastic > 80 + both turning down
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy15sRSIStochastic:
    def __init__(self):
        self.name = "15s RSI + Stochastic"
        self.timeframe = "15s"
        self.accuracy_target = 84.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['rsi'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. RSI Extreme + Turning (35 points)
        if latest['rsi'] < 30 and latest['rsi'] > prev['rsi']:
            call_signals += 35
            reasons.append(f"✅ RSI oversold & turning up ({latest['rsi']:.1f})")
        elif latest['rsi'] > 70 and latest['rsi'] < prev['rsi']:
            put_signals += 35
            reasons.append(f"✅ RSI overbought & turning down ({latest['rsi']:.1f})")
        
        # 2. Stochastic Extreme + Turning (35 points)
        if latest['stoch_k'] < 20 and latest['stoch_k'] > prev['stoch_k']:
            call_signals += 35
            reasons.append(f"✅ Stochastic oversold & turning up ({latest['stoch_k']:.1f})")
        elif latest['stoch_k'] > 80 and latest['stoch_k'] < prev['stoch_k']:
            put_signals += 35
            reasons.append(f"✅ Stochastic overbought & turning down ({latest['stoch_k']:.1f})")
        
        # 3. MACD Confirmation (20 points)
        if latest['macd'] > latest['macd_signal']:
            call_signals += 20
            reasons.append("✅ MACD bullish")
        elif latest['macd'] < latest['macd_signal']:
            put_signals += 20
            reasons.append("✅ MACD bearish")
        
        # 4. EMA Position (10 points)
        if latest['close'] > latest['ema_20']:
            call_signals += 10
        elif latest['close'] < latest['ema_20']:
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
                'rsi': float(latest['rsi']),
                'stoch_k': float(latest['stoch_k']),
                'macd': float(latest['macd'])
            }
        }


strategy_15s_rsi_stochastic = Strategy15sRSIStochastic()
