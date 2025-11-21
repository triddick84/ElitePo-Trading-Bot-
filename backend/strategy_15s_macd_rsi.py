"""
15-Second MACD + RSI Trend Confirmation Strategy
Research-Backed for Pocket Option 2025

Settings:
- MACD: 12, 26, 9
- RSI: 14

Buy Signal: MACD bullish crossover + RSI confirms momentum (not overbought)
Sell Signal: MACD bearish crossover + RSI confirms momentum (not oversold)
"""

import pandas as pd
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Strategy15sMACDRSI:
    def __init__(self):
        self.rsi_period = 14
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            if len(df) < 30:
                return None
            
            macd, signal, hist = talib.MACD(df['Close'])
            rsi = talib.RSI(df['Close'], timeperiod=self.rsi_period)
            
            current_macd = macd.iloc[-1]
            current_signal = signal.iloc[-1]
            prev_hist = hist.iloc[-2]
            current_hist = hist.iloc[-1]
            current_rsi = rsi.iloc[-1]
            
            direction = None
            confidence = 70.0
            
            # BUY: MACD bullish crossover + RSI not overbought
            if prev_hist < 0 and current_hist > 0 and current_rsi < 70:
                direction = 'CALL'
                confidence = 78.0 if 40 < current_rsi < 60 else 75.0
            # SELL: MACD bearish crossover + RSI not oversold
            elif prev_hist > 0 and current_hist < 0 and current_rsi > 30:
                direction = 'PUT'
                confidence = 78.0 if 40 < current_rsi < 60 else 75.0
            
            if direction is None:
                return None
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': f"MACD {'bullish' if direction == 'CALL' else 'bearish'} crossover with RSI {current_rsi:.1f} confirmation",
                'technical_analysis': {
                    'strategy': 'macd_rsi_15s',
                    'macd': float(current_macd),
                    'macd_signal': float(current_signal),
                    'rsi': float(current_rsi)
                }
            }
        except Exception as e:
            logger.error(f"Error in MACD RSI strategy: {e}")
            return None

def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    strategy = Strategy15sMACDRSI()
    return strategy.analyze(df, symbol)
