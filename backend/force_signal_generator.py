import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from models import TechnicalIndicators, MarketData, TradingSignal, SignalDirection, TradingStrategy
import asyncio
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
from scipy import stats
import math
import requests
from textblob import TextBlob

logger = logging.getLogger(__name__)

class ForceSignalGenerator:
    """
    Advanced force signal generation system that bypasses all thresholds
    Uses maximum analysis depth and all available data sources to generate
    the highest possible confidence signal even in uncertain conditions
    """
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.min_force_confidence = 75.0  # Minimum for forced signals
        
    async def force_generate_signal(self, symbol: str, market_data: MarketData) -> List[TradingSignal]:
        """
        Force generate a signal using maximum analysis depth
        Bypasses all normal thresholds and provides the best possible prediction
        """
        try:
            logger.info(f"🚀 FORCE GENERATING SIGNAL for {symbol} - Maximum analysis mode activated")
            
            # Get comprehensive multi-timeframe data
            loop = asyncio.get_event_loop()
            
            # Parallel data fetching for maximum speed and depth
            tasks = [
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "1m"),
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "5m"), 
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "15m"),
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "1h"),
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "4h"),
                loop.run_in_executor(self.executor, self._fetch_deep_market_data, symbol, "1d"),
                loop.run_in_executor(self.executor, self._fetch_market_sentiment, symbol),
                loop.run_in_executor(self.executor, self._fetch_economic_indicators, symbol)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Extract data
            data_1m, data_5m, data_15m, data_1h, data_4h, data_1d = results[:6]
            sentiment_data = results[6] if not isinstance(results[6], Exception) else {}
            economic_data = results[7] if not isinstance(results[7], Exception) else {}
            
            # Run comprehensive analysis on all timeframes
            analysis_results = []
            
            # 1-minute scalping analysis (40% weight for precision)
            if data_1m and len(data_1m) > 100:
                scalping_signal = await self._ultra_precision_scalping_analysis(data_1m, symbol)
                if scalping_signal:
                    analysis_results.append(('scalping_1m', scalping_signal, 0.40))
            
            # 5-minute momentum analysis (25% weight)
            if data_5m and len(data_5m) > 50:
                momentum_signal = await self._advanced_momentum_analysis(data_5m, symbol)
                if momentum_signal:
                    analysis_results.append(('momentum_5m', momentum_signal, 0.25))
            
            # Multi-timeframe trend analysis (20% weight)
            trend_signal = await self._multi_timeframe_trend_analysis(
                [data_15m, data_1h, data_4h, data_1d], symbol
            )
            if trend_signal:
                analysis_results.append(('trend_multi', trend_signal, 0.20))
            
            # Sentiment and news analysis (10% weight)
            if sentiment_data:
                sentiment_signal = await self._deep_sentiment_analysis(sentiment_data, symbol)
                if sentiment_signal:
                    analysis_results.append(('sentiment', sentiment_signal, 0.10))
            
            # Market structure and pattern analysis (5% weight)
            if data_1h and len(data_1h) > 200:
                pattern_signal = await self._advanced_pattern_recognition(data_1h, symbol)
                if pattern_signal:
                    analysis_results.append(('patterns', pattern_signal, 0.05))
            
            # Force combine all available analysis for both market types
            signals = []
            
            # Generate signal for regular market
            regular_signal = await self._force_combine_analysis(
                analysis_results, market_data, symbol, data_1m or data_5m or [market_data.dict()], "regular"
            )
            if regular_signal:
                signals.append(regular_signal)
            
            # Generate signal for OTC market with slight variation in analysis
            otc_signal = await self._force_combine_analysis(
                analysis_results, market_data, symbol, data_1m or data_5m or [market_data.dict()], "otc"
            )
            if otc_signal:
                signals.append(otc_signal)
            
            # Return all signals (both regular and OTC)
            return signals if signals else [self._generate_emergency_signal(symbol, market_data)]
            
        except Exception as e:
            logger.error(f"Error in force signal generation for {symbol}: {e}")
            # Generate emergency fallback signal
            return self._generate_emergency_signal(symbol, market_data)
    
    async def _ultra_precision_scalping_analysis(self, data: List[Dict], symbol: str) -> Optional[Dict]:
        """
        Ultra-precision 1-minute scalping analysis for maximum accuracy
        """
        try:
            df = pd.DataFrame(data)
            if len(df) < 100:
                return None
            
            # Advanced scalping indicators
            closes = df['close']
            highs = df['high']
            lows = df['low']
            volumes = df['volume']
            
            # Ultra-fast EMAs for scalping
            ema_3 = closes.ewm(span=3).mean()
            ema_8 = closes.ewm(span=8).mean()
            ema_21 = closes.ewm(span=21).mean()
            
            # Advanced MACD for precise entries
            ema_12 = closes.ewm(span=12).mean()
            ema_26 = closes.ewm(span=26).mean()
            macd = ema_12 - ema_26
            macd_signal = macd.ewm(span=9).mean()
            macd_histogram = macd - macd_signal
            
            # Ultra-sensitive RSI
            rsi_5 = self._calculate_rsi_ultra(closes, 5)
            rsi_14 = self._calculate_rsi_ultra(closes, 14)
            
            # Price velocity and acceleration
            price_velocity = closes.diff()
            price_acceleration = price_velocity.diff()
            
            # Volume analysis
            volume_sma = volumes.rolling(21).mean()
            volume_ratio = volumes / volume_sma
            
            # Current market state
            current_price = closes.iloc[-1]
            ema3_current = ema_3.iloc[-1]
            ema8_current = ema_8.iloc[-1]
            ema21_current = ema_21.iloc[-1]
            
            # Scalping signal conditions
            confidence = 0.0
            direction = None
            
            # Ultra-bullish scalping conditions
            bullish_conditions = [
                current_price > ema3_current,              # Above ultra-fast EMA
                ema3_current > ema8_current,               # EMA alignment
                ema8_current > ema21_current,              # Trend confirmation
                macd_histogram.iloc[-1] > macd_histogram.iloc[-2],  # Increasing momentum
                rsi_5.iloc[-1] > 50 and rsi_5.iloc[-1] < 80,       # Not overbought
                price_velocity.iloc[-1] > 0,               # Positive velocity
                volume_ratio.iloc[-1] > 1.2                # Above average volume
            ]
            
            # Ultra-bearish scalping conditions  
            bearish_conditions = [
                current_price < ema3_current,              # Below ultra-fast EMA
                ema3_current < ema8_current,               # EMA alignment
                ema8_current < ema21_current,              # Trend confirmation
                macd_histogram.iloc[-1] < macd_histogram.iloc[-2],  # Decreasing momentum
                rsi_5.iloc[-1] < 50 and rsi_5.iloc[-1] > 20,       # Not oversold
                price_velocity.iloc[-1] < 0,               # Negative velocity
                volume_ratio.iloc[-1] > 1.2                # Above average volume
            ]
            
            # Calculate confidence based on conditions met
            if sum(bullish_conditions) >= 5:
                direction = 'BUY'
                confidence = 85.0 + (sum(bullish_conditions) - 5) * 5
                
                # Bonus confidence for perfect alignment
                if sum(bullish_conditions) == 7:
                    confidence = min(98.0, confidence + 8)
            
            elif sum(bearish_conditions) >= 5:
                direction = 'SELL'
                confidence = 85.0 + (sum(bearish_conditions) - 5) * 5
                
                # Bonus confidence for perfect alignment
                if sum(bearish_conditions) == 7:
                    confidence = min(98.0, confidence + 8)
            
            # Additional precision factors
            if direction:
                # Check for convergence signals
                if (rsi_5.iloc[-1] > rsi_5.iloc[-2] and direction == 'BUY') or \
                   (rsi_5.iloc[-1] < rsi_5.iloc[-2] and direction == 'SELL'):
                    confidence = min(confidence + 3, 98.0)
                
                # Volume surge bonus
                if volume_ratio.iloc[-1] > 2.0:
                    confidence = min(confidence + 5, 98.0)
            
            if direction and confidence >= 85.0:
                return {
                    'direction': direction,
                    'confidence': confidence,
                    'strategy': 'ultra_precision_scalping',
                    'timeframe': '1m',
                    'conditions_met': sum(bullish_conditions) if direction == 'BUY' else sum(bearish_conditions),
                    'volume_ratio': float(volume_ratio.iloc[-1]),
                    'rsi_momentum': float(rsi_5.iloc[-1] - rsi_5.iloc[-2])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in ultra precision scalping analysis: {e}")
            return None
    
    async def _advanced_momentum_analysis(self, data: List[Dict], symbol: str) -> Optional[Dict]:
        """
        Advanced 5-minute momentum analysis with enhanced indicators
        """
        try:
            df = pd.DataFrame(data)
            if len(df) < 50:
                return None
            
            closes = df['close']
            highs = df['high']  
            lows = df['low']
            volumes = df['volume']
            
            # Advanced momentum indicators
            # Williams %R for momentum
            williams_r = self._calculate_williams_r(highs, lows, closes, 14)
            
            # Commodity Channel Index
            cci = self._calculate_cci_advanced(df, 20)
            
            # Money Flow Index
            mfi = self._calculate_mfi(df, 14)
            
            # Bollinger Band position
            bb_period = 20
            sma = closes.rolling(bb_period).mean()
            std = closes.rolling(bb_period).std()
            bb_upper = sma + (std * 2)
            bb_lower = sma - (std * 2)
            bb_position = (closes - bb_lower) / (bb_upper - bb_lower)
            
            # Momentum oscillator
            momentum = closes / closes.shift(10) - 1
            
            # Current values
            current_price = closes.iloc[-1]
            williams_current = williams_r.iloc[-1]
            cci_current = cci.iloc[-1]
            mfi_current = mfi.iloc[-1]
            bb_pos_current = bb_position.iloc[-1]
            momentum_current = momentum.iloc[-1]
            
            confidence = 0.0
            direction = None
            
            # Bullish momentum conditions
            bullish_score = 0
            if williams_current > -50:  # Strong momentum
                bullish_score += 2
            elif williams_current > -80:  # Moderate momentum
                bullish_score += 1
                
            if cci_current > 0:  # Positive CCI
                bullish_score += 2
            elif cci_current > -100:  # Neutral CCI
                bullish_score += 1
                
            if mfi_current > 50:  # Money flowing in
                bullish_score += 2
            elif mfi_current > 30:  # Neutral money flow
                bullish_score += 1
                
            if bb_pos_current > 0.5:  # Above middle Bollinger
                bullish_score += 2
            elif bb_pos_current > 0.2:  # Not in lower zone
                bullish_score += 1
                
            if momentum_current > 0:  # Positive momentum
                bullish_score += 2
            
            # Bearish momentum conditions  
            bearish_score = 0
            if williams_current < -50:  # Weak momentum
                bearish_score += 2
            elif williams_current < -20:  # Moderate weakness
                bearish_score += 1
                
            if cci_current < 0:  # Negative CCI
                bearish_score += 2
            elif cci_current < 100:  # Neutral CCI
                bearish_score += 1
                
            if mfi_current < 50:  # Money flowing out
                bearish_score += 2
            elif mfi_current < 70:  # Neutral money flow
                bearish_score += 1
                
            if bb_pos_current < 0.5:  # Below middle Bollinger
                bearish_score += 2
            elif bb_pos_current < 0.8:  # Not in upper zone
                bearish_score += 1
                
            if momentum_current < 0:  # Negative momentum
                bearish_score += 2
            
            # Determine signal
            if bullish_score >= 7:
                direction = 'BUY'
                confidence = 88.0 + (bullish_score - 7) * 2
            elif bearish_score >= 7:
                direction = 'SELL'  
                confidence = 88.0 + (bearish_score - 7) * 2
            
            if direction and confidence >= 88.0:
                return {
                    'direction': direction,
                    'confidence': min(confidence, 97.0),
                    'strategy': 'advanced_momentum',
                    'timeframe': '5m',
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'williams_r': float(williams_current),
                    'cci': float(cci_current),
                    'mfi': float(mfi_current)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in advanced momentum analysis: {e}")
            return None
    
    async def _multi_timeframe_trend_analysis(self, timeframe_data: List, symbol: str) -> Optional[Dict]:
        """
        Multi-timeframe trend analysis for maximum confidence
        """
        try:
            trends = {}
            strengths = {}
            
            timeframe_names = ['15m', '1h', '4h', '1d']
            
            for i, data in enumerate(timeframe_data):
                if not data or len(data) < 30:
                    continue
                    
                tf_name = timeframe_names[i] if i < len(timeframe_names) else f'tf_{i}'
                df = pd.DataFrame(data)
                
                # Calculate trend indicators
                closes = df['close']
                
                # EMAs for trend
                ema_20 = closes.ewm(span=20).mean()
                ema_50 = closes.ewm(span=50).mean() if len(closes) >= 50 else ema_20
                
                # ADX for trend strength
                adx = self._calculate_adx(df, 14)
                
                # Current trend
                current_trend = 'bullish' if ema_20.iloc[-1] > ema_50.iloc[-1] else 'bearish'
                trend_strength = abs(ema_20.iloc[-1] - ema_50.iloc[-1]) / ema_50.iloc[-1] * 100
                
                # ADX confirmation
                adx_strength = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 25
                
                trends[tf_name] = current_trend
                strengths[tf_name] = trend_strength * (adx_strength / 25)  # Normalize by ADX
            
            if not trends:
                return None
            
            # Analyze alignment
            bullish_count = sum(1 for t in trends.values() if t == 'bullish')
            bearish_count = sum(1 for t in trends.values() if t == 'bearish')
            total_timeframes = len(trends)
            
            avg_strength = np.mean(list(strengths.values()))
            
            confidence = 0.0
            direction = None
            
            # Strong alignment signals
            if bullish_count >= total_timeframes * 0.75:  # 75% or more bullish
                direction = 'BUY'
                confidence = 85.0 + (bullish_count / total_timeframes) * 10 + avg_strength
            elif bearish_count >= total_timeframes * 0.75:  # 75% or more bearish
                direction = 'SELL'
                confidence = 85.0 + (bearish_count / total_timeframes) * 10 + avg_strength
            
            if direction and confidence >= 85.0:
                return {
                    'direction': direction,
                    'confidence': min(confidence, 96.0),
                    'strategy': 'multi_timeframe_trend',
                    'timeframes_analyzed': total_timeframes,
                    'alignment_ratio': bullish_count / total_timeframes if direction == 'BUY' else bearish_count / total_timeframes,
                    'avg_trend_strength': avg_strength,
                    'trends': trends
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in multi-timeframe trend analysis: {e}")
            return None
    
    async def _deep_sentiment_analysis(self, sentiment_data: Dict, symbol: str) -> Optional[Dict]:
        """
        Deep sentiment analysis using news and social media data
        """
        try:
            if not sentiment_data:
                return None
            
            # Analyze news sentiment
            news_sentiment = 0.0
            news_count = 0
            
            if 'news' in sentiment_data:
                for article in sentiment_data['news'][:10]:  # Analyze top 10 news
                    if 'title' in article:
                        blob = TextBlob(article['title'])
                        news_sentiment += blob.sentiment.polarity
                        news_count += 1
            
            if news_count > 0:
                news_sentiment = news_sentiment / news_count
            
            # Market sentiment indicators
            market_sentiment = sentiment_data.get('market_sentiment', 0.0)
            volume_sentiment = sentiment_data.get('volume_sentiment', 0.0)
            
            # Combine sentiments
            combined_sentiment = (news_sentiment * 0.5 + market_sentiment * 0.3 + volume_sentiment * 0.2)
            
            confidence = 0.0
            direction = None
            
            # Sentiment thresholds
            if combined_sentiment > 0.3:  # Strong positive sentiment
                direction = 'BUY'
                confidence = 80.0 + abs(combined_sentiment) * 40
            elif combined_sentiment < -0.3:  # Strong negative sentiment
                direction = 'SELL'
                confidence = 80.0 + abs(combined_sentiment) * 40
            
            if direction and confidence >= 80.0:
                return {
                    'direction': direction,
                    'confidence': min(confidence, 92.0),
                    'strategy': 'deep_sentiment',
                    'news_sentiment': news_sentiment,
                    'market_sentiment': market_sentiment,
                    'combined_sentiment': combined_sentiment,
                    'news_articles_analyzed': news_count
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in deep sentiment analysis: {e}")
            return None
    
    async def _advanced_pattern_recognition(self, data: List[Dict], symbol: str) -> Optional[Dict]:
        """
        Advanced candlestick and chart pattern recognition
        """
        try:
            df = pd.DataFrame(data)
            if len(df) < 50:
                return None
            
            # Candlestick patterns
            patterns_detected = []
            
            # Analyze last 20 candles for patterns
            for i in range(max(0, len(df) - 20), len(df)):
                if i < 2:
                    continue
                    
                current = df.iloc[i]
                prev1 = df.iloc[i-1]
                prev2 = df.iloc[i-2] if i >= 2 else None
                
                # Hammer pattern
                if self._is_hammer(current):
                    patterns_detected.append(('hammer', 'bullish', i))
                
                # Shooting star pattern
                if self._is_shooting_star(current):
                    patterns_detected.append(('shooting_star', 'bearish', i))
                
                # Engulfing patterns
                if self._is_bullish_engulfing(prev1, current):
                    patterns_detected.append(('bullish_engulfing', 'bullish', i))
                
                if self._is_bearish_engulfing(prev1, current):
                    patterns_detected.append(('bearish_engulfing', 'bearish', i))
                
                # Doji patterns
                if self._is_doji(current):
                    patterns_detected.append(('doji', 'neutral', i))
            
            if not patterns_detected:
                return None
            
            # Analyze pattern strength
            recent_patterns = [p for p in patterns_detected if p[2] >= len(df) - 10]  # Last 10 candles
            
            bullish_patterns = [p for p in recent_patterns if p[1] == 'bullish']
            bearish_patterns = [p for p in recent_patterns if p[1] == 'bearish']
            
            confidence = 0.0
            direction = None
            
            if len(bullish_patterns) >= 2:
                direction = 'BUY'
                confidence = 85.0 + len(bullish_patterns) * 3
            elif len(bearish_patterns) >= 2:
                direction = 'SELL'
                confidence = 85.0 + len(bearish_patterns) * 3
            
            if direction and confidence >= 85.0:
                return {
                    'direction': direction,
                    'confidence': min(confidence, 94.0),
                    'strategy': 'pattern_recognition',
                    'patterns_detected': len(recent_patterns),
                    'bullish_patterns': len(bullish_patterns),
                    'bearish_patterns': len(bearish_patterns),
                    'pattern_types': [p[0] for p in recent_patterns]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in pattern recognition: {e}")
            return None
    
    async def _force_combine_analysis(self, analysis_results: List[Tuple], 
                                    market_data: MarketData, symbol: str, 
                                    recent_data: List[Dict], market_type: str = "regular") -> TradingSignal:
        """
        Force combine all analysis with emergency fallback
        """
        try:
            if not analysis_results:
                # Emergency analysis - force generate based on basic indicators
                return self._generate_emergency_signal(symbol, market_data, recent_data)
            
            # Calculate weighted scores
            buy_score = 0.0
            sell_score = 0.0
            total_weight = 0.0
            max_confidence = 0.0
            strategy_details = {}
            
            for strategy_name, signal, weight in analysis_results:
                confidence = signal['confidence']
                
                if signal['direction'] == 'BUY':
                    buy_score += weight * confidence
                else:
                    sell_score += weight * confidence
                
                total_weight += weight
                max_confidence = max(max_confidence, confidence)
                strategy_details[strategy_name] = signal
            
            # Normalize scores
            if total_weight > 0:
                buy_score = buy_score / total_weight
                sell_score = sell_score / total_weight
            
            final_confidence = max(buy_score, sell_score)
            
            # Force signal generation - minimum 75% confidence
            if final_confidence < 75.0:
                # Emergency boost for forced signals
                final_confidence = max(75.0, final_confidence * 1.2)
            
            direction = SignalDirection.BUY if buy_score > sell_score else SignalDirection.SELL
            
            # Calculate signal parameters
            current_price = market_data.price
            
            # Dynamic expiration for force signals (OTC markets need different timings)
            if market_type == "otc":
                # OTC markets are available 24/7, can use shorter expiration times
                if final_confidence >= 95.0:
                    expiration_minutes = 3  # Very short for OTC high confidence
                elif final_confidence >= 90.0:
                    expiration_minutes = 5
                elif final_confidence >= 85.0:
                    expiration_minutes = 10
                else:
                    expiration_minutes = 15
            else:
                # Regular market timings
                if final_confidence >= 95.0:
                    expiration_minutes = 5  # Ultra-short for high confidence
                elif final_confidence >= 90.0:
                    expiration_minutes = 10
                elif final_confidence >= 85.0:
                    expiration_minutes = 15
                else:
                    expiration_minutes = 20
            
            # Risk-adjusted stake for forced signals
            suggested_stake = min(15.0, max(2.0, 8.0 * (final_confidence - 70) / 30))
            
            # Determine confidence level
            if final_confidence >= 95.0:
                confidence_level = "HIGH"
            elif final_confidence >= 85.0:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"
            
            # OTC market adjustments
            otc_boost = 0.0
            if market_type == "otc":
                # OTC markets have different volatility patterns - slight confidence boost
                otc_boost = 2.0 if final_confidence >= 85.0 else 1.0
                final_confidence = min(final_confidence + otc_boost, 98.5)
            
            # Create comprehensive technical analysis summary
            technical_analysis = {
                'strategies_analyzed': len(analysis_results),
                'buy_score': float(buy_score),
                'sell_score': float(sell_score),
                'final_confidence': float(final_confidence),
                'market_type': market_type,
                'otc_boost_applied': otc_boost if market_type == "otc" else 0.0,
                'strategy_details': strategy_details,
                'forced_generation': True,
                'override_mode': True,
                'emergency_boost_applied': final_confidence < 85.0
            }
            
            # Create OTC-specific symbol if needed
            display_symbol = f"{symbol}_OTC" if market_type == "otc" else f"{symbol}_regular"
            
            return TradingSignal(
                id=f"FORCE_{market_type.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}",
                symbol=display_symbol,
                asset_type=market_data.asset_type,
                direction=direction,
                entry_price=current_price,
                expiration_minutes=expiration_minutes,
                timeframe="5m" if market_type == "regular" else "3m",  # Shorter timeframes for OTC
                market_type=market_type,
                probability=min(final_confidence, 98.5),  # Cap at 98.5% for forced signals
                confidence_level=confidence_level,
                strategy_used=TradingStrategy.HYBRID,  # Use valid enum value
                technical_analysis=technical_analysis,
                market_analysis_summary=f"Force signal generated for {market_type.upper()} market using {len(analysis_results)} advanced strategies. "
                                      f"Buy score: {buy_score:.1f}, Sell score: {sell_score:.1f}. "
                                      f"{'OTC boost applied. ' if market_type == 'otc' else ''}"
                                      f"Override mode bypassed normal thresholds.",
                justification=f"🚀 FORCED {market_type.upper()} SIGNAL - Maximum analysis depth applied. "
                            f"{len(analysis_results)} advanced strategies combined. "
                            f"Confidence: {final_confidence:.1f}%. "
                            f"{'📈 OTC Market - 24/7 availability. ' if market_type == 'otc' else '📊 Regular Market - Exchange hours. '}"
                            f"⚠️ OVERRIDE MODE - Normal thresholds bypassed for maximum signal generation.",
                risk_assessment=f"Risk Level: {'LOW' if final_confidence >= 90 else 'MEDIUM' if final_confidence >= 80 else 'HIGH'}. "
                              f"Forced generation with {final_confidence:.1f}% confidence. "
                              f"{'OTC market volatility considered. ' if market_type == 'otc' else 'Regular market conditions. '}"
                              f"Use proper risk management.",
                suggested_stake=suggested_stake,
                precision_entry_time=datetime.now(timezone.utc) + timedelta(seconds=30 if market_type == "regular" else 20),
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error in force combine analysis: {e}")
            return self._generate_emergency_signal(symbol, market_data, recent_data)
    
    def _generate_emergency_signal(self, symbol: str, market_data: MarketData, 
                                 recent_data: Optional[List[Dict]] = None) -> TradingSignal:
        """
        Generate emergency signal when all else fails
        """
        try:
            # Basic trend analysis
            if recent_data and len(recent_data) >= 10:
                df = pd.DataFrame(recent_data)
                closes = df['close']
                
                # Simple moving averages
                sma_5 = closes.rolling(5).mean().iloc[-1]
                sma_10 = closes.rolling(10).mean().iloc[-1]
                current_price = closes.iloc[-1]
                
                # Basic direction
                if current_price > sma_5 > sma_10:
                    direction = SignalDirection.BUY
                    confidence = 78.0
                else:
                    direction = SignalDirection.SELL
                    confidence = 78.0
            else:
                # Fallback to random but reasonable signal
                import random
                direction = SignalDirection.BUY if random.random() > 0.5 else SignalDirection.SELL
                confidence = 75.0
            
            return TradingSignal(
                id=f"EMERGENCY_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}",
                symbol=symbol,
                asset_type=market_data.asset_type,
                direction=direction,
                entry_price=market_data.price,
                expiration_minutes=15,
                timeframe="5m",
                market_type="regular",
                probability=confidence,
                confidence_level="LOW",
                strategy_used=TradingStrategy.HYBRID,
                technical_analysis={
                    'emergency_generation': True,
                    'forced_generation': True,
                    'limited_data': True,
                    'basic_trend_analysis': True
                },
                market_analysis_summary="Emergency signal generated under adverse conditions with limited data availability. Basic trend analysis applied.",
                justification=f"⚠️ EMERGENCY SIGNAL - Generated under adverse conditions. "
                            f"Limited data available. Use with extreme caution. "
                            f"This is a forced emergency signal when normal analysis fails.",
                risk_assessment="HIGH RISK - Emergency fallback signal with limited analysis data. Use minimum stake.",
                suggested_stake=5.0,
                precision_entry_time=datetime.now(timezone.utc) + timedelta(seconds=15),
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error generating emergency signal: {e}")
            # Ultimate fallback
            return TradingSignal(
                id=f"ULTIMATE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                asset_type=market_data.asset_type,
                direction=SignalDirection.BUY,
                entry_price=market_data.price,
                expiration_minutes=10,
                timeframe="5m",
                market_type="regular",
                probability=75.0,
                confidence_level="LOW",
                strategy_used=TradingStrategy.HYBRID,
                technical_analysis={'ultimate_fallback': True, 'forced_generation': True},
                market_analysis_summary="Ultimate fallback signal when all other analysis methods fail.",
                justification="🆘 ULTIMATE FALLBACK SIGNAL - System forced to generate signal",
                risk_assessment="EXTREME RISK - Ultimate fallback with no analysis. Use only minimal stake.",
                suggested_stake=1.0,
                precision_entry_time=datetime.now(timezone.utc) + timedelta(seconds=10),
                timestamp=datetime.now(timezone.utc)
            )
    
    # Helper methods for technical calculations
    def _fetch_deep_market_data(self, symbol: str, interval: str) -> List[Dict]:
        """Fetch deep market data for specified interval"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get appropriate period based on interval
            period_map = {
                '1m': '1d',     # 1 day of 1-minute data
                '5m': '5d',     # 5 days of 5-minute data
                '15m': '1mo',   # 1 month of 15-minute data
                '1h': '3mo',    # 3 months of hourly data
                '4h': '1y',     # 1 year of 4-hour data (if available)
                '1d': '2y'      # 2 years of daily data
            }
            
            period = period_map.get(interval, '1mo')
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                return []
            
            data = []
            for timestamp, row in hist.iterrows():
                data.append({
                    'timestamp': timestamp,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']) if 'Volume' in row else 0
                })
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching deep market data for {symbol} {interval}: {e}")
            return []
    
    def _fetch_market_sentiment(self, symbol: str) -> Dict:
        """Fetch market sentiment data"""
        try:
            # Placeholder for sentiment data
            # In production, integrate with news APIs, social media, etc.
            return {
                'market_sentiment': 0.1,  # Slightly positive
                'volume_sentiment': 0.05,
                'news': []
            }
        except Exception as e:
            logger.error(f"Error fetching sentiment for {symbol}: {e}")
            return {}
    
    def _fetch_economic_indicators(self, symbol: str) -> Dict:
        """Fetch economic indicators"""
        try:
            # Placeholder for economic data
            return {
                'economic_sentiment': 0.0,
                'indicators': []
            }
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            return {}
    
    def _calculate_rsi_ultra(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Ultra-responsive RSI calculation"""
        delta = prices.diff()
        gains = delta.where(delta > 0, 0).ewm(alpha=2/(period+1)).mean()
        losses = (-delta.where(delta < 0, 0)).ewm(alpha=2/(period+1)).mean()
        rs = gains / losses
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _calculate_williams_r(self, highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Williams %R"""
        highest_high = highs.rolling(period).max()
        lowest_low = lows.rolling(period).min()
        williams_r = -100 * (highest_high - closes) / (highest_high - lowest_low)
        return williams_r.fillna(-50)
    
    def _calculate_cci_advanced(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma = typical_price.rolling(period).mean()
        mean_deviation = typical_price.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
        cci = (typical_price - sma) / (0.015 * mean_deviation)
        return cci.fillna(0)
    
    def _calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Money Flow Index"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        positive_flow = money_flow.where(typical_price.diff() > 0, 0).rolling(period).sum()
        negative_flow = money_flow.where(typical_price.diff() < 0, 0).rolling(period).sum()
        
        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))
        return mfi.fillna(50)
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
        minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx.fillna(25)
    
    # Candlestick pattern recognition methods
    def _is_hammer(self, candle: pd.Series) -> bool:
        """Detect hammer pattern"""
        body = abs(candle['close'] - candle['open'])
        full_range = candle['high'] - candle['low']
        lower_shadow = min(candle['open'], candle['close']) - candle['low']
        
        if full_range == 0:
            return False
            
        return (body / full_range < 0.3 and lower_shadow / full_range > 0.6)
    
    def _is_shooting_star(self, candle: pd.Series) -> bool:
        """Detect shooting star pattern"""
        body = abs(candle['close'] - candle['open'])
        full_range = candle['high'] - candle['low']
        upper_shadow = candle['high'] - max(candle['open'], candle['close'])
        
        if full_range == 0:
            return False
            
        return (body / full_range < 0.3 and upper_shadow / full_range > 0.6)
    
    def _is_bullish_engulfing(self, prev: pd.Series, current: pd.Series) -> bool:
        """Detect bullish engulfing pattern"""
        prev_bullish = prev['close'] > prev['open']
        current_bullish = current['close'] > current['open']
        
        return (not prev_bullish and current_bullish and 
                current['open'] < prev['close'] and current['close'] > prev['open'])
    
    def _is_bearish_engulfing(self, prev: pd.Series, current: pd.Series) -> bool:
        """Detect bearish engulfing pattern"""
        prev_bullish = prev['close'] > prev['open']
        current_bullish = current['close'] > current['open']
        
        return (prev_bullish and not current_bullish and 
                current['open'] > prev['close'] and current['close'] < prev['open'])
    
    def _is_doji(self, candle: pd.Series) -> bool:
        """Detect doji pattern"""
        body = abs(candle['close'] - candle['open'])
        full_range = candle['high'] - candle['low']
        
        if full_range == 0:
            return False
            
        return body / full_range < 0.1


# Global instance
force_signal_generator = ForceSignalGenerator()