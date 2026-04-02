"""
Advanced LSTM/GRU Time-Series Prediction System v2.0
=====================================================
Bidirectional LSTM + GRU with Attention for price direction prediction.
Proper feature engineering, auto-labeling, and OANDA training pipeline.
"""
import logging
import numpy as np
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Force CPU
try:
    import ml_config
except ImportError:
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    tf.config.set_visible_devices([], 'GPU')
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available - LSTM/GRU system disabled")


class FeatureEngine:
    """Calculate technical indicators from OHLCV candles."""

    @staticmethod
    def compute(candles: List[Dict]) -> np.ndarray:
        n = len(candles)
        if n < 30:
            return None

        closes = np.array([float(c.get('close', 0)) for c in candles])
        highs = np.array([float(c.get('high', 0)) for c in candles])
        lows = np.array([float(c.get('low', 0)) for c in candles])
        opens = np.array([float(c.get('open', 0)) for c in candles])
        volumes = np.array([float(c.get('volume', 0)) for c in candles])

        # 1. Returns (log)
        returns = np.zeros(n)
        returns[1:] = np.log(closes[1:] / (closes[:-1] + 1e-10))

        # 2. RSI (14)
        rsi = FeatureEngine._rsi(closes, 14)

        # 3-4. MACD (12, 26, 9)
        macd_line, macd_signal = FeatureEngine._macd(closes)

        # 5. Bollinger Band %B (20, 2)
        bb_pct = FeatureEngine._bb_percent(closes, 20)

        # 6-7. Stochastic K, D (14, 3)
        stoch_k, stoch_d = FeatureEngine._stochastic(highs, lows, closes, 14, 3)

        # 8. ATR (14) normalized
        atr = FeatureEngine._atr(highs, lows, closes, 14)
        atr_norm = atr / (closes + 1e-10)

        # 9. EMA ratio (9/21)
        ema9 = FeatureEngine._ema(closes, 9)
        ema21 = FeatureEngine._ema(closes, 21)
        ema_ratio = (ema9 - ema21) / (ema21 + 1e-10)

        # 10. Price momentum (5-bar)
        momentum = np.zeros(n)
        momentum[5:] = (closes[5:] - closes[:-5]) / (closes[:-5] + 1e-10)

        # 11. Volume ratio vs 20-period MA
        vol_ma = FeatureEngine._sma(volumes, 20)
        vol_ratio = volumes / (vol_ma + 1e-10)

        # 12. Candle body ratio
        body = np.abs(closes - opens)
        wick = highs - lows
        body_ratio = body / (wick + 1e-10)

        # 13. Higher-high / Lower-low indicator
        hh_ll = np.zeros(n)
        for i in range(1, n):
            if highs[i] > highs[i-1] and lows[i] > lows[i-1]:
                hh_ll[i] = 1.0  # Higher high + higher low (bullish)
            elif highs[i] < highs[i-1] and lows[i] < lows[i-1]:
                hh_ll[i] = -1.0  # Lower high + lower low (bearish)

        features = np.column_stack([
            returns,         # 0
            rsi / 100.0,     # 1 (normalized 0-1)
            macd_line,       # 2
            macd_signal,     # 3
            bb_pct,          # 4
            stoch_k / 100.0, # 5
            stoch_d / 100.0, # 6
            atr_norm,        # 7
            ema_ratio,       # 8
            momentum,        # 9
            vol_ratio,       # 10
            body_ratio,      # 11
            hh_ll,           # 12
        ])
        return features

    @staticmethod
    def _ema(data, period):
        result = np.zeros_like(data)
        result[0] = data[0]
        k = 2 / (period + 1)
        for i in range(1, len(data)):
            result[i] = data[i] * k + result[i-1] * (1 - k)
        return result

    @staticmethod
    def _sma(data, period):
        result = np.zeros_like(data)
        for i in range(len(data)):
            start = max(0, i - period + 1)
            result[i] = np.mean(data[start:i+1])
        return result

    @staticmethod
    def _rsi(closes, period=14):
        n = len(closes)
        rsi = np.full(n, 50.0)
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.zeros(n - 1)
        avg_loss = np.zeros(n - 1)
        if len(gains) >= period:
            avg_gain[period-1] = np.mean(gains[:period])
            avg_loss[period-1] = np.mean(losses[:period])
            for i in range(period, len(gains)):
                avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i]) / period
                avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i]) / period
            for i in range(period - 1, len(gains)):
                if avg_loss[i] == 0:
                    rsi[i+1] = 100
                else:
                    rs = avg_gain[i] / avg_loss[i]
                    rsi[i+1] = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _macd(closes, fast=12, slow=26, signal=9):
        ema_fast = FeatureEngine._ema(closes, fast)
        ema_slow = FeatureEngine._ema(closes, slow)
        macd = ema_fast - ema_slow
        macd_signal = FeatureEngine._ema(macd, signal)
        # Normalize by price
        price_scale = closes + 1e-10
        return macd / price_scale, macd_signal / price_scale

    @staticmethod
    def _bb_percent(closes, period=20, std_dev=2):
        sma = FeatureEngine._sma(closes, period)
        n = len(closes)
        std = np.zeros(n)
        for i in range(period - 1, n):
            std[i] = np.std(closes[max(0, i-period+1):i+1])
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        bb_range = upper - lower + 1e-10
        return (closes - lower) / bb_range

    @staticmethod
    def _stochastic(highs, lows, closes, k_period=14, d_period=3):
        n = len(closes)
        k = np.full(n, 50.0)
        for i in range(k_period - 1, n):
            h_high = np.max(highs[i-k_period+1:i+1])
            l_low = np.min(lows[i-k_period+1:i+1])
            denom = h_high - l_low
            if denom > 0:
                k[i] = ((closes[i] - l_low) / denom) * 100
        d = FeatureEngine._sma(k, d_period)
        return k, d

    @staticmethod
    def _atr(highs, lows, closes, period=14):
        n = len(closes)
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        atr = FeatureEngine._sma(tr, period)
        return atr


class AttentionLayer(layers.Layer):
    """Simple attention mechanism for LSTM/GRU sequences."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self, input_shape):
        self.W = self.add_weight(name='attn_W', shape=(input_shape[-1], input_shape[-1]), initializer='glorot_uniform')
        self.b = self.add_weight(name='attn_b', shape=(input_shape[-1],), initializer='zeros')
        self.u = self.add_weight(name='attn_u', shape=(input_shape[-1],), initializer='glorot_uniform')
        super().build(input_shape)

    def call(self, x):
        score = tf.nn.tanh(tf.tensordot(x, self.W, axes=1) + self.b)
        attn_weights = tf.nn.softmax(tf.tensordot(score, self.u, axes=1), axis=1)
        context = tf.reduce_sum(x * tf.expand_dims(attn_weights, -1), axis=1)
        return context


class LSTMGRUSystem:
    """
    Advanced LSTM/GRU system with:
    - Bidirectional LSTM + GRU layers
    - Attention mechanism
    - 13-feature technical indicator input
    - Auto-labeling from price movement
    - OANDA training pipeline
    """

    N_FEATURES = 13
    SEQUENCE_LEN = 30  # 30 candles lookback

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.training_history = {}
        self.model_path = '/app/backend/models/lstm_gru_v2.keras'
        self.stats_path = '/app/backend/models/lstm_gru_stats.json'
        self.accuracy = 0.0
        self.total_predictions = 0
        self.correct_predictions = 0
        self._load_stats()

        if TF_AVAILABLE:
            self._build_model()
            self._try_load()

    def _build_model(self):
        """Build Bidirectional LSTM + GRU model with Attention."""
        inp = layers.Input(shape=(self.SEQUENCE_LEN, self.N_FEATURES))

        # Bidirectional LSTM
        x = layers.Bidirectional(layers.LSTM(64, return_sequences=True))(inp)
        x = layers.Dropout(0.25)(x)

        # GRU layer
        x = layers.GRU(48, return_sequences=True)(x)
        x = layers.Dropout(0.2)(x)

        # Attention
        x = AttentionLayer()(x)

        # Dense head
        x = layers.Dense(32, activation='relu')(x)
        x = layers.Dropout(0.2)(x)
        out = layers.Dense(3, activation='softmax')(x)  # BUY, SELL, HOLD

        self.model = keras.Model(inputs=inp, outputs=out)
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        logger.info("LSTM/GRU model built: BiLSTM(64) + GRU(48) + Attention + Dense(32)")

    def _try_load(self):
        if os.path.exists(self.model_path):
            try:
                self.model = keras.models.load_model(
                    self.model_path,
                    custom_objects={'AttentionLayer': AttentionLayer}
                )
                self.is_trained = True
                logger.info(f"Loaded LSTM/GRU model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")
                self._build_model()

    def _load_stats(self):
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path) as f:
                    stats = json.load(f)
                self.accuracy = stats.get('accuracy', 0)
                self.total_predictions = stats.get('total_predictions', 0)
                self.correct_predictions = stats.get('correct_predictions', 0)
                self.training_history = stats.get('training_history', {})
            except Exception:
                pass

    def _save_stats(self):
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        with open(self.stats_path, 'w') as f:
            json.dump({
                'accuracy': self.accuracy,
                'total_predictions': self.total_predictions,
                'correct_predictions': self.correct_predictions,
                'training_history': self.training_history,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }, f)

    def _make_labels(self, closes: np.ndarray, lookahead: int = 5, threshold: float = 0.0003) -> np.ndarray:
        """
        Auto-label: compare price at t+lookahead vs t.
        0 = BUY (price goes up > threshold)
        1 = SELL (price goes down > threshold)
        2 = HOLD (flat)
        """
        n = len(closes)
        labels = np.full(n, 2, dtype=np.int32)  # default HOLD
        for i in range(n - lookahead):
            pct = (closes[i + lookahead] - closes[i]) / (closes[i] + 1e-10)
            if pct > threshold:
                labels[i] = 0  # BUY
            elif pct < -threshold:
                labels[i] = 1  # SELL
        return labels

    def prepare_training_data(self, candles: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Build X, y arrays from raw candles."""
        features = FeatureEngine.compute(candles)
        if features is None:
            return None, None

        closes = np.array([float(c.get('close', 0)) for c in candles])
        labels = self._make_labels(closes, lookahead=5)

        X, y = [], []
        for i in range(self.SEQUENCE_LEN, len(features) - 5):
            seq = features[i - self.SEQUENCE_LEN:i]
            X.append(seq)
            y.append(labels[i])

        if len(X) < 50:
            return None, None

        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.int32)

        # Replace NaN/Inf
        X = np.nan_to_num(X, nan=0.0, posinf=1.0, neginf=-1.0)
        return X, y

    def train(self, candles: List[Dict], epochs: int = 30, batch_size: int = 32) -> Dict:
        """Train on OANDA candle data."""
        if not TF_AVAILABLE or self.model is None:
            return {'success': False, 'error': 'TensorFlow not available'}

        X, y = self.prepare_training_data(candles)
        if X is None:
            return {'success': False, 'error': 'Insufficient data for training'}

        y_cat = keras.utils.to_categorical(y, num_classes=3)

        logger.info(f"Training LSTM/GRU: {len(X)} samples, {epochs} epochs")
        logger.info(f"  Label distribution: BUY={np.sum(y==0)}, SELL={np.sum(y==1)}, HOLD={np.sum(y==2)}")

        # Class weights to handle imbalance
        counts = np.bincount(y, minlength=3).astype(float)
        total = counts.sum()
        weights = {i: total / (3 * c + 1) for i, c in enumerate(counts)}

        history = self.model.fit(
            X, y_cat,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            class_weight=weights,
            verbose=0,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=3)
            ]
        )

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model.save(self.model_path)
        self.is_trained = True

        val_acc = history.history.get('val_accuracy', [0])[-1]
        train_acc = history.history.get('accuracy', [0])[-1]
        self.accuracy = val_acc * 100

        self.training_history = {
            'train_accuracy': round(train_acc * 100, 2),
            'val_accuracy': round(val_acc * 100, 2),
            'epochs_run': len(history.history['loss']),
            'samples': len(X),
            'label_dist': {'BUY': int(np.sum(y==0)), 'SELL': int(np.sum(y==1)), 'HOLD': int(np.sum(y==2))},
            'trained_at': datetime.now(timezone.utc).isoformat()
        }
        self._save_stats()

        logger.info(f"LSTM/GRU trained: train_acc={train_acc:.2%}, val_acc={val_acc:.2%}")
        return {
            'success': True,
            'train_accuracy': round(train_acc * 100, 2),
            'val_accuracy': round(val_acc * 100, 2),
            'epochs_run': len(history.history['loss']),
            'samples': len(X)
        }

    def predict(self, candles: List[Dict]) -> Optional[Dict]:
        """Predict direction from recent candles."""
        if not TF_AVAILABLE or self.model is None:
            return self._fallback(candles)

        features = FeatureEngine.compute(candles)
        if features is None or len(features) < self.SEQUENCE_LEN:
            return self._fallback(candles)

        seq = features[-self.SEQUENCE_LEN:]
        seq = np.nan_to_num(seq, nan=0.0, posinf=1.0, neginf=-1.0)
        X = seq.reshape(1, self.SEQUENCE_LEN, self.N_FEATURES).astype(np.float32)

        probs = self.model.predict(X, verbose=0)[0]
        buy_p, sell_p, hold_p = float(probs[0]), float(probs[1]), float(probs[2])

        if buy_p > sell_p and buy_p > hold_p and buy_p > 0.40:
            direction = 'BUY'
            confidence = buy_p * 100
        elif sell_p > buy_p and sell_p > hold_p and sell_p > 0.40:
            direction = 'SELL'
            confidence = sell_p * 100
        else:
            direction = 'HOLD'
            confidence = hold_p * 100

        self.total_predictions += 1
        return {
            'direction': direction,
            'confidence': round(confidence, 2),
            'probabilities': {'BUY': round(buy_p*100, 2), 'SELL': round(sell_p*100, 2), 'HOLD': round(hold_p*100, 2)},
            'method': 'LSTM_GRU' if self.is_trained else 'LSTM_GRU_UNTRAINED',
            'model_trained': self.is_trained
        }

    def _fallback(self, candles):
        if not candles or len(candles) < 10:
            return {'direction': 'HOLD', 'confidence': 50.0, 'method': 'FALLBACK', 'model_trained': False}
        prices = [float(c.get('close', 0)) for c in candles[-10:]]
        chg = prices[-1] - prices[0]
        if chg > 0:
            return {'direction': 'BUY', 'confidence': min(60 + abs(chg)*5000, 75), 'method': 'FALLBACK', 'model_trained': False}
        elif chg < 0:
            return {'direction': 'SELL', 'confidence': min(60 + abs(chg)*5000, 75), 'method': 'FALLBACK', 'model_trained': False}
        return {'direction': 'HOLD', 'confidence': 55.0, 'method': 'FALLBACK', 'model_trained': False}

    def get_stats(self) -> Dict:
        return {
            'model_type': 'BiLSTM + GRU + Attention',
            'is_trained': self.is_trained,
            'accuracy': round(self.accuracy, 2),
            'total_predictions': self.total_predictions,
            'sequence_length': self.SEQUENCE_LEN,
            'n_features': self.N_FEATURES,
            'training_history': self.training_history
        }


# Global instance
lstm_gru_system = LSTMGRUSystem()
