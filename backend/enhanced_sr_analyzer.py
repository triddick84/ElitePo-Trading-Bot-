"""
Enhanced Support & Resistance Analyzer
Advanced bounce and reversal detection for accurate signal generation
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SRLevel:
    """Support or Resistance level with metadata"""
    price: float
    type: str  # 'SUPPORT' or 'RESISTANCE'
    strength: float  # 0-100
    touches: int  # Number of times price touched this level
    last_touch: int  # Index of last touch
    is_broken: bool  # Has price broken through?
    bounce_count: int  # Number of successful bounces
    rejection_strength: float  # How strongly price rejected from level


class EnhancedSRAnalyzer:
    """
    Advanced Support & Resistance Analysis with:
    - Dynamic level detection using multiple algorithms
    - Bounce pattern recognition
    - Reversal zone identification
    - Price action context
    - Level strength scoring
    - Touch and test analysis
    """
    
    def __init__(self):
        self.min_touches = 2  # Minimum touches to confirm a level
        self.max_levels = 10  # Maximum S/R levels to track
        self.proximity_pct = 0.002  # 0.2% proximity threshold
        self.strength_decay = 0.95  # Decay factor for old levels
        
    def analyze(self, candles: List[Dict], current_price: float = None) -> Dict:
        """
        Comprehensive S/R analysis with bounce and reversal detection
        
        Args:
            candles: List of OHLCV candles
            current_price: Current market price (defaults to last close)
        
        Returns:
            Complete analysis including levels, bounces, reversals, and signals
        """
        if not candles or len(candles) < 20:
            return self._empty_analysis()
        
        df = pd.DataFrame(candles)
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna()
        
        if len(df) < 20:
            return self._empty_analysis()
        
        current_price = current_price or float(df.iloc[-1]['close'])
        
        # Step 1: Identify all potential S/R levels
        levels = self._identify_levels(df)
        
        # Step 2: Calculate level strength
        levels = self._calculate_strength(df, levels)
        
        # Step 3: Detect bounces
        bounce_analysis = self._detect_bounces(df, levels, current_price)
        
        # Step 4: Identify reversal zones
        reversal_zones = self._identify_reversal_zones(df, levels, current_price)
        
        # Step 5: Analyze price action near levels
        price_action = self._analyze_price_action(df, levels, current_price)
        
        # Step 6: Generate trading signals
        signals = self._generate_signals(levels, bounce_analysis, reversal_zones, price_action, current_price)
        
        return {
            'current_price': current_price,
            'levels': [self._level_to_dict(lvl) for lvl in levels[:self.max_levels]],
            'nearest_support': self._find_nearest_support(levels, current_price),
            'nearest_resistance': self._find_nearest_resistance(levels, current_price),
            'bounce_analysis': bounce_analysis,
            'reversal_zones': reversal_zones,
            'price_action': price_action,
            'signals': signals,
            'summary': self._generate_summary(levels, bounce_analysis, reversal_zones, current_price)
        }
    
    def _identify_levels(self, df: pd.DataFrame) -> List[SRLevel]:
        """Identify S/R levels using multiple methods"""
        levels = []
        
        # Method 1: Swing Highs and Lows
        swing_levels = self._find_swing_levels(df)
        levels.extend(swing_levels)
        
        # Method 2: Historical Highs and Lows
        historical_levels = self._find_historical_levels(df)
        levels.extend(historical_levels)
        
        # Method 3: Pivot Points
        pivot_levels = self._calculate_pivot_points(df)
        levels.extend(pivot_levels)
        
        # Method 4: Volume Profile (price clusters with high volume)
        volume_levels = self._find_volume_levels(df)
        levels.extend(volume_levels)
        
        # Merge nearby levels
        levels = self._merge_nearby_levels(levels)
        
        return levels
    
    def _find_swing_levels(self, df: pd.DataFrame) -> List[SRLevel]:
        """Find swing highs and lows"""
        levels = []
        window = 5  # Look at 5 candles on each side
        
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(window, len(df) - window):
            # Swing High
            if highs[i] == max(highs[i-window:i+window+1]):
                levels.append(SRLevel(
                    price=float(highs[i]),
                    type='RESISTANCE',
                    strength=50.0,
                    touches=1,
                    last_touch=i,
                    is_broken=False,
                    bounce_count=0,
                    rejection_strength=0.0
                ))
            
            # Swing Low
            if lows[i] == min(lows[i-window:i+window+1]):
                levels.append(SRLevel(
                    price=float(lows[i]),
                    type='SUPPORT',
                    strength=50.0,
                    touches=1,
                    last_touch=i,
                    is_broken=False,
                    bounce_count=0,
                    rejection_strength=0.0
                ))
        
        return levels
    
    def _find_historical_levels(self, df: pd.DataFrame) -> List[SRLevel]:
        """Find significant historical highs and lows"""
        levels = []
        
        # Recent high/low (last 20 candles)
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        
        levels.extend([
            SRLevel(recent_high, 'RESISTANCE', 60.0, 1, len(df)-1, False, 0, 0.0),
            SRLevel(recent_low, 'SUPPORT', 60.0, 1, len(df)-1, False, 0, 0.0)
        ])
        
        # Overall high/low
        overall_high = df['high'].max()
        overall_low = df['low'].min()
        
        levels.extend([
            SRLevel(overall_high, 'RESISTANCE', 80.0, 1, len(df)-1, False, 0, 0.0),
            SRLevel(overall_low, 'SUPPORT', 80.0, 1, len(df)-1, False, 0, 0.0)
        ])
        
        return levels
    
    def _calculate_pivot_points(self, df: pd.DataFrame) -> List[SRLevel]:
        """Calculate pivot points from recent data"""
        levels = []
        
        # Use last complete period
        high = df['high'].tail(20).max()
        low = df['low'].tail(20).min()
        close = df['close'].tail(20).mean()
        
        # Standard Pivot
        pivot = (high + low + close) / 3
        
        # Support and Resistance levels
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        
        levels.extend([
            SRLevel(float(r2), 'RESISTANCE', 70.0, 0, 0, False, 0, 0.0),
            SRLevel(float(r1), 'RESISTANCE', 65.0, 0, 0, False, 0, 0.0),
            SRLevel(float(s1), 'SUPPORT', 65.0, 0, 0, False, 0, 0.0),
            SRLevel(float(s2), 'SUPPORT', 70.0, 0, 0, False, 0, 0.0),
        ])
        
        return levels
    
    def _find_volume_levels(self, df: pd.DataFrame) -> List[SRLevel]:
        """Find price levels with high volume"""
        if 'volume' not in df.columns or df['volume'].sum() == 0:
            return []
        
        levels = []
        
        # Create price bins
        price_range = df['high'].max() - df['low'].min()
        num_bins = min(20, len(df) // 5)
        
        df['price_bin'] = pd.cut(df['close'], bins=num_bins)
        volume_by_price = df.groupby('price_bin')['volume'].sum()
        
        # Find top volume levels
        top_volumes = volume_by_price.nlargest(3)
        
        for price_bin, volume in top_volumes.items():
            mid_price = (price_bin.left + price_bin.right) / 2
            
            # Determine if support or resistance based on current price
            level_type = 'SUPPORT' if mid_price < df['close'].iloc[-1] else 'RESISTANCE'
            
            levels.append(SRLevel(
                float(mid_price),
                level_type,
                75.0,
                0,
                0,
                False,
                0,
                0.0
            ))
        
        return levels
    
    def _merge_nearby_levels(self, levels: List[SRLevel]) -> List[SRLevel]:
        """Merge levels that are very close together"""
        if not levels:
            return []
        
        # Sort by price
        levels.sort(key=lambda x: x.price)
        
        merged = []
        current = levels[0]
        
        for next_level in levels[1:]:
            # Calculate proximity
            if abs(next_level.price - current.price) / current.price < self.proximity_pct:
                # Merge levels
                current = SRLevel(
                    price=(current.price + next_level.price) / 2,
                    type=current.type,
                    strength=max(current.strength, next_level.strength),
                    touches=current.touches + next_level.touches,
                    last_touch=max(current.last_touch, next_level.last_touch),
                    is_broken=current.is_broken or next_level.is_broken,
                    bounce_count=current.bounce_count + next_level.bounce_count,
                    rejection_strength=max(current.rejection_strength, next_level.rejection_strength)
                )
            else:
                merged.append(current)
                current = next_level
        
        merged.append(current)
        return merged
    
    def _calculate_strength(self, df: pd.DataFrame, levels: List[SRLevel]) -> List[SRLevel]:
        """Calculate strength of each S/R level based on touches and rejections"""
        
        for level in levels:
            touches = 0
            rejections = 0
            bounces = 0
            
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            for i in range(len(df)):
                price_range = highs[i] - lows[i]
                
                # Check if price touched this level
                if abs(highs[i] - level.price) / level.price < self.proximity_pct or \
                   abs(lows[i] - level.price) / level.price < self.proximity_pct:
                    touches += 1
                    level.last_touch = i
                    
                    # Check for rejection (price came near but didn't break)
                    if i < len(df) - 1:
                        next_close = closes[i + 1]
                        
                        if level.type == 'RESISTANCE':
                            # Check if price rejected downward
                            if highs[i] >= level.price and next_close < level.price:
                                rejections += 1
                                bounces += 1
                                level.rejection_strength += abs(next_close - level.price) / price_range * 100
                        else:  # SUPPORT
                            # Check if price rejected upward
                            if lows[i] <= level.price and next_close > level.price:
                                rejections += 1
                                bounces += 1
                                level.rejection_strength += abs(next_close - level.price) / price_range * 100
            
            level.touches = touches
            level.bounce_count = bounces
            
            # Calculate strength score
            base_strength = level.strength
            touch_bonus = min(touches * 10, 30)
            bounce_bonus = min(bounces * 15, 40)
            rejection_bonus = min(level.rejection_strength, 20)
            
            level.strength = min(base_strength + touch_bonus + bounce_bonus + rejection_bonus, 100.0)
        
        # Sort by strength
        levels.sort(key=lambda x: x.strength, reverse=True)
        
        return levels
    
    def _detect_bounces(self, df: pd.DataFrame, levels: List[SRLevel], current_price: float) -> Dict:
        """Detect bounce patterns near S/R levels"""
        
        bounces = {
            'recent_bounce': None,
            'bounce_in_progress': False,
            'bounce_direction': None,
            'bounce_strength': 0,
            'expected_target': None
        }
        
        if len(df) < 5:
            return bounces
        
        recent_candles = df.tail(5)
        last_candle = df.iloc[-1]
        
        # Find nearest level
        nearest_level = None
        min_distance = float('inf')
        
        for level in levels:
            distance = abs(current_price - level.price) / current_price
            if distance < min_distance:
                min_distance = distance
                nearest_level = level
        
        if nearest_level and min_distance < self.proximity_pct * 3:  # Within 3x proximity
            # Check for bounce pattern
            if nearest_level.type == 'SUPPORT':
                # Check if price is bouncing up from support
                low_touches_level = recent_candles['low'].min() <= nearest_level.price * 1.001
                price_moving_up = current_price > recent_candles['close'].iloc[0]
                
                if low_touches_level and price_moving_up:
                    bounces['recent_bounce'] = nearest_level.price
                    bounces['bounce_in_progress'] = True
                    bounces['bounce_direction'] = 'UP'
                    bounces['bounce_strength'] = nearest_level.strength
                    
                    # Calculate target (nearest resistance)
                    target = self._find_nearest_resistance(levels, current_price)
                    bounces['expected_target'] = target
            
            elif nearest_level.type == 'RESISTANCE':
                # Check if price is bouncing down from resistance
                high_touches_level = recent_candles['high'].max() >= nearest_level.price * 0.999
                price_moving_down = current_price < recent_candles['close'].iloc[0]
                
                if high_touches_level and price_moving_down:
                    bounces['recent_bounce'] = nearest_level.price
                    bounces['bounce_in_progress'] = True
                    bounces['bounce_direction'] = 'DOWN'
                    bounces['bounce_strength'] = nearest_level.strength
                    
                    # Calculate target (nearest support)
                    target = self._find_nearest_support(levels, current_price)
                    bounces['expected_target'] = target
        
        return bounces
    
    def _identify_reversal_zones(self, df: pd.DataFrame, levels: List[SRLevel], current_price: float) -> Dict:
        """Identify potential reversal zones"""
        
        reversals = {
            'in_reversal_zone': False,
            'reversal_type': None,  # 'BULLISH' or 'BEARISH'
            'zone_strength': 0,
            'confluence_levels': [],
            'probability': 0
        }
        
        # Check if multiple S/R levels are close together (confluence)
        confluence_zones = []
        
        for i, level1 in enumerate(levels[:5]):  # Check top 5 levels
            nearby_levels = [level1]
            
            for level2 in levels[i+1:i+4]:
                if abs(level1.price - level2.price) / level1.price < self.proximity_pct * 2:
                    nearby_levels.append(level2)
            
            if len(nearby_levels) >= 2:  # Confluence found
                avg_price = np.mean([l.price for l in nearby_levels])
                avg_strength = np.mean([l.strength for l in nearby_levels])
                
                confluence_zones.append({
                    'price': avg_price,
                    'strength': avg_strength,
                    'count': len(nearby_levels),
                    'levels': nearby_levels
                })
        
        # Check if current price is near a confluence zone
        for zone in confluence_zones:
            distance = abs(current_price - zone['price']) / current_price
            
            if distance < self.proximity_pct * 3:
                reversals['in_reversal_zone'] = True
                reversals['zone_strength'] = zone['strength']
                reversals['confluence_levels'] = [l.price for l in zone['levels']]
                
                # Determine reversal type based on zone type
                support_count = sum(1 for l in zone['levels'] if l.type == 'SUPPORT')
                resistance_count = len(zone['levels']) - support_count
                
                if support_count > resistance_count:
                    reversals['reversal_type'] = 'BULLISH'  # Bounce up from support
                else:
                    reversals['reversal_type'] = 'BEARISH'  # Bounce down from resistance
                
                # Calculate probability based on strength and confluence
                reversals['probability'] = min(
                    (zone['strength'] / 100) * (zone['count'] / 5) * 100,
                    90.0
                )
        
        return reversals
    
    def _analyze_price_action(self, df: pd.DataFrame, levels: List[SRLevel], current_price: float) -> Dict:
        """Analyze price action context"""
        
        action = {
            'position': 'MIDDLE',  # NEAR_SUPPORT, NEAR_RESISTANCE, MIDDLE, BREAKOUT
            'momentum': 'NEUTRAL',  # BULLISH, BEARISH, NEUTRAL
            'volatility': 'NORMAL',  # LOW, NORMAL, HIGH
            'trend': 'SIDEWAYS',  # UPTREND, DOWNTREND, SIDEWAYS
            'distance_to_support': 0,
            'distance_to_resistance': 0
        }
        
        if len(df) < 10:
            return action
        
        # Find nearest support and resistance
        nearest_support = self._find_nearest_support(levels, current_price)
        nearest_resistance = self._find_nearest_resistance(levels, current_price)
        
        if nearest_support:
            action['distance_to_support'] = ((current_price - nearest_support) / current_price) * 100
        
        if nearest_resistance:
            action['distance_to_resistance'] = ((nearest_resistance - current_price) / current_price) * 100
        
        # Determine position
        if action['distance_to_support'] < 0.5:
            action['position'] = 'NEAR_SUPPORT'
        elif action['distance_to_resistance'] < 0.5:
            action['position'] = 'NEAR_RESISTANCE'
        elif action['distance_to_support'] < -0.5:
            action['position'] = 'BREAKOUT_BELOW'
        elif action['distance_to_resistance'] < -0.5:
            action['position'] = 'BREAKOUT_ABOVE'
        
        # Momentum analysis
        recent_closes = df['close'].tail(5).values
        if recent_closes[-1] > recent_closes[0] * 1.002:
            action['momentum'] = 'BULLISH'
        elif recent_closes[-1] < recent_closes[0] * 0.998:
            action['momentum'] = 'BEARISH'
        
        # Volatility analysis
        recent_range = (df['high'].tail(10) - df['low'].tail(10)) / df['close'].tail(10)
        avg_volatility = recent_range.mean()
        
        if avg_volatility > 0.01:
            action['volatility'] = 'HIGH'
        elif avg_volatility < 0.003:
            action['volatility'] = 'LOW'
        
        # Trend analysis
        sma_20 = df['close'].tail(20).mean()
        if current_price > sma_20 * 1.01:
            action['trend'] = 'UPTREND'
        elif current_price < sma_20 * 0.99:
            action['trend'] = 'DOWNTREND'
        
        return action
    
    def _generate_signals(
        self, 
        levels: List[SRLevel], 
        bounce: Dict, 
        reversal: Dict, 
        action: Dict,
        current_price: float
    ) -> Dict:
        """Generate trading signals based on S/R analysis"""
        
        signals = {
            'direction': 'NEUTRAL',
            'confidence': 0,
            'reason': [],
            'entry_price': current_price,
            'stop_loss': None,
            'take_profit': None,
            'risk_reward': 0
        }
        
        reasons = []
        confidence = 50
        
        # Signal 1: Bounce from S/R level
        if bounce['bounce_in_progress']:
            if bounce['bounce_direction'] == 'UP':
                signals['direction'] = 'CALL'
                confidence += 15
                reasons.append(f"Bouncing up from support at {bounce['recent_bounce']:.5f}")
                
                signals['stop_loss'] = bounce['recent_bounce'] * 0.999
                if bounce['expected_target']:
                    signals['take_profit'] = bounce['expected_target']
            
            elif bounce['bounce_direction'] == 'DOWN':
                signals['direction'] = 'PUT'
                confidence += 15
                reasons.append(f"Bouncing down from resistance at {bounce['recent_bounce']:.5f}")
                
                signals['stop_loss'] = bounce['recent_bounce'] * 1.001
                if bounce['expected_target']:
                    signals['take_profit'] = bounce['expected_target']
            
            confidence += bounce['bounce_strength'] * 0.2
        
        # Signal 2: Reversal zone
        if reversal['in_reversal_zone']:
            if reversal['reversal_type'] == 'BULLISH':
                if signals['direction'] == 'CALL' or signals['direction'] == 'NEUTRAL':
                    signals['direction'] = 'CALL'
                    confidence += reversal['probability'] * 0.3
                    reasons.append(f"In bullish reversal zone ({len(reversal['confluence_levels'])} level confluence)")
            
            elif reversal['reversal_type'] == 'BEARISH':
                if signals['direction'] == 'PUT' or signals['direction'] == 'NEUTRAL':
                    signals['direction'] = 'PUT'
                    confidence += reversal['probability'] * 0.3
                    reasons.append(f"In bearish reversal zone ({len(reversal['confluence_levels'])} level confluence)")
        
        # Signal 3: Price action confirmation
        if action['position'] == 'NEAR_SUPPORT' and action['momentum'] == 'BULLISH':
            if signals['direction'] == 'CALL' or signals['direction'] == 'NEUTRAL':
                signals['direction'] = 'CALL'
                confidence += 10
                reasons.append("Near support with bullish momentum")
        
        elif action['position'] == 'NEAR_RESISTANCE' and action['momentum'] == 'BEARISH':
            if signals['direction'] == 'PUT' or signals['direction'] == 'NEUTRAL':
                signals['direction'] = 'PUT'
                confidence += 10
                reasons.append("Near resistance with bearish momentum")
        
        # Reduce confidence in high volatility
        if action['volatility'] == 'HIGH':
            confidence *= 0.9
            reasons.append("High volatility (reduced confidence)")
        
        signals['confidence'] = min(confidence, 95)
        signals['reason'] = reasons
        
        # Calculate risk-reward if we have stop loss and take profit
        if signals['stop_loss'] and signals['take_profit']:
            risk = abs(current_price - signals['stop_loss'])
            reward = abs(signals['take_profit'] - current_price)
            signals['risk_reward'] = round(reward / risk if risk > 0 else 0, 2)
        
        return signals
    
    def _find_nearest_support(self, levels: List[SRLevel], price: float) -> Optional[float]:
        """Find nearest support level below current price"""
        supports = [l for l in levels if l.type == 'SUPPORT' and l.price < price]
        if supports:
            return max(supports, key=lambda x: x.price).price
        return None
    
    def _find_nearest_resistance(self, levels: List[SRLevel], price: float) -> Optional[float]:
        """Find nearest resistance level above current price"""
        resistances = [l for l in levels if l.type == 'RESISTANCE' and l.price > price]
        if resistances:
            return min(resistances, key=lambda x: x.price).price
        return None
    
    def _level_to_dict(self, level: SRLevel) -> Dict:
        """Convert SRLevel to dictionary"""
        return {
            'price': round(level.price, 5),
            'type': level.type,
            'strength': round(level.strength, 1),
            'touches': level.touches,
            'bounces': level.bounce_count,
            'rejection_strength': round(level.rejection_strength, 1)
        }
    
    def _generate_summary(self, levels: List[SRLevel], bounce: Dict, reversal: Dict, current_price: float) -> str:
        """Generate human-readable summary"""
        parts = []
        
        nearest_support = self._find_nearest_support(levels, current_price)
        nearest_resistance = self._find_nearest_resistance(levels, current_price)
        
        if nearest_support:
            dist = ((current_price - nearest_support) / current_price) * 100
            parts.append(f"Support {dist:.2f}% below")
        
        if nearest_resistance:
            dist = ((nearest_resistance - current_price) / current_price) * 100
            parts.append(f"Resistance {dist:.2f}% above")
        
        if bounce['bounce_in_progress']:
            parts.append(f"Bounce {bounce['bounce_direction']} detected")
        
        if reversal['in_reversal_zone']:
            parts.append(f"{reversal['reversal_type']} reversal zone")
        
        return ', '.join(parts) if parts else 'No significant levels nearby'
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis"""
        return {
            'current_price': 0,
            'levels': [],
            'nearest_support': None,
            'nearest_resistance': None,
            'bounce_analysis': {'bounce_in_progress': False},
            'reversal_zones': {'in_reversal_zone': False},
            'price_action': {},
            'signals': {'direction': 'NEUTRAL', 'confidence': 0, 'reason': []},
            'summary': 'Insufficient data'
        }


# Global instance
enhanced_sr_analyzer = EnhancedSRAnalyzer()
