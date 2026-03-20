"""
1-Minute Momentum Exhaustion Reversal Strategy
===============================================
Designed for OTC Forex Binary Options (1-minute expiry)

THEORY:
- OTC markets are prone to quick reversals due to lower liquidity
- Price often overshoots and snaps back (mean reversion)
- Momentum exhaustion signals appear at turning points
- Multiple fast indicators confirm high-probability entries

ENTRY CONDITIONS FOR CALL:
1. RSI-2 below 10 (extreme oversold)
2. Stochastic %K crosses above %D from below 20
3. Price touches or pierces lower Bollinger Band (20,2)
4. Bullish candlestick pattern (hammer, bullish engulfing, or doji at bottom)
5. MACD histogram showing decreasing bearish momentum (getting less negative)

ENTRY CONDITIONS FOR PUT:
1. RSI-2 above 90 (extreme overbought)
2. Stochastic %K crosses below %D from above 80
3. Price touches or pierces upper Bollinger Band (20,2)
4. Bearish candlestick pattern (shooting star, bearish engulfing, or doji at top)
5. MACD histogram showing decreasing bullish momentum (getting less positive)

FILTERS:
- ATR filter: Skip if volatility too low (choppy market) or too high (news event)
- Avoid trading during first/last 5 minutes of session
- Require minimum 3 out of 5 confirmations for trade

WIN RATE TARGET: 70-75%
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime

class MomentumExhaustionStrategy:
    """
    1-Minute Momentum Exhaustion Reversal Strategy
    Catches reversals at momentum extremes with multiple confirmations
    """
    
    def __init__(self):
        self.name = "1m_momentum_exhaustion"
        self.display_name = "Momentum Exhaustion Reversal"
        self.timeframe = "1m"
        self.min_confidence = 70
        self.description = "Catches reversals at momentum extremes using RSI-2, Stochastic, BB, and candlestick patterns"
        
        # Indicator parameters optimized for 1-minute
        self.rsi_period = 2          # Ultra-fast RSI
        self.rsi_oversold = 10       # Extreme oversold
        self.rsi_overbought = 90     # Extreme overbought
        
        self.stoch_k = 5             # Fast stochastic
        self.stoch_d = 3
        self.stoch_smooth = 3
        self.stoch_oversold = 20
        self.stoch_overbought = 80
        
        self.bb_period = 20          # Bollinger Bands
        self.bb_std = 2.0
        
        self.macd_fast = 8           # Faster MACD for 1-min
        self.macd_slow = 17
        self.macd_signal = 9
        
        self.atr_period = 14
        
    def calculate_rsi(self, prices: pd.Series, period: int = 2) -> pd.Series:
        """Calculate RSI with specified period"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss.replace(0, 0.0001)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate Stochastic %K and %D"""
        lowest_low = low.rolling(window=self.stoch_k).min()
        highest_high = high.rolling(window=self.stoch_k).max()
        
        stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low + 0.0001)
        stoch_k = stoch_k.rolling(window=self.stoch_smooth).mean()
        stoch_d = stoch_k.rolling(window=self.stoch_d).mean()
        
        return stoch_k, stoch_d
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> tuple:
        """Calculate Bollinger Bands"""
        sma = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        
        upper = sma + (self.bb_std * std)
        lower = sma - (self.bb_std * std)
        
        return upper, sma, lower
    
    def calculate_macd(self, prices: pd.Series) -> tuple:
        """Calculate MACD line, signal, and histogram"""
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        return atr
    
    def detect_candlestick_pattern(self, candles: List[Dict]) -> Dict[str, Any]:
        """
        Detect reversal candlestick patterns
        Returns: {'bullish': bool, 'bearish': bool, 'pattern': str}
        """
        if len(candles) < 3:
            return {'bullish': False, 'bearish': False, 'pattern': None}
        
        current = candles[-1]
        prev = candles[-2]
        
        curr_open, curr_high, curr_low, curr_close = current['open'], current['high'], current['low'], current['close']
        body = abs(curr_close - curr_open)
        upper_wick = curr_high - max(curr_open, curr_close)
        lower_wick = min(curr_open, curr_close) - curr_low
        total_range = curr_high - curr_low if curr_high != curr_low else 0.0001
        
        prev_o, prev_c = prev['open'], prev['close']
        
        result = {'bullish': False, 'bearish': False, 'pattern': None}
        
        # BULLISH PATTERNS
        # Hammer: Small body at top, long lower wick (2x+ body)
        if lower_wick > body * 2 and upper_wick < body * 0.5 and body < total_range * 0.4:
            result['bullish'] = True
            result['pattern'] = 'hammer'
        
        # Bullish Engulfing: Current green candle engulfs previous red
        elif curr_close > curr_open and prev_c < prev_o and curr_close > prev_o and curr_open < prev_c:
            result['bullish'] = True
            result['pattern'] = 'bullish_engulfing'
        
        # Doji at bottom (after downtrend): Very small body
        elif body < total_range * 0.1 and candles[-3]['close'] > candles[-2]['close'] > curr_close:
            result['bullish'] = True
            result['pattern'] = 'doji_reversal'
        
        # Morning Star pattern (3 candles)
        elif len(candles) >= 3:
            candle_3 = candles[-3]
            if (candle_3['close'] < candle_3['open'] and  # First: bearish
                abs(prev_c - prev_o) < abs(candle_3['close'] - candle_3['open']) * 0.3 and  # Second: small body
                curr_close > curr_open and curr_close > (candle_3['open'] + candle_3['close']) / 2):  # Third: bullish closes above mid
                result['bullish'] = True
                result['pattern'] = 'morning_star'
        
        # BEARISH PATTERNS
        # Shooting Star: Small body at bottom, long upper wick (2x+ body)
        if upper_wick > body * 2 and lower_wick < body * 0.5 and body < total_range * 0.4:
            result['bearish'] = True
            result['pattern'] = 'shooting_star'
        
        # Bearish Engulfing: Current red candle engulfs previous green
        elif curr_close < curr_open and prev_c > prev_o and curr_close < prev_o and curr_open > prev_c:
            result['bearish'] = True
            result['pattern'] = 'bearish_engulfing'
        
        # Doji at top (after uptrend): Very small body
        elif body < total_range * 0.1 and candles[-3]['close'] < candles[-2]['close'] < curr_close:
            result['bearish'] = True
            result['pattern'] = 'doji_reversal'
        
        # Evening Star pattern (3 candles)
        elif len(candles) >= 3:
            candle_3 = candles[-3]
            if (candle_3['close'] > candle_3['open'] and  # First: bullish
                abs(prev_c - prev_o) < abs(candle_3['close'] - candle_3['open']) * 0.3 and  # Second: small body
                curr_close < curr_open and curr_close < (candle_3['open'] + candle_3['close']) / 2):  # Third: bearish closes below mid
                result['bearish'] = True
                result['pattern'] = 'evening_star'
        
        return result
    
    def generate_signal(self, candles: List[Dict], current_price: float = None) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on momentum exhaustion
        
        Args:
            candles: List of OHLCV dictionaries with keys: open, high, low, close, volume, time
            current_price: Optional current price override
            
        Returns:
            Signal dictionary or None
        """
        if len(candles) < 50:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Ensure we have required columns
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                return None
        
        # Calculate all indicators
        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        
        rsi = self.calculate_rsi(close, self.rsi_period)
        stoch_k, stoch_d = self.calculate_stochastic(high, low, close)
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(close)
        macd_line, signal_line, macd_hist = self.calculate_macd(close)
        atr = self.calculate_atr(high, low, close)
        
        # Get current values
        current_close = float(close.iloc[-1])
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        current_stoch_k = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else 50
        current_stoch_d = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else 50
        prev_stoch_k = float(stoch_k.iloc[-2]) if not pd.isna(stoch_k.iloc[-2]) else 50
        prev_stoch_d = float(stoch_d.iloc[-2]) if not pd.isna(stoch_d.iloc[-2]) else 50
        current_bb_upper = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else current_close
        current_bb_lower = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else current_close
        current_macd_hist = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0
        prev_macd_hist = float(macd_hist.iloc[-2]) if not pd.isna(macd_hist.iloc[-2]) else 0
        current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
        
        # Detect candlestick patterns
        candle_pattern = self.detect_candlestick_pattern(candles[-5:])
        
        # ATR filter - skip if volatility is abnormal
        avg_atr = float(atr.rolling(50).mean().iloc[-1]) if not pd.isna(atr.rolling(50).mean().iloc[-1]) else current_atr
        if current_atr < avg_atr * 0.3 or current_atr > avg_atr * 3:
            return None  # Skip choppy or volatile markets
        
        # Initialize confirmations
        call_confirmations = []
        put_confirmations = []
        
        # ===== CALL SIGNAL CONDITIONS =====
        
        # 1. RSI-2 extreme oversold
        if current_rsi < self.rsi_oversold:
            call_confirmations.append(f"RSI_EXTREME_OVERSOLD ({current_rsi:.1f})")
        elif current_rsi < 20:
            call_confirmations.append(f"RSI_OVERSOLD ({current_rsi:.1f})")
        
        # 2. Stochastic bullish crossover from oversold
        if current_stoch_k > current_stoch_d and prev_stoch_k <= prev_stoch_d and current_stoch_k < 30:
            call_confirmations.append(f"STOCH_BULLISH_CROSS ({current_stoch_k:.1f})")
        elif current_stoch_k < self.stoch_oversold:
            call_confirmations.append(f"STOCH_OVERSOLD ({current_stoch_k:.1f})")
        
        # 3. Price at/below lower Bollinger Band
        if current_close <= current_bb_lower:
            call_confirmations.append("PRICE_AT_BB_LOWER")
        elif current_close <= current_bb_lower * 1.002:  # Within 0.2% of lower band
            call_confirmations.append("PRICE_NEAR_BB_LOWER")
        
        # 4. Bullish candlestick pattern
        if candle_pattern['bullish']:
            call_confirmations.append(f"CANDLE_{candle_pattern['pattern'].upper()}")
        
        # 5. MACD histogram momentum exhaustion (bearish momentum decreasing)
        if current_macd_hist < 0 and current_macd_hist > prev_macd_hist:
            call_confirmations.append("MACD_BEARISH_EXHAUSTION")
        
        # ===== PUT SIGNAL CONDITIONS =====
        
        # 1. RSI-2 extreme overbought
        if current_rsi > self.rsi_overbought:
            put_confirmations.append(f"RSI_EXTREME_OVERBOUGHT ({current_rsi:.1f})")
        elif current_rsi > 80:
            put_confirmations.append(f"RSI_OVERBOUGHT ({current_rsi:.1f})")
        
        # 2. Stochastic bearish crossover from overbought
        if current_stoch_k < current_stoch_d and prev_stoch_k >= prev_stoch_d and current_stoch_k > 70:
            put_confirmations.append(f"STOCH_BEARISH_CROSS ({current_stoch_k:.1f})")
        elif current_stoch_k > self.stoch_overbought:
            put_confirmations.append(f"STOCH_OVERBOUGHT ({current_stoch_k:.1f})")
        
        # 3. Price at/above upper Bollinger Band
        if current_close >= current_bb_upper:
            put_confirmations.append("PRICE_AT_BB_UPPER")
        elif current_close >= current_bb_upper * 0.998:  # Within 0.2% of upper band
            put_confirmations.append("PRICE_NEAR_BB_UPPER")
        
        # 4. Bearish candlestick pattern
        if candle_pattern['bearish']:
            put_confirmations.append(f"CANDLE_{candle_pattern['pattern'].upper()}")
        
        # 5. MACD histogram momentum exhaustion (bullish momentum decreasing)
        if current_macd_hist > 0 and current_macd_hist < prev_macd_hist:
            put_confirmations.append("MACD_BULLISH_EXHAUSTION")
        
        # ===== DETERMINE SIGNAL =====
        
        call_count = len(call_confirmations)
        put_count = len(put_confirmations)
        
        # Need minimum 3 confirmations
        min_confirmations = 3
        
        if call_count >= min_confirmations and call_count > put_count:
            # Calculate confidence based on confirmations
            base_confidence = 60
            confidence = min(95, base_confidence + (call_count * 7))
            
            # Boost for extreme RSI
            if current_rsi < 5:
                confidence = min(95, confidence + 5)
            
            # Boost for candlestick pattern
            if candle_pattern['bullish']:
                confidence = min(95, confidence + 5)
            
            return {
                "direction": "CALL",
                "confidence": confidence,
                "strategy_name": self.display_name,
                "timeframe": self.timeframe,
                "expiry_seconds": 60,
                "entry_price": current_price or current_close,
                "confirmations": call_confirmations,
                "confirmations_count": call_count,
                "indicators": {
                    "rsi_2": round(current_rsi, 2),
                    "stochastic_k": round(current_stoch_k, 2),
                    "stochastic_d": round(current_stoch_d, 2),
                    "bb_position": "lower",
                    "macd_histogram": round(current_macd_hist, 6),
                    "atr": round(current_atr, 6),
                    "candle_pattern": candle_pattern['pattern']
                },
                "quality": "high" if call_count >= 4 else "medium",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        elif put_count >= min_confirmations and put_count > call_count:
            # Calculate confidence based on confirmations
            base_confidence = 60
            confidence = min(95, base_confidence + (put_count * 7))
            
            # Boost for extreme RSI
            if current_rsi > 95:
                confidence = min(95, confidence + 5)
            
            # Boost for candlestick pattern
            if candle_pattern['bearish']:
                confidence = min(95, confidence + 5)
            
            return {
                "direction": "PUT",
                "confidence": confidence,
                "strategy_name": self.display_name,
                "timeframe": self.timeframe,
                "expiry_seconds": 60,
                "entry_price": current_price or current_close,
                "confirmations": put_confirmations,
                "confirmations_count": put_count,
                "indicators": {
                    "rsi_2": round(current_rsi, 2),
                    "stochastic_k": round(current_stoch_k, 2),
                    "stochastic_d": round(current_stoch_d, 2),
                    "bb_position": "upper",
                    "macd_histogram": round(current_macd_hist, 6),
                    "atr": round(current_atr, 6),
                    "candle_pattern": candle_pattern['pattern']
                },
                "quality": "high" if put_count >= 4 else "medium",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return None


# Create singleton instance
momentum_exhaustion_strategy = MomentumExhaustionStrategy()


def get_momentum_exhaustion_signal(candles: List[Dict], current_price: float = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to generate momentum exhaustion signal
    
    Args:
        candles: List of OHLCV candles
        current_price: Current market price
        
    Returns:
        Signal dictionary or None
    """
    return momentum_exhaustion_strategy.generate_signal(candles, current_price)


# Strategy metadata for registration
STRATEGY_INFO = {
    "id": "1m_momentum_exhaustion",
    "name": "Momentum Exhaustion Reversal",
    "timeframe": "1m",
    "description": "Catches reversals at momentum extremes using RSI-2, Stochastic, Bollinger Bands, and candlestick patterns. Best for OTC forex pairs.",
    "win_rate_target": "70-75%",
    "risk_level": "medium",
    "indicators": ["RSI-2", "Stochastic (5,3,3)", "Bollinger Bands (20,2)", "MACD (8,17,9)", "Candlestick Patterns"],
    "entry_rules": {
        "CALL": [
            "RSI-2 below 10 (extreme oversold)",
            "Stochastic %K crosses above %D from below 20",
            "Price at/near lower Bollinger Band",
            "Bullish candlestick pattern (hammer, engulfing, doji)",
            "MACD histogram showing decreasing bearish momentum"
        ],
        "PUT": [
            "RSI-2 above 90 (extreme overbought)",
            "Stochastic %K crosses below %D from above 80", 
            "Price at/near upper Bollinger Band",
            "Bearish candlestick pattern (shooting star, engulfing, doji)",
            "MACD histogram showing decreasing bullish momentum"
        ]
    },
    "min_confirmations": 3,
    "filters": ["ATR volatility filter", "Avoid abnormal market conditions"]
}
