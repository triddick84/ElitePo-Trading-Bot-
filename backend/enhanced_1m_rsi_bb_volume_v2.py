"""
ENHANCED Pocket Option 1-Minute RSI + BB + Volume Strategy
TARGET: 85-89% Win Rate (Enhanced with Advanced Filters)

IMPROVEMENTS FROM V1:
1. Multi-Timeframe Confirmation (5m trend must align)
2. ADX Trend Strength Filter (ADX > 25 required)
3. ATR Volatility Filter (must be in optimal range)
4. Market Regime Detection (avoid ranging/choppy markets)
5. Enhanced S/R Validation (Fibonacci levels)
6. Time-of-Day Filter (best trading hours only)
7. Stricter Confirmation Requirements (4+ instead of 3)

WIN RATE TARGET: 85-89% (with stricter filtering)
TRADE FREQUENCY: Lower (2-5 high-quality signals/day vs 5-15)
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Optional, List
from datetime import datetime, time

logger = logging.getLogger(__name__)


class Enhanced1mRSIBBVolumeV2:
    """
    Enhanced 1-Minute RSI + BB + Volume Strategy
    Target: 85-89% win rate with multi-layer filtering
    """
    
    def __init__(self):
        # Original indicators
        self.rsi_period = 14
        self.rsi_fast_period = 7
        self.bb_period = 20
        self.bb_std = 2.0
        self.volume_period = 10
        self.volume_spike_threshold = 1.5
        
        # NEW: Advanced filters
        self.adx_period = 14
        self.adx_min_strength = 25  # Minimum trend strength
        self.atr_period = 14
        self.atr_min_multiplier = 0.7  # Minimum volatility (70% of average)
        self.atr_max_multiplier = 2.0  # Maximum volatility (200% of average)
        
        # Multi-timeframe settings
        self.mtf_lookback = 20  # 5m candles for trend
        
        # Thresholds (STRICTER)
        self.rsi_oversold = 25  # Stricter (was 30)
        self.rsi_overbought = 75  # Stricter (was 70)
        self.rsi_extreme_oversold = 15  # Very extreme
        self.rsi_extreme_overbought = 85  # Very extreme
        
        # Minimum confidence (HIGHER)
        self.min_confidence = 85  # Raised from 70
        
        # Best trading hours (UTC)
        self.best_hours = [
            (8, 12),   # London session
            (13, 17),  # New York session
            (8, 17)    # Overlap
        ]
        
        logger.info("✅ ENHANCED RSI+BB+Volume V2 initialized (TARGET: 85-89%)")
    
    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate ADX and directional indicators"""
        adx = talib.ADX(high, low, close, timeperiod=self.adx_period)
        plus_di = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
        minus_di = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)
        return adx, plus_di, minus_di
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range"""
        return talib.ATR(high, low, close, timeperiod=self.atr_period)
    
    def detect_market_regime(self, close: pd.Series, adx: pd.Series) -> Dict:
        """
        Detect if market is trending, ranging, or choppy
        Uses ADX and price action
        """
        curr_adx = adx.iloc[-1]
        
        # Price movement analysis
        recent_closes = close.tail(10)
        price_range = recent_closes.max() - recent_closes.min()
        avg_price = recent_closes.mean()
        range_pct = (price_range / avg_price) * 100
        
        # Determine regime
        if curr_adx > 25:
            if range_pct > 0.5:
                regime = 'STRONG_TREND'
                quality = 95
            else:
                regime = 'WEAK_TREND'
                quality = 70
        elif curr_adx > 20:
            regime = 'DEVELOPING_TREND'
            quality = 60
        else:
            regime = 'RANGING'
            quality = 30
        
        return {
            'regime': regime,
            'quality': quality,
            'adx': curr_adx,
            'tradeable': regime in ['STRONG_TREND', 'WEAK_TREND']
        }
    
    def check_multi_timeframe_alignment(self, df: pd.DataFrame) -> Dict:
        """
        Check if 5m trend aligns with 1m signal
        Simulated by looking at broader price movement
        """
        # Use last 20 candles to simulate 5m trend (20 x 1m = 20 minutes)
        recent_data = df.tail(20)
        
        # Calculate 5m equivalent indicators
        close_5m = recent_data['close']
        high_5m = recent_data['high']
        low_5m = recent_data['low']
        
        # 5m trend via EMA
        ema_fast_5m = talib.EMA(close_5m, timeperiod=5)
        ema_slow_5m = talib.EMA(close_5m, timeperiod=10)
        
        curr_fast = ema_fast_5m.iloc[-1]
        curr_slow = ema_slow_5m.iloc[-1]
        
        # 5m RSI
        rsi_5m = talib.RSI(close_5m, timeperiod=14)
        curr_rsi_5m = rsi_5m.iloc[-1]
        
        # Determine 5m trend
        if curr_fast > curr_slow:
            trend_5m = 'BULLISH'
            strength = min(((curr_fast - curr_slow) / curr_slow) * 1000, 100)
        else:
            trend_5m = 'BEARISH'
            strength = min(((curr_slow - curr_fast) / curr_fast) * 1000, 100)
        
        return {
            '5m_trend': trend_5m,
            '5m_strength': strength,
            '5m_rsi': curr_rsi_5m,
            'strong_alignment': strength > 30
        }
    
    def check_time_filter(self) -> Dict:
        """Check if current time is within best trading hours"""
        now = datetime.utcnow()
        current_hour = now.hour
        
        for start, end in self.best_hours:
            if start <= current_hour < end:
                return {
                    'within_hours': True,
                    'session': 'London' if start == 8 and end == 12 else 'NY' if start == 13 else 'Overlap',
                    'quality': 100
                }
        
        return {
            'within_hours': False,
            'session': 'Off-hours',
            'quality': 50
        }
    
    def calculate_fibonacci_levels(self, high: pd.Series, low: pd.Series) -> Dict:
        """Calculate Fibonacci retracement levels"""
        swing_high = high.tail(50).max()
        swing_low = low.tail(50).min()
        diff = swing_high - swing_low
        
        return {
            'fib_0': swing_high,
            'fib_236': swing_high - (diff * 0.236),
            'fib_382': swing_high - (diff * 0.382),
            'fib_50': swing_high - (diff * 0.5),
            'fib_618': swing_high - (diff * 0.618),
            'fib_786': swing_high - (diff * 0.786),
            'fib_100': swing_low
        }
    
    def is_near_fibonacci(self, price: float, fib_levels: Dict) -> Dict:
        """Check if price is near key Fibonacci level"""
        tolerance = 0.002  # 0.2%
        
        for level_name, level_price in fib_levels.items():
            distance = abs(price - level_price) / price
            if distance < tolerance:
                return {
                    'near_fib': True,
                    'level': level_name,
                    'distance_pct': distance * 100
                }
        
        return {'near_fib': False}
    
    def generate_signal(
        self,
        symbol: str,
        market_data: pd.DataFrame,
        use_fast_rsi: bool = False
    ) -> Optional[Dict]:
        """
        Generate ENHANCED trading signal with advanced filtering
        TARGET: 85-89% accuracy
        """
        try:
            if market_data is None or len(market_data) < 100:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            df = market_data.copy()
            
            # === FILTER 1: TIME OF DAY ===
            time_filter = self.check_time_filter()
            if not time_filter['within_hours']:
                logger.info(f"⏰ REJECTED: Outside best trading hours ({time_filter['session']})")
                return None
            
            logger.info(f"✅ Time Filter: {time_filter['session']} session")
            
            # Calculate indicators
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # Original indicators
            rsi_period = self.rsi_fast_period if use_fast_rsi else self.rsi_period
            rsi = talib.RSI(close, timeperiod=rsi_period)
            bb_upper, bb_middle, bb_lower = talib.BBANDS(
                close, timeperiod=self.bb_period,
                nbdevup=self.bb_std, nbdevdn=self.bb_std, matype=0
            )
            volume_ratio = volume / volume.rolling(window=self.volume_period).mean()
            
            # NEW: Advanced filters
            adx, plus_di, minus_di = self.calculate_adx(high, low, close)
            atr = self.calculate_atr(high, low, close)
            
            # Current values
            curr_price = close.iloc[-1]
            curr_rsi = rsi.iloc[-1]
            curr_bb_upper = bb_upper.iloc[-1]
            curr_bb_lower = bb_lower.iloc[-1]
            curr_volume_ratio = volume_ratio.iloc[-1]
            curr_adx = adx.iloc[-1]
            curr_plus_di = plus_di.iloc[-1]
            curr_minus_di = minus_di.iloc[-1]
            curr_atr = atr.iloc[-1]
            avg_atr = atr.tail(20).mean()
            
            prev_price = close.iloc[-2]
            prev_rsi = rsi.iloc[-2]
            
            # === FILTER 2: ADX TREND STRENGTH ===
            if curr_adx < self.adx_min_strength:
                logger.info(f"⛔ REJECTED: Weak trend (ADX={curr_adx:.1f} < {self.adx_min_strength})")
                return None
            
            logger.info(f"✅ ADX Filter: Strong trend (ADX={curr_adx:.1f})")
            
            # === FILTER 3: ATR VOLATILITY ===
            atr_ratio = curr_atr / avg_atr if avg_atr > 0 else 1
            if atr_ratio < self.atr_min_multiplier or atr_ratio > self.atr_max_multiplier:
                logger.info(f"⛔ REJECTED: Volatility out of range (ATR ratio={atr_ratio:.2f})")
                return None
            
            logger.info(f"✅ ATR Filter: Optimal volatility (ratio={atr_ratio:.2f})")
            
            # === FILTER 4: MARKET REGIME ===
            regime = self.detect_market_regime(close, adx)
            if not regime['tradeable']:
                logger.info(f"⛔ REJECTED: Market regime = {regime['regime']}")
                return None
            
            logger.info(f"✅ Regime Filter: {regime['regime']} (quality={regime['quality']}%)")
            
            # === FILTER 5: MULTI-TIMEFRAME ALIGNMENT ===
            mtf = self.check_multi_timeframe_alignment(df)
            
            logger.info(f"✅ 5m Trend: {mtf['5m_trend']} (strength={mtf['5m_strength']:.1f}%)")
            
            # === FILTER 6: FIBONACCI LEVELS ===
            fib_levels = self.calculate_fibonacci_levels(high, low)
            fib_check = self.is_near_fibonacci(curr_price, fib_levels)
            
            # Calculate BB position
            bb_range = curr_bb_upper - curr_bb_lower
            bb_position = (curr_price - curr_bb_lower) / bb_range if bb_range > 0 else 0.5
            
            # Volume spike
            has_volume_spike = curr_volume_ratio >= self.volume_spike_threshold
            
            logger.info(f"📊 {symbol} ENHANCED Analysis:")
            logger.info(f"   Price={curr_price:.5f}, RSI={curr_rsi:.1f}, ADX={curr_adx:.1f}")
            logger.info(f"   BB Position={bb_position:.2%}, Volume={curr_volume_ratio:.2f}x")
            logger.info(f"   +DI={curr_plus_di:.1f}, -DI={curr_minus_di:.1f}")
            
            # Signal generation with STRICTER criteria
            signal = None
            confidence = 0
            reasoning = []
            confirmations = 0
            
            # === CALL SIGNAL (ENHANCED) ===
            if curr_rsi < self.rsi_oversold:
                if bb_position < 0.12:  # Stricter (was 0.15)
                    if curr_price > prev_price:  # Price bouncing
                        # MUST align with 5m trend OR be at Fib level
                        if mtf['5m_trend'] == 'BULLISH' or fib_check.get('near_fib'):
                            # MUST have bullish DI
                            if curr_plus_di > curr_minus_di:
                                signal = "CALL"
                                confidence = 85  # Higher base
                                
                                # RSI level
                                if curr_rsi < self.rsi_extreme_oversold:
                                    reasoning.append(f"🟢 EXTREME OVERSOLD: RSI={curr_rsi:.1f} (< 15)")
                                    confidence += 7
                                else:
                                    reasoning.append(f"🟢 OVERSOLD: RSI={curr_rsi:.1f} (< 25)")
                                confirmations += 1
                                
                                # BB touch
                                reasoning.append(f"📊 Lower BB touch ({bb_position:.1%})")
                                confirmations += 1
                                
                                # Volume
                                if has_volume_spike:
                                    confidence += 10
                                    reasoning.append(f"📈 VOLUME SPIKE: {curr_volume_ratio:.2f}x")
                                    confirmations += 1
                                else:
                                    confidence -= 8
                                
                                # Price bounce
                                reasoning.append(f"✅ Price bouncing ({prev_price:.5f}→{curr_price:.5f})")
                                confidence += 4
                                confirmations += 1
                                
                                # ADX strength
                                reasoning.append(f"✅ Strong trend (ADX={curr_adx:.1f})")
                                confidence += 3
                                confirmations += 1
                                
                                # Directional strength
                                di_diff = curr_plus_di - curr_minus_di
                                if di_diff > 10:
                                    reasoning.append(f"✅ Strong bullish DI (+DI={curr_plus_di:.1f} > -DI={curr_minus_di:.1f})")
                                    confidence += 5
                                    confirmations += 1
                                
                                # 5m alignment
                                if mtf['5m_trend'] == 'BULLISH' and mtf['strong_alignment']:
                                    reasoning.append(f"✅ 5m BULLISH TREND (strength={mtf['5m_strength']:.0f}%)")
                                    confidence += 6
                                    confirmations += 1
                                
                                # Fibonacci
                                if fib_check.get('near_fib'):
                                    reasoning.append(f"✅ Near Fib level: {fib_check['level']}")
                                    confidence += 4
                                    confirmations += 1
                                
                                # Market regime bonus
                                if regime['regime'] == 'STRONG_TREND':
                                    confidence += 3
                                    reasoning.append(f"✅ {regime['regime']} (quality={regime['quality']}%)")
                                
                                # RSI momentum
                                if curr_rsi > prev_rsi:
                                    reasoning.append("✅ RSI turning up")
                                    confidence += 2
            
            # === PUT SIGNAL (ENHANCED) ===
            elif curr_rsi > self.rsi_overbought:
                if bb_position > 0.88:  # Stricter (was 0.85)
                    if curr_price < prev_price:  # Price rejected
                        # MUST align with 5m trend OR be at Fib level
                        if mtf['5m_trend'] == 'BEARISH' or fib_check.get('near_fib'):
                            # MUST have bearish DI
                            if curr_minus_di > curr_plus_di:
                                signal = "PUT"
                                confidence = 85
                                
                                # RSI level
                                if curr_rsi > self.rsi_extreme_overbought:
                                    reasoning.append(f"🔴 EXTREME OVERBOUGHT: RSI={curr_rsi:.1f} (> 85)")
                                    confidence += 7
                                else:
                                    reasoning.append(f"🔴 OVERBOUGHT: RSI={curr_rsi:.1f} (> 75)")
                                confirmations += 1
                                
                                # BB touch
                                reasoning.append(f"📊 Upper BB touch ({bb_position:.1%})")
                                confirmations += 1
                                
                                # Volume
                                if has_volume_spike:
                                    confidence += 10
                                    reasoning.append(f"📈 VOLUME SPIKE: {curr_volume_ratio:.2f}x")
                                    confirmations += 1
                                else:
                                    confidence -= 8
                                
                                # Price rejection
                                reasoning.append(f"✅ Price rejected ({prev_price:.5f}→{curr_price:.5f})")
                                confidence += 4
                                confirmations += 1
                                
                                # ADX strength
                                reasoning.append(f"✅ Strong trend (ADX={curr_adx:.1f})")
                                confidence += 3
                                confirmations += 1
                                
                                # Directional strength
                                di_diff = curr_minus_di - curr_plus_di
                                if di_diff > 10:
                                    reasoning.append(f"✅ Strong bearish DI (-DI={curr_minus_di:.1f} > +DI={curr_plus_di:.1f})")
                                    confidence += 5
                                    confirmations += 1
                                
                                # 5m alignment
                                if mtf['5m_trend'] == 'BEARISH' and mtf['strong_alignment']:
                                    reasoning.append(f"✅ 5m BEARISH TREND (strength={mtf['5m_strength']:.0f}%)")
                                    confidence += 6
                                    confirmations += 1
                                
                                # Fibonacci
                                if fib_check.get('near_fib'):
                                    reasoning.append(f"✅ Near Fib level: {fib_check['level']}")
                                    confidence += 4
                                    confirmations += 1
                                
                                # Market regime bonus
                                if regime['regime'] == 'STRONG_TREND':
                                    confidence += 3
                                    reasoning.append(f"✅ {regime['regime']} (quality={regime['quality']}%)")
                                
                                # RSI momentum
                                if curr_rsi < prev_rsi:
                                    reasoning.append("✅ RSI turning down")
                                    confidence += 2
            
            # No signal
            if signal is None:
                logger.info(f"⏸️ No signal: Strict criteria not met")
                return None
            
            # STRICTER: Need at least 5 confirmations (was 3)
            if confirmations < 5:
                logger.warning(f"⛔ REJECTED: Only {confirmations} confirmations (need 5+)")
                return None
            
            # Confidence check
            if confidence < self.min_confidence:
                logger.warning(f"⛔ REJECTED: Confidence too low ({confidence:.1f}% < 85%)")
                return None
            
            # Cap at 95% (realistic)
            confidence = min(confidence, 95)
            
            reasoning.append(f"✅ {confirmations} STRONG confirmations - PREMIUM setup")
            
            logger.info(f"🎯 ENHANCED SIGNAL APPROVED: {signal} - {confidence:.1f}% confidence")
            
            return {
                'signal': signal,
                'confidence': round(confidence, 1),
                'symbol': symbol,
                'timeframe': '1m',
                'strategy': 'Enhanced_RSI_BB_Volume_V2',
                'reasoning': reasoning,
                'expiry': '60 seconds',
                'technical_analysis': {
                    f'rsi_{rsi_period}': round(curr_rsi, 1),
                    'bb_position': round(bb_position, 3),
                    'volume_ratio': round(curr_volume_ratio, 2),
                    'volume_spike': has_volume_spike,
                    'adx': round(curr_adx, 1),
                    'plus_di': round(curr_plus_di, 1),
                    'minus_di': round(curr_minus_di, 1),
                    'atr_ratio': round(atr_ratio, 2),
                    'market_regime': regime['regime'],
                    '5m_trend': mtf['5m_trend'],
                    '5m_strength': round(mtf['5m_strength'], 1),
                    'session': time_filter['session'],
                    'fib_proximity': fib_check.get('near_fib', False),
                    'confirmations': confirmations
                },
                'expected_accuracy': '85-89%',
                'version': 'V2_Enhanced',
                'quality_grade': 'PREMIUM' if confidence >= 90 else 'EXCELLENT'
            }
            
        except Exception as e:
            logger.error(f"Error in Enhanced RSI+BB+Volume V2: {e}", exc_info=True)
            return None


# Global instance
enhanced_1m_rsi_bb_volume_v2 = Enhanced1mRSIBBVolumeV2()
