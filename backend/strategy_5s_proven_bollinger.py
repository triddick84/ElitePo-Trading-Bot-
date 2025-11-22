"""
ProvenSignals.io - 5 Second Bollinger Bands Strategy
Settings: Period 50, Deviation 1.5, Line Chart preferred

ENTRY RULES:
- BUY: Price touches or crosses below lower Bollinger Band (oversold)
- SELL: Price touches or crosses above upper Bollinger Band (overbought)

Best for: Quick scalping on OTC currencies, crypto, stocks, indices
High frequency strategy for capturing quick reversals
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 50, std_dev: float = 1.5) -> pd.DataFrame:
    """
    Calculate Bollinger Bands with ProvenSignals.io settings
    
    Args:
        df: DataFrame with OHLC data
        period: MA period (50 for 5s strategy)
        std_dev: Standard deviation multiplier (1.5 for 5s strategy)
    
    Returns:
        DataFrame with bb_upper, bb_middle, bb_lower columns
    """
    try:
        # Calculate middle band (SMA)
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        
        # Calculate standard deviation
        rolling_std = df['close'].rolling(window=period).std()
        
        # Calculate upper and lower bands
        df['bb_upper'] = df['bb_middle'] + (rolling_std * std_dev)
        df['bb_lower'] = df['bb_middle'] - (rolling_std * std_dev)
        
        return df
    except Exception as e:
        logger.error(f"Error calculating Bollinger Bands: {e}")
        df['bb_upper'] = df['close']
        df['bb_middle'] = df['close']
        df['bb_lower'] = df['close']
        return df


def analyze_5s_proven_bollinger(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Analyze using ProvenSignals.io 5s Bollinger Bands Strategy
    
    Strategy:
    - BUY: Price touches/crosses lower band (oversold reversal)
    - SELL: Price touches/crosses upper band (overbought reversal)
    - Settings: Period 50, Deviation 1.5
    
    Args:
        symbol: Trading symbol
        df: DataFrame with OHLC data
        current_price: Current market price
    
    Returns:
        Signal dict with direction, confidence, and analysis
    """
    try:
        if df is None or len(df) < 60:
            logger.warning(f"Insufficient data for ProvenSignals Bollinger strategy: {len(df) if df is not None else 0} bars")
            return None
        
        # Calculate Bollinger Bands (Period 50, Deviation 1.5)
        df = calculate_bollinger_bands(df, period=50, std_dev=1.5)
        
        # Get recent values
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        
        bb_upper = df['bb_upper'].iloc[-1]
        bb_middle = df['bb_middle'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        
        prev_bb_upper = df['bb_upper'].iloc[-2]
        prev_bb_lower = df['bb_lower'].iloc[-2]
        
        # Calculate band width (volatility)
        band_width = (bb_upper - bb_lower) / bb_middle * 100
        
        logger.info(f"📊 BB: Upper={bb_upper:.5f}, Middle={bb_middle:.5f}, Lower={bb_lower:.5f}, Price={current_close:.5f}")
        
        signal_direction = None
        confidence = 50
        reason = ""
        
        # BUY SIGNAL: Price touches or crosses lower band (oversold)
        if current_close <= bb_lower * 1.001:  # Within 0.1% of lower band
            # Check if price bounced from lower band
            if prev_close < bb_lower and current_close > prev_close:
                signal_direction = "CALL"
                confidence = 85
                reason = f"Price bounced from lower Bollinger Band (oversold reversal). Price: {current_close:.5f}, Lower Band: {bb_lower:.5f}"
                logger.info(f"🟢 BUY SIGNAL (ProvenSignals BB): {reason}")
            elif current_close <= bb_lower:
                signal_direction = "CALL"
                confidence = 80
                reason = f"Price at lower Bollinger Band (oversold). Price: {current_close:.5f}, Lower Band: {bb_lower:.5f}"
                logger.info(f"🟢 BUY SIGNAL (ProvenSignals BB): {reason}")
        
        # SELL SIGNAL: Price touches or crosses upper band (overbought)
        elif current_close >= bb_upper * 0.999:  # Within 0.1% of upper band
            # Check if price rejected from upper band
            if prev_close > bb_upper and current_close < prev_close:
                signal_direction = "PUT"
                confidence = 85
                reason = f"Price rejected from upper Bollinger Band (overbought reversal). Price: {current_close:.5f}, Upper Band: {bb_upper:.5f}"
                logger.info(f"🔴 SELL SIGNAL (ProvenSignals BB): {reason}")
            elif current_close >= bb_upper:
                signal_direction = "PUT"
                confidence = 80
                reason = f"Price at upper Bollinger Band (overbought). Price: {current_close:.5f}, Upper Band: {bb_upper:.5f}"
                logger.info(f"🔴 SELL SIGNAL (ProvenSignals BB): {reason}")
        
        # Enhance confidence based on band width (volatility)
        if signal_direction:
            # Higher confidence in volatile markets (wider bands)
            if band_width > 2.0:
                confidence = min(confidence + 5, 95)
                reason += f" | High volatility (band width: {band_width:.2f}%)"
            
            # Distance from middle band adds confidence
            distance_from_middle = abs(current_close - bb_middle) / bb_middle * 100
            if distance_from_middle > 1.0:
                confidence = min(confidence + 5, 95)
                reason += f" | Strong deviation from middle ({distance_from_middle:.2f}%)"
        
        # No signal if price is in middle zone
        if signal_direction is None:
            distance_to_upper = (bb_upper - current_close) / bb_middle * 100
            distance_to_lower = (current_close - bb_lower) / bb_middle * 100
            logger.info(f"⏸️ No ProvenSignals BB signal. Price in middle zone. Distance to upper: {distance_to_upper:.2f}%, lower: {distance_to_lower:.2f}%")
            return None
        
        return {
            'direction': signal_direction,
            'confidence': confidence,
            'reason': reason,
            'indicators': {
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'band_width': band_width,
                'current_price': current_close
            },
            'strategy': 'ProvenSignals Bollinger Bands 5s'
        }
    
    except Exception as e:
        logger.error(f"Error in ProvenSignals Bollinger Bands analysis: {e}")
        return None


# Main entry point for strategy execution
def execute_strategy(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Main entry point for ProvenSignals Bollinger Bands 5s strategy
    """
    return analyze_5s_proven_bollinger(symbol, df, current_price)
