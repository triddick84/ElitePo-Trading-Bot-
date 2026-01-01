"""
Support and Resistance Detection Module
========================================

Advanced S/R detection for 5-second binary options trading.
Identifies key price levels where price is likely to bounce or break through.

Methods Used:
1. Swing High/Low Detection
2. Price Clustering Zones
3. Pivot Points (Classic & Fibonacci)
4. Dynamic S/R from EMAs
5. Volume Profile Analysis
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SRType(Enum):
    """Support/Resistance type"""
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PIVOT = "pivot"


class SRStrength(Enum):
    """S/R level strength"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class SRLevel:
    """Support/Resistance level"""
    price: float
    type: SRType
    strength: SRStrength
    touch_count: int
    last_touch_index: int
    created_index: int
    is_broken: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "price": round(self.price, 5),
            "type": self.type.value,
            "strength": self.strength.value,
            "touch_count": self.touch_count,
            "is_broken": self.is_broken
        }


@dataclass
class SRAnalysis:
    """Complete S/R analysis result"""
    support_levels: List[SRLevel]
    resistance_levels: List[SRLevel]
    nearest_support: Optional[SRLevel]
    nearest_resistance: Optional[SRLevel]
    price_position: str  # "at_support", "at_resistance", "between_levels", "above_resistance", "below_support"
    distance_to_support_pct: float
    distance_to_resistance_pct: float
    breakout_potential: str  # "bullish_breakout", "bearish_breakout", "consolidation", "bounce_likely"
    signal_adjustment: float  # -1 to +1 adjustment factor
    
    def to_dict(self) -> Dict:
        return {
            "support_levels": [s.to_dict() for s in self.support_levels[:5]],  # Top 5
            "resistance_levels": [r.to_dict() for r in self.resistance_levels[:5]],  # Top 5
            "nearest_support": self.nearest_support.to_dict() if self.nearest_support else None,
            "nearest_resistance": self.nearest_resistance.to_dict() if self.nearest_resistance else None,
            "price_position": self.price_position,
            "distance_to_support_pct": round(self.distance_to_support_pct, 4),
            "distance_to_resistance_pct": round(self.distance_to_resistance_pct, 4),
            "breakout_potential": self.breakout_potential,
            "signal_adjustment": round(self.signal_adjustment, 2)
        }


class SupportResistanceDetector:
    """
    Advanced Support and Resistance Detection
    
    Uses multiple methods to identify key price levels:
    1. Swing points (local highs/lows)
    2. Price clustering (consolidation zones)
    3. Pivot points
    4. Dynamic EMA-based S/R
    """
    
    def __init__(
        self,
        swing_period: int = 5,
        cluster_threshold: float = 0.0002,  # 2 pips for forex
        min_touches: int = 2,
        sr_zone_width: float = 0.0003  # 3 pips zone width
    ):
        """
        Initialize S/R detector
        
        Args:
            swing_period: Lookback for swing high/low detection
            cluster_threshold: Price difference threshold for clustering
            min_touches: Minimum touches to confirm S/R level
            sr_zone_width: Width of S/R zone for proximity detection
        """
        self.swing_period = swing_period
        self.cluster_threshold = cluster_threshold
        self.min_touches = min_touches
        self.sr_zone_width = sr_zone_width
    
    def detect_levels(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray = None
    ) -> Tuple[List[SRLevel], List[SRLevel]]:
        """
        Detect all support and resistance levels
        
        Returns:
            Tuple of (support_levels, resistance_levels) sorted by strength
        """
        all_levels = []
        
        # Method 1: Swing High/Low Detection
        swing_levels = self._detect_swing_levels(highs, lows, closes)
        all_levels.extend(swing_levels)
        
        # Method 2: Price Clustering
        cluster_levels = self._detect_cluster_levels(highs, lows, closes)
        all_levels.extend(cluster_levels)
        
        # Method 3: Pivot Points
        pivot_levels = self._calculate_pivot_points(highs, lows, closes)
        all_levels.extend(pivot_levels)
        
        # Method 4: Dynamic EMA S/R
        ema_levels = self._detect_ema_levels(closes)
        all_levels.extend(ema_levels)
        
        # Merge nearby levels
        merged_levels = self._merge_nearby_levels(all_levels, closes[-1])
        
        # Separate into support and resistance
        current_price = closes[-1]
        support_levels = [l for l in merged_levels if l.price < current_price]
        resistance_levels = [l for l in merged_levels if l.price >= current_price]
        
        # Sort by strength (touch count and recency)
        support_levels.sort(key=lambda x: (x.touch_count, -x.last_touch_index), reverse=True)
        resistance_levels.sort(key=lambda x: (x.touch_count, -x.last_touch_index), reverse=True)
        
        return support_levels, resistance_levels
    
    def _detect_swing_levels(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> List[SRLevel]:
        """Detect swing highs and lows"""
        levels = []
        n = len(closes)
        
        for i in range(self.swing_period, n - self.swing_period):
            # Swing High
            if highs[i] == max(highs[i-self.swing_period:i+self.swing_period+1]):
                # Count touches
                touch_count = self._count_touches(highs, highs[i], i, n)
                strength = self._determine_strength(touch_count)
                
                levels.append(SRLevel(
                    price=highs[i],
                    type=SRType.RESISTANCE,
                    strength=strength,
                    touch_count=touch_count,
                    last_touch_index=i,
                    created_index=i
                ))
            
            # Swing Low
            if lows[i] == min(lows[i-self.swing_period:i+self.swing_period+1]):
                touch_count = self._count_touches(lows, lows[i], i, n)
                strength = self._determine_strength(touch_count)
                
                levels.append(SRLevel(
                    price=lows[i],
                    type=SRType.SUPPORT,
                    strength=strength,
                    touch_count=touch_count,
                    last_touch_index=i,
                    created_index=i
                ))
        
        return levels
    
    def _detect_cluster_levels(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> List[SRLevel]:
        """Detect price clustering zones"""
        levels = []
        
        # Combine all price points
        all_prices = np.concatenate([highs, lows, closes])
        
        # Find clusters using histogram
        price_range = all_prices.max() - all_prices.min()
        if price_range == 0:
            return levels
        
        num_bins = max(20, int(price_range / self.cluster_threshold))
        hist, bin_edges = np.histogram(all_prices, bins=num_bins)
        
        # Find significant clusters (above average)
        mean_count = np.mean(hist)
        std_count = np.std(hist)
        
        for i, count in enumerate(hist):
            if count > mean_count + std_count:  # Significant cluster
                cluster_price = (bin_edges[i] + bin_edges[i+1]) / 2
                current_price = closes[-1]
                
                sr_type = SRType.SUPPORT if cluster_price < current_price else SRType.RESISTANCE
                touch_count = int(count)
                strength = self._determine_strength(touch_count)
                
                levels.append(SRLevel(
                    price=cluster_price,
                    type=sr_type,
                    strength=strength,
                    touch_count=touch_count,
                    last_touch_index=len(closes) - 1,
                    created_index=0
                ))
        
        return levels
    
    def _calculate_pivot_points(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> List[SRLevel]:
        """Calculate pivot points (using recent data window)"""
        levels = []
        
        # Use last 50 candles for pivot calculation
        window = min(50, len(closes))
        high = np.max(highs[-window:])
        low = np.min(lows[-window:])
        close = closes[-1]
        
        # Classic Pivot Points
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        current_price = closes[-1]
        
        # Add pivot levels
        pivot_prices = [
            (pivot, SRType.PIVOT, "P"),
            (r1, SRType.RESISTANCE, "R1"),
            (r2, SRType.RESISTANCE, "R2"),
            (r3, SRType.RESISTANCE, "R3"),
            (s1, SRType.SUPPORT, "S1"),
            (s2, SRType.SUPPORT, "S2"),
            (s3, SRType.SUPPORT, "S3")
        ]
        
        for price, sr_type, _ in pivot_prices:
            if sr_type == SRType.PIVOT:
                sr_type = SRType.SUPPORT if price < current_price else SRType.RESISTANCE
            
            touch_count = self._count_touches(closes, price, 0, len(closes))
            strength = self._determine_strength(max(touch_count, 2))  # Pivots get minimum moderate strength
            
            levels.append(SRLevel(
                price=price,
                type=sr_type,
                strength=strength,
                touch_count=max(touch_count, 2),
                last_touch_index=len(closes) - 1,
                created_index=0
            ))
        
        return levels
    
    def _detect_ema_levels(self, closes: np.ndarray) -> List[SRLevel]:
        """Detect dynamic S/R from EMAs"""
        levels = []
        ema_periods = [10, 20, 50]
        
        for period in ema_periods:
            if len(closes) < period:
                continue
            
            ema = self._calculate_ema(closes, period)
            ema_value = ema[-1]
            current_price = closes[-1]
            
            sr_type = SRType.SUPPORT if ema_value < current_price else SRType.RESISTANCE
            
            # Count how many times price touched EMA
            touch_count = 0
            for i in range(period, len(closes)):
                if abs(closes[i] - ema[i]) / ema[i] < 0.001:  # Within 0.1%
                    touch_count += 1
            
            strength = self._determine_strength(touch_count)
            
            levels.append(SRLevel(
                price=ema_value,
                type=sr_type,
                strength=strength,
                touch_count=touch_count,
                last_touch_index=len(closes) - 1,
                created_index=period
            ))
        
        return levels
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        
        return ema
    
    def _count_touches(
        self,
        prices: np.ndarray,
        level: float,
        start_idx: int,
        end_idx: int
    ) -> int:
        """Count how many times price touched a level"""
        touches = 0
        threshold = level * 0.001  # 0.1% threshold
        
        for i in range(start_idx, min(end_idx, len(prices))):
            if abs(prices[i] - level) <= threshold:
                touches += 1
        
        return touches
    
    def _determine_strength(self, touch_count: int) -> SRStrength:
        """Determine S/R strength based on touch count"""
        if touch_count >= 5:
            return SRStrength.VERY_STRONG
        elif touch_count >= 3:
            return SRStrength.STRONG
        elif touch_count >= 2:
            return SRStrength.MODERATE
        else:
            return SRStrength.WEAK
    
    def _merge_nearby_levels(
        self,
        levels: List[SRLevel],
        current_price: float
    ) -> List[SRLevel]:
        """Merge S/R levels that are close together"""
        if not levels:
            return []
        
        # Sort by price
        sorted_levels = sorted(levels, key=lambda x: x.price)
        merged = []
        
        i = 0
        while i < len(sorted_levels):
            # Find all levels within threshold
            group = [sorted_levels[i]]
            j = i + 1
            
            while j < len(sorted_levels):
                if abs(sorted_levels[j].price - group[0].price) <= self.cluster_threshold * 2:
                    group.append(sorted_levels[j])
                    j += 1
                else:
                    break
            
            # Merge group into single level
            avg_price = np.mean([l.price for l in group])
            total_touches = sum(l.touch_count for l in group)
            max_strength = max(group, key=lambda x: x.touch_count).strength
            sr_type = SRType.SUPPORT if avg_price < current_price else SRType.RESISTANCE
            last_touch = max(l.last_touch_index for l in group)
            
            merged.append(SRLevel(
                price=avg_price,
                type=sr_type,
                strength=max_strength,
                touch_count=total_touches,
                last_touch_index=last_touch,
                created_index=min(l.created_index for l in group)
            ))
            
            i = j
        
        return merged
    
    def analyze(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray = None,
        signal_direction: str = None  # "call" or "put"
    ) -> SRAnalysis:
        """
        Complete S/R analysis with signal adjustment
        
        Args:
            highs, lows, closes: Price arrays
            volumes: Volume array (optional)
            signal_direction: Current signal direction for adjustment calculation
        
        Returns:
            SRAnalysis with all S/R information and signal adjustment factor
        """
        current_price = closes[-1]
        
        # Detect S/R levels
        support_levels, resistance_levels = self.detect_levels(highs, lows, closes, volumes)
        
        # Find nearest levels
        nearest_support = support_levels[0] if support_levels else None
        nearest_resistance = resistance_levels[0] if resistance_levels else None
        
        # Calculate distances
        distance_to_support = 0.0
        distance_to_resistance = 0.0
        
        if nearest_support:
            distance_to_support = ((current_price - nearest_support.price) / current_price) * 100
        
        if nearest_resistance:
            distance_to_resistance = ((nearest_resistance.price - current_price) / current_price) * 100
        
        # Determine price position
        price_position = self._determine_price_position(
            current_price, nearest_support, nearest_resistance
        )
        
        # Determine breakout potential
        breakout_potential = self._assess_breakout_potential(
            closes, nearest_support, nearest_resistance, current_price
        )
        
        # Calculate signal adjustment
        signal_adjustment = self._calculate_signal_adjustment(
            signal_direction,
            price_position,
            breakout_potential,
            distance_to_support,
            distance_to_resistance,
            nearest_support,
            nearest_resistance
        )
        
        return SRAnalysis(
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            price_position=price_position,
            distance_to_support_pct=distance_to_support,
            distance_to_resistance_pct=distance_to_resistance,
            breakout_potential=breakout_potential,
            signal_adjustment=signal_adjustment
        )
    
    def _determine_price_position(
        self,
        current_price: float,
        nearest_support: Optional[SRLevel],
        nearest_resistance: Optional[SRLevel]
    ) -> str:
        """Determine where price is relative to S/R levels"""
        zone_threshold = self.sr_zone_width
        
        if nearest_support and abs(current_price - nearest_support.price) / current_price < zone_threshold:
            return "at_support"
        
        if nearest_resistance and abs(current_price - nearest_resistance.price) / current_price < zone_threshold:
            return "at_resistance"
        
        if not nearest_support:
            return "below_support"
        
        if not nearest_resistance:
            return "above_resistance"
        
        return "between_levels"
    
    def _assess_breakout_potential(
        self,
        closes: np.ndarray,
        nearest_support: Optional[SRLevel],
        nearest_resistance: Optional[SRLevel],
        current_price: float
    ) -> str:
        """Assess potential for breakout vs bounce"""
        # Look at recent momentum
        if len(closes) < 10:
            return "consolidation"
        
        recent_momentum = closes[-1] - closes[-10]
        momentum_strength = abs(recent_momentum) / closes[-1]
        
        # Check if momentum is strong
        is_strong_momentum = momentum_strength > 0.001  # 0.1% momentum
        
        # Bullish momentum near resistance
        if recent_momentum > 0 and nearest_resistance:
            distance_to_res = (nearest_resistance.price - current_price) / current_price
            if distance_to_res < 0.001 and is_strong_momentum:
                return "bullish_breakout"
            elif distance_to_res < 0.002:
                return "bounce_likely"
        
        # Bearish momentum near support
        if recent_momentum < 0 and nearest_support:
            distance_to_sup = (current_price - nearest_support.price) / current_price
            if distance_to_sup < 0.001 and is_strong_momentum:
                return "bearish_breakout"
            elif distance_to_sup < 0.002:
                return "bounce_likely"
        
        return "consolidation"
    
    def _calculate_signal_adjustment(
        self,
        signal_direction: str,
        price_position: str,
        breakout_potential: str,
        distance_to_support: float,
        distance_to_resistance: float,
        nearest_support: Optional[SRLevel],
        nearest_resistance: Optional[SRLevel]
    ) -> float:
        """
        Calculate signal adjustment factor based on S/R analysis
        
        Returns:
            Adjustment factor from -1 (strong negative) to +1 (strong positive)
            - Negative = reduce confidence / consider opposite direction
            - Positive = increase confidence
            - Zero = no adjustment
        """
        adjustment = 0.0
        
        if not signal_direction:
            return 0.0
        
        is_call = signal_direction.lower() in ["call", "buy", "up"]
        
        # Case 1: CALL signal at resistance - HIGH RISK of bounce back
        if is_call and price_position == "at_resistance":
            if breakout_potential == "bullish_breakout":
                adjustment = 0.2  # Slight positive - breakout potential
            else:
                adjustment = -0.6  # Strong negative - likely to bounce down
                if nearest_resistance and nearest_resistance.strength in [SRStrength.STRONG, SRStrength.VERY_STRONG]:
                    adjustment = -0.8  # Even stronger negative for strong resistance
        
        # Case 2: PUT signal at support - HIGH RISK of bounce back
        elif not is_call and price_position == "at_support":
            if breakout_potential == "bearish_breakout":
                adjustment = 0.2  # Slight positive - breakout potential
            else:
                adjustment = -0.6  # Strong negative - likely to bounce up
                if nearest_support and nearest_support.strength in [SRStrength.STRONG, SRStrength.VERY_STRONG]:
                    adjustment = -0.8  # Even stronger negative for strong support
        
        # Case 3: CALL signal at support - GOOD setup
        elif is_call and price_position == "at_support":
            adjustment = 0.4  # Positive - good bounce opportunity
            if nearest_support and nearest_support.strength in [SRStrength.STRONG, SRStrength.VERY_STRONG]:
                adjustment = 0.6
        
        # Case 4: PUT signal at resistance - GOOD setup
        elif not is_call and price_position == "at_resistance":
            adjustment = 0.4  # Positive - good bounce opportunity
            if nearest_resistance and nearest_resistance.strength in [SRStrength.STRONG, SRStrength.VERY_STRONG]:
                adjustment = 0.6
        
        # Case 5: Between levels - neutral
        elif price_position == "between_levels":
            # Check if very close to either level
            if distance_to_support < 0.05:  # Within 0.05%
                if is_call:
                    adjustment = 0.2  # Slight positive - near support
                else:
                    adjustment = -0.3  # Negative - PUT near support
            elif distance_to_resistance < 0.05:
                if not is_call:
                    adjustment = 0.2  # Slight positive - near resistance
                else:
                    adjustment = -0.3  # Negative - CALL near resistance
        
        # Bonus for breakout scenarios
        if breakout_potential == "bullish_breakout" and is_call:
            adjustment = max(adjustment, 0.3)
        elif breakout_potential == "bearish_breakout" and not is_call:
            adjustment = max(adjustment, 0.3)
        
        return np.clip(adjustment, -1.0, 1.0)


# Create singleton instance
_sr_detector: Optional[SupportResistanceDetector] = None


def get_sr_detector() -> SupportResistanceDetector:
    """Get or create S/R detector instance"""
    global _sr_detector
    if _sr_detector is None:
        _sr_detector = SupportResistanceDetector()
    return _sr_detector
