"""
15-Second EMA Crossover Strategy
Accuracy Target: 82%+

Based on research:
- Fast and slow EMA crossovers
- Stochastic for overbought/oversold confirmation
- Volume validation

Entry Rules:
CALL: EMA(5) crosses above EMA(13), Stochastic turns up from oversold, volume increasing
PUT: EMA(5) crosses below EMA(13), Stochastic turns down from overbought, volume increasing
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy15sEMACrossover:
    """15-Second EMA Crossover Strategy with confirmation"""
    
    def __init__(self):
        self.name = "15s EMA Crossover"
        self.timeframe = "15s"
        self.accuracy_target = 82.0
        
        # Parameters
        self.ema_fast = 5
        self.ema_slow = 13
        self.stoch_period = 14
        self.stoch_smooth = 3
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # EMAs
            df['ema_fast'] = talib.EMA(df['close'], timeperiod=self.ema_fast)
            df['ema_slow'] = talib.EMA(df['close'], timeperiod=self.ema_slow)
            
            # Stochastic
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=self.stoch_period,
                slowk_period=self.stoch_smooth,
                slowd_period=self.stoch_smooth
            )
            
            # Volume
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # RSI for additional confirmation
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal"""
        if len(df) < 30:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['ema_fast'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. EMA Crossover (40 points)
        if latest['ema_fast'] > latest['ema_slow'] and prev['ema_fast'] <= prev['ema_slow']:
            call_signals += 40
            reasons.append("✅ Bullish EMA crossover")
        elif latest['ema_fast'] < latest['ema_slow'] and prev['ema_fast'] >= prev['ema_slow']:
            put_signals += 40
            reasons.append("✅ Bearish EMA crossover")
        
        # 2. EMA Trend Strength (20 points)
        ema_distance = abs(latest['ema_fast'] - latest['ema_slow']) / latest['close'] * 100
        if ema_distance > 0.1:  # Significant separation
            if latest['ema_fast'] > latest['ema_slow']:
                call_signals += 20
                reasons.append(f"✅ Strong EMA separation ({ema_distance:.2f}%)")
            else:
                put_signals += 20
                reasons.append(f"✅ Strong EMA separation ({ema_distance:.2f}%)")
        
        # 3. Stochastic Confirmation (20 points)
        if latest['stoch_k'] < 30 and latest['stoch_k'] > prev['stoch_k']:
            call_signals += 20
            reasons.append("✅ Stochastic turning up from oversold")
        elif latest['stoch_k'] > 70 and latest['stoch_k'] < prev['stoch_k']:
            put_signals += 20
            reasons.append("✅ Stochastic turning down from overbought")
        
        # 4. Volume Confirmation (10 points)
        if latest['volume_ratio'] > 1.2:
            if call_signals > put_signals:
                call_signals += 10
                reasons.append(f"✅ Volume surge ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 10
                reasons.append(f"✅ Volume surge ({latest['volume_ratio']:.2f}x)")
        
        # 5. RSI Filter (10 points)
        if 45 < latest['rsi'] < 75:
            call_signals += 10
            reasons.append("✅ RSI in bullish range")
        elif 25 < latest['rsi'] < 55:
            put_signals += 10
            reasons.append("✅ RSI in bearish range")
        
        # Determine signal
        if call_signals > put_signals and call_signals >= 65:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 65:
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
                'ema_fast': float(latest['ema_fast']),
                'ema_slow': float(latest['ema_slow']),
                'stoch_k': float(latest['stoch_k']),
                'rsi': float(latest['rsi'])
            }
        }


strategy_15s_ema_crossover = Strategy15sEMACrossover()
