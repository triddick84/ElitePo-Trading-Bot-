"""
Pocket Option 1-Minute Chart / 5-Second Signal Reversal Strategy

Chart Timeframe: 1 minute
Signal/Trade Duration: 5 seconds
Signals generated at new candle formation only

LOGIC:
- Green candle closes in middle (not at high) → BUY signal
- Red candle closes in middle (not at low) → SELL signal
- Green candle makes new high high at close → SELL signal (reversal)
- Red candle makes new low low at close → BUY signal (reversal)

Summary: Middle closes = continuation, Extreme closes = reversal
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import yfinance as yf

logger = logging.getLogger(__name__)

class PocketOption1M5SReversalStrategy:
    """
    1-Minute Chart / 5-Second Signal Reversal Strategy
    Based on candle positioning and color for mean reversion and momentum reversal
    """
    
    def __init__(self):
        self.name = "1M Chart 5S Signal Reversal"
        self.chart_timeframe = "1m"
        self.signal_duration = "5s"
        
    def generate_signal(self, symbol: str, chart_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on 1-minute candle position and color
        
        Args:
            symbol: Trading symbol (e.g., EURUSD)
            chart_data: Optional pre-fetched chart data
            
        Returns:
            Signal dictionary with direction, confidence, and analysis
        """
        try:
            logger.info(f"🎯 Generating 1M/5S Reversal signal for {symbol}")
            
            # Fetch 1-minute chart data if not provided
            if chart_data is None:
                chart_data = self._fetch_1m_data(symbol)
            
            if chart_data is None or len(chart_data) < 20:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Analyze current and previous candles
            analysis = self._analyze_candle_position(chart_data)
            
            if analysis['signal_direction'] is None:
                logger.info(f"No clear signal for {symbol}")
                return None
            
            # Build signal
            signal = {
                'direction': analysis['signal_direction'],
                'confidence': analysis['confidence'],
                'probability': analysis['probability'],
                'entry_price': analysis['entry_price'],
                'reasoning': analysis['reasoning'],
                'chart_timeframe': '1m',
                'signal_duration': '5s',
                'strategy_name': self.name,
                'technical_analysis': {
                    'current_candle': analysis['current_candle'],
                    'candle_position': analysis['candle_position'],
                    'is_reversal': analysis['is_reversal'],
                    'is_continuation': analysis['is_continuation'],
                    'new_high_low': analysis['new_high_low'],
                    'candle_color': analysis['candle_color'],
                    'middle_range_pct': analysis['middle_range_pct']
                }
            }
            
            logger.info(f"✅ Generated {signal['direction']} signal with {signal['confidence']}% confidence")
            return signal
            
        except Exception as e:
            logger.error(f"Error generating 1M/5S Reversal signal for {symbol}: {e}")
            return None
    
    def _fetch_1m_data(self, symbol: str, periods: int = 50) -> Optional[pd.DataFrame]:
        """Fetch 1-minute candle data"""
        try:
            # Convert symbol format for yfinance
            yf_symbol = symbol.replace('EURUSD', 'EURUSD=X').replace('GBPUSD', 'GBPUSD=X')
            yf_symbol = yf_symbol.replace('BTCUSD', 'BTC-USD').replace('ETHUSD', 'ETH-USD')
            
            logger.info(f"Fetching 1m data for {yf_symbol}")
            
            # Fetch 1-minute data
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period='1d', interval='1m')
            
            if df is None or len(df) == 0:
                logger.warning(f"No 1m data available for {yf_symbol}")
                return None
            
            logger.info(f"Fetched {len(df)} 1-minute candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching 1m data for {symbol}: {e}")
            return None
    
    def _analyze_candle_position(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze candle position and determine signal direction
        
        Returns analysis with signal direction based on:
        - Candle color (green/red)
        - Close position (middle vs extreme)
        - New high/low formation
        """
        try:
            # Get current candle (most recent)
            current = df.iloc[-1]
            
            # Get previous candles for context
            prev_highs = df['High'].iloc[-20:-1]
            prev_lows = df['Low'].iloc[-20:-1]
            
            # Calculate candle metrics
            open_price = current['Open']
            close_price = current['Close']
            high_price = current['High']
            low_price = current['Low']
            
            # Candle color
            is_green = close_price > open_price
            is_red = close_price < open_price
            candle_color = 'green' if is_green else 'red'
            
            # Candle range
            candle_range = high_price - low_price
            body_size = abs(close_price - open_price)
            
            # Close position within candle (0 = at low, 1 = at high)
            if candle_range > 0:
                close_position = (close_price - low_price) / candle_range
            else:
                close_position = 0.5
            
            # Determine if close is in middle (30% - 70% of range)
            in_middle = 0.3 <= close_position <= 0.7
            at_high = close_position > 0.85
            at_low = close_position < 0.15
            
            # Check for new high/low
            making_new_high = high_price > prev_highs.max()
            making_new_low = low_price < prev_lows.min()
            
            # Signal Logic
            signal_direction = None
            reasoning = ""
            confidence = 75.0
            is_reversal = False
            is_continuation = False
            
            # Rule 1: Green candle closes in middle → BUY (continuation)
            if is_green and in_middle:
                signal_direction = 'CALL'
                reasoning = f"🟢 Green candle closed in middle ({close_position:.1%}) → Bullish continuation"
                confidence = 80.0
                is_continuation = True
            
            # Rule 2: Red candle closes in middle → SELL (continuation)
            elif is_red and in_middle:
                signal_direction = 'PUT'
                reasoning = f"🔴 Red candle closed in middle ({close_position:.1%}) → Bearish continuation"
                confidence = 80.0
                is_continuation = True
            
            # Rule 3: Green candle makes new high → SELL (reversal)
            elif is_green and making_new_high and at_high:
                signal_direction = 'PUT'
                reasoning = f"🟢 Green candle made new high at close ({close_position:.1%}) → Bearish reversal"
                confidence = 85.0
                is_reversal = True
            
            # Rule 4: Red candle makes new low → BUY (reversal)
            elif is_red and making_new_low and at_low:
                signal_direction = 'CALL'
                reasoning = f"🔴 Red candle made new low at close ({close_position:.1%}) → Bullish reversal"
                confidence = 85.0
                is_reversal = True
            
            # Rule 5: Green candle at high (not necessarily new high) → SELL
            elif is_green and at_high:
                signal_direction = 'PUT'
                reasoning = f"🟢 Green candle closed at high ({close_position:.1%}) → Potential reversal"
                confidence = 77.0
                is_reversal = True
            
            # Rule 6: Red candle at low (not necessarily new low) → BUY
            elif is_red and at_low:
                signal_direction = 'CALL'
                reasoning = f"🔴 Red candle closed at low ({close_position:.1%}) → Potential reversal"
                confidence = 77.0
                is_reversal = True
            
            # Adjust confidence based on body size
            body_to_range = body_size / candle_range if candle_range > 0 else 0
            if body_to_range > 0.7:  # Strong body
                confidence += 5.0
            elif body_to_range < 0.3:  # Weak body (doji-like)
                confidence -= 5.0
            
            # Cap confidence
            confidence = min(confidence, 95.0)
            probability = confidence
            
            return {
                'signal_direction': signal_direction,
                'confidence': confidence,
                'probability': probability,
                'entry_price': close_price,
                'reasoning': reasoning,
                'current_candle': {
                    'open': float(open_price),
                    'high': float(high_price),
                    'low': float(low_price),
                    'close': float(close_price),
                    'body_size': float(body_size),
                    'range': float(candle_range)
                },
                'candle_position': f"{close_position:.1%}",
                'candle_color': candle_color,
                'is_reversal': is_reversal,
                'is_continuation': is_continuation,
                'new_high_low': {
                    'making_new_high': making_new_high,
                    'making_new_low': making_new_low
                },
                'middle_range_pct': f"{close_position:.1%}",
                'at_high': at_high,
                'at_low': at_low,
                'in_middle': in_middle
            }
            
        except Exception as e:
            logger.error(f"Error analyzing candle position: {e}")
            return {
                'signal_direction': None,
                'confidence': 0,
                'probability': 0,
                'entry_price': 0,
                'reasoning': f"Error: {str(e)}",
                'current_candle': {},
                'candle_position': 'unknown',
                'candle_color': 'unknown',
                'is_reversal': False,
                'is_continuation': False,
                'new_high_low': {},
                'middle_range_pct': '0%'
            }

# Global instance
pocket_option_1m_5s_reversal_strategy = PocketOption1M5SReversalStrategy()
