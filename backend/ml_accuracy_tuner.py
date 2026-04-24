"""
ML Accuracy Tuning Service
============================
Trains ML models using accumulated OTC candle data + OANDA data.
Applies adaptive labeling thresholds, feature selection, and hyperparameter tuning.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
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

            # Feature selection — keep top features
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X)

            n_features = min(50, X.shape[1])
            selector = SelectKBest(mutual_info_classif, k=n_features)
            X_selected = selector.fit_transform(X_scaled, y)

            # Cross-validate
            tscv = TimeSeriesSplit(n_splits=5)
            cv_scores = cross_val_score(ml_system.model, X_selected, y, cv=tscv, scoring='accuracy', n_jobs=-1)

            logger.info(f"OTC CV scores: {cv_scores}")
            logger.info(f"OTC Mean accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

            # Train final model
            ml_system.model.fit(X_selected, y)
            ml_system.is_trained = True
            ml_system.model_accuracy = cv_scores.mean()
            ml_system.scaler = scaler
            ml_system.last_training_time = datetime.now(timezone.utc)
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
                "features_used": n_features,
                "features_total": X.shape[1],
                "selected_features": selected_names[:15],
                "cv_accuracy": round(cv_scores.mean() * 100, 2),
                "cv_std": round(cv_scores.std() * 100, 2),
                "cv_scores": [round(s * 100, 2) for s in cv_scores.tolist()],
                "class_distribution": {"CALL": int(sum(y)), "PUT": int(len(y) - sum(y))},
                "symbol_stats": symbol_stats,
                "trained_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"OTC training error: {e}")
            import traceback
            traceback.print_exc()
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
                    "feature_selection": "SelectKBest (mutual_info_classif, k=50)",
                    "cross_validation": "TimeSeriesSplit (5 splits)",
                    "new_features_apr23": [
                        "fib_impulse_up", "fib_dist_236", "fib_dist_382",
                        "fib_dist_500", "fib_dist_618", "fib_dist_786",
                        "fib_nearest_bps",
                        "supply_zone_bps", "supply_zone_count",
                        "demand_zone_bps", "demand_zone_count",
                        "volume_osc", "volume_spike",
                    ],
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
