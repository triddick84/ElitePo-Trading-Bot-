"""
ProvenSignals.io - 15 Second RSI Strategy
Settings: RSI Period 5 (not 14), Line Chart preferred

ENTRY RULES:
- BUY: RSI crosses above oversold line (30) with price divergence
- SELL: RSI crosses below overbought line (70) with price divergence

Best for: OTC currencies and stocks, trend reversals
High frequency strategy for catching reversal points with divergence confirmation
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 5) -> pd.Series:
    """
    Calculate RSI indicator
    
    Args:
        prices: Price series
        period: RSI period (5 for ProvenSignals strategy, not default 14)
    
    Returns:
        RSI series
    """
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        return pd.Series([50] * len(prices), index=prices.index)


def detect_divergence(prices: pd.Series, indicator: pd.Series, lookback: int = 10) -> Dict[str, bool]:
    """
    Detect bullish/bearish divergence between price and indicator
    
    Args:
        prices: Price series
        indicator: Indicator series (RSI)
        lookback: Number of bars to look back
    
    Returns:
        Dict with bullish and bearish divergence flags
    """
    try:
        if len(prices) < lookback + 5:
            return {'bullish': False, 'bearish': False}
        
        recent_prices = prices.tail(lookback)
        recent_indicator = indicator.tail(lookback)
        
        # Find price lows and highs
        price_min_idx = recent_prices.idxmin()
        price_max_idx = recent_prices.idxmax()
        
        # Find indicator lows and highs
        indicator_min_idx = recent_indicator.idxmin()
        indicator_max_idx = recent_indicator.idxmax()
        
        # Bullish divergence: Price makes lower low, but RSI makes higher low
        bullish_divergence = False
        if price_min_idx < recent_prices.index[-1]:
            prev_price_low = recent_prices[price_min_idx]
            current_price = recent_prices.iloc[-1]
            prev_rsi_low = recent_indicator[price_min_idx] if price_min_idx in recent_indicator.index else recent_indicator.iloc[0]
            current_rsi = recent_indicator.iloc[-1]
            
            if current_price < prev_price_low and current_rsi > prev_rsi_low:
                bullish_divergence = True
                logger.info(f"🔄 Bullish divergence detected: Price {prev_price_low:.5f}→{current_price:.5f}, RSI {prev_rsi_low:.1f}→{current_rsi:.1f}")
        
        # Bearish divergence: Price makes higher high, but RSI makes lower high
        bearish_divergence = False
        if price_max_idx < recent_prices.index[-1]:
            prev_price_high = recent_prices[price_max_idx]
            current_price = recent_prices.iloc[-1]
            prev_rsi_high = recent_indicator[price_max_idx] if price_max_idx in recent_indicator.index else recent_indicator.iloc[0]
            current_rsi = recent_indicator.iloc[-1]
            
            if current_price > prev_price_high and current_rsi < prev_rsi_high:
                bearish_divergence = True
                logger.info(f"🔄 Bearish divergence detected: Price {prev_price_high:.5f}→{current_price:.5f}, RSI {prev_rsi_high:.1f}→{current_rsi:.1f}")
        
        return {'bullish': bullish_divergence, 'bearish': bearish_divergence}
    
    except Exception as e:
        logger.error(f"Error detecting divergence: {e}")
        return {'bullish': False, 'bearish': False}


def analyze_15s_proven_rsi(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Analyze using ProvenSignals.io 15s RSI Strategy
    
    Strategy:
    - BUY: RSI crosses above 30 (oversold) with bullish divergence
    - SELL: RSI crosses below 70 (overbought) with bearish divergence
    - Settings: RSI Period 5 (not 14 - more sensitive for short timeframes)
    
    Args:
        symbol: Trading symbol
        df: DataFrame with OHLC data
        current_price: Current market price
    
    Returns:
        Signal dict with direction, confidence, and analysis
    """
    try:
        if df is None or len(df) < 25:
            logger.warning(f"Insufficient data for ProvenSignals RSI strategy: {len(df) if df is not None else 0} bars")
            return None
        
        # Calculate RSI with Period 5 (ProvenSignals setting)
        df['rsi'] = calculate_rsi(df['close'], period=5)
        
        # Get recent values
        current_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        prev_2_rsi = df['rsi'].iloc[-3]
        
        current_close = df['close'].iloc[-1]
        
        logger.info(f"📊 RSI(5): Current={current_rsi:.1f}, Prev={prev_rsi:.1f}, Prev2={prev_2_rsi:.1f}")
        
        # Detect divergence
        divergence = detect_divergence(df['close'], df['rsi'], lookback=10)
        
        signal_direction = None
        confidence = 50
        reason = ""
        
        # BUY SIGNAL: RSI crosses above 30 (oversold line)
        if current_rsi > 30 and prev_rsi <= 30:
            if divergence['bullish']:
                # Strong signal with bullish divergence
                signal_direction = "CALL"
                confidence = 92
                reason = f"RSI crossed above oversold (30) WITH bullish divergence. RSI: {current_rsi:.1f}"
                logger.info(f"🟢 STRONG BUY SIGNAL (ProvenSignals RSI): {reason}")
            else:
                # Regular signal without divergence
                signal_direction = "CALL"
                confidence = 78
                reason = f"RSI crossed above oversold (30). RSI: {current_rsi:.1f}"
                logger.info(f"🟢 BUY SIGNAL (ProvenSignals RSI): {reason}")
        
        # SELL SIGNAL: RSI crosses below 70 (overbought line)
        elif current_rsi < 70 and prev_rsi >= 70:
            if divergence['bearish']:
                # Strong signal with bearish divergence
                signal_direction = "PUT"
                confidence = 92
                reason = f"RSI crossed below overbought (70) WITH bearish divergence. RSI: {current_rsi:.1f}"
                logger.info(f"🔴 STRONG SELL SIGNAL (ProvenSignals RSI): {reason}")
            else:
                # Regular signal without divergence
                signal_direction = "PUT"
                confidence = 78
                reason = f"RSI crossed below overbought (70). RSI: {current_rsi:.1f}"
                logger.info(f"🔴 SELL SIGNAL (ProvenSignals RSI): {reason}")
        
        # Additional signals: Deep oversold/overbought without cross
        elif current_rsi < 20 and divergence['bullish']:
            signal_direction = "CALL"
            confidence = 85
            reason = f"RSI deeply oversold ({current_rsi:.1f}) with bullish divergence"
            logger.info(f"🟢 BUY SIGNAL (ProvenSignals RSI - deep oversold): {reason}")
        elif current_rsi > 80 and divergence['bearish']:
            signal_direction = "PUT"
            confidence = 85
            reason = f"RSI deeply overbought ({current_rsi:.1f}) with bearish divergence"
            logger.info(f"🔴 SELL SIGNAL (ProvenSignals RSI - deep overbought): {reason}")
        
        # Enhance confidence based on RSI momentum
        if signal_direction:
            # Calculate RSI change rate
            rsi_change = abs(current_rsi - prev_rsi)
            if rsi_change > 5:
                confidence = min(confidence + 3, 95)
                reason += f" | Strong RSI momentum (change: {rsi_change:.1f})"
            
            # Check if RSI is trending away from extreme
            if signal_direction == "CALL" and current_rsi > prev_rsi > prev_2_rsi:
                confidence = min(confidence + 3, 95)
                reason += " | RSI trending up"
            elif signal_direction == "PUT" and current_rsi < prev_rsi < prev_2_rsi:
                confidence = min(confidence + 3, 95)
                reason += " | RSI trending down"
        
        # No signal if RSI in neutral zone (30-70)
        if signal_direction is None:
            logger.info(f"⏸️ No ProvenSignals RSI signal. RSI in neutral zone: {current_rsi:.1f}")
            return None
        
        return {
            'direction': signal_direction,
            'confidence': confidence,
            'reason': reason,
            'indicators': {
                'rsi': current_rsi,
                'rsi_prev': prev_rsi,
                'oversold_level': 30,
                'overbought_level': 70,
                'bullish_divergence': divergence['bullish'],
                'bearish_divergence': divergence['bearish']
            },
            'strategy': 'ProvenSignals RSI 15s'
        }
    
    except Exception as e:
        logger.error(f"Error in ProvenSignals RSI analysis: {e}")
        return None


# Main entry point for strategy execution
def execute_strategy(symbol: str, df: pd.DataFrame, current_price: float) -> Optional[Dict[str, Any]]:
    """
    Main entry point for ProvenSignals RSI 15s strategy
    """
    return analyze_15s_proven_rsi(symbol, df, current_price)
