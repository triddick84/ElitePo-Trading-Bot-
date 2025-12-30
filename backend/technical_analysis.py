import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging
from trading_models import TechnicalIndicators, MarketData

logger = logging.getLogger(__name__)

class TechnicalAnalysisEngine:
    """Advanced technical analysis engine for trading signals"""
    
    def __init__(self):
        self.indicators_cache = {}
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI
            
        prices_array = np.array(prices)
        deltas = np.diff(prices_array)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.mean(gains[:period])
        avg_losses = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            avg_gains = (avg_gains * (period - 1) + gains[i]) / period
            avg_losses = (avg_losses * (period - 1) + losses[i]) / period
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0}
            
        prices_series = pd.Series(prices)
        
        # Calculate EMAs
        ema_fast = prices_series.ewm(span=fast).mean()
        ema_slow = prices_series.ewm(span=slow).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=signal).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return {
            "macd_line": round(macd_line.iloc[-1], 6),
            "signal_line": round(signal_line.iloc[-1], 6),
            "histogram": round(histogram.iloc[-1], 6)
        }
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
            
        prices_series = pd.Series(prices)
        ema = prices_series.ewm(span=period).mean()
        return round(ema.iloc[-1], 6)
    
    def calculate_cci(self, highs: List[float], lows: List[float], closes: List[float], period: int = 20) -> float:
        """Calculate Commodity Channel Index"""
        if len(closes) < period:
            return 0.0
            
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        
        if len(typical_prices) < period:
            return 0.0
            
        sma = np.mean(typical_prices[-period:])
        mean_deviation = np.mean([abs(tp - sma) for tp in typical_prices[-period:]])
        
        if mean_deviation == 0:
            return 0.0
            
        cci = (typical_prices[-1] - sma) / (0.015 * mean_deviation)
        return round(cci, 2)
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0.0
            return {
                "upper": current_price * 1.02,
                "middle": current_price,
                "lower": current_price * 0.98
            }
            
        prices_array = np.array(prices[-period:])
        sma = np.mean(prices_array)
        std = np.std(prices_array)
        
        return {
            "upper": round(sma + (std * std_dev), 6),
            "middle": round(sma, 6),
            "lower": round(sma - (std * std_dev), 6)
        }
    
    def calculate_stochastic(self, highs: List[float], lows: List[float], closes: List[float], 
                           k_period: int = 14, d_period: int = 3) -> Dict[str, float]:
        """Calculate Stochastic Oscillator"""
        if len(closes) < k_period:
            return {"k": 50.0, "d": 50.0}
            
        recent_highs = highs[-k_period:]
        recent_lows = lows[-k_period:]
        current_close = closes[-1]
        
        highest_high = max(recent_highs)
        lowest_low = min(recent_lows)
        
        if highest_high == lowest_low:
            k_percent = 50.0
        else:
            k_percent = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        
        # Simplified D% calculation (should use SMA of K% values in real implementation)
        d_percent = k_percent  # For simplicity
        
        return {
            "k": round(k_percent, 2),
            "d": round(d_percent, 2)
        }
    
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(closes) < 2:
            return 0.0
            
        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_prev_close = abs(highs[i] - closes[i-1])
            low_prev_close = abs(lows[i] - closes[i-1])
            
            true_range = max(high_low, high_prev_close, low_prev_close)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return np.mean(true_ranges) if true_ranges else 0.0
            
        return round(np.mean(true_ranges[-period:]), 6)
    
    def generate_price_history(self, current_price: float, periods: int = 50) -> Dict[str, List[float]]:
        """Generate simulated price history for demo purposes"""
        np.random.seed(42)  # For consistent demo data
        
        prices = []
        highs = []
        lows = []
        closes = []
        
        price = current_price
        for i in range(periods):
            # Simulate price movement
            change = np.random.normal(0, price * 0.01)  # 1% volatility
            price = max(price + change, price * 0.95)  # Prevent unrealistic drops
            
            # Generate OHLC
            high = price * (1 + abs(np.random.normal(0, 0.005)))
            low = price * (1 - abs(np.random.normal(0, 0.005)))
            close = price + np.random.normal(0, price * 0.005)
            
            prices.append(close)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            
        return {
            "prices": prices,
            "highs": highs,
            "lows": lows,
            "closes": closes
        }
    
    def analyze_market_data(self, market_data: MarketData) -> TechnicalIndicators:
        """Complete technical analysis for given market data"""
        try:
            # Generate price history for analysis
            price_history = self.generate_price_history(market_data.price)
            
            prices = price_history["prices"]
            highs = price_history["highs"]
            lows = price_history["lows"]
            closes = price_history["closes"]
            
            # Calculate all indicators
            rsi_5 = self.calculate_rsi(prices, 5)
            rsi_14 = self.calculate_rsi(prices, 14)
            
            macd_result = self.calculate_macd(prices, 12, 26, 9)
            macd_3_9_6 = self.calculate_macd(prices, 3, 9, 6)  # Alternative MACD settings
            
            ema_3 = self.calculate_ema(prices, 3)
            ema_8 = self.calculate_ema(prices, 8)
            ema_50 = self.calculate_ema(prices, 50)
            ema_200 = self.calculate_ema(prices, 200)
            
            cci_20 = self.calculate_cci(highs, lows, closes, 20)
            
            bollinger = self.calculate_bollinger_bands(prices, 20, 2)
            stoch = self.calculate_stochastic(highs, lows, closes, 14, 3)
            atr = self.calculate_atr(highs, lows, closes, 14)
            
            return TechnicalIndicators(
                symbol=market_data.symbol,
                timestamp=market_data.timestamp,
                rsi_5=rsi_5,
                rsi_14=rsi_14,
                macd_line=macd_result["macd_line"],
                macd_signal=macd_result["signal_line"],
                macd_histogram=macd_result["histogram"],
                ema_3=ema_3,
                ema_8=ema_8,
                ema_50=ema_50,
                ema_200=ema_200,
                cci_20=cci_20,
                bollinger_upper=bollinger["upper"],
                bollinger_middle=bollinger["middle"],
                bollinger_lower=bollinger["lower"],
                stoch_k=stoch["k"],
                stoch_d=stoch["d"],
                atr=atr
            )
            
        except Exception as e:
            logger.error(f"Error analyzing market data for {market_data.symbol}: {e}")
            # Return default indicators
            return TechnicalIndicators(
                symbol=market_data.symbol,
                timestamp=market_data.timestamp,
                rsi_5=50.0,
                rsi_14=50.0,
                macd_line=0.0,
                macd_signal=0.0,
                macd_histogram=0.0,
                ema_3=market_data.price,
                ema_8=market_data.price,
                ema_50=market_data.price,
                ema_200=market_data.price,
                cci_20=0.0,
                bollinger_upper=market_data.price * 1.02,
                bollinger_middle=market_data.price,
                bollinger_lower=market_data.price * 0.98,
                stoch_k=50.0,
                stoch_d=50.0,
                atr=market_data.price * 0.01
            )
    
    def interpret_indicators(self, indicators: TechnicalIndicators) -> Dict[str, str]:
        """Interpret technical indicators for signal generation"""
        interpretations = {}
        
        # RSI interpretation
        if indicators.rsi_14 > 70:
            interpretations["rsi"] = f"Overbought ({indicators.rsi_14:.1f}) - potential sell signal"
        elif indicators.rsi_14 < 30:
            interpretations["rsi"] = f"Oversold ({indicators.rsi_14:.1f}) - potential buy signal"
        else:
            interpretations["rsi"] = f"Neutral ({indicators.rsi_14:.1f}) - no clear signal"
        
        # MACD interpretation
        if indicators.macd_line > indicators.macd_signal and indicators.macd_histogram > 0:
            interpretations["macd"] = "Bullish crossover - uptrend momentum"
        elif indicators.macd_line < indicators.macd_signal and indicators.macd_histogram < 0:
            interpretations["macd"] = "Bearish crossover - downtrend momentum"
        else:
            interpretations["macd"] = "Mixed signals - trend uncertain"
        
        # EMA interpretation
        if indicators.ema_3 > indicators.ema_8:
            interpretations["ema"] = "EMA 3 above EMA 8 - short-term bullish"
        else:
            interpretations["ema"] = "EMA 3 below EMA 8 - short-term bearish"
        
        # CCI interpretation
        if indicators.cci_20 > 100:
            interpretations["cci"] = f"Overbought ({indicators.cci_20:.1f}) - potential reversal down"
        elif indicators.cci_20 < -100:
            interpretations["cci"] = f"Oversold ({indicators.cci_20:.1f}) - potential reversal up"
        else:
            interpretations["cci"] = f"Normal range ({indicators.cci_20:.1f}) - trend continuation"
        
        return interpretations