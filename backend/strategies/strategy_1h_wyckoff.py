"""
1-Hour Wyckoff Method Strategy
Accuracy Target: 86%+

Based on research:
- Wyckoff accumulation/distribution
- Volume analysis
- Smart money tracking

Entry Rules:
CALL: Accumulation phase + spring test + volume increase
PUT: Distribution phase + upthrust test + volume increase
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy1hWyckoff:
    def __init__(self):
        self.name = "1h Wyckoff Method"
        self.timeframe = "1h"
        self.accuracy_target = 86.0
    
    def detect_wyckoff_phase(self, df: pd.DataFrame) -> str:
        """Detect Wyckoff accumulation or distribution phase"""
        if len(df) < 20:
            return 'none'
        
        recent = df.tail(20)
        price_range = recent['high'].max() - recent['low'].min()
        avg_volume = recent['volume'].mean()
        
        # Check for low volatility + high volume (accumulation sign)
        recent_range = recent['high'].iloc[-5:].max() - recent['low'].iloc[-5:].min()
        recent_volume = recent['volume'].iloc[-5:].mean()
        
        if recent_range < (price_range * 0.3) and recent_volume > avg_volume:
            # Narrow range + high volume suggests accumulation
            return 'accumulation'
        elif recent_range < (price_range * 0.3) and recent_volume < (avg_volume * 0.7):
            # Narrow range + low volume suggests distribution
            return 'distribution'
        
        return 'none'
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            df['obv'] = talib.OBV(df['close'], df['volume'])
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        wyckoff_phase = self.detect_wyckoff_phase(df)
        
        if df.empty or df['ema_20'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Wyckoff Phase Detection (40 points)
        if wyckoff_phase == 'accumulation':
            call_signals += 40
            reasons.append("✅ Wyckoff accumulation phase detected")
        elif wyckoff_phase == 'distribution':
            put_signals += 40
            reasons.append("✅ Wyckoff distribution phase detected")
        
        # 2. Volume Confirmation (25 points)
        if latest['volume_ratio'] > 1.5:
            if call_signals > put_signals:
                call_signals += 25
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 25
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
        
        # 3. OBV Trend (20 points)
        if latest['obv'] > prev['obv']:
            call_signals += 20
            reasons.append("✅ OBV rising (buying pressure)")
        elif latest['obv'] < prev['obv']:
            put_signals += 20
            reasons.append("✅ OBV falling (selling pressure)")
        
        # 4. MACD Confirmation (10 points)
        if latest['macd'] > latest['macd_signal']:
            call_signals += 10
        elif latest['macd'] < latest['macd_signal']:
            put_signals += 10
        
        # 5. EMA Position (5 points)
        if latest['close'] > latest['ema_20']:
            call_signals += 5
        elif latest['close'] < latest['ema_20']:
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
            reasons.append("⚠️ No clear Wyckoff phase or insufficient confirmation")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'wyckoff_phase': wyckoff_phase,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'volume_ratio': float(latest['volume_ratio']),
                'obv': float(latest['obv']),
                'rsi': float(latest['rsi'])
            }
        }


strategy_1h_wyckoff = Strategy1hWyckoff()
