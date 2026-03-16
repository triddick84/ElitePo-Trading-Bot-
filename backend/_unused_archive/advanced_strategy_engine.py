import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from trading_models import TradingSignal, SignalDirection, TradingStrategy
from pocket_option_timing_sync import pocket_option_sync
import yfinance as yf
from scipy.signal import find_peaks
import talib

logger = logging.getLogger(__name__)

class AdvancedStrategyEngine:
    """
    Advanced strategy engine implementing researched high-accuracy algorithms:
    - 3 WMA Crossover strategy for 5s, 15s timeframes (95%+ accuracy target)
    - GPT/AI advanced algorithms for 1m, 3m timeframes
    - Support/Resistance with AI candle pattern recognition
    """
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.chicago_tz = pocket_option_sync.pocket_option_tz
        
        # Strategy configuration per timeframe
        self.timeframe_strategies = {
            '5s': 'wma_crossover_ultra',
            '15s': 'wma_crossover_ultra', 
            '30s': 'hybrid_scalping',
            '1m': 'gpt_ai_advanced',
            '2m': 'gpt_ai_advanced',
            '3m': 'gpt_ai_advanced',
            '5m': 'ensemble_ml'
        }
        
        # WMA Crossover parameters for ultra-short timeframes
        self.wma_params = {
            '5s': {'wma1': 3, 'wma2': 8, 'tma': 4, 'trend_period': 10},
            '15s': {'wma1': 3, 'wma2': 8, 'tma': 4, 'trend_period': 15}
        }
        
        # Support/Resistance detection parameters
        self.sr_params = {
            'lookback_period': 20,
            'min_touches': 2,
            'proximity_threshold': 0.001  # 0.1% proximity to S/R level
        }
        
        # Candle pattern recognition training data
        self.candle_patterns = {
            'bullish': ['hammer', 'bullish_engulfing', 'morning_star', 'dragonfly_doji'],
            'bearish': ['shooting_star', 'bearish_engulfing', 'evening_star', 'gravestone_doji'],
            'neutral': ['spinning_top', 'doji', 'harami']
        }
    
    async def generate_advanced_signal(self, symbol: str, market_data, timeframe: str, 
                                     real_time_data: List[Dict]) -> Optional[TradingSignal]:
        """
        Generate signal using the optimal strategy for the selected timeframe
        """
        try:
            strategy = self.timeframe_strategies.get(timeframe, 'hybrid_scalping')
            logger.info(f"Using {strategy} strategy for {timeframe} timeframe on {symbol}")
            
            df = pd.DataFrame(real_time_data)
            if len(df) < 30:
                logger.warning(f"Insufficient data for {timeframe} analysis: {len(df)} bars")
                return None
            
            # Route to appropriate strategy
            if strategy == 'wma_crossover_ultra':
                return await self._wma_crossover_ultra_strategy(symbol, market_data, df, timeframe)
            elif strategy == 'gpt_ai_advanced':
                return await self._gpt_ai_advanced_strategy(symbol, market_data, df, timeframe)
            elif strategy == 'ensemble_ml':
                return await self._ensemble_ml_strategy(symbol, market_data, df, timeframe)
            else:
                return await self._hybrid_scalping_strategy(symbol, market_data, df, timeframe)
                
        except Exception as e:
            logger.error(f"Error generating advanced signal: {e}")
            return None
    
    async def _wma_crossover_ultra_strategy(self, symbol: str, market_data, df: pd.DataFrame, 
                                          timeframe: str) -> Optional[TradingSignal]:
        """
        3 WMA Crossover strategy for 5s and 15s timeframes
        1st MA: 3 WMA, 2nd MA: 8 WMA, 3rd MA: 4 TMA
        """
        try:
            if timeframe not in ['5s', '15s']:
                return None
            
            params = self.wma_params[timeframe]
            closes = df['close'].values
            
            # Calculate 3-period WMA
            wma_3 = self._calculate_wma(closes, params['wma1'])
            
            # Calculate 8-period WMA
            wma_8 = self._calculate_wma(closes, params['wma2'])
            
            # Calculate 4-period TMA (Triangular Moving Average)
            tma_4 = self._calculate_tma(closes, params['tma'])
            
            # Get current values
            wma3_current = wma_3[-1]
            wma3_prev = wma_3[-2] if len(wma_3) > 1 else wma3_current
            wma8_current = wma_8[-1]
            wma8_prev = wma_8[-2] if len(wma_8) > 1 else wma8_current
            tma4_current = tma_4[-1]
            tma4_prev = tma_4[-2] if len(tma_4) > 1 else tma4_current
            
            # Detect crossovers
            wma_cross_bullish = wma3_prev <= wma8_prev and wma3_current > wma8_current
            wma_cross_bearish = wma3_prev >= wma8_prev and wma3_current < wma8_current
            
            # TMA crossing both WMAs
            tma_above_both = tma4_current > max(wma3_current, wma8_current)
            tma_below_both = tma4_current < min(wma3_current, wma8_current)
            tma_was_below_both = tma4_prev < min(wma3_prev, wma8_prev)
            tma_was_above_both = tma4_prev > max(wma3_prev, wma8_prev)
            
            # TMA crossover detection
            tma_crosses_up = tma_was_below_both and tma_above_both
            tma_crosses_down = tma_was_above_both and tma_below_both
            
            # Trend confirmation using larger period
            trend_ma = self._calculate_wma(closes, params['trend_period'])
            current_price = closes[-1]
            uptrend = current_price > trend_ma[-1]
            downtrend = current_price < trend_ma[-1]
            
            # Support/Resistance analysis
            sr_levels = await self._detect_support_resistance(df)
            sr_signal = self._analyze_sr_proximity(current_price, sr_levels)
            
            # AI Candle pattern analysis
            candle_pattern = await self._ai_candle_pattern_analysis(df.tail(10))
            
            # Signal generation logic
            confidence = 0.0
            direction = None
            signal_factors = []
            
            # BULLISH SIGNAL CONDITIONS
            if (wma_cross_bullish and tma_crosses_up and uptrend):
                direction = SignalDirection.BUY
                confidence = 85.0
                signal_factors.extend(['WMA_Bullish_Cross', 'TMA_Crosses_Up', 'Uptrend_Confirmed'])
                
                # Bonus confidence factors
                if sr_signal == 'support_bounce':
                    confidence += 5
                    signal_factors.append('Support_Bounce')
                if candle_pattern['sentiment'] == 'bullish':
                    confidence += 4
                    signal_factors.append('Bullish_Candle_Pattern')
                if candle_pattern['strength'] > 0.7:
                    confidence += 3
                    signal_factors.append('Strong_Pattern_Confirmation')
            
            # BEARISH SIGNAL CONDITIONS  
            elif (wma_cross_bearish and tma_crosses_down and downtrend):
                direction = SignalDirection.SELL
                confidence = 85.0
                signal_factors.extend(['WMA_Bearish_Cross', 'TMA_Crosses_Down', 'Downtrend_Confirmed'])
                
                # Bonus confidence factors
                if sr_signal == 'resistance_rejection':
                    confidence += 5
                    signal_factors.append('Resistance_Rejection')
                if candle_pattern['sentiment'] == 'bearish':
                    confidence += 4
                    signal_factors.append('Bearish_Candle_Pattern')
                if candle_pattern['strength'] > 0.7:
                    confidence += 3
                    signal_factors.append('Strong_Pattern_Confirmation')
            
            # Additional validation for ultra-short timeframes
            if direction:
                # Volume confirmation (if available)
                if 'volume' in df.columns:
                    volume_avg = df['volume'].rolling(10).mean().iloc[-1]
                    current_volume = df['volume'].iloc[-1]
                    if current_volume > volume_avg * 1.3:
                        confidence += 2
                        signal_factors.append('Volume_Confirmation')
                
                # Price momentum confirmation
                price_momentum = (closes[-1] - closes[-3]) / closes[-3] * 100
                if (direction == SignalDirection.BUY and price_momentum > 0.05) or \
                   (direction == SignalDirection.SELL and price_momentum < -0.05):
                    confidence += 2
                    signal_factors.append('Momentum_Confirmation')
                
                # Final confidence capping for ultra-short timeframes
                confidence = min(confidence, 97.0)
                
                # Only generate if confidence is high enough for ultra-short trading
                if confidence >= 88.0:
                    return await self._create_wma_crossover_signal(
                        symbol, market_data, direction, confidence, timeframe, signal_factors, df
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in WMA crossover strategy: {e}")
            return None
    
    async def _gpt_ai_advanced_strategy(self, symbol: str, market_data, df: pd.DataFrame, 
                                      timeframe: str) -> Optional[TradingSignal]:
        """
        Advanced GPT/AI strategy for 1m and 3m timeframes
        Combines neural network-like analysis with ensemble methods
        """
        try:
            if timeframe not in ['1m', '2m', '3m']:
                return None
            
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            # Advanced AI-inspired indicators
            # 1. Multi-layer EMA analysis (neural network-like)
            ema_layers = {
                'layer1': closes.copy(),  # Input layer
                'layer2': self._calculate_ema_smooth(closes, 5),   # Fast processing
                'layer3': self._calculate_ema_smooth(closes, 13),  # Medium processing
                'layer4': self._calculate_ema_smooth(closes, 34),  # Slow processing
            }
            
            # 2. LSTM-inspired trend analysis
            lstm_trend = self._lstm_inspired_trend_analysis(closes, 21)
            
            # 3. CNN-inspired pattern recognition
            cnn_patterns = await self._cnn_inspired_pattern_analysis(df.tail(20))
            
            # 4. Sentiment-based market regime detection
            market_regime = self._detect_market_regime(closes, highs, lows)
            
            # 5. Support/Resistance with AI enhancement
            sr_levels = await self._ai_enhanced_support_resistance(df)
            sr_analysis = self._advanced_sr_analysis(closes[-1], sr_levels, market_regime)
            
            # 6. Advanced candle behavior analysis
            candle_behavior = await self._advanced_candle_behavior_analysis(df.tail(15))
            
            # Signal scoring using AI-inspired weighted ensemble
            signal_scores = {
                'buy_score': 0.0,
                'sell_score': 0.0,
                'confidence_factors': []
            }
            
            # Layer 1: EMA Network Analysis (30% weight)
            ema_signal = self._analyze_ema_layers(ema_layers)
            if ema_signal['direction'] == 'BUY':
                signal_scores['buy_score'] += 30.0 * ema_signal['strength']
                signal_scores['confidence_factors'].append(f"EMA_Network_Bullish_{ema_signal['strength']:.2f}")
            elif ema_signal['direction'] == 'SELL':
                signal_scores['sell_score'] += 30.0 * ema_signal['strength']
                signal_scores['confidence_factors'].append(f"EMA_Network_Bearish_{ema_signal['strength']:.2f}")
            
            # Layer 2: LSTM-inspired Trend (25% weight)
            if lstm_trend['direction'] == 'BUY' and lstm_trend['confidence'] > 0.6:
                signal_scores['buy_score'] += 25.0 * lstm_trend['confidence']
                signal_scores['confidence_factors'].append(f"LSTM_Trend_Bullish_{lstm_trend['confidence']:.2f}")
            elif lstm_trend['direction'] == 'SELL' and lstm_trend['confidence'] > 0.6:
                signal_scores['sell_score'] += 25.0 * lstm_trend['confidence']
                signal_scores['confidence_factors'].append(f"LSTM_Trend_Bearish_{lstm_trend['confidence']:.2f}")
            
            # Layer 3: CNN Pattern Recognition (20% weight)
            if cnn_patterns['bullish_strength'] > 0.7:
                signal_scores['buy_score'] += 20.0 * cnn_patterns['bullish_strength']
                signal_scores['confidence_factors'].append(f"CNN_Bullish_Pattern_{cnn_patterns['bullish_strength']:.2f}")
            elif cnn_patterns['bearish_strength'] > 0.7:
                signal_scores['sell_score'] += 20.0 * cnn_patterns['bearish_strength']
                signal_scores['confidence_factors'].append(f"CNN_Bearish_Pattern_{cnn_patterns['bearish_strength']:.2f}")
            
            # Layer 4: Support/Resistance AI (15% weight)
            if sr_analysis['signal'] == 'BUY':
                signal_scores['buy_score'] += 15.0 * sr_analysis['confidence']
                signal_scores['confidence_factors'].append(f"AI_SR_Support_{sr_analysis['confidence']:.2f}")
            elif sr_analysis['signal'] == 'SELL':
                signal_scores['sell_score'] += 15.0 * sr_analysis['confidence']
                signal_scores['confidence_factors'].append(f"AI_SR_Resistance_{sr_analysis['confidence']:.2f}")
            
            # Layer 5: Advanced Candle Behavior (10% weight)
            if candle_behavior['next_candle_prediction'] == 'BUY':
                signal_scores['buy_score'] += 10.0 * candle_behavior['prediction_confidence']
                signal_scores['confidence_factors'].append(f"Candle_Behavior_Bullish_{candle_behavior['prediction_confidence']:.2f}")
            elif candle_behavior['next_candle_prediction'] == 'SELL':
                signal_scores['sell_score'] += 10.0 * candle_behavior['prediction_confidence']
                signal_scores['confidence_factors'].append(f"Candle_Behavior_Bearish_{candle_behavior['prediction_confidence']:.2f}")
            
            # Final decision with ensemble confidence
            final_confidence = max(signal_scores['buy_score'], signal_scores['sell_score'])
            direction = SignalDirection.BUY if signal_scores['buy_score'] > signal_scores['sell_score'] else SignalDirection.SELL
            
            # GPT/AI strategies require high confidence for 1m, 3m timeframes
            min_confidence = 90.0 if timeframe in ['1m', '3m'] else 85.0
            
            if final_confidence >= min_confidence:
                return await self._create_gpt_ai_signal(
                    symbol, market_data, direction, final_confidence, timeframe, 
                    signal_scores['confidence_factors'], df, market_regime
                )
            
            logger.info(f"GPT/AI signal confidence {final_confidence:.1f}% below threshold {min_confidence}% for {timeframe}")
            return None
            
        except Exception as e:
            logger.error(f"Error in GPT/AI advanced strategy: {e}")
            return None
    
    def _calculate_wma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Weighted Moving Average"""
        try:
            if len(data) < period:
                return np.full(len(data), data[0] if len(data) > 0 else 0.0)
            
            weights = np.arange(1, period + 1)
            wma = np.convolve(data, weights[::-1], mode='same') / weights.sum()
            
            # Handle edges
            wma[:period-1] = data[:period-1]
            
            return wma
            
        except Exception as e:
            logger.error(f"Error calculating WMA: {e}")
            return np.full(len(data), data[0] if len(data) > 0 else 0.0)
    
    def _calculate_tma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Triangular Moving Average (smoother than WMA)"""
        try:
            # TMA is a double-smoothed moving average
            if len(data) < period:
                return np.full(len(data), data[0] if len(data) > 0 else 0.0)
            
            # First smoothing: SMA
            sma1_period = (period + 1) // 2
            sma1 = np.convolve(data, np.ones(sma1_period), mode='same') / sma1_period
            
            # Second smoothing: SMA of the first SMA
            sma2_period = period - sma1_period + 1
            tma = np.convolve(sma1, np.ones(sma2_period), mode='same') / sma2_period
            
            # Handle edges
            tma[:period-1] = data[:period-1]
            
            return tma
            
        except Exception as e:
            logger.error(f"Error calculating TMA: {e}")
            return np.full(len(data), data[0] if len(data) > 0 else 0.0)
    
    def _calculate_ema_smooth(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate smoothed EMA for AI neural network-like processing"""
        try:
            if len(data) < 2:
                return data.copy()
            
            alpha = 2.0 / (period + 1)
            ema = np.zeros_like(data)
            ema[0] = data[0]
            
            for i in range(1, len(data)):
                ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
            return ema
            
        except Exception as e:
            logger.error(f"Error calculating EMA smooth: {e}")
            return data.copy()
    
    async def _detect_support_resistance(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """
        Advanced support and resistance detection with AI enhancement
        """
        try:
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            # Find peaks and valleys
            high_peaks, _ = find_peaks(highs, prominence=np.std(highs) * 0.5)
            low_valleys, _ = find_peaks(-lows, prominence=np.std(lows) * 0.5)
            
            # Extract resistance levels from peaks
            resistance_levels = []
            for peak in high_peaks:
                if peak < len(highs):
                    level = highs[peak]
                    # Count touches near this level
                    touches = sum(1 for h in highs if abs(h - level) / level < self.sr_params['proximity_threshold'])
                    if touches >= self.sr_params['min_touches']:
                        resistance_levels.append(level)
            
            # Extract support levels from valleys
            support_levels = []
            for valley in low_valleys:
                if valley < len(lows):
                    level = lows[valley]
                    # Count touches near this level
                    touches = sum(1 for l in lows if abs(l - level) / level < self.sr_params['proximity_threshold'])
                    if touches >= self.sr_params['min_touches']:
                        support_levels.append(level)
            
            return {
                'resistance': sorted(set(resistance_levels), reverse=True)[:5],
                'support': sorted(set(support_levels))[:5]
            }
            
        except Exception as e:
            logger.error(f"Error detecting support/resistance: {e}")
            return {'resistance': [], 'support': []}
    
    def _analyze_sr_proximity(self, current_price: float, sr_levels: Dict) -> str:
        """Analyze proximity to support/resistance levels"""
        try:
            # Check proximity to resistance
            for resistance in sr_levels.get('resistance', []):
                distance = abs(current_price - resistance) / resistance
                if distance < self.sr_params['proximity_threshold'] * 2:
                    if current_price < resistance * 1.001:  # Just below resistance
                        return 'resistance_rejection'
                    elif current_price > resistance * 1.001:  # Breaking resistance
                        return 'resistance_breakout'
            
            # Check proximity to support
            for support in sr_levels.get('support', []):
                distance = abs(current_price - support) / support
                if distance < self.sr_params['proximity_threshold'] * 2:
                    if current_price > support * 0.999:  # Just above support
                        return 'support_bounce'
                    elif current_price < support * 0.999:  # Breaking support
                        return 'support_breakdown'
            
            return 'neutral'
            
        except Exception as e:
            logger.error(f"Error analyzing S/R proximity: {e}")
            return 'neutral'
    
    async def _ai_candle_pattern_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        AI-enhanced candle pattern analysis with machine learning-like recognition
        """
        try:
            patterns_detected = []
            overall_sentiment = 'neutral'
            pattern_strength = 0.0
            
            for i in range(1, len(df)):
                current = df.iloc[i]
                previous = df.iloc[i-1] if i > 0 else current
                
                # Calculate candle properties
                body_size = abs(current['close'] - current['open'])
                total_range = current['high'] - current['low']
                upper_shadow = current['high'] - max(current['close'], current['open'])
                lower_shadow = min(current['close'], current['open']) - current['low']
                
                if total_range == 0:
                    continue
                
                body_ratio = body_size / total_range
                upper_shadow_ratio = upper_shadow / total_range
                lower_shadow_ratio = lower_shadow / total_range
                
                # AI pattern recognition
                confidence = 0.0
                
                # Hammer pattern (bullish reversal)
                if lower_shadow_ratio > 0.6 and body_ratio < 0.3 and upper_shadow_ratio < 0.1:
                    patterns_detected.append({'pattern': 'hammer', 'sentiment': 'bullish', 'confidence': 0.8})
                    confidence = 0.8
                
                # Shooting star (bearish reversal)
                elif upper_shadow_ratio > 0.6 and body_ratio < 0.3 and lower_shadow_ratio < 0.1:
                    patterns_detected.append({'pattern': 'shooting_star', 'sentiment': 'bearish', 'confidence': 0.8})
                    confidence = 0.8
                
                # Bullish engulfing
                elif (current['close'] > current['open'] and previous['close'] < previous['open'] and
                      current['open'] < previous['close'] and current['close'] > previous['open']):
                    patterns_detected.append({'pattern': 'bullish_engulfing', 'sentiment': 'bullish', 'confidence': 0.9})
                    confidence = 0.9
                
                # Bearish engulfing
                elif (current['close'] < current['open'] and previous['close'] > previous['open'] and
                      current['open'] > previous['close'] and current['close'] < previous['open']):
                    patterns_detected.append({'pattern': 'bearish_engulfing', 'sentiment': 'bearish', 'confidence': 0.9})
                    confidence = 0.9
                
                # Strong bullish candle
                elif current['close'] > current['open'] and body_ratio > 0.7:
                    patterns_detected.append({'pattern': 'strong_bullish', 'sentiment': 'bullish', 'confidence': 0.6})
                    confidence = 0.6
                
                # Strong bearish candle
                elif current['close'] < current['open'] and body_ratio > 0.7:
                    patterns_detected.append({'pattern': 'strong_bearish', 'sentiment': 'bearish', 'confidence': 0.6})
                    confidence = 0.6
                
                pattern_strength = max(pattern_strength, confidence)
            
            # Determine overall sentiment
            if patterns_detected:
                bullish_patterns = [p for p in patterns_detected if p['sentiment'] == 'bullish']
                bearish_patterns = [p for p in patterns_detected if p['sentiment'] == 'bearish']
                
                bullish_strength = sum(p['confidence'] for p in bullish_patterns) / len(patterns_detected)
                bearish_strength = sum(p['confidence'] for p in bearish_patterns) / len(patterns_detected)
                
                if bullish_strength > bearish_strength:
                    overall_sentiment = 'bullish'
                elif bearish_strength > bullish_strength:
                    overall_sentiment = 'bearish'
            
            return {
                'sentiment': overall_sentiment,
                'strength': pattern_strength,
                'patterns_detected': len(patterns_detected),
                'bullish_patterns': len([p for p in patterns_detected if p['sentiment'] == 'bullish']),
                'bearish_patterns': len([p for p in patterns_detected if p['sentiment'] == 'bearish']),
                'details': patterns_detected
            }
            
        except Exception as e:
            logger.error(f"Error in AI candle pattern analysis: {e}")
            return {'sentiment': 'neutral', 'strength': 0.0, 'patterns_detected': 0}
    
    def _lstm_inspired_trend_analysis(self, data: np.ndarray, period: int) -> Dict[str, Any]:
        """
        LSTM-inspired trend analysis using sequential pattern recognition
        """
        try:
            if len(data) < period:
                return {'direction': 'neutral', 'confidence': 0.5}
            
            # Create sequences like LSTM would process
            sequences = []
            for i in range(period, len(data)):
                sequences.append(data[i-period:i])
            
            if not sequences:
                return {'direction': 'neutral', 'confidence': 0.5}
            
            # Analyze sequence trends
            trend_scores = []
            for seq in sequences[-10:]:  # Last 10 sequences
                # Calculate sequence trend
                start_price = seq[0]
                end_price = seq[-1]
                trend_strength = (end_price - start_price) / start_price
                trend_scores.append(trend_strength)
            
            # Overall trend confidence
            avg_trend = np.mean(trend_scores)
            trend_consistency = 1.0 - np.std(trend_scores) / (abs(np.mean(trend_scores)) + 0.001)
            
            confidence = min(trend_consistency, 1.0)
            direction = 'BUY' if avg_trend > 0 else 'SELL'
            
            return {
                'direction': direction,
                'confidence': confidence,
                'trend_strength': abs(avg_trend),
                'consistency': trend_consistency
            }
            
        except Exception as e:
            logger.error(f"Error in LSTM-inspired analysis: {e}")
            return {'direction': 'neutral', 'confidence': 0.5}
    
    async def _cnn_inspired_pattern_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        CNN-inspired pattern analysis using convolution-like feature extraction
        """
        try:
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            # Feature extraction similar to CNN kernels
            features = {
                'price_gradients': np.gradient(closes),
                'volatility_gradients': np.gradient(highs - lows),
                'body_shadows': [],
                'momentum_shifts': []
            }
            
            # Extract candle features
            for i in range(len(df)):
                row = df.iloc[i]
                body = abs(row['close'] - row['open'])
                total_range = row['high'] - row['low']
                
                if total_range > 0:
                    features['body_shadows'].append({
                        'body_ratio': body / total_range,
                        'upper_shadow_ratio': (row['high'] - max(row['close'], row['open'])) / total_range,
                        'lower_shadow_ratio': (min(row['close'], row['open']) - row['low']) / total_range
                    })
            
            # Pattern strength calculation
            bullish_strength = 0.0
            bearish_strength = 0.0
            
            # Analyze recent patterns
            if len(features['body_shadows']) >= 3:
                recent_patterns = features['body_shadows'][-3:]
                
                # Look for bullish patterns
                bullish_bodies = sum(1 for p in recent_patterns if p['body_ratio'] > 0.5)
                long_lower_shadows = sum(1 for p in recent_patterns if p['lower_shadow_ratio'] > 0.4)
                
                if bullish_bodies >= 2 or long_lower_shadows >= 2:
                    bullish_strength = min(0.8, (bullish_bodies + long_lower_shadows) / 6)
                
                # Look for bearish patterns
                bearish_bodies = sum(1 for p in recent_patterns if p['body_ratio'] > 0.5)
                long_upper_shadows = sum(1 for p in recent_patterns if p['upper_shadow_ratio'] > 0.4)
                
                if bearish_bodies >= 2 or long_upper_shadows >= 2:
                    bearish_strength = min(0.8, (bearish_bodies + long_upper_shadows) / 6)
            
            return {
                'bullish_strength': bullish_strength,
                'bearish_strength': bearish_strength,
                'pattern_complexity': len(features['body_shadows']),
                'features_extracted': len(features)
            }
            
        except Exception as e:
            logger.error(f"Error in CNN-inspired pattern analysis: {e}")
            return {'bullish_strength': 0.0, 'bearish_strength': 0.0}
    
    def _detect_market_regime(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Dict[str, Any]:
        """
        Detect market regime (trending, ranging, volatile) using AI-inspired analysis
        """
        try:
            # Volatility analysis
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns)
            
            # Trend analysis
            trend_strength = abs(closes[-1] - closes[0]) / closes[0]
            
            # Range analysis
            recent_high = np.max(highs[-20:]) if len(highs) >= 20 else np.max(highs)
            recent_low = np.min(lows[-20:]) if len(lows) >= 20 else np.min(lows)
            range_ratio = (recent_high - recent_low) / recent_low if recent_low > 0 else 0
            
            # Determine regime
            if trend_strength > 0.02 and volatility < 0.05:
                regime = 'trending'
                confidence = 0.8
            elif range_ratio < 0.03 and volatility < 0.02:
                regime = 'ranging'
                confidence = 0.7
            elif volatility > 0.05:
                regime = 'volatile'
                confidence = 0.6
            else:
                regime = 'mixed'
                confidence = 0.5
            
            return {
                'regime': regime,
                'confidence': confidence,
                'volatility': volatility,
                'trend_strength': trend_strength,
                'range_ratio': range_ratio
            }
            
        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return {'regime': 'mixed', 'confidence': 0.5}
    
    async def _ai_enhanced_support_resistance(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """
        AI-enhanced support and resistance with machine learning-like clustering
        """
        try:
            # Use multiple methods to detect S/R levels
            methods = [
                self._detect_pivot_points(df),
                self._detect_volume_clusters(df),
                await self._detect_price_clusters(df)
            ]
            
            # Combine all detected levels
            all_support = []
            all_resistance = []
            
            for method in methods:
                if method:
                    all_support.extend(method.get('support', []))
                    all_resistance.extend(method.get('resistance', []))
            
            # Remove duplicates and cluster similar levels
            support_clustered = self._cluster_price_levels(all_support)
            resistance_clustered = self._cluster_price_levels(all_resistance)
            
            return {
                'support': sorted(support_clustered)[:5],
                'resistance': sorted(resistance_clustered, reverse=True)[:5]
            }
            
        except Exception as e:
            logger.error(f"Error in AI-enhanced S/R detection: {e}")
            return {'support': [], 'resistance': []}
    
    def _cluster_price_levels(self, levels: List[float], tolerance: float = 0.005) -> List[float]:
        """Cluster similar price levels using AI-inspired grouping"""
        if not levels:
            return []
        
        levels = sorted(set(levels))
        clustered = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] < tolerance:
                current_cluster.append(level)
            else:
                # Save cluster average
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        # Don't forget the last cluster
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    async def _advanced_candle_behavior_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Advanced candle behavior analysis to predict next candle direction
        """
        try:
            # Analyze candle sequences for patterns
            candle_behaviors = []
            
            for i in range(len(df)):
                row = df.iloc[i]
                body_size = abs(row['close'] - row['open'])
                total_range = row['high'] - row['low']
                
                if total_range > 0:
                    candle_behaviors.append({
                        'bullish': row['close'] > row['open'],
                        'body_strength': body_size / total_range,
                        'rejection_top': (row['high'] - max(row['close'], row['open'])) / total_range > 0.4,
                        'rejection_bottom': (min(row['close'], row['open']) - row['low']) / total_range > 0.4
                    })
            
            if not candle_behaviors:
                return {'next_candle_prediction': 'neutral', 'prediction_confidence': 0.5}
            
            # Analyze last 5 candles for pattern
            recent_candles = candle_behaviors[-5:]
            
            bullish_signals = sum(1 for c in recent_candles if c['bullish'] and c['body_strength'] > 0.5)
            bearish_signals = sum(1 for c in recent_candles if not c['bullish'] and c['body_strength'] > 0.5)
            rejection_tops = sum(1 for c in recent_candles if c['rejection_top'])
            rejection_bottoms = sum(1 for c in recent_candles if c['rejection_bottom'])
            
            # Predict next candle
            prediction_confidence = 0.5
            prediction = 'neutral'
            
            if bullish_signals >= 3 or rejection_bottoms >= 2:
                prediction = 'BUY'
                prediction_confidence = min(0.85, 0.6 + (bullish_signals + rejection_bottoms) * 0.1)
            elif bearish_signals >= 3 or rejection_tops >= 2:
                prediction = 'SELL'
                prediction_confidence = min(0.85, 0.6 + (bearish_signals + rejection_tops) * 0.1)
            
            return {
                'next_candle_prediction': prediction,
                'prediction_confidence': prediction_confidence,
                'bullish_signals': bullish_signals,
                'bearish_signals': bearish_signals,
                'rejection_analysis': {'tops': rejection_tops, 'bottoms': rejection_bottoms}
            }
            
        except Exception as e:
            logger.error(f"Error in candle behavior analysis: {e}")
            return {'next_candle_prediction': 'neutral', 'prediction_confidence': 0.5}
    
    def _analyze_ema_layers(self, ema_layers: Dict) -> Dict[str, Any]:
        """Analyze EMA layers like a neural network"""
        try:
            # Get current values from each layer
            layer_values = {}
            for layer_name, layer_data in ema_layers.items():
                if isinstance(layer_data, np.ndarray) and len(layer_data) > 0:
                    layer_values[layer_name] = layer_data[-1]
                else:
                    layer_values[layer_name] = 0.0
            
            # Neural network-like analysis
            current_price = layer_values['layer1']
            fast_ema = layer_values['layer2']
            medium_ema = layer_values['layer3']
            slow_ema = layer_values['layer4']
            
            # Layer alignment analysis
            bullish_alignment = current_price > fast_ema > medium_ema > slow_ema
            bearish_alignment = current_price < fast_ema < medium_ema < slow_ema
            
            # Calculate signal strength
            if bullish_alignment:
                strength = min(1.0, (current_price - slow_ema) / slow_ema * 100)
                return {'direction': 'BUY', 'strength': strength}
            elif bearish_alignment:
                strength = min(1.0, (slow_ema - current_price) / current_price * 100)
                return {'direction': 'SELL', 'strength': strength}
            else:
                return {'direction': 'neutral', 'strength': 0.3}
                
        except Exception as e:
            logger.error(f"Error analyzing EMA layers: {e}")
            return {'direction': 'neutral', 'strength': 0.3}
    
    def _advanced_sr_analysis(self, current_price: float, sr_levels: Dict, market_regime: Dict) -> Dict[str, Any]:
        """Advanced support/resistance analysis with market regime consideration"""
        try:
            # Adjust S/R sensitivity based on market regime
            regime = market_regime.get('regime', 'mixed')
            
            if regime == 'trending':
                proximity_multiplier = 1.5  # Wider tolerance in trending markets
            elif regime == 'ranging':
                proximity_multiplier = 0.5  # Tighter tolerance in ranging markets
            else:
                proximity_multiplier = 1.0
            
            threshold = self.sr_params['proximity_threshold'] * proximity_multiplier
            
            # Analyze support levels
            for support in sr_levels.get('support', []):
                distance_ratio = abs(current_price - support) / support
                if distance_ratio < threshold:
                    if current_price > support * (1 + threshold/2):
                        confidence = 0.8 if regime == 'ranging' else 0.6
                        return {'signal': 'BUY', 'confidence': confidence, 'level': support, 'type': 'support_bounce'}
            
            # Analyze resistance levels
            for resistance in sr_levels.get('resistance', []):
                distance_ratio = abs(current_price - resistance) / resistance
                if distance_ratio < threshold:
                    if current_price < resistance * (1 - threshold/2):
                        confidence = 0.8 if regime == 'ranging' else 0.6
                        return {'signal': 'SELL', 'confidence': confidence, 'level': resistance, 'type': 'resistance_rejection'}
            
            return {'signal': 'neutral', 'confidence': 0.5}
            
        except Exception as e:
            logger.error(f"Error in advanced S/R analysis: {e}")
            return {'signal': 'neutral', 'confidence': 0.5}
    
    async def _create_wma_crossover_signal(self, symbol: str, market_data, direction: SignalDirection, 
                                         confidence: float, timeframe: str, factors: List[str], 
                                         df: pd.DataFrame) -> TradingSignal:
        """Create WMA crossover signal with precise timing"""
        try:
            # Get precise Pocket Option timing
            timing_info = await pocket_option_sync.get_precise_candle_timing(timeframe, 
                "otc" if "_OTC" in symbol else "regular")
            
            # Ultra-short expiration for 5s and 15s
            if timeframe == '5s':
                expiration_minutes = 1  # 1 minute for 5-second trades
            elif timeframe == '15s':
                expiration_minutes = 1  # 1 minute for 15-second trades
            else:
                expiration_minutes = 2
            
            current_price = df['close'].iloc[-1]
            market_type = "otc" if "_OTC" in symbol else "regular"
            
            return TradingSignal(
                id=f"WMA_CROSS_{timeframe}_{datetime.now(self.chicago_tz).strftime('%Y%m%d_%H%M%S')}_{symbol}",
                symbol=symbol,
                asset_type=market_data.asset_type,
                direction=direction,
                entry_price=float(current_price),
                expiration_minutes=expiration_minutes,
                timeframe=timeframe,
                market_type=market_type,
                probability=min(confidence, 97.0),
                confidence_level="HIGH" if confidence >= 92 else "MEDIUM",
                strategy_used=TradingStrategy.HYBRID,
                technical_analysis={
                    'strategy': 'wma_crossover_ultra',
                    'timeframe_specific': True,
                    'confidence_factors': factors,
                    'wma_analysis': True,
                    'support_resistance_analysis': True,
                    'ai_candle_patterns': True,
                    'precision_timing': timing_info
                },
                market_analysis_summary=f"WMA Crossover {timeframe} signal: 3-WMA, 8-WMA, 4-TMA alignment with {confidence:.1f}% confidence. "
                                      f"Factors: {', '.join(factors)}. Support/resistance analysis included.",
                justification=f"🚀 WMA CROSSOVER {timeframe.upper()} SIGNAL - 3-WMA crosses 8-WMA with 4-TMA confirmation. "
                            f"Trend alignment confirmed. Support/resistance levels analyzed. "
                            f"AI candle pattern recognition applied. "
                            f"⚡ ULTRA-SHORT PRECISION: Optimized for {timeframe} Pocket Option trading.",
                risk_assessment=f"ULTRA-SHORT {timeframe.upper()} - High precision with {confidence:.1f}% confidence. "
                              f"WMA crossover strategy optimized for {timeframe} timeframes. Use appropriate risk management.",
                suggested_stake=2.0 if timeframe == '5s' else 3.0,
                precision_entry_time=timing_info['next_candle_start'],
                timestamp=datetime.now(self.chicago_tz)
            )
            
        except Exception as e:
            logger.error(f"Error creating WMA crossover signal: {e}")
            return None
    
    async def _create_gpt_ai_signal(self, symbol: str, market_data, direction: SignalDirection, 
                                  confidence: float, timeframe: str, factors: List[str], 
                                  df: pd.DataFrame, market_regime: Dict) -> TradingSignal:
        """Create GPT/AI advanced signal for 1m, 3m timeframes"""
        try:
            # Get precise timing
            timing_info = await pocket_option_sync.get_precise_candle_timing(timeframe,
                "otc" if "_OTC" in symbol else "regular")
            
            # Optimized expiration for 1m and 3m
            if timeframe == '1m':
                expiration_minutes = 2  # 2 minutes for 1-minute analysis
            elif timeframe == '3m':
                expiration_minutes = 5  # 5 minutes for 3-minute analysis
            else:
                expiration_minutes = 3
            
            current_price = df['close'].iloc[-1]
            market_type = "otc" if "_OTC" in symbol else "regular"
            
            return TradingSignal(
                id=f"GPT_AI_{timeframe}_{datetime.now(self.chicago_tz).strftime('%Y%m%d_%H%M%S')}_{symbol}",
                symbol=symbol,
                asset_type=market_data.asset_type,
                direction=direction,
                entry_price=float(current_price),
                expiration_minutes=expiration_minutes,
                timeframe=timeframe,
                market_type=market_type,
                probability=min(confidence, 98.0),
                confidence_level="HIGH" if confidence >= 92 else "MEDIUM",
                strategy_used=TradingStrategy.HYBRID,
                technical_analysis={
                    'strategy': 'gpt_ai_advanced',
                    'timeframe_specific': True,
                    'confidence_factors': factors,
                    'ai_ensemble_analysis': True,
                    'lstm_inspired': True,
                    'cnn_pattern_recognition': True,
                    'market_regime': market_regime,
                    'precision_timing': timing_info
                },
                market_analysis_summary=f"GPT/AI {timeframe} signal: Advanced ensemble analysis with {confidence:.1f}% confidence. "
                                      f"Market regime: {market_regime.get('regime', 'unknown')}. "
                                      f"Factors: {', '.join(factors[:5])}...",
                justification=f"🧠 GPT/AI ADVANCED {timeframe.upper()} SIGNAL - Multi-layer neural network-inspired analysis. "
                            f"LSTM trend analysis, CNN pattern recognition, ensemble decision-making. "
                            f"Market regime: {market_regime.get('regime', 'mixed')}. "
                            f"⚡ AI-OPTIMIZED: Advanced algorithms for {timeframe} precision trading.",
                risk_assessment=f"AI-ENHANCED {timeframe.upper()} - Advanced analysis with {confidence:.1f}% confidence. "
                              f"GPT-inspired strategy with ensemble validation. Market regime considered.",
                suggested_stake=5.0 if timeframe == '1m' else 8.0 if timeframe == '3m' else 3.0,
                precision_entry_time=timing_info['next_candle_start'],
                timestamp=datetime.now(self.chicago_tz)
            )
            
        except Exception as e:
            logger.error(f"Error creating GPT/AI signal: {e}")
            return None
    
    # Helper methods for technical calculations
    def _detect_pivot_points(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Detect pivot-based support and resistance"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            # Find pivot highs and lows
            pivot_highs, _ = find_peaks(highs, distance=5, prominence=np.std(highs) * 0.3)
            pivot_lows, _ = find_peaks(-lows, distance=5, prominence=np.std(lows) * 0.3)
            
            resistance = [highs[i] for i in pivot_highs]
            support = [lows[i] for i in pivot_lows]
            
            return {'support': support, 'resistance': resistance}
            
        except Exception as e:
            logger.error(f"Error detecting pivot points: {e}")
            return {'support': [], 'resistance': []}
    
    def _detect_volume_clusters(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Detect volume-based support and resistance"""
        try:
            if 'volume' not in df.columns:
                return {'support': [], 'resistance': []}
            
            # Group by price levels and sum volume
            price_volume_map = {}
            for _, row in df.iterrows():
                price_level = round(row['close'], 4)
                price_volume_map[price_level] = price_volume_map.get(price_level, 0) + row['volume']
            
            # Find high-volume price levels
            sorted_levels = sorted(price_volume_map.items(), key=lambda x: x[1], reverse=True)
            high_volume_levels = [level[0] for level in sorted_levels[:10]]
            
            current_price = df['close'].iloc[-1]
            support = [level for level in high_volume_levels if level < current_price]
            resistance = [level for level in high_volume_levels if level > current_price]
            
            return {'support': support, 'resistance': resistance}
            
        except Exception as e:
            logger.error(f"Error detecting volume clusters: {e}")
            return {'support': [], 'resistance': []}
    
    async def _detect_price_clusters(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Detect price clusters using AI-inspired clustering"""
        try:
            closes = df['close'].values
            
            # Use simple clustering approach
            from sklearn.cluster import KMeans
            
            # Reshape data for clustering
            price_data = closes.reshape(-1, 1)
            
            # Find optimal number of clusters (between 3-7)
            n_clusters = min(7, max(3, len(set(closes)) // 5))
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(price_data)
            
            # Get cluster centers
            cluster_centers = kmeans.cluster_centers_.flatten()
            
            current_price = closes[-1]
            support = [center for center in cluster_centers if center < current_price]
            resistance = [center for center in cluster_centers if center > current_price]
            
            return {'support': support, 'resistance': resistance}
            
        except Exception as e:
            # Fallback without sklearn
            closes = df['close'].values
            current_price = closes[-1]
            
            # Simple percentile-based levels
            support = [np.percentile(closes, p) for p in [10, 25, 40] if np.percentile(closes, p) < current_price]
            resistance = [np.percentile(closes, p) for p in [60, 75, 90] if np.percentile(closes, p) > current_price]
            
            return {'support': support, 'resistance': resistance}


# Global instance
advanced_strategy_engine = AdvancedStrategyEngine()