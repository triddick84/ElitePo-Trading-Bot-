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

from routes.models import QuickAuthTestRequest, SSIDConnectRequest, DataCollectionStartRequest, BotStartRequest
from pocket_option_client import get_pocket_option_client
import time
import base64
from io import BytesIO

    
@router.post("/pocket-option/quick-auth-test")
async def quick_auth_test(request: QuickAuthTestRequest):
    """
    Quick test of Pocket Option authentication
    
    Accepts TWO formats:
    1. Full WebSocket message: 42["auth",{"session":"...","isDemo":1,"uid":...}]
    2. Simple cookie SSID: A4zP7dZSXxYCq0X5z
    
    Usage Option 1 (WebSocket message):
    1. Open Pocket Option in browser
    2. DevTools (F12) -> Network -> WS -> Messages
    3. Copy the auth message: 42["auth",{"session":"...","isDemo":1,"uid":...}]
    
    Usage Option 2 (Cookie):
    1. Open Pocket Option in browser  
    2. DevTools (F12) -> Application -> Cookies
    3. Copy the "ssid" cookie value
    """
    try:
        import json
        import re
        
        logger.info("🧪 Quick Auth Test Starting...")
        logger.info(f"📋 Received message: {request.auth_message[:100]}...")
        
        # Check if it's the full WebSocket message or simple SSID
        if request.auth_message.startswith('42["auth"'):
            # Format 1: Full WebSocket message
            match = re.search(r'42\["auth",(\{.*?\})\]', request.auth_message)
            
            if not match:
                return {
                    "success": False,
                    "error": "Invalid WebSocket auth message format",
                    "expected": '42["auth",{"session":"...","isDemo":1,"uid":...}]',
                    "received": request.auth_message
                }
            
            auth_data = json.loads(match.group(1))
            ssid = auth_data.get('session')
            uid = auth_data.get('uid', 0)
            is_demo = auth_data.get('isDemo', 1) == 1
            
            logger.info("✅ Extracted from WebSocket message:")
            logger.info(f"   SSID: {ssid[:50]}...")
            logger.info(f"   UID: {uid}")
            logger.info(f"   Demo: {is_demo}")
        else:
            # Format 2: Simple cookie SSID
            ssid = request.auth_message.strip()
            uid = int(os.getenv('POCKET_OPTION_UID', '0'))
            is_demo = True  # Default to demo
            
            logger.info("✅ Using simple SSID format:")
            logger.info(f"   SSID: {ssid}")
            logger.info(f"   UID: {uid} (from env)")
            logger.info(f"   Demo: {is_demo} (default)")
        
        # Test connection using AsyncPocketOptionClient (simpler, more stable)
        from pocketoptionapi_async import AsyncPocketOptionClient
        client = AsyncPocketOptionClient(
            ssid=ssid,
            is_demo=is_demo,
            uid=uid,
            enable_logging=True
        )
        
        logger.info("🔌 Attempting connection with AsyncPocketOptionClient...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ Connection successful!")
            
            # Get balance
            try:
                balance = await client.get_balance()
            except:
                balance = 0
            
            # Test candle data
            try:
                candles = await client.get_candles('EURUSD_otc', 60, 5)
            except:
                candles = []
            
            await client.disconnect()
            
            return {
                "success": True,
                "message": "✅ Pocket Option connection SUCCESSFUL!",
                "connection": {
                    "ssid_format": "websocket_message" if request.auth_message.startswith('42[') else "simple_cookie",
                    "ssid_preview": ssid[:20] + "..." if len(ssid) > 20 else ssid,
                    "uid": uid,
                    "is_demo": is_demo,
                    "balance": balance,
                    "candles_retrieved": len(candles) if candles else 0
                }
            }
        else:
            return {
                "success": False,
                "error": "Connection failed - SSID might be expired or invalid",
                "recommendation": "Get a fresh SSID:\n1. WebSocket: Network→WS→Messages\n2. Cookie: Application→Cookies→ssid",
                "extracted_data": {
                    "ssid_format": "websocket_message" if request.auth_message.startswith('42[') else "simple_cookie",
                    "ssid_preview": ssid[:20] + "...",
                    "uid": uid,
                    "is_demo": is_demo
                }
            }
            
    except Exception as e:
        logger.error(f"Error in quick auth test: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }




@router.post("/pocket-option/update-ssid")
async def update_pocket_option_ssid(ssid: str, is_demo: bool = True):
    """
    Update the Pocket Option SSID
    
    Accepts TWO formats:
    1. Simple cookie value: A4zP7dZSXxYCq0X5z
    2. Full WebSocket message: 42["auth",{"session":"...","isDemo":1,"uid":123}]
    
    Args:
        ssid: Either the cookie value OR the full WebSocket auth message
        is_demo: Whether this is a demo account (default True)
    
    Examples:
        # Simple cookie:
        curl -X POST "URL/api/pocket-option/update-ssid?ssid=A4zP7dZSXxYCq0X5z"
        
        # Full message (URL encode the quotes):
        curl -X POST "URL/api/pocket-option/update-ssid" --data-urlencode 'ssid=42["auth",...'
    """
    try:
        import json
        import re
        
        logger.info(f"🔄 Updating SSID (format: {ssid[:20]}...)")
        
        # Parse the SSID format
        actual_ssid = ssid
        uid = int(os.getenv('POCKET_OPTION_UID', '0'))
        parsed_is_demo = is_demo
        
        if ssid.startswith('42["auth"'):
            # Extract from WebSocket message (greedy match to capture all JSON)
            match = re.search(r'42\["auth",(\{.*\})\]', ssid)
            if match:
                auth_data = json.loads(match.group(1))
                actual_ssid = auth_data.get('session', ssid)
                uid = auth_data.get('uid', uid)
                parsed_is_demo = auth_data.get('isDemo', 1) == 1
                logger.info(f"📨 Extracted from WebSocket: uid={uid}, demo={parsed_is_demo}")
        
        # Update .env file with the actual SSID
        env_path = '/app/backend/.env'
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Update SSID and UID
        updated_ssid = False
        updated_uid = False
        for i, line in enumerate(lines):
            if line.startswith('POCKET_OPTION_SSID='):
                lines[i] = f'POCKET_OPTION_SSID={actual_ssid}\n'
                updated_ssid = True
            elif line.startswith('POCKET_OPTION_UID='):
                lines[i] = f'POCKET_OPTION_UID={uid}\n'
                updated_uid = True
        
        if not updated_ssid:
            lines.append(f'POCKET_OPTION_SSID={actual_ssid}\n')
        if not updated_uid:
            lines.append(f'POCKET_OPTION_UID={uid}\n')
        
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        logger.info("✅ SSID updated in .env file")
        
        # Test the new SSID using our custom WebSocket handler (compatible with websockets 15+)
        from pocket_option_ws import connect_pocket_option
        
        logger.info("🧪 Testing connection with new WebSocket handler...")
        
        # Use the full SSID message for connection if available
        connection_ssid = ssid if ssid.startswith('42["auth"') else f'42["auth",{{"session":"{actual_ssid}","isDemo":{1 if parsed_is_demo else 0},"uid":{uid}}}]'
        
        result = await connect_pocket_option(connection_ssid, parsed_is_demo)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "✅ SSID updated and tested successfully!",
                "ssid_format": "websocket_message" if ssid.startswith('42[') else "simple_cookie",
                "ssid_preview": f"{actual_ssid[:15]}..." if len(actual_ssid) > 15 else actual_ssid,
                "uid": uid,
                "is_demo": parsed_is_demo,
                "connection": result.get("state", {})
            }
        else:
            return {
                "success": False,
                "message": "SSID updated in .env but connection test failed",
                "error": result.get("error", "SSID might be expired or invalid"),
                "connection_state": result.get("state", {}),
                "recommendation": "Try getting a fresh SSID:\n1. Cookie: Application→Cookies→ssid\n2. WebSocket: Network→WS→Messages"
            }
            
    except Exception as e:
        logger.error(f"Error updating SSID: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }



@router.post("/pocket-option/test-auto-refresh")
async def test_pocket_option_auto_refresh():
    """
    Test the automatic SSID refresh and reconnection feature
    """
    try:
        logger.info("🧪 Testing Pocket Option auto-refresh feature...")
        
        # Get current SSID from env
        current_ssid = os.getenv('POCKET_OPTION_SSID')
        uid = int(os.getenv('POCKET_OPTION_UID', '0'))
        
        if not current_ssid:
            return {
                "success": False,
                "error": "No SSID found in environment"
            }
        
        # Create client with auto-refresh enabled
        from pocket_option_v2 import PocketOptionV2
        client = PocketOptionV2(
            ssid=current_ssid,
            uid=uid,
            is_demo=True,
            auto_refresh=True  # Enable auto-refresh
        )
        
        # Try to connect (will auto-refresh if SSID is expired)
        logger.info("🔌 Attempting connection with auto-refresh enabled...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ Connection successful!")
            balance = await client.get_balance()
            candles = await client.get_candles('EURUSD_otc', 60, 5)
            await client.disconnect()
            
            return {
                "success": True,
                "message": "✅ Connection successful with auto-refresh",
                "connection": {
                    "ssid": client.ssid[:20] + "...",
                    "balance": balance,
                    "candles_retrieved": len(candles) if candles else 0,
                    "auto_refresh_enabled": True
                }
            }
        else:
            return {
                "success": False,
                "error": "Connection failed even with auto-refresh",
                "recommendation": "Check if Selenium/Chrome is properly installed and credentials are correct",
                "reconnect_attempts": client.reconnect_attempts
            }
            
    except Exception as e:
        logger.error(f"Error testing auto-refresh: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }



@router.post("/pocket-option/persistent/start")
async def start_persistent_connection():
    """
    Start persistent Pocket Option connection with auto-reconnection
    and keep-alive features
    """
    try:
        logger.info("🚀 Starting persistent Pocket Option connection...")
        
        from pocket_option_persistent import PersistentPocketOptionConnection
        
        ssid = os.getenv('POCKET_OPTION_SSID')
        uid = int(os.getenv('POCKET_OPTION_UID', '0'))
        
        if not ssid:
            return {
                "success": False,
                "error": "No SSID configured in environment"
            }
        
        # Store in global state for reuse
        global persistent_po_connection
        
        if 'persistent_po_connection' in globals() and persistent_po_connection:
            await persistent_po_connection.stop()
        
        persistent_po_connection = PersistentPocketOptionConnection(
            ssid=ssid,
            uid=uid,
            is_demo=True,
            ping_interval=25,
            enable_auto_refresh=True
        )
        
        started = await persistent_po_connection.start()
        
        if started:
            # Get initial balance
            balance = await persistent_po_connection.get_balance()
            
            return {
                "success": True,
                "message": "✅ Persistent connection started",
                "connection": {
                    "ssid_preview": ssid[:20] + "...",
                    "uid": uid,
                    "is_demo": True,
                    "balance": balance,
                    "ping_interval": 25,
                    "auto_refresh_enabled": True
                }
            }
        else:
            return {
                "success": False,
                "error": "Failed to start persistent connection"
            }
            
    except Exception as e:
        logger.error(f"Error starting persistent connection: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }



@router.get("/pocket-option/persistent/stats")
async def get_persistent_connection_stats():
    """Get statistics about the persistent connection"""
    try:
        if 'persistent_po_connection' not in globals() or not persistent_po_connection:
            return {
                "success": False,
                "error": "Persistent connection not started"
            }
        
        stats = persistent_po_connection.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



@router.post("/pocket-option/persistent/stop")
async def stop_persistent_connection():
    """Stop the persistent connection"""
    try:
        if 'persistent_po_connection' in globals() and persistent_po_connection:
            await persistent_po_connection.stop()
            return {
                "success": True,
                "message": "✅ Persistent connection stopped"
            }
        else:
            return {
                "success": False,
                "error": "No persistent connection running"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



@router.post("/pocket-option/auto-login")
async def pocket_option_auto_login():
    """
    Automatically login to Pocket Option and extract SSID
    Uses Selenium to automate browser login
    """
    try:
        logger.info("🔐 Starting auto-login to Pocket Option...")
        
        # Run in executor to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        ssid = await loop.run_in_executor(None, auto_login_and_get_ssid)
        
        if ssid:
            # Update the global client with new SSID
            global pocket_option_client
            pocket_option_client = None  # Reset so it creates new instance
            
            return {
                "success": True,
                "message": "Successfully logged in and extracted SSID",
                "ssid_preview": f"{ssid[:20]}...",
                "ssid_length": len(ssid)
            }
        else:
            return {
                "success": False,
                "error": "Failed to extract SSID - check credentials or reCAPTCHA"
            }
    except Exception as e:
        logger.error(f"Error during auto-login: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/pocket-option/status")
async def get_pocket_option_status():
    """
    Check Pocket Option API connection status
    """
    try:
        # First try our new WebSocket handler
        from pocket_option_ws import get_connection, test_connection
        
        connection = get_connection()
        if connection and connection.state.connected:
            return {
                "success": True,
                "connected": True,
                "is_demo": connection.state.is_demo,
                "balance": connection.state.balance,
                "account_id": connection.state.user_id,
                "authenticated": connection.state.authenticated,
                "connection_url": connection.state.url,
                "message": "Connected via custom WebSocket handler"
            }
        
        # Fallback to checking env for credentials
        ssid = os.getenv('POCKET_OPTION_SSID')
        if not ssid:
            return {
                "success": False,
                "connected": False,
                "message": "Pocket Option SSID not configured. Please update SSID."
            }
        
        return {
            "success": False,
            "connected": False,
            "message": "SSID configured but not connected. Try updating SSID.",
            "has_ssid": True
        }
    except Exception as e:
        logger.error(f"Error checking Pocket Option status: {e}")
        return {
            "success": False,
            "connected": False,
            "error": str(e)
        }




@router.get("/pocket-option/balance")
async def get_pocket_option_balance():
    """Get current Pocket Option account balance"""
    try:
        client = await get_pocket_option_client(is_demo=True)
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Pocket Option not connected")
        
        balance = await client.get_balance()
        return {
            "success": True,
            "balance": balance,
            "currency": "USD",
            "account_type": "DEMO" if client.is_demo else "LIVE"
        }
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/pocket-option/order")
async def place_pocket_option_order(
    asset: str,
    direction: str,
    amount: float,
    duration: int
):
    """
    Place a binary options order on Pocket Option
    
    Args:
        asset: Asset symbol (e.g., EURUSD)
        direction: BUY/CALL or SELL/PUT
        amount: Investment amount
        duration: Trade duration in seconds
    """
    try:
        client = await get_pocket_option_client(is_demo=True)
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Pocket Option not connected")
        
        result = await client.place_order(asset, direction, amount, duration)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            "success": True,
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pocket-option/candles/{asset}")
async def get_pocket_option_candles(
    asset: str,
    timeframe: int = 60,
    count: int = 100
):
    """
    Get real-time candles from Pocket Option
    
    Args:
        asset: Asset symbol
        timeframe: Timeframe in seconds (60, 300, 900, 3600)
        count: Number of candles to retrieve
    """
    try:
        client = await get_pocket_option_client(is_demo=True)
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Pocket Option not connected")
        
        candles = await client.get_candles(asset, timeframe, count)
        
        return {
            "success": True,
            "asset": asset,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        logger.error(f"Error getting candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== POCKET OPTION REAL-TIME MARKET DATA ====================

@router.post("/pocket-option/realtime/connect")
async def connect_po_realtime(ssid: str, is_demo: bool = True):
    """
    Connect to Pocket Option for real-time market data
    
    Args:
        ssid: Full SSID string (42["auth",...] format) or simple session cookie
        is_demo: Whether to connect to demo account
    """
    try:
        # Build full SSID if simple format provided
        if not ssid.startswith('42["auth"'):
            # Simple SSID format - build full auth message
            uid = int(os.getenv('POCKET_OPTION_UID', '0'))
            auth_data = {
                "session": ssid,
                "isDemo": 1 if is_demo else 0,
                "uid": uid
            }
            full_ssid = f'42["auth",{json.dumps(auth_data)}]'
        else:
            full_ssid = ssid
        
        success = await po_market_data.connect(full_ssid, is_demo)
        
        if success:
            return {
                "success": True,
                "message": "Connected to Pocket Option real-time data",
                "is_demo": is_demo
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to Pocket Option"
            }
    except Exception as e:
        logger.error(f"PO realtime connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/pocket-option/realtime/subscribe/{symbol}")
async def subscribe_po_asset(symbol: str):
    """
    Subscribe to real-time price updates for an asset
    
    Args:
        symbol: Asset symbol (e.g., EURUSD, EURUSD_OTC, BTCUSD)
    """
    try:
        success = await po_market_data.subscribe_asset(symbol.upper())
        
        return {
            "success": success,
            "symbol": symbol.upper(),
            "message": f"Subscribed to {symbol}" if success else f"Failed to subscribe to {symbol}"
        }
    except Exception as e:
        logger.error(f"PO subscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pocket-option/realtime/market-data/{symbol}")
async def get_po_market_data(symbol: str):
    """
    Get current market data for a symbol from Pocket Option
    
    Returns real-time price, indicators, and trend analysis
    """
    try:
        market_data = po_market_data.get_market_data(symbol.upper())
        
        if market_data:
            # Calculate indicators
            indicators = po_market_data.calculate_indicators(symbol.upper(), "1m")
            
            return {
                "success": True,
                "symbol": symbol.upper(),
                "data": market_data.to_dict(),
                "indicators": indicators
            }
        else:
            return {
                "success": False,
                "message": f"No market data available for {symbol}. Subscribe to the asset first."
            }
    except Exception as e:
        logger.error(f"PO market data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pocket-option/realtime/signal/{symbol}")
async def get_po_realtime_signal(symbol: str, timeframe: str = "1m"):
    """
    Generate trading signal from Pocket Option real-time data
    
    Args:
        symbol: Asset symbol
        timeframe: Timeframe for analysis (5s, 1m, 5m, etc.)
    """
    try:
        signal = po_market_data.generate_signal(symbol.upper(), timeframe)
        return signal
    except Exception as e:
        logger.error(f"PO signal generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pocket-option/realtime/candles/{symbol}")
async def get_po_candles(symbol: str, timeframe: str = "1m", count: int = 100):
    """
    Get candle history from Pocket Option
    
    Args:
        symbol: Asset symbol
        timeframe: Candle timeframe (5s, 1m, 5m, 15m, 1h)
        count: Number of candles to retrieve
    """
    try:
        candles = await po_market_data.get_candles(symbol.upper(), timeframe, count)
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        logger.error(f"PO candles error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pocket-option/realtime/status")
async def get_po_realtime_status():
    """
    Get Pocket Option real-time connection status
    """
    try:
        connection = po_market_data.connection
        
        if connection:
            state = connection.get_state()
            return {
                "success": True,
                "connected": state.get("connected", False),
                "authenticated": state.get("authenticated", False),
                "balance": state.get("balance", 0),
                "subscribed_assets": po_market_data.subscribed_assets,
                "market_data_count": len(po_market_data.market_data),
                "state": state
            }
        else:
            return {
                "success": False,
                "connected": False,
                "message": "Not connected to Pocket Option"
            }
    except Exception as e:
        logger.error(f"PO status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/pocket-option/realtime/disconnect")
async def disconnect_po_realtime():
    """
    Disconnect from Pocket Option real-time data
    """
    try:
        await po_market_data.disconnect()
        return {
            "success": True,
            "message": "Disconnected from Pocket Option"
        }
    except Exception as e:
        logger.error(f"PO disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# SSID AUTO-REFRESH ENDPOINTS
# =============================================================================

# ========== SSID AUTO-REFRESH SERVICE ENDPOINTS ==========

@router.get("/ssid/status")
async def get_ssid_status():
    """
    Get current SSID status with preview and validity information
    """
    try:
        ssid_service = get_ssid_service()
        if ssid_service:
            status = ssid_service.get_status()
            return status['ssid_status']
        else:
            # Return status from environment if service not running
            ssid = os.getenv('POCKET_OPTION_SSID', '')
            return {
                'ssid_preview': ssid[:20] + '...' if len(ssid) > 20 else ssid,
                'is_valid': bool(ssid),
                'service_running': False,
                'message': 'SSID service not initialized'
            }
    except Exception as e:
        logger.error(f"Error getting SSID status: {e}")
        return {
            'ssid_preview': '',
            'is_valid': False,
            'error': str(e)
        }



@router.post("/ssid/start-auto-refresh")
async def start_ssid_auto_refresh():
    """
    Start the SSID auto-refresh service
    May fail if Selenium not working (that's acceptable)
    """
    try:
        ssid_service = get_ssid_service()
        if not ssid_service:
            # Initialize service with callbacks
            telegram_notifier = get_telegram_notifier()
            
            def on_ssid_refreshed(ssid: str):
                asyncio.create_task(telegram_notifier.send_ssid_refreshed(ssid))
            
            def on_refresh_failed(error: str):
                asyncio.create_task(telegram_notifier.send_ssid_failed(error))
            
            ssid_service = await initialize_ssid_service(
                on_ssid_refreshed=on_ssid_refreshed,
                on_refresh_failed=on_refresh_failed
            )
        
        success = await ssid_service.start()
        
        if success:
            return {
                "success": True,
                "message": "SSID auto-refresh service started successfully"
            }
        else:
            return {
                "success": False,
                "message": "Failed to start SSID auto-refresh service (missing credentials or Selenium not available)"
            }
    except Exception as e:
        logger.error(f"Error starting SSID auto-refresh: {e}")
        return {
            "success": False,
            "message": f"Error starting SSID auto-refresh: {str(e)}"
        }



@router.post("/ssid/stop-auto-refresh")
async def stop_ssid_auto_refresh():
    """
    Stop the SSID auto-refresh service
    """
    try:
        ssid_service = get_ssid_service()
        if ssid_service:
            await ssid_service.stop()
        
        return {
            "success": True,
            "message": "SSID auto-refresh service stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping SSID auto-refresh: {e}")
        return {
            "success": False,
            "message": f"Error stopping SSID auto-refresh: {str(e)}"
        }




# ============================================================================
# POCKET OPTION API CLIENT ENDPOINTS (pocketoptionapi-async)
# ============================================================================

@router.get("/po-api/status")
async def get_po_api_status():
    """Get Pocket Option API Client connection status"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        
        if not service:
            return {
                "success": False,
                "is_connected": False,
                "error": "Service not initialized - check POCKET_OPTION_SSID"
            }
        
        status = service.get_status()
        
        return {
            "success": True,
            **status
        }
    except Exception as e:
        logger.error(f"Error getting PO API status: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_connected": False
        }




@router.post("/po-api/place-order")
async def place_order_api(request: Request):
    """
    Place a trading order
    
    Body:
    - asset: Asset symbol (e.g., 'EURUSD_otc')
    - amount: Trade amount in dollars
    - direction: 'call' or 'put'
    - duration: Trade duration in seconds
    """
    try:
        data = await request.json()
        asset = data.get('asset', 'EURUSD_otc')
        amount = float(data.get('amount', 1.0))
        direction = data.get('direction', 'call')
        duration = int(data.get('duration', 60))
        
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service or not service.is_connected:
            return {
                "success": False,
                "error": "Not connected to Pocket Option"
            }
        
        order = await service.place_order(asset, amount, direction, duration)
        
        if order:
            return {
                "success": True,
                "order": order,
                "message": f"Order placed: {direction.upper()} {asset}"
            }
        else:
            return {
                "success": False,
                "error": "Failed to place order"
            }
        
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-api/order-result/{order_id}")
async def get_order_result_api(order_id: str):
    """Check order result"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service:
            return {
                "success": False,
                "error": "Service not available"
            }
        
        result = await service.check_order_result(order_id)
        
        if result:
            return {
                "success": True,
                "result": result
            }
        else:
            return {
                "success": False,
                "error": "Order result not available yet"
            }
        
    except Exception as e:
        logger.error(f"Error getting order result: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-api/balance")
async def get_balance_api():
    """Get current account balance"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service:
            return {
                "success": False,
                "error": "Service not available"
            }
        
        balance = await service.get_balance()
        
        return {
            "success": True,
            "balance": balance,
            "is_demo": service.is_demo
        }
        
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-api/candles/{asset}")
async def get_candles_api(
    asset: str,
    period: int = 60,
    count: int = 100
):
    """Get historical candles"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service:
            return {
                "success": False,
                "error": "Service not available"
            }
        
        candles = await service.get_candles(asset, period, count)
        
        return {
            "success": True,
            "asset": asset,
            "period": period,
            "count": len(candles),
            "candles": candles
        }
        
    except Exception as e:
        logger.error(f"Error getting candles: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-api/payout/{asset}")
async def get_payout_api(asset: str):
    """Get payout percentage for an asset"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service:
            return {
                "success": False,
                "error": "Service not available"
            }
        
        payout = await service.get_payout(asset)
        
        return {
            "success": True,
            "asset": asset,
            "payout": payout
        }
        
    except Exception as e:
        logger.error(f"Error getting payout: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-api/statistics")
async def get_statistics_api():
    """Get trading statistics"""
    try:
        from pocket_option_api_client import get_api_service
        
        service = await get_api_service()
        if not service:
            return {
                "success": False,
                "error": "Service not available"
            }
        
        stats = service.get_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {
            "success": False,
            "error": str(e)
        }




# ============================================================================
# POCKET OPTION V2 MONITOR ENDPOINTS (BinaryOptionsToolsV2)
# ============================================================================

@router.get("/po-v2/status")
async def get_po_v2_status():
    """Get Pocket Option V2 Monitor connection status"""
    try:
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        
        if not monitor:
            return {
                "success": False,
                "is_connected": False,
                "error": "Monitor not initialized - check POCKET_OPTION_SSID in environment"
            }
        
        balance = await monitor.get_balance()
        is_demo = monitor.is_demo_account()
        
        return {
            "success": True,
            "is_connected": monitor.is_connected,
            "balance": balance,
            "is_demo": is_demo,
            "subscribed_assets": list(monitor.subscriptions.keys()),
            "candle_count": len(monitor.latest_candles)
        }
    except Exception as e:
        logger.error(f"Error getting PO V2 status: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_connected": False
        }




@router.post("/po-v2/subscribe")
async def subscribe_to_asset(request: Request):
    """
    Subscribe to real-time candles for an asset
    
    Body:
    - asset: Asset symbol (e.g., 'EURUSD_otc')
    - timeframe: Timeframe in seconds (default: 60)
    """
    try:
        data = await request.json()
        asset = data.get('asset', 'EURUSD_otc')
        timeframe = data.get('timeframe', 60)
        
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        if not monitor:
            return {
                "success": False,
                "error": "Monitor not initialized"
            }
        
        success = await monitor.subscribe_candles(asset, timeframe)
        
        return {
            "success": success,
            "asset": asset,
            "timeframe": timeframe,
            "message": f"Subscribed to {asset}" if success else "Subscription failed"
        }
        
    except Exception as e:
        logger.error(f"Error subscribing to asset: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/po-v2/unsubscribe")
async def unsubscribe_from_asset(request: Request):
    """
    Unsubscribe from an asset
    
    Body:
    - asset: Asset symbol
    """
    try:
        data = await request.json()
        asset = data.get('asset')
        
        if not asset:
            return {
                "success": False,
                "error": "Asset required"
            }
        
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        if monitor:
            await monitor.unsubscribe(asset)
        
        return {
            "success": True,
            "asset": asset,
            "message": f"Unsubscribed from {asset}"
        }
        
    except Exception as e:
        logger.error(f"Error unsubscribing from asset: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-v2/candle/{asset}")
async def get_latest_candle(asset: str):
    """Get the latest candle for an asset"""
    try:
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        if not monitor:
            return {
                "success": False,
                "error": "Monitor not initialized"
            }
        
        candle = monitor.get_latest_candle(asset)
        
        if candle:
            return {
                "success": True,
                "asset": asset,
                "candle": candle
            }
        else:
            return {
                "success": False,
                "error": f"No candle data for {asset} - not subscribed or no data yet"
            }
        
    except Exception as e:
        logger.error(f"Error getting latest candle: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-v2/history/{asset}")
async def get_historical_candles_v2(
    asset: str,
    period: int = 60,
    count: int = 100
):
    """
    Get historical candles from Pocket Option V2
    
    Args:
        asset: Asset symbol
        period: Candle period in seconds
        count: Number of candles to fetch
    """
    try:
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        if not monitor:
            return {
                "success": False,
                "error": "Monitor not initialized"
            }
        
        candles = await monitor.get_historical_candles(asset, period, count)
        
        return {
            "success": True,
            "asset": asset,
            "period": period,
            "count": len(candles),
            "candles": candles
        }
        
    except Exception as e:
        logger.error(f"Error getting historical candles: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/po-v2/payout/{asset}")
async def get_asset_payout_v2(asset: str):
    """Get payout percentage for an asset"""
    try:
        from pocket_option_v2_monitor import get_monitor
        
        monitor = await get_monitor()
        if not monitor:
            return {
                "success": False,
                "error": "Monitor not initialized"
            }
        
        payout = await monitor.get_payout(asset)
        
        return {
            "success": True,
            "asset": asset,
            "payout": payout
        }
        
    except Exception as e:
        logger.error(f"Error getting payout: {e}")
        return {
            "success": False,
            "error": str(e)
        }




# ============================================================================
# HEADLESS BROWSER AUTOMATION ENDPOINTS
# ============================================================================

@router.post("/headless/start")
async def start_headless_automation(account_type: str = "live"):
    """
    Start headless browser automation for real trading
    
    Args:
        account_type: "demo" or "live" (default: "live")
    
    This launches a headless Chromium browser that:
    1. Logs into Pocket Option with stored credentials
    2. Navigates to the trading page
    3. Is ready to execute trades automatically
    """
    try:
        from browser_automation import get_browser_automation
        
        automation = await get_browser_automation(db)
        result = await automation.start(account_type=account_type)
        
        if result['success']:
            # Set execution mode to HEADLESS
            from auto_execution_mode import get_auto_execution
            auto_exec = await get_auto_execution(db)
            auto_exec.set_mode("HEADLESS")
            auto_exec.browser_automation = automation
        
        return result
        
    except Exception as e:
        logger.error(f"Error starting headless automation: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/headless/stop")
async def stop_headless_automation():
    """Stop headless browser automation"""
    try:
        from browser_automation import stop_browser_automation
        
        await stop_browser_automation()
        
        # Reset execution mode to DEMO
        from auto_execution_mode import get_auto_execution
        auto_exec = await get_auto_execution(db)
        auto_exec.set_mode("DEMO")
        auto_exec.browser_automation = None
        
        return {
            "success": True,
            "message": "Headless browser stopped"
        }
        
    except Exception as e:
        logger.error(f"Error stopping headless automation: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.get("/headless/status")
async def get_headless_status():
    """Get headless browser automation status"""
    try:
        from browser_automation import get_browser_automation
        
        automation = await get_browser_automation(db)
        status = automation.get_status()
        
        # Also get execution mode
        from auto_execution_mode import get_auto_execution
        auto_exec = await get_auto_execution(db)
        
        return {
            "success": True,
            "execution_mode": auto_exec.get_mode(),
            **status
        }
        
    except Exception as e:
        logger.error(f"Error getting headless status: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/headless/execute-trade")
async def execute_headless_trade(
    asset: str = "EURUSD_otc",
    direction: str = "call",
    amount: float = 1.0,
    duration: int = 60
):
    """
    Execute a single trade via headless browser
    
    Args:
        asset: Asset symbol (e.g., 'EURUSD_otc')
        direction: 'call' or 'put'
        amount: Trade amount in dollars
        duration: Trade duration in seconds
    
    Returns:
        Trade execution result
    """
    try:
        from browser_automation import get_browser_automation
        
        automation = await get_browser_automation(db)
        
        # Check if browser is running
        status = automation.get_status()
        if not status['state']['is_running']:
            return {
                "success": False,
                "error": "Headless browser not running. Call /api/headless/start first."
            }
        
        result = await automation.execute_trade(
            asset=asset,
            direction=direction,
            amount=amount,
            duration=duration
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing headless trade: {e}")
        return {
            "success": False,
            "error": str(e)
        }



@router.post("/po-api-v2/connect")
async def connect_pocket_option_v2(request: SSIDConnectRequest):
    """
    Connect to Pocket Option using BinaryOptionsToolsV2
    
    Request Body:
        ssid: The AUTH message from WebSocket (NOT the session cookie!)
              Format: 42["auth",{"session":"YOUR_SESSION_HERE","isDemo":0}]
        demo: True for demo account, False for real (default: False for live)
    
    HOW TO GET SSID:
    1. Login to Pocket Option in your browser
    2. Open Developer Tools (F12)
    3. Go to Network tab
    4. Click "WS" filter (WebSocket)
    5. Refresh the page
    6. Find the WebSocket connection
    7. Look for message with "auth" and "session" (NOT sessionToken)
    8. Right-click and "Copy message"
    9. Paste the entire message as the ssid parameter
    
    Example SSID format:
    42["auth",{"session":"abcd1234...","isDemo":0}]
    """
    try:
        from pocket_option_api_v2 import get_api_client
        
        ssid = request.ssid
        demo = request.demo
        
        if not ssid:
            return {
                "success": False,
                "error": "SSID required. See endpoint description for how to get it.",
                "instructions": [
                    "1. Login to Pocket Option in browser",
                    "2. Open Developer Tools (F12)",
                    "3. Go to Network tab → WS filter",
                    "4. Refresh page",
                    "5. Find WebSocket, look for 'auth' message with 'session'",
                    "6. Right-click → Copy message",
                    "7. Pass entire message as 'ssid' parameter"
                ]
            }
        
        logger.info(f"🔌 Connecting to Pocket Option V2 API (demo={demo})")
        logger.info(f"SSID: {ssid[:50]}...")
        
        client = await get_api_client(ssid=ssid, demo=demo)
        result = await client.connect()
        
        return result
        
    except Exception as e:
        logger.error(f"V2 API connect error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"V2 API connect error: {e}")
        return {
            "success": False,
            "error": str(e)
        }




@router.post("/po-api-v2/disconnect")
async def disconnect_pocket_option_v2():
    """Disconnect from Pocket Option V2 API"""
    try:
        from pocket_option_api_v2 import reset_api_client
        await reset_api_client()
        return {"success": True, "message": "Disconnected"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/po-api-v2/status")
async def get_pocket_option_v2_status():
    """Get V2 API connection status"""
    try:
        from pocket_option_api_v2 import get_api_client
        
        try:
            client = await get_api_client()
            return client.get_status()
        except ValueError:
            return {
                "success": True,
                "is_connected": False,
                "message": "Client not initialized - call /connect first"
            }
        
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/po-api-v2/balance")
async def get_pocket_option_v2_balance():
    """Get current account balance via V2 API"""
    try:
        from pocket_option_api_v2 import get_api_client
        
        client = await get_api_client()
        result = await client.get_balance()
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/po-api-v2/trade")
async def execute_pocket_option_v2_trade(
    asset: str = "EURUSD_otc",
    direction: str = "call",
    amount: float = 1.0,
    duration: int = 60
):
    """
    Execute a trade via V2 API (Direct WebSocket)
    
    Args:
        asset: Asset symbol (e.g., 'EURUSD_otc', 'GBPUSD_otc')
        direction: 'call' (up) or 'put' (down)
        amount: Trade amount in dollars
        duration: Trade duration in seconds (min 5)
    
    This executes trades directly without browser automation!
    """
    try:
        from pocket_option_api_v2 import get_api_client
        
        client = await get_api_client()
        result = await client.execute_trade(
            asset=asset,
            direction=direction,
            amount=amount,
            duration=duration
        )
        
        return result
        
    except Exception as e:
        logger.error(f"V2 trade error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/po-api-v2/check-result/{order_id}")
async def check_pocket_option_v2_trade_result(order_id: str, timeout: float = 120):
    """
    Check the result of a trade
    
    Args:
        order_id: Order ID from trade execution
        timeout: Max time to wait for result (seconds)
    """
    try:
        from pocket_option_api_v2 import get_api_client
        
        client = await get_api_client()
        result = await client.check_trade_result(order_id, timeout=timeout)
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/po-api-v2/auto-trade")
async def execute_auto_trade_v2(
    ssid: str = None,
    asset: str = "EURUSD_otc",
    direction: str = "call",
    amount: float = 1.0,
    duration: int = 60,
    wait_for_result: bool = False
):
    """
    Execute automated trade via V2 API and optionally wait for result
    
    This is the MAIN ENDPOINT for automated trading!
    Uses direct WebSocket connection, no browser needed.
    
    Args:
        ssid: WebSocket AUTH message (required on first call)
        asset: Asset symbol
        direction: 'call' or 'put'
        amount: Trade amount in dollars
        duration: Trade duration in seconds
        wait_for_result: If True, wait for trade result before returning
    """
    try:
        from pocket_option_api_v2 import get_api_client
        
        # Get or create client
        try:
            client = await get_api_client()
        except ValueError:
            if not ssid:
                return {
                    "success": False,
                    "error": "SSID required for first connection. See /api/po-api-v2/connect for instructions."
                }
            client = await get_api_client(ssid=ssid, demo=False)
        
        if not client.state.is_connected:
            conn = await client.connect()
            if not conn['success']:
                return conn
        
        # Execute trade
        trade_result = await client.execute_trade(
            asset=asset,
            direction=direction,
            amount=amount,
            duration=duration
        )
        
        if not trade_result['success']:
            return trade_result
        
        # Optionally wait for result
        if wait_for_result and trade_result.get('order_id'):
            # Wait for trade duration + buffer
            result = await client.check_trade_result(
                trade_result['order_id'],
                timeout=duration + 30
            )
            trade_result['trade_result'] = result
        
        return trade_result
        
    except Exception as e:
        logger.error(f"Auto trade V2 error: {e}")
        return {"success": False, "error": str(e)}




# ============================================================================
# SELENIUM TRADING BOT ENDPOINTS - Real Browser Automation
# ============================================================================

@router.post("/selenium-bot/start")
async def start_selenium_bot(
    email: str = None,
    password: str = None,
    demo: bool = True,
    headless: bool = True
):
    """
    Start Selenium trading bot with real browser automation
    
    Args:
        email: Pocket Option login email (uses default if not provided)
        password: Pocket Option password (uses default if not provided)
        demo: True for demo account, False for real
        headless: Run browser in headless mode (no visible window)
    
    This bot uses a real Chromium browser to:
    1. Login to Pocket Option
    2. Navigate to trading page
    3. Execute trades by clicking buttons
    """
    try:
        from selenium_trading_bot import get_selenium_bot
        
        # Use defaults if not provided
        if not email:
            email = os.environ.get('POCKET_OPTION_EMAIL', '')
        if not password:
            password = os.environ.get('POCKET_OPTION_PASSWORD', '')
        
        bot = get_selenium_bot(
            email=email,
            password=password,
            demo=demo,
            headless=headless
        )
        
        result = bot.start()
        return result
        
    except Exception as e:
        logger.error(f"Selenium bot start error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/selenium-bot/stop")
async def stop_selenium_bot():
    """Stop the Selenium trading bot"""
    try:
        from selenium_trading_bot import stop_selenium_bot
        stop_selenium_bot()
        return {"success": True, "message": "Bot stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/selenium-bot/status")
async def get_selenium_bot_status():
    """Get Selenium bot status"""
    try:
        from selenium_trading_bot import get_selenium_bot
        
        try:
            bot = get_selenium_bot()
            return bot.get_status()
        except:
            return {
                "success": True,
                "state": {
                    "is_running": False,
                    "message": "Bot not initialized"
                }
            }
        
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/selenium-bot/balance")
async def get_selenium_bot_balance():
    """Get current balance from Selenium bot"""
    try:
        from selenium_trading_bot import get_selenium_bot
        bot = get_selenium_bot()
        return bot.get_balance()
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/selenium-bot/trade")
async def execute_selenium_trade(
    direction: str = "call",
    amount: float = 1.0,
    asset: str = "EURUSD_otc",
    duration: int = 60
):
    """
    Execute a trade via Selenium bot
    
    Args:
        direction: 'call' or 'put'
        amount: Trade amount in dollars
        asset: Asset symbol
        duration: Trade duration in seconds
    
    The bot must be started first with /selenium-bot/start
    """
    try:
        from selenium_trading_bot import get_selenium_bot
        
        bot = get_selenium_bot()
        
        if not bot.state.is_running:
            return {
                "success": False,
                "error": "Bot not running. Start it first with /api/selenium-bot/start"
            }
        
        result = bot.execute_trade(
            direction=direction,
            amount=amount,
            asset=asset,
            duration=duration
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Selenium trade error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/selenium-bot/auto-trade")
async def selenium_auto_trade(
    direction: str = "call",
    amount: float = 1.0,
    asset: str = "EURUSD_otc",
    duration: int = 60,
    demo: bool = True
):
    """
    Execute automated trade via Selenium - starts bot if needed
    
    This is the MAIN ENDPOINT for Selenium-based automated trading!
    Automatically starts the bot if not running.
    
    Args:
        direction: 'call' or 'put'
        amount: Trade amount
        asset: Asset symbol
        duration: Trade duration in seconds
        demo: True for demo, False for real account
    """
    try:
        from selenium_trading_bot import get_selenium_bot
        
        bot = get_selenium_bot(demo=demo, headless=True)
        
        # Start bot if not running
        if not bot.state.is_running:
            logger.info("🚀 Auto-starting Selenium bot...")
            start_result = bot.start()
            
            if not start_result.get('success'):
                return start_result
            
            # Wait for bot to be fully ready
            import asyncio
            await asyncio.sleep(3)
        
        # Execute trade
        result = bot.execute_trade(
            direction=direction,
            amount=amount,
            asset=asset,
            duration=duration
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Selenium auto-trade error: {e}")
        return {"success": False, "error": str(e)}




# =============================================================================
# SSID HEALTH MONITOR ENDPOINTS
# =============================================================================

@router.get("/ssid/health/status")
async def get_ssid_health_status():
    """Get SSID health monitor status and recent alerts"""
    try:
        from ssid_health_monitor import get_health_monitor
        monitor = get_health_monitor()
        return {
            "success": True,
            "status": monitor.get_status()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/ssid/health/alerts")
async def get_ssid_alerts(limit: int = 50, level: str = None):
    """Get recent SSID health alerts"""
    try:
        from ssid_health_monitor import get_health_monitor, AlertLevel
        monitor = get_health_monitor()
        
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level)
            except ValueError:
                pass
        
        alerts = monitor.get_alerts(limit=limit, level=alert_level)
        return {
            "success": True,
            "alerts": alerts,
            "count": len(alerts)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/ssid/health/start")
async def start_health_monitor():
    """Start the SSID health monitor"""
    try:
        from ssid_health_monitor import start_health_monitor
        monitor = await start_health_monitor()
        return {
            "success": True,
            "message": "Health monitor started",
            "status": monitor.get_status()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/ssid/health/stop")
async def stop_health_monitor():
    """Stop the SSID health monitor"""
    try:
        from ssid_health_monitor import get_health_monitor
        monitor = get_health_monitor()
        await monitor.stop()
        return {
            "success": True,
            "message": "Health monitor stopped"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/local-bot/download")
async def download_local_bot():
    """Get the local bot script for download"""
    try:
        import os
        bot_path = "/app/backend/local_bot/pocket_option_local_bot.py"
        if os.path.exists(bot_path):
            with open(bot_path, 'r') as f:
                content = f.read()
            return {
                "success": True,
                "filename": "pocket_option_local_bot.py",
                "content": content,
                "instructions": """
                    1. Save this file to your computer
                    2. Install dependencies: pip install websockets aiohttp requests
                    3. Run: python pocket_option_local_bot.py
                    4. Follow the prompts to connect
                """
            }
        return {"success": False, "error": "Bot file not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/ssid/instructions")
async def get_ssid_instructions():
    """Get detailed SSID extraction instructions"""
    return {
        "success": True,
        "instructions": {
            "title": "How to Get Your Pocket Option SSID",
            "steps": [
                {"step": 1, "action": "Open https://pocketoption.com in Chrome/Firefox"},
                {"step": 2, "action": "Login to your account (demo or real)"},
                {"step": 3, "action": "Press F12 to open Developer Tools"},
                {"step": 4, "action": "Click on 'Network' tab"},
                {"step": 5, "action": "Click 'WS' filter (WebSocket)"},
                {"step": 6, "action": "Refresh the page (F5)"},
                {"step": 7, "action": "Find WebSocket connection to wss://..."},
                {"step": 8, "action": "Click on it, then 'Messages' tab"},
                {"step": 9, "action": "Find message starting with: 42[\"auth\",{...}]"},
                {"step": 10, "action": "Copy the ENTIRE message"}
            ],
            "notes": [
                "SSID expires every 1-24 hours",
                "Never share your SSID",
                "Get fresh SSID if connection fails",
                "Make sure you're logged in before extracting"
            ],
            "example_format": '42["auth",{"session":"ABC123...","isDemo":1,"uid":12345}]'
        }
    }




# =============================================================================
# ENHANCED POCKET OPTION CLIENT ENDPOINTS
# =============================================================================

@router.post("/pocket-option/enhanced/connect")
async def enhanced_connect(ssid: str, is_demo: bool = True):
    """
    Connect using the enhanced Pocket Option client with keep-alive
    
    Features:
    - Automatic ping every 60 seconds
    - Automatic reconnection on disconnect
    - Event-based architecture
    - Better error handling
    """
    try:
        from enhanced_pocket_option_client import create_enhanced_client
        
        client = await create_enhanced_client(ssid=ssid, is_demo=is_demo)
        status = client.get_status()
        
        return {
            "success": status["connected"],
            "status": status,
            "message": "Connected with enhanced client (keep-alive enabled)" if status["connected"] else "Connection failed"
        }
    except Exception as e:
        logger.error(f"Enhanced connect error: {e}")
        return {"success": False, "error": str(e)}




@router.get("/pocket-option/enhanced/status")
async def enhanced_status():
    """Get enhanced client status"""
    try:
        from enhanced_pocket_option_client import get_enhanced_client
        
        client = get_enhanced_client()
        if client:
            return {
                "success": True,
                "status": client.get_status(),
                "statistics": client.get_statistics()
            }
        return {"success": False, "error": "No enhanced client initialized"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/pocket-option/enhanced/trade")
async def enhanced_trade(
    asset: str = "EURUSD_otc",
    amount: float = 1,
    direction: str = "call",
    duration: int = 60
):
    """
    Place trade using enhanced client
    
    Args:
        asset: Asset symbol (e.g., EURUSD_otc, GBPUSD)
        amount: Trade amount in dollars
        direction: "call" or "put"
        duration: Expiration in seconds
    """
    try:
        from enhanced_pocket_option_client import get_enhanced_client
        
        client = get_enhanced_client()
        if not client:
            return {"success": False, "error": "No client connected"}
        
        result = await client.buy(
            asset=asset,
            amount=amount,
            direction=direction,
            duration=duration
        )
        
        return result
    except Exception as e:
        logger.error(f"Enhanced trade error: {e}")
        return {"success": False, "error": str(e)}




@router.post("/pocket-option/enhanced/disconnect")
async def enhanced_disconnect():
    """Disconnect enhanced client"""
    try:
        from enhanced_pocket_option_client import get_enhanced_client
        
        client = get_enhanced_client()
        if client:
            await client.disconnect()
            return {"success": True, "message": "Disconnected"}
        return {"success": False, "error": "No client to disconnect"}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/desktop-client/signals")
async def get_desktop_client_signals():
    """
    Get pending signals for the desktop client to execute
    """
    try:
        # Get signals that haven't been sent to desktop client yet
        pending = _desktop_client_state.get("pending_signals", [])
        
        # Clear pending after sending
        _desktop_client_state["pending_signals"] = []
        
        return {
            "success": True,
            "signals": pending,
            "count": len(pending)
        }
    except Exception as e:
        logger.error(f"Error getting desktop signals: {e}")
        return {"success": False, "signals": [], "error": str(e)}




@router.post("/desktop-client/trade-result")
async def report_desktop_trade_result(result: Dict[str, Any]):
    """
    Desktop client reports trade execution result
    """
    try:
        # Store the trade result
        result["received_at"] = datetime.now(timezone.utc).isoformat()
        _desktop_client_state["executed_trades"].append(result)
        
        # Keep only last 100 trades
        if len(_desktop_client_state["executed_trades"]) > 100:
            _desktop_client_state["executed_trades"] = _desktop_client_state["executed_trades"][-100:]
        
        logger.info(f"📊 Desktop trade result: {result.get('direction')} {result.get('asset')} - {'✅' if result.get('success') else '❌'}")
        
        return {
            "success": True,
            "message": "Trade result recorded"
        }
    except Exception as e:
        logger.error(f"Error recording trade result: {e}")
        return {"success": False, "error": str(e)}




@router.post("/desktop-client/status")
async def update_desktop_client_status(status: Dict[str, Any]):
    """
    Desktop client sends status update
    """
    try:
        _desktop_client_state.update({
            "connected": status.get("connected", False),
            "balance": status.get("balance", 0.0),
            "account_type": status.get("account_type", "demo"),
            "last_seen": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/desktop-client/status")
async def get_desktop_client_status():
    """
    Get current desktop client status
    """
    last_seen = _desktop_client_state.get("last_seen")
    is_online = False
    
    if last_seen:
        try:
            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            seconds_ago = (datetime.now(timezone.utc) - last_seen_dt).total_seconds()
            is_online = seconds_ago < 30  # Consider online if seen in last 30 seconds
        except:
            pass
    
    return {
        "success": True,
        "status": {
            "connected": _desktop_client_state.get("connected", False),
            "is_online": is_online,
            "balance": _desktop_client_state.get("balance", 0.0),
            "account_type": _desktop_client_state.get("account_type", "demo"),
            "last_seen": last_seen,
            "recent_trades": len(_desktop_client_state.get("executed_trades", []))
        }
    }




@router.post("/desktop-client/send-signal")
async def send_signal_to_desktop(signal: Dict[str, Any]):
    """
    Queue a signal to be sent to desktop client
    """
    try:
        signal["id"] = str(uuid.uuid4())
        signal["queued_at"] = datetime.now(timezone.utc).isoformat()
        
        _desktop_client_state["pending_signals"].append(signal)
        
        logger.info(f"📤 Signal queued for desktop: {signal.get('direction')} {signal.get('asset')}")
        
        return {
            "success": True,
            "signal_id": signal["id"],
            "message": "Signal queued for desktop client"
        }
    except Exception as e:
        logger.error(f"Error queuing signal: {e}")
        return {"success": False, "error": str(e)}




@router.get("/desktop-client/download")
async def download_desktop_client():
    """
    Download the desktop client files as a zip
    """
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    
    try:
        # Create zip in memory
        zip_buffer = io.BytesIO()
        
        desktop_path = "/app/backend/desktop_client"
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in ['main.py', 'config.py', 'requirements.txt', 'README.md']:
                filepath = os.path.join(desktop_path, filename)
                if os.path.exists(filepath):
                    zip_file.write(filepath, f"pocket_option_desktop_bot/{filename}")
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=pocket_option_desktop_bot.zip"
            }
        )
    except Exception as e:
        logger.error(f"Error creating download: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/desktop-client/trades")
async def get_desktop_trades(limit: int = 50):
    """
    Get recent trades executed by desktop client
    """
    trades = _desktop_client_state.get("executed_trades", [])
    return {
        "success": True,
        "trades": trades[-limit:],
        "count": len(trades)
    }



@router.post("/auto-login/attempt")
async def attempt_auto_login(
    email: str,
    password: str,
    use_stealth_first: bool = True,
    captcha_api_key: Optional[str] = None
):
    """
    Attempt automated login to Pocket Option
    
    Strategy:
    1. Try stealth browser first (free, may be blocked by CAPTCHA)
    2. If CAPTCHA detected and API key provided, use 2Captcha solver (~$0.003/solve)
    3. Return manual instructions if all else fails
    
    Args:
        email: Pocket Option account email
        password: Account password
        use_stealth_first: Try stealth browser before CAPTCHA solver (currently ignored, always uses combined approach)
        captcha_api_key: 2Captcha API key (optional, uses env var if not provided)
    """
    try:
        service = get_auto_login_service(captcha_api_key)
        result = await service.auto_login(email, password)
        
        return {
            "success": result.success,
            "result": result.to_dict(),
            "stats": service.get_login_stats(),
            "message": "Login successful! SSID has been obtained." if result.success else result.error
        }
    except Exception as e:
        logger.error(f"Auto login error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Auto login failed. Please try manual SSID extraction."
        }




@router.get("/auto-login/stats")
async def get_login_stats():
    """Get auto login statistics and available methods"""
    try:
        service = get_auto_login_service()
        return {
            "success": True,
            "stats": service.get_login_stats()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.get("/auto-login/last-ssid")
async def get_last_obtained_ssid():
    """Get the last successfully obtained SSID"""
    try:
        service = get_auto_login_service()
        ssid = service.get_last_ssid()
        
        if ssid:
            return {
                "success": True,
                "has_ssid": True,
                "ssid_preview": ssid[:50] + "..." if len(ssid) > 50 else ssid,
                "message": "SSID available from last successful login"
            }
        else:
            return {
                "success": True,
                "has_ssid": False,
                "message": "No SSID available. Please attempt auto login first."
            }
    except Exception as e:
        return {"success": False, "error": str(e)}




@router.post("/auto-login/set-captcha-key")
async def set_captcha_api_key(api_key: str):
    """
    Set 2Captcha API key for CAPTCHA solving
    
    Get your API key from: https://2captcha.com/
    Cost: ~$2.99 per 1000 CAPTCHAs (~$0.003 per solve)
    """
    try:
        # Re-initialize service with new key
        global _auto_login_service
        from auto_login_service import AutoLoginService
        _auto_login_service = AutoLoginService(api_key)
        
        return {
            "success": True,
            "message": "2Captcha API key configured successfully",
            "captcha_solver_enabled": True
        }
    except Exception as e:
        return {"success": False, "error": str(e)}



@router.get("/ssid/health/status")
async def get_ssid_health_status():
    """Get SSID health monitor status"""
    try:
        monitor = get_health_monitor(db)
        status = monitor.get_status()
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return {"success": False, "error": str(e)}




@router.post("/ssid/health/start")
async def start_ssid_health_monitor():
    """Start the SSID health monitor"""
    try:
        monitor = await start_health_monitor(db)
        return {
            "success": True,
            "message": "Health monitor started",
            "status": monitor.get_status()
        }
    except Exception as e:
        logger.error(f"Error starting health monitor: {e}")
        return {"success": False, "error": str(e)}




@router.post("/ssid/health/stop")
async def stop_ssid_health_monitor():
    """Stop the SSID health monitor"""
    try:
        monitor = get_health_monitor(db)
        await monitor.stop()
        return {
            "success": True,
            "message": "Health monitor stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping health monitor: {e}")
        return {"success": False, "error": str(e)}




@router.get("/ssid/health/alerts")
async def get_ssid_alerts(limit: int = 50):
    """Get recent SSID alerts"""
    try:
        monitor = get_health_monitor(db)
        alerts = monitor.get_alerts(limit=limit)
        return {
            "success": True,
            "count": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return {"success": False, "error": str(e)}




# =====================================================
# SSID AUTO-REFRESH ENDPOINTS
# =====================================================

@router.get("/ssid/status")
async def get_ssid_status():
    """Get current SSID status and auto-refresh information"""
    ssid_service = get_ssid_service()
    
    if ssid_service:
        status = ssid_service.get_status()
        return {
            "success": True,
            "ssid_service": status,
            "auto_refresh_available": True
        }
    else:
        # Check for manual SSID in environment
        current_ssid = os.environ.get('POCKET_OPTION_SSID', '')
        return {
            "success": True,
            "ssid_service": {
                "is_running": False,
                "has_credentials": False,
                "ssid_status": {
                    "ssid_preview": current_ssid[:20] + "..." if len(current_ssid) > 20 else current_ssid,
                    "is_valid": bool(current_ssid),
                    "refresh_count": 0
                }
            },
            "auto_refresh_available": False,
            "message": "SSID auto-refresh service not initialized. Start Telegram bot to enable."
        }




@router.post("/ssid/refresh")
async def manual_ssid_refresh():
    """Manually trigger SSID refresh using auto-login"""
    ssid_service = get_ssid_service()
    
    if ssid_service and ssid_service.is_running:
        success = await ssid_service.refresh_ssid()
        
        if success:
            return {
                "success": True,
                "message": "SSID refreshed successfully",
                "new_ssid_preview": ssid_service.get_current_ssid()[:20] + "..."
            }
        else:
            return {
                "success": False,
                "error": "SSID refresh failed",
                "last_error": ssid_service.status.last_refresh_error
            }
    else:
        # Try to refresh using auto-login directly
        try:
            from auto_login_service import get_auto_login_service
            login_service = get_auto_login_service()
            
            email = os.environ.get('POCKET_OPTION_EMAIL', '')
            password = os.environ.get('POCKET_OPTION_PASSWORD', '')
            
            if not email or not password:
                return {
                    "success": False,
                    "error": "No credentials configured for auto-login",
                    "hint": "Set POCKET_OPTION_EMAIL and POCKET_OPTION_PASSWORD in environment"
                }
            
            result = await login_service.auto_login(email, password)
            
            if result.success:
                # Update environment variable
                os.environ['POCKET_OPTION_SSID'] = result.ssid
                
                # Notify via Telegram if bot is running
                telegram_bot = get_telegram_bot(db)
                if telegram_bot.is_running:
                    await telegram_bot.send_message(
                        f"🔄 <b>SSID Manually Refreshed!</b>\n\n"
                        f"✅ New SSID obtained\n"
                        f"📋 Preview: <code>{result.ssid[:20]}...</code>"
                    )
                
                return {
                    "success": True,
                    "message": "SSID refreshed via auto-login",
                    "new_ssid_preview": result.ssid[:20] + "...",
                    "method": result.method_used.value if result.method_used else "unknown"
                }
            else:
                return {
                    "success": False,
                    "error": result.error or "Auto-login failed",
                    "status": result.status.value
                }
                
        except Exception as e:
            logger.error(f"Manual SSID refresh error: {e}")
            return {
                "success": False,
                "error": str(e)
            }




@router.put("/ssid/settings")
async def update_ssid_settings(
    refresh_interval_minutes: int = 45,
    auto_refresh_enabled: bool = True
):
    """Update SSID auto-refresh settings"""
    ssid_service = get_ssid_service()
    
    if ssid_service:
        ssid_service.refresh_interval = refresh_interval_minutes
        
        if auto_refresh_enabled and not ssid_service.is_running:
            await ssid_service.start()
        elif not auto_refresh_enabled and ssid_service.is_running:
            await ssid_service.stop()
        
        return {
            "success": True,
            "message": "SSID settings updated",
            "settings": {
                "refresh_interval_minutes": refresh_interval_minutes,
                "auto_refresh_enabled": ssid_service.is_running
            }
        }
    else:
        return {
            "success": False,
            "error": "SSID service not initialized. Start Telegram bot first."
        }


