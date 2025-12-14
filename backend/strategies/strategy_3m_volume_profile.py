"""
3-Minute Volume Profile Strategy
Accuracy Target: 79%+

Based on research:
- Volume analysis at key price levels
- VWAP for trend direction
- Price action confirmation

Entry Rules:
CALL: Price above VWAP, high volume at support, bullish momentum
PUT: Price below VWAP, high volume at resistance, bearish momentum
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy3mVolumeProfile:
    """3-Minute Volume Profile Strategy"""
    
    def __init__(self):
        self.name = "3m Volume Profile"
        self.timeframe = "3m"
        self.accuracy_target = 79.0
        
    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            # VWAP
            df['vwap'] = self.calculate_vwap(df)
            
            # Volume analysis
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # EMAs
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['vwap'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. VWAP Position (35 points)
        if latest['close'] > latest['vwap']:
            call_signals += 35
            reasons.append(f"✅ Price above VWAP (${latest['vwap']:.5f})")
        elif latest['close'] < latest['vwap']:
            put_signals += 35
            reasons.append(f"✅ Price below VWAP (${latest['vwap']:.5f})")
        
        # 2. Volume Confirmation (25 points)
        if latest['volume_ratio'] > 1.5:  # 50% above average
            if call_signals > put_signals:
                call_signals += 25
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x avg)")
            elif put_signals > call_signals:
                put_signals += 25
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x avg)")
        
        # 3. EMA Trend (20 points)
        if latest['ema_20'] > latest['ema_50']:
            call_signals += 20
            reasons.append("✅ EMA trend bullish")
        elif latest['ema_20'] < latest['ema_50']:
            put_signals += 20
            reasons.append("✅ EMA trend bearish")
        
        # 4. MACD Momentum (10 points)
        if latest['macd'] > latest['macd_signal']:
            call_signals += 10
            reasons.append("✅ MACD bullish")
        elif latest['macd'] < latest['macd_signal']:
            put_signals += 10
            reasons.append("✅ MACD bearish")
        
        # 5. RSI Filter (10 points)
        if 40 < latest['rsi'] < 70:
            call_signals += 10
        elif 30 < latest['rsi'] < 60:
            put_signals += 10
        
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
                'vwap': float(latest['vwap']),
                'volume_ratio': float(latest['volume_ratio']),
                'rsi': float(latest['rsi'])
            }
        }


strategy_3m_volume_profile = Strategy3mVolumeProfile()
