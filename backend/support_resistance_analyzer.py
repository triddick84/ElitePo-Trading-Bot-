"""
Support & Resistance Analyzer - Advanced Level Detection
Identifies key price levels, swing points, and reversal zones
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SupportResistanceAnalyzer:
    """
    Analyzes support and resistance levels using multiple methods:
    - Pivot Points (Standard, Fibonacci, Camarilla)
    - Swing Highs/Lows
    - Price Clustering
    - Volume Profile levels
    """
    
    def __init__(self):
        # Timeframe-specific lookback periods (optimized for accuracy)
        self.lookback_periods = {
            '5s': {'pivot': 20, 'swing': 10, 'cluster': 15},
            '15s': {'pivot': 30, 'swing': 15, 'cluster': 20},
            '30s': {'pivot': 40, 'swing': 20, 'cluster': 25},
            '1m': {'pivot': 50, 'swing': 25, 'cluster': 30},
            '2m': {'pivot': 60, 'swing': 30, 'cluster': 35},
            '3m': {'pivot': 70, 'swing': 35, 'cluster': 40},
            '5m': {'pivot': 100, 'swing': 50, 'cluster': 50}
        }
        
        # Distance threshold for level proximity (as % of price)
        self.proximity_threshold = {
            '5s': 0.001,   # 0.1% for ultra-short
            '15s': 0.0015, # 0.15%
            '30s': 0.002,  # 0.2%
            '1m': 0.003,   # 0.3%
            '2m': 0.004,   # 0.4%
            '3m': 0.005,   # 0.5%
            '5m': 0.008    # 0.8%
        }
    
    def analyze_levels(self, candles: List[Dict], timeframe: str = '1m') -> Dict:
        """
        Main analysis function - identifies all support/resistance levels
        
        Args:
            candles: List of OHLCV candles
            timeframe: Chart timeframe (5s, 15s, 30s, 1m, etc.)
            
        Returns:
            Dict with support/resistance levels and current price position
        """
        try:
            if not candles or len(candles) < 10:
                logger.warning("Insufficient candles for S/R analysis")
                return self._default_levels()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Ensure required columns
            if not all(col in df.columns for col in ['high', 'low', 'close', 'open']):
                logger.warning("Missing required OHLC columns")
                return self._default_levels()
            
            # Convert to numeric
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            
            # Drop NaN
            df = df.dropna(subset=['high', 'low', 'close', 'open'])
            
            if len(df) < 10:
                logger.warning("Too few valid candles after cleaning")
                return self._default_levels()
            
            current_price = float(df['close'].iloc[-1])
            
            # Get timeframe-specific settings
            settings = self.lookback_periods.get(timeframe, self.lookback_periods['1m'])
            proximity = self.proximity_threshold.get(timeframe, self.proximity_threshold['1m'])
            
            # Calculate different types of levels
            pivot_levels = self._calculate_pivot_points(df, settings['pivot'])
            swing_levels = self._calculate_swing_levels(df, settings['swing'])
            cluster_levels = self._calculate_price_clusters(df, settings['cluster'])
            
            # Combine and rank levels
            all_levels = self._combine_levels(
                pivot_levels, 
                swing_levels, 
                cluster_levels,
                current_price,
                proximity
            )
            
            # Identify nearest levels
            nearest_support = self._find_nearest_support(all_levels['support'], current_price)
            nearest_resistance = self._find_nearest_resistance(all_levels['resistance'], current_price)
            
            # Calculate price position relative to levels
            position_analysis = self._analyze_price_position(
                current_price,
                nearest_support,
                nearest_resistance,
                all_levels
            )
            
            result = {
                'current_price': current_price,
                'timeframe': timeframe,
                'support_levels': all_levels['support'][:5],  # Top 5
                'resistance_levels': all_levels['resistance'][:5],  # Top 5
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'distance_to_support': position_analysis['distance_to_support'],
                'distance_to_resistance': position_analysis['distance_to_resistance'],
                'price_position': position_analysis['position'],  # 'near_support', 'near_resistance', 'neutral'
                'reversal_risk': position_analysis['reversal_risk'],  # 'high', 'medium', 'low'
                'trade_recommendation': position_analysis['recommendation'],  # 'buy', 'sell', 'wait'
                'key_levels': {
                    'pivot_point': pivot_levels.get('pivot'),
                    'r1': pivot_levels.get('r1'),
                    'r2': pivot_levels.get('r2'),
                    's1': pivot_levels.get('s1'),
                    's2': pivot_levels.get('s2')
                }
            }
            
            logger.info(f"📊 S/R Analysis ({timeframe}): Position={position_analysis['position']}, Risk={position_analysis['reversal_risk']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in S/R analysis: {e}")
            return self._default_levels()
    
    def _calculate_pivot_points(self, df: pd.DataFrame, lookback: int) -> Dict:
        """Calculate Standard Pivot Points"""
        try:
            recent_data = df.tail(lookback)
            
            high = float(recent_data['high'].max())
            low = float(recent_data['low'].min())
            close = float(df['close'].iloc[-1])
            
            # Standard Pivot Point formula
            pivot = (high + low + close) / 3
            
            # Support and Resistance levels
            r1 = (2 * pivot) - low
            r2 = pivot + (high - low)
            r3 = high + 2 * (pivot - low)
            
            s1 = (2 * pivot) - high
            s2 = pivot - (high - low)
            s3 = low - 2 * (high - pivot)
            
            return {
                'pivot': pivot,
                'r1': r1, 'r2': r2, 'r3': r3,
                's1': s1, 's2': s2, 's3': s3
            }
        except Exception as e:
            logger.error(f"Error calculating pivots: {e}")
            return {}
    
    def _calculate_swing_levels(self, df: pd.DataFrame, lookback: int) -> Dict:
        """Identify swing highs and lows"""
        try:
            recent_data = df.tail(lookback * 2)  # Need more data for swing detection
            
            swing_highs = []
            swing_lows = []
            
            highs = recent_data['high'].values
            lows = recent_data['low'].values
            
            # Detect swing highs (local maxima)
            for i in range(2, len(highs) - 2):
                if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                    highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                    swing_highs.append(float(highs[i]))
            
            # Detect swing lows (local minima)
            for i in range(2, len(lows) - 2):
                if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                    swing_lows.append(float(lows[i]))
            
            return {
                'swing_highs': swing_highs[-5:] if swing_highs else [],  # Last 5
                'swing_lows': swing_lows[-5:] if swing_lows else []      # Last 5
            }
        except Exception as e:
            logger.error(f"Error calculating swings: {e}")
            return {'swing_highs': [], 'swing_lows': []}
    
    def _calculate_price_clusters(self, df: pd.DataFrame, lookback: int) -> Dict:
        """Find price clustering zones (areas of repeated touches)"""
        try:
            recent_data = df.tail(lookback)
            
            all_prices = []
            for _, row in recent_data.iterrows():
                all_prices.extend([row['high'], row['low'], row['close']])
            
            if not all_prices:
                return {'clusters': []}
            
            # Use histogram to find price clusters
            hist, bin_edges = np.histogram(all_prices, bins=20)
            
            # Find bins with high frequency (clusters)
            threshold = np.percentile(hist, 70)  # Top 30%
            cluster_indices = np.where(hist >= threshold)[0]
            
            clusters = []
            for idx in cluster_indices:
                cluster_price = (bin_edges[idx] + bin_edges[idx + 1]) / 2
                clusters.append(float(cluster_price))
            
            return {'clusters': clusters}
        except Exception as e:
            logger.error(f"Error calculating clusters: {e}")
            return {'clusters': []}
    
    def _combine_levels(self, pivots: Dict, swings: Dict, clusters: Dict, 
                       current_price: float, proximity: float) -> Dict:
        """Combine all levels and separate into support/resistance"""
        
        all_resistance = []
        all_support = []
        
        # Add pivot levels
        for key, value in pivots.items():
            if value and key != 'pivot':
                if key.startswith('r') and value > current_price:
                    all_resistance.append({'price': value, 'type': 'pivot', 'strength': 3})
                elif key.startswith('s') and value < current_price:
                    all_support.append({'price': value, 'type': 'pivot', 'strength': 3})
        
        # Add pivot point as both support and resistance
        if pivots.get('pivot'):
            pivot_price = pivots['pivot']
            if pivot_price > current_price:
                all_resistance.append({'price': pivot_price, 'type': 'pivot_point', 'strength': 4})
            else:
                all_support.append({'price': pivot_price, 'type': 'pivot_point', 'strength': 4})
        
        # Add swing levels
        for swing_high in swings.get('swing_highs', []):
            if swing_high > current_price:
                all_resistance.append({'price': swing_high, 'type': 'swing_high', 'strength': 2})
        
        for swing_low in swings.get('swing_lows', []):
            if swing_low < current_price:
                all_support.append({'price': swing_low, 'type': 'swing_low', 'strength': 2})
        
        # Add cluster levels
        for cluster in clusters.get('clusters', []):
            if cluster > current_price * (1 + proximity):
                all_resistance.append({'price': cluster, 'type': 'cluster', 'strength': 1})
            elif cluster < current_price * (1 - proximity):
                all_support.append({'price': cluster, 'type': 'cluster', 'strength': 1})
        
        # Merge nearby levels
        all_resistance = self._merge_nearby_levels(all_resistance, proximity)
        all_support = self._merge_nearby_levels(all_support, proximity)
        
        # Sort by strength and distance
        all_resistance.sort(key=lambda x: (x['strength'], -abs(x['price'] - current_price)), reverse=True)
        all_support.sort(key=lambda x: (x['strength'], -abs(x['price'] - current_price)), reverse=True)
        
        return {
            'resistance': all_resistance,
            'support': all_support
        }
    
    def _merge_nearby_levels(self, levels: List[Dict], proximity: float) -> List[Dict]:
        """Merge levels that are very close to each other"""
        if not levels:
            return []
        
        merged = []
        levels_sorted = sorted(levels, key=lambda x: x['price'])
        
        current_group = [levels_sorted[0]]
        
        for level in levels_sorted[1:]:
            if abs(level['price'] - current_group[-1]['price']) / current_group[-1]['price'] < proximity:
                current_group.append(level)
            else:
                # Merge current group
                avg_price = sum(l['price'] for l in current_group) / len(current_group)
                max_strength = max(l['strength'] for l in current_group)
                merged.append({
                    'price': avg_price,
                    'type': 'merged',
                    'strength': max_strength,
                    'count': len(current_group)
                })
                current_group = [level]
        
        # Merge last group
        if current_group:
            avg_price = sum(l['price'] for l in current_group) / len(current_group)
            max_strength = max(l['strength'] for l in current_group)
            merged.append({
                'price': avg_price,
                'type': 'merged',
                'strength': max_strength,
                'count': len(current_group)
            })
        
        return merged
    
    def _find_nearest_support(self, supports: List[Dict], current_price: float) -> Optional[Dict]:
        """Find the nearest support level below current price"""
        if not supports:
            return None
        
        supports_below = [s for s in supports if s['price'] < current_price]
        if not supports_below:
            return None
        
        return max(supports_below, key=lambda x: x['price'])
    
    def _find_nearest_resistance(self, resistances: List[Dict], current_price: float) -> Optional[Dict]:
        """Find the nearest resistance level above current price"""
        if not resistances:
            return None
        
        resistances_above = [r for r in resistances if r['price'] > current_price]
        if not resistances_above:
            return None
        
        return min(resistances_above, key=lambda x: x['price'])
    
    def _analyze_price_position(self, current_price: float, nearest_support: Optional[Dict],
                                nearest_resistance: Optional[Dict], all_levels: Dict) -> Dict:
        """Analyze where price is relative to key levels"""
        
        # Calculate distances
        distance_to_support = 999  # Large default
        distance_to_resistance = 999
        
        if nearest_support:
            distance_to_support = ((current_price - nearest_support['price']) / current_price) * 100
        
        if nearest_resistance:
            distance_to_resistance = ((nearest_resistance['price'] - current_price) / current_price) * 100
        
        # Determine position
        position = 'neutral'
        reversal_risk = 'low'
        recommendation = 'wait'
        
        # Near support (potential bounce up)
        if distance_to_support < 0.5:  # Within 0.5%
            position = 'near_support'
            reversal_risk = 'high' if distance_to_support < 0.2 else 'medium'
            recommendation = 'buy'  # Expect bounce
        
        # Near resistance (potential bounce down)
        elif distance_to_resistance < 0.5:  # Within 0.5%
            position = 'near_resistance'
            reversal_risk = 'high' if distance_to_resistance < 0.2 else 'medium'
            recommendation = 'sell'  # Expect bounce down
        
        # In the middle
        else:
            position = 'neutral'
            reversal_risk = 'low'
            # Check if closer to support or resistance
            if distance_to_support < distance_to_resistance:
                recommendation = 'buy'  # More room to go up
            else:
                recommendation = 'sell'  # More room to go down
        
        return {
            'position': position,
            'distance_to_support': round(distance_to_support, 3),
            'distance_to_resistance': round(distance_to_resistance, 3),
            'reversal_risk': reversal_risk,
            'recommendation': recommendation
        }
    
    def _default_levels(self) -> Dict:
        """Return default levels when analysis fails"""
        return {
            'current_price': 0,
            'timeframe': '1m',
            'support_levels': [],
            'resistance_levels': [],
            'nearest_support': None,
            'nearest_resistance': None,
            'distance_to_support': 999,
            'distance_to_resistance': 999,
            'price_position': 'unknown',
            'reversal_risk': 'medium',
            'trade_recommendation': 'wait',
            'key_levels': {}
        }

# Global instance
support_resistance_analyzer = SupportResistanceAnalyzer()
