"""
Pocket Option Real-Time Market Data Service
============================================

Fetches live market data directly from Pocket Option platform
for accurate signal generation using the same data traders see.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from pocket_option_ws import PocketOptionWebSocket, get_connection, connect_pocket_option

logger = logging.getLogger(__name__)


@dataclass
class PocketOptionCandle:
    """Single candle data from Pocket Option"""
    timestamp: int  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }


@dataclass  
class PocketOptionMarketData:
    """Real-time market data from Pocket Option"""
    symbol: str
    current_price: float
    bid: float = 0
    ask: float = 0
    spread: float = 0
    payout: float = 0  # Current payout percentage
    is_open: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    candles: List[PocketOptionCandle] = field(default_factory=list)
    
    # Technical indicators calculated from candles
    rsi: Optional[float] = None
    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_percent: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    atr: Optional[float] = None
    
    # Trend analysis
    trend_direction: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    trend_strength: float = 0  # 0-100
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "payout": self.payout,
            "is_open": self.is_open,
            "timestamp": self.timestamp.isoformat(),
            "candles_count": len(self.candles),
            "indicators": {
                "rsi": self.rsi,
                "sma_5": self.sma_5,
                "sma_10": self.sma_10,
                "sma_20": self.sma_20,
                "ema_9": self.ema_9,
                "ema_21": self.ema_21,
                "macd": self.macd,
                "macd_signal": self.macd_signal,
                "macd_histogram": self.macd_histogram,
                "bb_upper": self.bb_upper,
                "bb_middle": self.bb_middle,
                "bb_lower": self.bb_lower,
                "bb_percent": self.bb_percent,
                "stoch_k": self.stoch_k,
                "stoch_d": self.stoch_d,
                "atr": self.atr
            },
            "trend": {
                "direction": self.trend_direction,
                "strength": self.trend_strength
            }
        }


class PocketOptionMarketDataService:
    """
    Real-time market data service for Pocket Option
    
    Subscribes to price updates and maintains candle history
    for technical analysis and signal generation.
    """
    
    # Pocket Option asset IDs mapping
    ASSET_IDS = {
        # Forex pairs
        "EURUSD": 1, "EURUSD_OTC": 2,
        "GBPUSD": 3, "GBPUSD_OTC": 4,
        "USDJPY": 5, "USDJPY_OTC": 6,
        "AUDUSD": 7, "AUDUSD_OTC": 8,
        "USDCAD": 9, "USDCAD_OTC": 10,
        "USDCHF": 11, "USDCHF_OTC": 12,
        "NZDUSD": 13, "NZDUSD_OTC": 14,
        "EURJPY": 15, "EURJPY_OTC": 16,
        "GBPJPY": 17, "GBPJPY_OTC": 18,
        "EURGBP": 19, "EURGBP_OTC": 20,
        "AUDJPY": 21, "AUDJPY_OTC": 22,
        "EURAUD": 23, "EURAUD_OTC": 24,
        "EURCAD": 25, "EURCAD_OTC": 26,
        # Crypto
        "BTCUSD": 100, "BTCUSD_OTC": 101,
        "ETHUSD": 102, "ETHUSD_OTC": 103,
        "LTCUSD": 104, "LTCUSD_OTC": 105,
        # Commodities
        "XAUUSD": 200, "XAUUSD_OTC": 201,  # Gold
        "XAGUSD": 202, "XAGUSD_OTC": 203,  # Silver
    }
    
    # Timeframe to seconds mapping
    TIMEFRAMES = {
        "5s": 5,
        "10s": 10,
        "15s": 15,
        "30s": 30,
        "1m": 60,
        "2m": 120,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "1h": 3600
    }
    
    def __init__(self):
        self.connection: Optional[PocketOptionWebSocket] = None
        self.market_data: Dict[str, PocketOptionMarketData] = {}
        self.candle_history: Dict[str, Dict[str, List[PocketOptionCandle]]] = {}  # symbol -> timeframe -> candles
        self.price_callbacks: List[Callable] = []
        self.subscribed_assets: List[str] = []
        self._running = False
        self._price_buffer: Dict[str, List[Dict]] = {}  # Buffer for building candles
        
    async def connect(self, ssid: str, is_demo: bool = True) -> bool:
        """Connect to Pocket Option"""
        try:
            result = await connect_pocket_option(ssid, is_demo)
            if result.get("success"):
                self.connection = get_connection()
                if self.connection:
                    self.connection.add_message_handler(self._handle_message)
                    self._running = True
                    logger.info("✅ Connected to Pocket Option market data")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def _handle_message(self, msg: str):
        """Handle incoming WebSocket messages"""
        try:
            msg_str = str(msg)
            
            # Price update message: 42["q",{...}] or 42["price",{...}]
            if msg_str.startswith('42') and ('"q"' in msg_str or '"price"' in msg_str or '"candle"' in msg_str):
                data = json.loads(msg_str[2:])
                if isinstance(data, list) and len(data) >= 2:
                    event_type = data[0]
                    payload = data[1]
                    
                    if event_type in ["q", "price", "candle", "candles"]:
                        await self._process_price_update(payload)
                    
            # Asset info message
            elif msg_str.startswith('42') and '"assets"' in msg_str:
                data = json.loads(msg_str[2:])
                if isinstance(data, list) and len(data) >= 2:
                    await self._process_assets_info(data[1])
                    
        except Exception as e:
            logger.debug(f"Message handling error: {e}")
    
    async def _process_price_update(self, payload: Dict):
        """Process price update from Pocket Option"""
        try:
            # Extract symbol from asset ID
            asset_id = payload.get("asset") or payload.get("id") or payload.get("a")
            price = payload.get("price") or payload.get("value") or payload.get("p") or payload.get("c")
            timestamp = payload.get("timestamp") or payload.get("time") or payload.get("t") or int(time.time())
            
            if not asset_id or not price:
                return
            
            # Find symbol name from ID
            symbol = self._get_symbol_from_id(asset_id)
            if not symbol:
                symbol = str(asset_id)
            
            price = float(price)
            
            # Update market data
            if symbol not in self.market_data:
                self.market_data[symbol] = PocketOptionMarketData(
                    symbol=symbol,
                    current_price=price
                )
            
            self.market_data[symbol].current_price = price
            self.market_data[symbol].timestamp = datetime.now(timezone.utc)
            
            # Add to price buffer for candle building
            if symbol not in self._price_buffer:
                self._price_buffer[symbol] = []
            
            self._price_buffer[symbol].append({
                "price": price,
                "timestamp": timestamp
            })
            
            # Keep buffer manageable (last 1000 ticks)
            if len(self._price_buffer[symbol]) > 1000:
                self._price_buffer[symbol] = self._price_buffer[symbol][-500:]
            
            # Build candles from buffer periodically
            await self._build_candles_from_buffer(symbol)
            
            # Call price callbacks
            for callback in self.price_callbacks:
                try:
                    await callback(symbol, price, timestamp)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Price update processing error: {e}")
    
    async def _process_assets_info(self, assets: Dict):
        """Process assets info (payout, open status, etc.)"""
        try:
            for asset_id, info in assets.items():
                symbol = self._get_symbol_from_id(int(asset_id))
                if symbol and symbol in self.market_data:
                    self.market_data[symbol].payout = info.get("payout", 0)
                    self.market_data[symbol].is_open = info.get("is_open", True)
        except Exception as e:
            logger.debug(f"Assets info processing error: {e}")
    
    def _get_symbol_from_id(self, asset_id: int) -> Optional[str]:
        """Get symbol name from Pocket Option asset ID"""
        for symbol, aid in self.ASSET_IDS.items():
            if aid == asset_id:
                return symbol
        return None
    
    def _get_id_from_symbol(self, symbol: str) -> Optional[int]:
        """Get Pocket Option asset ID from symbol name"""
        # Normalize symbol
        symbol_upper = symbol.upper().replace("-", "").replace("/", "").replace("_", "")
        
        # Try exact match first
        if symbol.upper() in self.ASSET_IDS:
            return self.ASSET_IDS[symbol.upper()]
        
        # Try without OTC suffix
        for name, aid in self.ASSET_IDS.items():
            if name.replace("_OTC", "") == symbol_upper.replace("OTC", ""):
                return aid
        
        return None
    
    async def _build_candles_from_buffer(self, symbol: str):
        """Build candles from price buffer"""
        if symbol not in self._price_buffer or len(self._price_buffer[symbol]) < 2:
            return
        
        buffer = self._price_buffer[symbol]
        
        # Build 5-second candles
        await self._build_timeframe_candles(symbol, "5s", 5)
        
        # Build 1-minute candles  
        await self._build_timeframe_candles(symbol, "1m", 60)
    
    async def _build_timeframe_candles(self, symbol: str, timeframe: str, seconds: int):
        """Build candles for a specific timeframe"""
        if symbol not in self._price_buffer:
            return
        
        buffer = self._price_buffer[symbol]
        if len(buffer) < 2:
            return
        
        # Initialize candle history
        if symbol not in self.candle_history:
            self.candle_history[symbol] = {}
        if timeframe not in self.candle_history[symbol]:
            self.candle_history[symbol][timeframe] = []
        
        # Group prices by candle period
        current_time = int(time.time())
        candle_start = (current_time // seconds) * seconds
        
        # Get prices for current candle period
        candle_prices = [p["price"] for p in buffer if p["timestamp"] >= candle_start]
        
        if candle_prices:
            candle = PocketOptionCandle(
                timestamp=candle_start,
                open=candle_prices[0],
                high=max(candle_prices),
                low=min(candle_prices),
                close=candle_prices[-1],
                volume=len(candle_prices)
            )
            
            # Update or add candle
            candles = self.candle_history[symbol][timeframe]
            if candles and candles[-1].timestamp == candle_start:
                candles[-1] = candle
            else:
                candles.append(candle)
            
            # Keep last 200 candles
            if len(candles) > 200:
                self.candle_history[symbol][timeframe] = candles[-100:]
    
    async def subscribe_asset(self, symbol: str) -> bool:
        """Subscribe to price updates for an asset"""
        try:
            if not self.connection or not self.connection.state.connected:
                logger.warning("Not connected to Pocket Option")
                return False
            
            asset_id = self._get_id_from_symbol(symbol)
            if not asset_id:
                logger.warning(f"Unknown asset: {symbol}")
                return False
            
            # Send subscription message
            # Format: 42["subscribe",{"asset":ID}]
            msg = f'42["subscribeMessage",{{"asset":{asset_id},"period":60}}]'
            await self.connection.send(msg)
            
            self.subscribed_assets.append(symbol)
            logger.info(f"📊 Subscribed to {symbol} (ID: {asset_id})")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False
    
    async def get_candles(self, symbol: str, timeframe: str = "1m", count: int = 100) -> List[Dict]:
        """Get historical candles for a symbol"""
        try:
            if not self.connection or not self.connection.state.connected:
                logger.warning("Not connected to Pocket Option")
                return []
            
            asset_id = self._get_id_from_symbol(symbol)
            if not asset_id:
                return []
            
            # Request candle history
            # Format: 42["history",{"asset":ID,"period":60,"count":100}]
            period_seconds = self.TIMEFRAMES.get(timeframe, 60)
            msg = f'42["history",{{"asset":{asset_id},"period":{period_seconds},"count":{count}}}]'
            await self.connection.send(msg)
            
            # Wait for response (candles will be processed by message handler)
            await asyncio.sleep(1)
            
            # Return cached candles
            if symbol in self.candle_history and timeframe in self.candle_history[symbol]:
                return [c.to_dict() for c in self.candle_history[symbol][timeframe][-count:]]
            
            return []
            
        except Exception as e:
            logger.error(f"Get candles error: {e}")
            return []
    
    def get_market_data(self, symbol: str) -> Optional[PocketOptionMarketData]:
        """Get current market data for a symbol"""
        return self.market_data.get(symbol)
    
    def calculate_indicators(self, symbol: str, timeframe: str = "1m") -> Dict[str, Any]:
        """Calculate technical indicators from candle data"""
        try:
            if symbol not in self.candle_history:
                return {}
            if timeframe not in self.candle_history[symbol]:
                return {}
            
            candles = self.candle_history[symbol][timeframe]
            if len(candles) < 20:
                return {}
            
            # Convert to DataFrame
            df = pd.DataFrame([c.to_dict() for c in candles])
            closes = df['close'].astype(float)
            highs = df['high'].astype(float)
            lows = df['low'].astype(float)
            
            indicators = {}
            
            # RSI
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            indicators['rsi'] = float(100 - (100 / (1 + rs.iloc[-1]))) if not pd.isna(rs.iloc[-1]) else None
            
            # SMAs
            indicators['sma_5'] = float(closes.rolling(5).mean().iloc[-1])
            indicators['sma_10'] = float(closes.rolling(10).mean().iloc[-1])
            indicators['sma_20'] = float(closes.rolling(20).mean().iloc[-1])
            
            # EMAs
            indicators['ema_9'] = float(closes.ewm(span=9).mean().iloc[-1])
            indicators['ema_21'] = float(closes.ewm(span=21).mean().iloc[-1])
            
            # MACD
            ema_12 = closes.ewm(span=12).mean()
            ema_26 = closes.ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9).mean()
            indicators['macd'] = float(macd_line.iloc[-1])
            indicators['macd_signal'] = float(signal_line.iloc[-1])
            indicators['macd_histogram'] = float((macd_line - signal_line).iloc[-1])
            
            # Bollinger Bands
            sma_20 = closes.rolling(20).mean()
            std_20 = closes.rolling(20).std()
            indicators['bb_upper'] = float(sma_20.iloc[-1] + 2 * std_20.iloc[-1])
            indicators['bb_middle'] = float(sma_20.iloc[-1])
            indicators['bb_lower'] = float(sma_20.iloc[-1] - 2 * std_20.iloc[-1])
            bb_range = indicators['bb_upper'] - indicators['bb_lower']
            if bb_range > 0:
                indicators['bb_percent'] = float((closes.iloc[-1] - indicators['bb_lower']) / bb_range)
            
            # Stochastic
            low_14 = lows.rolling(14).min()
            high_14 = highs.rolling(14).max()
            stoch_k = 100 * (closes - low_14) / (high_14 - low_14)
            indicators['stoch_k'] = float(stoch_k.iloc[-1])
            indicators['stoch_d'] = float(stoch_k.rolling(3).mean().iloc[-1])
            
            # ATR
            tr = pd.concat([
                highs - lows,
                (highs - closes.shift()).abs(),
                (lows - closes.shift()).abs()
            ], axis=1).max(axis=1)
            indicators['atr'] = float(tr.rolling(14).mean().iloc[-1])
            
            # Trend Analysis
            current_price = closes.iloc[-1]
            bullish_count = 0
            bearish_count = 0
            
            # SMA alignment
            if current_price > indicators['sma_5'] > indicators['sma_10'] > indicators['sma_20']:
                bullish_count += 2
            elif current_price < indicators['sma_5'] < indicators['sma_10'] < indicators['sma_20']:
                bearish_count += 2
            
            # RSI
            if indicators['rsi']:
                if indicators['rsi'] < 30:
                    bullish_count += 1  # Oversold, expect reversal up
                elif indicators['rsi'] > 70:
                    bearish_count += 1  # Overbought, expect reversal down
                elif indicators['rsi'] > 50:
                    bullish_count += 0.5
                else:
                    bearish_count += 0.5
            
            # MACD
            if indicators['macd_histogram'] > 0:
                bullish_count += 1
            else:
                bearish_count += 1
            
            # EMA cross
            if indicators['ema_9'] > indicators['ema_21']:
                bullish_count += 1
            else:
                bearish_count += 1
            
            # Determine trend
            total = bullish_count + bearish_count
            if bullish_count > bearish_count:
                indicators['trend_direction'] = "BULLISH"
                indicators['trend_strength'] = (bullish_count / total) * 100 if total > 0 else 50
            elif bearish_count > bullish_count:
                indicators['trend_direction'] = "BEARISH"  
                indicators['trend_strength'] = (bearish_count / total) * 100 if total > 0 else 50
            else:
                indicators['trend_direction'] = "NEUTRAL"
                indicators['trend_strength'] = 50
            
            return indicators
            
        except Exception as e:
            logger.error(f"Indicator calculation error: {e}")
            return {}
    
    def generate_signal(self, symbol: str, timeframe: str = "1m") -> Dict[str, Any]:
        """Generate trading signal from Pocket Option market data"""
        try:
            indicators = self.calculate_indicators(symbol, timeframe)
            if not indicators:
                return {"success": False, "message": "Insufficient data"}
            
            market_data = self.get_market_data(symbol)
            current_price = market_data.current_price if market_data else 0
            
            # Calculate signal
            direction = "HOLD"
            confidence = 50
            reasons = []
            
            trend = indicators.get('trend_direction', 'NEUTRAL')
            strength = indicators.get('trend_strength', 50)
            
            # Strong trend signals
            if trend == "BULLISH" and strength >= 60:
                direction = "CALL"
                confidence = min(95, 60 + strength * 0.35)
                reasons.append(f"Bullish trend ({strength:.0f}% strength)")
            elif trend == "BEARISH" and strength >= 60:
                direction = "PUT"
                confidence = min(95, 60 + strength * 0.35)
                reasons.append(f"Bearish trend ({strength:.0f}% strength)")
            
            # RSI signals
            rsi = indicators.get('rsi')
            if rsi:
                if rsi < 25:
                    if direction != "PUT":
                        direction = "CALL"
                        confidence = max(confidence, 75)
                    reasons.append(f"RSI oversold ({rsi:.1f})")
                elif rsi > 75:
                    if direction != "CALL":
                        direction = "PUT"
                        confidence = max(confidence, 75)
                    reasons.append(f"RSI overbought ({rsi:.1f})")
            
            # Bollinger Band signals
            bb_percent = indicators.get('bb_percent')
            if bb_percent is not None:
                if bb_percent < 0.1:
                    if direction != "PUT":
                        direction = "CALL"
                        confidence = max(confidence, 70)
                    reasons.append(f"Price at lower BB ({bb_percent:.2f})")
                elif bb_percent > 0.9:
                    if direction != "CALL":
                        direction = "PUT"
                        confidence = max(confidence, 70)
                    reasons.append(f"Price at upper BB ({bb_percent:.2f})")
            
            # MACD confirmation
            macd_hist = indicators.get('macd_histogram')
            if macd_hist:
                if macd_hist > 0 and direction == "CALL":
                    confidence += 5
                    reasons.append("MACD bullish")
                elif macd_hist < 0 and direction == "PUT":
                    confidence += 5
                    reasons.append("MACD bearish")
            
            confidence = min(95, confidence)
            
            return {
                "success": True,
                "symbol": symbol,
                "direction": direction,
                "confidence": confidence,
                "current_price": current_price,
                "indicators": indicators,
                "reasons": reasons,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "pocket_option_realtime"
            }
            
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return {"success": False, "error": str(e)}
    
    def add_price_callback(self, callback: Callable):
        """Add callback for price updates"""
        self.price_callbacks.append(callback)
    
    async def disconnect(self):
        """Disconnect from Pocket Option"""
        self._running = False
        self.subscribed_assets = []
        self.market_data = {}


# Global instance
po_market_data = PocketOptionMarketDataService()


async def get_po_market_data_service() -> PocketOptionMarketDataService:
    """Get the Pocket Option market data service instance"""
    return po_market_data
