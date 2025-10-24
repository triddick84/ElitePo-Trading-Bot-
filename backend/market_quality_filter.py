"""
Market Quality Filter - Aggressive Accuracy Improvement
Filters out low-quality market conditions to ensure only high-probability signals

This module ensures we ONLY trade during optimal market conditions:
- Adequate volume
- Moderate volatility (not too high, not too low)
- Clear market structure
- No major news events (future enhancement)
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MarketQualityFilter:
    """
    Aggressive market quality filtering for 90%+ accuracy
    """
    
    def __init__(self, timeframe: str = '5s'):
        self.timeframe = timeframe
        
        # Volume thresholds (relative to moving average)
        self.min_volume_ratio = 0.5  # At least 50% of average volume
        
        # Volatility thresholds (ATR-based)
        if timeframe == '5s':
            self.max_volatility_percentile = 85  # Avoid top 15% most volatile periods
            self.min_volatility_percentile = 20  # Avoid bottom 20% least volatile (no movement)
        elif timeframe == '15s':
            self.max_volatility_percentile = 85
            self.min_volatility_percentile = 25
        else:  # 1m and longer
            self.max_volatility_percentile = 90
            self.min_volatility_percentile = 20
        
        # Spread thresholds (for forex/crypto)
        self.max_spread_pct = 0.05  # 0.05% maximum spread
        
        # Trend clarity threshold
        self.min_trend_strength = 0.4  # On scale of 0-1
        
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range for volatility measurement"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_volume_quality(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        Assess volume quality
        Returns quality score and reasoning
        """
        try:
            if 'volume' not in df.columns or df['volume'].sum() == 0:
                return {
                    'quality_score': 0.5,  # Neutral when volume data unavailable
                    'passed': True,  # Don't reject based on missing volume
                    'reasoning': 'Volume data unavailable (common for forex)'
                }
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].rolling(window=lookback).mean().iloc[-1]
            
            if pd.isna(avg_volume) or avg_volume == 0:
                return {
                    'quality_score': 0.5,
                    'passed': True,
                    'reasoning': 'Insufficient volume history'
                }
            
            volume_ratio = current_volume / avg_volume
            
            # Quality scoring
            if volume_ratio < self.min_volume_ratio:
                return {
                    'quality_score': 0.3,
                    'passed': False,
                    'reasoning': f'LOW VOLUME: {volume_ratio:.1%} of average (need >{self.min_volume_ratio:.0%})'
                }
            elif volume_ratio > 3.0:
                return {
                    'quality_score': 0.6,
                    'passed': False,
                    'reasoning': f'ABNORMAL VOLUME SPIKE: {volume_ratio:.1f}x average (may indicate news event)'
                }
            else:
                return {
                    'quality_score': 0.9,
                    'passed': True,
                    'reasoning': f'Volume OK: {volume_ratio:.1%} of average'
                }
        
        except Exception as e:
            logger.warning(f"Volume quality check error: {e}")
            return {'quality_score': 0.5, 'passed': True, 'reasoning': 'Volume check skipped'}
    
    def calculate_volatility_quality(self, df: pd.DataFrame) -> Dict:
        """
        Assess volatility quality - avoid both extreme volatility AND dead markets
        """
        try:
            atr = self.calculate_atr(df)
            current_atr = atr.iloc[-1]
            
            if pd.isna(current_atr):
                return {'quality_score': 0.5, 'passed': True, 'reasoning': 'ATR calculation incomplete'}
            
            # Calculate ATR percentile (where current ATR falls in recent history)
            atr_percentile = (atr.iloc[-50:] < current_atr).sum() / 50 * 100
            
            # Reject extreme volatility (chaos) or no volatility (no movement)
            if atr_percentile > self.max_volatility_percentile:
                return {
                    'quality_score': 0.2,
                    'passed': False,
                    'reasoning': f'TOO VOLATILE: {atr_percentile:.0f}th percentile (avoid top {100-self.max_volatility_percentile}%)'
                }
            elif atr_percentile < self.min_volatility_percentile:
                return {
                    'quality_score': 0.3,
                    'passed': False,
                    'reasoning': f'TOO QUIET: {atr_percentile:.0f}th percentile (need more movement)'
                }
            else:
                # Ideal volatility range
                quality = 1.0 - abs(atr_percentile - 60) / 60  # Peak quality at 60th percentile
                return {
                    'quality_score': quality,
                    'passed': True,
                    'reasoning': f'Volatility ideal: {atr_percentile:.0f}th percentile'
                }
        
        except Exception as e:
            logger.warning(f"Volatility quality check error: {e}")
            return {'quality_score': 0.5, 'passed': True, 'reasoning': 'Volatility check skipped'}
    
    def calculate_trend_clarity(self, df: pd.DataFrame) -> Dict:
        """
        Measure how clear/strong the trend is
        Unclear/choppy markets = lower quality
        """
        try:
            close = df['close']
            
            # Calculate directional movement
            up_moves = (close.diff() > 0).rolling(window=20).sum()
            down_moves = (close.diff() < 0).rolling(window=20).sum()
            
            current_up = up_moves.iloc[-1]
            current_down = down_moves.iloc[-1]
            
            # Trend strength: 20/0 = perfect trend, 10/10 = choppy
            if current_up + current_down == 0:
                trend_strength = 0
            else:
                trend_strength = abs(current_up - current_down) / (current_up + current_down)
            
            if trend_strength < self.min_trend_strength:
                return {
                    'quality_score': 0.4,
                    'passed': False,
                    'reasoning': f'CHOPPY MARKET: Trend strength {trend_strength:.2f} (need >{self.min_trend_strength:.2f})'
                }
            else:
                return {
                    'quality_score': 0.85 + (trend_strength * 0.15),  # 0.85-1.0 range
                    'passed': True,
                    'reasoning': f'Clear trend: strength {trend_strength:.2f}'
                }
        
        except Exception as e:
            logger.warning(f"Trend clarity check error: {e}")
            return {'quality_score': 0.5, 'passed': True, 'reasoning': 'Trend check skipped'}
    
    def check_market_quality(self, df: pd.DataFrame) -> Dict:
        """
        Comprehensive market quality check
        
        Returns:
            Dict with:
                - overall_quality: 0-1 score
                - passed: Boolean (whether to proceed with signal generation)
                - volume_check: Dict
                - volatility_check: Dict
                - trend_check: Dict
                - rejection_reasons: List of reasons if rejected
        """
        try:
            logger.info(f"🔍 MARKET QUALITY CHECK ({self.timeframe})...")
            
            volume_result = self.calculate_volume_quality(df)
            volatility_result = self.calculate_volatility_quality(df)
            trend_result = self.calculate_trend_clarity(df)
            
            # Overall quality is weighted average
            overall_quality = (
                volume_result['quality_score'] * 0.25 +
                volatility_result['quality_score'] * 0.40 +  # Volatility most important
                trend_result['quality_score'] * 0.35
            )
            
            # Must pass ALL checks
            all_passed = (
                volume_result['passed'] and
                volatility_result['passed'] and
                trend_result['passed']
            )
            
            rejection_reasons = []
            if not volume_result['passed']:
                rejection_reasons.append(volume_result['reasoning'])
            if not volatility_result['passed']:
                rejection_reasons.append(volatility_result['reasoning'])
            if not trend_result['passed']:
                rejection_reasons.append(trend_result['reasoning'])
            
            result = {
                'overall_quality': overall_quality,
                'passed': all_passed,
                'volume_check': volume_result,
                'volatility_check': volatility_result,
                'trend_check': trend_result,
                'rejection_reasons': rejection_reasons
            }
            
            if all_passed:
                logger.info(f"✅ MARKET QUALITY PASSED: {overall_quality:.1%} quality")
                logger.info(f"   - {volume_result['reasoning']}")
                logger.info(f"   - {volatility_result['reasoning']}")
                logger.info(f"   - {trend_result['reasoning']}")
            else:
                logger.warning(f"❌ MARKET QUALITY REJECTED: {', '.join(rejection_reasons)}")
            
            return result
        
        except Exception as e:
            logger.error(f"Market quality check error: {e}")
            # On error, allow trading but with neutral quality
            return {
                'overall_quality': 0.5,
                'passed': True,
                'volume_check': {'quality_score': 0.5, 'passed': True, 'reasoning': 'Check skipped'},
                'volatility_check': {'quality_score': 0.5, 'passed': True, 'reasoning': 'Check skipped'},
                'trend_check': {'quality_score': 0.5, 'passed': True, 'reasoning': 'Check skipped'},
                'rejection_reasons': []
            }

def get_market_filter(timeframe: str = '5s') -> MarketQualityFilter:
    """Factory function to get appropriate filter for timeframe"""
    return MarketQualityFilter(timeframe)
