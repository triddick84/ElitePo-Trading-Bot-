"""
Holly Crossover Strategy
========================
Reversal crossover strategy using EMA(12) and WMA(23).

Platform: Pocket Option
Timeframes: 5s, 15s, 30s
Expiration: Matches timeframe

Indicators:
- Fast MA: 12 EMA (Exponential Moving Average)
- Slow MA: 23 WMA (Weighted Moving Average)
- Support/Resistance levels for confirmation

Entry Rules (REVERSAL crossover - catching trend reversals):
- CALL (Buy): EMA(12) crosses ABOVE WMA(23) during a downtrend (bullish reversal)
- PUT (Sell): EMA(12) crosses BELOW WMA(23) during an uptrend (bearish reversal)

Author: GPT Signal Bot
Version: 1.0.0
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TIMEFRAME_EXPIRY = {"5s": 5, "15s": 15, "30s": 30}


class HollyCrossoverStrategy:
    """
    Holly Crossover - Reversal strategy using EMA(12) x WMA(23).
    Catches trend reversals confirmed by support/resistance proximity.
    """

    def __init__(self, timeframe: str = "5s"):
        self.name = "Holly Crossover"
        self.timeframe = timeframe
        self.expiration = TIMEFRAME_EXPIRY.get(timeframe, 5)

        # MA settings
        self.ema_period = 12
        self.wma_period = 23

        # S/R settings
        self.sr_lookback = 50
        self.sr_tolerance_pct = 0.05  # 0.05% proximity to S/R counts as confirmation

        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = None

        logger.info(f"Holly Crossover [{self.timeframe}] initialized — EMA({self.ema_period}) x WMA({self.wma_period})")

    # ------------------------------------------------------------------
    # Indicator calculations
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_ema(closes: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        ema = np.full(len(closes), np.nan)
        if len(closes) < period:
            return ema
        ema[period - 1] = np.mean(closes[:period])
        k = 2.0 / (period + 1)
        for i in range(period, len(closes)):
            ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
        return ema

    @staticmethod
    def calculate_wma(closes: np.ndarray, period: int) -> np.ndarray:
        """Weighted Moving Average — recent prices weigh more."""
        wma = np.full(len(closes), np.nan)
        if len(closes) < period:
            return wma
        weights = np.arange(1, period + 1, dtype=float)
        weight_sum = weights.sum()
        for i in range(period - 1, len(closes)):
            wma[i] = np.dot(closes[i - period + 1: i + 1], weights) / weight_sum
        return wma

    # ------------------------------------------------------------------
    # Support / Resistance
    # ------------------------------------------------------------------

    def find_support_resistance(self, highs: np.ndarray, lows: np.ndarray,
                                closes: np.ndarray) -> Dict:
        """Detect nearest support & resistance from recent swing highs/lows."""
        n = len(closes)
        lookback = min(self.sr_lookback, n)
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        current = closes[-1]

        # Simple pivot-based S/R: local maxima → resistance, local minima → support
        resistance_levels = []
        support_levels = []

        for i in range(2, lookback - 2):
            # Swing high
            if (recent_highs[i] > recent_highs[i - 1] and
                    recent_highs[i] > recent_highs[i - 2] and
                    recent_highs[i] > recent_highs[i + 1] and
                    recent_highs[i] > recent_highs[i + 2]):
                resistance_levels.append(float(recent_highs[i]))
            # Swing low
            if (recent_lows[i] < recent_lows[i - 1] and
                    recent_lows[i] < recent_lows[i - 2] and
                    recent_lows[i] < recent_lows[i + 1] and
                    recent_lows[i] < recent_lows[i + 2]):
                support_levels.append(float(recent_lows[i]))

        nearest_support = None
        nearest_resistance = None

        if support_levels:
            below = [s for s in support_levels if s < current]
            if below:
                nearest_support = max(below)

        if resistance_levels:
            above = [r for r in resistance_levels if r > current]
            if above:
                nearest_resistance = min(above)

        at_support = (nearest_support is not None and
                      abs(current - nearest_support) / current * 100 < self.sr_tolerance_pct)
        at_resistance = (nearest_resistance is not None and
                         abs(nearest_resistance - current) / current * 100 < self.sr_tolerance_pct)

        return {
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "at_support": at_support,
            "at_resistance": at_resistance,
        }

    # ------------------------------------------------------------------
    # Trend detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_trend(closes: np.ndarray, lookback: int = 10) -> str:
        """Simple trend detection using slope of recent closes."""
        if len(closes) < lookback:
            return "neutral"
        recent = closes[-lookback:]
        x = np.arange(lookback)
        slope = np.polyfit(x, recent, 1)[0]
        threshold = np.std(recent) * 0.01
        if slope > threshold:
            return "uptrend"
        elif slope < -threshold:
            return "downtrend"
        return "neutral"

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def generate_signal(self, candles: List[Dict]) -> Optional[Dict]:
        min_candles = self.wma_period + 5
        if len(candles) < min_candles:
            return None

        closes = np.array([float(c["close"]) for c in candles])
        highs = np.array([float(c["high"]) for c in candles])
        lows = np.array([float(c["low"]) for c in candles])

        ema = self.calculate_ema(closes, self.ema_period)
        wma = self.calculate_wma(closes, self.wma_period)

        # Need at least 2 valid values to detect crossover
        if np.isnan(ema[-1]) or np.isnan(ema[-2]) or np.isnan(wma[-1]) or np.isnan(wma[-2]):
            return None

        ema_curr, ema_prev = float(ema[-1]), float(ema[-2])
        wma_curr, wma_prev = float(wma[-1]), float(wma[-2])

        # Crossover detection
        bullish_cross = ema_prev <= wma_prev and ema_curr > wma_curr  # EMA crosses above WMA
        bearish_cross = ema_prev >= wma_prev and ema_curr < wma_curr  # EMA crosses below WMA

        if not bullish_cross and not bearish_cross:
            return None

        trend = self.detect_trend(closes)
        sr = self.find_support_resistance(highs, lows, closes)

        direction = None
        confirmations = []
        confidence = 70  # base

        # CALL: bullish crossover during a DOWNTREND (reversal)
        if bullish_cross and trend == "downtrend":
            direction = "CALL"
            confirmations.append("ema12_crosses_above_wma23")
            confirmations.append("downtrend_reversal")

            if sr["at_support"]:
                confidence += 10
                confirmations.append("at_support")
            if sr["nearest_support"] is not None:
                confidence += 5
                confirmations.append("support_nearby")

        # PUT: bearish crossover during an UPTREND (reversal)
        elif bearish_cross and trend == "uptrend":
            direction = "PUT"
            confirmations.append("ema12_crosses_below_wma23")
            confirmations.append("uptrend_reversal")

            if sr["at_resistance"]:
                confidence += 10
                confirmations.append("at_resistance")
            if sr["nearest_resistance"] is not None:
                confidence += 5
                confirmations.append("resistance_nearby")

        if not direction:
            return None

        # Extra confidence: crossover strength (gap between EMA and WMA)
        cross_gap = abs(ema_curr - wma_curr)
        avg_price = closes[-1]
        gap_pct = (cross_gap / avg_price) * 100 if avg_price else 0
        if gap_pct > 0.01:
            confidence += 5
            confirmations.append("strong_crossover")

        confidence = min(confidence, 95)
        self.signals_generated += 1
        self.last_signal_time = datetime.now(timezone.utc)

        signal = {
            "direction": direction,
            "confidence": confidence,
            "strategy": f"{self.name} {self.timeframe}",
            "timeframe": self.timeframe,
            "expiration": self.expiration,
            "confirmations": confirmations,
            "indicators": {
                "ema12_current": round(ema_curr, 5),
                "ema12_previous": round(ema_prev, 5),
                "wma23_current": round(wma_curr, 5),
                "wma23_previous": round(wma_prev, 5),
                "trend": trend,
                "nearest_support": round(sr["nearest_support"], 5) if sr["nearest_support"] else None,
                "nearest_resistance": round(sr["nearest_resistance"], 5) if sr["nearest_resistance"] else None,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Holly Crossover [{self.timeframe}] {direction} @ {confidence}%  "
            f"EMA={ema_prev:.5f}->{ema_curr:.5f}  WMA={wma_prev:.5f}->{wma_curr:.5f}  trend={trend}"
        )
        return signal

    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "timeframe": self.timeframe,
            "expiration_seconds": self.expiration,
            "indicators": {
                "fast_ma": f"EMA({self.ema_period})",
                "slow_ma": f"WMA({self.wma_period})",
            },
            "entry_rules": {
                "call": "EMA(12) crosses above WMA(23) during downtrend + S/R confirmation",
                "put": "EMA(12) crosses below WMA(23) during uptrend + S/R confirmation",
            },
            "signals_generated": self.signals_generated,
            "last_signal": self.last_signal_time.isoformat() if self.last_signal_time else None,
        }


# Global instances — one per timeframe
holly_crossover_5s = HollyCrossoverStrategy("5s")
holly_crossover_15s = HollyCrossoverStrategy("15s")
holly_crossover_30s = HollyCrossoverStrategy("30s")


def get_holly_crossover_signal(candles: List[Dict], timeframe: str = "5s") -> Optional[Dict]:
    """Convenience function — picks the right instance by timeframe."""
    instances = {"5s": holly_crossover_5s, "15s": holly_crossover_15s, "30s": holly_crossover_30s}
    return instances.get(timeframe, holly_crossover_5s).generate_signal(candles)
