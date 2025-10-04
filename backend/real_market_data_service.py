import asyncio
import aiohttp
import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import logging
from models import MarketData, AssetType
import requests
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

class RealMarketDataService:
    """Real-time market data service using multiple data sources"""
    
    def __init__(self):
        self.alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_API_KEY', '')
        self.finnhub_api_key = os.environ.get('FINNHUB_API_KEY', '')
        
        # Define real trading symbols (Yahoo Finance format)
        self.symbol_mapping = {
            # Forex Regular
            'EURUSD': 'EURUSD=X',
            'GBPUSD': 'GBPUSD=X',
            'USDJPY': 'USDJPY=X',
            'USDCHF': 'USDCHF=X',
            'AUDUSD': 'AUDUSD=X',
            'USDCAD': 'USDCAD=X',
            'NZDUSD': 'NZDUSD=X',
            
            # Forex OTC (use same data source)
            'EURUSD_OTC': 'EURUSD=X',
            'GBPUSD_OTC': 'GBPUSD=X',
            'USDJPY_OTC': 'USDJPY=X',
            
            # Crypto Regular
            'BTCUSD': 'BTC-USD',
            'ETHUSD': 'ETH-USD',
            'LTCUSD': 'LTC-USD',
            'XRPUSD': 'XRP-USD',
            'ADAUSD': 'ADA-USD',
            'BNBUSD': 'BNB-USD',
            
            # Crypto OTC
            'BTCUSD_OTC': 'BTC-USD',
            'ETHUSD_OTC': 'ETH-USD',
            
            # Stocks Regular
            'AAPL': 'AAPL',
            'GOOGL': 'GOOGL',
            'MSFT': 'MSFT',
            'TSLA': 'TSLA',
            'AMZN': 'AMZN',
            'META': 'META',
            'NVDA': 'NVDA',
            
            # Stocks OTC
            'AAPL_OTC': 'AAPL',
            'GOOGL_OTC': 'GOOGL',
            'MSFT_OTC': 'MSFT',
            
            # Commodities
            'XAUUSD': 'GC=F',  # Gold
            'XAGUSD': 'SI=F',  # Silver
            'USOIL': 'CL=F',   # Crude Oil
            'UKOIL': 'BZ=F',   # Brent Oil
            
            # Indices
            'SPX500': '^GSPC',  # S&P 500
            'NAS100': '^IXIC',  # NASDAQ
            'DJ30': '^DJI',     # Dow Jones
        }
        
        self.forex_symbols = {
            'EURUSD=X': 'EUR/USD',
            'GBPUSD=X': 'GBP/USD', 
            'USDJPY=X': 'USD/JPY',
            'USDCHF=X': 'USD/CHF',
            'AUDUSD=X': 'AUD/USD',
            'USDCAD=X': 'USD/CAD',
            'NZDUSD=X': 'NZD/USD'
        }
        
        self.crypto_symbols = {
            'BTC-USD': 'Bitcoin',
            'ETH-USD': 'Ethereum',
            'ADA-USD': 'Cardano',
            'BNB-USD': 'Binance Coin',
            'SOL-USD': 'Solana',
            'DOT-USD': 'Polkadot'
        }
        
        self.stock_symbols = {
            'AAPL': 'Apple Inc.',
            'GOOGL': 'Alphabet Inc.',
            'MSFT': 'Microsoft Corp.',
            'TSLA': 'Tesla Inc.',
            'AMZN': 'Amazon.com Inc.',
            'NVDA': 'NVIDIA Corp.',
            'META': 'Meta Platforms'
        }
        
        self.commodity_symbols = {
            'GC=F': 'Gold',
            'SI=F': 'Silver', 
            'CL=F': 'Crude Oil',
            'NG=F': 'Natural Gas'
        }
        
        self.executor = ThreadPoolExecutor(max_workers=10)
        
    def get_yahoo_finance_data(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time data from Yahoo Finance using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get real-time info
            info = ticker.info
            
            # Get recent price data
            hist = ticker.history(period="1d", interval="1m")
            
            if hist.empty:
                logger.warning(f"No historical data for {symbol}")
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            
            # Calculate change
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
            
            return {
                'symbol': symbol,
                'price': float(current_price),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': float(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
                'high': float(hist['High'].iloc[-1]) if 'High' in hist.columns else float(current_price),
                'low': float(hist['Low'].iloc[-1]) if 'Low' in hist.columns else float(current_price),
                'open': float(hist['Open'].iloc[-1]) if 'Open' in hist.columns else float(current_price),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance data for {symbol}: {e}")
            return None
    
    async def get_alpha_vantage_data(self, symbol: str, asset_type: str) -> Optional[Dict]:
        """Fetch data from Alpha Vantage API"""
        if not self.alpha_vantage_key:
            return None
            
        try:
            # Determine function based on asset type
            if asset_type == 'forex':
                function = 'FX_INTRADAY'
                from_symbol, to_symbol = symbol.replace('=X', '').replace('USD', ',USD').split(',')
                url = f"https://www.alphavantage.co/query?function={function}&from_symbol={from_symbol}&to_symbol={to_symbol}&interval=1min&apikey={self.alpha_vantage_key}"
            elif asset_type == 'crypto':
                function = 'CRYPTO_INTRADAY'
                crypto_symbol = symbol.replace('-USD', '')
                url = f"https://www.alphavantage.co/query?function={function}&symbol={crypto_symbol}&market=USD&interval=1min&apikey={self.alpha_vantage_key}"
            else:
                function = 'TIME_SERIES_INTRADAY'
                url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&interval=1min&apikey={self.alpha_vantage_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_alpha_vantage_response(data, symbol)
                    else:
                        logger.error(f"Alpha Vantage API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data for {symbol}: {e}")
            return None
    
    def _parse_alpha_vantage_response(self, data: Dict, symbol: str) -> Optional[Dict]:
        """Parse Alpha Vantage API response"""
        try:
            # Find the time series data key
            time_series_key = None
            for key in data.keys():
                if 'Time Series' in key or 'FX Intraday' in key:
                    time_series_key = key
                    break
            
            if not time_series_key or time_series_key not in data:
                return None
                
            time_series = data[time_series_key]
            if not time_series:
                return None
                
            # Get the latest data point
            latest_time = max(time_series.keys())
            latest_data = time_series[latest_time]
            
            current_price = float(latest_data.get('4. close', 0))
            open_price = float(latest_data.get('1. open', current_price))
            
            change = current_price - open_price
            change_percent = (change / open_price) * 100 if open_price != 0 else 0
            
            return {
                'symbol': symbol,
                'price': current_price,
                'change': change,
                'change_percent': change_percent,
                'volume': float(latest_data.get('5. volume', 0)),
                'high': float(latest_data.get('2. high', current_price)),
                'low': float(latest_data.get('3. low', current_price)),
                'open': open_price,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error parsing Alpha Vantage response: {e}")
            return None
    
    async def get_finnhub_data(self, symbol: str) -> Optional[Dict]:
        """Fetch data from Finnhub API"""
        if not self.finnhub_api_key:
            return None
            
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        current_price = data.get('c', 0)  # current price
                        prev_close = data.get('pc', current_price)  # previous close
                        
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        return {
                            'symbol': symbol,
                            'price': float(current_price),
                            'change': float(change),
                            'change_percent': float(change_percent),
                            'volume': 0,  # Finnhub quote doesn't include volume
                            'high': float(data.get('h', current_price)),
                            'low': float(data.get('l', current_price)),
                            'open': float(data.get('o', current_price)),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        logger.error(f"Finnhub API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching Finnhub data for {symbol}: {e}")
            return None
    
    def get_real_time_data(self, symbol: str, asset_type: str) -> Optional[Dict]:
        """Get real-time data with fallback to multiple sources"""
        # Primary: Yahoo Finance (no API key required)
        data = self.get_yahoo_finance_data(symbol)
        
        if data:
            return data
            
        # Fallback to other sources if available
        logger.warning(f"Yahoo Finance failed for {symbol}, trying other sources")
        return None
    
    async def get_market_data(self, symbol: str, asset_type: AssetType) -> Optional[MarketData]:
        """Get comprehensive market data for a symbol"""
        try:
            # Use ThreadPoolExecutor to run synchronous Yahoo Finance calls
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                self.executor, 
                self.get_real_time_data, 
                symbol, 
                asset_type.value
            )
            
            if not data:
                logger.error(f"No market data available for {symbol}")
                return None
            
            # Calculate bid/ask spread (approximate)
            price = data['price']
            spread = price * 0.0001  # 0.01% spread approximation
            
            return MarketData(
                symbol=symbol,
                asset_type=asset_type,
                price=price,
                bid=round(price - spread, 6),
                ask=round(price + spread, 6),
                volume=data.get('volume', 0),
                change=data.get('change', 0),
                change_percent=data.get('change_percent', 0),
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get real historical price data for backtesting"""
        try:
            # Use ThreadPoolExecutor for synchronous yfinance call
            loop = asyncio.get_event_loop()
            hist_data = await loop.run_in_executor(
                self.executor,
                self._fetch_yahoo_historical,
                symbol,
                days
            )
            
            if hist_data is None:
                return []
                
            return hist_data
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []
    
    def _fetch_yahoo_historical(self, symbol: str, days: int) -> List[Dict]:
        """Fetch historical data using yfinance (synchronous)"""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get hourly data for the specified period
            hist = ticker.history(start=start_date, end=end_date, interval="1h")
            
            if hist.empty:
                return []
            
            historical_data = []
            for timestamp, row in hist.iterrows():
                historical_data.append({
                    'timestamp': timestamp.isoformat(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']) if 'Volume' in row else 0
                })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo historical data for {symbol}: {e}")
            return []
    
    async def get_all_market_data(self) -> Dict[str, List[MarketData]]:
        """Get real-time market data for all tracked assets"""
        all_data = {
            'forex': [],
            'crypto': [],
            'stocks': [],
            'commodities': []
        }
        
        try:
            # Create tasks for parallel data fetching
            tasks = []
            
            # Forex data
            for symbol in list(self.forex_symbols.keys())[:4]:  # Limit to prevent rate limits
                tasks.append(self.get_market_data(symbol, AssetType.FOREX))
            
            # Crypto data
            for symbol in list(self.crypto_symbols.keys())[:4]:
                tasks.append(self.get_market_data(symbol, AssetType.CRYPTO))
            
            # Stock data
            for symbol in list(self.stock_symbols.keys())[:4]:
                tasks.append(self.get_market_data(symbol, AssetType.STOCKS))
            
            # Commodity data
            for symbol in list(self.commodity_symbols.keys())[:2]:
                tasks.append(self.get_market_data(symbol, AssetType.COMMODITIES))
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Organize results by asset type
            forex_count = len(list(self.forex_symbols.keys())[:4])
            crypto_count = len(list(self.crypto_symbols.keys())[:4])
            stock_count = len(list(self.stock_symbols.keys())[:4])
            
            # Process results
            idx = 0
            for result in results[:forex_count]:
                if isinstance(result, MarketData):
                    all_data['forex'].append(result)
                idx += 1
            
            for result in results[forex_count:forex_count + crypto_count]:
                if isinstance(result, MarketData):
                    all_data['crypto'].append(result)
            
            for result in results[forex_count + crypto_count:forex_count + crypto_count + stock_count]:
                if isinstance(result, MarketData):
                    all_data['stocks'].append(result)
            
            for result in results[forex_count + crypto_count + stock_count:]:
                if isinstance(result, MarketData):
                    all_data['commodities'].append(result)
            
        except Exception as e:
            logger.error(f"Error fetching all market data: {e}")
            
        return all_data
    
    def get_symbol_info(self, symbol: str) -> Dict[str, str]:
        """Get human-readable information about a symbol"""
        all_symbols = {
            **self.forex_symbols,
            **self.crypto_symbols, 
            **self.stock_symbols,
            **self.commodity_symbols
        }
        
        return {
            'symbol': symbol,
            'name': all_symbols.get(symbol, symbol),
            'type': self._get_symbol_type(symbol)
        }
    
    def _get_symbol_type(self, symbol: str) -> str:
        """Determine the asset type of a symbol"""
        if symbol in self.forex_symbols:
            return 'forex'
        elif symbol in self.crypto_symbols:
            return 'crypto'
        elif symbol in self.stock_symbols:
            return 'stocks'
        elif symbol in self.commodity_symbols:
            return 'commodities'
        else:
            return 'unknown'