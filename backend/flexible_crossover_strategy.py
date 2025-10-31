"""
30-Second Moving Average Crossover Strategy
Based on user specification with flexible timeframe support

Indicators:
- 6 SMA and 12 SMA crossover
- SuperTrend (ATR 2, Multiplier 2.2)
- Awesome Oscillator (6/12 periods) - Line version

BUY Signal: 6 SMA crosses above 12 SMA + AO moving up to 0 + SuperTrend buy
SELL Signal: 6 SMA crosses below 12 SMA + AO moving down to 0 + SuperTrend sell
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, Optional, List, Tuple
import talib

logger = logging.getLogger(__name__)

class FlexibleCrossoverStrategy:
    """
    Flexible Moving Average Crossover Strategy
    Supports multiple chart timeframes (5s, 10s, 15s, 30s, 1m, 2m, 3m, 5m)
    """
    
    def __init__(self, chart_timeframe: str = '30s', sma_fast: int = 6, sma_slow: int = 12,
                 supertrend_atr_period: int = 2, supertrend_multiplier: float = 2.2,
                 ao_short_period: int = 6, ao_long_period: int = 12):
        self.chart_timeframe = chart_timeframe
        
        # User-specified indicator parameters (now customizable)
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.supertrend_atr_period = supertrend_atr_period
        self.supertrend_multiplier = supertrend_multiplier
        self.ao_short_period = ao_short_period
        self.ao_long_period = ao_long_period
        
        # Minimum data points needed
        self.min_data_points = 50
        
        logger.info(f"✅ Flexible Crossover Strategy initialized for {chart_timeframe}")
        logger.info(f"   SMA: {self.sma_fast}/{self.sma_slow}, SuperTrend: ATR({self.supertrend_atr_period}), Mult({self.supertrend_multiplier})")
        logger.info(f"   Awesome Oscillator: {self.ao_short_period}/{self.ao_long_period}")
    
    def get_real_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch real-time market data for the specified chart timeframe
        
        For ultra-short timeframes (5s-30s), we fetch 1m data and use it
        For 1m+, we fetch actual interval data
        """
        try:
            logger.info(f"📊 Fetching {self.chart_timeframe} data for {symbol}")
            
            # Map chart timeframes to yfinance intervals
            interval_map = {
                '5s': '1m',   # Use 1m data for 5s analysis
                '10s': '1m',  # Use 1m data for 10s analysis
                '15s': '1m',  # Use 1m data for 15s analysis
                '30s': '1m',  # Use 1m data for 30s analysis
                '1m': '1m',
                '2m': '2m',
                '3m': '5m',   # Use 5m data for 3m analysis
                '5m': '5m'
            }
            
            interval = interval_map.get(self.chart_timeframe, '1m')
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period='1d', interval=interval)
            
            if df is None or len(df) < self.min_data_points:
                logger.error(f"Insufficient data for {symbol}")
                return None
            
            # Verify data is recent
            latest_data_time = df.index[-1]
            current_time = datetime.now(timezone.utc)
            data_age_seconds = (current_time - latest_data_time).total_seconds()
            
            if data_age_seconds > 300:
                logger.error(f"❌ DATA TOO OLD: {data_age_seconds:.0f}s")
                return None
            
            logger.info(f"✅ Got {len(df)} candles for {symbol}, age: {data_age_seconds:.1f}s")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return pd.Series(talib.SMA(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_supertrend(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate SuperTrend indicator
        
        Returns:
        - supertrend: the supertrend line
        - trend: 1 for uptrend (buy), -1 for downtrend (sell)
        """
        try:
            high = df['High'].values
            low = df['Low'].values
            close = df['Close'].values
            
            # Calculate ATR
            atr = talib.ATR(high, low, close, timeperiod=self.supertrend_atr_period)
            
            # Calculate basic bands
            hl_avg = (high + low) / 2
            
            # Upper and lower bands
            upper_band = hl_avg + (self.supertrend_multiplier * atr)
            lower_band = hl_avg - (self.supertrend_multiplier * atr)
            
            # Initialize supertrend
            supertrend = np.zeros(len(close))
            trend = np.zeros(len(close))
            
            # First value
            supertrend[0] = upper_band[0]
            trend[0] = 1
            
            for i in range(1, len(close)):
                # Uptrend
                if close[i] > supertrend[i-1]:
                    supertrend[i] = lower_band[i]
                    trend[i] = 1
                # Downtrend
                elif close[i] < supertrend[i-1]:
                    supertrend[i] = upper_band[i]
                    trend[i] = -1
                # Continue previous trend
                else:
                    supertrend[i] = supertrend[i-1]
                    trend[i] = trend[i-1]
            
            return pd.Series(supertrend, index=df.index), pd.Series(trend, index=df.index)
            
        except Exception as e:
            logger.error(f"Error calculating SuperTrend: {e}")
            return pd.Series([0]*len(df), index=df.index), pd.Series([0]*len(df), index=df.index)
    
    def calculate_awesome_oscillator(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Awesome Oscillator (Bill Williams)
        AO = SMA(median price, short) - SMA(median price, long)
        
        Returns line values (not histogram)
        """
        try:
            # Median price (HL/2)
            median_price = (df['High'] + df['Low']) / 2
            
            # Calculate SMAs
            sma_short = talib.SMA(median_price.values, timeperiod=self.ao_short_period)
            sma_long = talib.SMA(median_price.values, timeperiod=self.ao_long_period)
            
            # AO = short SMA - long SMA
            ao = sma_short - sma_long
            
            return pd.Series(ao, index=df.index)
            
        except Exception as e:
            logger.error(f"Error calculating Awesome Oscillator: {e}")
            return pd.Series([0]*len(df), index=df.index)
    
    def generate_signal(self, symbol: str, trade_duration_seconds: int = 82) -> Optional[Dict]:
        """
        Generate trading signal with custom trade duration
        
        Args:
        - symbol: trading pair
        - trade_duration_seconds: signal expiration time in seconds (e.g., 82 = 1m 22s)
        
        Returns signal with all confirmations
        """
        try:
            # Fetch market data
            df = self.get_real_market_data(symbol)
            if df is None:
                return None
            
            close = df['Close']
            
            # Calculate all indicators
            sma_fast = self.calculate_sma(close, self.sma_fast)
            sma_slow = self.calculate_sma(close, self.sma_slow)
            supertrend, trend = self.calculate_supertrend(df)
            ao = self.calculate_awesome_oscillator(df)
            
            # Get current values
            current_sma_fast = sma_fast.iloc[-1]
            current_sma_slow = sma_slow.iloc[-1]
            prev_sma_fast = sma_fast.iloc[-2]
            prev_sma_slow = sma_slow.iloc[-2]
            
            current_supertrend = trend.iloc[-1]
            
            current_ao = ao.iloc[-1]
            prev_ao = ao.iloc[-2]
            prev_prev_ao = ao.iloc[-3] if len(ao) >= 3 else prev_ao
            
            # Check for NaN
            if pd.isna([current_sma_fast, current_sma_slow, current_supertrend, current_ao]).any():
                logger.warning(f"NaN values in indicators for {symbol}")
                return None
            
            logger.info(f"🎯 Crossover Analysis for {symbol} ({self.chart_timeframe}):")
            logger.info(f"   SMA Fast: {current_sma_fast:.5f} (prev: {prev_sma_fast:.5f})")
            logger.info(f"   SMA Slow: {current_sma_slow:.5f} (prev: {prev_sma_slow:.5f})")
            logger.info(f"   SuperTrend: {'BUY' if current_supertrend == 1 else 'SELL'}")
            logger.info(f"   AO: {current_ao:.5f} (prev: {prev_ao:.5f})")
            
            signal = None
            confidence = 85  # Base confidence
            reasoning = []
            
            # === BUY SIGNAL CONDITIONS ===
            # 1. 6 SMA crosses above 12 SMA
            sma_bullish_cross = prev_sma_fast <= prev_sma_slow and current_sma_fast > current_sma_slow
            
            # 2. Awesome Oscillator moving towards 0 from below (upward momentum)
            ao_moving_up = current_ao > prev_ao and prev_ao > prev_prev_ao  # Consistent upward
            ao_below_zero_moving_up = current_ao < 0 and ao_moving_up  # Below 0 but rising towards it
            
            # 3. SuperTrend shows BUY
            supertrend_buy = current_supertrend == 1
            
            if sma_bullish_cross and ao_below_zero_moving_up and supertrend_buy:
                signal = "CALL"
                reasoning.append(f"🟢 BUY: 6 SMA ({current_sma_fast:.5f}) crossed above 12 SMA ({current_sma_slow:.5f})")
                reasoning.append(f"📈 AO moving UP towards 0: {current_ao:.5f} (from {prev_ao:.5f})")
                reasoning.append(f"✅ SuperTrend: BUY signal")
                confidence += 10
                logger.info(f"✅ BUY SIGNAL: All 3 confirmations met")
            
            # === SELL SIGNAL CONDITIONS ===
            # 1. 6 SMA crosses below 12 SMA
            sma_bearish_cross = prev_sma_fast >= prev_sma_slow and current_sma_fast < current_sma_slow
            
            # 2. Awesome Oscillator moving towards 0 from above (downward momentum)
            ao_moving_down = current_ao < prev_ao and prev_ao < prev_prev_ao  # Consistent downward
            ao_above_zero_moving_down = current_ao > 0 and ao_moving_down  # Above 0 but falling towards it
            
            # 3. SuperTrend shows SELL
            supertrend_sell = current_supertrend == -1
            
            if sma_bearish_cross and ao_above_zero_moving_down and supertrend_sell:
                signal = "PUT"
                reasoning.append(f"🔴 SELL: 6 SMA ({current_sma_fast:.5f}) crossed below 12 SMA ({current_sma_slow:.5f})")
                reasoning.append(f"📉 AO moving DOWN towards 0: {current_ao:.5f} (from {prev_ao:.5f})")
                reasoning.append(f"✅ SuperTrend: SELL signal")
                confidence += 10
                logger.info(f"✅ SELL SIGNAL: All 3 confirmations met")
            
            # No signal if conditions not met
            if signal is None:
                logger.info(f"⛔ NO SIGNAL: Not all conditions met")
                logger.info(f"   SMA Cross: Bull={sma_bullish_cross}, Bear={sma_bearish_cross}")
                logger.info(f"   AO: {current_ao:.5f} (moving {'up' if current_ao > prev_ao else 'down'})")
                logger.info(f"   SuperTrend: {'BUY' if supertrend_buy else 'SELL'}")
                return None
            
            # Calculate trade duration in human-readable format
            duration_minutes = trade_duration_seconds // 60
            duration_seconds = trade_duration_seconds % 60
            duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_minutes > 0 else f"{duration_seconds}s"
            
            return {
                "signal": signal,
                "confidence": min(98, confidence),
                "reasoning": reasoning,
                "analysis": {
                    "sma_fast": current_sma_fast,
                    "sma_slow": current_sma_slow,
                    "sma_cross": "bullish" if sma_bullish_cross else ("bearish" if sma_bearish_cross else "none"),
                    "supertrend": "BUY" if supertrend_buy else "SELL",
                    "awesome_oscillator": current_ao,
                    "ao_direction": "UP" if ao_moving_up else ("DOWN" if ao_moving_down else "FLAT")
                },
                "strategy": "Moving Average Crossover (Flexible)",
                "chart_timeframe": self.chart_timeframe,
                "trade_duration_seconds": trade_duration_seconds,
                "trade_duration_text": duration_text
            }
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            import traceback
            traceback.print_exc()
            return None


# Global instance (will be recreated for each timeframe)
_flexible_strategy = None

def get_flexible_strategy(chart_timeframe: str = '30s') -> FlexibleCrossoverStrategy:
    """Get or create Flexible Crossover Strategy for specified timeframe"""
    global _flexible_strategy
    # Always create new instance to support different timeframes
    _flexible_strategy = FlexibleCrossoverStrategy(chart_timeframe)
    return _flexible_strategy
