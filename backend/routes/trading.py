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
from force_signal_generator import force_signal_generator
from pocket_option_auto_trader import get_auto_trading_service
import time



# =============================================================================
# MONEY MANAGEMENT SYSTEM ENDPOINTS
# =============================================================================

@router.get("/money-management/status")
async def get_money_management_status():
    """
    Get money management system status and account state.
    """
    try:
        from money_management_system import money_management
        return {
            "success": True,
            **money_management.to_dict()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/money-management/calculate-stake")
async def calculate_optimal_stake(
    confidence: float = Query(..., ge=0, le=100, description="Signal confidence (0-100)"),
    balance: float = Query(default=None, description="Optional balance override"),
    atr: float = Query(default=0.0, description="Current ATR"),
    avg_atr: float = Query(default=0.0, description="Average ATR")
):
    """
    Calculate optimal stake size using Kelly Formula and risk management.
    
    Args:
        confidence: Signal confidence percentage
        balance: Optional account balance override
        atr: Current ATR for volatility adjustment
        avg_atr: Average ATR for comparison
        
    Returns:
        Recommended stake with risk assessment
    """
    try:
        from money_management_system import get_optimal_stake
        result = get_optimal_stake(confidence, balance, atr, avg_atr)
        return {
            "success": True,
            **result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/money-management/risk-check")
async def check_trading_risk(
    symbol: str = Query(..., description="Trading symbol"),
    open_positions: List[str] = Query(default=[], description="List of currently open positions"),
    atr: float = Query(default=0.0, description="Current ATR"),
    avg_atr: float = Query(default=0.0, description="Average ATR")
):
    """
    Run all 7 risk control scheme checks.
    
    Schemes:
    1. Fixed Capital Percentage
    2. Time-Based Filter (liquidity hours)
    3. Volatility Filter
    4. Correlation Analysis
    5. Diversification
    6. Trade Limit Per Session
    7. Periodic Review
    
    Returns:
        Risk check results with can_trade boolean
    """
    try:
        from money_management_system import run_risk_checks
        result = run_risk_checks(symbol, open_positions, atr, avg_atr)
        return {
            "success": True,
            **result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.put("/money-management/settings")
async def update_money_management_settings(
    balance: float = Query(default=None, description="Update account balance"),
    risk_level: str = Query(default=None, description="Risk level: conservative, moderate, aggressive")
):
    """
    Update money management settings.
    """
    try:
        from money_management_system import money_management
        if balance is not None:
            money_management.update_balance(balance)
        
        if risk_level:
            from money_management_system import RiskLevel
            try:
                new_level = RiskLevel(risk_level.lower())
                money_management.risk_level = new_level
                risk_pcts = {RiskLevel.CONSERVATIVE: 0.5, RiskLevel.MODERATE: 1.0, RiskLevel.AGGRESSIVE: 2.0}
                money_management.base_risk_pct = risk_pcts[new_level]
            except ValueError:
                return {"success": False, "error": f"Invalid risk level: {risk_level}"}
        
        return {
            "success": True,
            "message": "Settings updated",
            **money_management.to_dict()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/money-management/kelly-calculate")
async def kelly_formula_calculate(
    win_probability: float = Query(..., ge=0.01, le=0.99, description="Win probability (0-1)"),
    payout_rate: float = Query(default=0.85, description="Payout rate (e.g., 0.85 for 85%)"),
    fraction: float = Query(default=0.25, description="Kelly fraction (0.25 = quarter Kelly)")
):
    """
    Calculate Kelly Formula stake size.
    
    Formula: f = (bp - q) / b
    Where b=payout, p=win_prob, q=1-p
    """
    try:
        from money_management_system import KellyFormula
        
        full_kelly = KellyFormula.calculate(win_probability, payout_rate, 1.0)
        fractional_kelly = KellyFormula.calculate(win_probability, payout_rate, fraction)
        
        return {
            "success": True,
            "input": {
                "win_probability": win_probability,
                "payout_rate": payout_rate,
                "fraction": fraction
            },
            "result": {
                "full_kelly_pct": round(full_kelly, 2),
                "fractional_kelly_pct": round(fractional_kelly, 2),
                "recommendation": "Use fractional Kelly for safety"
            },
            "formula": f"f = ({payout_rate} × {win_probability} - {1-win_probability}) / {payout_rate}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



@router.get("/auto-trade/status")
async def get_auto_trade_status():
    """
    Get auto trading service status
    
    Returns connection state, balance, and trading statistics
    """
    try:
        service = get_auto_trading_service()
        return {
            "success": True,
            **service.get_status()
        }
    except Exception as e:
        logger.error(f"Auto trade status error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.post("/auto-trade/connect")
async def connect_auto_trade(ssid: str = None):
    """
    Connect to Pocket Option for auto trading
    
    Args:
        ssid: SSID authentication string. If not provided, uses stored SSID from .env
    
    Returns:
        Connection status
    """
    try:
        # Get SSID from parameter or environment
        if not ssid:
            ssid = os.getenv('POCKET_OPTION_SSID', '')
        
        if not ssid:
            return {
                "success": False,
                "message": "❌ No SSID provided. Please provide SSID or configure in .env"
            }
        
        # Connect
        service = get_auto_trading_service()
        success = await service.connect(ssid)
        
        if success:
            return {
                "success": True,
                "message": "✅ Connected to Pocket Option",
                "is_demo": service.ws_client.is_demo if service.ws_client else True,
                **service.get_status()
            }
        else:
            return {
                "success": False,
                "message": "❌ Failed to connect to Pocket Option"
            }
            
    except Exception as e:
        logger.error(f"Auto trade connect error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.post("/auto-trade/disconnect")
async def disconnect_auto_trade():
    """
    Disconnect from Pocket Option
    """
    try:
        service = get_auto_trading_service()
        await service.disconnect()
        
        return {
            "success": True,
            "message": "✅ Disconnected from Pocket Option"
        }
    except Exception as e:
        logger.error(f"Auto trade disconnect error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.post("/auto-trade/enable")
async def enable_auto_trade(enabled: bool = True):
    """
    Enable or disable auto trading
    
    Args:
        enabled: Whether to enable auto trading
    """
    try:
        service = get_auto_trading_service()
        service.enable_auto_trade(enabled)
        
        return {
            "success": True,
            "message": f"✅ Auto trading {'enabled' if enabled else 'disabled'}",
            "is_auto_trade_enabled": service.is_auto_trade_enabled
        }
    except Exception as e:
        logger.error(f"Enable auto trade error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.post("/auto-trade/execute-signal")
async def execute_signal_auto_trade(
    symbol: str = "EURUSD_otc",
    direction: str = "CALL",
    amount: float = 1.0,
    expiration: int = 60,
    probability: float = 80.0,
    strategy: str = "manual",
    send_telegram: bool = True
):
    """
    Execute a trading signal via auto trade
    
    Args:
        symbol: Asset symbol
        direction: Trade direction (CALL/PUT)
        amount: Trade amount
        expiration: Expiration in seconds
        probability: Signal probability/confidence
        strategy: Strategy name
        send_telegram: Send notification to Telegram
    
    Returns:
        Trade execution result
    """
    try:
        service = get_auto_trading_service()
        
        if not service.is_running:
            return {
                "success": False,
                "message": "❌ Auto trading service not connected. Call /auto-trade/connect first."
            }
        
        # Create signal dict
        signal = {
            "symbol": symbol,
            "direction": direction,
            "amount": amount,
            "expiration_seconds": expiration,
            "probability": probability,
            "strategy": strategy
        }
        
        # Execute
        trade = await service.execute_signal(signal)
        
        if trade:
            # Send to Telegram if requested
            if send_telegram:
                notifier = get_telegram_notifier()
                if notifier.config.is_valid():
                    await notifier.send_signal({
                        "symbol": symbol,
                        "direction": direction,
                        "probability": probability,
                        "timeframe": f"{expiration}s",
                        "market_type": "OTC" if "_otc" in symbol.lower() else "regular",
                        "expiration_minutes": expiration / 60,
                        "strategy_used": strategy,
                        "precision_entry_time": datetime.now(timezone.utc).isoformat()
                    })
            
            return {
                "success": True,
                "message": "✅ Trade executed successfully",
                "trade": trade.to_dict(),
                "telegram_sent": send_telegram
            }
        else:
            return {
                "success": False,
                "message": "❌ Failed to execute trade"
            }
            
    except Exception as e:
        logger.error(f"Execute signal error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.post("/auto-trade/execute-ai-signal")
async def execute_ai_signal_auto_trade(
    asset: str = "EURUSD_OTC",
    strategy: str = "fast_supertrend_catch",
    amount: float = 1.0,
    send_telegram: bool = True
):
    """
    Generate an AI signal and automatically execute it
    
    This combines signal generation with trade execution in one call.
    
    Args:
        asset: Asset symbol
        strategy: Strategy to use for signal generation
        amount: Trade amount
        send_telegram: Send notification to Telegram
    """
    try:
        service = get_auto_trading_service()
        
        if not service.is_running:
            return {
                "success": False,
                "message": "❌ Auto trading service not connected. Call /auto-trade/connect first."
            }
        
        # Generate signal based on strategy
        signal = None
        
        if strategy == "fast_supertrend_catch":
            from strategies.fast_supertrend_catch import get_fast_supertrend_strategy
            from real_market_data_service import RealMarketDataService
            
            strat = get_fast_supertrend_strategy()
            market_service = RealMarketDataService()
            
            # Get market data
            yahoo_data = market_service.get_yahoo_finance_data(asset.replace('_OTC', '').replace('_otc', ''))
            
            if yahoo_data:
                candle_data = []
                prices = yahoo_data.get('historical_prices', [])
                for p in prices:
                    candle_data.append({
                        'open': p * 0.999,
                        'high': p * 1.001,
                        'low': p * 0.998,
                        'close': p,
                        'volume': 10000
                    })
                signal = strat.analyze(asset, candle_data)
        else:
            # Use force signal generator
            from real_market_data_service import RealMarketDataService
            from trading_models import MarketData, AssetType
            
            market_service = RealMarketDataService()
            asset_type = AssetType.FOREX if 'usd' in asset.lower() or 'eur' in asset.lower() else AssetType.CRYPTO
            market_data = await market_service.get_market_data(asset, asset_type)
            
            if not market_data:
                market_data = MarketData(
                    symbol=asset,
                    current_price=1.05,
                    timestamp=datetime.now(timezone.utc),
                    historical_prices=[1.05 + i * 0.0001 for i in range(-100, 0)],
                    volume=1000000
                )
            
            from server import force_signal_generator
            signals = await force_signal_generator.force_generate_signal(
                symbol=asset,
                market_data=market_data,
                user_expirations=['5s']
            )
            
            if signals:
                s = signals[0]
                signal = {
                    "symbol": s.symbol,
                    "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                    "probability": s.probability,
                    "expiration_seconds": 5,
                    "strategy": strategy
                }
        
        if not signal:
            return {
                "success": False,
                "message": "❌ Could not generate signal - conditions not met"
            }
        
        # Add amount to signal
        signal['amount'] = amount
        
        # Execute the signal
        trade = await service.execute_signal(signal)
        
        if trade:
            # Send to Telegram
            if send_telegram:
                notifier = get_telegram_notifier()
                if notifier.config.is_valid():
                    await notifier.send_signal(signal)
            
            return {
                "success": True,
                "message": "✅ AI signal generated and executed",
                "signal": signal,
                "trade": trade.to_dict(),
                "telegram_sent": send_telegram
            }
        else:
            return {
                "success": False,
                "message": "❌ Signal generated but trade execution failed",
                "signal": signal
            }
            
    except Exception as e:
        logger.error(f"Execute AI signal error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.put("/auto-trade/settings")
async def update_auto_trade_settings(
    amount: float = None,
    min_probability: float = None,
    max_trades_per_minute: int = None
):
    """
    Update auto trading settings
    
    Args:
        amount: Default trade amount
        min_probability: Minimum signal probability to execute
        max_trades_per_minute: Rate limit for trades
    """
    try:
        service = get_auto_trading_service()
        
        if amount is not None:
            service.set_trade_amount(amount)
        
        if min_probability is not None:
            service.set_min_probability(min_probability)
        
        if max_trades_per_minute is not None:
            service.max_trades_per_minute = max(1, min(60, max_trades_per_minute))
        
        return {
            "success": True,
            "message": "✅ Settings updated",
            **service.get_status()
        }
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




@router.get("/auto-trade/history")
async def get_auto_trade_history(limit: int = 50):
    """
    Get auto trade history
    
    Args:
        limit: Maximum number of trades to return
    """
    try:
        service = get_auto_trading_service()
        
        return {
            "success": True,
            "trades": service.get_trade_history(limit),
            "stats": service.stats.to_dict()
        }
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }




# ============================================================================
# TRADE EXECUTOR ENDPOINTS (Bridge Script Integration)
# ============================================================================

@router.post("/trade-executor/queue")
async def queue_trade_for_bridge(
    asset: str = "EURUSD_otc",
    direction: str = "call",
    amount: float = 1.0,
    duration: int = 60
):
    """
    Queue a trade for bridge script execution
    
    This adds a trade to the pending queue that the bridge script will pick up
    and execute in the browser.
    
    Args:
        asset: Asset symbol (e.g., 'EURUSD_otc')
        direction: 'call' or 'put'
        amount: Trade amount in dollars
        duration: Trade duration in seconds
    """
    try:
        from trade_executor import get_trade_executor
        from auto_execution_mode import get_auto_execution
        
        # Ensure we're in BRIDGE mode
        auto_exec = await get_auto_execution(db)
        current_mode = auto_exec.get_mode()
        
        if current_mode != "BRIDGE":
            auto_exec.set_mode("BRIDGE")
            logger.info("🔄 Switched to BRIDGE mode for trade queueing")
        
        executor = await get_trade_executor(db)
        result = await executor.execute_trade(
            asset=asset,
            direction=direction,
            amount=amount,
            duration=duration,
            strategy="manual_bridge",
            confidence=95.0
        )
        
        # Get pending trades to confirm
        pending = await executor.get_pending_trades()
        
        return {
            "success": True,
            "message": "Trade queued for bridge execution",
            "order_id": result.get('order_id'),
            "status": result.get('status'),
            "pending_count": len(pending),
            "trade_details": {
                "asset": asset,
                "direction": direction,
                "amount": amount,
                "duration": duration
            }
        }
        
    except Exception as e:
        logger.error(f"Error queueing trade: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/trade-executor/pending")
async def get_pending_trades_for_bridge():
    """
    Get pending trades waiting for bridge execution
    
    This endpoint is called by the frontend bridge script to get trades to execute
    """
    try:
        from trade_executor import get_trade_executor
        
        executor = await get_trade_executor(db)
        pending_trades = await executor.get_pending_trades()
        
        return {
            "success": True,
            "pending_trades": pending_trades,
            "count": len(pending_trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending trades: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/trade-executor/confirm-execution")
async def confirm_trade_execution(request: Request):
    """
    Confirm trade execution from bridge
    
    Called by bridge script when it successfully executes a trade
    
    Body:
    - order_id: Our internal order ID
    - bridge_order_id: Pocket Option's order ID
    - execution_price: Price at execution
    - execution_time: ISO timestamp
    """
    try:
        data = await request.json()
        
        from trade_executor import get_trade_executor
        
        executor = await get_trade_executor(db)
        result = await executor.confirm_execution(
            order_id=data.get('order_id'),
            bridge_order_id=data.get('bridge_order_id'),
            execution_price=data.get('execution_price'),
            execution_time=data.get('execution_time')
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error confirming execution: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/trade-executor/report-result")
async def report_trade_result_from_bridge(request: Request):
    """
    Report trade result from bridge
    
    Called by bridge script when trade expires
    
    Body:
    - order_id: Our internal order ID
    - result: 'win', 'loss', or 'draw'
    - profit: Profit amount (can be negative)
    - close_price: Closing price
    - close_time: ISO timestamp
    """
    try:
        data = await request.json()
        
        from trade_executor import get_trade_executor
        
        executor = await get_trade_executor(db)
        result = await executor.report_trade_result(
            order_id=data.get('order_id'),
            result=data.get('result'),
            profit=data.get('profit'),
            close_price=data.get('close_price'),
            close_time=data.get('close_time')
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error reporting trade result: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/trade-executor/statistics")
async def get_trade_executor_statistics():
    """Get trade executor statistics"""
    try:
        from trade_executor import get_trade_executor
        
        executor = await get_trade_executor(db)
        stats = executor.get_statistics()
        
        return {
            "success": True,
            **stats
        }
        
    except Exception as e:
        logger.error(f"Error getting executor statistics: {e}")
        return {
            "success": False,
            "error": str(e)
        }




# ============================================================================
# AUTOMATED TRADING ENDPOINTS
# ============================================================================

@router.get("/automated-trading/status")
async def get_automated_trading_status():
    """Get automated trading status and statistics"""
    try:
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        stats = service.get_statistics()
        
        return {
            "success": True,
            **stats
        }
        
    except Exception as e:
        logger.error(f"Error getting automated trading status: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/automated-trading/enable")
async def enable_automated_trading():
    """Enable automated trading"""
    try:
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        await service.enable()
        
        return {
            "success": True,
            "message": "Automated trading enabled",
            "is_enabled": service.is_enabled
        }
        
    except Exception as e:
        logger.error(f"Error enabling automated trading: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/automated-trading/disable")
async def disable_automated_trading():
    """Disable automated trading"""
    try:
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        await service.disable()
        
        return {
            "success": True,
            "message": "Automated trading disabled",
            "is_enabled": service.is_enabled
        }
        
    except Exception as e:
        logger.error(f"Error disabling automated trading: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/automated-trading/toggle")
async def toggle_automated_trading(request: dict):
    """Toggle automated trading on/off"""
    try:
        enabled = request.get("enabled", False)
        
        # Update config
        await db.bot_config.update_one(
            {"_id": "trading_config"},
            {"$set": {"auto_trade_enabled": enabled}},
            upsert=True
        )
        
        return {
            "success": True,
            "message": f"Auto-trading {'enabled' if enabled else 'disabled'}",
            "auto_trade_enabled": enabled
        }
    except Exception as e:
        logger.error(f"Error toggling automated trading: {e}")
        return {"success": False, "error": str(e)}




@router.get("/automated-trading/config")
async def get_automated_trading_config_v2():
    """Get automated trading configuration"""
    try:
        config = await db.bot_config.find_one({"_id": "trading_config"}, {"_id": 0})
        return config or {
            "auto_trade_enabled": False,
            "min_confidence": 75,
            "max_trades_per_hour": 10,
            "max_trades_per_day": 50,
            "cooldown_seconds": 30,
            "account_type": "demo",
            "money_management": {
                "mode": "fixed",
                "base_amount": 1,
                "martingale_multiplier": 2,
                "martingale_max_steps": 5
            }
        }
    except Exception as e:
        logger.error(f"Error getting automated trading config: {e}")
        return {}




@router.post("/automated-trading/config")
async def update_automated_trading_config(request: Request):
    """
    Update automated trading configuration
    
    Body:
    - default_stake: Default stake amount
    - max_concurrent_trades: Maximum concurrent trades
    - min_confidence: Minimum confidence threshold
    - use_money_management: Enable Kelly Formula
    - use_risk_rules: Enable risk management rules
    """
    try:
        data = await request.json()
        
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        await service.update_config(data)
        
        return {
            "success": True,
            "message": "Configuration updated",
            "config": service.get_statistics()['config']
        }
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/automated-trading/active-orders")
async def get_active_orders():
    """Get list of active orders"""
    try:
        from automated_trading_service import get_automated_trading_service
        
        service = await get_automated_trading_service(db)
        
        return {
            "success": True,
            "active_orders": list(service.active_orders.values()),
            "count": len(service.active_orders)
        }
        
    except Exception as e:
        logger.error(f"Error getting active orders: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/automated-trading/trade-history")
async def get_trade_history(limit: int = 50):
    """Get recent trade history"""
    try:
        trades = await db.automated_trades.find(
            {"user_id": "default_user"},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(length=limit)
        
        return {
            "success": True,
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/execution-mode/set")
async def set_execution_mode(mode: str = "DEMO"):
    """
    Set the trade execution mode
    
    Args:
        mode: "DEMO", "BRIDGE", "API", or "HEADLESS"
        
    - DEMO: Simulates trades (for testing)
        - BRIDGE: Requires manual browser Bridge Script setup
        - API: Direct API (not implemented)
        - HEADLESS: Uses Playwright browser automation (REAL TRADING)
    """
    try:
        valid_modes = ["DEMO", "BRIDGE", "API", "HEADLESS"]
        if mode.upper() not in valid_modes:
            return {
                "success": False,
                "error": f"Invalid mode. Must be one of: {valid_modes}"
            }
        
        from auto_execution_mode import get_auto_execution
        
        auto_exec = await get_auto_execution(db)
        auto_exec.set_mode(mode.upper())
        
        return {
            "success": True,
            "mode": mode.upper(),
            "message": f"Execution mode set to {mode.upper()}"
        }
        
    except Exception as e:
        logger.error(f"Error setting execution mode: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/execution-mode/current")
async def get_current_execution_mode():
    """Get current execution mode and statistics"""
    try:
        from auto_execution_mode import get_auto_execution
        
        auto_exec = await get_auto_execution(db)
        stats = auto_exec.get_statistics()
        
        return {
            "success": True,
            **stats
        }
        
    except Exception as e:
        logger.error(f"Error getting execution mode: {e}")
        return {
            "success": False,
            "error": str(e)
        }


