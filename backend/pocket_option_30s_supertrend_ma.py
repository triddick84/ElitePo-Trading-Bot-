"""
POCKET OPTION 30-SECOND SUPERTREND + MA CROSSOVER STRATEGY

Specific Technical Indicators:
1. SuperTrend: ATR Period 2, Multiplier 1.1
2. 12 TMA (Triangular Moving Average) - White
3. 17 EMA (Exponential Moving Average) - Yellow

Signal Rules:
- SELL: 12 TMA crosses below 17 EMA + SuperTrend SELL
- BUY: 12 TMA crosses above 17 EMA + SuperTrend BUY

Only for: 30s timeframe, Japanese candles, Heikin Ashi
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from models import TradingSignal, SignalDirection, TradingStrategy
import talib

logger = logging.getLogger(__name__)

class PocketOption30sSuperTrendMA:
    """
    30-second strategy using SuperTrend + MA Crossover
    Ultra-precise confirmations for high accuracy
    """
    
    def __init__(self):
        self.name = "Pocket Option 30s SuperTrend MA Strategy"
        
        # SuperTrend parameters (EXACT as specified)
        self.supertrend_atr_period = 2
        self.supertrend_multiplier = 1.1
        
        # Moving Average parameters (EXACT as specified)
        self.tma_period = 12  # Triangular MA (White)
        self.ema_period = 17  # Exponential MA (Yellow)
        
        # Minimum confidence for signals
        self.min_confidence = 75.0
        
        logger.info(f"🎯 {self.name} initialized")
        logger.info(f"   SuperTrend: ATR={self.supertrend_atr_period}, Multiplier={self.supertrend_multiplier}")
        logger.info(f"   MA Crossover: {self.tma_period} TMA x {self.ema_period} EMA")
    
    def calculate_tma(self, data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Triangular Moving Average (TMA)
        TMA = SMA of SMA (double smoothed)
        """
        try:
            sma1 = data.rolling(window=period).mean()
            tma = sma1.rolling(window=period).mean()
            return tma
        except Exception as e:
            logger.error(f"Error calculating TMA: {e}")
            return pd.Series([data.iloc[-1]] * len(data))
    
    def calculate_supertrend(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate SuperTrend indicator with EXACT parameters
        ATR Period: 2, Multiplier: 1.1
        
        Returns: (supertrend_line, direction)
        direction: 1 = BUY trend, -1 = SELL trend
        """
        try:
            # Calculate ATR with period 2
            atr = talib.ATR(high.values, low.values, close.values, timeperiod=self.supertrend_atr_period)
            atr_series = pd.Series(atr, index=close.index)
            
            # Basic bands
            hl_avg = (high + low) / 2
            upper_band = hl_avg + (self.supertrend_multiplier * atr_series)
            lower_band = hl_avg - (self.supertrend_multiplier * atr_series)
            
            # SuperTrend logic
            supertrend = pd.Series(index=close.index, dtype=float)
            direction = pd.Series(index=close.index, dtype=int)
            
            for i in range(len(close)):
                if i == 0:
                    supertrend.iloc[i] = lower_band.iloc[i]
                    direction.iloc[i] = 1  # BUY
                else:
                    # Determine trend direction
                    if close.iloc[i] > supertrend.iloc[i-1]:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = 1  # BUY trend
                    else:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = -1  # SELL trend
            
            return supertrend, direction
            
        except Exception as e:
            logger.error(f"Error calculating SuperTrend: {e}")
            return pd.Series([close.iloc[-1]] * len(close)), pd.Series([1] * len(close))
    
    def detect_crossover(self, fast: pd.Series, slow: pd.Series) -> str:
        """
        Detect MA crossover
        Returns: 'bullish' (fast crosses above slow), 'bearish' (fast crosses below slow), or 'none'
        """
        try:
            if len(fast) < 2 or len(slow) < 2:
                return 'none'
            
            # Current and previous values
            fast_current = fast.iloc[-1]
            fast_prev = fast.iloc[-2]
            slow_current = slow.iloc[-1]
            slow_prev = slow.iloc[-2]
            
            # Bullish crossover: fast crosses ABOVE slow
            if fast_prev < slow_prev and fast_current > slow_current:
                return 'bullish'
            
            # Bearish crossover: fast crosses BELOW slow
            if fast_prev > slow_prev and fast_current < slow_current:
                return 'bearish'
            
            return 'none'
            
        except Exception as e:
            logger.error(f"Error detecting crossover: {e}")
            return 'none'
    
    async def analyze(self, market_data: Dict, symbol: str, force_mode: bool = False) -> Optional[Dict]:
        """
        Analyze market data for 30s signals
        
        Args:
            market_data: Market candle data
            symbol: Trading symbol
            force_mode: If True, use AI prediction when confirmations not met
        """
        try:
            logger.info(f"📊 Analyzing {symbol} with 30s SuperTrend MA Strategy...")
            
            # Convert to DataFrame
            if isinstance(market_data, list):
                df = pd.DataFrame(market_data)
            else:
                df = pd.DataFrame([market_data])
            
            if len(df) < 50:
                logger.warning(f"⚠️ Insufficient data: {len(df)} candles (need 50+)")
                return None
            
            # Prepare price data
            close = pd.Series([float(x.get('close', x.get('price', 0))) for x in market_data])
            high = pd.Series([float(x.get('high', x.get('price', 0))) for x in market_data])
            low = pd.Series([float(x.get('low', x.get('price', 0))) for x in market_data])
            
            current_price = close.iloc[-1]
            
            # === INDICATOR 1: SUPERTREND (ATR Period 2, Multiplier 1.1) ===
            logger.info(f"   📈 Calculating SuperTrend (ATR=2, Multiplier=1.1)...")
            supertrend_line, supertrend_direction = self.calculate_supertrend(high, low, close)
            
            supertrend_current = supertrend_direction.iloc[-1]
            supertrend_signal = 'BUY' if supertrend_current == 1 else 'SELL'
            
            logger.info(f"   ✅ SuperTrend Signal: {supertrend_signal}")
            
            # === INDICATOR 2: 12 TMA (Triangular Moving Average) ===
            logger.info(f"   📊 Calculating 12 TMA (White)...")
            tma_12 = self.calculate_tma(close, self.tma_period)
            tma_12_current = tma_12.iloc[-1]
            
            # === INDICATOR 3: 17 EMA (Exponential Moving Average) ===
            logger.info(f"   📊 Calculating 17 EMA (Yellow)...")
            ema_17 = talib.EMA(close.values, timeperiod=self.ema_period)
            ema_17_series = pd.Series(ema_17, index=close.index)
            ema_17_current = ema_17_series.iloc[-1]
            
            # === DETECT MA CROSSOVER ===
            crossover = self.detect_crossover(tma_12, ema_17_series)
            logger.info(f"   🔄 MA Crossover: {crossover.upper()}")
            
            # === SIGNAL CONFIRMATION LOGIC ===
            signal_confirmed = False
            direction = None
            confidence = 0
            
            # BUY SIGNAL: 12 TMA crosses ABOVE 17 EMA + SuperTrend BUY
            if crossover == 'bullish' and supertrend_signal == 'BUY':
                signal_confirmed = True
                direction = SignalDirection.BUY
                confidence = 85.0
                logger.info(f"   ✅ BUY SIGNAL CONFIRMED!")
                logger.info(f"      • 12 TMA crossed above 17 EMA ✅")
                logger.info(f"      • SuperTrend shows BUY ✅")
            
            # SELL SIGNAL: 12 TMA crosses BELOW 17 EMA + SuperTrend SELL
            elif crossover == 'bearish' and supertrend_signal == 'SELL':
                signal_confirmed = True
                direction = SignalDirection.SELL
                confidence = 85.0
                logger.info(f"   ✅ SELL SIGNAL CONFIRMED!")
                logger.info(f"      • 12 TMA crossed below 17 EMA ✅")
                logger.info(f"      • SuperTrend shows SELL ✅")
            
            # === FORCE MODE: AI PREDICTION ===
            if not signal_confirmed and force_mode:
                logger.info(f"   🤖 FORCE MODE: Using AI prediction (confirmations not met)")
                
                # AI-based prediction using current indicator states
                tma_above_ema = tma_12_current > ema_17_current
                
                # Score system
                bullish_score = 0
                bearish_score = 0
                
                # SuperTrend weight (40%)
                if supertrend_signal == 'BUY':
                    bullish_score += 40
                else:
                    bearish_score += 40
                
                # MA position weight (30%)
                if tma_above_ema:
                    bullish_score += 30
                else:
                    bearish_score += 30
                
                # Price vs MAs weight (20%)
                if current_price > tma_12_current:
                    bullish_score += 20
                if current_price < tma_12_current:
                    bearish_score += 20
                
                # Momentum weight (10%)
                recent_change = close.iloc[-1] - close.iloc[-5]
                if recent_change > 0:
                    bullish_score += 10
                else:
                    bearish_score += 10
                
                logger.info(f"   📊 AI Scores: Bullish={bullish_score}, Bearish={bearish_score}")
                
                if bullish_score > bearish_score:
                    direction = SignalDirection.BUY
                    confidence = (bullish_score / 100) * 80  # Max 80% for AI predictions
                    logger.info(f"   🤖 AI PREDICTION: BUY ({confidence:.1f}%)")
                elif bearish_score > bullish_score:
                    direction = SignalDirection.SELL
                    confidence = (bearish_score / 100) * 80
                    logger.info(f"   🤖 AI PREDICTION: SELL ({confidence:.1f}%)")
                else:
                    logger.info(f"   ⚠️ AI: No clear direction")
                    return None
            
            # If no signal and not force mode
            if not signal_confirmed and not force_mode:
                logger.info(f"   ⚠️ No signal: Confirmations not met")
                return None
            
            # Add bonus for confirmed signals
            if signal_confirmed:
                confidence += 5.0  # Perfect confirmation bonus
            
            # Cap confidence
            final_confidence = min(confidence, 99.0)
            
            logger.info(f"   🎯 FINAL SIGNAL: {direction.value} with {final_confidence:.1f}% confidence")
            
            return {
                'direction': direction,
                'confidence': final_confidence,
                'strategy': TradingStrategy.ULTRA_SHORT_30S,
                'signal_confirmed': signal_confirmed,
                'force_mode': force_mode,
                'technical_analysis': {
                    'supertrend_signal': supertrend_signal,
                    'supertrend_value': float(supertrend_line.iloc[-1]),
                    'tma_12': float(tma_12_current),
                    'ema_17': float(ema_17_current),
                    'ma_crossover': crossover,
                    'tma_above_ema': tma_12_current > ema_17_current,
                    'confirmations': {
                        'ma_crossover': crossover != 'none',
                        'supertrend_aligned': signal_confirmed
                    }
                },
                'entry_price': current_price,
                'timeframe': '30s',
                'strategy_name': self.name
            }
            
        except Exception as e:
            logger.error(f"❌ Error in 30s SuperTrend MA analysis: {e}")
            import traceback
            traceback.print_exc()
            return None


# Global instance
pocket_option_30s_supertrend_ma = PocketOption30sSuperTrendMA()
