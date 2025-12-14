"""
5-Minute Trend Following Strategy
Accuracy Target: 80%+

Based on research:
- EMA trend confirmation
- ADX for trend strength
- Stochastic for entry timing

Entry Rules:
CALL: Price above EMA(20), ADX > 25, Stochastic crosses up from oversold
PUT: Price below EMA(20), ADX > 25, Stochastic crosses down from overbought
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy5mTrendFollowing:
    """
    5-Minute Trend Following Strategy
    Catches strong trends with proper entry timing
    """
    
    def __init__(self):
        self.name = "5m Trend Following"
        self.timeframe = "5m"
        self.accuracy_target = 80.0
        
        # Parameters
        self.ema_fast = 20
        self.ema_slow = 50
        self.ema_trend = 200
        self.adx_period = 14
        self.adx_threshold = 25
        self.stoch_period = 14
        self.stoch_smooth = 3
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # EMAs for trend
            df['ema_fast'] = talib.EMA(df['close'], timeperiod=self.ema_fast)
            df['ema_slow'] = talib.EMA(df['close'], timeperiod=self.ema_slow)
            df['ema_trend'] = talib.EMA(df['close'], timeperiod=self.ema_trend)
            
            # ADX for trend strength
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
            df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
            df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
            
            # Stochastic for entry timing
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=self.stoch_period,
                slowk_period=self.stoch_smooth,
                slowd_period=self.stoch_smooth
            )
            
            # ATR for volatility
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # RSI for confirmation
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def identify_trend(self, df: pd.DataFrame) -> str:
        """
        Identify market trend
        Returns: 'uptrend', 'downtrend', or 'ranging'
        """
        if len(df) < 200:
            return 'ranging'
        
        latest = df.iloc[-1]
        
        # Strong uptrend conditions
        if (latest['ema_fast'] > latest['ema_slow'] > latest['ema_trend'] and
            latest['close'] > latest['ema_fast'] and
            latest['plus_di'] > latest['minus_di']):
            return 'uptrend'
        
        # Strong downtrend conditions
        elif (latest['ema_fast'] < latest['ema_slow'] < latest['ema_trend'] and
              latest['close'] < latest['ema_fast'] and
              latest['minus_di'] > latest['plus_di']):
            return 'downtrend'
        
        else:
            return 'ranging'
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal based on strategy rules"""
        if len(df) < 200:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data for trend analysis'}
        
        # Calculate indicators
        df = self.calculate_indicators(df)
        
        if df.empty or df['adx'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Identify trend
        trend = self.identify_trend(df)
        
        confidence = 0
        direction = 'NEUTRAL'
        reasons = []
        
        # Signal scoring
        call_signals = 0
        put_signals = 0
        
        # 1. Trend Identification (30 points)
        if trend == 'uptrend':
            call_signals += 30
            reasons.append("✅ Strong uptrend identified")
        elif trend == 'downtrend':
            put_signals += 30
            reasons.append("✅ Strong downtrend identified")
        else:
            reasons.append("⚠️ Market ranging - no clear trend")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        # 2. ADX Trend Strength (25 points)
        if latest['adx'] > self.adx_threshold:
            strength_bonus = min(25, (latest['adx'] - self.adx_threshold) / 2)
            if trend == 'uptrend':
                call_signals += strength_bonus
            else:
                put_signals += strength_bonus
            reasons.append(f"✅ Strong ADX ({latest['adx']:.1f})")
        else:
            reasons.append(f"⚠️ Weak trend strength (ADX: {latest['adx']:.1f})")
        
        # 3. Stochastic Entry Timing (25 points)
        if trend == 'uptrend':
            # Look for pullback entries
            if latest['stoch_k'] < 30 and latest['stoch_k'] > prev['stoch_k']:
                call_signals += 25
                reasons.append("✅ Stochastic turning up from oversold")
            elif latest['stoch_k'] > prev['stoch_k']:
                call_signals += 15
                reasons.append("✅ Stochastic rising")
        
        elif trend == 'downtrend':
            # Look for pullback entries
            if latest['stoch_k'] > 70 and latest['stoch_k'] < prev['stoch_k']:
                put_signals += 25
                reasons.append("✅ Stochastic turning down from overbought")
            elif latest['stoch_k'] < prev['stoch_k']:
                put_signals += 15
                reasons.append("✅ Stochastic falling")
        
        # 4. RSI Confirmation (10 points)
        if trend == 'uptrend' and 40 < latest['rsi'] < 70:
            call_signals += 10
            reasons.append("✅ RSI in bullish range")
        elif trend == 'downtrend' and 30 < latest['rsi'] < 60:
            put_signals += 10
            reasons.append("✅ RSI in bearish range")
        
        # 5. Momentum Check (10 points)
        price_change = (latest['close'] - prev['close']) / prev['close'] * 100
        if trend == 'uptrend' and price_change > 0:
            call_signals += 10
            reasons.append(f"✅ Positive momentum ({price_change:.2f}%)")
        elif trend == 'downtrend' and price_change < 0:
            put_signals += 10
            reasons.append(f"✅ Negative momentum ({price_change:.2f}%)")
        
        # Determine final signal
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
            'trend': trend,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'adx': float(latest['adx']),
                'ema_fast': float(latest['ema_fast']),
                'ema_slow': float(latest['ema_slow']),
                'stoch_k': float(latest['stoch_k']),
                'rsi': float(latest['rsi'])
            }
        }


# Global instance
strategy_5m_trend_following = Strategy5mTrendFollowing()
