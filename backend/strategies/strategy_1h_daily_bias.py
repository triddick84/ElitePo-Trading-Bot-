"""
1-Hour Daily Bias Strategy
Accuracy Target: 85%+

Based on research:
- Higher timeframe trend analysis
- Session bias (Asian, London, NY)
- Key level bounces

Entry Rules:
CALL: Daily uptrend + H1 pullback + session high break
PUT: Daily downtrend + H1 pullback + session low break
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Strategy1hDailyBias:
    def __init__(self):
        self.name = "1h Daily Bias"
        self.timeframe = "1h"
        self.accuracy_target = 85.0
    
    def identify_daily_trend(self, df: pd.DataFrame) -> str:
        """Identify daily trend from hourly data"""
        if len(df) < 100:
            return 'ranging'
        
        # Use 100-period EMA on 1h (roughly 4 days)
        latest = df.iloc[-1]
        
        if latest['ema_100'] > df['ema_100'].iloc[-50:].mean() and latest['close'] > latest['ema_100']:
            return 'uptrend'
        elif latest['ema_100'] < df['ema_100'].iloc[-50:].mean() and latest['close'] < latest['ema_100']:
            return 'downtrend'
        else:
            return 'ranging'
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            df['ema_100'] = talib.EMA(df['close'], timeperiod=100)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # Session highs/lows (last 8 hours)
            df['session_high'] = df['high'].rolling(window=8).max()
            df['session_low'] = df['low'].rolling(window=8).min()
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 100:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        daily_trend = self.identify_daily_trend(df)
        
        if df.empty or df['ema_20'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Daily Trend Bias (40 points)
        if daily_trend == 'uptrend':
            call_signals += 40
            reasons.append("✅ Daily uptrend bias")
        elif daily_trend == 'downtrend':
            put_signals += 40
            reasons.append("✅ Daily downtrend bias")
        else:
            reasons.append("⚠️ No clear daily bias")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        # 2. H1 Pullback to EMA (30 points)
        ema_distance = abs(latest['close'] - latest['ema_20']) / latest['close'] * 100
        if ema_distance < 0.3:  # Within 0.3% of EMA(20)
            if daily_trend == 'uptrend':
                call_signals += 30
                reasons.append("✅ Pullback to H1 EMA in uptrend")
            elif daily_trend == 'downtrend':
                put_signals += 30
                reasons.append("✅ Pullback to H1 EMA in downtrend")
        
        # 3. Session Level Break (20 points)
        if daily_trend == 'uptrend' and latest['high'] > prev['session_high']:
            call_signals += 20
            reasons.append("✅ Break above session high")
        elif daily_trend == 'downtrend' and latest['low'] < prev['session_low']:
            put_signals += 20
            reasons.append("✅ Break below session low")
        
        # 4. MACD Alignment (5 points)
        if daily_trend == 'uptrend' and latest['macd'] > latest['macd_signal']:
            call_signals += 5
        elif daily_trend == 'downtrend' and latest['macd'] < latest['macd_signal']:
            put_signals += 5
        
        # 5. RSI Filter (5 points)
        if daily_trend == 'uptrend' and 45 < latest['rsi'] < 70:
            call_signals += 5
        elif daily_trend == 'downtrend' and 30 < latest['rsi'] < 55:
            put_signals += 5
        
        if call_signals > put_signals and call_signals >= 80:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 80:
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
            'daily_trend': daily_trend,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'rsi': float(latest['rsi']),
                'macd': float(latest['macd']),
                'session_high': float(latest['session_high']),
                'session_low': float(latest['session_low'])
            }
        }


strategy_1h_daily_bias = Strategy1hDailyBias()
