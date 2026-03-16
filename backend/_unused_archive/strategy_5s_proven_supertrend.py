"""
ProvenSignals.io - 5 Second SuperTrend Strategy
Settings: ATR Period 10, Multiplier 5, Line Chart preferred

ENTRY RULES:
- BUY: SuperTrend signals uptrend (indicator below price, green)
- SELL: SuperTrend signals downtrend (indicator above price, red)

Best for: Trending markets on all asset types
High frequency strategy for trend following on 5-second timeframe
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_supertrend(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 5.0) -> pd.DataFrame:
    """
    Calculate SuperTrend indicator with ProvenSignals.io settings
    
    Args:
        df: DataFrame with OHLC data
        atr_period: ATR period (10 for 5s strategy)
        multiplier: ATR multiplier (5 for 5s strategy)
    
    Returns:
        DataFrame with supertrend, supertrend_direction columns
    """
    try:
        # Calculate ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(atr_period).mean()
        
        # Calculate basic upper and lower bands
        hl2 = (df['high'] + df['low']) / 2
        basic_upperband = hl2 + (multiplier * atr)
        basic_lowerband = hl2 - (multiplier * atr)
        
        # Calculate final bands
        final_upperband = basic_upperband.copy()
        final_lowerband = basic_lowerband.copy()
        
        for i in range(atr_period, len(df)):
            if basic_upperband.iloc[i] < final_upperband.iloc[i-1] or df['close'].iloc[i-1] > final_upperband.iloc[i-1]:
                final_upperband.iloc[i] = basic_upperband.iloc[i]
            else:
                final_upperband.iloc[i] = final_upperband.iloc[i-1]
            
            if basic_lowerband.iloc[i] > final_lowerband.iloc[i-1] or df['close'].iloc[i-1] < final_lowerband.iloc[i-1]:
                final_lowerband.iloc[i] = basic_lowerband.iloc[i]
            else:
                final_lowerband.iloc[i] = final_lowerband.iloc[i-1]
        
        # Determine SuperTrend direction
        supertrend = []
        direction = []
        
        for i in range(len(df)):
            if i < atr_period:
                supertrend.append(np.nan)
                direction.append(0)
            else:
                if df['close'].iloc[i] <= final_upperband.iloc[i]:
                    supertrend.append(final_upperband.iloc[i])
                    direction.append(-1)  # Downtrend
                else:
                    supertrend.append(final_lowerband.iloc[i])
                    direction.append(1)   # Uptrend
        
        df['supertrend'] = supertrend
        df['supertrend_direction'] = direction
        
        return df
    
    except Exception as e:
        logger.error(f"Error calculating SuperTrend: {e}")
        df['supertrend'] = df['close']
        df['supertrend_direction'] = 0
        return df


def analyze_5s_proven_supertrend(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Analyze using ProvenSignals.io 5s SuperTrend Strategy
    
    Strategy:
    - BUY: SuperTrend in uptrend (direction = 1, green)
    - SELL: SuperTrend in downtrend (direction = -1, red)
    - Settings: ATR Period 10, Multiplier 5
    
    Args:
        symbol: Trading symbol
        df: DataFrame with OHLC data
        current_price: Current market price
    
    Returns:
        Signal dict with direction, confidence, and analysis
    """
    try:
        if df is None or len(df) < 20:
            logger.warning(f"Insufficient data for ProvenSignals SuperTrend strategy: {len(df) if df is not None else 0} bars")
            return None
        
        # Calculate SuperTrend (ATR Period 10, Multiplier 5)
        df = calculate_supertrend(df, atr_period=10, multiplier=5.0)
        
        # Get recent values
        current_direction = df['supertrend_direction'].iloc[-1]
        prev_direction = df['supertrend_direction'].iloc[-2]
        
        supertrend_value = df['supertrend'].iloc[-1]
        current_close = df['close'].iloc[-1]
        
        logger.info(f"📊 SuperTrend: Direction={current_direction}, Value={supertrend_value:.5f}, Price={current_close:.5f}")
        
        signal_direction = None
        confidence = 50
        reason = ""
        
        # Detect trend change (signal generation point)
        trend_changed = current_direction != prev_direction
        
        # BUY SIGNAL: SuperTrend in uptrend (direction = 1)
        if current_direction == 1:
            if trend_changed:
                # Fresh buy signal (trend just changed)
                signal_direction = "CALL"
                confidence = 90
                reason = f"SuperTrend switched to UPTREND (fresh signal). Price: {current_close:.5f}, ST: {supertrend_value:.5f}"
                logger.info(f"🟢 STRONG BUY SIGNAL (ProvenSignals SuperTrend): {reason}")
            else:
                # Continuation of uptrend
                signal_direction = "CALL"
                confidence = 75
                reason = f"SuperTrend in UPTREND (continuation). Price: {current_close:.5f}, ST: {supertrend_value:.5f}"
                logger.info(f"🟢 BUY SIGNAL (ProvenSignals SuperTrend): {reason}")
        
        # SELL SIGNAL: SuperTrend in downtrend (direction = -1)
        elif current_direction == -1:
            if trend_changed:
                # Fresh sell signal (trend just changed)
                signal_direction = "PUT"
                confidence = 90
                reason = f"SuperTrend switched to DOWNTREND (fresh signal). Price: {current_close:.5f}, ST: {supertrend_value:.5f}"
                logger.info(f"🔴 STRONG SELL SIGNAL (ProvenSignals SuperTrend): {reason}")
            else:
                # Continuation of downtrend
                signal_direction = "PUT"
                confidence = 75
                reason = f"SuperTrend in DOWNTREND (continuation). Price: {current_close:.5f}, ST: {supertrend_value:.5f}"
                logger.info(f"🔴 SELL SIGNAL (ProvenSignals SuperTrend): {reason}")
        
        # Enhance confidence based on distance from SuperTrend line
        if signal_direction:
            distance = abs(current_close - supertrend_value) / current_close * 100
            if distance > 0.2:
                confidence = min(confidence + 5, 95)
                reason += f" | Strong trend (distance: {distance:.3f}%)"
            
            # Calculate trend strength from last few bars
            trend_bars = df['supertrend_direction'].tail(5)
            trend_consistency = (trend_bars == current_direction).sum()
            if trend_consistency >= 4:
                confidence = min(confidence + 5, 95)
                reason += f" | Consistent trend ({trend_consistency}/5 bars)"
        
        # No signal if direction is neutral
        if signal_direction is None:
            logger.info(f"⏸️ No ProvenSignals SuperTrend signal. Neutral direction.")
            return None
        
        return {
            'direction': signal_direction,
            'confidence': confidence,
            'reason': reason,
            'indicators': {
                'supertrend': supertrend_value,
                'direction': 'UP' if current_direction == 1 else 'DOWN',
                'trend_changed': trend_changed,
                'current_price': current_close
            },
            'strategy': 'ProvenSignals SuperTrend 5s'
        }
    
    except Exception as e:
        logger.error(f"Error in ProvenSignals SuperTrend analysis: {e}")
        return None


# Main entry point for strategy execution
def execute_strategy(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Main entry point for ProvenSignals SuperTrend 5s strategy
    """
    return analyze_5s_proven_supertrend(symbol, df, current_price)
