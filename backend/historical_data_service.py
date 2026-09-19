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
otc_candles_5s = db['otc_candles_5s']   # v8.58.1: live-collected OTC data (5s granularity)
data_imports = db['data_imports']
backtest_results = db['backtest_results']

# Create indexes for efficient queries
# Iter 149 — Legacy `symbol_1_timeframe_1_timestamp_-1` unique index was
# blocking every ingester upsert (records used `asset` field, not
# `symbol`, so every insert had `symbol=null` → duplicate-key collision
# against stale null-symbol rows). Rebuilt on the current `asset` schema.
historical_candles.create_index([
    ("asset", ASCENDING),
    ("timeframe", ASCENDING),
    ("timestamp", DESCENDING)
], unique=True, name="asset_1_timeframe_1_timestamp_-1")

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
            # v8.58.1: Fall back to `otc_candles_5s` — live-collected OTC data
            # that wasn't being used by the /backtest/run path. This collection
            # stores data at 5s granularity; resample to the requested timeframe
            # in-memory via pandas.
            df_otc = self._fetch_from_otc_collection(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
            if df_otc is not None and not df_otc.empty:
                return df_otc
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        return df

    def _fetch_from_otc_collection(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100_000,
    ) -> Optional[pd.DataFrame]:
        """
        v8.58.1 OTC backfill fallback. `otc_candles_5s` stores 5s candles for
        OTC pairs keyed on {symbol, timestamp (unix seconds)}. We resample to
        the requested backtest timeframe using pandas.

        Supported input timeframes: 5s / 15s / 30s / M1 / M5 / M15 / M30 /
        H1 / H4 (output); always 5s on the source side.
        """
        try:
            tf = (timeframe or "M1").upper()
            # Normalise PO-style M1/M5 to pandas resample rules
            rule_map = {
                "5S": "5s", "10S": "10s", "15S": "15s", "30S": "30s",
                "M1": "1min", "1M": "1min",
                "M5": "5min", "5M": "5min",
                "M15": "15min", "15M": "15min",
                "M30": "30min", "30M": "30min",
                "H1": "1h", "1H": "1h",
                "H4": "4h", "4H": "4h",
            }
            rule = rule_map.get(tf, "1min")

            # Symbol variants — otc_candles_5s uses e.g. EURUSD_OTC (uppercase)
            sym_u = symbol.upper()
            variants: List[str] = [sym_u]
            if not sym_u.endswith("_OTC"):
                variants.append(f"{sym_u}_OTC")
            # dedupe preserving order
            seen = set()
            variants = [s for s in variants if not (s in seen or seen.add(s))]

            # Build time window — otc_candles_5s was seen using ISO-string
            # timestamps (v8.58.1). Build $or query that covers both int
            # (unix seconds) and ISO-string representations so we work with
            # any writer version of the OTC backfill pipeline.
            time_clauses: List[Dict[str, Any]] = []
            if start_time or end_time:
                int_q: Dict[str, Any] = {}
                str_q: Dict[str, Any] = {}
                if start_time:
                    int_q["$gte"] = int(start_time.timestamp())
                    str_q["$gte"] = start_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                if end_time:
                    int_q["$lte"] = int(end_time.timestamp())
                    str_q["$lte"] = end_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                time_clauses = [{"timestamp": int_q}, {"timestamp": str_q}]

            raw: List[Dict[str, Any]] = []
            for sym in variants:
                q: Dict[str, Any] = {"symbol": sym}
                if time_clauses:
                    q["$or"] = time_clauses
                cursor = otc_candles_5s.find(
                    q, {"_id": 0, "collected_at": 0, "timeframe": 0}
                ).sort("timestamp", ASCENDING).limit(limit)
                raw = list(cursor)
                if raw and len(raw) >= 12:
                    logger.info(f"otc_candles_5s: {len(raw)} @5s rows for {sym} — resampling to {tf}")
                    break
                # If time-filtered came up empty, retry with NO time filter
                # (OTC data can be weeks old; better to return old data than
                # none). Only do this for OTC-tagged requests.
                if not raw and "_OTC" in sym:
                    cursor2 = otc_candles_5s.find(
                        {"symbol": sym}, {"_id": 0, "collected_at": 0, "timeframe": 0}
                    ).sort("timestamp", DESCENDING).limit(limit)
                    raw = list(cursor2)
                    if raw and len(raw) >= 12:
                        # Re-sort ascending for the resampler
                        raw.sort(key=lambda d: d.get("timestamp", ""))
                        logger.info(f"otc_candles_5s (untimed fallback): {len(raw)} @5s rows for {sym}")
                        break

            if not raw or len(raw) < 12:
                return None

            df5s = pd.DataFrame(raw)
            # Timestamps may be strings or ints — handle both
            if df5s["timestamp"].dtype == object:
                # ISO string path
                df5s["timestamp"] = pd.to_datetime(df5s["timestamp"], utc=True, errors="coerce")
            else:
                df5s["timestamp"] = pd.to_datetime(df5s["timestamp"], unit="s", utc=True)
            df5s = df5s.dropna(subset=["timestamp"])
            df5s = df5s.set_index("timestamp").sort_index()

            # If already 5s, no resample needed
            if rule == "5s":
                agg = df5s
            else:
                agg = df5s.resample(rule).agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum" if "volume" in df5s.columns else "last",
                }).dropna(subset=["open", "high", "low", "close"])

            if agg.empty or len(agg) < 5:
                return None

            out = agg.reset_index()
            # Tag source so downstream callers know this came from OTC live data
            out["source"] = "otc_candles_5s"
            out["symbol"] = variants[0]
            out["timeframe"] = timeframe
            return out
        except Exception as e:
            logger.warning(f"[otc_candles_5s fallback] failed for {symbol}/{timeframe}: {e}")
            return None
    
    def get_candles_for_backtest(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Get candles for backtesting (last N days).

        Iter 61 — fallback chain: local pool → Twelve Data (if pool insufficient).
        Twelve Data covers forex, OTC analogues, crypto, indices, commodities
        on the free tier (8 calls / 60s, rate-limited internally).

        The returned DataFrame carries `df.attrs['data_source']` set to one of
        `local_pool`, `twelvedata`, or `none` so callers (backtest endpoints)
        can surface it to the UI.
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        df = self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        if df is not None and not df.empty and len(df) >= 50:
            df.attrs["data_source"] = "local_pool"
            return df

        # Twelve Data fallback for any symbol the existing pool didn't cover
        try:
            from twelvedata_service import twelvedata_client
            # TwelveData free-tier intervals: 1min and up. For sub-minute (OTC
            # 5s/15s/30s) we can't help — return whatever we already had.
            sub_minute = timeframe in ("3s", "5s", "15s", "30s")
            if not sub_minute:
                # Pull plenty of candles. Free-tier outputsize cap 5000.
                td_df = twelvedata_client.get_candles(symbol, timeframe, outputsize=5000)
                if td_df is not None and not td_df.empty:
                    logger.info(
                        f"[twelvedata-fallback] {symbol} {timeframe}: {len(td_df)} candles"
                    )
                    td_df.attrs["data_source"] = "twelvedata"
                    return td_df
        except Exception as _e:
            logger.debug(f"[twelvedata-fallback] {symbol}: {_e}")

        out = df if df is not None else pd.DataFrame()
        out.attrs["data_source"] = "local_pool" if (df is not None and not df.empty) else "none"
        return out
    
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
