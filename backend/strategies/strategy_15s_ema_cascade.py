"""
15-Second EMA Cascade Strategy (3-5-8-13)
Accuracy Target: 82%+

Based on research:
- Fibonacci EMA periods (3, 5, 8, 13)
- Cascade alignment for trend confirmation
- Golden/Death cross cascade patterns
- MACD + RSI confirmation

Entry Rules:
CALL: EMA3 > EMA5 > EMA8 > EMA13 (Golden Cascade) + RSI rising from oversold
PUT: EMA3 < EMA5 < EMA8 < EMA13 (Death Cascade) + RSI falling from overbought

Research Sources:
- EMA crossover scalping strategies
- Fibonacci-based momentum trading
- Triple EMA confirmation systems
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False


class Strategy15sEMACascade:
    """
    15-Second EMA Cascade Strategy
    
    Uses Fibonacci-based EMA periods for cascade alignment:
    - EMA 3 (ultra-fast)
    - EMA 5 (fast)
    - EMA 8 (medium)
    - EMA 13 (slow)
    
    Golden Cascade = All EMAs aligned bullish
    Death Cascade = All EMAs aligned bearish
    """
    
    def __init__(self):
        self.name = "15s EMA Cascade (3-5-8-13)"
        self.timeframe = "15s"
        self.accuracy_target = 82.0
        
        # EMA periods (Fibonacci-inspired)
        self.ema_periods = [3, 5, 8, 13]
        
        # Additional filters
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        self.min_confidence = 72
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all EMAs and confirmation indicators"""
        try:
            df = df.copy()
            
            # Normalize columns
            for col in ['open', 'high', 'low', 'close']:
                if col not in df.columns and col.capitalize() in df.columns:
                    df[col] = df[col.capitalize()]
            
            close = df['close'].astype(float)
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            
            if TALIB_AVAILABLE:
                # Calculate all EMAs
                df['ema_3'] = talib.EMA(close, timeperiod=3)
                df['ema_5'] = talib.EMA(close, timeperiod=5)
                df['ema_8'] = talib.EMA(close, timeperiod=8)
                df['ema_13'] = talib.EMA(close, timeperiod=13)
                df['ema_21'] = talib.EMA(close, timeperiod=21)
                
                # RSI
                df['rsi'] = talib.RSI(close, timeperiod=self.rsi_period)
                
                # MACD
                df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                    close, fastperiod=12, slowperiod=26, signalperiod=9
                )
                
                # Stochastic
                df['stoch_k'], df['stoch_d'] = talib.STOCH(
                    high, low, close,
                    fastk_period=5, slowk_period=3, slowd_period=3
                )
                
                # ADX for trend strength
                df['adx'] = talib.ADX(high, low, close, timeperiod=14)
                
                # Momentum
                df['mom'] = talib.MOM(close, timeperiod=10)
                
            else:
                # Fallback EMA calculations
                df['ema_3'] = close.ewm(span=3, adjust=False).mean()
                df['ema_5'] = close.ewm(span=5, adjust=False).mean()
                df['ema_8'] = close.ewm(span=8, adjust=False).mean()
                df['ema_13'] = close.ewm(span=13, adjust=False).mean()
                df['ema_21'] = close.ewm(span=21, adjust=False).mean()
                
                # RSI
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(self.rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                # MACD
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                df['macd'] = ema12 - ema26
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_hist'] = df['macd'] - df['macd_signal']
                
                # Stochastic
                lowest_low = low.rolling(5).min()
                highest_high = high.rolling(5).max()
                df['stoch_k'] = 100 * (close - lowest_low) / (highest_high - lowest_low)
                df['stoch_d'] = df['stoch_k'].rolling(3).mean()
                
                # Momentum
                df['mom'] = close.diff(10)
                
                df['adx'] = 25  # Default
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def _check_cascade_alignment(self, ema3: float, ema5: float, ema8: float, ema13: float) -> tuple:
        """
        Check EMA cascade alignment
        Returns: (is_bullish, is_bearish, alignment_score)
        """
        bullish_count = 0
        bearish_count = 0
        
        # Check each adjacent pair
        if ema3 > ema5:
            bullish_count += 1
        elif ema3 < ema5:
            bearish_count += 1
        
        if ema5 > ema8:
            bullish_count += 1
        elif ema5 < ema8:
            bearish_count += 1
        
        if ema8 > ema13:
            bullish_count += 1
        elif ema8 < ema13:
            bearish_count += 1
        
        is_bullish = bullish_count == 3  # Perfect golden cascade
        is_bearish = bearish_count == 3  # Perfect death cascade
        
        alignment_score = max(bullish_count, bearish_count) / 3 * 100
        
        return is_bullish, is_bearish, alignment_score, bullish_count, bearish_count
    
    def generate_signal(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
        """Generate trading signal based on EMA cascade"""
        if len(df) < 25:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'Insufficient data',
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        df = self.calculate_indicators(df)
        
        if df.empty or 'ema_3' not in df.columns:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'Indicator calculation failed',
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_score = 0
        put_score = 0
        reasons = []
        
        # Get EMA values
        ema3 = latest['ema_3']
        ema5 = latest['ema_5']
        ema8 = latest['ema_8']
        ema13 = latest['ema_13']
        close = latest['close']
        
        # Previous EMAs for crossover detection
        ema3_prev = prev['ema_3']
        ema5_prev = prev['ema_5']
        
        # ============================================
        # 1. EMA CASCADE ALIGNMENT (40 points)
        # ============================================
        is_bullish, is_bearish, alignment_score, bull_count, bear_count = self._check_cascade_alignment(
            ema3, ema5, ema8, ema13
        )
        
        if is_bullish:  # Perfect golden cascade
            call_score += 40
            reasons.append("✅ GOLDEN CASCADE: EMA3 > EMA5 > EMA8 > EMA13")
        elif is_bearish:  # Perfect death cascade
            put_score += 40
            reasons.append("✅ DEATH CASCADE: EMA3 < EMA5 < EMA8 < EMA13")
        elif bull_count >= 2:
            call_score += 25
            reasons.append(f"⚡ Partial bullish cascade ({bull_count}/3)")
        elif bear_count >= 2:
            put_score += 25
            reasons.append(f"⚡ Partial bearish cascade ({bear_count}/3)")
        
        # ============================================
        # 2. PRICE VS EMA POSITION (15 points)
        # ============================================
        if close > ema3 and close > ema5:
            call_score += 15
            reasons.append("✅ Price above fast EMAs")
        elif close < ema3 and close < ema5:
            put_score += 15
            reasons.append("✅ Price below fast EMAs")
        
        # ============================================
        # 3. EMA 3/5 CROSSOVER (15 points)
        # ============================================
        # Bullish crossover: EMA3 crosses above EMA5
        if ema3 > ema5 and ema3_prev <= ema5_prev:
            call_score += 15
            reasons.append("✅ EMA3 bullish crossover above EMA5")
        # Bearish crossover: EMA3 crosses below EMA5
        elif ema3 < ema5 and ema3_prev >= ema5_prev:
            put_score += 15
            reasons.append("✅ EMA3 bearish crossover below EMA5")
        
        # ============================================
        # 4. RSI CONFIRMATION (15 points)
        # ============================================
        rsi = latest['rsi']
        rsi_prev = prev['rsi']
        
        if rsi < self.rsi_oversold and rsi > rsi_prev:
            call_score += 15
            reasons.append(f"✅ RSI oversold & rising ({rsi:.1f})")
        elif rsi > self.rsi_overbought and rsi < rsi_prev:
            put_score += 15
            reasons.append(f"✅ RSI overbought & falling ({rsi:.1f})")
        elif rsi > 50 and call_score > put_score:
            call_score += 8
        elif rsi < 50 and put_score > call_score:
            put_score += 8
        
        # ============================================
        # 5. MACD MOMENTUM (10 points)
        # ============================================
        macd_hist = latest['macd_hist']
        macd_hist_prev = prev['macd_hist']
        
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            call_score += 10
            reasons.append("✅ MACD bullish momentum")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            put_score += 10
            reasons.append("✅ MACD bearish momentum")
        
        # ============================================
        # 6. STOCHASTIC CONFIRMATION (5 points)
        # ============================================
        stoch_k = latest.get('stoch_k', 50)
        
        if stoch_k < 20:
            call_score += 5
        elif stoch_k > 80:
            put_score += 5
        
        # ============================================
        # FINAL SIGNAL
        # ============================================
        direction = 'NEUTRAL'
        confidence = max(call_score, put_score)
        
        if call_score > put_score and call_score >= self.min_confidence:
            direction = 'CALL'
            confidence = min(call_score, 100)
        elif put_score > call_score and put_score >= self.min_confidence:
            direction = 'PUT'
            confidence = min(put_score, 100)
        else:
            reasons.append(f"⚠️ Confidence {confidence} below {self.min_confidence}")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'probability': confidence,
            'reason': ' | '.join(reasons[:5]),
            'reasoning': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'call_score': call_score,
            'put_score': put_score,
            'symbol': symbol,
            'indicators': {
                'ema_3': float(ema3) if not np.isnan(ema3) else 0,
                'ema_5': float(ema5) if not np.isnan(ema5) else 0,
                'ema_8': float(ema8) if not np.isnan(ema8) else 0,
                'ema_13': float(ema13) if not np.isnan(ema13) else 0,
                'rsi': float(rsi) if not np.isnan(rsi) else 50,
                'cascade_aligned': is_bullish or is_bearish
            }
        }


strategy_15s_ema_cascade = Strategy15sEMACascade()


def generate_signal(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
    """Wrapper for strategy registry"""
    return strategy_15s_ema_cascade.generate_signal(df, symbol)
