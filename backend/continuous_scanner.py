"""
Continuous Market Scanner
Continuously scans markets until valid signals meeting criteria are found
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContinuousMarketScanner:
    """
    Continuously scans market assets until signals meeting criteria are found
    """
    
    def __init__(self, force_signal_generator, db):
        self.force_signal_generator = force_signal_generator
        self.db = db
        self.is_scanning = False
        self.scan_task = None
        
    async def start_continuous_scan(
        self,
        assets: List[str],
        min_accuracy: float = 75.0,
        max_signals: int = 5,
        scan_interval: int = 60,  # Seconds between scans
        max_scans: int = 100  # Maximum number of scan cycles
    ) -> Dict:
        """
        Start continuous scanning of assets
        
        Args:
            assets: List of asset symbols to scan
            min_accuracy: Minimum accuracy threshold
            max_signals: Maximum signals to collect
            scan_interval: Seconds to wait between scan cycles
            max_scans: Maximum number of scan cycles before stopping
        
        Returns:
            dict with scan status and collected signals
        """
        if self.is_scanning:
            return {
                "success": False,
                "message": "Scanner already running"
            }
        
        self.is_scanning = True
        collected_signals = []
        scan_count = 0
        
        logger.info(f"🔍 Starting continuous scan: {len(assets)} assets, min_accuracy={min_accuracy}%")
        
        try:
            while self.is_scanning and scan_count < max_scans and len(collected_signals) < max_signals:
                scan_count += 1
                logger.info(f"📊 Scan cycle {scan_count}/{max_scans}")
                
                # Scan all assets
                for asset_id in assets:
                    if not self.is_scanning:
                        break
                        
                    try:
                        # Parse asset
                        if '_' in asset_id:
                            symbol, market_type = asset_id.rsplit('_', 1)
                        else:
                            symbol, market_type = asset_id, 'regular'
                        
                        # Generate signal
                        signal_result = await self.force_signal_generator.generate_force_signal(
                            asset_symbol=symbol,
                            market_type=market_type,
                            selected_timeframe='1m',
                            selected_strategy='enhanced_rsi_bb_volume',
                            force_signal=False  # Only generate if conditions met
                        )
                        
                        # Check if signal meets criteria
                        if signal_result.get('signal'):
                            signal = signal_result['signal']
                            probability = signal.get('probability', 0)
                            
                            # Filter out emergency signals
                            is_emergency = signal.get('emergency_generation', False)
                            is_forced = signal.get('forced_generation', False)
                            
                            if not is_emergency and not is_forced and probability >= min_accuracy:
                                logger.info(f"✅ Valid signal found: {asset_id} ({probability}%)")
                                collected_signals.append(signal)
                                
                                # Stop if we have enough signals
                                if len(collected_signals) >= max_signals:
                                    logger.info(f"🎯 Collected {max_signals} signals, stopping scan")
                                    break
                        
                    except Exception as e:
                        logger.error(f"Error scanning {asset_id}: {e}")
                        continue
                
                # If we have enough signals, stop
                if len(collected_signals) >= max_signals:
                    break
                
                # Wait before next scan cycle (unless we're done)
                if self.is_scanning and scan_count < max_scans and len(collected_signals) < max_signals:
                    logger.info(f"⏳ Waiting {scan_interval}s before next scan cycle...")
                    await asyncio.sleep(scan_interval)
            
            self.is_scanning = False
            
            return {
                "success": True,
                "message": f"Scan completed: {len(collected_signals)} signals found in {scan_count} cycles",
                "signals": collected_signals,
                "scan_cycles": scan_count,
                "assets_scanned": len(assets)
            }
            
        except Exception as e:
            self.is_scanning = False
            logger.error(f"Error in continuous scan: {e}")
            return {
                "success": False,
                "message": f"Scan error: {str(e)}",
                "signals": collected_signals,
                "scan_cycles": scan_count
            }
    
    def stop_scan(self):
        """Stop the continuous scan"""
        if self.is_scanning:
            logger.info("🛑 Stopping continuous scan...")
            self.is_scanning = False
            return True
        return False
    
    def get_status(self) -> Dict:
        """Get current scanner status"""
        return {
            "is_scanning": self.is_scanning,
            "scan_active": self.is_scanning
        }
