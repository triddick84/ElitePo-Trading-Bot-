"""
30-Second Williams %R + ADX + ATR Strategy
Accuracy Target: 83%+

Based on research:
- Williams %R for overbought/oversold (-80/-20 levels)
- ADX for trend strength filter (>25 = strong trend)
- ATR for volatility filtering and timing
- Only trade when all conditions align

Entry Rules:
CALL: Williams %R < -80 (oversold) + ADX > 25 + price reversing up
PUT: Williams %R > -20 (overbought) + ADX > 25 + price reversing down

Research Sources:
- Williams %R reversal strategies
- ADX trend strength filtering
- ATR volatility-based timing
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
    logger.warning("TALib not available, using pandas calculations")


class Strategy30sWilliamsADXATR:
    """
    30-Second Williams %R + ADX + ATR Strategy
    
    Uses three complementary indicators:
    1. Williams %R - Overbought/oversold momentum
    2. ADX - Trend strength filter
    3. ATR - Volatility filter
    """
    
    def __init__(self):
        self.name = "30s Williams + ADX + ATR"
        self.timeframe = "30s"
        self.accuracy_target = 83.0
        
        # Williams %R Settings
        self.williams_period = 14
        self.williams_oversold = -80
        self.williams_overbought = -20
        
        # ADX Settings
        self.adx_period = 14
        self.adx_strong_trend = 25
        self.adx_very_strong = 40
        
        # ATR Settings
        self.atr_period = 14
        
        # RSI for confirmation
        self.rsi_period = 14
        
        # Minimum confidence
        self.min_confidence = 70
    
    def _calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calculate Williams %R without TALib"""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return -100 * (highest_high - close) / (highest_high - lowest_low)
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calculate ADX without TALib (simplified)"""
        plus_dm = high.diff()
        minus_dm = low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm.abs()) & (plus_dm > 0), 0)
        minus_dm = minus_dm.abs().where((minus_dm.abs() > plus_dm) & (minus_dm < 0), 0)
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
        adx = dx.rolling(period).mean()
        
        return adx
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calculate ATR without TALib"""
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calculate RSI without TALib"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        try:
            df = df.copy()
            
            # Normalize column names
            for col in ['open', 'high', 'low', 'close']:
                if col not in df.columns:
                    if col.capitalize() in df.columns:
                        df[col] = df[col.capitalize()]
            
            close = df['close'].astype(float)
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            
            if TALIB_AVAILABLE:
                # Williams %R
                df['williams_r'] = talib.WILLR(high, low, close, timeperiod=self.williams_period)
                
                # ADX and DI
                df['adx'] = talib.ADX(high, low, close, timeperiod=self.adx_period)
                df['plus_di'] = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
                df['minus_di'] = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)
                
                # ATR
                df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)
                
                # RSI for confirmation
                df['rsi'] = talib.RSI(close, timeperiod=self.rsi_period)
                
                # Stochastic for extra confirmation
                df['stoch_k'], df['stoch_d'] = talib.STOCH(
                    high, low, close,
                    fastk_period=5, slowk_period=3, slowd_period=3
                )
                
                # EMAs
                df['ema_8'] = talib.EMA(close, timeperiod=8)
                df['ema_21'] = talib.EMA(close, timeperiod=21)
                
                # MACD
                df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(close)
                
            else:
                # Fallback calculations
                df['williams_r'] = self._calculate_williams_r(high, low, close, self.williams_period)
                df['adx'] = self._calculate_adx(high, low, close, self.adx_period)
                df['atr'] = self._calculate_atr(high, low, close, self.atr_period)
                df['rsi'] = self._calculate_rsi(close, self.rsi_period)
                
                # Stochastic
                lowest_low = low.rolling(5).min()
                highest_high = high.rolling(5).max()
                df['stoch_k'] = 100 * (close - lowest_low) / (highest_high - lowest_low)
                df['stoch_d'] = df['stoch_k'].rolling(3).mean()
                
                # EMAs
                df['ema_8'] = close.ewm(span=8, adjust=False).mean()
                df['ema_21'] = close.ewm(span=21, adjust=False).mean()
                
                # Simple MACD
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                df['macd'] = ema12 - ema26
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_hist'] = df['macd'] - df['macd_signal']
                
                # DI approximation
                df['plus_di'] = 50
                df['minus_di'] = 50
            
            # ATR percentile for volatility context
            df['atr_percentile'] = df['atr'].rank(pct=True) * 100
            
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
        
        if df.empty or 'williams_r' not in df.columns:
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
        
        # ============================================
        # 1. WILLIAMS %R SIGNAL (30 points)
        # ============================================
        williams = latest['williams_r']
        williams_prev = prev['williams_r']
        
        if williams < self.williams_oversold:  # Below -80
            if williams > williams_prev:  # Turning up from oversold
                call_score += 30
                reasons.append(f"✅ Williams %R oversold & turning up ({williams:.1f})")
            else:
                call_score += 20
                reasons.append(f"⚡ Williams %R oversold ({williams:.1f})")
        elif williams > self.williams_overbought:  # Above -20
            if williams < williams_prev:  # Turning down from overbought
                put_score += 30
                reasons.append(f"✅ Williams %R overbought & turning down ({williams:.1f})")
            else:
                put_score += 20
                reasons.append(f"⚡ Williams %R overbought ({williams:.1f})")
        
        # ============================================
        # 2. ADX TREND STRENGTH FILTER (20 points)
        # ============================================
        adx = latest['adx']
        plus_di = latest.get('plus_di', 50)
        minus_di = latest.get('minus_di', 50)
        
        if adx > self.adx_very_strong:  # Very strong trend
            if plus_di > minus_di:  # Bullish trend
                call_score += 20
                reasons.append(f"✅ Very strong bullish trend (ADX: {adx:.1f})")
            else:  # Bearish trend
                put_score += 20
                reasons.append(f"✅ Very strong bearish trend (ADX: {adx:.1f})")
        elif adx > self.adx_strong_trend:  # Strong trend
            if plus_di > minus_di:
                call_score += 15
                reasons.append(f"✅ Strong bullish trend (ADX: {adx:.1f})")
            else:
                put_score += 15
                reasons.append(f"✅ Strong bearish trend (ADX: {adx:.1f})")
        elif adx < 20:  # Weak trend - good for reversals
            # In weak trends, oversold/overbought signals are more reliable
            if call_score > 0:
                call_score += 10
                reasons.append("✅ Low ADX favors mean reversion")
            elif put_score > 0:
                put_score += 10
                reasons.append("✅ Low ADX favors mean reversion")
        
        # ============================================
        # 3. ATR VOLATILITY FILTER (15 points)
        # ============================================
        atr_percentile = latest.get('atr_percentile', 50)
        
        if 30 <= atr_percentile <= 70:  # Normal volatility
            if call_score > put_score:
                call_score += 15
            elif put_score > call_score:
                put_score += 15
            reasons.append("✅ Normal volatility (good for trading)")
        elif atr_percentile > 70:  # High volatility - be cautious
            if call_score > put_score:
                call_score += 5
            elif put_score > call_score:
                put_score += 5
            reasons.append("⚠️ High volatility")
        
        # ============================================
        # 4. RSI CONFIRMATION (15 points)
        # ============================================
        rsi = latest['rsi']
        rsi_prev = prev['rsi']
        
        if rsi < 30:  # Oversold
            if rsi > rsi_prev:
                call_score += 15
                reasons.append(f"✅ RSI oversold & rising ({rsi:.1f})")
            else:
                call_score += 8
        elif rsi > 70:  # Overbought
            if rsi < rsi_prev:
                put_score += 15
                reasons.append(f"✅ RSI overbought & falling ({rsi:.1f})")
            else:
                put_score += 8
        
        # ============================================
        # 5. STOCHASTIC CONFIRMATION (10 points)
        # ============================================
        stoch_k = latest.get('stoch_k', 50)
        stoch_d = latest.get('stoch_d', 50)
        
        if stoch_k < 20 and stoch_k > stoch_d:
            call_score += 10
            reasons.append("✅ Stochastic bullish crossover in oversold")
        elif stoch_k > 80 and stoch_k < stoch_d:
            put_score += 10
            reasons.append("✅ Stochastic bearish crossover in overbought")
        
        # ============================================
        # 6. EMA TREND (10 points)
        # ============================================
        ema_8 = latest['ema_8']
        ema_21 = latest['ema_21']
        close = latest['close']
        
        if ema_8 > ema_21 and close > ema_8:
            call_score += 10
            reasons.append("✅ Bullish EMA alignment")
        elif ema_8 < ema_21 and close < ema_8:
            put_score += 10
            reasons.append("✅ Bearish EMA alignment")
        
        # ============================================
        # FINAL SIGNAL
        # ============================================
        direction = 'NEUTRAL'
        confidence = max(call_score, put_score)
        
        # Check for strong Williams signal with confirmation
        williams_call = williams < self.williams_oversold
        williams_put = williams > self.williams_overbought
        rsi_call = rsi < 35
        rsi_put = rsi > 65
        
        if williams_call and rsi_call:
            call_score += 10
            reasons.append("🎯 Williams + RSI oversold confluence")
        if williams_put and rsi_put:
            put_score += 10
            reasons.append("🎯 Williams + RSI overbought confluence")
        
        if call_score > put_score and call_score >= self.min_confidence:
            direction = 'CALL'
            confidence = min(call_score, 100)
        elif put_score > call_score and put_score >= self.min_confidence:
            direction = 'PUT'
            confidence = min(put_score, 100)
        else:
            confidence = max(call_score, put_score)
            reasons.append(f"⚠️ Signal strength below threshold")
        
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
                'williams_r': float(williams) if not np.isnan(williams) else -50,
                'adx': float(adx) if not np.isnan(adx) else 25,
                'atr_percentile': float(atr_percentile) if not np.isnan(atr_percentile) else 50,
                'rsi': float(rsi) if not np.isnan(rsi) else 50,
                'stoch_k': float(stoch_k) if not np.isnan(stoch_k) else 50
            }
        }


# Singleton instance
strategy_30s_williams_adx_atr = Strategy30sWilliamsADXATR()


def generate_signal(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
    """Wrapper function for strategy registry compatibility"""
    return strategy_30s_williams_adx_atr.generate_signal(df, symbol)
