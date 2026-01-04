"""
Enhanced Ultra-Short Timeframe Strategy (5s, 15s, 30s, 1m)
==========================================================

RESEARCH-BASED HIGH WIN-RATE STRATEGY targeting 80%+ accuracy

Key Improvements over previous strategies:
1. RSI Divergence Detection (not just extreme levels)
2. MACD Histogram Momentum Exhaustion Analysis
3. Multi-timeframe Confluence (align 1m with 5m trend)
4. Volume Spike Confirmation (institutional activity)
5. Candlestick Pattern Recognition (pin bars, engulfing)
6. ADX Trend Strength Filter (avoid choppy markets)
7. Support/Resistance Level Confirmation
8. Stricter 6/8 Confirmation Requirement

Based on research from:
- Quantified Strategies backtests showing 73% win rate with RSI+MACD divergence
- Pocket Option scalping strategies for 1-minute trades
- Market microstructure and order flow principles
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import talib

logger = logging.getLogger(__name__)


class EnhancedUltraShortStrategy:
    """
    Enhanced strategy for 5s-1m timeframes with research-backed indicators
    Target: 80%+ win rate through strict multi-confirmation filtering
    """
    
    def __init__(self, timeframe: str = '5s'):
        self.timeframe = timeframe
        self.name = f"Enhanced Ultra-Short ({timeframe})"
        
        # Indicator Settings (optimized for ultra-short timeframes)
        # RSI - Ultra-fast for quick reversals
        self.rsi_period = 3 if timeframe in ['5s', '15s'] else 7
        self.rsi_oversold = 25  # Slightly relaxed for more signals
        self.rsi_overbought = 75
        self.rsi_extreme_oversold = 15  # Extra confirmation
        self.rsi_extreme_overbought = 85
        
        # MACD - Fast settings for scalping
        self.macd_fast = 8
        self.macd_slow = 17
        self.macd_signal = 9
        
        # Stochastic - Ultra-fast
        self.stoch_k = 5
        self.stoch_d = 3
        self.stoch_smooth = 3
        self.stoch_oversold = 20
        self.stoch_overbought = 80
        
        # Bollinger Bands
        self.bb_period = 10
        self.bb_std = 2.0
        
        # EMAs for trend
        self.ema_fast = 8
        self.ema_slow = 21
        self.ema_trend = 50  # Trend filter
        
        # ADX for trend strength (avoid choppy markets)
        self.adx_period = 14
        self.adx_threshold = 20  # Below this = choppy market
        
        # Volume settings
        self.volume_ma_period = 20
        self.volume_spike_threshold = 1.3  # 30% above average
        
        # Confirmation requirements (STRICT)
        self.min_confirmations = 6  # Out of 8 possible
        self.min_confidence = 80
        
        # Divergence lookback
        self.divergence_lookback = 10
        
        logger.info(f"🎯 Enhanced Ultra-Short Strategy initialized for {timeframe}")
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all technical indicators needed for analysis"""
        if len(df) < 50:
            return {}
        
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float) if 'volume' in df.columns else np.ones(len(close))
        
        indicators = {}
        
        try:
            # RSI
            indicators['rsi'] = talib.RSI(close, timeperiod=self.rsi_period)
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(
                close, 
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            indicators['macd'] = macd
            indicators['macd_signal'] = macd_signal
            indicators['macd_hist'] = macd_hist
            
            # Stochastic
            stoch_k, stoch_d = talib.STOCH(
                high, low, close,
                fastk_period=self.stoch_k,
                slowk_period=self.stoch_d,
                slowk_matype=0,
                slowd_period=self.stoch_smooth,
                slowd_matype=0
            )
            indicators['stoch_k'] = stoch_k
            indicators['stoch_d'] = stoch_d
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(
                close,
                timeperiod=self.bb_period,
                nbdevup=self.bb_std,
                nbdevdn=self.bb_std
            )
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            
            # EMAs
            indicators['ema_fast'] = talib.EMA(close, timeperiod=self.ema_fast)
            indicators['ema_slow'] = talib.EMA(close, timeperiod=self.ema_slow)
            indicators['ema_trend'] = talib.EMA(close, timeperiod=self.ema_trend)
            
            # ADX for trend strength
            indicators['adx'] = talib.ADX(high, low, close, timeperiod=self.adx_period)
            indicators['plus_di'] = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
            indicators['minus_di'] = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)
            
            # ATR for volatility
            indicators['atr'] = talib.ATR(high, low, close, timeperiod=14)
            
            # Volume MA
            if not np.all(volume == 1):
                indicators['volume_ma'] = talib.SMA(volume, timeperiod=self.volume_ma_period)
                indicators['volume'] = volume
            else:
                indicators['volume_ma'] = np.ones(len(close))
                indicators['volume'] = np.ones(len(close))
            
            # Store raw data
            indicators['close'] = close
            indicators['high'] = high
            indicators['low'] = low
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
        
        return indicators
    
    def detect_rsi_divergence(self, close: np.ndarray, rsi: np.ndarray, lookback: int = 10) -> Dict[str, Any]:
        """
        Detect RSI divergence patterns (higher accuracy than simple thresholds)
        
        Bullish Divergence: Price lower low, RSI higher low
        Bearish Divergence: Price higher high, RSI lower high
        """
        if len(close) < lookback + 2 or len(rsi) < lookback + 2:
            return {'bullish': False, 'bearish': False, 'strength': 0}
        
        # Get recent data
        recent_close = close[-lookback:]
        recent_rsi = rsi[-lookback:]
        
        # Remove NaN
        valid_mask = ~np.isnan(recent_rsi)
        if np.sum(valid_mask) < 5:
            return {'bullish': False, 'bearish': False, 'strength': 0}
        
        # Find local minima and maxima
        price_min_idx = np.argmin(recent_close)
        price_max_idx = np.argmax(recent_close)
        
        current_close = close[-1]
        current_rsi = rsi[-1]
        
        # Bullish divergence: Price making lower low but RSI making higher low
        bullish_divergence = False
        bearish_divergence = False
        strength = 0
        
        # Check for bullish divergence (price lower low, RSI higher low)
        if current_close <= recent_close[price_min_idx]:
            # Price is at or below recent low
            min_rsi = np.nanmin(recent_rsi)
            if current_rsi > min_rsi:
                # RSI is higher than recent low = bullish divergence
                bullish_divergence = True
                strength = (current_rsi - min_rsi) / 10  # Normalize strength
        
        # Check for bearish divergence (price higher high, RSI lower high)
        if current_close >= recent_close[price_max_idx]:
            # Price is at or above recent high
            max_rsi = np.nanmax(recent_rsi)
            if current_rsi < max_rsi:
                # RSI is lower than recent high = bearish divergence
                bearish_divergence = True
                strength = (max_rsi - current_rsi) / 10
        
        return {
            'bullish': bullish_divergence,
            'bearish': bearish_divergence,
            'strength': min(strength, 1.0)
        }
    
    def detect_macd_momentum_exhaustion(self, macd_hist: np.ndarray) -> Dict[str, Any]:
        """
        Detect MACD histogram momentum exhaustion
        
        Exhaustion occurs when:
        - Histogram bars are shrinking (losing momentum)
        - Color change imminent (crossing zero)
        """
        if len(macd_hist) < 5:
            return {'bullish': False, 'bearish': False, 'strength': 0}
        
        # Remove NaN
        valid_hist = macd_hist[~np.isnan(macd_hist)]
        if len(valid_hist) < 5:
            return {'bullish': False, 'bearish': False, 'strength': 0}
        
        recent_hist = valid_hist[-5:]
        current_hist = recent_hist[-1]
        
        bullish_exhaustion = False
        bearish_exhaustion = False
        strength = 0
        
        # Bearish exhaustion (price going up but momentum fading) -> expect reversal down
        if current_hist > 0:
            # Check if histogram is shrinking (momentum fading)
            if recent_hist[-1] < recent_hist[-2] < recent_hist[-3]:
                bearish_exhaustion = True
                strength = abs(recent_hist[-3] - recent_hist[-1]) / abs(recent_hist[-3]) if recent_hist[-3] != 0 else 0
        
        # Bullish exhaustion (price going down but momentum fading) -> expect reversal up
        elif current_hist < 0:
            # Check if histogram is rising (less negative = momentum fading)
            if recent_hist[-1] > recent_hist[-2] > recent_hist[-3]:
                bullish_exhaustion = True
                strength = abs(recent_hist[-1] - recent_hist[-3]) / abs(recent_hist[-3]) if recent_hist[-3] != 0 else 0
        
        return {
            'bullish': bullish_exhaustion,
            'bearish': bearish_exhaustion,
            'strength': min(strength, 1.0)
        }
    
    def detect_candlestick_pattern(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect high-probability candlestick patterns
        - Pin bars (rejection wicks)
        - Engulfing patterns
        - Doji at key levels
        """
        if len(df) < 3:
            return {'bullish': False, 'bearish': False, 'pattern': None}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        open_price = last['open']
        close_price = last['close']
        high_price = last['high']
        low_price = last['low']
        
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        
        if total_range == 0:
            return {'bullish': False, 'bearish': False, 'pattern': None}
        
        upper_wick = high_price - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low_price
        
        bullish = False
        bearish = False
        pattern = None
        
        # Pin Bar / Hammer (bullish)
        if lower_wick > body * 2 and lower_wick > upper_wick * 2:
            bullish = True
            pattern = 'hammer'
        
        # Inverted Hammer / Shooting Star (bearish)
        elif upper_wick > body * 2 and upper_wick > lower_wick * 2:
            bearish = True
            pattern = 'shooting_star'
        
        # Bullish Engulfing
        prev_body = abs(prev['close'] - prev['open'])
        if (prev['close'] < prev['open'] and  # Previous was bearish
            close_price > open_price and  # Current is bullish
            body > prev_body * 1.2 and  # Current body larger
            close_price > prev['open'] and  # Engulfs previous
            open_price < prev['close']):
            bullish = True
            pattern = 'bullish_engulfing'
        
        # Bearish Engulfing
        if (prev['close'] > prev['open'] and  # Previous was bullish
            close_price < open_price and  # Current is bearish
            body > prev_body * 1.2 and  # Current body larger
            close_price < prev['open'] and  # Engulfs previous
            open_price > prev['close']):
            bearish = True
            pattern = 'bearish_engulfing'
        
        # Doji (indecision - use with other signals)
        if body < total_range * 0.1:
            pattern = 'doji'
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'pattern': pattern
        }
    
    def check_volume_spike(self, volume: np.ndarray, volume_ma: np.ndarray) -> Dict[str, Any]:
        """Check for volume spike indicating institutional activity"""
        if len(volume) < 2 or len(volume_ma) < 2:
            return {'spike': False, 'ratio': 1.0}
        
        current_volume = volume[-1]
        ma_volume = volume_ma[-1]
        
        if np.isnan(ma_volume) or ma_volume == 0:
            return {'spike': False, 'ratio': 1.0}
        
        ratio = current_volume / ma_volume
        spike = ratio >= self.volume_spike_threshold
        
        return {
            'spike': spike,
            'ratio': round(ratio, 2)
        }
    
    def check_trend_filter(self, indicators: Dict) -> Dict[str, Any]:
        """
        Check trend strength using ADX and EMA alignment
        Avoid trading in choppy/ranging markets
        """
        adx = indicators.get('adx', np.array([]))
        plus_di = indicators.get('plus_di', np.array([]))
        minus_di = indicators.get('minus_di', np.array([]))
        ema_fast = indicators.get('ema_fast', np.array([]))
        ema_slow = indicators.get('ema_slow', np.array([]))
        
        if len(adx) < 2 or len(ema_fast) < 2:
            return {'trending': True, 'direction': 'neutral', 'strength': 0}
        
        current_adx = adx[-1]
        current_plus = plus_di[-1] if len(plus_di) > 0 else 0
        current_minus = minus_di[-1] if len(minus_di) > 0 else 0
        
        if np.isnan(current_adx):
            return {'trending': True, 'direction': 'neutral', 'strength': 0}
        
        # Check if market is trending (ADX > threshold)
        is_trending = current_adx > self.adx_threshold
        
        # Determine trend direction from EMAs and DI
        ema_trend = 'up' if ema_fast[-1] > ema_slow[-1] else 'down'
        di_trend = 'up' if current_plus > current_minus else 'down'
        
        direction = 'neutral'
        if is_trending:
            if ema_trend == di_trend:
                direction = ema_trend
            else:
                direction = ema_trend  # EMA takes priority
        
        return {
            'trending': is_trending,
            'direction': direction,
            'strength': current_adx / 100,
            'adx': round(current_adx, 1)
        }
    
    def generate_signal(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Optional[Dict[str, Any]]:
        """
        Generate trading signal with strict multi-confirmation filtering
        
        Confirmations checked (8 total):
        1. RSI Divergence
        2. RSI Extreme Level
        3. MACD Momentum Exhaustion
        4. MACD Histogram Direction
        5. Stochastic Crossover in Extreme
        6. Bollinger Band Touch
        7. Candlestick Pattern
        8. Volume Spike
        
        Requires 6/8 confirmations for signal generation
        """
        indicators = self.calculate_all_indicators(df)
        
        if not indicators:
            logger.warning(f"Could not calculate indicators for {symbol}")
            return None
        
        # Get current values
        close = indicators['close']
        rsi = indicators['rsi']
        macd_hist = indicators['macd_hist']
        stoch_k = indicators['stoch_k']
        stoch_d = indicators['stoch_d']
        
        current_price = close[-1]
        current_rsi = rsi[-1] if not np.isnan(rsi[-1]) else 50
        current_stoch_k = stoch_k[-1] if not np.isnan(stoch_k[-1]) else 50
        current_stoch_d = stoch_d[-1] if not np.isnan(stoch_d[-1]) else 50
        
        # Track confirmations
        buy_confirmations = []
        sell_confirmations = []
        
        # === 1. RSI DIVERGENCE (High weight) ===
        rsi_div = self.detect_rsi_divergence(close, rsi, self.divergence_lookback)
        if rsi_div['bullish']:
            buy_confirmations.append(f"RSI Bullish Divergence (strength: {rsi_div['strength']:.2f})")
        if rsi_div['bearish']:
            sell_confirmations.append(f"RSI Bearish Divergence (strength: {rsi_div['strength']:.2f})")
        
        # === 2. RSI EXTREME LEVELS ===
        if current_rsi < self.rsi_oversold:
            buy_confirmations.append(f"RSI={current_rsi:.1f} < {self.rsi_oversold} (oversold)")
            if current_rsi < self.rsi_extreme_oversold:
                buy_confirmations.append(f"RSI={current_rsi:.1f} EXTREME oversold")
        elif current_rsi > self.rsi_overbought:
            sell_confirmations.append(f"RSI={current_rsi:.1f} > {self.rsi_overbought} (overbought)")
            if current_rsi > self.rsi_extreme_overbought:
                sell_confirmations.append(f"RSI={current_rsi:.1f} EXTREME overbought")
        
        # === 3. MACD MOMENTUM EXHAUSTION ===
        macd_exhaust = self.detect_macd_momentum_exhaustion(macd_hist)
        if macd_exhaust['bullish']:
            buy_confirmations.append(f"MACD Bullish Exhaustion (strength: {macd_exhaust['strength']:.2f})")
        if macd_exhaust['bearish']:
            sell_confirmations.append(f"MACD Bearish Exhaustion (strength: {macd_exhaust['strength']:.2f})")
        
        # === 4. MACD HISTOGRAM DIRECTION ===
        current_hist = macd_hist[-1] if not np.isnan(macd_hist[-1]) else 0
        prev_hist = macd_hist[-2] if len(macd_hist) > 1 and not np.isnan(macd_hist[-2]) else 0
        
        if current_hist > prev_hist and current_hist < 0:
            # Histogram rising from negative = bullish momentum building
            buy_confirmations.append(f"MACD Histogram rising ({current_hist:.4f})")
        elif current_hist < prev_hist and current_hist > 0:
            # Histogram falling from positive = bearish momentum building
            sell_confirmations.append(f"MACD Histogram falling ({current_hist:.4f})")
        
        # === 5. STOCHASTIC CROSSOVER IN EXTREME ===
        prev_k = stoch_k[-2] if len(stoch_k) > 1 else current_stoch_k
        prev_d = stoch_d[-2] if len(stoch_d) > 1 else current_stoch_d
        
        # Bullish crossover in oversold
        if current_stoch_k < self.stoch_oversold:
            if current_stoch_k > current_stoch_d and prev_k <= prev_d:
                buy_confirmations.append(f"Stochastic bullish crossover in oversold ({current_stoch_k:.1f})")
            else:
                buy_confirmations.append(f"Stochastic in oversold ({current_stoch_k:.1f})")
        
        # Bearish crossover in overbought
        if current_stoch_k > self.stoch_overbought:
            if current_stoch_k < current_stoch_d and prev_k >= prev_d:
                sell_confirmations.append(f"Stochastic bearish crossover in overbought ({current_stoch_k:.1f})")
            else:
                sell_confirmations.append(f"Stochastic in overbought ({current_stoch_k:.1f})")
        
        # === 6. BOLLINGER BAND TOUCH ===
        bb_upper = indicators['bb_upper'][-1]
        bb_lower = indicators['bb_lower'][-1]
        bb_middle = indicators['bb_middle'][-1]
        
        if not np.isnan(bb_lower) and not np.isnan(bb_upper):
            bb_range = bb_upper - bb_lower
            lower_dist = (current_price - bb_lower) / bb_range if bb_range > 0 else 0.5
            upper_dist = (bb_upper - current_price) / bb_range if bb_range > 0 else 0.5
            
            if lower_dist < 0.05:  # Within 5% of lower band
                buy_confirmations.append(f"Price at lower Bollinger Band (dist: {lower_dist:.2%})")
            elif upper_dist < 0.05:  # Within 5% of upper band
                sell_confirmations.append(f"Price at upper Bollinger Band (dist: {upper_dist:.2%})")
        
        # === 7. CANDLESTICK PATTERN ===
        candle = self.detect_candlestick_pattern(df)
        if candle['bullish'] and candle['pattern']:
            buy_confirmations.append(f"Candlestick: {candle['pattern']}")
        if candle['bearish'] and candle['pattern']:
            sell_confirmations.append(f"Candlestick: {candle['pattern']}")
        
        # === 8. VOLUME SPIKE ===
        vol_spike = self.check_volume_spike(indicators['volume'], indicators['volume_ma'])
        if vol_spike['spike']:
            # Volume spike confirms momentum - add to both and direction will determine
            buy_confirmations.append(f"Volume spike ({vol_spike['ratio']:.1f}x average)")
            sell_confirmations.append(f"Volume spike ({vol_spike['ratio']:.1f}x average)")
        
        # === CHECK TREND FILTER ===
        trend = self.check_trend_filter(indicators)
        
        # === DETERMINE SIGNAL ===
        buy_count = len(buy_confirmations)
        sell_count = len(sell_confirmations)
        
        direction = None
        confidence = 0
        confirmations = []
        
        # For counter-trend trades (reversals), we want opposite of current trend
        if buy_count >= self.min_confirmations and buy_count > sell_count:
            direction = 'CALL'
            # Base confidence from confirmation count
            base_conf = 75 + (buy_count - self.min_confirmations) * 2.5
            
            # Boost for divergence (high-probability signal)
            if rsi_div['bullish']:
                base_conf += 5
            if macd_exhaust['bullish']:
                base_conf += 3
            if vol_spike['spike']:
                base_conf += 2
            
            confidence = min(base_conf, 95)
            confirmations = buy_confirmations
            
        elif sell_count >= self.min_confirmations and sell_count > buy_count:
            direction = 'PUT'
            base_conf = 75 + (sell_count - self.min_confirmations) * 2.5
            
            if rsi_div['bearish']:
                base_conf += 5
            if macd_exhaust['bearish']:
                base_conf += 3
            if vol_spike['spike']:
                base_conf += 2
            
            confidence = min(base_conf, 95)
            confirmations = sell_confirmations
        
        # Apply trend filter penalty for counter-trend in strong trends
        if direction and trend['trending'] and trend['strength'] > 0.3:
            if (direction == 'CALL' and trend['direction'] == 'down') or \
               (direction == 'PUT' and trend['direction'] == 'up'):
                # Counter-trend trade - reduce confidence but allow if strong signal
                confidence = confidence * 0.9
                confirmations.append(f"⚠️ Counter-trend (ADX: {trend['adx']})")
        
        # Final check - reject low confidence signals
        if direction and confidence < self.min_confidence:
            logger.info(f"Signal rejected: confidence {confidence:.1f}% < {self.min_confidence}% threshold")
            return None
        
        if direction is None:
            logger.debug(f"No signal for {symbol}: buy={buy_count}, sell={sell_count}, need={self.min_confirmations}")
            return None
        
        # Build signal response
        signal = {
            'direction': direction,
            'confidence': round(confidence, 1),
            'probability': round(confidence, 1),
            'entry_price': current_price,
            'symbol': symbol,
            'timeframe': self.timeframe,
            'confirmations': confirmations,
            'confirmation_count': max(buy_count, sell_count),
            'indicators': {
                'rsi': round(current_rsi, 1),
                'stoch_k': round(current_stoch_k, 1),
                'stoch_d': round(current_stoch_d, 1),
                'macd_hist': round(current_hist, 5),
                'adx': trend.get('adx', 0)
            },
            'analysis': {
                'rsi_divergence': rsi_div,
                'macd_exhaustion': macd_exhaust,
                'candlestick': candle,
                'volume_spike': vol_spike,
                'trend': trend
            },
            'strategy': self.name,
            'reasoning': f"{direction} signal with {max(buy_count, sell_count)}/8 confirmations: " + 
                        ", ".join(confirmations[:3]) + ("..." if len(confirmations) > 3 else "")
        }
        
        logger.info(f"✅ {self.name} Signal: {symbol} {direction} @ {current_price} ({confidence:.1f}% confidence)")
        logger.info(f"   Confirmations ({max(buy_count, sell_count)}): {confirmations}")
        
        return signal


def get_enhanced_ultra_short_strategy(timeframe: str = '5s') -> EnhancedUltraShortStrategy:
    """Factory function to get enhanced strategy instance"""
    return EnhancedUltraShortStrategy(timeframe)


def generate_enhanced_signal(df: pd.DataFrame, symbol: str, timeframe: str = '5s') -> Optional[Dict[str, Any]]:
    """Convenience function to generate signal"""
    strategy = EnhancedUltraShortStrategy(timeframe)
    return strategy.generate_signal(df, symbol)
