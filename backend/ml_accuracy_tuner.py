"""
ML Accuracy Tuning Service
============================
Trains ML models using accumulated OTC candle data + OANDA data.
Applies adaptive labeling thresholds, feature selection, and hyperparameter tuning.
"""

import logging
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score, GridSearchCV
    from sklearn.feature_selection import SelectKBest, mutual_info_classif
    from sklearn.preprocessing import RobustScaler
    from sklearn.metrics import accuracy_score, classification_report
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Adaptive labeling thresholds per timeframe
TIMEFRAME_THRESHOLDS = {
    '5s': 0.00005,    # 0.5 pips
    '15s': 0.0001,    # 1 pip
    '30s': 0.00015,   # 1.5 pips
    'S5': 0.00005,
    'S15': 0.0001,
    'S30': 0.00015,
    'M1': 0.0003,     # 3 pips
    '1m': 0.0003,
}

# Prediction horizons per timeframe (how many candles ahead to predict)
TIMEFRAME_HORIZONS = {
    '5s': 3,    # predict 15 seconds ahead
    '15s': 2,   # predict 30 seconds ahead
    '30s': 2,   # predict 1 minute ahead
    'S5': 3,
    'S15': 2,
    'S30': 2,
    'M1': 5,    # predict 5 minutes ahead
    '1m': 5,
}


class MLAccuracyTuner:
    """Handles ML accuracy tuning with OTC data, feature selection, and hyperparameters."""

    def __init__(self, db):
        self.db = db
        self.otc_collection = db["otc_candles_5s"]

    async def get_otc_training_data(self, symbol: str = None, limit: int = 10000) -> pd.DataFrame:
        """Fetch accumulated OTC candle data from MongoDB."""
        query = {}
        if symbol:
            query["symbol"] = symbol

        cursor = self.otc_collection.find(query, {"_id": 0}).sort("timestamp", 1).limit(limit)
        docs = await cursor.to_list(limit)

        if not docs:
            return pd.DataFrame()

        df = pd.DataFrame(docs)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        return df

    def generate_labels(self, df: pd.DataFrame, timeframe: str = '5s') -> Tuple[pd.Series, pd.Series]:
        """
        Generate adaptive labels based on timeframe.
        Returns (labels Series, valid_mask Series).
        """
        threshold_pct = TIMEFRAME_THRESHOLDS.get(timeframe, 0.0003)
        horizon = TIMEFRAME_HORIZONS.get(timeframe, 5)

        labels = pd.Series(np.nan, index=df.index)
        valid = pd.Series(False, index=df.index)

        closes = df['close'].values

        for i in range(len(df) - horizon):
            current = closes[i]
            future = closes[i + horizon]
            threshold = current * threshold_pct

            if future > current + threshold:
                labels.iloc[i] = 1  # CALL
                valid.iloc[i] = True
            elif future < current - threshold:
                labels.iloc[i] = 0  # PUT
                valid.iloc[i] = True
            # else: skip ambiguous

        return labels, valid

    def extract_5s_features(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        """
        Extract features optimized for 5-second binary options.
        Uses smaller lookback windows appropriate for ultra-short timeframes.
        """
        if idx < 30:
            return None

        close = df['close'].values[:idx + 1]
        high = df['high'].values[:idx + 1]
        low = df['low'].values[:idx + 1]
        open_p = df['open'].values[:idx + 1]

        features = {}

        # Returns (multiple horizons)
        for period in [1, 2, 3, 5, 10, 15, 20]:
            if len(close) > period:
                features[f'return_{period}'] = (close[-1] - close[-1 - period]) / close[-1 - period] * 10000  # in pips

        # Candle characteristics
        cr = high[-1] - low[-1]
        features['body_ratio'] = abs(close[-1] - open_p[-1]) / cr if cr > 0 else 0.5
        features['upper_wick'] = (high[-1] - max(close[-1], open_p[-1])) / cr if cr > 0 else 0
        features['lower_wick'] = (min(close[-1], open_p[-1]) - low[-1]) / cr if cr > 0 else 0
        features['is_bullish'] = 1 if close[-1] > open_p[-1] else 0
        features['close_pos'] = (close[-1] - low[-1]) / cr if cr > 0 else 0.5

        # Streak
        bull = sum(1 for i in range(-5, 0) if close[i] > open_p[i])
        features['bull_streak'] = bull
        features['bear_streak'] = 5 - bull

        # RSI (multiple periods for 5s)
        for period in [3, 5, 8, 14]:
            if len(close) > period + 1:
                deltas = np.diff(close[-(period + 1):])
                gains = np.mean([d for d in deltas if d > 0]) if any(d > 0 for d in deltas) else 0
                losses = np.mean([-d for d in deltas if d < 0]) if any(d < 0 for d in deltas) else 0
                rs = gains / losses if losses > 0 else 100
                features[f'rsi_{period}'] = 100 - (100 / (1 + rs))

        # EMA features
        for period in [3, 5, 8, 13, 21]:
            ema = pd.Series(close).ewm(span=period, adjust=False).mean().values
            features[f'price_vs_ema{period}'] = (close[-1] - ema[-1]) / ema[-1] * 10000

        # EMA alignment
        ema3 = pd.Series(close).ewm(span=3, adjust=False).mean().values[-1]
        ema8 = pd.Series(close).ewm(span=8, adjust=False).mean().values[-1]
        ema21 = pd.Series(close).ewm(span=21, adjust=False).mean().values[-1]
        features['ema_aligned_bull'] = 1 if ema3 > ema8 > ema21 else 0
        features['ema_aligned_bear'] = 1 if ema3 < ema8 < ema21 else 0

        # Volatility
        if len(close) > 11:
            rets = np.diff(close[-11:]) / close[-11:-1]
            features['volatility_10'] = np.std(rets) * 10000
            features['avg_range_10'] = np.mean(high[-10:] - low[-10:]) * 10000

        if len(close) > 21:
            rets20 = np.diff(close[-21:]) / close[-21:-1]
            features['volatility_20'] = np.std(rets20) * 10000

        # Stochastic (fast for 5s)
        if len(close) > 8:
            period_h = np.max(high[-8:])
            period_l = np.min(low[-8:])
            features['stoch_k_8'] = ((close[-1] - period_l) / (period_h - period_l) * 100) if period_h != period_l else 50

        if len(close) > 14:
            period_h14 = np.max(high[-14:])
            period_l14 = np.min(low[-14:])
            features['stoch_k_14'] = ((close[-1] - period_l14) / (period_h14 - period_l14) * 100) if period_h14 != period_l14 else 50

        # MACD (fast for 5s: 5,13,4)
        ema_fast = pd.Series(close).ewm(span=5, adjust=False).mean().values[-1]
        ema_slow = pd.Series(close).ewm(span=13, adjust=False).mean().values[-1]
        features['macd_fast'] = (ema_fast - ema_slow) * 10000

        # Bollinger Band position
        if len(close) > 15:
            sma15 = np.mean(close[-15:])
            std15 = np.std(close[-15:])
            if std15 > 0:
                features['bb_pos_15'] = (close[-1] - (sma15 - 2 * std15)) / (4 * std15) if std15 > 0 else 0.5
                features['bb_width_15'] = (4 * std15) / sma15 * 10000

        # Price momentum
        if len(close) > 5:
            features['momentum_3'] = (close[-1] - close[-4]) / close[-4] * 10000
            features['momentum_5'] = (close[-1] - close[-6]) / close[-6] * 10000 if len(close) > 6 else 0

        # Price acceleration
        if len(close) > 6:
            mom1 = close[-1] - close[-2]
            mom2 = close[-2] - close[-3]
            features['acceleration'] = (mom1 - mom2) * 10000

        # Support/Resistance proximity
        if len(close) > 20:
            recent_high = np.max(high[-20:])
            recent_low = np.min(low[-20:])
            rng = recent_high - recent_low
            if rng > 0:
                features['sr_position'] = (close[-1] - recent_low) / rng

        # ------------------------------------------------------------
        # NEW (Apr 23, 2026): Fibonacci-distance + Supply/Demand proximity
        # + Volume Oscillator features — mirrors the new BETA strategies
        # (Fibonacci Confluence + Triple Confirmation). Gives ML a chance
        # to learn which Fib levels / zones actually predict direction.
        # ------------------------------------------------------------

        # Fibonacci distance features: how close is price to each of the 5
        # classic retracement levels of the last 30-bar swing range?
        # Output in BPS (basis points * 10,000) with sign (negative = below).
        if len(close) >= 30:
            swing_hi = np.max(high[-30:])
            swing_lo = np.min(low[-30:])
            rng_fib = swing_hi - swing_lo
            if rng_fib > 0:
                price = close[-1]
                # Direction of the recent impulse: hi_idx vs lo_idx
                hi_idx = int(np.argmax(high[-30:]))
                lo_idx = int(np.argmin(low[-30:]))
                impulse_up = lo_idx < hi_idx
                features['fib_impulse_up'] = 1 if impulse_up else 0
                for ratio in (0.236, 0.382, 0.500, 0.618, 0.786):
                    if impulse_up:
                        level = swing_hi - ratio * rng_fib
                    else:
                        level = swing_lo + ratio * rng_fib
                    if level > 0:
                        features[f'fib_dist_{int(ratio * 1000)}'] = (price - level) / level * 10_000
                # Nearest-Fib level absolute distance in bps (always positive)
                if f'fib_dist_{int(0.618 * 1000)}' in features:
                    features['fib_nearest_bps'] = min(
                        abs(features[f'fib_dist_{int(r * 1000)}'])
                        for r in (0.236, 0.382, 0.500, 0.618, 0.786)
                        if f'fib_dist_{int(r * 1000)}' in features
                    )

        # Supply / Demand proximity: BPS distance to the nearest pivot high
        # (supply) and pivot low (demand) within the last 30 bars. Uses a
        # 3-bar fractal window — cheap enough for per-bar extraction.
        if len(close) >= 30:
            window_h = high[-30:]
            window_l = low[-30:]
            pivot_highs, pivot_lows = [], []
            for i in range(2, len(window_h) - 2):
                if (window_h[i] > window_h[i - 1] and window_h[i] > window_h[i - 2]
                        and window_h[i] > window_h[i + 1] and window_h[i] > window_h[i + 2]):
                    pivot_highs.append(float(window_h[i]))
                if (window_l[i] < window_l[i - 1] and window_l[i] < window_l[i - 2]
                        and window_l[i] < window_l[i + 1] and window_l[i] < window_l[i + 2]):
                    pivot_lows.append(float(window_l[i]))
            price = close[-1]
            if pivot_highs:
                nearest_supply = min(pivot_highs, key=lambda p: abs(p - price))
                features['supply_zone_bps'] = (price - nearest_supply) / nearest_supply * 10_000
                features['supply_zone_count'] = len(pivot_highs)
            if pivot_lows:
                nearest_demand = min(pivot_lows, key=lambda p: abs(p - price))
                features['demand_zone_bps'] = (price - nearest_demand) / nearest_demand * 10_000
                features['demand_zone_count'] = len(pivot_lows)

        # Volume Oscillator: (fast_ma − slow_ma) / slow_ma × 100. Confirms
        # institutional participation. Requires a volume column.
        if 'volume' in df.columns and len(close) >= 20:
            vol = df['volume'].values[max(0, idx - 19):idx + 1]
            if len(vol) >= 10 and vol.sum() > 0:
                vol_fast = np.mean(vol[-5:])
                vol_slow = np.mean(vol[-20:]) if len(vol) >= 20 else np.mean(vol)
                if vol_slow > 0:
                    features['volume_osc'] = (vol_fast - vol_slow) / vol_slow * 100.0
                    features['volume_spike'] = 1 if features['volume_osc'] > 15.0 else 0

        # ------------------------------------------------------------
        # NEW (Apr 24, 2026): Advanced AI Candlestick Patterns +
        # Multi-Timeframe Fusion + Volume Validation. Mirrors the
        # behavioral-pattern paradigm — pattern strength, MTF context
        # alignment, and volume-confirmed reversal logic.
        # ------------------------------------------------------------
        cdl_feats = self._extract_candlestick_patterns(open_p, high, low, close)
        features.update(cdl_feats)

        mtf_feats = self._extract_mtf_features(df, idx)
        features.update(mtf_feats)

        vol_feats = self._extract_volume_validation(
            df, idx, cdl_feats.get('cdl_pattern_score', 0)
        )
        features.update(vol_feats)

        # Hour/minute features
        try:
            ts = df['timestamp'].iloc[idx]
            if isinstance(ts, str):
                ts = pd.Timestamp(ts)
            features['hour_sin'] = np.sin(2 * np.pi * ts.hour / 24)
            features['hour_cos'] = np.cos(2 * np.pi * ts.hour / 24)
            features['minute_sin'] = np.sin(2 * np.pi * ts.minute / 60)
        except Exception:
            features['hour_sin'] = 0
            features['hour_cos'] = 0
            features['minute_sin'] = 0

        return features

    # ------------------------------------------------------------------
    # AI Candlestick Pattern Extractor (Apr 24, 2026)
    # ------------------------------------------------------------------
    def _extract_candlestick_patterns(self, open_p, high, low, close) -> Dict:
        """
        Detect candlestick reversal/continuation patterns with continuous
        strength scores rather than just binary flags. Returns up to 16
        features. `open_p, high, low, close` are 1-D numpy arrays where the
        last element is the current bar.
        """
        f = {}
        if len(close) < 3:
            return f

        # Current bar
        o, hi, lo, c = float(open_p[-1]), float(high[-1]), float(low[-1]), float(close[-1])
        rng = hi - lo if (hi - lo) > 0 else 1e-9
        body = abs(c - o)
        body_ratio = body / rng
        upper_wick = (hi - max(c, o)) / rng
        lower_wick = (min(c, o) - lo) / rng
        is_bull = c > o
        is_bear = c < o

        # Previous bar
        po, pc = float(open_p[-2]), float(close[-2])
        prev_body = abs(pc - po)
        prev_bull = pc > po
        prev_bear = pc < po

        # 1) Engulfing
        eng_bull = is_bull and prev_bear and c >= po and o <= pc and body > prev_body
        eng_bear = is_bear and prev_bull and c <= po and o >= pc and body > prev_body
        f['cdl_engulfing_bull'] = 1 if eng_bull else 0
        f['cdl_engulfing_bear'] = 1 if eng_bear else 0
        f['cdl_engulfing_strength'] = (body / prev_body) if (eng_bull or eng_bear) and prev_body > 0 else 0

        # 2) Hammer / Inverted Hammer (small body, long lower wick)
        hammer = body_ratio < 0.35 and lower_wick > 0.55 and upper_wick < 0.15
        inv_hammer = body_ratio < 0.35 and upper_wick > 0.55 and lower_wick < 0.15
        f['cdl_hammer'] = 1 if hammer else 0
        f['cdl_inverted_hammer'] = 1 if inv_hammer else 0
        f['cdl_hammer_strength'] = (lower_wick / max(body_ratio, 0.05)) if hammer else 0

        # 3) Shooting Star (after up move, small body, long upper wick)
        recent_up = len(close) >= 4 and close[-2] > close[-4]
        shooting_star = inv_hammer and recent_up
        f['cdl_shooting_star'] = 1 if shooting_star else 0
        f['cdl_shooting_star_strength'] = upper_wick / max(body_ratio, 0.05) if shooting_star else 0

        # 4) Doji (very small body, indecision)
        is_doji = body_ratio < 0.10
        f['cdl_doji'] = 1 if is_doji else 0
        f['cdl_doji_quality'] = (1.0 - body_ratio) if is_doji else 0

        # 5) Pin Bar — body in lower 1/3 (bull) or upper 1/3 (bear) of range
        close_pos = (c - lo) / rng
        f['cdl_pin_bar_bull'] = 1 if (lower_wick > 0.6 and close_pos > 0.6) else 0
        f['cdl_pin_bar_bear'] = 1 if (upper_wick > 0.6 and close_pos < 0.4) else 0

        # 6) Marubozu (body fills most of range, tiny wicks)
        f['cdl_marubozu_bull'] = 1 if (body_ratio > 0.85 and is_bull) else 0
        f['cdl_marubozu_bear'] = 1 if (body_ratio > 0.85 and is_bear) else 0

        # 7) 3-bar patterns (Morning/Evening Star, 3 White Soldiers, 3 Black Crows)
        if len(close) >= 4:
            o2, c2 = float(open_p[-3]), float(close[-3])
            o3, c3 = float(open_p[-4]), float(close[-4])
            body2 = abs(c2 - o2)

            # Morning Star: bear-big, small-doji, bull-big closing above mid of bar1
            morning_star = (
                c2 < o2 and body2 > rng * 0.5
                and abs(pc - po) < body2 * 0.4
                and is_bull and c > (o2 + c2) / 2
            )
            evening_star = (
                c2 > o2 and body2 > rng * 0.5
                and abs(pc - po) < body2 * 0.4
                and is_bear and c < (o2 + c2) / 2
            )
            f['cdl_morning_star'] = 1 if morning_star else 0
            f['cdl_evening_star'] = 1 if evening_star else 0

            # 3 White Soldiers / 3 Black Crows
            three_white = (
                c3 >= o3 and c2 > o2 and pc > po and is_bull
                and c > pc > c2 and o > o2  # progressively higher closes
            )
            three_black = (
                c3 <= o3 and c2 < o2 and pc < po and is_bear
                and c < pc < c2 and o < o2
            )
            f['cdl_3_white_soldiers'] = 1 if three_white else 0
            f['cdl_3_black_crows'] = 1 if three_black else 0
        else:
            f['cdl_morning_star'] = 0
            f['cdl_evening_star'] = 0
            f['cdl_3_white_soldiers'] = 0
            f['cdl_3_black_crows'] = 0

        # Aggregate pattern score: positive=bullish, negative=bearish
        bull_score = (
            f['cdl_engulfing_bull'] * 2 + f['cdl_hammer'] + f['cdl_pin_bar_bull'] * 2
            + f['cdl_marubozu_bull'] + f['cdl_morning_star'] * 3 + f['cdl_3_white_soldiers'] * 2
        )
        bear_score = (
            f['cdl_engulfing_bear'] * 2 + f['cdl_shooting_star'] + f['cdl_pin_bar_bear'] * 2
            + f['cdl_marubozu_bear'] + f['cdl_evening_star'] * 3 + f['cdl_3_black_crows'] * 2
        )
        f['cdl_pattern_score'] = bull_score - bear_score
        return f

    # ------------------------------------------------------------------
    # Multi-Timeframe Fusion Extractor (Apr 24, 2026)
    # ------------------------------------------------------------------
    def _extract_mtf_features(self, df: pd.DataFrame, idx: int) -> Dict:
        """
        Build 15s and 1m aggregations from the 5s base series and emit
        agreement/alignment features. 15s = group of 3 bars, 1m = 12 bars.
        Always returns the same 14 keys (zero-filled when history is short)
        so the feature pool stays stable across samples.
        """
        # Default zero-filled dict — keeps schema stable for SelectKBest
        f = {
            'mtf_rsi_5s_15s_align': 0, 'mtf_rsi_5s_1m_align': 0,
            'mtf_rsi_15s': 50.0, 'mtf_rsi_1m': 50.0,
            'mtf_ema_align_5s_15s': 0, 'mtf_ema_align_5s_1m': 0,
            'mtf_ema_trend_count': 0,
            'mtf_macd_agreement': 0, 'mtf_macd_sign_15s': 0, 'mtf_macd_sign_1m': 0,
            'mtf_momentum_score': 0.0, 'mtf_momentum_15s': 0.0, 'mtf_momentum_1m': 0.0,
            'mtf_trend_strength': 0,
        }
        if idx < 60:
            return f

        close = df['close'].values[:idx + 1]

        def agg_close(window: int) -> np.ndarray:
            # Take last bar of each window — fast proxy for higher-TF close
            tail = close[-(window * 40):] if len(close) >= window * 40 else close
            n = (len(tail) // window) * window
            if n < window * 4:
                return np.array([])
            reshaped = tail[-n:].reshape(-1, window)
            return reshaped[:, -1]

        def rsi(arr, period=14):
            if len(arr) < period + 1:
                return 50.0
            d = np.diff(arr[-(period + 1):])
            g = np.mean([x for x in d if x > 0]) if any(x > 0 for x in d) else 0
            ll = np.mean([-x for x in d if x < 0]) if any(x < 0 for x in d) else 0
            rs_ = g / ll if ll > 0 else 100
            return 100 - (100 / (1 + rs_))

        def ema_dir(arr, fast=5, slow=13):
            if len(arr) < slow + 1:
                return 0
            ef = pd.Series(arr).ewm(span=fast, adjust=False).mean().values[-1]
            es = pd.Series(arr).ewm(span=slow, adjust=False).mean().values[-1]
            return 1 if ef > es else (-1 if ef < es else 0)

        def macd_sign(arr):
            if len(arr) < 26:
                return 0
            ef = pd.Series(arr).ewm(span=12, adjust=False).mean().values[-1]
            es = pd.Series(arr).ewm(span=26, adjust=False).mean().values[-1]
            return 1 if ef > es else (-1 if ef < es else 0)

        rsi_5s = rsi(close, 14)
        ema_5s = ema_dir(close)
        macd_5s = macd_sign(close)
        mom_5s = (close[-1] - close[-6]) / close[-6] * 10000 if len(close) > 6 else 0

        c15 = agg_close(3)
        c1m = agg_close(12)

        rsi_15s = rsi(c15, 14) if len(c15) >= 15 else rsi_5s
        ema_15s = ema_dir(c15) if len(c15) >= 14 else ema_5s
        macd_15s = macd_sign(c15) if len(c15) >= 26 else 0
        rsi_1m = rsi(c1m, 14) if len(c1m) >= 15 else rsi_5s
        ema_1m = ema_dir(c1m) if len(c1m) >= 14 else ema_5s
        macd_1m = macd_sign(c1m) if len(c1m) >= 26 else 0

        # RSI agreement: both above 50 or both below 50
        f['mtf_rsi_5s_15s_align'] = 1 if (rsi_5s - 50) * (rsi_15s - 50) > 0 else 0
        f['mtf_rsi_5s_1m_align'] = 1 if (rsi_5s - 50) * (rsi_1m - 50) > 0 else 0
        f['mtf_rsi_1m'] = rsi_1m
        f['mtf_rsi_15s'] = rsi_15s

        # EMA trend agreement
        f['mtf_ema_align_5s_15s'] = 1 if (ema_5s == ema_15s and ema_5s != 0) else 0
        f['mtf_ema_align_5s_1m'] = 1 if (ema_5s == ema_1m and ema_5s != 0) else 0
        f['mtf_ema_trend_count'] = (1 if ema_5s > 0 else 0) + (1 if ema_15s > 0 else 0) + (1 if ema_1m > 0 else 0)

        # MACD sign agreement (count of TFs in same direction as 5s)
        macd_dir = 1 if macd_5s > 0 else (-1 if macd_5s < 0 else 0)
        f['mtf_macd_agreement'] = sum(
            1 for s in (macd_5s, macd_15s, macd_1m) if s == macd_dir and s != 0
        )
        f['mtf_macd_sign_15s'] = macd_15s
        f['mtf_macd_sign_1m'] = macd_1m

        # Momentum confluence: signed score combining 5s mom + 15s mom + 1m mom
        mom_15s = ((c15[-1] - c15[-4]) / c15[-4] * 10000) if len(c15) >= 4 and c15[-4] > 0 else 0
        mom_1m = ((c1m[-1] - c1m[-4]) / c1m[-4] * 10000) if len(c1m) >= 4 and c1m[-4] > 0 else 0
        f['mtf_momentum_score'] = (mom_5s + mom_15s + mom_1m) / 3.0
        f['mtf_momentum_15s'] = mom_15s
        f['mtf_momentum_1m'] = mom_1m

        # Trend strength: how many TFs (out of 3) agree on direction
        dirs = []
        for d in (ema_5s, ema_15s, ema_1m):
            if d > 0:
                dirs.append(1)
            elif d < 0:
                dirs.append(-1)
            else:
                dirs.append(0)
        non_zero = [d for d in dirs if d != 0]
        if non_zero:
            f['mtf_trend_strength'] = abs(sum(non_zero)) / len(non_zero)
        else:
            f['mtf_trend_strength'] = 0
        return f

    # ------------------------------------------------------------------
    # Volume Validation Extractor (Apr 24, 2026)
    # ------------------------------------------------------------------
    def _extract_volume_validation(self, df: pd.DataFrame, idx: int, pattern_score: float) -> Dict:
        """
        Confirm candlestick patterns with volume context. Returns 4 flags
        gauging whether pattern + volume agree (institutional confirmation).
        Always returns the same 4 keys (zero-filled on missing volume).
        """
        f = {
            'vol_spike_at_pattern': 0, 'vol_climactic': 0,
            'vol_pattern_confirm': 0, 'vol_ratio_20': 1.0,
        }
        if 'volume' not in df.columns or idx < 20:
            return f

        vol = df['volume'].values[max(0, idx - 19):idx + 1]
        if vol.sum() <= 0 or len(vol) < 10:
            return f

        avg20 = float(np.mean(vol[-20:])) if len(vol) >= 20 else float(np.mean(vol))
        cur_vol = float(vol[-1])
        vol_ratio = cur_vol / avg20 if avg20 > 0 else 1.0

        # Volume spike at pattern: pattern fired AND vol > 1.2x avg
        f['vol_spike_at_pattern'] = 1 if (abs(pattern_score) > 0 and vol_ratio > 1.2) else 0

        # Climactic volume: cur > 2x avg-20 (capitulation/exhaustion)
        f['vol_climactic'] = 1 if vol_ratio > 2.0 else 0

        # Pattern+volume confirmation: bull pattern with rising volume OR bear with rising
        prev_vol = float(vol[-2]) if len(vol) >= 2 else cur_vol
        rising = cur_vol > prev_vol
        f['vol_pattern_confirm'] = 1 if (abs(pattern_score) > 0 and rising) else 0

        # Volume ratio (continuous) — useful for ML
        f['vol_ratio_20'] = vol_ratio
        return f

    async def train_from_otc(self, ml_system, symbols: List[str] = None,
                              min_samples: int = 200) -> Dict:
        """
        Train an ML model using accumulated OTC candle data.
        Uses adaptive thresholds and 5s-optimized features.
        """
        if not ML_AVAILABLE:
            return {"success": False, "error": "ML libraries not available"}

        try:
            all_symbols = symbols or ['EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC', 'EURJPY_OTC']

            all_features = []
            all_labels = []
            feature_names = None
            symbol_stats = {}

            for symbol in all_symbols:
                df = await self.get_otc_training_data(symbol, limit=10000)
                if df.empty or len(df) < 50:
                    symbol_stats[symbol] = {"status": "insufficient_data", "candles": len(df)}
                    continue

                labels, valid = self.generate_labels(df, timeframe='5s')
                valid_count = valid.sum()

                if valid_count < 20:
                    symbol_stats[symbol] = {"status": "insufficient_labels", "candles": len(df), "valid": int(valid_count)}
                    continue

                samples = 0
                for idx in range(30, len(df)):
                    if not valid.iloc[idx]:
                        continue

                    feats = self.extract_5s_features(df, idx)
                    if feats:
                        if feature_names is None:
                            feature_names = list(feats.keys())
                        
                        # Ensure consistent feature vector
                        feat_vec = [feats.get(fn, 0) for fn in feature_names]
                        all_features.append(feat_vec)
                        all_labels.append(int(labels.iloc[idx]))
                        samples += 1

                symbol_stats[symbol] = {"status": "ok", "candles": len(df), "samples": samples}
                logger.info(f"OTC {symbol}: {samples} samples from {len(df)} candles")

            if len(all_features) < min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient OTC data: {len(all_features)} samples (need {min_samples}). Collect more candles by running the Tampermonkey script.",
                    "symbol_stats": symbol_stats,
                    "total_samples": len(all_features)
                }

            X = np.array(all_features, dtype=float)
            y = np.array(all_labels)
            
            # Replace any NaN/inf with 0
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

            logger.info(f"OTC Training: {len(X)} samples, {X.shape[1]} features")
            logger.info(f"Class dist: CALL={sum(y)}, PUT={len(y) - sum(y)}")

            # Iter 57 — TEMPORAL OUT-OF-SAMPLE HOLD-OUT (anti-overfit)
            # Switch Markets best practice: "Always validate your strategy on
            # out-of-sample data". Reserve the FINAL 15% of samples (chrono-
            # logical) as a held-out test set the model never sees during
            # training/CV. This gives an honest read on overfitting:
            #   - cv_accuracy >> test_accuracy → model memorised training data
            #   - cv_accuracy ≈ test_accuracy → genuine generalisation
            # Order is preserved across get_otc_training_data() so the split
            # is truly forward-walking.
            test_fraction = 0.15
            test_size = max(1, int(len(X) * test_fraction))
            X_train, X_test = X[:-test_size], X[-test_size:]
            y_train, y_test = y[:-test_size], y[-test_size:]
            logger.info(
                f"OTC split → train={len(X_train)} | test (hold-out, never seen by CV)={len(X_test)}"
            )

            # Feature selection — fit on TRAIN ONLY (test must remain unseen)
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            n_features = min(70, X.shape[1])
            selector = SelectKBest(mutual_info_classif, k=n_features)
            X_train_selected = selector.fit_transform(X_train_scaled, y_train)
            X_test_selected = selector.transform(X_test_scaled)

            # Cross-validate on training portion only
            tscv = TimeSeriesSplit(n_splits=5)
            cv_scores = cross_val_score(ml_system.model, X_train_selected, y_train, cv=tscv, scoring='accuracy', n_jobs=-1)

            logger.info(f"OTC CV scores: {cv_scores}")
            logger.info(f"OTC Mean CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

            # Train final model on full training portion
            ml_system.model.fit(X_train_selected, y_train)
            
            # Score on the held-out test set — this is the honest accuracy
            train_score = ml_system.model.score(X_train_selected, y_train)
            test_score = ml_system.model.score(X_test_selected, y_test)
            overfit_gap = train_score - test_score
            overfit_warning = overfit_gap > 0.10  # >10% drop = clear overfitting

            logger.info(
                f"OTC train_acc={train_score:.4f} | test_acc={test_score:.4f} | gap={overfit_gap:.4f}"
                + (" ⚠️ OVERFIT" if overfit_warning else " ✓")
            )

            # Now refit on ALL data (train+test) so production predictions use
            # everything we know. The test score above is what we REPORT, but
            # the deployed model uses every sample available.
            X_all_scaled = scaler.fit_transform(X)
            X_all_selected = selector.fit_transform(X_all_scaled, y)
            ml_system.model.fit(X_all_selected, y)
            ml_system.is_trained = True
            # Use the honest hold-out score as the published accuracy, not CV
            ml_system.model_accuracy = test_score
            ml_system.scaler = scaler
            ml_system.last_training_time = datetime.now(timezone.utc)
            # Persist tuner-pipeline metadata so predict_with_tuner_pipeline()
            # can rebuild the EXACT feature vector at inference time.
            ml_system.tuner_feature_names = feature_names
            ml_system.tuner_selected_mask = selector.get_support().tolist() if hasattr(selector, 'get_support') else None
            # Iter 57 — persist OOS metrics on the ml_system so get_tuning_report()
            # can surface them back to the UI between training runs.
            ml_system.tuner_oos_metrics = {
                "cv_accuracy": round(cv_scores.mean() * 100, 2),
                "cv_std": round(cv_scores.std() * 100, 2),
                "train_accuracy": round(train_score * 100, 2),
                "test_accuracy": round(test_score * 100, 2),
                "overfit_gap": round(overfit_gap * 100, 2),
                "overfit_warning": bool(overfit_warning),
                "train_samples": int(len(X_train)),
                "test_samples": int(len(X_test)),
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "source": "otc_candles_5s",
            }
            ml_system._save_model()

            # Get selected feature names
            if feature_names:
                mask = selector.get_support()
                selected_names = [feature_names[i] for i in range(len(feature_names)) if i < len(mask) and mask[i]]
            else:
                selected_names = []

            return {
                "success": True,
                "source": "otc_candles_5s",
                "total_samples": len(X),
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "features_used": n_features,
                "features_total": X.shape[1],
                "selected_features": selected_names[:15],
                "cv_accuracy": round(cv_scores.mean() * 100, 2),
                "cv_std": round(cv_scores.std() * 100, 2),
                "cv_scores": [round(s * 100, 2) for s in cv_scores.tolist()],
                # Iter 57 — true out-of-sample test scores
                "train_accuracy": round(train_score * 100, 2),
                "test_accuracy": round(test_score * 100, 2),
                "overfit_gap": round(overfit_gap * 100, 2),
                "overfit_warning": overfit_warning,
                "headline_accuracy": round(test_score * 100, 2),
                "class_distribution": {"CALL": int(sum(y)), "PUT": int(len(y) - sum(y))},
                "symbol_stats": symbol_stats,
                "trained_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"OTC training error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    async def train_from_trade_reports(
        self,
        ml_system,
        min_samples: int = 50,
        symbols: Optional[List[str]] = None,
        max_age_days: int = 90,
        oanda_fallback: bool = True,
    ) -> Dict:
        """
        Train ML model using REAL Tampermonkey trade outcomes (Iter 54).

        For each closed trade in `tm_trade_reports` with outcome WIN/LOSS:
          1. Locate the OTC candle window at the trade's entry timestamp
             (or fetch OANDA S5 backfill on demand when OTC pool is stale)
          2. Extract the same 5s feature vector the live predictor uses
          3. Derive the ground-truth label from the OUTCOME, not synthetic
             next-candle direction:
                WIN  + CALL → label 1 (CALL was correct → market went UP)
                WIN  + PUT  → label 0 (PUT  was correct → market went DOWN)
                LOSS + CALL → label 0 (CALL lost → market actually went DOWN)
                LOSS + PUT  → label 1 (PUT  lost → market actually went UP)

        This trains the model on REAL trades you actually took — calibration is
        grounded in market outcomes that paid out (or didn't), not next-candle
        proxy labels. Sharpens accuracy/confidence on the same setups the bot
        will see live.
        """
        if not ML_AVAILABLE:
            return {"success": False, "error": "ML libraries not available"}

        try:
            reports_coll = self.db["tm_trade_reports"]
            
            # 1) Pull closed trades within max_age_days, optionally per-symbol
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
            query: Dict[str, Any] = {
                "outcome": {"$in": ["WIN", "LOSS", "win", "loss"]},
                "server_received_at": {"$gte": cutoff},
            }
            if symbols:
                query["asset_normalized"] = {"$in": symbols}
            
            reports = await reports_coll.find(query, {"_id": 0}).sort("server_received_at", 1).to_list(length=20000)
            if not reports:
                return {
                    "success": False,
                    "error": "No closed trade reports in window. Run the Tampermonkey bot to accumulate WIN/LOSS outcomes.",
                    "total_samples": 0,
                }
            
            # 2) Group by symbol for efficient candle fetch. Track weekend
            # trades separately — OANDA forex is closed on Sat/Sun so those
            # PO OTC trades can't be matched to real market candles. Real-
            # outcome training therefore only learns from weekday entries
            # (still a strong signal — same indicators, same execution path).
            symbol_groups: Dict[str, List[Dict]] = {}
            weekend_skipped = 0
            for r in reports:
                sym = r.get("asset_normalized") or r.get("asset")
                if not sym:
                    continue
                ts_raw = r.get("server_received_at") or r.get("timestamp")
                if ts_raw:
                    try:
                        ts_parsed = pd.to_datetime(ts_raw, errors="coerce", utc=True)
                        if not pd.isna(ts_parsed) and ts_parsed.dayofweek >= 5:  # Sat=5, Sun=6
                            weekend_skipped += 1
                            continue
                    except Exception:
                        pass
                symbol_groups.setdefault(sym, []).append(r)
            
            all_features: List[List[float]] = []
            all_labels: List[int] = []
            feature_names: Optional[List[str]] = None
            symbol_stats: Dict[str, Any] = {}
            outcome_counts = {"WIN_CALL": 0, "WIN_PUT": 0, "LOSS_CALL": 0, "LOSS_PUT": 0}
            unmatched = 0  # trades without nearby candle window
            oanda_fallback_used = 0  # trades resolved via OANDA backfill
            
            # OANDA fallback setup (lazy)
            oanda_service = None
            oanda_map = None
            if oanda_fallback:
                try:
                    from enhanced_oanda_service import enhanced_oanda
                    from routes.ml import OTC_TO_OANDA
                    if enhanced_oanda and getattr(enhanced_oanda, "is_configured", False):
                        oanda_service = enhanced_oanda
                        oanda_map = OTC_TO_OANDA
                        logger.info("[real-trade-train] OANDA fallback enabled")
                except Exception as e:
                    logger.warning(f"[real-trade-train] OANDA fallback unavailable: {e}")
            
            for sym, sym_reports in symbol_groups.items():
                # Pull all OTC candles for this symbol (oldest first)
                df = await self.get_otc_training_data(sym, limit=20000)
                has_otc = not df.empty and len(df) >= 31
                if has_otc:
                    df = df.reset_index(drop=True)
                    if "timestamp" not in df.columns:
                        has_otc = False
                    else:
                        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
                
                # OANDA fallback: ONE batched fetch covering all this symbol's trades.
                # Cap the window so we don't pull excessive batches (>30 days
                # would mean many thousand S5 batches and might rate-limit).
                oanda_df = None
                if oanda_service and oanda_map and sym in oanda_map:
                    try:
                        from datetime import timedelta as _td
                        sym_ts = []
                        for r in sym_reports:
                            tsr = r.get("server_received_at") or r.get("timestamp")
                            if tsr:
                                ts_parsed = pd.to_datetime(tsr, errors="coerce", utc=True)
                                if not pd.isna(ts_parsed):
                                    sym_ts.append(ts_parsed)
                        if sym_ts:
                            ts_min = min(sym_ts)
                            ts_max = max(sym_ts)
                            # Cap window to 30 days (typical max_age_days range)
                            if (ts_max - ts_min) > _td(days=30):
                                ts_min = ts_max - _td(days=30)
                            window_start = (ts_min - _td(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
                            window_end = (ts_max + _td(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                            oanda_pair = oanda_map[sym]
                            ohlc = await asyncio.to_thread(
                                oanda_service.get_candles_large,
                                instrument=oanda_pair,
                                granularity="S5",
                                from_time=window_start,
                                to_time=window_end,
                            )
                            if ohlc is not None and not ohlc.empty:
                                ohlc = ohlc.reset_index()
                                for col in ('open', 'high', 'low', 'close', 'volume'):
                                    if col in ohlc.columns:
                                        ohlc[col] = pd.to_numeric(ohlc[col], errors='coerce')
                                ohlc = ohlc.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
                                if len(ohlc) >= 31:
                                    ohlc["_ts"] = pd.to_datetime(ohlc["timestamp"], errors="coerce", utc=True)
                                    oanda_df = ohlc
                                    logger.info(
                                        f"[real-trade-train] {sym}: OANDA fetched {len(ohlc)} S5 candles "
                                        f"covering {window_start} → {window_end}"
                                    )
                    except Exception as oe:
                        logger.warning(f"[real-trade-train] OANDA batch fetch failed for {sym}: {oe}")
                
                matched = 0
                fallback_used_this_sym = 0
                for r in sym_reports:
                    trade_ts_raw = r.get("server_received_at") or r.get("timestamp")
                    if not trade_ts_raw:
                        unmatched += 1
                        continue
                    try:
                        trade_ts = pd.to_datetime(trade_ts_raw, errors="coerce", utc=True)
                        if pd.isna(trade_ts):
                            unmatched += 1
                            continue
                    except Exception:
                        unmatched += 1
                        continue
                    
                    feats = None
                    # Try OTC pool first
                    if has_otc:
                        deltas = (df["_ts"] - trade_ts).dt.total_seconds()
                        # Allow the candle to be up to 5 minutes before trade
                        eligible = (deltas <= 0) & (deltas >= -300)
                        if eligible.any():
                            idx = int(deltas[eligible].abs().idxmin())
                            if idx >= 30:
                                feats = self.extract_5s_features(df, idx)
                    
                    # Fall back to OANDA S5 batch
                    if feats is None and oanda_df is not None:
                        deltas = (oanda_df["_ts"] - trade_ts).dt.total_seconds()
                        eligible = (deltas <= 0) & (deltas >= -300)
                        if eligible.any():
                            idx = int(deltas[eligible].abs().idxmin())
                            if idx >= 30:
                                feats = self.extract_5s_features(oanda_df, idx)
                                if feats is not None:
                                    oanda_fallback_used += 1
                                    fallback_used_this_sym += 1
                    
                    if feats is None:
                        unmatched += 1
                        continue
                    
                    if feature_names is None:
                        feature_names = list(feats.keys())
                    feat_vec = [feats.get(fn, 0) for fn in feature_names]
                    
                    # Derive ground-truth label from REAL outcome
                    direction = (r.get("direction") or "").upper()
                    outcome = (r.get("outcome") or "").upper()
                    if direction == "CALL" and outcome == "WIN":
                        label = 1
                        outcome_counts["WIN_CALL"] += 1
                    elif direction == "PUT" and outcome == "WIN":
                        label = 0
                        outcome_counts["WIN_PUT"] += 1
                    elif direction == "CALL" and outcome == "LOSS":
                        label = 0  # CALL lost → actual move was DOWN
                        outcome_counts["LOSS_CALL"] += 1
                    elif direction == "PUT" and outcome == "LOSS":
                        label = 1  # PUT lost → actual move was UP
                        outcome_counts["LOSS_PUT"] += 1
                    else:
                        unmatched += 1
                        continue
                    
                    all_features.append(feat_vec)
                    all_labels.append(label)
                    matched += 1
                
                symbol_stats[sym] = {
                    "trades": len(sym_reports),
                    "matched": matched,
                    "unmatched": len(sym_reports) - matched,
                    "oanda_fallback": fallback_used_this_sym,
                }
                logger.info(
                    f"[real-trade-train] {sym}: matched {matched}/{len(sym_reports)} "
                    f"(OANDA fallback: {fallback_used_this_sym})"
                )
            
            if len(all_features) < min_samples:
                return {
                    "success": False,
                    "error": (
                        f"Insufficient matched samples: {len(all_features)} (need {min_samples}). "
                        f"Either too few WIN/LOSS reports, or trade timestamps don't align with "
                        f"otc_candles_5s history and OANDA fallback is unavailable / unfunded."
                    ),
                    "total_samples": len(all_features),
                    "symbol_stats": symbol_stats,
                    "outcome_counts": outcome_counts,
                    "unmatched": unmatched,
                    "oanda_fallback_used": oanda_fallback_used,
                }
            
            X = np.array(all_features, dtype=float)
            y = np.array(all_labels)
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
            
            logger.info(f"[real-trade-train] {len(X)} samples ({X.shape[1]} features). "
                        f"Class dist CALL={int(sum(y))}, PUT={int(len(y) - sum(y))}")
            
            # Iter 57 — out-of-sample hold-out (anti-overfit). Same logic as
            # train_from_otc: reserve the final 15% chronologically as a test
            # set the model never sees during training/CV. Reports an honest
            # `test_accuracy` and an `overfit_warning` when train-test gap
            # exceeds 10%.
            test_fraction = 0.15
            test_size = max(1, int(len(X) * test_fraction))
            X_train, X_test = X[:-test_size], X[-test_size:]
            y_train, y_test = y[:-test_size], y[-test_size:]
            
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            n_features = min(70, X.shape[1])
            selector = SelectKBest(mutual_info_classif, k=n_features)
            X_train_selected = selector.fit_transform(X_train_scaled, y_train)
            X_test_selected = selector.transform(X_test_scaled)
            
            # Cross-validate (TimeSeriesSplit; n_splits ≤ samples/10 to keep folds valid)
            n_splits = max(2, min(5, len(X_train) // 10))
            tscv = TimeSeriesSplit(n_splits=n_splits)
            cv_scores = cross_val_score(ml_system.model, X_train_selected, y_train, cv=tscv, scoring="accuracy", n_jobs=-1)
            
            ml_system.model.fit(X_train_selected, y_train)
            train_score = ml_system.model.score(X_train_selected, y_train)
            test_score = ml_system.model.score(X_test_selected, y_test) if len(X_test) > 0 else 0.0
            overfit_gap = train_score - test_score
            overfit_warning = overfit_gap > 0.10
            
            logger.info(
                f"[real-trade-train] train_acc={train_score:.4f} | test_acc={test_score:.4f} | "
                f"gap={overfit_gap:.4f}" + (" ⚠️ OVERFIT" if overfit_warning else " ✓")
            )
            
            # Refit on all data for production
            X_all_scaled = scaler.fit_transform(X)
            X_all_selected = selector.fit_transform(X_all_scaled, y)
            ml_system.model.fit(X_all_selected, y)
            ml_system.is_trained = True
            ml_system.model_accuracy = float(test_score)
            ml_system.scaler = scaler
            ml_system.last_training_time = datetime.now(timezone.utc)
            ml_system.tuner_feature_names = feature_names
            ml_system.tuner_selected_mask = (
                selector.get_support().tolist() if hasattr(selector, "get_support") else None
            )
            # Iter 57 — persist OOS metrics for tuning-report surface-up
            ml_system.tuner_oos_metrics = {
                "cv_accuracy": round(float(cv_scores.mean()) * 100, 2),
                "cv_std": round(float(cv_scores.std()) * 100, 2),
                "train_accuracy": round(train_score * 100, 2),
                "test_accuracy": round(test_score * 100, 2),
                "overfit_gap": round(overfit_gap * 100, 2),
                "overfit_warning": bool(overfit_warning),
                "train_samples": int(len(X_train)),
                "test_samples": int(len(X_test)),
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "source": "tm_trade_reports",
            }
            try:
                ml_system._save_model()
            except Exception as save_err:
                logger.warning(f"[real-trade-train] _save_model failed: {save_err}")
            
            selected_names: List[str] = []
            if feature_names:
                mask = selector.get_support()
                selected_names = [feature_names[i] for i in range(len(feature_names)) if i < len(mask) and mask[i]]
            
            return {
                "success": True,
                "source": "tm_trade_reports",
                "method": "real-outcome-grounded",
                "total_samples": len(X),
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "features_used": n_features,
                "features_total": X.shape[1],
                "selected_features": selected_names[:15],
                "cv_accuracy": round(float(cv_scores.mean()) * 100, 2),
                "cv_std": round(float(cv_scores.std()) * 100, 2),
                "cv_scores": [round(float(s) * 100, 2) for s in cv_scores.tolist()],
                "n_splits": n_splits,
                # Iter 57 — out-of-sample metrics
                "train_accuracy": round(train_score * 100, 2),
                "test_accuracy": round(test_score * 100, 2),
                "overfit_gap": round(overfit_gap * 100, 2),
                "overfit_warning": overfit_warning,
                "headline_accuracy": round(test_score * 100, 2),
                "class_distribution": {"CALL": int(sum(y)), "PUT": int(len(y) - sum(y))},
                "outcome_counts": outcome_counts,
                "symbol_stats": symbol_stats,
                "unmatched_trades": unmatched,
                "weekend_trades_skipped": weekend_skipped,
                "oanda_fallback_used": oanda_fallback_used,
                "max_age_days": max_age_days,
                "trained_at": datetime.now(timezone.utc).isoformat(),
            }
        
        except Exception as e:
            logger.exception(f"[real-trade-train] error: {e}")
            return {"success": False, "error": str(e)}



    async def get_tuning_report(self) -> Dict:
        """Generate a report on current ML model accuracy and OTC data availability."""
        try:
            # OTC data stats
            pipeline = [
                {"$group": {
                    "_id": "$symbol",
                    "count": {"$sum": 1},
                    "oldest": {"$min": "$timestamp"},
                    "newest": {"$max": "$timestamp"}
                }},
                {"$sort": {"count": -1}}
            ]

            otc_stats = []
            total_otc = 0
            async for doc in self.otc_collection.aggregate(pipeline):
                otc_stats.append({
                    "symbol": doc["_id"],
                    "candles": doc["count"],
                    "oldest": doc.get("oldest"),
                    "newest": doc.get("newest"),
                    "trainable": doc["count"] >= 200
                })
                total_otc += doc["count"]

            return {
                "success": True,
                "otc_data": {
                    "total_candles": total_otc,
                    "by_symbol": otc_stats,
                    "min_required": 200,
                    "ready_for_training": total_otc >= 200
                },
                "tuning_config": {
                    "timeframe_thresholds": TIMEFRAME_THRESHOLDS,
                    "prediction_horizons": TIMEFRAME_HORIZONS,
                    "feature_selection": "SelectKBest (mutual_info_classif, k=70)",
                    "cross_validation": "TimeSeriesSplit (5 splits)",
                    "new_features_apr23": [
                        "fib_impulse_up", "fib_dist_236", "fib_dist_382",
                        "fib_dist_500", "fib_dist_618", "fib_dist_786",
                        "fib_nearest_bps",
                        "supply_zone_bps", "supply_zone_count",
                        "demand_zone_bps", "demand_zone_count",
                        "volume_osc", "volume_spike",
                    ],
                    "candlestick_mtf_apr24": {
                        "candlestick_patterns": [
                            "cdl_engulfing_bull", "cdl_engulfing_bear", "cdl_engulfing_strength",
                            "cdl_hammer", "cdl_inverted_hammer", "cdl_hammer_strength",
                            "cdl_shooting_star", "cdl_shooting_star_strength",
                            "cdl_doji", "cdl_doji_quality",
                            "cdl_pin_bar_bull", "cdl_pin_bar_bear",
                            "cdl_marubozu_bull", "cdl_marubozu_bear",
                            "cdl_morning_star", "cdl_evening_star",
                            "cdl_3_white_soldiers", "cdl_3_black_crows",
                            "cdl_pattern_score",
                        ],
                        "multi_timeframe_fusion": [
                            "mtf_rsi_5s_15s_align", "mtf_rsi_5s_1m_align",
                            "mtf_rsi_15s", "mtf_rsi_1m",
                            "mtf_ema_align_5s_15s", "mtf_ema_align_5s_1m",
                            "mtf_ema_trend_count",
                            "mtf_macd_agreement", "mtf_macd_sign_15s", "mtf_macd_sign_1m",
                            "mtf_momentum_score", "mtf_momentum_15s", "mtf_momentum_1m",
                            "mtf_trend_strength",
                        ],
                        "volume_validation": [
                            "vol_spike_at_pattern", "vol_climactic",
                            "vol_pattern_confirm", "vol_ratio_20",
                        ],
                        "k_bumped_to": 70,
                        "added_on": "2026-04-24",
                    },
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


_ml_tuner = None

def get_ml_tuner(db) -> MLAccuracyTuner:
    global _ml_tuner
    if _ml_tuner is None:
        _ml_tuner = MLAccuracyTuner(db)
    return _ml_tuner


async def train_lstm_gru_from_otc(db, lstm_system, symbols: List[str] = None, epochs: int = 30) -> Dict:
    """
    Feed the OTC candle pool through LSTMGRUSystem.train() (Iter 66, Apr 25, 2026).
    LSTM needs `candles: List[Dict]` so we pull raw OHLCV rows and concatenate.
    """
    tuner = get_ml_tuner(db)
    symbols = symbols or ['EURUSD_OTC', 'AUDCAD_OTC', 'GBPJPY_OTC']
    all_candles = []
    per_sym_counts = {}

    for sym in symbols:
        df = await tuner.get_otc_training_data(sym, limit=10000)
        if df is None or df.empty:
            per_sym_counts[sym] = 0
            continue
        records = df.to_dict('records')
        all_candles.extend(records)
        per_sym_counts[sym] = len(records)

    if len(all_candles) < 200:
        return {
            "success": False,
            "error": f"Insufficient OTC data: {len(all_candles)} candles (need 200)",
            "symbols_checked": per_sym_counts,
        }

    result = lstm_system.train(all_candles, epochs=epochs, batch_size=32)
    result["source"] = "otc_candles_5s"
    result["total_candles"] = len(all_candles)
    result["symbols"] = per_sym_counts
    result["trained_at"] = datetime.now(timezone.utc).isoformat()
    return result


async def train_ppo_from_otc(db, ppo_agent, symbols: List[str] = None, n_episodes: int = 20) -> Dict:
    """
    Feed the OTC candle pool through PPOAgent.train() (Iter 66, Apr 25, 2026).
    PPO needs (features: np.ndarray, closes: np.ndarray). We extract features
    via the same MLAccuracyTuner.extract_5s_features() so PPO sees the EXACT
    same 84/90-feature vector the sklearn models train on — ensuring the RL
    agent benefits from the candlestick + MTF + volume features.
    """
    tuner = get_ml_tuner(db)
    symbols = symbols or ['EURUSD_OTC', 'AUDCAD_OTC', 'GBPJPY_OTC']
    all_features, all_closes, per_sym_counts = [], [], {}
    feat_names = None

    for sym in symbols:
        df = await tuner.get_otc_training_data(sym, limit=5000)
        if df is None or df.empty:
            per_sym_counts[sym] = 0
            continue
        closes = df['close'].astype(float).values
        sym_features = []
        for idx in range(30, len(df)):
            feats = tuner.extract_5s_features(df, idx)
            if not feats:
                continue
            if feat_names is None:
                feat_names = list(feats.keys())
            sym_features.append([feats.get(n, 0.0) for n in feat_names])
        if sym_features:
            per_sym_counts[sym] = len(sym_features)
            all_features.extend(sym_features)
            # Align closes with features (features start at idx=30)
            all_closes.extend(closes[30:30 + len(sym_features)].tolist())

    if len(all_features) < 200:
        return {
            "success": False,
            "error": f"Insufficient OTC data: {len(all_features)} feature rows (need 200)",
            "symbols_checked": per_sym_counts,
        }

    features_arr = np.nan_to_num(
        np.array(all_features, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0
    )
    closes_arr = np.array(all_closes, dtype=np.float32)
    result = ppo_agent.train(features_arr, closes_arr, n_episodes=n_episodes)
    result["source"] = "otc_candles_5s"
    result["total_samples"] = len(all_features)
    result["symbols"] = per_sym_counts
    result["trained_at"] = datetime.now(timezone.utc).isoformat()
    result["feature_count"] = len(feat_names or [])
    return result


def predict_with_tuner_pipeline(ml_system, df: pd.DataFrame) -> Optional[Dict]:
    """
    Predict using a model that was trained via MLAccuracyTuner.train_from_otc().
    Bypasses each system's native extract_features() (which produces a different
    feature count). Uses extract_5s_features() so the input matches the trained
    scaler's expected input shape.

    Returns {direction, confidence, call_probability, put_probability, model_accuracy, source}
    or None if the model isn't trained / df is too short.
    """
    if ml_system is None or not getattr(ml_system, "is_trained", False):
        return None
    if df is None or len(df) < 32:
        return None

    try:
        # Use a stub tuner — extract_5s_features doesn't actually need db access
        class _Stub:
            def __getitem__(self, name): return None
        tuner = MLAccuracyTuner(_Stub())

        # Coerce to 5s-style frame: ensure timestamp column + numeric OHLCV
        local = df.copy()
        if "timestamp" not in local.columns:
            local = local.reset_index().rename(columns={"index": "timestamp"})
        for col in ("open", "high", "low", "close"):
            if col not in local.columns:
                return None

        # Build the same 84/90-feature vector the trainer used at the LAST bar
        feats = tuner.extract_5s_features(local, len(local) - 1)
        if not feats:
            return None

        scaler = getattr(ml_system, "scaler", None)
        if scaler is None:
            return None

        expected = getattr(scaler, "n_features_in_", None)

        # Prefer the EXACT feature ordering used at training time
        names = getattr(ml_system, "tuner_feature_names", None)
        if names:
            vec = np.array([feats.get(n, 0.0) for n in names], dtype=float)
        else:
            # Fallback: insertion-order, then pad/truncate to expected length
            vec = np.array(list(feats.values()), dtype=float)

        vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)

        if expected is not None:
            if len(vec) > expected:
                vec = vec[:expected]
            elif len(vec) < expected:
                vec = np.concatenate([vec, np.zeros(expected - len(vec))])

        Xs = scaler.transform(vec.reshape(1, -1))

        # If a SelectKBest mask was persisted, use it (matches training-time
        # feature subset). Otherwise the model was fit on the post-scale
        # vector directly.
        mask = getattr(ml_system, "tuner_selected_mask", None)
        if mask is not None and len(mask) == Xs.shape[1]:
            Xs = Xs[:, np.array(mask, dtype=bool)]

        proba = ml_system.model.predict_proba(Xs)[0]
        # Class 1 = CALL, class 0 = PUT (consistent with train_from_otc labels)
        call_p = float(proba[1])
        put_p = float(proba[0])
        direction = "CALL" if call_p >= put_p else "PUT"
        confidence = max(call_p, put_p) * 100.0

        return {
            "direction": direction,
            "confidence": round(confidence, 2),
            "call_probability": round(call_p * 100, 2),
            "put_probability": round(put_p * 100, 2),
            "model_accuracy": round(getattr(ml_system, "model_accuracy", 0.5) * 100, 2),
            "source": "tuner_pipeline",
        }
    except Exception as e:
        logger.debug(f"predict_with_tuner_pipeline failed: {e}")
        return None
