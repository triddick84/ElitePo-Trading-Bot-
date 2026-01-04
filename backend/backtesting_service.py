"""
Comprehensive Backtesting Service
=================================

Features:
- Historical data fetching from multiple providers (Finnhub, Alpha Vantage, CryptoCompare)
- Intelligent fallback system: Finnhub -> Alpha Vantage -> Synthetic Data
- Strategy backtesting across multiple timeframes and assets
- Live data testing mode
- Performance analytics and comparison
- Up to 90 days of historical data

Author: GPT Signal Bot
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import aiohttp
import json
import os
from uuid import uuid4

logger = logging.getLogger(__name__)

# API Keys from environment
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '')
ALPHAVANTAGE_API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')

# Finnhub forex symbol mappings (OANDA format)
FINNHUB_FOREX_SYMBOLS = {
    'EURUSD': 'OANDA:EUR_USD',
    'GBPUSD': 'OANDA:GBP_USD',
    'USDJPY': 'OANDA:USD_JPY',
    'USDCHF': 'OANDA:USD_CHF',
    'AUDUSD': 'OANDA:AUD_USD',
    'USDCAD': 'OANDA:USD_CAD',
    'NZDUSD': 'OANDA:NZD_USD',
    'EURGBP': 'OANDA:EUR_GBP',
    'EURJPY': 'OANDA:EUR_JPY',
    'GBPJPY': 'OANDA:GBP_JPY',
    'EUR_USD': 'OANDA:EUR_USD',
    'GBP_USD': 'OANDA:GBP_USD',
    'USD_JPY': 'OANDA:USD_JPY',
    'AUD_USD': 'OANDA:AUD_USD',
}

# Alpha Vantage forex symbol mappings (FROM_SYMBOL, TO_SYMBOL)
ALPHAVANTAGE_FOREX_SYMBOLS = {
    'EURUSD': ('EUR', 'USD'),
    'GBPUSD': ('GBP', 'USD'),
    'USDJPY': ('USD', 'JPY'),
    'USDCHF': ('USD', 'CHF'),
    'AUDUSD': ('AUD', 'USD'),
    'USDCAD': ('USD', 'CAD'),
    'NZDUSD': ('NZD', 'USD'),
    'EURGBP': ('EUR', 'GBP'),
    'EURJPY': ('EUR', 'JPY'),
    'GBPJPY': ('GBP', 'JPY'),
    'EUR_USD': ('EUR', 'USD'),
    'GBP_USD': ('GBP', 'USD'),
    'USD_JPY': ('USD', 'JPY'),
    'AUD_USD': ('AUD', 'USD'),
}

# CryptoCompare symbols
CRYPTO_SYMBOLS = ['BTC', 'ETH', 'ADA', 'BNB', 'XRP', 'SOL', 'DOGE', 'DOT', 'MATIC', 'LTC']

# Stock symbols (direct Yahoo Finance)
STOCK_SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA', 'AMD', 'NFLX', 'DIS']


class AssetType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCK = "stock"
    COMMODITY = "commodity"


class TimeFrame(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


@dataclass
class BacktestConfig:
    """Configuration for a backtest run"""
    id: str = field(default_factory=lambda: str(uuid4()))
    strategies: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    days: int = 30
    initial_balance: float = 1000.0
    trade_amount: float = 10.0
    payout_rate: float = 0.85  # 85% payout
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TradeResult:
    """Result of a single simulated trade"""
    timestamp: str
    asset: str
    direction: str  # 'call' or 'put'
    entry_price: float
    exit_price: float
    result: str  # 'win' or 'loss'
    profit: float
    strategy: str
    timeframe: str
    confidence: float


@dataclass
class BacktestResult:
    """Result of a complete backtest"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str = ""
    strategy: str = ""
    asset: str = ""
    timeframe: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    initial_balance: float = 1000.0
    final_balance: float = 1000.0
    roi: float = 0.0
    start_date: str = ""
    end_date: str = ""
    data_source: str = "unknown"  # Track which data provider was used (finnhub, alphavantage, cryptocompare, synthetic)
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HistoricalDataFetcher:
    """Fetches historical market data from multiple providers with intelligent fallback"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        self.data_source_used = {}  # Track which source was used for each request
    
    async def fetch_finnhub_forex_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """Fetch historical forex data from Finnhub API (Primary provider)"""
        if not FINNHUB_API_KEY:
            logger.warning("Finnhub API key not configured")
            return None
            
        try:
            # Map symbol to Finnhub OANDA format
            symbol_upper = symbol.upper().replace('_', '')
            finnhub_symbol = FINNHUB_FOREX_SYMBOLS.get(symbol_upper) or FINNHUB_FOREX_SYMBOLS.get(symbol.upper())
            
            if not finnhub_symbol:
                # Try to construct the symbol
                if len(symbol_upper) == 6:
                    base = symbol_upper[:3]
                    quote = symbol_upper[3:]
                    finnhub_symbol = f"OANDA:{base}_{quote}"
                else:
                    logger.warning(f"Cannot map symbol {symbol} to Finnhub format")
                    return None
            
            # Map interval to Finnhub resolution
            resolution_map = {
                '1m': '1', '5m': '5', '15m': '15', '30m': '30',
                '1h': '60', '4h': '60', '1d': 'D'
            }
            resolution = resolution_map.get(interval, '60')
            
            # Calculate time range
            end_time = int(datetime.now().timestamp())
            start_time = int((datetime.now() - timedelta(days=days)).timestamp())
            
            url = "https://finnhub.io/api/v1/forex/candle"
            params = {
                'symbol': finnhub_symbol,
                'resolution': resolution,
                'from': start_time,
                'to': end_time,
                'token': FINNHUB_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Finnhub API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    # Check for valid response
                    if data.get('s') != 'ok' or not data.get('c'):
                        logger.warning(f"Finnhub returned no data for {finnhub_symbol}: {data.get('s', 'unknown')}")
                        return None
                    
                    # Convert to DataFrame
                    df = pd.DataFrame({
                        'open': data['o'],
                        'high': data['h'],
                        'low': data['l'],
                        'close': data['c'],
                        'volume': data.get('v', [0] * len(data['c']))
                    })
                    
                    # Set timestamp index
                    df.index = pd.to_datetime(data['t'], unit='s')
                    df = df.sort_index()
                    
                    logger.info(f"✅ Finnhub: Fetched {len(df)} candles for {finnhub_symbol}")
                    return df
                    
        except asyncio.TimeoutError:
            logger.error(f"Finnhub request timeout for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Finnhub error for {symbol}: {e}")
            return None
    
    async def fetch_finnhub_stock_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """Fetch historical stock data from Finnhub API"""
        if not FINNHUB_API_KEY:
            return None
            
        try:
            # Map interval to resolution
            resolution_map = {
                '1m': '1', '5m': '5', '15m': '15', '30m': '30',
                '1h': '60', '4h': '60', '1d': 'D'
            }
            resolution = resolution_map.get(interval, '60')
            
            end_time = int(datetime.now().timestamp())
            start_time = int((datetime.now() - timedelta(days=days)).timestamp())
            
            url = "https://finnhub.io/api/v1/stock/candle"
            params = {
                'symbol': symbol.upper(),
                'resolution': resolution,
                'from': start_time,
                'to': end_time,
                'token': FINNHUB_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if data.get('s') != 'ok' or not data.get('c'):
                        return None
                    
                    df = pd.DataFrame({
                        'open': data['o'],
                        'high': data['h'],
                        'low': data['l'],
                        'close': data['c'],
                        'volume': data.get('v', [0] * len(data['c']))
                    })
                    
                    df.index = pd.to_datetime(data['t'], unit='s')
                    df = df.sort_index()
                    
                    logger.info(f"✅ Finnhub: Fetched {len(df)} stock candles for {symbol}")
                    return df
                    
        except Exception as e:
            logger.error(f"Finnhub stock error for {symbol}: {e}")
            return None
    
    async def fetch_alphavantage_forex_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """
        Fetch historical forex data from Alpha Vantage API (Secondary provider).
        Note: Free tier only supports DAILY data. Intraday requires premium.
        """
        if not ALPHAVANTAGE_API_KEY:
            logger.warning("Alpha Vantage API key not configured")
            return None
            
        try:
            # Map symbol to Alpha Vantage format
            symbol_upper = symbol.upper().replace('_', '')
            av_pair = ALPHAVANTAGE_FOREX_SYMBOLS.get(symbol_upper) or ALPHAVANTAGE_FOREX_SYMBOLS.get(symbol.upper())
            
            if not av_pair:
                # Try to construct the pair
                if len(symbol_upper) == 6:
                    av_pair = (symbol_upper[:3], symbol_upper[3:])
                else:
                    logger.warning(f"Cannot map symbol {symbol} to Alpha Vantage format")
                    return None
            
            from_symbol, to_symbol = av_pair
            
            # Alpha Vantage free tier only supports FX_DAILY for forex
            # For intraday intervals, we fetch daily data and can interpolate later if needed
            function = 'FX_DAILY'
            
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': function,
                'from_symbol': from_symbol,
                'to_symbol': to_symbol,
                'apikey': ALPHAVANTAGE_API_KEY,
                'outputsize': 'full' if days > 30 else 'compact',
                'datatype': 'json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Alpha Vantage API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    # Check for error messages
                    if 'Error Message' in data:
                        logger.error(f"Alpha Vantage error: {data['Error Message']}")
                        return None
                    
                    if 'Note' in data:
                        logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                        return None
                    
                    if 'Information' in data and 'premium' in data['Information'].lower():
                        logger.warning(f"Alpha Vantage premium required: {data['Information'][:100]}")
                        return None
                    
                    # Find the time series key
                    time_series_key = None
                    for key in data:
                        if 'Time Series' in key:
                            time_series_key = key
                            break
                    
                    if not time_series_key or not data.get(time_series_key):
                        logger.warning(f"Alpha Vantage returned no data for {symbol}")
                        return None
                    
                    # Convert to DataFrame
                    time_series = data[time_series_key]
                    df = pd.DataFrame.from_dict(time_series, orient='index')
                    
                    # Standardize column names
                    column_map = {}
                    for col in df.columns:
                        if 'open' in col.lower():
                            column_map[col] = 'open'
                        elif 'high' in col.lower():
                            column_map[col] = 'high'
                        elif 'low' in col.lower():
                            column_map[col] = 'low'
                        elif 'close' in col.lower():
                            column_map[col] = 'close'
                    
                    df = df.rename(columns=column_map)
                    df.index = pd.to_datetime(df.index)
                    df = df.sort_index()
                    
                    # Convert to float
                    for col in ['open', 'high', 'low', 'close']:
                        if col in df.columns:
                            df[col] = df[col].astype(float)
                    
                    # Add volume column if missing
                    if 'volume' not in df.columns:
                        df['volume'] = 0.0
                    
                    # Filter by days
                    cutoff_date = datetime.now() - timedelta(days=days)
                    df = df[df.index >= cutoff_date]
                    
                    # For intraday intervals, expand daily data to simulate intraday
                    if interval in ['1m', '5m', '15m', '30m', '1h', '4h'] and len(df) > 0:
                        df = self._expand_daily_to_intraday(df, interval)
                    
                    logger.info(f"✅ Alpha Vantage: Fetched {len(df)} candles for {from_symbol}/{to_symbol}")
                    return df
                    
        except asyncio.TimeoutError:
            logger.error(f"Alpha Vantage request timeout for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Alpha Vantage error for {symbol}: {e}")
            return None
    
    def _expand_daily_to_intraday(self, daily_df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """
        Expand daily OHLC data to intraday candles with realistic price movement.
        This creates more data points for backtesting from daily data.
        """
        interval_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240
        }
        minutes = interval_minutes.get(interval, 60)
        
        # Trading hours per day (assume 24h for forex)
        candles_per_day = 1440 // minutes
        
        expanded_data = []
        
        for idx, row in daily_df.iterrows():
            day_open = row['open']
            day_high = row['high']
            day_low = row['low']
            day_close = row['close']
            day_volume = row.get('volume', 0)
            
            # Generate intraday prices using a random walk from open to close
            # while respecting the high/low range
            np.random.seed(int(idx.timestamp()) % 2**31)
            
            # Create a path from open to close
            price_range = day_high - day_low
            
            for i in range(candles_per_day):
                # Time for this candle
                candle_time = idx + timedelta(minutes=i * minutes)
                
                # Progress through the day (0 to 1)
                progress = (i + 1) / candles_per_day
                
                # Interpolate from open to close with some noise
                base_price = day_open + (day_close - day_open) * progress
                noise = np.random.normal(0, price_range * 0.05)
                
                # Generate OHLC for this candle
                candle_open = np.clip(base_price + noise, day_low, day_high)
                candle_close = np.clip(base_price + np.random.normal(0, price_range * 0.03), day_low, day_high)
                candle_high = min(day_high, max(candle_open, candle_close) * (1 + np.random.uniform(0, 0.001)))
                candle_low = max(day_low, min(candle_open, candle_close) * (1 - np.random.uniform(0, 0.001)))
                candle_volume = day_volume / candles_per_day if day_volume > 0 else 0
                
                expanded_data.append({
                    'open': candle_open,
                    'high': candle_high,
                    'low': candle_low,
                    'close': candle_close,
                    'volume': candle_volume,
                    'timestamp': candle_time
                })
        
        if not expanded_data:
            return daily_df
        
        expanded_df = pd.DataFrame(expanded_data)
        expanded_df = expanded_df.set_index('timestamp')
        expanded_df = expanded_df.sort_index()
        
        return expanded_df
    
    async def fetch_alphavantage_stock_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data from Alpha Vantage API.
        Note: Free tier only supports DAILY data. Intraday requires premium.
        """
        if not ALPHAVANTAGE_API_KEY:
            return None
            
        try:
            # Alpha Vantage free tier only supports TIME_SERIES_DAILY for stocks
            function = 'TIME_SERIES_DAILY'
            
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': function,
                'symbol': symbol.upper(),
                'apikey': ALPHAVANTAGE_API_KEY,
                'outputsize': 'full' if days > 30 else 'compact',
                'datatype': 'json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if 'Error Message' in data or 'Note' in data:
                        return None
                    
                    if 'Information' in data and 'premium' in data['Information'].lower():
                        logger.warning(f"Alpha Vantage premium required for {symbol}")
                        return None
                    
                    # Find time series key
                    time_series_key = None
                    for key in data:
                        if 'Time Series' in key:
                            time_series_key = key
                            break
                    
                    if not time_series_key:
                        return None
                    
                    df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
                    
                    # Standardize columns
                    column_map = {}
                    for col in df.columns:
                        col_lower = col.lower()
                        if 'open' in col_lower:
                            column_map[col] = 'open'
                        elif 'high' in col_lower:
                            column_map[col] = 'high'
                        elif 'low' in col_lower:
                            column_map[col] = 'low'
                        elif 'close' in col_lower:
                            column_map[col] = 'close'
                        elif 'volume' in col_lower:
                            column_map[col] = 'volume'
                    
                    df = df.rename(columns=column_map)
                    df.index = pd.to_datetime(df.index)
                    df = df.sort_index()
                    
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        if col in df.columns:
                            df[col] = df[col].astype(float)
                    
                    cutoff_date = datetime.now() - timedelta(days=days)
                    df = df[df.index >= cutoff_date]
                    
                    # For intraday intervals, expand daily data
                    if interval in ['1m', '5m', '15m', '30m', '1h', '4h'] and len(df) > 0:
                        df = self._expand_daily_to_intraday(df, interval)
                    
                    logger.info(f"✅ Alpha Vantage: Fetched {len(df)} stock candles for {symbol}")
                    return df
                    
        except Exception as e:
            logger.error(f"Alpha Vantage stock error for {symbol}: {e}")
            return None
    
    def _generate_synthetic_data(self, symbol: str, days: int, interval: str) -> pd.DataFrame:
        """Generate synthetic market data for backtesting when live data unavailable"""
        # Determine candle count based on interval
        interval_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440
        }
        minutes = interval_minutes.get(interval, 60)
        candles_per_day = 1440 // minutes
        total_candles = days * candles_per_day
        
        # Base prices by asset type
        base_prices = {
            'EURUSD': 1.05, 'EUR_USD': 1.05, 'GBPUSD': 1.25, 'GBP_USD': 1.25,
            'USDJPY': 150.0, 'USD_JPY': 150.0, 'AUDUSD': 0.65, 'AUD_USD': 0.65,
            'BTC': 45000, 'ETH': 2500, 'AAPL': 190, 'GOOGL': 140, 'MSFT': 380
        }
        
        # Get base price
        symbol_upper = symbol.upper().replace('USDT', '').replace('=X', '')
        base_price = base_prices.get(symbol_upper, 100)
        
        # Generate random walk with mean reversion
        np.random.seed(hash(symbol) % 2**32)
        
        returns = np.random.normal(0, 0.0005, total_candles)  # Small random returns
        # Add some trend and mean reversion
        trend = np.sin(np.linspace(0, 4 * np.pi, total_candles)) * 0.002
        returns = returns + trend * 0.1
        
        prices = [base_price]
        for r in returns:
            new_price = prices[-1] * (1 + r)
            prices.append(new_price)
        prices = np.array(prices[1:])
        
        # Generate OHLC from prices
        high_diff = np.abs(np.random.normal(0.001, 0.0005, total_candles))
        low_diff = np.abs(np.random.normal(0.001, 0.0005, total_candles))
        
        opens = np.roll(prices, 1)
        opens[0] = prices[0]
        highs = np.maximum(prices, opens) * (1 + high_diff)
        lows = np.minimum(prices, opens) * (1 - low_diff)
        closes = prices
        volumes = np.random.randint(1000, 100000, total_candles).astype(float)
        
        # Create datetime index
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        date_range = pd.date_range(start=start_time, periods=total_candles, freq=f'{minutes}min')
        
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=date_range)
        
        logger.info(f"Generated {len(df)} synthetic candles for {symbol}")
        return df
    
    async def fetch_crypto_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """Fetch historical crypto data from CryptoCompare"""
        try:
            # Extract base symbol
            base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('_', '').upper()
            
            # Map interval to CryptoCompare format
            if interval in ['1m', '5m', '15m', '30m']:
                endpoint = "histominute"
                limit = min(days * 24 * 60, 2000)  # CryptoCompare limit
                aggregate = {'1m': 1, '5m': 5, '15m': 15, '30m': 30}.get(interval, 1)
            elif interval in ['1h', '4h']:
                endpoint = "histohour"
                limit = min(days * 24, 2000)
                aggregate = {'1h': 1, '4h': 4}.get(interval, 1)
            else:
                endpoint = "histoday"
                limit = min(days, 2000)
                aggregate = 1
            
            url = f"https://min-api.cryptocompare.com/data/v2/{endpoint}"
            params = {
                "fsym": base_symbol,
                "tsym": "USD",
                "limit": limit,
                "aggregate": aggregate
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"CryptoCompare API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if data.get("Response") == "Error":
                        logger.error(f"CryptoCompare error: {data.get('Message')}")
                        return None
                    
                    candles = data.get("Data", {}).get("Data", [])
                    
                    if not candles:
                        return None
                    
                    df = pd.DataFrame(candles)
                    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
                    df = df.set_index('timestamp')
                    df = df.rename(columns={
                        'open': 'open', 'high': 'high', 'low': 'low',
                        'close': 'close', 'volumefrom': 'volume'
                    })
                    df = df[['open', 'high', 'low', 'close', 'volume']].copy()
                    
                    logger.info(f"✅ CryptoCompare: Fetched {len(df)} candles for {base_symbol}")
                    return df
                    
        except Exception as e:
            logger.error(f"Error fetching crypto data for {symbol}: {e}")
            return None
    
    async def fetch_historical_data(self, symbol: str, asset_type: str, days: int = 30, interval: str = "1h") -> Tuple[Optional[pd.DataFrame], str]:
        """
        Fetch historical data with multi-provider fallback system.
        
        Fallback order:
        1. Finnhub (Primary - 60 calls/min)
        2. Alpha Vantage (Secondary - 5 calls/min)
        3. CryptoCompare (For crypto only)
        4. Synthetic Data (Last resort)
        
        Returns: (DataFrame, data_source_name)
        """
        cache_key = f"{symbol}_{asset_type}_{days}_{interval}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time, cached_source = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                logger.info(f"📦 Cache hit for {symbol}: {cached_source}")
                return cached_data, cached_source
        
        df = None
        data_source = "synthetic"
        is_crypto = asset_type == AssetType.CRYPTO or symbol.upper() in CRYPTO_SYMBOLS or 'USDT' in symbol.upper()
        is_stock = asset_type == AssetType.STOCK or symbol.upper() in STOCK_SYMBOLS
        
        if is_crypto:
            # Try CryptoCompare first for crypto
            logger.info(f"🔄 Fetching crypto data for {symbol}...")
            df = await self.fetch_crypto_data(symbol, days, interval)
            if df is not None and len(df) > 0:
                data_source = "cryptocompare"
        else:
            # For forex and stocks, use multi-provider fallback
            
            # 1. Try Finnhub first (higher rate limit)
            logger.info(f"🔄 Trying Finnhub for {symbol}...")
            if is_stock:
                df = await self.fetch_finnhub_stock_data(symbol, days, interval)
            else:
                df = await self.fetch_finnhub_forex_data(symbol, days, interval)
            
            if df is not None and len(df) > 0:
                data_source = "finnhub"
            else:
                # 2. Try Alpha Vantage as fallback
                logger.info(f"🔄 Finnhub failed, trying Alpha Vantage for {symbol}...")
                if is_stock:
                    df = await self.fetch_alphavantage_stock_data(symbol, days, interval)
                else:
                    df = await self.fetch_alphavantage_forex_data(symbol, days, interval)
                
                if df is not None and len(df) > 0:
                    data_source = "alphavantage"
        
        # 3. Last resort: Generate synthetic data
        if df is None or len(df) == 0:
            logger.warning(f"⚠️ All data providers failed for {symbol}, using synthetic data")
            df = self._generate_synthetic_data(symbol, days, interval)
            data_source = "synthetic"
        
        # Cache the result
        if df is not None:
            self.cache[cache_key] = (df, datetime.now(), data_source)
            self.data_source_used[cache_key] = data_source
        
        logger.info(f"📊 Data source for {symbol}: {data_source.upper()} ({len(df) if df is not None else 0} candles)")
        return df, data_source


class StrategyEngine:
    """Executes trading strategies on historical data"""
    
    def __init__(self):
        self.strategies = {
            'rsi_reversal': self._rsi_reversal_strategy,
            'ema_crossover': self._ema_crossover_strategy,
            'macd_crossover': self._macd_crossover_strategy,
            'bollinger_bounce': self._bollinger_bounce_strategy,
            'stochastic_rsi': self._stochastic_rsi_strategy,
            'supertrend': self._supertrend_strategy,
            'support_resistance': self._support_resistance_strategy,
            'hybrid': self._hybrid_strategy,
            'enhanced_rsi_bb_volume': self._enhanced_rsi_bb_volume_strategy,
            'enhanced_divergence': self._enhanced_divergence_strategy,  # NEW: RSI/MACD Divergence
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate EMA"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def _calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate SMA"""
        return prices.rolling(window=period).mean()
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD with customizable periods"""
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = self._calculate_sma(prices, period)
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic oscillator with customizable periods"""
        low_min = low.rolling(window=k_period).min()
        high_max = high.rolling(window=k_period).max()
        k = 100 * (close - low_min) / (high_max - low_min)
        d = k.rolling(window=d_period).mean()
        return k, d
    
    def _rsi_reversal_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """RSI Reversal Strategy"""
        signals = []
        rsi = self._calculate_rsi(df['close'], 14)
        
        for i in range(1, len(df)):
            if pd.isna(rsi.iloc[i]) or pd.isna(rsi.iloc[i-1]):
                continue
            
            # Oversold reversal (CALL)
            if rsi.iloc[i-1] < 30 and rsi.iloc[i] > 30:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': min(95, 70 + (30 - rsi.iloc[i-1])),
                    'entry_price': df['close'].iloc[i]
                })
            # Overbought reversal (PUT)
            elif rsi.iloc[i-1] > 70 and rsi.iloc[i] < 70:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': min(95, 70 + (rsi.iloc[i-1] - 70)),
                    'entry_price': df['close'].iloc[i]
                })
        
        return signals
    
    def _ema_crossover_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """EMA Crossover Strategy (7/21)"""
        signals = []
        ema_fast = self._calculate_ema(df['close'], 7)
        ema_slow = self._calculate_ema(df['close'], 21)
        
        for i in range(1, len(df)):
            if pd.isna(ema_fast.iloc[i]) or pd.isna(ema_slow.iloc[i]):
                continue
            
            # Golden cross (CALL)
            if ema_fast.iloc[i-1] <= ema_slow.iloc[i-1] and ema_fast.iloc[i] > ema_slow.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 75,
                    'entry_price': df['close'].iloc[i]
                })
            # Death cross (PUT)
            elif ema_fast.iloc[i-1] >= ema_slow.iloc[i-1] and ema_fast.iloc[i] < ema_slow.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 75,
                    'entry_price': df['close'].iloc[i]
                })
        
        return signals
    
    def _macd_crossover_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """MACD Crossover Strategy"""
        signals = []
        macd_line, signal_line, _ = self._calculate_macd(df['close'])
        
        for i in range(1, len(df)):
            if pd.isna(macd_line.iloc[i]) or pd.isna(signal_line.iloc[i]):
                continue
            
            # Bullish crossover
            if macd_line.iloc[i-1] <= signal_line.iloc[i-1] and macd_line.iloc[i] > signal_line.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 72,
                    'entry_price': df['close'].iloc[i]
                })
            # Bearish crossover
            elif macd_line.iloc[i-1] >= signal_line.iloc[i-1] and macd_line.iloc[i] < signal_line.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 72,
                    'entry_price': df['close'].iloc[i]
                })
        
        return signals
    
    def _bollinger_bounce_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """Bollinger Bands Bounce Strategy"""
        signals = []
        upper, middle, lower = self._calculate_bollinger_bands(df['close'])
        
        for i in range(1, len(df)):
            if pd.isna(upper.iloc[i]) or pd.isna(lower.iloc[i]):
                continue
            
            close = df['close'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            
            # Bounce from lower band (CALL)
            if prev_close <= lower.iloc[i-1] and close > lower.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 73,
                    'entry_price': close
                })
            # Bounce from upper band (PUT)
            elif prev_close >= upper.iloc[i-1] and close < upper.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 73,
                    'entry_price': close
                })
        
        return signals
    
    def _stochastic_rsi_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """Stochastic RSI Strategy"""
        signals = []
        k, d = self._calculate_stochastic(df)
        
        for i in range(1, len(df)):
            if pd.isna(k.iloc[i]) or pd.isna(d.iloc[i]):
                continue
            
            # Oversold crossover (CALL)
            if k.iloc[i-1] < 20 and k.iloc[i-1] <= d.iloc[i-1] and k.iloc[i] > d.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 74,
                    'entry_price': df['close'].iloc[i]
                })
            # Overbought crossover (PUT)
            elif k.iloc[i-1] > 80 and k.iloc[i-1] >= d.iloc[i-1] and k.iloc[i] < d.iloc[i]:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 74,
                    'entry_price': df['close'].iloc[i]
                })
        
        return signals
    
    def _supertrend_strategy(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> List[Dict]:
        """SuperTrend Strategy"""
        signals = []
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Calculate SuperTrend
        hl2 = (df['high'] + df['low']) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(period, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = lower_band.iloc[i]
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
                supertrend.iloc[i] = upper_band.iloc[i]
            else:
                direction.iloc[i] = direction.iloc[i-1] if not pd.isna(direction.iloc[i-1]) else 1
                if direction.iloc[i] == 1:
                    supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1] if not pd.isna(supertrend.iloc[i-1]) else lower_band.iloc[i])
                else:
                    supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1] if not pd.isna(supertrend.iloc[i-1]) else upper_band.iloc[i])
        
        for i in range(period + 1, len(df)):
            if pd.isna(direction.iloc[i]) or pd.isna(direction.iloc[i-1]):
                continue
            
            # Bullish signal
            if direction.iloc[i-1] == -1 and direction.iloc[i] == 1:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 76,
                    'entry_price': df['close'].iloc[i]
                })
            # Bearish signal
            elif direction.iloc[i-1] == 1 and direction.iloc[i] == -1:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 76,
                    'entry_price': df['close'].iloc[i]
                })
        
        return signals
    
    def _support_resistance_strategy(self, df: pd.DataFrame, lookback: int = 20) -> List[Dict]:
        """Support/Resistance Breakout Strategy"""
        signals = []
        
        for i in range(lookback, len(df)):
            window = df.iloc[i-lookback:i]
            resistance = window['high'].max()
            support = window['low'].min()
            
            close = df['close'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            
            # Resistance breakout (CALL)
            if prev_close < resistance and close > resistance:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 77,
                    'entry_price': close
                })
            # Support breakdown (PUT)
            elif prev_close > support and close < support:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 77,
                    'entry_price': close
                })
        
        return signals
    
    def _hybrid_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """Hybrid Strategy combining multiple indicators"""
        signals = []
        
        # Calculate indicators
        rsi = self._calculate_rsi(df['close'], 14)
        ema_fast = self._calculate_ema(df['close'], 7)
        ema_slow = self._calculate_ema(df['close'], 21)
        upper, middle, lower = self._calculate_bollinger_bands(df['close'])
        
        for i in range(21, len(df)):
            if pd.isna(rsi.iloc[i]) or pd.isna(ema_fast.iloc[i]):
                continue
            
            close = df['close'].iloc[i]
            bullish_signals = 0
            bearish_signals = 0
            
            # RSI conditions
            if rsi.iloc[i] < 35:
                bullish_signals += 1
            elif rsi.iloc[i] > 65:
                bearish_signals += 1
            
            # EMA conditions
            if ema_fast.iloc[i] > ema_slow.iloc[i]:
                bullish_signals += 1
            else:
                bearish_signals += 1
            
            # Bollinger conditions
            if close < lower.iloc[i]:
                bullish_signals += 1
            elif close > upper.iloc[i]:
                bearish_signals += 1
            
            # Generate signal if 2+ indicators agree
            if bullish_signals >= 2:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 70 + (bullish_signals * 5),
                    'entry_price': close
                })
            elif bearish_signals >= 2:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 70 + (bearish_signals * 5),
                    'entry_price': close
                })
        
        return signals
    
    def _enhanced_rsi_bb_volume_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """Enhanced RSI + Bollinger Bands + Volume Strategy"""
        signals = []
        
        rsi = self._calculate_rsi(df['close'], 14)
        upper, middle, lower = self._calculate_bollinger_bands(df['close'])
        volume_sma = self._calculate_sma(df['volume'], 20)
        
        for i in range(20, len(df)):
            if pd.isna(rsi.iloc[i]) or pd.isna(upper.iloc[i]) or pd.isna(volume_sma.iloc[i]):
                continue
            
            close = df['close'].iloc[i]
            volume = df['volume'].iloc[i]
            
            # Volume confirmation
            high_volume = volume > volume_sma.iloc[i] * 1.2
            
            # Bullish: RSI oversold + near lower BB + high volume
            if rsi.iloc[i] < 35 and close < lower.iloc[i] * 1.01 and high_volume:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': 78,
                    'entry_price': close
                })
            # Bearish: RSI overbought + near upper BB + high volume
            elif rsi.iloc[i] > 65 and close > upper.iloc[i] * 0.99 and high_volume:
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': 78,
                    'entry_price': close
                })
        
        return signals
    
    def _enhanced_divergence_strategy(self, df: pd.DataFrame) -> List[Dict]:
        """
        Enhanced RSI Divergence + MACD Exhaustion Strategy
        Based on research showing 73%+ win rate with divergence confluence
        
        Entry Rules:
        1. RSI Divergence (bullish: price lower low, RSI higher low)
        2. MACD Histogram Exhaustion (shrinking bars)
        3. Stochastic in extreme zone
        4. Volume confirmation
        """
        signals = []
        
        if len(df) < 50:
            return signals
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume'] if 'volume' in df.columns else pd.Series([1] * len(df))
        
        # Calculate indicators
        rsi = self._calculate_rsi(close, 7)  # Faster RSI for short timeframes
        macd, macd_signal, macd_hist = self._calculate_macd(close, 8, 17, 9)
        stoch_k, stoch_d = self._calculate_stochastic(high, low, close, 5, 3)
        volume_ma = self._calculate_sma(volume, 20)
        
        # Lookback for divergence detection
        lookback = 10
        
        for i in range(max(lookback + 5, 30), len(df)):
            if pd.isna(rsi.iloc[i]) or pd.isna(macd_hist.iloc[i]) or pd.isna(stoch_k.iloc[i]):
                continue
            
            current_close = close.iloc[i]
            current_rsi = rsi.iloc[i]
            current_hist = macd_hist.iloc[i]
            current_stoch = stoch_k.iloc[i]
            current_volume = volume.iloc[i]
            
            # Get recent data for divergence
            recent_close = close.iloc[i-lookback:i]
            recent_rsi = rsi.iloc[i-lookback:i]
            recent_hist = macd_hist.iloc[i-lookback:i].dropna()
            
            # Track confirmations
            bullish_confirmations = 0
            bearish_confirmations = 0
            
            # === 1. RSI DIVERGENCE ===
            # Bullish: Price lower low, RSI higher low
            if current_close <= recent_close.min():
                if len(recent_rsi.dropna()) > 0 and current_rsi > recent_rsi.min():
                    bullish_confirmations += 2  # High weight
            
            # Bearish: Price higher high, RSI lower high
            if current_close >= recent_close.max():
                if len(recent_rsi.dropna()) > 0 and current_rsi < recent_rsi.max():
                    bearish_confirmations += 2  # High weight
            
            # === 2. RSI EXTREME LEVELS ===
            if current_rsi < 25:
                bullish_confirmations += 1
            elif current_rsi > 75:
                bearish_confirmations += 1
            
            # === 3. MACD HISTOGRAM EXHAUSTION ===
            if len(recent_hist) >= 3:
                hist_values = recent_hist.values
                # Bullish exhaustion: negative but rising histogram
                if current_hist < 0 and len(hist_values) >= 3:
                    if hist_values[-1] > hist_values[-2] > hist_values[-3]:
                        bullish_confirmations += 1
                # Bearish exhaustion: positive but falling histogram
                elif current_hist > 0 and len(hist_values) >= 3:
                    if hist_values[-1] < hist_values[-2] < hist_values[-3]:
                        bearish_confirmations += 1
            
            # === 4. STOCHASTIC CONFIRMATION ===
            prev_stoch_k = stoch_k.iloc[i-1] if i > 0 else current_stoch
            prev_stoch_d = stoch_d.iloc[i-1] if i > 0 else stoch_d.iloc[i]
            current_stoch_d = stoch_d.iloc[i]
            
            # Bullish crossover in oversold
            if current_stoch < 20:
                bullish_confirmations += 1
                if current_stoch > current_stoch_d and prev_stoch_k <= prev_stoch_d:
                    bullish_confirmations += 1  # Crossover bonus
            
            # Bearish crossover in overbought
            if current_stoch > 80:
                bearish_confirmations += 1
                if current_stoch < current_stoch_d and prev_stoch_k >= prev_stoch_d:
                    bearish_confirmations += 1  # Crossover bonus
            
            # === 5. VOLUME CONFIRMATION ===
            if not pd.isna(volume_ma.iloc[i]) and volume_ma.iloc[i] > 0:
                if current_volume > volume_ma.iloc[i] * 1.3:
                    # Add to whichever direction has more confirmations
                    if bullish_confirmations > bearish_confirmations:
                        bullish_confirmations += 1
                    elif bearish_confirmations > bullish_confirmations:
                        bearish_confirmations += 1
            
            # === GENERATE SIGNAL (require 4+ confirmations) ===
            min_confirmations = 4
            
            if bullish_confirmations >= min_confirmations and bullish_confirmations > bearish_confirmations:
                confidence = min(70 + (bullish_confirmations - min_confirmations) * 5, 92)
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call',
                    'confidence': confidence,
                    'entry_price': current_close,
                    'confirmations': bullish_confirmations
                })
            
            elif bearish_confirmations >= min_confirmations and bearish_confirmations > bullish_confirmations:
                confidence = min(70 + (bearish_confirmations - min_confirmations) * 5, 92)
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'put',
                    'confidence': confidence,
                    'entry_price': current_close,
                    'confirmations': bearish_confirmations
                })
        
        return signals
    
    def execute_strategy(self, df: pd.DataFrame, strategy_name: str) -> List[Dict]:
        """Execute a strategy and return signals"""
        if strategy_name not in self.strategies:
            logger.warning(f"Unknown strategy: {strategy_name}, using hybrid")
            strategy_name = 'hybrid'
        
        return self.strategies[strategy_name](df)


class BacktestingService:
    """Main backtesting service"""
    
    def __init__(self, db=None):
        self.db = db
        self.data_fetcher = HistoricalDataFetcher()
        self.strategy_engine = StrategyEngine()
    
    def _determine_asset_type(self, symbol: str) -> str:
        """Determine asset type from symbol"""
        symbol_upper = symbol.upper().replace('_', '')
        
        if any(crypto in symbol_upper for crypto in CRYPTO_SYMBOLS) or 'USDT' in symbol_upper:
            return AssetType.CRYPTO
        elif symbol_upper in [s.replace('_', '') for s in FINNHUB_FOREX_SYMBOLS.keys()] or '=' in symbol:
            return AssetType.FOREX
        elif symbol_upper in STOCK_SYMBOLS:
            return AssetType.STOCK
        else:
            return AssetType.FOREX  # Default
    
    def _simulate_trade(self, signal: Dict, df: pd.DataFrame, payout_rate: float = 0.85) -> Dict:
        """Simulate a trade outcome"""
        idx = signal['index']
        
        # Check if we have enough future data
        if idx + 1 >= len(df):
            return None
        
        entry_price = signal['entry_price']
        exit_price = df['close'].iloc[idx + 1]  # Next candle close
        
        # Determine win/loss
        if signal['direction'] == 'call':
            win = exit_price > entry_price
        else:
            win = exit_price < entry_price
        
        return {
            'timestamp': signal['timestamp'],
            'direction': signal['direction'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'result': 'win' if win else 'loss',
            'confidence': signal['confidence']
        }
    
    async def run_backtest(self, config: BacktestConfig) -> List[BacktestResult]:
        """Run a comprehensive backtest"""
        results = []
        data_sources_used = {}  # Track data sources for reporting
        
        for asset in config.assets:
            asset_type = self._determine_asset_type(asset)
            
            for timeframe in config.timeframes:
                # Fetch historical data with multi-provider fallback
                df, data_source = await self.data_fetcher.fetch_historical_data(
                    asset, asset_type, config.days, timeframe
                )
                
                # Track data source
                data_sources_used[f"{asset}_{timeframe}"] = data_source
                
                if df is None or len(df) < 50:
                    logger.warning(f"Insufficient data for {asset} {timeframe}")
                    continue
                
                for strategy in config.strategies:
                    # Generate signals
                    signals = self.strategy_engine.execute_strategy(df, strategy)
                    
                    if not signals:
                        continue
                    
                    # Simulate trades
                    trades = []
                    balance = config.initial_balance
                    equity_curve = [balance]
                    max_balance = balance
                    max_drawdown = 0
                    
                    for signal in signals:
                        trade = self._simulate_trade(signal, df, config.payout_rate)
                        if trade is None:
                            continue
                        
                        # Calculate profit/loss
                        if trade['result'] == 'win':
                            profit = config.trade_amount * config.payout_rate
                        else:
                            profit = -config.trade_amount
                        
                        trade['profit'] = profit
                        trade['strategy'] = strategy
                        trade['asset'] = asset
                        trade['timeframe'] = timeframe
                        trades.append(trade)
                        
                        balance += profit
                        equity_curve.append(balance)
                        
                        # Track drawdown
                        if balance > max_balance:
                            max_balance = balance
                        drawdown = (max_balance - balance) / max_balance * 100
                        if drawdown > max_drawdown:
                            max_drawdown = drawdown
                    
                    if not trades:
                        continue
                    
                    # Calculate statistics
                    winning_trades = len([t for t in trades if t['result'] == 'win'])
                    losing_trades = len([t for t in trades if t['result'] == 'loss'])
                    total_trades = len(trades)
                    
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                    total_profit = sum(t['profit'] for t in trades)
                    
                    # Profit factor
                    gross_profit = sum(t['profit'] for t in trades if t['profit'] > 0)
                    gross_loss = abs(sum(t['profit'] for t in trades if t['profit'] < 0))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
                    
                    # ROI
                    roi = (balance - config.initial_balance) / config.initial_balance * 100
                    
                    result = BacktestResult(
                        config_id=config.id,
                        strategy=strategy,
                        asset=asset,
                        timeframe=timeframe,
                        total_trades=total_trades,
                        winning_trades=winning_trades,
                        losing_trades=losing_trades,
                        win_rate=win_rate,
                        total_profit=total_profit,
                        max_drawdown=max_drawdown,
                        profit_factor=profit_factor,
                        initial_balance=config.initial_balance,
                        final_balance=balance,
                        roi=roi,
                        start_date=str(df.index[0]),
                        end_date=str(df.index[-1]),
                        data_source=data_source,  # Track the data provider used
                        trades=[asdict(TradeResult(**t)) if isinstance(t, dict) else t for t in trades[:100]],  # Limit stored trades
                        equity_curve=equity_curve[-100:]  # Limit equity curve points
                    )
                    
                    results.append(result)
                    
                    # Save to database
                    if self.db:
                        await self.db.backtest_results.insert_one({
                            **asdict(result),
                            '_id': result.id
                        })
        
        return results
    
    async def get_available_assets(self) -> Dict[str, List[str]]:
        """Get list of available assets for backtesting"""
        return {
            "forex": list(FINNHUB_FOREX_SYMBOLS.keys()),
            "crypto": [f"{s}USDT" for s in CRYPTO_SYMBOLS],
            "stocks": STOCK_SYMBOLS
        }
    
    async def get_available_strategies(self) -> List[Dict]:
        """Get list of available strategies"""
        return [
            {"id": "rsi_reversal", "name": "RSI Reversal", "description": "RSI oversold/overbought reversals"},
            {"id": "ema_crossover", "name": "EMA Crossover", "description": "7/21 EMA golden/death cross"},
            {"id": "macd_crossover", "name": "MACD Crossover", "description": "MACD line crossing signal line"},
            {"id": "bollinger_bounce", "name": "Bollinger Bounce", "description": "Price bouncing off Bollinger Bands"},
            {"id": "stochastic_rsi", "name": "Stochastic RSI", "description": "Stochastic K/D crossover in extremes"},
            {"id": "supertrend", "name": "SuperTrend", "description": "SuperTrend direction changes"},
            {"id": "support_resistance", "name": "Support/Resistance", "description": "Breakout of support/resistance levels"},
            {"id": "hybrid", "name": "Hybrid Strategy", "description": "Combination of RSI, EMA, and Bollinger"},
            {"id": "enhanced_rsi_bb_volume", "name": "Enhanced RSI+BB+Volume", "description": "RSI + Bollinger with volume confirmation"},
        ]


# Singleton instance
_backtesting_service = None

async def get_backtesting_service(db=None):
    global _backtesting_service
    if _backtesting_service is None:
        _backtesting_service = BacktestingService(db)
    return _backtesting_service
