"""
AI/ML Trading Model Training Service
=====================================

Integrates with the backtesting system to:
1. Train ML models on backtest results
2. Identify winning patterns using Random Forest & Neural Networks
3. Optimize strategy parameters automatically
4. Continuous learning loop with daily retraining

Based on best practices from:
- Zipline ML4Trading workflow
- Walk-forward optimization
- Feature engineering for trading

Author: GPT Signal Bot
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from uuid import uuid4
import json
import pickle
import os

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.utils.class_weight import compute_sample_weight
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not available. ML features will be limited.")

# v8.75.0 — Optional SMOTE oversampling. When imbalanced-learn is available
# AND the minority class is severely under-represented (≤25% of training
# samples), we synthetically oversample so the trainer doesn't bias toward
# the majority class. Falls back to class_weight='balanced' / sample_weight
# when SMOTE is unavailable or unsafe (e.g. <5 minority samples).
try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    logger.warning("imbalanced-learn not available — falling back to class_weight only")


def _maybe_smote_balance(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    minority_threshold: float = 0.25,
    k_neighbors: int = 5,
) -> Tuple[np.ndarray, np.ndarray, str]:
    """v8.75.0 — Conditionally apply SMOTE to a training split.

    Returns the (possibly resampled) X/y plus a short tag explaining what
    happened (audited into model metadata). Gates the call so we never
    SMOTE when:
      * imblearn isn't installed
      * the classes are already balanced (minority ≥ threshold)
      * the minority class has < k_neighbors+1 samples (SMOTE crashes)
      * the labels aren't binary 0/1
    """
    try:
        y_arr = np.asarray(y_train).ravel()
        unique, counts = np.unique(y_arr, return_counts=True)
        if len(unique) != 2:
            return X_train, y_train, "smote-skipped:non-binary"
        minority_count = int(counts.min())
        majority_count = int(counts.max())
        total = minority_count + majority_count
        minority_ratio = minority_count / max(1, total)
        if minority_ratio >= minority_threshold:
            return X_train, y_train, f"smote-skipped:balanced({minority_ratio:.2f})"
        if not IMBLEARN_AVAILABLE:
            return X_train, y_train, "smote-skipped:imblearn-missing"
        # Need at least k_neighbors+1 minority samples, otherwise SMOTE
        # falls back to fewer neighbors automatically — but we clamp it
        # ourselves so we never crash on tiny datasets.
        k = max(1, min(k_neighbors, minority_count - 1))
        sm = SMOTE(random_state=42, k_neighbors=k)
        X_res, y_res = sm.fit_resample(X_train, y_arr)
        new_counts = dict(zip(*np.unique(y_res, return_counts=True)))
        return X_res, y_res, (
            f"smote-applied:{minority_count}→{int(max(new_counts.values()))} "
            f"(k={k})"
        )
    except Exception as e:
        logger.warning(f"SMOTE failed, using raw split: {e}")
        return X_train, y_train, f"smote-failed:{type(e).__name__}"

# Try to import neural network libraries
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
    DEEP_LEARNING_AVAILABLE = True
except ImportError:
    DEEP_LEARNING_AVAILABLE = False
    logger.warning("TensorFlow not available. Deep learning features will be limited.")


@dataclass
class ModelMetrics:
    """Metrics for a trained model"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    win_rate_improvement: float = 0.0
    training_samples: int = 0
    validation_samples: int = 0
    trained_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # v8.75.0 — Class-balancing audit. Tracks whether SMOTE was applied,
    # skipped, or unavailable so the UI can show "Trained on N samples
    # (SMOTE-balanced 12 → 70)" instead of hiding the imbalance.
    smote_status: str = ""
    minority_class_ratio: float = 0.0


@dataclass
class TrainedModel:
    """Container for a trained model"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    model_type: str = ""  # 'random_forest', 'gradient_boosting', 'lstm', 'ensemble'
    asset: str = ""  # Asset it was trained on (or 'all' for universal)
    timeframe: str = ""  # Timeframe it was trained on
    strategy: str = ""  # Base strategy it enhances
    metrics: ModelMetrics = field(default_factory=ModelMetrics)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_retrained: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FeatureEngineer:
    """Extracts features from price data for ML models"""
    
    @staticmethod
    def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical features for ML training"""
        features = pd.DataFrame(index=df.index)
        
        # Price-based features
        features['returns'] = df['close'].pct_change()
        features['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            features[f'sma_{period}'] = df['close'].rolling(window=period).mean()
            features[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']
        
        # EMA crossover features
        features['ema_7'] = df['close'].ewm(span=7, adjust=False).mean()
        features['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        features['ema_crossover'] = (features['ema_7'] > features['ema_21']).astype(int)
        features['ema_diff'] = features['ema_7'] - features['ema_21']
        features['ema_diff_pct'] = features['ema_diff'] / features['ema_21']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        features['rsi'] = 100 - (100 / (1 + rs))
        features['rsi_oversold'] = (features['rsi'] < 30).astype(int)
        features['rsi_overbought'] = (features['rsi'] > 70).astype(int)
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9, adjust=False).mean()
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        features['macd_crossover'] = (features['macd'] > features['macd_signal']).astype(int)
        
        # Bollinger Bands
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        features['bb_upper'] = sma_20 + (2 * std_20)
        features['bb_lower'] = sma_20 - (2 * std_20)
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / sma_20
        features['bb_position'] = (df['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
        
        # Volatility features
        features['volatility_5'] = df['close'].pct_change().rolling(window=5).std()
        features['volatility_20'] = df['close'].pct_change().rolling(window=20).std()
        features['volatility_ratio'] = features['volatility_5'] / features['volatility_20']
        
        # Volume features (if available)
        if 'volume' in df.columns and df['volume'].sum() > 0:
            features['volume_sma_20'] = df['volume'].rolling(window=20).mean()
            features['volume_ratio'] = df['volume'] / features['volume_sma_20']
            features['price_volume_trend'] = (df['close'].pct_change() * df['volume']).cumsum()
        
        # Momentum features
        features['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        features['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        features['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # Candle patterns
        features['body_size'] = abs(df['close'] - df['open']) / df['open']
        features['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['open']
        features['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['open']
        features['is_bullish'] = (df['close'] > df['open']).astype(int)
        
        # Higher timeframe trend (using longer MAs)
        features['trend_50'] = (df['close'] > features['sma_50']).astype(int)
        
        # Stochastic
        low_14 = df['low'].rolling(window=14).min()
        high_14 = df['high'].rolling(window=14).max()
        features['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        features['stoch_d'] = features['stoch_k'].rolling(window=3).mean()
        
        return features.dropna()
    
    @staticmethod
    def prepare_training_data(df: pd.DataFrame, features_df: pd.DataFrame, lookahead: int = 1) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features (X) and target (y) for training
        Target: 1 if price goes up in next 'lookahead' candles, 0 otherwise
        """
        # Create target variable (next candle direction)
        target = (df['close'].shift(-lookahead) > df['close']).astype(int)
        
        # Align features and target
        valid_idx = features_df.index.intersection(target.dropna().index)
        X = features_df.loc[valid_idx]
        y = target.loc[valid_idx]
        
        # Remove any remaining NaN
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_mask]
        y = y[valid_mask]
        
        return X, y


class RandomForestModel:
    """Random Forest model for signal classification"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.is_trained = False
        self.smote_status = ""  # v8.75.0 — populated in train()
    
    def train(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.2) -> ModelMetrics:
        """Train the Random Forest model"""
        if not ML_AVAILABLE:
            logger.error("scikit-learn not available")
            return ModelMetrics()
        
        self.feature_names = list(X.columns)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=test_size, shuffle=False)
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        # v8.75.0 — Apply SMOTE oversampling on the TRAINING split only so
        # we never leak synthetic samples into validation. Class imbalance
        # was driving 17% precision on the minority (winning-trade) class.
        X_train_bal, y_train_bal, self.smote_status = _maybe_smote_balance(
            X_train_scaled, y_train.to_numpy() if hasattr(y_train, "to_numpy") else np.asarray(y_train)
        )
        logger.info(f"[RandomForest] {self.smote_status} — final train size={len(X_train_bal)}")

        # Train model
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train_bal, y_train_bal)
        self.is_trained = True
        
        # Evaluate
        y_pred = self.model.predict(X_val_scaled)

        # v8.75.0 — Report minority ratio on the ORIGINAL (un-resampled) train
        # set so users see the real imbalance.
        try:
            _orig = y_train.to_numpy() if hasattr(y_train, "to_numpy") else np.asarray(y_train)
            _, _cnts = np.unique(_orig, return_counts=True)
            minority_ratio = float(_cnts.min() / max(1, _cnts.sum())) if len(_cnts) == 2 else 0.0
        except Exception:
            minority_ratio = 0.0

        metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, zero_division=0),
            recall=recall_score(y_val, y_pred, zero_division=0),
            f1_score=f1_score(y_val, y_pred, zero_division=0),
            training_samples=len(X_train_bal),
            validation_samples=len(X_val),
            smote_status=self.smote_status,
            minority_class_ratio=minority_ratio,
        )
        
        logger.info(f"Random Forest trained: Accuracy={metrics.accuracy:.4f}, F1={metrics.f1_score:.4f}")
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict signal direction"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        if not self.is_trained:
            return {}
        
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    
    def save(self, path: str):
        """Save model to file"""
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'n_estimators': self.n_estimators,
                'max_depth': self.max_depth
            }, f)
    
    def load(self, path: str):
        """Load model from file"""
        with open(path, 'rb') as f:
            from safe_model_loader import RestrictedUnpickler
            data = RestrictedUnpickler(f).load()
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_names = data['feature_names']
            self.n_estimators = data['n_estimators']
            self.max_depth = data['max_depth']
            self.is_trained = True


class GradientBoostingModel:
    """Gradient Boosting model for signal classification"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 5, learning_rate: float = 0.1):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.is_trained = False
        self.smote_status = ""  # v8.75.0 — populated in train()
    
    def train(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.2) -> ModelMetrics:
        """Train the Gradient Boosting model"""
        if not ML_AVAILABLE:
            logger.error("scikit-learn not available")
            return ModelMetrics()
        
        self.feature_names = list(X.columns)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=test_size, shuffle=False)
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        # v8.75.0 — SMOTE on training split. sklearn's GradientBoosting
        # doesn't expose class_weight, so we use compute_sample_weight as
        # a secondary safety net (rebalances loss gradient even when SMOTE
        # itself is skipped).
        X_train_bal, y_train_bal, self.smote_status = _maybe_smote_balance(
            X_train_scaled, y_train.to_numpy() if hasattr(y_train, "to_numpy") else np.asarray(y_train)
        )
        try:
            sample_weight = compute_sample_weight(class_weight="balanced", y=y_train_bal)
        except Exception:
            sample_weight = None
        logger.info(f"[GradientBoosting] {self.smote_status} — final train size={len(X_train_bal)}")

        # Train model
        self.model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )
        self.model.fit(X_train_bal, y_train_bal, sample_weight=sample_weight)
        self.is_trained = True
        
        # Evaluate
        y_pred = self.model.predict(X_val_scaled)

        # v8.75.0 — Report minority ratio on the ORIGINAL train set
        try:
            _orig = y_train.to_numpy() if hasattr(y_train, "to_numpy") else np.asarray(y_train)
            _, _cnts = np.unique(_orig, return_counts=True)
            minority_ratio = float(_cnts.min() / max(1, _cnts.sum())) if len(_cnts) == 2 else 0.0
        except Exception:
            minority_ratio = 0.0

        metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, zero_division=0),
            recall=recall_score(y_val, y_pred, zero_division=0),
            f1_score=f1_score(y_val, y_pred, zero_division=0),
            training_samples=len(X_train_bal),
            validation_samples=len(X_val),
            smote_status=self.smote_status,
            minority_class_ratio=minority_ratio,
        )
        
        logger.info(f"Gradient Boosting trained: Accuracy={metrics.accuracy:.4f}, F1={metrics.f1_score:.4f}")
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict signal direction"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        if not self.is_trained:
            return {}
        
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))


class LSTMModel:
    """LSTM model for time series prediction"""
    
    def __init__(self, sequence_length: int = 20, units: int = 50):
        self.model = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.sequence_length = sequence_length
        self.units = units
        self.feature_names = []
        self.is_trained = False
    
    def _create_sequences(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training"""
        X_seq, y_seq = [], []
        for i in range(len(X) - self.sequence_length):
            X_seq.append(X[i:i + self.sequence_length])
            y_seq.append(y[i + self.sequence_length])
        return np.array(X_seq), np.array(y_seq)
    
    def train(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.2, epochs: int = 50) -> ModelMetrics:
        """Train the LSTM model"""
        if not DEEP_LEARNING_AVAILABLE:
            logger.error("TensorFlow not available")
            return ModelMetrics()
        
        self.feature_names = list(X.columns)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Create sequences
        X_seq, y_seq = self._create_sequences(X_scaled, y.values)
        
        # Split data
        split_idx = int(len(X_seq) * (1 - test_size))
        X_train, X_val = X_seq[:split_idx], X_seq[split_idx:]
        y_train, y_val = y_seq[:split_idx], y_seq[split_idx:]
        
        # Build model
        self.model = Sequential([
            LSTM(self.units, return_sequences=True, input_shape=(self.sequence_length, len(self.feature_names))),
            Dropout(0.2),
            LSTM(self.units // 2),
            Dropout(0.2),
            Dense(32, activation='relu'),
            BatchNormalization(),
            Dense(1, activation='sigmoid')
        ])
        
        self.model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        # Train
        early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
        
        self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=32,
            callbacks=[early_stop],
            verbose=0
        )
        self.is_trained = True
        
        # Evaluate
        y_pred = (self.model.predict(X_val, verbose=0) > 0.5).astype(int).flatten()
        
        metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, zero_division=0),
            recall=recall_score(y_val, y_pred, zero_division=0),
            f1_score=f1_score(y_val, y_pred, zero_division=0),
            training_samples=len(X_train),
            validation_samples=len(X_val)
        )
        
        logger.info(f"LSTM trained: Accuracy={metrics.accuracy:.4f}, F1={metrics.f1_score:.4f}")
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict signal direction"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        
        # Need at least sequence_length samples
        if len(X_scaled) < self.sequence_length:
            return np.array([])
        
        X_seq = X_scaled[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        return (self.model.predict(X_seq, verbose=0) > 0.5).astype(int).flatten()


class EnsembleModel:
    """Ensemble model combining multiple ML models"""
    
    def __init__(self):
        self.models = {}
        self.weights = {}
        self.is_trained = False
    
    def add_model(self, name: str, model: Any, weight: float = 1.0):
        """Add a model to the ensemble"""
        self.models[name] = model
        self.weights[name] = weight
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict using weighted voting"""
        if not self.models:
            raise ValueError("No models in ensemble")
        
        predictions = []
        total_weight = 0
        
        for name, model in self.models.items():
            try:
                if hasattr(model, 'predict_proba'):
                    pred = model.predict_proba(X)[:, 1]
                else:
                    pred = model.predict(X).astype(float)
                
                predictions.append(pred * self.weights[name])
                total_weight += self.weights[name]
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")
        
        if not predictions:
            raise ValueError("All model predictions failed")
        
        # Weighted average
        weighted_pred = np.sum(predictions, axis=0) / total_weight
        return (weighted_pred > 0.5).astype(int)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get ensemble prediction probabilities"""
        predictions = []
        total_weight = 0
        
        for name, model in self.models.items():
            try:
                if hasattr(model, 'predict_proba'):
                    pred = model.predict_proba(X)[:, 1]
                else:
                    pred = model.predict(X).astype(float)
                
                predictions.append(pred * self.weights[name])
                total_weight += self.weights[name]
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")
        
        if not predictions:
            return np.array([0.5] * len(X))
        
        return np.sum(predictions, axis=0) / total_weight


class MLTrainingService:
    """Main service for training and managing ML models"""
    
    def __init__(self, db=None):
        self.db = db
        self.feature_engineer = FeatureEngineer()
        self.models: Dict[str, Any] = {}
        self.trained_models: Dict[str, TrainedModel] = {}
        self.model_save_path = "/app/backend/ml_models"
        
        # Create model save directory
        os.makedirs(self.model_save_path, exist_ok=True)
    
    async def train_from_backtest_results(self, backtest_results: List[Dict], asset: str = "all", timeframe: str = "1h") -> Dict[str, TrainedModel]:
        """Train ML models from backtest results"""
        logger.info(f"Training ML models from {len(backtest_results)} backtest results")
        
        # Extract trades from backtest results
        all_trades = []
        for result in backtest_results:
            trades = result.get('trades', [])
            for trade in trades:
                trade['backtest_strategy'] = result.get('strategy', 'unknown')
                trade['backtest_asset'] = result.get('asset', 'unknown')
                trade['backtest_timeframe'] = result.get('timeframe', '1h')
                all_trades.append(trade)
        
        if len(all_trades) < 100:
            logger.warning(f"Insufficient trades for training: {len(all_trades)} < 100")
            return {}
        
        # Create DataFrame from trades
        df = pd.DataFrame(all_trades)
        
        # Create features from trade data
        # This is simplified - in production, you'd want the actual price data
        X, y = self._prepare_training_data_from_trades(df)
        
        if len(X) < 100:
            logger.warning(f"Insufficient features for training: {len(X)} < 100")
            return {}
        
        trained_models = {}
        
        # Train Random Forest
        rf_model = RandomForestModel(n_estimators=100, max_depth=10)
        rf_metrics = rf_model.train(X, y)
        
        trained_models['random_forest'] = TrainedModel(
            name="Signal Classifier (Random Forest)",
            model_type="random_forest",
            asset=asset,
            timeframe=timeframe,
            metrics=rf_metrics,
            feature_importance=rf_model.get_feature_importance()
        )
        self.models['random_forest'] = rf_model
        
        # Train Gradient Boosting
        gb_model = GradientBoostingModel(n_estimators=100, max_depth=5)
        gb_metrics = gb_model.train(X, y)
        
        trained_models['gradient_boosting'] = TrainedModel(
            name="Signal Classifier (Gradient Boosting)",
            model_type="gradient_boosting",
            asset=asset,
            timeframe=timeframe,
            metrics=gb_metrics,
            feature_importance=gb_model.get_feature_importance()
        )
        self.models['gradient_boosting'] = gb_model
        
        # Create ensemble
        ensemble = EnsembleModel()
        ensemble.add_model('random_forest', rf_model, weight=rf_metrics.f1_score)
        ensemble.add_model('gradient_boosting', gb_model, weight=gb_metrics.f1_score)
        ensemble.is_trained = True

        # v8.76.0 — Actually evaluate the ensemble on a fresh validation
        # split instead of naively averaging RF + GB metrics. The previous
        # code only averaged accuracy + f1, leaving precision/recall/
        # validation_samples at default 0 (which made the ensemble look
        # broken in the API response). We re-split with the same
        # `shuffle=False` policy the individual models use so the
        # validation set matches what they evaluated on.
        from sklearn.model_selection import train_test_split as _split
        try:
            _X_train_full, _X_val_ens, _y_train_full, _y_val_ens = _split(
                X, y, test_size=0.2, shuffle=False
            )
            ens_pred = ensemble.predict(_X_val_ens)
            ens_acc = float(accuracy_score(_y_val_ens, ens_pred))
            ens_prec = float(precision_score(_y_val_ens, ens_pred, zero_division=0))
            ens_recall = float(recall_score(_y_val_ens, ens_pred, zero_division=0))
            ens_f1 = float(f1_score(_y_val_ens, ens_pred, zero_division=0))
            ens_train_n = int(len(_X_train_full))
            ens_val_n = int(len(_X_val_ens))
            # Surface the audit details from the better-balanced model
            ens_smote_status = rf_model.smote_status or gb_model.smote_status or ""
            ens_minority_ratio = rf_metrics.minority_class_ratio
        except Exception as e:
            logger.warning(f"Ensemble evaluation failed, falling back to averaged metrics: {e}")
            ens_acc = (rf_metrics.accuracy + gb_metrics.accuracy) / 2
            ens_prec = (rf_metrics.precision + gb_metrics.precision) / 2
            ens_recall = (rf_metrics.recall + gb_metrics.recall) / 2
            ens_f1 = (rf_metrics.f1_score + gb_metrics.f1_score) / 2
            ens_train_n = rf_metrics.training_samples
            ens_val_n = rf_metrics.validation_samples
            ens_smote_status = "ensemble-eval-failed"
            ens_minority_ratio = rf_metrics.minority_class_ratio

        trained_models['ensemble'] = TrainedModel(
            name="Ensemble Signal Classifier",
            model_type="ensemble",
            asset=asset,
            timeframe=timeframe,
            metrics=ModelMetrics(
                accuracy=ens_acc,
                precision=ens_prec,
                recall=ens_recall,
                f1_score=ens_f1,
                training_samples=ens_train_n,
                validation_samples=ens_val_n,
                smote_status=ens_smote_status,
                minority_class_ratio=ens_minority_ratio,
            )
        )
        self.models['ensemble'] = ensemble
        
        # Save models to database
        if self.db is not None:
            for name, model_info in trained_models.items():
                await self.db.ml_models.update_one(
                    {"model_type": name, "asset": asset, "timeframe": timeframe},
                    {"$set": asdict(model_info)},
                    upsert=True
                )
        
        self.trained_models = trained_models
        logger.info(f"Trained {len(trained_models)} ML models successfully")
        
        return trained_models
    
    def _prepare_training_data_from_trades(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare training data from trade records"""
        # Create features from trade metadata
        features = pd.DataFrame()
        
        # Trade-based features - use bracket notation for DataFrame columns
        features['confidence'] = df['confidence'] if 'confidence' in df.columns else 75
        features['is_call'] = (df['direction'].str.lower() == 'call').astype(int) if 'direction' in df.columns else 0
        
        # Strategy encoding
        if 'backtest_strategy' in df.columns:
            strategies = df['backtest_strategy'].unique()
            for strategy in strategies:
                features[f'strategy_{strategy}'] = (df['backtest_strategy'] == strategy).astype(int)
        
        # Target: did the trade win?
        if 'result' in df.columns:
            target = (df['result'].str.lower() == 'win').astype(int)
        elif 'outcome' in df.columns:
            target = (df['outcome'].str.lower() == 'win').astype(int)
        else:
            target = pd.Series([0] * len(df))

        # Iter 60 — REMOVED `noise_1`/`noise_2` random features. Previous
        # code injected np.random.randn() as features which then dominated
        # the model's feature importance (81% combined) and made every
        # prediction effectively random. Train on actual signal features only.

        return features, target
    
    async def train_on_price_data(self, price_df: pd.DataFrame, asset: str, timeframe: str) -> Dict[str, TrainedModel]:
        """Train ML models on actual price data"""
        logger.info(f"Training ML models on {len(price_df)} candles for {asset} {timeframe}")
        
        # Calculate features
        features = self.feature_engineer.calculate_features(price_df)
        
        if len(features) < 100:
            logger.warning(f"Insufficient data for training: {len(features)} < 100")
            return {}
        
        # Prepare training data
        X, y = self.feature_engineer.prepare_training_data(price_df, features, lookahead=1)
        
        if len(X) < 100:
            logger.warning(f"Insufficient samples for training: {len(X)} < 100")
            return {}
        
        trained_models = {}
        
        # Train Random Forest
        rf_model = RandomForestModel(n_estimators=100, max_depth=10)
        rf_metrics = rf_model.train(X, y)
        
        trained_models['random_forest'] = TrainedModel(
            name=f"Price Predictor RF ({asset})",
            model_type="random_forest",
            asset=asset,
            timeframe=timeframe,
            metrics=rf_metrics,
            feature_importance=rf_model.get_feature_importance()
        )
        self.models[f'rf_{asset}_{timeframe}'] = rf_model
        
        # Save model file
        rf_model.save(f"{self.model_save_path}/rf_{asset}_{timeframe}.pkl")
        
        # Train Gradient Boosting
        gb_model = GradientBoostingModel(n_estimators=100, max_depth=5)
        gb_metrics = gb_model.train(X, y)
        
        trained_models['gradient_boosting'] = TrainedModel(
            name=f"Price Predictor GB ({asset})",
            model_type="gradient_boosting",
            asset=asset,
            timeframe=timeframe,
            metrics=gb_metrics,
            feature_importance=gb_model.get_feature_importance()
        )
        self.models[f'gb_{asset}_{timeframe}'] = gb_model

        # Iter 88 — Register an Ensemble alongside RF + GB so all three
        # models show consistent metrics side-by-side. Mirrors the
        # `train_from_backtest_results` pattern (Iter 76): weight by F1,
        # evaluate on a fresh held-out validation split, surface real
        # precision / recall / f1 / validation_samples.
        ensemble = EnsembleModel()
        ensemble.add_model('random_forest', rf_model, weight=rf_metrics.f1_score)
        ensemble.add_model('gradient_boosting', gb_model, weight=gb_metrics.f1_score)
        ensemble.is_trained = True

        try:
            _X_train_full, _X_val_ens, _y_train_full, _y_val_ens = train_test_split(
                X, y, test_size=0.2, shuffle=False
            )
            ens_pred = ensemble.predict(_X_val_ens)
            ens_acc = float(accuracy_score(_y_val_ens, ens_pred))
            ens_prec = float(precision_score(_y_val_ens, ens_pred, zero_division=0))
            ens_recall = float(recall_score(_y_val_ens, ens_pred, zero_division=0))
            ens_f1 = float(f1_score(_y_val_ens, ens_pred, zero_division=0))
            ens_train_n = int(len(_X_train_full))
            ens_val_n = int(len(_X_val_ens))
            ens_smote_status = rf_model.smote_status or gb_model.smote_status or ""
            ens_minority_ratio = rf_metrics.minority_class_ratio
        except Exception as e:
            logger.warning(f"Ensemble evaluation failed, falling back to averaged metrics: {e}")
            ens_acc = (rf_metrics.accuracy + gb_metrics.accuracy) / 2
            ens_prec = (rf_metrics.precision + gb_metrics.precision) / 2
            ens_recall = (rf_metrics.recall + gb_metrics.recall) / 2
            ens_f1 = (rf_metrics.f1_score + gb_metrics.f1_score) / 2
            ens_train_n = rf_metrics.training_samples
            ens_val_n = rf_metrics.validation_samples
            ens_smote_status = "ensemble-eval-failed"
            ens_minority_ratio = rf_metrics.minority_class_ratio

        trained_models['ensemble'] = TrainedModel(
            name=f"Price Predictor Ensemble ({asset})",
            model_type="ensemble",
            asset=asset,
            timeframe=timeframe,
            metrics=ModelMetrics(
                accuracy=ens_acc,
                precision=ens_prec,
                recall=ens_recall,
                f1_score=ens_f1,
                training_samples=ens_train_n,
                validation_samples=ens_val_n,
                smote_status=ens_smote_status,
                minority_class_ratio=ens_minority_ratio,
            )
        )
        self.models[f'ens_{asset}_{timeframe}'] = ensemble

        # Save to database
        if self.db is not None:
            for name, model_info in trained_models.items():
                await self.db.ml_models.update_one(
                    {"model_type": name, "asset": asset, "timeframe": timeframe},
                    {"$set": asdict(model_info)},
                    upsert=True
                )
        
        logger.info(f"Trained {len(trained_models)} models for {asset} {timeframe}")
        return trained_models
    
    async def predict_signal(self, price_df: pd.DataFrame, asset: str, timeframe: str) -> Dict[str, Any]:
        """Use trained models to predict signal"""
        model_key = f'rf_{asset}_{timeframe}'
        
        if model_key not in self.models:
            # Try to load model
            model_path = f"{self.model_save_path}/rf_{asset}_{timeframe}.pkl"
            if os.path.exists(model_path):
                rf_model = RandomForestModel()
                rf_model.load(model_path)
                self.models[model_key] = rf_model
            else:
                return {"error": f"No model trained for {asset} {timeframe}"}
        
        model = self.models[model_key]
        
        # Calculate features
        features = self.feature_engineer.calculate_features(price_df)
        
        if len(features) == 0:
            return {"error": "Insufficient data for prediction"}
        
        # Get latest features
        latest_features = features.iloc[-1:][model.feature_names]
        
        # Predict
        prediction = model.predict(latest_features)[0]
        proba = model.predict_proba(latest_features)[0]
        
        return {
            "direction": "call" if prediction == 1 else "put",
            "confidence": float(max(proba) * 100),
            "model": "random_forest",
            "asset": asset,
            "timeframe": timeframe
        }
    
    async def get_model_performance(self) -> List[Dict]:
        """Get performance metrics for all trained models"""
        if self.db is not None:
            models = await self.db.ml_models.find({}, {"_id": 0}).to_list(100)
            return models
        
        return [asdict(m) for m in self.trained_models.values()]
    
    async def schedule_daily_retrain(self):
        """Schedule daily model retraining"""
        while True:
            try:
                # Wait until next day
                now = datetime.now(timezone.utc)
                next_run = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                wait_seconds = (next_run - now).total_seconds()
                
                logger.info(f"Next ML retraining scheduled in {wait_seconds/3600:.1f} hours")
                await asyncio.sleep(wait_seconds)
                
                # Run retraining
                logger.info("Starting scheduled ML model retraining...")
                await self.run_daily_retrain()
                
            except asyncio.CancelledError:
                logger.info("Scheduled retraining cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduled retraining: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def run_daily_retrain(self):
        """Run daily model retraining using recent backtest results"""
        try:
            if self.db is None:
                logger.warning("Database not available for retraining")
                return
            
            # Get recent backtest results
            results = await self.db.backtest_results.find({}).sort("created_at", -1).limit(100).to_list(100)
            
            if len(results) < 10:
                logger.warning("Insufficient backtest results for retraining")
                return
            
            # Train models
            await self.train_from_backtest_results(results)
            
            logger.info("Daily ML retraining completed successfully")
            
        except Exception as e:
            logger.error(f"Error in daily retraining: {e}")


# Singleton instance
_ml_training_service = None

async def get_ml_training_service(db=None):
    global _ml_training_service
    if _ml_training_service is None:
        _ml_training_service = MLTrainingService(db)
    return _ml_training_service
