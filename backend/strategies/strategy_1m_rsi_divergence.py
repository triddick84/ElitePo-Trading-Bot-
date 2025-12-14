"""
1-Minute RSI Divergence Strategy
Accuracy Target: 83%+

Based on research:
- RSI divergence for reversal predictions
- MACD confirmation
- Bollinger Bands for overbought/oversold

Entry Rules:
CALL: RSI bullish divergence + MACD turns bullish + Price at lower BB
PUT: RSI bearish divergence + MACD turns bearish + Price at upper BB
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy1mRSIDivergence:
    """
    1-Minute RSI Divergence Strategy
    Focuses on reversal trading with divergence confirmation
    """
    
    def __init__(self):
        self.name = "1m RSI Divergence"
        self.timeframe = "1m"
        self.accuracy_target = 83.0
        
        # Parameters
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.bb_period = 20
        self.bb_std = 2
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=self.rsi_period)
            
            # Bollinger Bands
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'],
                timeperiod=self.bb_period,
                nbdevup=self.bb_std,
                nbdevdn=self.bb_std
            )
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'],
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            
            # Stochastic for additional confirmation
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def detect_divergence(self, df: pd.DataFrame, lookback: int = 10) -> Dict:
        """
        Detect bullish or bearish divergence
        
        Returns:
            Dict with divergence type and strength
        """
        if len(df) < lookback:
            return {'type': 'none', 'strength': 0}
        
        recent_df = df.tail(lookback)
        
        # Find price highs/lows
        price_high_idx = recent_df['high'].idxmax()
        price_low_idx = recent_df['low'].idxmin()
        
        # Find RSI highs/lows
        rsi_high_idx = recent_df['rsi'].idxmax()
        rsi_low_idx = recent_df['rsi'].idxmin()
        
        # Bullish Divergence: Price makes lower low, RSI makes higher low
        if price_low_idx < len(recent_df) - 3:  # Not too recent
            price_ll = recent_df.loc[price_low_idx, 'low']
            current_low = recent_df['low'].iloc[-3:].min()
            
            rsi_ll = recent_df.loc[price_low_idx, 'rsi']
            current_rsi = recent_df['rsi'].iloc[-3:].min()
            
            if current_low < price_ll and current_rsi > rsi_ll:
                strength = min(100, (current_rsi - rsi_ll) * 10)
                return {'type': 'bullish', 'strength': strength}
        
        # Bearish Divergence: Price makes higher high, RSI makes lower high
        if price_high_idx < len(recent_df) - 3:
            price_hh = recent_df.loc[price_high_idx, 'high']
            current_high = recent_df['high'].iloc[-3:].max()
            
            rsi_hh = recent_df.loc[price_high_idx, 'rsi']
            current_rsi = recent_df['rsi'].iloc[-3:].max()
            
            if current_high > price_hh and current_rsi < rsi_hh:
                strength = min(100, (rsi_hh - current_rsi) * 10)
                return {'type': 'bearish', 'strength': strength}
        
        return {'type': 'none', 'strength': 0}
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal based on strategy rules"""
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        # Calculate indicators
        df = self.calculate_indicators(df)
        
        if df.empty or df['rsi'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Detect divergence
        divergence = self.detect_divergence(df)
        
        confidence = 0
        direction = 'NEUTRAL'
        reasons = []
        
        # Signal scoring
        call_signals = 0
        put_signals = 0
        
        # 1. RSI Divergence (35 points)
        if divergence['type'] == 'bullish':
            call_signals += 35
            reasons.append(f"✅ Bullish RSI divergence (strength: {divergence['strength']:.0f})")
        elif divergence['type'] == 'bearish':
            put_signals += 35
            reasons.append(f"✅ Bearish RSI divergence (strength: {divergence['strength']:.0f})")
        
        # 2. RSI Extreme Levels (20 points)
        if latest['rsi'] < self.rsi_oversold:
            call_signals += 20
            reasons.append(f"✅ RSI oversold ({latest['rsi']:.1f})")
        elif latest['rsi'] > self.rsi_overbought:
            put_signals += 20
            reasons.append(f"✅ RSI overbought ({latest['rsi']:.1f})")
        
        # 3. Bollinger Band Position (20 points)
        if latest['close'] <= latest['bb_lower']:
            call_signals += 20
            reasons.append("✅ Price at lower Bollinger Band")
        elif latest['close'] >= latest['bb_upper']:
            put_signals += 20
            reasons.append("✅ Price at upper Bollinger Band")
        
        # 4. MACD Confirmation (15 points)
        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            call_signals += 15
            reasons.append("✅ MACD bullish crossover")
        elif latest['macd'] < latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            put_signals += 15
            reasons.append("✅ MACD bearish crossover")
        
        # 5. Stochastic Confirmation (10 points)
        if latest['stoch_k'] < 20 and latest['stoch_k'] > prev['stoch_k']:
            call_signals += 10
            reasons.append("✅ Stochastic turning up from oversold")
        elif latest['stoch_k'] > 80 and latest['stoch_k'] < prev['stoch_k']:
            put_signals += 10
            reasons.append("✅ Stochastic turning down from overbought")
        
        # Determine final signal
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
            'divergence': divergence,
            'indicators': {
                'rsi': float(latest['rsi']),
                'bb_upper': float(latest['bb_upper']),
                'bb_lower': float(latest['bb_lower']),
                'macd': float(latest['macd']),
                'stoch_k': float(latest['stoch_k'])
            }
        }


# Global instance
strategy_1m_rsi_divergence = Strategy1mRSIDivergence()
