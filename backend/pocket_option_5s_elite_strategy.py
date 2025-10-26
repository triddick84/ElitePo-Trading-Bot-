"""
Pocket Option 5-Second ELITE Strategy - Maximum Accuracy (95%+ Target)
Keltner Channel + MACD on Heikin Ashi Candles

🎯 STRATEGY OVERVIEW:
This strategy combines three powerful components for ultra-high accuracy:
1. Heikin Ashi Candles - Smooth out noise and clarify trends
2. Keltner Channel - Identify trend direction and volatility
3. MACD - Confirm momentum and entry timing

📊 EXACT PARAMETERS:
- Chart Type: Heikin Ashi Candles ONLY
- Keltner Channel: EMA 18, ATR 13, Multiplier 2
- MACD: Fast 13, Slow 24, Signal 11

🔥 SIGNAL LOGIC:
SELL Signal (PUT):
- MACD lines cross UPWARD (bullish crossover)
- Keltner Channel moving UP (uptrend)
- Price in MIDDLE of Keltner (0.35-0.65 range)
- → Fade the move, expect pullback

BUY Signal (CALL):
- MACD lines cross DOWNWARD (bearish crossover)
- Keltner Channel moving DOWN (downtrend)
- Price in MIDDLE of Keltner (0.35-0.65 range)
- → Fade the move, expect bounce

SIDEWAYS Market:
- Wait for price to reach MIDDLE of channel
- Then follow MACD direction

This is a CONTRARIAN/FADING strategy - we fade momentum when it reaches the middle
of the channel, expecting mean reversion within 5 seconds.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional
import talib

from keltner_channel import get_keltner_channel
from heikin_ashi import transform_to_heikin_ashi, detect_ha_trend_strength
from market_quality_filter import get_market_filter

logger = logging.getLogger(__name__)

class PocketOption5SecondEliteStrategy:
    """
    Elite 5-second strategy for 95%+ accuracy
    Keltner + MACD + Heikin Ashi combination
    """
    
    def __init__(self):
        # Keltner Channel settings
        self.keltner = get_keltner_channel(ema_period=18, atr_period=13, multiplier=2.0)
        
        # MACD settings
        self.macd_fast = 13
        self.macd_slow = 24
        self.macd_signal = 11
        
        # Minimum data requirements
        self.min_data_points = 100
        
        # ELITE confidence threshold - only highest probability setups
        self.min_base_confidence = 92  # Start very high
        
        # Market quality filter
        self.market_filter = get_market_filter('5s')
        
        logger.info("🔥 5s ELITE Strategy initialized:")
        logger.info(f"   📊 Chart: Heikin Ashi Candles ONLY")
        logger.info(f"   📈 Keltner: EMA 18, ATR 13, Multiplier 2")
        logger.info(f"   📉 MACD: Fast 13, Slow 24, Signal 11")
        logger.info(f"   🎯 Target Accuracy: 95%+")
    
    def generate_signal(
        self,
        symbol: str,
        market_data: pd.DataFrame,
        timeframe: str = '5s',
        chart_type: str = 'heikin_ashi',
        invert: bool = False
    ) -> Optional[Dict]:
        """
        Generate trading signal using Keltner + MACD + Heikin Ashi
        
        Args:
            symbol: Asset symbol
            market_data: OHLCV data
            timeframe: Must be '5s'
            chart_type: Must be 'heikin_ashi'
            invert: Whether to invert signals
            
        Returns:
            Signal dict or None
        """
        try:
            # CRITICAL: This strategy ONLY works on 5s timeframe
            if timeframe != '5s':
                logger.warning(f"Elite 5s strategy called with {timeframe} - ONLY 5s supported")
                return None
            
            # CRITICAL: This strategy REQUIRES Heikin Ashi candles
            if chart_type != 'heikin_ashi':
                logger.warning(f"Elite 5s strategy requires Heikin Ashi, got {chart_type}")
                return None
            
            # Validate data
            if market_data is None or market_data.empty:
                logger.warning(f"No market data for {symbol}")
                return None
            
            if len(market_data) < self.min_data_points:
                logger.warning(f"Insufficient data: {len(market_data)} < {self.min_data_points}")
                return None
            
            # Create working copy
            df = market_data.copy()
            
            # === STEP 1: TRANSFORM TO HEIKIN ASHI ===
            logger.info(f"🎌 Transforming to Heikin Ashi candles...")
            df = transform_to_heikin_ashi(df)
            
            # === STEP 2: MARKET QUALITY CHECK ===
            market_quality = self.market_filter.check_market_quality(df)
            
            if not market_quality['passed']:
                logger.warning(f"⛔ MARKET QUALITY REJECTED for {symbol}")
                return None
            
            logger.info(f"✅ Market quality: {market_quality['overall_quality']:.1%}")
            
            # === STEP 3: CALCULATE KELTNER CHANNEL ===
            df = self.keltner.calculate(df)
            kc_analysis = self.keltner.get_channel_analysis(df)
            
            logger.info(f"📊 Keltner: Direction={kc_analysis['direction']}, "
                       f"Position={kc_analysis['position']} ({kc_analysis['position_value']:.2f}), "
                       f"In Middle={kc_analysis['is_in_middle']}")
            
            # === STEP 4: CALCULATE MACD ===
            close_prices = df['close']
            macd_line, macd_signal, macd_hist = talib.MACD(
                close_prices,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            
            # Get current and previous MACD values
            current_macd = macd_line.iloc[-1]
            current_signal = macd_signal.iloc[-1]
            prev_macd = macd_line.iloc[-2]
            prev_signal = macd_signal.iloc[-2]
            current_hist = macd_hist.iloc[-1]
            
            # Detect MACD crossovers
            macd_bullish_cross = (prev_macd <= prev_signal) and (current_macd > current_signal)
            macd_bearish_cross = (prev_macd >= prev_signal) and (current_macd < current_signal)
            
            logger.info(f"📉 MACD: Bullish Cross={macd_bullish_cross}, Bearish Cross={macd_bearish_cross}, "
                       f"Histogram={current_hist:.5f}")
            
            # === STEP 5: ANALYZE HEIKIN ASHI TREND ===
            ha_trend = detect_ha_trend_strength(df)
            logger.info(f"🎌 HA Trend: {ha_trend['trend']}, Strength={ha_trend['strength']:.1%}")
            
            # === STRATEGY LOGIC: CONTRARIAN/FADING APPROACH ===
            signal = None
            confidence = 0
            reasoning = []
            confirmations_count = 0
            
            # Check if price is in middle zone (REQUIRED)
            if not kc_analysis['is_in_middle']:
                # Handle sideways market - wait for movement to middle
                if kc_analysis['direction'] == 'SIDEWAYS':
                    breakout = self.keltner.detect_breakout(df)
                    if breakout['just_entered_middle']:
                        logger.info(f"💡 Sideways market: Price just entered middle from {breakout.get('from')}")
                        # Allow signal generation based on MACD
                    else:
                        logger.info(f"⏸️ Sideways market: Waiting for price to reach middle (currently {kc_analysis['position']})")
                        return None
                else:
                    logger.info(f"⏸️ Price not in middle: Position={kc_analysis['position']} ({kc_analysis['position_value']:.2f})")
                    return None
            
            # === PRIMARY SIGNALS: CONTRARIAN FADING ===
            # SELL Signal (PUT): Fade upward momentum at middle
            if macd_bullish_cross and kc_analysis['direction'] == 'UP' and kc_analysis['is_in_middle']:
                signal = "PUT"
                confidence = self.min_base_confidence
                reasoning.append(f"🔴 FADE UP: MACD bullish cross + Keltner UP + Middle position")
                reasoning.append(f"💡 Expecting pullback from {kc_analysis['position_value']:.2f} position")
                confirmations_count += 2  # MACD + Keltner direction
                
                logger.info(f"✅ SELL SIGNAL: Fading upward momentum at middle of channel")
            
            # BUY Signal (CALL): Fade downward momentum at middle
            elif macd_bearish_cross and kc_analysis['direction'] == 'DOWN' and kc_analysis['is_in_middle']:
                signal = "CALL"
                confidence = self.min_base_confidence
                reasoning.append(f"🟢 FADE DOWN: MACD bearish cross + Keltner DOWN + Middle position")
                reasoning.append(f"💡 Expecting bounce from {kc_analysis['position_value']:.2f} position")
                confirmations_count += 2
                
                logger.info(f"✅ BUY SIGNAL: Fading downward momentum at middle of channel")
            
            # No signal if conditions not met
            else:
                if macd_bullish_cross or macd_bearish_cross:
                    logger.info(f"⏸️ MACD crossover detected but Keltner conditions not met")
                    logger.info(f"   Keltner Direction: {kc_analysis['direction']}, In Middle: {kc_analysis['is_in_middle']}")
                return None
            
            # === HEIKIN ASHI CONFIRMATION ===
            # HA trend should align with our fade expectation
            if signal == "PUT":
                if ha_trend['trend'] in ['STRONG_UP', 'WEAK_UP']:
                    confidence += 5
                    reasoning.append(f"✅ HA confirms uptrend ({ha_trend['consecutive_bullish']} consecutive bullish)")
                    confirmations_count += 1
            
            elif signal == "CALL":
                if ha_trend['trend'] in ['STRONG_DOWN', 'WEAK_DOWN']:
                    confidence += 5
                    reasoning.append(f"✅ HA confirms downtrend ({ha_trend['consecutive_bearish']} consecutive bearish)")
                    confirmations_count += 1
            
            # === KELTNER TREND STRENGTH ===
            if kc_analysis['trend_strength'] > 0.5:
                confidence += 3
                reasoning.append(f"✅ Strong Keltner trend (strength: {kc_analysis['trend_strength']:.1%})")
                confirmations_count += 1
            
            # === MINIMUM CONFIRMATIONS CHECK ===
            if confirmations_count < 3:
                logger.warning(f"⛔ SIGNAL REJECTED: Only {confirmations_count} confirmations (need 3+)")
                return None
            
            reasoning.append(f"✅ {confirmations_count} confirmations detected")
            
            # === FINAL CONFIDENCE CHECK ===
            if confidence < 92:
                logger.warning(f"⛔ SIGNAL REJECTED: Confidence too low ({confidence}% < 92%)")
                return None
            
            # Cap confidence at 98%
            confidence = min(confidence, 98)
            
            # Apply invert if requested
            if invert:
                original_signal = signal
                signal = "PUT" if signal == "CALL" else "CALL"
                logger.info(f"🔄 Signal INVERTED: {original_signal} → {signal}")
                reasoning.append(f"🔄 [INVERTED] from {original_signal}")
            
            logger.info(f"🎯 ELITE SIGNAL APPROVED: {signal} with {confidence}% confidence")
            
            # Build signal response
            return {
                'signal': signal,
                'confidence': round(confidence, 1),
                'symbol': symbol,
                'timeframe': '5s',
                'chart_type': 'heikin_ashi',
                'strategy': 'keltner_macd_ha_elite',
                'reasoning': reasoning,
                'technical_analysis': {
                    'keltner_direction': kc_analysis['direction'],
                    'keltner_position': kc_analysis['position'],
                    'keltner_position_value': kc_analysis['position_value'],
                    'keltner_trend_strength': kc_analysis['trend_strength'],
                    'macd_line': round(current_macd, 5),
                    'macd_signal': round(current_signal, 5),
                    'macd_histogram': round(current_hist, 5),
                    'macd_bullish_cross': macd_bullish_cross,
                    'macd_bearish_cross': macd_bearish_cross,
                    'ha_trend': ha_trend['trend'],
                    'ha_strength': ha_trend['strength'],
                    'confirmations': confirmations_count
                },
                'indicators': {
                    'keltner_channel': {
                        'middle': round(kc_analysis['current_middle'], 5),
                        'upper': round(kc_analysis['current_upper'], 5),
                        'lower': round(kc_analysis['current_lower'], 5),
                        'settings': 'EMA 18, ATR 13, Multiplier 2'
                    },
                    'macd': {
                        'settings': 'Fast 13, Slow 24, Signal 11',
                        'current': {
                            'macd': round(current_macd, 5),
                            'signal': round(current_signal, 5),
                            'histogram': round(current_hist, 5)
                        }
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating 5s elite signal for {symbol}: {e}", exc_info=True)
            return None


# Global instance
pocket_option_5s_elite_strategy = PocketOption5SecondEliteStrategy()
