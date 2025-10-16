"""
Complete Pocket Option Asset Lists for 2025
Based on official Pocket Option asset offerings including:
- 53 Forex pairs (Regular + OTC)
- 30+ Cryptocurrencies (OTC 24/7)
- 19+ Stocks (Regular + OTC)  
- 7 Commodities (OTC 24/7)
- Multiple Indices (Regular + OTC)
"""

from typing import Dict, List, Tuple

class PocketOptionAssets:
    """Complete asset lists from Pocket Option platform"""
    
    def __init__(self):
        self.forex_pairs = self._get_forex_pairs()
        self.cryptocurrencies = self._get_cryptocurrencies()
        self.stocks = self._get_stocks()
        self.commodities = self._get_commodities()
        self.indices = self._get_indices()
        
    def _get_forex_pairs(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """Get all 53 Forex pairs available on Pocket Option"""
        return {
            "major_pairs": [
                ("EURUSD", "EUR/USD", "Euro vs US Dollar"),
                ("GBPUSD", "GBP/USD", "British Pound vs US Dollar"), 
                ("USDJPY", "USD/JPY", "US Dollar vs Japanese Yen"),
                ("AUDUSD", "AUD/USD", "Australian Dollar vs US Dollar"),
                ("USDCHF", "USD/CHF", "US Dollar vs Swiss Franc"),
                ("USDCAD", "USD/CAD", "US Dollar vs Canadian Dollar"),
                ("NZDUSD", "NZD/USD", "New Zealand Dollar vs US Dollar"),
            ],
            "minor_pairs": [
                ("EURGBP", "EUR/GBP", "Euro vs British Pound"),
                ("EURJPY", "EUR/JPY", "Euro vs Japanese Yen"),
                ("EURCHF", "EUR/CHF", "Euro vs Swiss Franc"),
                ("EURCAD", "EUR/CAD", "Euro vs Canadian Dollar"),
                ("EURAUD", "EUR/AUD", "Euro vs Australian Dollar"),
                ("EURNZD", "EUR/NZD", "Euro vs New Zealand Dollar"),
                ("GBPJPY", "GBP/JPY", "British Pound vs Japanese Yen"),
                ("GBPCHF", "GBP/CHF", "British Pound vs Swiss Franc"),
                ("GBPCAD", "GBP/CAD", "British Pound vs Canadian Dollar"),
                ("GBPAUD", "GBP/AUD", "British Pound vs Australian Dollar"),
                ("GBPNZD", "GBP/NZD", "British Pound vs New Zealand Dollar"),
                ("CHFJPY", "CHF/JPY", "Swiss Franc vs Japanese Yen"),
                ("CADJPY", "CAD/JPY", "Canadian Dollar vs Japanese Yen"),
                ("AUDJPY", "AUD/JPY", "Australian Dollar vs Japanese Yen"),
                ("AUDCHF", "AUD/CHF", "Australian Dollar vs Swiss Franc"),
                ("AUDCAD", "AUD/CAD", "Australian Dollar vs Canadian Dollar"),
                ("AUDNZD", "AUD/NZD", "Australian Dollar vs New Zealand Dollar"),
                ("NZDJPY", "NZD/JPY", "New Zealand Dollar vs Japanese Yen"),
                ("NZDCHF", "NZD/CHF", "New Zealand Dollar vs Swiss Franc"),
                ("NZDCAD", "NZD/CAD", "New Zealand Dollar vs Canadian Dollar"),
                ("CADCHF", "CAD/CHF", "Canadian Dollar vs Swiss Franc"),
            ],
            "exotic_pairs": [
                ("USDMXN", "USD/MXN", "US Dollar vs Mexican Peso"),
                ("USDARS", "USD/ARS", "US Dollar vs Argentine Peso"),
                ("USDBRL", "USD/BRL", "US Dollar vs Brazilian Real"),
                ("USDCOP", "USD/COP", "US Dollar vs Colombian Peso"),
                ("USDEGP", "USD/EGP", "US Dollar vs Egyptian Pound"),
                ("USDPHP", "USD/PHP", "US Dollar vs Philippine Peso"),
                ("USDDZD", "USD/DZD", "US Dollar vs Algerian Dinar"),
                ("USDIDR", "USD/IDR", "US Dollar vs Indonesian Rupiah"),
                ("USDBDT", "USD/BDT", "US Dollar vs Bangladeshi Taka"),
                ("YERUSD", "YER/USD", "Yemeni Rial vs US Dollar"),
                ("CHFNOK", "CHF/NOK", "Swiss Franc vs Norwegian Krone"),
                ("JODCNY", "JOD/CNY", "Jordanian Dinar vs Chinese Yuan"),
                ("USDMYR", "USD/MYR", "US Dollar vs Malaysian Ringgit"),
                ("ZARUSD", "ZAR/USD", "South African Rand vs US Dollar"),
                ("EURRUB", "EUR/RUB", "Euro vs Russian Ruble"),
                ("USDRUB", "USD/RUB", "US Dollar vs Russian Ruble"),
                ("USDTRY", "USD/TRY", "US Dollar vs Turkish Lira"),
                ("USDZAR", "USD/ZAR", "US Dollar vs South African Rand"),
                ("USDPLN", "USD/PLN", "US Dollar vs Polish Zloty"),
                ("USDSGD", "USD/SGD", "US Dollar vs Singapore Dollar"),
                ("USDHKD", "USD/HKD", "US Dollar vs Hong Kong Dollar"),
                ("USDTHB", "USD/THB", "US Dollar vs Thai Baht"),
                ("USDSEK", "USD/SEK", "US Dollar vs Swedish Krona"),
                ("USDNOK", "USD/NOK", "US Dollar vs Norwegian Krone"),
                ("USDDKK", "USD/DKK", "US Dollar vs Danish Krone"),
            ]
        }
    
    def _get_cryptocurrencies(self) -> List[Tuple[str, str, str]]:
        """Get all 30+ cryptocurrencies available on Pocket Option"""
        return [
            # Major Cryptocurrencies
            ("BTCUSD", "BTC/USD", "Bitcoin vs US Dollar"),
            ("ETHUSD", "ETH/USD", "Ethereum vs US Dollar"),
            ("LTCUSD", "LTC/USD", "Litecoin vs US Dollar"),
            ("ADAUSD", "ADA/USD", "Cardano vs US Dollar"),
            ("DOTUSD", "DOT/USD", "Polkadot vs US Dollar"),
            
            # Popular Altcoins
            ("DOGEUSD", "DOGE/USD", "Dogecoin vs US Dollar"),
            ("SOLUSD", "SOL/USD", "Solana vs US Dollar"),
            ("AVAXUSD", "AVAX/USD", "Avalanche vs US Dollar"),
            ("MATICUSD", "MATIC/USD", "Polygon vs US Dollar"),
            ("LINKUSD", "LINK/USD", "Chainlink vs US Dollar"),
            ("TONUSD", "TON/USD", "Toncoin vs US Dollar"),
            
            # Exchange Tokens & DeFi
            ("BNBUSD", "BNB/USD", "Binance Coin vs US Dollar"),
            ("UNIUSD", "UNI/USD", "Uniswap vs US Dollar"),
            ("AAVEUSD", "AAVE/USD", "Aave vs US Dollar"),
            ("SUSHIUSD", "SUSHI/USD", "SushiSwap vs US Dollar"),
            
            # Layer 1 & Infrastructure
            ("ATOMUSD", "ATOM/USD", "Cosmos vs US Dollar"),
            ("FILUSD", "FIL/USD", "Filecoin vs US Dollar"),
            ("XTZUSD", "XTZ/USD", "Tezos vs US Dollar"),
            ("ALGOUSD", "ALGO/USD", "Algorand vs US Dollar"),
            ("EGLD USD", "EGLD/USD", "MultiversX vs US Dollar"),
            
            # Meme & Community Coins
            ("SHIBUSDT", "SHIB/USD", "Shiba Inu vs US Dollar"),
            ("FLOKIUSD", "FLOKI/USD", "Floki vs US Dollar"),
            
            # Privacy & Others
            ("XMRUSD", "XMR/USD", "Monero vs US Dollar"),
            ("ZECUSD", "ZEC/USD", "Zcash vs US Dollar"),
            ("DASHUSD", "DASH/USD", "Dash vs US Dollar"),
            
            # Stablecoins & ETF
            ("BTCETF", "BTC ETF", "Bitcoin ETF OTC"),
            ("ETHBTC", "ETH/BTC", "Ethereum vs Bitcoin"),
            ("ADABTC", "ADA/BTC", "Cardano vs Bitcoin"),
            ("DOGEBTC", "DOGE/BTC", "Dogecoin vs Bitcoin"),
            
            # New & Emerging
            ("APTOUSD", "APTO/USD", "Aptos vs US Dollar"),
            ("OPUSD", "OP/USD", "Optimism vs US Dollar"),
            ("ARBUSD", "ARB/USD", "Arbitrum vs US Dollar"),
            ("NEARUSD", "NEAR/USD", "NEAR Protocol vs US Dollar"),
        ]
    
    def _get_stocks(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """Get all stocks available on Pocket Option"""
        return {
            "tech_giants": [
                ("AAPL", "Apple Inc.", "Technology - Consumer Electronics"),
                ("MSFT", "Microsoft Corp.", "Technology - Software"),
                ("GOOGL", "Alphabet Inc.", "Technology - Internet Services"),
                ("AMZN", "Amazon.com Inc.", "Technology - E-commerce"),
                ("TSLA", "Tesla Inc.", "Automotive - Electric Vehicles"),
                ("META", "Meta Platforms Inc.", "Technology - Social Media"),
                ("NFLX", "Netflix Inc.", "Technology - Streaming"),
                ("NVDA", "NVIDIA Corp.", "Technology - Semiconductors"),
                ("BABA", "Alibaba Group", "Technology - E-commerce (Chinese)"),
            ],
            "financial": [
                ("JPM", "JPMorgan Chase", "Financial - Banking"),
                ("BAC", "Bank of America", "Financial - Banking"),
                ("WFC", "Wells Fargo", "Financial - Banking"),
                ("GS", "Goldman Sachs", "Financial - Investment Banking"),
                ("MS", "Morgan Stanley", "Financial - Investment Banking"),
                ("AXP", "American Express", "Financial - Credit Services"),
            ],
            "industrial": [
                ("BA", "Boeing Co.", "Industrial - Aerospace"),
                ("CAT", "Caterpillar Inc.", "Industrial - Heavy Machinery"),
                ("GE", "General Electric", "Industrial - Conglomerate"),
                ("MMM", "3M Company", "Industrial - Diversified"),
            ],
            "healthcare": [
                ("JNJ", "Johnson & Johnson", "Healthcare - Pharmaceuticals"),
                ("PFE", "Pfizer Inc.", "Healthcare - Pharmaceuticals"),
                ("UNH", "UnitedHealth Group", "Healthcare - Insurance"),
                ("ABBV", "AbbVie Inc.", "Healthcare - Biotechnology"),
            ],
            "consumer": [
                ("MCD", "McDonald's Corp.", "Consumer - Restaurants"),
                ("KO", "Coca-Cola Co.", "Consumer - Beverages"),
                ("PG", "Procter & Gamble", "Consumer - Personal Care"),
                ("WMT", "Walmart Inc.", "Consumer - Retail"),
            ],
            "energy": [
                ("XOM", "Exxon Mobil", "Energy - Oil & Gas"),
                ("CVX", "Chevron Corp.", "Energy - Oil & Gas"),
            ]
        }
    
    def _get_commodities(self) -> List[Tuple[str, str, str]]:
        """Get all 7 commodities available on Pocket Option"""
        return [
            ("XAUUSD", "Gold OTC", "Precious Metals - Gold Spot Price"),
            ("XAGUSD", "Silver OTC", "Precious Metals - Silver Spot Price"),
            ("BRENTOIL", "Brent Oil OTC", "Energy - Brent Crude Oil"),
            ("WTIUSD", "WTI Crude Oil OTC", "Energy - West Texas Intermediate"),
            ("NATGAS", "Natural Gas OTC", "Energy - Natural Gas Futures"),
            ("XPTUSD", "Platinum OTC", "Precious Metals - Platinum Spot Price"),
            ("XPDUSD", "Palladium OTC", "Precious Metals - Palladium Spot Price"),
        ]
    
    def _get_indices(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """Get all indices available on Pocket Option"""
        return {
            "us_indices": [
                ("US100", "US100 (NASDAQ)", "US Technology Index"),
                ("US30", "US30 (Dow Jones)", "US Industrial Average"),
                ("SPX500", "S&P 500", "US Large Cap Index"),
                ("US2000", "Russell 2000", "US Small Cap Index"),
            ],
            "european_indices": [
                ("E35EUR", "E35EUR OTC", "EuroStoxx 35 Index"),
                ("GER40", "GER40 (DAX)", "German Stock Index"),
                ("UK100", "UK100 (FTSE)", "UK Stock Index"),
                ("FRA40", "CAC 40", "French Stock Index"),
                ("ESP35", "IBEX 35", "Spanish Stock Index"),
                ("ITA40", "FTSE MIB", "Italian Stock Index"),
            ],
            "asia_pacific": [
                ("AUS200", "AUS200 OTC", "Australian Stock Index"),
                ("JPN225", "Nikkei 225", "Japanese Stock Index"),
                ("HK50", "Hang Seng", "Hong Kong Stock Index"),
                ("CHINA50", "China A50", "Chinese Stock Index"),
            ],
            "other_regions": [
                ("SA40", "South Africa 40", "South African Stock Index"),
                ("BRAZIL60", "Bovespa", "Brazilian Stock Index"),
                ("MEXICO35", "IPC Mexico", "Mexican Stock Index"),
            ]
        }
    
    def get_all_assets_formatted(self) -> Dict[str, List[Dict]]:
        """Get all assets in a format suitable for frontend selection"""
        formatted_assets = {
            "forex": [],
            "crypto": [],
            "stocks": [], 
            "commodities": [],
            "indices": []
        }
        
        # Format Forex pairs
        for category, pairs in self.forex_pairs.items():
            for symbol, display, description in pairs:
                formatted_assets["forex"].append({
                    "symbol": symbol,
                    "display_name": display,
                    "description": description,
                    "category": category.replace("_", " ").title(),
                    "market_types": ["regular", "otc"],
                    "trading_hours": "24/7 OTC, Regular Market Hours"
                })
        
        # Format Cryptocurrencies
        for symbol, display, description in self.cryptocurrencies:
            formatted_assets["crypto"].append({
                "symbol": symbol,
                "display_name": display,
                "description": description,
                "category": "Cryptocurrency",
                "market_types": ["otc"],
                "trading_hours": "24/7 OTC"
            })
        
        # Format Stocks
        for category, stocks in self.stocks.items():
            for symbol, name, description in stocks:
                formatted_assets["stocks"].append({
                    "symbol": symbol,
                    "display_name": f"{symbol} - {name}",
                    "description": description,
                    "category": category.replace("_", " ").title(),
                    "market_types": ["regular", "otc"],
                    "trading_hours": "Regular Market Hours + 24/7 OTC"
                })
        
        # Format Commodities
        for symbol, display, description in self.commodities:
            formatted_assets["commodities"].append({
                "symbol": symbol,
                "display_name": display,
                "description": description,
                "category": "Commodities",
                "market_types": ["otc"],
                "trading_hours": "24/7 OTC"
            })
        
        # Format Indices
        for category, indices in self.indices.items():
            for symbol, display, description in indices:
                formatted_assets["indices"].append({
                    "symbol": symbol,
                    "display_name": display,
                    "description": description,
                    "category": category.replace("_", " ").title(),
                    "market_types": ["regular", "otc"],
                    "trading_hours": "Regular Market Hours + 24/7 OTC"
                })
        
        return formatted_assets
    
    def get_symbols_list(self) -> List[str]:
        """Get a simple list of all available symbols"""
        symbols = []
        
        # Add all forex pairs
        for category, pairs in self.forex_pairs.items():
            symbols.extend([symbol for symbol, _, _ in pairs])
        
        # Add cryptocurrencies
        symbols.extend([symbol for symbol, _, _ in self.cryptocurrencies])
        
        # Add stocks
        for category, stocks in self.stocks.items():
            symbols.extend([symbol for symbol, _, _ in stocks])
        
        # Add commodities
        symbols.extend([symbol for symbol, _, _ in self.commodities])
        
        # Add indices
        for category, indices in self.indices.items():
            symbols.extend([symbol for symbol, _, _ in indices])
        
        return sorted(symbols)
    
    def get_otc_symbols(self) -> List[str]:
        """Get all symbols that have OTC variants"""
        otc_symbols = []
        
        # All forex pairs have OTC
        for category, pairs in self.forex_pairs.items():
            otc_symbols.extend([f"{symbol}_OTC" for symbol, _, _ in pairs])
        
        # All crypto are OTC only
        otc_symbols.extend([f"{symbol}_OTC" for symbol, _, _ in self.cryptocurrencies])
        
        # Stocks have OTC variants
        for category, stocks in self.stocks.items():
            otc_symbols.extend([f"{symbol}_OTC" for symbol, _, _ in stocks])
        
        # Commodities are OTC only (already have OTC in name)
        otc_symbols.extend([symbol for symbol, _, _ in self.commodities])
        
        # Indices have OTC variants
        for category, indices in self.indices.items():
            otc_symbols.extend([f"{symbol}_OTC" for symbol, _, _ in indices])
        
        return sorted(otc_symbols)

# Global instance
pocket_option_assets = PocketOptionAssets()