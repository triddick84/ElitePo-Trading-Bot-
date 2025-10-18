"""
Ultra-Short 5-Second Strategy for Pocket Option
Specialized for 5s timeframe with inverted/contrarian logic
Uses mean reversion and bounce-back patterns
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional
from chart_transformations import chart_transformer

logger = logging.getLogger(__name__)

class UltraShort5SecondStrategy:
    """
    Specialized 5-second strategy using CONTRARIAN/MEAN REVERSION logic
    
    Key Insight: For ultra-short timeframes, traditional momentum indicators lag.
    We use INVERSE logic - when indicators show overbought, market likely to reverse DOWN.
    """
    
    def __init__(self):
        self.ema_period = 10  # Shorter EMA for ultra-short
        self.rsi_period = 3   # Very fast RSI
        self.min_data_points = 100
        
        # CONTRARIAN thresholds
        self.rsi_extreme_overbought = 75  # Too high → expect reversal DOWN
        self.rsi_extreme_oversold = 25    # Too low → expect reversal UP
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate EMA"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 3) -> pd.Series:
        """Calculate fast RSI for 5-second"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_real_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch REAL 1-minute data for ultra-short analysis
        """
        try:
            if '_OTC' in symbol or '_otc' in symbol:
                base_symbol = symbol.replace('_OTC', '').replace('_otc', '')
            else:
                base_symbol = symbol.replace('_regular', '').replace('_REGULAR', '')
            
            # Symbol mapping
            symbol_map = {
                'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
                'AUDUSD': 'AUDUSD=X', 'USDCHF': 'USDCHF=X', 'USDCAD': 'USDCAD=X',
                'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD', 'XRPUSD': 'XRP-USD',
            }
            
            yf_symbol = symbol_map.get(base_symbol, base_symbol + '=X')
            
            logger.info(f"📊 Fetching REAL data for ultra-short 5s strategy: {yf_symbol}")
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty or len(data) < self.min_data_points:
                logger.warning(f"❌ Insufficient data for {symbol}")
                return None
            
            recent_data = data.tail(self.min_data_points).copy()
            logger.info(f"✅ Using {len(recent_data)} REAL 1-min candles, Latest: {recent_data['Close'].iloc[-1]:.5f}")
            
            return recent_data
            
        except Exception as e:
            logger.error(f"❌ Error fetching data for {symbol}: {e}")
            return None
    
    def analyze_ultra_short(self, symbol: str, chart_type: str = 'japanese_candles') -> Optional[Dict]:
        """
        Ultra-short 5-second analysis with CONTRARIAN/MEAN REVERSION logic
        """
        try:
            data = self.get_real_market_data(symbol)
            if data is None:
                return None
            
            # Transform based on chart type
            transformed_data = chart_transformer.transform_data(data, chart_type)
            
            prices = transformed_data['Close']
            high = transformed_data['High']
            low = transformed_data['Low']
            
            # Calculate indicators
            ema_10 = self.calculate_ema(prices, self.ema_period)
            rsi = self.calculate_rsi(prices, self.rsi_period)
            
            # Current values
            current_price = prices.iloc[-1]
            current_ema = ema_10.iloc[-1]
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0  # Default to neutral if NaN
            
            # Price momentum (last 3 candles)
            price_change_short = prices.iloc[-1] - prices.iloc[-3]
            price_velocity = price_change_short / prices.iloc[-3] * 100  # Percentage change
            
            # Distance from EMA (mean reversion indicator)
            ema_distance = ((current_price - current_ema) / current_ema) * 100
            
            # CONTRARIAN LOGIC for Ultra-Short Timeframes
            signal = None
            confidence = 0
            reasoning = []
            
            logger.info(f"🎯 5s Analysis: Price={current_price:.5f}, EMA={current_ema:.5f}, RSI={current_rsi:.1f}")
            logger.info(f"📊 Distance from EMA: {ema_distance:.3f}%, Velocity: {price_velocity:.3f}%")
            
            # If RSI is valid and shows extremes, use it
            if not pd.isna(rsi.iloc[-1]) and (current_rsi > self.rsi_extreme_overbought or current_rsi < self.rsi_extreme_oversold):
                # RULE 1: RSI EXTREMES → MEAN REVERSION (Primary signal)
                if current_rsi > self.rsi_extreme_overbought:
            # If RSI is valid and shows extremes, use it
            if not pd.isna(rsi.iloc[-1]) and (current_rsi > self.rsi_extreme_overbought or current_rsi < self.rsi_extreme_oversold):
                # RULE 1: RSI EXTREMES → MEAN REVERSION (Primary signal)
                if current_rsi > self.rsi_extreme_overbought:
                    # RSI OVERBOUGHT → Price likely to reverse DOWN → PUT
                    signal = "PUT"
                    confidence = 78 + min(10, (current_rsi - 75) * 2)  # Higher RSI = higher confidence
                    reasoning.append(f"🔴 RSI OVERBOUGHT: {current_rsi:.1f} → Expect reversal DOWN")
                    reasoning.append("💡 CONTRARIAN: Price overextended, mean reversion expected")
                    
                elif current_rsi < self.rsi_extreme_oversold:
                    # RSI OVERSOLD → Price likely to reverse UP → CALL
                    signal = "CALL"
                    confidence = 78 + min(10, (25 - current_rsi) * 2)  # Lower RSI = higher confidence
                    reasoning.append(f"🟢 RSI OVERSOLD: {current_rsi:.1f} → Expect reversal UP")
                    reasoning.append("💡 CONTRARIAN: Price oversold, bounce expected")
            
            # RULE 2: EMA DISTANCE → MEAN REVERSION (Primary when RSI unavailable)
            if signal is None and abs(ema_distance) > 0.1:  # More than 0.1% from EMA
                if ema_distance > 0.15:
                    # Price TOO FAR ABOVE EMA → Expect pullback → PUT
                    signal = "PUT"
                    confidence = 75 + min(8, abs(ema_distance) * 20)
                    reasoning.append(f"📉 Price {ema_distance:.2f}% above EMA → Pullback expected")
                    reasoning.append("💡 MEAN REVERSION: Price extended from average")
                    
                elif ema_distance < -0.15:
                    # Price TOO FAR BELOW EMA → Expect bounce → CALL
                    signal = "CALL"
                    confidence = 75 + min(8, abs(ema_distance) * 20)
                    reasoning.append(f"📈 Price {abs(ema_distance):.2f}% below EMA → Bounce expected")
                    reasoning.append("💡 MEAN REVERSION: Price below average, bounce up")
            
            # RULE 3: VELOCITY REVERSAL (Tertiary signal)
            elif abs(price_velocity) > 0.08:  # Strong recent move
                if price_velocity > 0.08:
                    # Fast move UP recently → Expect exhaustion → PUT
                    signal = "PUT"
                    confidence = 72
                    reasoning.append(f"⚡ Fast UP move ({price_velocity:.2f}%) → Exhaustion expected")
                    
                elif price_velocity < -0.08:
                    # Fast move DOWN recently → Expect bounce → CALL  
                    signal = "CALL"
                    confidence = 72
                    reasoning.append(f"⚡ Fast DOWN move ({price_velocity:.2f}%) → Bounce expected")
            
            if signal is None:
                return None
            
            # Add context
            reasoning.extend([
                "",
                f"💹 Current: {current_price:.5f}",
                f"📊 EMA(10): {current_ema:.5f}",
                f"⚡ RSI(3): {current_rsi:.1f}",
                f"🎯 Strategy: 5s ULTRA-SHORT CONTRARIAN"
            ])
            
            return {
                'signal': signal,
                'confidence': min(confidence, 88),  # Cap at 88% for ultra-short
                'reasoning': reasoning,
                'current_price': current_price,
                'indicators': {
                    'ema_10': current_ema,
                    'rsi_3': current_rsi,
                    'ema_distance_pct': ema_distance,
                    'price_velocity_pct': price_velocity
                },
                'strategy': 'ULTRA_SHORT_5S_CONTRARIAN',
                'timeframe': '5s',
                'expiration': '5_seconds',
                'chart_type': chart_type
            }
            
        except Exception as e:
            logger.error(f"❌ Error in ultra-short 5s analysis for {symbol}: {e}")
            return None


# Global instance
ultra_short_5s_strategy = UltraShort5SecondStrategy()
