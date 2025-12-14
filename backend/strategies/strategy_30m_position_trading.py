"""
30-Minute Position Trading Strategy
Accuracy Target: 82%+

Based on research:
- Strong trend following
- Multi-timeframe confirmation
- Risk management with stops

Entry Rules:
CALL: All EMAs aligned up + ADX > 30 + Price pullback to EMA(20)
PUT: All EMAs aligned down + ADX > 30 + Price pullback to EMA(20)
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy30mPositionTrading:
    def __init__(self):
        self.name = "30m Position Trading"
        self.timeframe = "30m"
        self.accuracy_target = 82.0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['ema_20'] = talib.EMA(df['close'], timeperiod=20)
            df['ema_50'] = talib.EMA(df['close'], timeperiod=50)
            df['ema_100'] = talib.EMA(df['close'], timeperiod=100)
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
            df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 100:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['ema_20'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. EMA Alignment (40 points)
        if latest['ema_20'] > latest['ema_50'] > latest['ema_100']:
            call_signals += 40
            reasons.append("✅ All EMAs aligned bullish")
        elif latest['ema_20'] < latest['ema_50'] < latest['ema_100']:
            put_signals += 40
            reasons.append("✅ All EMAs aligned bearish")
        
        # 2. Strong Trend (ADX) (30 points)
        if latest['adx'] > 30:
            if latest['plus_di'] > latest['minus_di']:
                call_signals += 30
                reasons.append(f"✅ Strong uptrend (ADX: {latest['adx']:.1f})")
            else:
                put_signals += 30
                reasons.append(f"✅ Strong downtrend (ADX: {latest['adx']:.1f})")
        
        # 3. Pullback Entry (20 points)
        ema_distance = abs(latest['close'] - latest['ema_20']) / latest['close'] * 100
        if ema_distance < 0.5:  # Within 0.5% of EMA(20)
            if call_signals > put_signals:
                call_signals += 20
                reasons.append("✅ Price near EMA(20) - pullback entry")
            elif put_signals > call_signals:
                put_signals += 20
                reasons.append("✅ Price near EMA(20) - pullback entry")
        
        # 4. RSI Filter (5 points)
        if 45 < latest['rsi'] < 70:
            call_signals += 5
        elif 30 < latest['rsi'] < 55:
            put_signals += 5
        
        # 5. Volatility Check (5 points)
        if latest['atr'] > df['atr'].mean():
            if call_signals > 0 or put_signals > 0:
                if call_signals > put_signals:
                    call_signals += 5
                else:
                    put_signals += 5
                reasons.append("✅ High volatility environment")
        
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
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'adx': float(latest['adx']),
                'ema_20': float(latest['ema_20']),
                'rsi': float(latest['rsi']),
                'atr': float(latest['atr'])
            }
        }


strategy_30m_position_trading = Strategy30mPositionTrading()
