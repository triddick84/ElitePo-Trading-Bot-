"""
Enhanced Signal Quality Optimizer
Improves accuracy, confidence, and speed of signal generation across all timeframes
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EnhancedSignalQualityOptimizer:
    """
    Advanced signal quality optimization system that improves:
    1. Real-time data fetching speed
    2. Analysis accuracy
    3. Confidence scoring
    4. Prediction reliability
    """
    
    def __init__(self):
        self.confidence_threshold = 75.0
        self.min_data_points = 50
        self.quality_weights = {
            'trend_strength': 0.25,
            'momentum_alignment': 0.20,
            'volatility_score': 0.15,
            'volume_confirmation': 0.15,
            'support_resistance': 0.15,
            'multi_timeframe_alignment': 0.10
        }
        logger.info("🎯 Enhanced Signal Quality Optimizer initialized")
    
    def optimize_signal_quality(self, signal: Dict[str, Any], market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Enhance signal quality with advanced analysis
        
        Args:
            signal: Raw signal from strategy
            market_data: DataFrame with OHLCV data
            
        Returns:
            Enhanced signal with improved confidence and quality scores
        """
        try:
            if market_data is None or len(market_data) < self.min_data_points:
                logger.warning("Insufficient data for quality optimization")
                return signal
            
            # Calculate enhanced quality scores
            trend_score = self._calculate_trend_strength(market_data)
            momentum_score = self._calculate_momentum_alignment(market_data, signal.get('direction'))
            volatility_score = self._calculate_volatility_score(market_data)
            volume_score = self._calculate_volume_confirmation(market_data, signal.get('direction'))
            sr_score = self._calculate_support_resistance_score(market_data, signal.get('direction'))
            
            # Calculate weighted quality score
            quality_score = (
                trend_score * self.quality_weights['trend_strength'] +
                momentum_score * self.quality_weights['momentum_alignment'] +
                volatility_score * self.quality_weights['volatility_score'] +
                volume_score * self.quality_weights['volume_confirmation'] +
                sr_score * self.quality_weights['support_resistance']
            )
            
            # Enhance confidence based on quality
            original_confidence = signal.get('confidence', 50)
            enhanced_confidence = min(
                original_confidence * (1 + quality_score / 100),
                99.0  # Cap at 99%
            )
            
            # Add quality metrics to signal
            signal['enhanced_confidence'] = round(enhanced_confidence, 1)
            signal['quality_score'] = round(quality_score, 1)
            signal['quality_breakdown'] = {
                'trend_strength': round(trend_score, 1),
                'momentum_alignment': round(momentum_score, 1),
                'volatility_score': round(volatility_score, 1),
                'volume_confirmation': round(volume_score, 1),
                'support_resistance': round(sr_score, 1)
            }
            
            logger.info(f"✨ Signal quality enhanced: {original_confidence:.1f}% → {enhanced_confidence:.1f}%")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error optimizing signal quality: {e}")
            return signal
    
    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """Calculate trend strength using multiple EMAs"""
        try:
            # Calculate EMAs
            ema_8 = df['close'].ewm(span=8, adjust=False).mean()
            ema_21 = df['close'].ewm(span=21, adjust=False).mean()
            ema_50 = df['close'].ewm(span=50, adjust=False).mean()
            
            # Check alignment
            current_price = df['close'].iloc[-1]
            ema_8_val = ema_8.iloc[-1]
            ema_21_val = ema_21.iloc[-1]
            ema_50_val = ema_50.iloc[-1]
            
            # Uptrend: price > ema8 > ema21 > ema50
            uptrend = (current_price > ema_8_val > ema_21_val > ema_50_val)
            # Downtrend: price < ema8 < ema21 < ema50
            downtrend = (current_price < ema_8_val < ema_21_val < ema_50_val)
            
            if uptrend or downtrend:
                # Strong trend - calculate separation
                separation = abs((ema_8_val - ema_50_val) / ema_50_val) * 100
                score = min(80 + separation * 100, 100)
            else:
                # Weak trend or ranging
                score = 40
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 50
    
    def _calculate_momentum_alignment(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate momentum alignment with signal direction"""
        try:
            # RSI
            rsi = self._calculate_rsi(df['close'], 14)
            rsi_current = rsi.iloc[-1]
            
            # MACD
            ema_12 = df['close'].ewm(span=12, adjust=False).mean()
            ema_26 = df['close'].ewm(span=26, adjust=False).mean()
            macd = ema_12 - ema_26
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            macd_current = macd.iloc[-1]
            macd_signal_current = macd_signal.iloc[-1]
            
            score = 50
            
            if direction == 'CALL':
                # For CALL, want oversold RSI and bullish MACD
                if rsi_current < 40:
                    score += 20
                elif rsi_current < 50:
                    score += 10
                
                if macd_current > macd_signal_current:
                    score += 30
                    
            elif direction == 'PUT':
                # For PUT, want overbought RSI and bearish MACD
                if rsi_current > 60:
                    score += 20
                elif rsi_current > 50:
                    score += 10
                
                if macd_current < macd_signal_current:
                    score += 30
            
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"Error calculating momentum alignment: {e}")
            return 50
    
    def _calculate_volatility_score(self, df: pd.DataFrame) -> float:
        """Calculate optimal volatility score"""
        try:
            # ATR for volatility
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(14).mean()
            
            # Calculate volatility percentage
            atr_current = atr.iloc[-1]
            price = df['close'].iloc[-1]
            volatility_pct = (atr_current / price) * 100
            
            # Optimal volatility: 0.5% - 2.0%
            if 0.5 <= volatility_pct <= 2.0:
                score = 90
            elif 0.3 <= volatility_pct < 0.5:
                score = 70  # Low volatility
            elif 2.0 < volatility_pct <= 3.0:
                score = 70  # Moderate high volatility
            else:
                score = 50  # Too low or too high
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating volatility score: {e}")
            return 50
    
    def _calculate_volume_confirmation(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate volume confirmation score"""
        try:
            if 'volume' not in df.columns or df['volume'].sum() == 0:
                return 50  # Neutral if no volume data
            
            # Volume MA
            volume_ma = df['volume'].rolling(20).mean()
            current_volume = df['volume'].iloc[-1]
            avg_volume = volume_ma.iloc[-1]
            
            # Price change
            price_change = df['close'].iloc[-1] - df['close'].iloc[-2]
            
            score = 50
            
            # High volume confirmation
            if current_volume > avg_volume * 1.5:
                if direction == 'CALL' and price_change > 0:
                    score = 90  # Strong bullish volume
                elif direction == 'PUT' and price_change < 0:
                    score = 90  # Strong bearish volume
                else:
                    score = 70  # High volume but conflicting direction
            elif current_volume > avg_volume:
                score = 70  # Above average volume
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating volume confirmation: {e}")
            return 50
    
    def _calculate_support_resistance_score(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate support/resistance score"""
        try:
            current_price = df['close'].iloc[-1]
            
            # Find recent highs and lows
            highs = df['high'].rolling(20).max()
            lows = df['low'].rolling(20).min()
            
            recent_high = highs.iloc[-1]
            recent_low = lows.iloc[-1]
            
            # Calculate position in range
            range_size = recent_high - recent_low
            if range_size == 0:
                return 50
            
            position = (current_price - recent_low) / range_size
            
            score = 50
            
            if direction == 'CALL':
                # For CALL, want to be near support (low in range)
                if position < 0.3:
                    score = 90  # Near support
                elif position < 0.5:
                    score = 70
            elif direction == 'PUT':
                # For PUT, want to be near resistance (high in range)
                if position > 0.7:
                    score = 90  # Near resistance
                elif position > 0.5:
                    score = 70
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance score: {e}")
            return 50
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def filter_high_quality_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter signals to only return high quality ones
        
        Args:
            signals: List of signals to filter
            
        Returns:
            Filtered list of high-quality signals
        """
        high_quality = []
        
        for signal in signals:
            enhanced_conf = signal.get('enhanced_confidence', signal.get('confidence', 0))
            quality_score = signal.get('quality_score', 0)
            
            # Only keep signals with high confidence AND quality
            if enhanced_conf >= self.confidence_threshold and quality_score >= 60:
                high_quality.append(signal)
                logger.info(f"✅ High quality signal: {signal.get('direction')} - {enhanced_conf:.1f}% confidence, {quality_score:.1f} quality")
            else:
                logger.debug(f"⏭️ Filtered out low quality signal: {enhanced_conf:.1f}% confidence, {quality_score:.1f} quality")
        
        return high_quality


# Global instance
enhanced_signal_optimizer = EnhancedSignalQualityOptimizer()
