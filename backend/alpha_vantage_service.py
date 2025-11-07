"""
Alpha Vantage Real-Time Market Data Service

Provides real-time forex and cryptocurrency exchange rates using Alpha Vantage API
Optimized for 5-second OTC trading with proper rate limiting and caching

Features:
- Real-time CURRENCY_EXCHANGE_RATE endpoint
- Rate limiting (5 calls/minute, 500 calls/day)
- Response caching to minimize API calls
- Support for both forex and crypto pairs
- Bid/Ask price extraction
"""

import os
import requests
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class AlphaVantageRealTimeData:
    """
    Alpha Vantage real-time currency exchange rate provider
    
    Rate Limits:
    - Free tier: 5 API calls per minute, 500 per day
    - Implements 12-second delays between calls
    - Caches responses for 5 seconds to reduce calls
    """
    
    def __init__(self):
        self.api_key = os.getenv('ALPHAVANTAGE_API_KEY', 'demo')
        self.base_url = 'https://www.alphavantage.co/query'
        
        # Rate limiting
        self.min_delay_seconds = 12  # 5 calls/min = 12s between calls
        self.last_request_time = None
        self.daily_call_count = 0
        self.daily_call_limit = 500
        self.call_reset_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)
        
        # Caching
        self.cache = {}
        self.cache_ttl_seconds = 5  # Cache for 5 seconds (ultra-short for 5s trading)
        
        logger.info("✅ Alpha Vantage Real-Time Data Service initialized")
        logger.info(f"   API Key: {'[SET]' if self.api_key != 'demo' else '[DEMO - Limited]'}")
        logger.info(f"   Rate Limit: {60 // self.min_delay_seconds} calls/min, {self.daily_call_limit} calls/day")
        logger.info(f"   Cache TTL: {self.cache_ttl_seconds}s")
    
    def _reset_daily_counter_if_needed(self):
        """Reset daily call counter at midnight UTC"""
        now = datetime.now(timezone.utc)
        if now >= self.call_reset_time:
            self.daily_call_count = 0
            self.call_reset_time = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
            logger.info(f"📅 Daily call counter reset (new limit: {self.daily_call_limit})")
    
    def _enforce_rate_limit(self):
        """Enforce minimum delay between API calls"""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_delay_seconds:
                sleep_time = self.min_delay_seconds - elapsed
                logger.debug(f"⏳ Rate limit: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _get_cache_key(self, from_currency: str, to_currency: str) -> str:
        """Generate cache key for currency pair"""
        return f"{from_currency}_{to_currency}"
    
    def _get_cached_data(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """Retrieve cached data if still valid"""
        cache_key = self._get_cache_key(from_currency, to_currency)
        
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            age = time.time() - cache_time
            
            if age < self.cache_ttl_seconds:
                logger.debug(f"💾 Cache HIT: {cache_key} (age: {age:.1f}s)")
                return cached_data
            else:
                logger.debug(f"💾 Cache EXPIRED: {cache_key} (age: {age:.1f}s)")
                del self.cache[cache_key]
        
        return None
    
    def _set_cached_data(self, from_currency: str, to_currency: str, data: Dict):
        """Store data in cache"""
        cache_key = self._get_cache_key(from_currency, to_currency)
        self.cache[cache_key] = (data, time.time())
        logger.debug(f"💾 Cache SET: {cache_key}")
    
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """
        Get real-time exchange rate for currency pair
        
        Args:
            from_currency: Source currency (e.g., "EUR", "BTC")
            to_currency: Destination currency (e.g., "USD", "EUR")
        
        Returns:
            Dict with exchange rate data or None if error
            {
                'from_currency': 'EUR',
                'to_currency': 'USD',
                'exchange_rate': 1.0867,
                'bid_price': 1.0866,
                'ask_price': 1.0868,
                'last_refreshed': '2024-01-01 12:00:00',
                'timezone': 'UTC'
            }
        """
        # Check cache first
        cached_data = self._get_cached_data(from_currency, to_currency)
        if cached_data is not None:
            return cached_data
        
        # Reset daily counter if needed
        self._reset_daily_counter_if_needed()
        
        # Check daily limit
        if self.daily_call_count >= self.daily_call_limit:
            logger.error(f"❌ Daily API limit reached ({self.daily_call_limit} calls)")
            return None
        
        # Enforce rate limit
        self._enforce_rate_limit()
        
        try:
            params = {
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': from_currency,
                'to_currency': to_currency,
                'apikey': self.api_key
            }
            
            logger.info(f"🌐 API Call: {from_currency}/{to_currency}")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            self.daily_call_count += 1
            logger.debug(f"📊 Daily calls: {self.daily_call_count}/{self.daily_call_limit}")
            
            data = response.json()
            
            # Check for error or rate limit message
            if 'Error Message' in data:
                logger.error(f"❌ API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"⚠️ API Note: {data['Note']}")
                return None
            
            # Extract exchange rate data
            if 'Realtime Currency Exchange Rate' not in data:
                logger.error(f"❌ Unexpected response format: {data}")
                return None
            
            rate_data = data['Realtime Currency Exchange Rate']
            
            result = {
                'from_currency': rate_data['1. From_Currency Code'],
                'to_currency': rate_data['3. To_Currency Code'],
                'exchange_rate': float(rate_data['5. Exchange Rate']),
                'bid_price': float(rate_data.get('8. Bid Price', rate_data['5. Exchange Rate'])),
                'ask_price': float(rate_data.get('9. Ask Price', rate_data['5. Exchange Rate'])),
                'last_refreshed': rate_data['6. Last Refreshed'],
                'timezone': rate_data['7. Time Zone']
            }
            
            # Cache the result
            self._set_cached_data(from_currency, to_currency, result)
            
            logger.info(f"✅ Exchange Rate: {from_currency}/{to_currency} = {result['exchange_rate']:.5f}")
            logger.info(f"   Bid: {result['bid_price']:.5f}, Ask: {result['ask_price']:.5f}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API Request failed: {e}")
            return None
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Data parsing error: {e}")
            return None
    
    def convert_symbol_to_currencies(self, symbol: str) -> Optional[Tuple[str, str]]:
        """
        Convert trading symbol to Alpha Vantage currency pair
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
        
        Returns:
            Tuple of (from_currency, to_currency) or None
        """
        # Remove common suffixes
        symbol = symbol.replace('_OTC', '').replace('=X', '').upper()
        
        # Common forex pairs (6 characters)
        if len(symbol) == 6:
            from_curr = symbol[:3]
            to_curr = symbol[3:]
            return (from_curr, to_curr)
        
        # Crypto pairs
        crypto_map = {
            'BTCUSD': ('BTC', 'USD'),
            'ETHUSD': ('ETH', 'USD'),
            'LTCUSD': ('LTC', 'USD'),
            'XRPUSD': ('XRP', 'USD'),
            'ADAUSD': ('ADA', 'USD'),
            'DOGEUSD': ('DOGE', 'USD'),
            'SOLUSD': ('SOL', 'USD'),
        }
        
        if symbol in crypto_map:
            return crypto_map[symbol]
        
        logger.warning(f"⚠️ Unknown symbol format: {symbol}")
        return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current mid price for trading symbol
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
        
        Returns:
            Current mid price (average of bid/ask) or None
        """
        currencies = self.convert_symbol_to_currencies(symbol)
        if currencies is None:
            return None
        
        from_curr, to_curr = currencies
        rate_data = self.get_exchange_rate(from_curr, to_curr)
        
        if rate_data is None:
            return None
        
        # Return mid price (average of bid and ask)
        mid_price = (rate_data['bid_price'] + rate_data['ask_price']) / 2
        return mid_price
    
    def get_ohlc_proxy(self, symbol: str, periods: int = 20) -> Optional[Dict]:
        """
        Get proxy OHLC data by sampling current price multiple times
        
        Note: Alpha Vantage free tier doesn't provide historical intraday data
        This creates a proxy by sampling current price
        
        Args:
            symbol: Trading symbol
            periods: Number of periods to simulate
        
        Returns:
            Dict with simulated OHLC data
        """
        price = self.get_current_price(symbol)
        if price is None:
            return None
        
        # Create proxy candles (all same price - real implementation needs historical endpoint)
        return {
            'open': [price] * periods,
            'high': [price * 1.0001] * periods,  # Slight variance
            'low': [price * 0.9999] * periods,
            'close': [price] * periods,
            'current_price': price
        }


# Global instance
_alpha_vantage_service = None


def get_alpha_vantage_service() -> AlphaVantageRealTimeData:
    """Get or create Alpha Vantage service instance"""
    global _alpha_vantage_service
    if _alpha_vantage_service is None:
        _alpha_vantage_service = AlphaVantageRealTimeData()
    return _alpha_vantage_service
