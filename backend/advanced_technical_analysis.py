import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from trading_models import TechnicalIndicators, MarketData
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AdvancedTechnicalAnalysis:
    """Advanced technical analysis using real market data"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    async def analyze_symbol_comprehensive(self, symbol: str, market_data: MarketData) -> TechnicalIndicators:
        """Comprehensive technical analysis using real historical data"""
        try:
            # Get real historical data for analysis
            loop = asyncio.get_event_loop()
            hist_data = await loop.run_in_executor(
                self.executor,
                self._fetch_comprehensive_data,
                symbol
            )
            
            if not hist_data or len(hist_data) < 50:
                logger.warning(f"Insufficient data for {symbol}, using basic analysis")
                return self._basic_analysis(market_data)
            
            df = pd.DataFrame(hist_data)
            
            # Calculate all technical indicators
            indicators = TechnicalIndicators(
                symbol=market_data.symbol,
                timestamp=market_data.timestamp,
                rsi_5=self._calculate_rsi(df['close'], 5),
                rsi_14=self._calculate_rsi(df['close'], 14),
                macd_line=0.0,  # Will be calculated
                macd_signal=0.0,  # Will be calculated  
                macd_histogram=0.0,  # Will be calculated
                ema_3=self._calculate_ema(df['close'], 3),
                ema_8=self._calculate_ema(df['close'], 8),
                ema_50=self._calculate_ema(df['close'], 50) if len(df) >= 50 else market_data.price,
                ema_200=self._calculate_ema(df['close'], 200) if len(df) >= 200 else market_data.price,
                cci_20=self._calculate_cci(df, 20),
                bollinger_upper=0.0,  # Will be calculated
                bollinger_middle=0.0,  # Will be calculated
                bollinger_lower=0.0,  # Will be calculated
                stoch_k=0.0,  # Will be calculated
                stoch_d=0.0,  # Will be calculated
                atr=self._calculate_atr(df, 14)
            )
            
            # Calculate MACD
            macd_data = self._calculate_macd(df['close'])
            indicators.macd_line = macd_data['macd']
            indicators.macd_signal = macd_data['signal']
            indicators.macd_histogram = macd_data['histogram']
            
            # Calculate Bollinger Bands
            bb_data = self._calculate_bollinger_bands(df['close'])
            indicators.bollinger_upper = bb_data['upper']
            indicators.bollinger_middle = bb_data['middle']
            indicators.bollinger_lower = bb_data['lower']
            
            # Calculate Stochastic
            stoch_data = self._calculate_stochastic(df)
            indicators.stoch_k = stoch_data['k']
            indicators.stoch_d = stoch_data['d']
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis for {symbol}: {e}")
            return self._basic_analysis(market_data)
    
    def _fetch_comprehensive_data(self, symbol: str) -> List[Dict]:
        """Fetch comprehensive historical data for analysis"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get 6 months of hourly data for thorough analysis
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            hist = ticker.history(start=start_date, end=end_date, interval="1h")
            
            if hist.empty:
                # Fallback to daily data if hourly not available
                hist = ticker.history(period="6mo", interval="1d")
            
            if hist.empty:
                return []
            
            data = []
            for timestamp, row in hist.iterrows():
                data.append({
                    'timestamp': timestamp,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']) if 'Volume' in row else 0
                })
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching comprehensive data for {symbol}: {e}")
            return []
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        try:
            if len(prices) < period + 1:
                return 50.0
                
            delta = prices.diff()
            gains = delta.where(delta > 0, 0).rolling(window=period).mean()
            losses = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return 50.0
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> float:
        """Calculate Exponential Moving Average"""
        try:
            if len(prices) < period:
                return float(prices.mean()) if len(prices) > 0 else 0.0
                
            ema = prices.ewm(span=period).mean()
            return float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else float(prices.iloc[-1])
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return 0.0
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        try:
            if len(prices) < slow:
                return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
            
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line
            
            return {
                "macd": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
                "signal": float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0,
                "histogram": float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    
    def _calculate_cci(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate Commodity Channel Index"""
        try:
            if len(df) < period:
                return 0.0
            
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma = typical_price.rolling(window=period).mean()
            mean_deviation = typical_price.rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - x.mean()))
            )
            
            cci = (typical_price - sma) / (0.015 * mean_deviation)
            return float(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating CCI: {e}")
            return 0.0
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        try:
            if len(prices) < period:
                current_price = float(prices.iloc[-1]) if len(prices) > 0 else 0.0
                return {
                    "upper": current_price * 1.02,
                    "middle": current_price,
                    "lower": current_price * 0.98
                }
            
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            
            return {
                "upper": float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else 0.0,
                "middle": float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else 0.0,
                "lower": float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {"upper": 0.0, "middle": 0.0, "lower": 0.0}
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, float]:
        """Calculate Stochastic Oscillator"""
        try:
            if len(df) < k_period:
                return {"k": 50.0, "d": 50.0}
            
            lowest_low = df['low'].rolling(window=k_period).min()
            highest_high = df['high'].rolling(window=k_period).max()
            
            k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_period).mean()
            
            return {
                "k": float(k_percent.iloc[-1]) if not pd.isna(k_percent.iloc[-1]) else 50.0,
                "d": float(d_percent.iloc[-1]) if not pd.isna(d_percent.iloc[-1]) else 50.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return {"k": 50.0, "d": 50.0}
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            if len(df) < 2:
                return 0.0
            
            high_low = df['high'] - df['low']
            high_prev_close = np.abs(df['high'] - df['close'].shift(1))
            low_prev_close = np.abs(df['low'] - df['close'].shift(1))
            
            true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
            
            return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0
    
    def _basic_analysis(self, market_data: MarketData) -> TechnicalIndicators:
        """Fallback basic analysis when insufficient data"""
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
    
    def interpret_real_signals(self, indicators: TechnicalIndicators, market_data: MarketData) -> Dict[str, Dict]:
        """Interpret technical indicators for real market conditions"""
        signals = {}
        
        # RSI Analysis
        if indicators.rsi_14 > 70:
            signals["rsi"] = {
                "signal": "SELL",
                "strength": "STRONG" if indicators.rsi_14 > 80 else "MEDIUM",
                "reason": f"Overbought condition (RSI: {indicators.rsi_14:.1f})"
            }
        elif indicators.rsi_14 < 30:
            signals["rsi"] = {
                "signal": "BUY", 
                "strength": "STRONG" if indicators.rsi_14 < 20 else "MEDIUM",
                "reason": f"Oversold condition (RSI: {indicators.rsi_14:.1f})"
            }
        else:
            signals["rsi"] = {
                "signal": "NEUTRAL",
                "strength": "WEAK",
                "reason": f"Normal range (RSI: {indicators.rsi_14:.1f})"
            }
        
        # MACD Analysis
        if indicators.macd_line > indicators.macd_signal and indicators.macd_histogram > 0:
            signals["macd"] = {
                "signal": "BUY",
                "strength": "STRONG" if abs(indicators.macd_histogram) > 0.001 else "MEDIUM",
                "reason": "Bullish MACD crossover with positive momentum"
            }
        elif indicators.macd_line < indicators.macd_signal and indicators.macd_histogram < 0:
            signals["macd"] = {
                "signal": "SELL",
                "strength": "STRONG" if abs(indicators.macd_histogram) > 0.001 else "MEDIUM", 
                "reason": "Bearish MACD crossover with negative momentum"
            }
        else:
            signals["macd"] = {
                "signal": "NEUTRAL",
                "strength": "WEAK",
                "reason": "Mixed MACD signals"
            }
        
        # EMA Trend Analysis
        if indicators.ema_3 > indicators.ema_8 > indicators.ema_50:
            signals["trend"] = {
                "signal": "BUY",
                "strength": "STRONG",
                "reason": "Strong uptrend across all timeframes"
            }
        elif indicators.ema_3 < indicators.ema_8 < indicators.ema_50:
            signals["trend"] = {
                "signal": "SELL", 
                "strength": "STRONG",
                "reason": "Strong downtrend across all timeframes"
            }
        elif indicators.ema_3 > indicators.ema_8:
            signals["trend"] = {
                "signal": "BUY",
                "strength": "MEDIUM",
                "reason": "Short-term bullish trend"
            }
        else:
            signals["trend"] = {
                "signal": "SELL",
                "strength": "MEDIUM", 
                "reason": "Short-term bearish trend"
            }
        
        # Bollinger Bands Analysis
        current_price = market_data.price
        if current_price >= indicators.bollinger_upper:
            signals["bollinger"] = {
                "signal": "SELL",
                "strength": "MEDIUM",
                "reason": "Price at upper Bollinger Band - potential reversal"
            }
        elif current_price <= indicators.bollinger_lower:
            signals["bollinger"] = {
                "signal": "BUY",
                "strength": "MEDIUM", 
                "reason": "Price at lower Bollinger Band - potential bounce"
            }
        else:
            signals["bollinger"] = {
                "signal": "NEUTRAL",
                "strength": "WEAK",
                "reason": "Price within normal Bollinger Band range"
            }
        
        return signals
    
    async def get_market_strength(self, symbol: str) -> Dict[str, float]:
        """Analyze overall market strength and volatility"""
        try:
            loop = asyncio.get_event_loop()
            hist_data = await loop.run_in_executor(
                self.executor,
                self._fetch_comprehensive_data,
                symbol
            )
            
            if not hist_data or len(hist_data) < 20:
                return {"strength": 0.5, "volatility": 0.5, "volume_trend": 0.5}
            
            df = pd.DataFrame(hist_data)
            
            # Calculate market strength indicators
            price_momentum = self._calculate_price_momentum(df)
            volume_trend = self._calculate_volume_trend(df)
            volatility = self._calculate_volatility(df)
            
            return {
                "strength": price_momentum,
                "volatility": volatility,
                "volume_trend": volume_trend
            }
            
        except Exception as e:
            logger.error(f"Error calculating market strength: {e}")
            return {"strength": 0.5, "volatility": 0.5, "volume_trend": 0.5}
    
    def _calculate_price_momentum(self, df: pd.DataFrame) -> float:
        """Calculate price momentum (0-1 scale)"""
        try:
            if len(df) < 10:
                return 0.5
            
            recent_prices = df['close'].tail(10)
            older_prices = df['close'].tail(20).head(10)
            
            recent_avg = recent_prices.mean()
            older_avg = older_prices.mean()
            
            momentum = (recent_avg - older_avg) / older_avg if older_avg != 0 else 0
            
            # Normalize to 0-1 scale
            normalized = 0.5 + (momentum * 2.5)  # Amplify small changes
            return max(0, min(1, normalized))
            
        except Exception:
            return 0.5
    
    def _calculate_volume_trend(self, df: pd.DataFrame) -> float:
        """Calculate volume trend (0-1 scale)"""
        try:
            if len(df) < 10 or 'volume' not in df.columns:
                return 0.5
            
            recent_volume = df['volume'].tail(5).mean()
            historical_volume = df['volume'].head(len(df)-5).mean()
            
            if historical_volume == 0:
                return 0.5
            
            volume_ratio = recent_volume / historical_volume
            
            # Normalize to 0-1 scale (volume_ratio of 2 = max, 0.5 = min)
            normalized = min(1, max(0, (volume_ratio - 0.5) / 1.5))
            return normalized
            
        except Exception:
            return 0.5
    
    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """Calculate price volatility (0-1 scale)"""
        try:
            if len(df) < 10:
                return 0.5
            
            returns = df['close'].pct_change().dropna()
            volatility = returns.std()
            
            # Normalize volatility (0.02 = low, 0.1 = high)
            normalized = min(1, max(0, (volatility - 0.01) / 0.09))
            return normalized
            
        except Exception:
            return 0.5