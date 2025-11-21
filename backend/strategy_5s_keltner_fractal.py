"""
5-Second Keltner Channel and Fractal Strategy
User-Requested Strategy for Pocket Option

Keltner Channel Settings:
- EMA Period: 10
- ATR Period: 10
- Multiplier: 2

Fractal Indicator Settings:
- Period: 2

Buy Signal: Candle closes outside/near bottom of Keltner lower band + Fractal reversal up
Sell Signal: Candle closes outside/near top of Keltner upper band + Fractal reversal down
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Strategy5sKeltnerFractal:
    """5s Keltner Channel + Fractal Strategy"""
    
    def __init__(self):
        self.ema_period = 10
        self.atr_period = 10
        self.multiplier = 2
        self.fractal_period = 2
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze using Keltner Channel and Fractals"""
        try:
            if len(df) < 30:
                return None
            
            # Calculate EMA (middle line of Keltner)
            ema = talib.EMA(df['Close'], timeperiod=self.ema_period)
            
            # Calculate ATR
            atr = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=self.atr_period)
            
            # Calculate Keltner Channels
            upper_band = ema + (self.multiplier * atr)
            lower_band = ema - (self.multiplier * atr)
            
            # Detect Fractals (local highs and lows)
            fractals_up = self._detect_fractals_up(df)
            fractals_down = self._detect_fractals_down(df)
            
            # Get current values
            current_close = df['Close'].iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            
            # Check for signals
            direction = None
            confidence = 75.0
            reasoning = []
            
            # BUY Signal: Close near/outside lower band + Fractal reversal up
            near_lower = abs(current_close - current_lower) / current_lower < 0.002  # Within 0.2%
            outside_lower = current_close < current_lower
            
            if (near_lower or outside_lower) and fractals_up[-1]:
                direction = 'CALL'
                confidence = 82.0 if outside_lower else 78.0
                reasoning.append(f"Price {'outside' if outside_lower else 'near'} lower Keltner band ({current_lower:.5f})")
                reasoning.append(f"Fractal reversal detected (upward)")
                reasoning.append(f"Keltner Channel confirms oversold condition")
            
            # SELL Signal: Close near/outside upper band + Fractal reversal down
            near_upper = abs(current_close - current_upper) / current_upper < 0.002
            outside_upper = current_close > current_upper
            
            if (near_upper or outside_upper) and fractals_down[-1]:
                if direction is None:  # Don't override BUY signal
                    direction = 'PUT'
                    confidence = 82.0 if outside_upper else 78.0
                    reasoning.append(f"Price {'outside' if outside_upper else 'near'} upper Keltner band ({current_upper:.5f})")
                    reasoning.append(f"Fractal reversal detected (downward)")
                    reasoning.append(f"Keltner Channel confirms overbought condition")
            
            if direction is None:
                return None
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': ' | '.join(reasoning),
                'technical_analysis': {
                    'strategy': 'keltner_fractal_5s',
                    'keltner_upper': float(current_upper),
                    'keltner_middle': float(ema.iloc[-1]),
                    'keltner_lower': float(current_lower),
                    'current_price': float(current_close),
                    'fractal_up': bool(fractals_up[-1]),
                    'fractal_down': bool(fractals_down[-1])
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Keltner Fractal strategy: {e}")
            return None
    
    def _detect_fractals_up(self, df: pd.DataFrame) -> pd.Series:
        """Detect bullish fractals (potential reversal up)"""
        fractals = pd.Series([False] * len(df), index=df.index)
        
        for i in range(self.fractal_period, len(df) - self.fractal_period):
            # Bullish fractal: Low is lower than surrounding lows
            is_fractal = True
            center_low = df['Low'].iloc[i]
            
            for j in range(1, self.fractal_period + 1):
                if df['Low'].iloc[i-j] <= center_low or df['Low'].iloc[i+j] <= center_low:
                    is_fractal = False
                    break
            
            fractals.iloc[i] = is_fractal
        
        return fractals
    
    def _detect_fractals_down(self, df: pd.DataFrame) -> pd.Series:
        """Detect bearish fractals (potential reversal down)"""
        fractals = pd.Series([False] * len(df), index=df.index)
        
        for i in range(self.fractal_period, len(df) - self.fractal_period):
            # Bearish fractal: High is higher than surrounding highs
            is_fractal = True
            center_high = df['High'].iloc[i]
            
            for j in range(1, self.fractal_period + 1):
                if df['High'].iloc[i-j] >= center_high or df['High'].iloc[i+j] >= center_high:
                    is_fractal = False
                    break
            
            fractals.iloc[i] = is_fractal
        
        return fractals


def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """Generate signal using Keltner Channel + Fractal strategy"""
    strategy = Strategy5sKeltnerFractal()
    return strategy.analyze(df, symbol)