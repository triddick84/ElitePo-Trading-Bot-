"""
Latency Optimizer for Pocket Option Trading Signals

Critical for ultra-short timeframes (5s, 15s):
- Measures signal generation to execution lag
- Compensates for network/processing delays
- Optimizes entry timing for maximum accuracy
- Ensures signals align with Pocket Option candle formation
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging
import statistics

logger = logging.getLogger(__name__)

class LatencyOptimizer:
    """
    Optimizes signal timing to account for latency between signal generation
    and trade execution on Pocket Option platform
    """
    
    def __init__(self):
        # Historical latency measurements (in milliseconds)
        self.latency_samples = []
        self.max_samples = 100  # Keep last 100 measurements
        
        # Average latencies (milliseconds) - OPTIMIZED FOR POCKET OPTION CANDLE SYNC
        # Research shows signals must arrive 2-3 seconds before candle close for optimal execution
        self.avg_signal_generation = 600   # Fast signal generation with research-backed strategies
        self.avg_network_latency = 150     # Network round-trip
        self.avg_ui_delay = 800            # Frontend display + notification
        self.avg_pocket_option_processing = 150  # Pocket Option order processing
        self.avg_user_reaction_time = 1300 # User reads and clicks quickly
        
        # Total estimated latency
        self.total_latency_ms = (
            self.avg_signal_generation +
            self.avg_network_latency +
            self.avg_ui_delay +
            self.avg_pocket_option_processing +
            self.avg_user_reaction_time
        )  # ~3000ms (3 seconds) total - optimized for candle sync
        
        # Early signal buffer (generate signal earlier to account for latency)
        self.early_signal_buffer_seconds = self.total_latency_ms / 1000.0  # 3.0 seconds
        
        # Timeframe-specific buffers for optimal precision  
        # For ultra-short timeframes: Adjusted buffers based on user requirements
        # 5s timeframe: +5 seconds latency adjustment for better timing
        self.early_signal_buffer_5s = -5.0  # -5 seconds for 5s (negative = arrive earlier by 5s)
        self.early_signal_buffer_15s = 0.0  # 0 seconds for 15s - signal at exact candle formation
        self.early_signal_buffer_30s = 0.0  # 0 seconds for 30s - signal at exact candle formation
        self.early_signal_buffer_1m = 0.0   # 0 seconds for 1m - signal at exact candle formation
        
        # User-adjustable latency offset (allows manual fine-tuning)
        # Positive = signals arrive later, Negative = signals arrive earlier
        self.user_latency_offset = 0.0  # Default: no offset
        
        logger.info(f"📊 Latency Optimizer initialized: {self.total_latency_ms}ms total latency")
        logger.info(f"⏰ Early signal buffer: {self.early_signal_buffer_seconds:.2f}s")
    
    def set_user_latency_offset(self, offset_seconds: float):
        """
        Set user-defined latency offset for manual timing adjustment
        
        Args:
            offset_seconds: Offset in seconds (-10 to +10)
                - Negative: signals arrive earlier
                - Positive: signals arrive later
                - 0: use automatic timing
        """
        self.user_latency_offset = max(-10.0, min(10.0, offset_seconds))
        logger.info(f"🎛️ User latency offset set to {self.user_latency_offset:.2f}s")
    
    def get_effective_buffer(self, timeframe: str) -> float:
        """
        Get effective latency buffer including user offset
        
        Args:
            timeframe: Trading timeframe (5s, 15s, 30s, 1m, etc.)
            
        Returns:
            Effective buffer in seconds (base buffer + user offset)
        """
        # Get base buffer for timeframe
        if timeframe == '5s':
            base_buffer = self.early_signal_buffer_5s
        elif timeframe == '15s':
            base_buffer = self.early_signal_buffer_15s
        elif timeframe == '30s':
            base_buffer = self.early_signal_buffer_30s
        elif timeframe == '1m':
            base_buffer = self.early_signal_buffer_1m
        else:
            base_buffer = self.early_signal_buffer_seconds
        
        # Apply user offset (negative offset = earlier signal = increase buffer)
        # (positive offset = later signal = decrease buffer)
        effective_buffer = base_buffer - self.user_latency_offset
        
        # Ensure non-negative
        return max(0.0, effective_buffer)
    
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
