"""
Pocket Option Live Connection Module
Based on: https://github.com/GILGALO/PocketOptionOTCbot-mainzip

This module provides:
1. WebSocket Bridge for browser-based data streaming
2. Real-time candle data parsing
3. Live price updates
4. Signal integration with existing strategies
"""

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import deque
import time

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class PocketOptionCandle:
    """Single candle data from Pocket Option"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_list(self) -> List:
        """Return [timestamp, open, close, high, low] format"""
        return [self.timestamp, self.open, self.close, self.high, self.low]


@dataclass
class PocketOptionAsset:
    """Asset information from Pocket Option"""
    symbol: str
    payout: float = 0.0
    is_active: bool = True
    last_price: float = 0.0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    candles: List[PocketOptionCandle] = field(default_factory=list)


@dataclass
class BridgeMessage:
    """Message received from browser bridge"""
    type: str
    data: Any
    timestamp: int
    url: str = ""
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'BridgeMessage':
        return cls(
            type=d.get('type', 'unknown'),
            data=d.get('data'),
            timestamp=d.get('timestamp', int(time.time() * 1000)),
            url=d.get('url', '')
        )


# ============================================================================
# POCKET OPTION AVAILABLE ASSETS
# ============================================================================

POCKET_OPTION_ASSETS = {
    # Forex OTC
    'EURUSD_otc': {'name': 'EUR/USD OTC', 'type': 'forex'},
    'GBPUSD_otc': {'name': 'GBP/USD OTC', 'type': 'forex'},
    'USDJPY_otc': {'name': 'USD/JPY OTC', 'type': 'forex'},
    'AUDUSD_otc': {'name': 'AUD/USD OTC', 'type': 'forex'},
    'USDCAD_otc': {'name': 'USD/CAD OTC', 'type': 'forex'},
    'USDCHF_otc': {'name': 'USD/CHF OTC', 'type': 'forex'},
    'NZDUSD_otc': {'name': 'NZD/USD OTC', 'type': 'forex'},
    'EURGBP_otc': {'name': 'EUR/GBP OTC', 'type': 'forex'},
    'EURJPY_otc': {'name': 'EUR/JPY OTC', 'type': 'forex'},
    'GBPJPY_otc': {'name': 'GBP/JPY OTC', 'type': 'forex'},
    
    # Stocks OTC
    '#AAPL_otc': {'name': 'Apple OTC', 'type': 'stock'},
    '#TSLA_otc': {'name': 'Tesla OTC', 'type': 'stock'},
    '#AMZN_otc': {'name': 'Amazon OTC', 'type': 'stock'},
    '#MSFT_otc': {'name': 'Microsoft OTC', 'type': 'stock'},
    '#GOOGL_otc': {'name': 'Google OTC', 'type': 'stock'},
    '#FB_otc': {'name': 'Meta OTC', 'type': 'stock'},
    '#NFLX_otc': {'name': 'Netflix OTC', 'type': 'stock'},
    'VISA_otc': {'name': 'Visa OTC', 'type': 'stock'},
    '#BA_otc': {'name': 'Boeing OTC', 'type': 'stock'},
    '#JNJ_otc': {'name': 'Johnson & Johnson OTC', 'type': 'stock'},
    
    # Crypto OTC
    'BTCUSD_otc': {'name': 'Bitcoin OTC', 'type': 'crypto'},
    'ETHUSD_otc': {'name': 'Ethereum OTC', 'type': 'crypto'},
    'LTCUSD_otc': {'name': 'Litecoin OTC', 'type': 'crypto'},
    
    # Regular Forex
    'EURUSD': {'name': 'EUR/USD', 'type': 'forex'},
    'GBPUSD': {'name': 'GBP/USD', 'type': 'forex'},
    'USDJPY': {'name': 'USD/JPY', 'type': 'forex'},
}


# ============================================================================
# WEBSOCKET DATA PARSER
# ============================================================================

class PocketOptionDataParser:
    """
    Parser for Pocket Option WebSocket messages
    Based on the bot's websocket_log function
    """
    
    def __init__(self):
        self.assets: Dict[str, PocketOptionAsset] = {}
        self.current_period = 1  # Default 1 second/candle
        self.current_asset: Optional[str] = None
        self.last_parse_time = datetime.now(timezone.utc)
        
    def parse_binary_message(self, payload_data: str) -> Optional[Dict]:
        """
        Parse base64 encoded binary WebSocket message
        
        Expected format after decode:
        {
            "history": [...],
            "candles": [...],
            "asset": "EURUSD_otc",
            "period": 1
        }
        OR real-time update:
        [[asset, timestamp, price], ...]
        """
        try:
            # Decode base64
            decoded = base64.b64decode(payload_data).decode('utf-8')
            data = json.loads(decoded)
            return data
        except Exception as e:
            logger.debug(f"Failed to parse binary message: {e}")
            return None
    
    def parse_websocket_message(self, raw_data: Any) -> Optional[Dict]:
        """
        Parse raw WebSocket message from bridge
        Handles both JSON and binary formats
        """
        try:
            if isinstance(raw_data, str):
                # Try JSON parse first
                try:
                    return json.loads(raw_data)
                except json.JSONDecodeError:
                    # Try base64 decode
                    return self.parse_binary_message(raw_data)
            elif isinstance(raw_data, dict):
                return raw_data
            return None
        except Exception as e:
            logger.debug(f"Message parse error: {e}")
            return None
    
    def process_history_data(self, data: Dict) -> bool:
        """
        Process historical candle data from WebSocket
        
        Format: {
            "history": [[timestamp, price], ...],
            "candles": [[timestamp, open, close, high, low], ...],
            "asset": "EURUSD_otc",
            "period": 1
        }
        """
        try:
            if 'history' not in data:
                return False
            
            asset = data.get('asset', 'unknown')
            period = data.get('period', 1)
            
            # Update current tracking
            if not self.current_asset:
                self.current_asset = asset
            self.current_period = period
            
            # Create asset if not exists
            if asset not in self.assets:
                self.assets[asset] = PocketOptionAsset(symbol=asset)
            
            # Parse candles (reversed to oldest first)
            candles_raw = list(reversed(data.get('candles', [])))
            candles = []
            
            for c in candles_raw:
                if len(c) >= 5:
                    candle = PocketOptionCandle(
                        timestamp=c[0],
                        open=c[1],
                        close=c[2],
                        high=c[3],
                        low=c[4]
                    )
                    candles.append(candle)
            
            # Process history data (tick-level)
            for tstamp, value in data.get('history', []):
                tstamp = int(float(tstamp))
                
                # Update existing candle or create new one
                if candles:
                    last_candle = candles[-1]
                    last_candle.close = value
                    if value > last_candle.high:
                        last_candle.high = value
                    if value < last_candle.low:
                        last_candle.low = value
                
                # Check if new candle should be created
                if tstamp % period == 0:
                    existing_timestamps = [c.timestamp for c in candles]
                    if tstamp not in existing_timestamps:
                        new_candle = PocketOptionCandle(
                            timestamp=tstamp,
                            open=value,
                            close=value,
                            high=value,
                            low=value
                        )
                        candles.append(new_candle)
            
            # Store candles
            self.assets[asset].candles = candles
            self.assets[asset].last_update = datetime.now(timezone.utc)
            
            if candles:
                self.assets[asset].last_price = candles[-1].close
            
            logger.info(f"📊 Loaded {len(candles)} candles for {asset} (period: {period}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error processing history data: {e}")
            return False
    
    def process_realtime_update(self, data: Any) -> bool:
        """
        Process real-time price update
        
        Format: [[asset, timestamp, price], ...]
        """
        try:
            if not isinstance(data, list) or len(data) == 0:
                return False
            
            update = data[0]
            if not isinstance(update, list) or len(update) < 3:
                return False
            
            asset = update[0]
            timestamp = int(float(update[1]))
            price = float(update[2])
            
            if asset not in self.assets:
                self.assets[asset] = PocketOptionAsset(symbol=asset)
            
            asset_data = self.assets[asset]
            asset_data.last_price = price
            asset_data.last_update = datetime.now(timezone.utc)
            
            # Update latest candle
            if asset_data.candles:
                last_candle = asset_data.candles[-1]
                last_candle.close = price
                
                if price > last_candle.high:
                    last_candle.high = price
                if price < last_candle.low:
                    last_candle.low = price
                
                # Check if new candle should start
                if timestamp % self.current_period == 0:
                    existing_timestamps = [c.timestamp for c in asset_data.candles]
                    if timestamp not in existing_timestamps:
                        new_candle = PocketOptionCandle(
                            timestamp=timestamp,
                            open=price,
                            close=price,
                            high=price,
                            low=price
                        )
                        asset_data.candles.append(new_candle)
                        logger.debug(f"📈 New candle for {asset} at {timestamp}")
            
            return True
            
        except Exception as e:
            logger.debug(f"Error processing realtime update: {e}")
            return False
    
    def process_message(self, message: BridgeMessage) -> Dict:
        """
        Process incoming bridge message
        
        Returns:
            Dict with processing result
        """
        result = {
            'success': False,
            'type': 'unknown',
            'asset': None,
            'candles_count': 0
        }
        
        try:
            data = self.parse_websocket_message(message.data)
            
            if data is None:
                return result
            
            # Check if it's history data
            if isinstance(data, dict) and 'history' in data:
                if self.process_history_data(data):
                    result['success'] = True
                    result['type'] = 'history'
                    result['asset'] = data.get('asset')
                    result['candles_count'] = len(self.assets.get(data.get('asset'), PocketOptionAsset('')).candles)
            
            # Check if it's realtime update
            elif isinstance(data, list):
                if self.process_realtime_update(data):
                    result['success'] = True
                    result['type'] = 'realtime'
                    if data and len(data[0]) >= 1:
                        result['asset'] = data[0][0]
            
            self.last_parse_time = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
        
        return result
    
    def get_candles_dataframe(self, asset: str):
        """Get candles as pandas DataFrame"""
        try:
            import pandas as pd
            
            if asset not in self.assets:
                return None
            
            candles = self.assets[asset].candles
            if not candles:
                return None
            
            data = [{
                'timestamp': c.timestamp,
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume
            } for c in candles]
            
            df = pd.DataFrame(data)
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame: {e}")
            return None
    
    def get_asset_summary(self) -> Dict:
        """Get summary of all tracked assets"""
        summary = {}
        for symbol, asset in self.assets.items():
            summary[symbol] = {
                'last_price': asset.last_price,
                'candles_count': len(asset.candles),
                'last_update': asset.last_update.isoformat() if asset.last_update else None,
                'is_active': asset.is_active
            }
        return summary


# ============================================================================
# BRIDGE CONNECTION MANAGER
# ============================================================================

class PocketOptionBridge:
    """
    Manages connection between browser bridge and trading system
    
    Usage:
    1. Paste bridge script in Pocket Option browser console
    2. Bridge sends WebSocket data to our API endpoint
    3. This class processes the data for trading signals
    """
    
    def __init__(self):
        self.parser = PocketOptionDataParser()
        self.is_connected = False
        self.last_message_time: Optional[datetime] = None
        self.message_count = 0
        self.signal_callbacks: List[Callable] = []
        
        # Connection status
        self.connection_status = {
            'connected': False,
            'last_heartbeat': None,
            'messages_received': 0,
            'assets_tracked': 0,
            'error': None
        }
        
        logger.info("🌉 Pocket Option Bridge initialized")
    
    def receive_message(self, data: Dict) -> Dict:
        """
        Receive and process message from browser bridge
        
        Called by API endpoint when bridge sends data
        """
        try:
            message = BridgeMessage.from_dict(data)
            result = self.parser.process_message(message)
            
            self.message_count += 1
            self.last_message_time = datetime.now(timezone.utc)
            self.is_connected = True
            
            # Update connection status
            self.connection_status['connected'] = True
            self.connection_status['last_heartbeat'] = self.last_message_time.isoformat()
            self.connection_status['messages_received'] = self.message_count
            self.connection_status['assets_tracked'] = len(self.parser.assets)
            self.connection_status['error'] = None
            
            # Trigger callbacks if we have new data
            if result['success'] and result['type'] == 'history':
                self._trigger_signal_check(result['asset'])
            
            return {
                'success': True,
                'processed': result,
                'status': 'connected'
            }
            
        except Exception as e:
            logger.error(f"Bridge message error: {e}")
            self.connection_status['error'] = str(e)
            return {
                'success': False,
                'error': str(e)
            }
    
    def register_signal_callback(self, callback: Callable):
        """Register callback for when new data arrives"""
        self.signal_callbacks.append(callback)
    
    def _trigger_signal_check(self, asset: str):
        """Trigger signal check when new data arrives"""
        for callback in self.signal_callbacks:
            try:
                callback(asset, self.parser.assets.get(asset))
            except Exception as e:
                logger.error(f"Signal callback error: {e}")
    
    def get_status(self) -> Dict:
        """Get bridge connection status"""
        # Check if connection is stale (no messages for 30 seconds)
        if self.last_message_time:
            age = (datetime.now(timezone.utc) - self.last_message_time).total_seconds()
            if age > 30:
                self.is_connected = False
                self.connection_status['connected'] = False
        
        return {
            **self.connection_status,
            'parser_summary': self.parser.get_asset_summary()
        }
    
    def get_candles(self, asset: str) -> Optional[List[Dict]]:
        """Get candles for an asset"""
        if asset not in self.parser.assets:
            return None
        
        return [c.to_dict() for c in self.parser.assets[asset].candles]
    
    def get_dataframe(self, asset: str):
        """Get candles as DataFrame for strategy analysis"""
        return self.parser.get_candles_dataframe(asset)
    
    def get_live_price(self, asset: str) -> Optional[float]:
        """Get latest price for an asset"""
        if asset not in self.parser.assets:
            return None
        return self.parser.assets[asset].last_price


# ============================================================================
# BROWSER BRIDGE SCRIPT GENERATOR
# ============================================================================

def generate_bridge_script(app_url: str) -> str:
    """
    Generate the browser bridge script to paste in Pocket Option console
    
    Enhanced Version with:
    - SSID extraction for auto-trading
    - Auto-reconnection logic
    - Better error handling
    - Real-time price streaming
    - Trade execution support
    
    Args:
        app_url: The URL of our trading app (e.g., https://sigbot.preview.emergentagent.com)
    
    Returns:
        JavaScript code to paste in browser console
    """
    script = f'''
// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║           Pocket Option Bridge Script v2.0 - Enhanced Edition              ║
// ║              Paste this in your browser console on Pocket Option           ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

(function() {{
  'use strict';
  
  console.log('%c🚀 Pocket Option Bridge v2.0 Starting...', 'color: #00ff00; font-size: 16px; font-weight: bold;');
  
  // ═══════════════════════════════════════════════════════════════════════════
  // CONFIGURATION
  // ═══════════════════════════════════════════════════════════════════════════
  
  const CONFIG = {{
    appUrl: '{app_url}',
    heartbeatInterval: 5000,      // 5 seconds
    reconnectDelay: 3000,         // 3 seconds
    maxReconnectAttempts: 10,
    debug: true,
    extractSSID: true,
    forwardPrices: true,
    forwardOrders: true
  }};
  
  // ═══════════════════════════════════════════════════════════════════════════
  // STATE MANAGEMENT
  // ═══════════════════════════════════════════════════════════════════════════
  
  const state = {{
    connected: false,
    ssid: null,
    isDemo: null,
    balance: 0,
    messageCount: 0,
    lastMessageTime: null,
    reconnectAttempts: 0,
    activeWebSockets: new Set(),
    trackedAssets: new Set()
  }};
  
  // ═══════════════════════════════════════════════════════════════════════════
  // UTILITY FUNCTIONS
  // ═══════════════════════════════════════════════════════════════════════════
  
  function log(message, type = 'info') {{
    if (!CONFIG.debug && type === 'debug') return;
    
    const colors = {{
      info: '#00bfff',
      success: '#00ff00', 
      warning: '#ffff00',
      error: '#ff0000',
      debug: '#888888'
    }};
    
    console.log(`%c[Bridge] ${{message}}`, `color: ${{colors[type] || colors.info}}`);
  }}
  
  function isValidSite() {{
    const validDomains = ['pocketoption.com', 'pocket2.click', 'po.market', 'po.trade'];
    return validDomains.some(domain => window.location.href.includes(domain));
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // API COMMUNICATION
  // ═══════════════════════════════════════════════════════════════════════════
  
  async function sendToApp(endpoint, data) {{
    try {{
      const response = await fetch(`${{CONFIG.appUrl}}/api/bridge/${{endpoint}}`, {{
        method: 'POST',
        headers: {{ 
          'Content-Type': 'application/json',
          'X-Bridge-Version': '2.0'
        }},
        body: JSON.stringify(data)
      }});
      
      if (response.ok) {{
        state.connected = true;
        state.lastMessageTime = Date.now();
        return await response.json();
      }}
      return null;
    }} catch (err) {{
      log(`Failed to send to app: ${{err.message}}`, 'error');
      return null;
    }}
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // SSID EXTRACTION
  // ═══════════════════════════════════════════════════════════════════════════
  
  function extractSSID() {{
    try {{
      // Method 1: From localStorage
      const keys = Object.keys(localStorage);
      for (const key of keys) {{
        const value = localStorage.getItem(key);
        if (value && (value.includes('session') || value.includes('token'))) {{
          try {{
            const parsed = JSON.parse(value);
            if (parsed.session) {{
              log('SSID found in localStorage', 'success');
              return parsed;
            }}
          }} catch (e) {{}}
        }}
      }}
      
      // Method 2: From cookies
      const cookies = document.cookie.split(';');
      for (const cookie of cookies) {{
        const [name, value] = cookie.trim().split('=');
        if (name && (name.includes('session') || name.includes('ssid'))) {{
          log('SSID found in cookies', 'success');
          return {{ session: decodeURIComponent(value) }};
        }}
      }}
      
      // Method 3: Intercept from WebSocket auth messages
      log('SSID will be captured from WebSocket auth', 'info');
      return null;
    }} catch (e) {{
      log(`SSID extraction error: ${{e.message}}`, 'error');
      return null;
    }}
  }}
  
  function captureSSIDFromMessage(data) {{
    try {{
      if (typeof data === 'string' && data.includes('"auth"')) {{
        // Extract auth data from 42["auth",{...}] format
        const match = data.match(/42\\["auth",(.+)\\]/);
        if (match) {{
          const authData = JSON.parse(match[1]);
          state.ssid = authData.session || data;
          state.isDemo = authData.isDemo === 1;
          
          log(`SSID captured! Mode: ${{state.isDemo ? 'Demo' : 'Real'}}`, 'success');
          
          // Send SSID to app
          sendToApp('ssid-update', {{
            ssid: data,
            isDemo: state.isDemo,
            timestamp: Date.now()
          }});
          
          return true;
        }}
      }}
    }} catch (e) {{}}
    return false;
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // WEBSOCKET INTERCEPTION
  // ═══════════════════════════════════════════════════════════════════════════
  
  function forwardMessage(data, wsUrl, direction = 'receive') {{
    if (!CONFIG.forwardPrices && direction === 'receive') return;
    
    state.messageCount++;
    
    // Check for SSID in auth messages
    if (CONFIG.extractSSID && direction === 'send') {{
      captureSSIDFromMessage(data);
    }}
    
    // Forward to app
    sendToApp('ws-stream', {{
      type: 'ws_message',
      direction: direction,
      data: data,
      timestamp: Date.now(),
      url: wsUrl,
      messageNumber: state.messageCount
    }});
    
    // Log progress every 50 messages
    if (state.messageCount % 50 === 0) {{
      log(`📊 Messages processed: ${{state.messageCount}}`, 'info');
    }}
  }}
  
  function hookWebSocket(ws, url) {{
    if (state.activeWebSockets.has(ws)) return;
    state.activeWebSockets.add(ws);
    
    log(`🔗 Hooking WebSocket: ${{url.substring(0, 50)}}...`, 'info');
    
    // Store original handlers
    const originalOnMessage = ws.onmessage;
    const originalOnOpen = ws.onopen;
    const originalOnClose = ws.onclose;
    const originalOnError = ws.onerror;
    const originalSend = ws.send.bind(ws);
    
    // Override onmessage
    ws.onmessage = function(event) {{
      forwardMessage(event.data, url, 'receive');
      if (originalOnMessage) originalOnMessage.call(this, event);
    }};
    
    // Also add event listener for redundancy
    ws.addEventListener('message', function(event) {{
      // Already handled by onmessage override
    }});
    
    // Override send to capture outgoing messages (including auth)
    ws.send = function(data) {{
      forwardMessage(data, url, 'send');
      return originalSend(data);
    }};
    
    // Handle open
    ws.onopen = function(event) {{
      log(`✅ WebSocket connected: ${{url.substring(0, 50)}}...`, 'success');
      
      sendToApp('connected', {{
        url: url,
        timestamp: Date.now(),
        ssid: state.ssid
      }});
      
      if (originalOnOpen) originalOnOpen.call(this, event);
    }};
    
    // Handle close
    ws.onclose = function(event) {{
      log(`🔒 WebSocket closed: ${{url.substring(0, 50)}}...`, 'warning');
      state.activeWebSockets.delete(ws);
      
      sendToApp('disconnected', {{
        url: url,
        timestamp: Date.now(),
        code: event.code,
        reason: event.reason
      }});
      
      if (originalOnClose) originalOnClose.call(this, event);
    }};
    
    // Handle error
    ws.onerror = function(event) {{
      log(`❌ WebSocket error: ${{url.substring(0, 50)}}...`, 'error');
      if (originalOnError) originalOnError.call(this, event);
    }};
  }}
  
  function findExistingWebSockets() {{
    log('🔍 Scanning for existing WebSocket connections...', 'info');
    let found = 0;
    
    // Scan window properties
    for (const prop in window) {{
      try {{
        const obj = window[prop];
        if (obj && obj instanceof WebSocket && 
            obj.readyState === WebSocket.OPEN &&
            (obj.url.includes('po.market') || 
             obj.url.includes('pocketoption') ||
             obj.url.includes('pocket'))) {{
          hookWebSocket(obj, obj.url);
          found++;
        }}
      }} catch (e) {{}}
    }}
    
    // Scan iframes
    try {{
      const iframes = document.querySelectorAll('iframe');
      iframes.forEach(iframe => {{
        try {{
          const iframeWindow = iframe.contentWindow;
          for (const prop in iframeWindow) {{
            const obj = iframeWindow[prop];
            if (obj && obj instanceof WebSocket && obj.readyState === WebSocket.OPEN) {{
              hookWebSocket(obj, obj.url);
              found++;
            }}
          }}
        }} catch (e) {{}}
      }});
    }} catch (e) {{}}
    
    log(`Found ${{found}} existing WebSocket connection(s)`, found > 0 ? 'success' : 'info');
    return found;
  }}
  
  function interceptNewWebSockets() {{
    const OriginalWebSocket = window.WebSocket;
    
    window.WebSocket = function(url, protocols) {{
      log(`📡 New WebSocket: ${{url.substring(0, 60)}}...`, 'debug');
      
      const ws = protocols 
        ? new OriginalWebSocket(url, protocols) 
        : new OriginalWebSocket(url);
      
      // Hook if it's a Pocket Option connection
      if (url.includes('po.market') || 
          url.includes('pocketoption') || 
          url.includes('pocket')) {{
        hookWebSocket(ws, url);
      }}
      
      return ws;
    }};
    
    // Preserve prototype chain
    window.WebSocket.prototype = OriginalWebSocket.prototype;
    window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
    window.WebSocket.OPEN = OriginalWebSocket.OPEN;
    window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
    window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // BALANCE & TRADE MONITORING
  // ═══════════════════════════════════════════════════════════════════════════
  
  function monitorBalance() {{
    // Try to find balance element on page
    const selectors = [
      '.balance-value',
      '.user-balance',
      '[data-balance]',
      '.balance__value',
      '.header-balance'
    ];
    
    for (const selector of selectors) {{
      const element = document.querySelector(selector);
      if (element) {{
        const text = element.textContent || element.innerText;
        const match = text.match(/[\\d,.]+/);
        if (match) {{
          const newBalance = parseFloat(match[0].replace(',', ''));
          if (newBalance !== state.balance) {{
            state.balance = newBalance;
            log(`💰 Balance updated: $${{newBalance.toFixed(2)}}`, 'info');
            
            sendToApp('balance-update', {{
              balance: newBalance,
              isDemo: state.isDemo,
              timestamp: Date.now()
            }});
          }}
          break;
        }}
      }}
    }}
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // HEARTBEAT & STATUS
  // ═══════════════════════════════════════════════════════════════════════════
  
  function startHeartbeat() {{
    setInterval(async () => {{
      // Monitor balance
      monitorBalance();
      
      // Send heartbeat
      const result = await sendToApp('heartbeat', {{
        timestamp: Date.now(),
        messageCount: state.messageCount,
        activeConnections: state.activeWebSockets.size,
        ssid: state.ssid ? 'present' : 'missing',
        isDemo: state.isDemo,
        balance: state.balance
      }});
      
      if (result) {{
        state.reconnectAttempts = 0;
      }} else {{
        state.reconnectAttempts++;
        if (state.reconnectAttempts > CONFIG.maxReconnectAttempts) {{
          log('⚠️ Lost connection to app. Please refresh.', 'warning');
        }}
      }}
    }}, CONFIG.heartbeatInterval);
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // TRADE EXECUTION
  // ═══════════════════════════════════════════════════════════════════════════
  
  let lastPollTime = 0;
  let pollCount = 0;
  
  async function checkForPendingTrades() {{
    try {{
      pollCount++;
      
      const response = await fetch(`${{CONFIG.appUrl}}/api/trade-executor/pending`, {{
        method: 'GET',
        headers: {{ 'Content-Type': 'application/json' }}
      }});
      
      const data = await response.json();
      
      // Log every 15 polls (30 seconds) to show it's working
      if (pollCount % 15 === 0) {{
        log(`🔍 Poll #${{pollCount}}: Checking for trades... (${{data.pending_trades?.length || 0}} pending)`, 'debug');
      }}
      
      if (data.success && data.pending_trades && data.pending_trades.length > 0) {{
        log(`📋 Found ${{data.pending_trades.length}} pending trade(s)!`, 'success');
        
        for (const trade of data.pending_trades) {{
          log(`🎯 Processing trade: ${{trade.order_id}}`, 'info');
          await executeTrade(trade);
        }}
      }}
    }} catch (error) {{
      if (pollCount % 30 === 0) {{
        log(`⚠️ Trade poll error: ${{error.message}}`, 'warning');
      }}
    }}
  }}
  
  async function executeTrade(trade) {{
    try {{
      log(`🎯 Executing trade: ${{trade.direction.toUpperCase()}} ${{trade.asset}} $${{trade.amount}}`, 'info');
      
      // Find the trading interface
      // This is Pocket Option specific - may need adjustment based on their UI
      
      // 1. Set asset
      if (typeof window.setAsset === 'function') {{
        window.setAsset(trade.asset);
      }}
      
      // 2. Set amount
      if (typeof window.setAmount === 'function') {{
        window.setAmount(trade.amount);
      }}
      
      // 3. Set duration
      if (typeof window.setDuration === 'function') {{
        window.setDuration(trade.duration);
      }}
      
      // 4. Place order
      const orderResult = await placeOrder(trade.direction, trade.asset, trade.amount, trade.duration);
      
      if (orderResult.success) {{
        log(`✅ Trade executed: ${{orderResult.order_id}}`, 'success');
        
        // Confirm execution with backend
        await fetch(`${{CONFIG.appUrl}}/api/trade-executor/confirm-execution`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            order_id: trade.order_id,
            bridge_order_id: orderResult.order_id,
            execution_price: orderResult.price,
            execution_time: new Date().toISOString()
          }})
        }});
        
        // Monitor order for result
        monitorOrderResult(trade.order_id, orderResult.order_id, trade.duration);
      }} else {{
        log(`❌ Trade execution failed: ${{orderResult.error}}`, 'error');
      }}
      
    }} catch (error) {{
      log(`❌ Error executing trade: ${{error.message}}`, 'error');
    }}
  }}
  
  async function placeOrder(direction, asset, amount, duration) {{
    try {{
      log(`🎯 Attempting to place ${{direction.toUpperCase()}} order...`, 'info');
      
      // METHOD 1: Try using global trading functions (if available)
      if (typeof window.placeOrder === 'function') {{
        const result = await window.placeOrder({{
          asset: asset,
          direction: direction === 'call' ? 'higher' : 'lower',
          amount: amount,
          duration: duration
        }});
        
        return {{
          success: true,
          order_id: result.id || result.orderId || result.order_id,
          price: result.price || result.entryPrice
        }};
      }}
      
      // METHOD 2: Find trading buttons by multiple selectors
      const callSelectors = [
        'button.btn-call',
        'button.call-btn',
        'button[class*="call"]',
        'button[class*="higher"]',
        'button[class*="green"]',
        '.btn-call',
        '.call-btn',
        '[class*="call-btn"]',
        'button[data-dir="call"]',
        '.deal-button--call'
      ];
      
      const putSelectors = [
        'button.btn-put',
        'button.put-btn',
        'button[class*="put"]',
        'button[class*="lower"]',
        'button[class*="red"]',
        '.btn-put',
        '.put-btn',
        '[class*="put-btn"]',
        'button[data-dir="put"]',
        '.deal-button--put'
      ];
      
      const selectors = direction === 'call' ? callSelectors : putSelectors;
      let orderButton = null;
      
      // Try CSS selectors first
      for (const selector of selectors) {{
        try {{
          const btn = document.querySelector(selector);
          if (btn && !btn.disabled) {{
            orderButton = btn;
            log(`Found button using: ${{selector}}`, 'debug');
            break;
          }}
        }} catch (e) {{}}
      }}
      
      // Fallback: Find by text content
      if (!orderButton) {{
        const allButtons = document.querySelectorAll('button, div[role="button"], [class*="btn"]');
        const keywords = direction === 'call' 
          ? ['call', 'higher', 'up', 'выше', 'green']
          : ['put', 'lower', 'down', 'ниже', 'red'];
        
        for (const button of allButtons) {{
          const text = (button.textContent || '').toLowerCase();
          const classes = (button.className || '').toLowerCase();
          
          if (keywords.some(kw => text.includes(kw) || classes.includes(kw))) {{
            orderButton = button;
            log(`Found button by keyword match`, 'debug');
            break;
          }}
        }}
      }}
      
      // Fallback: Try position-based selection (call is usually first/left, put is last/right)
      if (!orderButton) {{
        const dealButtons = document.querySelectorAll('.deal-buttons button, .trading-buttons button, [class*="trade"] button');
        if (dealButtons.length >= 2) {{
          orderButton = direction === 'call' ? dealButtons[0] : dealButtons[1];
          log(`Using position-based button selection`, 'debug');
        }}
      }}
      
      if (orderButton) {{
        log(`Clicking ${{direction.toUpperCase()}} button...`, 'info');
        orderButton.click();
        
        // Wait for order to register
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Try to extract order ID
        const orderElements = document.querySelectorAll('[class*="order"], [class*="trade"], [class*="deal"], [id*="order"]');
        let orderId = 'BRIDGE_' + Date.now();
        
        for (const el of orderElements) {{
          const text = el.textContent || '';
          const match = text.match(/#?(\\d{{6,}})/);
          if (match) {{
            orderId = match[1];
            break;
          }}
        }}
        
        log(`✅ Order placed: ${{orderId}}`, 'success');
        
        return {{
          success: true,
          order_id: orderId,
          price: getCurrentPrice(asset)
        }};
      }}
      
      log(`❌ Could not find ${{direction}} button - trading interface not found`, 'error');
      return {{
        success: false,
        error: 'Could not find trading interface - make sure you are on the trading page'
      }};
      
    }} catch (error) {{
      log(`❌ Order error: ${{error.message}}`, 'error');
      return {{
        success: false,
        error: error.message
      }};
    }}
  }}
  
  function getCurrentPrice(asset) {{
    // Try to get current price from page
    try {{
      const priceElements = document.querySelectorAll('[class*="price"], [class*="rate"], [id*="price"], [id*="rate"]');
      for (const el of priceElements) {{
        const text = el.textContent.trim();
        const match = text.match(/\\d+\\.\\d{{2,}}/);
        if (match) {{
          return parseFloat(match[0]);
        }}
      }}
    }} catch (error) {{
      // Silent fail
    }}
    return 0;
  }}
  
  function monitorOrderResult(ourOrderId, bridgeOrderId, duration) {{
    // Wait for trade duration + 5 seconds
    setTimeout(async () => {{
      try {{
        // Try to get result from page
        const result = await getOrderResult(bridgeOrderId);
        
        // Report result to backend
        await fetch(`${{CONFIG.appUrl}}/api/trade-executor/report-result`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            order_id: ourOrderId,
            result: result.status, // 'win', 'loss', or 'draw'
            profit: result.profit,
            close_price: result.closePrice,
            close_time: new Date().toISOString()
          }})
        }});
        
        log(`📊 Trade result reported: ${{result.status.toUpperCase()}} - $${{result.profit.toFixed(2)}}`, 
            result.status === 'win' ? 'success' : 'error');
        
      }} catch (error) {{
        log(`⚠️ Could not get order result: ${{error.message}}`, 'warning');
      }}
    }}, (duration + 5) * 1000);
  }}
  
  async function getOrderResult(orderId) {{
    // Try to find order result in page
    try {{
      // Look for order in history/results section
      const orderElements = document.querySelectorAll('[class*="history"], [class*="result"], [class*="trade"]');
      
      for (const el of orderElements) {{
        if (el.textContent.includes(orderId)) {{
          const text = el.textContent.toLowerCase();
          
          // Check if win/loss
          const isWin = text.includes('win') || text.includes('won') || text.includes('profit') || text.includes('+');
          const isLoss = text.includes('loss') || text.includes('lost') || text.includes('-');
          
          // Try to extract profit amount
          const profitMatch = text.match(/[+-]?\\$?\\d+\\.\\d{{2}}/);
          const profit = profitMatch ? parseFloat(profitMatch[0].replace('$', '')) : 0;
          
          return {{
            status: isWin ? 'win' : isLoss ? 'loss' : 'draw',
            profit: profit,
            closePrice: getCurrentPrice('') // Current price as approximation
          }};
        }}
      }}
      
      // Default to unknown if can't find
      return {{
        status: 'unknown',
        profit: 0,
        closePrice: 0
      }};
      
    }} catch (error) {{
      return {{
        status: 'error',
        profit: 0,
        closePrice: 0
      }};
    }}
  }}
  
  // Start polling for pending trades every 2 seconds
  function startTradePolling() {{
    setInterval(checkForPendingTrades, 2000);
    log('🔄 Trade polling started', 'info');
  }}
  
  // ═══════════════════════════════════════════════════════════════════════════
  // INITIALIZATION
  // ═══════════════════════════════════════════════════════════════════════════
  
  async function initialize() {{
    // Validate site
    if (!isValidSite()) {{
      log('⚠️ Please run this script on pocketoption.com or po.trade', 'warning');
      return;
    }}
    
    log('✅ Running on valid Pocket Option domain', 'success');
    
    // Test connection to app
    const testResult = await sendToApp('status', {{ test: true }});
    if (!testResult) {{
      log('⚠️ Could not reach your trading app. Make sure it\\'s running at:', 'warning');
      log(CONFIG.appUrl, 'info');
    }} else {{
      log('✅ Connected to trading app!', 'success');
    }}
    
    // Try to extract SSID
    if (CONFIG.extractSSID) {{
      const ssidData = extractSSID();
      if (ssidData) {{
        state.ssid = ssidData.session;
        state.isDemo = ssidData.isDemo;
      }}
    }}
    
    // Intercept new WebSockets
    interceptNewWebSockets();
    
    // Find existing WebSockets
    const existing = findExistingWebSockets();
    
    // Start heartbeat
    startHeartbeat();
    
    // Start trade polling
    startTradePolling();
    
    // Display status
    console.log('%c╔═══════════════════════════════════════════════════════════════╗', 'color: #00ff00');
    console.log('%c║          🎯 Pocket Option Bridge v2.0 Active!                  ║', 'color: #00ff00; font-weight: bold');
    console.log('%c╠═══════════════════════════════════════════════════════════════╣', 'color: #00ff00');
    console.log(`%c║ App URL: ${{CONFIG.appUrl.substring(0, 45).padEnd(45)}} ║`, 'color: #00bfff');
    console.log(`%c║ SSID: ${{state.ssid ? 'Captured ✅' : 'Waiting... ⏳'.padEnd(50)}}║`, 'color: #ffff00');
    console.log(`%c║ Mode: ${{state.isDemo !== null ? (state.isDemo ? 'Demo 🎮' : 'Real 💰') : 'Unknown'.padEnd(52)}}║`, 'color: #ff69b4');
    console.log(`%c║ Active WS: ${{String(existing).padEnd(48)}}║`, 'color: #00bfff');
    console.log('%c╚═══════════════════════════════════════════════════════════════╝', 'color: #00ff00');
    
    log('💡 Navigate to a trading chart to start receiving data', 'info');
    log('🎉 Pocket Option Bridge fully initialized!', 'success');
    log('✨ Now monitoring trades and executing automated orders', 'success');
  }}
  
  // Start the bridge
  initialize();
  
}})();
'''
    return script


def generate_bridge_script_minified(app_url: str) -> str:
    """Generate a minified version of the bridge script"""
    # For now, return the full version
    return generate_bridge_script(app_url)


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_bridge_instance: Optional[PocketOptionBridge] = None


def get_pocket_option_bridge() -> PocketOptionBridge:
    """Get singleton bridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = PocketOptionBridge()
    return _bridge_instance


def get_bridge_script(app_url: str = None) -> str:
    """Get the browser bridge script"""
    if app_url is None:
        # Default to placeholder - will be replaced with actual URL
        app_url = "https://sigbot.preview.emergentagent.com"
    return generate_bridge_script(app_url)
