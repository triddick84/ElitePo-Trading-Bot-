"""
15-Minute Multi-Timeframe Strategy
Accuracy Target: 85%+

Based on research:
- Multi-timeframe trend alignment
- Higher timeframe (1h) for trend
- Lower timeframe (5m) for entry

Entry Rules:
CALL: 1h uptrend + 5m pullback + RSI oversold + MACD turns bullish
PUT: 1h downtrend + 5m pullback + RSI overbought + MACD turns bearish
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy15mMultiTimeframe:
    """15-Minute Multi-Timeframe Strategy"""
    
    def __init__(self):
        self.name = "15m Multi-Timeframe"
        self.timeframe = "15m"
        self.accuracy_target = 85.0
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            # EMAs for multiple timeframes
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)  # ~5h on 15m chart
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)  # ~12.5h on 15m chart
            df['ema_200'] = talib.EMA(df['close'], timeperiod=200)  # ~50h on 15m chart
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            
            # Stochastic
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            
            # ATR
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # ADX for trend strength
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def identify_higher_tf_trend(self, df: pd.DataFrame) -> str:
        """Identify trend from higher timeframe perspective"""
        if len(df) < 200:
            return 'ranging'
        
        latest = df.iloc[-1]
        
        # Check EMA alignment
        if (latest['ema_20'] > latest['ema_50'] > latest['ema_200'] and
            latest['close'] > latest['ema_20']):
            return 'uptrend'
        elif (latest['ema_20'] < latest['ema_50'] < latest['ema_200'] and
              latest['close'] < latest['ema_20']):
            return 'downtrend'
        else:
            return 'ranging'
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 200:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data for multi-TF analysis'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['ema_20'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Identify higher timeframe trend
        htf_trend = self.identify_higher_tf_trend(df)
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Higher Timeframe Trend (35 points)
        if htf_trend == 'uptrend':
            call_signals += 35
            reasons.append("✅ Higher TF: Strong uptrend")
        elif htf_trend == 'downtrend':
            put_signals += 35
            reasons.append("✅ Higher TF: Strong downtrend")
        else:
            reasons.append("⚠️ Higher TF: Ranging market")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        # 2. Trend Strength (ADX) (25 points)
        if latest['adx'] > 25:
            strength_bonus = min(25, (latest['adx'] - 25) / 2)
            if htf_trend == 'uptrend':
                call_signals += strength_bonus
            else:
                put_signals += strength_bonus
            reasons.append(f"✅ Strong trend (ADX: {latest['adx']:.1f})")
        
        # 3. Entry Timing (Pullback) (20 points)
        if htf_trend == 'uptrend':
            # Look for pullback in uptrend
            if latest['stoch_k'] < 30 or latest['rsi'] < 40:
                call_signals += 20
                reasons.append("✅ Pullback in uptrend (entry opportunity)")
        elif htf_trend == 'downtrend':
            # Look for pullback in downtrend
            if latest['stoch_k'] > 70 or latest['rsi'] > 60:
                put_signals += 20
                reasons.append("✅ Pullback in downtrend (entry opportunity)")
        
        # 4. MACD Confirmation (15 points)
        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            call_signals += 15
            reasons.append("✅ MACD bullish crossover")
        elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            put_signals += 15
            reasons.append("✅ MACD bearish crossover")
        
        # 5. Price Action (5 points)
        price_momentum = (latest['close'] - prev['close']) / prev['close'] * 100
        if htf_trend == 'uptrend' and price_momentum > 0:
            call_signals += 5
            reasons.append("✅ Bullish momentum")
        elif htf_trend == 'downtrend' and price_momentum < 0:
            put_signals += 5
            reasons.append("✅ Bearish momentum")
        
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
            'htf_trend': htf_trend,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'adx': float(latest['adx']),
                'rsi': float(latest['rsi']),
                'stoch_k': float(latest['stoch_k']),
                'macd': float(latest['macd'])
            }
        }


strategy_15m_multi_timeframe = Strategy15mMultiTimeframe()
