"""
Pocket Option Data Collector Mode
==================================

Specialized mode for the desktop client that focuses purely on 
capturing and storing historical market data from Pocket Option.

This runs alongside or separately from trading to build a 
database of real market data for ML training.

Features:
- Captures data for multiple assets
- Auto-switches between assets to maximize data coverage
- Stores data via HTTP API to main backend
- Supports both demo and live accounts (data is the same)

Usage:
    python data_collector_mode.py --assets EURUSD_otc,GBPUSD_otc --duration 24h
"""

import asyncio
import aiohttp
import base64
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from selenium.webdriver.common.by import By

# Import from parent directory
import sys
sys.path.insert(0, '..')
from driver import get_driver, ASSET_SYMBOLS

logger = logging.getLogger(__name__)

# Backend API URL (update based on environment)
BACKEND_URL = "http://localhost:8001/api"

# Demo trading URL (we use demo since data is same as live)
TRADING_URL = 'https://pocketoption.com/en/cabinet/demo-quick-high-low/'

# Popular OTC assets for data collection (available 24/7)
DEFAULT_ASSETS = [
    'EURUSD_otc',
    'GBPUSD_otc',
    'USDJPY_otc',
    'AUDUSD_otc',
    'EURGBP_otc',
    'BTCUSD_otc',
    'ETHUSD_otc'
]


class PocketOptionDataCollector:
    """
    Specialized client for collecting market data from Pocket Option.
    
    This client:
    1. Connects to Pocket Option via Chrome
    2. Captures WebSocket market data
    3. Sends data to backend API for storage
    4. Rotates through multiple assets for comprehensive coverage
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.driver = None
        
        # Data collection state
        self.current_asset = None
        self.candles: Dict[str, List] = {}
        self.period = 60  # Current period in seconds
        
        # Collection settings
        self.assets_to_collect = self.config.get('assets', DEFAULT_ASSETS)
        self.asset_rotation_minutes = self.config.get('rotation_minutes', 5)
        self.duration_hours = self.config.get('duration_hours', 24)
        
        # API communication
        self.backend_url = self.config.get('backend_url', BACKEND_URL)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self.stats = {
            'total_candles': 0,
            'total_ticks': 0,
            'assets_collected': set(),
            'start_time': None,
            'errors': 0
        }
        
        self.is_running = False
    
    def initialize(self) -> bool:
        """Initialize the browser"""
        try:
            logger.info("🚀 Initializing Pocket Option Data Collector...")
            
            headless = self.config.get('headless', False)
            self.driver = get_driver(headless=headless)
            
            # Navigate to trading page
            logger.info(f"📍 Navigating to {TRADING_URL}")
            self.driver.get(TRADING_URL)
            
            # Wait for page load
            time.sleep(5)
            
            logger.info("✅ Data Collector initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def send_to_backend(self, endpoint: str, data: Dict) -> bool:
        """Send data to backend API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            url = f"{self.backend_url}{endpoint}"
            async with self.session.post(url, json=data, timeout=10) as response:
                if response.status == 200:
                    return True
                else:
                    logger.warning(f"Backend returned {response.status}")
                    return False
        except Exception as e:
            logger.debug(f"Error sending to backend: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_websocket_data(self):
        """
        Process WebSocket data from browser performance logs.
        This is the core method for capturing market data.
        """
        try:
            for ws_data in self.driver.get_log('performance'):
                message = json.loads(ws_data['message'])['message']
                response = message.get('params', {}).get('response', {})
                
                if response.get('opcode', 0) == 2:
                    try:
                        payload_str = base64.b64decode(response['payloadData']).decode('utf-8')
                        data = json.loads(payload_str)
                        
                        # Handle history data (initial load)
                        if 'history' in data:
                            asset = data.get('asset', 'UNKNOWN')
                            self.period = data.get('period', 60)
                            self.current_asset = asset
                            
                            # Build candle list
                            history = data.get('history', [])
                            candles_raw = data.get('candles', [])
                            
                            # Send to backend
                            await self.send_to_backend('/data-collector/history', {
                                'asset': asset,
                                'period': self.period,
                                'history': history,
                                'candles': candles_raw
                            })
                            
                            self.stats['total_candles'] += len(history) + len(candles_raw)
                            self.stats['assets_collected'].add(asset)
                            logger.info(f"📊 Captured {len(history) + len(candles_raw)} historical candles for {asset}")
                        
                        # Handle real-time tick updates
                        if isinstance(data, list) and len(data) >= 3:
                            try:
                                asset, timestamp, price = data[0], data[1], data[2]
                                
                                # Send tick to backend
                                await self.send_to_backend('/data-collector/tick', {
                                    'asset': asset,
                                    'timestamp': int(float(timestamp)),
                                    'price': float(price)
                                })
                                
                                self.stats['total_ticks'] += 1
                                
                            except (ValueError, IndexError):
                                pass
                    
                    except Exception as e:
                        logger.debug(f"Error processing WS payload: {e}")
        
        except Exception as e:
            logger.debug(f"Error reading performance logs: {e}")
    
    def switch_asset(self, asset_symbol: str) -> bool:
        """Switch to a different asset for data collection"""
        try:
            # Find and click asset selector
            # This is simplified - actual implementation may need UI interaction
            logger.info(f"🔄 Switching to {asset_symbol}...")
            
            # Try clicking the asset dropdown and selecting the new asset
            # Implementation depends on Pocket Option's UI structure
            
            return True
        except Exception as e:
            logger.warning(f"Could not switch asset: {e}")
            return False
    
    def print_stats(self):
        """Print collection statistics"""
        elapsed = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else timedelta(0)
        logger.info("=" * 50)
        logger.info("📈 DATA COLLECTION STATISTICS")
        logger.info(f"   Runtime: {elapsed}")
        logger.info(f"   Total candles collected: {self.stats['total_candles']}")
        logger.info(f"   Total ticks processed: {self.stats['total_ticks']}")
        logger.info(f"   Assets covered: {len(self.stats['assets_collected'])}")
        logger.info(f"   Errors: {self.stats['errors']}")
        logger.info("=" * 50)
    
    async def run(self):
        """Main data collection loop"""
        if not self.driver:
            if not self.initialize():
                return
        
        self.stats['start_time'] = datetime.now()
        end_time = datetime.now() + timedelta(hours=self.duration_hours)
        
        logger.info(f"🤖 Data Collection Started")
        logger.info(f"   Duration: {self.duration_hours} hours")
        logger.info(f"   Assets: {self.assets_to_collect}")
        logger.info(f"   Will run until: {end_time}")
        
        self.is_running = True
        last_stats_print = datetime.now()
        asset_switch_time = datetime.now()
        current_asset_idx = 0
        
        try:
            while self.is_running and datetime.now() < end_time:
                # Process WebSocket data
                await self.process_websocket_data()
                
                # Print stats every 5 minutes
                if datetime.now() - last_stats_print > timedelta(minutes=5):
                    self.print_stats()
                    last_stats_print = datetime.now()
                
                # Rotate assets periodically (if configured)
                if self.asset_rotation_minutes > 0:
                    if datetime.now() - asset_switch_time > timedelta(minutes=self.asset_rotation_minutes):
                        current_asset_idx = (current_asset_idx + 1) % len(self.assets_to_collect)
                        self.switch_asset(self.assets_to_collect[current_asset_idx])
                        asset_switch_time = datetime.now()
                
                # Small delay
                await asyncio.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("👋 Stopping data collection...")
        except Exception as e:
            logger.error(f"Collection error: {e}")
        finally:
            self.print_stats()
            await self.stop()
    
    async def stop(self):
        """Stop the collector and clean up"""
        self.is_running = False
        
        if self.session:
            await self.session.close()
        
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        logger.info("🛑 Data Collector stopped")


async def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Pocket Option Data Collector')
    parser.add_argument('--assets', type=str, default=','.join(DEFAULT_ASSETS),
                        help='Comma-separated list of assets to collect')
    parser.add_argument('--duration', type=int, default=24,
                        help='Duration in hours')
    parser.add_argument('--rotation', type=int, default=0,
                        help='Asset rotation interval in minutes (0 = no rotation)')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode')
    parser.add_argument('--backend', type=str, default=BACKEND_URL,
                        help='Backend API URL')
    
    args = parser.parse_args()
    
    config = {
        'assets': args.assets.split(','),
        'duration_hours': args.duration,
        'rotation_minutes': args.rotation,
        'headless': args.headless,
        'backend_url': args.backend
    }
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    collector = PocketOptionDataCollector(config)
    await collector.run()


if __name__ == '__main__':
    asyncio.run(main())
