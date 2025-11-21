"""
15-Second Bollinger Bands + EMA Breakout Strategy
Research-Backed for Pocket Option 2025

Settings:
- Bollinger Bands: Period 20, StdDev 2
- EMA: Period 20

Buy Signal: Price breaks above upper BB + EMA confirms uptrend
Sell Signal: Price breaks below lower BB + EMA confirms downtrend
"""

import pandas as pd
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Strategy15sBollingerEMA:
    def __init__(self):
        self.bb_period = 20
        self.ema_period = 20
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            if len(df) < 25:
                return None
            
            upper, middle, lower = talib.BBANDS(df['Close'], timeperiod=self.bb_period)
            ema = talib.EMA(df['Close'], timeperiod=self.ema_period)
            
            current_price = df['Close'].iloc[-1]
            current_upper = upper.iloc[-1]
            current_lower = lower.iloc[-1]
            current_ema = ema.iloc[-1]
            
            direction = None
            confidence = 72.0
            
            # BUY: Break above upper BB + price above EMA
            if current_price > current_upper and current_price > current_ema:
                direction = 'CALL'
                distance = (current_price - current_upper) / current_upper * 100
                confidence = min(75.0 + (distance * 100), 85.0)
            # SELL: Break below lower BB + price below EMA
            elif current_price < current_lower and current_price < current_ema:
                direction = 'PUT'
                distance = (current_lower - current_price) / current_lower * 100
                confidence = min(75.0 + (distance * 100), 85.0)
            
            if direction is None:
                return None
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': f"Bollinger {'breakout above' if direction == 'CALL' else 'breakdown below'} with EMA confirmation",
                'technical_analysis': {
                    'strategy': 'bollinger_ema_15s',
                    'bb_upper': float(current_upper),
                    'bb_lower': float(current_lower),
                    'ema': float(current_ema),
                    'price': float(current_price)
                }
            }
        except Exception as e:
            logger.error(f"Error in Bollinger EMA strategy: {e}")
            return None

def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    strategy = Strategy15sBollingerEMA()
    return strategy.analyze(df, symbol)
