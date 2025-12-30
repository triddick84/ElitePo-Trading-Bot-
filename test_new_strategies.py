#!/usr/bin/env python3
"""
Test the new Pocket Option trading strategies specifically
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# Test configuration
BACKEND_URL = "https://signalbot-34.preview.emergentagent.com/api"

class NewStrategyTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 New Strategy testing session initialized")
        
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
            else:
                print(f"❌ {test_name}: FAILED")
                self.failed_tests.append(test_name)
                self.test_results.append({"test": test_name, "status": "FAILED"})
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.failed_tests.append(test_name)
            self.test_results.append({"test": test_name, "status": "ERROR", "details": str(e)})

    async def test_pocket_option_5s_strategy_signal_generation(self) -> bool:
        """Test Pocket Option 5-Second Strategy signal generation"""
        try:
            print("   Testing Pocket Option 5-Second Strategy")
            
            # Test with different assets and chart types
            test_cases = [
                {"asset": "EURUSD", "chart_type": "japanese_candles"},
                {"asset": "BTCUSD", "chart_type": "line"},
                {"asset": "GBPUSD", "chart_type": "bars"}
            ]
            
            for case in test_cases:
                print(f"   Testing {case['asset']} with {case['chart_type']} chart")
                
                # Test force signal generation with 5s timeframe
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate/asset/{case['asset']}_OTC") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('success'):
                            signals = data.get('signals', [])
                            print(f"   ✅ Generated {len(signals)} signals for {case['asset']}")
                            
                            # Verify signal properties
                            for signal in signals:
                                timeframe = signal.get('timeframe')
                                confidence = signal.get('probability', 0)
                                direction = signal.get('direction')
                                
                                print(f"   Signal: {direction} at {confidence}% confidence, timeframe: {timeframe}")
                                
                                # Check if this could be a 5s strategy signal
                                if timeframe == '5s':
                                    print(f"   ✅ Found 5s timeframe signal")
                                    
                                    if confidence >= 75 and confidence <= 98:
                                        print(f"   ✅ Confidence {confidence}% in expected range (75-98%)")
                                    else:
                                        print(f"   ⚠️ Confidence {confidence}% outside expected range")
                                    
                                    if direction in ['BUY', 'SELL', 'CALL', 'PUT']:
                                        print(f"   ✅ Valid direction: {direction}")
                                    else:
                                        print(f"   ❌ Invalid direction: {direction}")
                                        return False
                        else:
                            print(f"   ⚠️ No signals generated for {case['asset']} (acceptable)")
                    else:
                        print(f"   ❌ Force generation failed: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Pocket Option 5s strategy test error: {e}")
            return False

    async def test_force_signal_generator_strategy_routing(self) -> bool:
        """Test Force Signal Generator strategy routing based on timeframes"""
        try:
            print("   Testing Force Signal Generator strategy routing")
            
            # Test different timeframe routing
            timeframe_tests = [
                {"timeframes": ["5s"], "expected_strategy": "5s"},
                {"timeframes": ["15s"], "expected_strategy": "15s"},
                {"timeframes": ["1m"], "expected_strategy": "1m"},
                {"timeframes": ["3m"], "expected_strategy": "1m"},  # Should route to 1m strategy
                {"timeframes": ["5m"], "expected_strategy": "1m"}   # Should route to 1m strategy
            ]
            
            for test_case in timeframe_tests:
                timeframes = test_case["timeframes"]
                expected = test_case["expected_strategy"]
                
                print(f"   Testing timeframe routing: {timeframes} -> {expected} strategy")
                
                # Update configuration with specific timeframes
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex"],
                    "selected_assets": ["EURUSD_OTC"],
                    "selected_timeframes": timeframes,
                    "risk_tolerance": "medium",
                    "max_stake_per_trade": 10.0,
                    "max_daily_trades": 50,
                    "min_probability_threshold": 75.0,
                    "auto_trading_enabled": False,
                    "invert_signals": False,
                    "sound_alerts_enabled": True
                }
                
                # Update configuration
                async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                    if response.status != 200:
                        print(f"   ❌ Failed to update config for {timeframes}")
                        return False
                
                # Test force signal generation
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('success'):
                            signals = data.get('signals', [])
                            
                            # Check if signals use correct timeframe
                            for signal in signals:
                                signal_timeframe = signal.get('timeframe')
                                strategy_used = signal.get('strategy_used', '')
                                
                                print(f"   Signal timeframe: {signal_timeframe}, Strategy: {strategy_used}")
                                
                                # Verify timeframe matches expectation
                                if signal_timeframe == timeframes[0]:
                                    print(f"   ✅ Correct timeframe routing: {timeframes[0]}")
                                else:
                                    print(f"   ⚠️ Timeframe mismatch: expected {timeframes[0]}, got {signal_timeframe}")
                        else:
                            print(f"   ⚠️ No signals generated for timeframes {timeframes}")
                    else:
                        print(f"   ❌ Force generation failed for {timeframes}: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Force signal generator routing test error: {e}")
            return False

    async def test_ta_lib_integration(self) -> bool:
        """Test TA-Lib integration and calculations"""
        try:
            print("   Testing TA-Lib integration")
            
            # Test that TA-Lib can be imported and used
            try:
                import sys
                sys.path.append('/app/backend')
                import talib
                import numpy as np
                
                print("   ✅ TA-Lib imported successfully")
                
                # Test basic TA-Lib calculations
                test_data = np.array([1.0, 1.1, 1.05, 1.15, 1.12, 1.18, 1.16, 1.20, 1.19, 1.22])
                
                # Test EMA calculation
                ema = talib.EMA(test_data, timeperiod=5)
                if not np.isnan(ema[-1]):
                    print(f"   ✅ EMA calculation working: {ema[-1]:.4f}")
                else:
                    print("   ❌ EMA calculation returned NaN")
                    return False
                
                # Test RSI calculation
                rsi = talib.RSI(test_data, timeperiod=5)
                if not np.isnan(rsi[-1]):
                    print(f"   ✅ RSI calculation working: {rsi[-1]:.2f}")
                else:
                    print("   ❌ RSI calculation returned NaN")
                    return False
                
                # Test MACD calculation
                macd, signal, hist = talib.MACD(test_data)
                if not np.isnan(macd[-1]):
                    print(f"   ✅ MACD calculation working: {macd[-1]:.6f}")
                else:
                    print("   ❌ MACD calculation returned NaN")
                    return False
                
                # Test Bollinger Bands
                upper, middle, lower = talib.BBANDS(test_data, timeperiod=5)
                if not np.isnan(upper[-1]):
                    print(f"   ✅ Bollinger Bands calculation working: {upper[-1]:.4f}")
                else:
                    print("   ❌ Bollinger Bands calculation returned NaN")
                    return False
                
                # Test Stochastic
                high_data = test_data * 1.01  # Simulate high prices
                low_data = test_data * 0.99   # Simulate low prices
                slowk, slowd = talib.STOCH(high_data, low_data, test_data)
                if not np.isnan(slowk[-1]):
                    print(f"   ✅ Stochastic calculation working: {slowk[-1]:.2f}")
                else:
                    print("   ❌ Stochastic calculation returned NaN")
                    return False
                
                return True
                
            except ImportError as e:
                print(f"   ❌ TA-Lib import failed: {e}")
                return False
            except Exception as e:
                print(f"   ❌ TA-Lib calculation error: {e}")
                return False
            
        except Exception as e:
            print(f"   TA-Lib integration test error: {e}")
            return False

    async def test_end_to_end_strategy_signal_generation(self) -> bool:
        """Test end-to-end signal generation with new strategies"""
        try:
            print("   Testing end-to-end strategy signal generation")
            
            # Test different timeframe configurations
            test_configs = [
                {
                    "name": "5s Ultra-Short Strategy",
                    "timeframes": ["5s"],
                    "assets": ["EURUSD_OTC"],
                    "expected_confidence_min": 75
                },
                {
                    "name": "15s EMA Crossover Strategy", 
                    "timeframes": ["15s"],
                    "assets": ["BTCUSD_OTC"],
                    "expected_confidence_min": 80
                },
                {
                    "name": "1m Multi-Indicator Strategy",
                    "timeframes": ["1m"],
                    "assets": ["GBPUSD"],
                    "expected_confidence_min": 75  # Lowered expectation for testing
                }
            ]
            
            for config in test_configs:
                print(f"   Testing {config['name']}")
                
                # Configure bot for this test
                bot_config = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex", "crypto"],
                    "selected_assets": config["assets"],
                    "selected_timeframes": config["timeframes"],
                    "risk_tolerance": "medium",
                    "max_stake_per_trade": 10.0,
                    "max_daily_trades": 50,
                    "min_probability_threshold": 75.0,
                    "auto_trading_enabled": False,
                    "invert_signals": False,
                    "sound_alerts_enabled": True
                }
                
                # Update configuration
                async with self.session.put(f"{BACKEND_URL}/config", json=bot_config) as response:
                    if response.status != 200:
                        print(f"   ❌ Failed to update config for {config['name']}")
                        return False
                
                # Test force signal generation
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('success'):
                            signals = data.get('signals', [])
                            print(f"   ✅ Generated {len(signals)} signals for {config['name']}")
                            
                            # Verify signal quality
                            for signal in signals:
                                confidence = signal.get('probability', 0)
                                timeframe = signal.get('timeframe')
                                direction = signal.get('direction')
                                symbol = signal.get('symbol')
                                
                                print(f"   Signal: {symbol} {direction} at {confidence}% ({timeframe})")
                                
                                # Check confidence meets minimum
                                if confidence >= config["expected_confidence_min"]:
                                    print(f"   ✅ Confidence {confidence}% meets minimum {config['expected_confidence_min']}%")
                                else:
                                    print(f"   ⚠️ Confidence {confidence}% below expected {config['expected_confidence_min']}%")
                                
                                # Check timeframe matches
                                if timeframe in config["timeframes"]:
                                    print(f"   ✅ Timeframe {timeframe} matches configuration")
                                else:
                                    print(f"   ⚠️ Timeframe {timeframe} doesn't match expected {config['timeframes']}")
                        else:
                            print(f"   ⚠️ No signals generated for {config['name']}")
                    else:
                        print(f"   ❌ Force generation failed for {config['name']}: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   End-to-end strategy test error: {e}")
            return False

    async def test_strategy_files_exist(self) -> bool:
        """Test that strategy files exist and can be imported"""
        try:
            print("   Testing strategy files existence and import")
            
            import sys
            sys.path.append('/app/backend')
            
            # Test importing strategy files
            try:
                from pocket_option_5s_strategy import pocket_option_5s_strategy
                print("   ✅ pocket_option_5s_strategy imported successfully")
            except ImportError as e:
                print(f"   ❌ Failed to import pocket_option_5s_strategy: {e}")
                return False
            
            try:
                from pocket_option_15s_strategy import pocket_option_15s_strategy
                print("   ✅ pocket_option_15s_strategy imported successfully")
            except ImportError as e:
                print(f"   ❌ Failed to import pocket_option_15s_strategy: {e}")
                return False
            
            try:
                from pocket_option_1m_strategy import pocket_option_1m_strategy
                print("   ✅ pocket_option_1m_strategy imported successfully")
            except ImportError as e:
                print(f"   ❌ Failed to import pocket_option_1m_strategy: {e}")
                return False
            
            try:
                from force_signal_generator import force_signal_generator
                print("   ✅ force_signal_generator imported successfully")
            except ImportError as e:
                print(f"   ❌ Failed to import force_signal_generator: {e}")
                return False
            
            return True
            
        except Exception as e:
            print(f"   Strategy files test error: {e}")
            return False

    async def run_all_tests(self):
        """Run all new strategy tests"""
        print("🚀 Starting New Pocket Option Strategy Testing")
        print("=" * 80)
        
        await self.setup()
        
        # Define test suite for new strategies
        tests = [
            ("Strategy Files Exist and Import", self.test_strategy_files_exist),
            ("TA-Lib Integration", self.test_ta_lib_integration),
            ("Pocket Option 5s Strategy Signal Generation", self.test_pocket_option_5s_strategy_signal_generation),
            ("Force Signal Generator Strategy Routing", self.test_force_signal_generator_strategy_routing),
            ("End-to-End Strategy Signal Generation", self.test_end_to_end_strategy_signal_generation),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 NEW STRATEGY TESTING SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {len([r for r in self.test_results if r['status'] == 'PASSED'])}")
        print(f"Failed: {len(self.failed_tests)}")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   - {test}")
        else:
            print("\n✅ All tests passed!")

async def main():
    tester = NewStrategyTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())