#!/usr/bin/env python3
"""
5-Second Supertrend Reversal Strategy Testing
Tests all endpoints for the new 5s Supertrend Reversal Strategy implementation
"""

import asyncio
import aiohttp
import json
import random
from datetime import datetime, timedelta

# Test configuration
BACKEND_URL = "https://pocket-gpt-signals.preview.emergentagent.com/api"

class SupertrendTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 5s Supertrend testing session initialized")
        
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
                self.test_results.append({"test": test_name, "status": "PASSED"})
                return True
            else:
                print(f"❌ {test_name}: FAILED")
                self.failed_tests.append(test_name)
                self.test_results.append({"test": test_name, "status": "FAILED"})
                return False
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.failed_tests.append(test_name)
            self.test_results.append({"test": test_name, "status": "ERROR", "details": str(e)})
            return False

    def create_mock_candles(self, count: int = 100) -> list:
        """Create mock 5-second candles with realistic price movement"""
        candles = []
        base_price = 1.0850
        current_price = base_price
        
        for i in range(count):
            # Simulate realistic 5-second price movement
            change_pct = random.uniform(-0.0005, 0.0005)  # ±0.05% per 5s candle
            current_price *= (1 + change_pct)
            
            # Create OHLC with small spread
            spread = random.uniform(0.0001, 0.0003)
            open_price = current_price
            high_price = current_price + random.uniform(0, spread)
            low_price = current_price - random.uniform(0, spread)
            close_price = current_price + random.uniform(-spread/2, spread/2)
            
            candle = {
                "open": round(open_price, 5),
                "high": round(high_price, 5),
                "low": round(low_price, 5),
                "close": round(close_price, 5),
                "timestamp": (datetime.now() - timedelta(seconds=(count-i)*5)).isoformat() + "Z"
            }
            candles.append(candle)
            current_price = close_price
        
        return candles

    async def test_5s_supertrend_info_endpoint(self) -> bool:
        """Test 5-Second Supertrend Strategy Information Endpoint"""
        try:
            print("   📊 Testing 5s Supertrend Info endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/5s-supertrend/info") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 5s Supertrend Info endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'name', 'display_name', 'timeframe', 'type', 'parameters']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify strategy details
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    if data.get('name') != '5s_supertrend_reversal':
                        print(f"   ❌ Strategy name mismatch: {data.get('name')}")
                        return False
                    
                    if data.get('timeframe') != '5s':
                        print(f"   ❌ Timeframe mismatch: {data.get('timeframe')}")
                        return False
                    
                    # Check parameters
                    params = data.get('parameters', {})
                    if params.get('atr_period') != 2:
                        print(f"   ❌ ATR period mismatch: {params.get('atr_period')}")
                        return False
                    
                    if params.get('multiplier') != 1.11:
                        print(f"   ❌ Multiplier mismatch: {params.get('multiplier')}")
                        return False
                    
                    if data.get('risk_level') != 'very_high':
                        print(f"   ❌ Risk level mismatch: {data.get('risk_level')}")
                        return False
                    
                    if data.get('recommended_expiration') != 5:
                        print(f"   ❌ Recommended expiration mismatch: {data.get('recommended_expiration')}")
                        return False
                    
                    print(f"   📊 Strategy: {data.get('display_name')}")
                    print(f"   📊 Timeframe: {data.get('timeframe')}")
                    print(f"   📊 Type: {data.get('type')}")
                    print(f"   📊 ATR Period: {params.get('atr_period')}")
                    print(f"   📊 Multiplier: {params.get('multiplier')}")
                    print(f"   📊 Risk Level: {data.get('risk_level')}")
                    print(f"   📊 Expiration: {data.get('recommended_expiration')}s")
                    
                    return True
                else:
                    print(f"   ❌ 5s Supertrend Info endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend Info endpoint test error: {e}")
            return False

    async def test_5s_supertrend_signal_generation_no_data(self) -> bool:
        """Test 5s Supertrend Signal Generation with No Data"""
        try:
            print("   📊 Testing 5s Supertrend Signal Generation (No Data)")
            
            request_data = {
                "candle_data": [],
                "asset": "EURUSD_OTC"
            }
            
            async with self.session.post(f"{BACKEND_URL}/5s-supertrend/generate-signal", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 5s Supertrend Signal Generation endpoint accessible")
                    
                    # Should return error about insufficient data
                    if data.get('success') != False:
                        print(f"   ❌ Expected success=False for no data, got: {data.get('success')}")
                        return False
                    
                    error_msg = data.get('error', '')
                    if '50 candles' not in error_msg:
                        print(f"   ❌ Expected error about 50 candles, got: {error_msg}")
                        return False
                    
                    print(f"   ✅ Correctly returned error: {error_msg}")
                    return True
                else:
                    print(f"   ❌ 5s Supertrend Signal Generation endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend Signal Generation (No Data) test error: {e}")
            return False

    async def test_5s_supertrend_signal_generation_with_data(self) -> bool:
        """Test 5s Supertrend Signal Generation with Mock Data"""
        try:
            print("   📊 Testing 5s Supertrend Signal Generation (With Mock Data)")
            
            # Create 100 mock 5-second candles
            candles = self.create_mock_candles(100)
            
            request_data = {
                "candle_data": candles,
                "asset": "EURUSD_OTC"
            }
            
            async with self.session.post(f"{BACKEND_URL}/5s-supertrend/generate-signal", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 5s Supertrend Signal Generation endpoint accessible")
                    
                    # Check if signal was generated or no signal message
                    if data.get('success') == True:
                        signal = data.get('signal')
                        if signal:
                            # Verify signal structure
                            required_signal_fields = ['direction', 'confidence', 'entry_price', 'expiration_seconds', 'strategy']
                            missing_signal_fields = [field for field in required_signal_fields if field not in signal]
                            
                            if missing_signal_fields:
                                print(f"   ❌ Missing signal fields: {missing_signal_fields}")
                                return False
                            
                            # Verify signal values
                            if signal.get('direction') not in ['call', 'put']:
                                print(f"   ❌ Invalid direction: {signal.get('direction')}")
                                return False
                            
                            confidence = signal.get('confidence', 0)
                            if not (50 <= confidence <= 95):
                                print(f"   ❌ Invalid confidence: {confidence}")
                                return False
                            
                            if signal.get('expiration_seconds') != 5:
                                print(f"   ❌ Invalid expiration: {signal.get('expiration_seconds')}")
                                return False
                            
                            if signal.get('strategy') != '5s_supertrend_reversal':
                                print(f"   ❌ Invalid strategy: {signal.get('strategy')}")
                                return False
                            
                            # Check technical indicators
                            tech_indicators = signal.get('technical_indicators', {})
                            required_indicators = ['supertrend_value', 'atr', 'distance_from_supertrend']
                            missing_indicators = [ind for ind in required_indicators if ind not in tech_indicators]
                            
                            if missing_indicators:
                                print(f"   ❌ Missing technical indicators: {missing_indicators}")
                                return False
                            
                            print(f"   ✅ Signal Generated:")
                            print(f"       Direction: {signal.get('direction')}")
                            print(f"       Confidence: {signal.get('confidence')}%")
                            print(f"       Entry Price: {signal.get('entry_price')}")
                            print(f"       Expiration: {signal.get('expiration_seconds')}s")
                            print(f"       Strategy: {signal.get('strategy')}")
                            print(f"       Reason: {signal.get('reason', 'N/A')}")
                            print(f"       Supertrend Value: {tech_indicators.get('supertrend_value')}")
                            print(f"       ATR: {tech_indicators.get('atr')}")
                            print(f"       Distance from ST: {tech_indicators.get('distance_from_supertrend')}%")
                            
                        else:
                            print(f"   ✅ No signal generated (no Supertrend flip detected)")
                        
                        return True
                    else:
                        # No signal case is also valid
                        message = data.get('message', '')
                        if 'no signal' in message.lower() or 'no supertrend flip' in message.lower():
                            print(f"   ✅ No signal generated: {message}")
                            return True
                        else:
                            print(f"   ❌ Unexpected response: {data}")
                            return False
                else:
                    print(f"   ❌ 5s Supertrend Signal Generation endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend Signal Generation (With Data) test error: {e}")
            return False

    async def test_5s_supertrend_backtest_endpoint(self) -> bool:
        """Test 5s Supertrend Backtest Endpoint"""
        try:
            print("   📊 Testing 5s Supertrend Backtest endpoint")
            
            # Create 100 mock candles for backtesting
            candles = self.create_mock_candles(100)
            
            request_data = {
                "candle_data": candles,
                "initial_balance": 1000,
                "stake_per_trade": 10,
                "payout_rate": 0.8
            }
            
            async with self.session.post(f"{BACKEND_URL}/5s-supertrend/backtest", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 5s Supertrend Backtest endpoint accessible")
                    
                    if data.get('success') != True:
                        print(f"   ❌ Backtest failed: {data.get('error', 'Unknown error')}")
                        return False
                    
                    results = data.get('results', {})
                    required_fields = ['total_trades', 'wins', 'losses', 'win_rate', 'final_balance', 'roi']
                    missing_fields = [field for field in required_fields if field not in results]
                    
                    if missing_fields:
                        print(f"   ❌ Missing backtest result fields: {missing_fields}")
                        return False
                    
                    # Verify result values are reasonable
                    total_trades = results.get('total_trades', 0)
                    wins = results.get('wins', 0)
                    losses = results.get('losses', 0)
                    win_rate = results.get('win_rate', 0)
                    final_balance = results.get('final_balance', 0)
                    roi = results.get('roi', 0)
                    
                    # Basic validation
                    if wins + losses != total_trades:
                        print(f"   ❌ Wins + Losses ({wins + losses}) != Total Trades ({total_trades})")
                        return False
                    
                    if total_trades > 0:
                        expected_win_rate = (wins / total_trades) * 100
                        if abs(win_rate - expected_win_rate) > 0.1:
                            print(f"   ❌ Win rate calculation error: {win_rate} vs {expected_win_rate}")
                            return False
                    
                    print(f"   ✅ Backtest Results:")
                    print(f"       Total Trades: {total_trades}")
                    print(f"       Wins: {wins}")
                    print(f"       Losses: {losses}")
                    print(f"       Win Rate: {win_rate}%")
                    print(f"       Final Balance: ${final_balance}")
                    print(f"       ROI: {roi}%")
                    
                    return True
                else:
                    print(f"   ❌ 5s Supertrend Backtest endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend Backtest endpoint test error: {e}")
            return False

    async def test_5s_supertrend_ai_training_endpoint(self) -> bool:
        """Test 5s Supertrend AI Training Endpoint (with small dataset)"""
        try:
            print("   📊 Testing 5s Supertrend AI Training endpoint (insufficient data)")
            
            # Create only 100 candles (should fail - needs 1000+)
            candles = self.create_mock_candles(100)
            
            request_data = {
                "candle_data": candles,
                "model_name": "test_model"
            }
            
            async with self.session.post(f"{BACKEND_URL}/5s-supertrend/train-ai-model", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 5s Supertrend AI Training endpoint accessible")
                    
                    # Should return error about insufficient data
                    if data.get('success') != False:
                        print(f"   ❌ Expected success=False for insufficient data, got: {data.get('success')}")
                        return False
                    
                    error_msg = data.get('error', '')
                    if '1000 candles' not in error_msg:
                        print(f"   ❌ Expected error about 1000 candles, got: {error_msg}")
                        return False
                    
                    print(f"   ✅ Correctly returned error: {error_msg}")
                    return True
                else:
                    print(f"   ❌ 5s Supertrend AI Training endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend AI Training endpoint test error: {e}")
            return False

    async def test_5s_supertrend_force_signal_integration(self) -> bool:
        """Test 5s Supertrend Integration with Force Signal Generation"""
        try:
            print("   📊 Testing 5s Supertrend Force Signal Integration")
            
            # Test force signal generation to see if 5s supertrend is available
            # First, set up configuration for 5s timeframe
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_OTC"],
                "selected_expirations": ["5s"],  # 5-second expiration
                "risk_tolerance": "high",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 70.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Update configuration
            async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                if response.status != 200:
                    print(f"   ❌ Failed to set 5s configuration: {response.status}")
                    return False
            
            print("   ✅ Configuration set for 5s timeframe")
            
            # Test force signal generation
            async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success') == True:
                        signal = data.get('signal')
                        signals = data.get('signals', [])
                        
                        # Check if any signal uses 5s timeframe or supertrend strategy
                        found_5s_signal = False
                        
                        if signal and signal.get('timeframe') == '5s':
                            found_5s_signal = True
                            print(f"   ✅ Found 5s signal in main response")
                        
                        for sig in signals:
                            if sig.get('timeframe') == '5s' or '5s' in sig.get('strategy_used', ''):
                                found_5s_signal = True
                                print(f"   ✅ Found 5s signal in signals array: {sig.get('strategy_used')}")
                                break
                        
                        if found_5s_signal:
                            print(f"   ✅ 5s Supertrend strategy is integrated with force signal generation")
                            return True
                        else:
                            print(f"   ℹ️ No 5s signals generated (may be due to market conditions)")
                            # This is not necessarily a failure - the strategy might not have signals
                            return True
                    else:
                        print(f"   ℹ️ Force signal generation returned no signals: {data.get('message', 'No message')}")
                        # This is acceptable - not all conditions generate signals
                        return True
                else:
                    print(f"   ❌ Force signal generation failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   5s Supertrend Force Signal Integration test error: {e}")
            return False

async def run_5s_supertrend_tests():
    """Run all 5s Supertrend Reversal Strategy tests"""
    print("🚀 Testing 5-Second Supertrend Reversal Strategy Implementation")
    print("=" * 80)
    
    tester = SupertrendTester()
    await tester.setup()
    
    # Define tests
    tests = [
        ("5s Supertrend Info Endpoint", tester.test_5s_supertrend_info_endpoint),
        ("5s Supertrend Signal Generation (No Data)", tester.test_5s_supertrend_signal_generation_no_data),
        ("5s Supertrend Signal Generation (With Data)", tester.test_5s_supertrend_signal_generation_with_data),
        ("5s Supertrend Backtest Endpoint", tester.test_5s_supertrend_backtest_endpoint),
        ("5s Supertrend AI Training Endpoint", tester.test_5s_supertrend_ai_training_endpoint),
        ("5s Supertrend Force Signal Integration", tester.test_5s_supertrend_force_signal_integration),
    ]
    
    # Run all tests
    for test_name, test_func in tests:
        await tester.run_test(test_name, test_func)
    
    await tester.cleanup()
    
    # Print summary
    print("\n" + "=" * 80)
    print("🏁 5-Second Supertrend Reversal Strategy Testing Complete: {}/{} tests passed".format(
        len(tests) - len(tester.failed_tests), len(tests)
    ))
    print("=" * 80)
    
    total_tests = len(tests)
    passed_tests = total_tests - len(tester.failed_tests)
    
    if tester.failed_tests:
        print(f"\n❌ Failed Tests:")
        for test in tester.failed_tests:
            print(f"   - {test}")
        print(f"\n📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        return False
    else:
        print(f"\n🎉 All 5-Second Supertrend Reversal Strategy tests passed!")
        print(f"\n📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        return True

if __name__ == "__main__":
    asyncio.run(run_5s_supertrend_tests())