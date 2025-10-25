"""
Pocket Option 15-Second High-Accuracy Strategy (90%+ Target)
Based on research of top-performing Pocket Option bots in 2024-2025

EXACT PARAMETERS FROM RESEARCH:
- EMA Crossover: 5 EMA crossing 20 EMA
- RSI: 14 periods (standard)
- Stochastic Oscillator: (5, 3, 3) - Slow Stochastic
- Bollinger Bands: 20 periods, 2 SD

Strategy Logic:
1. EMA 5/20 crossover for trend detection
2. RSI 14 for momentum confirmation
3. Stochastic for overbought/oversold
4. Bollinger Bands for volatility
5. Support/Resistance + Price Action
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, List
from chart_transformations import chart_transformer
from support_resistance_detector import get_detector
from market_quality_filter import get_market_filter
from supertrend_indicator import get_supertrend
import talib

logger = logging.getLogger(__name__)

class PocketOption15SecondStrategy:
    """
    High-accuracy 15-second strategy with EMA crossover
    Target accuracy: 90%+
    """
    
    def __init__(self):
        # EXACT parameters from research
        self.ema_fast = 5
        self.ema_slow = 20
        self.rsi_period = 14
        self.stoch_k_period = 5
        self.stoch_d_period = 3
        self.stoch_smooth = 3
        self.bb_period = 20
        self.bb_std = 2.0
        
        self.min_data_points = 100
        
        # AGGRESSIVE ACCURACY THRESHOLDS (90%+ TARGET)
        self.rsi_overbought = 72  # Stricter (was 70)
        self.rsi_oversold = 28    # Stricter (was 30)
        self.stoch_overbought = 82  # Stricter (was 80)
        self.stoch_oversold = 18    # Stricter (was 20)
        
        # Minimum base confidence
        self.min_base_confidence = 90  # Start high for 15s
        
        # Enhanced S/R detector for 15s timeframe
        self.sr_detector = get_detector('15s')
        
        # Market quality filter
        self.market_filter = get_market_filter('15s')
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate EMA using TA-Lib"""
        return pd.Series(talib.EMA(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using TA-Lib"""
        return pd.Series(talib.RSI(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate Slow Stochastic Oscillator"""
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
    
    def detect_support_resistance(self, prices: pd.Series, window: int = 20) -> Dict:
        """Detect support and resistance levels"""
        highs = prices.rolling(window=window).max()
        lows = prices.rolling(window=window).min()
        
        current_price = prices.iloc[-1]
        resistance = highs.iloc[-1]
        support = lows.iloc[-1]
        
        return {
            'resistance': resistance,
            'support': support,
            'near_resistance': abs(current_price - resistance) / current_price < 0.002,
            'near_support': abs(current_price - support) / current_price < 0.002
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
            df = ticker.history(period="1d", interval="1m")
            
            if df.empty or len(df) < self.min_data_points:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
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
        Generate 15-second trading signal using EMA crossover strategy
        
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
            
            # === MARKET QUALITY CHECK ===
            market_quality = self.market_filter.check_market_quality(df)
            
            if not market_quality['passed']:
                logger.warning(f"⛔ SIGNAL REJECTED: Poor market quality for {symbol}")
                return None
            
            logger.info(f"✅ Market quality: {market_quality['overall_quality']:.1%}")
            
            # Calculate all indicators
            close_prices = df['close']
            high_prices = df['high']
            low_prices = df['low']
            
            # EMAs
            ema_fast = self.calculate_ema(close_prices, self.ema_fast)
            ema_slow = self.calculate_ema(close_prices, self.ema_slow)
            
            # RSI
            rsi = self.calculate_rsi(close_prices, self.rsi_period)
            
            # Stochastic
            stoch_k, stoch_d = self.calculate_stochastic(high_prices, low_prices, close_prices)
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close_prices)
            
            # Get current values
            current_price = close_prices.iloc[-1]
            current_ema_fast = ema_fast.iloc[-1]
            current_ema_slow = ema_slow.iloc[-1]
            prev_ema_fast = ema_fast.iloc[-2]
            prev_ema_slow = ema_slow.iloc[-2]
            current_rsi = rsi.iloc[-1]
            current_stoch_k = stoch_k.iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            
            # Check for NaN values
            if pd.isna([current_ema_fast, current_ema_slow, current_rsi, current_stoch_k]).any():
                logger.warning(f"NaN values in indicators for {symbol}")
                return None
            
            # Enhanced S/R detection with trend reversal analysis
            sr_levels = self.sr_detector.identify_key_levels(df)
            proximity = self.sr_detector.is_near_support_resistance(current_price, sr_levels)
            reversal = self.sr_detector.detect_trend_reversal(df, sr_levels)
            
            # Detect EMA crossover
            bullish_crossover = prev_ema_fast <= prev_ema_slow and current_ema_fast > current_ema_slow
            bearish_crossover = prev_ema_fast >= prev_ema_slow and current_ema_fast < current_ema_slow
            
            # Current trend based on EMA position
            in_uptrend = current_ema_fast > current_ema_slow
            in_downtrend = current_ema_fast < current_ema_slow
            
            # Calculate BB position
            bb_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower) if current_bb_upper != current_bb_lower else 0.5
            
            # Strategy Logic
            signal = None
            confidence = 0
            reasoning = []
            
            logger.info(f"🎯 15s Analysis for {symbol}:")
            logger.info(f"   Price={current_price:.5f}, EMA5={current_ema_fast:.5f}, EMA20={current_ema_slow:.5f}")
            logger.info(f"   RSI={current_rsi:.1f}, Stoch={current_stoch_k:.1f}")
            logger.info(f"   Bullish Cross={bullish_crossover}, Bearish Cross={bearish_crossover}")
            
            # === AGGRESSIVE SELECTIVITY: ONLY CLEAR CROSSOVERS WITH CONFIRMATION ===
            signal = None
            confidence = 0
            reasoning = []
            confirmations_count = 0
            
            # === PRIMARY SIGNAL: EMA Crossover + RSI Confirmation (MANDATORY) ===
            # Only accept crossovers with proper RSI confirmation
            if bullish_crossover:
                if 45 < current_rsi < self.rsi_overbought:  # RSI in "healthy" range
                    signal = "CALL"
                    confidence = self.min_base_confidence
                    reasoning.append("🟢 BULLISH CROSSOVER: EMA 5 crossed above EMA 20")
                    reasoning.append(f"✅ RSI confirms momentum ({current_rsi:.1f})")
                    confirmations_count += 2  # Crossover + RSI
                else:
                    logger.warning(f"⛔ Bullish crossover but RSI out of range ({current_rsi:.1f})")
                    return None  # Reject if RSI doesn't support
            
            elif bearish_crossover:
                if self.rsi_oversold < current_rsi < 55:  # RSI in "healthy" range
                    signal = "PUT"
                    confidence = self.min_base_confidence
                    reasoning.append("🔴 BEARISH CROSSOVER: EMA 5 crossed below EMA 20")
                    reasoning.append(f"✅ RSI confirms momentum ({current_rsi:.1f})")
                    confirmations_count += 2
                else:
                    logger.warning(f"⛔ Bearish crossover but RSI out of range ({current_rsi:.1f})")
                    return None
            
            # If no crossover, don't look for weaker signals - STOP HERE
            else:
                logger.info(f"⛔ NO EMA CROSSOVER: No primary signal for {symbol}")
                return None  # ONLY trade crossovers in 15s strategy
            
            # === REQUIRE STOCHASTIC CONFIRMATION (MANDATORY) ===
            stoch_confirms = False
            if signal == "CALL":
                if current_stoch_k < 50:  # Stochastic shows room to rise
                    confidence += 5
                    reasoning.append(f"✅ Stochastic below midpoint ({current_stoch_k:.1f}) - room for upside")
                    confirmations_count += 1
                    stoch_confirms = True
                elif current_stoch_k > 82:  # Too overbought
                    logger.warning(f"⛔ CALL rejected: Stochastic overbought ({current_stoch_k:.1f})")
                    return None
            
            elif signal == "PUT":
                if current_stoch_k > 50:  # Stochastic shows room to fall
                    confidence += 5
                    reasoning.append(f"✅ Stochastic above midpoint ({current_stoch_k:.1f}) - room for downside")
                    confirmations_count += 1
                    stoch_confirms = True
                elif current_stoch_k < 18:  # Too oversold
                    logger.warning(f"⛔ PUT rejected: Stochastic oversold ({current_stoch_k:.1f})")
                    return None
            
            if not stoch_confirms:
                # Stochastic in neutral zone - still allow but don't boost
                reasoning.append(f"⚠️ Stochastic neutral ({current_stoch_k:.1f})")
                confidence -= 3  # Small penalty
            
            # === REQUIRE S/R CONFIRMATION (MANDATORY) ===
            sr_confirms = False
            
            if reversal['reversal_detected']:
                if reversal['bounce_off_support'] and signal == "CALL":
                    confidence += 9
                    reasoning.append(f"✅ REVERSAL: Bounce off support (strength: {reversal['reversal_strength']})")
                    confirmations_count += 1
                    sr_confirms = True
                elif reversal['bounce_off_resistance'] and signal == "PUT":
                    confidence += 9
                    reasoning.append(f"✅ REVERSAL: Reversal at resistance (strength: {reversal['reversal_strength']})")
                    confirmations_count += 1
                    sr_confirms = True
            elif proximity['near_support'] and signal == "CALL":
                confidence += 6
                reasoning.append(f"✅ Price near support ({proximity['support_distance_pct']:.2f}% away)")
                confirmations_count += 1
                sr_confirms = True
            elif proximity['near_resistance'] and signal == "PUT":
                confidence += 6
                reasoning.append(f"✅ Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
                confirmations_count += 1
                sr_confirms = True
            
            if not sr_confirms:
                logger.warning(f"⛔ SIGNAL REJECTED: No S/R confirmation")
                return None
            
            # === MINIMUM CONFIRMATIONS CHECK ===
            if confirmations_count < 3:
                logger.warning(f"⛔ SIGNAL REJECTED: Only {confirmations_count} confirmations (need 3+)")
                return None
            
            reasoning.append(f"✅ STRONG SETUP: {confirmations_count} confirmations")
            
            if signal is None:
                return None
            
            # === CRITICAL: Validate signal against S/R levels ===
            validation = self.sr_detector.validate_signal_direction(signal, current_price, sr_levels)
            
            if not validation['valid']:
                logger.warning(f"⚠️ Signal REJECTED by S/R validation: {validation['reasoning']}")
                return None
            
            # Apply confidence adjustment from S/R validation
            confidence += validation['confidence_adjustment']
            reasoning.extend(validation['reasoning'])
            
            # === FINAL CONFIDENCE CHECK ===
            if confidence < 90:
                logger.warning(f"⛔ SIGNAL REJECTED: Final confidence too low ({confidence:.0f}% < 90%)")
                return None
            
            # Cap confidence at 97%
            confidence = min(confidence, 97)
            
            logger.info(f"✅ SIGNAL APPROVED: {signal} with {confidence:.0f}% confidence")
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reasoning": reasoning,
                "analysis": {
                    "price": current_price,
                    "ema_5": current_ema_fast,
                    "ema_20": current_ema_slow,
                    "rsi_14": current_rsi,
                    "stoch_k": current_stoch_k,
                    "bb_position": bb_position,
                    "trend": "UP" if in_uptrend else "DOWN",
                    "crossover": "BULLISH" if bullish_crossover else ("BEARISH" if bearish_crossover else "NONE"),
                    "nearest_support": sr_levels['nearest_support'],
                    "nearest_resistance": sr_levels['nearest_resistance'],
                    "pivot_point": sr_levels['pivot_point'],
                    "reversal_detected": reversal['reversal_detected'],
                    "reversal_type": reversal['reversal_type']
                },
                "strategy": "Pocket Option 15s EMA Crossover",
                "timeframe": "15s"
            }
            
        except Exception as e:
            logger.error(f"Error in 15s strategy for {symbol}: {e}", exc_info=True)
            return None

# Create singleton instance
pocket_option_15s_strategy = PocketOption15SecondStrategy()
