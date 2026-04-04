"""
AI ML Trading System - Enhanced with Historical Data Learning
==============================================================
This module provides machine learning capabilities for binary options trading
with proper historical data training and validation.

Key Features:
1. Historical data collection and preprocessing
2. Feature engineering for binary options
3. Model training with cross-validation
4. Real-time predictions with confidence scores
5. Continuous learning from validated signals

Author: GPT Signal Bot
Version: 2.0.0
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import pickle
import os
import asyncio

# ML imports with fallbacks
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.warning("scikit-learn not available. ML features disabled.")

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logging.warning("TA-Lib not available. Using fallback indicators.")

logger = logging.getLogger(__name__)


class EnhancedAIMLSystem:
    """
    Enhanced AI/ML system for binary options trading with historical data learning.
    """
    
    def __init__(self):
        self.is_trained = False
        self.model = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.feature_names = []
        self.training_history = []
        self.model_accuracy = 0.0
        self.last_training_time = None
        self.min_training_samples = 100
        self.model_path = '/app/backend/ml_models/trading_model.pkl'
        
        # Performance tracking
        self.predictions_made = 0
        self.correct_predictions = 0
        
        # Initialize model
        if ML_AVAILABLE:
            self._initialize_model()
        
        logger.info("🤖 Enhanced AI ML System initialized")
    
    def _initialize_model(self):
        """Initialize the ensemble ML model"""
        if not ML_AVAILABLE:
            return
        
        try:
            # Create ensemble of classifiers
            rf = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            
            gb = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            
            # Voting ensemble
            self.model = VotingClassifier(
                estimators=[('rf', rf), ('gb', gb)],
                voting='soft'
            )
            
            logger.info("✅ ML model initialized (RF + GB ensemble)")
            
        except Exception as e:
            logger.error(f"Error initializing ML model: {e}")
    
    def extract_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Extract features from price data for ML model.
        Returns feature array ready for model input.
        """
        try:
            if len(df) < 50:
                return None
            
            features = {}
            
            # Price features
            features['close'] = df['close'].iloc[-1]
            features['price_change_1'] = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
            features['price_change_5'] = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            features['price_change_10'] = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
            
            # Volatility features
            features['volatility_5'] = df['close'].tail(5).std() / df['close'].tail(5).mean() * 100
            features['volatility_20'] = df['close'].tail(20).std() / df['close'].tail(20).mean() * 100
            
            # Range features
            features['high_low_range'] = (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-1] * 100
            features['body_size'] = abs(df['close'].iloc[-1] - df['open'].iloc[-1]) / df['close'].iloc[-1] * 100
            
            if TALIB_AVAILABLE:
                # RSI
                rsi = talib.RSI(df['close'].values, timeperiod=14)
                features['rsi_14'] = rsi[-1] if not np.isnan(rsi[-1]) else 50
                
                rsi_2 = talib.RSI(df['close'].values, timeperiod=2)
                features['rsi_2'] = rsi_2[-1] if not np.isnan(rsi_2[-1]) else 50
                
                # MACD
                macd, signal, hist = talib.MACD(df['close'].values)
                features['macd'] = macd[-1] if not np.isnan(macd[-1]) else 0
                features['macd_signal'] = signal[-1] if not np.isnan(signal[-1]) else 0
                features['macd_hist'] = hist[-1] if not np.isnan(hist[-1]) else 0
                
                # Bollinger Bands
                upper, middle, lower = talib.BBANDS(df['close'].values, timeperiod=20)
                bb_position = (df['close'].iloc[-1] - lower[-1]) / (upper[-1] - lower[-1])
                features['bb_position'] = bb_position if not np.isnan(bb_position) else 0.5
                features['bb_width'] = (upper[-1] - lower[-1]) / middle[-1] if not np.isnan(middle[-1]) else 0
                
                # Stochastic
                slowk, slowd = talib.STOCH(df['high'].values, df['low'].values, df['close'].values)
                features['stoch_k'] = slowk[-1] if not np.isnan(slowk[-1]) else 50
                features['stoch_d'] = slowd[-1] if not np.isnan(slowd[-1]) else 50
                
                # ADX
                adx = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                features['adx'] = adx[-1] if not np.isnan(adx[-1]) else 25
                
                # ATR
                atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                features['atr_percent'] = (atr[-1] / df['close'].iloc[-1] * 100) if not np.isnan(atr[-1]) else 0
                
                # CCI
                cci = talib.CCI(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                features['cci'] = cci[-1] if not np.isnan(cci[-1]) else 0
                
                # Williams %R
                willr = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                features['willr'] = willr[-1] if not np.isnan(willr[-1]) else -50
                
                # MFI (if volume available)
                if 'volume' in df.columns and df['volume'].sum() > 0:
                    mfi = talib.MFI(df['high'].values, df['low'].values, df['close'].values, df['volume'].values, timeperiod=14)
                    features['mfi'] = mfi[-1] if not np.isnan(mfi[-1]) else 50
                else:
                    features['mfi'] = 50
                    
            else:
                # Fallback: Simple RSI calculation
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                features['rsi_14'] = (100 - (100 / (1 + rs.iloc[-1]))) if not np.isnan(rs.iloc[-1]) else 50
                features['rsi_2'] = 50
                features['macd'] = 0
                features['macd_signal'] = 0
                features['macd_hist'] = 0
                features['bb_position'] = 0.5
                features['bb_width'] = 0
                features['stoch_k'] = 50
                features['stoch_d'] = 50
                features['adx'] = 25
                features['atr_percent'] = 0
                features['cci'] = 0
                features['willr'] = -50
                features['mfi'] = 50
            
            # EMA features
            ema_8 = df['close'].ewm(span=8, adjust=False).mean().iloc[-1]
            ema_20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
            features['ema_8_20_diff'] = (ema_8 - ema_20) / ema_20 * 100
            features['price_vs_ema_8'] = (df['close'].iloc[-1] - ema_8) / ema_8 * 100
            features['price_vs_ema_20'] = (df['close'].iloc[-1] - ema_20) / ema_20 * 100
            
            # Trend features
            features['trend_strength'] = abs(features['price_change_10']) / features['volatility_20'] if features['volatility_20'] > 0 else 0
            
            # Momentum
            features['momentum_3'] = df['close'].iloc[-1] - df['close'].iloc[-4]
            features['momentum_5'] = df['close'].iloc[-1] - df['close'].iloc[-6]
            
            # Store feature names
            self.feature_names = list(features.keys())
            
            # Convert to numpy array
            feature_array = np.array(list(features.values())).reshape(1, -1)
            
            # Handle NaN values
            feature_array = np.nan_to_num(feature_array, nan=0.0)
            
            return feature_array
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    async def train_from_historical(self, db, symbol: str = None, days: int = 30) -> Dict:
        """
        Train the model using historical validated signals from the database.
        """
        if not ML_AVAILABLE:
            return {"success": False, "error": "ML libraries not available"}
        
        try:
            logger.info(f"🎓 Starting ML training from historical data ({days} days)...")
            
            # Build query for validated signals
            cutoff_time = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query = {
                'validated_at': {'$gte': cutoff_time},
                'result': {'$in': ['WIN', 'LOSS']}
            }
            
            if symbol:
                query['symbol'] = symbol
            
            # Fetch validated signals
            validations = await db.signal_validations.find(query).to_list(10000)
            
            logger.info(f"📊 Found {len(validations)} validated signals for training")
            
            if len(validations) < self.min_training_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data: {len(validations)} < {self.min_training_samples}"
                }
            
            # Prepare training data
            X = []
            y = []
            
            for v in validations:
                # Get the original signal's indicators
                indicators = v.get('indicators', {})
                
                if indicators:
                    # Create feature vector from stored indicators
                    features = [
                        indicators.get('rsi_14', 50),
                        indicators.get('rsi_2', 50),
                        indicators.get('macd', 0),
                        indicators.get('bb_position', 0.5),
                        indicators.get('stoch_k', 50),
                        indicators.get('stoch_d', 50),
                        indicators.get('adx', 25),
                        indicators.get('atr_percent', 0),
                        indicators.get('price_change_percent', 0),
                        indicators.get('volatility', 0)
                    ]
                    
                    X.append(features)
                    y.append(1 if v['result'] == 'WIN' else 0)
            
            if len(X) < self.min_training_samples:
                logger.warning("Not enough feature data from validations, generating synthetic training data...")
                return await self._train_synthetic(db)
            
            X = np.array(X)
            y = np.array(y)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=5)
            cv_scores = cross_val_score(self.model, X_scaled, y, cv=tscv, scoring='accuracy')
            
            logger.info(f"📈 Cross-validation scores: {cv_scores}")
            logger.info(f"📈 Mean CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
            
            # Train final model on all data
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.model_accuracy = cv_scores.mean()
            self.last_training_time = datetime.now(timezone.utc)
            
            # Save model
            self._save_model()
            
            result = {
                "success": True,
                "samples_used": len(X),
                "cv_accuracy": round(cv_scores.mean() * 100, 2),
                "cv_std": round(cv_scores.std() * 100, 2),
                "training_time": self.last_training_time.isoformat()
            }
            
            logger.info(f"✅ ML Training completed: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error training from historical: {e}")
            return {"success": False, "error": str(e)}
    
    async def _train_synthetic(self, db) -> Dict:
        """
        Generate synthetic training data from historical price data
        when we don't have enough validated signals.
        """
        try:
            logger.info("🔬 Generating synthetic training data from price history...")
            
            # Fetch historical price data
            from server import realtime_market_hub
            
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'EURJPY']
            X = []
            y = []
            
            for symbol in symbols:
                try:
                    candles = await realtime_market_hub.get_historical_candles(symbol, '1m', 1000)
                    
                    if not candles or len(candles) < 100:
                        continue
                    
                    df = pd.DataFrame(candles)
                    df = df.rename(columns={'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'})
                    
                    # Generate features and labels for each candle
                    for i in range(50, len(df) - 5):
                        df_slice = df.iloc[:i+1].copy()
                        features = self.extract_features(df_slice)
                        
                        if features is not None:
                            # Label: 1 if price went UP in next 5 candles, 0 otherwise
                            future_price = df['close'].iloc[i + 5]
                            current_price = df['close'].iloc[i]
                            label = 1 if future_price > current_price else 0
                            
                            X.append(features.flatten())
                            y.append(label)
                            
                except Exception as e:
                    logger.warning(f"Error processing {symbol}: {e}")
                    continue
            
            if len(X) < self.min_training_samples:
                return {"success": False, "error": "Could not generate enough synthetic data"}
            
            X = np.array(X)
            y = np.array(y)
            
            logger.info(f"📊 Generated {len(X)} synthetic training samples")
            
            # Scale and train
            X_scaled = self.scaler.fit_transform(X)
            
            tscv = TimeSeriesSplit(n_splits=5)
            cv_scores = cross_val_score(self.model, X_scaled, y, cv=tscv, scoring='accuracy')
            
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.model_accuracy = cv_scores.mean()
            self.last_training_time = datetime.now(timezone.utc)
            
            self._save_model()
            
            return {
                "success": True,
                "samples_used": len(X),
                "cv_accuracy": round(cv_scores.mean() * 100, 2),
                "data_type": "synthetic",
                "training_time": self.last_training_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating synthetic training data: {e}")
            return {"success": False, "error": str(e)}
    
    def predict(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Make a prediction using the trained ML model.
        Returns prediction with confidence score.
        """
        if not self.is_trained or self.model is None:
            return None
        
        try:
            features = self.extract_features(df)
            
            if features is None:
                return None
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Get prediction and probabilities
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            direction = "CALL" if prediction == 1 else "PUT"
            confidence = max(probabilities) * 100
            
            self.predictions_made += 1
            
            return {
                'direction': direction,
                'confidence': round(confidence, 2),
                'call_prob': round(probabilities[1] * 100, 2),
                'put_prob': round(probabilities[0] * 100, 2),
                'model_accuracy': round(self.model_accuracy * 100, 2),
                'source': 'ml_ensemble'
            }
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None
    
    def _save_model(self):
        """Save the trained model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'accuracy': self.model_accuracy,
                    'feature_names': self.feature_names,
                    'trained_at': self.last_training_time.isoformat() if self.last_training_time else None
                }, f)
            
            logger.info(f"💾 Model saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def _load_model(self) -> bool:
        """Load a previously trained model from disk"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    from safe_model_loader import RestrictedUnpickler
                    data = RestrictedUnpickler(f).load()
                
                self.model = data['model']
                self.scaler = data['scaler']
                self.model_accuracy = data['accuracy']
                self.feature_names = data['feature_names']
                self.last_training_time = datetime.fromisoformat(data['trained_at']) if data['trained_at'] else None
                self.is_trained = True
                
                logger.info(f"✅ Model loaded from {self.model_path}")
                return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
        
        return False
    
    def get_stats(self) -> Dict:
        """Get current ML system statistics"""
        return {
            "is_trained": self.is_trained,
            "model_accuracy": round(self.model_accuracy * 100, 2) if self.model_accuracy else 0,
            "predictions_made": self.predictions_made,
            "last_training": self.last_training_time.isoformat() if self.last_training_time else None,
            "feature_count": len(self.feature_names),
            "ml_available": ML_AVAILABLE
        }


# Global instance
enhanced_ai_ml = EnhancedAIMLSystem()

# Try to load existing model
enhanced_ai_ml._load_model()
