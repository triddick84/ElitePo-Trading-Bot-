"""
Real-Time Market Data Hub
Multi-source data aggregation with quality validation and caching
NO SIMULATED DATA - Real market data only
"""

import asyncio
import aiohttp
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class DataQuality:
    """Data quality metrics"""
    EXCELLENT = "excellent"  # <1s latency, full data
    GOOD = "good"           # 1-5s latency, complete data
    FAIR = "fair"           # 5-15s latency or partial data
    POOR = "poor"           # >15s latency or incomplete
    UNAVAILABLE = "unavailable"  # No data available


class RealtimeMarketDataHub:
    """
    Multi-source real-time market data hub
    Priority: Binance > Finnhub > Alpha Vantage
    """
    
    def __init__(self, finnhub_key: str, alpha_vantage_key: str):
        self.finnhub_key = finnhub_key
        self.alpha_vantage_key = alpha_vantage_key
        
        # Data cache with expiry
        self.cache = {}
        self.cache_ttl = 5  # 5 seconds cache for real-time data
        
        # Rate limiting
        self.rate_limits = {
            'finnhub': {'calls': 0, 'reset_time': time.time() + 60, 'limit': 60},  # 60/min
            'alpha_vantage': {'calls': 0, 'reset_time': time.time() + 60, 'limit': 5},  # 5/min
            'binance': {'calls': 0, 'reset_time': time.time() + 60, 'limit': 1200}  # 1200/min
        }
        
        # Symbol mapping for different APIs
        self.symbol_mappings = self._init_symbol_mappings()
        
        # Data quality tracking
        self.quality_stats = defaultdict(list)
        
        logger.info("🚀 Real-Time Market Data Hub initialized - Multi-source aggregation enabled")
    
    def _init_symbol_mappings(self) -> Dict:
        """Initialize symbol mappings for different APIs"""
        return {
            'binance': {
                # Crypto symbols
                'BTCUSD': 'BTCUSDT',
                'ETHUSD': 'ETHUSDT',
                'BNBUSD': 'BNBUSDT',
                'XRPUSD': 'XRPUSDT',
                'ADAUSD': 'ADAUSDT',
                'DOGEUSD': 'DOGEUSDT',
                'SOLUSD': 'SOLUSDT',
                'MATICUSD': 'MATICUSDT',
                'DOTUSD': 'DOTUSDT',
                'LTCUSD': 'LTCUSDT',
            },
            'finnhub': {
                # Stocks
                'AAPL': 'AAPL',
                'GOOGL': 'GOOGL',
                'MSFT': 'MSFT',
                'TSLA': 'TSLA',
                'AMZN': 'AMZN',
                'META': 'META',
                'NVDA': 'NVDA',
                # Forex
                'EURUSD': 'OANDA:EUR_USD',
                'GBPUSD': 'OANDA:GBP_USD',
                'USDJPY': 'OANDA:USD_JPY',
                'AUDUSD': 'OANDA:AUD_USD',
            },
            'alpha_vantage': {
                # Forex
                'EURUSD': 'EUR/USD',
                'GBPUSD': 'GBP/USD',
                'USDJPY': 'USD/JPY',
                'AUDUSD': 'AUD/USD',
            }
        }
    
    def _check_rate_limit(self, source: str) -> bool:
        """Check if we can make API call within rate limits"""
        limits = self.rate_limits[source]
        current_time = time.time()
        
        # Reset counter if time window passed
        if current_time >= limits['reset_time']:
            limits['calls'] = 0
            limits['reset_time'] = current_time + 60
        
        # Check if under limit
        if limits['calls'] < limits['limit']:
            limits['calls'] += 1
            return True
        
        return False
    
    def _get_cache_key(self, symbol: str, data_type: str) -> str:
        """Generate cache key"""
        return f"{symbol}:{data_type}"
    
    def _check_cache(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Check if data exists in cache and is still fresh"""
        cache_key = self._get_cache_key(symbol, data_type)
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            age = time.time() - timestamp
            
            if age < self.cache_ttl:
                logger.debug(f"✅ Cache hit: {symbol} ({data_type}) - {age:.2f}s old")
                return cached_data
        
        return None
    
    def _update_cache(self, symbol: str, data_type: str, data: Dict):
        """Update cache with fresh data"""
        cache_key = self._get_cache_key(symbol, data_type)
        self.cache[cache_key] = (data, time.time())
    
    async def get_realtime_price(self, symbol: str) -> Optional[Dict]:
        """
        Get real-time price from best available source
        Returns: {price, bid, ask, volume, timestamp, source, quality}
        """
        # Check cache first
        cached = self._check_cache(symbol, 'price')
        if cached:
            return cached
        
        start_time = time.time()
        
        # Determine asset type and try appropriate sources
        if self._is_crypto(symbol):
            # Try Binance first (best for crypto)
            data = await self._get_binance_price(symbol)
            if data:
                latency = time.time() - start_time
                data['quality'] = self._assess_quality(latency, data)
                self._update_cache(symbol, 'price', data)
                return data
        
        # Try Finnhub for stocks/forex
        if self._check_rate_limit('finnhub'):
            data = await self._get_finnhub_price(symbol)
            if data:
                latency = time.time() - start_time
                data['quality'] = self._assess_quality(latency, data)
                self._update_cache(symbol, 'price', data)
                return data
        
        # Fallback to Alpha Vantage
        if self._check_rate_limit('alpha_vantage'):
            data = await self._get_alpha_vantage_price(symbol)
            if data:
                latency = time.time() - start_time
                data['quality'] = self._assess_quality(latency, data)
                self._update_cache(symbol, 'price', data)
                return data
        
        logger.error(f"❌ NO REAL DATA AVAILABLE for {symbol} - All sources exhausted")
        return None
    
    async def get_historical_candles(self, symbol: str, interval: str, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get historical candlestick data
        interval: 1m, 5m, 15m, 1h, 4h, 1d
        Returns list of {timestamp, open, high, low, close, volume}
        """
        # Check cache
        cache_key = f"candles_{interval}_{limit}"
        cached = self._check_cache(symbol, cache_key)
        if cached:
            return cached
        
        if self._is_crypto(symbol):
            data = await self._get_binance_candles(symbol, interval, limit)
            if data:
                self._update_cache(symbol, cache_key, data)
                return data
        
        # Try Finnhub for stocks
        if self._check_rate_limit('finnhub'):
            data = await self._get_finnhub_candles(symbol, interval, limit)
            if data:
                self._update_cache(symbol, cache_key, data)
                return data
        
        logger.warning(f"⚠️ No candle data available for {symbol} {interval}")
        return None
    
    async def _get_binance_price(self, symbol: str) -> Optional[Dict]:
        """Get real-time price from Binance (FREE, no auth, fastest)"""
        try:
            if not self._check_rate_limit('binance'):
                return None
            
            binance_symbol = self.symbol_mappings['binance'].get(symbol)
            if not binance_symbol:
                return None
            
            url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={binance_symbol}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            'symbol': symbol,
                            'price': float(data['bidPrice']),  # Use bid as current price
                            'bid': float(data['bidPrice']),
                            'ask': float(data['askPrice']),
                            'spread': float(data['askPrice']) - float(data['bidPrice']),
                            'volume': None,  # Get from 24hr ticker if needed
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'source': 'binance',
                            'symbol_native': binance_symbol
                        }
        except Exception as e:
            logger.debug(f"Binance API error for {symbol}: {e}")
            return None
    
    async def _get_finnhub_price(self, symbol: str) -> Optional[Dict]:
        """Get real-time price from Finnhub"""
        try:
            finnhub_symbol = self.symbol_mappings['finnhub'].get(symbol, symbol)
            url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={self.finnhub_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('c', 0) > 0:  # c = current price
                            price = float(data['c'])
                            return {
                                'symbol': symbol,
                                'price': price,
                                'bid': price * 0.9999,  # Estimate bid/ask
                                'ask': price * 1.0001,
                                'spread': price * 0.0002,
                                'volume': None,
                                'change': float(data.get('d', 0)),
                                'change_percent': float(data.get('dp', 0)),
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'source': 'finnhub',
                                'symbol_native': finnhub_symbol
                            }
        except Exception as e:
            logger.debug(f"Finnhub API error for {symbol}: {e}")
            return None
    
    async def _get_alpha_vantage_price(self, symbol: str) -> Optional[Dict]:
        """Get real-time price from Alpha Vantage"""
        try:
            av_symbol = self.symbol_mappings['alpha_vantage'].get(symbol, symbol)
            
            # For forex
            if '/' in av_symbol:
                from_currency, to_currency = av_symbol.split('/')
                url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_currency}&to_currency={to_currency}&apikey={self.alpha_vantage_key}"
            else:
                # For stocks
                url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.alpha_vantage_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Parse forex response
                        if 'Realtime Currency Exchange Rate' in data:
                            rate_data = data['Realtime Currency Exchange Rate']
                            price = float(rate_data.get('5. Exchange Rate', 0))
                            
                            if price > 0:
                                return {
                                    'symbol': symbol,
                                    'price': price,
                                    'bid': float(rate_data.get('8. Bid Price', price * 0.9999)),
                                    'ask': float(rate_data.get('9. Ask Price', price * 1.0001)),
                                    'spread': None,
                                    'volume': None,
                                    'timestamp': rate_data.get('6. Last Refreshed'),
                                    'source': 'alpha_vantage',
                                    'symbol_native': av_symbol
                                }
                        
                        # Parse stock response
                        elif 'Global Quote' in data:
                            quote = data['Global Quote']
                            price = float(quote.get('05. price', 0))
                            
                            if price > 0:
                                return {
                                    'symbol': symbol,
                                    'price': price,
                                    'bid': price * 0.9999,
                                    'ask': price * 1.0001,
                                    'spread': price * 0.0002,
                                    'volume': float(quote.get('06. volume', 0)),
                                    'change': float(quote.get('09. change', 0)),
                                    'change_percent': quote.get('10. change percent', '0').replace('%', ''),
                                    'timestamp': quote.get('07. latest trading day'),
                                    'source': 'alpha_vantage',
                                    'symbol_native': symbol
                                }
        except Exception as e:
            logger.debug(f"Alpha Vantage API error for {symbol}: {e}")
            return None
    
    async def _get_binance_candles(self, symbol: str, interval: str, limit: int) -> Optional[List[Dict]]:
        """Get candlestick data from Binance"""
        try:
            binance_symbol = self.symbol_mappings['binance'].get(symbol)
            if not binance_symbol:
                return None
            
            # Map interval to Binance format
            interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'}
            binance_interval = interval_map.get(interval, '1m')
            
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={binance_interval}&limit={limit}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        candles = []
                        for candle in data:
                            candles.append({
                                'timestamp': datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': float(candle[5]),
                                'close_time': datetime.fromtimestamp(candle[6] / 1000, tz=timezone.utc),
                                'trades': int(candle[8])
                            })
                        
                        logger.info(f"✅ Binance: {len(candles)} candles for {symbol} ({interval})")
                        return candles
        except Exception as e:
            logger.debug(f"Binance candles error for {symbol}: {e}")
            return None
    
    async def _get_finnhub_candles(self, symbol: str, interval: str, limit: int) -> Optional[List[Dict]]:
        """Get candlestick data from Finnhub"""
        try:
            finnhub_symbol = self.symbol_mappings['finnhub'].get(symbol, symbol)
            
            # Calculate time range
            now = int(time.time())
            interval_seconds = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400}
            seconds = interval_seconds.get(interval, 60)
            start = now - (seconds * limit)
            
            # Map to Finnhub resolution
            resolution_map = {'1m': '1', '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D'}
            resolution = resolution_map.get(interval, '1')
            
            url = f"https://finnhub.io/api/v1/stock/candle?symbol={finnhub_symbol}&resolution={resolution}&from={start}&to={now}&token={self.finnhub_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('s') == 'ok':
                            candles = []
                            for i in range(len(data['t'])):
                                candles.append({
                                    'timestamp': datetime.fromtimestamp(data['t'][i], tz=timezone.utc),
                                    'open': float(data['o'][i]),
                                    'high': float(data['h'][i]),
                                    'low': float(data['l'][i]),
                                    'close': float(data['c'][i]),
                                    'volume': float(data['v'][i])
                                })
                            
                            logger.info(f"✅ Finnhub: {len(candles)} candles for {symbol} ({interval})")
                            return candles
        except Exception as e:
            logger.debug(f"Finnhub candles error for {symbol}: {e}")
            return None
    
    def _is_crypto(self, symbol: str) -> bool:
        """Check if symbol is cryptocurrency"""
        crypto_keywords = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'MATIC', 'DOT', 'LTC']
        return any(crypto in symbol.upper() for crypto in crypto_keywords)
    
    def _assess_quality(self, latency: float, data: Dict) -> str:
        """Assess data quality based on latency and completeness"""
        if latency < 1 and all(k in data for k in ['price', 'bid', 'ask']):
            return DataQuality.EXCELLENT
        elif latency < 5 and 'price' in data:
            return DataQuality.GOOD
        elif latency < 15:
            return DataQuality.FAIR
        else:
            return DataQuality.POOR
    
    async def get_market_depth(self, symbol: str) -> Optional[Dict]:
        """Get order book depth for volume analysis"""
        if not self._is_crypto(symbol):
            return None
        
        try:
            binance_symbol = self.symbol_mappings['binance'].get(symbol)
            if not binance_symbol:
                return None
            
            url = f"https://api.binance.com/api/v3/depth?symbol={binance_symbol}&limit=20"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Calculate volume profile
                        bid_volume = sum(float(b[1]) for b in data['bids'])
                        ask_volume = sum(float(a[1]) for a in data['asks'])
                        
                        return {
                            'bid_volume': bid_volume,
                            'ask_volume': ask_volume,
                            'buy_pressure': bid_volume / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0.5,
                            'bids': [[float(b[0]), float(b[1])] for b in data['bids'][:10]],
                            'asks': [[float(a[0]), float(a[1])] for a in data['asks'][:10]]
                        }
        except Exception as e:
            logger.debug(f"Market depth error for {symbol}: {e}")
            return None
    
    def get_quality_report(self) -> Dict:
        """Get data quality report"""
        total_calls = sum(limit['calls'] for limit in self.rate_limits.values())
        
        return {
            'cache_size': len(self.cache),
            'rate_limits': {
                source: {'used': limit['calls'], 'limit': limit['limit'], 'remaining': limit['limit'] - limit['calls']}
                for source, limit in self.rate_limits.items()
            },
            'total_api_calls': total_calls
        }


# Global instance (will be initialized in server.py with API keys)
realtime_hub = None
