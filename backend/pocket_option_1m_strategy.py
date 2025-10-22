"""
Pocket Option 1-Minute High-Accuracy Strategy (93%+ Target)
Based on research of top-performing Pocket Option bots in 2024-2025

EXACT PARAMETERS FROM RESEARCH:
- EMA: 20 periods
- RSI: 14 periods
- MACD: Standard (12, 26, 9)
- Bollinger Bands: 20 periods, 2 SD
- Stochastic: (14, 3, 3)

Strategy Logic:
1. EMA 20 for trend direction
2. RSI 14 for momentum
3. MACD for trend validation
4. Bollinger Bands for volatility and extremes
5. Stochastic for overbought/oversold
6. Support/Resistance + Price Action patterns
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, List
from chart_transformations import chart_transformer
from support_resistance_detector import get_detector
from gpt_signal_enhancer import gpt_signal_enhancer
import talib
import asyncio

logger = logging.getLogger(__name__)

class PocketOption1MinuteStrategy:
    """
    High-accuracy 1-minute strategy with multiple confirmations
    Target accuracy: 93%+
    """
    
    def __init__(self):
        # EXACT parameters from research
        self.ema_period = 20
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2.0
        self.stoch_k_period = 14
        self.stoch_d_period = 3
        self.stoch_smooth = 3
        
        self.min_data_points = 100
        
        # Thresholds
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.stoch_overbought = 80
        self.stoch_oversold = 20
        
        # Enhanced S/R detector for 1m timeframe
        self.sr_detector = get_detector('1m')
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate EMA using TA-Lib"""
        return pd.Series(talib.EMA(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using TA-Lib"""
        return pd.Series(talib.RSI(prices.values, timeperiod=period), index=prices.index)
    
    def calculate_macd(self, prices: pd.Series) -> tuple:
        """Calculate MACD"""
        macd, signal, hist = talib.MACD(
            prices.values,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal
        )
        return (
            pd.Series(macd, index=prices.index),
            pd.Series(signal, index=prices.index),
            pd.Series(hist, index=prices.index)
        )
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate Slow Stochastic"""
        slowk, slowd = talib.STOCH(
            high.values, low.values, close.values,
            fastk_period=self.stoch_k_period,
            slowk_period=self.stoch_d_period,
            slowk_matype=0,
            slowd_period=self.stoch_smooth,
            slowd_matype=0
        )
        return pd.Series(slowk, index=close.index), pd.Series(slowd, index=close.index)
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> tuple:
        """Calculate Bollinger Bands"""
        upper, middle, lower = talib.BBANDS(
            prices.values,
            timeperiod=self.bb_period,
            nbdevup=self.bb_std,
            nbdevdn=self.bb_std,
            matype=0
        )
        return (
            pd.Series(upper, index=prices.index),
            pd.Series(middle, index=prices.index),
            pd.Series(lower, index=prices.index)
        )
    
    def detect_support_resistance(self, prices: pd.Series, window: int = 30) -> Dict:
        """Detect support and resistance levels"""
        highs = prices.rolling(window=window).max()
        lows = prices.rolling(window=window).min()
        
        current_price = prices.iloc[-1]
        resistance = highs.iloc[-1]
        support = lows.iloc[-1]
        
        return {
            'resistance': resistance,
            'support': support,
            'near_resistance': abs(current_price - resistance) / current_price < 0.003,
            'near_support': abs(current_price - support) / current_price < 0.003
        }
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict:
        """Detect candlestick patterns using TA-Lib"""
        if len(df) < 5:
            return {}
        
        patterns = {}
        
        # Pin Bar (Hammer/Hanging Man)
        hammer = talib.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
        hanging_man = talib.CDLHANGINGMAN(df['open'], df['high'], df['low'], df['close'])
        patterns['hammer'] = hammer.iloc[-1] != 0
        patterns['hanging_man'] = hanging_man.iloc[-1] != 0
        
        # Doji
        doji = talib.CDLDOJI(df['open'], df['high'], df['low'], df['close'])
        patterns['doji'] = doji.iloc[-1] != 0
        
        # Engulfing
        engulfing = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
        patterns['bullish_engulfing'] = engulfing.iloc[-1] > 0
        patterns['bearish_engulfing'] = engulfing.iloc[-1] < 0
        
        return patterns
    
    def get_real_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch real 1-minute data for analysis"""
        try:
            # Convert symbol for yfinance (forex pairs need =X suffix)
            yf_symbol = symbol
            if '_OTC' in symbol or '_regular' in symbol:
                yf_symbol = symbol.replace('_OTC', '').replace('_regular', '')
            
            # Add =X for forex pairs
            if len(yf_symbol) == 6 and yf_symbol.isalpha():  # Forex pair like EURUSD
                yf_symbol = f"{yf_symbol}=X"
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1d", interval="1m")
            
            if df.empty or len(df) < self.min_data_points:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    def generate_signal(self, symbol: str, chart_type: str = "japanese_candles", user_timeframes: List[str] = None) -> Optional[Dict]:
        """
        Generate 1-minute trading signal using comprehensive strategy
        
        Returns:
            Dict with signal, confidence, reasoning, and analysis
        """
        try:
            # Fetch real market data
            df = self.get_real_market_data(symbol)
            if df is None:
                return None
            
            # Apply chart transformation
            df = chart_transformer.transform_data(df, chart_type)
            
            # Calculate all indicators
            close_prices = df['close']
            high_prices = df['high']
            low_prices = df['low']
            
            # EMA 20
            ema = self.calculate_ema(close_prices, self.ema_period)
            
            # RSI 14
            rsi = self.calculate_rsi(close_prices, self.rsi_period)
            
            # MACD
            macd, macd_signal, macd_hist = self.calculate_macd(close_prices)
            
            # Stochastic
            stoch_k, stoch_d = self.calculate_stochastic(high_prices, low_prices, close_prices)
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close_prices)
            
            # Get current values
            current_price = close_prices.iloc[-1]
            current_ema = ema.iloc[-1]
            current_rsi = rsi.iloc[-1]
            current_macd = macd.iloc[-1]
            current_macd_signal = macd_signal.iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            prev_macd_hist = macd_hist.iloc[-2]
            current_stoch_k = stoch_k.iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            
            # Check for NaN values
            if pd.isna([current_ema, current_rsi, current_macd, current_stoch_k]).any():
                logger.warning(f"NaN values in indicators for {symbol}")
                return None
            
            # Enhanced S/R detection with trend reversal analysis
            sr_levels = self.sr_detector.identify_key_levels(df)
            proximity = self.sr_detector.is_near_support_resistance(current_price, sr_levels)
            reversal = self.sr_detector.detect_trend_reversal(df, sr_levels)
            
            # Detect candlestick patterns
            patterns = self.detect_candlestick_patterns(df)
            
            # MACD crossover detection
            macd_bullish_cross = prev_macd_hist < 0 and current_macd_hist > 0
            macd_bearish_cross = prev_macd_hist > 0 and current_macd_hist < 0
            
            # Calculate BB position
            bb_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower) if current_bb_upper != current_bb_lower else 0.5
            
            # Strategy Logic (Multi-Indicator Confluence)
            signal = None
            confidence = 0
            reasoning = []
            
            logger.info(f"🎯 1m Analysis for {symbol}:")
            logger.info(f"   Price={current_price:.5f}, EMA={current_ema:.5f}, RSI={current_rsi:.1f}")
            logger.info(f"   MACD={current_macd:.5f}, Signal={current_macd_signal:.5f}, Hist={current_macd_hist:.5f}")
            logger.info(f"   Stoch={current_stoch_k:.1f}, BB Position={bb_position:.2%}")
            
            # === RULE 1: Triple Confirmation (EMA + RSI + MACD) - Highest Priority ===
            if current_price > current_ema and current_rsi > 50 and current_macd > current_macd_signal:
                # Strong bullish alignment
                signal = "CALL"
                confidence = 90
                reasoning.append("🟢 TRIPLE BULLISH: Price > EMA, RSI > 50, MACD > Signal")
                reasoning.append("💡 All major indicators aligned for upward movement")
            
            elif current_price < current_ema and current_rsi < 50 and current_macd < current_macd_signal:
                # Strong bearish alignment
                signal = "PUT"
                confidence = 90
                reasoning.append("🔴 TRIPLE BEARISH: Price < EMA, RSI < 50, MACD < Signal")
                reasoning.append("💡 All major indicators aligned for downward movement")
            
            # === RULE 2: MACD Crossover + RSI Confirmation ===
            if signal is None:
                if macd_bullish_cross and current_rsi > 40:
                    signal = "CALL"
                    confidence = 87
                    reasoning.append("🟢 MACD BULLISH CROSSOVER detected")
                    reasoning.append(f"✅ RSI confirms momentum ({current_rsi:.1f})")
                
                elif macd_bearish_cross and current_rsi < 60:
                    signal = "PUT"
                    confidence = 87
                    reasoning.append("🔴 MACD BEARISH CROSSOVER detected")
                    reasoning.append(f"✅ RSI confirms momentum ({current_rsi:.1f})")
            
            # === RULE 3: BB Extremes + Multiple Confirmations ===
            if signal is None:
                if bb_position < 0.1:  # Lower BB
                    if current_rsi < 35 and current_stoch_k < 30:
                        signal = "CALL"
                        confidence = 88
                        reasoning.append("🟢 OVERSOLD BOUNCE: Price at lower BB")
                        reasoning.append(f"✅ RSI ({current_rsi:.1f}) and Stoch ({current_stoch_k:.1f}) confirm oversold")
                
                elif bb_position > 0.9:  # Upper BB
                    if current_rsi > 65 and current_stoch_k > 70:
                        signal = "PUT"
                        confidence = 88
                        reasoning.append("🔴 OVERBOUGHT REVERSAL: Price at upper BB")
                        reasoning.append(f"✅ RSI ({current_rsi:.1f}) and Stoch ({current_stoch_k:.1f}) confirm overbought")
            
            # === RULE 4: Trend Following + Momentum ===
            if signal is None:
                if current_price > current_ema:
                    if 45 < current_rsi < 70 and current_macd_hist > 0:
                        signal = "CALL"
                        confidence = 83
                        reasoning.append("📈 UPTREND: Price above EMA with positive momentum")
                        reasoning.append(f"✅ RSI ({current_rsi:.1f}) and MACD histogram positive")
                
                elif current_price < current_ema:
                    if 30 < current_rsi < 55 and current_macd_hist < 0:
                        signal = "PUT"
                        confidence = 83
                        reasoning.append("📉 DOWNTREND: Price below EMA with negative momentum")
                        reasoning.append(f"✅ RSI ({current_rsi:.1f}) and MACD histogram negative")
            
            # === Confidence Boosters ===
            if signal == "CALL":
                # Stochastic confirmation
                if current_stoch_k < 30:
                    confidence += 5
                    reasoning.append(f"✅ Stochastic oversold ({current_stoch_k:.1f})")
                
                # Enhanced S/R confirmation with reversal detection
                if reversal['reversal_detected'] and reversal['bounce_off_support']:
                    confidence += 7
                    reasoning.append(f"✅ REVERSAL: Bounce off support (strength: {reversal['reversal_strength']})")
                elif proximity['near_support']:
                    confidence += 5
                    reasoning.append(f"✅ Price near support ({proximity['support_distance_pct']:.2f}% away)")
                
                # Bullish patterns
                if patterns.get('hammer') or patterns.get('bullish_engulfing'):
                    confidence += 3
                    reasoning.append("✅ Bullish candlestick pattern detected")
            
            elif signal == "PUT":
                # Stochastic confirmation
                if current_stoch_k > 70:
                    confidence += 5
                    reasoning.append(f"✅ Stochastic overbought ({current_stoch_k:.1f})")
                
                # Enhanced S/R confirmation with reversal detection
                if reversal['reversal_detected'] and reversal['bounce_off_resistance']:
                    confidence += 7
                    reasoning.append(f"✅ REVERSAL: Reversal at resistance (strength: {reversal['reversal_strength']})")
                elif proximity['near_resistance']:
                    confidence += 5
                    reasoning.append(f"✅ Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
                
                # Bearish patterns
                if patterns.get('hanging_man') or patterns.get('bearish_engulfing'):
                    confidence += 3
                    reasoning.append("✅ Bearish candlestick pattern detected")
            
            if signal is None:
                return None
            
            # === GPT-4 ENHANCEMENT (Advanced AI Validation) ===
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    gpt_result = {'enhanced': False, 'valid': True, 'confidence_adjustment': 0, 'reasoning': [], 'risk_factors': []}
                else:
                    gpt_result = loop.run_until_complete(
                        gpt_signal_enhancer.enhance_signal(
                            signal=signal,
                            confidence=confidence,
                            features={},  # 1m strategy doesn't have advanced features yet
                            technical_analysis={
                                'rsi_14': current_rsi,
                                'ema_distance': (current_price - current_ema) / current_price if current_price > 0 else 0,
                                'stoch_k': current_stoch_k,
                                'bb_position': bb_position,
                                'macd_histogram': current_macd_hist,
                                'nearest_support': sr_levels.get('nearest_support'),
                                'nearest_resistance': sr_levels.get('nearest_resistance'),
                                'reversal_detected': reversal.get('reversal_detected'),
                                'reversal_type': reversal.get('reversal_type')
                            },
                            timeframe='1m'
                        )
                    )
                
                if gpt_result.get('enhanced'):
                    gpt_adjustment = gpt_result.get('confidence_adjustment', 0)
                    confidence += gpt_adjustment
                    
                    if gpt_result.get('reasoning'):
                        reasoning.append(f"🤖 GPT-4: {', '.join(gpt_result['reasoning'][:2])}")
                    
                    if gpt_result.get('risk_factors'):
                        reasoning.append(f"⚠️ Risks: {', '.join(gpt_result['risk_factors'][:2])}")
                    
                    if not gpt_result.get('valid', True):
                        logger.warning(f"⚠️ GPT-4 REJECTED signal: {gpt_result.get('reasoning')}")
                        return None
                    
                    logger.info(f"🤖 GPT-4 Enhanced: {signal} ({gpt_adjustment:+.1f}% adjustment)")
            except Exception as e:
                logger.error(f"GPT enhancement error (continuing without): {e}")
            
            # === CRITICAL: Validate signal against S/R levels ===
            validation = self.sr_detector.validate_signal_direction(signal, current_price, sr_levels)
            
            if not validation['valid']:
                logger.warning(f"⚠️ Signal REJECTED by S/R validation: {validation['reasoning']}")
                return None
            
            # Apply confidence adjustment from S/R validation
            confidence += validation['confidence_adjustment']
            reasoning.extend(validation['reasoning'])
            
            # Cap confidence at 98%
            confidence = min(confidence, 98)
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reasoning": reasoning,
                "analysis": {
                    "price": current_price,
                    "ema_20": current_ema,
                    "rsi_14": current_rsi,
                    "macd": current_macd,
                    "macd_signal": current_macd_signal,
                    "macd_histogram": current_macd_hist,
                    "stoch_k": current_stoch_k,
                    "bb_position": bb_position,
                    "nearest_support": sr_levels['nearest_support'],
                    "nearest_resistance": sr_levels['nearest_resistance'],
                    "pivot_point": sr_levels['pivot_point'],
                    "reversal_detected": reversal['reversal_detected'],
                    "reversal_type": reversal['reversal_type'],
                    "patterns": patterns
                },
                "strategy": "Pocket Option 1m Multi-Indicator",
                "timeframe": "1m"
            }
            
        except Exception as e:
            logger.error(f"Error in 1m strategy for {symbol}: {e}", exc_info=True)
            return None

# Create singleton instance
pocket_option_1m_strategy = PocketOption1MinuteStrategy()
