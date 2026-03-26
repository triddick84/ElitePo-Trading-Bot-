"""
Golden One Moment - 30 Second Strategy
=======================================
A precise mean reversion strategy using RSI(2) and Stochastic(4,3,3) crossovers.

Platform: Binomo / Pocket Option
Timeframe: 30 seconds
Expiration: 30 seconds

Indicators:
- RSI(2): Fast RSI for quick reversals
- Stochastic(4,3,3): Fast stochastic for momentum confirmation
- Overbought Level: 80
- Oversold Level: 20

Entry Rules:
- CALL Signal (Upward):
  * Previous candle: Both RSI and Stochastic below 20 (oversold)
  * Current candle: RSI crosses ABOVE 20 (reversal confirmation)
  
- PUT Signal (Downward):
  * Previous candle: Both RSI and Stochastic above 80 (overbought)
  * Current candle: RSI crosses BELOW 80 (reversal confirmation)

Author: GPT Signal Bot
Version: 1.0.0
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GoldenOneMomentStrategy:
    """
    Golden One Moment - 30 Second Mean Reversion Strategy.
    Uses RSI(2) + Stochastic(4,3,3) crossover for precise entry timing.
    """
    
    def __init__(self):
        self.name = "Golden One Moment"
        self.timeframe = "30s"
        self.expiration = 30  # seconds
        
        # Indicator settings
        self.rsi_period = 2
        self.stoch_k_period = 4
        self.stoch_k_slow = 3
        self.stoch_d_period = 3
        
        # Levels
        self.overbought = 80
        self.oversold = 20
        
        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = None
        
        logger.info(f"✨ {self.name} Strategy initialized")
        logger.info(f"   RSI({self.rsi_period}), Stochastic({self.stoch_k_period},{self.stoch_k_slow},{self.stoch_d_period})")
        logger.info(f"   Overbought: {self.overbought}, Oversold: {self.oversold}")
    
    def calculate_rsi(self, closes: np.ndarray, period: int = 2) -> np.ndarray:
        """
        Calculate RSI (Relative Strength Index).
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        if len(closes) < period + 1:
            return np.array([50.0])
        
        deltas = np.diff(closes)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate initial averages
        avg_gain = np.zeros(len(deltas))
        avg_loss = np.zeros(len(deltas))
        
        # First average is simple average
        avg_gain[period-1] = np.mean(gains[:period])
        avg_loss[period-1] = np.mean(losses[:period])
        
        # Subsequent averages use smoothing
        for i in range(period, len(deltas)):
            avg_gain[i] = (avg_gain[i-1] * (period-1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i-1] * (period-1) + losses[i]) / period
        
        # Calculate RS and RSI
        rs = np.divide(avg_gain, avg_loss, out=np.ones_like(avg_gain), where=avg_loss != 0)
        rsi = 100 - (100 / (1 + rs))
        
        # Prepend NaN for alignment
        rsi_full = np.concatenate([[np.nan], rsi])
        
        return rsi_full
    
    def calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                             k_period: int = 4, k_slow: int = 3, d_period: int = 3) -> Dict[str, np.ndarray]:
        """
        Calculate Stochastic Oscillator (K and D lines).
        
        %K = ((Close - Lowest Low) / (Highest High - Lowest Low)) * 100
        Slow %K = SMA(%K, k_slow)
        %D = SMA(Slow %K, d_period)
        """
        n = len(closes)
        if n < k_period:
            return {'k': np.array([50.0]), 'd': np.array([50.0])}
        
        # Calculate raw %K
        raw_k = np.zeros(n)
        for i in range(k_period - 1, n):
            highest_high = np.max(highs[i - k_period + 1:i + 1])
            lowest_low = np.min(lows[i - k_period + 1:i + 1])
            
            if highest_high != lowest_low:
                raw_k[i] = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
            else:
                raw_k[i] = 50.0
        
        # Calculate Slow %K (smooth the raw %K)
        slow_k = np.zeros(n)
        for i in range(k_period + k_slow - 2, n):
            slow_k[i] = np.mean(raw_k[i - k_slow + 1:i + 1])
        
        # Calculate %D (smooth the Slow %K)
        d = np.zeros(n)
        for i in range(k_period + k_slow + d_period - 3, n):
            d[i] = np.mean(slow_k[i - d_period + 1:i + 1])
        
        return {'k': slow_k, 'd': d}
    
    def check_call_signal(self, rsi_prev: float, rsi_curr: float, 
                          stoch_k_prev: float, stoch_d_prev: float) -> bool:
        """
        Check for CALL signal (upward direction).
        
        Conditions:
        1. Previous candle: Both RSI and Stochastic below oversold (20)
        2. Current candle: RSI crosses above oversold line
        """
        # Previous candle - both indicators oversold
        prev_oversold = (rsi_prev < self.oversold and 
                        stoch_k_prev < self.oversold)
        
        # Current candle - RSI crosses above oversold
        rsi_crossover = rsi_prev < self.oversold and rsi_curr >= self.oversold
        
        return prev_oversold and rsi_crossover
    
    def check_put_signal(self, rsi_prev: float, rsi_curr: float,
                         stoch_k_prev: float, stoch_d_prev: float) -> bool:
        """
        Check for PUT signal (downward direction).
        
        Conditions:
        1. Previous candle: Both RSI and Stochastic above overbought (80)
        2. Current candle: RSI crosses below overbought line
        """
        # Previous candle - both indicators overbought
        prev_overbought = (rsi_prev > self.overbought and 
                          stoch_k_prev > self.overbought)
        
        # Current candle - RSI crosses below overbought
        rsi_crossover = rsi_prev > self.overbought and rsi_curr <= self.overbought
        
        return prev_overbought and rsi_crossover
    
    def calculate_confidence(self, rsi_curr: float, stoch_k_curr: float, 
                            stoch_d_curr: float, direction: str) -> int:
        """Calculate signal confidence based on indicator alignment."""
        confidence = 70  # Base confidence for valid signal
        
        if direction == "CALL":
            # Stronger signal if both indicators are recovering together
            if stoch_k_curr > stoch_d_curr:  # Bullish stochastic crossover
                confidence += 10
            
            # RSI showing momentum
            if rsi_curr > 25 and rsi_curr < 40:
                confidence += 5
            
            # Stochastic also crossing up
            if stoch_k_curr >= self.oversold:
                confidence += 5
                
        elif direction == "PUT":
            # Stronger signal if both indicators are declining together
            if stoch_k_curr < stoch_d_curr:  # Bearish stochastic crossover
                confidence += 10
            
            # RSI showing momentum
            if rsi_curr < 75 and rsi_curr > 60:
                confidence += 5
            
            # Stochastic also crossing down
            if stoch_k_curr <= self.overbought:
                confidence += 5
        
        return min(confidence, 95)
    
    def generate_signal(self, candles: List[Dict]) -> Optional[Dict]:
        """
        Generate trading signal based on Golden One Moment strategy.
        
        Args:
            candles: List of candle dictionaries with 'open', 'high', 'low', 'close'
        
        Returns:
            Signal dictionary or None if no signal
        """
        min_candles = max(self.rsi_period, self.stoch_k_period + self.stoch_k_slow + self.stoch_d_period) + 5
        
        if len(candles) < min_candles:
            logger.debug(f"Insufficient candles: {len(candles)} < {min_candles}")
            return None
        
        # Extract price data
        closes = np.array([c['close'] for c in candles], dtype=float)
        highs = np.array([c['high'] for c in candles], dtype=float)
        lows = np.array([c['low'] for c in candles], dtype=float)
        
        # Calculate indicators
        rsi = self.calculate_rsi(closes, self.rsi_period)
        stoch = self.calculate_stochastic(highs, lows, closes, 
                                          self.stoch_k_period, self.stoch_k_slow, self.stoch_d_period)
        
        # Get current and previous values
        rsi_curr = rsi[-1] if not np.isnan(rsi[-1]) else 50
        rsi_prev = rsi[-2] if len(rsi) > 1 and not np.isnan(rsi[-2]) else 50
        
        stoch_k_curr = stoch['k'][-1] if stoch['k'][-1] != 0 else 50
        stoch_k_prev = stoch['k'][-2] if len(stoch['k']) > 1 and stoch['k'][-2] != 0 else 50
        stoch_d_curr = stoch['d'][-1] if stoch['d'][-1] != 0 else 50
        stoch_d_prev = stoch['d'][-2] if len(stoch['d']) > 1 and stoch['d'][-2] != 0 else 50
        
        signal = None
        direction = None
        confirmations = []
        
        # Check for CALL signal
        if self.check_call_signal(rsi_prev, rsi_curr, stoch_k_prev, stoch_d_prev):
            direction = "CALL"
            confirmations.append("rsi_oversold_crossover")
            confirmations.append("stoch_oversold")
            
            if stoch_k_curr > stoch_d_curr:
                confirmations.append("stoch_bullish_cross")
            
        # Check for PUT signal
        elif self.check_put_signal(rsi_prev, rsi_curr, stoch_k_prev, stoch_d_prev):
            direction = "PUT"
            confirmations.append("rsi_overbought_crossover")
            confirmations.append("stoch_overbought")
            
            if stoch_k_curr < stoch_d_curr:
                confirmations.append("stoch_bearish_cross")
        
        # Generate signal if direction found
        if direction:
            confidence = self.calculate_confidence(rsi_curr, stoch_k_curr, stoch_d_curr, direction)
            
            self.signals_generated += 1
            self.last_signal_time = datetime.now(timezone.utc)
            
            signal = {
                "direction": direction,
                "confidence": confidence,
                "strategy": self.name,
                "timeframe": self.timeframe,
                "expiration": self.expiration,
                "confirmations": confirmations,
                "indicators": {
                    "rsi_current": round(rsi_curr, 2),
                    "rsi_previous": round(rsi_prev, 2),
                    "stoch_k": round(stoch_k_curr, 2),
                    "stoch_d": round(stoch_d_curr, 2),
                    "stoch_k_prev": round(stoch_k_prev, 2)
                },
                "levels": {
                    "overbought": self.overbought,
                    "oversold": self.oversold
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"✨ {self.name} Signal: {direction} @ {confidence}%")
            logger.info(f"   RSI: {rsi_prev:.1f} → {rsi_curr:.1f}, Stoch K: {stoch_k_prev:.1f} → {stoch_k_curr:.1f}")
        
        return signal
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "timeframe": self.timeframe,
            "expiration_seconds": self.expiration,
            "indicators": {
                "rsi_period": self.rsi_period,
                "stochastic": f"({self.stoch_k_period},{self.stoch_k_slow},{self.stoch_d_period})"
            },
            "levels": {
                "overbought": self.overbought,
                "oversold": self.oversold
            },
            "signals_generated": self.signals_generated,
            "last_signal": self.last_signal_time.isoformat() if self.last_signal_time else None
        }


# Global instance
golden_one_moment = GoldenOneMomentStrategy()


def get_golden_one_moment_signal(candles: List[Dict]) -> Optional[Dict]:
    """Convenience function to get signal from global instance."""
    return golden_one_moment.generate_signal(candles)
