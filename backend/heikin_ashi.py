"""
Heikin Ashi Candle Transformation
Converts regular OHLC candles to Heikin Ashi candles for smoother trend analysis

Heikin Ashi candles filter out market noise and make trends more visible.
Particularly useful for ultra-short timeframes like 5 seconds.
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def transform_to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform regular candles to Heikin Ashi candles
    
    Heikin Ashi Formula:
    - HA Close = (Open + High + Low + Close) / 4
    - HA Open = (Previous HA Open + Previous HA Close) / 2
    - HA High = Max(High, HA Open, HA Close)
    - HA Low = Min(Low, HA Open, HA Close)
    
    Args:
        df: DataFrame with 'open', 'high', 'low', 'close' columns
        
    Returns:
        DataFrame with Heikin Ashi values, original OHLC preserved as 'orig_*'
    """
    try:
        if df is None or df.empty:
            logger.warning("Empty DataFrame provided for Heikin Ashi transformation")
            return df
        
        # Preserve original OHLC
        df['orig_open'] = df['open']
        df['orig_high'] = df['high']
        df['orig_low'] = df['low']
        df['orig_close'] = df['close']
        
        # Create Heikin Ashi columns
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = pd.Series(index=df.index, dtype=float)
        
        # First candle: HA Open = (Open + Close) / 2
        ha_open.iloc[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        
        # Subsequent candles: HA Open = (Prev HA Open + Prev HA Close) / 2
        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        
        # HA High and Low
        ha_high = pd.concat([df['high'], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = pd.concat([df['low'], ha_open, ha_close], axis=1).min(axis=1)
        
        # Replace original OHLC with Heikin Ashi values
        df['open'] = ha_open
        df['high'] = ha_high
        df['low'] = ha_low
        df['close'] = ha_close
        
        logger.info(f"✅ Transformed {len(df)} candles to Heikin Ashi")
        
        return df
        
    except Exception as e:
        logger.error(f"Error transforming to Heikin Ashi: {e}")
        return df


def is_bullish_ha_candle(row: pd.Series) -> bool:
    """Check if Heikin Ashi candle is bullish (close > open)"""
    return row['close'] > row['open']


def is_bearish_ha_candle(row: pd.Series) -> bool:
    """Check if Heikin Ashi candle is bearish (close < open)"""
    return row['close'] < row['open']


def has_no_lower_wick(row: pd.Series, tolerance: float = 0.0001) -> bool:
    """Check if HA candle has no lower wick (strong uptrend)"""
    return abs(row['low'] - min(row['open'], row['close'])) < tolerance


def has_no_upper_wick(row: pd.Series, tolerance: float = 0.0001) -> bool:
    """Check if HA candle has no upper wick (strong downtrend)"""
    return abs(row['high'] - max(row['open'], row['close'])) < tolerance


def detect_ha_trend_strength(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Analyze Heikin Ashi trend strength
    
    Returns:
        Dict with:
            - consecutive_bullish: Number of consecutive bullish HA candles
            - consecutive_bearish: Number of consecutive bearish HA candles
            - trend: 'STRONG_UP', 'STRONG_DOWN', 'WEAK', or 'NEUTRAL'
            - strength: 0-1 score
    """
    try:
        if len(df) < lookback:
            return {'consecutive_bullish': 0, 'consecutive_bearish': 0, 'trend': 'NEUTRAL', 'strength': 0}
        
        # Count consecutive bullish candles
        consecutive_bullish = 0
        for i in range(len(df) - 1, -1, -1):
            if is_bullish_ha_candle(df.iloc[i]):
                consecutive_bullish += 1
            else:
                break
        
        # Count consecutive bearish candles
        consecutive_bearish = 0
        for i in range(len(df) - 1, -1, -1):
            if is_bearish_ha_candle(df.iloc[i]):
                consecutive_bearish += 1
            else:
                break
        
        # Determine trend strength
        if consecutive_bullish >= 3:
            trend = 'STRONG_UP'
            strength = min(consecutive_bullish / 5, 1.0)
        elif consecutive_bearish >= 3:
            trend = 'STRONG_DOWN'
            strength = min(consecutive_bearish / 5, 1.0)
        elif consecutive_bullish >= 2:
            trend = 'WEAK_UP'
            strength = 0.5
        elif consecutive_bearish >= 2:
            trend = 'WEAK_DOWN'
            strength = 0.5
        else:
            trend = 'NEUTRAL'
            strength = 0
        
        return {
            'consecutive_bullish': consecutive_bullish,
            'consecutive_bearish': consecutive_bearish,
            'trend': trend,
            'strength': strength
        }
        
    except Exception as e:
        logger.error(f"Error detecting HA trend strength: {e}")
        return {'consecutive_bullish': 0, 'consecutive_bearish': 0, 'trend': 'NEUTRAL', 'strength': 0}
