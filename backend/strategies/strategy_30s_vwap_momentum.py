"""
30-Second VWAP Momentum Divergence Strategy
Accuracy Target: 80%+

Based on research:
- VWAP as dynamic support/resistance
- Volume confirmation for breakouts
- RSI/MACD momentum divergence
- Price deviation from VWAP

Entry Rules:
CALL: Price crosses above VWAP + volume spike + RSI > 50 + MACD bullish
PUT: Price crosses below VWAP + volume spike + RSI < 50 + MACD bearish

Research Sources:
- VWAP trading strategies
- Volume-weighted momentum
- Intraday scalping systems
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False


class Strategy30sVWAPMomentum:
    """
    30-Second VWAP Momentum Strategy
    
    Uses VWAP as a dynamic benchmark:
    - Price above VWAP with volume = bullish
    - Price below VWAP with volume = bearish
    - Divergence from VWAP signals mean reversion
    """
    
    def __init__(self):
        self.name = "30s VWAP Momentum"
        self.timeframe = "30s"
        self.accuracy_target = 80.0
        
        # RSI settings
        self.rsi_period = 14
        
        # Volume spike threshold
        self.volume_spike_multiplier = 1.5
        
        self.min_confidence = 70
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate VWAP"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1, index=df.index)
        
        cumulative_tp_vol = (typical_price * volume).cumsum()
        cumulative_vol = volume.cumsum()
        
        vwap = cumulative_tp_vol / cumulative_vol
        return vwap
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        try:
            df = df.copy()
            
            # Normalize columns
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col not in df.columns:
                    if col.capitalize() in df.columns:
                        df[col] = df[col.capitalize()]
                    elif col == 'volume':
                        df['volume'] = 1  # Default volume
            
            close = df['close'].astype(float)
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            volume = df['volume'].astype(float) if 'volume' in df.columns else pd.Series(1, index=df.index)
            
            # VWAP
            df['vwap'] = self._calculate_vwap(df)
            
            # VWAP deviation (percentage)
            df['vwap_deviation'] = (close - df['vwap']) / df['vwap'] * 100
            
            # Volume analysis
            df['volume_sma'] = volume.rolling(20).mean()
            df['volume_spike'] = volume > (df['volume_sma'] * self.volume_spike_multiplier)
            
            if TALIB_AVAILABLE:
                # RSI
                df['rsi'] = talib.RSI(close, timeperiod=self.rsi_period)
                
                # MACD
                df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(close)
                
                # EMAs
                df['ema_8'] = talib.EMA(close, timeperiod=8)
                df['ema_21'] = talib.EMA(close, timeperiod=21)
                
                # Stochastic
                df['stoch_k'], df['stoch_d'] = talib.STOCH(
                    high, low, close,
                    fastk_period=5, slowk_period=3, slowd_period=3
                )
                
                # Bollinger Bands for volatility context
                df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                    close, timeperiod=20, nbdevup=2, nbdevdn=2
                )
                
                # Momentum
                df['mom'] = talib.MOM(close, timeperiod=10)
                
            else:
                # Fallback calculations
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
                
                # EMAs
                df['ema_8'] = close.ewm(span=8, adjust=False).mean()
                df['ema_21'] = close.ewm(span=21, adjust=False).mean()
                
                # Stochastic
                lowest_low = low.rolling(5).min()
                highest_high = high.rolling(5).max()
                df['stoch_k'] = 100 * (close - lowest_low) / (highest_high - lowest_low)
                df['stoch_d'] = df['stoch_k'].rolling(3).mean()
                
                # Bollinger Bands
                sma20 = close.rolling(20).mean()
                std20 = close.rolling(20).std()
                df['bb_upper'] = sma20 + (std20 * 2)
                df['bb_middle'] = sma20
                df['bb_lower'] = sma20 - (std20 * 2)
                
                # Momentum
                df['mom'] = close.diff(10)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
        """Generate trading signal"""
        if len(df) < 30:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'Insufficient data',
                'strategy': self.name,
                'timeframe': self.timeframe
            }
        
        df = self.calculate_indicators(df)
        
        if df.empty or 'vwap' not in df.columns:
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
        
        close = latest['close']
        vwap = latest['vwap']
        close_prev = prev['close']
        vwap_prev = prev['vwap']
        
        # ============================================
        # 1. VWAP CROSSOVER (25 points)
        # ============================================
        # Bullish: Price crosses above VWAP
        if close > vwap and close_prev <= vwap_prev:
            call_score += 25
            reasons.append("✅ Price crossed ABOVE VWAP")
        elif close > vwap:
            call_score += 15
            reasons.append("✅ Price above VWAP")
        
        # Bearish: Price crosses below VWAP
        if close < vwap and close_prev >= vwap_prev:
            put_score += 25
            reasons.append("✅ Price crossed BELOW VWAP")
        elif close < vwap:
            put_score += 15
            reasons.append("✅ Price below VWAP")
        
        # ============================================
        # 2. VOLUME CONFIRMATION (20 points)
        # ============================================
        volume_spike = latest.get('volume_spike', False)
        
        if volume_spike:
            if call_score > put_score:
                call_score += 20
                reasons.append("✅ Volume spike confirms bullish move")
            elif put_score > call_score:
                put_score += 20
                reasons.append("✅ Volume spike confirms bearish move")
        else:
            if call_score > put_score:
                call_score += 8
            elif put_score > call_score:
                put_score += 8
        
        # ============================================
        # 3. RSI MOMENTUM (20 points)
        # ============================================
        rsi = latest['rsi']
        rsi_prev = prev['rsi']
        
        if rsi > 50 and rsi > rsi_prev:
            call_score += 20
            reasons.append(f"✅ RSI bullish momentum ({rsi:.1f})")
        elif rsi < 50 and rsi < rsi_prev:
            put_score += 20
            reasons.append(f"✅ RSI bearish momentum ({rsi:.1f})")
        elif rsi < 30 and rsi > rsi_prev:
            call_score += 15
            reasons.append(f"✅ RSI oversold & turning ({rsi:.1f})")
        elif rsi > 70 and rsi < rsi_prev:
            put_score += 15
            reasons.append(f"✅ RSI overbought & turning ({rsi:.1f})")
        
        # ============================================
        # 4. MACD DIRECTION (15 points)
        # ============================================
        macd = latest['macd']
        macd_signal = latest['macd_signal']
        macd_hist = latest['macd_hist']
        macd_hist_prev = prev['macd_hist']
        
        if macd > macd_signal and macd_hist > macd_hist_prev:
            call_score += 15
            reasons.append("✅ MACD bullish")
        elif macd < macd_signal and macd_hist < macd_hist_prev:
            put_score += 15
            reasons.append("✅ MACD bearish")
        
        # ============================================
        # 5. EMA TREND (10 points)
        # ============================================
        ema_8 = latest['ema_8']
        ema_21 = latest['ema_21']
        
        if ema_8 > ema_21:
            call_score += 10
            reasons.append("✅ Bullish EMA trend")
        elif ema_8 < ema_21:
            put_score += 10
            reasons.append("✅ Bearish EMA trend")
        
        # ============================================
        # 6. VWAP DEVIATION EXTREME (10 points)
        # Mean reversion opportunity
        # ============================================
        vwap_dev = latest['vwap_deviation']
        
        if vwap_dev < -0.5:  # Price significantly below VWAP
            call_score += 10
            reasons.append(f"✅ Price below VWAP - reversion opportunity")
        elif vwap_dev > 0.5:  # Price significantly above VWAP
            put_score += 10
            reasons.append(f"✅ Price above VWAP - reversion opportunity")
        
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
            reasons.append(f"⚠️ Signal strength insufficient")
        
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
                'vwap': float(vwap) if not np.isnan(vwap) else close,
                'vwap_deviation': float(vwap_dev) if not np.isnan(vwap_dev) else 0,
                'rsi': float(rsi) if not np.isnan(rsi) else 50,
                'macd_hist': float(macd_hist) if not np.isnan(macd_hist) else 0,
                'volume_spike': bool(volume_spike)
            }
        }


strategy_30s_vwap_momentum = Strategy30sVWAPMomentum()


def generate_signal(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
    """Wrapper for strategy registry"""
    return strategy_30s_vwap_momentum.generate_signal(df, symbol)
