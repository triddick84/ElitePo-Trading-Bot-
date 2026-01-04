"""
Historical Data Collector Service
==================================

Captures and stores REAL market data from Pocket Option via WebSocket.
This is the foundation for training high-accuracy AI/ML models.

Key Features:
- Stores 5s, 1m, 5m candle data in MongoDB
- Aggregates tick data into proper OHLCV candles
- Supports multiple assets simultaneously
- Provides data retrieval for ML training
- Tracks data quality metrics

Author: GPT Signal Bot
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import json
import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


@dataclass
class CandleData:
    """Single candle data point"""
    asset: str
    timeframe: str  # '5s', '1m', '5m', '15m', '1h'
    timestamp: int  # Unix timestamp (candle open time)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    tick_count: int = 0  # Number of ticks in this candle
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "asset": self.asset,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DataCollectionStats:
    """Statistics for data collection"""
    asset: str
    timeframe: str
    total_candles: int = 0
    first_candle_time: Optional[datetime] = None
    last_candle_time: Optional[datetime] = None
    gaps_detected: int = 0
    avg_tick_count: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "asset": self.asset,
            "timeframe": self.timeframe,
            "total_candles": self.total_candles,
            "first_candle_time": self.first_candle_time.isoformat() if self.first_candle_time else None,
            "last_candle_time": self.last_candle_time.isoformat() if self.last_candle_time else None,
            "gaps_detected": self.gaps_detected,
            "avg_tick_count": self.avg_tick_count
        }


# Timeframe to seconds mapping
TIMEFRAME_SECONDS = {
    '5s': 5,
    '15s': 15,
    '30s': 30,
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '1h': 3600
}


class HistoricalDataCollector:
    """
    Service for collecting and storing real market data from Pocket Option.
    
    This service:
    1. Receives tick/candle data from WebSocket connections
    2. Aggregates ticks into proper OHLCV candles
    3. Stores data in MongoDB for ML training
    4. Provides data retrieval APIs
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.candles_collection = db.historical_candles
        self.stats_collection = db.collection_stats
        
        # In-memory candle buffers for aggregation
        # Structure: {asset: {timeframe: current_candle_dict}}
        self.current_candles: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(dict))
        
        # Track last saved timestamp per asset/timeframe
        self.last_saved: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # Collection settings
        self.enabled = False
        self.collecting_assets: List[str] = []
        self.collecting_timeframes: List[str] = ['5s', '1m', '5m']
        
        # Stats tracking
        self.session_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        logger.info("📊 Historical Data Collector initialized")
    
    async def initialize(self):
        """Initialize the collector and create indexes"""
        # Create compound index for efficient queries
        await self.candles_collection.create_index([
            ("asset", 1),
            ("timeframe", 1),
            ("timestamp", 1)
        ], unique=True)
        
        await self.candles_collection.create_index([
            ("asset", 1),
            ("timeframe", 1),
            ("created_at", -1)
        ])
        
        logger.info("✅ Historical data indexes created")
    
    def start_collection(self, assets: List[str] = None, timeframes: List[str] = None):
        """Start collecting data for specified assets and timeframes"""
        self.enabled = True
        if assets:
            self.collecting_assets = assets
        if timeframes:
            self.collecting_timeframes = timeframes
        
        logger.info(f"🟢 Data collection STARTED")
        logger.info(f"   Assets: {self.collecting_assets or 'ALL'}")
        logger.info(f"   Timeframes: {self.collecting_timeframes}")
    
    def stop_collection(self):
        """Stop collecting data"""
        self.enabled = False
        logger.info("🔴 Data collection STOPPED")
    
    def _get_candle_timestamp(self, tick_time: int, timeframe: str) -> int:
        """Get the candle open timestamp for a given tick time"""
        period_seconds = TIMEFRAME_SECONDS.get(timeframe, 60)
        return (tick_time // period_seconds) * period_seconds
    
    async def process_tick(self, asset: str, timestamp: int, price: float, volume: float = 0.0):
        """
        Process a single tick/price update from WebSocket.
        
        This is called for each price update received from Pocket Option.
        The tick is aggregated into candles for each configured timeframe.
        """
        if not self.enabled:
            return
        
        # Filter by asset if specified
        if self.collecting_assets and asset not in self.collecting_assets:
            return
        
        for timeframe in self.collecting_timeframes:
            await self._aggregate_tick(asset, timestamp, price, volume, timeframe)
    
    async def _aggregate_tick(self, asset: str, timestamp: int, price: float, 
                              volume: float, timeframe: str):
        """Aggregate a tick into the appropriate candle"""
        candle_ts = self._get_candle_timestamp(timestamp, timeframe)
        current = self.current_candles[asset][timeframe]
        
        if not current or current.get('timestamp') != candle_ts:
            # Save previous candle if exists
            if current and current.get('timestamp'):
                await self._save_candle(asset, timeframe, current)
            
            # Start new candle
            self.current_candles[asset][timeframe] = {
                'timestamp': candle_ts,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'tick_count': 1
            }
        else:
            # Update current candle
            current['close'] = price
            current['high'] = max(current['high'], price)
            current['low'] = min(current['low'], price)
            current['volume'] += volume
            current['tick_count'] += 1
    
    async def process_candle(self, asset: str, candle: Dict[str, Any], timeframe: str = '1m'):
        """
        Process a complete candle received from WebSocket.
        
        This is called when Pocket Option sends a complete candle (on new candle formation).
        """
        if not self.enabled:
            return
        
        if self.collecting_assets and asset not in self.collecting_assets:
            return
        
        if timeframe not in self.collecting_timeframes:
            return
        
        await self._save_candle(asset, timeframe, candle)
    
    async def process_history(self, asset: str, history_data: List[Tuple], 
                              candles_data: List = None, period: int = 60):
        """
        Process historical data batch from WebSocket 'history' message.
        
        This captures the initial historical data sent when connecting to an asset.
        """
        if not self.enabled:
            return
        
        # Determine timeframe from period
        timeframe = '1m'  # default
        for tf, seconds in TIMEFRAME_SECONDS.items():
            if seconds == period:
                timeframe = tf
                break
        
        if timeframe not in self.collecting_timeframes:
            return
        
        saved_count = 0
        
        # Process history tuples (timestamp, price)
        for tstamp, price in history_data:
            ts = int(float(tstamp))
            candle = {
                'timestamp': ts,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': 0,
                'tick_count': 1
            }
            if await self._save_candle(asset, timeframe, candle, upsert=True):
                saved_count += 1
        
        # Process full candles if provided
        if candles_data:
            for c in candles_data:
                candle = {
                    'timestamp': int(c[0]),
                    'open': c[1],
                    'close': c[2],
                    'high': c[3],
                    'low': c[4],
                    'volume': 0,
                    'tick_count': 1
                }
                if await self._save_candle(asset, timeframe, candle, upsert=True):
                    saved_count += 1
        
        logger.info(f"📥 Imported {saved_count} historical candles for {asset} ({timeframe})")
        return saved_count
    
    async def _save_candle(self, asset: str, timeframe: str, candle: Dict, 
                           upsert: bool = False) -> bool:
        """Save a candle to MongoDB"""
        try:
            # Avoid duplicate saves
            ts = candle.get('timestamp', 0)
            if ts <= self.last_saved[asset][timeframe] and not upsert:
                return False
            
            candle_doc = {
                "asset": asset,
                "timeframe": timeframe,
                "timestamp": ts,
                "open": float(candle.get('open', 0)),
                "high": float(candle.get('high', 0)),
                "low": float(candle.get('low', 0)),
                "close": float(candle.get('close', 0)),
                "volume": float(candle.get('volume', 0)),
                "tick_count": int(candle.get('tick_count', 1)),
                "created_at": datetime.now(timezone.utc)
            }
            
            if upsert:
                await self.candles_collection.update_one(
                    {"asset": asset, "timeframe": timeframe, "timestamp": ts},
                    {"$set": candle_doc},
                    upsert=True
                )
            else:
                await self.candles_collection.insert_one(candle_doc)
            
            self.last_saved[asset][timeframe] = ts
            self.session_stats[asset][timeframe] += 1
            
            return True
            
        except Exception as e:
            # Duplicate key errors are expected and okay
            if "duplicate key" not in str(e).lower():
                logger.error(f"Error saving candle: {e}")
            return False
    
    async def get_candles(self, asset: str, timeframe: str, 
                          start_time: datetime = None, end_time: datetime = None,
                          limit: int = 1000) -> List[Dict]:
        """
        Retrieve historical candles from MongoDB.
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc')
            timeframe: Timeframe ('5s', '1m', '5m', etc.)
            start_time: Optional start datetime filter
            end_time: Optional end datetime filter
            limit: Maximum number of candles to return
        
        Returns:
            List of candle dictionaries sorted by timestamp
        """
        query = {"asset": asset, "timeframe": timeframe}
        
        if start_time:
            query["timestamp"] = {"$gte": int(start_time.timestamp())}
        if end_time:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = int(end_time.timestamp())
            else:
                query["timestamp"] = {"$lte": int(end_time.timestamp())}
        
        cursor = self.candles_collection.find(
            query, {"_id": 0}
        ).sort("timestamp", 1).limit(limit)
        
        candles = await cursor.to_list(length=limit)
        return candles
    
    async def get_training_data(self, asset: str, timeframe: str,
                                 days: int = 7) -> Optional[Dict]:
        """
        Get data formatted for ML training.
        
        Returns data as pandas-compatible dict with arrays for each OHLCV column.
        """
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        candles = await self.get_candles(asset, timeframe, start_time=start_time, limit=50000)
        
        if not candles or len(candles) < 100:
            logger.warning(f"Insufficient data for {asset} {timeframe}: {len(candles)} candles")
            return None
        
        # Convert to arrays
        data = {
            "timestamp": [c["timestamp"] for c in candles],
            "open": [c["open"] for c in candles],
            "high": [c["high"] for c in candles],
            "low": [c["low"] for c in candles],
            "close": [c["close"] for c in candles],
            "volume": [c["volume"] for c in candles],
        }
        
        return {
            "asset": asset,
            "timeframe": timeframe,
            "candle_count": len(candles),
            "start_timestamp": candles[0]["timestamp"],
            "end_timestamp": candles[-1]["timestamp"],
            "data": data
        }
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected data"""
        stats = {}
        
        # Get unique asset/timeframe combinations
        pipeline = [
            {"$group": {
                "_id": {"asset": "$asset", "timeframe": "$timeframe"},
                "count": {"$sum": 1},
                "first_ts": {"$min": "$timestamp"},
                "last_ts": {"$max": "$timestamp"},
                "avg_ticks": {"$avg": "$tick_count"}
            }}
        ]
        
        async for doc in self.candles_collection.aggregate(pipeline):
            key = f"{doc['_id']['asset']}_{doc['_id']['timeframe']}"
            stats[key] = {
                "asset": doc['_id']['asset'],
                "timeframe": doc['_id']['timeframe'],
                "total_candles": doc['count'],
                "first_candle": datetime.fromtimestamp(doc['first_ts'], tz=timezone.utc).isoformat(),
                "last_candle": datetime.fromtimestamp(doc['last_ts'], tz=timezone.utc).isoformat(),
                "avg_tick_count": round(doc['avg_ticks'], 2)
            }
        
        # Add session stats
        session = {}
        for asset, timeframes in self.session_stats.items():
            for tf, count in timeframes.items():
                session[f"{asset}_{tf}"] = count
        
        return {
            "collection_enabled": self.enabled,
            "collecting_assets": self.collecting_assets,
            "collecting_timeframes": self.collecting_timeframes,
            "database_stats": stats,
            "session_stats": session
        }
    
    async def get_data_quality_report(self, asset: str, timeframe: str, 
                                       days: int = 1) -> Dict[str, Any]:
        """
        Analyze data quality for an asset/timeframe.
        
        Checks for:
        - Data gaps (missing candles)
        - Price anomalies
        - Low tick counts
        """
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        candles = await self.get_candles(asset, timeframe, start_time=start_time, limit=50000)
        
        if not candles:
            return {"error": "No data available"}
        
        period_seconds = TIMEFRAME_SECONDS.get(timeframe, 60)
        
        # Check for gaps
        gaps = []
        prev_ts = None
        for candle in candles:
            if prev_ts:
                expected_next = prev_ts + period_seconds
                if candle["timestamp"] != expected_next:
                    gap_size = (candle["timestamp"] - prev_ts) // period_seconds - 1
                    if gap_size > 0:
                        gaps.append({
                            "start": prev_ts,
                            "end": candle["timestamp"],
                            "missing_candles": gap_size
                        })
            prev_ts = candle["timestamp"]
        
        # Price statistics
        closes = [c["close"] for c in candles]
        tick_counts = [c["tick_count"] for c in candles]
        
        return {
            "asset": asset,
            "timeframe": timeframe,
            "total_candles": len(candles),
            "period_analyzed_hours": days * 24,
            "expected_candles": int((days * 24 * 3600) / period_seconds),
            "gaps_found": len(gaps),
            "total_missing_candles": sum(g["missing_candles"] for g in gaps),
            "price_stats": {
                "min": min(closes),
                "max": max(closes),
                "mean": sum(closes) / len(closes),
                "std": float(np.std(closes))
            },
            "tick_stats": {
                "min": min(tick_counts),
                "max": max(tick_counts),
                "mean": sum(tick_counts) / len(tick_counts)
            },
            "data_completeness_pct": round(
                len(candles) / max(1, int((days * 24 * 3600) / period_seconds)) * 100, 2
            ),
            "gaps": gaps[:10]  # First 10 gaps
        }
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove data older than specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        cutoff_ts = int(cutoff.timestamp())
        
        result = await self.candles_collection.delete_many(
            {"timestamp": {"$lt": cutoff_ts}}
        )
        
        logger.info(f"🗑️ Cleaned up {result.deleted_count} old candles (older than {days_to_keep} days)")
        return result.deleted_count


# Singleton instance
_historical_data_collector: Optional[HistoricalDataCollector] = None


def get_historical_data_collector(db: AsyncIOMotorDatabase) -> HistoricalDataCollector:
    """Get or create the historical data collector instance"""
    global _historical_data_collector
    if _historical_data_collector is None:
        _historical_data_collector = HistoricalDataCollector(db)
    return _historical_data_collector


async def initialize_data_collector(db: AsyncIOMotorDatabase) -> HistoricalDataCollector:
    """Initialize the data collector with database"""
    collector = get_historical_data_collector(db)
    await collector.initialize()
    return collector
