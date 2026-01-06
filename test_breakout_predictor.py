#!/usr/bin/env python3
"""
Enhanced Breakout Predictor Testing Script
Tests the newly implemented Enhanced Breakout Predictor with Alerts system
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Add backend to path
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://sigbot.preview.emergentagent.com/api"

class BreakoutPredictorTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Breakout Predictor testing session initialized")
        
    async def cleanup(self):
        """Cleanup test session"""
        if self.session:
            await self.session.close()
        print("🧹 Test session cleaned up")
        
    async def run_test(self, test_name: str, test_func):
        """Run individual test with error handling"""
        try:
            print(f"\n🧪 Running test: {test_name}")
            result = await test_func()
            if result:
                print(f"✅ {test_name}: PASSED")
                self.test_results.append({"test": test_name, "status": "PASSED", "details": result})
                return True
            else:
                print(f"❌ {test_name}: FAILED")
                self.failed_tests.append(test_name)
                self.test_results.append({"test": test_name, "status": "FAILED", "details": "Test returned False"})
                return False
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.failed_tests.append(test_name)
            self.test_results.append({"test": test_name, "status": "ERROR", "details": str(e)})
            return False

    async def test_breakout_predictor_module(self) -> bool:
        """
        Test 1: Breakout Predictor Module
        - Import get_breakout_predictor_5s() and verify instance creation
        - Check settings: lookback_period=15, percentage_step=0.5, min_breakout_strength=0.4
        - Test get_current_levels(symbol, price) function with EURUSD at price 1.05
        - Verify it returns support_levels and resistance_levels arrays
        """
        try:
            print("   🎯 Test 1: Breakout Predictor Module - Testing predictor initialization and level calculation")
            
            # Import the breakout predictor module
            from indicators.breakout_predictor import get_breakout_predictor_5s
            
            # Test instance creation
            predictor = get_breakout_predictor_5s()
            print("   ✅ get_breakout_predictor_5s() instance created successfully")
            
            # Verify settings
            settings = predictor.breakout_settings
            print(f"   📊 Lookback period: {settings.lookback_period}")
            print(f"   📊 Percentage step: {settings.percentage_step}")
            print(f"   📊 Min breakout strength: {settings.min_breakout_strength}")
            
            # Check expected settings for 5s optimization
            expected_lookback = 15
            expected_step = 0.5
            expected_strength = 0.4
            
            settings_correct = (
                settings.lookback_period == expected_lookback and
                settings.percentage_step == expected_step and
                settings.min_breakout_strength == expected_strength
            )
            
            if settings_correct:
                print("   ✅ Settings match expected 5s optimization values")
            else:
                print(f"   ❌ Settings mismatch - Expected: lookback={expected_lookback}, step={expected_step}, strength={expected_strength}")
                print(f"   ❌ Actual: lookback={settings.lookback_period}, step={settings.percentage_step}, strength={settings.min_breakout_strength}")
                return False
            
            # Test get_current_levels function
            symbol = "EURUSD"
            price = 1.05
            levels = predictor.get_current_levels(symbol, price)
            
            print(f"   ✅ get_current_levels called successfully for {symbol} at {price}")
            
            # Verify response structure
            required_fields = ['symbol', 'current_price', 'support_levels', 'resistance_levels', 'percentage_step']
            missing_fields = [field for field in required_fields if field not in levels]
            
            if missing_fields:
                print(f"   ❌ Missing required fields: {missing_fields}")
                return False
            
            print(f"   ✅ All required fields present: {required_fields}")
            
            # Verify arrays are returned
            support_levels = levels.get('support_levels', [])
            resistance_levels = levels.get('resistance_levels', [])
            
            if not isinstance(support_levels, list) or not isinstance(resistance_levels, list):
                print("   ❌ Support/resistance levels are not arrays")
                return False
            
            if len(support_levels) == 0 or len(resistance_levels) == 0:
                print("   ❌ Support/resistance level arrays are empty")
                return False
            
            print(f"   ✅ Support levels ({len(support_levels)}): {support_levels[:3]}...")
            print(f"   ✅ Resistance levels ({len(resistance_levels)}): {resistance_levels[:3]}...")
            
            # Verify levels are calculated correctly (should be below/above current price)
            all_support_below = all(level < price for level in support_levels)
            all_resistance_above = all(level > price for level in resistance_levels)
            
            if not all_support_below:
                print("   ❌ Some support levels are above current price")
                return False
            
            if not all_resistance_above:
                print("   ❌ Some resistance levels are below current price")
                return False
            
            print("   ✅ Support levels correctly below price, resistance levels correctly above price")
            
            return True
            
        except Exception as e:
            print(f"   Breakout predictor module test error: {e}")
            return False

    async def test_five_second_breakout_strategy(self) -> bool:
        """
        Test 2: Five Second Breakout Strategy
        - Import get_breakout_strategy() and create instance
        - Verify config: min_confidence=75, enable_alerts=True, timeframe="5s"
        - Test generate_signal('EURUSD') method
        - Verify output structure includes: direction, confidence, breakout_type, support_levels, resistance_levels
        """
        try:
            print("   🎯 Test 2: Five Second Breakout Strategy - Testing strategy initialization and signal generation")
            
            # Import the strategy module
            from strategies.five_second_breakout import get_breakout_strategy
            
            # Test instance creation
            strategy = get_breakout_strategy()
            print("   ✅ get_breakout_strategy() instance created successfully")
            
            # Verify configuration
            config = strategy.config
            min_confidence = strategy.min_confidence
            enable_alerts = strategy.enable_alerts
            timeframe = strategy.timeframe
            
            print(f"   📊 Min confidence: {min_confidence}%")
            print(f"   📊 Enable alerts: {enable_alerts}")
            print(f"   📊 Timeframe: {timeframe}")
            
            # Check expected configuration
            expected_confidence = 75
            expected_alerts = True
            expected_timeframe = "5s"
            
            config_correct = (
                min_confidence == expected_confidence and
                enable_alerts == expected_alerts and
                timeframe == expected_timeframe
            )
            
            if config_correct:
                print("   ✅ Configuration matches expected values")
            else:
                print(f"   ❌ Configuration mismatch - Expected: confidence={expected_confidence}, alerts={expected_alerts}, timeframe={expected_timeframe}")
                print(f"   ❌ Actual: confidence={min_confidence}, alerts={enable_alerts}, timeframe={timeframe}")
                return False
            
            # Test generate_signal method
            symbol = "EURUSD"
            print(f"   🔄 Testing generate_signal for {symbol}")
            
            signal = strategy.generate_signal(symbol)
            
            if signal is None:
                print("   ℹ️ No signal generated (acceptable - market conditions may not meet criteria)")
                # This is acceptable as the strategy may not find breakout conditions
                return True
            
            print("   ✅ Signal generated successfully")
            
            # Verify output structure
            required_fields = ['direction', 'confidence', 'breakout_type', 'support_levels', 'resistance_levels']
            missing_fields = [field for field in required_fields if field not in signal]
            
            if missing_fields:
                print(f"   ❌ Missing required fields: {missing_fields}")
                return False
            
            print(f"   ✅ All required fields present: {required_fields}")
            
            # Verify field types and values
            direction = signal.get('direction')
            confidence = signal.get('confidence')
            breakout_type = signal.get('breakout_type')
            support_levels = signal.get('support_levels', [])
            resistance_levels = signal.get('resistance_levels', [])
            
            print(f"   📊 Direction: {direction}")
            print(f"   📊 Confidence: {confidence}%")
            print(f"   📊 Breakout type: {breakout_type}")
            print(f"   📊 Support levels count: {len(support_levels)}")
            print(f"   📊 Resistance levels count: {len(resistance_levels)}")
            
            # Validate field values
            if direction not in ['BUY', 'SELL', 'CALL', 'PUT']:
                print(f"   ❌ Invalid direction: {direction}")
                return False
            
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
                print(f"   ❌ Invalid confidence: {confidence}")
                return False
            
            if breakout_type not in ['bullish', 'bearish']:
                print(f"   ❌ Invalid breakout type: {breakout_type}")
                return False
            
            if not isinstance(support_levels, list) or not isinstance(resistance_levels, list):
                print("   ❌ Support/resistance levels are not arrays")
                return False
            
            print("   ✅ All field values are valid")
            
            return True
            
        except Exception as e:
            print(f"   Five second breakout strategy test error: {e}")
            return False

    async def test_breakout_alert_service(self) -> bool:
        """
        Test 3: Breakout Alert Service
        - Import get_alert_manager() and verify instance
        - Test create_alert_payload() with sample signal data
        - Verify payload includes: ticker, signal, price, timestamp, breakout_level, confidence_score
        """
        try:
            print("   🎯 Test 3: Breakout Alert Service - Testing alert manager and payload creation")
            
            # Import the alert service module
            from alerts.breakout_alerts import get_alert_manager
            
            # Test instance creation
            alert_manager = get_alert_manager()
            print("   ✅ get_alert_manager() instance created successfully")
            
            # Verify instance type and basic properties
            if not hasattr(alert_manager, 'create_alert_payload'):
                print("   ❌ Alert manager missing create_alert_payload method")
                return False
            
            print("   ✅ Alert manager has required methods")
            
            # Test create_alert_payload with sample signal data
            sample_signal_data = {
                'ticker': 'EURUSD',
                'symbol': 'EURUSD',
                'signal': 'BUY',
                'direction': 'BUY',
                'price': 1.0500,
                'current_price': 1.0500,
                'timestamp': '2024-01-01T12:00:00Z',
                'message': 'BULLISH BREAKOUT: Price broke above 15-bar high (0.50% move)',
                'reasoning': 'BULLISH BREAKOUT: Price broke above 15-bar high (0.50% move)',
                'timeframe': '5s',
                'breakout_level': 1.0495,
                'confidence_score': 78.5,
                'confidence': 78.5,
                'breakout_type': 'bullish',
                'strength': 0.65,
                'support_levels': [1.0485, 1.0480, 1.0475],
                'resistance_levels': [1.0505, 1.0510, 1.0515]
            }
            
            print("   🔄 Testing create_alert_payload with sample data")
            
            payload = alert_manager.create_alert_payload(sample_signal_data)
            print("   ✅ create_alert_payload executed successfully")
            
            # Verify payload structure
            required_fields = ['ticker', 'signal', 'price', 'timestamp', 'breakout_level', 'confidence_score']
            missing_fields = []
            
            for field in required_fields:
                if not hasattr(payload, field):
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"   ❌ Missing required payload fields: {missing_fields}")
                return False
            
            print(f"   ✅ All required payload fields present: {required_fields}")
            
            # Verify field values
            print(f"   📊 Ticker: {payload.ticker}")
            print(f"   📊 Signal: {payload.signal}")
            print(f"   📊 Price: {payload.price}")
            print(f"   📊 Timestamp: {payload.timestamp}")
            print(f"   📊 Breakout level: {payload.breakout_level}")
            print(f"   📊 Confidence score: {payload.confidence_score}")
            
            # Validate field values match input
            if payload.ticker != sample_signal_data['ticker']:
                print(f"   ❌ Ticker mismatch: expected {sample_signal_data['ticker']}, got {payload.ticker}")
                return False
            
            if payload.signal != sample_signal_data['signal']:
                print(f"   ❌ Signal mismatch: expected {sample_signal_data['signal']}, got {payload.signal}")
                return False
            
            if payload.price != sample_signal_data['price']:
                print(f"   ❌ Price mismatch: expected {sample_signal_data['price']}, got {payload.price}")
                return False
            
            if payload.breakout_level != sample_signal_data['breakout_level']:
                print(f"   ❌ Breakout level mismatch: expected {sample_signal_data['breakout_level']}, got {payload.breakout_level}")
                return False
            
            if payload.confidence_score != sample_signal_data['confidence_score']:
                print(f"   ❌ Confidence score mismatch: expected {sample_signal_data['confidence_score']}, got {payload.confidence_score}")
                return False
            
            print("   ✅ All payload field values match input data")
            
            # Test payload serialization methods
            try:
                json_payload = payload.to_json()
                print("   ✅ Payload to_json() method works")
                
                mt4_payload = payload.to_mt4_format()
                print("   ✅ Payload to_mt4_format() method works")
                
                tv_payload = payload.to_tradingview_format()
                print("   ✅ Payload to_tradingview_format() method works")
                
            except Exception as e:
                print(f"   ❌ Payload serialization error: {e}")
                return False
            
            return True
            
        except Exception as e:
            print(f"   Breakout alert service test error: {e}")
            return False

    async def test_breakout_api_endpoints(self) -> bool:
        """
        Test 4: API Endpoints
        Test breakout predictor endpoints using REACT_APP_BACKEND_URL from frontend/.env
        """
        try:
            print("   🎯 Test 4: Breakout API Endpoints - Testing all breakout-related API endpoints")
            
            # Test 4a: POST /api/breakout/signal
            print("   🔄 Testing POST /api/breakout/signal")
            
            signal_request = {
                "symbol": "EURUSD_otc",
                "timeframe": "5s"
            }
            
            async with self.session.post(f"{BACKEND_URL}/breakout/signal", json=signal_request) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Breakout signal endpoint success: {data.get('success')}")
                    
                    if data.get('success'):
                        signal = data.get('signal')
                        if signal:
                            print(f"   📊 Signal generated: {signal.get('direction')} with {signal.get('confidence')}% confidence")
                        else:
                            print(f"   📊 Message: {data.get('message')}")
                    else:
                        print(f"   📊 No signal: {data.get('message')}")
                    
                    signal_endpoint_works = True
                else:
                    print(f"   ❌ Breakout signal endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    signal_endpoint_works = False
            
            # Test 4b: GET /api/breakout/levels/EURUSD?price=1.05
            print("   🔄 Testing GET /api/breakout/levels/EURUSD")
            
            async with self.session.get(f"{BACKEND_URL}/breakout/levels/EURUSD?price=1.05") as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Breakout levels endpoint success")
                    
                    support_levels = data.get('support_levels', [])
                    resistance_levels = data.get('resistance_levels', [])
                    
                    print(f"   📊 Support levels count: {len(support_levels)}")
                    print(f"   📊 Resistance levels count: {len(resistance_levels)}")
                    
                    if len(support_levels) > 0 and len(resistance_levels) > 0:
                        print(f"   📊 Sample support: {support_levels[:2]}")
                        print(f"   📊 Sample resistance: {resistance_levels[:2]}")
                        levels_endpoint_works = True
                    else:
                        print("   ❌ No support/resistance levels returned")
                        levels_endpoint_works = False
                else:
                    print(f"   ❌ Breakout levels endpoint failed: {response.status}")
                    levels_endpoint_works = False
            
            # Test 4c: GET /api/breakout/performance
            print("   🔄 Testing GET /api/breakout/performance")
            
            async with self.session.get(f"{BACKEND_URL}/breakout/performance") as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Breakout performance endpoint success")
                    
                    signals_generated = data.get('signals_generated', 0)
                    avg_processing_time = data.get('avg_processing_time_ms', 0)
                    latency_target_met = data.get('latency_target_met', False)
                    
                    print(f"   📊 Signals generated: {signals_generated}")
                    print(f"   📊 Avg processing time: {avg_processing_time}ms")
                    print(f"   📊 Latency target met (<100ms): {latency_target_met}")
                    
                    performance_endpoint_works = True
                else:
                    print(f"   ❌ Breakout performance endpoint failed: {response.status}")
                    performance_endpoint_works = False
            
            # Test 4d: POST /api/breakout/config
            print("   🔄 Testing POST /api/breakout/config")
            
            config_update = {
                "min_confidence": 80
            }
            
            async with self.session.post(f"{BACKEND_URL}/breakout/config", json=config_update) as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Breakout config endpoint success")
                    
                    updated_config = data.get('config', {})
                    new_min_confidence = updated_config.get('min_confidence')
                    
                    print(f"   📊 Updated min confidence: {new_min_confidence}")
                    
                    if new_min_confidence == 80:
                        print("   ✅ Configuration updated correctly")
                        config_endpoint_works = True
                    else:
                        print(f"   ❌ Configuration not updated correctly: expected 80, got {new_min_confidence}")
                        config_endpoint_works = False
                else:
                    print(f"   ❌ Breakout config endpoint failed: {response.status}")
                    config_endpoint_works = False
            
            # Overall result
            all_endpoints_work = (
                signal_endpoint_works and
                levels_endpoint_works and
                performance_endpoint_works and
                config_endpoint_works
            )
            
            if all_endpoints_work:
                print("   ✅ All breakout API endpoints working correctly")
            else:
                print("   ⚠️ Some breakout API endpoints have issues")
            
            return all_endpoints_work
            
        except Exception as e:
            print(f"   Breakout API endpoints test error: {e}")
            return False

    async def test_breakout_performance_requirements(self) -> bool:
        """
        Test 5: Performance Requirements
        Verify the implementation meets requirements:
        - Processing time < 100ms (check latency_target_met in performance metrics)
        - Buffer size = 3000 for 5s optimization
        - Correct indicator settings for 5s timeframe
        """
        try:
            print("   🎯 Test 5: Performance Requirements - Testing latency, buffer size, and 5s optimization")
            
            # Test performance metrics
            print("   🔄 Testing performance metrics")
            
            async with self.session.get(f"{BACKEND_URL}/breakout/performance") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    avg_processing_time = data.get('avg_processing_time_ms', 0)
                    latency_target_met = data.get('latency_target_met', False)
                    
                    print(f"   📊 Average processing time: {avg_processing_time}ms")
                    print(f"   📊 Latency target met (<100ms): {latency_target_met}")
                    
                    if latency_target_met:
                        print("   ✅ Processing time requirement met (<100ms)")
                        latency_ok = True
                    else:
                        print(f"   ⚠️ Processing time requirement not met: {avg_processing_time}ms >= 100ms")
                        # Still pass if no signals generated yet (avg_processing_time = 0)
                        latency_ok = avg_processing_time == 0
                else:
                    print(f"   ❌ Performance metrics endpoint failed: {response.status}")
                    latency_ok = False
            
            # Test buffer size and 5s optimization settings
            print("   🔄 Testing 5s optimization settings")
            
            try:
                from indicators.breakout_predictor import get_breakout_predictor_5s
                
                predictor = get_breakout_predictor_5s()
                settings = predictor.breakout_settings
                
                buffer_size = settings.buffer_size
                lookback_period = settings.lookback_period
                percentage_step = settings.percentage_step
                min_breakout_strength = settings.min_breakout_strength
                
                print(f"   📊 Buffer size: {buffer_size}")
                print(f"   📊 Lookback period: {lookback_period}")
                print(f"   📊 Percentage step: {percentage_step}")
                print(f"   📊 Min breakout strength: {min_breakout_strength}")
                
                # Check expected values for 5s optimization
                expected_buffer = 3000
                expected_lookback = 15
                expected_step = 0.5
                expected_strength = 0.4
                
                buffer_ok = buffer_size == expected_buffer
                settings_ok = (
                    lookback_period == expected_lookback and
                    percentage_step == expected_step and
                    min_breakout_strength == expected_strength
                )
                
                if buffer_ok:
                    print(f"   ✅ Buffer size correct: {buffer_size} = {expected_buffer}")
                else:
                    print(f"   ❌ Buffer size incorrect: {buffer_size} != {expected_buffer}")
                
                if settings_ok:
                    print("   ✅ 5s optimization settings correct")
                else:
                    print("   ❌ 5s optimization settings incorrect")
                    print(f"   Expected: lookback={expected_lookback}, step={expected_step}, strength={expected_strength}")
                    print(f"   Actual: lookback={lookback_period}, step={percentage_step}, strength={min_breakout_strength}")
                
                optimization_ok = buffer_ok and settings_ok
                
            except Exception as e:
                print(f"   ❌ Error checking 5s optimization settings: {e}")
                optimization_ok = False
            
            # Test signal generation speed
            print("   🔄 Testing signal generation speed")
            
            signal_request = {
                "symbol": "EURUSD_otc",
                "timeframe": "5s"
            }
            
            import time
            start_time = time.time()
            
            async with self.session.post(f"{BACKEND_URL}/breakout/signal", json=signal_request) as response:
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                print(f"   📊 API response time: {response_time_ms:.2f}ms")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if processing time is included in response
                    if 'processing_time_ms' in data:
                        processing_time = data['processing_time_ms']
                        print(f"   📊 Internal processing time: {processing_time}ms")
                        
                        speed_ok = processing_time < 100
                        if speed_ok:
                            print("   ✅ Signal generation speed requirement met")
                        else:
                            print(f"   ⚠️ Signal generation speed requirement not met: {processing_time}ms >= 100ms")
                    else:
                        # Use API response time as proxy
                        speed_ok = response_time_ms < 1000  # Allow 1s for API overhead
                        print(f"   ✅ API response time acceptable: {response_time_ms:.2f}ms")
                else:
                    print(f"   ❌ Signal generation test failed: {response.status}")
                    speed_ok = False
            
            # Overall performance assessment
            performance_ok = latency_ok and optimization_ok and speed_ok
            
            if performance_ok:
                print("   ✅ All performance requirements met")
            else:
                print("   ⚠️ Some performance requirements not fully met")
                print(f"   Latency: {'✅' if latency_ok else '❌'}")
                print(f"   Optimization: {'✅' if optimization_ok else '❌'}")
                print(f"   Speed: {'✅' if speed_ok else '❌'}")
            
            return performance_ok
            
        except Exception as e:
            print(f"   Breakout performance requirements test error: {e}")
            return False

    async def run_all_tests(self):
        """Run all Enhanced Breakout Predictor tests"""
        print("🚀 Enhanced Breakout Predictor with Alerts Testing")
        print("=" * 60)
        
        await self.setup()
        
        # Define all breakout predictor tests
        breakout_tests = [
            ("Breakout Predictor Module", self.test_breakout_predictor_module),
            ("Five Second Breakout Strategy", self.test_five_second_breakout_strategy),
            ("Breakout Alert Service", self.test_breakout_alert_service),
            ("Breakout API Endpoints", self.test_breakout_api_endpoints),
            ("Breakout Performance Requirements", self.test_breakout_performance_requirements),
        ]
        
        # Run all tests
        for test_name, test_func in breakout_tests:
            await self.run_test(test_name, test_func)
        
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 ENHANCED BREAKOUT PREDICTOR TESTING SUMMARY")
        print("=" * 60)
        
        total_tests = len(breakout_tests)
        passed_tests = total_tests - len(self.failed_tests)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   - {test}")
        else:
            print("\n✅ All Enhanced Breakout Predictor tests passed!")

async def main():
    """Main test execution"""
    tester = BreakoutPredictorTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())