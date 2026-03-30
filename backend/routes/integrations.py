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
from tradingview_webhook_service import TradingViewAlertModel
from force_signal_generator import force_signal_generator
from pocket_option_auto_trader import get_auto_trading_service
from telegram_signal_notifier import get_telegram_notifier
from platform_integrations import platform_integration

# Import MT5 services (may not be available on all platforms)
try:
    from mt5_trading_service import mt5_service, get_mt5_service
except ImportError:
    mt5_service = None
    get_mt5_service = None

try:
    from mt5_zeromq_bridge import mt5_zmq_bridge, mt5_integration, get_mt5_bridge, get_mt5_integration
except ImportError:
    mt5_zmq_bridge = None
    mt5_integration = None
    get_mt5_bridge = None
    get_mt5_integration = None

from routes.models import TelegramMessageRequest, TelegramSettingsRequest, TradingViewAlert, MT5Config, MT5TradeRequest, ArbitrageCheckRequest, OandaConfigRequest
import traceback
import numpy as np
import time



# ==================== METATRADER 5 INTEGRATION ENDPOINTS ====================

@router.get("/mt5/status")
async def get_mt5_status():
    """Get MetaTrader 5 connection status"""
    return {
        "success": True,
        "status": mt5_service.connection.get_status()
    }




@router.post("/mt5/connect")
async def connect_mt5(
    login: int = Query(None, description="MT5 account number"),
    password: str = Query(None, description="MT5 password"),
    server: str = Query(None, description="MT5 broker server name")
):
    """
    Connect to MetaTrader 5
    
    Credentials can be provided via query parameters or environment variables:
    - MT5_LOGIN
    - MT5_PASSWORD
    - MT5_SERVER
    """
    result = mt5_service.connect(login=login, password=password, server=server)
    return result




@router.post("/mt5/disconnect")
async def disconnect_mt5():
    """Disconnect from MetaTrader 5"""
    return mt5_service.disconnect()




@router.get("/mt5/account")
async def get_mt5_account():
    """Get MetaTrader 5 account information"""
    account = mt5_service.get_account_info()
    
    if account:
        return {
            "success": True,
            "account": account.to_dict()
        }
    else:
        return {
            "success": False,
            "message": "Failed to get account info. Is MT5 connected?"
        }




@router.get("/mt5/symbol/{symbol}")
async def get_mt5_symbol_info(symbol: str):
    """Get information about a trading symbol"""
    info = mt5_service.get_symbol_info(symbol)
    
    if info:
        return {
            "success": True,
            "symbol_info": info
        }
    else:
        return {
            "success": False,
            "message": f"Symbol {symbol} not found"
        }




@router.post("/mt5/order")
async def execute_mt5_order(
    symbol: str = Query(..., description="Trading symbol (e.g., EURUSD)"),
    direction: str = Query(..., description="BUY/CALL or SELL/PUT"),
    volume: float = Query(0.1, description="Trade volume in lots"),
    stop_loss: float = Query(None, description="Stop loss price"),
    take_profit: float = Query(None, description="Take profit price"),
    comment: str = Query("Signal Bot", description="Order comment")
):
    """
    Execute a trading order on MetaTrader 5
    
    Args:
        symbol: Trading symbol (e.g., EURUSD)
        direction: BUY/CALL or SELL/PUT
        volume: Trade volume in lots (default 0.1)
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
        comment: Order comment
    """
    result = mt5_service.execute_order(
        symbol=symbol,
        direction=direction,
        volume=volume,
        stop_loss=stop_loss,
        take_profit=take_profit,
        comment=comment
    )
    
    return {
        "success": result.success,
        "trade": result.to_dict()
    }




@router.post("/mt5/signal/process")
async def process_mt5_signal(
    symbol: str = Query(..., description="Trading symbol"),
    direction: str = Query(..., description="CALL/BUY or PUT/SELL"),
    confidence: float = Query(..., description="Signal confidence 0-100"),
    volume: float = Query(0.1, description="Trade volume in lots"),
    stop_loss: float = Query(None, description="Stop loss price"),
    take_profit: float = Query(None, description="Take profit price"),
    strategy_name: str = Query("High Accuracy Bot", description="Strategy name")
):
    """
    Process a trading signal and execute on MetaTrader 5
    
    Only executes if confidence >= 65%
    """
    result = mt5_service.process_signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        volume=volume,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy_name=strategy_name
    )
    
    return result




@router.get("/mt5/positions")
async def get_mt5_positions():
    """Get all open positions in MetaTrader 5"""
    positions = mt5_service.get_positions()
    
    return {
        "success": True,
        "positions": [p.to_dict() for p in positions],
        "count": len(positions),
        "total_profit": sum(p.profit for p in positions)
    }




@router.post("/mt5/positions/{ticket}/close")
async def close_mt5_position(ticket: int, comment: str = "Closed by API"):
    """Close an open position by ticket number"""
    result = mt5_service.close_position(ticket, comment)
    
    return {
        "success": result.success,
        "result": result.to_dict()
    }




@router.put("/mt5/positions/{ticket}/modify")
async def modify_mt5_position(
    ticket: int,
    stop_loss: float = Query(None, description="New stop loss"),
    take_profit: float = Query(None, description="New take profit")
):
    """Modify stop loss and/or take profit of an open position"""
    if stop_loss is None and take_profit is None:
        raise HTTPException(status_code=400, detail="Must specify stop_loss or take_profit")
    
    result = mt5_service.modify_position(ticket, stop_loss, take_profit)
    
    return {
        "success": result.success,
        "result": result.to_dict()
    }




@router.get("/mt5/history")
async def get_mt5_trade_history(limit: int = 50):
    """Get recent trade execution history"""
    return mt5_service.get_trade_history(limit)




# ==================== MT5 ZEROMQ BRIDGE ENDPOINTS ====================

@router.get("/mt5-zmq/status")
async def get_mt5_zmq_status():
    """Get MT5 ZeroMQ bridge connection status"""
    return {
        "success": True,
        "bridge": mt5_zmq_bridge.get_status()
    }




@router.post("/mt5-zmq/connect")
async def connect_mt5_zmq(
    host: str = Query("localhost", description="MT5 terminal IP address"),
    sub_port: int = Query(15555, description="ZeroMQ SUB port"),
    push_port: int = Query(15556, description="ZeroMQ PUSH port")
):
    """
    Connect to MT5 via ZeroMQ bridge
    
    Requirements:
    - MT5 terminal running on Windows with ZeroMQ EA installed
    - Firewall allowing connections on specified ports
    """
    mt5_zmq_bridge.config.host = host
    mt5_zmq_bridge.config.sub_port = sub_port
    mt5_zmq_bridge.config.push_port = push_port
    
    success = await mt5_zmq_bridge.connect()
    
    return {
        "success": success,
        "status": mt5_zmq_bridge.get_status()
    }




@router.post("/mt5-zmq/order")
async def place_mt5_zmq_order(
    symbol: str = Query(..., description="Trading symbol (e.g., EURUSD)"),
    direction: str = Query(..., description="BUY or SELL"),
    volume: float = Query(0.01, description="Trade volume in lots"),
    stop_loss: float = Query(0, description="Stop loss price"),
    take_profit: float = Query(0, description="Take profit price"),
    comment: str = Query("GPT Signal Bot", description="Order comment")
):
    """
    Place a market order via MT5 ZeroMQ bridge
    """
    result = await mt5_zmq_bridge.place_market_order(
        symbol=symbol,
        order_type=direction.upper(),
        volume=volume,
        stop_loss=stop_loss,
        take_profit=take_profit,
        comment=comment
    )
    
    return {
        "success": result.success,
        "ticket": result.ticket,
        "message": result.message
    }




@router.post("/mt5-zmq/close/{ticket}")
async def close_mt5_zmq_position(ticket: int):
    """Close a position via MT5 ZeroMQ bridge"""
    result = await mt5_zmq_bridge.close_position(ticket)
    return {
        "success": result.success,
        "message": result.message
    }




@router.get("/mt5-zmq/positions")
async def get_mt5_zmq_positions():
    """Get all open positions via MT5 ZeroMQ bridge"""
    positions = await mt5_zmq_bridge.get_positions()
    return {
        "success": True,
        "positions": positions
    }




@router.get("/mt5-zmq/account")
async def get_mt5_zmq_account():
    """Get account info via MT5 ZeroMQ bridge"""
    account = await mt5_zmq_bridge.get_account_info()
    return {
        "success": True,
        "account": account
    }




@router.post("/mt5-zmq/execute-signal")
async def execute_signal_on_mt5(
    symbol: str = Query(..., description="Trading symbol"),
    direction: str = Query(..., description="CALL/BUY or PUT/SELL"),
    volume: float = Query(0.01, description="Lot size"),
    stop_loss: float = Query(0, description="Stop loss price"),
    take_profit: float = Query(0, description="Take profit price")
):
    """
    Execute a trading signal on MT5 via ZeroMQ
    
    Translates signal format (CALL/PUT) to MT5 format (BUY/SELL)
    """
    # Translate direction
    if direction.upper() in ["CALL", "BUY"]:
        order_type = "BUY"
    elif direction.upper() in ["PUT", "SELL"]:
        order_type = "SELL"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid direction: {direction}")
    
    result = await mt5_zmq_bridge.place_market_order(
        symbol=symbol.replace("_OTC", "").replace("_", ""),
        order_type=order_type,
        volume=volume,
        stop_loss=stop_loss,
        take_profit=take_profit,
        comment=f"GPT Signal: {direction}"
    )
    
    return {
        "success": result.success,
        "ticket": result.ticket,
        "message": result.message,
        "direction": order_type,
        "symbol": symbol
    }




# ==================== TRADINGVIEW WEBHOOK INTEGRATION ====================

@router.post("/tradingview/webhook")
async def tradingview_webhook(alert: TradingViewAlertModel):
    """
    Receive webhook alerts from TradingView
    
    Configure in TradingView:
    1. Create alert on your chart/indicator
    2. Set webhook URL to: {your-domain}/api/tradingview/webhook
    3. Use JSON message format:
    {
        "action": "buy",
        "symbol": "EURUSD",
        "price": {{close}},
        "passphrase": "gpt-signal",
        "destination": "mt5"
    }
    """
    try:
        # Process the alert
        processed = tradingview_webhook_service.process_alert(alert.dict())
        
        # If valid, route to appropriate destination
        execution_result = None
        
        if processed.is_valid:
            if processed.destination in [DestinationBroker.MT5, DestinationBroker.ALL]:
                # Execute on MT5
                try:
                    mt5_result = await mt5_zmq_bridge.place_market_order(
                        symbol=processed.symbol,
                        order_type="BUY" if processed.action in [AlertAction.BUY, AlertAction.CALL] else "SELL",
                        volume=processed.quantity,
                        stop_loss=processed.stop_loss or 0,
                        take_profit=processed.take_profit or 0,
                        comment=f"TV: {processed.strategy}"
                    )
                    execution_result = {
                        "mt5": {
                            "success": mt5_result.success,
                            "ticket": mt5_result.ticket
                        }
                    }
                except Exception as e:
                    execution_result = {"mt5": {"success": False, "error": str(e)}}
            
            if processed.destination in [DestinationBroker.POCKET_OPTION, DestinationBroker.ALL]:
                # Store as internal signal for Pocket Option Tampermonkey
                execution_result = execution_result or {}
                execution_result["pocket_option"] = {
                    "success": True,
                    "message": "Signal queued for Pocket Option auto-trader"
                }
            
            processed.execution_status = "executed"
            processed.execution_result = execution_result
        
        return {
            "success": processed.is_valid,
            "alert": processed.to_dict()
        }
        
    except Exception as e:
        logger.error(f"TradingView webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import AlertAction and DestinationBroker for the endpoint
from tradingview_webhook_service import AlertAction, DestinationBroker




@router.get("/tradingview/history")
async def get_tradingview_alert_history(limit: int = 50):
    """Get recent TradingView alert history"""
    return {
        "success": True,
        "alerts": tradingview_webhook_service.get_alert_history(limit)
    }




@router.get("/tradingview/stats")
async def get_tradingview_stats():
    """Get TradingView alert statistics"""
    return {
        "success": True,
        "stats": tradingview_webhook_service.get_alert_stats()
    }




@router.get("/tradingview/setup")
async def get_tradingview_setup_instructions(request: Request):
    """Get instructions for setting up TradingView webhooks"""
    base_url = str(request.base_url).rstrip("/")
    return {
        "success": True,
        "instructions": tradingview_webhook_service.get_webhook_setup_instructions(base_url)
    }




@router.get("/tradingview/pine-script")
async def get_tradingview_pine_script():
    """Get Pine Script template for TradingView alerts"""
    return {
        "success": True,
        "template": tradingview_webhook_service.generate_pine_script_template()
    }





# ============================================================================
# POCKET OPTION LIVE BRIDGE ENDPOINTS
# ============================================================================

@router.post("/bridge/ws-stream")
async def receive_bridge_ws_stream(request: Request):
    """
    Receive WebSocket data from browser bridge
    
    This endpoint receives forwarded WebSocket messages from the
    Pocket Option browser extension/bridge script
    """
    try:
        data = await request.json()
        
        from pocket_option_live import get_pocket_option_bridge
        bridge = get_pocket_option_bridge()
        
        result = bridge.receive_message(data)
        return result
        
    except Exception as e:
        logger.error(f"Bridge stream error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/bridge/connected")
async def bridge_connected_notification(request: Request):
    """Notification when bridge WebSocket connects"""
    try:
        data = await request.json()
        logger.info(f"🔗 Bridge connected from: {data.get('url', 'unknown')}")
        
        # If SSID is provided, update the auto-trader
        if data.get('ssid'):
            service = get_auto_trading_service()
            if not service.is_running:
                logger.info("📱 Attempting to connect auto-trader with bridge SSID...")
        
        return {"success": True, "message": "Connection acknowledged"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/bridge/disconnected")
async def bridge_disconnected_notification(request: Request):
    """Notification when bridge WebSocket disconnects"""
    try:
        data = await request.json()
        logger.warning(f"🔌 Bridge disconnected: {data.get('url', 'unknown')} - Code: {data.get('code')}")
        return {"success": True, "message": "Disconnection acknowledged"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/bridge/ssid-update")
async def bridge_ssid_update(request: Request):
    """
    Receive SSID update from browser bridge
    This allows auto-trading to use the captured SSID
    """
    try:
        data = await request.json()
        ssid = data.get('ssid')
        is_demo = data.get('isDemo', True)
        
        if not ssid:
            return {"success": False, "message": "No SSID provided"}
        
        logger.info(f"🔑 SSID received from bridge (Demo: {is_demo})")
        
        # Store in environment
        os.environ['POCKET_OPTION_SSID'] = ssid
        
        # Try to connect auto-trader with new SSID
        service = get_auto_trading_service()
        if not service.is_running:
            success = await service.connect(ssid)
            if success:
                logger.info("✅ Auto-trader connected with bridge SSID!")
                
                # Notify via Telegram
                notifier = get_telegram_notifier()
                if notifier.config.is_valid():
                    await notifier.send_status(
                        "🔗 Bridge Connected",
                        {
                            "Mode": "Demo" if is_demo else "Real",
                            "Auto-Trade": "Ready"
                        }
                    )
                
                return {
                    "success": True,
                    "message": "✅ SSID received and auto-trader connected",
                    "auto_trade_status": service.get_status()
                }
        
        return {
            "success": True,
            "message": "✅ SSID received and stored",
            "is_demo": is_demo
        }
        
    except Exception as e:
        logger.error(f"SSID update error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/bridge/balance-update")
async def bridge_balance_update(request: Request):
    """Receive balance update from browser bridge"""
    try:
        data = await request.json()
        balance = data.get('balance', 0)
        is_demo = data.get('isDemo', True)
        
        logger.info(f"💰 Balance update from bridge: ${balance:.2f} ({'Demo' if is_demo else 'Real'})")
        
        # Update auto-trader balance if connected
        service = get_auto_trading_service()
        if service.ws_client:
            service.ws_client.balance = balance
        
        return {"success": True, "balance": balance}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/bridge/heartbeat")
async def bridge_heartbeat(request: Request):
    """Bridge keepalive heartbeat"""
    try:
        data = await request.json()
        
        from pocket_option_live import get_pocket_option_bridge
        bridge = get_pocket_option_bridge()
        bridge.last_message_time = datetime.now(timezone.utc)
        bridge.is_connected = True
        
        # Update ALL connection status fields properly
        bridge.connection_status['connected'] = True
        bridge.connection_status['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        bridge.connection_status['active_connections'] = data.get('activeConnections', 0)
        bridge.connection_status['ssid_present'] = data.get('ssid') == 'present'
        bridge.connection_status['is_demo'] = data.get('isDemo')
        bridge.connection_status['balance'] = data.get('balance', 0)
        bridge.connection_status['error'] = None
        
        logger.info(f"💓 Bridge heartbeat received - Balance: ${data.get('balance', 0)}")
        
        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messages_received": bridge.message_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/bridge/status")
async def get_bridge_status():
    """Get bridge connection status"""
    try:
        from pocket_option_live import get_pocket_option_bridge
        bridge = get_pocket_option_bridge()
        
        return {
            "success": True,
            **bridge.get_status()
        }
    except Exception as e:
        logger.error(f"Bridge status error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/script")
async def get_bridge_script():
    """
    Get the browser bridge script to paste in Pocket Option console
    """
    try:
        from pocket_option_live import get_bridge_script
        
        # Get the app URL from environment
        import os
        app_url = os.environ.get('REACT_APP_BACKEND_URL', '')
        
        if not app_url:
            # Try to read from frontend .env
            try:
                with open('/app/frontend/.env', 'r') as f:
                    for line in f:
                        if line.startswith('REACT_APP_BACKEND_URL='):
                            app_url = line.split('=')[1].strip()
                            break
            except:
                pass
        
        script = get_bridge_script(app_url)
        
        return {
            "success": True,
            "script": script,
            "instructions": [
                "1. Open Pocket Option in your browser and log in",
                "2. Navigate to the trading interface",
                "3. Open Developer Tools (F12 or Right-click → Inspect)",
                "4. Go to the Console tab",
                "5. Paste the entire script below and press Enter",
                "6. You should see '✅ Bridge script installed!'",
                "7. Navigate to different assets to load their data"
            ],
            "app_url": app_url
        }
    except Exception as e:
        logger.error(f"Error generating bridge script: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/simple-script")
async def get_simple_bridge_script():
    """
    Get a SIMPLIFIED bridge script - only for trade execution
    Use this if the full bridge has connection issues
    """
    try:
        import os
        app_url = os.environ.get('REACT_APP_BACKEND_URL', '')
        
        if not app_url:
            try:
                with open('/app/frontend/.env', 'r') as f:
                    for line in f:
                        if line.startswith('REACT_APP_BACKEND_URL='):
                            app_url = line.split('=')[1].strip()
                            break
            except:
                pass
        
        # Simplified script focused only on trade execution
        script = f'''
// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║       POCKET OPTION SIMPLE TRADE BOT v3.0 - Trade Execution Only          ║
// ║              Works on DEMO and REAL accounts                               ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

(function() {{
  'use strict';
  
  const SERVER = '{app_url}';
  let pollCount = 0;
  let tradesExecuted = 0;
  let lastTradeId = null;
  
  console.log('%c🚀 Simple Trade Bot Starting...', 'color: #00ff00; font-size: 18px; font-weight: bold;');
  console.log('%c📡 Server: ' + SERVER, 'color: #00bfff; font-size: 14px;');
  
  // ═══════════════════════════════════════════════════════════════════════════
  // TRADE BUTTON FINDER - Works for both Demo and Real
  // ═══════════════════════════════════════════════════════════════════════════
  
  function findTradeButton(direction) {{
    const isCall = direction.toLowerCase() === 'call';
    
    // Method 1: Look for buttons with specific classes
    const classPatterns = isCall 
      ? ['btn-call', 'call', 'higher', 'green', 'up', 'buy']
      : ['btn-put', 'put', 'lower', 'red', 'down', 'sell'];
    
    // Search all clickable elements
    const clickables = document.querySelectorAll('button, div[role="button"], a[role="button"], span[role="button"], [class*="btn"], [class*="button"]');
    
    for (const el of clickables) {{
      const classes = (el.className || '').toLowerCase();
      const text = (el.textContent || '').toLowerCase();
      const dataDir = (el.getAttribute('data-dir') || '').toLowerCase();
      
      // Check class names
      for (const pattern of classPatterns) {{
        if (classes.includes(pattern)) {{
          console.log(`%c✓ Found ${{direction}} button by class: ${{pattern}}`, 'color: #00ff00');
          return el;
        }}
      }}
      
      // Check text content
      const textPatterns = isCall
        ? ['higher', 'call', 'up', 'вверх', 'выше', 'купить']
        : ['lower', 'put', 'down', 'вниз', 'ниже', 'продать'];
      
      for (const pattern of textPatterns) {{
        if (text.includes(pattern)) {{
          console.log(`%c✓ Found ${{direction}} button by text: ${{pattern}}`, 'color: #00ff00');
          return el;
        }}
      }}
      
      // Check data attributes
      if (dataDir === direction.toLowerCase() || dataDir === (isCall ? 'higher' : 'lower')) {{
        console.log(`%c✓ Found ${{direction}} button by data-dir`, 'color: #00ff00');
        return el;
      }}
    }}
    
    // Method 2: Try to find by color (green for call, red for put)
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {{
      if (el.offsetWidth > 50 && el.offsetHeight > 30) {{ // Reasonable button size
        const style = window.getComputedStyle(el);
        const bgColor = style.backgroundColor;
        
        if (isCall && (bgColor.includes('0, 128') || bgColor.includes('0, 255') || bgColor.includes('34, 139'))) {{
          if (el.offsetParent !== null) {{ // Is visible
            console.log(`%c✓ Found CALL button by green color`, 'color: #00ff00');
            return el;
          }}
        }}
        if (!isCall && (bgColor.includes('255, 0') || bgColor.includes('220, 53') || bgColor.includes('239, 68'))) {{
          if (el.offsetParent !== null) {{
            console.log(`%c✓ Found PUT button by red color`, 'color: #ff6600');
            return el;
          }}
        }}
      }}
    }}
    
    // Method 3: Position-based (usually call is on left/top, put is on right/bottom)
    const tradingPanels = document.querySelectorAll('[class*="trading"], [class*="deal"], [class*="order"], [class*="trade"]');
    for (const panel of tradingPanels) {{
      const buttons = panel.querySelectorAll('button');
      if (buttons.length >= 2) {{
        console.log(`%c✓ Found buttons in trading panel, using position`, 'color: #ffff00');
        return isCall ? buttons[0] : buttons[buttons.length - 1];
      }}
    }}
    
    return null;
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // SET TRADE AMOUNT
  // ═══════════════════════════════════════════════════════════════════════════
  
  function setAmount(amount) {{
    const inputs = document.querySelectorAll('input[type="number"], input[type="text"], input[class*="amount"], input[class*="input"]');
    
    for (const input of inputs) {{
      const placeholder = (input.placeholder || '').toLowerCase();
      const classes = (input.className || '').toLowerCase();
      const name = (input.name || '').toLowerCase();
      
      if (classes.includes('amount') || name.includes('amount') || placeholder.includes('amount') || placeholder.includes('сумма')) {{
        input.value = amount;
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        console.log(`%c💰 Amount set to: $${{amount}}`, 'color: #00bfff');
        return true;
      }}
    }}
    
    // Try clicking on amount display and typing
    const amountDisplays = document.querySelectorAll('[class*="amount"], [class*="value"]');
    for (const display of amountDisplays) {{
      if (display.textContent && display.textContent.match(/\\$?\\d+/)) {{
        display.click();
        return true;
      }}
    }}
    
    return false;
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // EXECUTE TRADE
  // ═══════════════════════════════════════════════════════════════════════════
  
  async function executeTrade(trade) {{
    const {{ order_id, direction, amount, asset }} = trade;
    
    console.log(`%c🎯 EXECUTING: ${{direction.toUpperCase()}} $${{amount}} on ${{asset}}`, 'color: #ff00ff; font-size: 14px; font-weight: bold;');
    
    // Set amount first
    setAmount(amount);
    await sleep(300);
    
    // Find and click trade button
    const button = findTradeButton(direction);
    
    if (button) {{
      // Highlight the button briefly
      const originalBg = button.style.backgroundColor;
      button.style.backgroundColor = direction === 'call' ? '#00ff00' : '#ff0000';
      button.style.transform = 'scale(1.1)';
      
      await sleep(200);
      
      // Click!
      button.click();
      
      // Restore style
      setTimeout(() => {{
        button.style.backgroundColor = originalBg;
        button.style.transform = '';
      }}, 500);
      
      tradesExecuted++;
      lastTradeId = order_id;
      
      console.log(`%c✅ TRADE EXECUTED! Order: ${{order_id}} | Total trades: ${{tradesExecuted}}`, 'color: #00ff00; font-size: 14px; font-weight: bold;');
      
      // Report success to server
      await reportExecution(order_id, true);
      return true;
    }} else {{
      console.log(`%c❌ Could not find ${{direction.toUpperCase()}} button!`, 'color: #ff0000; font-size: 14px;');
      console.log('%c💡 Make sure you are on the trading page with the chart visible', 'color: #ffff00');
      
      // Report failure
      await reportExecution(order_id, false);
      return false;
    }}
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // SERVER COMMUNICATION
  // ═══════════════════════════════════════════════════════════════════════════
  
  async function checkForTrades() {{
    try {{
      const response = await fetch(`${{SERVER}}/api/trade-executor/pending`);
      const data = await response.json();
      
      if (data.success && data.pending_trades && data.pending_trades.length > 0) {{
        console.log(`%c📋 Found ${{data.pending_trades.length}} pending trade(s)!`, 'color: #00ff00; font-size: 14px;');
        
        for (const trade of data.pending_trades) {{
          // Skip if we already executed this trade
          if (trade.order_id === lastTradeId) continue;
          
          await executeTrade(trade);
          await sleep(1000); // Wait between trades
        }}
      }}
    }} catch (err) {{
      // Only log errors occasionally
      if (pollCount % 30 === 0) {{
        console.log(`%c⚠️ Server check failed: ${{err.message}}`, 'color: #ffff00');
      }}
    }}
  }}
  
  async function reportExecution(orderId, success) {{
    try {{
      await fetch(`${{SERVER}}/api/trade-executor/confirm-execution`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          order_id: orderId,
          bridge_order_id: 'SIMPLE_' + Date.now(),
          success: success,
          execution_time: new Date().toISOString()
        }})
      }});
    }} catch (err) {{
      console.log('%c⚠️ Could not report execution', 'color: #ffff00');
    }}
  }}
  
  async function sendHeartbeat() {{
    try {{
      const isDemo = window.location.href.includes('demo');
      
      await fetch(`${{SERVER}}/api/bridge/heartbeat`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          timestamp: Date.now(),
          messageCount: pollCount,
          activeConnections: 1,
          ssid: 'present',
          isDemo: isDemo,
          balance: getBalance(),
          tradesExecuted: tradesExecuted
        }})
      }});
    }} catch (err) {{}}
  }}
  
  function getBalance() {{
    const balanceEls = document.querySelectorAll('[class*="balance"], [class*="amount"]');
    for (const el of balanceEls) {{
      const text = el.textContent || '';
      const match = text.match(/[\\d,]+\\.?\\d*/);
      if (match) {{
        return parseFloat(match[0].replace(',', ''));
      }}
    }}
    return 0;
  }}
  
  function sleep(ms) {{
    return new Promise(resolve => setTimeout(resolve, ms));
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // MAIN LOOP
  // ═══════════════════════════════════════════════════════════════════════════
  
  async function mainLoop() {{
    pollCount++;
    
    // Check for trades
    await checkForTrades();
    
    // Send heartbeat every 5 polls
    if (pollCount % 5 === 0) {{
      await sendHeartbeat();
    }}
    
    // Status update every 30 polls (1 minute)
    if (pollCount % 30 === 0) {{
      console.log(`%c📊 Status: Poll #${{pollCount}} | Trades: ${{tradesExecuted}} | Server: ${{SERVER}}`, 'color: #00bfff');
    }}
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // START
  // ═══════════════════════════════════════════════════════════════════════════
  
  console.log('%c═══════════════════════════════════════════════════════════', 'color: #00ff00');
  console.log('%c           🤖 SIMPLE TRADE BOT ACTIVE!                     ', 'color: #00ff00; font-weight: bold;');
  console.log('%c═══════════════════════════════════════════════════════════', 'color: #00ff00');
  console.log('%c📡 Polling server for trades every 2 seconds...', 'color: #00bfff');
  console.log('%c💡 Queue trades at: ' + SERVER + '/api/trade-executor/queue', 'color: #ffff00');
  console.log('%c═══════════════════════════════════════════════════════════', 'color: #00ff00');
  
  // Initial heartbeat
  sendHeartbeat();
  
  // Start main loop
  setInterval(mainLoop, 2000);
  
  // Expose for manual testing
  window.BOT = {{
    executeTrade: executeTrade,
    findButton: findTradeButton,
    setAmount: setAmount,
    status: () => console.log(`Polls: ${{pollCount}}, Trades: ${{tradesExecuted}}`)
  }};
  
  console.log('%c💡 Manual test: window.BOT.findButton("call") or window.BOT.findButton("put")', 'color: #888888');
  
}})();
'''
        
        return {
            "success": True,
            "script": script,
            "instructions": [
                "1. Open Pocket Option (DEMO or REAL account)",
                "2. Navigate to trading page with chart",
                "3. Open Console (F12 → Console)",
                "4. Paste this script and press Enter",
                "5. You should see '🤖 SIMPLE TRADE BOT ACTIVE!'",
                "6. Queue trades with: curl -X POST '" + app_url + "/api/trade-executor/queue?direction=call&amount=1'",
                "",
                "Manual testing commands:",
                "  window.BOT.findButton('call')  - Test finding CALL button",
                "  window.BOT.findButton('put')   - Test finding PUT button",
                "  window.BOT.status()            - Check bot status"
            ],
            "app_url": app_url
        }
    except Exception as e:
        logger.error(f"Error generating simple bridge script: {e}")
        return {"success": False, "error": str(e)}
        logger.error(f"Bridge script error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/candles/{asset}")
async def get_bridge_candles(asset: str, limit: int = 100):
    """Get candles for an asset from the bridge"""
    try:
        from pocket_option_live import get_pocket_option_bridge
        bridge = get_pocket_option_bridge()
        
        candles = bridge.get_candles(asset)
        
        if candles is None:
            return {
                "success": False,
                "error": f"No data for asset {asset}",
                "available_assets": list(bridge.parser.assets.keys())
            }
        
        return {
            "success": True,
            "asset": asset,
            "candles": candles[-limit:] if limit else candles,
            "total_candles": len(candles)
        }
    except Exception as e:
        logger.error(f"Bridge candles error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/assets")
async def get_bridge_assets():
    """Get all assets tracked by the bridge"""
    try:
        from pocket_option_live import get_pocket_option_bridge
        bridge = get_pocket_option_bridge()
        
        return {
            "success": True,
            "assets": bridge.parser.get_asset_summary()
        }
    except Exception as e:
        logger.error(f"Bridge assets error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/bridge/signal")
async def get_bridge_live_signal(request: Request):
    """
    Generate signal using live Pocket Option data
    
    Body:
    - asset: Asset symbol (e.g., "EURUSD_otc")
    """
    try:
        data = await request.json()
        asset = data.get('asset', 'EURUSD_otc')
        
        from pocket_option_live_strategy import get_signal_integration
        integration = get_signal_integration()
        
        signal = integration.get_live_signal(asset)
        
        if signal:
            return {
                "success": True,
                "signal": signal
            }
        else:
            return {
                "success": False,
                "message": f"No signal for {asset} - bridge may not be connected or no trading opportunity"
            }
    except Exception as e:
        logger.error(f"Bridge signal error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/signals/all")
async def get_all_bridge_signals():
    """Get signals from all tracked assets"""
    try:
        from pocket_option_live_strategy import get_signal_integration
        integration = get_signal_integration()
        
        signals = integration.get_all_live_signals()
        
        return {
            "success": True,
            "signals": signals,
            "count": len(signals)
        }
    except Exception as e:
        logger.error(f"Bridge signals error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/bridge/config")
async def update_bridge_config(request: Request):
    """
    Update live strategy configuration
    
    Body:
    - fast_ma: Fast MA period (default 3)
    - fast_ma_type: SMA/EMA/WMA (default SMA)
    - slow_ma: Slow MA period (default 8)
    - slow_ma_type: SMA/EMA/WMA (default SMA)
    - rsi_enabled: Enable RSI confirmation (default true)
    - rsi_period: RSI period (default 14)
    - rsi_upper: RSI upper threshold (default 70)
    - vice_versa: Invert signals (default false)
    """
    try:
        data = await request.json()
        
        from pocket_option_live_strategy import get_live_strategy
        strategy = get_live_strategy()
        
        strategy.update_config(data)
        
        return {
            "success": True,
            "config": strategy.config
        }
    except Exception as e:
        logger.error(f"Bridge config error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/bridge/integration/status")
async def get_integration_status():
    """Get full integration status"""
    try:
        from pocket_option_live_strategy import get_signal_integration
        integration = get_signal_integration()
        
        return {
            "success": True,
            **integration.get_status()
        }
    except Exception as e:
        logger.error(f"Integration status error: {e}")
        return {"success": False, "error": str(e)}



# ========== TELEGRAM NOTIFICATION SERVICE ENDPOINTS ==========

@router.get("/telegram/status")
async def get_telegram_status():
    """
    Get Telegram notifier status
    Should show configured=true, chat_id=6434316177
    """
    try:
        telegram_notifier = get_telegram_notifier()
        status = telegram_notifier.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting Telegram status: {e}")
        return {
            "configured": False,
            "error": str(e)
        }



@router.post("/telegram/test")
async def test_telegram_notification():
    """
    Send a test notification to Telegram
    Should return success=true if sent successfully
    """
    try:
        telegram_notifier = get_telegram_notifier()
        
        test_message = "🧪 TEST NOTIFICATION 🧪\n\n✅ Telegram integration is working!\n📱 Bot: @ElitePocket_bot\n🕐 Time: " + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        success = await telegram_notifier.send_message(test_message, parse_mode="")
        
        return {
            "success": success,
            "message": "Test notification sent successfully" if success else "Failed to send test notification"
        }
    except Exception as e:
        logger.error(f"Error sending test Telegram notification: {e}")
        return {
            "success": False,
            "message": f"Error sending test notification: {str(e)}"
        }



@router.put("/telegram/config")
async def update_telegram_config(config_update: dict):
    """
    Update Telegram notification configuration
    Update config options like enabled, send_signals, etc.
    """
    try:
        telegram_notifier = get_telegram_notifier()
        telegram_notifier.update_config(**config_update)
        
        # Return updated status
        updated_status = telegram_notifier.get_status()
        updated_status["success"] = True
        updated_status["message"] = "✅ Telegram configuration updated"
        
        return updated_status
    except Exception as e:
        logger.error(f"Error updating Telegram config: {e}")
        return {
            "success": False,
            "message": f"Error updating Telegram config: {str(e)}"
        }



@router.get("/telegram-bot/status")
async def get_telegram_bot_status():
    """Get Telegram bot status"""
    telegram_bot = get_telegram_bot(db)
    return {
        "success": True,
        "status": {
            "is_running": telegram_bot.is_running,
            "auto_trading_enabled": telegram_bot.auto_trading_enabled,
            "demo_mode": telegram_bot.demo_mode,
            "trade_amount": telegram_bot.trade_amount,
            "default_chat_id": telegram_bot.default_chat_id,
            "bot_token_configured": bool(telegram_bot.bot_token)
        }
    }



@router.post("/telegram-bot/send")
async def send_telegram_bot_message(request: TelegramMessageRequest):
    """Send a message to Telegram"""
    telegram_bot = get_telegram_bot(db)
    result = await telegram_bot.send_message(request.message, request.chat_id)
    return result



@router.post("/telegram-bot/send-signal")
async def send_signal_to_telegram_bot(signal_data: Dict):
    """Send a trading signal to Telegram"""
    telegram_bot = get_telegram_bot(db)
    
    signal = TelegramTradingSignal(
        id=signal_data.get('id', str(uuid.uuid4())),
        symbol=signal_data.get('symbol', 'UNKNOWN'),
        direction=signal_data.get('direction', 'NEUTRAL'),
        confidence=signal_data.get('confidence', 0),
        entry_price=signal_data.get('entry_price', 0),
        timeframe=signal_data.get('timeframe', '1m'),
        expiration_seconds=signal_data.get('expiration_seconds', 60),
        strategy=signal_data.get('strategy', 'unknown'),
        timestamp=signal_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
        reasoning=signal_data.get('reasoning', '')
    )
    
    result = await telegram_bot.send_signal(signal)
    return result



@router.put("/telegram-bot/settings")
async def update_telegram_bot_settings(settings: TelegramSettingsRequest):
    """Update Telegram bot settings"""
    telegram_bot = get_telegram_bot(db)
    
    if settings.auto_trading_enabled is not None:
        telegram_bot.auto_trading_enabled = settings.auto_trading_enabled
    if settings.demo_mode is not None:
        telegram_bot.demo_mode = settings.demo_mode
    if settings.trade_amount is not None:
        telegram_bot.trade_amount = settings.trade_amount
    
    # Save settings to database
    if db is not None:
        await db.telegram_bot_settings.update_one(
            {'id': 'default'},
            {'$set': {
                'auto_trading_enabled': telegram_bot.auto_trading_enabled,
                'demo_mode': telegram_bot.demo_mode,
                'trade_amount': telegram_bot.trade_amount,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
    
    return {
        "success": True,
        "settings": {
            "auto_trading_enabled": telegram_bot.auto_trading_enabled,
            "demo_mode": telegram_bot.demo_mode,
            "trade_amount": telegram_bot.trade_amount
        }
    }



@router.post("/telegram-bot/start")
async def start_telegram_bot_polling(background_tasks: BackgroundTasks):
    """Start Telegram bot polling with SSID auto-refresh integration"""
    telegram_bot = get_telegram_bot(db)
    
    if telegram_bot.is_running:
        return {"success": True, "message": "Bot already running"}
    
    # Set up signal callback that properly generates and sends signals
    async def signal_callback():
        try:
            logger.info("📡 Telegram /signal command triggered - generating signal...")
            
            # Get user config for assets
            config_doc = await db.trading_configurations.find_one({"user_id": "default_user"})
            selected_assets = config_doc.get('selected_assets', ['EURUSD_otc']) if config_doc else ['EURUSD_otc']
            user_expirations = config_doc.get('selected_expirations', ['1m']) if config_doc else ['1m']
            
            # Use first selected asset
            asset = selected_assets[0] if selected_assets else 'EURUSD_otc'
            base_symbol = asset.replace('_regular', '').replace('_otc', '')
            
            # Create market data object
            from trading_models import MarketData, AssetType
            target_asset = MarketData(
                symbol=base_symbol,
                price=1.0500,
                timestamp=datetime.now(timezone.utc),
                asset_type=AssetType.FOREX,
                volume=0
            )
            
            # Generate signal using force_generate_signal
            from server import force_signal_generator
            signals = await force_signal_generator.force_generate_signal(
                base_symbol, target_asset, user_expirations, 
                chart_type='japanese_candles', wait_for_candle=False
            )
            
            if signals and len(signals) > 0:
                signal = signals[0]
                signal.symbol = asset  # Use full asset name
                
                # Send to Telegram via platform integration (this handles the enum properly now)
                await platform_integration.send_telegram_signal(signal)
                
                # Also execute auto-trade if enabled
                if telegram_bot.auto_trading_enabled:
                    # Create TelegramTradingSignal for auto-trading
                    tg_signal = TelegramTradingSignal(
                        id=str(signal.id),
                        symbol=signal.symbol,
                        direction=signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
                        confidence=float(signal.probability),
                        entry_price=float(signal.entry_price),
                        timeframe=str(signal.timeframe),
                        expiration_seconds=int(signal.expiration_minutes * 60),
                        strategy=str(signal.strategy_used),
                        timestamp=signal.timestamp.isoformat(),
                        reasoning=signal.justification[:200]
                    )
                    await telegram_bot.send_signal(tg_signal)
                
                logger.info(f"✅ Signal generated and sent via Telegram: {signal.id}")
            else:
                await telegram_bot.send_message("⚠️ No signal generated - conditions not met. Try again.")
                logger.warning("⚠️ No signal generated from /signal command")
                
        except Exception as e:
            logger.error(f"Signal callback error: {e}")
            await telegram_bot.send_message(f"❌ Signal generation error: {str(e)[:100]}")
    
    telegram_bot.set_signal_callback(signal_callback)
    
    # Start polling in background
    background_tasks.add_task(telegram_bot.start_polling)
    
    # Start SSID auto-refresh service
    ssid_service = get_ssid_service()
    ssid_auto_refresh_started = False
    
    if ssid_service is None:
        # Initialize SSID service with Telegram notification callbacks
        async def on_ssid_refreshed(new_ssid: str):
            """Callback when SSID is successfully refreshed"""
            try:
                await telegram_bot.send_message(
                    f"🔄 <b>SSID Auto-Refreshed!</b>\n\n"
                    f"✅ New SSID obtained successfully\n"
                    f"📋 Preview: <code>{new_ssid[:20]}...</code>\n"
                    f"⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                logger.info("✅ SSID refreshed and Telegram notified")
            except Exception as e:
                logger.error(f"Error sending SSID refresh notification: {e}")
        
        async def on_refresh_failed(error: str):
            """Callback when SSID refresh fails"""
            try:
                await telegram_bot.send_message(
                    f"⚠️ <b>SSID Refresh Failed!</b>\n\n"
                    f"❌ Error: {error}\n"
                    f"🔧 Manual refresh may be required\n"
                    f"⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                logger.warning("⚠️ SSID refresh failed, Telegram notified")
            except Exception as e:
                logger.error(f"Error sending SSID failure notification: {e}")
        
        try:
            await initialize_ssid_service(
                on_ssid_refreshed=lambda ssid: asyncio.create_task(on_ssid_refreshed(ssid)),
                on_refresh_failed=lambda err: asyncio.create_task(on_refresh_failed(err))
            )
            ssid_auto_refresh_started = True
            logger.info("🔄 SSID auto-refresh service started with Telegram integration")
        except Exception as e:
            logger.warning(f"⚠️ SSID auto-refresh could not be started: {e}")
    else:
        # Service already exists, just start it
        if not ssid_service.is_running:
            await ssid_service.start()
            ssid_auto_refresh_started = True
    
    return {
        "success": True, 
        "message": "Telegram bot started",
        "ssid_auto_refresh": ssid_auto_refresh_started,
        "features": {
            "telegram_polling": True,
            "ssid_auto_refresh": ssid_auto_refresh_started,
            "signal_callback": True
        }
    }



@router.post("/telegram-bot/stop")
async def stop_telegram_bot_polling():
    """Stop Telegram bot polling and SSID auto-refresh"""
    telegram_bot = get_telegram_bot(db)
    await telegram_bot.stop_polling()
    
    # Also stop SSID auto-refresh
    ssid_service = get_ssid_service()
    if ssid_service and ssid_service.is_running:
        await ssid_service.stop()
        logger.info("🛑 SSID auto-refresh service stopped")
    
    return {
        "success": True, 
        "message": "Telegram bot and SSID auto-refresh stopped",
        "telegram_stopped": True,
        "ssid_auto_refresh_stopped": True
    }



@router.get("/telegram-bot/history")
async def get_telegram_bot_history(limit: int = 50):
    """Get Telegram signal and trade history"""
    signals = await db.telegram_signals.find(
        {}, {'_id': 0}
    ).sort('sent_at', -1).limit(limit).to_list(limit)
    
    trades = await db.telegram_trades.find(
        {}, {'_id': 0}
    ).sort('timestamp', -1).limit(limit).to_list(limit)
    
    return {
        "success": True,
        "signals": signals,
        "trades": trades
    }



@router.get("/telegram-bot/stats")
async def get_telegram_bot_stats():
    """Get Telegram trading statistics"""
    total_signals = await db.telegram_signals.count_documents({})
    total_trades = await db.telegram_trades.count_documents({})
    wins = await db.telegram_trades.count_documents({'status': 'won'})
    losses = await db.telegram_trades.count_documents({'status': 'lost'})
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate profit/loss
    pipeline = [
        {'$group': {'_id': None, 'total_profit': {'$sum': '$profit'}}}
    ]
    profit_result = await db.telegram_trades.aggregate(pipeline).to_list(1)
    total_profit = profit_result[0]['total_profit'] if profit_result else 0
    
    return {
        "success": True,
        "stats": {
            "total_signals": total_signals,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2)
        }
    }




# =====================================================
# 3COMMAS SIGNAL BOT ENDPOINTS
# =====================================================

@router.get("/3commas/status")
async def get_threecommas_status():
    """Get 3Commas integration status"""
    service = get_threecommas_service()
    
    if service:
        config = await service.get_config()
        return {
            "success": True,
            "configured": service.is_configured,
            "enabled": service.is_enabled,
            "config": {
                "secret": "***" + config.get("secret", "")[-10:] if config.get("secret") else "",
                "bot_uuid": config.get("bot_uuid", ""),
                "max_lag": config.get("max_lag", "300"),
                "tv_exchange": config.get("tv_exchange", "BINANCE"),
                "enabled": config.get("enabled", False)
            }
        }
    
    return {
        "success": True,
        "configured": False,
        "enabled": False,
        "config": {}
    }




@router.post("/3commas/config")
async def save_threecommas_config(config: dict):
    """Save 3Commas configuration"""
    service = get_threecommas_service()
    
    if not service:
        # Initialize service if not exists
        service = await initialize_threecommas_service(db)
    
    success = await service.save_config(config)
    
    if success:
        return {
            "success": True,
            "message": "3Commas configuration saved successfully"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to save 3Commas configuration")




@router.post("/3commas/test")
async def test_threecommas_connection():
    """Test 3Commas webhook connection"""
    service = get_threecommas_service()
    
    if not service:
        return {
            "success": False,
            "error": "3Commas service not initialized"
        }
    
    result = await service.test_connection()
    return result




@router.post("/3commas/send-signal")
async def send_threecommas_signal(signal_data: dict):
    """Manually send a signal to 3Commas"""
    service = get_threecommas_service()
    
    if not service or not service.is_enabled:
        return {
            "success": False,
            "error": "3Commas integration not enabled"
        }
    
    # Create a simple signal object
    class SimpleSignal:
        def __init__(self, data):
            self.direction = data.get("direction", "CALL")
            self.symbol = data.get("symbol", "BTCUSD")
            self.entry_price = data.get("entry_price", 0)
    
    signal = SimpleSignal(signal_data)
    result = await service.send_signal(signal)
    return result



@router.post("/tradingview/webhook")
async def receive_tradingview_alert(alert: TradingViewAlert):
    """
    Receive and process TradingView webhook alerts.
    
    Configure in TradingView:
    1. Create alert on your indicator/strategy
    2. Set webhook URL to: https://your-domain/api/tradingview/webhook
    3. Set message body to JSON:
       {"ticker": "{{ticker}}", "action": "{{strategy.order.action}}", "price": "{{close}}"}
    
    Supported actions: buy, sell, call, put
    """
    try:
        logger.info(f"📊 TradingView Alert: {alert.ticker} - {alert.action} @ {alert.price}")
        
        # Normalize action
        action_upper = alert.action.upper()
        if action_upper in ["BUY", "CALL", "LONG"]:
            direction = "CALL"
        elif action_upper in ["SELL", "PUT", "SHORT"]:
            direction = "PUT"
        else:
            return {"success": False, "error": f"Unknown action: {alert.action}"}
        
        # Convert ticker to OANDA format
        ticker = alert.ticker.replace("/", "").replace("-", "")
        if len(ticker) == 6 and "_" not in ticker:
            oanda_ticker = f"{ticker[:3]}_{ticker[3:]}"
        else:
            oanda_ticker = ticker
        
        # Create signal from TradingView alert
        new_signal = {
            "id": f"TV_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{ticker}",
            "symbol": ticker,
            "direction": direction,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": 85,  # TradingView signals assumed high confidence
            "probability": 85,
            "expiration_minutes": 1,
            "strategy": alert.strategy,
            "entry_price": alert.price,
            "message": alert.message,
            "source": "tradingview"
        }
        
        # Save to database
        await db.trading_signals.insert_one({**new_signal})
        
        logger.info(f"✅ TradingView signal saved: {new_signal['direction']} {new_signal['symbol']}")
        
        return {
            "success": True,
            "message": f"Alert processed: {direction} {ticker}",
            "signal_id": new_signal["id"]
        }
        
    except Exception as e:
        logger.error(f"TradingView webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/tradingview/status")
async def get_tradingview_status():
    """Get TradingView integration status and webhook URL"""
    return {
        "configured": True,
        "webhook_url": "/api/tradingview/webhook",
        "instructions": {
            "step1": "In TradingView, create an alert on your indicator/strategy",
            "step2": "Enable 'Webhook URL' and paste your endpoint URL",
            "step3": "Set message to: {\"ticker\": \"{{ticker}}\", \"action\": \"{{strategy.order.action}}\", \"price\": \"{{close}}\"}",
            "supported_actions": ["buy", "sell", "call", "put", "long", "short"]
        },
        "recent_signals": await get_recent_tv_signals()
    }

async def get_recent_tv_signals():
    """Get recent TradingView signals"""
    signals = []
    async for signal in db.trading_signals.find(
        {"source": "tradingview"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(10):
        signals.append(signal)
    return signals



@router.post("/mt5/configure")
async def configure_mt5(config: MT5Config):
    """
    Configure MetaTrader 5 connection.
    
    NOTE: MT5 integration requires:
    1. MetaTrader 5 terminal running on the same machine as the backend
    2. pip install MetaTrader5 (Windows only)
    3. AutoTrading enabled in MT5 settings
    
    For cloud deployment, use a VPS with MT5 installed.
    """
    global mt5_state
    
    try:
        # Check if MT5 module is available
        try:
            import MetaTrader5 as mt5
            mt5_available = True
        except ImportError:
            mt5_available = False
            return {
                "success": False,
                "error": "MetaTrader5 Python package not installed. Run: pip install MetaTrader5",
                "note": "MT5 integration only works on Windows with MT5 terminal installed"
            }
        
        # Try to initialize
        if not mt5.initialize(
            login=config.login,
            password=config.password,
            server=config.server,
            path=config.path
        ):
            error = mt5.last_error()
            return {
                "success": False,
                "error": f"MT5 initialization failed: {error}"
            }
        
        # Get account info
        account_info = mt5.account_info()
        
        mt5_state["configured"] = True
        mt5_state["connected"] = True
        mt5_state["login"] = config.login
        mt5_state["server"] = config.server
        
        return {
            "success": True,
            "account": {
                "login": account_info.login,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "currency": account_info.currency,
                "server": config.server
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



@router.get("/mt5/status")
async def get_mt5_status():
    """Get MetaTrader 5 connection status"""
    global mt5_state
    
    # Check if MT5 is available
    try:
        import MetaTrader5 as mt5
        mt5_available = True
        
        if mt5_state["connected"]:
            # Check if still connected
            account_info = mt5.account_info()
            if account_info:
                return {
                    "available": True,
                    "configured": True,
                    "connected": True,
                    "account": {
                        "login": account_info.login,
                        "balance": account_info.balance,
                        "equity": account_info.equity,
                        "profit": account_info.profit
                    }
                }
    except ImportError:
        mt5_available = False
    
    return {
        "available": mt5_available,
        "configured": mt5_state["configured"],
        "connected": mt5_state["connected"],
        "note": "MT5 integration requires Windows with MT5 terminal installed" if not mt5_available else None
    }



@router.post("/mt5/trade")
async def execute_mt5_trade(request: MT5TradeRequest):
    """
    Execute a trade on MetaTrader 5.
    
    Requires MT5 to be configured and connected.
    """
    global mt5_state
    
    if not mt5_state["connected"]:
        return {"success": False, "error": "MT5 not connected. Configure MT5 first."}
    
    try:
        import MetaTrader5 as mt5
        
        # Get symbol info
        symbol_info = mt5.symbol_info(request.symbol)
        if not symbol_info:
            return {"success": False, "error": f"Symbol not found: {request.symbol}"}
        
        # Get current price
        tick = mt5.symbol_info_tick(request.symbol)
        if not tick:
            return {"success": False, "error": "Could not get current price"}
        
        # Determine order type and price
        if request.order_type.upper() == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        
        # Build trade request
        trade_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": request.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "GPT Signal Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if request.stop_loss:
            trade_request["sl"] = request.stop_loss
        if request.take_profit:
            trade_request["tp"] = request.take_profit
        
        # Send order
        result = mt5.order_send(trade_request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"Trade failed: {result.comment}",
                "retcode": result.retcode
            }
        
        return {
            "success": True,
            "order_ticket": result.order,
            "volume": result.volume,
            "price": result.price
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


