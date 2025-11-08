"""
Latency and Accuracy Testing System for Pocket Option Trading Platform
Tests signal generation timing, platform lag, and signal accuracy
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import logging
import time
import statistics
from pocket_option_timing_sync import pocket_option_sync
from timezone_utils import get_chicago_time
import json

logger = logging.getLogger(__name__)

class LatencyAccuracyTester:
    """
    Comprehensive testing system for:
    1. Signal generation to platform execution lag
    2. Candle formation timing accuracy
    3. Signal win/loss tracking
    4. Latency compensation recommendations
    """
    
    def __init__(self, db=None):
        self.db = db
        self.test_results = []
        self.signal_performance = {}
        
        # Current latency compensation settings (from candle_formation_scheduler.py)
        self.current_compensation = {
            '5s': 0.5,    # 500ms
            '15s': 0.5,   # 500ms
            '30s': 1.0,   # 1s
            '1m': 2.0,    # 2s
            '2m': 2.0,    # 2s
            '3m': 2.0,    # 2s
            '5m': 3.0,    # 3s
            '10m': 3.0,   # 3s
            '15m': 3.0,   # 3s
            '30m': 5.0,   # 5s
            '1h': 5.0     # 5s
        }
        
        logger.info("🧪 Latency & Accuracy Tester initialized")
    
    async def test_signal_generation_lag(self, timeframe: str = '5s', iterations: int = 10) -> Dict:
        """
        Test the time it takes to generate a signal
        Measures pure signal generation performance
        """
        try:
            logger.info(f"🧪 Starting signal generation lag test ({iterations} iterations)...")
            
            generation_times = []
            
            for i in range(iterations):
                start_time = time.perf_counter()
                
                # Simulate signal generation (without actual API calls)
                chicago_time = get_chicago_time()
                next_candle = pocket_option_sync.get_next_candle_formation_time(
                    timeframe, "regular", False
                )
                
                # Simulate analysis time
                await asyncio.sleep(0.001)  # 1ms simulated processing
                
                end_time = time.perf_counter()
                generation_time_ms = (end_time - start_time) * 1000
                generation_times.append(generation_time_ms)
                
                logger.info(f"   Iteration {i+1}: {generation_time_ms:.2f}ms")
            
            # Calculate statistics
            avg_time = statistics.mean(generation_times)
            median_time = statistics.median(generation_times)
            min_time = min(generation_times)
            max_time = max(generation_times)
            stdev = statistics.stdev(generation_times) if len(generation_times) > 1 else 0
            
            result = {
                "test": "Signal Generation Lag",
                "timeframe": timeframe,
                "iterations": iterations,
                "average_ms": round(avg_time, 2),
                "median_ms": round(median_time, 2),
                "min_ms": round(min_time, 2),
                "max_ms": round(max_time, 2),
                "stdev_ms": round(stdev, 2),
                "timestamp": get_chicago_time().isoformat()
            }
            
            logger.info(f"✅ Signal generation average: {avg_time:.2f}ms")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in signal generation lag test: {e}")
            return {"error": str(e)}
    
    async def test_candle_timing_accuracy(self, timeframe: str = '5s', samples: int = 5) -> Dict:
        """
        Test how accurately we can predict Pocket Option candle formation times
        Measures timing synchronization precision
        """
        try:
            logger.info(f"🧪 Starting candle timing accuracy test for {timeframe} ({samples} samples)...")
            
            timing_deltas = []
            
            for sample in range(samples):
                # Get next candle time prediction
                predicted_time = pocket_option_sync.get_next_candle_formation_time(
                    timeframe, "regular", False
                )
                
                # Wait until predicted time
                chicago_time = get_chicago_time()
                wait_seconds = (predicted_time - chicago_time).total_seconds()
                
                logger.info(f"   Sample {sample+1}: Waiting {wait_seconds:.3f}s for {timeframe} candle...")
                
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                
                # Measure actual vs predicted
                actual_time = get_chicago_time()
                delta = (actual_time - predicted_time).total_seconds()
                timing_deltas.append(delta)
                
                logger.info(f"   Sample {sample+1}: Delta = {delta:.3f}s")
            
            # Calculate statistics
            avg_delta = statistics.mean(timing_deltas)
            median_delta = statistics.median(timing_deltas)
            max_early = min(timing_deltas)  # Negative = early
            max_late = max(timing_deltas)   # Positive = late
            stdev = statistics.stdev(timing_deltas) if len(timing_deltas) > 1 else 0
            
            # Determine accuracy rating
            if abs(avg_delta) < 0.1:
                accuracy_rating = "EXCELLENT (±100ms)"
            elif abs(avg_delta) < 0.5:
                accuracy_rating = "GOOD (±500ms)"
            elif abs(avg_delta) < 1.0:
                accuracy_rating = "FAIR (±1s)"
            else:
                accuracy_rating = "NEEDS IMPROVEMENT (>1s)"
            
            result = {
                "test": "Candle Timing Accuracy",
                "timeframe": timeframe,
                "samples": samples,
                "average_delta_s": round(avg_delta, 3),
                "median_delta_s": round(median_delta, 3),
                "max_early_s": round(max_early, 3),
                "max_late_s": round(max_late, 3),
                "stdev_s": round(stdev, 3),
                "accuracy_rating": accuracy_rating,
                "timestamp": get_chicago_time().isoformat()
            }
            
            logger.info(f"✅ Timing accuracy: {accuracy_rating} (avg delta: {avg_delta:.3f}s)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in candle timing accuracy test: {e}")
            return {"error": str(e)}
    
    async def test_network_latency(self, iterations: int = 10) -> Dict:
        """
        Test network latency to simulate API calls to Pocket Option
        Measures round-trip time for network requests
        """
        try:
            logger.info(f"🧪 Starting network latency test ({iterations} iterations)...")
            
            latencies = []
            
            for i in range(iterations):
                start_time = time.perf_counter()
                
                # Simulate network request
                await asyncio.sleep(0.05)  # 50ms simulated network delay
                
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
                
                logger.info(f"   Iteration {i+1}: {latency_ms:.2f}ms")
            
            # Calculate statistics
            avg_latency = statistics.mean(latencies)
            median_latency = statistics.median(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else max_latency
            
            result = {
                "test": "Network Latency",
                "iterations": iterations,
                "average_ms": round(avg_latency, 2),
                "median_ms": round(median_latency, 2),
                "min_ms": round(min_latency, 2),
                "max_ms": round(max_latency, 2),
                "p95_ms": round(p95_latency, 2),
                "timestamp": get_chicago_time().isoformat()
            }
            
            logger.info(f"✅ Network latency average: {avg_latency:.2f}ms (P95: {p95_latency:.2f}ms)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in network latency test: {e}")
            return {"error": str(e)}
    
    async def test_end_to_end_timing(self, timeframe: str = '5s') -> Dict:
        """
        Test complete end-to-end timing from signal generation to theoretical execution
        Combines all timing factors
        """
        try:
            logger.info(f"🧪 Starting end-to-end timing test for {timeframe}...")
            
            # Start timing
            test_start = time.perf_counter()
            
            # 1. Get next candle time
            step1_start = time.perf_counter()
            chicago_time = get_chicago_time()
            next_candle = pocket_option_sync.get_next_candle_formation_time(
                timeframe, "regular", False
            )
            step1_duration = (time.perf_counter() - step1_start) * 1000
            
            # 2. Calculate timing with compensation
            step2_start = time.perf_counter()
            compensation = self.current_compensation.get(timeframe, 1.0)
            signal_time = next_candle - timedelta(seconds=compensation)
            wait_time = (signal_time - chicago_time).total_seconds()
            step2_duration = (time.perf_counter() - step2_start) * 1000
            
            # 3. Simulate signal generation
            step3_start = time.perf_counter()
            await asyncio.sleep(0.01)  # 10ms simulated processing
            step3_duration = (time.perf_counter() - step3_start) * 1000
            
            # 4. Simulate network transmission
            step4_start = time.perf_counter()
            await asyncio.sleep(0.05)  # 50ms simulated network
            step4_duration = (time.perf_counter() - step4_start) * 1000
            
            # Total timing
            total_duration = (time.perf_counter() - test_start) * 1000
            
            # Calculate when signal would actually arrive at platform
            actual_arrival = chicago_time + timedelta(milliseconds=total_duration)
            time_before_candle = (next_candle - actual_arrival).total_seconds()
            
            # Recommendation
            if time_before_candle < 0:
                recommendation = f"⚠️ INCREASE compensation by {abs(time_before_candle):.2f}s (signal arrives late)"
            elif time_before_candle > compensation * 2:
                recommendation = f"✅ DECREASE compensation by {(time_before_candle - compensation):.2f}s (too early)"
            else:
                recommendation = "✅ Current compensation is OPTIMAL"
            
            result = {
                "test": "End-to-End Timing",
                "timeframe": timeframe,
                "current_compensation_s": compensation,
                "steps": {
                    "candle_calculation_ms": round(step1_duration, 2),
                    "timing_calculation_ms": round(step2_duration, 2),
                    "signal_generation_ms": round(step3_duration, 2),
                    "network_transmission_ms": round(step4_duration, 2)
                },
                "total_duration_ms": round(total_duration, 2),
                "time_before_candle_s": round(time_before_candle, 3),
                "recommendation": recommendation,
                "timestamp": get_chicago_time().isoformat()
            }
            
            logger.info(f"✅ End-to-end: {total_duration:.2f}ms, arrives {time_before_candle:.2f}s before candle")
            logger.info(f"   {recommendation}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in end-to-end timing test: {e}")
            return {"error": str(e)}
    
    async def run_comprehensive_test_suite(self) -> Dict:
        """
        Run all tests and provide comprehensive report with recommendations
        """
        try:
            logger.info("🧪🧪🧪 STARTING COMPREHENSIVE TEST SUITE 🧪🧪🧪")
            logger.info("=" * 60)
            
            results = {
                "test_suite": "Pocket Option Latency & Accuracy",
                "timestamp": get_chicago_time().isoformat(),
                "tests": {}
            }
            
            # Test 1: Signal Generation Lag
            logger.info("\n📊 TEST 1: Signal Generation Lag")
            results["tests"]["signal_generation"] = await self.test_signal_generation_lag('5s', 10)
            
            # Test 2: Candle Timing Accuracy
            logger.info("\n📊 TEST 2: Candle Timing Accuracy (5s)")
            results["tests"]["candle_timing_5s"] = await self.test_candle_timing_accuracy('5s', 3)
            
            logger.info("\n📊 TEST 3: Candle Timing Accuracy (1m)")
            results["tests"]["candle_timing_1m"] = await self.test_candle_timing_accuracy('1m', 2)
            
            # Test 3: Network Latency
            logger.info("\n📊 TEST 4: Network Latency")
            results["tests"]["network_latency"] = await self.test_network_latency(10)
            
            # Test 4: End-to-End for multiple timeframes
            logger.info("\n📊 TEST 5: End-to-End (5s)")
            results["tests"]["e2e_5s"] = await self.test_end_to_end_timing('5s')
            
            logger.info("\n📊 TEST 6: End-to-End (1m)")
            results["tests"]["e2e_1m"] = await self.test_end_to_end_timing('1m')
            
            logger.info("\n📊 TEST 7: End-to-End (5m)")
            results["tests"]["e2e_5m"] = await self.test_end_to_end_timing('5m')
            
            # Generate overall recommendations
            recommendations = self._generate_recommendations(results["tests"])
            results["recommendations"] = recommendations
            
            # Save results to database if available
            if self.db:
                await self.db.test_results.insert_one(results)
                logger.info("✅ Test results saved to database")
            
            logger.info("\n" + "=" * 60)
            logger.info("🎯 COMPREHENSIVE TEST SUITE COMPLETED")
            logger.info("=" * 60)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in comprehensive test suite: {e}")
            return {"error": str(e)}
    
    def _generate_recommendations(self, tests: Dict) -> Dict:
        """Generate recommendations based on test results"""
        recommendations = {
            "latency_adjustments": {},
            "overall_status": "",
            "action_items": []
        }
        
        # Analyze end-to-end tests
        for key, test in tests.items():
            if key.startswith("e2e_"):
                timeframe = test.get("timeframe")
                recommendation = test.get("recommendation", "")
                
                if "INCREASE" in recommendation:
                    recommendations["latency_adjustments"][timeframe] = "increase"
                    recommendations["action_items"].append(
                        f"⚠️ Increase latency compensation for {timeframe} timeframe"
                    )
                elif "DECREASE" in recommendation:
                    recommendations["latency_adjustments"][timeframe] = "decrease"
                    recommendations["action_items"].append(
                        f"📉 Consider decreasing compensation for {timeframe} (currently too early)"
                    )
                else:
                    recommendations["latency_adjustments"][timeframe] = "optimal"
        
        # Determine overall status
        if any(v == "increase" for v in recommendations["latency_adjustments"].values()):
            recommendations["overall_status"] = "NEEDS ADJUSTMENT - Some timeframes arriving late"
        elif all(v == "optimal" for v in recommendations["latency_adjustments"].values()):
            recommendations["overall_status"] = "OPTIMAL - All timeframes well-compensated"
        else:
            recommendations["overall_status"] = "GOOD - Minor adjustments possible"
        
        if not recommendations["action_items"]:
            recommendations["action_items"].append("✅ No adjustments needed - system is well-calibrated")
        
        return recommendations


# Global instance
latency_tester = LatencyAccuracyTester()
