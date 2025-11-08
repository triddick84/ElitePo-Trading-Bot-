import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import asyncio
import pytz
import logging
from models import TradingSignal, SignalDirection, TradingStrategy
from pocket_option_timing_sync import pocket_option_sync

logger = logging.getLogger(__name__)

class UltraShortPrecisionEngine:
    """
    Ultra-short timeframe precision engine for 5s, 15s, 30s binary options
    Implements high-accuracy algorithms for Pocket Option platform synchronization
    Target: 95%+ accuracy through precision timing and micro-movement analysis
    """
    
    def __init__(self):
        self.chicago_tz = pytz.timezone('America/Chicago')
        
        # Ultra-short timeframe settings (in seconds)
        self.ultra_timeframes = {
            '5s': 5,
            '15s': 15,
            '30s': 30,
            '1m': 60,
            '2m': 120,
            '3m': 180,
            '5m': 300
        }
        
        # Optimized indicator parameters for ultra-short timeframes
        self.indicator_params = {
            '5s': {
                'ema_fast': 3, 'ema_slow': 7, 'ema_signal': 14,
                'macd_fast': 5, 'macd_slow': 10, 'macd_signal': 3,
                'rsi_period': 7, 'rsi_overbought': 75, 'rsi_oversold': 25
            },
            '15s': {
                'ema_fast': 5, 'ema_slow': 10, 'ema_signal': 20,
                'macd_fast': 8, 'macd_slow': 17, 'macd_signal': 5,
                'rsi_period': 9, 'rsi_overbought': 70, 'rsi_oversold': 30
            },
            '30s': {
                'ema_fast': 7, 'ema_slow': 14, 'ema_signal': 28,
                'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 7,
                'rsi_period': 14, 'rsi_overbought': 70, 'rsi_oversold': 30
            }
        }
        
        # Precision timing buffers for Pocket Option synchronization
        self.timing_precision = {
            '5s': {'signal_buffer': 0.5, 'execution_window': 1.0},
            '15s': {'signal_buffer': 1.0, 'execution_window': 2.0},
            '30s': {'signal_buffer': 1.5, 'execution_window': 3.0}
        }
    
    async def get_precise_candle_timing(self, timeframe: str, market_type: str = "regular") -> Dict[str, datetime]:
        """
        Calculate precise candle formation timing synchronized with Pocket Option
        """
        try:
            chicago_now = datetime.now(self.chicago_tz)
            timeframe_seconds = self.ultra_timeframes.get(timeframe, 60)
            
            # Calculate exact candle boundaries
            seconds_since_epoch = chicago_now.timestamp()
            current_candle_start = int(seconds_since_epoch // timeframe_seconds) * timeframe_seconds
            next_candle_start = current_candle_start + timeframe_seconds
            
            # Convert back to datetime
            current_candle_time = datetime.fromtimestamp(current_candle_start, self.chicago_tz)
            next_candle_time = datetime.fromtimestamp(next_candle_start, self.chicago_tz)
            
            # Calculate optimal signal generation time (before candle closes)
            buffer = self.timing_precision[timeframe]['signal_buffer']
            signal_time = next_candle_time - timedelta(seconds=buffer)
            
            # Calculate execution window
            execution_window = self.timing_precision[timeframe]['execution_window']
            execution_start = next_candle_time - timedelta(seconds=execution_window)
            execution_end = next_candle_time + timedelta(seconds=execution_window)
            
            return {
                'current_candle_start': current_candle_time,
                'next_candle_start': next_candle_time,
                'signal_generation_time': signal_time,
                'execution_window_start': execution_start,
                'execution_window_end': execution_end,
                'seconds_to_next_candle': (next_candle_time - chicago_now).total_seconds(),
                'seconds_to_signal': (signal_time - chicago_now).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Error calculating precise candle timing: {e}")
            chicago_now = datetime.now(self.chicago_tz)
            return {
                'current_candle_start': chicago_now,
                'next_candle_start': chicago_now + timedelta(seconds=60),
                'signal_generation_time': chicago_now + timedelta(seconds=50),
                'execution_window_start': chicago_now + timedelta(seconds=55),
                'execution_window_end': chicago_now + timedelta(seconds=65),
                'seconds_to_next_candle': 60,
                'seconds_to_signal': 50
            }
    
    async def analyze_ultra_short_price_action(self, df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        """
        Analyze price action patterns optimized for ultra-short timeframes
        """
        try:
            if len(df) < 20:
                return {'pattern': 'insufficient_data', 'confidence': 0}
            
            # Get indicator parameters for timeframe
            params = self.indicator_params.get(timeframe, self.indicator_params['30s'])
            
            # Calculate ultra-short EMAs
            ema_fast = df['close'].ewm(span=params['ema_fast']).mean()
            ema_slow = df['close'].ewm(span=params['ema_slow']).mean()
            ema_signal = df['close'].ewm(span=params['ema_signal']).mean()
            
            # Current values
            price_current = df['close'].iloc[-1]
            ema_fast_current = ema_fast.iloc[-1]
            ema_slow_current = ema_slow.iloc[-1]
            ema_signal_current = ema_signal.iloc[-1]
            
            # EMA alignment analysis
            ema_bullish = ema_fast_current > ema_slow_current > ema_signal_current
            ema_bearish = ema_fast_current < ema_slow_current < ema_signal_current
            
            # Calculate micro MACD
            macd_line = ema_fast - ema_slow
            macd_signal_line = macd_line.ewm(span=params['macd_signal']).mean()
            macd_histogram = macd_line - macd_signal_line
            
            # Current MACD values
            macd_current = macd_histogram.iloc[-1]
            macd_previous = macd_histogram.iloc[-2] if len(macd_histogram) > 1 else 0
            macd_momentum = macd_current > macd_previous
            
            # Ultra-sensitive RSI
            rsi = self._calculate_ultra_rsi(df['close'], params['rsi_period'])
            rsi_current = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # RSI conditions
            rsi_overbought = rsi_current > params['rsi_overbought']
            rsi_oversold = rsi_current < params['rsi_oversold']
            rsi_neutral = params['rsi_oversold'] <= rsi_current <= params['rsi_overbought']
            
            # Micro candlestick analysis
            candle_analysis = self._analyze_micro_candles(df.tail(5))
            
            # Price velocity and acceleration
            price_velocity = df['close'].diff().iloc[-1]
            price_acceleration = df['close'].diff().diff().iloc[-1]
            
            # Volume analysis (if available)
            volume_signal = 'neutral'
            if 'volume' in df.columns and len(df) > 10:
                volume_avg = df['volume'].rolling(10).mean().iloc[-1]
                volume_current = df['volume'].iloc[-1]
                volume_ratio = volume_current / volume_avg if volume_avg > 0 else 1
                
                if volume_ratio > 1.5:
                    volume_signal = 'high'
                elif volume_ratio < 0.7:
                    volume_signal = 'low'
            
            return {
                'price_current': price_current,
                'ema_alignment': {
                    'bullish': ema_bullish,
                    'bearish': ema_bearish,
                    'fast': ema_fast_current,
                    'slow': ema_slow_current,
                    'signal': ema_signal_current
                },
                'macd': {
                    'current': macd_current,
                    'momentum': macd_momentum,
                    'histogram': macd_current
                },
                'rsi': {
                    'value': rsi_current,
                    'overbought': rsi_overbought,
                    'oversold': rsi_oversold,
                    'neutral': rsi_neutral
                },
                'candle_pattern': candle_analysis,
                'price_dynamics': {
                    'velocity': price_velocity,
                    'acceleration': price_acceleration
                },
                'volume_signal': volume_signal,
                'timeframe': timeframe
            }
            
        except Exception as e:
            logger.error(f"Error in ultra-short price action analysis: {e}")
            return {'pattern': 'error', 'confidence': 0, 'error': str(e)}
    
    def _calculate_ultra_rsi(self, prices: pd.Series, period: int = 7) -> pd.Series:
        """Calculate ultra-responsive RSI for short timeframes"""
        delta = prices.diff()
        gains = delta.where(delta > 0, 0).ewm(alpha=2/(period+1), adjust=False).mean()
        losses = (-delta.where(delta < 0, 0)).ewm(alpha=2/(period+1), adjust=False).mean()
        rs = gains / losses
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _analyze_micro_candles(self, candles_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze micro candlestick patterns for ultra-short timeframes"""
        try:
            if len(candles_df) < 3:
                return {'pattern': 'insufficient', 'strength': 0}
            
            latest = candles_df.iloc[-1]
            previous = candles_df.iloc[-2]
            
            # Candle properties
            body_size = abs(latest['close'] - latest['open'])
            total_range = latest['high'] - latest['low']
            upper_shadow = latest['high'] - max(latest['close'], latest['open'])
            lower_shadow = min(latest['close'], latest['open']) - latest['low']
            
            # Ratios
            body_ratio = body_size / total_range if total_range > 0 else 0
            upper_shadow_ratio = upper_shadow / total_range if total_range > 0 else 0
            lower_shadow_ratio = lower_shadow / total_range if total_range > 0 else 0
            
            # Pattern detection
            patterns = []
            
            # Bullish patterns
            if latest['close'] > latest['open'] and body_ratio > 0.6:
                patterns.append('strong_bullish_body')
            if lower_shadow_ratio > 0.4 and body_ratio < 0.3:
                patterns.append('hammer_like')
            if latest['close'] > previous['close'] and body_ratio > 0.5:
                patterns.append('bullish_continuation')
            
            # Bearish patterns
            if latest['close'] < latest['open'] and body_ratio > 0.6:
                patterns.append('strong_bearish_body')
            if upper_shadow_ratio > 0.4 and body_ratio < 0.3:
                patterns.append('shooting_star_like')
            if latest['close'] < previous['close'] and body_ratio > 0.5:
                patterns.append('bearish_continuation')
            
            # Indecision patterns
            if body_ratio < 0.2:
                patterns.append('doji_like')
            
            # Overall sentiment
            if any('bullish' in p for p in patterns):
                sentiment = 'bullish'
                strength = len([p for p in patterns if 'bullish' in p]) * 0.3
            elif any('bearish' in p for p in patterns):
                sentiment = 'bearish'
                strength = len([p for p in patterns if 'bearish' in p]) * 0.3
            else:
                sentiment = 'neutral'
                strength = 0.1
            
            return {
                'patterns': patterns,
                'sentiment': sentiment,
                'strength': min(strength, 1.0),
                'body_ratio': body_ratio,
                'upper_shadow_ratio': upper_shadow_ratio,
                'lower_shadow_ratio': lower_shadow_ratio
            }
            
        except Exception as e:
            logger.error(f"Error analyzing micro candles: {e}")
            return {'pattern': 'error', 'strength': 0}
    
    async def generate_ultra_short_signal(self, symbol: str, market_data, timeframe: str, 
                                        analysis_data: Dict) -> Optional[TradingSignal]:
        """
        Generate ultra-short timeframe signal with maximum precision
        """
        try:
            # Get precise timing for this timeframe
            timing_info = await self.get_precise_candle_timing(timeframe, 
                "otc" if "_OTC" in symbol else "regular")
            
            # Check if we're in the optimal signal generation window
            seconds_to_signal = timing_info['seconds_to_signal']
            if seconds_to_signal > 10:  # Too early to generate signal
                logger.info(f"Too early to generate {timeframe} signal, waiting {seconds_to_signal:.1f}s")
                return None
            
            # Analyze all signal components
            ema_data = analysis_data['ema_alignment']
            macd_data = analysis_data['macd']
            rsi_data = analysis_data['rsi']
            candle_data = analysis_data['candle_pattern']
            
            # Signal scoring system for ultra-high accuracy
            signal_score = 0
            direction_votes = {'BUY': 0, 'SELL': 0}
            confidence_factors = []
            
            # EMA alignment scoring (40% weight)
            if ema_data['bullish']:
                direction_votes['BUY'] += 4
                signal_score += 40
                confidence_factors.append('EMA_Bullish_Alignment')
            elif ema_data['bearish']:
                direction_votes['SELL'] += 4
                signal_score += 40
                confidence_factors.append('EMA_Bearish_Alignment')
            
            # MACD momentum scoring (30% weight)
            if macd_data['momentum'] and macd_data['current'] > 0:
                direction_votes['BUY'] += 3
                signal_score += 30
                confidence_factors.append('MACD_Bullish_Momentum')
            elif not macd_data['momentum'] and macd_data['current'] < 0:
                direction_votes['SELL'] += 3
                signal_score += 30
                confidence_factors.append('MACD_Bearish_Momentum')
            
            # RSI scoring (20% weight)
            if rsi_data['oversold'] and not rsi_data['overbought']:
                direction_votes['BUY'] += 2
                signal_score += 20
                confidence_factors.append('RSI_Oversold_Reversal')
            elif rsi_data['overbought'] and not rsi_data['oversold']:
                direction_votes['SELL'] += 2
                signal_score += 20
                confidence_factors.append('RSI_Overbought_Reversal')
            elif rsi_data['neutral']:
                signal_score += 10  # Neutral RSI adds some confidence
            
            # Candlestick pattern scoring (10% weight)
            if candle_data['sentiment'] == 'bullish' and candle_data['strength'] > 0.5:
                direction_votes['BUY'] += 1
                signal_score += 10
                confidence_factors.append('Bullish_Candle_Pattern')
            elif candle_data['sentiment'] == 'bearish' and candle_data['strength'] > 0.5:
                direction_votes['SELL'] += 1
                signal_score += 10
                confidence_factors.append('Bearish_Candle_Pattern')
            
            # Volume confirmation (bonus)
            if analysis_data['volume_signal'] == 'high':
                signal_score += 5
                confidence_factors.append('High_Volume_Confirmation')
            
            # Determine final direction
            if direction_votes['BUY'] > direction_votes['SELL']:
                final_direction = SignalDirection.BUY
                vote_ratio = direction_votes['BUY'] / (direction_votes['BUY'] + direction_votes['SELL'])
            elif direction_votes['SELL'] > direction_votes['BUY']:
                final_direction = SignalDirection.SELL
                vote_ratio = direction_votes['SELL'] / (direction_votes['BUY'] + direction_votes['SELL'])
            else:
                logger.info("No clear directional signal, skipping")
                return None
            
            # ENHANCED Calculate final confidence for MAXIMUM levels
            base_confidence = signal_score
            vote_confidence = vote_ratio * 22  # Up to 22% bonus for strong agreement (ENHANCED from 20)
            
            # Ultra-short timeframe bonus (ENHANCED - these timeframes can be very accurate)
            timeframe_bonus = {'5s': 12, '15s': 10, '30s': 7}.get(timeframe, 0)
            
            # Additional confidence factor boost
            confidence_factors_bonus = len(confidence_factors) * 1.5  # Boost for each confirmation factor
            
            final_confidence = min(base_confidence + vote_confidence + timeframe_bonus + confidence_factors_bonus, 99.0)
            
            # Only generate signals with 85%+ confidence for ultra-short timeframes
            if final_confidence < 85.0:
                logger.info(f"Confidence {final_confidence:.1f}% below threshold for {timeframe} signal")
                return None
            
            # Determine market type
            market_type = "otc" if "_OTC" in symbol else "regular"
            
            # Create the signal
            signal = TradingSignal(
                id=f"ULTRA_{timeframe}_{datetime.now(self.chicago_tz).strftime('%Y%m%d_%H%M%S')}_{symbol}",
                symbol=symbol,
                asset_type=market_data.asset_type,
                direction=final_direction,
                entry_price=analysis_data['price_current'],
                expiration_minutes=1 if timeframe in ['5s', '15s'] else 2,  # Ultra-short expiration
                timeframe=timeframe,
                market_type=market_type,
                probability=final_confidence,
                confidence_level="HIGH" if final_confidence >= 90 else "MEDIUM",
                strategy_used=TradingStrategy.HYBRID,
                technical_analysis={
                    'ultra_short_analysis': True,
                    'timeframe': timeframe,
                    'signal_score': signal_score,
                    'direction_votes': direction_votes,
                    'confidence_factors': confidence_factors,
                    'ema_alignment': ema_data,
                    'macd_data': macd_data,
                    'rsi_data': rsi_data,
                    'candle_pattern': candle_data,
                    'timing_precision': timing_info
                },
                market_analysis_summary=f"Ultra-short {timeframe} signal with {final_confidence:.1f}% confidence. "
                                      f"Analysis factors: {', '.join(confidence_factors)}. "
                                      f"Direction votes: {direction_votes['BUY']} BUY vs {direction_votes['SELL']} SELL.",
                justification=f"🚀 ULTRA-SHORT {timeframe.upper()} SIGNAL - Precision timing analysis. "
                            f"Signal strength: {signal_score}/100. "
                            f"Confidence factors: {len(confidence_factors)}. "
                            f"⚡ POCKET OPTION SYNCHRONIZED: Entry at next {timeframe} candle formation. "
                            f"Expiration optimized for {timeframe} micro-movements.",
                risk_assessment=f"ULTRA-SHORT RISK - {timeframe} timeframe trading. "
                              f"High precision with {final_confidence:.1f}% confidence. "
                              f"Use minimal stake for ultra-short trades.",
                suggested_stake=2.0 if timeframe == '5s' else 3.0 if timeframe == '15s' else 5.0,
                precision_entry_time=timing_info['next_candle_start'],
                timestamp=datetime.now(self.chicago_tz)
            )
            
            logger.info(f"Generated ultra-short {timeframe} signal: {symbol} {final_direction} "
                       f"with {final_confidence:.1f}% confidence")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating ultra-short signal: {e}")
            return None


# Global instance
ultra_short_engine = UltraShortPrecisionEngine()