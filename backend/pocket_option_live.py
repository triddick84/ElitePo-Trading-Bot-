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
    
    Args:
        app_url: The URL of our trading app (e.g., https://your-app.preview.emergentagent.com)
    
    Returns:
        JavaScript code to paste in browser console
    """
    script = f'''
// Pocket Option Bridge Script - Paste this in browser console
(function() {{
  console.log('🚀 Pocket Option Bridge Starting...');
  
  // Check if we're on the right site
  if (!window.location.href.includes('pocketoption.com') && 
      !window.location.href.includes('pocket2.click') &&
      !window.location.href.includes('po.market')) {{
    console.log('⚠️ Please run this script on pocketoption.com');
    return;
  }}
  
  let connected = false;
  let messageCount = 0;
  const appUrl = '{app_url}';
  
  // Function to forward WebSocket messages
  function forwardMessage(data, wsUrl) {{
    fetch(appUrl + '/api/bridge/ws-stream', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        type: 'ws_message',
        data: data,
        timestamp: Date.now(),
        url: wsUrl
      }})
    }}).then(() => {{
      messageCount++;
      if (!connected) {{
        connected = true;
        console.log('🔗 Successfully connected to your trading app!');
      }}
      if (messageCount % 100 === 0) {{
        console.log('📊 Messages sent:', messageCount);
      }}
    }}).catch(err => {{
      console.error('❌ Failed to send data to app:', err);
    }});
  }}
  
  // Check for existing WebSocket connections
  function findExistingConnections() {{
    console.log('🔍 Looking for existing WebSocket connections...');
    
    for (let prop in window) {{
      try {{
        if (window[prop] && window[prop].constructor && 
            window[prop].constructor.name === 'WebSocket' &&
            (window[prop].url.includes('po.market') || 
             window[prop].url.includes('pocketoption') ||
             window[prop].url.includes('pocket'))) {{
          console.log('📡 Found existing WebSocket:', window[prop].url);
          
          const originalOnMessage = window[prop].onmessage;
          window[prop].onmessage = function(event) {{
            forwardMessage(event.data, window[prop].url);
            if (originalOnMessage) originalOnMessage.call(this, event);
          }};
          
          window[prop].addEventListener('message', function(event) {{
            forwardMessage(event.data, window[prop].url);
          }});
          
          console.log('✅ Hooked into existing connection!');
          return true;
        }}
      }} catch (e) {{}}
    }}
    return false;
  }}
  
  // Intercept new WebSocket connections
  const originalWebSocket = window.WebSocket;
  window.WebSocket = function(url, protocols) {{
    const ws = new originalWebSocket(url, protocols);
    
    if (url.includes('po.market') || url.includes('pocketoption') || url.includes('pocket')) {{
      console.log('📡 New WebSocket connection:', url);
      
      ws.addEventListener('message', function(event) {{
        forwardMessage(event.data, url);
      }});
      
      ws.addEventListener('open', function() {{
        console.log('🔓 WebSocket opened:', url);
        // Send connection notification
        fetch(appUrl + '/api/bridge/connected', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ url: url, timestamp: Date.now() }})
        }});
      }});
      
      ws.addEventListener('close', function() {{
        console.log('🔒 WebSocket closed:', url);
        connected = false;
      }});
    }}
    
    return ws;
  }};
  
  Object.setPrototypeOf(window.WebSocket, originalWebSocket);
  Object.defineProperty(window.WebSocket, 'prototype', {{
    value: originalWebSocket.prototype,
    writable: false
  }});
  
  const foundExisting = findExistingConnections();
  
  if (!foundExisting) {{
    console.log('💡 No existing connections found. The bridge will activate when you navigate to trading pages or refresh.');
  }}
  
  console.log('✅ Bridge script installed! Monitoring for WebSocket connections...');
  console.log('🏠 Forwarding data to:', appUrl);
  
  // Test connection to app
  fetch(appUrl + '/api/bridge/status')
    .then(r => r.json())
    .then(data => console.log('🏠 App connection test:', data.connected ? 'Connected' : 'Waiting'))
    .catch(() => console.log('⚠️ Could not reach your app. Make sure it\\'s running.'));
  
  // Keep-alive heartbeat
  setInterval(() => {{
    if (connected) {{
      fetch(appUrl + '/api/bridge/heartbeat', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ timestamp: Date.now(), messages: messageCount }})
      }}).catch(() => {{}});
    }}
  }}, 10000);
}})();
'''
    return script


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
        app_url = "https://YOUR-APP-URL.preview.emergentagent.com"
    return generate_bridge_script(app_url)
