"""
EMA 20 Pullback Reversal Strategy - 5 Second Timeframe
Accuracy Target: 80-90%

Optimized for Pocket Option 5-second Quick Trading mode.

Key Settings:
- EMA 20: Primary trend filter
- RSI 2: Ultra-fast momentum confirmation
- Bollinger Bands (5, 2.5): Tight volatility bands for reversal zones
- Stochastic (3, 1, 1): Overbought/oversold crossovers

Entry Rules:
CALL: Price above EMA 20 (uptrend) -> pullback touches EMA 20 or lower BB -> bounce up
      Confirm RSI 2 crossing above 20 or in 50-70 range. Stochastic oversold cross.
PUT:  Price below EMA 20 (downtrend) -> pullback touches EMA 20 or upper BB -> reject down
      Confirm RSI 2 crossing below 80 or in 30-50 range. Stochastic overbought cross.

High-probability filters:
- S/R bounce with volume/tick rejection
- Tight range breakout after compression
- RSI divergence
- First reversal after momentum spike

Assets: EUR/JPY_OTC, EUR/USD_OTC, GBP/USD_OTC, AUD/CAD_OTC, AUD/USD_OTC
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class EMA20PullbackReversalStrategy:
    def __init__(self):
        self.name = "EMA 20 Pullback Reversal"
        self.timeframe = "5s"
        self.accuracy_target = 85.0

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate signal from DataFrame with OHLCV columns"""
        try:
            if df is None or len(df) < 30:
                return self._neutral("Insufficient data (need 30+ candles)")

            closes = df['close'].values.astype(float)
            highs = df['high'].values.astype(float)
            lows = df['low'].values.astype(float)
            opens = df['open'].values.astype(float)

            # === Core Indicators ===
            ema20 = self._ema(closes, 20)
            rsi2 = self._rsi(closes, 2)
            bb_upper, bb_middle, bb_lower = self._bollinger(closes, 5, 2.5)
            stoch_k, stoch_d = self._stochastic(highs, lows, closes, 3, 1, 1)

            current_price = closes[-1]
            prev_price = closes[-2]
            prev2_price = closes[-3]

            # === Trend Detection (EMA 20) ===
            # Count candles above/below EMA 20 in last 10 bars
            above_ema_count = sum(1 for i in range(-10, 0) if closes[i] > ema20[i])
            below_ema_count = 10 - above_ema_count

            is_uptrend = above_ema_count >= 7 and current_price > ema20[-1]
            is_downtrend = below_ema_count >= 7 and current_price < ema20[-1]

            # === Pullback Detection ===
            # Uptrend pullback: price recently dipped to touch EMA 20 or lower BB
            pullback_to_ema_bull = False
            pullback_to_bb_lower = False
            for i in range(-3, 0):
                if lows[i] <= ema20[i] * 1.0005:  # Touched EMA within 0.05%
                    pullback_to_ema_bull = True
                if lows[i] <= bb_lower[i] * 1.001:
                    pullback_to_bb_lower = True

            # Downtrend pullback: price recently spiked to touch EMA 20 or upper BB
            pullback_to_ema_bear = False
            pullback_to_bb_upper = False
            for i in range(-3, 0):
                if highs[i] >= ema20[i] * 0.9995:
                    pullback_to_ema_bear = True
                if highs[i] >= bb_upper[i] * 0.999:
                    pullback_to_bb_upper = True

            # === Bounce Detection ===
            # Bounce up: current candle closes above previous candle's high
            bounce_up = (current_price > prev_price and
                         closes[-1] > opens[-1] and
                         current_price > highs[-2])

            # Bounce down: current candle closes below previous candle's low
            bounce_down = (current_price < prev_price and
                           closes[-1] < opens[-1] and
                           current_price < lows[-2])

            # === RSI 2 Confirmation ===
            rsi2_bull = rsi2[-1] > 20 and rsi2[-2] <= 20  # Crossing above 20
            rsi2_bull_zone = 50 <= rsi2[-1] <= 70  # In bullish zone
            rsi2_bear = rsi2[-1] < 80 and rsi2[-2] >= 80  # Crossing below 80
            rsi2_bear_zone = 30 <= rsi2[-1] <= 50  # In bearish zone

            # === Stochastic Confirmation ===
            stoch_bull_cross = stoch_k[-1] > stoch_d[-1] and stoch_k[-2] <= stoch_d[-2]
            stoch_bear_cross = stoch_k[-1] < stoch_d[-1] and stoch_k[-2] >= stoch_d[-2]
            stoch_oversold = stoch_k[-1] < 25
            stoch_overbought = stoch_k[-1] > 75

            # === S/R Detection (simple) ===
            recent_lows = lows[-20:]
            recent_highs = highs[-20:]
            support_level = np.percentile(recent_lows, 10)
            resistance_level = np.percentile(recent_highs, 90)

            near_support = abs(current_price - support_level) / current_price < 0.001
            near_resistance = abs(current_price - resistance_level) / current_price < 0.001

            # === Compression Detection ===
            bb_width = (bb_upper[-1] - bb_lower[-1]) / bb_middle[-1] * 100
            is_compressed = bb_width < 0.15  # Tight Bollinger Bands

            # === RSI Divergence ===
            price_making_lower_low = lows[-1] < min(lows[-5:-1])
            rsi_making_higher_low = rsi2[-1] > min(rsi2[-5:-1])
            bullish_divergence = price_making_lower_low and rsi_making_higher_low

            price_making_higher_high = highs[-1] > max(highs[-5:-1])
            rsi_making_lower_high = rsi2[-1] < max(rsi2[-5:-1])
            bearish_divergence = price_making_higher_high and rsi_making_lower_high

            # === Volatility Filter ===
            avg_range = np.mean(highs[-10:] - lows[-10:])
            current_range = highs[-1] - lows[-1]
            volatility_ok = current_range < avg_range * 3.0  # Not too volatile

            # === Score Signals ===
            bull_score = 0
            bear_score = 0
            bull_reasons = []
            bear_reasons = []

            # CALL conditions
            if is_uptrend:
                bull_score += 2
                bull_reasons.append("Uptrend (EMA 20)")

                if pullback_to_ema_bull:
                    bull_score += 3
                    bull_reasons.append("Pullback touched EMA 20")
                if pullback_to_bb_lower:
                    bull_score += 2
                    bull_reasons.append("Pullback touched lower BB")
                if bounce_up:
                    bull_score += 2
                    bull_reasons.append("Bounce candle confirmed")
                if rsi2_bull:
                    bull_score += 2
                    bull_reasons.append("RSI-2 crossed above 20")
                elif rsi2_bull_zone:
                    bull_score += 1
                    bull_reasons.append("RSI-2 in bull zone (50-70)")
                if stoch_bull_cross or stoch_oversold:
                    bull_score += 1.5
                    bull_reasons.append("Stochastic bullish")
                if near_support:
                    bull_score += 2
                    bull_reasons.append("At support level")
                if bullish_divergence:
                    bull_score += 2
                    bull_reasons.append("Bullish RSI divergence")
                if is_compressed and bounce_up:
                    bull_score += 1.5
                    bull_reasons.append("Compression breakout up")

            # PUT conditions
            if is_downtrend:
                bear_score += 2
                bear_reasons.append("Downtrend (EMA 20)")

                if pullback_to_ema_bear:
                    bear_score += 3
                    bear_reasons.append("Pullback touched EMA 20")
                if pullback_to_bb_upper:
                    bear_score += 2
                    bear_reasons.append("Pullback touched upper BB")
                if bounce_down:
                    bear_score += 2
                    bear_reasons.append("Rejection candle confirmed")
                if rsi2_bear:
                    bear_score += 2
                    bear_reasons.append("RSI-2 crossed below 80")
                elif rsi2_bear_zone:
                    bear_score += 1
                    bear_reasons.append("RSI-2 in bear zone (30-50)")
                if stoch_bear_cross or stoch_overbought:
                    bear_score += 1.5
                    bear_reasons.append("Stochastic bearish")
                if near_resistance:
                    bear_score += 2
                    bear_reasons.append("At resistance level")
                if bearish_divergence:
                    bear_score += 2
                    bear_reasons.append("Bearish RSI divergence")
                if is_compressed and bounce_down:
                    bear_score += 1.5
                    bear_reasons.append("Compression breakout down")

            # Volatility penalty
            if not volatility_ok:
                bull_score *= 0.6
                bear_score *= 0.6

            # === Generate Signal ===
            min_score = 5.0  # Need at least trend + pullback + one confirmation

            if bull_score >= min_score and bull_score > bear_score + 2:
                confidence = min(95, 55 + bull_score * 4)
                return {
                    'direction': 'CALL',
                    'confidence': round(confidence, 1),
                    'reason': ' | '.join(bull_reasons),
                    'strategy': self.name,
                    'score': round(bull_score, 1),
                    'indicators': {
                        'ema20': round(ema20[-1], 5),
                        'rsi2': round(rsi2[-1], 1),
                        'bb_upper': round(bb_upper[-1], 5),
                        'bb_lower': round(bb_lower[-1], 5),
                        'stoch_k': round(stoch_k[-1], 1),
                        'bb_width': round(bb_width, 3),
                    }
                }

            if bear_score >= min_score and bear_score > bull_score + 2:
                confidence = min(95, 55 + bear_score * 4)
                return {
                    'direction': 'PUT',
                    'confidence': round(confidence, 1),
                    'reason': ' | '.join(bear_reasons),
                    'strategy': self.name,
                    'score': round(bear_score, 1),
                    'indicators': {
                        'ema20': round(ema20[-1], 5),
                        'rsi2': round(rsi2[-1], 1),
                        'bb_upper': round(bb_upper[-1], 5),
                        'bb_lower': round(bb_lower[-1], 5),
                        'stoch_k': round(stoch_k[-1], 1),
                        'bb_width': round(bb_width, 3),
                    }
                }

            return self._neutral("No clear pullback reversal setup")

        except Exception as e:
            logger.error(f"EMA 20 Pullback Reversal error: {e}")
            return self._neutral(f"Error: {str(e)}")

    def _neutral(self, reason: str) -> Dict:
        return {
            'direction': 'NEUTRAL',
            'confidence': 0,
            'reason': reason,
            'strategy': self.name,
        }

    def _ema(self, data, period):
        """Calculate EMA array"""
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        k = 2.0 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = data[i] * k + ema[i-1] * (1 - k)
        return ema

    def _rsi(self, prices, period):
        """Calculate RSI array"""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        rsi = np.full(len(prices), 50.0)
        if len(gains) < period:
            return rsi

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100 - (100 / (1 + rs))

        return rsi

    def _bollinger(self, prices, period, std_dev):
        """Calculate Bollinger Bands"""
        upper = np.zeros_like(prices, dtype=float)
        middle = np.zeros_like(prices, dtype=float)
        lower = np.zeros_like(prices, dtype=float)

        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window)
            middle[i] = mean
            upper[i] = mean + std_dev * std
            lower[i] = mean - std_dev * std

        # Fill early values
        for i in range(period - 1):
            middle[i] = prices[i]
            upper[i] = prices[i]
            lower[i] = prices[i]

        return upper, middle, lower

    def _stochastic(self, highs, lows, closes, k_period, d_period, slowing):
        """Calculate Stochastic Oscillator"""
        n = len(closes)
        k_values = np.full(n, 50.0)
        d_values = np.full(n, 50.0)

        for i in range(k_period - 1, n):
            highest = np.max(highs[i - k_period + 1:i + 1])
            lowest = np.min(lows[i - k_period + 1:i + 1])
            if highest != lowest:
                k_values[i] = ((closes[i] - lowest) / (highest - lowest)) * 100
            else:
                k_values[i] = 50.0

        # Smooth K with slowing period
        if slowing > 1:
            smoothed_k = np.full(n, 50.0)
            for i in range(slowing - 1, n):
                smoothed_k[i] = np.mean(k_values[i - slowing + 1:i + 1])
            k_values = smoothed_k

        # D line (SMA of K)
        for i in range(d_period - 1, n):
            d_values[i] = np.mean(k_values[i - d_period + 1:i + 1])

        return k_values, d_values


# Singleton instance
strategy_5s_ema20_pullback_reversal = EMA20PullbackReversalStrategy()
