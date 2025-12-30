"""
AI/ML Training Module for 5-Second Supertrend Reversal Strategy

This module implements:
1. Data preparation and feature engineering
2. Label generation for supervised learning
3. Model training (XGBoost, LSTM, etc.)
4. Backtesting and evaluation
5. Model deployment integration

CPU-ONLY MODE: Configured for deployment without GPU/CUDA
"""

# CRITICAL: Force CPU mode BEFORE imports
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
import logging
import json
import pickle

# ML libraries
try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.preprocessing import StandardScaler
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available - install with: pip install xgboost scikit-learn")

# Optional: Deep learning
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class Supertrend5sAITrainer:
    """
    AI trainer for 5-second Supertrend reversal strategy
    """
    
    def __init__(self, atr_period: int = 2, multiplier: float = 1.11):
        """Initialize trainer with strategy parameters"""
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        
        logger.info("🤖 Initialized AI Trainer for 5s Supertrend Strategy")
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from raw OHLC data
        
        Args:
            df: DataFrame with OHLC data
        
        Returns:
            DataFrame with engineered features
        """
        from strategies.strategy_5s_supertrend_reversal import SupertrendReversal5s
        
        # Calculate Supertrend
        strategy = SupertrendReversal5s(self.atr_period, self.multiplier)
        supertrend, direction = strategy.calculate_supertrend(df)
        atr = strategy.calculate_atr(df, self.atr_period)
        
        # Add Supertrend features
        df['supertrend'] = supertrend
        df['direction'] = direction
        df['atr'] = atr
        df['distance_from_st'] = (df['close'] - supertrend) / df['close'] * 100
        
        # Detect flips
        df['flip_to_up'] = (direction == 1) & (direction.shift(1) == -1)
        df['flip_to_down'] = (direction == -1) & (direction.shift(1) == 1)
        
        # Price action features
        df['price_change'] = df['close'].pct_change() * 100
        df['range'] = (df['high'] - df['low']) / df['close'] * 100
        df['body'] = abs(df['close'] - df['open']) / df['close'] * 100
        
        # Momentum features
        df['rsi_5'] = self._calculate_rsi(df['close'], 5)
        df['rsi_10'] = self._calculate_rsi(df['close'], 10)
        
        # Volatility features
        df['volatility_10'] = df['close'].rolling(10).std() / df['close'].rolling(10).mean() * 100
        df['volatility_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean() * 100
        
        # Volume features (if available)
        if 'volume' in df.columns:
            df['volume_change'] = df['volume'].pct_change() * 100
            df['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(10).mean()
        
        # Time-based features (for session patterns)
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['minute'] = pd.to_datetime(df['timestamp']).dt.minute
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
        
        # Lag features (previous candles)
        for lag in [1, 2, 3, 5]:
            df[f'close_lag_{lag}'] = df['close'].shift(lag)
            df[f'direction_lag_{lag}'] = df['direction'].shift(lag)
        
        return df
    
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate training labels based on actual outcomes
        
        Args:
            df: DataFrame with features
        
        Returns:
            DataFrame with labels
        """
        # Initialize labels
        df['label_call'] = np.nan
        df['label_put'] = np.nan
        
        # For each flip, check if reversal trade would profit
        for i in range(len(df) - 1):
            # Flip to uptrend → reversal PUT signal
            if df['flip_to_up'].iloc[i]:
                # Check if price goes DOWN in next candle (winning PUT)
                next_close = df['close'].iloc[i + 1]
                current_close = df['close'].iloc[i]
                df.loc[df.index[i], 'label_put'] = 1 if next_close < current_close else 0
            
            # Flip to downtrend → reversal CALL signal
            if df['flip_to_down'].iloc[i]:
                # Check if price goes UP in next candle (winning CALL)
                next_close = df['close'].iloc[i + 1]
                current_close = df['close'].iloc[i]
                df.loc[df.index[i], 'label_call'] = 1 if next_close > current_close else 0
        
        return df
    
    def prepare_training_data(
        self,
        df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare X (features) and y (labels) for training
        
        Args:
            df: DataFrame with features and labels
        
        Returns:
            Tuple: (X, y, feature_columns)
        """
        # Select feature columns (exclude labels, raw OHLC, timestamps)
        exclude_cols = [
            'open', 'high', 'low', 'close', 'timestamp', 'volume',
            'label_call', 'label_put', 'flip_to_up', 'flip_to_down'
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        feature_cols = [col for col in feature_cols if not df[col].isna().all()]
        
        self.feature_columns = feature_cols
        
        # Get rows where we have flip signals (training examples)
        flip_mask = df['flip_to_up'] | df['flip_to_down']
        training_rows = df[flip_mask].copy()
        
        # Combine labels (1 for win, 0 for loss)
        training_rows['label'] = training_rows['label_call'].fillna(training_rows['label_put'])
        
        # Remove rows with missing labels or features
        training_rows = training_rows.dropna(subset=['label'] + feature_cols)
        
        X = training_rows[feature_cols].values
        y = training_rows['label'].values
        
        logger.info(f"Prepared {len(X)} training examples with {len(feature_cols)} features")
        logger.info(f"Win rate in training data: {y.mean()*100:.2f}%")
        
        return X, y, feature_cols
    
    def train_xgboost_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Train XGBoost classifier
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
        
        Returns:
            Training results dictionary
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost not available")
        
        logger.info("🚀 Training XGBoost model...")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # XGBoost parameters
        params = {
            'objective': 'binary:logistic',
            'max_depth': 5,
            'learning_rate': 0.1,
            'n_estimators': 100,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'eval_metric': 'logloss',
            'random_state': 42
        }
        
        # Train model
        self.model = xgb.XGBClassifier(**params)
        
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            self.model.fit(
                X_train_scaled, y_train,
                eval_set=[(X_val_scaled, y_val)],
                verbose=False
            )
        else:
            self.model.fit(X_train_scaled, y_train)
        
        # Evaluate on training data
        y_pred_train = self.model.predict(X_train_scaled)
        train_acc = accuracy_score(y_train, y_pred_train)
        train_precision = precision_score(y_train, y_pred_train, zero_division=0)
        
        results = {
            'train_accuracy': train_acc,
            'train_precision': train_precision,
            'feature_importance': dict(zip(
                self.feature_columns,
                self.model.feature_importances_
            ))
        }
        
        # Validation metrics
        if X_val is not None:
            y_pred_val = self.model.predict(X_val_scaled)
            results['val_accuracy'] = accuracy_score(y_val, y_pred_val)
            results['val_precision'] = precision_score(y_val, y_pred_val, zero_division=0)
        
        logger.info(f"✅ Training complete - Accuracy: {train_acc*100:.2f}%")
        
        return results
    
    def predict(self, features: np.ndarray) -> Tuple[int, float]:
        """
        Make prediction with trained model
        
        Args:
            features: Feature vector
        
        Returns:
            Tuple: (prediction, probability)
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        prediction = self.model.predict(features_scaled)[0]
        probability = self.model.predict_proba(features_scaled)[0][1]
        
        return int(prediction), float(probability)
    
    def save_model(self, filepath: str):
        """Save trained model to disk"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'parameters': {
                'atr_period': self.atr_period,
                'multiplier': self.multiplier
            }
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"💾 Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load trained model from disk"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']
        
        logger.info(f"📂 Model loaded from {filepath}")
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def backtest_strategy(
        self,
        df: pd.DataFrame,
        initial_balance: float = 1000.0,
        stake_per_trade: float = 10.0,
        payout_rate: float = 0.8
    ) -> Dict:
        """
        Backtest the strategy on historical data
        
        Args:
            df: DataFrame with OHLC data
            initial_balance: Starting balance
            stake_per_trade: Amount per trade
            payout_rate: Payout rate on wins (e.g., 0.8 = 80%)
        
        Returns:
            Backtest results dictionary
        """
        logger.info("📊 Running backtest...")
        
        # Prepare data
        df = self.prepare_features(df)
        df = self.generate_labels(df)
        
        balance = initial_balance
        trades = []
        
        # Simulate trading
        for i in range(len(df) - 1):
            # Check for flip signals
            if df['flip_to_up'].iloc[i]:
                # PUT signal
                direction = 'put'
                win = df['label_put'].iloc[i] == 1
            elif df['flip_to_down'].iloc[i]:
                # CALL signal
                direction = 'call'
                win = df['label_call'].iloc[i] == 1
            else:
                continue
            
            # Execute trade
            if win:
                profit = stake_per_trade * payout_rate
                balance += profit
            else:
                balance -= stake_per_trade
            
            trades.append({
                'timestamp': df['timestamp'].iloc[i] if 'timestamp' in df.columns else i,
                'direction': direction,
                'win': win,
                'balance': balance
            })
        
        # Calculate metrics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t['win'])
        losses = total_trades - wins
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_profit = balance - initial_balance
        roi = (total_profit / initial_balance * 100)
        
        results = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'initial_balance': initial_balance,
            'final_balance': balance,
            'total_profit': total_profit,
            'roi': roi,
            'trades': trades
        }
        
        logger.info(f"✅ Backtest complete - Win Rate: {win_rate:.2f}%, ROI: {roi:.2f}%")
        
        return results


# Training script example
def train_5s_supertrend_model(candle_data_path: str, output_model_path: str):
    """
    Complete training pipeline
    
    Args:
        candle_data_path: Path to CSV file with historical 5s candle data
        output_model_path: Path to save trained model
    """
    # Load data
    df = pd.DataFrame(candle_data_path)
    
    logger.info(f"Loaded {len(df)} candles for training")
    
    # Initialize trainer
    trainer = Supertrend5sAITrainer()
    
    # Prepare features
    df = trainer.prepare_features(df)
    df = trainer.generate_labels(df)
    
    # Prepare training data
    X, y, feature_cols = trainer.prepare_training_data(df)
    
    # Split data (time-series split)
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    # Train model
    results = trainer.train_xgboost_model(X_train, y_train, X_val, y_val)
    
    # Save model
    trainer.save_model(output_model_path)
    
    # Run backtest
    backtest_results = trainer.backtest_strategy(df)
    
    return {
        'training_results': results,
        'backtest_results': backtest_results
    }
