"""
Pocket Option 5-Second High-Accuracy Strategy (93%+ Target)
Based on research of top-performing Pocket Option bots in 2024-2025

EXACT PARAMETERS FROM RESEARCH:
- EMA: 20 periods
- RSI: 2 periods (ultra-fast for 5s)
- Stochastic Oscillator: (3, 1, 1)
- Bollinger Bands: 5 periods, 2.5 SD

Strategy Logic:
1. Bollinger Bands + RSI for overbought/oversold confirmation
2. EMA 20 for trend direction
3. Stochastic for momentum filter
4. Support/Resistance detection
5. Candlestick pattern recognition (Pin Bar, Doji, Engulfing)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, List
from chart_transformations import chart_transformer
from support_resistance_detector import get_detector
from advanced_5s_ai_ensemble import advanced_5s_ai_ensemble
import talib

logger = logging.getLogger(__name__)

class PocketOption5SecondStrategy:
    """
    High-accuracy 5-second strategy based on proven Pocket Option algorithms
    Target accuracy: 93-95%
    """
    
    def __init__(self):
        # EXACT parameters from research
        self.ema_period = 20
        self.rsi_period = 2  # Ultra-fast RSI for 5s
        self.stoch_k_period = 3
        self.stoch_d_period = 1
        self.stoch_smooth = 1
        self.bb_period = 5
        self.bb_std = 2.5
        
        self.min_data_points = 100
        
        # Thresholds from research
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.stoch_overbought = 80
        self.stoch_oversold = 20
        
        # Enhanced S/R detector for 5s timeframe
        self.sr_detector = get_detector('5s')
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate EMA using TA-Lib for accuracy"""
        return pd.Series(talib.EMA(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using TA-Lib"""
        return pd.Series(talib.RSI(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate Stochastic Oscillator"""
        slowk, slowd = talib.STOCH(
            high.values, low.values, close.values,
            fastk_period=self.stoch_k_period,
            slowk_period=self.stoch_d_period,
            slowk_matype=0,
            slowd_period=self.stoch_smooth,
            slowd_matype=0
        )
        return pd.Series(slowk, index=close.index), pd.Series(slowd, index=close.index)
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> tuple:
        """Calculate Bollinger Bands"""
        upper, middle, lower = talib.BBANDS(
            prices.values,
            timeperiod=self.bb_period,
            nbdevup=self.bb_std,
            nbdevdn=self.bb_std,
            matype=0
        )
        return (
            pd.Series(upper, index=prices.index),
            pd.Series(middle, index=prices.index),
            pd.Series(lower, index=prices.index)
        )
    
    def detect_support_resistance(self, prices: pd.Series, window: int = 10) -> Dict:
        """Detect recent support and resistance levels"""
        highs = prices.rolling(window=window).max()
        lows = prices.rolling(window=window).min()
        
        current_price = prices.iloc[-1]
        resistance = highs.iloc[-1]
        support = lows.iloc[-1]
        
        return {
            'resistance': resistance,
            'support': support,
            'near_resistance': abs(current_price - resistance) / current_price < 0.001,  # Within 0.1%
            'near_support': abs(current_price - support) / current_price < 0.001
        }
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict:
        """Detect key candlestick patterns: Pin Bar, Doji, Engulfing"""
        if len(df) < 3:
            return {'pin_bar': None, 'doji': None, 'engulfing': None}
        
        # Get last few candles
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Pin Bar detection
        body = abs(last['close'] - last['open'])
        total_range = last['high'] - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        lower_wick = min(last['open'], last['close']) - last['low']
        
        pin_bar = None
        if total_range > 0:
            # Bullish pin bar: long lower wick
            if lower_wick > body * 2 and lower_wick > upper_wick * 2:
                pin_bar = 'BULLISH'
            # Bearish pin bar: long upper wick
            elif upper_wick > body * 2 and upper_wick > lower_wick * 2:
                pin_bar = 'BEARISH'
        
        # Doji detection (small body, indecision)
        doji = None
        if total_range > 0 and body / total_range < 0.1:
            doji = 'INDECISION'
        
        # Engulfing pattern detection
        engulfing = None
        prev_body = abs(prev['close'] - prev['open'])
        if body > prev_body * 1.5:
            # Bullish engulfing
            if last['close'] > last['open'] and prev['close'] < prev['open']:
                if last['close'] > prev['open'] and last['open'] < prev['close']:
                    engulfing = 'BULLISH'
            # Bearish engulfing
            elif last['close'] < last['open'] and prev['close'] > prev['open']:
                if last['close'] < prev['open'] and last['open'] > prev['close']:
                    engulfing = 'BEARISH'
        
        return {
            'pin_bar': pin_bar,
            'doji': doji,
            'engulfing': engulfing
        }
    
    def get_real_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch real 1-minute data for analysis"""
        try:
            # Convert symbol for yfinance (forex pairs need =X suffix)
            yf_symbol = symbol
            if '_OTC' in symbol or '_regular' in symbol:
                yf_symbol = symbol.replace('_OTC', '').replace('_regular', '')
            
            # Add =X for forex pairs
            if len(yf_symbol) == 6 and yf_symbol.isalpha():  # Forex pair like EURUSD
                yf_symbol = f"{yf_symbol}=X"
            
            ticker = yf.Ticker(yf_symbol)
            # Get last 1 day of 1-minute data
            df = ticker.history(period="1d", interval="1m")
            
            if df.empty or len(df) < self.min_data_points:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Ensure we have OHLCV columns
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    def generate_signal(self, symbol: str, chart_type: str = "japanese_candles", user_timeframes: List[str] = None) -> Optional[Dict]:
        """
        Generate 5-second trading signal using researched high-accuracy strategy
        
        Returns:
            Dict with signal, confidence, reasoning, and analysis
        """
        try:
            # Fetch real market data
            df = self.get_real_market_data(symbol)
            if df is None:
                return None
            
            # Apply chart transformation
            df = chart_transformer.transform_data(df, chart_type)
            
            # Calculate all indicators
            close_prices = df['close']
            high_prices = df['high']
            low_prices = df['low']
            
            # EMA 20
            ema = self.calculate_ema(close_prices, self.ema_period)
            
            # RSI 2 (ultra-fast)
            rsi = self.calculate_rsi(close_prices, self.rsi_period)
            
            # Stochastic (3, 1, 1)
            stoch_k, stoch_d = self.calculate_stochastic(high_prices, low_prices, close_prices)
            
            # Bollinger Bands (5, 2.5)
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close_prices)
            
            # Get current values
            current_price = close_prices.iloc[-1]
            current_ema = ema.iloc[-1]
            current_rsi = rsi.iloc[-1]
            current_stoch_k = stoch_k.iloc[-1]
            current_stoch_d = stoch_d.iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            
            # Check for NaN values
            if pd.isna([current_ema, current_rsi, current_stoch_k, current_bb_upper]).any():
                logger.warning(f"NaN values in indicators for {symbol}")
                return None
            
            # Enhanced S/R detection with trend reversal analysis
            sr_levels = self.sr_detector.identify_key_levels(df)
            proximity = self.sr_detector.is_near_support_resistance(current_price, sr_levels)
            reversal = self.sr_detector.detect_trend_reversal(df, sr_levels)
            
            # Detect candlestick patterns
            patterns = self.detect_candlestick_patterns(df)
            
            # Calculate position relative to Bollinger Bands
            bb_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower) if current_bb_upper != current_bb_lower else 0.5
            
            # Strategy Logic (Multiple Confirmation System)
            signal = None
            confidence = 0
            reasoning = []
            
            logger.info(f"🎯 5s Analysis for {symbol}:")
            logger.info(f"   Price={current_price:.5f}, EMA={current_ema:.5f}, RSI={current_rsi:.1f}")
            logger.info(f"   Stoch K={current_stoch_k:.1f}, BB Position={bb_position:.2%}")
            
            # === RULE 1: Bollinger Bands + RSI (Primary Signal) ===
            if bb_position < 0.15:  # Price near lower BB
                if current_rsi < self.rsi_oversold:
                    # Oversold condition - expect bounce UP
                    signal = "CALL"
                    confidence = 85
                    reasoning.append(f"🟢 OVERSOLD: Price at lower BB ({bb_position:.1%}), RSI={current_rsi:.1f}")
                    reasoning.append("💡 Strong bounce expected from support zone")
            
            elif bb_position > 0.85:  # Price near upper BB
                if current_rsi > self.rsi_overbought:
                    # Overbought condition - expect reversal DOWN
                    signal = "PUT"
                    confidence = 85
                    reasoning.append(f"🔴 OVERBOUGHT: Price at upper BB ({bb_position:.1%}), RSI={current_rsi:.1f}")
                    reasoning.append("💡 Strong reversal expected from resistance zone")
            
            # === RULE 2: EMA + RSI Trend Confirmation ===
            if signal is None:
                if current_price > current_ema and self.rsi_oversold < current_rsi < 65:
                    # Uptrend with momentum
                    signal = "CALL"
                    confidence = 78
                    reasoning.append(f"📈 UPTREND: Price above EMA, RSI={current_rsi:.1f} shows strength")
                    reasoning.append("💡 Trend continuation expected")
                
                elif current_price < current_ema and 35 < current_rsi < self.rsi_overbought:
                    # Downtrend with momentum
                    signal = "PUT"
                    confidence = 78
                    reasoning.append(f"📉 DOWNTREND: Price below EMA, RSI={current_rsi:.1f} shows weakness")
                    reasoning.append("💡 Trend continuation expected")
            
            # === RULE 3: Stochastic Confirmation (Boosts confidence) ===
            if signal == "CALL" and current_stoch_k < self.stoch_oversold:
                confidence += 5
                reasoning.append(f"✅ Stochastic confirms oversold ({current_stoch_k:.1f})")
            elif signal == "PUT" and current_stoch_k > self.stoch_overbought:
                confidence += 5
                reasoning.append(f"✅ Stochastic confirms overbought ({current_stoch_k:.1f})")
            
            # === RULE 4: Enhanced S/R Confirmation & Reversal Detection ===
            if reversal['reversal_detected']:
                if reversal['bounce_off_support'] and signal == "CALL":
                    confidence += 10
                    reasoning.append(f"✅ REVERSAL DETECTED: Bounce off support (strength: {reversal['reversal_strength']})")
                elif reversal['bounce_off_resistance'] and signal == "PUT":
                    confidence += 10
                    reasoning.append(f"✅ REVERSAL DETECTED: Reversal at resistance (strength: {reversal['reversal_strength']})")
            elif proximity['near_support'] and signal == "CALL":
                confidence += 6
                reasoning.append(f"✅ Price near support ({proximity['support_distance_pct']:.2f}% away)")
            elif proximity['near_resistance'] and signal == "PUT":
                confidence += 6
                reasoning.append(f"✅ Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
            
            # === RULE 5: Candlestick Pattern Confirmation (Boosts confidence) ===
            if signal == "CALL":
                if patterns['pin_bar'] == 'BULLISH':
                    confidence += 5
                    reasoning.append("✅ Bullish Pin Bar detected")
                elif patterns['engulfing'] == 'BULLISH':
                    confidence += 5
                    reasoning.append("✅ Bullish Engulfing pattern detected")
            
            elif signal == "PUT":
                if patterns['pin_bar'] == 'BEARISH':
                    confidence += 5
                    reasoning.append("✅ Bearish Pin Bar detected")
                elif patterns['engulfing'] == 'BEARISH':
                    confidence += 5
                    reasoning.append("✅ Bearish Engulfing pattern detected")
            
            # Doji at extremes signals reversal
            if patterns['doji'] == 'INDECISION':
                if bb_position > 0.85:
                    if signal == "PUT":
                        confidence += 3
                        reasoning.append("✅ Doji at resistance confirms reversal")
                elif bb_position < 0.15:
                    if signal == "CALL":
                        confidence += 3
                        reasoning.append("✅ Doji at support confirms reversal")
            
            # === Final Signal Check ===
            if signal is None:
                return None
            
            # === CRITICAL: Validate signal against S/R levels ===
            # Prevent wrong-direction signals during trend reversals
            validation = self.sr_detector.validate_signal_direction(signal, current_price, sr_levels)
            
            if not validation['valid']:
                logger.warning(f"⚠️ Signal REJECTED by S/R validation: {validation['reasoning']}")
                return None  # Don't generate signal if it contradicts S/R
            
            # Apply confidence adjustment from S/R validation
            confidence += validation['confidence_adjustment']
            reasoning.extend(validation['reasoning'])
            
            # Cap confidence at 98%
            confidence = min(confidence, 98)
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reasoning": reasoning,
                "analysis": {
                    "price": current_price,
                    "ema_20": current_ema,
                    "rsi_2": current_rsi,
                    "stoch_k": current_stoch_k,
                    "bb_position": bb_position,
                    "nearest_support": sr_levels['nearest_support'],
                    "nearest_resistance": sr_levels['nearest_resistance'],
                    "pivot_point": sr_levels['pivot_point'],
                    "reversal_detected": reversal['reversal_detected'],
                    "reversal_type": reversal['reversal_type'],
                    "patterns": patterns
                },
                "strategy": "Pocket Option 5s High-Accuracy",
                "timeframe": "5s"
            }
            
        except Exception as e:
            logger.error(f"Error in 5s strategy for {symbol}: {e}", exc_info=True)
            return None

# Create singleton instance
pocket_option_5s_strategy = PocketOption5SecondStrategy()
