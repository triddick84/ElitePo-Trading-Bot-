"""
Enhanced Support & Resistance Detection Module
Based on research of optimal parameters for ultra-short to medium timeframes

Key Features:
- Timeframe-specific lookback periods
- Swing high/low detection algorithm
- Pivot point calculations
- Price action zones (support/resistance zones, not lines)
- Trend reversal detection
- Signal validation against S/R levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SupportResistanceDetector:
    """
    Advanced support and resistance detection with timeframe-optimized parameters
    """
    
    # Optimal lookback periods per timeframe (based on research)
    TIMEFRAME_PARAMS = {
        '5s': {
            'lookback': 10,          # 8-15 bars for very recent swings
            'swing_window': 2,       # Window for swing detection
            'zone_threshold': 0.0005, # 0.05% price zone tolerance (very tight for 5s)
            'strength_periods': 5,    # Periods to calculate level strength
            'min_touches': 2          # Minimum touches to confirm level
        },
        '15s': {
            'lookback': 15,          # 10-20 bars
            'swing_window': 3,
            'zone_threshold': 0.001,  # 0.1% price zone tolerance
            'strength_periods': 8,
            'min_touches': 2
        },
        '30s': {
            'lookback': 20,
            'swing_window': 3,
            'zone_threshold': 0.0012,
            'strength_periods': 10,
            'min_touches': 2
        },
        '1m': {
            'lookback': 20,          # 15-25 bars
            'swing_window': 4,
            'zone_threshold': 0.0015, # 0.15% price zone tolerance
            'strength_periods': 12,
            'min_touches': 3
        },
        '3m': {
            'lookback': 25,
            'swing_window': 5,
            'zone_threshold': 0.002,
            'strength_periods': 15,
            'min_touches': 3
        },
        '5m': {
            'lookback': 30,
            'swing_window': 5,
            'zone_threshold': 0.0025,
            'strength_periods': 20,
            'min_touches': 3
        },
        '15m': {
            'lookback': 40,
            'swing_window': 6,
            'zone_threshold': 0.003,
            'strength_periods': 25,
            'min_touches': 3
        },
        '30m': {
            'lookback': 50,
            'swing_window': 7,
            'zone_threshold': 0.004,
            'strength_periods': 30,
            'min_touches': 4
        }
    }
    
    def __init__(self, timeframe: str = '5s'):
        """
        Initialize detector with timeframe-specific parameters
        
        Args:
            timeframe: Trading timeframe (5s, 15s, 30s, 1m, 3m, 5m, 15m, 30m)
        """
        self.timeframe = timeframe
        self.params = self.TIMEFRAME_PARAMS.get(timeframe, self.TIMEFRAME_PARAMS['5s'])
        logger.info(f"📊 S/R Detector initialized for {timeframe} with params: {self.params}")
    
    def detect_swing_highs(self, prices: pd.Series, window: int = None) -> List[Tuple[int, float]]:
        """
        Detect swing highs using price action algorithm
        
        Args:
            prices: Price series (typically high prices)
            window: Window size for swing detection (default: from params)
        
        Returns:
            List of (index, price) tuples for swing highs
        """
        if window is None:
            window = self.params['swing_window']
        
        swing_highs = []
        prices_array = prices.values
        
        for i in range(window, len(prices_array) - window):
            local_high = prices_array[i]
            is_swing_high = True
            
            # Check if this point is higher than surrounding points
            for j in range(1, window + 1):
                if prices_array[i - j] >= local_high or prices_array[i + j] >= local_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append((i, local_high))
        
        return swing_highs
    
    def detect_swing_lows(self, prices: pd.Series, window: int = None) -> List[Tuple[int, float]]:
        """
        Detect swing lows using price action algorithm
        
        Args:
            prices: Price series (typically low prices)
            window: Window size for swing detection (default: from params)
        
        Returns:
            List of (index, price) tuples for swing lows
        """
        if window is None:
            window = self.params['swing_window']
        
        swing_lows = []
        prices_array = prices.values
        
        for i in range(window, len(prices_array) - window):
            local_low = prices_array[i]
            is_swing_low = True
            
            # Check if this point is lower than surrounding points
            for j in range(1, window + 1):
                if prices_array[i - j] <= local_low or prices_array[i + j] <= local_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append((i, local_low))
        
        return swing_lows
    
    def calculate_pivot_points(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        Calculate pivot points and support/resistance levels
        
        Args:
            high: Period high
            low: Period low
            close: Period close
        
        Returns:
            Dictionary with pivot point and S/R levels
        """
        pivot = (high + low + close) / 3
        
        return {
            'pivot': pivot,
            'r1': (2 * pivot) - low,
            'r2': pivot + (high - low),
            'r3': high + 2 * (pivot - low),
            's1': (2 * pivot) - high,
            's2': pivot - (high - low),
            's3': low - 2 * (high - pivot)
        }
    
    def identify_key_levels(self, df: pd.DataFrame) -> Dict:
        """
        Identify key support and resistance levels using multiple methods
        
        Args:
            df: OHLC dataframe
        
        Returns:
            Dictionary with support/resistance levels and metadata
        """
        try:
            lookback = self.params['lookback']
            
            # Use recent data based on lookback period
            recent_df = df.tail(lookback * 2) if len(df) > lookback * 2 else df
            
            # Detect swing highs and lows
            swing_highs = self.detect_swing_highs(recent_df['high'])
            swing_lows = self.detect_swing_lows(recent_df['low'])
            
            # Calculate pivot points from most recent period
            recent_high = recent_df['high'].iloc[-lookback:].max()
            recent_low = recent_df['low'].iloc[-lookback:].min()
            recent_close = recent_df['close'].iloc[-1]
            
            pivots = self.calculate_pivot_points(recent_high, recent_low, recent_close)
            
            # Consolidate resistance levels
            resistance_levels = []
            if swing_highs:
                resistance_levels.extend([price for idx, price in swing_highs[-5:]])  # Last 5 swing highs
            resistance_levels.extend([pivots['r1'], pivots['r2']])
            
            # Consolidate support levels
            support_levels = []
            if swing_lows:
                support_levels.extend([price for idx, price in swing_lows[-5:]])  # Last 5 swing lows
            support_levels.extend([pivots['s1'], pivots['s2']])
            
            # Find strongest levels (cluster detection)
            resistance_zones = self._find_zones(resistance_levels, recent_close)
            support_zones = self._find_zones(support_levels, recent_close)
            
            # Get nearest levels
            nearest_resistance = self._find_nearest_level(resistance_zones, recent_close, 'above')
            nearest_support = self._find_nearest_level(support_zones, recent_close, 'below')
            
            return {
                'support_levels': support_zones,
                'resistance_levels': resistance_zones,
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'pivot_point': pivots['pivot'],
                'swing_highs': swing_highs[-3:] if swing_highs else [],
                'swing_lows': swing_lows[-3:] if swing_lows else [],
                'current_price': recent_close
            }
            
        except Exception as e:
            logger.error(f"Error identifying key levels: {e}")
            return {
                'support_levels': [],
                'resistance_levels': [],
                'nearest_support': None,
                'nearest_resistance': None,
                'pivot_point': None,
                'swing_highs': [],
                'swing_lows': [],
                'current_price': None
            }
    
    def _find_zones(self, levels: List[float], current_price: float) -> List[Dict]:
        """
        Find price zones from individual levels (cluster detection)
        
        Args:
            levels: List of price levels
            current_price: Current market price
        
        Returns:
            List of zone dictionaries with price and strength
        """
        if not levels:
            return []
        
        zone_threshold = self.params['zone_threshold'] * current_price
        zones = []
        
        # Sort levels
        sorted_levels = sorted(levels)
        
        # Cluster nearby levels into zones
        current_zone = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level - current_zone[-1]) <= zone_threshold:
                current_zone.append(level)
            else:
                # Save current zone
                zone_price = np.mean(current_zone)
                zone_strength = len(current_zone)
                zones.append({
                    'price': zone_price,
                    'strength': zone_strength,
                    'touches': zone_strength
                })
                current_zone = [level]
        
        # Add last zone
        if current_zone:
            zone_price = np.mean(current_zone)
            zone_strength = len(current_zone)
            zones.append({
                'price': zone_price,
                'strength': zone_strength,
                'touches': zone_strength
            })
        
        # Sort by strength
        zones.sort(key=lambda x: x['strength'], reverse=True)
        
        return zones[:5]  # Return top 5 strongest zones
    
    def _find_nearest_level(self, zones: List[Dict], current_price: float, direction: str) -> Optional[Dict]:
        """
        Find nearest support or resistance zone
        
        Args:
            zones: List of zone dictionaries
            current_price: Current market price
            direction: 'above' for resistance, 'below' for support
        
        Returns:
            Nearest zone dictionary or None
        """
        if not zones:
            return None
        
        if direction == 'above':
            # Find nearest resistance (above current price)
            above_zones = [z for z in zones if z['price'] > current_price]
            if above_zones:
                return min(above_zones, key=lambda x: abs(x['price'] - current_price))
        else:
            # Find nearest support (below current price)
            below_zones = [z for z in zones if z['price'] < current_price]
            if below_zones:
                return min(below_zones, key=lambda x: abs(x['price'] - current_price))
        
        return None
    
    def is_near_support_resistance(self, current_price: float, sr_levels: Dict) -> Dict:
        """
        Check if price is near support or resistance
        
        Args:
            current_price: Current market price
            sr_levels: Support/resistance levels from identify_key_levels()
        
        Returns:
            Dictionary with proximity information
        """
        zone_threshold = self.params['zone_threshold'] * current_price
        
        nearest_support = sr_levels.get('nearest_support')
        nearest_resistance = sr_levels.get('nearest_resistance')
        
        near_support = False
        near_resistance = False
        support_distance = None
        resistance_distance = None
        
        if nearest_support:
            support_distance = abs(current_price - nearest_support['price']) / current_price
            near_support = support_distance <= self.params['zone_threshold']
        
        if nearest_resistance:
            resistance_distance = abs(current_price - nearest_resistance['price']) / current_price
            near_resistance = resistance_distance <= self.params['zone_threshold']
        
        return {
            'near_support': near_support,
            'near_resistance': near_resistance,
            'support_distance_pct': support_distance * 100 if support_distance else None,
            'resistance_distance_pct': resistance_distance * 100 if resistance_distance else None,
            'support_level': nearest_support,
            'resistance_level': nearest_resistance
        }
    
    def detect_trend_reversal(self, df: pd.DataFrame, sr_levels: Dict) -> Dict:
        """
        Detect potential trend reversals at support/resistance zones
        
        Args:
            df: OHLC dataframe
            sr_levels: Support/resistance levels
        
        Returns:
            Dictionary with reversal information
        """
        try:
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            
            # Check proximity to S/R
            proximity = self.is_near_support_resistance(current_price, sr_levels)
            
            # Detect bounce patterns
            bounce_off_support = False
            bounce_off_resistance = False
            
            if proximity['near_support'] and current_price > prev_price:
                # Price was near support and now moving up - potential bounce
                bounce_off_support = True
            
            if proximity['near_resistance'] and current_price < prev_price:
                # Price was near resistance and now moving down - potential reversal
                bounce_off_resistance = True
            
            # Calculate reversal strength
            reversal_strength = 0
            reversal_type = None
            
            if bounce_off_support:
                reversal_strength = proximity['support_level']['strength'] if proximity['support_level'] else 0
                reversal_type = 'BOUNCE_UP'
            elif bounce_off_resistance:
                reversal_strength = proximity['resistance_level']['strength'] if proximity['resistance_level'] else 0
                reversal_type = 'REVERSAL_DOWN'
            
            return {
                'reversal_detected': bounce_off_support or bounce_off_resistance,
                'reversal_type': reversal_type,
                'reversal_strength': reversal_strength,
                'bounce_off_support': bounce_off_support,
                'bounce_off_resistance': bounce_off_resistance,
                'proximity': proximity
            }
            
        except Exception as e:
            logger.error(f"Error detecting trend reversal: {e}")
            return {
                'reversal_detected': False,
                'reversal_type': None,
                'reversal_strength': 0,
                'bounce_off_support': False,
                'bounce_off_resistance': False,
                'proximity': {}
            }
    
    def validate_signal_direction(self, signal: str, current_price: float, sr_levels: Dict) -> Dict:
        """
        Validate if signal direction makes sense given S/R levels
        Prevents wrong-direction signals during trend reversals
        
        Args:
            signal: Proposed signal direction ('CALL' or 'PUT')
            current_price: Current market price
            sr_levels: Support/resistance levels
        
        Returns:
            Dictionary with validation result and reasoning
        """
        proximity = self.is_near_support_resistance(current_price, sr_levels)
        
        # Default: signal is valid
        valid = True
        confidence_adjustment = 0
        reasoning = []
        
        # CALL signal validation
        if signal == 'CALL':
            if proximity['near_resistance']:
                # CALL signal near resistance is risky
                valid = False
                confidence_adjustment = -15
                reasoning.append(f"⚠️ CALL rejected: Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
                reasoning.append("💡 High probability of reversal DOWN at resistance")
            elif proximity['near_support']:
                # CALL signal near support is good (bounce expected)
                confidence_adjustment = +8
                reasoning.append(f"✅ CALL confirmed: Price near support ({proximity['support_distance_pct']:.2f}% away)")
                reasoning.append("💡 Bounce up expected from support zone")
        
        # PUT signal validation
        elif signal == 'PUT':
            if proximity['near_support']:
                # PUT signal near support is risky
                valid = False
                confidence_adjustment = -15
                reasoning.append(f"⚠️ PUT rejected: Price near support ({proximity['support_distance_pct']:.2f}% away)")
                reasoning.append("💡 High probability of bounce UP at support")
            elif proximity['near_resistance']:
                # PUT signal near resistance is good (reversal expected)
                confidence_adjustment = +8
                reasoning.append(f"✅ PUT confirmed: Price near resistance ({proximity['resistance_distance_pct']:.2f}% away)")
                reasoning.append("💡 Reversal down expected from resistance zone")
        
        return {
            'valid': valid,
            'confidence_adjustment': confidence_adjustment,
            'reasoning': reasoning,
            'proximity': proximity
        }

# Create singleton instance factory
def get_detector(timeframe: str) -> SupportResistanceDetector:
    """Get S/R detector instance for specific timeframe"""
    return SupportResistanceDetector(timeframe)
