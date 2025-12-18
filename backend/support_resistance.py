"""
Support and Resistance Level Detection Module
Real-time S/R detection using fractal analysis, zone clustering, and strength scoring
Optimized for all timeframes including ultra-short 5-second trading
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@dataclass
class SRZone:
    """Represents a Support or Resistance zone with strength metrics"""
    price: float
    zone_type: str  # 'support' or 'resistance'
    touches: int = 1
    total_volume: float = 0.0
    avg_rejection_strength: float = 0.0
    first_detected: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_touched: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    price_min: float = 0.0
    price_max: float = 0.0
    strength_score: float = 0.0
    
    def __post_init__(self):
        if self.price_min == 0.0:
            self.price_min = self.price
        if self.price_max == 0.0:
            self.price_max = self.price
    
    def update(self, price: float, volume: float, rejection_strength: float, timestamp: datetime):
        """Update zone with new touch"""
        self.touches += 1
        self.total_volume += volume
        self.avg_rejection_strength = (
            (self.avg_rejection_strength * (self.touches - 1) + rejection_strength) / self.touches
        )
        self.price = (self.price * (self.touches - 1) + price) / self.touches
        self.price_min = min(self.price_min, price)
        self.price_max = max(self.price_max, price)
        self.last_touched = timestamp
    
    def to_dict(self) -> dict:
        return {
            "price": round(self.price, 5),
            "type": self.zone_type,
            "touches": self.touches,
            "strength": round(self.strength_score, 2),
            "avg_volume": round(self.total_volume / max(1, self.touches), 2),
            "rejection_strength": round(self.avg_rejection_strength, 3),
            "zone_range": [round(self.price_min, 5), round(self.price_max, 5)],
            "last_touched": self.last_touched.isoformat() if self.last_touched else None
        }


class SupportResistanceDetector:
    """
    Real-time Support and Resistance Level Detector
    Uses fractal detection + zone clustering + strength scoring
    """
    
    # Timeframe-specific settings
    TIMEFRAME_SETTINGS = {
        '5s': {'lookback': 3, 'merge_pct': 0.0015, 'wick_threshold': 0.3, 'max_zones': 10},
        '15s': {'lookback': 4, 'merge_pct': 0.0012, 'wick_threshold': 0.35, 'max_zones': 12},
        '30s': {'lookback': 5, 'merge_pct': 0.001, 'wick_threshold': 0.4, 'max_zones': 15},
        '1m': {'lookback': 5, 'merge_pct': 0.001, 'wick_threshold': 0.4, 'max_zones': 15},
        '5m': {'lookback': 7, 'merge_pct': 0.0008, 'wick_threshold': 0.45, 'max_zones': 20},
        '15m': {'lookback': 10, 'merge_pct': 0.0006, 'wick_threshold': 0.5, 'max_zones': 20},
        '1h': {'lookback': 14, 'merge_pct': 0.0005, 'wick_threshold': 0.5, 'max_zones': 25},
    }
    
    def __init__(self, timeframe: str = '5s'):
        self.timeframe = timeframe
        settings = self.TIMEFRAME_SETTINGS.get(timeframe, self.TIMEFRAME_SETTINGS['1m'])
        self.lookback = settings['lookback']
        self.merge_pct = settings['merge_pct']
        self.wick_threshold = settings['wick_threshold']
        self.max_zones = settings['max_zones']
        
        self.support_zones: List[SRZone] = []
        self.resistance_zones: List[SRZone] = []
        
    def calculate_rejection_strength(self, candle: dict) -> Tuple[float, float]:
        """
        Calculate wick rejection strength for support and resistance
        Returns (lower_wick_strength, upper_wick_strength)
        """
        open_price = candle['open']
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        body = abs(close - open_price)
        candle_range = high - low
        
        if candle_range == 0:
            return 0.0, 0.0
        
        # Lower wick strength (support rejection)
        lower_wick = min(open_price, close) - low
        lower_strength = lower_wick / candle_range if candle_range > 0 else 0
        
        # Upper wick strength (resistance rejection)
        upper_wick = high - max(open_price, close)
        upper_strength = upper_wick / candle_range if candle_range > 0 else 0
        
        return lower_strength, upper_strength
    
    def is_support_fractal(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a support fractal (local minimum)"""
        if idx < self.lookback:
            return False
        
        low = df['low'].iloc[idx]
        window_lows = df['low'].iloc[idx - self.lookback:idx]
        
        # Must be lower than all candles in lookback window
        if low >= window_lows.min():
            return False
        
        # Check for rejection wick (lower wick should be significant)
        candle = df.iloc[idx]
        lower_strength, _ = self.calculate_rejection_strength(candle.to_dict())
        
        return lower_strength >= self.wick_threshold
    
    def is_resistance_fractal(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a resistance fractal (local maximum)"""
        if idx < self.lookback:
            return False
        
        high = df['high'].iloc[idx]
        window_highs = df['high'].iloc[idx - self.lookback:idx]
        
        # Must be higher than all candles in lookback window
        if high <= window_highs.max():
            return False
        
        # Check for rejection wick (upper wick should be significant)
        candle = df.iloc[idx]
        _, upper_strength = self.calculate_rejection_strength(candle.to_dict())
        
        return upper_strength >= self.wick_threshold
    
    def add_support_candidate(self, price: float, volume: float, rejection_strength: float, 
                               timestamp: datetime = None):
        """Add a new support level candidate, merging with existing if close"""
        timestamp = timestamp or datetime.now(timezone.utc)
        
        # Check if we can merge with existing zone
        for zone in self.support_zones:
            if abs(price - zone.price) <= zone.price * self.merge_pct:
                zone.update(price, volume, rejection_strength, timestamp)
                return
        
        # Create new zone
        new_zone = SRZone(
            price=price,
            zone_type='support',
            touches=1,
            total_volume=volume,
            avg_rejection_strength=rejection_strength,
            first_detected=timestamp,
            last_touched=timestamp
        )
        self.support_zones.append(new_zone)
        
        # Keep top zones by touches/strength
        self._cleanup_zones()
    
    def add_resistance_candidate(self, price: float, volume: float, rejection_strength: float,
                                  timestamp: datetime = None):
        """Add a new resistance level candidate, merging with existing if close"""
        timestamp = timestamp or datetime.now(timezone.utc)
        
        # Check if we can merge with existing zone
        for zone in self.resistance_zones:
            if abs(price - zone.price) <= zone.price * self.merge_pct:
                zone.update(price, volume, rejection_strength, timestamp)
                return
        
        # Create new zone
        new_zone = SRZone(
            price=price,
            zone_type='resistance',
            touches=1,
            total_volume=volume,
            avg_rejection_strength=rejection_strength,
            first_detected=timestamp,
            last_touched=timestamp
        )
        self.resistance_zones.append(new_zone)
        
        # Keep top zones
        self._cleanup_zones()
    
    def _calculate_strength_scores(self):
        """Calculate strength scores for all zones"""
        all_zones = self.support_zones + self.resistance_zones
        
        if not all_zones:
            return
        
        # Get average volume for normalization
        total_vol = sum(z.total_volume for z in all_zones)
        avg_vol = total_vol / len(all_zones) if total_vol > 0 else 1
        
        now = datetime.now(timezone.utc)
        
        for zone in all_zones:
            # Components of strength score:
            # 1. Touches (more touches = stronger level)
            touch_score = min(zone.touches * 2, 20)  # Cap at 20
            
            # 2. Volume (higher volume = more significant)
            vol_score = (zone.total_volume / max(1, avg_vol)) * 5 if avg_vol > 0 else 0
            vol_score = min(vol_score, 15)  # Cap at 15
            
            # 3. Rejection strength (stronger wicks = better confirmation)
            rejection_score = zone.avg_rejection_strength * 10
            
            # 4. Recency bonus (more recent = more relevant)
            age_seconds = (now - zone.last_touched).total_seconds()
            # Decay over time: full value within 5 min, half at 30 min, quarter at 2 hours
            recency_factor = max(0.25, 1.0 - (age_seconds / 7200))
            
            # Final score
            zone.strength_score = (touch_score + vol_score + rejection_score) * recency_factor
    
    def _cleanup_zones(self):
        """Remove weakest zones if over limit"""
        self._calculate_strength_scores()
        
        # Sort by strength and keep top N
        self.support_zones = sorted(
            self.support_zones, 
            key=lambda z: z.strength_score, 
            reverse=True
        )[:self.max_zones]
        
        self.resistance_zones = sorted(
            self.resistance_zones,
            key=lambda z: z.strength_score,
            reverse=True
        )[:self.max_zones]
    
    def detect_levels_from_ohlcv(self, df: pd.DataFrame) -> Dict[str, List[SRZone]]:
        """
        Detect support and resistance levels from OHLCV DataFrame
        Expects columns: open, high, low, close, volume (optional)
        """
        if df.empty or len(df) < self.lookback + 1:
            return {'support': [], 'resistance': []}
        
        # Reset zones for fresh detection
        self.support_zones = []
        self.resistance_zones = []
        
        # Scan for fractals
        for idx in range(self.lookback, len(df)):
            candle = df.iloc[idx]
            volume = candle.get('volume', 1.0) if 'volume' in df.columns else 1.0
            timestamp = candle.name if isinstance(candle.name, datetime) else datetime.now(timezone.utc)
            
            lower_strength, upper_strength = self.calculate_rejection_strength(candle.to_dict())
            
            # Check for support fractal
            if self.is_support_fractal(df, idx):
                self.add_support_candidate(
                    price=candle['low'],
                    volume=volume,
                    rejection_strength=lower_strength,
                    timestamp=timestamp
                )
            
            # Check for resistance fractal
            if self.is_resistance_fractal(df, idx):
                self.add_resistance_candidate(
                    price=candle['high'],
                    volume=volume,
                    rejection_strength=upper_strength,
                    timestamp=timestamp
                )
        
        self._calculate_strength_scores()
        
        return {
            'support': self.support_zones,
            'resistance': self.resistance_zones
        }
    
    def get_nearest_support(self, current_price: float) -> Optional[SRZone]:
        """Get the nearest support level below current price"""
        supports_below = [z for z in self.support_zones if z.price < current_price]
        if not supports_below:
            return None
        return max(supports_below, key=lambda z: z.price)
    
    def get_nearest_resistance(self, current_price: float) -> Optional[SRZone]:
        """Get the nearest resistance level above current price"""
        resistances_above = [z for z in self.resistance_zones if z.price > current_price]
        if not resistances_above:
            return None
        return min(resistances_above, key=lambda z: z.price)
    
    def is_near_support(self, current_price: float, tolerance_pct: float = 0.002) -> Tuple[bool, Optional[SRZone]]:
        """Check if price is near a support level"""
        for zone in self.support_zones:
            if abs(current_price - zone.price) / zone.price <= tolerance_pct:
                return True, zone
        return False, None
    
    def is_near_resistance(self, current_price: float, tolerance_pct: float = 0.002) -> Tuple[bool, Optional[SRZone]]:
        """Check if price is near a resistance level"""
        for zone in self.resistance_zones:
            if abs(current_price - zone.price) / zone.price <= tolerance_pct:
                return True, zone
        return False, None
    
    def get_sr_confirmation(self, current_price: float, signal_direction: str) -> Dict:
        """
        Get S/R confirmation for a trading signal
        Returns confidence boost and details about nearby S/R levels
        """
        result = {
            'has_confirmation': False,
            'confidence_boost': 0.0,
            'nearest_support': None,
            'nearest_resistance': None,
            'support_distance_pct': None,
            'resistance_distance_pct': None,
            'confirmation_type': None,
            'details': ''
        }
        
        # Get nearest levels
        nearest_support = self.get_nearest_support(current_price)
        nearest_resistance = self.get_nearest_resistance(current_price)
        
        if nearest_support:
            result['nearest_support'] = nearest_support.to_dict()
            result['support_distance_pct'] = round(
                (current_price - nearest_support.price) / current_price * 100, 3
            )
        
        if nearest_resistance:
            result['nearest_resistance'] = nearest_resistance.to_dict()
            result['resistance_distance_pct'] = round(
                (nearest_resistance.price - current_price) / current_price * 100, 3
            )
        
        # Check for S/R confirmation based on signal direction
        tolerance = 0.003  # 0.3% tolerance for "near" level
        
        if signal_direction.upper() in ['BUY', 'CALL', 'UP', 'HIGHER']:
            # For BUY signals, we want price near support (bounce expected)
            is_near, support_zone = self.is_near_support(current_price, tolerance)
            if is_near and support_zone:
                # Strong confirmation: bouncing off support
                strength_factor = min(support_zone.strength_score / 20, 1.5)
                result['has_confirmation'] = True
                result['confidence_boost'] = 3.0 + (strength_factor * 2)  # 3-5% boost
                result['confirmation_type'] = 'support_bounce'
                result['details'] = f"Price at support level ({support_zone.price:.5f}), {support_zone.touches} touches, strength {support_zone.strength_score:.1f}"
            elif nearest_support and result['support_distance_pct'] < 0.5:
                # Moderate confirmation: close to support
                result['has_confirmation'] = True
                result['confidence_boost'] = 1.5
                result['confirmation_type'] = 'near_support'
                result['details'] = f"Price near support ({nearest_support.price:.5f}), {result['support_distance_pct']:.2f}% away"
                
        elif signal_direction.upper() in ['SELL', 'PUT', 'DOWN', 'LOWER']:
            # For SELL signals, we want price near resistance (rejection expected)
            is_near, resistance_zone = self.is_near_resistance(current_price, tolerance)
            if is_near and resistance_zone:
                # Strong confirmation: rejecting from resistance
                strength_factor = min(resistance_zone.strength_score / 20, 1.5)
                result['has_confirmation'] = True
                result['confidence_boost'] = 3.0 + (strength_factor * 2)  # 3-5% boost
                result['confirmation_type'] = 'resistance_rejection'
                result['details'] = f"Price at resistance level ({resistance_zone.price:.5f}), {resistance_zone.touches} touches, strength {resistance_zone.strength_score:.1f}"
            elif nearest_resistance and result['resistance_distance_pct'] < 0.5:
                # Moderate confirmation: close to resistance
                result['has_confirmation'] = True
                result['confidence_boost'] = 1.5
                result['confirmation_type'] = 'near_resistance'
                result['details'] = f"Price near resistance ({nearest_resistance.price:.5f}), {result['resistance_distance_pct']:.2f}% away"
        
        return result
    
    def get_all_levels(self) -> Dict:
        """Get all detected S/R levels with their details"""
        self._calculate_strength_scores()
        
        return {
            'support_levels': [z.to_dict() for z in sorted(
                self.support_zones, key=lambda x: x.strength_score, reverse=True
            )],
            'resistance_levels': [z.to_dict() for z in sorted(
                self.resistance_zones, key=lambda x: x.strength_score, reverse=True
            )],
            'total_support': len(self.support_zones),
            'total_resistance': len(self.resistance_zones),
            'timeframe': self.timeframe
        }


# Global instances for different timeframes
sr_detectors: Dict[str, SupportResistanceDetector] = {}

def get_sr_detector(timeframe: str) -> SupportResistanceDetector:
    """Get or create S/R detector for a specific timeframe"""
    if timeframe not in sr_detectors:
        sr_detectors[timeframe] = SupportResistanceDetector(timeframe)
    return sr_detectors[timeframe]

def detect_support_resistance(df: pd.DataFrame, timeframe: str = '5s') -> Dict:
    """
    Convenience function to detect S/R levels from OHLCV data
    
    Args:
        df: DataFrame with columns [open, high, low, close, volume]
        timeframe: Trading timeframe ('5s', '15s', '30s', '1m', '5m', '15m', '1h')
    
    Returns:
        Dictionary with support and resistance levels
    """
    detector = get_sr_detector(timeframe)
    detector.detect_levels_from_ohlcv(df)
    return detector.get_all_levels()

def get_sr_signal_confirmation(current_price: float, signal_direction: str, 
                                timeframe: str = '5s') -> Dict:
    """
    Get S/R confirmation for a trading signal
    
    Args:
        current_price: Current asset price
        signal_direction: 'BUY'/'CALL' or 'SELL'/'PUT'
        timeframe: Trading timeframe
    
    Returns:
        Dictionary with confirmation details and confidence boost
    """
    detector = get_sr_detector(timeframe)
    return detector.get_sr_confirmation(current_price, signal_direction)
