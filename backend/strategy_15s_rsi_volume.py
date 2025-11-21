"""
15-Second RSI + Volume Reversal Strategy
Research-Backed for Pocket Option 2025

Settings:
- RSI Period: 14
- Volume: Spike detection

Buy Signal: RSI < 30 (oversold) + Volume spike
Sell Signal: RSI > 70 (overbought) + Volume spike
"""

import pandas as pd
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Strategy15sRSIVolume:
    def __init__(self):
        self.rsi_period = 14
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            if len(df) < 20:
                return None
            
            rsi = talib.RSI(df['Close'], timeperiod=self.rsi_period)
            
            # Volume spike detection
            if 'Volume' not in df.columns:
                return None
            
            avg_volume = df['Volume'].iloc[-20:].mean()
            current_volume = df['Volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            current_rsi = rsi.iloc[-1]
            
            direction = None
            confidence = 70.0
            
            # BUY: Oversold + Volume spike
            if current_rsi < 30 and volume_ratio > 1.5:
                direction = 'CALL'
                confidence = min(80.0 + (30 - current_rsi), 88.0)
            # SELL: Overbought + Volume spike
            elif current_rsi > 70 and volume_ratio > 1.5:
                direction = 'PUT'
                confidence = min(80.0 + (current_rsi - 70), 88.0)
            
            if direction is None:
                return None
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': f"RSI {current_rsi:.1f} {'oversold' if direction == 'CALL' else 'overbought'} with {volume_ratio:.1f}x volume spike",
                'technical_analysis': {
                    'strategy': 'rsi_volume_15s',
                    'rsi': float(current_rsi),
                    'volume_ratio': float(volume_ratio)
                }
            }
        except Exception as e:
            logger.error(f"Error in RSI Volume strategy: {e}")
            return None

def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    strategy = Strategy15sRSIVolume()
    return strategy.analyze(df, symbol)
