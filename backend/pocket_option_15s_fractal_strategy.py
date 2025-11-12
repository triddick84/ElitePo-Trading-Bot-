"""
Pocket Option 15-Second Signal / 5-Second Chart Fractal Strategy

Chart Timeframe: 5 seconds
Signal/Trade Duration: 15 seconds
Indicator: Williams Fractal (Period 2)

LOGIC:
- Up Fractal arrow detected → BUY signal (if recent and not at resistance)
- Down Fractal arrow detected → SELL signal (if recent and not at support)
- Signal only valid if fractal appeared within last 2-3 candles
- Skip signal if price is at/near support/resistance - wait for reversal/bounce

Fractal Detection (Period 2):
- Up Fractal: High with 2 lower highs on each side
- Down Fractal: Low with 2 higher lows on each side
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import yfinance as yf

logger = logging.getLogger(__name__)

class PocketOption15sFractalStrategy:
    """
    15-Second Signal / 5-Second Chart Fractal Strategy
    Uses Williams Fractal indicator with period 2 for signal generation
    """
    
    def __init__(self):
        self.name = "15S Signal 5S Chart Fractal"
        self.chart_timeframe = "5s"
        self.signal_duration = "15s"
        self.fractal_period = 2
        self.max_candles_since_fractal = 2  # REDUCED: Signal valid if fractal within last 2 candles (more aggressive)
        self.sr_proximity_threshold = 0.0015  # 0.15% proximity to S/R levels
        
    def generate_signal(self, symbol: str, chart_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on Fractal indicator on 5-second chart
        
        Args:
            symbol: Trading symbol (e.g., EURUSD)
            chart_data: Optional pre-fetched 5-second chart data
            
        Returns:
            Signal dictionary with direction, confidence, and analysis
        """
        try:
            logger.info(f"🎯 Generating 15S/5S Fractal signal for {symbol}")
            
            # Fetch 5-second chart data if not provided
            if chart_data is None:
                chart_data = self._fetch_5s_data(symbol)
            
            if chart_data is None or len(chart_data) < 30:
                logger.warning(f"Insufficient 5s data for {symbol} (need 30+ candles)")
                return None
            
            # Calculate Fractal indicator
            fractals = self._calculate_fractals(chart_data)
            
            # Detect support and resistance levels
            support_levels, resistance_levels = self._detect_support_resistance(chart_data)
            
            # Analyze current price position and recent fractals
            analysis = self._analyze_fractal_signals(
                chart_data, 
                fractals, 
                support_levels, 
                resistance_levels
            )
            
            if analysis['signal_direction'] is None:
                logger.info(f"No valid Fractal signal for {symbol}: {analysis['reason']}")
                return None
            
            # Build signal
            signal = {
                'direction': analysis['signal_direction'],
                'confidence': analysis['confidence'],
                'probability': analysis['probability'],
                'entry_price': analysis['entry_price'],
                'reasoning': analysis['reasoning'],
                'chart_timeframe': '5s',
                'signal_duration': '15s',
                'strategy_name': self.name,
                'technical_analysis': {
                    'fractal_type': analysis['fractal_type'],
                    'fractal_candles_ago': analysis['fractal_candles_ago'],
                    'at_support': analysis['at_support'],
                    'at_resistance': analysis['at_resistance'],
                    'support_levels': support_levels,
                    'resistance_levels': resistance_levels,
                    'current_price': analysis['entry_price'],
                    'fractal_price': analysis['fractal_price'],
                    'trend_confirmed': analysis['trend_confirmed']
                }
            }
            
            logger.info(f"✅ Generated {signal['direction']} signal with {signal['confidence']}% confidence")
            return signal
            
        except Exception as e:
            logger.error(f"Error generating 15S/5S Fractal signal for {symbol}: {e}")
            return None
    
    def _fetch_5s_data(self, symbol: str, periods: int = 100) -> Optional[pd.DataFrame]:
        """Fetch 5-second candle data"""
        try:
            # Note: yfinance doesn't support 5s directly, using 1m as proxy
            # In production, you'd use a broker API that supports 5s data
            yf_symbol = symbol.replace('EURUSD', 'EURUSD=X').replace('GBPUSD', 'GBPUSD=X')
            yf_symbol = yf_symbol.replace('BTCUSD', 'BTC-USD').replace('ETHUSD', 'ETH-USD')
            
            logger.info(f"Fetching 1m data for {yf_symbol} (proxy for 5s)")
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period='1d', interval='1m')
            
            if df is None or len(df) == 0:
                logger.warning(f"No data available for {yf_symbol}")
                return None
            
            logger.info(f"Fetched {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching 5s data for {symbol}: {e}")
            return None
    
    def _calculate_fractals(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """
        Calculate Williams Fractal indicator with period 2
        
        Returns:
            Dictionary with 'up_fractals' and 'down_fractals' as lists of indices
        """
        try:
            up_fractals = []
            down_fractals = []
            period = self.fractal_period
            
            # Need at least period*2 + 1 candles
            if len(df) < period * 2 + 1:
                return {'up_fractals': up_fractals, 'down_fractals': down_fractals}
            
            # Check each candle that has enough neighbors
            for i in range(period, len(df) - period):
                # Up Fractal: High is higher than surrounding highs
                is_up_fractal = True
                center_high = df['High'].iloc[i]
                
                # Check left side
                for j in range(1, period + 1):
                    if df['High'].iloc[i - j] >= center_high:
                        is_up_fractal = False
                        break
                
                # Check right side
                if is_up_fractal:
                    for j in range(1, period + 1):
                        if df['High'].iloc[i + j] >= center_high:
                            is_up_fractal = False
                            break
                
                if is_up_fractal:
                    up_fractals.append(i)
                
                # Down Fractal: Low is lower than surrounding lows
                is_down_fractal = True
                center_low = df['Low'].iloc[i]
                
                # Check left side
                for j in range(1, period + 1):
                    if df['Low'].iloc[i - j] <= center_low:
                        is_down_fractal = False
                        break
                
                # Check right side
                if is_down_fractal:
                    for j in range(1, period + 1):
                        if df['Low'].iloc[i + j] <= center_low:
                            is_down_fractal = False
                            break
                
                if is_down_fractal:
                    down_fractals.append(i)
            
            logger.info(f"Found {len(up_fractals)} up fractals and {len(down_fractals)} down fractals")
            return {
                'up_fractals': up_fractals,
                'down_fractals': down_fractals
            }
            
        except Exception as e:
            logger.error(f"Error calculating fractals: {e}")
            return {'up_fractals': [], 'down_fractals': []}
    
    def _detect_support_resistance(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[List[float], List[float]]:
        """
        Detect support and resistance levels from recent swing points
        
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        try:
            support_levels = []
            resistance_levels = []
            
            if len(df) < lookback:
                return support_levels, resistance_levels
            
            # Look at recent data
            recent_df = df.iloc[-lookback:]
            
            # Find swing highs (resistance)
            for i in range(2, len(recent_df) - 2):
                if (recent_df['High'].iloc[i] > recent_df['High'].iloc[i-1] and
                    recent_df['High'].iloc[i] > recent_df['High'].iloc[i-2] and
                    recent_df['High'].iloc[i] > recent_df['High'].iloc[i+1] and
                    recent_df['High'].iloc[i] > recent_df['High'].iloc[i+2]):
                    resistance_levels.append(float(recent_df['High'].iloc[i]))
            
            # Find swing lows (support)
            for i in range(2, len(recent_df) - 2):
                if (recent_df['Low'].iloc[i] < recent_df['Low'].iloc[i-1] and
                    recent_df['Low'].iloc[i] < recent_df['Low'].iloc[i-2] and
                    recent_df['Low'].iloc[i] < recent_df['Low'].iloc[i+1] and
                    recent_df['Low'].iloc[i] < recent_df['Low'].iloc[i+2]):
                    support_levels.append(float(recent_df['Low'].iloc[i]))
            
            # Remove duplicates and sort
            support_levels = sorted(list(set(support_levels)))
            resistance_levels = sorted(list(set(resistance_levels)))
            
            logger.info(f"Detected {len(support_levels)} support and {len(resistance_levels)} resistance levels")
            return support_levels, resistance_levels
            
        except Exception as e:
            logger.error(f"Error detecting S/R levels: {e}")
            return [], []
    
    def _analyze_fractal_signals(self, df: pd.DataFrame, fractals: Dict, 
                                  support_levels: List[float], 
                                  resistance_levels: List[float]) -> Dict[str, Any]:
        """
        Analyze fractal signals and determine if signal should be generated
        """
        try:
            current_price = float(df['Close'].iloc[-1])
            current_index = len(df) - 1
            
            # Find most recent up and down fractals
            recent_up_fractal = None
            recent_down_fractal = None
            
            if fractals['up_fractals']:
                recent_up_fractal = fractals['up_fractals'][-1]
            
            if fractals['down_fractals']:
                recent_down_fractal = fractals['down_fractals'][-1]
            
            # Check if fractals are recent enough (within max_candles_since_fractal)
            # Fractals confirmed at period candles ago are the freshest possible signals
            up_fractal_valid = (recent_up_fractal is not None and 
                               current_index - recent_up_fractal <= self.max_candles_since_fractal)
            down_fractal_valid = (recent_down_fractal is not None and 
                                 current_index - recent_down_fractal <= self.max_candles_since_fractal)
            
            # Boost confidence for JUST confirmed fractals (exactly at period candles ago)
            up_fractal_just_confirmed = (recent_up_fractal is not None and 
                                        current_index - recent_up_fractal == self.fractal_period)
            down_fractal_just_confirmed = (recent_down_fractal is not None and 
                                          current_index - recent_down_fractal == self.fractal_period)
            
            # Check proximity to support/resistance
            at_resistance = self._is_near_resistance(current_price, resistance_levels)
            at_support = self._is_near_support(current_price, support_levels)
            
            # Determine signal direction
            signal_direction = None
            fractal_type = None
            fractal_candles_ago = 0
            fractal_price = current_price
            confidence = 78.0
            reasoning = ""
            trend_confirmed = False
            
            # Up Fractal signal (BUY)
            if up_fractal_valid and not down_fractal_valid:
                fractal_candles_ago = current_index - recent_up_fractal
                fractal_price = float(df['High'].iloc[recent_up_fractal])
                
                # Check if at resistance - if so, wait for reversal/bounce
                if at_resistance:
                    reasoning = f"⚠️ Up Fractal detected {fractal_candles_ago} candles ago, but price at resistance - waiting for confirmation"
                    signal_direction = None
                else:
                    # Check if price has bounced/reversed from support
                    if at_support and current_price > df['Low'].iloc[-2]:
                        trend_confirmed = True
                        confidence = 87.0 if up_fractal_just_confirmed else 85.0
                        reasoning = f"🟢 Up Fractal + Bounce from support {'JUST CONFIRMED' if up_fractal_just_confirmed else f'({fractal_candles_ago} candles ago)'}"
                        signal_direction = 'CALL'
                        fractal_type = 'up'
                    else:
                        # Regular up fractal signal - higher confidence if just confirmed
                        if up_fractal_just_confirmed:
                            confidence = 83.0
                            reasoning = f"🟢 Up Fractal JUST CONFIRMED (fresh signal) → Bullish"
                        else:
                            confidence = 80.0
                            reasoning = f"🟢 Up Fractal detected {fractal_candles_ago} candles ago → Bullish"
                        signal_direction = 'CALL'
                        fractal_type = 'up'
                        trend_confirmed = True
            
            # Down Fractal signal (SELL)
            elif down_fractal_valid and not up_fractal_valid:
                fractal_candles_ago = current_index - recent_down_fractal
                fractal_price = float(df['Low'].iloc[recent_down_fractal])
                
                # Check if at support - if so, wait for reversal/bounce
                if at_support:
                    reasoning = f"⚠️ Down Fractal detected {fractal_candles_ago} candles ago, but price at support - waiting for confirmation"
                    signal_direction = None
                else:
                    # Check if price has bounced/reversed from resistance
                    if at_resistance and current_price < df['High'].iloc[-2]:
                        trend_confirmed = True
                        confidence = 87.0 if down_fractal_just_confirmed else 85.0
                        reasoning = f"🔴 Down Fractal + Bounce from resistance {'JUST CONFIRMED' if down_fractal_just_confirmed else f'({fractal_candles_ago} candles ago)'}"
                        signal_direction = 'PUT'
                        fractal_type = 'down'
                    else:
                        # Regular down fractal signal - higher confidence if just confirmed
                        if down_fractal_just_confirmed:
                            confidence = 83.0
                            reasoning = f"🔴 Down Fractal JUST CONFIRMED (fresh signal) → Bearish"
                        else:
                            confidence = 80.0
                            reasoning = f"🔴 Down Fractal detected {fractal_candles_ago} candles ago → Bearish"
                        signal_direction = 'PUT'
                        fractal_type = 'down'
                        trend_confirmed = True
            
            # Both fractals recent - use the most recent one
            elif up_fractal_valid and down_fractal_valid:
                # Use the fractal that was confirmed more recently
                if recent_up_fractal > recent_down_fractal:
                    fractal_candles_ago = current_index - recent_up_fractal
                    fractal_price = float(df['High'].iloc[recent_up_fractal])
                    
                    if not at_resistance:
                        confidence = 82.0 if up_fractal_just_confirmed else 78.0
                        reasoning = f"🟢 Up Fractal more recent {'' if up_fractal_just_confirmed else f'({fractal_candles_ago} candles ago)'} → Bullish"
                        signal_direction = 'CALL'
                        fractal_type = 'up'
                        trend_confirmed = True
                    else:
                        reasoning = "⚠️ Both fractals recent, up fractal more recent but at resistance - waiting"
                        signal_direction = None
                else:
                    fractal_candles_ago = current_index - recent_down_fractal
                    fractal_price = float(df['Low'].iloc[recent_down_fractal])
                    
                    if not at_support:
                        confidence = 82.0 if down_fractal_just_confirmed else 78.0
                        reasoning = f"🔴 Down Fractal more recent {'' if down_fractal_just_confirmed else f'({fractal_candles_ago} candles ago)'} → Bearish"
                        signal_direction = 'PUT'
                        fractal_type = 'down'
                        trend_confirmed = True
                    else:
                        reasoning = "⚠️ Both fractals recent, down fractal more recent but at support - waiting"
                        signal_direction = None
            
            # No recent fractals
            else:
                reasoning = f"No recent Fractals (within {self.max_candles_since_fractal} candles)"
                signal_direction = None
            
            probability = confidence
            
            return {
                'signal_direction': signal_direction,
                'confidence': confidence,
                'probability': probability,
                'entry_price': current_price,
                'reasoning': reasoning,
                'fractal_type': fractal_type,
                'fractal_candles_ago': fractal_candles_ago,
                'fractal_price': fractal_price,
                'at_support': at_support,
                'at_resistance': at_resistance,
                'trend_confirmed': trend_confirmed,
                'reason': reasoning if signal_direction is None else ""
            }
            
        except Exception as e:
            logger.error(f"Error analyzing fractal signals: {e}")
            return {
                'signal_direction': None,
                'confidence': 0,
                'probability': 0,
                'entry_price': 0,
                'reasoning': f"Error: {str(e)}",
                'fractal_type': None,
                'fractal_candles_ago': 0,
                'fractal_price': 0,
                'at_support': False,
                'at_resistance': False,
                'trend_confirmed': False,
                'reason': f"Error: {str(e)}"
            }
    
    def _is_near_resistance(self, price: float, resistance_levels: List[float]) -> bool:
        """Check if price is near any resistance level"""
        if not resistance_levels:
            return False
        
        for level in resistance_levels:
            if abs(price - level) / level < self.sr_proximity_threshold:
                return True
        return False
    
    def _is_near_support(self, price: float, support_levels: List[float]) -> bool:
        """Check if price is near any support level"""
        if not support_levels:
            return False
        
        for level in support_levels:
            if abs(price - level) / level < self.sr_proximity_threshold:
                return True
        return False

# Global instance
pocket_option_15s_fractal_strategy = PocketOption15sFractalStrategy()
