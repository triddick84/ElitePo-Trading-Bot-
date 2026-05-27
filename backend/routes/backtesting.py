"""
API Routes for Backtesting and Historical Data Management
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import logging
import asyncio
import pandas as pd

logger = logging.getLogger(__name__)
router = APIRouter()

# Import services
from historical_data_service import historical_data_service
from backtesting_engine import (
    BacktestingEngine,
    create_deep_confluence_strategy,
    create_momentum_buster_strategy,
    create_lstm_model_predictor,
    create_ppo_model_predictor,
    create_hybrid_ensemble_strategy,
)

# Try to import Deriv service
try:
    from deriv_data_service import deriv_service, fetch_deriv_historical_data
    DERIV_AVAILABLE = True
except ImportError:
    DERIV_AVAILABLE = False
    logger.warning("Deriv service not available")


# ==========================================
# PYDANTIC MODELS
# ==========================================

class DataImportRequest(BaseModel):
    symbol: str = Field(..., description="Symbol name (e.g., EURUSD_OTC)")
    timeframe: str = Field(..., description="Timeframe (5s, 15s, 30s, M1, M5, M15, M30, H1, H4)")
    source: str = Field(default="import", description="Data source identifier")


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Symbol to backtest")
    timeframe: str = Field(default="M1", description="Timeframe")
    strategy: str = Field(..., description="Strategy name or 'all'")
    days: int = Field(default=30, ge=1, le=90, description="Days of data to use")
    min_confidence: float = Field(default=65.0, ge=0, le=100)
    expiry_seconds: int = Field(default=60, ge=5, le=3600)
    initial_balance: float = Field(default=1000.0, ge=100)
    trade_size: float = Field(default=10.0, ge=1)


class CandleData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


class BulkCandleImport(BaseModel):
    symbol: str
    timeframe: str
    source: str = "import"
    candles: List[CandleData]


# ==========================================
# HISTORICAL DATA ENDPOINTS
# ==========================================

@router.get("/historical/summary")
async def get_data_summary():
    """Get summary of all stored historical data"""
    try:
        summary = historical_data_service.get_data_summary()
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Error getting data summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/symbols")
async def get_available_symbols():
    """Get list of symbols with historical data"""
    try:
        symbols = historical_data_service.get_available_symbols()
        return {"success": True, "symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/timeframes")
async def get_available_timeframes(symbol: Optional[str] = None):
    """Get list of available timeframes"""
    try:
        timeframes = historical_data_service.get_available_timeframes(symbol)
        return {"success": True, "timeframes": timeframes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/coverage/{symbol}/{timeframe}")
async def get_symbol_coverage(symbol: str, timeframe: str):
    """Get data coverage for a specific symbol and timeframe"""
    try:
        coverage = historical_data_service.get_symbol_coverage(symbol, timeframe)
        return {"success": True, "coverage": coverage}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/candles/{symbol}/{timeframe}")
async def get_historical_candles(
    symbol: str,
    timeframe: str,
    limit: int = Query(default=1000, ge=1, le=10000),
    days: Optional[int] = Query(default=None, ge=1, le=90)
):
    """Get historical candles for a symbol"""
    try:
        if days:
            df = historical_data_service.get_candles_for_backtest(symbol, timeframe, days)
        else:
            df = historical_data_service.get_candles(symbol, timeframe, limit=limit)
        
        if df.empty:
            return {"success": True, "candles": [], "count": 0}
        
        # Convert to JSON-serializable format
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        candles = df.to_dict('records')
        
        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
            "count": len(candles)
        }
    except Exception as e:
        logger.error(f"Error fetching candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/historical/import/csv")
async def import_csv_data(
    file: UploadFile = File(...),
    symbol: str = Query(...),
    timeframe: str = Query(...),
    source: str = Query(default="import")
):
    """Import historical data from CSV file"""
    try:
        content = await file.read()
        result = historical_data_service.import_csv(content, symbol, timeframe, source)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Imported {result['rows_processed']} rows",
                "details": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Import failed"))
            
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/historical/import/json")
async def import_json_data(
    file: UploadFile = File(...),
    symbol: str = Query(...),
    timeframe: str = Query(...),
    source: str = Query(default="import")
):
    """Import historical data from JSON file"""
    try:
        content = await file.read()
        result = historical_data_service.import_json(content, symbol, timeframe, source)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Imported {result['rows_processed']} candles",
                "details": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Import failed"))
            
    except Exception as e:
        logger.error(f"JSON import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/historical/import/bulk")
async def import_bulk_candles(data: BulkCandleImport):
    """Import candles from JSON body"""
    try:
        candles = [c.dict() for c in data.candles]
        result = historical_data_service.store_candles_bulk(
            candles, data.symbol, data.timeframe, data.source
        )
        
        return {
            "success": True,
            "message": f"Processed {len(candles)} candles",
            "inserted": result["inserted"],
            "updated": result["updated"],
            "errors": result["errors"]
        }
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/historical/cleanup")
async def cleanup_old_data(days: int = Query(default=30, ge=1, le=365)):
    """Remove data older than specified days"""
    try:
        deleted = historical_data_service.cleanup_old_data(days)
        return {
            "success": True,
            "message": f"Deleted {deleted} old candles",
            "deleted_count": deleted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# DERIV DATA ENDPOINTS
# ==========================================

@router.get("/deriv/symbols")
async def get_deriv_symbols():
    """Get available Deriv synthetic indices symbols"""
    if not DERIV_AVAILABLE:
        raise HTTPException(status_code=503, detail="Deriv service not available")
    
    return {
        "success": True,
        "symbols": deriv_service.get_available_symbols(),
        "timeframes": deriv_service.get_available_timeframes()
    }


@router.post("/deriv/fetch")
async def fetch_deriv_data(
    background_tasks: BackgroundTasks,
    symbol: str = Query(..., description="Deriv symbol (e.g., V100, CRASH_500)"),
    timeframe: str = Query(default="M1"),
    count: int = Query(default=1000, ge=100, le=5000),
    store: bool = Query(default=True, description="Store in historical database")
):
    """Fetch historical data from Deriv API"""
    if not DERIV_AVAILABLE:
        raise HTTPException(status_code=503, detail="Deriv service not available")
    
    try:
        # Fetch data asynchronously
        df = await fetch_deriv_historical_data(symbol, timeframe, count)
        
        if df is None or df.empty:
            return {
                "success": False,
                "message": f"No data returned for {symbol} {timeframe}"
            }
        
        result = {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "candles_fetched": len(df)
        }
        
        # Store if requested
        if store:
            store_result = historical_data_service.store_dataframe(
                df, symbol, timeframe, "deriv"
            )
            result["stored"] = store_result
        
        return result
        
    except Exception as e:
        logger.error(f"Deriv fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deriv/fetch-all")
async def fetch_all_deriv_symbols(
    background_tasks: BackgroundTasks,
    timeframe: str = Query(default="M1"),
    count: int = Query(default=500, ge=100, le=2000)
):
    """Fetch data for all available Deriv symbols (runs in background)"""
    if not DERIV_AVAILABLE:
        raise HTTPException(status_code=503, detail="Deriv service not available")
    
    async def fetch_all():
        symbols = deriv_service.get_available_symbols()
        for symbol in symbols[:10]:  # Limit to prevent timeout
            try:
                df = await fetch_deriv_historical_data(symbol, timeframe, count)
                if df is not None and not df.empty:
                    historical_data_service.store_dataframe(df, symbol, timeframe, "deriv")
                    logger.info(f"Stored {len(df)} candles for {symbol}")
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
            await asyncio.sleep(1)  # Rate limit
    
    background_tasks.add_task(asyncio.create_task, fetch_all())
    
    return {
        "success": True,
        "message": "Fetching data in background",
        "symbols_queued": min(10, len(deriv_service.get_available_symbols()))
    }


# ==========================================
# BACKTESTING ENDPOINTS
# ==========================================

@router.get("/backtest/strategies")
async def get_available_strategies():
    """Get list of available strategies for backtesting"""
    strategies = [
        {
            "name": "deep_confluence",
            "description": "Deep Confluence Analysis with multi-indicator validation",
            "min_timeframe": "M1",
            "default_expiry": 60
        },
        {
            "name": "momentum_buster",
            "description": "Momentum Buster 15s strategy",
            "min_timeframe": "5s",
            "default_expiry": 15
        },
        {
            "name": "lstm_gru",
            "description": "LSTM/GRU Time-Series ML Model",
            "min_timeframe": "M1",
            "default_expiry": 60,
            "requires_training": True
        },
        {
            "name": "ppo_rl",
            "description": "PPO Reinforcement Learning Agent",
            "min_timeframe": "M1",
            "default_expiry": 60,
            "requires_training": True
        }
    ]
    
    return {"success": True, "strategies": strategies}


@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Run backtest for a strategy or ML model"""
    try:
        # Get historical data
        df = historical_data_service.get_candles_for_backtest(
            request.symbol, request.timeframe, request.days
        )
        data_source = (df.attrs.get("data_source") if df is not None else None) or "none"
        
        if df.empty:
            # Try to get from OANDA if no historical data
            try:
                from enhanced_oanda_service import enhanced_oanda
                oanda_df = enhanced_oanda.get_candles(
                    request.symbol.replace("_OTC", "").replace("_", "_"),
                    request.timeframe,
                    count=request.days * 1440 // (60 if request.timeframe == "M1" else 1)
                )
                if oanda_df is not None and not oanda_df.empty:
                    df = oanda_df
                    df['timestamp'] = pd.to_datetime(df.index, utc=True)
                    df = df.reset_index(drop=True)
                    data_source = "oanda"
            except Exception as e:
                logger.warning(f"OANDA fallback failed: {e}")
        
        if df.empty:
            # Final fallback: Twelve Data
            try:
                from twelvedata_service import twelvedata_client
                if request.timeframe not in ("3s", "5s", "15s", "30s"):
                    td_df = twelvedata_client.get_candles(
                        request.symbol, request.timeframe, outputsize=5000
                    )
                    if td_df is not None and not td_df.empty:
                        df = td_df
                        data_source = "twelvedata"
            except Exception as e:
                logger.warning(f"Twelve Data fallback failed: {e}")

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No historical data available for {request.symbol} {request.timeframe}. Please import data first."
            )
        
        # Initialize engine
        engine = BacktestingEngine(
            initial_balance=request.initial_balance,
            trade_size=request.trade_size
        )
        
        results = []
        
        # Run appropriate backtest
        strategies_to_run = []
        
        if request.strategy == "all":
            strategies_to_run = ["deep_confluence", "momentum_buster", "lstm_gru", "ppo_rl", "hybrid"]
        else:
            strategies_to_run = [request.strategy]
        
        for strategy_name in strategies_to_run:
            try:
                if strategy_name in ("hybrid", "force_generate_v2", "ensemble"):
                    # Iter 58 — hybrid uses the same confluence+MTF+regime+ML
                    # stack as the live force-generate-v2 pipeline.
                    strategy_func = create_hybrid_ensemble_strategy()
                    metrics = engine.run_strategy_backtest(
                        df, strategy_func, request.timeframe,
                        request.expiry_seconds, request.min_confidence
                    )

                elif strategy_name == "deep_confluence":
                    strategy_func = create_deep_confluence_strategy()
                    metrics = engine.run_strategy_backtest(
                        df, strategy_func, request.timeframe,
                        request.expiry_seconds, request.min_confidence
                    )
                    
                elif strategy_name == "momentum_buster":
                    strategy_func = create_momentum_buster_strategy()
                    metrics = engine.run_strategy_backtest(
                        df, strategy_func, request.timeframe,
                        15, request.min_confidence  # 15s expiry for momentum buster
                    )
                    
                elif strategy_name == "lstm_gru":
                    model_func = create_lstm_model_predictor()
                    if model_func is None:
                        results.append({
                            "strategy": strategy_name,
                            "error": "LSTM model not available or not trained"
                        })
                        continue
                    metrics = engine.run_ml_model_backtest(
                        df, model_func, request.timeframe,
                        request.expiry_seconds, request.min_confidence
                    )
                    
                elif strategy_name == "ppo_rl":
                    model_func = create_ppo_model_predictor()
                    if model_func is None:
                        results.append({
                            "strategy": strategy_name,
                            "error": "PPO model not available or not trained"
                        })
                        continue
                    metrics = engine.run_ml_model_backtest(
                        df, model_func, request.timeframe,
                        request.expiry_seconds, request.min_confidence
                    )
                else:
                    results.append({
                        "strategy": strategy_name,
                        "error": f"Unknown strategy: {strategy_name}"
                    })
                    continue
                
                # Save results
                result_id = engine.save_results(
                    request.symbol, request.timeframe, strategy_name, metrics
                )
                
                results.append({
                    "strategy": strategy_name,
                    "result_id": result_id,
                    "metrics": metrics.to_dict()
                })
                
            except Exception as e:
                logger.error(f"Backtest error for {strategy_name}: {e}")
                results.append({
                    "strategy": strategy_name,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "data_points": len(df),
            "data_source": data_source,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/results")
async def get_backtest_results(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100)
):
    """Get recent backtest results"""
    try:
        from backtesting_engine import backtest_results_collection
        
        query = {}
        if symbol:
            query["symbol"] = symbol.upper()
        if strategy:
            query["strategy"] = strategy
        
        cursor = backtest_results_collection.find(
            query,
            {"_id": 0, "equity_curve": 0}
        ).sort("created_at", -1).limit(limit)
        
        results = list(cursor)
        
        # Convert datetime to string
        for r in results:
            if "created_at" in r:
                r["created_at"] = r["created_at"].isoformat()
        
        return {"success": True, "results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/compare")
async def compare_strategies(
    symbol: str = Query(...),
    timeframe: str = Query(default="M1"),
    days: int = Query(default=30, ge=1, le=90)
):
    """Compare all strategies on the same data"""
    try:
        # Create a backtest request for all strategies
        request = BacktestRequest(
            symbol=symbol,
            timeframe=timeframe,
            strategy="all",
            days=days,
            min_confidence=65.0
        )
        
        result = await run_backtest(request)
        
        # Sort by win rate
        if result.get("results"):
            valid_results = [r for r in result["results"] if "metrics" in r]
            valid_results.sort(
                key=lambda x: x["metrics"].get("win_rate", 0),
                reverse=True
            )
            result["results"] = valid_results
            result["best_strategy"] = valid_results[0]["strategy"] if valid_results else None
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TAMPERMONKEY DATA COLLECTION ENDPOINT
# ==========================================

@router.post("/tampermonkey/candles")
async def receive_tampermonkey_candles(
    symbol: str = Query(...),
    timeframe: str = Query(default="5s"),
    candles: List[Dict] = []
):
    """
    Receive candle data from Tampermonkey scraper
    This endpoint allows the userscript to send scraped price data
    """
    try:
        if not candles:
            return {"success": False, "error": "No candles provided"}
        
        result = historical_data_service.store_candles_bulk(
            candles, symbol, timeframe, "tampermonkey"
        )
        
        return {
            "success": True,
            "stored": result["inserted"] + result["updated"],
            "errors": result["errors"]
        }
        
    except Exception as e:
        logger.error(f"Tampermonkey candle storage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
