"""
5-Second 3 EMA Crossover Strategy
User-Requested Strategy for Pocket Option

Moving Average EMA Settings:
- 1st EMA Period: 3
- 2nd EMA Period: 8
- 3rd EMA Period: 20

Buy Signal: EMA-3 crosses over EMA-8 downward AND has not crossed EMA-20 yet
Sell Signal: EMA-3 crosses over EMA-8 upward AND has not crossed EMA-20 yet
If EMA-3 crosses EMA-20, don't generate signals
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Strategy5s3EMACrossover:
    """5s 3 EMA Crossover Strategy"""
    
    def __init__(self):
        self.ema_fast = 3
        self.ema_mid = 8
        self.ema_slow = 20
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze using 3 EMA Crossover"""
        try:
            if len(df) < 25:
                return None
            
            # Calculate EMAs
            ema3 = talib.EMA(df['Close'], timeperiod=self.ema_fast)
            ema8 = talib.EMA(df['Close'], timeperiod=self.ema_mid)
            ema20 = talib.EMA(df['Close'], timeperiod=self.ema_slow)
            
            # Get current and previous values
            curr_ema3 = ema3.iloc[-1]
            prev_ema3 = ema3.iloc[-2]
            curr_ema8 = ema8.iloc[-1]
            prev_ema8 = ema8.iloc[-2]
            curr_ema20 = ema20.iloc[-1]
            
            # Check if EMA-3 has crossed EMA-20 (invalidates signals)
            ema3_crossed_ema20 = False
            
            # Check last 5 candles for EMA-3 crossing EMA-20
            for i in range(-5, 0):
                if (ema3.iloc[i-1] < ema20.iloc[i-1] and ema3.iloc[i] > ema20.iloc[i]) or \
                   (ema3.iloc[i-1] > ema20.iloc[i-1] and ema3.iloc[i] < ema20.iloc[i]):
                    ema3_crossed_ema20 = True
                    break
            
            if ema3_crossed_ema20:
                logger.info(f"{symbol}: EMA-3 crossed EMA-20 recently - no signal")
                return None
            
            direction = None
            confidence = 75.0
            reasoning = []
            
            # BUY Signal: EMA-3 crosses over EMA-8 in DOWNWARD direction
            # (EMA-3 was above EMA-8, now crosses below)
            if prev_ema3 > prev_ema8 and curr_ema3 < curr_ema8:
                # Check EMA-3 has NOT crossed EMA-20
                if not ((prev_ema3 > curr_ema20 and curr_ema3 < curr_ema20) or \
                        (prev_ema3 < curr_ema20 and curr_ema3 > curr_ema20)):
                    direction = 'CALL'
                    confidence = 80.0
                    reasoning.append(f"EMA-3 ({curr_ema3:.5f}) crossed below EMA-8 ({curr_ema8:.5f})")
                    reasoning.append(f"EMA-3 has not crossed EMA-20 ({curr_ema20:.5f})")
                    reasoning.append(f"Valid crossover signal for reversal")
            
            # SELL Signal: EMA-3 crosses over EMA-8 in UPWARD direction
            # (EMA-3 was below EMA-8, now crosses above)
            elif prev_ema3 < prev_ema8 and curr_ema3 > curr_ema8:
                # Check EMA-3 has NOT crossed EMA-20
                if not ((prev_ema3 > curr_ema20 and curr_ema3 < curr_ema20) or \
                        (prev_ema3 < curr_ema20 and curr_ema3 > curr_ema20)):
                    direction = 'PUT'
                    confidence = 80.0
                    reasoning.append(f"EMA-3 ({curr_ema3:.5f}) crossed above EMA-8 ({curr_ema8:.5f})")
                    reasoning.append(f"EMA-3 has not crossed EMA-20 ({curr_ema20:.5f})")
                    reasoning.append(f"Valid crossover signal for reversal")
            
            if direction is None:
                return None
            
            return {
                'direction': direction,
                'confidence': confidence,
                'probability': confidence,
                'reasoning': ' | '.join(reasoning),
                'technical_analysis': {
                    'strategy': '3ema_crossover_5s',
                    'ema3': float(curr_ema3),
                    'ema8': float(curr_ema8),
                    'ema20': float(curr_ema20),
                    'crossover_type': 'downward' if direction == 'CALL' else 'upward',
                    'ema3_distance_to_ema20': float(abs(curr_ema3 - curr_ema20))
                }
            }
            
        except Exception as e:
            logger.error(f"Error in 3 EMA Crossover strategy: {e}")
            return None


def generate_signal(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """Generate signal using 3 EMA Crossover strategy"""
    strategy = Strategy5s3EMACrossover()
    return strategy.analyze(df, symbol)
