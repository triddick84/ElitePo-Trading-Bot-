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
from trading_models import BacktestResult

from routes.models import BacktestRequest
import numpy as np


# Backtesting
@router.post("/backtest/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Run backtesting for a specific strategy"""
    try:
        from server import trading_bot
        result = await trading_bot.run_backtest(
            request.strategy, 
            request.symbol, 
            request.days
        )
        return result
        
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
