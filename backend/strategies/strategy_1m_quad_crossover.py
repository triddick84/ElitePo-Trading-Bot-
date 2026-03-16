"""
1-Minute Quad SMA/EMA Crossover Strategy
Accuracy Target: 80%+

Based on user specification:
- White: 2 SMA
- Yellow: 5 SMA
- Pink: 10 SMA
- Blue: 20 EMA

Crossover Rules:
1st: White(2) crosses Yellow(5) → Go WITH Trend
2nd: Yellow(5) crosses Pink(10) AND White(2) crosses Pink(10) → Go AGAINST Trend
3rd: White(2) crosses Blue(20) AND Yellow(5) crosses Blue(20) → Go WITH Trend
4th: Pink(10) crosses Blue(20) → Go AGAINST last Trend (if new started)

Special: White(2) crosses ALL lines in one candle → Go AGAINST Trend
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy1mQuadCrossover:
    def __init__(self):
        self.name = "1m Quad SMA/EMA Crossover"
        self.timeframe = "1m"
        self.accuracy_target = 80.0
        
        # MA Periods
        self.white_period = 2    # SMA
        self.yellow_period = 5   # SMA
        self.pink_period = 10    # SMA
        self.blue_period = 20    # EMA
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required moving averages"""
        try:
            # SMAs (White, Yellow, Pink)
            df['white_sma'] = talib.SMA(df['close'], timeperiod=self.white_period)   # 2 SMA
            df['yellow_sma'] = talib.SMA(df['close'], timeperiod=self.yellow_period) # 5 SMA
            df['pink_sma'] = talib.SMA(df['close'], timeperiod=self.pink_period)     # 10 SMA
            
            # EMA (Blue)
            df['blue_ema'] = talib.EMA(df['close'], timeperiod=self.blue_period)     # 20 EMA
            
            # Additional indicators for trend confirmation
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def detect_crossover(self, curr_fast: float, curr_slow: float, 
                         prev_fast: float, prev_slow: float) -> Optional[str]:
        """
        Detect crossover direction
        Returns: 'bullish' (fast crossed above slow), 'bearish' (fast crossed below slow), or None
        """
        if np.isnan(curr_fast) or np.isnan(curr_slow) or np.isnan(prev_fast) or np.isnan(prev_slow):
            return None
        
        # Bullish crossover: fast was below slow, now above
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return 'bullish'
        
        # Bearish crossover: fast was above slow, now below
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return 'bearish'
        
        return None
    
    def detect_single_candle_all_cross(self, df: pd.DataFrame) -> Optional[str]:
        """
        Special Rule: Detect if White(2) crosses ALL lines in one candle
        Returns the direction if detected
        """
        if len(df) < 3:
            return None
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        white_curr = curr['white_sma']
        yellow_curr = curr['yellow_sma']
        pink_curr = curr['pink_sma']
        blue_curr = curr['blue_ema']
        
        white_prev = prev['white_sma']
        yellow_prev = prev['yellow_sma']
        pink_prev = prev['pink_sma']
        blue_prev = prev['blue_ema']
        
        # Check if white crossed all three lines in one candle
        cross_yellow = self.detect_crossover(white_curr, yellow_curr, white_prev, yellow_prev)
        cross_pink = self.detect_crossover(white_curr, pink_curr, white_prev, pink_prev)
        cross_blue = self.detect_crossover(white_curr, blue_curr, white_prev, blue_prev)
        
        # All crosses must be in the same direction
        if cross_yellow and cross_pink and cross_blue:
            if cross_yellow == cross_pink == cross_blue:
                logger.info(f"🚨 SPECIAL: White crossed ALL lines in one candle ({cross_yellow})")
                # Go AGAINST the trend (opposite direction)
                return 'bearish' if cross_yellow == 'bullish' else 'bullish'
        
        return None
    
    def get_current_trend(self, df: pd.DataFrame) -> str:
        """Determine current trend based on MA positions"""
        curr = df.iloc[-1]
        
        # Count bullish vs bearish positions
        bullish_count = 0
        
        if curr['white_sma'] > curr['yellow_sma']:
            bullish_count += 1
        if curr['yellow_sma'] > curr['pink_sma']:
            bullish_count += 1
        if curr['pink_sma'] > curr['blue_ema']:
            bullish_count += 1
        if curr['white_sma'] > curr['blue_ema']:
            bullish_count += 1
        
        if bullish_count >= 3:
            return 'bullish'
        elif bullish_count <= 1:
            return 'bearish'
        return 'neutral'
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal based on crossover rules"""
        
        if len(df) < 25:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'Insufficient data (need 25+ candles)',
                'strategy': self.name
            }
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['white_sma'].isna().all():
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'Indicator calculation failed',
                'strategy': self.name
            }
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) > 2 else prev
        
        crossover_signals = []
        reasons = []
        direction = None
        confidence = 0
        
        # Get current trend
        trend = self.get_current_trend(df)
        
        # ==== SPECIAL RULE: White crosses ALL lines in one candle ====
        special_cross = self.detect_single_candle_all_cross(df)
        if special_cross:
            direction = 'CALL' if special_cross == 'bullish' else 'PUT'
            confidence = 90  # High confidence for this rare pattern
            reasons.append(f"🚨 SPECIAL: White(2) crossed ALL lines → Go AGAINST trend")
            
            return {
                'direction': direction,
                'confidence': confidence,
                'reason': ' | '.join(reasons),
                'strategy': self.name,
                'timeframe': self.timeframe,
                'crossover_type': 'special_all_cross',
                'trend': trend,
                'indicators': self._get_indicator_values(curr)
            }
        
        # ==== 1st Crossover: White(2) crosses Yellow(5) → WITH Trend ====
        cross_1 = self.detect_crossover(
            curr['white_sma'], curr['yellow_sma'],
            prev['white_sma'], prev['yellow_sma']
        )
        if cross_1:
            crossover_signals.append(('1st', cross_1, 'with'))
            reasons.append(f"1st: White(2) crossed Yellow(5) → {cross_1.upper()}")
        
        # ==== 2nd Crossover: Yellow(5) crosses Pink(10) AND White(2) crosses Pink(10) → AGAINST Trend ====
        cross_yellow_pink = self.detect_crossover(
            curr['yellow_sma'], curr['pink_sma'],
            prev['yellow_sma'], prev['pink_sma']
        )
        cross_white_pink = self.detect_crossover(
            curr['white_sma'], curr['pink_sma'],
            prev['white_sma'], prev['pink_sma']
        )
        
        # Check for recent crosses (within last 3 candles)
        recent_cross_white_pink = None
        for i in range(-3, -1):
            if len(df) > abs(i):
                c = df.iloc[i]
                p = df.iloc[i-1] if len(df) > abs(i-1) else c
                x = self.detect_crossover(c['white_sma'], c['pink_sma'], p['white_sma'], p['pink_sma'])
                if x:
                    recent_cross_white_pink = x
        
        if cross_yellow_pink and (cross_white_pink or recent_cross_white_pink):
            # Both conditions met - go AGAINST trend
            opposite = 'bearish' if cross_yellow_pink == 'bullish' else 'bullish'
            crossover_signals.append(('2nd', opposite, 'against'))
            reasons.append(f"2nd: Yellow(5)+White(2) crossed Pink(10) → Go AGAINST ({opposite.upper()})")
        
        # ==== 3rd Crossover: White(2) crosses Blue(20) AND Yellow(5) crosses Blue(20) → WITH Trend ====
        cross_white_blue = self.detect_crossover(
            curr['white_sma'], curr['blue_ema'],
            prev['white_sma'], prev['blue_ema']
        )
        cross_yellow_blue = self.detect_crossover(
            curr['yellow_sma'], curr['blue_ema'],
            prev['yellow_sma'], prev['blue_ema']
        )
        
        # Check for recent yellow-blue cross
        recent_cross_yellow_blue = None
        for i in range(-3, -1):
            if len(df) > abs(i):
                c = df.iloc[i]
                p = df.iloc[i-1] if len(df) > abs(i-1) else c
                x = self.detect_crossover(c['yellow_sma'], c['blue_ema'], p['yellow_sma'], p['blue_ema'])
                if x:
                    recent_cross_yellow_blue = x
        
        if cross_white_blue and (cross_yellow_blue or recent_cross_yellow_blue):
            crossover_signals.append(('3rd', cross_white_blue, 'with'))
            reasons.append(f"3rd: White(2)+Yellow(5) crossed Blue(20) → {cross_white_blue.upper()}")
        
        # ==== 4th Crossover: Pink(10) crosses Blue(20) → AGAINST last Trend if New Started ====
        cross_pink_blue = self.detect_crossover(
            curr['pink_sma'], curr['blue_ema'],
            prev['pink_sma'], prev['blue_ema']
        )
        
        if cross_pink_blue:
            # This is a trend change signal - go against the previous trend
            opposite = 'bearish' if cross_pink_blue == 'bullish' else 'bullish'
            crossover_signals.append(('4th', opposite, 'against'))
            reasons.append(f"4th: Pink(10) crossed Blue(20) → Go AGAINST prev trend ({opposite.upper()})")
        
        # ==== Determine Final Signal ====
        if crossover_signals:
            # Priority: 4th > 3rd > 2nd > 1st (later crossovers are more significant)
            priority_order = ['4th', '3rd', '2nd', '1st']
            
            # Find highest priority crossover
            selected_signal = None
            for priority in priority_order:
                for signal in crossover_signals:
                    if signal[0] == priority:
                        selected_signal = signal
                        break
                if selected_signal:
                    break
            
            if selected_signal:
                cross_type, cross_dir, trend_dir = selected_signal
                
                # Confidence based on crossover type
                confidence_map = {
                    '4th': 85,  # Pink-Blue is strong reversal
                    '3rd': 82,  # White+Yellow-Blue is strong trend
                    '2nd': 78,  # Against trend signal
                    '1st': 75   # Basic crossover
                }
                base_confidence = confidence_map.get(cross_type, 70)
                
                # Adjust confidence based on trend alignment
                if trend_dir == 'with' and trend == cross_dir:
                    base_confidence += 5  # Trend aligned
                elif trend_dir == 'against':
                    base_confidence += 3  # Counter-trend can be strong
                
                direction = 'CALL' if cross_dir == 'bullish' else 'PUT'
                confidence = min(base_confidence, 95)
        
        # ==== No Signal ====
        if not direction:
            # Check for near-crossover setup
            white_yellow_diff = abs(curr['white_sma'] - curr['yellow_sma']) / curr['close'] * 100
            if white_yellow_diff < 0.05:  # Within 0.05% - potential crossover forming
                reasons.append(f"⏳ White-Yellow near crossover ({white_yellow_diff:.3f}%)")
            
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': 'No crossover detected | ' + ' | '.join(reasons) if reasons else 'No crossover detected',
                'strategy': self.name,
                'timeframe': self.timeframe,
                'trend': trend,
                'indicators': self._get_indicator_values(curr)
            }
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'crossover_type': crossover_signals[0][0] if crossover_signals else None,
            'trend': trend,
            'crossover_signals': [{'type': s[0], 'direction': s[1], 'trend_action': s[2]} for s in crossover_signals],
            'indicators': self._get_indicator_values(curr)
        }
    
    def _get_indicator_values(self, row: pd.Series) -> Dict:
        """Get indicator values for logging/display"""
        return {
            'white_2sma': float(row['white_sma']) if not np.isnan(row['white_sma']) else None,
            'yellow_5sma': float(row['yellow_sma']) if not np.isnan(row['yellow_sma']) else None,
            'pink_10sma': float(row['pink_sma']) if not np.isnan(row['pink_sma']) else None,
            'blue_20ema': float(row['blue_ema']) if not np.isnan(row['blue_ema']) else None,
            'rsi': float(row['rsi']) if not np.isnan(row['rsi']) else None,
            'close': float(row['close'])
        }


# Global instance for strategy registry
strategy_1m_quad_crossover = Strategy1mQuadCrossover()
