"""
5-Second EMA 20 and RSI 14 Combination Strategy
User-Requested Strategy for Pocket Option

Settings:
- EMA Period: 20
- RSI Period: 14

Buy Signal: Price above EMA 20 AND RSI between 50-70 (upward momentum)
Sell Signal: Price below EMA 20 AND RSI between 30-50 (downward momentum)
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Strategy5sEMA20RSI14:
    """5s EMA 20 + RSI 14 Strategy"""
    
    def __init__(self):
        self.ema_period = 20
        self.rsi_period = 14
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze using EMA 20 and RSI 14"""
        try:
            if len(df) < 25:
                return None
            
            # Calculate EMA 20
            ema20 = talib.EMA(df['Close'], timeperiod=self.ema_period)
            
            # Calculate RSI 14
            rsi = talib.RSI(df['Close'], timeperiod=self.rsi_period)
            
            # Get current values
            current_price = df['Close'].iloc[-1]
            current_ema = ema20.iloc[-1]
            current_rsi = rsi.iloc[-1]
            
            direction = None
            confidence = 75.0
            reasoning = []
            
            # BUY Signal: Price above EMA 20 AND RSI between 50-70
            if current_price > current_ema and 50 <= current_rsi <= 70:
                direction = 'CALL'
                # Higher confidence if RSI is closer to 60 (sweet spot)
                rsi_optimal = abs(current_rsi - 60)
                confidence = 85.0 - (rsi_optimal * 0.5)  # Max 85% at RSI=60, min 80% at edges
                
                reasoning.append(f"Price ({current_price:.5f}) above EMA-20 ({current_ema:.5f})")
                reasoning.append(f"RSI ({current_rsi:.2f}) in bullish zone (50-70)")
                reasoning.append(f"Upward momentum confirmed")
                
            # SELL Signal: Price below EMA 20 AND RSI between 30-50
            elif current_price < current_ema and 30 <= current_rsi <= 50:
                direction = 'PUT'
                # Higher confidence if RSI is closer to 40 (sweet spot)
                rsi_optimal = abs(current_rsi - 40)
                confidence = 85.0 - (rsi_optimal * 0.5)  # Max 85% at RSI=40, min 80% at edges
                
                reasoning.append(f"Price ({current_price:.5f}) below EMA-20 ({current_ema:.5f})")
                reasoning.append(f"RSI ({current_rsi:.2f}) in bearish zone (30-50)")
                reasoning.append(f"Downward momentum confirmed")
            
            if direction is None:
                return None
            
            # Calculate distance from EMA for additional context
            distance_from_ema = abs(current_price - current_ema) / current_ema * 100
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': ' | '.join(reasoning),
                'technical_analysis': {
                    'strategy': 'ema20_rsi14_5s',
                    'ema20': float(current_ema),
                    'rsi14': float(current_rsi),
                    'current_price': float(current_price),
                    'price_position': 'above_ema' if current_price > current_ema else 'below_ema',
                    'distance_from_ema_pct': float(distance_from_ema),
                    'momentum': 'bullish' if direction == 'CALL' else 'bearish'
                }
            }
            
        except Exception as e:
            logger.error(f"Error in EMA 20 RSI 14 strategy: {e}")
            return None


def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """Generate signal using EMA 20 + RSI 14 strategy"""
    strategy = Strategy5sEMA20RSI14()
    return strategy.analyze(df, symbol)
