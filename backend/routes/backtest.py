"""Auto-extracted route module from server.py refactoring."""
from fastapi import APIRouter, HTTPException, Query, Request, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging
import json
import uuid
import os
import asyncio
import pandas as pd

from routes import db, convert_numpy_types, logger

# Re-use the main api_router — routes are registered via include in server.py
# This module uses a local router that gets included by server.py
router = APIRouter()

from routes.models import BacktestRequest
import numpy as np


# Backtesting
@router.post("/backtest/run")
async def run_backtest(request: dict = Body(...)):
    """
    Iter 58 — Delegate to the canonical /backtest/run implementation in
    routes/backtesting.py which supports the `hybrid` ensemble strategy
    and the OTC candle fallback. The previous handler routed to a stale
    `trading_bot.run_backtest()` path that only knew yfinance + failed
    on every OTC symbol.
    """
    try:
        from routes.backtesting import run_backtest as canonical_run_backtest
        from routes.backtesting import BacktestRequest as CanonicalReq
        # Build the canonical request, defaulting fields when omitted.
        req = CanonicalReq(
            symbol=request.get("symbol"),
            timeframe=request.get("timeframe", "M1"),
            strategy=request.get("strategy", "hybrid"),
            days=int(request.get("days", 7)),
            min_confidence=float(request.get("min_confidence", 65.0)),
            expiry_seconds=int(request.get("expiry_seconds", 60)),
            initial_balance=float(request.get("initial_balance", 1000.0)),
            trade_size=float(request.get("trade_size", 10.0)),
        )
        return await canonical_run_backtest(req)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error running backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/backtest/history")
async def get_backtest_history():
    """Get historical backtest results"""
    try:
        results = await db.backtest_results.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(length=None)
        return {"results": results}
        
    except Exception as e:
        logging.error(f"Error getting backtest history: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# =====================================================
# COMPREHENSIVE BACKTESTING ENDPOINTS
# =====================================================

@router.get("/backtest/assets")
async def get_backtest_assets():
    """Get available assets for backtesting"""
    try:
        from backtesting_service import get_backtesting_service
        service = await get_backtesting_service(db)
        assets = await service.get_available_assets()
        return {"success": True, "assets": assets}
    except Exception as e:
        logger.error(f"Error getting backtest assets: {e}")
        return {"success": False, "assets": {"forex": [], "crypto": [], "stocks": []}}


# Iter 58 — FULL backtesting asset universe with per-class allowed timeframes.
# Iter 63 — expanded to cover the full Pocket Option asset menu (regular + OTC).
# Rule (per user, May 17, 2026):
#   - Regular markets (forex/commodities/crypto/indices/stocks) → ≥ 1m
#   - OTC markets → ≥ 3s (PO-native)
_FOREX_MAJORS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
]
_FOREX_CROSSES = [
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCAD", "AUDCHF", "AUDNZD",
    "CADJPY", "CADCHF", "CHFJPY", "NZDJPY", "NZDCAD", "NZDCHF",
]
_FOREX_EXOTICS = [
    "USDMXN", "USDZAR", "USDTRY", "USDSGD", "USDHKD", "USDSEK", "USDNOK",
    "USDPLN", "USDCNH", "USDINR", "USDBRL", "USDKRW", "USDTHB", "USDIDR",
    "USDPHP", "USDARS", "USDCLP", "USDCOP", "USDDKK", "USDHUF", "USDCZK",
    "USDRUB", "USDEGP", "USDSAR", "USDAED", "USDILS",
    "EURPLN", "EURNOK", "EURSEK", "EURTRY", "EURZAR", "EURDKK", "EURHUF",
    "GBPPLN", "GBPNOK", "GBPSEK", "GBPTRY", "GBPZAR",
    "AUDSGD", "AUDHKD", "NZDSGD", "CADSGD", "CHFSGD", "ZARJPY", "TRYJPY",
]
_COMMODITIES = [
    "XAUUSD", "XAGUSD", "WTI", "BRENT", "NGAS", "XPTUSD", "XPDUSD",
    "COFFEE", "COCOA", "SUGAR", "COTTON", "WHEAT", "CORN", "SOYBEAN",
    "COPPER",
]
_CRYPTO = [
    "BTCUSD", "ETHUSD", "LTCUSD", "BCHUSD", "XRPUSD", "EOSUSD", "DASHUSD",
    "ZECUSD", "BNBUSD", "ADAUSD", "SOLUSD", "DOGEUSD", "MATICUSD", "AVAXUSD",
    "DOTUSD", "SHIBUSD", "LINKUSD", "TRXUSD", "ATOMUSD", "UNIUSD", "XLMUSD",
    "FILUSD", "AAVEUSD", "ALGOUSD", "ICPUSD", "NEARUSD", "APTUSD", "ARBUSD",
    "OPUSD", "PEPEUSD",
]
_INDICES = [
    "SPX500", "NDX100", "DJI30", "RUT2000",
    "DAX40", "FTSE100", "CAC40", "IBEX35", "AEX25", "STOXX50", "SMI20",
    "NIKKEI225", "HSI50", "ASX200", "KOSPI",
    "BVSP", "MICEX",
]
_STOCKS_US = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX",
    "DIS", "BABA", "INTC", "AMD", "IBM", "ORCL", "CSCO", "ADBE",
    "PYPL", "V", "MA", "JPM", "BAC", "WFC", "GS", "MS",
    "C", "T", "VZ", "PFE", "JNJ", "MRK", "KO", "PEP",
    "WMT", "MCD", "NKE", "BA", "GE", "F", "TWTR", "UBER",
    "LYFT", "SNAP", "SPOT", "ROKU", "ZM", "SQ", "SHOP", "COIN",
]

_OTC_PAIRS = sorted({f"{s}_OTC" for s in (_FOREX_MAJORS + _FOREX_CROSSES + _FOREX_EXOTICS)})
_OTC_COMMODITIES = [f"{s}_OTC" for s in _COMMODITIES]
_OTC_CRYPTO = [f"{s}_OTC" for s in _CRYPTO]
_OTC_INDICES = [f"{s}_OTC" for s in _INDICES]
_OTC_STOCKS = [f"{s}_OTC" for s in _STOCKS_US]

_REGULAR_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
_OTC_TIMEFRAMES = ["3s", "5s", "15s", "30s", "M1", "M5", "M15", "M30", "H1"]


@router.get("/backtest/assets-universe")
async def get_backtest_assets_universe():
    """
    Iter 58 / Iter 63 — full backtesting universe (forex + OTC + commodities +
    crypto + indices + stocks). Each class carries its allowed timeframes so
    the UI can gate the dropdown:
      - Regular markets: ≥ 1m
      - OTC markets: ≥ 3s
    """
    return {
        "success": True,
        "classes": [
            {
                "id": "forex",
                "label": "Forex (Regular)",
                "min_timeframe": "M1",
                "timeframes": _REGULAR_TIMEFRAMES,
                "symbols": _FOREX_MAJORS + _FOREX_CROSSES + _FOREX_EXOTICS,
            },
            {
                "id": "forex_otc",
                "label": "Forex (OTC)",
                "min_timeframe": "3s",
                "timeframes": _OTC_TIMEFRAMES,
                "symbols": _OTC_PAIRS,
            },
            {
                "id": "commodities",
                "label": "Commodities (Regular)",
                "min_timeframe": "M1",
                "timeframes": _REGULAR_TIMEFRAMES,
                "symbols": _COMMODITIES,
            },
            {
                "id": "commodities_otc",
                "label": "Commodities (OTC)",
                "min_timeframe": "3s",
                "timeframes": _OTC_TIMEFRAMES,
                "symbols": _OTC_COMMODITIES,
            },
            {
                "id": "crypto",
                "label": "Crypto (Regular)",
                "min_timeframe": "M1",
                "timeframes": _REGULAR_TIMEFRAMES,
                "symbols": _CRYPTO,
            },
            {
                "id": "crypto_otc",
                "label": "Crypto (OTC)",
                "min_timeframe": "3s",
                "timeframes": _OTC_TIMEFRAMES,
                "symbols": _OTC_CRYPTO,
            },
            {
                "id": "indices",
                "label": "Indices (Regular)",
                "min_timeframe": "M1",
                "timeframes": _REGULAR_TIMEFRAMES,
                "symbols": _INDICES,
            },
            {
                "id": "indices_otc",
                "label": "Indices (OTC)",
                "min_timeframe": "3s",
                "timeframes": _OTC_TIMEFRAMES,
                "symbols": _OTC_INDICES,
            },
            {
                "id": "stocks",
                "label": "US Stocks (Regular)",
                "min_timeframe": "M1",
                "timeframes": _REGULAR_TIMEFRAMES,
                "symbols": _STOCKS_US,
            },
            {
                "id": "stocks_otc",
                "label": "US Stocks (OTC)",
                "min_timeframe": "3s",
                "timeframes": _OTC_TIMEFRAMES,
                "symbols": _OTC_STOCKS,
            },
        ],
        "totals": {
            "forex_regular": len(_FOREX_MAJORS) + len(_FOREX_CROSSES) + len(_FOREX_EXOTICS),
            "forex_otc": len(_OTC_PAIRS),
            "commodities": len(_COMMODITIES),
            "commodities_otc": len(_OTC_COMMODITIES),
            "crypto": len(_CRYPTO),
            "crypto_otc": len(_OTC_CRYPTO),
            "indices": len(_INDICES),
            "indices_otc": len(_OTC_INDICES),
            "stocks": len(_STOCKS_US),
            "stocks_otc": len(_OTC_STOCKS),
            "grand_total": (
                len(_FOREX_MAJORS) + len(_FOREX_CROSSES) + len(_FOREX_EXOTICS)
                + len(_OTC_PAIRS) + len(_COMMODITIES) + len(_OTC_COMMODITIES)
                + len(_CRYPTO) + len(_OTC_CRYPTO) + len(_INDICES) + len(_OTC_INDICES)
                + len(_STOCKS_US) + len(_OTC_STOCKS)
            ),
        },
        "rules": {
            "regular_min": "M1",
            "otc_min": "3s",
            "note": "Regular markets cannot use sub-minute timeframes; OTC supports 3s/5s/15s/30s.",
        },
    }





@router.get("/backtest/strategies")
async def get_backtest_strategies():
    """Get available strategies for backtesting"""
    try:
        from backtesting_service import get_backtesting_service
        service = await get_backtesting_service(db)
        strategies = await service.get_available_strategies()
        return {"success": True, "strategies": strategies}
    except Exception as e:
        logger.error(f"Error getting backtest strategies: {e}")
        return {"success": False, "strategies": []}




@router.post("/backtest/comprehensive")
async def run_comprehensive_backtest(request: dict):
    """
    Run comprehensive backtest with multiple strategies, assets, and timeframes.
    
    Request body:
    {
        "strategies": ["rsi_reversal", "ema_crossover"],
        "assets": ["EURUSD", "BTCUSDT"],
        "timeframes": ["1h", "4h"],
        "days": 30,
        "initial_balance": 1000,
        "trade_amount": 10
    }
    """
    try:
        from backtesting_service import BacktestingService, BacktestConfig
        from dataclasses import asdict
        
        # Create service WITH database connection for real data access
        service = BacktestingService(db=db)
        
        config = BacktestConfig(
            strategies=request.get("strategies", ["hybrid"]),
            assets=request.get("assets", ["EURUSD"]),
            timeframes=request.get("timeframes", ["1h"]),
            days=min(request.get("days", 30), 90),  # Max 90 days
            initial_balance=request.get("initial_balance", 1000.0),
            trade_amount=request.get("trade_amount", 10.0),
            payout_rate=request.get("payout_rate", 0.85)
        )
        
        logger.info(f"Starting comprehensive backtest: {len(config.strategies)} strategies, {len(config.assets)} assets, {len(config.timeframes)} timeframes")
        
        results = await service.run_backtest(config)
        
        # Convert results to dicts
        results_data = [asdict(r) for r in results]
        
        # Save results to database
        if results_data:
            for result_dict in results_data:
                try:
                    result_dict['_id'] = result_dict['id']
                    await db.backtest_results.update_one(
                        {"_id": result_dict['id']},
                        {"$set": result_dict},
                        upsert=True
                    )
                except Exception as save_error:
                    logger.warning(f"Error saving result: {save_error}")
        
        # Calculate summary statistics
        if results_data:
            avg_win_rate = sum(r['win_rate'] for r in results_data) / len(results_data)
            best_result = max(results_data, key=lambda x: x['win_rate'])
            total_trades = sum(r['total_trades'] for r in results_data)
        else:
            avg_win_rate = 0
            best_result = None
            total_trades = 0
        
        logger.info(f"Backtest complete: {len(results_data)} results, avg win rate: {avg_win_rate:.1f}%")
        
        return {
            "success": True,
            "config_id": config.id,
            "results": results_data,
            "summary": {
                "total_backtests": len(results_data),
                "total_trades_simulated": total_trades,
                "average_win_rate": round(avg_win_rate, 2),
                "best_performer": best_result['strategy'] if best_result else None,
                "best_win_rate": round(best_result['win_rate'], 2) if best_result else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error running comprehensive backtest: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "results": []}




@router.get("/backtest/result/{result_id}")
async def get_backtest_result(result_id: str):
    """Get detailed backtest result by ID"""
    try:
        result = await db.backtest_results.find_one({"id": result_id}, {"_id": 0})
        if result:
            return {"success": True, "result": result}
        return {"success": False, "error": "Result not found"}
    except Exception as e:
        logger.error(f"Error getting backtest result: {e}")
        return {"success": False, "error": str(e)}




@router.delete("/backtest/clear")
async def clear_backtest_history():
    """Clear all backtest history"""
    try:
        result = await db.backtest_results.delete_many({})
        return {"success": True, "deleted_count": result.deleted_count}
    except Exception as e:
        logger.error(f"Error clearing backtest history: {e}")
        return {"success": False, "error": str(e)}




@router.get("/backtest/compare")
async def compare_strategies(strategies: str = "", asset: str = "EURUSD", timeframe: str = "1h", days: int = 30):
    """
    Compare multiple strategies on the same asset/timeframe.
    Query params: strategies=rsi_reversal,ema_crossover&asset=EURUSD&timeframe=1h&days=30
    """
    try:
        from backtesting_service import get_backtesting_service, BacktestConfig
        from dataclasses import asdict
        
        strategy_list = strategies.split(",") if strategies else ["hybrid", "rsi_reversal", "ema_crossover"]
        
        service = await get_backtesting_service(db)
        
        config = BacktestConfig(
            strategies=strategy_list,
            assets=[asset],
            timeframes=[timeframe],
            days=min(days, 90)
        )
        
        results = await service.run_backtest(config)
        results_data = [asdict(r) for r in results]
        
        # Sort by win rate
        results_data.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return {
            "success": True,
            "comparison": results_data,
            "asset": asset,
            "timeframe": timeframe,
            "days": days,
            "winner": results_data[0]['strategy'] if results_data else None
        }
        
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        return {"success": False, "error": str(e)}


# ==========================================
# HISTORICAL DATA MANAGEMENT ENDPOINTS
# ==========================================

# Import historical data service
try:
    from historical_data_service import historical_data_service
    HISTORICAL_SERVICE_AVAILABLE = True
except ImportError:
    HISTORICAL_SERVICE_AVAILABLE = False
    logger.warning("Historical data service not available")

# Import Deriv service
try:
    from deriv_data_service import deriv_service, fetch_deriv_historical_data
    DERIV_AVAILABLE = True
except ImportError:
    DERIV_AVAILABLE = False
    logger.warning("Deriv service not available")


@router.get("/historical/summary")
async def get_data_summary():
    """Get summary of all stored historical data"""
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
    try:
        summary = historical_data_service.get_data_summary()
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Error getting data summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/symbols")
async def get_available_symbols():
    """Get list of symbols with historical data"""
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
    try:
        symbols = historical_data_service.get_available_symbols()
        return {"success": True, "symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/timeframes")
async def get_available_timeframes(symbol: Optional[str] = None):
    """Get list of available timeframes"""
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
    try:
        timeframes = historical_data_service.get_available_timeframes(symbol)
        return {"success": True, "timeframes": timeframes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical/coverage/{symbol}/{timeframe}")
async def get_symbol_coverage(symbol: str, timeframe: str):
    """Get data coverage for a specific symbol and timeframe"""
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
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
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
    try:
        if days:
            df = historical_data_service.get_candles_for_backtest(symbol, timeframe, days)
        else:
            df = historical_data_service.get_candles(symbol, timeframe, limit=limit)
        
        if df.empty:
            return {"success": True, "candles": [], "count": 0}
        
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


@router.post("/historical/import/bulk")
async def import_bulk_candles(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    source: str = Query(default="import"),
    candles: List[Dict] = Body(...)
):
    """Import candles from JSON body"""
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
    try:
        result = historical_data_service.store_candles_bulk(candles, symbol, timeframe, source)
        
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
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
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
    symbol: str = Query(..., description="Deriv symbol (e.g., V100, CRASH_500)"),
    timeframe: str = Query(default="M1"),
    count: int = Query(default=1000, ge=100, le=5000),
    store: bool = Query(default=True, description="Store in historical database")
):
    """Fetch historical data from Deriv API"""
    if not DERIV_AVAILABLE:
        raise HTTPException(status_code=503, detail="Deriv service not available")
    
    try:
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
        
        if store and HISTORICAL_SERVICE_AVAILABLE:
            store_result = historical_data_service.store_dataframe(
                df, symbol, timeframe, "deriv"
            )
            result["stored"] = store_result
        
        return result
        
    except Exception as e:
        logger.error(f"Deriv fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TAMPERMONKEY DATA COLLECTION ENDPOINT
# ==========================================

@router.post("/tampermonkey/candles")
async def receive_tampermonkey_candles(
    symbol: str = Query(...),
    timeframe: str = Query(default="5s"),
    candles: List[Dict] = Body(default=[])
):
    """
    Receive candle data from Tampermonkey scraper
    This endpoint allows the userscript to send scraped price data
    """
    if not HISTORICAL_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Historical data service not available")
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


# ==========================================
# ADVANCED BACKTESTING WITH ML MODELS
# ==========================================

@router.post("/backtest/ml")
async def run_ml_backtest(
    symbol: str = Query(...),
    timeframe: str = Query(default="M1"),
    model: str = Query(default="lstm_gru", description="lstm_gru, ppo_rl, or ensemble"),
    days: int = Query(default=30, ge=1, le=90),
    min_confidence: float = Query(default=60.0, ge=0, le=100)
):
    """Run backtest for ML models (LSTM/GRU, PPO, or Ensemble)"""
    try:
        from backtesting_engine import (
            BacktestingEngine,
            create_lstm_model_predictor,
            create_ppo_model_predictor
        )
        
        # Get historical data
        if HISTORICAL_SERVICE_AVAILABLE:
            df = historical_data_service.get_candles_for_backtest(symbol, timeframe, days)
        else:
            df = pd.DataFrame()
        
        if df.empty:
            # Fallback to OANDA
            try:
                from enhanced_oanda_service import enhanced_oanda
                oanda_symbol = symbol.replace("_OTC", "").replace("OTC", "")
                oanda_df = enhanced_oanda.get_candles(oanda_symbol, timeframe, count=days * 1440)
                if oanda_df is not None and not oanda_df.empty:
                    df = oanda_df.copy()
                    df['timestamp'] = pd.to_datetime(df.index, utc=True)
                    df = df.reset_index(drop=True)
            except Exception as e:
                logger.warning(f"OANDA fallback failed: {e}")
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No historical data for {symbol} {timeframe}. Import data first."
            )
        
        engine = BacktestingEngine(initial_balance=1000.0, trade_size=10.0)
        
        if model == "lstm_gru":
            predictor = create_lstm_model_predictor()
            if predictor is None:
                raise HTTPException(status_code=400, detail="LSTM model not trained")
            metrics = engine.run_ml_model_backtest(df, predictor, timeframe, 60, min_confidence)
            
        elif model == "ppo_rl":
            predictor = create_ppo_model_predictor()
            if predictor is None:
                raise HTTPException(status_code=400, detail="PPO model not trained")
            metrics = engine.run_ml_model_backtest(df, predictor, timeframe, 60, min_confidence)
            
        elif model == "ensemble":
            # Run both and average
            lstm_pred = create_lstm_model_predictor()
            ppo_pred = create_ppo_model_predictor()
            
            results = []
            if lstm_pred:
                m = engine.run_ml_model_backtest(df.copy(), lstm_pred, timeframe, 60, min_confidence)
                results.append(("lstm_gru", m))
            if ppo_pred:
                engine.reset()
                m = engine.run_ml_model_backtest(df.copy(), ppo_pred, timeframe, 60, min_confidence)
                results.append(("ppo_rl", m))
            
            return {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "model": model,
                "results": [{"model": n, "metrics": m.to_dict()} for n, m in results]
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model}")
        
        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "model": model,
            "data_points": len(df),
            "metrics": metrics.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ML backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

