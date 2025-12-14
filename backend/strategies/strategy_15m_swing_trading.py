"""
15-Minute Swing Trading Strategy
Accuracy Target: 80%+

Based on research:
- Swing highs/lows
- Fibonacci retracements
- Trend continuation

Entry Rules:
CALL: Uptrend + pullback to 50-61.8% fib + RSI oversold recovery
PUT: Downtrend + pullback to 50-61.8% fib + RSI overbought recovery
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy15mSwingTrading:
    def __init__(self):
        self.name = "15m Swing Trading"
        self.timeframe = "15m"
        self.accuracy_target = 80.0
    
    def identify_trend(self, df: pd.DataFrame) -> str:
        """Identify market trend"""
        if len(df) < 50:
            return 'ranging'
        
        latest = df.iloc[-1]
        
        if latest['ema_50'] > latest['ema_100'] and latest['close'] > latest['ema_50']:
            return 'uptrend'
        elif latest['ema_50'] < latest['ema_100'] and latest['close'] < latest['ema_50']:
            return 'downtrend'
        else:
            return 'ranging'
    
    def calculate_fib_levels(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """Calculate Fibonacci retracement levels"""
        recent = df.tail(lookback)
        high = recent['high'].max()
        low = recent['low'].min()
        diff = high - low
        
        return {
            '0': high,
            '23.6': high - (0.236 * diff),
            '38.2': high - (0.382 * diff),
            '50.0': high - (0.5 * diff),
            '61.8': high - (0.618 * diff),
            '100': low
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            df['ema_100'] = talib.EMA(df['close'], timeperiod=100)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 100:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        trend = self.identify_trend(df)
        fib_levels = self.calculate_fib_levels(df)
        
        if df.empty or df['ema_50'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Trend Identification (30 points)
        if trend == 'uptrend':
            call_signals += 30
            reasons.append("✅ Uptrend confirmed")
        elif trend == 'downtrend':
            put_signals += 30
            reasons.append("✅ Downtrend confirmed")
        else:
            reasons.append("⚠️ Market ranging - no clear trend")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        # 2. Fibonacci Pullback (35 points)
        fib_50 = fib_levels['50.0']
        fib_618 = fib_levels['61.8']
        
        if trend == 'uptrend':
            if fib_618 <= latest['close'] <= fib_50:
                call_signals += 35
                reasons.append("✅ Pullback to 50-61.8% Fib level")
        elif trend == 'downtrend':
            if fib_50 <= latest['close'] <= fib_618:
                put_signals += 35
                reasons.append("✅ Pullback to 50-61.8% Fib level")
        
        # 3. RSI Pullback Recovery (20 points)
        if trend == 'uptrend':
            if latest['rsi'] > prev['rsi'] and 40 < latest['rsi'] < 60:
                call_signals += 20
                reasons.append("✅ RSI recovering from pullback")
        elif trend == 'downtrend':
            if latest['rsi'] < prev['rsi'] and 40 < latest['rsi'] < 60:
                put_signals += 20
                reasons.append("✅ RSI recovering from pullback")
        
        # 4. MACD Alignment (10 points)
        if trend == 'uptrend' and latest['macd'] > latest['macd_signal']:
            call_signals += 10
            reasons.append("✅ MACD aligned with trend")
        elif trend == 'downtrend' and latest['macd'] < latest['macd_signal']:
            put_signals += 10
            reasons.append("✅ MACD aligned with trend")
        
        # 5. Momentum Check (5 points)
        price_momentum = (latest['close'] - prev['close']) / prev['close'] * 100
        if trend == 'uptrend' and price_momentum > 0:
            call_signals += 5
        elif trend == 'downtrend' and price_momentum < 0:
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
            'trend': trend,
            'call_score': call_signals,
            'put_score': put_signals,
            'fib_levels': {k: float(v) for k, v in fib_levels.items()},
            'indicators': {
                'rsi': float(latest['rsi']),
                'macd': float(latest['macd'])
            }
        }


strategy_15m_swing_trading = Strategy15mSwingTrading()
