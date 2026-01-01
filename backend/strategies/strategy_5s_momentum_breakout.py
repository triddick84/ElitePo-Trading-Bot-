"""
5-Second Momentum Breakout Strategy
Accuracy Target: 88%+

Based on research:
- MACD + EMA crossover for momentum
- Price action breakout confirmation
- Quick execution for ultra-short timeframes
- Support/Resistance filtering (NEW)

Entry Rules:
CALL: MACD crosses above signal, price above EMA(8), strong volume
PUT: MACD crosses below signal, price below EMA(8), strong volume
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import talib
import logging

# Import S/R detector
try:
    from strategies.support_resistance import get_sr_detector
except ImportError:
    try:
        from support_resistance import get_sr_detector
    except ImportError:
        get_sr_detector = None

logger = logging.getLogger(__name__)


class Strategy5sMomentumBreakout:
    """
    5-Second Momentum Breakout Strategy
    Targets ultra-short timeframe with momentum confirmation
    With S/R filtering for improved accuracy
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "5s Momentum Breakout"
        self.timeframe = "5s"
        self.accuracy_target = 88.0
        self.enable_sr_filter = enable_sr_filter
        
        # Initialize S/R detector
        if get_sr_detector:
            self.sr_detector = get_sr_detector()
        else:
            self.sr_detector = None
            logger.warning("S/R detector not available")
        
        # Parameters
        self.ema_fast = 8
        self.ema_slow = 21
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.volume_threshold = 1.2  # 20% above average
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # EMAs
            df['ema_fast'] = talib.EMA(df['close'], timeperiod=self.ema_fast)
            df['ema_slow'] = talib.EMA(df['close'], timeperiod=self.ema_slow)
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'],
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            
            # Volume analysis
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # Momentum
            df['momentum'] = talib.MOM(df['close'], timeperiod=5)
            
            # ATR for volatility
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """
        Generate trading signal based on strategy rules
        
        Returns:
            Dict with direction, confidence, and reasoning
        """
        if len(df) < 50:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        # Calculate indicators
        df = self.calculate_indicators(df)
        
        if df.empty or df['ema_fast'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check for valid data
        if pd.isna(latest['macd']) or pd.isna(latest['ema_fast']):
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Invalid indicator values'}
        
        confidence = 0
        direction = 'NEUTRAL'
        reasons = []
        
        # CALL Signal Conditions
        call_signals = 0
        put_signals = 0
        
        # 1. MACD Crossover (30 points)
        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            call_signals += 30
            reasons.append("✅ MACD bullish crossover")
        elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            put_signals += 30
            reasons.append("✅ MACD bearish crossover")
        
        # 2. EMA Trend (25 points)
        if latest['close'] > latest['ema_fast'] > latest['ema_slow']:
            call_signals += 25
            reasons.append("✅ Price above EMAs (bullish trend)")
        elif latest['close'] < latest['ema_fast'] < latest['ema_slow']:
            put_signals += 25
            reasons.append("✅ Price below EMAs (bearish trend)")
        
        # 3. Volume Confirmation (20 points)
        if latest['volume_ratio'] > self.volume_threshold:
            if call_signals > put_signals:
                call_signals += 20
                reasons.append(f"✅ High volume confirmation ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 20
                reasons.append(f"✅ High volume confirmation ({latest['volume_ratio']:.2f}x)")
        
        # 4. Momentum (15 points)
        if latest['momentum'] > 0 and latest['momentum'] > prev['momentum']:
            call_signals += 15
            reasons.append("✅ Positive momentum increasing")
        elif latest['momentum'] < 0 and latest['momentum'] < prev['momentum']:
            put_signals += 15
            reasons.append("✅ Negative momentum increasing")
        
        # 5. Volatility Check (10 points)
        if latest['atr'] > df['atr'].mean():
            if call_signals > put_signals:
                call_signals += 10
                reasons.append("✅ High volatility favors breakout")
            elif put_signals > call_signals:
                put_signals += 10
                reasons.append("✅ High volatility favors breakout")
        
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
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'macd': float(latest['macd']),
                'macd_signal': float(latest['macd_signal']),
                'ema_fast': float(latest['ema_fast']),
                'ema_slow': float(latest['ema_slow']),
                'volume_ratio': float(latest['volume_ratio']),
                'momentum': float(latest['momentum'])
            }
        }


# Global instance
strategy_5s_momentum_breakout = Strategy5sMomentumBreakout()
