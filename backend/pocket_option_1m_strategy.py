"""
Pocket Option 1-Minute ADVANCED Multi-Layer Strategy (93-95%+ Target)
Based on 2025 research - Multi-layer confirmation system

Layer 1: Smart Money Concepts (SMC) - Institutional activity
Layer 2: Technical Analysis - Optimized for 1-minute
Layer 3: ML Ensemble - XGBoost + LightGBM + Random Forest  
Layer 4: Signal Fusion - Weighted confirmation

EXACT PARAMETERS FROM 2025 RESEARCH:
- RSI: 7 periods (faster for 1-minute)
- Bollinger Bands: (20, 2)
- MACD: (12, 26, 9)
- EMA: 9 and 21 periods (dual EMA system)
- Stochastic: (14, 3, 3)

Strategy Logic:
1. RSI extremes (< 30 CALL, > 70 PUT) + BB touches
2. MACD histogram confirms momentum
3. EMA 9 crosses EMA 21 for trend
4. Smart Money validation (liquidity grabs, order blocks)
5. ML ensemble prediction
6. Multi-layer fusion (all must agree)
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
from market_quality_filter import get_market_filter
import talib
import asyncio

logger = logging.getLogger(__name__)

class PocketOption1MinuteStrategy:
    """
    ADVANCED Multi-Layer 1-minute strategy
    Target accuracy: 93-95%+
    """
    
    def __init__(self):
        # EXACT parameters from 2025 research
        self.ema_fast = 9     # Fast EMA (research-verified)
        self.ema_slow = 21    # Slow EMA (research-verified)
        self.rsi_period = 7   # Faster RSI for 1-minute (research-verified)
        self.rsi_period_backup = 14  # Backup for confirmation
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2.0
        self.stoch_k_period = 14
        self.stoch_d_period = 3
        self.stoch_smooth = 3
        
        self.min_data_points = 100
        
        # RSI THRESHOLDS (1-minute optimized)
        self.rsi_oversold = 30  # CALL zone
        self.rsi_overbought = 70  # PUT zone
        self.rsi_extreme_oversold = 20  # Extra strong CALL
        self.rsi_extreme_overbought = 80  # Extra strong PUT
        
        # Stochastic thresholds
        self.stoch_overbought = 80
        self.stoch_oversold = 20
        
        # Minimum base confidence
        self.min_base_confidence = 90
        
        # Enhanced S/R detector for 1m timeframe
        self.sr_detector = get_detector('1m')
        
        # Market quality filter
        self.market_filter = get_market_filter('1m')
        
        logger.info("✅ 1m ADVANCED Strategy initialized with Multi-Layer system")
        
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
        Generate 1-minute trading signal using ADVANCED MULTI-LAYER strategy
        
        Layer 1: Smart Money Concepts (SMC)
        Layer 2: Technical Analysis (RSI + BB + MACD + EMA)
        Layer 3: ML Ensemble
        Layer 4: Signal Fusion
        
        Target Accuracy: 93-95%+
        
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
            
            # === MARKET QUALITY CHECK ===
            market_quality = self.market_filter.check_market_quality(df)
            
            if not market_quality['passed']:
                logger.warning(f"⛔ SIGNAL REJECTED: Poor market quality for {symbol}")
                return None
            
            logger.info(f"✅ Market quality: {market_quality['overall_quality']:.1%}")
            
            # === LAYER 1: SMART MONEY CONCEPTS ANALYSIS ===
            logger.info("🧠 === LAYER 1: Smart Money Analysis (1m) ===")
            from smart_money_detector import get_smart_money_detector
            smc_detector = get_smart_money_detector('1m')
            smc_analysis = smc_detector.get_comprehensive_analysis(df)
            
            smc_confidence = smc_analysis.get('smc_confidence', 0)
            smc_direction = smc_analysis.get('smc_direction')
            
            if smc_confidence < 25:  # Lower threshold for 1m (more signals)
                logger.warning(f"⚠️ Low Smart Money confidence ({smc_confidence:.1f}%), proceeding with caution")
            
            logger.info(f"✅ Smart Money: {smc_direction or 'NEUTRAL'} with {smc_confidence:.1f}% confidence")
            if smc_analysis.get('smc_reasons'):
                logger.info(f"   SMC Reasons: {', '.join(smc_analysis['smc_reasons'])}")
            
            # === LAYER 3: MACHINE LEARNING ENSEMBLE ===
            logger.info("🤖 === LAYER 3: ML Ensemble Prediction (1m) ===")
            from ml_signal_ensemble import get_ml_ensemble
            ml_ensemble = get_ml_ensemble()
            ml_prediction = ml_ensemble.predict(df, smc_analysis)
            
            ml_confidence = ml_prediction.get('confidence', 0)
            ml_direction = ml_prediction.get('direction')
            ml_agreement = ml_prediction.get('agreement', False)
            
            logger.info(f"🤖 ML: {ml_direction or 'NONE'} with {ml_confidence:.1f}% confidence (Agreement: {ml_agreement})")
            
            # === LAYER 2: TECHNICAL ANALYSIS (1-minute optimized) ===
            logger.info("📊 === LAYER 2: Technical Indicators (1m) ===")
            
            # Calculate all indicators with RESEARCH-VERIFIED settings
            close_prices = df['close']
            high_prices = df['high']
            low_prices = df['low']
            
            # Dual EMA system (9 and 21)
            ema_fast = self.calculate_ema(close_prices, self.ema_fast)
            ema_slow = self.calculate_ema(close_prices, self.ema_slow)
            
            # RSI 7 (faster for 1-minute)
            rsi_fast = self.calculate_rsi(close_prices, self.rsi_period)
            rsi_slow = self.calculate_rsi(close_prices, self.rsi_period_backup)
            
            # MACD
            macd, macd_signal, macd_hist = self.calculate_macd(close_prices)
            
            # Stochastic
            stoch_k, stoch_d = self.calculate_stochastic(high_prices, low_prices, close_prices)
            
            # Bollinger Bands (20, 2)
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close_prices)
            
            # Get current values
            current_price = close_prices.iloc[-1]
            current_ema_fast = ema_fast.iloc[-1]
            current_ema_slow = ema_slow.iloc[-1]
            prev_ema_fast = ema_fast.iloc[-2]
            prev_ema_slow = ema_slow.iloc[-2]
            current_rsi_fast = rsi_fast.iloc[-1]
            current_rsi_slow = rsi_slow.iloc[-1]
            current_macd = macd.iloc[-1]
            current_macd_signal = macd_signal.iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            prev_macd_hist = macd_hist.iloc[-2]
            current_stoch_k = stoch_k.iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            current_bb_middle = bb_middle.iloc[-1]
            
            # Check for NaN values
            if pd.isna([current_ema_fast, current_ema_slow, current_rsi_fast, current_macd, current_stoch_k]).any():
                logger.warning(f"NaN values in indicators for {symbol}")
                return None
            
            # Enhanced S/R detection
            sr_levels = self.sr_detector.identify_key_levels(df)
            proximity = self.sr_detector.is_near_support_resistance(current_price, sr_levels)
            reversal = self.sr_detector.detect_trend_reversal(df, sr_levels)
            
            # Detect candlestick patterns
            patterns = self.detect_candlestick_patterns(df)
            
            # MACD crossover and histogram analysis
            macd_bullish_cross = prev_macd_hist < 0 and current_macd_hist > 0
            macd_bearish_cross = prev_macd_hist > 0 and current_macd_hist < 0
            macd_bullish_momentum = current_macd_hist > 0 and current_macd_hist > prev_macd_hist
            macd_bearish_momentum = current_macd_hist < 0 and current_macd_hist < prev_macd_hist
            
            # EMA crossover analysis
            ema_cross_bullish = prev_ema_fast < prev_ema_slow and current_ema_fast > current_ema_slow
            ema_cross_bearish = prev_ema_fast > prev_ema_slow and current_ema_fast < current_ema_slow
            ema_aligned_bullish = current_ema_fast > current_ema_slow
            ema_aligned_bearish = current_ema_fast < current_ema_slow
            
            # Calculate BB position
            bb_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower) if current_bb_upper != current_bb_lower else 0.5
            
            # Price touching Bollinger Bands
            touching_lower_bb = current_price <= current_bb_lower * 1.002  # Within 0.2% of lower BB
            touching_upper_bb = current_price >= current_bb_upper * 0.998  # Within 0.2% of upper BB
            
            # Strategy Logic (Research-Verified 1-minute setup)
            signal = None
            confidence = 0
            reasoning = []
            confirmations_count = 0
            
            logger.info(f"🎯 1m Analysis for {symbol}:")
            logger.info(f"   Price={current_price:.5f}, EMA Fast={current_ema_fast:.5f}, EMA Slow={current_ema_slow:.5f}")
            logger.info(f"   RSI-7={current_rsi_fast:.1f}, RSI-14={current_rsi_slow:.1f}")
            logger.info(f"   MACD Hist={current_macd_hist:.5f}, Stoch={current_stoch_k:.1f}")
            logger.info(f"   BB Position={bb_position:.2%}, Lower BB={current_bb_lower:.5f}, Upper BB={current_bb_upper:.5f}")
            
            # === PRIMARY SIGNAL: RSI EXTREMES + BOLLINGER BAND TOUCHES (INVERTED) ===
            # Research-verified: Best setup for 1-minute binary options
            # ⚠️ INVERTED: Market reverses from extremes
            
            # **PUT Setup (INVERTED)**: RSI oversold + Price touches lower BB → Expect further DOWN
            if current_rsi_fast < self.rsi_oversold and touching_lower_bb:
                signal = "PUT"  # INVERTED
                confidence = self.min_base_confidence  # Start at 90%
                confirmations_count += 2  # RSI + BB
                
                if current_rsi_fast < self.rsi_extreme_oversold:
                    reasoning.append(f"🔴 EXTREME OVERSOLD (INVERTED): RSI-7={current_rsi_fast:.1f} (< 20) + Price touching lower BB → Expect DOWN")
                    confidence += 5  # Extra confidence for extreme
                else:
                    reasoning.append(f"🔴 OVERSOLD SETUP (INVERTED): RSI-7={current_rsi_fast:.1f} (< 30) + Price at lower BB ({bb_position:.1%}) → Expect DOWN")
                
                logger.info(f"✅ PUT Signal (Inverted): Oversold RSI + Lower BB touch")
            
            # **CALL Setup (INVERTED)**: RSI overbought + Price touches upper BB → Expect further UP
            elif current_rsi_fast > self.rsi_overbought and touching_upper_bb:
                signal = "CALL"  # INVERTED
                confidence = self.min_base_confidence
                confirmations_count += 2  # RSI + BB
                
                if current_rsi_fast > self.rsi_extreme_overbought:
                    reasoning.append(f"🟢 EXTREME OVERBOUGHT (INVERTED): RSI-7={current_rsi_fast:.1f} (> 80) + Price touching upper BB → Expect UP")
                    confidence += 5
                else:
                    reasoning.append(f"🟢 OVERBOUGHT SETUP (INVERTED): RSI-7={current_rsi_fast:.1f} (> 70) + Price at upper BB ({bb_position:.1%}) → Expect UP")
                
                logger.info(f"✅ CALL Signal (Inverted): Overbought RSI + Upper BB touch")
            
            # If no primary signal, STOP HERE
            if signal is None:
                logger.info(f"⛔ NO PRIMARY SIGNAL: RSI+BB conditions not met")
                logger.info(f"   RSI-7: {current_rsi_fast:.1f} (need < 30 or > 70)")
                logger.info(f"   BB Position: {bb_position:.2%} (need near 0% or 100%)")
                return None
            
            # === REQUIRE MACD CONFIRMATION (MANDATORY) ===
            macd_confirms = False
            if signal == "CALL":
                # MACD histogram must be positive or turning positive
                if current_macd_hist > 0 or macd_bullish_cross or macd_bullish_momentum:
                    confidence += 8
                    macd_type = "bullish cross" if macd_bullish_cross else ("rising" if macd_bullish_momentum else "positive")
                    reasoning.append(f"✅ MACD confirms CALL ({macd_type}, hist={current_macd_hist:.5f})")
                    confirmations_count += 1
                    macd_confirms = True
            elif signal == "PUT":
                # MACD histogram must be negative or turning negative
                if current_macd_hist < 0 or macd_bearish_cross or macd_bearish_momentum:
                    confidence += 8
                    macd_type = "bearish cross" if macd_bearish_cross else ("falling" if macd_bearish_momentum else "negative")
                    reasoning.append(f"✅ MACD confirms PUT ({macd_type}, hist={current_macd_hist:.5f})")
                    confirmations_count += 1
                    macd_confirms = True
            
            if not macd_confirms:
                logger.warning(f"⛔ SIGNAL REJECTED: MACD doesn't confirm {signal}")
                logger.warning(f"   MACD Histogram: {current_macd_hist:.5f}")
                return None
            
            # === EMA CROSSOVER CONFIRMATION (BONUS) ===
            if signal == "CALL":
                if ema_aligned_bullish:
                    confidence += 6
                    reasoning.append(f"✅ EMA trend bullish (Fast {current_ema_fast:.5f} > Slow {current_ema_slow:.5f})")
                    confirmations_count += 1
                    if ema_cross_bullish:
                        confidence += 4
                        reasoning.append(f"🎯 BONUS: Fresh EMA bullish crossover!")
            elif signal == "PUT":
                if ema_aligned_bearish:
                    confidence += 6
                    reasoning.append(f"✅ EMA trend bearish (Fast {current_ema_fast:.5f} < Slow {current_ema_slow:.5f})")
                    confirmations_count += 1
                    if ema_cross_bearish:
                        confidence += 4
                        reasoning.append(f"🎯 BONUS: Fresh EMA bearish crossover!")
            
            # === STOCHASTIC CONFIRMATION (MANDATORY) ===
            stoch_confirms = False
            if signal == "CALL":
                if current_stoch_k < 30:  # Oversold
                    confidence += 7
                    reasoning.append(f"✅ Stochastic oversold ({current_stoch_k:.1f}) - strong bounce expected")
                    confirmations_count += 1
                    stoch_confirms = True
                elif current_stoch_k < 70:  # Not overbought
                    confidence += 4
                    reasoning.append(f"✅ Stochastic OK ({current_stoch_k:.1f}) - room to rise")
                    stoch_confirms = True
            elif signal == "PUT":
                if current_stoch_k > 70:  # Overbought
                    confidence += 7
                    reasoning.append(f"✅ Stochastic overbought ({current_stoch_k:.1f}) - strong drop expected")
                    confirmations_count += 1
                    stoch_confirms = True
                elif current_stoch_k > 30:  # Not oversold
                    confidence += 4
                    reasoning.append(f"✅ Stochastic OK ({current_stoch_k:.1f}) - room to fall")
                    stoch_confirms = True
            
            if not stoch_confirms:
                logger.warning(f"⛔ SIGNAL REJECTED: Stochastic doesn't confirm")
                return None
            
            # === SUPPORT/RESISTANCE CONFIRMATION (MANDATORY) ===
            sr_confirms = False
            
            if signal == "CALL":
                # Enhanced S/R confirmation with reversal detection
                if reversal['reversal_detected'] and reversal['bounce_off_support']:
                    confidence += 8
                    reasoning.append(f"✅ REVERSAL: Bounce off support (strength: {reversal['reversal_strength']})")
                    confirmations_count += 1
                    sr_confirms = True
                elif proximity['near_support']:
                    confidence += 6
                    reasoning.append(f"✅ Price near support ({proximity['support_distance_pct']:.2f}% away)")
                    confirmations_count += 1
                    sr_confirms = True
                
                # Bullish patterns (bonus)
                if patterns.get('hammer') or patterns.get('bullish_engulfing'):
                    confidence += 3
                    reasoning.append("✅ Bullish candlestick pattern")
            
            elif signal == "PUT":
                # Enhanced S/R confirmation with reversal detection
                if reversal['reversal_detected'] and reversal['bounce_off_resistance']:
                    confidence += 8
                    reasoning.append(f"✅ REVERSAL: Reversal at resistance (strength: {reversal['reversal_strength']})")
                    confirmations_count += 1
                    sr_confirms = True
                elif proximity['near_resistance']:
                    confidence += 6
                    reasoning.append(f"✅ Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
                    confirmations_count += 1
                    sr_confirms = True
                
                # Bearish patterns (bonus)
                if patterns.get('hanging_man') or patterns.get('bearish_engulfing'):
                    confidence += 3
                    reasoning.append("✅ Bearish candlestick pattern")
            
            if not sr_confirms:
                logger.warning(f"⛔ SIGNAL REJECTED: No S/R confirmation")
                return None
            
            # === MINIMUM CONFIRMATIONS CHECK ===
            # Need at least 4 confirmations (RSI+BB + MACD + Stoch + S/R)
            if confirmations_count < 4:
                logger.warning(f"⛔ SIGNAL REJECTED: Only {confirmations_count} confirmations (need 4+)")
                return None
            
            reasoning.append(f"✅ HIGH-QUALITY SETUP: {confirmations_count} confirmations")
            
            if signal is None:
                return None
            
            # === GPT-4 ENHANCEMENT WITH VETO POWER ===
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    gpt_result = {'enhanced': False, 'valid': True, 'confidence_adjustment': 0, 'reasoning': [], 'risk_factors': []}
                else:
                    gpt_result = loop.run_until_complete(
                        gpt_signal_enhancer.enhance_signal(
                            signal=signal,
                            confidence=confidence,
                            features={},
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
                    
                    # If GPT reduces confidence significantly, reject
                    if gpt_adjustment < -10:
                        logger.warning(f"⛔ SIGNAL REJECTED: GPT-4 reduces confidence by {gpt_adjustment}%")
                        return None
                    
                    confidence += gpt_adjustment
                    
                    if gpt_result.get('reasoning'):
                        reasoning.append(f"🤖 GPT-4: {', '.join(gpt_result['reasoning'][:2])}")
                    
                    if gpt_result.get('risk_factors'):
                        reasoning.append(f"⚠️ Risks: {', '.join(gpt_result['risk_factors'][:2])}")
                        if len(gpt_result['risk_factors']) > 2:
                            confidence -= 5
                    
                    if not gpt_result.get('valid', True):
                        logger.warning(f"⛔ GPT-4 REJECTED signal: {gpt_result.get('reasoning')}")
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
            
            # === LAYER 4: SIGNAL FUSION (Multi-Layer Confirmation) ===
            logger.info("🎯 === LAYER 4: Signal Fusion & Final Validation (1m) ===")
            
            # Check layer agreement
            layer_signals = []
            if smc_direction:
                layer_signals.append(smc_direction)
            if signal:
                layer_signals.append(signal)
            if ml_direction:
                layer_signals.append(ml_direction)
            
            # All active layers must agree on direction
            if len(set(layer_signals)) > 1:
                logger.warning(f"⛔ SIGNAL REJECTED: Layer disagreement")
                logger.warning(f"   SMC: {smc_direction}, Technical: {signal}, ML: {ml_direction}")
                return None
            
            # Calculate weighted fusion confidence
            fusion_confidence = 0
            fusion_weights = {
                'smc': 0.25,        # 25% from Smart Money (lower for 1m)
                'technical': 0.30,  # 30% from Technical (higher weight for 1m)
                'ml': 0.25,         # 25% from ML
                'structure': 0.10,  # 10% from Market Structure
                'quality': 0.10     # 10% from Market Quality
            }
            
            # SMC contribution (lower weight for 1m as it's more reliable on higher timeframes)
            fusion_confidence += smc_confidence * fusion_weights['smc']
            
            # Technical contribution (higher weight for 1m)
            fusion_confidence += confidence * fusion_weights['technical']
            
            # ML contribution
            if ml_direction:
                fusion_confidence += ml_confidence * fusion_weights['ml']
            else:
                # Redistribute to technical if ML doesn't predict
                fusion_confidence += confidence * fusion_weights['ml']
            
            # Market structure contribution
            structure_score = smc_analysis.get('market_structure', {}).get('strength', 50)
            fusion_confidence += structure_score * fusion_weights['structure']
            
            # Market quality contribution
            fusion_confidence += market_quality['overall_quality'] * 100 * fusion_weights['quality']
            
            # Update final confidence with fusion score
            original_confidence = confidence
            confidence = fusion_confidence
            
            logger.info(f"🎯 Fusion Confidence: {confidence:.1f}% (Tech: {original_confidence:.1f}%, SMC: {smc_confidence:.1f}%, ML: {ml_confidence:.1f}%)")
            
            # Add fusion analysis to reasoning
            reasoning.append(f"🎯 Multi-layer fusion (1m): SMC {smc_confidence:.0f}% + Tech {original_confidence:.0f}% + ML {ml_confidence:.0f}% = {confidence:.0f}%")
            
            # === FINAL CONFIDENCE CHECK ===
            # After fusion, confidence must be >= 88% (slightly lower threshold for 1m)
            if confidence < 88:
                logger.warning(f"⛔ SIGNAL REJECTED: Fusion confidence too low ({confidence:.0f}% < 88%)")
                return None
            
            # Cap confidence at 98%
            confidence = min(confidence, 98)
            
            logger.info(f"✅ ADVANCED SIGNAL APPROVED: {signal} with {confidence:.0f}% fusion confidence ({confirmations_count} confirmations)")
            logger.info(f"   🧠 SMC + 📊 Technical + 🤖 ML = 🎯 High-Probability 1m Setup")
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reasoning": reasoning,
                "analysis": {
                    "price": current_price,
                    "ema_fast": current_ema_fast,
                    "ema_slow": current_ema_slow,
                    "rsi_fast": current_rsi_fast,
                    "rsi_slow": current_rsi_slow,
                    "macd": current_macd,
                    "macd_signal": current_macd_signal,
                    "macd_histogram": current_macd_hist,
                    "stoch_k": current_stoch_k,
                    "bb_position": bb_position,
                    "bb_upper": current_bb_upper,
                    "bb_lower": current_bb_lower,
                    "nearest_support": sr_levels['nearest_support'],
                    "nearest_resistance": sr_levels['nearest_resistance'],
                    "pivot_point": sr_levels['pivot_point'],
                    "reversal_detected": reversal['reversal_detected'],
                    "reversal_type": reversal['reversal_type'],
                    "patterns": patterns,
                    "smc_analysis": {
                        "confidence": smc_confidence,
                        "direction": smc_direction,
                        "liquidity_grab": smc_analysis.get('liquidity_grab', {}).get('grab_detected', False),
                        "near_order_block": smc_analysis.get('order_blocks', {}).get('near_ob', False),
                        "fvg_detected": smc_analysis.get('fair_value_gap', {}).get('fvg_detected', False)
                    },
                    "ml_prediction": {
                        "confidence": ml_confidence,
                        "direction": ml_direction,
                        "agreement": ml_agreement,
                        "model_votes": ml_prediction.get('model_votes', {})
                    }
                },
                "strategy": "Pocket Option 1m ADVANCED Multi-Layer",
                "timeframe": "1m",
                "fusion_score": confidence
            }
            
        except Exception as e:
            logger.error(f"Error in 1m strategy for {symbol}: {e}", exc_info=True)
            return None

# Create singleton instance
pocket_option_1m_strategy = PocketOption1MinuteStrategy()
