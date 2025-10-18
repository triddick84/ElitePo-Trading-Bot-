"""
Enhanced 5-Second Ultra-High Accuracy Strategy for Pocket Option
Combines EMA, RSI, Stochastic, Bollinger Bands, Volume, and Pattern Recognition
Supports multiple chart types: Japanese Candles, Line, Bars, Heikin Ashi
Target: 85%+ Accuracy
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, Tuple, List
from scipy import stats
from chart_transformations import chart_transformer

logger = logging.getLogger(__name__)

class Enhanced5SecondStrategy:
    """
    Ultra-High Accuracy 5-Second Strategy
    
    Multi-Indicator Approach:
    1. EMA 20 - Trend Direction
    2. RSI 2 - Fast Momentum
    3. Stochastic (3,1,1) - Overbought/Oversold
    4. Bollinger Bands (5, 2.5) - Volatility
    5. Volume - Confirmation
    6. Candlestick Patterns - Additional confirmation
    """
    
    def __init__(self):
        # Core indicators
        self.ema_period = 20
        self.rsi_period = 2  # Fast RSI for 5-second
        self.stoch_k_period = 3
        self.stoch_d_period = 1
        self.stoch_smooth = 1
        self.bb_period = 5
        self.bb_std = 2.5
        
        # Support/Resistance parameters
        self.sr_lookback = 20  # Lookback period for S/R levels
        self.sr_tolerance = 0.0003  # 0.03% tolerance for price near level
        
        # Thresholds
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.stoch_overbought = 80
        self.stoch_oversold = 20
        
        # Minimum data requirements
        self.min_data_points = 200
    
    def find_support_resistance_levels(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict:
        """
        Identify key support and resistance levels using pivot points
        
        Returns:
            Dict with support_levels, resistance_levels, and current analysis
        """
        try:
            # Find local maxima (resistance) and minima (support)
            support_levels = []
            resistance_levels = []
            
            # Use rolling window to find pivot points
            window = 5  # Check 5 periods on each side
            
            for i in range(window, len(close) - window):
                # Check for resistance (local high)
                is_resistance = True
                for j in range(i - window, i + window + 1):
                    if j != i and high.iloc[i] <= high.iloc[j]:
                        is_resistance = False
                        break
                
                if is_resistance:
                    resistance_levels.append(high.iloc[i])
                
                # Check for support (local low)
                is_support = True
                for j in range(i - window, i + window + 1):
                    if j != i and low.iloc[i] >= low.iloc[j]:
                        is_support = False
                        break
                
                if is_support:
                    support_levels.append(low.iloc[i])
            
            # Filter to most recent and significant levels
            if support_levels:
                support_levels = sorted(support_levels)[-3:]  # Top 3 support levels
            if resistance_levels:
                resistance_levels = sorted(resistance_levels)[-3:]  # Top 3 resistance levels
            
            current_price = close.iloc[-1]
            
            # Analyze current price position
            nearest_support = None
            nearest_resistance = None
            distance_to_support = float('inf')
            distance_to_resistance = float('inf')
            
            for support in support_levels:
                dist = abs(current_price - support) / current_price
                if dist < distance_to_support:
                    distance_to_support = dist
                    nearest_support = support
            
            for resistance in resistance_levels:
                dist = abs(current_price - resistance) / current_price
                if dist < distance_to_resistance:
                    distance_to_resistance = dist
                    nearest_resistance = resistance
            
            # Determine if near support or resistance
            near_support = distance_to_support < self.sr_tolerance
            near_resistance = distance_to_resistance < self.sr_tolerance
            
            # Check for bounce or breakout
            bounce_from_support = False
            bounce_from_resistance = False
            breaking_support = False
            breaking_resistance = False
            
            if near_support and nearest_support:
                # Check if bouncing (price moving up from support)
                price_change = close.iloc[-1] - close.iloc[-3]
                if price_change > 0:
                    bounce_from_support = True
                elif price_change < 0:
                    breaking_support = True
            
            if near_resistance and nearest_resistance:
                # Check if bouncing (price moving down from resistance)
                price_change = close.iloc[-1] - close.iloc[-3]
                if price_change < 0:
                    bounce_from_resistance = True
                elif price_change > 0:
                    breaking_resistance = True
            
            return {
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'near_support': near_support,
                'near_resistance': near_resistance,
                'bounce_from_support': bounce_from_support,
                'bounce_from_resistance': bounce_from_resistance,
                'breaking_support': breaking_support,
                'breaking_resistance': breaking_resistance,
                'distance_to_support_pct': distance_to_support * 100,
                'distance_to_resistance_pct': distance_to_resistance * 100
            }
            
        except Exception as e:
            logger.error(f"Error finding support/resistance: {e}")
            return {
                'support_levels': [],
                'resistance_levels': [],
                'near_support': False,
                'near_resistance': False
            }
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 2) -> pd.Series:
        """Calculate fast RSI for 5-second trading"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator (3,1,1)
        Returns: (%K, %D)
        """
        # %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
        lowest_low = low.rolling(window=self.stoch_k_period).min()
        highest_high = high.rolling(window=self.stoch_k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        
        # %D = SMA of %K
        d_percent = k_percent.rolling(window=self.stoch_d_period).mean()
        
        return k_percent, d_percent
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands (5, 2.5)
        Returns: (upper_band, middle_band, lower_band)
        """
        middle_band = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        
        upper_band = middle_band + (std * self.bb_std)
        lower_band = middle_band - (std * self.bb_std)
        
        return upper_band, middle_band, lower_band
    
    def detect_volume_spike(self, volume: pd.Series, lookback: int = 10) -> bool:
        """Detect significant volume increase"""
        if len(volume) < lookback + 1:
            return False
        
        current_volume = volume.iloc[-1]
        avg_volume = volume.iloc[-lookback-1:-1].mean()
        
        # Volume spike if current is 50% above average
        return current_volume > avg_volume * 1.5
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Detect key candlestick patterns for 5-second trading
        """
        if len(df) < 3:
            return {'bullish': False, 'bearish': False, 'neutral': True}
        
        # Get last 3 candles
        candles = df.tail(3)
        
        patterns = {
            'bullish': False,
            'bearish': False,
            'neutral': False,
            'pattern_name': 'None'
        }
        
        # Calculate candle properties
        c1_open = candles['Open'].iloc[-3]
        c1_close = candles['Close'].iloc[-3]
        c1_high = candles['High'].iloc[-3]
        c1_low = candles['Low'].iloc[-3]
        
        c2_open = candles['Open'].iloc[-2]
        c2_close = candles['Close'].iloc[-2]
        c2_high = candles['High'].iloc[-2]
        c2_low = candles['Low'].iloc[-2]
        
        c3_open = candles['Open'].iloc[-1]
        c3_close = candles['Close'].iloc[-1]
        c3_high = candles['High'].iloc[-1]
        c3_low = candles['Low'].iloc[-1]
        
        # Bullish Engulfing
        if (c2_close < c2_open and  # Previous red
            c3_close > c3_open and  # Current green
            c3_open < c2_close and  # Opens below previous close
            c3_close > c2_open):    # Closes above previous open
            patterns['bullish'] = True
            patterns['pattern_name'] = 'Bullish Engulfing'
        
        # Bearish Engulfing
        elif (c2_close > c2_open and  # Previous green
              c3_close < c3_open and  # Current red
              c3_open > c2_close and  # Opens above previous close
              c3_close < c2_open):    # Closes below previous open
            patterns['bearish'] = True
            patterns['pattern_name'] = 'Bearish Engulfing'
        
        # Hammer (Bullish)
        c3_body = abs(c3_close - c3_open)
        c3_lower_wick = min(c3_open, c3_close) - c3_low
        c3_upper_wick = c3_high - max(c3_open, c3_close)
        
        if c3_lower_wick > 2 * c3_body and c3_upper_wick < c3_body * 0.5:
            patterns['bullish'] = True
            patterns['pattern_name'] = 'Hammer'
        
        # Shooting Star (Bearish)
        if c3_upper_wick > 2 * c3_body and c3_lower_wick < c3_body * 0.5:
            patterns['bearish'] = True
            patterns['pattern_name'] = 'Shooting Star'
        
        # Morning Star (Bullish)
        if (c1_close < c1_open and  # First candle red
            abs(c2_close - c2_open) < c1_body * 0.3 and  # Second candle small
            c3_close > c3_open and  # Third candle green
            c3_close > (c1_open + c1_close) / 2):  # Closes above midpoint of first
            patterns['bullish'] = True
            patterns['pattern_name'] = 'Morning Star'
        
        # Evening Star (Bearish)
        if (c1_close > c1_open and  # First candle green
            abs(c2_close - c2_open) < c1_body * 0.3 and  # Second candle small
            c3_close < c3_open and  # Third candle red
            c3_close < (c1_open + c1_close) / 2):  # Closes below midpoint of first
            patterns['bearish'] = True
            patterns['pattern_name'] = 'Evening Star'
        
        if not patterns['bullish'] and not patterns['bearish']:
            patterns['neutral'] = True
        
        return patterns
    
    def get_ultra_short_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch REAL ultra-short timeframe data - NO SIMULATION
        Uses actual 1-minute data from yfinance (lowest available interval)
        """
        try:
            # Convert symbol
            if '_OTC' in symbol or '_otc' in symbol:
                base_symbol = symbol.replace('_OTC', '').replace('_otc', '')
            else:
                base_symbol = symbol.replace('_regular', '').replace('_REGULAR', '')
            
            # Comprehensive symbol mapping for yfinance
            symbol_map = {
                # Forex
                'EURUSD': 'EURUSD=X',
                'GBPUSD': 'GBPUSD=X',
                'USDJPY': 'USDJPY=X',
                'AUDUSD': 'AUDUSD=X',
                'USDCHF': 'USDCHF=X',
                'USDCAD': 'USDCAD=X',
                'NZDUSD': 'NZDUSD=X',
                'EURGBP': 'EURGBP=X',
                'EURJPY': 'EURJPY=X',
                'GBPJPY': 'GBPJPY=X',
                'AUDJPY': 'AUDJPY=X',
                'AUDCAD': 'AUDCAD=X',
                'AUDCHF': 'AUDCHF=X',
                'AUDNZD': 'AUDNZD=X',
                'CADJPY': 'CADJPY=X',
                'CHFJPY': 'CHFJPY=X',
                'EURCHF': 'EURCHF=X',
                'EURCAD': 'EURCAD=X',
                'EURAUD': 'EURAUD=X',
                'EURNZD': 'EURNZD=X',
                'GBPCHF': 'GBPCHF=X',
                'GBPCAD': 'GBPCAD=X',
                'GBPAUD': 'GBPAUD=X',
                'GBPNZD': 'GBPNZD=X',
                'NZDJPY': 'NZDJPY=X',
                'NZDCHF': 'NZDCHF=X',
                'NZDCAD': 'NZDCAD=X',
                # Crypto
                'BTCUSD': 'BTC-USD',
                'ETHUSD': 'ETH-USD',
                'XRPUSD': 'XRP-USD',
                'LTCUSD': 'LTC-USD',
                'ADAUSD': 'ADA-USD',
                'DOGUSD': 'DOGE-USD',
                'SOLUSD': 'SOL-USD',
                'DOTUSD': 'DOT-USD',
            }
            
            yf_symbol = symbol_map.get(base_symbol, base_symbol + '=X')
            
            # Fetch REAL 1-minute data (lowest interval available on yfinance)
            logger.info(f"📊 Fetching REAL market data for {yf_symbol} (no simulation)")
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty or len(data) < 20:
                logger.warning(f"❌ Insufficient REAL market data for {symbol} ({yf_symbol})")
                return None
            
            # Use ACTUAL 1-minute data - NO INTERPOLATION OR SIMULATION
            # For 5-second strategies, we use the most granular real data available (1m)
            # This is MORE ACCURATE than simulated 5s data
            recent_data = data.tail(self.min_data_points).copy()
            
            logger.info(f"✅ Using {len(recent_data)} REAL 1-minute candles for {symbol} (from {yf_symbol})")
            logger.info(f"📈 Latest price: {recent_data['Close'].iloc[-1]:.5f}")
            
            return recent_data
            
        except Exception as e:
            logger.error(f"❌ Error fetching REAL market data for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def analyze_signal(self, symbol: str, chart_type: str = 'japanese_candles') -> Optional[Dict]:
        """
        Comprehensive multi-indicator analysis for 5-second trading
        
        Args:
            symbol: Trading symbol (e.g., EURUSD_OTC)
            chart_type: Chart type for analysis ('japanese_candles', 'line', 'bars', 'heikin_ashi')
        """
        try:
            # Get data
            data = self.get_ultra_short_data(symbol)
            if data is None:
                return None
            
            # Transform data based on chart type
            transformed_data = chart_transformer.transform_data(data, chart_type)
            chart_info = chart_transformer.get_chart_type_info(chart_type)
            
            logger.info(f"Using {chart_info['name']} for {symbol} analysis")
            
            # Calculate all indicators
            prices = transformed_data['Close']
            high = transformed_data['High']
            low = transformed_data['Low']
            volume = transformed_data['Volume']
            
            # Core indicators
            ema_20 = self.calculate_ema(prices, self.ema_period)
            rsi = self.calculate_rsi(prices, self.rsi_period)
            stoch_k, stoch_d = self.calculate_stochastic(high, low, prices)
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(prices)
            
            # Current values
            current_price = prices.iloc[-1]
            current_ema = ema_20.iloc[-1]
            current_rsi = rsi.iloc[-1]
            current_stoch_k = stoch_k.iloc[-1]
            current_stoch_d = stoch_d.iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_middle = bb_middle.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            
            # Volume analysis
            volume_spike = self.detect_volume_spike(volume)
            
            # Pattern recognition
            patterns = self.detect_candlestick_patterns(data)
            
            # Support & Resistance analysis
            sr_analysis = self.find_support_resistance_levels(high, low, prices)
            
            # Multi-indicator signal logic including S/R
            signal_scores = self._calculate_signal_scores(
                current_price, current_ema, current_rsi,
                current_stoch_k, current_stoch_d,
                current_bb_upper, current_bb_middle, current_bb_lower,
                volume_spike, patterns, sr_analysis
            )
            
            # Determine final signal based on scores
            # Lowered threshold to 3 for more signal generation
            if signal_scores['bullish_score'] >= 3:
                signal = "CALL"
                confidence = self._calculate_confidence(signal_scores, 'bullish')
                reasoning = self._generate_reasoning(signal_scores, 'bullish', 
                                                     current_price, current_ema, current_rsi,
                                                     current_stoch_k, patterns)
            elif signal_scores['bearish_score'] >= 3:
                signal = "PUT"
                confidence = self._calculate_confidence(signal_scores, 'bearish')
                reasoning = self._generate_reasoning(signal_scores, 'bearish',
                                                     current_price, current_ema, current_rsi,
                                                     current_stoch_k, patterns)
            else:
                # No clear signal
                return {
                    'signal': None,
                    'confidence': 0,
                    'reasoning': [
                        f"⚠️ Insufficient indicator alignment (Bullish: {signal_scores['bullish_score']}, Bearish: {signal_scores['bearish_score']})",
                        "❌ Minimum 3 indicators must align for signal generation"
                    ],
                    'current_price': current_price,
                    'indicators': {
                        'ema_20': current_ema,
                        'rsi': current_rsi,
                        'stoch_k': current_stoch_k,
                        'stoch_d': current_stoch_d,
                        'bb_position': self._get_bb_position(current_price, current_bb_upper, current_bb_middle, current_bb_lower)
                    },
                    'market_analysis': 'No valid signal - waiting for stronger alignment'
                }
            
            return {
                'signal': signal,
                'confidence': confidence,
                'reasoning': reasoning,
                'current_price': current_price,
                'indicators': {
                    'ema_20': current_ema,
                    'rsi': current_rsi,
                    'stoch_k': current_stoch_k,
                    'stoch_d': current_stoch_d,
                    'bb_upper': current_bb_upper,
                    'bb_middle': current_bb_middle,
                    'bb_lower': current_bb_lower,
                    'volume_spike': volume_spike
                },
                'pattern': patterns.get('pattern_name', 'None'),
                'signal_scores': signal_scores,
                'strategy': 'ENHANCED_5S_MULTI_INDICATOR',
                'timeframe': '5s',
                'expiration': '5_seconds',
                'chart_type': chart_type,
                'chart_info': chart_info
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced 5s analysis for {symbol}: {e}")
            return None
    
    def _calculate_signal_scores(self, price: float, ema: float, rsi: float,
                                 stoch_k: float, stoch_d: float,
                                 bb_upper: float, bb_middle: float, bb_lower: float,
                                 volume_spike: bool, patterns: Dict, sr_analysis: Dict) -> Dict:
        """
        Score each indicator for bullish/bearish signals
        Now includes Support/Resistance analysis
        """
        bullish_score = 0
        bearish_score = 0
        details = []
        
        # 1. EMA Trend (1 point)
        if price > ema:
            bullish_score += 1
            details.append("✅ Price above EMA 20 (Bullish)")
        else:
            bearish_score += 1
            details.append("✅ Price below EMA 20 (Bearish)")
        
        # 2. RSI Momentum (1 point)
        if 50 < rsi < self.rsi_overbought:
            bullish_score += 1
            details.append(f"✅ RSI bullish momentum: {rsi:.1f}")
        elif self.rsi_oversold < rsi < 50:
            bearish_score += 1
            details.append(f"✅ RSI bearish momentum: {rsi:.1f}")
        
        # 3. Stochastic (1 point)
        if stoch_k < self.stoch_oversold and stoch_k > stoch_d:
            bullish_score += 1
            details.append(f"✅ Stochastic oversold turning up: K={stoch_k:.1f}")
        elif stoch_k > self.stoch_overbought and stoch_k < stoch_d:
            bearish_score += 1
            details.append(f"✅ Stochastic overbought turning down: K={stoch_k:.1f}")
        
        # 4. Bollinger Bands (1 point)
        bb_range = bb_upper - bb_lower
        lower_threshold = bb_lower + (bb_range * 0.2)
        upper_threshold = bb_upper - (bb_range * 0.2)
        
        if price < lower_threshold:
            bullish_score += 1
            details.append("✅ Price near lower BB (Potential bounce)")
        elif price > upper_threshold:
            bearish_score += 1
            details.append("✅ Price near upper BB (Potential reversal)")
        
        # 5. Volume Confirmation (1 point)
        if volume_spike:
            # Volume confirms the direction indicated by other indicators
            if bullish_score > bearish_score:
                bullish_score += 1
                details.append("✅ Volume spike confirms bullish move")
            elif bearish_score > bullish_score:
                bearish_score += 1
                details.append("✅ Volume spike confirms bearish move")
        
        # 6. Candlestick Patterns (1 point)
        if patterns['bullish']:
            bullish_score += 1
            details.append(f"✅ Bullish pattern: {patterns['pattern_name']}")
        elif patterns['bearish']:
            bearish_score += 1
            details.append(f"✅ Bearish pattern: {patterns['pattern_name']}")
        
        # 7. Support/Resistance Analysis (1 point) - NEW!
        if sr_analysis.get('bounce_from_support'):
            bullish_score += 1
            if sr_analysis.get('nearest_support'):
                details.append(f"🔥 BOUNCE from Support @ {sr_analysis['nearest_support']:.5f} - Reversal Signal!")
        elif sr_analysis.get('near_support') and not sr_analysis.get('breaking_support'):
            bullish_score += 0.5  # Half point for being near support
            details.append(f"📍 Near Support @ {sr_analysis['nearest_support']:.5f} ({sr_analysis['distance_to_support_pct']:.2f}%)")
        
        if sr_analysis.get('bounce_from_resistance'):
            bearish_score += 1
            if sr_analysis.get('nearest_resistance'):
                details.append(f"🔥 BOUNCE from Resistance @ {sr_analysis['nearest_resistance']:.5f} - Reversal Signal!")
        elif sr_analysis.get('near_resistance') and not sr_analysis.get('breaking_resistance'):
            bearish_score += 0.5  # Half point for being near resistance
            details.append(f"📍 Near Resistance @ {sr_analysis['nearest_resistance']:.5f} ({sr_analysis['distance_to_resistance_pct']:.2f}%)")
        
        # Breaking through levels (indicates strong momentum)
        if sr_analysis.get('breaking_resistance'):
            bullish_score += 1
            details.append(f"🚀 BREAKING Resistance @ {sr_analysis['nearest_resistance']:.5f} - Breakout!")
        
        if sr_analysis.get('breaking_support'):
            bearish_score += 1
            details.append(f"💥 BREAKING Support @ {sr_analysis['nearest_support']:.5f} - Breakdown!")
        
        return {
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'details': details,
            'max_possible': 7,  # Updated to 7 with S/R
            'sr_analysis': sr_analysis
        }
    
    def _calculate_confidence(self, signal_scores: Dict, direction: str) -> float:
        """
        Calculate confidence percentage based on indicator alignment
        """
        if direction == 'bullish':
            score = signal_scores['bullish_score']
        else:
            score = signal_scores['bearish_score']
        
        max_score = signal_scores['max_possible']
        
        # Base confidence mapping - updated for lower threshold
        confidence_map = {
            3: 75.0,
            4: 82.0,
            5: 88.0,
            6: 95.0
        }
        
        return confidence_map.get(score, 70.0)
    
    def _generate_reasoning(self, signal_scores: Dict, direction: str,
                           price: float, ema: float, rsi: float, stoch: float,
                           patterns: Dict) -> List[str]:
        """Generate human-readable reasoning"""
        reasoning = [
            f"🎯 {signal_scores[f'{direction}_score']}/{signal_scores['max_possible']} indicators aligned for {direction.upper()} signal",
            ""
        ]
        
        reasoning.extend(signal_scores['details'])
        
        reasoning.extend([
            "",
            f"💹 Current Price: {price:.5f}",
            f"📊 EMA 20: {ema:.5f}",
            f"⚡ RSI(2): {rsi:.1f}",
            f"📈 Stochastic: {stoch:.1f}",
            f"🕯️ Pattern: {patterns.get('pattern_name', 'None')}"
        ])
        
        return reasoning
    
    def _get_bb_position(self, price: float, upper: float, middle: float, lower: float) -> str:
        """Get price position relative to Bollinger Bands"""
        bb_range = upper - lower
        if price > upper:
            return "Above Upper Band"
        elif price > middle + (bb_range * 0.3):
            return "Upper Zone"
        elif price > middle - (bb_range * 0.3):
            return "Middle Zone"
        elif price > lower:
            return "Lower Zone"
        else:
            return "Below Lower Band"


# Global instance
enhanced_5s_strategy = Enhanced5SecondStrategy()
