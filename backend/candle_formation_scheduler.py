"""
Candle Formation Scheduler Service
Automatically generates signals synchronized with Pocket Option candle formation times
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
import logging
from pocket_option_timing_sync import pocket_option_sync
from timezone_utils import get_chicago_time
from models import TradingSignal

logger = logging.getLogger(__name__)

class CandleFormationScheduler:
    """
    Scheduler that monitors Pocket Option candle formation times and triggers
    signal generation at precise moments for optimal entry timing
    """
    
    def __init__(self, trading_bot_service=None):
        self.trading_bot = trading_bot_service
        self.active_timeframes: Set[str] = set()
        self.scheduler_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.signal_callback = None
        
        # Configuration - OPTIMIZED FOR POCKET OPTION CANDLE SYNCHRONIZATION
        # These values ensure signals arrive exactly when needed for candle close entry
        self.latency_compensation_seconds = {
            '5s': 3.1,    # 3.1s early - perfect sync with Pocket Option (fine-tuned from 4.0s)
            '15s': 2.0,   # 2.0s early - signals arrive at 13s (optimal for 15s candles)
            '30s': 2.5,   # 2.5s early - signals arrive at 27.5s (optimal for 30s candles)
            '1m': 3.0,    # 3.0s early - signals arrive at 57s (optimal for 1m candles)
            '2m': 3.0,    # 3.0s early
            '3m': 3.0,    # 3.0s early
            '5m': 4.0,    # 4.0s early
            '10m': 4.0,   # 4.0s early
            '15m': 5.0,   # 5.0s early
            '30m': 6.0,   # 6.0s early
            '1h': 6.0     # 6.0s early
        }
        
        logger.info("🕐 Candle Formation Scheduler initialized")
    
    def set_signal_callback(self, callback):
        """Set callback function to call when signal should be generated"""
        self.signal_callback = callback
        logger.info("📞 Signal generation callback registered")
    
    async def start(self, timeframes: List[str], selected_assets: List[str]):
        """
        Start monitoring candle formations for specified timeframes
        
        Args:
            timeframes: List of timeframes to monitor (e.g., ['5s', '1m', '5m'])
            selected_assets: List of assets to generate signals for
        """
        try:
            if self.is_running:
                logger.warning("⚠️ Scheduler already running")
                return
            
            self.is_running = True
            self.active_timeframes = set(timeframes)
            
            logger.info(f"🚀 Starting Candle Formation Scheduler")
            logger.info(f"📊 Monitoring timeframes: {', '.join(timeframes)}")
            logger.info(f"💰 Selected assets: {', '.join(selected_assets[:5])}..." if len(selected_assets) > 5 else f"💰 Selected assets: {', '.join(selected_assets)}")
            
            # Start a scheduler task for each timeframe
            for timeframe in timeframes:
                if timeframe not in self.scheduler_tasks or self.scheduler_tasks[timeframe].done():
                    task = asyncio.create_task(
                        self._timeframe_monitor(timeframe, selected_assets)
                    )
                    self.scheduler_tasks[timeframe] = task
                    logger.info(f"✅ Started {timeframe} candle monitor")
            
            logger.info("🎯 Candle Formation Scheduler is now active")
            
        except Exception as e:
            logger.error(f"❌ Error starting scheduler: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop all candle formation monitoring"""
        try:
            logger.info("🛑 Stopping Candle Formation Scheduler...")
            
            self.is_running = False
            
            # Cancel all running tasks
            for timeframe, task in self.scheduler_tasks.items():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.info(f"✅ Stopped {timeframe} candle monitor")
            
            self.scheduler_tasks.clear()
            self.active_timeframes.clear()
            
            logger.info("✅ Candle Formation Scheduler stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping scheduler: {e}")
    
    async def _timeframe_monitor(self, timeframe: str, selected_assets: List[str]):
        """
        Monitor a specific timeframe and trigger signal generation at candle formation
        
        Args:
            timeframe: Timeframe to monitor (e.g., '5s', '1m')
            selected_assets: Assets to generate signals for
        """
        try:
            logger.info(f"🔍 {timeframe} monitor started")
            
            while self.is_running and timeframe in self.active_timeframes:
                try:
                    # Calculate next candle formation time
                    chicago_time = get_chicago_time()
                    next_candle_time = pocket_option_sync.get_next_candle_formation_time(
                        timeframe, 
                        market_type="regular",
                        apply_latency_compensation=False  # We'll handle compensation manually
                    )
                    
                    # Calculate wait time with latency compensation
                    latency_buffer = self.latency_compensation_seconds.get(timeframe, 2.0)
                    signal_generation_time = next_candle_time - timedelta(seconds=latency_buffer)
                    
                    wait_seconds = (signal_generation_time - chicago_time).total_seconds()
                    
                    if wait_seconds > 0:
                        logger.info(f"⏰ {timeframe}: Next candle in {wait_seconds:.2f}s, "
                                  f"signal generation in {wait_seconds:.2f}s "
                                  f"(Chicago: {chicago_time.strftime('%H:%M:%S')})")
                        
                        # Wait until signal generation time
                        await asyncio.sleep(wait_seconds)
                        
                        # Generate signals at candle formation
                        if self.is_running:
                            await self._generate_signals_for_candle_formation(
                                timeframe, selected_assets, next_candle_time
                            )
                    else:
                        # We're past the candle time, calculate next one
                        logger.warning(f"⚠️ {timeframe}: Missed candle formation by {abs(wait_seconds):.2f}s, "
                                     f"calculating next candle...")
                        await asyncio.sleep(0.1)  # Small delay before recalculating
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error in {timeframe} monitor: {e}")
                    await asyncio.sleep(5)  # Wait before retrying
            
            logger.info(f"✅ {timeframe} monitor stopped")
            
        except asyncio.CancelledError:
            logger.info(f"🛑 {timeframe} monitor cancelled")
        except Exception as e:
            logger.error(f"❌ Fatal error in {timeframe} monitor: {e}")
    
    async def _generate_signals_for_candle_formation(
        self, 
        timeframe: str, 
        selected_assets: List[str],
        candle_time: datetime
    ):
        """
        Generate signals for all selected assets at candle formation time
        
        Args:
            timeframe: The timeframe that just formed a new candle
            selected_assets: Assets to generate signals for
            candle_time: The exact candle formation time
        """
        try:
            chicago_time = get_chicago_time()
            timing_delta = (chicago_time - candle_time).total_seconds()
            
            logger.info(f"🎯 {timeframe} CANDLE FORMED - Generating signals for {len(selected_assets)} assets")
            logger.info(f"   📍 Chicago Time: {chicago_time.strftime('%H:%M:%S.%f')[:-3]}")
            logger.info(f"   🎯 Candle Time: {candle_time.strftime('%H:%M:%S.%f')[:-3]}")
            logger.info(f"   ⚡ Timing Delta: {timing_delta:.3f}s")
            
            if abs(timing_delta) > 5.0:
                logger.warning(f"   ⚠️ Timing drift detected: {timing_delta:.3f}s")
            
            # Call the signal generation callback if registered
            if self.signal_callback:
                await self.signal_callback(timeframe, selected_assets, candle_time)
            
            # Alternative: Generate signals through trading bot service
            elif self.trading_bot:
                signals_generated = 0
                
                for asset in selected_assets:
                    try:
                        # Generate signal for this asset at this candle formation
                        signal = await self.trading_bot._generate_signal_for_asset(
                            asset,
                            timeframe=timeframe,
                            candle_formation_time=candle_time
                        )
                        
                        if signal:
                            signals_generated += 1
                            logger.info(f"   ✅ {asset}: Signal generated ({signal.direction.value} {signal.probability}%)")
                    
                    except Exception as e:
                        logger.error(f"   ❌ {asset}: Signal generation failed - {e}")
                
                logger.info(f"🎉 {timeframe}: Generated {signals_generated}/{len(selected_assets)} signals")
            
            else:
                logger.warning("⚠️ No signal generation method available (no callback or trading_bot)")
            
        except Exception as e:
            logger.error(f"❌ Error generating signals for {timeframe} candle: {e}")
            import traceback
            traceback.print_exc()
    
    def get_status(self) -> Dict:
        """Get current scheduler status"""
        return {
            "is_running": self.is_running,
            "active_timeframes": list(self.active_timeframes),
            "monitored_timeframes_count": len(self.active_timeframes),
            "running_tasks": len([t for t in self.scheduler_tasks.values() if not t.done()]),
            "next_candle_times": self._get_next_candle_times()
        }
    
    def _get_next_candle_times(self) -> Dict[str, str]:
        """Calculate next candle formation times for all active timeframes"""
        next_times = {}
        chicago_time = get_chicago_time()
        
        for timeframe in self.active_timeframes:
            try:
                next_candle = pocket_option_sync.get_next_candle_formation_time(
                    timeframe,
                    market_type="regular",
                    apply_latency_compensation=False
                )
                seconds_until = (next_candle - chicago_time).total_seconds()
                next_times[timeframe] = {
                    "time": next_candle.strftime('%H:%M:%S'),
                    "seconds_until": round(seconds_until, 2)
                }
            except Exception as e:
                next_times[timeframe] = {"error": str(e)}
        
        return next_times
    
    async def add_timeframe(self, timeframe: str, selected_assets: List[str]):
        """Dynamically add a timeframe to monitor"""
        if timeframe in self.active_timeframes:
            logger.warning(f"⚠️ {timeframe} already being monitored")
            return
        
        self.active_timeframes.add(timeframe)
        
        if self.is_running:
            task = asyncio.create_task(
                self._timeframe_monitor(timeframe, selected_assets)
            )
            self.scheduler_tasks[timeframe] = task
            logger.info(f"✅ Added {timeframe} to monitoring")
    
    async def remove_timeframe(self, timeframe: str):
        """Dynamically remove a timeframe from monitoring"""
        if timeframe not in self.active_timeframes:
            logger.warning(f"⚠️ {timeframe} is not being monitored")
            return
        
        self.active_timeframes.discard(timeframe)
        
        if timeframe in self.scheduler_tasks:
            task = self.scheduler_tasks[timeframe]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.scheduler_tasks[timeframe]
            logger.info(f"✅ Removed {timeframe} from monitoring")


# Global instance
candle_scheduler = CandleFormationScheduler()
