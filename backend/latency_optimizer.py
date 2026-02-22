"""
Latency Optimizer for Pocket Option Trading Signals

Critical for ultra-short timeframes (5s, 15s):
- Measures signal generation to execution lag
- Compensates for network/processing delays
- Optimizes entry timing for maximum accuracy
- Ensures signals align with Pocket Option candle formation

MODES:
- AUTO (default): Automatic latency correction based on measured delays
- MANUAL: User sets a fixed latency offset
- DISABLED: No latency correction applied
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Literal
from enum import Enum
import logging
import statistics

logger = logging.getLogger(__name__)


class LatencyCorrectionMode(Enum):
    """Latency correction mode options"""
    AUTO = "auto"           # Automatic correction (default, always enabled)
    MANUAL = "manual"       # User-defined fixed offset
    DISABLED = "disabled"   # No latency correction


class LatencyOptimizer:
    """
    Optimizes signal timing to account for latency between signal generation
    and trade execution on Pocket Option platform
    
    FEATURES:
    - Auto-correction: Learns from measured latencies and auto-adjusts
    - Manual mode: User can set a fixed offset for fine-tuning
    - Disabled mode: Turn off latency correction entirely
    - Per-timeframe optimization: Different buffers for 5s, 15s, 30s, 1m
    """
    
    def __init__(self):
        # Historical latency measurements (in milliseconds)
        self.latency_samples = []
        self.max_samples = 100  # Keep last 100 measurements
        
        # ============================================================
        # LATENCY CORRECTION MODE (Default: AUTO - always enabled)
        # ============================================================
        self.correction_mode = LatencyCorrectionMode.AUTO
        
        # Average latencies (milliseconds) - OPTIMIZED FOR POCKET OPTION CANDLE SYNC
        # Research shows signals must arrive 2-3 seconds before candle close for optimal execution
        self.avg_signal_generation = 500   # Fast signal generation with optimized strategies
        self.avg_network_latency = 120     # Network round-trip (measured average)
        self.avg_ui_delay = 600            # Frontend display + notification
        self.avg_pocket_option_processing = 200  # Pocket Option order processing
        self.avg_user_reaction_time = 1500 # User reads and clicks (conservative estimate)
        
        # Total estimated latency
        self.total_latency_ms = (
            self.avg_signal_generation +
            self.avg_network_latency +
            self.avg_ui_delay +
            self.avg_pocket_option_processing +
            self.avg_user_reaction_time
        )  # ~2920ms (~3 seconds) total - optimized for candle sync
        
        # ============================================================
        # AUTO-CORRECTION PARAMETERS
        # ============================================================
        # These are automatically updated based on trade outcome feedback
        self.auto_correction_offset = 0.0  # Learned offset from trade results
        self.auto_learning_rate = 0.1      # How fast to adapt (0.1 = 10% adjustment per feedback)
        self.auto_correction_history = []  # Track corrections for analysis
        
        # ============================================================
        # EARLY SIGNAL BUFFER (generate signal earlier to account for latency)
        # ============================================================
        # Positive value = signal arrives earlier to give user time to execute
        # These are the BASE values - auto-correction adds/subtracts from these
        self.early_signal_buffer_seconds = 3.0  # Base: 3 seconds early
        
        # Timeframe-specific buffers for optimal precision
        # Shorter timeframes need MORE lead time because timing is critical
        self.early_signal_buffer_5s = 2.5   # 2.5 seconds early for 5s (tight timing)
        self.early_signal_buffer_15s = 3.0  # 3 seconds early for 15s
        self.early_signal_buffer_30s = 3.5  # 3.5 seconds early for 30s
        self.early_signal_buffer_1m = 4.0   # 4 seconds early for 1m (more buffer)
        self.early_signal_buffer_2m = 5.0   # 5 seconds early for 2m+
        
        # ============================================================
        # MANUAL MODE OFFSET
        # ============================================================
        # User-adjustable latency offset (for manual fine-tuning)
        # Positive = signals arrive later, Negative = signals arrive earlier
        self.manual_offset_seconds = 0.0  # Default: no manual offset
        
        # ============================================================
        # ADAPTIVE TRACKING
        # ============================================================
        # Track signal accuracy by timeframe for auto-optimization
        self.timeframe_accuracy = {
            '5s': {'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0},
            '15s': {'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0},
            '30s': {'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0},
            '1m': {'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0},
            '2m': {'wins': 0, 'losses': 0, 'early_errors': 0, 'late_errors': 0},
        }
        
        logger.info(f"📊 Latency Optimizer initialized: {self.total_latency_ms}ms total latency")
        logger.info(f"🔧 Mode: {self.correction_mode.value.upper()} (auto-correction enabled by default)")
        logger.info(f"⏰ Base signal buffer: {self.early_signal_buffer_seconds:.2f}s")
    
    # ============================================================
    # MODE MANAGEMENT
    # ============================================================
    
    def set_mode(self, mode: str) -> Dict:
        """
        Set latency correction mode
        
        Args:
            mode: 'auto', 'manual', or 'disabled'
        
        Returns:
            Status dict with new mode and settings
        """
        mode_lower = mode.lower().strip()
        
        if mode_lower == 'auto':
            self.correction_mode = LatencyCorrectionMode.AUTO
            logger.info("🔧 Latency correction mode: AUTO (auto-correction enabled)")
        elif mode_lower == 'manual':
            self.correction_mode = LatencyCorrectionMode.MANUAL
            logger.info(f"🔧 Latency correction mode: MANUAL (offset: {self.manual_offset_seconds:.2f}s)")
        elif mode_lower in ['disabled', 'off', 'none']:
            self.correction_mode = LatencyCorrectionMode.DISABLED
            logger.info("🔧 Latency correction mode: DISABLED")
        else:
            logger.warning(f"⚠️ Invalid mode '{mode}', keeping current: {self.correction_mode.value}")
            return {
                'success': False,
                'error': f"Invalid mode: {mode}. Use 'auto', 'manual', or 'disabled'",
                'current_mode': self.correction_mode.value
            }
        
        return {
            'success': True,
            'mode': self.correction_mode.value,
            'auto_correction_offset': self.auto_correction_offset,
            'manual_offset': self.manual_offset_seconds,
            'effective_buffer_5s': self.get_effective_buffer('5s')
        }
    
    def set_manual_offset(self, offset_seconds: float) -> Dict:
        """
        Set manual latency offset (for MANUAL mode)
        
        Args:
            offset_seconds: Offset in seconds (-10 to +10)
                - Positive: signals arrive later (wait longer)
                - Negative: signals arrive earlier (more lead time)
        
        Returns:
            Status dict
        """
        # Clamp to reasonable range
        self.manual_offset_seconds = max(-10.0, min(10.0, offset_seconds))
        
        # Auto-switch to manual mode if setting an offset
        if self.correction_mode != LatencyCorrectionMode.MANUAL:
            self.correction_mode = LatencyCorrectionMode.MANUAL
            logger.info("🔧 Automatically switched to MANUAL mode")
        
        logger.info(f"🎛️ Manual latency offset set to {self.manual_offset_seconds:.2f}s")
        
        return {
            'success': True,
            'mode': 'manual',
            'manual_offset_seconds': self.manual_offset_seconds,
            'effective_buffer_5s': self.get_effective_buffer('5s'),
            'effective_buffer_15s': self.get_effective_buffer('15s'),
            'effective_buffer_1m': self.get_effective_buffer('1m')
        }
    
    # ============================================================
    # AUTO-CORRECTION LEARNING
    # ============================================================
    
    def record_trade_timing_feedback(self, timeframe: str, was_early: bool, was_late: bool, was_win: bool):
        """
        Record feedback about trade timing to improve auto-correction
        
        Called after a trade result is known:
        - was_early: Signal arrived too early (price moved away before execution)
        - was_late: Signal arrived too late (missed optimal entry)
        - was_win: Trade was successful
        
        This feedback is used to adjust the auto_correction_offset
        """
        if self.correction_mode != LatencyCorrectionMode.AUTO:
            return  # Only learn in AUTO mode
        
        if timeframe not in self.timeframe_accuracy:
            timeframe = '1m'  # Default fallback
        
        # Update accuracy tracking
        if was_win:
            self.timeframe_accuracy[timeframe]['wins'] += 1
        else:
            self.timeframe_accuracy[timeframe]['losses'] += 1
        
        if was_early:
            self.timeframe_accuracy[timeframe]['early_errors'] += 1
            # Signal was too early - reduce the buffer (arrive closer to candle)
            adjustment = -self.auto_learning_rate * 0.5  # Reduce by 0.05s per early error
            self.auto_correction_offset += adjustment
            logger.info(f"📉 Signal was EARLY - reducing buffer by {-adjustment:.2f}s")
            
        elif was_late:
            self.timeframe_accuracy[timeframe]['late_errors'] += 1
            # Signal was too late - increase the buffer (arrive earlier)
            adjustment = self.auto_learning_rate * 0.5  # Increase by 0.05s per late error
            self.auto_correction_offset += adjustment
            logger.info(f"📈 Signal was LATE - increasing buffer by {adjustment:.2f}s")
        
        # Clamp auto-correction to reasonable range (-3s to +3s)
        self.auto_correction_offset = max(-3.0, min(3.0, self.auto_correction_offset))
        
        # Track history
        self.auto_correction_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timeframe': timeframe,
            'was_early': was_early,
            'was_late': was_late,
            'was_win': was_win,
            'new_offset': self.auto_correction_offset
        })
        
        # Keep history limited
        if len(self.auto_correction_history) > 100:
            self.auto_correction_history = self.auto_correction_history[-100:]
        
        logger.info(f"🔧 Auto-correction offset: {self.auto_correction_offset:.2f}s | Wins: {self.timeframe_accuracy[timeframe]['wins']} | Losses: {self.timeframe_accuracy[timeframe]['losses']}")
    
    # ============================================================
    # EFFECTIVE BUFFER CALCULATION
    # ============================================================
    
    def get_effective_buffer(self, timeframe: str) -> float:
        """
        Get effective latency buffer based on current mode and settings
        
        Args:
            timeframe: Trading timeframe (5s, 15s, 30s, 1m, etc.)
            
        Returns:
            Effective buffer in seconds (positive = signal arrives early)
        """
        # If DISABLED, return 0 (no correction)
        if self.correction_mode == LatencyCorrectionMode.DISABLED:
            return 0.0
        
        # Get base buffer for timeframe
        if timeframe == '5s':
            base_buffer = self.early_signal_buffer_5s
        elif timeframe == '15s':
            base_buffer = self.early_signal_buffer_15s
        elif timeframe == '30s':
            base_buffer = self.early_signal_buffer_30s
        elif timeframe == '1m':
            base_buffer = self.early_signal_buffer_1m
        elif timeframe in ['2m', '3m', '5m']:
            base_buffer = self.early_signal_buffer_2m
        else:
            base_buffer = self.early_signal_buffer_seconds
        
        # Apply mode-specific offset
        if self.correction_mode == LatencyCorrectionMode.AUTO:
            # AUTO mode: apply learned auto-correction
            effective_buffer = base_buffer + self.auto_correction_offset
        elif self.correction_mode == LatencyCorrectionMode.MANUAL:
            # MANUAL mode: apply user-defined offset
            # Negative user offset = arrive earlier = increase buffer
            effective_buffer = base_buffer - self.manual_offset_seconds
        else:
            effective_buffer = base_buffer
        
        # Ensure reasonable range (0.5s to 10s)
        effective_buffer = max(0.5, min(10.0, effective_buffer))
        
        return effective_buffer
    
    def set_user_latency_offset(self, offset_seconds: float):
        """
        Legacy method - use set_manual_offset instead
        Kept for backward compatibility
        """
        return self.set_manual_offset(offset_seconds)
    
    def measure_latency(self, start_time: float, end_time: float, operation: str):
        """
        Measure and record latency for an operation
        
        Args:
            start_time: Operation start timestamp (seconds)
            end_time: Operation end timestamp (seconds)
            operation: Description of operation
        """
        latency_ms = (end_time - start_time) * 1000
        
        self.latency_samples.append({
            'timestamp': datetime.now(timezone.utc),
            'operation': operation,
            'latency_ms': latency_ms
        })
        
        # Keep only recent samples
        if len(self.latency_samples) > self.max_samples:
            self.latency_samples.pop(0)
        
        # Update averages
        self._update_latency_estimates()
        
        logger.debug(f"⏱️ {operation}: {latency_ms:.1f}ms")
    
    def _update_latency_estimates(self):
        """Update average latency estimates from samples"""
        if len(self.latency_samples) < 10:
            return  # Need at least 10 samples
        
        recent_samples = [s['latency_ms'] for s in self.latency_samples[-20:]]
        self.avg_signal_generation = statistics.mean(recent_samples)
        self.total_latency_ms = (
            self.avg_signal_generation +
            self.avg_network_latency +
            self.avg_ui_delay +
            self.avg_pocket_option_processing
        )
        self.early_signal_buffer_seconds = self.total_latency_ms / 1000.0
    
    def get_optimal_entry_time(self, candle_formation_time: datetime, timeframe: str) -> Dict:
        """
        Calculate optimal signal generation time accounting for latency
        
        Args:
            candle_formation_time: When the next candle will form
            timeframe: Trading timeframe (5s, 15s, 1m)
        
        Returns:
            Dictionary with timing information
        """
        # Get current time
        current_time = datetime.now(timezone.utc)
        
        # Calculate time to candle formation
        time_to_candle = (candle_formation_time - current_time).total_seconds()
        
        # For ultra-short timeframes, we need to be more aggressive
        if timeframe in ['5s', '15s', '30s']:
            # Generate signal 1-2 seconds before candle forms
            # This accounts for processing + network + execution time
            optimal_signal_time = candle_formation_time - timedelta(seconds=self.early_signal_buffer_seconds)
            
            # Minimum advance time (don't signal too late)
            min_advance_seconds = 1.5
            if time_to_candle < min_advance_seconds:
                logger.warning(f"⚠️ Too late to signal! Time to candle: {time_to_candle:.2f}s")
                return {
                    'should_signal_now': False,
                    'too_late': True,
                    'time_to_candle': time_to_candle
                }
            
            # Check if we should signal now
            time_to_optimal = (optimal_signal_time - current_time).total_seconds()
            should_signal_now = time_to_optimal <= 0
            
            return {
                'should_signal_now': should_signal_now,
                'too_late': False,
                'optimal_signal_time': optimal_signal_time,
                'candle_formation_time': candle_formation_time,
                'time_to_candle': time_to_candle,
                'time_to_optimal': max(0, time_to_optimal),
                'latency_buffer': self.early_signal_buffer_seconds,
                'estimated_execution_time': current_time + timedelta(seconds=self.total_latency_ms/1000)
            }
        
        else:
            # For longer timeframes (1m+), we can signal closer to candle formation
            optimal_signal_time = candle_formation_time - timedelta(seconds=2)
            time_to_optimal = (optimal_signal_time - current_time).total_seconds()
            
            return {
                'should_signal_now': time_to_optimal <= 0,
                'too_late': time_to_candle < 3,
                'optimal_signal_time': optimal_signal_time,
                'candle_formation_time': candle_formation_time,
                'time_to_candle': time_to_candle,
                'time_to_optimal': max(0, time_to_optimal),
                'latency_buffer': 2.0
            }
    
    def calculate_execution_timing(self, timeframe: str) -> Dict:
        """
        Calculate precise execution timing for a timeframe
        
        Returns timing guidance for optimal trade execution
        """
        from pocket_option_timing_sync import pocket_option_sync
        
        # Get next candle formation time
        next_candle = pocket_option_sync.get_next_candle_formation_time(timeframe)
        
        # Get optimal entry timing
        timing = self.get_optimal_entry_time(next_candle, timeframe)
        
        return timing
    
    def get_latency_stats(self) -> Dict:
        """Get current latency statistics"""
        if not self.latency_samples:
            return {
                'avg_latency_ms': self.total_latency_ms,
                'sample_count': 0
            }
        
        recent_latencies = [s['latency_ms'] for s in self.latency_samples[-20:]]
        
        return {
            'avg_latency_ms': statistics.mean(recent_latencies),
            'median_latency_ms': statistics.median(recent_latencies),
            'min_latency_ms': min(recent_latencies),
            'max_latency_ms': max(recent_latencies),
            'sample_count': len(self.latency_samples),
            'total_estimated_latency_ms': self.total_latency_ms,
            'early_signal_buffer_seconds': self.early_signal_buffer_seconds
        }

# Create singleton instance
latency_optimizer = LatencyOptimizer()
