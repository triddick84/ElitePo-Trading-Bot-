"""
2-Minute Trend Momentum Strategy
Accuracy Target: 78%+

Based on research:
- ADX for trend strength
- Moving average trend
- Momentum oscillators

Entry Rules:
CALL: ADX > 25, price above MA, RSI rising, momentum positive
PUT: ADX > 25, price below MA, RSI falling, momentum negative
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy2mTrendMomentum:
    def __init__(self):
        self.name = "2m Trend Momentum"
        self.timeframe = "2m"
        self.accuracy_target = 78.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
            df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
            df['sma_20'] = talib.SMA(df['close'], timeperiod=20)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['momentum'] = talib.MOM(df['close'], timeperiod=10)
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['adx'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. ADX Trend Strength (30 points)
        if latest['adx'] > 25:
            if latest['plus_di'] > latest['minus_di']:
                call_signals += 30
                reasons.append(f"✅ Strong uptrend (ADX: {latest['adx']:.1f})")
            else:
                put_signals += 30
                reasons.append(f"✅ Strong downtrend (ADX: {latest['adx']:.1f})")
        else:
            reasons.append(f"⚠️ Weak trend (ADX: {latest['adx']:.1f})")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        # 2. Price vs MA (25 points)
        if latest['close'] > latest['sma_20']:
            call_signals += 25
            reasons.append("✅ Price above SMA(20)")
        elif latest['close'] < latest['sma_20']:
            put_signals += 25
            reasons.append("✅ Price below SMA(20)")
        
        # 3. RSI Momentum (20 points)
        if latest['rsi'] > prev['rsi'] and latest['rsi'] > 50:
            call_signals += 20
            reasons.append("✅ RSI rising (bullish momentum)")
        elif latest['rsi'] < prev['rsi'] and latest['rsi'] < 50:
            put_signals += 20
            reasons.append("✅ RSI falling (bearish momentum)")
        
        # 4. Momentum Oscillator (15 points)
        if latest['momentum'] > 0 and latest['momentum'] > prev['momentum']:
            call_signals += 15
            reasons.append("✅ Positive momentum increasing")
        elif latest['momentum'] < 0 and latest['momentum'] < prev['momentum']:
            put_signals += 15
            reasons.append("✅ Negative momentum increasing")
        
        # 5. Stochastic (10 points)
        if latest['stoch_k'] > latest['stoch_d']:
            call_signals += 10
        elif latest['stoch_k'] < latest['stoch_d']:
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
                'adx': float(latest['adx']),
                'rsi': float(latest['rsi']),
                'momentum': float(latest['momentum'])
            }
        }


strategy_2m_trend_momentum = Strategy2mTrendMomentum()
