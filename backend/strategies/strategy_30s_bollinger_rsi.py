"""
30-Second Bollinger Bands + RSI Mean Reversion Strategy
Accuracy Target: 83%+

Based on research:
- Bollinger Bands for overbought/oversold
- RSI confirmation
- Mean reversion trading

Entry Rules:
CALL: Price touches lower BB, RSI < 30, price starts reverting to mean
PUT: Price touches upper BB, RSI > 70, price starts reverting to mean
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy30sBollingerRSI:
    """30-Second Bollinger + RSI Mean Reversion Strategy"""
    
    def __init__(self):
        self.name = "30s Bollinger + RSI"
        self.timeframe = "30s"
        self.accuracy_target = 83.0
        
        # Parameters
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # Bollinger Bands
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'],
                timeperiod=self.bb_period,
                nbdevup=self.bb_std,
                nbdevdn=self.bb_std
            )
            
            # BB Width for volatility
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=self.rsi_period)
            
            # MACD for trend
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            
            # ATR
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal"""
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['bb_lower'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Bollinger Band Position (35 points)
        if latest['close'] <= latest['bb_lower']:
            call_signals += 35
            reasons.append("✅ Price at/below lower Bollinger Band")
        elif latest['close'] >= latest['bb_upper']:
            put_signals += 35
            reasons.append("✅ Price at/above upper Bollinger Band")
        
        # Check BB squeeze for low volatility (better for mean reversion)
        if latest['bb_width'] < df['bb_width'].mean():
            if call_signals > 0:
                call_signals += 10
                reasons.append("✅ BB squeeze - low volatility favors reversion")
            elif put_signals > 0:
                put_signals += 10
                reasons.append("✅ BB squeeze - low volatility favors reversion")
        
        # 2. RSI Extreme (30 points)
        if latest['rsi'] < self.rsi_oversold:
            call_signals += 30
            reasons.append(f"✅ RSI oversold ({latest['rsi']:.1f})")
        elif latest['rsi'] > self.rsi_overbought:
            put_signals += 30
            reasons.append(f"✅ RSI overbought ({latest['rsi']:.1f})")
        
        # 3. Mean Reversion Starting (20 points)
        # Check if price is starting to move back toward mean
        if call_signals > 0 and latest['close'] > prev['close']:
            call_signals += 20
            reasons.append("✅ Price reversing upward toward mean")
        elif put_signals > 0 and latest['close'] < prev['close']:
            put_signals += 20
            reasons.append("✅ Price reversing downward toward mean")
        
        # 4. MACD Divergence (10 points)
        # Weakening trend favors mean reversion
        if abs(latest['macd_hist']) < abs(prev['macd_hist']):
            if call_signals > put_signals:
                call_signals += 10
                reasons.append("✅ MACD momentum weakening")
            elif put_signals > call_signals:
                put_signals += 10
                reasons.append("✅ MACD momentum weakening")
        
        # 5. Volatility Check (5 points)
        if latest['atr'] < df['atr'].mean():
            if call_signals > 0 or put_signals > 0:
                if call_signals > put_signals:
                    call_signals += 5
                else:
                    put_signals += 5
                reasons.append("✅ Low volatility environment")
        
        # Determine signal
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
                'bb_upper': float(latest['bb_upper']),
                'bb_middle': float(latest['bb_middle']),
                'bb_lower': float(latest['bb_lower']),
                'rsi': float(latest['rsi']),
                'bb_width': float(latest['bb_width'])
            }
        }


strategy_30s_bollinger_rsi = Strategy30sBollingerRSI()
