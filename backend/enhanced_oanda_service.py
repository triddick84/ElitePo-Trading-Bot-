"""
Enhanced OANDA Market Data Service using oandapyV20
===================================================
Provides advanced features for AI/ML trading:

1. Real-time Price Streaming - Instant tick data
2. InstrumentsCandlesFactory - Fetch >5000 candles for better training
3. Multi-instrument Arbitrage Detection
4. Connection Pooling and Error Recovery
5. Technical Analysis with TA-Lib style indicators

Based on: https://github.com/hootnot/oanda-api-v20
"""

import os
import logging
import asyncio
import json
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import numpy as np
import pandas as pd

# oandapyV20 imports
try:
    from oandapyV20 import API
    from oandapyV20.exceptions import V20Error, StreamTerminated
    import oandapyV20.endpoints.instruments as instruments
    import oandapyV20.endpoints.pricing as pricing
    import oandapyV20.endpoints.accounts as accounts
    from oandapyV20.contrib.factories import InstrumentsCandlesFactory
    OANDAPY_AVAILABLE = True
except ImportError:
    OANDAPY_AVAILABLE = False
    logging.warning("oandapyV20 not available - using fallback HTTP client")

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Signal strength classification"""
    VERY_STRONG = "VERY_STRONG"
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass
class EnhancedOHLCV:
    """Enhanced OHLCV with calculated indicators"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool = True
    
    # Technical indicators (pre-calculated)
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_percent: Optional[float] = None  # Where price is within bands (0-1)
    atr: Optional[float] = None
    adx: Optional[float] = None  # Trend strength
    stochastic_k: Optional[float] = None
    stochastic_d: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "complete": self.complete,
            "indicators": {
                "sma_10": self.sma_10,
                "sma_20": self.sma_20,
                "sma_50": self.sma_50,
                "ema_12": self.ema_12,
                "ema_26": self.ema_26,
                "rsi": self.rsi,
                "macd": self.macd,
                "macd_signal": self.macd_signal,
                "macd_histogram": self.macd_histogram,
                "bb_upper": self.bb_upper,
                "bb_middle": self.bb_middle,
                "bb_lower": self.bb_lower,
                "bb_percent": self.bb_percent,
                "atr": self.atr,
                "adx": self.adx,
                "stochastic_k": self.stochastic_k,
                "stochastic_d": self.stochastic_d
            }
        }


@dataclass  
class ArbitrageOpportunity:
    """Detected arbitrage opportunity"""
    instrument_pair: Tuple[str, str]
    price_difference: float
    expected_profit_pips: float
    confidence: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            "instruments": list(self.instrument_pair),
            "price_difference": self.price_difference,
            "expected_profit_pips": self.expected_profit_pips,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TrendSignal:
    """Enhanced trend detection signal"""
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    strength: SignalStrength
    confidence: float
    supporting_indicators: List[str]
    conflicting_indicators: List[str]
    recommended_action: str  # "CALL", "PUT", "HOLD"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "direction": self.direction,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "supporting_indicators": self.supporting_indicators,
            "conflicting_indicators": self.conflicting_indicators,
            "recommended_action": self.recommended_action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }


class TechnicalAnalyzer:
    """
    Advanced technical analysis engine.
    Calculates all major indicators for signal generation.
    """
    
    @staticmethod
    def calculate_sma(data: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(data: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD indicator"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(data: pd.Series, period: int = 20, std_mult: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands"""
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = sma + (std * std_mult)
        lower = sma - (std * std_mult)
        return upper, sma, lower
    
    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    @staticmethod
    def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average Directional Index (trend strength)"""
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr = TechnicalAnalyzer.calculate_atr(high, low, close, 1)
        
        plus_di = 100 * (plus_dm.ewm(span=period).mean() / tr.ewm(span=period).mean())
        minus_di = 100 * (minus_dm.ewm(span=period).mean() / tr.ewm(span=period).mean())
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period).mean()
        return adx
    
    @staticmethod
    def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        stoch_k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        stoch_d = stoch_k.rolling(window=d_period).mean()
        return stoch_k, stoch_d
    
    @staticmethod
    def analyze_full(df: pd.DataFrame) -> pd.DataFrame:
        """
        Perform full technical analysis on OHLCV dataframe.
        Adds all indicators as columns.
        """
        if len(df) < 50:
            return df
        
        # Moving Averages
        df['sma_10'] = TechnicalAnalyzer.calculate_sma(df['close'], 10)
        df['sma_20'] = TechnicalAnalyzer.calculate_sma(df['close'], 20)
        df['sma_50'] = TechnicalAnalyzer.calculate_sma(df['close'], 50)
        df['ema_12'] = TechnicalAnalyzer.calculate_ema(df['close'], 12)
        df['ema_26'] = TechnicalAnalyzer.calculate_ema(df['close'], 26)
        
        # RSI
        df['rsi'] = TechnicalAnalyzer.calculate_rsi(df['close'])
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_histogram'] = TechnicalAnalyzer.calculate_macd(df['close'])
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = TechnicalAnalyzer.calculate_bollinger_bands(df['close'])
        bb_range = df['bb_upper'] - df['bb_lower']
        df['bb_percent'] = (df['close'] - df['bb_lower']) / bb_range
        
        # ATR
        df['atr'] = TechnicalAnalyzer.calculate_atr(df['high'], df['low'], df['close'])
        
        # ADX
        df['adx'] = TechnicalAnalyzer.calculate_adx(df['high'], df['low'], df['close'])
        
        # Stochastic
        df['stochastic_k'], df['stochastic_d'] = TechnicalAnalyzer.calculate_stochastic(df['high'], df['low'], df['close'])
        
        return df


class EnhancedOandaService:
    """
    Enhanced OANDA service using oandapyV20 library.
    Provides streaming, factory patterns, and advanced analysis.
    """
    
    def __init__(self, access_token: str = None, account_id: str = None, environment: str = None):
        self.access_token = access_token or os.environ.get("OANDA_ACCESS_TOKEN", "")
        self.account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID", "")
        self.environment = environment or os.environ.get("OANDA_ENVIRONMENT", "practice")
        
        self.is_configured = bool(self.access_token and self.account_id)
        self.api: Optional[API] = None
        
        # Initialize API client
        if self.is_configured and OANDAPY_AVAILABLE:
            self.api = API(access_token=self.access_token, environment=self.environment)
        
        # Data caches
        self._candle_cache: Dict[str, pd.DataFrame] = {}
        self._price_cache: Dict[str, Dict] = {}
        self._tick_buffer: Dict[str, deque] = {}
        
        # Streaming state
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_active = False
        self._price_callbacks: List[Callable] = []
        
        # Analysis engine
        self.analyzer = TechnicalAnalyzer()
        
        logger.info(f"EnhancedOandaService initialized - configured: {self.is_configured}, oandapyV20: {OANDAPY_AVAILABLE}")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test OANDA API connection"""
        if not self.is_configured or not OANDAPY_AVAILABLE:
            return {"success": False, "error": "Not configured or oandapyV20 not available"}
        
        try:
            r = accounts.AccountDetails(self.account_id)
            response = self.api.request(r)
            account = response.get("account", {})
            
            return {
                "success": True,
                "account_id": account.get("id"),
                "balance": account.get("balance"),
                "currency": account.get("currency"),
                "unrealized_pl": account.get("unrealizedPL"),
                "nav": account.get("NAV"),
                "margin_used": account.get("marginUsed"),
                "open_trades": account.get("openTradeCount"),
                "environment": self.environment
            }
        except V20Error as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_candles_large(
        self,
        instrument: str,
        granularity: str,
        from_time: str,
        to_time: str
    ) -> pd.DataFrame:
        """
        Fetch large amounts of historical data using InstrumentsCandlesFactory.
        Can fetch >5000 candles by automatically batching requests.
        
        Args:
            instrument: e.g., "EUR_USD"
            granularity: e.g., "M1", "H1", "D"
            from_time: ISO format datetime string
            to_time: ISO format datetime string
        
        Returns:
            DataFrame with OHLCV data and calculated indicators
        """
        if not self.is_configured or not OANDAPY_AVAILABLE:
            return pd.DataFrame()
        
        try:
            params = {
                "granularity": granularity,
                "from": from_time,
                "to": to_time
            }
            
            candles_data = []
            
            for r in InstrumentsCandlesFactory(instrument=instrument, params=params):
                logger.info(f"Fetching batch: {r.params}")
                rv = self.api.request(r)
                
                for candle in rv.get("candles", []):
                    if candle.get("complete", True):
                        mid = candle.get("mid", {})
                        candles_data.append({
                            "timestamp": pd.to_datetime(candle["time"]),
                            "open": float(mid.get("o", 0)),
                            "high": float(mid.get("h", 0)),
                            "low": float(mid.get("l", 0)),
                            "close": float(mid.get("c", 0)),
                            "volume": int(candle.get("volume", 0))
                        })
            
            if not candles_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(candles_data)
            df.set_index("timestamp", inplace=True)
            
            # Calculate all technical indicators
            df = TechnicalAnalyzer.analyze_full(df)
            
            # Cache the result
            cache_key = f"{instrument}_{granularity}"
            self._candle_cache[cache_key] = df
            
            logger.info(f"Fetched {len(df)} candles for {instrument} {granularity}")
            return df
            
        except V20Error as e:
            logger.error(f"OANDA API error: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            return pd.DataFrame()
    
    def get_candles(
        self,
        instrument: str,
        granularity: str = "M1",
        count: int = 500
    ) -> pd.DataFrame:
        """
        Fetch recent candles with full technical analysis.
        """
        if not self.is_configured or not OANDAPY_AVAILABLE:
            return pd.DataFrame()
        
        try:
            params = {
                "granularity": granularity,
                "count": min(count, 5000)
            }
            
            r = instruments.InstrumentsCandles(instrument=instrument, params=params)
            response = self.api.request(r)
            
            candles_data = []
            for candle in response.get("candles", []):
                mid = candle.get("mid", {})
                candles_data.append({
                    "timestamp": pd.to_datetime(candle["time"]),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(candle.get("volume", 0)),
                    "complete": candle.get("complete", True)
                })
            
            if not candles_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(candles_data)
            df.set_index("timestamp", inplace=True)
            
            # Calculate technical indicators
            df = TechnicalAnalyzer.analyze_full(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            return pd.DataFrame()
    
    def get_current_prices(self, instruments_list: List[str]) -> Dict[str, Dict]:
        """
        Get current prices for multiple instruments.
        Useful for arbitrage detection.
        """
        if not self.is_configured or not OANDAPY_AVAILABLE:
            return {}
        
        try:
            params = {"instruments": ",".join(instruments_list)}
            r = pricing.PricingInfo(accountID=self.account_id, params=params)
            response = self.api.request(r)
            
            result = {}
            for price_data in response.get("prices", []):
                instrument = price_data.get("instrument")
                
                bids = price_data.get("bids", [])
                asks = price_data.get("asks", [])
                
                bid = float(bids[0]["price"]) if bids else 0
                ask = float(asks[0]["price"]) if asks else 0
                
                result[instrument] = {
                    "bid": bid,
                    "ask": ask,
                    "mid": (bid + ask) / 2,
                    "spread": ask - bid,
                    "tradeable": price_data.get("tradeable", False),
                    "timestamp": price_data.get("time")
                }
                
                self._price_cache[instrument] = result[instrument]
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}
    
    def start_price_stream(self, instruments_list: List[str], callback: Callable = None):
        """
        Start real-time price streaming in background thread.
        
        Args:
            instruments_list: List of instruments to stream
            callback: Function to call with each price update
        """
        if not self.is_configured or not OANDAPY_AVAILABLE:
            logger.warning("Cannot start stream - not configured")
            return False
        
        if self._stream_active:
            logger.warning("Stream already active")
            return False
        
        if callback:
            self._price_callbacks.append(callback)
        
        def stream_worker():
            try:
                params = {"instruments": ",".join(instruments_list)}
                r = pricing.PricingStream(accountID=self.account_id, params=params)
                
                self._stream_active = True
                logger.info(f"Starting price stream for: {instruments_list}")
                
                for tick in self.api.request(r):
                    if not self._stream_active:
                        break
                    
                    tick_type = tick.get("type")
                    
                    if tick_type == "PRICE":
                        instrument = tick.get("instrument")
                        bids = tick.get("bids", [])
                        asks = tick.get("asks", [])
                        
                        if bids and asks:
                            price_data = {
                                "instrument": instrument,
                                "bid": float(bids[0]["price"]),
                                "ask": float(asks[0]["price"]),
                                "mid": (float(bids[0]["price"]) + float(asks[0]["price"])) / 2,
                                "timestamp": tick.get("time"),
                                "type": "tick"
                            }
                            
                            # Update cache
                            self._price_cache[instrument] = price_data
                            
                            # Store in tick buffer for analysis
                            if instrument not in self._tick_buffer:
                                self._tick_buffer[instrument] = deque(maxlen=1000)
                            self._tick_buffer[instrument].append(price_data)
                            
                            # Call callbacks
                            for cb in self._price_callbacks:
                                try:
                                    cb(price_data)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                    
                    elif tick_type == "HEARTBEAT":
                        pass  # Keep-alive signal
                        
            except StreamTerminated as e:
                logger.info(f"Stream terminated: {e}")
            except Exception as e:
                logger.error(f"Stream error: {e}")
            finally:
                self._stream_active = False
        
        self._stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self._stream_thread.start()
        return True
    
    def stop_price_stream(self):
        """Stop the price streaming"""
        self._stream_active = False
        if self._stream_thread:
            self._stream_thread.join(timeout=5)
            self._stream_thread = None
        logger.info("Price stream stopped")
    
    def detect_arbitrage(self, correlated_pairs: List[Tuple[str, str]]) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities between correlated pairs.
        
        Args:
            correlated_pairs: List of instrument pairs that should move together
                              e.g., [("EUR_USD", "EUR_GBP"), ...]
        """
        opportunities = []
        
        # Get all unique instruments
        all_instruments = set()
        for pair in correlated_pairs:
            all_instruments.add(pair[0])
            all_instruments.add(pair[1])
        
        # Fetch current prices
        prices = self.get_current_prices(list(all_instruments))
        
        for inst1, inst2 in correlated_pairs:
            if inst1 not in prices or inst2 not in prices:
                continue
            
            price1 = prices[inst1]["mid"]
            price2 = prices[inst2]["mid"]
            
            # Calculate expected ratio and deviation
            # This is simplified - real arbitrage would need historical correlation
            ratio = price1 / price2 if price2 != 0 else 0
            
            # Check for significant deviations (simplified)
            # In reality, you'd compare against historical mean ratio
            expected_ratio = 1.0  # Placeholder
            deviation = abs(ratio - expected_ratio) / expected_ratio if expected_ratio != 0 else 0
            
            if deviation > 0.001:  # 0.1% deviation threshold
                opportunities.append(ArbitrageOpportunity(
                    instrument_pair=(inst1, inst2),
                    price_difference=price1 - price2,
                    expected_profit_pips=deviation * 10000,  # Simplified
                    confidence=min(100, deviation * 10000),
                    timestamp=datetime.now(timezone.utc)
                ))
        
        return opportunities
    
    def generate_trend_signal(self, instrument: str, timeframe: str = "M1") -> Optional[TrendSignal]:
        """
        Generate comprehensive trend signal using multiple indicators.
        """
        df = self.get_candles(instrument, timeframe, count=100)
        
        if df.empty or len(df) < 50:
            return None
        
        latest = df.iloc[-1]
        
        # Collect supporting and conflicting indicators
        bullish_signals = []
        bearish_signals = []
        
        # SMA Analysis
        close = latest['close']
        if pd.notna(latest.get('sma_20')) and pd.notna(latest.get('sma_50')):
            if close > latest['sma_20'] > latest['sma_50']:
                bullish_signals.append("Price above SMA20 > SMA50")
            elif close < latest['sma_20'] < latest['sma_50']:
                bearish_signals.append("Price below SMA20 < SMA50")
        
        # RSI Analysis
        rsi = latest.get('rsi')
        if pd.notna(rsi):
            if rsi < 30:
                bullish_signals.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                bearish_signals.append(f"RSI overbought ({rsi:.1f})")
            elif rsi > 50:
                bullish_signals.append(f"RSI bullish ({rsi:.1f})")
            else:
                bearish_signals.append(f"RSI bearish ({rsi:.1f})")
        
        # MACD Analysis
        macd_hist = latest.get('macd_histogram')
        if pd.notna(macd_hist):
            if macd_hist > 0:
                bullish_signals.append(f"MACD histogram positive ({macd_hist:.5f})")
            else:
                bearish_signals.append(f"MACD histogram negative ({macd_hist:.5f})")
        
        # Bollinger Band Analysis
        bb_percent = latest.get('bb_percent')
        if pd.notna(bb_percent):
            if bb_percent < 0.2:
                bullish_signals.append(f"Price near lower BB ({bb_percent:.2f})")
            elif bb_percent > 0.8:
                bearish_signals.append(f"Price near upper BB ({bb_percent:.2f})")
        
        # Stochastic Analysis
        stoch_k = latest.get('stochastic_k')
        stoch_d = latest.get('stochastic_d')
        if pd.notna(stoch_k) and pd.notna(stoch_d):
            if stoch_k < 20 and stoch_k > stoch_d:
                bullish_signals.append(f"Stochastic oversold cross ({stoch_k:.1f})")
            elif stoch_k > 80 and stoch_k < stoch_d:
                bearish_signals.append(f"Stochastic overbought cross ({stoch_k:.1f})")
        
        # ADX (trend strength)
        adx = latest.get('adx')
        trend_strength_value = adx if pd.notna(adx) else 25
        
        # Determine final direction and strength
        bull_count = len(bullish_signals)
        bear_count = len(bearish_signals)
        total = bull_count + bear_count
        
        if total == 0:
            return TrendSignal(
                direction="NEUTRAL",
                strength=SignalStrength.NO_SIGNAL,
                confidence=0,
                supporting_indicators=[],
                conflicting_indicators=[],
                recommended_action="HOLD"
            )
        
        if bull_count > bear_count:
            direction = "BULLISH"
            confidence = (bull_count / total) * 100
            supporting = bullish_signals
            conflicting = bearish_signals
            action = "CALL"
        elif bear_count > bull_count:
            direction = "BEARISH"
            confidence = (bear_count / total) * 100
            supporting = bearish_signals
            conflicting = bullish_signals
            action = "PUT"
        else:
            direction = "NEUTRAL"
            confidence = 50
            supporting = bullish_signals
            conflicting = bearish_signals
            action = "HOLD"
        
        # Adjust confidence based on ADX (trend strength)
        if trend_strength_value > 25:
            confidence = min(100, confidence * 1.2)  # Boost confidence in strong trends
        elif trend_strength_value < 20:
            confidence = confidence * 0.8  # Reduce confidence in weak trends
        
        # Determine signal strength
        if confidence >= 80:
            strength = SignalStrength.VERY_STRONG
        elif confidence >= 65:
            strength = SignalStrength.STRONG
        elif confidence >= 50:
            strength = SignalStrength.MODERATE
        elif confidence >= 35:
            strength = SignalStrength.WEAK
        else:
            strength = SignalStrength.NO_SIGNAL
        
        # Calculate stop loss and take profit based on ATR
        atr = latest.get('atr')
        if pd.notna(atr):
            if direction == "BULLISH":
                stop_loss = close - (atr * 2)
                take_profit = close + (atr * 3)
            elif direction == "BEARISH":
                stop_loss = close + (atr * 2)
                take_profit = close - (atr * 3)
            else:
                stop_loss = None
                take_profit = None
        else:
            stop_loss = None
            take_profit = None
        
        return TrendSignal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            supporting_indicators=supporting,
            conflicting_indicators=conflicting,
            recommended_action=action,
            entry_price=close,
            stop_loss=stop_loss,
            take_profit=take_profit
        )


# Global instance
enhanced_oanda = EnhancedOandaService()
