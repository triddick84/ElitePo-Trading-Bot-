"""
OANDA Market Data Service
=========================
Fetches historical OHLCV data and streams real-time prices from OANDA V20 API.
Used for AI/ML training, backtesting, and live trading signals.

Supports:
- Historical candlestick data across all timeframes (5s to Monthly)
- Real-time price streaming for multiple instruments
- Multi-timeframe analysis for trend detection and mean reversion
"""

import os
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class OandaGranularity(str, Enum):
    """OANDA candlestick granularities"""
    S5 = "S5"       # 5 seconds
    S10 = "S10"     # 10 seconds
    S15 = "S15"     # 15 seconds
    S30 = "S30"     # 30 seconds
    M1 = "M1"       # 1 minute
    M2 = "M2"       # 2 minutes
    M4 = "M4"       # 4 minutes
    M5 = "M5"       # 5 minutes
    M10 = "M10"     # 10 minutes
    M15 = "M15"     # 15 minutes
    M30 = "M30"     # 30 minutes
    H1 = "H1"       # 1 hour
    H2 = "H2"       # 2 hours
    H3 = "H3"       # 3 hours
    H4 = "H4"       # 4 hours
    H6 = "H6"       # 6 hours
    H8 = "H8"       # 8 hours
    H12 = "H12"     # 12 hours
    D = "D"         # Daily
    W = "W"         # Weekly
    M = "M"         # Monthly


# Map app timeframes to OANDA granularities
TIMEFRAME_TO_OANDA = {
    "5s": OandaGranularity.S5,
    "10s": OandaGranularity.S10,
    "15s": OandaGranularity.S15,
    "30s": OandaGranularity.S30,
    "1m": OandaGranularity.M1,
    "2m": OandaGranularity.M2,
    "3m": OandaGranularity.M4,  # Closest match
    "5m": OandaGranularity.M5,
    "10m": OandaGranularity.M10,
    "15m": OandaGranularity.M15,
    "30m": OandaGranularity.M30,
    "1h": OandaGranularity.H1,
    "4h": OandaGranularity.H4,
    "1d": OandaGranularity.D,
}


@dataclass
class OHLCVCandle:
    """Single candlestick data point"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "complete": self.complete
        }


@dataclass
class MarketDataSnapshot:
    """Current market state with technical indicators"""
    symbol: str
    timeframe: str
    candles: List[OHLCVCandle]
    current_price: float
    bid: float
    ask: float
    spread: float
    
    # Technical indicators (calculated)
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    
    # Trend detection
    trend_direction: Optional[str] = None  # "BULLISH", "BEARISH", "NEUTRAL"
    trend_strength: Optional[float] = None  # 0-100
    
    # Mean reversion
    is_overbought: bool = False
    is_oversold: bool = False
    distance_from_mean: Optional[float] = None  # In standard deviations


class OandaMarketDataService:
    """
    Service for fetching market data from OANDA V20 API.
    Provides historical OHLCV data and real-time price streaming.
    """
    
    def __init__(self, access_token: str = None, account_id: str = None, environment: str = None):
        # Load from environment if not provided
        self.access_token = access_token or os.environ.get("OANDA_ACCESS_TOKEN", "")
        self.account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID", "")
        self.environment = environment or os.environ.get("OANDA_ENVIRONMENT", "practice")
        
        # API URLs based on environment
        if self.environment == "live":
            self.api_url = "https://api-fxtrade.oanda.com"
            self.stream_url = "https://stream-fxtrade.oanda.com"
        else:
            self.api_url = "https://api-fxpractice.oanda.com"
            self.stream_url = "https://stream-fxpractice.oanda.com"
        
        self.is_configured = bool(self.access_token and self.account_id)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache for recent data
        self._candle_cache: Dict[str, List[OHLCVCandle]] = {}
        self._price_cache: Dict[str, Dict] = {}
        
        if self.is_configured:
            logger.info(f"OandaMarketDataService initialized - configured: True, env: {self.environment}, account: {self.account_id[:10]}...")
        else:
            logger.info(f"OandaMarketDataService initialized - configured: False (credentials not found)")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept-Datetime-Format": "RFC3339"
                }
            )
        return self._session
    
    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol format (EURUSD -> EUR_USD)"""
        # Already in OANDA format
        if "_" in symbol:
            return symbol
        
        # Common forex pairs
        forex_bases = ["EUR", "GBP", "USD", "JPY", "CHF", "AUD", "NZD", "CAD"]
        for base in forex_bases:
            if symbol.startswith(base) and len(symbol) == 6:
                return f"{symbol[:3]}_{symbol[3:]}"
        
        # OTC symbols - convert to closest OANDA equivalent
        if symbol.endswith("_OTC") or "_OTC" in symbol:
            base_symbol = symbol.replace("_OTC", "").replace("OTC", "")
            for base in forex_bases:
                if base_symbol.startswith(base) and len(base_symbol) == 6:
                    return f"{base_symbol[:3]}_{base_symbol[3:]}"
        
        return symbol
    
    async def get_candles(
        self,
        instrument: str,
        granularity: str,
        count: int = 500,
        from_time: datetime = None,
        to_time: datetime = None,
        price: str = "M"  # M=mid, B=bid, A=ask
    ) -> List[OHLCVCandle]:
        """
        Fetch historical candlestick data from OANDA.
        
        Args:
            instrument: Currency pair (e.g., "EUR_USD" or "EURUSD")
            granularity: Timeframe (e.g., "M1", "H1", "D")
            count: Number of candles to fetch (max 5000)
            from_time: Start time for data
            to_time: End time for data
            price: Price component (M=mid, B=bid, A=ask)
        
        Returns:
            List of OHLCV candles
        """
        if not self.is_configured:
            logger.warning("OANDA not configured - returning empty candles")
            return []
        
        try:
            session = await self._get_session()
            
            # Convert symbol format
            oanda_instrument = self._convert_symbol(instrument)
            
            # Convert granularity if needed
            if granularity in TIMEFRAME_TO_OANDA:
                oanda_granularity = TIMEFRAME_TO_OANDA[granularity].value
            else:
                oanda_granularity = granularity
            
            # Build params
            params = {
                "granularity": oanda_granularity,
                "price": price,
                "count": min(count, 5000)
            }
            
            if from_time:
                params["from"] = from_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            if to_time:
                params["to"] = to_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            url = f"{self.api_url}/v3/instruments/{oanda_instrument}/candles"
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    candles = []
                    
                    for candle in data.get("candles", []):
                        mid = candle.get("mid", candle.get("bid", candle.get("ask", {})))
                        
                        candles.append(OHLCVCandle(
                            timestamp=datetime.fromisoformat(candle["time"].replace("Z", "+00:00")),
                            open=float(mid.get("o", 0)),
                            high=float(mid.get("h", 0)),
                            low=float(mid.get("l", 0)),
                            close=float(mid.get("c", 0)),
                            volume=int(candle.get("volume", 0)),
                            complete=candle.get("complete", True)
                        ))
                    
                    # Cache the data
                    cache_key = f"{oanda_instrument}_{oanda_granularity}"
                    self._candle_cache[cache_key] = candles
                    
                    logger.info(f"Fetched {len(candles)} candles for {oanda_instrument} {oanda_granularity}")
                    return candles
                else:
                    error_text = await response.text()
                    logger.error(f"OANDA API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching OANDA candles: {e}")
            return []
    
    async def get_current_price(self, instrument: str) -> Optional[Dict]:
        """
        Get current bid/ask price for an instrument.
        
        Returns:
            Dict with bid, ask, mid, spread
        """
        if not self.is_configured:
            return None
        
        try:
            session = await self._get_session()
            oanda_instrument = self._convert_symbol(instrument)
            
            url = f"{self.api_url}/v3/accounts/{self.account_id}/pricing"
            params = {"instruments": oanda_instrument}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = data.get("prices", [])
                    
                    if prices:
                        price_data = prices[0]
                        bid = float(price_data.get("bids", [{"price": 0}])[0].get("price", 0))
                        ask = float(price_data.get("asks", [{"price": 0}])[0].get("price", 0))
                        
                        result = {
                            "instrument": oanda_instrument,
                            "bid": bid,
                            "ask": ask,
                            "mid": (bid + ask) / 2,
                            "spread": ask - bid,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        self._price_cache[oanda_instrument] = result
                        return result
                
                return None
                
        except Exception as e:
            logger.error(f"Error fetching OANDA price: {e}")
            return None
    
    async def get_multi_timeframe_data(
        self,
        instrument: str,
        timeframes: List[str] = None,
        candle_count: int = 100
    ) -> Dict[str, List[OHLCVCandle]]:
        """
        Fetch data for multiple timeframes simultaneously.
        Used for multi-timeframe analysis in AI/ML models.
        """
        if timeframes is None:
            timeframes = ["5s", "1m", "5m", "15m", "1h"]
        
        result = {}
        
        for tf in timeframes:
            candles = await self.get_candles(
                instrument=instrument,
                granularity=tf,
                count=candle_count
            )
            result[tf] = candles
        
        return result
    
    def calculate_technical_indicators(self, candles: List[OHLCVCandle]) -> Dict[str, Any]:
        """
        Calculate comprehensive technical indicators from candle data.
        Used for trend detection and mean reversion analysis.
        """
        if len(candles) < 50:
            return {}
        
        # Convert to pandas DataFrame
        df = pd.DataFrame([{
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume
        } for c in candles])
        
        df.set_index("timestamp", inplace=True)
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]
        
        indicators = {}
        
        # Moving Averages
        indicators["sma_20"] = closes.rolling(20).mean().iloc[-1] if len(closes) >= 20 else None
        indicators["sma_50"] = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
        indicators["ema_12"] = closes.ewm(span=12).mean().iloc[-1]
        indicators["ema_26"] = closes.ewm(span=26).mean().iloc[-1]
        
        # MACD
        macd_line = closes.ewm(span=12).mean() - closes.ewm(span=26).mean()
        signal_line = macd_line.ewm(span=9).mean()
        indicators["macd"] = macd_line.iloc[-1]
        indicators["macd_signal"] = signal_line.iloc[-1]
        indicators["macd_histogram"] = macd_line.iloc[-1] - signal_line.iloc[-1]
        
        # RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        indicators["rsi_14"] = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        
        # Bollinger Bands
        bb_sma = closes.rolling(20).mean()
        bb_std = closes.rolling(20).std()
        indicators["bb_upper"] = (bb_sma + 2 * bb_std).iloc[-1]
        indicators["bb_middle"] = bb_sma.iloc[-1]
        indicators["bb_lower"] = (bb_sma - 2 * bb_std).iloc[-1]
        
        # ATR
        tr1 = highs - lows
        tr2 = abs(highs - closes.shift())
        tr3 = abs(lows - closes.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        indicators["atr_14"] = tr.rolling(14).mean().iloc[-1]
        
        # Trend Detection
        current_price = closes.iloc[-1]
        sma_20 = indicators.get("sma_20")
        sma_50 = indicators.get("sma_50")
        
        if sma_20 and sma_50:
            if current_price > sma_20 > sma_50:
                indicators["trend_direction"] = "BULLISH"
                indicators["trend_strength"] = min(100, ((current_price - sma_50) / sma_50) * 1000)
            elif current_price < sma_20 < sma_50:
                indicators["trend_direction"] = "BEARISH"
                indicators["trend_strength"] = min(100, ((sma_50 - current_price) / sma_50) * 1000)
            else:
                indicators["trend_direction"] = "NEUTRAL"
                indicators["trend_strength"] = 30
        
        # Mean Reversion Detection
        rsi_val = indicators.get("rsi_14", 50)
        indicators["is_overbought"] = rsi_val > 70
        indicators["is_oversold"] = rsi_val < 30
        
        bb_middle = indicators.get("bb_middle")
        bb_std_val = bb_std.iloc[-1] if not pd.isna(bb_std.iloc[-1]) else 1
        if bb_middle and bb_std_val > 0:
            indicators["distance_from_mean"] = (current_price - bb_middle) / bb_std_val
        
        return indicators
    
    async def get_market_snapshot(self, instrument: str, timeframe: str = "1m") -> Optional[MarketDataSnapshot]:
        """
        Get complete market snapshot with price and indicators.
        Used for real-time trading decisions.
        """
        try:
            # Get candles
            candles = await self.get_candles(instrument, timeframe, count=100)
            if not candles:
                return None
            
            # Get current price
            price_data = await self.get_current_price(instrument)
            if not price_data:
                # Use last candle close as fallback
                price_data = {
                    "bid": candles[-1].close,
                    "ask": candles[-1].close,
                    "mid": candles[-1].close,
                    "spread": 0
                }
            
            # Calculate indicators
            indicators = self.calculate_technical_indicators(candles)
            
            return MarketDataSnapshot(
                symbol=instrument,
                timeframe=timeframe,
                candles=candles,
                current_price=price_data["mid"],
                bid=price_data["bid"],
                ask=price_data["ask"],
                spread=price_data["spread"],
                **indicators
            )
            
        except Exception as e:
            logger.error(f"Error getting market snapshot: {e}")
            return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test OANDA API connection"""
        if not self.is_configured:
            return {
                "success": False,
                "error": "OANDA credentials not configured",
                "configured": False
            }
        
        try:
            session = await self._get_session()
            url = f"{self.api_url}/v3/accounts/{self.account_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    account = data.get("account", {})
                    return {
                        "success": True,
                        "account_id": account.get("id"),
                        "balance": account.get("balance"),
                        "currency": account.get("currency"),
                        "environment": self.environment
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status}",
                        "configured": True
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "configured": True
            }


# Global instance
oanda_service = OandaMarketDataService()
