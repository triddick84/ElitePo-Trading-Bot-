"""
1-Minute 21-Second Reversal Strategy

A timing-based contrarian strategy designed for Pocket Option short-expiry trades.

Concept:
- On a 1-minute candle, when the current (still-open) candle has exactly
  21 seconds remaining (i.e., 39s elapsed), fire a trade in the OPPOSITE
  direction of the current candle's BODY (close vs. open — wicks ignored).
- Trade expiry: 4-5 seconds (auto-selects closest PO offers, typically 5s).
- Cooldown: skip exactly 1 full candle after a fire (trade every other candle max).
- Rotation hint: rotate to a different asset after a win.

This backend module exposes a stateless `generate_signal(df)` for dashboard
and backtesting. Actual timing execution happens in the Tampermonkey
strategy module (see /app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js).

Entry Rules (for backend/backtest, treating the latest bar as the "currently open"):
- If body_direction is UP (close > open)  → PUT  (opposite)
- If body_direction is DOWN (close < open) → CALL (opposite)
- If body is flat (|body| < epsilon)       → NEUTRAL
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class Strategy1m21sReversal:
    def __init__(self):
        self.name = "1m 21s Reversal"
        self.timeframe = "1m"
        self.accuracy_target = 68.0
        # Body must be at least this fraction of the full range
        # (wicks excluded) to count as directional.
        self.min_body_ratio = 0.15
        # Body magnitude threshold in price units (normalized by price level)
        # to avoid firing on indecision candles.
        self.min_body_bps = 0.8  # 0.8 basis points of mid price

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 1:
            return {
                'direction': 'NEUTRAL', 'confidence': 0,
                'reason': 'Insufficient data', 'strategy': self.name
            }

        # Work on the latest bar — treat it as the current open candle
        last = df.iloc[-1]
        o = float(last.get('open', 0))
        c = float(last.get('close', 0))
        h = float(last.get('high', o))
        low_v = float(last.get('low', o))

        if o <= 0 or c <= 0:
            return {
                'direction': 'NEUTRAL', 'confidence': 0,
                'reason': 'Invalid OHLC', 'strategy': self.name
            }

        body = c - o
        full_range = max(h - low_v, 1e-9)
        mid = (o + c) / 2.0
        body_bps = abs(body) / mid * 10_000 if mid > 0 else 0.0
        body_ratio = abs(body) / full_range

        # Filter indecision candles
        if body_bps < self.min_body_bps or body_ratio < self.min_body_ratio:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': f'Body too small (ratio={body_ratio:.2f}, bps={body_bps:.2f})',
                'strategy': self.name,
            }

        # Opposite direction
        if body > 0:
            direction = 'PUT'
            reason = f'Candle UP (body={body_bps:.1f}bps) → reverse to PUT'
        else:
            direction = 'CALL'
            reason = f'Candle DOWN (body={body_bps:.1f}bps) → reverse to CALL'

        # Confidence: scale with body ratio (clamped to 55-78%)
        # Stronger bodies → higher confidence the mean-reversion edge exists
        confidence = float(np.clip(55 + body_ratio * 25 + min(body_bps, 5.0) * 2, 55, 78))

        return {
            'direction': direction,
            'confidence': round(confidence, 1),
            'reason': reason,
            'strategy': self.name,
            'expiry_seconds': 5,
            'fire_at_seconds_remaining': 21,
            'cooldown_candles': 1,
            'body_ratio': round(body_ratio, 3),
            'body_bps': round(body_bps, 2),
        }


# Singleton
strategy_1m_21s_reversal = Strategy1m21sReversal()
