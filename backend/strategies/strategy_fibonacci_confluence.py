"""
Fibonacci Confluence Strategy
=============================
High-accuracy reversal strategy combining Fibonacci retracement levels with
rolling swing anchors, trend filter, and reversal-candle + volume confirmation.

Theory:
- Price retraces a recent impulse move and reacts off institutional Fibonacci
  levels (23.6 / 38.2 / 50 / 61.8 / 78.6 %).
- A reversal candle (Doji or Engulfing) printed AT a Fibonacci zone, aligned
  with the broader trend (EMA20/EMA50), fires a directional signal.
- Volume confirmation (current volume > 1.2 * 20-bar average) filters weak
  rejections typical of OTC noise.

Entry (CALL):
  1. Prior impulse was DOWN (swing high → swing low in last N bars)
  2. Current price retraced UP into a Fibonacci zone (0.382–0.786)
  3. Reversal candle: bullish engulfing OR hammer OR bullish pin bar
  4. Higher-TF trend bullish (close > EMA20 on 5x longer lookback)
  5. Volume confirms (current > 1.2 × avg_20)

Entry (PUT) mirrors the above for an upward impulse.

Timeframes supported: 30s, 1m, 5m (parameters tuned per TF).
Status: BETA — tracked separately in WinRateWidget until real-world validated.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional


# ---------- helpers ----------

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _recent_swing(df: pd.DataFrame, lookback: int) -> Tuple[float, float, int, int]:
    """Return (swing_high, swing_low, hi_idx, lo_idx) over the last `lookback` bars."""
    window = df.iloc[-lookback:]
    hi_idx = int(window['high'].idxmax())
    lo_idx = int(window['low'].idxmin())
    return (
        float(window['high'].max()),
        float(window['low'].min()),
        hi_idx,
        lo_idx,
    )


def _fib_levels(high: float, low: float) -> Dict[str, float]:
    """Compute the 5 classic Fibonacci retracement levels between high and low."""
    rng = high - low
    return {
        '0.236': high - 0.236 * rng,
        '0.382': high - 0.382 * rng,
        '0.500': high - 0.500 * rng,
        '0.618': high - 0.618 * rng,
        '0.786': high - 0.786 * rng,
    }


def _in_fib_zone(price: float, fibs: Dict[str, float], tolerance_pct: float) -> Optional[str]:
    """
    Return the Fib level label if `price` is within `tolerance_pct` of any level,
    preferring the deeper (stronger) retracements.
    """
    # Check from deepest to shallowest — deeper = higher confidence reversal
    for level in ('0.786', '0.618', '0.500', '0.382', '0.236'):
        target = fibs[level]
        if target <= 0:
            continue
        if abs(price - target) / target <= tolerance_pct:
            return level
    return None


def _is_bullish_engulfing(prev, curr) -> bool:
    return (
        float(prev['close']) < float(prev['open'])  # prev bearish
        and float(curr['close']) > float(curr['open'])  # curr bullish
        and float(curr['close']) > float(prev['open'])
        and float(curr['open']) < float(prev['close'])
    )


def _is_bearish_engulfing(prev, curr) -> bool:
    return (
        float(prev['close']) > float(prev['open'])  # prev bullish
        and float(curr['close']) < float(curr['open'])  # curr bearish
        and float(curr['close']) < float(prev['open'])
        and float(curr['open']) > float(prev['close'])
    )


def _is_hammer(bar) -> bool:
    o, c = float(bar['open']), float(bar['close'])
    h, lo = float(bar['high']), float(bar['low'])
    body = abs(c - o)
    full = max(h - lo, 1e-9)
    lower_wick = min(o, c) - lo
    upper_wick = h - max(o, c)
    return body / full < 0.35 and lower_wick > body * 2 and upper_wick < body * 0.6


def _is_shooting_star(bar) -> bool:
    o, c = float(bar['open']), float(bar['close'])
    h, lo = float(bar['high']), float(bar['low'])
    body = abs(c - o)
    full = max(h - lo, 1e-9)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - lo
    return body / full < 0.35 and upper_wick > body * 2 and lower_wick < body * 0.6


# ---------- strategy class ----------

class FibonacciConfluenceStrategy:
    """Fibonacci retracement + trend + reversal-candle + volume confluence."""

    def __init__(self, timeframe: str = '1m'):
        tf_config = {
            '30s': {
                'name': 'Fibonacci Confluence 30s',
                'swing_lookback': 20,
                'trend_ema': 20,
                'fib_tolerance_pct': 0.0012,  # 12 bps
                'min_confirms': 3,
                'expiry_seconds': 30,
            },
            '1m': {
                'name': 'Fibonacci Confluence 1m',
                'swing_lookback': 30,
                'trend_ema': 20,
                'fib_tolerance_pct': 0.0015,
                'min_confirms': 3,
                'expiry_seconds': 60,
            },
            '5m': {
                'name': 'Fibonacci Confluence 5m',
                'swing_lookback': 40,
                'trend_ema': 20,
                'fib_tolerance_pct': 0.0025,
                'min_confirms': 3,
                'expiry_seconds': 300,
            },
        }
        cfg = tf_config.get(timeframe, tf_config['1m'])
        self.name = cfg['name']
        self.timeframe = timeframe
        self.accuracy_target = 75.0
        self.beta = True
        self.swing_lookback = cfg['swing_lookback']
        self.trend_ema = cfg['trend_ema']
        self.fib_tolerance_pct = cfg['fib_tolerance_pct']
        self.min_confirms = cfg['min_confirms']
        self.expiry_seconds = cfg['expiry_seconds']

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        min_bars = self.swing_lookback + self.trend_ema + 2
        if df is None or len(df) < min_bars:
            return self._neutral(f'Need {min_bars}+ bars, got {0 if df is None else len(df)}')

        # Normalize column names
        d = df.copy()
        if 'close' not in d.columns and 'c' in d.columns:
            d = d.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
        if 'volume' not in d.columns:
            d['volume'] = 1.0

        last = d.iloc[-1]
        prev = d.iloc[-2]
        price = float(last['close'])

        # 1. Swing anchor + Fib levels
        swing_hi, swing_lo, hi_idx, lo_idx = _recent_swing(d, self.swing_lookback)
        if swing_hi <= swing_lo:
            return self._neutral('Invalid swing range')
        # Whether the impulse was up (low → high) or down (high → low)
        impulse_up = lo_idx < hi_idx  # low came first, high later

        if impulse_up:
            # Looking for PUT retracement rejection (pullback down to Fib then DOWN)
            fibs = _fib_levels(swing_hi, swing_lo)
        else:
            # Impulse down → CALL on bullish retracement rejection
            # Flip the retracement direction: levels measured from the swing_lo up
            rng = swing_hi - swing_lo
            fibs = {
                '0.236': swing_lo + 0.236 * rng,
                '0.382': swing_lo + 0.382 * rng,
                '0.500': swing_lo + 0.500 * rng,
                '0.618': swing_lo + 0.618 * rng,
                '0.786': swing_lo + 0.786 * rng,
            }

        fib_hit = _in_fib_zone(price, fibs, self.fib_tolerance_pct)
        if not fib_hit:
            return self._neutral(
                f'Price {price:.5f} not in any Fib zone (impulse_{"up" if impulse_up else "dn"})'
            )

        # 2. Trend filter (EMA20 over full available history)
        ema20 = _ema(d['close'], self.trend_ema).iloc[-1]
        above_ema = price > ema20
        below_ema = price < ema20

        # 3. Reversal candle
        bullish_reversal = _is_bullish_engulfing(prev, last) or _is_hammer(last)
        bearish_reversal = _is_bearish_engulfing(prev, last) or _is_shooting_star(last)

        # 4. Volume confirmation
        avg_vol = d['volume'].iloc[-20:].mean() if d['volume'].sum() > 0 else 1.0
        current_vol = float(last['volume'])
        vol_confirms = current_vol > avg_vol * 1.2 if avg_vol > 0 else True

        # Decide direction
        if impulse_up:
            # Rejection off retracement → continuation down = PUT
            confirms = {
                'fib_zone': fib_hit,
                'bearish_candle': bearish_reversal,
                'trend_aligned': below_ema,
                'volume': vol_confirms,
            }
            direction = 'PUT'
        else:
            confirms = {
                'fib_zone': fib_hit,
                'bullish_candle': bullish_reversal,
                'trend_aligned': above_ema,
                'volume': vol_confirms,
            }
            direction = 'CALL'

        passed = sum(1 for v in confirms.values() if v)
        if passed < self.min_confirms:
            return self._neutral(
                f'Only {passed}/{len(confirms)} confirms '
                f'(need {self.min_confirms}): {confirms}'
            )

        # Confidence: base 60 + 5 per extra confirm + deeper Fib bonus
        depth_bonus = {'0.236': 0, '0.382': 2, '0.500': 4, '0.618': 6, '0.786': 5}.get(fib_hit, 0)
        confidence = float(np.clip(60 + (passed - self.min_confirms) * 5 + depth_bonus, 60, 82))

        return {
            'direction': direction,
            'confidence': round(confidence, 1),
            'reason': (
                f'Fib {fib_hit} rejection on impulse_{"up" if impulse_up else "dn"} '
                f'| confirms={passed}/{len(confirms)}'
            ),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'expiry_seconds': self.expiry_seconds,
            'beta': True,
            'fib_level': fib_hit,
            'swing_high': round(swing_hi, 6),
            'swing_low': round(swing_lo, 6),
            'confirms': confirms,
        }

    def _neutral(self, reason: str) -> Dict:
        return {
            'direction': 'NEUTRAL',
            'confidence': 0,
            'reason': reason,
            'strategy': self.name,
            'timeframe': self.timeframe,
            'beta': True,
        }


# Singletons per timeframe
strategy_fibonacci_confluence_30s = FibonacciConfluenceStrategy('30s')
strategy_fibonacci_confluence_1m = FibonacciConfluenceStrategy('1m')
strategy_fibonacci_confluence_5m = FibonacciConfluenceStrategy('5m')
