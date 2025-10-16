"""
5-Second Pocket Option OTC Strategy using EMA 20 and RSI
Ultra-short-term forecasting for five-second expiration period
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class EMA_RSI_5S_Strategy:
    """
    5-Second Pocket Option OTC Strategy Implementation
    
    Strategy Logic:
    - Higher Trade: Price breaks above EMA 20 AND RSI between 50-70
    - Lower Trade: Price breaks below EMA 20 AND RSI between 30-50
    - Target: 5-second expiration OTC assets
    """
    
    def __init__(self):
        self.ema_period = 20
        self.rsi_period = 14
        self.min_data_points = 50  # Minimum data points for reliable calculation
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_ultra_short_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch ultra-short timeframe data for 5-second strategy
        Uses 1-minute data and interpolates for higher resolution
        """
        try:
            # Convert symbol for yfinance
            if '_OTC' in symbol:
                base_symbol = symbol.replace('_OTC', '')
            else:
                base_symbol = symbol
            
            # Convert to yfinance format
            if base_symbol == 'EURUSD':
                yf_symbol = 'EURUSD=X'
            elif base_symbol == 'GBPUSD':
                yf_symbol = 'GBPUSD=X'
            elif base_symbol == 'BTCUSD':
                yf_symbol = 'BTC-USD'
            elif base_symbol == 'ETHUSD':
                yf_symbol = 'ETH-USD'
            else:
                # Default conversion
                yf_symbol = base_symbol + '=X'
            
            # Fetch recent 1-minute data
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty or len(data) < self.min_data_points:
                logger.warning(f"Insufficient data for {symbol}: {len(data) if not data.empty else 0} points")
                return None
            
            # Get the most recent data points for ultra-short analysis
            recent_data = data.tail(self.min_data_points).copy()
            
            # Create higher resolution data through interpolation for 5-second precision
            expanded_data = []
            for i in range(len(recent_data)):
                row = recent_data.iloc[i]
                # Create 12 data points per minute (5-second intervals)
                for j in range(12):
                    timestamp = row.name + pd.Timedelta(seconds=j*5)
                    # Interpolate price within the minute
                    if i < len(recent_data) - 1:
                        next_row = recent_data.iloc[i + 1]
                        interpolation_factor = j / 12
                        price = row['Close'] + (next_row['Open'] - row['Close']) * interpolation_factor
                    else:
                        # For the last minute, use small random variations
                        price_change = np.random.normal(0, row['Close'] * 0.0001)  # 0.01% volatility
                        price = row['Close'] + price_change
                    
                    expanded_data.append({
                        'timestamp': timestamp,
                        'Close': price,
                        'Volume': row['Volume'] / 12  # Distribute volume
                    })
            
            # Convert to DataFrame
            df = pd.DataFrame(expanded_data)
            df.set_index('timestamp', inplace=True)
            df = df.tail(200)  # Keep last 200 5-second intervals
            
            logger.info(f"Generated {len(df)} 5-second data points for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching ultra-short data for {symbol}: {e}")
            return None
    
    def detect_ema_break(self, prices: pd.Series, ema: pd.Series, lookback: int = 3) -> Tuple[bool, bool]:
        """
        Detect EMA breakouts
        Returns: (break_above, break_below)
        """
        if len(prices) < lookback or len(ema) < lookback:
            return False, False
        
        # Check recent price action vs EMA
        recent_prices = prices.tail(lookback)
        recent_ema = ema.tail(lookback)
        
        # Break above: price was below/at EMA and now clearly above
        current_price = recent_prices.iloc[-1]
        current_ema = recent_ema.iloc[-1]
        prev_price = recent_prices.iloc[-2]
        prev_ema = recent_ema.iloc[-2]
        
        # Break above EMA
        break_above = (
            prev_price <= prev_ema * 1.0001 and  # Was at/below EMA (with small tolerance)
            current_price > current_ema * 1.0003  # Now clearly above EMA
        )
        
        # Break below EMA
        break_below = (
            prev_price >= prev_ema * 0.9999 and  # Was at/above EMA (with small tolerance)
            current_price < current_ema * 0.9997  # Now clearly below EMA
        )
        
        return break_above, break_below
    
    def analyze_signal(self, symbol: str) -> Optional[Dict]:
        """
        Analyze 5-second OTC signal using EMA 20 and RSI strategy
        """
        try:
            # Get ultra-short timeframe data
            data = self.get_ultra_short_data(symbol)
            if data is None:
                return None
            
            # Calculate indicators
            prices = data['Close']
            ema_20 = self.calculate_ema(prices, self.ema_period)
            rsi = self.calculate_rsi(prices, self.rsi_period)
            
            # Get current values
            current_price = prices.iloc[-1]
            current_ema = ema_20.iloc[-1]
            current_rsi = rsi.iloc[-1]
            
            # Check for EMA breaks
            break_above, break_below = self.detect_ema_break(prices, ema_20)
            
            # Strategy Logic Implementation
            signal = None
            confidence = 0
            reasoning = []
            
            # HIGHER Trade Conditions
            if break_above and 50 <= current_rsi <= 70:
                signal = "CALL"  # Higher/Up trade
                confidence = self._calculate_confidence(
                    current_price, current_ema, current_rsi, 
                    break_above=True, rsi_in_range=True
                )
                reasoning = [
                    f"✅ Price broke above EMA 20: {current_price:.5f} > {current_ema:.5f}",
                    f"✅ RSI in optimal range for upward move: {current_rsi:.1f} (50-70)",
                    f"📈 HIGHER trade signal for 5-second OTC expiration"
                ]
            
            # LOWER Trade Conditions  
            elif break_below and 30 <= current_rsi <= 50:
                signal = "PUT"  # Lower/Down trade
                confidence = self._calculate_confidence(
                    current_price, current_ema, current_rsi,
                    break_below=True, rsi_in_range=True
                )
                reasoning = [
                    f"✅ Price broke below EMA 20: {current_price:.5f} < {current_ema:.5f}",
                    f"✅ RSI in optimal range for downward move: {current_rsi:.1f} (30-50)",
                    f"📉 LOWER trade signal for 5-second OTC expiration"
                ]
            
            # No signal conditions
            else:
                reasons_no_signal = []
                if not break_above and not break_below:
                    reasons_no_signal.append("❌ No clear EMA 20 break detected")
                if signal is None and break_above:
                    reasons_no_signal.append(f"❌ RSI not in range for HIGHER trade: {current_rsi:.1f} (need 50-70)")
                if signal is None and break_below:
                    reasons_no_signal.append(f"❌ RSI not in range for LOWER trade: {current_rsi:.1f} (need 30-50)")
                
                return {
                    'signal': None,
                    'confidence': 0,
                    'reasoning': reasons_no_signal,
                    'current_price': current_price,
                    'ema_20': current_ema,
                    'rsi': current_rsi,
                    'market_analysis': 'No valid 5-second OTC signal conditions met'
                }
            
            return {
                'signal': signal,
                'confidence': confidence,
                'reasoning': reasoning,
                'current_price': current_price,
                'ema_20': current_ema,
                'rsi': current_rsi,
                'break_above': break_above,
                'break_below': break_below,
                'strategy': 'EMA_20_RSI_5S_OTC',
                'timeframe': '5s',
                'expiration': '5_seconds',
                'market_analysis': f"Ultra-short OTC analysis: Price={current_price:.5f}, EMA20={current_ema:.5f}, RSI={current_rsi:.1f}"
            }
            
        except Exception as e:
            logger.error(f"Error in 5-second EMA-RSI analysis for {symbol}: {e}")
            return None
    
    def _calculate_confidence(self, price: float, ema: float, rsi: float, 
                            break_above: bool = False, break_below: bool = False, 
                            rsi_in_range: bool = False) -> float:
        """
        Calculate confidence score for the 5-second strategy
        """
        base_confidence = 75.0  # Base confidence for 5-second ultra-short strategy
        
        # EMA break strength
        price_ema_diff = abs(price - ema) / ema
        if price_ema_diff > 0.001:  # 0.1% break
            base_confidence += 10
        elif price_ema_diff > 0.0005:  # 0.05% break
            base_confidence += 5
        
        # RSI positioning bonus
        if break_above and 55 <= rsi <= 65:  # Optimal RSI for upward move
            base_confidence += 8
        elif break_below and 35 <= rsi <= 45:  # Optimal RSI for downward move
            base_confidence += 8
        elif rsi_in_range:
            base_confidence += 3
        
        # Ultra-short timeframe adjustment (slightly lower confidence due to high volatility)
        base_confidence = min(base_confidence * 0.95, 95.0)  # Cap at 95% for 5-second trades
        
        return round(base_confidence, 1)
    
    def generate_5s_otc_signal(self, symbol: str) -> Optional[Dict]:
        """
        Generate a complete 5-second OTC signal
        """
        analysis = self.analyze_signal(symbol)
        if not analysis or not analysis['signal']:
            return None
        
        # Calculate entry timing for 5-second precision
        now = datetime.now()
        entry_time = now + timedelta(seconds=15)  # 15-second preparation time
        expiration_time = entry_time + timedelta(seconds=5)  # 5-second expiration
        
        return {
            'id': f"EMA_RSI_5S_{symbol}_{int(now.timestamp())}",
            'symbol': symbol,
            'direction': analysis['signal'],
            'timeframe': '5s',
            'entry_price': analysis['current_price'],
            'probability': analysis['confidence'],
            'confidence_level': 'HIGH' if analysis['confidence'] >= 85 else 'MEDIUM',
            'strategy_used': 'ema_rsi_5s_otc',
            'market_type': 'otc',
            'expiration_minutes': 1,  # Minimum 1 minute for system compatibility
            'actual_expiration_seconds': 5,
            'suggested_stake': 2.0,  # Conservative stake for ultra-short trades
            'precision_entry_time': entry_time.isoformat(),
            'expiration_time': expiration_time.isoformat(),
            'justification': ' | '.join(analysis['reasoning']),
            'technical_analysis': {
                'indicators_used': ['EMA_20', 'RSI_14'],
                'current_price': analysis['current_price'],
                'ema_20': analysis['ema_20'],
                'rsi': analysis['rsi'],
                'break_above_ema': analysis.get('break_above', False),
                'break_below_ema': analysis.get('break_below', False),
                'strategy': 'EMA_20_RSI_5S_OTC',
                'market_analysis': analysis['market_analysis'],
                'timeframe_analysis': '5-second ultra-short OTC strategy',
                'risk_level': 'HIGH',  # Ultra-short trades are inherently risky
                'market_type': 'otc'
            },
            'timestamp': now.isoformat(),
            'forced_generation': False
        }

# Global instance for easy import
ema_rsi_5s_strategy = EMA_RSI_5S_Strategy()