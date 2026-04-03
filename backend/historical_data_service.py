"""
Historical Data Service for Backtesting and ML Training
Handles data storage, retrieval, and management across multiple sources
"""
import os
import io
import json
import csv
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'gpt_signal_bot')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
historical_candles = db['historical_candles']
data_imports = db['data_imports']
backtest_results = db['backtest_results']

# Create indexes for efficient queries
historical_candles.create_index([
    ("symbol", ASCENDING),
    ("timeframe", ASCENDING),
    ("timestamp", DESCENDING)
], unique=True)

historical_candles.create_index([("timestamp", DESCENDING)])
historical_candles.create_index([("source", ASCENDING)])


class HistoricalDataService:
    """
    Unified service for historical market data management
    """
    
    SUPPORTED_TIMEFRAMES = ["5s", "15s", "30s", "M1", "M5", "M15", "M30", "H1", "H4"]
    SUPPORTED_SOURCES = ["oanda", "deriv", "pocket_option", "tampermonkey", "import"]
    
    # Data retention: 30 days
    RETENTION_DAYS = 30
    
    def __init__(self):
        self.stats = {
            "total_candles": 0,
            "symbols": set(),
            "timeframes": set(),
            "sources": set()
        }
        self._update_stats()
    
    def _update_stats(self):
        """Update internal statistics"""
        try:
            self.stats["total_candles"] = historical_candles.count_documents({})
            pipeline = [
                {"$group": {
                    "_id": None,
                    "symbols": {"$addToSet": "$symbol"},
                    "timeframes": {"$addToSet": "$timeframe"},
                    "sources": {"$addToSet": "$source"}
                }}
            ]
            result = list(historical_candles.aggregate(pipeline))
            if result:
                self.stats["symbols"] = set(result[0].get("symbols", []))
                self.stats["timeframes"] = set(result[0].get("timeframes", []))
                self.stats["sources"] = set(result[0].get("sources", []))
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def store_candle(
        self,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float = 0,
        source: str = "import"
    ) -> bool:
        """Store a single candle"""
        try:
            doc = {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "timestamp": timestamp,
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
                "source": source,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Upsert to handle duplicates
            historical_candles.update_one(
                {
                    "symbol": doc["symbol"],
                    "timeframe": doc["timeframe"],
                    "timestamp": doc["timestamp"]
                },
                {"$set": doc},
                upsert=True
            )
            return True
            
        except Exception as e:
            logger.error(f"Error storing candle: {e}")
            return False
    
    def store_candles_bulk(
        self,
        candles: List[Dict],
        symbol: str,
        timeframe: str,
        source: str = "import"
    ) -> Dict[str, int]:
        """
        Bulk store candles
        
        Args:
            candles: List of candle dicts with keys: timestamp, open, high, low, close, volume
            symbol: Symbol name
            timeframe: Timeframe string
            source: Data source identifier
            
        Returns:
            Dict with inserted/updated/error counts
        """
        results = {"inserted": 0, "updated": 0, "errors": 0}
        
        for candle in candles:
            try:
                # Parse timestamp
                ts = candle.get("timestamp") or candle.get("time") or candle.get("date")
                if isinstance(ts, str):
                    ts = pd.to_datetime(ts, utc=True)
                elif isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(ts, tz=timezone.utc)
                
                doc = {
                    "symbol": symbol.upper(),
                    "timeframe": timeframe,
                    "timestamp": ts,
                    "open": float(candle.get("open") or candle.get("Open", 0)),
                    "high": float(candle.get("high") or candle.get("High", 0)),
                    "low": float(candle.get("low") or candle.get("Low", 0)),
                    "close": float(candle.get("close") or candle.get("Close", 0)),
                    "volume": float(candle.get("volume") or candle.get("Volume", 0)),
                    "source": source,
                    "created_at": datetime.now(timezone.utc)
                }
                
                result = historical_candles.update_one(
                    {
                        "symbol": doc["symbol"],
                        "timeframe": doc["timeframe"],
                        "timestamp": doc["timestamp"]
                    },
                    {"$set": doc},
                    upsert=True
                )
                
                if result.upserted_id:
                    results["inserted"] += 1
                elif result.modified_count > 0:
                    results["updated"] += 1
                    
            except Exception as e:
                logger.error(f"Error storing candle: {e}")
                results["errors"] += 1
        
        self._update_stats()
        return results
    
    def store_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        source: str = "import"
    ) -> Dict[str, int]:
        """Store a pandas DataFrame of candles"""
        if df is None or df.empty:
            return {"inserted": 0, "updated": 0, "errors": 0}
        
        candles = df.to_dict('records')
        return self.store_candles_bulk(candles, symbol, timeframe, source)
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        source: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve historical candles
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe string
            start_time: Optional start datetime
            end_time: Optional end datetime
            limit: Maximum candles to return
            source: Optional filter by source
        """
        query = {
            "symbol": symbol.upper(),
            "timeframe": timeframe
        }
        
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        if end_time:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_time
            else:
                query["timestamp"] = {"$lte": end_time}
        if source:
            query["source"] = source
        
        cursor = historical_candles.find(
            query,
            {"_id": 0, "created_at": 0}
        ).sort("timestamp", ASCENDING).limit(limit)
        
        candles = list(cursor)
        
        if not candles:
            return pd.DataFrame()
        
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        return df
    
    def get_candles_for_backtest(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """Get candles for backtesting (last N days)"""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        
        return self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            limit=100000  # Large limit for backtesting
        )
    
    def import_csv(
        self,
        file_content: Union[str, bytes],
        symbol: str,
        timeframe: str,
        source: str = "import"
    ) -> Dict[str, Any]:
        """
        Import candles from CSV file content
        
        Expected CSV columns: timestamp/time/date, open, high, low, close, volume (optional)
        """
        try:
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')
            
            df = pd.read_csv(io.StringIO(file_content))
            
            # Normalize column names
            df.columns = df.columns.str.lower().str.strip()
            
            # Find timestamp column
            ts_col = None
            for col in ['timestamp', 'time', 'date', 'datetime']:
                if col in df.columns:
                    ts_col = col
                    break
            
            if ts_col is None:
                return {"success": False, "error": "No timestamp column found"}
            
            df['timestamp'] = pd.to_datetime(df[ts_col], utc=True)
            
            # Ensure required columns
            required = ['open', 'high', 'low', 'close']
            for col in required:
                if col not in df.columns:
                    return {"success": False, "error": f"Missing required column: {col}"}
            
            if 'volume' not in df.columns:
                df['volume'] = 0
            
            # Store
            results = self.store_dataframe(df, symbol, timeframe, source)
            
            # Log import
            data_imports.insert_one({
                "symbol": symbol,
                "timeframe": timeframe,
                "source": source,
                "rows": len(df),
                "results": results,
                "imported_at": datetime.now(timezone.utc)
            })
            
            return {
                "success": True,
                "rows_processed": len(df),
                "inserted": results["inserted"],
                "updated": results["updated"],
                "errors": results["errors"]
            }
            
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            return {"success": False, "error": str(e)}
    
    def import_json(
        self,
        file_content: Union[str, bytes],
        symbol: str,
        timeframe: str,
        source: str = "import"
    ) -> Dict[str, Any]:
        """
        Import candles from JSON file content
        
        Expected format: Array of objects with timestamp, open, high, low, close, volume
        """
        try:
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')
            
            data = json.loads(file_content)
            
            if not isinstance(data, list):
                # Try to find array in nested structure
                if isinstance(data, dict):
                    for key in ['candles', 'data', 'history', 'ohlc']:
                        if key in data and isinstance(data[key], list):
                            data = data[key]
                            break
            
            if not isinstance(data, list):
                return {"success": False, "error": "JSON must contain an array of candles"}
            
            results = self.store_candles_bulk(data, symbol, timeframe, source)
            
            # Log import
            data_imports.insert_one({
                "symbol": symbol,
                "timeframe": timeframe,
                "source": source,
                "rows": len(data),
                "results": results,
                "imported_at": datetime.now(timezone.utc)
            })
            
            return {
                "success": True,
                "rows_processed": len(data),
                "inserted": results["inserted"],
                "updated": results["updated"],
                "errors": results["errors"]
            }
            
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            logger.error(f"JSON import error: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup_old_data(self, days: int = None) -> int:
        """Remove data older than retention period"""
        if days is None:
            days = self.RETENTION_DAYS
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = historical_candles.delete_many({
            "timestamp": {"$lt": cutoff}
        })
        
        self._update_stats()
        logger.info(f"Cleaned up {result.deleted_count} old candles")
        return result.deleted_count
    
    def get_available_symbols(self) -> List[str]:
        """Get list of symbols with data"""
        return list(historical_candles.distinct("symbol"))
    
    def get_available_timeframes(self, symbol: Optional[str] = None) -> List[str]:
        """Get list of timeframes with data"""
        query = {}
        if symbol:
            query["symbol"] = symbol.upper()
        return list(historical_candles.distinct("timeframe", query))
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of stored historical data"""
        self._update_stats()
        
        # Get date range
        pipeline = [
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$timestamp"},
                "max_date": {"$max": "$timestamp"}
            }}
        ]
        date_range = list(historical_candles.aggregate(pipeline))
        
        # Get counts by symbol
        symbol_counts = list(historical_candles.aggregate([
            {"$group": {"_id": "$symbol", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]))
        
        # Get counts by source
        source_counts = list(historical_candles.aggregate([
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]))
        
        # Handle date range safely
        start_date = None
        end_date = None
        if date_range and date_range[0].get("min_date"):
            min_dt = date_range[0]["min_date"]
            max_dt = date_range[0]["max_date"]
            start_date = min_dt.isoformat() if hasattr(min_dt, 'isoformat') else str(min_dt)
            end_date = max_dt.isoformat() if hasattr(max_dt, 'isoformat') else str(max_dt)
        
        return {
            "total_candles": self.stats["total_candles"],
            "symbols": list(self.stats["symbols"]),
            "timeframes": list(self.stats["timeframes"]),
            "sources": list(self.stats["sources"]),
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "by_symbol": {item["_id"]: item["count"] for item in symbol_counts},
            "by_source": {item["_id"]: item["count"] for item in source_counts}
        }
    
    def get_symbol_coverage(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Get data coverage for a specific symbol and timeframe"""
        query = {"symbol": symbol.upper(), "timeframe": timeframe}
        
        count = historical_candles.count_documents(query)
        
        if count == 0:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "has_data": False,
                "candle_count": 0
            }
        
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$timestamp"},
                "max_date": {"$max": "$timestamp"},
                "sources": {"$addToSet": "$source"}
            }}
        ]
        
        result = list(historical_candles.aggregate(pipeline))
        
        if result:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "has_data": True,
                "candle_count": count,
                "start_date": result[0]["min_date"].isoformat(),
                "end_date": result[0]["max_date"].isoformat(),
                "sources": result[0]["sources"]
            }
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "has_data": False,
            "candle_count": 0
        }


# Global instance
historical_data_service = HistoricalDataService()
