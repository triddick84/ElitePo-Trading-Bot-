"""
Fast Real-Time Data Service
Optimized for speed and reliability in fetching market data for signal generation

PRIORITY ORDER:
1. OANDA API (real-time forex data) - PRIMARY
2. yfinance (delayed fallback)
3. Synthetic data (emergency fallback)

NOTE: OTC markets use the same underlying forex data since
Pocket Option OTC prices are based on real forex with broker adjustments.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
import logging
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Try to import OANDA service
try:
    from enhanced_oanda_service import EnhancedOandaService
    OANDA_AVAILABLE = True
except ImportError:
    OANDA_AVAILABLE = False
    logger.warning("⚠️ EnhancedOandaService not available")


class FastRealtimeDataService:
    """
    High-performance real-time data fetching service
    Features:
    - OANDA as PRIMARY data source (real-time forex)
    - Parallel data fetching
    - Intelligent caching
    - Multiple data sources with fallback
    - Sub-second response times
    
    Data Source Priority:
    1. OANDA API - Real-time, accurate forex data
    2. yfinance - Delayed data (15-20 min for forex)
    3. Synthetic - Emergency fallback only
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 5  # seconds
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.session = None
        
        # Initialize OANDA service
        self.oanda_service = None
        if OANDA_AVAILABLE:
            try:
                self.oanda_service = EnhancedOandaService()
                if self.oanda_service.is_configured:
                    logger.info("✅ OANDA service initialized - REAL-TIME DATA ENABLED")
                else:
                    logger.warning("⚠️ OANDA not configured - will use fallback sources")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OANDA: {e}")
        
        logger.info("⚡ Fast Realtime Data Service initialized")
        logger.info(f"   Primary: OANDA {'✅' if self.oanda_service and self.oanda_service.is_configured else '❌'}")
        logger.info("   Fallback: yfinance (delayed)")
    
    async def get_fast_market_data(
        self,
        symbol: str,
        timeframe: str = '1m',
        periods: int = 100,
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Fetch market data with sub-second response time
        
        Priority:
        1. OANDA (real-time) - if configured
        2. yfinance (delayed) - fallback
        3. Synthetic - emergency only
        
        Args:
            symbol: Trading symbol (e.g., EURUSD_OTC, EUR_USD)
            timeframe: Data timeframe
            periods: Number of data points
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Check cache first
            if use_cache:
                cached_data = self._get_cached_data(symbol, timeframe)
                if cached_data is not None:
                    logger.debug(f"📦 Cache hit: {symbol} {timeframe}")
                    return cached_data
            
            start_time = datetime.now()
            data = None
            source = "unknown"
            
            # PRIORITY 1: Try OANDA (real-time)
            if self.oanda_service and self.oanda_service.is_configured:
                data = await self._fetch_from_oanda(symbol, timeframe, periods)
                if data is not None and len(data) >= 20:
                    source = "OANDA (real-time)"
            
            # PRIORITY 2: Fallback to yfinance (delayed)
            if data is None or len(data) < 20:
                logger.warning(f"⚠️ OANDA unavailable for {symbol}, trying yfinance...")
                data = await self._fetch_from_yfinance(symbol, timeframe, periods)
                if data is not None and len(data) >= 20:
                    source = "yfinance (delayed ~15min)"
            
            # PRIORITY 3: Emergency synthetic data
            if data is None or len(data) < 20:
                logger.warning(f"⚠️ All sources failed for {symbol}, using synthetic")
                data = self._generate_synthetic_data(periods)
                source = "SYNTHETIC (emergency)"
            
            fetch_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"⚡ {symbol}: {len(data)} bars from {source} in {fetch_time:.2f}s")
            
            # Cache the data
            if data is not None:
                self._cache_data(symbol, timeframe, data)
            
            return data
                
        except Exception as e:
            logger.error(f"❌ Error fetching market data: {e}")
            return self._generate_synthetic_data(periods)
    
    async def _fetch_from_oanda(
        self,
        symbol: str,
        timeframe: str,
        periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch real-time data from OANDA API"""
        try:
            # Convert symbol to OANDA format
            oanda_instrument = self._convert_to_oanda_instrument(symbol)
            
            # Map timeframe to OANDA granularity
            granularity_map = {
                '1m': 'M1',
                '5m': 'M5',
                '15m': 'M15',
                '30m': 'M30',
                '1h': 'H1',
                '4h': 'H4',
                '1d': 'D'
            }
            granularity = granularity_map.get(timeframe, 'M1')
            
            # Fetch candles using OANDA service
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                self.executor,
                lambda: self.oanda_service.get_candles(
                    instrument=oanda_instrument,
                    granularity=granularity,
                    count=periods
                )
            )
            
            if data is not None and len(data) > 0:
                # Ensure standard column names
                if 'timestamp' not in data.columns and data.index.name == 'timestamp':
                    data = data.reset_index()
                
                required_cols = ['open', 'high', 'low', 'close']
                if all(col in data.columns for col in required_cols):
                    return data[required_cols + (['volume'] if 'volume' in data.columns else [])]
            
            return None
            
        except Exception as e:
            logger.error(f"OANDA fetch error for {symbol}: {e}")
            return None
    
    def _convert_to_oanda_instrument(self, symbol: str) -> str:
        """Convert Pocket Option symbol to OANDA instrument format"""
        # Remove _OTC suffix and any other market type indicators
        base_symbol = symbol.upper().replace('_OTC', '').replace('_REGULAR', '').replace('/', '')
        
        # Common forex pairs
        forex_pairs = {
            'EURUSD': 'EUR_USD',
            'GBPUSD': 'GBP_USD',
            'USDJPY': 'USD_JPY',
            'USDCHF': 'USD_CHF',
            'AUDUSD': 'AUD_USD',
            'USDCAD': 'USD_CAD',
            'NZDUSD': 'NZD_USD',
            'EURGBP': 'EUR_GBP',
            'EURJPY': 'EUR_JPY',
            'GBPJPY': 'GBP_JPY',
            'EURCHF': 'EUR_CHF',
            'AUDJPY': 'AUD_JPY',
            'EURAUD': 'EUR_AUD',
            'GBPAUD': 'GBP_AUD',
            'GBPCAD': 'GBP_CAD',
            'CADJPY': 'CAD_JPY',
            'CHFJPY': 'CHF_JPY',
            'AUDCAD': 'AUD_CAD',
            'AUDNZD': 'AUD_NZD',
            'NZDJPY': 'NZD_JPY',
        }
        
        if base_symbol in forex_pairs:
            return forex_pairs[base_symbol]
        
        # If not found, try to construct it
        if len(base_symbol) == 6:
            return f"{base_symbol[:3]}_{base_symbol[3:]}"
        
        return base_symbol
    
    async def _fetch_from_yfinance(
        self,
        symbol: str,
        timeframe: str,
        periods: int
    ) -> Optional[pd.DataFrame]:
        """Fetch data from yfinance with optimization"""
        try:
            import yfinance as yf
            
            # Convert Pocket Option symbols to Yahoo Finance format
            yahoo_symbol = self._convert_to_yahoo_symbol(symbol)
            
            # Map timeframe to yfinance interval
            interval_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '1d': '1d'
            }
            interval = interval_map.get(timeframe, '1m')
            
            # Calculate period
            days_map = {
                '1m': 1,
                '5m': 5,
                '15m': 7,
                '30m': 14,
                '1h': 30,
                '1d': 90
            }
            days = days_map.get(timeframe, 1)
            
            # Fetch data with timeout
            loop = asyncio.get_event_loop()
            ticker = yf.Ticker(yahoo_symbol)
            
            data = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor,
                    lambda: ticker.history(period=f'{days}d', interval=interval)
                ),
                timeout=3.0
            )
            
            if data is None or len(data) == 0:
                logger.warning(f"No data returned from yfinance for {yahoo_symbol}")
                return None
            
            # Standardize column names
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only required columns
            data = data[['open', 'high', 'low', 'close', 'volume']].tail(periods)
            
            return data
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ yfinance fetch timeout for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching from yfinance: {e}")
            return None
    
    def _convert_to_yahoo_symbol(self, symbol: str) -> str:
        """Convert Pocket Option symbol to Yahoo Finance format"""
        # Remove market type suffix
        base_symbol = symbol.split('_')[0]
        
        # Forex pairs
        if any(base_symbol.startswith(curr) for curr in ['EUR', 'GBP', 'USD', 'AUD', 'NZD', 'CAD', 'CHF', 'JPY']):
            if len(base_symbol) == 6:
                return f"{base_symbol[:3]}{base_symbol[3:]}=X"
        
        # Crypto
        if base_symbol.endswith('USD') and len(base_symbol) > 3:
            crypto = base_symbol[:-3]
            if crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'ADA', 'DOT', 'LINK']:
                return f"{crypto}-USD"
        
        # Stocks (use as-is)
        return base_symbol
    
    def _generate_synthetic_data(self, periods: int = 100) -> pd.DataFrame:
        """
        Generate synthetic realistic market data for testing
        Uses random walk with momentum and volatility clustering
        """
        try:
            np.random.seed()
            
            # Start price
            start_price = 100.0
            
            # Generate returns with momentum
            returns = np.random.normal(0.0001, 0.005, periods)
            
            # Add momentum
            momentum = np.random.choice([-1, 1]) * 0.0005
            returns += momentum * np.linspace(0, 1, periods)
            
            # Generate prices
            prices = start_price * np.exp(np.cumsum(returns))
            
            # Generate OHLC
            data = {
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': []
            }
            
            for i, close_price in enumerate(prices):
                open_price = prices[i-1] if i > 0 else start_price
                
                # Generate high/low
                volatility = abs(np.random.normal(0, 0.003))
                high = max(open_price, close_price) * (1 + volatility)
                low = min(open_price, close_price) * (1 - volatility)
                
                data['open'].append(open_price)
                data['high'].append(high)
                data['low'].append(low)
                data['close'].append(close_price)
                data['volume'].append(int(np.random.lognormal(10, 1)))
            
            df = pd.DataFrame(data)
            
            logger.info(f"🔮 Generated {len(df)} bars of synthetic data")
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating synthetic data: {e}")
            return None
    
    def _get_cached_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get data from cache if available and fresh"""
        cache_key = f"{symbol}_{timeframe}"
        
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            age = (datetime.now() - cached_item['timestamp']).total_seconds()
            
            if age < self.cache_ttl:
                return cached_item['data']
        
        return None
    
    def _cache_data(self, symbol: str, timeframe: str, data: pd.DataFrame):
        """Cache data with timestamp"""
        cache_key = f"{symbol}_{timeframe}"
        self.cache[cache_key] = {
            'data': data.copy(),
            'timestamp': datetime.now()
        }
        
        # Limit cache size
        if len(self.cache) > 100:
            # Remove oldest entries
            sorted_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k]['timestamp']
            )
            for old_key in sorted_keys[:20]:
                del self.cache[old_key]
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("🗑️ Data cache cleared")


# Global instance
fast_data_service = FastRealtimeDataService()
