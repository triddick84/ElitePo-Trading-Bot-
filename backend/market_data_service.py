import asyncio
import aiohttp
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from models import MarketData, AssetType

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self):
        self.finnhub_api_key = os.environ.get('FINNHUB_API_KEY', 'placeholder_finnhub_key')
        self.pocket_option_ssid = os.environ.get('POCKET_OPTION_SSID', 'placeholder_ssid')
        
        # Major trading pairs and assets
        self.forex_symbols = [
            'OANDA:EUR_USD', 'OANDA:GBP_USD', 'OANDA:USD_JPY', 'OANDA:USD_CHF',
            'OANDA:AUD_USD', 'OANDA:USD_CAD', 'OANDA:NZD_USD', 'OANDA:EUR_GBP'
        ]
        self.crypto_symbols = ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT', 'BINANCE:ADAUSDT', 'BINANCE:BNBUSDT']
        self.stock_symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META']
        self.commodity_symbols = ['OANDA:XAU_USD', 'OANDA:XAG_USD', 'IC MARKETS:CRUDE_OIL']
        
    async def get_finnhub_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time quote from Finnhub API"""
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.error(f"Finnhub API error for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching Finnhub data for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str, asset_type: AssetType) -> Optional[MarketData]:
        """Get comprehensive market data for a symbol"""
        try:
            # For demo purposes, we'll use Finnhub data with some simulation
            quote_data = await self.get_finnhub_quote(symbol)
            
            if not quote_data:
                # Return simulated data if API fails (for demo)
                return self._generate_simulated_data(symbol, asset_type)
            
            return MarketData(
                symbol=symbol,
                asset_type=asset_type,
                price=quote_data.get('c', 0),  # current price
                bid=quote_data.get('c', 0) - 0.0001,  # simulate bid
                ask=quote_data.get('c', 0) + 0.0001,  # simulate ask
                volume=quote_data.get('v', 0),  # volume
                change=quote_data.get('d', 0),  # change
                change_percent=quote_data.get('dp', 0),  # change percent
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return self._generate_simulated_data(symbol, asset_type)
    
    def _generate_simulated_data(self, symbol: str, asset_type: AssetType) -> MarketData:
        """Generate simulated market data for demo purposes"""
        import random
        
        # Base prices for different asset types
        base_prices = {
            AssetType.FOREX: 1.0850 + random.uniform(-0.1, 0.1),
            AssetType.CRYPTO: 45000 + random.uniform(-5000, 5000),
            AssetType.STOCKS: 150 + random.uniform(-50, 50),
            AssetType.COMMODITIES: 2000 + random.uniform(-200, 200),
            AssetType.INDICES: 4500 + random.uniform(-500, 500),
            AssetType.OTC: 100 + random.uniform(-20, 20)
        }
        
        price = base_prices.get(asset_type, 100.0)
        spread = price * 0.0001  # 0.01% spread
        
        return MarketData(
            symbol=symbol,
            asset_type=asset_type,
            price=round(price, 4),
            bid=round(price - spread, 4),
            ask=round(price + spread, 4),
            volume=random.randint(1000, 10000),
            change=round(random.uniform(-0.5, 0.5), 4),
            change_percent=round(random.uniform(-1.0, 1.0), 2),
            timestamp=datetime.now(timezone.utc)
        )
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get historical price data for backtesting"""
        try:
            # For demo, return simulated historical data
            historical_data = []
            import random
            from datetime import timedelta
            
            base_price = 1.0850 if 'EUR' in symbol else 45000 if 'BTC' in symbol else 150
            
            for i in range(days * 24):  # Hourly data
                timestamp = datetime.now(timezone.utc) - timedelta(hours=i)
                price_change = random.uniform(-0.01, 0.01)
                price = base_price * (1 + price_change)
                
                historical_data.append({
                    'timestamp': timestamp.isoformat(),
                    'open': round(price * 0.999, 4),
                    'high': round(price * 1.002, 4),
                    'low': round(price * 0.998, 4),
                    'close': round(price, 4),
                    'volume': random.randint(1000, 5000)
                })
                
            return list(reversed(historical_data))
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []
    
    async def get_all_market_data(self) -> Dict[str, List[MarketData]]:
        """Get market data for all tracked assets"""
        all_data = {
            'forex': [],
            'crypto': [],
            'stocks': [],
            'commodities': [],
            'otc': []
        }
        
        try:
            # Fetch forex data
            for symbol in self.forex_symbols[:3]:  # Limit for demo
                data = await self.get_market_data(symbol, AssetType.FOREX)
                if data:
                    all_data['forex'].append(data)
            
            # Fetch crypto data
            for symbol in self.crypto_symbols[:3]:  # Limit for demo
                data = await self.get_market_data(symbol, AssetType.CRYPTO)
                if data:
                    all_data['crypto'].append(data)
            
            # Fetch stock data
            for symbol in self.stock_symbols[:3]:  # Limit for demo
                data = await self.get_market_data(symbol, AssetType.STOCKS)
                if data:
                    all_data['stocks'].append(data)
            
            # Add some OTC simulated data
            otc_symbols = ['OTC_EUR_USD', 'OTC_BTC_USD', 'OTC_GOLD']
            for symbol in otc_symbols:
                data = await self.get_market_data(symbol, AssetType.OTC)
                if data:
                    all_data['otc'].append(data)
                    
        except Exception as e:
            logger.error(f"Error fetching all market data: {e}")
            
        return all_data