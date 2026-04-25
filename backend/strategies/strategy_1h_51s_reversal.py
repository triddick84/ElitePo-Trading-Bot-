"""
1-Hour 51-Second Reversal Strategy
===================================
Timing-based contrarian strategy using a 1-HOUR chart context with 5-second
trade expiries.

Mechanism (Tampermonkey side does the actual timing — backend exposes a
stateless evaluation for backtest/dashboard parity):
  - Evaluate the OPEN 1H candle (the most recent bar in the supplied DataFrame).
  - At every minute's :51-second wallclock mark, fire a 5-second trade in the
    OPPOSITE direction of that 1H candle's body (close vs. open, wicks ignored).
  - After firing, the executor rotates to the NEXT asset and waits for the
    next :51 mark.

Backend signal:
  - direction = PUT if 1H body is UP, CALL if DOWN, NEUTRAL on flat body.
  - confidence scales with body magnitude (clamped 55-78%).
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class Strategy1h51sReversal:
    def __init__(self):
        self.name = "1h 51s Reversal"
        self.timeframe = "1h"
        self.accuracy_target = 65.0
        # Body must be a small fraction of the full 1H range to count as
        # directional. 1H bodies are typically substantial so this is loose.
        self.min_body_ratio = 0.10
        # Body magnitude in BPS of mid (very low — most 1H candles qualify).
        self.min_body_bps = 0.5

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 1:
            return self._neutral('Insufficient data')

        last = df.iloc[-1]
        o = float(last.get('open', 0))
        c = float(last.get('close', 0))
        h = float(last.get('high', o))
        lo = float(last.get('low', o))

        if o <= 0 or c <= 0:
            return self._neutral('Invalid OHLC')

        body = c - o
        full_range = max(h - lo, 1e-9)
        mid = (o + c) / 2.0
        body_bps = abs(body) / mid * 10_000 if mid > 0 else 0.0
        body_ratio = abs(body) / full_range

        if body_bps < self.min_body_bps or body_ratio < self.min_body_ratio:
            return self._neutral(
                f'Body too small (ratio={body_ratio:.2f}, bps={body_bps:.2f})'
            )

        if body > 0:
            direction = 'PUT'
            reason = f'1H candle UP (body={body_bps:.1f}bps) → reverse to PUT'
        else:
            direction = 'CALL'
            reason = f'1H candle DOWN (body={body_bps:.1f}bps) → reverse to CALL'

        # Confidence: scale modestly with body — 1H candles can be huge so we
        # cap to keep this honest. Timing edge is the real value here.
        confidence = float(np.clip(55 + body_ratio * 20 + min(body_bps, 50.0) * 0.3, 55, 78))

        return {
            'direction': direction,
            'confidence': round(confidence, 1),
            'reason': reason,
            'strategy': self.name,
            'timeframe': self.timeframe,
            'expiry_seconds': 5,
            'fire_at_seconds_in_minute': 51,
            'rotate_after_fire': True,
            'body_ratio': round(body_ratio, 3),
            'body_bps': round(body_bps, 2),
        }

    def _neutral(self, reason: str) -> Dict:
        return {
            'direction': 'NEUTRAL',
            'confidence': 0,
            'reason': reason,
            'strategy': self.name,
            'timeframe': self.timeframe,
        }


# Singleton
strategy_1h_51s_reversal = Strategy1h51sReversal()
