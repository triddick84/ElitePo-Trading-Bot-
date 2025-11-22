"""
Stochastic Oscillator 5-Second Divergence Strategy
Optimized for Pocket Option binary options trading

STRATEGY RULES:
- %K Period: 14
- %D Period: 3
- Smoothing: 14
- Moving Average: SMA
- Uses only %D line (smoothed Stochastic)

ENTRY SIGNALS:
- BUY: Stochastic breaks above 20 line WITH divergence (price lower low, Stochastic higher low)
- SELL: Stochastic breaks below 80 line WITH divergence (price higher high, Stochastic lower high)

Best for: OTC currencies and stocks in trending and sideways markets
High win rate strategy based on mean-reversion and divergence confirmation
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_stochastic_oscillator(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth_k: int = 14) -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator with specified settings
    
    Args:
        df: DataFrame with OHLC data
        k_period: Period for %K calculation (default: 14)
        d_period: Period for %D smoothing (default: 3)
        smooth_k: Smoothing period for %K (default: 14)
    
    Returns:
        DataFrame with stochastic_k and stochastic_d columns
    """
    try:
        # Calculate raw %K
        low_min = df['low'].rolling(window=k_period, min_periods=1).min()
        high_max = df['high'].rolling(window=k_period, min_periods=1).max()
        
        stochastic_k_raw = 100 * ((df['close'] - low_min) / (high_max - low_min))
        
        # Smooth %K with SMA
        stochastic_k = stochastic_k_raw.rolling(window=smooth_k, min_periods=1).mean()
        
        # Calculate %D (SMA of smoothed %K)
        stochastic_d = stochastic_k.rolling(window=d_period, min_periods=1).mean()
        
        df['stochastic_k'] = stochastic_k
        df['stochastic_d'] = stochastic_d
        
        return df
    
    except Exception as e:
        logger.error(f"Error calculating Stochastic Oscillator: {e}")
        df['stochastic_k'] = 50
        df['stochastic_d'] = 50
        return df


def detect_bullish_divergence(df: pd.DataFrame, lookback: int = 10) -> bool:
    """
    Detect bullish divergence: Price makes lower low, but Stochastic makes higher low
    
    Args:
        df: DataFrame with price and stochastic data
        lookback: Number of bars to look back for divergence
    
    Returns:
        True if bullish divergence detected
    """
    try:
        if len(df) < lookback + 5:
            return False
        
        recent_df = df.tail(lookback).copy()
        
        # Find the lowest price point in the lookback period
        price_low_idx = recent_df['low'].idxmin()
        price_low = recent_df.loc[price_low_idx, 'low']
        
        # Find the previous low before the current lowest
        before_low = recent_df.loc[:price_low_idx]['low'].min() if price_low_idx > recent_df.index[0] else price_low
        
        # Check if current low is lower than previous low (price making lower low)
        if price_low >= before_low:
            return False
        
        # Get corresponding Stochastic values
        stoch_at_current_low = recent_df.loc[price_low_idx, 'stochastic_d']
        stoch_before = recent_df.loc[:price_low_idx]['stochastic_d'].min() if price_low_idx > recent_df.index[0] else stoch_at_current_low
        
        # Bullish divergence: Price lower low, but Stochastic higher low
        divergence_detected = stoch_at_current_low > stoch_before
        
        if divergence_detected:
            logger.info(f"🔄 Bullish divergence detected: Price low {price_low:.5f} < Previous {before_low:.5f}, "
                       f"but Stochastic {stoch_at_current_low:.2f} > Previous {stoch_before:.2f}")
        
        return divergence_detected
    
    except Exception as e:
        logger.error(f"Error detecting bullish divergence: {e}")
        return False


def detect_bearish_divergence(df: pd.DataFrame, lookback: int = 10) -> bool:
    """
    Detect bearish divergence: Price makes higher high, but Stochastic makes lower high
    
    Args:
        df: DataFrame with price and stochastic data
        lookback: Number of bars to look back for divergence
    
    Returns:
        True if bearish divergence detected
    """
    try:
        if len(df) < lookback + 5:
            return False
        
        recent_df = df.tail(lookback).copy()
        
        # Find the highest price point in the lookback period
        price_high_idx = recent_df['high'].idxmax()
        price_high = recent_df.loc[price_high_idx, 'high']
        
        # Find the previous high before the current highest
        before_high = recent_df.loc[:price_high_idx]['high'].max() if price_high_idx > recent_df.index[0] else price_high
        
        # Check if current high is higher than previous high (price making higher high)
        if price_high <= before_high:
            return False
        
        # Get corresponding Stochastic values
        stoch_at_current_high = recent_df.loc[price_high_idx, 'stochastic_d']
        stoch_before = recent_df.loc[:price_high_idx]['stochastic_d'].max() if price_high_idx > recent_df.index[0] else stoch_at_current_high
        
        # Bearish divergence: Price higher high, but Stochastic lower high
        divergence_detected = stoch_at_current_high < stoch_before
        
        if divergence_detected:
            logger.info(f"🔄 Bearish divergence detected: Price high {price_high:.5f} > Previous {before_high:.5f}, "
                       f"but Stochastic {stoch_at_current_high:.2f} < Previous {stoch_before:.2f}")
        
        return divergence_detected
    
    except Exception as e:
        logger.error(f"Error detecting bearish divergence: {e}")
        return False


def analyze_5s_stochastic_divergence(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Analyze 5-second Stochastic Divergence strategy
    
    Strategy:
    - BUY: Stochastic %D breaks above 20 WITH bullish divergence
    - SELL: Stochastic %D breaks below 80 WITH bearish divergence
    
    Args:
        symbol: Trading symbol
        df: DataFrame with OHLC data
        current_price: Current market price
    
    Returns:
        Signal dict with direction, confidence, and analysis
    """
    try:
        if df is None or len(df) < 50:
            logger.warning(f"Insufficient data for Stochastic Divergence analysis: {len(df) if df is not None else 0} bars")
            return None
        
        # Calculate Stochastic Oscillator with specified settings
        df = calculate_stochastic_oscillator(df, k_period=14, d_period=3, smooth_k=14)
        
        # Get recent Stochastic %D values
        current_stoch_d = df['stochastic_d'].iloc[-1]
        prev_stoch_d = df['stochastic_d'].iloc[-2]
        prev_2_stoch_d = df['stochastic_d'].iloc[-3]
        
        logger.info(f"📊 Stochastic %D: Current={current_stoch_d:.2f}, Prev={prev_stoch_d:.2f}, Prev2={prev_2_stoch_d:.2f}")
        
        signal_direction = None
        confidence = 50
        reason = ""
        
        # BUY SIGNAL: Stochastic breaks above 20 with bullish divergence
        if current_stoch_d > 20 and prev_stoch_d <= 20:
            # Check for bullish divergence
            has_divergence = detect_bullish_divergence(df, lookback=10)
            
            if has_divergence:
                signal_direction = "CALL"
                # Calculate confidence based on how oversold it was
                oversold_strength = max(0, 20 - prev_2_stoch_d) / 20  # 0 to 1
                confidence = 75 + (oversold_strength * 20)  # 75-95%
                reason = f"Stochastic broke above oversold (20) with bullish divergence. Stoch: {current_stoch_d:.1f}"
                logger.info(f"🟢 BUY SIGNAL: {reason}, Confidence: {confidence:.1f}%")
        
        # SELL SIGNAL: Stochastic breaks below 80 with bearish divergence
        elif current_stoch_d < 80 and prev_stoch_d >= 80:
            # Check for bearish divergence
            has_divergence = detect_bearish_divergence(df, lookback=10)
            
            if has_divergence:
                signal_direction = "PUT"
                # Calculate confidence based on how overbought it was
                overbought_strength = max(0, prev_2_stoch_d - 80) / 20  # 0 to 1
                confidence = 75 + (overbought_strength * 20)  # 75-95%
                reason = f"Stochastic broke below overbought (80) with bearish divergence. Stoch: {current_stoch_d:.1f}"
                logger.info(f"🔴 SELL SIGNAL: {reason}, Confidence: {confidence:.1f}%")
        
        # No signal if conditions not met
        if signal_direction is None:
            logger.info(f"⏸️ No Stochastic Divergence signal. Stoch %D: {current_stoch_d:.2f} (waiting for break + divergence)")
            return None
        
        return {
            'direction': signal_direction,
            'confidence': min(confidence, 95),  # Cap at 95%
            'reason': reason,
            'indicators': {
                'stochastic_d': current_stoch_d,
                'stochastic_k': df['stochastic_k'].iloc[-1],
                'oversold_level': 20,
                'overbought_level': 80
            },
            'strategy': 'Stochastic Divergence 5s'
        }
    
    except Exception as e:
        logger.error(f"Error in Stochastic Divergence analysis: {e}")
        return None


# Main entry point for strategy execution
def execute_strategy(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Main entry point for Stochastic Divergence 5s strategy
    """
    return analyze_5s_stochastic_divergence(symbol, df, current_price)
