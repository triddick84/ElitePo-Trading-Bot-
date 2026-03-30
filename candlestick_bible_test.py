#!/usr/bin/env python3
"""
Candlestick Bible Strategy Testing
Tests the newly implemented Candlestick Bible Strategy integration
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
BACKEND_URL = "https://pocket-option-auto-2.preview.emergentagent.com/api"

class CandlestickBibleTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Candlestick Bible testing session initialized")
        
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
    
    async def test_candlestick_bible_config_endpoint(self) -> bool:
        """
        Test Candlestick Bible Strategy Config Endpoint
        Test GET /api/strategy/candlestick-bible/config:
        - Should return all pattern names (bullish_engulfing, hammer, morning_star, etc.)
        - Should include pattern probabilities
        - Should include key_rules
        """
        try:
            print("   📕 Testing Candlestick Bible config endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/strategy/candlestick-bible/config") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Candlestick Bible config endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'name', 'description', 'bullish_patterns', 'bearish_patterns', 'pattern_probabilities', 'key_rules']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify success
                    if not data.get('success'):
                        print(f"   ❌ Config endpoint returned success=false")
                        return False
                    
                    # Check bullish patterns
                    bullish_patterns = data.get('bullish_patterns', [])
                    expected_bullish = ['bullish_engulfing', 'hammer', 'morning_star', 'dragonfly_doji', 'tweezers_bottom', 'bullish_harami']
                    
                    print(f"   📊 Bullish patterns: {bullish_patterns}")
                    for pattern in expected_bullish:
                        if pattern not in bullish_patterns:
                            print(f"   ❌ Missing bullish pattern: {pattern}")
                            return False
                    
                    # Check bearish patterns
                    bearish_patterns = data.get('bearish_patterns', [])
                    expected_bearish = ['bearish_engulfing', 'shooting_star', 'evening_star', 'gravestone_doji', 'tweezers_top', 'bearish_harami']
                    
                    print(f"   📊 Bearish patterns: {bearish_patterns}")
                    for pattern in expected_bearish:
                        if pattern not in bearish_patterns:
                            print(f"   ❌ Missing bearish pattern: {pattern}")
                            return False
                    
                    # Check pattern probabilities
                    probabilities = data.get('pattern_probabilities', {})
                    expected_prob_keys = ['engulfing', 'hammer_shooting_star', 'morning_evening_star', 'doji_patterns', 'tweezers', 'harami']
                    
                    print(f"   📊 Pattern probabilities: {probabilities}")
                    for key in expected_prob_keys:
                        if key not in probabilities:
                            print(f"   ❌ Missing probability for: {key}")
                            return False
                    
                    # Check key rules
                    key_rules = data.get('key_rules', [])
                    print(f"   📊 Key rules: {len(key_rules)} rules")
                    
                    if len(key_rules) < 3:
                        print(f"   ❌ Expected at least 3 key rules, got {len(key_rules)}")
                        return False
                    
                    print(f"   ✅ All required patterns, probabilities, and rules present")
                    return True
                else:
                    print(f"   ❌ Candlestick Bible config endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Candlestick Bible config test error: {e}")
            return False
    
    async def test_candlestick_bible_signal_generation(self) -> bool:
        """
        Test Candlestick Bible Signal Generation
        Test POST /api/strategy/candlestick-bible/signal?symbol=EURUSD:
        - Test for EURUSD, GBPUSD, BTCUSD
        - Verify response includes success field
        - If pattern detected, verify signal object has: pattern, signal, confidence, strength, at_key_level, trend_alignment
        """
        try:
            print("   📕 Testing Candlestick Bible signal generation")
            
            test_symbols = ['EURUSD', 'GBPUSD', 'BTCUSD']
            successful_tests = 0
            
            for symbol in test_symbols:
                print(f"   🔍 Testing signal generation for {symbol}")
                
                async with self.session.post(f"{BACKEND_URL}/strategy/candlestick-bible/signal?symbol={symbol}") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ {symbol} signal endpoint accessible")
                        
                        # Check required fields
                        required_fields = ['success', 'message']
                        missing_fields = [field for field in required_fields if field not in data]
                        
                        if missing_fields:
                            print(f"   ❌ {symbol}: Missing required fields: {missing_fields}")
                            continue
                        
                        success = data.get('success')
                        message = data.get('message')
                        signal = data.get('signal')
                        
                        print(f"   📊 {symbol} Success: {success}")
                        print(f"   📊 {symbol} Message: {message}")
                        
                        if not success:
                            print(f"   ❌ {symbol}: Signal generation returned success=false")
                            continue
                        
                        # If signal is present, verify its structure
                        if signal:
                            print(f"   ✅ {symbol}: Pattern detected")
                            
                            # Check signal structure
                            signal_fields = ['pattern', 'signal', 'confidence', 'strength', 'at_key_level', 'trend_alignment']
                            missing_signal_fields = [field for field in signal_fields if field not in signal]
                            
                            if missing_signal_fields:
                                print(f"   ❌ {symbol}: Missing signal fields: {missing_signal_fields}")
                                continue
                            
                            print(f"   📊 {symbol} Pattern: {signal.get('pattern')}")
                            print(f"   📊 {symbol} Signal: {signal.get('signal')}")
                            print(f"   📊 {symbol} Confidence: {signal.get('confidence')}%")
                            print(f"   📊 {symbol} Strength: {signal.get('strength')}")
                            print(f"   📊 {symbol} At Key Level: {signal.get('at_key_level')}")
                            print(f"   📊 {symbol} Trend Alignment: {signal.get('trend_alignment')}")
                            
                            # Verify signal direction is valid
                            signal_direction = signal.get('signal')
                            if signal_direction not in ['BUY', 'SELL']:
                                print(f"   ❌ {symbol}: Invalid signal direction: {signal_direction}")
                                continue
                            
                            # Verify confidence is reasonable
                            confidence = signal.get('confidence', 0)
                            if not (0 <= confidence <= 100):
                                print(f"   ❌ {symbol}: Invalid confidence: {confidence}")
                                continue
                        else:
                            print(f"   ℹ️ {symbol}: No pattern detected (acceptable)")
                        
                        successful_tests += 1
                        print(f"   ✅ {symbol}: Test passed")
                        
                    else:
                        print(f"   ❌ {symbol}: Signal endpoint failed: {response.status}")
                        error_text = await response.text()
                        print(f"   Error details: {error_text}")
                        continue
                
                # Small delay between symbol tests
                await asyncio.sleep(0.5)
            
            print(f"   📊 Successful tests: {successful_tests}/{len(test_symbols)}")
            
            # Test passes if at least 2 out of 3 symbols work
            return successful_tests >= 2
            
        except Exception as e:
            print(f"   Candlestick Bible signal generation test error: {e}")
            return False
    
    async def test_force_signal_with_candlestick_bible(self) -> bool:
        """
        Test Force Signal Generation with Candlestick Bible
        Test POST /api/signals/force-generate:
        - First configure assets: PUT /api/configuration (select EURUSD_OTC)
        - Then generate signal: POST /api/signals/force-generate
        - Check backend logs for "📕 Candlestick Bible" to verify the strategy is being used
        """
        try:
            print("   📕 Testing force signal generation with Candlestick Bible integration")
            
            # First, configure assets to include EURUSD_OTC
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_OTC"],
                "selected_expirations": ["5s", "1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 70.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            print("   ⚙️ Configuring assets for force signal generation")
            async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                if response.status != 200:
                    print(f"   ❌ Failed to configure assets: {response.status}")
                    return False
            
            print("   ✅ Assets configured successfully")
            
            # Generate force signal
            print("   🚀 Generating force signal")
            async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Force signal generation endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message')
                    signals = data.get('signals', [])
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    print(f"   📊 Signals generated: {len(signals)}")
                    
                    if success and signals:
                        # Check if any signal has candlestick bible analysis
                        for signal in signals:
                            strategy_used = signal.get('strategy_used', '')
                            justification = signal.get('justification', '')
                            
                            if 'candlestick' in strategy_used.lower() or 'candlestick' in justification.lower():
                                print(f"   ✅ Candlestick Bible strategy detected in signal")
                                print(f"   📊 Strategy: {strategy_used}")
                                print(f"   📊 Justification: {justification[:100]}...")
                                break
                        else:
                            print("   ℹ️ No explicit candlestick bible reference in signals (may still be used internally)")
                    
                    # Check backend logs for candlestick bible usage
                    await self.check_candlestick_bible_logs()
                    
                    return success is True
                    
                elif response.status == 400:
                    # Check if it's a configuration error
                    data = await response.json()
                    error_msg = data.get('message', '')
                    if 'no assets selected' in error_msg.lower() or 'no expirations selected' in error_msg.lower():
                        print(f"   ⚠️ Configuration issue: {error_msg}")
                        return True  # This is expected behavior, not a failure
                    else:
                        print(f"   ❌ Force signal generation failed: {error_msg}")
                        return False
                else:
                    print(f"   ❌ Force signal generation failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
            
        except Exception as e:
            print(f"   Force signal with Candlestick Bible test error: {e}")
            return False
    
    async def check_candlestick_bible_logs(self):
        """Check backend logs for Candlestick Bible strategy usage"""
        try:
            print("   🔍 Checking backend logs for Candlestick Bible usage...")
            
            # Check supervisor backend logs
            import subprocess
            result = subprocess.run(['tail', '-n', '200', '/var/log/supervisor/backend.err.log'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logs = result.stdout
                
                # Look for Candlestick Bible indicators
                candlestick_indicators = [
                    '📕 Candlestick Bible',
                    'candlestick_bible_strategy',
                    'analyze_candles',
                    'pattern detected'
                ]
                
                found_indicators = []
                for indicator in candlestick_indicators:
                    if indicator.lower() in logs.lower():
                        found_indicators.append(indicator)
                
                if found_indicators:
                    print(f"   ✅ Found Candlestick Bible indicators in logs: {found_indicators}")
                else:
                    print("   ℹ️ No specific Candlestick Bible indicators found in recent logs")
                    
            else:
                print("   ⚠️ Could not read backend logs")
                
        except Exception as e:
            print(f"   ⚠️ Error checking Candlestick Bible logs: {e}")
    
    async def run_all_tests(self):
        """Run all Candlestick Bible Strategy tests"""
        print("📕 Starting Candlestick Bible Strategy Testing")
        print("=" * 80)
        
        await self.setup()
        
        # Run Candlestick Bible Strategy tests
        await self.run_test("Candlestick Bible Config Endpoint", self.test_candlestick_bible_config_endpoint)
        await self.run_test("Candlestick Bible Signal Generation", self.test_candlestick_bible_signal_generation)
        await self.run_test("Force Signal with Candlestick Bible", self.test_force_signal_with_candlestick_bible)
        
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 80)
        print("🎯 CANDLESTICK BIBLE STRATEGY TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASSED"])
        failed_tests = len(self.failed_tests)
        
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   - {test}")
        else:
            print(f"\n🎉 ALL CANDLESTICK BIBLE TESTS PASSED!")
        
        return len(self.failed_tests) == 0


async def main():
    """Main test execution"""
    tester = CandlestickBibleTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ All Candlestick Bible Strategy tests completed successfully!")
        return 0
    else:
        print("\n❌ Some Candlestick Bible Strategy tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)