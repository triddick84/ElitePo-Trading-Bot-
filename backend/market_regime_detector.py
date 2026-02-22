"""
Market Regime Detector and Signal Optimizer

This module detects market conditions and prevents losing streaks by:
1. Detecting bullish/bearish market regimes
2. Tracking signal performance and adjusting
3. Auto-inverting signals when market regime changes
4. Breaking losing streaks through adaptive analysis
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Detects market regime (bullish/bearish/ranging) and tracks signal performance
    to prevent and break losing streaks.
    """
    
    def __init__(self, db=None):
        self.db = db
        
        # Signal performance tracking
        self.recent_signals: deque = deque(maxlen=20)  # Last 20 signals
        self.win_loss_history: deque = deque(maxlen=50)  # Last 50 trade results
        
        # Market regime state
        self.current_regime = "neutral"  # bullish, bearish, neutral
        self.regime_confidence = 0.5
        self.regime_detected_at = None
        
        # Streak tracking
        self.current_streak = 0  # Positive = wins, Negative = losses
        self.max_losing_streak = 3  # After this many losses, invert signals
        self.streak_inversion_active = False
        
        # Price trend memory
        self.price_history: Dict[str, deque] = {}  # Per-symbol price history
        
    async def initialize(self):
        """Load historical data from database"""
        if self.db is not None:
            try:
                # Load recent trade results
                trades = await self.db.telegram_trades.find(
                    {},
                    {"_id": 0, "status": 1, "direction": 1, "symbol": 1, "timestamp": 1}
                ).sort("timestamp", -1).limit(50).to_list(50)
                
                for trade in reversed(trades):
                    is_win = trade.get("status") == "won"
                    self.win_loss_history.append({
                        "win": is_win,
                        "direction": trade.get("direction"),
                        "symbol": trade.get("symbol"),
                        "timestamp": trade.get("timestamp")
                    })
                    
                # Calculate current streak
                self._update_streak()
                
                logger.info(f"📊 Market Regime Detector initialized: {len(self.win_loss_history)} trades loaded, streak: {self.current_streak}")
                
            except Exception as e:
                logger.error(f"Error initializing regime detector: {e}")
    
    def _update_streak(self):
        """Update current win/loss streak"""
        if not self.win_loss_history:
            self.current_streak = 0
            return
            
        streak = 0
        last_result = None
        
        for trade in reversed(list(self.win_loss_history)):
            is_win = trade.get("win", False)
            
            if last_result is None:
                last_result = is_win
                streak = 1 if is_win else -1
            elif is_win == last_result:
                streak += 1 if is_win else -1
            else:
                break
                
        self.current_streak = streak
        
        # Check if we should activate streak inversion
        if self.current_streak <= -self.max_losing_streak:
            if not self.streak_inversion_active:
                logger.warning(f"🔄 ACTIVATING STREAK INVERSION after {abs(self.current_streak)} consecutive losses")
                self.streak_inversion_active = True
        elif self.current_streak >= 2:  # 2 wins in a row after inversion
            if self.streak_inversion_active:
                logger.info(f"✅ DEACTIVATING STREAK INVERSION after {self.current_streak} wins")
                self.streak_inversion_active = False
    
    def record_trade_result(self, direction: str, symbol: str, is_win: bool):
        """Record a trade result for streak tracking"""
        self.win_loss_history.append({
            "win": is_win,
            "direction": direction,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self._update_streak()
        
        # Log the update
        win_rate = self.get_recent_win_rate()
        logger.info(f"📈 Trade recorded: {'WIN' if is_win else 'LOSS'} | Streak: {self.current_streak} | Win Rate: {win_rate:.1f}%")
    
    def get_recent_win_rate(self, n: int = 10) -> float:
        """Get win rate of last n trades"""
        if not self.win_loss_history:
            return 50.0
            
        recent = list(self.win_loss_history)[-n:]
        if not recent:
            return 50.0
            
        wins = sum(1 for t in recent if t.get("win", False))
        return (wins / len(recent)) * 100
    
    def detect_regime_from_prices(self, prices: List[float], symbol: str = "default") -> Dict:
        """
        Detect market regime from recent prices
        
        Returns:
            Dict with regime, confidence, and trend info
        """
        if not prices or len(prices) < 10:
            return {
                "regime": "neutral",
                "confidence": 0.5,
                "trend_direction": 0,
                "volatility": "normal"
            }
        
        prices = np.array(prices)
        
        # Calculate multiple indicators for regime detection
        
        # 1. Price momentum (simple trend)
        short_ma = np.mean(prices[-5:])
        long_ma = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
        momentum = (short_ma - long_ma) / long_ma if long_ma != 0 else 0
        
        # 2. Rate of change
        roc = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0
        
        # 3. Higher highs / Lower lows detection
        mid = len(prices) // 2
        first_half_high = np.max(prices[:mid]) if mid > 0 else prices[0]
        second_half_high = np.max(prices[mid:])
        first_half_low = np.min(prices[:mid]) if mid > 0 else prices[0]
        second_half_low = np.min(prices[mid:])
        
        higher_highs = second_half_high > first_half_high
        higher_lows = second_half_low > first_half_low
        lower_highs = second_half_high < first_half_high
        lower_lows = second_half_low < first_half_low
        
        # 4. Volatility
        volatility = np.std(prices) / np.mean(prices) if np.mean(prices) != 0 else 0
        
        # Determine regime
        bullish_score = 0
        bearish_score = 0
        
        if momentum > 0.001:
            bullish_score += 1
        elif momentum < -0.001:
            bearish_score += 1
            
        if roc > 0.002:
            bullish_score += 1
        elif roc < -0.002:
            bearish_score += 1
            
        if higher_highs and higher_lows:
            bullish_score += 2
        if lower_highs and lower_lows:
            bearish_score += 2
            
        # Final regime determination
        total_score = bullish_score + bearish_score
        if total_score == 0:
            regime = "neutral"
            confidence = 0.5
        elif bullish_score > bearish_score:
            regime = "bullish"
            confidence = min(0.5 + (bullish_score / 10), 0.9)
        else:
            regime = "bearish"
            confidence = min(0.5 + (bearish_score / 10), 0.9)
        
        # Update stored regime
        self.current_regime = regime
        self.regime_confidence = confidence
        self.regime_detected_at = datetime.now(timezone.utc)
        
        return {
            "regime": regime,
            "confidence": confidence,
            "trend_direction": 1 if regime == "bullish" else (-1 if regime == "bearish" else 0),
            "volatility": "high" if volatility > 0.01 else ("low" if volatility < 0.002 else "normal"),
            "momentum": momentum,
            "bullish_score": bullish_score,
            "bearish_score": bearish_score
        }
    
    def should_invert_signal(self) -> Tuple[bool, str]:
        """
        Determine if signal should be inverted based on:
        1. Losing streak
        2. Market regime mismatch
        
        Returns:
            (should_invert, reason)
        """
        # Check streak-based inversion
        if self.streak_inversion_active:
            return True, f"Streak inversion active (losing streak: {abs(self.current_streak)})"
        
        # Check win rate
        win_rate = self.get_recent_win_rate(10)
        if win_rate < 30:  # Less than 30% win rate
            return True, f"Low win rate inversion ({win_rate:.1f}% in last 10)"
        
        return False, "No inversion needed"
    
    def get_optimal_direction(self, base_direction: str, prices: List[float] = None) -> Tuple[str, str]:
        """
        Get the optimal signal direction, potentially inverting based on conditions
        
        Args:
            base_direction: The original signal direction (CALL/PUT or BUY/SELL)
            prices: Recent price data for regime detection
            
        Returns:
            (optimal_direction, reason)
        """
        # Detect regime if prices provided
        if prices:
            regime = self.detect_regime_from_prices(prices)
        
        # Check if we should invert
        should_invert, reason = self.should_invert_signal()
        
        if should_invert:
            # Invert the direction
            if base_direction.upper() in ["CALL", "BUY"]:
                return "PUT", f"Inverted: {reason}"
            else:
                return "CALL", f"Inverted: {reason}"
        
        return base_direction, "Original direction maintained"
    
    def get_regime_adjusted_direction(self, prices: List[float]) -> str:
        """
        Get direction based purely on market regime, ignoring strategy output
        Used as fallback when strategies fail
        """
        regime = self.detect_regime_from_prices(prices)
        
        if regime["regime"] == "bullish" and regime["confidence"] > 0.6:
            return "CALL"
        elif regime["regime"] == "bearish" and regime["confidence"] > 0.6:
            return "PUT"
        else:
            # Neutral - use recent price action
            if len(prices) >= 5:
                recent_trend = prices[-1] - prices[-5]
                return "CALL" if recent_trend > 0 else "PUT"
            return "CALL"  # True last resort
    
    def get_status(self) -> Dict:
        """Get current status of the regime detector"""
        return {
            "current_regime": self.current_regime,
            "regime_confidence": self.regime_confidence,
            "current_streak": self.current_streak,
            "streak_inversion_active": self.streak_inversion_active,
            "recent_win_rate": self.get_recent_win_rate(10),
            "total_trades_tracked": len(self.win_loss_history),
            "regime_detected_at": self.regime_detected_at.isoformat() if self.regime_detected_at else None
        }


# Global instance
_regime_detector: Optional[MarketRegimeDetector] = None


def get_regime_detector() -> Optional[MarketRegimeDetector]:
    """Get the global regime detector instance"""
    return _regime_detector


async def initialize_regime_detector(db) -> MarketRegimeDetector:
    """Initialize and return the regime detector"""
    global _regime_detector
    _regime_detector = MarketRegimeDetector(db)
    await _regime_detector.initialize()
    return _regime_detector
