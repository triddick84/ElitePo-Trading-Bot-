"""
Triple Confirmation Strategy (Supply/Demand + Reversal + Volume Oscillator)
============================================================================
Inspired by the "90% win rate" professional setups that require three
independent layers of agreement before firing.

Theory:
- Institutions leave untapped supply/demand zones at recent pivot highs/lows
  where aggressive order flow once reversed price.
- When price returns to such a zone AND prints a high-probability reversal
  candle (engulfing/pin bar) AND a volume oscillator spike confirms
  institutional participation, the reversal edge is highest.

Three Layers (ALL required):
  Layer 1 — TREND: MA alignment + OSMA (MACD histogram) slope direction
  Layer 2 — ZONE: price tagging an untapped supply (for PUT) or demand (for
            CALL) zone detected from last 50 bars of pivot highs/lows
  Layer 3 — CONFIRMATION: reversal candle + Volume Oscillator crossover (fast
            vs slow volume MA)

Only when all three layers agree is a directional signal emitted.

Supported timeframes: 30s, 1m, 5m.
Status: BETA — tracked separately until real-world validated.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


# ---------- helpers ----------

def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    fast_ema = _ema(close, fast)
    slow_ema = _ema(close, slow)
    macd = fast_ema - slow_ema
    macd_signal = _ema(macd, signal)
    return macd - macd_signal  # OSMA


def _volume_oscillator(volume: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
    """Percentage volume oscillator: ((fast_ma - slow_ma) / slow_ma) * 100."""
    fast_ma = _sma(volume, fast)
    slow_ma = _sma(volume, slow).replace(0, np.nan)
    return ((fast_ma - slow_ma) / slow_ma) * 100.0


def _find_pivots(df: pd.DataFrame, left: int = 3, right: int = 3) -> Tuple[List[int], List[int]]:
    """Return (pivot_high_indices, pivot_low_indices) using fractal window."""
    highs, lows = [], []
    for i in range(left, len(df) - right):
        window_hi = df['high'].iloc[i - left:i + right + 1]
        window_lo = df['low'].iloc[i - left:i + right + 1]
        if df['high'].iloc[i] == window_hi.max() and (window_hi == df['high'].iloc[i]).sum() == 1:
            highs.append(i)
        if df['low'].iloc[i] == window_lo.min() and (window_lo == df['low'].iloc[i]).sum() == 1:
            lows.append(i)
    return highs, lows


def _build_zones(
    df: pd.DataFrame,
    lookback: int,
    zone_width_pct: float,
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Extract untapped supply (top) and demand (bottom) zones from recent pivots.
    A zone is considered "untapped" if price hasn't revisited it since its
    formation (simple heuristic — looks at bars after the pivot).
    Returns (supply_zones, demand_zones) each as list of (low_price, high_price).
    """
    window = df.iloc[-lookback:].reset_index(drop=True)
    if len(window) < 10:
        return [], []
    ph, pl = _find_pivots(window, left=2, right=2)

    supply_zones, demand_zones = [], []

    for idx in ph:
        pivot_high = float(window['high'].iloc[idx])
        # A supply zone is a narrow band around the pivot high
        zone_lo = pivot_high * (1 - zone_width_pct)
        zone_hi = pivot_high * (1 + zone_width_pct / 2)
        # Untapped heuristic: no close above pivot_high between pivot and now
        after = window['close'].iloc[idx + 1:]
        if len(after) > 0 and after.max() < pivot_high * (1 - 0.0003):
            supply_zones.append((zone_lo, zone_hi))

    for idx in pl:
        pivot_low = float(window['low'].iloc[idx])
        zone_lo = pivot_low * (1 - zone_width_pct / 2)
        zone_hi = pivot_low * (1 + zone_width_pct)
        after = window['close'].iloc[idx + 1:]
        if len(after) > 0 and after.min() > pivot_low * (1 + 0.0003):
            demand_zones.append((zone_lo, zone_hi))

    return supply_zones, demand_zones


def _in_zone(price: float, zones: List[Tuple[float, float]]) -> bool:
    return any(lo <= price <= hi for lo, hi in zones)


def _bullish_reversal_candle(prev, curr) -> bool:
    o, c = float(curr['open']), float(curr['close'])
    h, lo = float(curr['high']), float(curr['low'])
    po, pc = float(prev['open']), float(prev['close'])
    full = max(h - lo, 1e-9)
    body = abs(c - o)
    lower_wick = min(o, c) - lo
    # Bullish engulfing
    engulfing = pc < po and c > o and c > po and o < pc
    # Hammer / pin bar
    hammer = body / full < 0.35 and lower_wick > body * 2
    return engulfing or hammer


def _bearish_reversal_candle(prev, curr) -> bool:
    o, c = float(curr['open']), float(curr['close'])
    h, lo = float(curr['high']), float(curr['low'])
    po, pc = float(prev['open']), float(prev['close'])
    full = max(h - lo, 1e-9)
    body = abs(c - o)
    upper_wick = h - max(o, c)
    engulfing = pc > po and c < o and c < po and o > pc
    shooting_star = body / full < 0.35 and upper_wick > body * 2
    return engulfing or shooting_star


# ---------- strategy ----------

class TripleConfirmationStrategy:
    def __init__(self, timeframe: str = '1m'):
        tf_config = {
            '30s': {
                'name': 'Triple Confirmation 30s',
                'fast_ma': 5,
                'slow_ma': 20,
                'zone_lookback': 30,
                'zone_width_pct': 0.0008,
                'vol_fast': 5,
                'vol_slow': 20,
                'expiry_seconds': 30,
            },
            '1m': {
                'name': 'Triple Confirmation 1m',
                'fast_ma': 9,
                'slow_ma': 21,
                'zone_lookback': 50,
                'zone_width_pct': 0.0012,
                'vol_fast': 5,
                'vol_slow': 20,
                'expiry_seconds': 60,
            },
            '5m': {
                'name': 'Triple Confirmation 5m',
                'fast_ma': 12,
                'slow_ma': 26,
                'zone_lookback': 60,
                'zone_width_pct': 0.002,
                'vol_fast': 6,
                'vol_slow': 24,
                'expiry_seconds': 300,
            },
        }
        cfg = tf_config.get(timeframe, tf_config['1m'])
        self.name = cfg['name']
        self.timeframe = timeframe
        self.accuracy_target = 78.0
        self.beta = True
        self.fast_ma = cfg['fast_ma']
        self.slow_ma = cfg['slow_ma']
        self.zone_lookback = cfg['zone_lookback']
        self.zone_width_pct = cfg['zone_width_pct']
        self.vol_fast = cfg['vol_fast']
        self.vol_slow = cfg['vol_slow']
        self.expiry_seconds = cfg['expiry_seconds']

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        min_bars = max(self.slow_ma, self.zone_lookback) + 5
        if df is None or len(df) < min_bars:
            return self._neutral(f'Need {min_bars}+ bars')

        d = df.copy()
        if 'close' not in d.columns and 'c' in d.columns:
            d = d.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
        if 'volume' not in d.columns:
            d['volume'] = 1.0

        last = d.iloc[-1]
        prev = d.iloc[-2]
        price = float(last['close'])

        # Layer 1 — Trend
        fast = _ema(d['close'], self.fast_ma).iloc[-1]
        slow = _ema(d['close'], self.slow_ma).iloc[-1]
        osma = _macd_hist(d['close']).iloc[-3:].values
        trend_up = price > slow and fast > slow and osma[-1] > osma[-2]
        trend_dn = price < slow and fast < slow and osma[-1] < osma[-2]

        # Layer 2 — Zone
        supply_zones, demand_zones = _build_zones(d, self.zone_lookback, self.zone_width_pct)
        in_supply = _in_zone(price, supply_zones)
        in_demand = _in_zone(price, demand_zones)

        # Layer 3 — Confirmation (reversal candle + Volume Oscillator)
        vol_osc = _volume_oscillator(d['volume'], self.vol_fast, self.vol_slow)
        vol_osc_curr = float(vol_osc.iloc[-1]) if not np.isnan(vol_osc.iloc[-1]) else 0.0
        vol_spike = vol_osc_curr > 15.0  # fast vol > 15% above slow vol

        bullish_candle = _bullish_reversal_candle(prev, last)
        bearish_candle = _bearish_reversal_candle(prev, last)

        # Decision — ALL three layers must agree
        if in_demand and trend_up and bullish_candle and vol_spike:
            direction = 'CALL'
            layers = {'zone': 'demand', 'trend': 'up', 'candle': 'bullish_reversal', 'volume': vol_osc_curr}
        elif in_supply and trend_dn and bearish_candle and vol_spike:
            direction = 'PUT'
            layers = {'zone': 'supply', 'trend': 'dn', 'candle': 'bearish_reversal', 'volume': vol_osc_curr}
        else:
            return self._neutral(
                f'Layers incomplete — trend_up={trend_up} trend_dn={trend_dn} '
                f'demand={in_demand} supply={in_supply} '
                f'bull={bullish_candle} bear={bearish_candle} vol_spike={vol_spike}'
            )

        # Confidence: base 70 + vol strength + trend agreement
        vol_bonus = min((vol_osc_curr - 15.0) / 5.0, 5.0)
        trend_strength = abs(float(osma[-1])) / max(float(slow), 1e-9) * 10_000
        trend_bonus = min(trend_strength * 0.5, 5.0)
        confidence = float(np.clip(70 + vol_bonus + trend_bonus, 70, 85))

        return {
            'direction': direction,
            'confidence': round(confidence, 1),
            'reason': (
                f'Triple-agree: {layers["zone"]} zone + trend_{layers["trend"]} + '
                f'{layers["candle"]} + vol_osc={layers["volume"]:.1f}%'
            ),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'expiry_seconds': self.expiry_seconds,
            'beta': True,
            'layers': layers,
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
strategy_triple_confirmation_30s = TripleConfirmationStrategy('30s')
strategy_triple_confirmation_1m = TripleConfirmationStrategy('1m')
strategy_triple_confirmation_5m = TripleConfirmationStrategy('5m')
