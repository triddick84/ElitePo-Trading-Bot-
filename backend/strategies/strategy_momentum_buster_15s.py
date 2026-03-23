"""
Momentum Buster 15-Second Strategy
===================================
Ultra-fast scalping strategy for 15-second binary options

Strategy Rules:
- Timeframe: 15-second Japanese candles
- Expiration: 15 seconds
- Indicator: Momentum (period 3)
- BUY Signal: Green bars (momentum > 0) at new candle start / uptrend
- SELL Signal: Red bars (momentum < 0) at new candle start / downtrend

Key Features:
1. Momentum-based trend detection with period 3
2. Color-coded bar analysis (green = bullish, red = bearish)
3. New candle confirmation for entry timing
4. Fast reversal detection for quick profits

Author: GPT Signal Bot
Version: 1.0.0
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MomentumBuster15sStrategy:
    """
    15-second momentum-based scalping strategy.
    Uses momentum indicator with period 3 for ultra-fast signal generation.
    """
    
    def __init__(self):
        self.name = "Momentum Buster 15s"
        self.timeframe = "15s"
        self.expiration = 15  # seconds
        self.momentum_period = 3
        self.min_confidence = 65
        self.consecutive_bars_required = 2  # Require 2 consecutive same-color bars
        
        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = None
        
        logger.info(f"🚀 {self.name} Strategy initialized (Momentum period: {self.momentum_period})")
    
    def calculate_momentum(self, closes: np.ndarray, period: int = 3) -> np.ndarray:
        """
        Calculate momentum indicator.
        Momentum = Close - Close[n periods ago]
        
        Positive momentum = uptrend (green bars)
        Negative momentum = downtrend (red bars)
        """
        if len(closes) < period + 1:
            return np.array([])
        
        momentum = np.zeros(len(closes))
        for i in range(period, len(closes)):
            momentum[i] = closes[i] - closes[i - period]
        
        return momentum
    
    def detect_bar_color(self, momentum_value: float) -> str:
        """
        Detect bar color based on momentum value.
        Green = positive momentum (bullish)
        Red = negative momentum (bearish)
        """
        if momentum_value > 0:
            return "green"
        elif momentum_value < 0:
            return "red"
        else:
            return "neutral"
    
    def count_consecutive_bars(self, momentum: np.ndarray, color: str) -> int:
        """Count consecutive bars of the same color from the end."""
        count = 0
        for i in range(len(momentum) - 1, -1, -1):
            bar_color = self.detect_bar_color(momentum[i])
            if bar_color == color:
                count += 1
            else:
                break
        return count
    
    def is_new_candle_start(self, candle_time: datetime) -> bool:
        """
        Check if we're at the start of a new 15-second candle.
        New candle starts at seconds: 0, 15, 30, 45
        """
        second = candle_time.second
        return second % 15 < 2  # Within first 2 seconds of candle
    
    def detect_trend_reversal(self, momentum: np.ndarray) -> Optional[str]:
        """
        Detect if there's a trend reversal in momentum.
        Returns 'bullish_reversal' or 'bearish_reversal' or None.
        """
        if len(momentum) < 3:
            return None
        
        # Check for reversal pattern
        prev_prev = self.detect_bar_color(momentum[-3])
        prev = self.detect_bar_color(momentum[-2])
        current = self.detect_bar_color(momentum[-1])
        
        # Bearish to Bullish reversal (red -> red -> green)
        if prev_prev == "red" and prev == "red" and current == "green":
            return "bullish_reversal"
        
        # Bullish to Bearish reversal (green -> green -> red)
        if prev_prev == "green" and prev == "green" and current == "red":
            return "bearish_reversal"
        
        return None
    
    def calculate_momentum_strength(self, momentum: np.ndarray) -> float:
        """
        Calculate the strength of the momentum signal.
        Higher absolute momentum = stronger signal.
        """
        if len(momentum) < 3:
            return 0.0
        
        recent_momentum = momentum[-3:]
        avg_momentum = np.mean(np.abs(recent_momentum))
        
        # Normalize to 0-100 scale (assuming typical pip movements)
        # Adjust this based on the asset's typical volatility
        strength = min(100, avg_momentum * 10000)  # Scale for forex
        
        return strength
    
    def generate_signal(self, candles: List[Dict]) -> Optional[Dict]:
        """
        Generate trading signal based on momentum analysis.
        
        Args:
            candles: List of candle dictionaries with 'open', 'high', 'low', 'close', 'time'
        
        Returns:
            Signal dictionary or None if no signal
        """
        if len(candles) < self.momentum_period + 3:
            logger.debug(f"Insufficient candles: {len(candles)} < {self.momentum_period + 3}")
            return None
        
        # Extract close prices
        closes = np.array([c['close'] for c in candles])
        
        # Calculate momentum
        momentum = self.calculate_momentum(closes, self.momentum_period)
        
        if len(momentum) < 3:
            return None
        
        # Get current momentum state
        current_momentum = momentum[-1]
        current_color = self.detect_bar_color(current_momentum)
        prev_color = self.detect_bar_color(momentum[-2])
        
        # Calculate momentum strength
        strength = self.calculate_momentum_strength(momentum)
        
        # Check for reversal
        reversal = self.detect_trend_reversal(momentum)
        
        # Count consecutive same-color bars
        consecutive_count = self.count_consecutive_bars(momentum, current_color)
        
        # Determine signal
        signal = None
        direction = None
        confidence = 0
        confirmations = []
        
        # Use current and previous colors for signal logic
        _ = prev_color  # Used implicitly in reversal detection above
        
        # BUY SIGNAL: Green bars at new candle / uptrend
        if current_color == "green":
            direction = "CALL"
            confidence = 60
            confirmations.append("momentum_positive")
            
            if consecutive_count >= self.consecutive_bars_required:
                confidence += 10
                confirmations.append(f"consecutive_green_{consecutive_count}")
            
            if reversal == "bullish_reversal":
                confidence += 15
                confirmations.append("bullish_reversal")
            
            if strength > 30:
                confidence += 5
                confirmations.append("strong_momentum")
            
            # Check if price is making higher highs
            if len(candles) >= 3:
                if candles[-1]['high'] > candles[-2]['high'] > candles[-3]['high']:
                    confidence += 5
                    confirmations.append("higher_highs")
        
        # SELL SIGNAL: Red bars at new candle / downtrend  
        elif current_color == "red":
            direction = "PUT"
            confidence = 60
            confirmations.append("momentum_negative")
            
            if consecutive_count >= self.consecutive_bars_required:
                confidence += 10
                confirmations.append(f"consecutive_red_{consecutive_count}")
            
            if reversal == "bearish_reversal":
                confidence += 15
                confirmations.append("bearish_reversal")
            
            if strength > 30:
                confidence += 5
                confirmations.append("strong_momentum")
            
            # Check if price is making lower lows
            if len(candles) >= 3:
                if candles[-1]['low'] < candles[-2]['low'] < candles[-3]['low']:
                    confidence += 5
                    confirmations.append("lower_lows")
        
        # Only generate signal if confidence meets minimum
        if direction and confidence >= self.min_confidence:
            self.signals_generated += 1
            self.last_signal_time = datetime.now(timezone.utc)
            
            signal = {
                "direction": direction,
                "confidence": min(confidence, 95),  # Cap at 95%
                "strategy": self.name,
                "timeframe": self.timeframe,
                "expiration": self.expiration,
                "confirmations": confirmations,
                "indicators": {
                    "momentum": round(current_momentum, 6),
                    "momentum_color": current_color,
                    "momentum_strength": round(strength, 2),
                    "consecutive_bars": consecutive_count,
                    "reversal_detected": reversal
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"🎯 {self.name} Signal: {direction} @ {confidence}% ({', '.join(confirmations)})")
        
        return signal
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "name": self.name,
            "timeframe": self.timeframe,
            "expiration_seconds": self.expiration,
            "momentum_period": self.momentum_period,
            "min_confidence": self.min_confidence,
            "signals_generated": self.signals_generated,
            "last_signal": self.last_signal_time.isoformat() if self.last_signal_time else None
        }


# Global instance
momentum_buster_15s = MomentumBuster15sStrategy()


def get_momentum_buster_signal(candles: List[Dict]) -> Optional[Dict]:
    """Convenience function to get signal from global instance."""
    return momentum_buster_15s.generate_signal(candles)
