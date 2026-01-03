"""
Comprehensive Backtesting Service
=================================

Features:
- Historical data fetching from Yahoo Finance (forex/stocks) and CryptoCompare (crypto)
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
from uuid import uuid4

logger = logging.getLogger(__name__)

# Yahoo Finance symbol mappings for forex
YAHOO_FOREX_SYMBOLS = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'USDCHF': 'USDCHF=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'NZDUSD': 'NZDUSD=X',
    'EURGBP': 'EURGBP=X',
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'EUR_USD': 'EURUSD=X',
    'GBP_USD': 'GBPUSD=X',
    'USD_JPY': 'USDJPY=X',
    'AUD_USD': 'AUDUSD=X',
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
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HistoricalDataFetcher:
    """Fetches historical market data from various sources"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache
    
    async def fetch_yahoo_data(self, symbol: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """Fetch historical data from Yahoo Finance"""
        try:
            import subprocess
            import pickle
            import base64
            import tempfile
            import os
            
            # Map symbol to Yahoo format
            yahoo_symbol = YAHOO_FOREX_SYMBOLS.get(symbol.upper(), symbol)
            if not yahoo_symbol.endswith('=X') and symbol.upper() in YAHOO_FOREX_SYMBOLS:
                yahoo_symbol = YAHOO_FOREX_SYMBOLS[symbol.upper()]
            
            # Map interval and period
            interval_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "60m", "4h": "60m", "1d": "1d"
            }
            yf_interval = interval_map.get(interval, "60m")
            
            period_map = {7: '7d', 14: '14d', 30: '1mo', 60: '2mo', 90: '3mo'}
            period = '1mo'
            for p in sorted(period_map.keys()):
                if days <= p:
                    period = period_map[p]
                    break
            
            # Run yfinance in subprocess to avoid async context issues
            script = f'''
import yfinance as yf
import pickle
import sys

ticker = yf.Ticker("{yahoo_symbol}")
df = ticker.history(period="{period}", interval="{yf_interval}")
if df is not None and not df.empty:
    # Standardize columns
    df = df.rename(columns={{"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}})
    df = df[["open", "high", "low", "close", "volume"]].copy()
    # Reset index to avoid datetime serialization issues
    df = df.reset_index()
    df["Datetime"] = df["Datetime"].astype(str)
    sys.stdout.buffer.write(pickle.dumps(df))
else:
    sys.stdout.buffer.write(pickle.dumps(None))
'''
            
            # Execute in subprocess
            result = await asyncio.to_thread(
                subprocess.run,
                ['python3', '-c', script],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Subprocess error for {yahoo_symbol}: {result.stderr.decode()}")
                return None
            
            df = pickle.loads(result.stdout)
            
            if df is None or len(df) == 0:
                logger.warning(f"No data returned for {yahoo_symbol}")
                return None
            
            # Restore datetime index
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            df = df.set_index('Datetime')
            
            logger.info(f"Fetched {len(df)} candles for {yahoo_symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
                    
                    logger.info(f"Fetched {len(df)} candles for {base_symbol}")
                    return df
                    
        except Exception as e:
            logger.error(f"Error fetching crypto data for {symbol}: {e}")
            return None
    
    async def fetch_historical_data(self, symbol: str, asset_type: str, days: int = 30, interval: str = "1h") -> Optional[pd.DataFrame]:
        """Fetch historical data based on asset type"""
        cache_key = f"{symbol}_{asset_type}_{days}_{interval}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                return cached_data
        
        df = None
        
        if asset_type == AssetType.CRYPTO or symbol.upper() in CRYPTO_SYMBOLS or 'USDT' in symbol.upper():
            df = await self.fetch_crypto_data(symbol, days, interval)
        else:
            # Use Yahoo Finance for forex and stocks
            df = await self.fetch_yahoo_data(symbol, days, interval)
        
        if df is not None:
            self.cache[cache_key] = (df, datetime.now())
        
        return df


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
    
    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        macd_line = ema12 - ema26
        signal_line = self._calculate_ema(macd_line, 9)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = self._calculate_sma(prices, period)
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic oscillator"""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        k = 100 * (df['close'] - low_min) / (high_max - low_min)
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
        elif symbol_upper in [s.replace('_', '') for s in YAHOO_FOREX_SYMBOLS.keys()] or '=' in symbol:
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
        
        for asset in config.assets:
            asset_type = self._determine_asset_type(asset)
            
            for timeframe in config.timeframes:
                # Fetch historical data
                df = await self.data_fetcher.fetch_historical_data(
                    asset, asset_type, config.days, timeframe
                )
                
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
            "forex": list(YAHOO_FOREX_SYMBOLS.keys()),
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
