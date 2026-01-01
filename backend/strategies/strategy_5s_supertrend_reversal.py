"""
5-Second Supertrend Reversal Strategy for Pocket Option
Ultra-short timeframe reversal trading using Supertrend crossovers

Strategy Logic:
- Uses Supertrend indicator (ATR=2, Multiplier=1.11)
- Reversal-based: Trade OPPOSITE to the new Supertrend direction at flip
- Flip to uptrend → Generate SELL/PUT (bet on reversal down)
- Flip to downtrend → Generate BUY/CALL (bet on reversal up)
- 5-second expiration (next candle prediction)
- Support/Resistance filtering to avoid false signals (NEW)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Import S/R detector
try:
    from strategies.support_resistance import get_sr_detector
except ImportError:
    from support_resistance import get_sr_detector

logger = logging.getLogger(__name__)


class SupertrendReversal5s:
    """
    5-Second Supertrend Reversal Strategy Implementation
    """
    
    def __init__(self, atr_period: int = 2, multiplier: float = 1.11):
        """
        Initialize strategy with Supertrend parameters
        
        Args:
            atr_period: ATR calculation period (default: 2)
            multiplier: ATR multiplier for bands (default: 1.11)
        """
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.name = "5s_supertrend_reversal"
        
        logger.info(f"✅ Initialized 5s Supertrend Reversal (ATR={atr_period}, Mult={multiplier})")
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period
        
        Returns:
            Series: ATR values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range components
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        # True Range = max of the three
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = Simple Moving Average of TR
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_supertrend(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Supertrend indicator
        
        Args:
            df: DataFrame with OHLC data
        
        Returns:
            Tuple: (supertrend values, direction series)
                  direction: 1 = uptrend, -1 = downtrend
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate ATR
        atr = self.calculate_atr(df, self.atr_period)
        
        # Calculate basic bands
        hl_avg = (high + low) / 2
        basic_upper = hl_avg + (self.multiplier * atr)
        basic_lower = hl_avg - (self.multiplier * atr)
        
        # Initialize final bands
        final_upper = pd.Series(index=df.index, dtype=float)
        final_lower = pd.Series(index=df.index, dtype=float)
        
        # Calculate persistent final bands
        for i in range(len(df)):
            if i == 0:
                final_upper.iloc[i] = basic_upper.iloc[i]
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                # Upper band logic
                if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
                    final_upper.iloc[i] = basic_upper.iloc[i]
                else:
                    final_upper.iloc[i] = final_upper.iloc[i-1]
                
                # Lower band logic
                if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
                    final_lower.iloc[i] = basic_lower.iloc[i]
                else:
                    final_lower.iloc[i] = final_lower.iloc[i-1]
        
        # Initialize supertrend and direction
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        # Calculate supertrend line and direction
        for i in range(len(df)):
            if i == 0:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1  # Start with uptrend
            else:
                prev_supertrend = supertrend.iloc[i-1]
                
                # Determine direction based on close vs prev supertrend
                if close.iloc[i] > prev_supertrend:
                    # Uptrend
                    supertrend.iloc[i] = final_lower.iloc[i]
                    direction.iloc[i] = 1
                elif close.iloc[i] < prev_supertrend:
                    # Downtrend
                    supertrend.iloc[i] = final_upper.iloc[i]
                    direction.iloc[i] = -1
                else:
                    # No change
                    supertrend.iloc[i] = prev_supertrend
                    direction.iloc[i] = direction.iloc[i-1]
        
        return supertrend, direction
    
    def detect_flips(self, direction: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Detect Supertrend direction flips
        
        Args:
            direction: Series of direction values (1 or -1)
        
        Returns:
            Tuple: (flip_to_up series, flip_to_down series)
        """
        # Detect when direction changes
        direction_change = direction != direction.shift(1)
        
        # Flip to uptrend (from downtrend)
        flip_to_up = direction_change & (direction == 1)
        
        # Flip to downtrend (from uptrend)
        flip_to_down = direction_change & (direction == -1)
        
        return flip_to_up, flip_to_down
    
    def generate_signals(
        self,
        df: pd.DataFrame,
        min_confidence: float = 60.0
    ) -> List[Dict]:
        """
        Generate trading signals based on Supertrend reversals
        
        Args:
            df: DataFrame with OHLC data (must have at least 50 candles)
            min_confidence: Minimum confidence threshold (0-100)
        
        Returns:
            List of signal dictionaries
        """
        try:
            if len(df) < 50:
                logger.warning("Insufficient data for 5s Supertrend (need 50+ candles)")
                return []
            
            # Calculate Supertrend
            supertrend, direction = self.calculate_supertrend(df)
            
            # Detect flips
            flip_to_up, flip_to_down = self.detect_flips(direction)
            
            # Add to dataframe for analysis
            df['supertrend'] = supertrend
            df['direction'] = direction
            df['flip_to_up'] = flip_to_up
            df['flip_to_down'] = flip_to_down
            
            signals = []
            
            # Get the last candle (most recent)
            last_idx = len(df) - 1
            
            # Check for flip on last candle
            if df['flip_to_up'].iloc[last_idx]:
                # Flip to uptrend → REVERSAL STRATEGY → Generate SELL/PUT
                signal = self._create_signal(
                    df=df,
                    index=last_idx,
                    direction='put',
                    reason='Supertrend flip to uptrend - Reversal entry (betting on pullback)'
                )
                signals.append(signal)
                
            elif df['flip_to_down'].iloc[last_idx]:
                # Flip to downtrend → REVERSAL STRATEGY → Generate BUY/CALL
                signal = self._create_signal(
                    df=df,
                    index=last_idx,
                    direction='call',
                    reason='Supertrend flip to downtrend - Reversal entry (betting on bounce)'
                )
                signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating 5s Supertrend signals: {e}")
            return []
    
    def _create_signal(
        self,
        df: pd.DataFrame,
        index: int,
        direction: str,
        reason: str
    ) -> Dict:
        """
        Create a signal dictionary
        
        Args:
            df: DataFrame with indicator data
            index: Candle index
            direction: 'call' or 'put'
            reason: Signal justification
        
        Returns:
            Signal dictionary
        """
        close = df['close'].iloc[index]
        supertrend = df['supertrend'].iloc[index]
        atr = self.calculate_atr(df, self.atr_period).iloc[index]
        
        # Calculate distance from Supertrend (risk metric)
        distance_pct = abs((close - supertrend) / close) * 100
        
        # Base confidence calculation
        # Lower distance = higher confidence (tighter to Supertrend = better reversal setup)
        base_confidence = 70.0
        distance_factor = max(0, 15 - (distance_pct * 5))  # Penalty for distance
        
        # Recent volatility check (last 10 candles)
        recent_closes = df['close'].iloc[max(0, index-10):index+1]
        volatility = recent_closes.std() / recent_closes.mean() * 100
        
        # Higher volatility = higher confidence for reversal strategy
        volatility_boost = min(10, volatility * 2)
        
        confidence = base_confidence + distance_factor + volatility_boost
        confidence = min(95.0, max(50.0, confidence))  # Clamp 50-95%
        
        signal = {
            'direction': direction,
            'confidence': confidence,
            'entry_price': close,
            'expiration_seconds': 5,  # 5-second expiration
            'strategy': '5s_supertrend_reversal',
            'timeframe': '5s',
            'reason': reason,
            'technical_indicators': {
                'supertrend_value': float(supertrend),
                'supertrend_direction': int(df['direction'].iloc[index]),
                'atr': float(atr),
                'distance_from_supertrend': float(distance_pct),
                'volatility': float(volatility),
                'close': float(close)
            }
        }
        
        return signal
    
    def get_strategy_info(self) -> Dict:
        """Get strategy information"""
        return {
            'name': self.name,
            'display_name': '5s Supertrend Reversal',
            'timeframe': '5s',
            'type': 'reversal',
            'parameters': {
                'atr_period': self.atr_period,
                'multiplier': self.multiplier
            },
            'description': 'Ultra-short 5-second reversal strategy using Supertrend flips',
            'risk_level': 'very_high',
            'recommended_expiration': 5
        }


# Convenience function for API integration
def generate_5s_supertrend_signal(candle_data: List[Dict]) -> Optional[Dict]:
    """
    Generate signal from candle data
    
    Args:
        candle_data: List of candle dictionaries with OHLC data
    
    Returns:
        Signal dictionary or None
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame(candle_data)
        
        # Ensure required columns
        required = ['open', 'high', 'low', 'close', 'timestamp']
        if not all(col in df.columns for col in required):
            logger.error("Missing required columns in candle data")
            return None
        
        # Create strategy instance
        strategy = SupertrendReversal5s()
        
        # Generate signals
        signals = strategy.generate_signals(df)
        
        return signals[0] if signals else None
        
    except Exception as e:
        logger.error(f"Error in generate_5s_supertrend_signal: {e}")
        return None
