"""
SuperTrend Indicator for Pocket Option Binary Options Trading
Optimized for ultra-short timeframes (5s, 15s)

SuperTrend is a trend-following indicator that helps:
- Identify current trend direction (UP or DOWN)
- Avoid counter-trend signals
- Confirm support/resistance breakouts
- Filter false signals during trend reversals

Based on research for Pocket Option binary options:
- 5s timeframe: ATR period = 10, Multiplier = 5
- 15s timeframe: ATR period = 7, Multiplier = 2
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SuperTrendIndicator:
    """
    SuperTrend indicator implementation for binary options
    
    SuperTrend uses ATR (Average True Range) to plot dynamic support/resistance lines
    that adapt to volatility and help identify trend direction.
    """
    
    def __init__(self, timeframe: str = '5s'):
        """
        Initialize SuperTrend with optimal settings for timeframe
        
        Args:
            timeframe: Trading timeframe ('5s', '15s', '30s', '1m', etc.)
        """
        self.timeframe = timeframe
        
        # Optimal settings based on Pocket Option research
        if timeframe == '5s':
            self.atr_period = 10  # Higher period for noise reduction
            self.multiplier = 5.0  # Higher multiplier to filter false signals
        elif timeframe == '15s':
            self.atr_period = 7   # Balance between sensitivity and stability
            self.multiplier = 2.0  # Lower multiplier for faster response
        elif timeframe == '30s':
            self.atr_period = 7
            self.multiplier = 2.5
        elif timeframe == '1m':
            self.atr_period = 10
            self.multiplier = 3.0  # Standard setting
        else:
            # Default for longer timeframes
            self.atr_period = 10
            self.multiplier = 3.0
        
        logger.info(f"SuperTrend initialized for {timeframe}: ATR={self.atr_period}, Multiplier={self.multiplier}")
    
    def calculate_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate SuperTrend indicator values
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with added columns:
                - 'supertrend': SuperTrend line value
                - 'supertrend_direction': 1 for uptrend, -1 for downtrend
                - 'supertrend_signal': 'BUY' or 'SELL' on trend change
        """
        try:
            if df is None or df.empty or len(df) < self.atr_period + 5:
                logger.warning(f"Insufficient data for SuperTrend calculation (need {self.atr_period + 5}+ candles)")
                return df
            
            # Ensure required columns exist
            required_cols = ['high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Missing required columns for SuperTrend. Need: {required_cols}")
                return df
            
            # Calculate ATR (Average True Range)
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)
            
            # Calculate basic upper and lower bands
            hl_avg = (df['high'] + df['low']) / 2
            basic_upper_band = hl_avg + (self.multiplier * atr)
            basic_lower_band = hl_avg - (self.multiplier * atr)
            
            # Initialize final bands
            final_upper_band = pd.Series(index=df.index, dtype=float)
            final_lower_band = pd.Series(index=df.index, dtype=float)
            supertrend = pd.Series(index=df.index, dtype=float)
            direction = pd.Series(index=df.index, dtype=int)
            
            # Calculate final bands with comparison to previous values
            for i in range(len(df)):
                if i == 0:
                    final_upper_band.iloc[i] = basic_upper_band.iloc[i]
                    final_lower_band.iloc[i] = basic_lower_band.iloc[i]
                else:
                    # Final Upper Band
                    if basic_upper_band.iloc[i] < final_upper_band.iloc[i-1] or df['close'].iloc[i-1] > final_upper_band.iloc[i-1]:
                        final_upper_band.iloc[i] = basic_upper_band.iloc[i]
                    else:
                        final_upper_band.iloc[i] = final_upper_band.iloc[i-1]
                    
                    # Final Lower Band
                    if basic_lower_band.iloc[i] > final_lower_band.iloc[i-1] or df['close'].iloc[i-1] < final_lower_band.iloc[i-1]:
                        final_lower_band.iloc[i] = basic_lower_band.iloc[i]
                    else:
                        final_lower_band.iloc[i] = final_lower_band.iloc[i-1]
            
            # Determine SuperTrend line and direction
            for i in range(len(df)):
                if i == 0:
                    # Initial direction based on close vs bands
                    if df['close'].iloc[i] <= final_upper_band.iloc[i]:
                        supertrend.iloc[i] = final_upper_band.iloc[i]
                        direction.iloc[i] = -1  # Downtrend
                    else:
                        supertrend.iloc[i] = final_lower_band.iloc[i]
                        direction.iloc[i] = 1   # Uptrend
                else:
                    # Determine direction based on price crossing bands
                    if direction.iloc[i-1] == 1:  # Was in uptrend
                        if df['close'].iloc[i] <= final_lower_band.iloc[i]:
                            # Price broke below lower band - switch to downtrend
                            supertrend.iloc[i] = final_upper_band.iloc[i]
                            direction.iloc[i] = -1
                        else:
                            # Still in uptrend
                            supertrend.iloc[i] = final_lower_band.iloc[i]
                            direction.iloc[i] = 1
                    else:  # Was in downtrend
                        if df['close'].iloc[i] >= final_upper_band.iloc[i]:
                            # Price broke above upper band - switch to uptrend
                            supertrend.iloc[i] = final_lower_band.iloc[i]
                            direction.iloc[i] = 1
                        else:
                            # Still in downtrend
                            supertrend.iloc[i] = final_upper_band.iloc[i]
                            direction.iloc[i] = -1
            
            # Add to dataframe
            df['supertrend'] = supertrend
            df['supertrend_direction'] = direction
            df['supertrend_upper_band'] = final_upper_band
            df['supertrend_lower_band'] = final_lower_band
            
            # Generate signals on trend change
            df['supertrend_signal'] = None
            trend_changes = df['supertrend_direction'].diff() != 0
            for i in range(1, len(df)):
                if trend_changes.iloc[i]:
                    if df['supertrend_direction'].iloc[i] == 1:
                        df.loc[df.index[i], 'supertrend_signal'] = 'BUY'
                    else:
                        df.loc[df.index[i], 'supertrend_signal'] = 'SELL'
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating SuperTrend: {e}")
            return df
    
    def get_current_trend(self, df: pd.DataFrame) -> Dict:
        """
        Get current trend analysis from SuperTrend
        
        Returns:
            Dict with:
                - trend: 'UP', 'DOWN', or 'NEUTRAL'
                - direction: 1 (up), -1 (down), or 0 (neutral)
                - strength: 0-1 score indicating trend strength
                - distance_from_trend: % distance from SuperTrend line
                - trend_duration: Number of candles in current trend
                - is_trend_strong: Boolean indicating if trend is strong enough to trade
        """
        try:
            if 'supertrend_direction' not in df.columns:
                return {
                    'trend': 'NEUTRAL',
                    'direction': 0,
                    'strength': 0,
                    'distance_from_trend': 0,
                    'trend_duration': 0,
                    'is_trend_strong': False
                }
            
            # Get current values
            current_direction = df['supertrend_direction'].iloc[-1]
            current_close = df['close'].iloc[-1]
            current_supertrend = df['supertrend'].iloc[-1]
            
            # Calculate trend duration (consecutive candles in same direction)
            trend_duration = 1
            for i in range(len(df) - 2, -1, -1):
                if df['supertrend_direction'].iloc[i] == current_direction:
                    trend_duration += 1
                else:
                    break
            
            # Calculate distance from SuperTrend line (as percentage)
            if current_supertrend > 0:
                distance_pct = abs((current_close - current_supertrend) / current_supertrend) * 100
            else:
                distance_pct = 0
            
            # Calculate trend strength based on duration and distance
            # Longer trends and greater distance = stronger trend
            duration_score = min(trend_duration / 10, 1.0)  # Max out at 10 candles
            distance_score = min(distance_pct / 2, 1.0)     # Max out at 2% distance
            strength = (duration_score * 0.6) + (distance_score * 0.4)
            
            # Determine if trend is strong enough to trade
            # For ultra-short timeframes, need at least 3 candles in same direction
            min_duration = 3 if self.timeframe in ['5s', '15s', '30s'] else 5
            is_trend_strong = trend_duration >= min_duration and strength >= 0.5
            
            trend_name = 'UP' if current_direction == 1 else 'DOWN' if current_direction == -1 else 'NEUTRAL'
            
            return {
                'trend': trend_name,
                'direction': int(current_direction),
                'strength': round(strength, 2),
                'distance_from_trend': round(distance_pct, 2),
                'trend_duration': trend_duration,
                'is_trend_strong': is_trend_strong,
                'supertrend_value': round(current_supertrend, 5)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing current trend: {e}")
            return {
                'trend': 'NEUTRAL',
                'direction': 0,
                'strength': 0,
                'distance_from_trend': 0,
                'trend_duration': 0,
                'is_trend_strong': False
            }
    
    def should_allow_signal(self, df: pd.DataFrame, signal_direction: str) -> Dict:
        """
        Check if a signal should be allowed based on SuperTrend
        
        This prevents:
        - Counter-trend signals (selling in uptrend, buying in downtrend)
        - Signals during weak/uncertain trends
        - Signals too close to trend reversal points
        
        Args:
            df: DataFrame with SuperTrend calculated
            signal_direction: 'CALL' or 'PUT'
            
        Returns:
            Dict with:
                - allowed: Boolean
                - reason: String explanation
                - trend_info: Current trend analysis
        """
        try:
            trend_info = self.get_current_trend(df)
            
            # Convert signal to comparable format
            signal_type = 1 if signal_direction in ['CALL', 'BUY'] else -1
            
            # Check if signal aligns with trend
            trend_direction = trend_info['direction']
            
            # CRITICAL: For ultra-short timeframes, only allow signals WITH the trend
            if signal_type != trend_direction:
                return {
                    'allowed': False,
                    'reason': f'Counter-trend signal rejected: Signal={signal_direction}, Trend={trend_info["trend"]}',
                    'trend_info': trend_info
                }
            
            # Check if trend is strong enough
            if not trend_info['is_trend_strong']:
                return {
                    'allowed': False,
                    'reason': f'Weak trend rejected: Duration={trend_info["trend_duration"]}, Strength={trend_info["strength"]:.1%}',
                    'trend_info': trend_info
                }
            
            # Check if price is too far from SuperTrend line (may indicate exhaustion)
            if trend_info['distance_from_trend'] > 5.0:  # 5% threshold
                return {
                    'allowed': False,
                    'reason': f'Price too far from trend line: {trend_info["distance_from_trend"]:.2f}% away',
                    'trend_info': trend_info
                }
            
            # All checks passed
            return {
                'allowed': True,
                'reason': f'✅ Trend-aligned signal: {signal_direction} with {trend_info["trend"]} trend (strength: {trend_info["strength"]:.1%})',
                'trend_info': trend_info
            }
            
        except Exception as e:
            logger.error(f"Error checking signal allowance: {e}")
            # On error, be conservative and reject
            return {
                'allowed': False,
                'reason': f'Error in trend check: {str(e)}',
                'trend_info': {}
            }


# Factory function for easy import
def get_supertrend(timeframe: str = '5s') -> SuperTrendIndicator:
    """Get SuperTrend indicator instance for specified timeframe"""
    return SuperTrendIndicator(timeframe)
