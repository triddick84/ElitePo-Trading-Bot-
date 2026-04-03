"""
Deriv API Integration for Synthetic Indices Historical Data
Provides free access to Volatility indices, Crash/Boom, and other synthetic markets
"""
import asyncio
import websockets
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd

logger = logging.getLogger(__name__)

class DerivDataService:
    """
    Deriv WebSocket API client for historical tick/candle data
    No API key required for market data
    """
    
    DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"  # Public app_id
    
    # Synthetic indices symbols mapping
    SYNTHETIC_SYMBOLS = {
        # Volatility Indices
        "V10": "R_10",      # Volatility 10 Index
        "V25": "R_25",      # Volatility 25 Index
        "V50": "R_50",      # Volatility 50 Index
        "V75": "R_75",      # Volatility 75 Index
        "V100": "R_100",    # Volatility 100 Index
        # 1-second Volatility
        "V10_1S": "1HZ10V",
        "V25_1S": "1HZ25V",
        "V50_1S": "1HZ50V",
        "V75_1S": "1HZ75V",
        "V100_1S": "1HZ100V",
        # Crash/Boom
        "CRASH_300": "CRASH300N",
        "CRASH_500": "CRASH500",
        "CRASH_600": "CRASH600",
        "CRASH_900": "CRASH900",
        "CRASH_1000": "CRASH1000",
        "BOOM_300": "BOOM300N",
        "BOOM_500": "BOOM500",
        "BOOM_600": "BOOM600",
        "BOOM_900": "BOOM900",
        "BOOM_1000": "BOOM1000",
        # Step Indices
        "STEP_100": "stpRNG",
        # Jump Indices
        "JUMP_10": "JD10",
        "JUMP_25": "JD25",
        "JUMP_50": "JD50",
        "JUMP_75": "JD75",
        "JUMP_100": "JD100",
    }
    
    # Timeframe mappings (seconds)
    TIMEFRAMES = {
        "5s": 5,
        "15s": 15,
        "30s": 30,
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
    }
    
    def __init__(self):
        self.ws = None
        self.connected = False
        self.request_id = 0
        
    def _next_req_id(self) -> int:
        self.request_id += 1
        return self.request_id
    
    async def connect(self) -> bool:
        """Establish WebSocket connection to Deriv"""
        try:
            self.ws = await websockets.connect(
                self.DERIV_WS_URL,
                ping_interval=30,
                ping_timeout=10
            )
            self.connected = True
            logger.info("✅ Connected to Deriv WebSocket API")
            return True
        except Exception as e:
            logger.error(f"❌ Deriv connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("Disconnected from Deriv API")
    
    async def _send_request(self, request: Dict) -> Optional[Dict]:
        """Send request and wait for response"""
        if not self.connected:
            await self.connect()
        
        if not self.ws:
            return None
            
        try:
            req_id = self._next_req_id()
            request["req_id"] = req_id
            
            await self.ws.send(json.dumps(request))
            
            # Wait for response with matching req_id
            async for message in self.ws:
                response = json.loads(message)
                if response.get("req_id") == req_id:
                    if "error" in response:
                        logger.error(f"Deriv API error: {response['error']}")
                        return None
                    return response
                    
        except Exception as e:
            logger.error(f"Deriv request failed: {e}")
            self.connected = False
            return None
    
    async def get_active_symbols(self) -> List[Dict]:
        """Get list of available trading symbols"""
        request = {
            "active_symbols": "brief",
            "product_type": "basic"
        }
        response = await self._send_request(request)
        if response and "active_symbols" in response:
            return response["active_symbols"]
        return []
    
    async def get_ticks_history(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        count: int = 5000,
        style: str = "ticks"  # "ticks" or "candles"
    ) -> Optional[Dict]:
        """
        Fetch historical tick or candle data
        
        Args:
            symbol: Deriv symbol (e.g., "R_100", "CRASH500")
            start_time: Start datetime (default: 24h ago)
            end_time: End datetime (default: now)
            count: Number of data points (max 5000)
            style: "ticks" for raw ticks, "candles" for OHLC
        """
        # Map friendly name to Deriv symbol
        deriv_symbol = self.SYNTHETIC_SYMBOLS.get(symbol, symbol)
        
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(days=1)
        
        request = {
            "ticks_history": deriv_symbol,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "count": min(count, 5000),
            "style": style,
            "adjust_start_time": 1
        }
        
        if style == "candles":
            request["granularity"] = 60  # 1-minute candles by default
        
        response = await self._send_request(request)
        return response
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "M1",
        count: int = 1000,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLC candle data and return as DataFrame
        
        Args:
            symbol: Symbol name (friendly or Deriv format)
            timeframe: Timeframe string (5s, 15s, 30s, M1, M5, M15, M30, H1, H4)
            count: Number of candles
            start_time: Optional start time
            end_time: Optional end time
        """
        deriv_symbol = self.SYNTHETIC_SYMBOLS.get(symbol, symbol)
        granularity = self.TIMEFRAMES.get(timeframe, 60)
        
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            # Calculate start based on count and granularity
            start_time = end_time - timedelta(seconds=granularity * count * 1.5)
        
        request = {
            "ticks_history": deriv_symbol,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "count": min(count, 5000),
            "style": "candles",
            "granularity": granularity,
            "adjust_start_time": 1
        }
        
        response = await self._send_request(request)
        
        if not response or "candles" not in response:
            logger.warning(f"No candle data returned for {symbol}")
            return None
        
        candles = response["candles"]
        if not candles:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['epoch'], unit='s', utc=True)
        df = df.rename(columns={'epoch': 'time'})
        df = df[['timestamp', 'open', 'high', 'low', 'close']]
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Add volume placeholder (Deriv doesn't provide volume for synthetics)
        df['volume'] = 0
        
        return df
    
    async def get_ticks(
        self,
        symbol: str,
        count: int = 1000,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch raw tick data and return as DataFrame
        
        Args:
            symbol: Symbol name
            count: Number of ticks
            start_time: Optional start time
            end_time: Optional end time
        """
        deriv_symbol = self.SYNTHETIC_SYMBOLS.get(symbol, symbol)
        
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=24)
        
        request = {
            "ticks_history": deriv_symbol,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "count": min(count, 5000),
            "style": "ticks",
            "adjust_start_time": 1
        }
        
        response = await self._send_request(request)
        
        if not response or "history" not in response:
            return None
        
        history = response["history"]
        prices = history.get("prices", [])
        times = history.get("times", [])
        
        if not prices or not times:
            return None
        
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(times, unit='s', utc=True),
            'price': prices
        })
        
        return df
    
    def aggregate_ticks_to_candles(
        self,
        ticks_df: pd.DataFrame,
        timeframe: str = "5s"
    ) -> pd.DataFrame:
        """
        Aggregate tick data into OHLC candles
        
        Args:
            ticks_df: DataFrame with 'timestamp' and 'price' columns
            timeframe: Target timeframe (5s, 15s, 30s, M1, etc.)
        """
        if ticks_df is None or ticks_df.empty:
            return pd.DataFrame()
        
        seconds = self.TIMEFRAMES.get(timeframe, 60)
        rule = f"{seconds}s"
        
        ticks_df = ticks_df.set_index('timestamp')
        
        ohlc = ticks_df['price'].resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        ohlc['volume'] = ticks_df['price'].resample(rule).count()
        ohlc = ohlc.reset_index()
        
        return ohlc
    
    def get_available_symbols(self) -> List[str]:
        """Return list of available synthetic symbols"""
        return list(self.SYNTHETIC_SYMBOLS.keys())
    
    def get_available_timeframes(self) -> List[str]:
        """Return list of available timeframes"""
        return list(self.TIMEFRAMES.keys())


# Global instance
deriv_service = DerivDataService()


async def fetch_deriv_historical_data(
    symbol: str,
    timeframe: str = "M1",
    count: int = 1000
) -> Optional[pd.DataFrame]:
    """
    Convenience function to fetch Deriv historical data
    """
    try:
        await deriv_service.connect()
        
        if timeframe in ["5s", "15s", "30s"]:
            # For sub-minute timeframes, fetch ticks and aggregate
            ticks = await deriv_service.get_ticks(symbol, count=count * 100)
            if ticks is not None:
                candles = deriv_service.aggregate_ticks_to_candles(ticks, timeframe)
                return candles.tail(count)
        else:
            # For minute+ timeframes, fetch candles directly
            candles = await deriv_service.get_candles(symbol, timeframe, count)
            return candles
            
    except Exception as e:
        logger.error(f"Error fetching Deriv data: {e}")
        return None
    finally:
        await deriv_service.disconnect()
