"""
Advanced Signal Strategies - Inspired by IQ-720 Trading Bot
============================================================
Implements sophisticated trading strategies with:
- Market Regime Detection (Trend/Range/Volatility)
- Session-aware Signal Generation (Asian/London/NY)
- Ensemble Signal Combination
- Confidence Calibration
- Kelly Criterion Position Sizing
- 60+ Technical Features

Author: Elite Pocket Option Bot
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


class TradingSession(Enum):
    ASIAN = "asian"         # 00:00 - 08:00 UTC
    LONDON = "london"       # 08:00 - 16:00 UTC
    NEW_YORK = "new_york"   # 13:00 - 21:00 UTC
    OVERLAP = "overlap"     # London/NY overlap 13:00-16:00 UTC
    OFF_HOURS = "off_hours"


class AdvancedSignalGenerator:
    """
    Advanced signal generator with market regime detection,
    session awareness, and ensemble signal combination.
    """
    
    def __init__(self):
        self.min_confidence = 65
        self.calibration_factor = 0.85  # Reduce overconfidence
        
        # Session-specific parameters
        self.session_weights = {
            TradingSession.ASIAN: 0.8,       # Lower weight during Asian
            TradingSession.LONDON: 1.0,      # Full weight during London
            TradingSession.NEW_YORK: 1.0,    # Full weight during NY
            TradingSession.OVERLAP: 1.2,     # Higher weight during overlap (best liquidity)
            TradingSession.OFF_HOURS: 0.6,   # Lower weight during off hours
        }
        
        # Market regime signal adjustments
        self.regime_adjustments = {
            MarketRegime.TRENDING_UP: {"call_boost": 10, "put_penalty": 5},
            MarketRegime.TRENDING_DOWN: {"call_penalty": 5, "put_boost": 10},
            MarketRegime.RANGING: {"reversal_boost": 8},
            MarketRegime.HIGH_VOLATILITY: {"confidence_penalty": 10},
            MarketRegime.LOW_VOLATILITY: {"confidence_boost": 5},
        }
    
    def get_current_session(self) -> TradingSession:
        """Determine current trading session based on UTC time"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Check for London/NY overlap first (best trading hours)
        if 13 <= hour < 16:
            return TradingSession.OVERLAP
        
        # Asian session (Tokyo)
        if 0 <= hour < 8:
            return TradingSession.ASIAN
        
        # London session
        if 8 <= hour < 16:
            return TradingSession.LONDON
        
        # New York session
        if 13 <= hour < 21:
            return TradingSession.NEW_YORK
        
        return TradingSession.OFF_HOURS
    
    def detect_market_regime(self, closes: pd.Series, highs: pd.Series = None, 
                            lows: pd.Series = None) -> MarketRegime:
        """
        Detect current market regime using multiple indicators.
        
        Returns: MarketRegime enum
        """
        if len(closes) < 50:
            return MarketRegime.UNKNOWN
        
        try:
            # 1. Trend Detection using ADX and Directional Movement
            adx = self._calculate_adx(closes, highs, lows, period=14)
            
            # 2. Volatility Detection using ATR ratio
            atr = self._calculate_atr(highs, lows, closes, period=14)
            avg_atr = atr.rolling(20).mean().iloc[-1]
            current_atr = atr.iloc[-1]
            volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
            
            # 3. Trend Direction using EMA
            ema_fast = closes.ewm(span=12).mean()
            ema_slow = closes.ewm(span=26).mean()
            trend_direction = 1 if ema_fast.iloc[-1] > ema_slow.iloc[-1] else -1
            
            # 4. Price range vs ATR (ranging detection)
            recent_range = closes.iloc[-20:].max() - closes.iloc[-20:].min()
            avg_range = atr.iloc[-20:].mean() * 20
            range_ratio = recent_range / avg_range if avg_range > 0 else 1.0
            
            # Decision logic
            if volatility_ratio > 1.5:
                return MarketRegime.HIGH_VOLATILITY
            elif volatility_ratio < 0.6:
                return MarketRegime.LOW_VOLATILITY
            
            if adx is not None and adx > 25:
                if trend_direction > 0:
                    return MarketRegime.TRENDING_UP
                else:
                    return MarketRegime.TRENDING_DOWN
            elif range_ratio < 0.8:
                return MarketRegime.RANGING
            
            return MarketRegime.UNKNOWN
            
        except Exception as e:
            logger.error(f"Market regime detection error: {e}")
            return MarketRegime.UNKNOWN
    
    def _calculate_adx(self, closes: pd.Series, highs: pd.Series = None, 
                       lows: pd.Series = None, period: int = 14) -> Optional[float]:
        """Calculate Average Directional Index"""
        if highs is None or lows is None:
            return None
        
        try:
            # True Range
            tr1 = highs - lows
            tr2 = abs(highs - closes.shift(1))
            tr3 = abs(lows - closes.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            plus_dm = highs.diff()
            minus_dm = -lows.diff()
            
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            
            # Smoothed values
            atr = tr.rolling(period).mean()
            plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
            
            # ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(period).mean()
            
            return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else None
        except:
            return None
    
    def _calculate_atr(self, highs: pd.Series, lows: pd.Series, 
                       closes: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        if highs is None or lows is None:
            highs = closes
            lows = closes
        
        tr1 = highs - lows
        tr2 = abs(highs - closes.shift(1))
        tr3 = abs(lows - closes.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def calculate_kelly_criterion(self, win_rate: float, avg_win: float, 
                                  avg_loss: float) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing.
        
        Kelly % = (Win% * Avg Win - Loss% * Avg Loss) / Avg Win
        Returns fraction of capital to risk (capped at 25%)
        """
        if avg_win <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.02  # Default 2% risk
        
        loss_rate = 1 - win_rate
        kelly = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
        
        # Cap at 25% and floor at 1%
        kelly = max(0.01, min(0.25, kelly))
        
        # Apply half-Kelly for safety
        return kelly * 0.5
    
    def calibrate_confidence(self, raw_confidence: float, 
                            market_regime: MarketRegime,
                            session: TradingSession,
                            signal_count: int) -> float:
        """
        Calibrate confidence to prevent overconfidence.
        
        Applies:
        1. Base calibration factor
        2. Market regime adjustments
        3. Session weighting
        4. Signal confirmation bonus/penalty
        """
        # Base calibration to prevent overconfidence
        calibrated = raw_confidence * self.calibration_factor
        
        # Apply session weight
        session_weight = self.session_weights.get(session, 1.0)
        calibrated *= session_weight
        
        # Apply regime adjustments
        if market_regime == MarketRegime.HIGH_VOLATILITY:
            calibrated -= 10
        elif market_regime == MarketRegime.LOW_VOLATILITY:
            calibrated += 5
        
        # Signal confirmation bonus
        if signal_count >= 3:
            calibrated += 5
        elif signal_count <= 1:
            calibrated -= 5
        
        return max(0, min(95, calibrated))
    
    def generate_60_features(self, candles: List[Dict]) -> Dict[str, float]:
        """
        Generate 60+ technical features for ML and signal generation.
        
        Features include:
        - Price-based (returns, volatility)
        - Moving averages (SMA, EMA multiple periods)
        - Momentum (RSI, Stochastic, ROC)
        - Trend (MACD, ADX, Aroon)
        - Volatility (ATR, Bollinger, Keltner)
        - Volume-based (if available)
        - Pattern recognition
        """
        if len(candles) < 60:
            return {}
        
        try:
            closes = pd.Series([float(c.get('close', c.get('Close', 0))) for c in candles])
            highs = pd.Series([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles])
            lows = pd.Series([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])
            
            features = {}
            
            # === PRICE FEATURES (10) ===
            features['return_1'] = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
            features['return_5'] = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100
            features['return_10'] = (closes.iloc[-1] / closes.iloc[-11] - 1) * 100
            features['return_20'] = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100
            features['high_low_range'] = (highs.iloc[-1] - lows.iloc[-1]) / closes.iloc[-1] * 100
            features['close_position'] = (closes.iloc[-1] - lows.iloc[-1]) / (highs.iloc[-1] - lows.iloc[-1] + 0.0001)
            features['gap'] = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
            features['volatility_5'] = closes.iloc[-5:].std() / closes.iloc[-5:].mean() * 100
            features['volatility_20'] = closes.iloc[-20:].std() / closes.iloc[-20:].mean() * 100
            features['price_acceleration'] = features['return_5'] - features['return_10']
            
            # === MOVING AVERAGES (12) ===
            for period in [5, 10, 20, 50]:
                sma = closes.rolling(period).mean()
                ema = closes.ewm(span=period).mean()
                features[f'sma_{period}_dist'] = (closes.iloc[-1] / sma.iloc[-1] - 1) * 100
                features[f'ema_{period}_dist'] = (closes.iloc[-1] / ema.iloc[-1] - 1) * 100
                features[f'sma_{period}_slope'] = (sma.iloc[-1] / sma.iloc[-5] - 1) * 100
            
            # === MOMENTUM (12) ===
            # RSI
            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 0.0001)
            rsi = 100 - (100 / (1 + rs))
            features['rsi_14'] = rsi.iloc[-1]
            features['rsi_7'] = self._calculate_rsi(closes, 7)
            features['rsi_slope'] = rsi.iloc[-1] - rsi.iloc[-5]
            
            # Stochastic
            lowest_low = lows.rolling(14).min()
            highest_high = highs.rolling(14).max()
            stoch_k = ((closes - lowest_low) / (highest_high - lowest_low + 0.0001)) * 100
            stoch_d = stoch_k.rolling(3).mean()
            features['stoch_k'] = stoch_k.iloc[-1]
            features['stoch_d'] = stoch_d.iloc[-1]
            features['stoch_crossover'] = 1 if stoch_k.iloc[-1] > stoch_d.iloc[-1] and stoch_k.iloc[-2] <= stoch_d.iloc[-2] else 0
            
            # ROC
            features['roc_10'] = (closes.iloc[-1] / closes.iloc[-11] - 1) * 100
            features['roc_20'] = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100
            
            # Williams %R
            features['williams_r'] = ((highest_high.iloc[-1] - closes.iloc[-1]) / 
                                     (highest_high.iloc[-1] - lowest_low.iloc[-1] + 0.0001)) * -100
            
            # Momentum
            features['momentum_10'] = closes.iloc[-1] - closes.iloc[-11]
            features['momentum_20'] = closes.iloc[-1] - closes.iloc[-21]
            
            # === TREND (10) ===
            # MACD
            ema_12 = closes.ewm(span=12).mean()
            ema_26 = closes.ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            features['macd'] = macd.iloc[-1]
            features['macd_signal'] = signal.iloc[-1]
            features['macd_hist'] = macd.iloc[-1] - signal.iloc[-1]
            features['macd_crossover'] = 1 if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2] else 0
            
            # ADX
            adx = self._calculate_adx(closes, highs, lows)
            features['adx'] = adx if adx is not None else 25
            
            # EMA Alignment
            ema_5 = closes.ewm(span=5).mean().iloc[-1]
            ema_10 = closes.ewm(span=10).mean().iloc[-1]
            ema_20 = closes.ewm(span=20).mean().iloc[-1]
            features['ema_aligned_bullish'] = 1 if ema_5 > ema_10 > ema_20 else 0
            features['ema_aligned_bearish'] = 1 if ema_5 < ema_10 < ema_20 else 0
            
            # Higher High / Lower Low
            features['higher_high'] = 1 if highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3] else 0
            features['lower_low'] = 1 if lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3] else 0
            
            # === VOLATILITY (10) ===
            # ATR
            atr = self._calculate_atr(highs, lows, closes, 14)
            features['atr'] = atr.iloc[-1]
            features['atr_percent'] = (atr.iloc[-1] / closes.iloc[-1]) * 100
            features['atr_ratio'] = atr.iloc[-1] / atr.iloc[-20:].mean()
            
            # Bollinger Bands
            bb_mid = closes.rolling(20).mean()
            bb_std = closes.rolling(20).std()
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            features['bb_position'] = (closes.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1] + 0.0001)
            features['bb_width'] = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100
            features['bb_squeeze'] = 1 if features['bb_width'] < features['bb_width'] * 0.5 else 0
            
            # Keltner Channel
            kc_mid = closes.ewm(span=20).mean()
            kc_atr = self._calculate_atr(highs, lows, closes, 20)
            kc_upper = kc_mid + 2 * kc_atr
            kc_lower = kc_mid - 2 * kc_atr
            features['kc_position'] = (closes.iloc[-1] - kc_lower.iloc[-1]) / (kc_upper.iloc[-1] - kc_lower.iloc[-1] + 0.0001)
            
            # === PATTERN RECOGNITION (6) ===
            # Candlestick patterns
            body = abs(closes.iloc[-1] - closes.iloc[-2])
            wick_upper = highs.iloc[-1] - max(closes.iloc[-1], closes.iloc[-2])
            wick_lower = min(closes.iloc[-1], closes.iloc[-2]) - lows.iloc[-1]
            
            features['doji'] = 1 if body < (highs.iloc[-1] - lows.iloc[-1]) * 0.1 else 0
            features['hammer'] = 1 if wick_lower > body * 2 and wick_upper < body * 0.5 else 0
            features['shooting_star'] = 1 if wick_upper > body * 2 and wick_lower < body * 0.5 else 0
            features['bullish_engulfing'] = 1 if closes.iloc[-1] > closes.iloc[-2] and closes.iloc[-2] < closes.iloc[-3] else 0
            features['bearish_engulfing'] = 1 if closes.iloc[-1] < closes.iloc[-2] and closes.iloc[-2] > closes.iloc[-3] else 0
            features['three_white_soldiers'] = 1 if all(closes.iloc[-3:].diff()[1:] > 0) else 0
            
            return features
            
        except Exception as e:
            logger.error(f"Feature generation error: {e}")
            return {}
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 0.0001)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def generate_ensemble_signal(self, candles: List[Dict]) -> Optional[Dict]:
        """
        Generate trading signal using ensemble of strategies.
        
        Combines:
        1. Technical indicators (RSI, MACD, Stochastic, etc.)
        2. Market regime analysis
        3. Session awareness
        4. Feature-based scoring
        
        Returns signal dict with direction, confidence, and metadata
        """
        if len(candles) < 60:
            return None
        
        try:
            # Extract price data
            closes = pd.Series([float(c.get('close', c.get('Close', 0))) for c in candles])
            highs = pd.Series([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles])
            lows = pd.Series([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])
            
            # Get market context
            regime = self.detect_market_regime(closes, highs, lows)
            session = self.get_current_session()
            features = self.generate_60_features(candles)
            
            if not features:
                return None
            
            # === SIGNAL SCORING ===
            call_score = 0
            put_score = 0
            confirmations = []
            
            # 1. RSI Signals (weight: 20%)
            rsi = features.get('rsi_14', 50)
            if rsi < 30:
                call_score += 15
                confirmations.append('RSI_OVERSOLD')
            elif rsi > 70:
                put_score += 15
                confirmations.append('RSI_OVERBOUGHT')
            elif rsi < 40:
                call_score += 5
            elif rsi > 60:
                put_score += 5
            
            # 2. MACD Signals (weight: 20%)
            macd_hist = features.get('macd_hist', 0)
            macd_crossover = features.get('macd_crossover', 0)
            if macd_crossover == 1:
                call_score += 20
                confirmations.append('MACD_BULLISH_CROSS')
            elif macd_hist > 0:
                call_score += 10
                confirmations.append('MACD_BULLISH')
            elif macd_hist < 0:
                put_score += 10
                confirmations.append('MACD_BEARISH')
            
            # 3. Stochastic Signals (weight: 15%)
            stoch_k = features.get('stoch_k', 50)
            stoch_crossover = features.get('stoch_crossover', 0)
            if stoch_k < 20:
                call_score += 15
                confirmations.append('STOCH_OVERSOLD')
            elif stoch_k > 80:
                put_score += 15
                confirmations.append('STOCH_OVERBOUGHT')
            if stoch_crossover == 1:
                call_score += 10
                confirmations.append('STOCH_BULLISH_CROSS')
            
            # 4. EMA Alignment (weight: 15%)
            if features.get('ema_aligned_bullish', 0) == 1:
                call_score += 15
                confirmations.append('EMA_ALIGNED_BULLISH')
            elif features.get('ema_aligned_bearish', 0) == 1:
                put_score += 15
                confirmations.append('EMA_ALIGNED_BEARISH')
            
            # 5. Bollinger Band Position (weight: 10%)
            bb_pos = features.get('bb_position', 0.5)
            if bb_pos < 0.1:
                call_score += 10
                confirmations.append('BB_OVERSOLD')
            elif bb_pos > 0.9:
                put_score += 10
                confirmations.append('BB_OVERBOUGHT')
            
            # 6. Keltner Channel Position (weight: 10%)
            kc_pos = features.get('kc_position', 0.5)
            if kc_pos < 0.2:
                call_score += 10
                confirmations.append('KC_OVERSOLD')
            elif kc_pos > 0.8:
                put_score += 10
                confirmations.append('KC_OVERBOUGHT')
            
            # 7. ADX Trend Strength (weight: 10%)
            adx = features.get('adx', 25)
            if adx > 25:
                # Strong trend - go with the trend
                if regime == MarketRegime.TRENDING_UP:
                    call_score += 10
                    confirmations.append('ADX_STRONG_UPTREND')
                elif regime == MarketRegime.TRENDING_DOWN:
                    put_score += 10
                    confirmations.append('ADX_STRONG_DOWNTREND')
            
            # 8. Candlestick Patterns (bonus)
            if features.get('hammer', 0) == 1:
                call_score += 8
                confirmations.append('HAMMER_PATTERN')
            if features.get('shooting_star', 0) == 1:
                put_score += 8
                confirmations.append('SHOOTING_STAR')
            if features.get('bullish_engulfing', 0) == 1:
                call_score += 8
                confirmations.append('BULLISH_ENGULFING')
            if features.get('bearish_engulfing', 0) == 1:
                put_score += 8
                confirmations.append('BEARISH_ENGULFING')
            
            # === APPLY MARKET REGIME ADJUSTMENTS ===
            adj = self.regime_adjustments.get(regime, {})
            if 'call_boost' in adj:
                call_score += adj['call_boost']
            if 'call_penalty' in adj:
                call_score -= adj['call_penalty']
            if 'put_boost' in adj:
                put_score += adj['put_boost']
            if 'put_penalty' in adj:
                put_score -= adj['put_penalty']
            
            # === DETERMINE DIRECTION ===
            min_score_diff = 15  # Minimum difference to generate signal
            
            if call_score > put_score + min_score_diff:
                direction = "CALL"
                raw_confidence = 50 + call_score
            elif put_score > call_score + min_score_diff:
                direction = "PUT"
                raw_confidence = 50 + put_score
            else:
                return None  # No clear signal
            
            # === CALIBRATE CONFIDENCE ===
            calibrated_confidence = self.calibrate_confidence(
                raw_confidence=raw_confidence,
                market_regime=regime,
                session=session,
                signal_count=len(confirmations)
            )
            
            if calibrated_confidence < self.min_confidence:
                return None
            
            return {
                "direction": direction,
                "confidence": round(calibrated_confidence, 1),
                "raw_confidence": round(raw_confidence, 1),
                "strategy": "IQ720_Ensemble",
                "confirmations": confirmations,
                "market_regime": regime.value,
                "session": session.value,
                "call_score": call_score,
                "put_score": put_score,
                "features": {
                    "rsi": round(features.get('rsi_14', 50), 2),
                    "macd_hist": round(features.get('macd_hist', 0), 6),
                    "stoch_k": round(features.get('stoch_k', 50), 2),
                    "bb_position": round(features.get('bb_position', 0.5), 3),
                    "kc_position": round(features.get('kc_position', 0.5), 3),
                    "adx": round(features.get('adx', 25), 2),
                },
                "expiry": 5,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ensemble signal generation error: {e}")
            return None


# Global instance
advanced_signal_generator = AdvancedSignalGenerator()


def generate_iq720_signal(candles: List[Dict]) -> Optional[Dict]:
    """
    Generate trading signal using IQ-720 inspired ensemble strategy.
    
    This is the main entry point for the advanced signal generation.
    """
    return advanced_signal_generator.generate_ensemble_signal(candles)
