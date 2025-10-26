"""
Keltner Channel Indicator for Binary Options Trading
Optimized for 5-second timeframe with Heikin Ashi candles

Keltner Channel uses EMA and ATR to create dynamic bands that show trend direction
and volatility. Price position within the channel indicates trend strength.

Settings for 5s Pocket Option:
- EMA: 18 periods
- ATR: 13 periods  
- Multiplier: 2
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class KeltnerChannel:
    """
    Keltner Channel indicator for trend and volatility analysis
    
    Components:
    - Middle Line: EMA (18)
    - Upper Band: EMA + (ATR × Multiplier)
    - Lower Band: EMA - (ATR × Multiplier)
    """
    
    def __init__(self, ema_period: int = 18, atr_period: int = 13, multiplier: float = 2.0):
        """
        Initialize Keltner Channel with specified settings
        
        Args:
            ema_period: Period for EMA calculation (default 18 for 5s)
            atr_period: Period for ATR calculation (default 13 for 5s)
            multiplier: Multiplier for ATR bands (default 2)
        """
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.multiplier = multiplier
        
        logger.info(f"Keltner Channel initialized: EMA={ema_period}, ATR={atr_period}, Multiplier={multiplier}")
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Keltner Channel values
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with added columns:
                - 'kc_middle': Middle line (EMA)
                - 'kc_upper': Upper band
                - 'kc_lower': Lower band
                - 'kc_position': Price position within channel (0-1)
        """
        try:
            if df is None or df.empty or len(df) < max(self.ema_period, self.atr_period) + 5:
                logger.warning(f"Insufficient data for Keltner Channel (need {max(self.ema_period, self.atr_period) + 5}+ candles)")
                return df
            
            # Calculate EMA of close (middle line)
            df['kc_middle'] = talib.EMA(df['close'], timeperiod=self.ema_period)
            
            # Calculate ATR
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)
            
            # Calculate upper and lower bands
            df['kc_upper'] = df['kc_middle'] + (atr * self.multiplier)
            df['kc_lower'] = df['kc_middle'] - (atr * self.multiplier)
            
            # Calculate position within channel (0 = lower band, 0.5 = middle, 1 = upper band)
            channel_width = df['kc_upper'] - df['kc_lower']
            df['kc_position'] = (df['close'] - df['kc_lower']) / channel_width
            df['kc_position'] = df['kc_position'].clip(0, 1)  # Clamp between 0 and 1
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating Keltner Channel: {e}")
            return df
    
    def get_channel_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Analyze current Keltner Channel conditions
        
        Returns:
            Dict with:
                - direction: 'UP', 'DOWN', or 'SIDEWAYS'
                - position: 'UPPER', 'MIDDLE', 'LOWER'
                - position_value: 0-1 (exact position)
                - trend_strength: 0-1 score
                - is_in_middle: Boolean (0.35-0.65 range)
                - channel_width_pct: % width relative to price
        """
        try:
            if 'kc_middle' not in df.columns:
                return self._default_analysis()
            
            # Get current values
            current_close = df['close'].iloc[-1]
            current_middle = df['kc_middle'].iloc[-1]
            current_upper = df['kc_upper'].iloc[-1]
            current_lower = df['kc_lower'].iloc[-1]
            current_position = df['kc_position'].iloc[-1]
            
            # Determine trend direction based on EMA slope
            # Look at last 5 candles
            ema_values = df['kc_middle'].iloc[-5:]
            ema_slope = (ema_values.iloc[-1] - ema_values.iloc[0]) / ema_values.iloc[0] * 100
            
            if ema_slope > 0.05:  # > 0.05% upward slope
                direction = 'UP'
            elif ema_slope < -0.05:  # < -0.05% downward slope
                direction = 'DOWN'
            else:
                direction = 'SIDEWAYS'
            
            # Determine position within channel
            if current_position > 0.65:
                position = 'UPPER'
            elif current_position < 0.35:
                position = 'LOWER'
            else:
                position = 'MIDDLE'
            
            # Check if in middle zone (critical for signal generation)
            is_in_middle = 0.35 <= current_position <= 0.65
            
            # Calculate trend strength based on slope and position consistency
            trend_strength = min(abs(ema_slope) / 0.2, 1.0)  # Normalize to 0-1
            
            # Calculate channel width as percentage of price
            channel_width = current_upper - current_lower
            channel_width_pct = (channel_width / current_close) * 100 if current_close > 0 else 0
            
            return {
                'direction': direction,
                'position': position,
                'position_value': round(current_position, 3),
                'trend_strength': round(trend_strength, 2),
                'is_in_middle': is_in_middle,
                'channel_width_pct': round(channel_width_pct, 2),
                'ema_slope': round(ema_slope, 4),
                'current_middle': round(current_middle, 5),
                'current_upper': round(current_upper, 5),
                'current_lower': round(current_lower, 5)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Keltner Channel: {e}")
            return self._default_analysis()
    
    def _default_analysis(self) -> Dict:
        """Return default analysis when calculation fails"""
        return {
            'direction': 'SIDEWAYS',
            'position': 'MIDDLE',
            'position_value': 0.5,
            'trend_strength': 0,
            'is_in_middle': False,
            'channel_width_pct': 0,
            'ema_slope': 0
        }
    
    def detect_breakout(self, df: pd.DataFrame) -> Dict:
        """
        Detect breakouts from Keltner Channel
        
        Returns:
            Dict with:
                - breakout_type: 'UPPER', 'LOWER', or None
                - just_entered_middle: Boolean (moved from edge to middle)
        """
        try:
            if len(df) < 2 or 'kc_position' not in df.columns:
                return {'breakout_type': None, 'just_entered_middle': False}
            
            current_position = df['kc_position'].iloc[-1]
            prev_position = df['kc_position'].iloc[-2]
            
            # Detect upper breakout (moved from middle to upper)
            if current_position > 0.65 and prev_position <= 0.65:
                return {'breakout_type': 'UPPER', 'just_entered_middle': False}
            
            # Detect lower breakout (moved from middle to lower)
            if current_position < 0.35 and prev_position >= 0.35:
                return {'breakout_type': 'LOWER', 'just_entered_middle': False}
            
            # Detect entry to middle zone (from upper)
            if 0.35 <= current_position <= 0.65 and prev_position > 0.65:
                return {'breakout_type': None, 'just_entered_middle': True, 'from': 'UPPER'}
            
            # Detect entry to middle zone (from lower)
            if 0.35 <= current_position <= 0.65 and prev_position < 0.35:
                return {'breakout_type': None, 'just_entered_middle': True, 'from': 'LOWER'}
            
            return {'breakout_type': None, 'just_entered_middle': False}
            
        except Exception as e:
            logger.error(f"Error detecting Keltner breakout: {e}")
            return {'breakout_type': None, 'just_entered_middle': False}


def get_keltner_channel(ema_period: int = 18, atr_period: int = 13, multiplier: float = 2.0) -> KeltnerChannel:
    """Factory function to get Keltner Channel instance"""
    return KeltnerChannel(ema_period, atr_period, multiplier)
