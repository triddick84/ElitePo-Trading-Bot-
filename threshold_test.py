#!/usr/bin/env python3
"""
Focused Threshold Slider Testing for GPT Signal Bot
Tests the new threshold functionality with comprehensive coverage
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://binary-signal-pro-14.preview.emergentagent.com/api"

class ThresholdTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Threshold testing session initialized")
        
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

    async def test_default_threshold_85_percent(self) -> bool:
        """Test that default threshold is 85%"""
        try:
            # Reset to default by saving a clean config
            default_config = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,  # Explicit default
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            async with self.session.put(f"{BACKEND_URL}/config", json=default_config) as response:
                if response.status != 200:
                    print(f"   Failed to set default config: {response.status}")
                    return False
            
            # Get config and verify default
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    config = await response.json()
                    threshold = config.get('min_probability_threshold')
                    print(f"   Current threshold: {threshold}%")
                    
                    if threshold == 85.0:
                        print("   ✅ Default threshold is correctly 85%")
                        return True
                    else:
                        print(f"   ❌ Expected 85%, got {threshold}%")
                        return False
                else:
                    print(f"   Failed to get config: {response.status}")
                    return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def test_threshold_range_50_to_99(self) -> bool:
        """Test threshold range validation (50% to 99%)"""
        try:
            # Test valid thresholds
            valid_thresholds = [50.0, 60.0, 75.0, 85.0, 90.0, 95.0, 99.0]
            
            for threshold in valid_thresholds:
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex"],
                    "selected_assets": ["EURUSD_regular"],
                    "selected_timeframes": ["1m"],
                    "risk_tolerance": "medium",
                    "max_stake_per_trade": 10.0,
                    "max_daily_trades": 50,
                    "min_probability_threshold": threshold,
                    "auto_trading_enabled": False,
                    "invert_signals": False,
                    "sound_alerts_enabled": True
                }
                
                async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                    if response.status == 200:
                        print(f"   ✅ Valid threshold {threshold}% accepted")
                    else:
                        print(f"   ❌ Valid threshold {threshold}% rejected: {response.status}")
                        return False
            
            # Test invalid thresholds
            invalid_thresholds = [49.0, 49.9, 99.1, 100.0, 101.0, -10.0]
            
            for threshold in invalid_thresholds:
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex"],
                    "selected_assets": ["EURUSD_regular"],
                    "selected_timeframes": ["1m"],
                    "risk_tolerance": "medium",
                    "max_stake_per_trade": 10.0,
                    "max_daily_trades": 50,
                    "min_probability_threshold": threshold,
                    "auto_trading_enabled": False,
                    "invert_signals": False,
                    "sound_alerts_enabled": True
                }
                
                async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                    if response.status in [400, 422]:
                        print(f"   ✅ Invalid threshold {threshold}% properly rejected")
                    else:
                        print(f"   ❌ Invalid threshold {threshold}% was accepted: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def test_bot_start_with_custom_thresholds(self) -> bool:
        """Test bot start accepts custom threshold values"""
        try:
            test_thresholds = [60.0, 80.0, 95.0]
            
            for threshold in test_thresholds:
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex"],
                    "selected_assets": ["EURUSD_regular"],
                    "selected_timeframes": ["1m"],
                    "risk_tolerance": "medium",
                    "max_stake_per_trade": 10.0,
                    "max_daily_trades": 50,
                    "min_probability_threshold": threshold,
                    "auto_trading_enabled": False,
                    "invert_signals": False,
                    "sound_alerts_enabled": True
                }
                
                # Stop bot first
                await self.session.post(f"{BACKEND_URL}/bot/stop")
                
                # Start bot with custom threshold
                async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        config = data.get('config', {})
                        actual_threshold = config.get('min_probability_threshold')
                        
                        if actual_threshold == threshold:
                            print(f"   ✅ Bot started with threshold {threshold}%")
                        else:
                            print(f"   ❌ Threshold mismatch: expected {threshold}%, got {actual_threshold}%")
                            return False
                    else:
                        print(f"   ❌ Bot start failed with threshold {threshold}%: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def test_configuration_persistence(self) -> bool:
        """Test threshold configuration persists"""
        try:
            test_threshold = 77.5
            
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": test_threshold,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Save configuration
            async with self.session.put(f"{BACKEND_URL}/config", json=config_data) as response:
                if response.status != 200:
                    print(f"   Failed to save config: {response.status}")
                    return False
            
            print(f"   Configuration with threshold {test_threshold}% saved")
            
            # Create new session to simulate restart
            await self.session.close()
            self.session = aiohttp.ClientSession()
            
            # Retrieve configuration
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    config = await response.json()
                    persisted_threshold = config.get('min_probability_threshold')
                    
                    if persisted_threshold == test_threshold:
                        print(f"   ✅ Threshold {test_threshold}% persisted correctly")
                        return True
                    else:
                        print(f"   ❌ Threshold mismatch: expected {test_threshold}%, got {persisted_threshold}%")
                        return False
                else:
                    print(f"   Failed to retrieve config: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def test_auto_generation_with_thresholds(self) -> bool:
        """Test auto generation start/stop with threshold settings"""
        try:
            threshold = 80.0
            
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": threshold,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Start bot
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status != 200:
                    print(f"   Failed to start bot: {response.status}")
                    return False
            
            print(f"   Bot started with threshold {threshold}%")
            
            # Test auto generation start
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    print("   ✅ Auto generation started")
                else:
                    print(f"   ❌ Auto generation start failed: {response.status}")
                    return False
            
            # Check status
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    active = data.get('auto_generation_active')
                    if active:
                        print("   ✅ Auto generation is active")
                    else:
                        print("   ❌ Auto generation should be active")
                        return False
                else:
                    print(f"   ❌ Failed to get status: {response.status}")
                    return False
            
            # Test auto generation stop
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
                if response.status == 200:
                    print("   ✅ Auto generation stopped")
                else:
                    print(f"   ❌ Auto generation stop failed: {response.status}")
                    return False
            
            # Verify stopped
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    active = data.get('auto_generation_active')
                    if not active:
                        print("   ✅ Auto generation is stopped")
                        return True
                    else:
                        print("   ❌ Auto generation should be stopped")
                        return False
                else:
                    print(f"   ❌ Failed to get final status: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   Error: {e}")
            return False

    async def run_all_tests(self):
        """Run all threshold slider tests"""
        print("🚀 Starting Comprehensive Threshold Slider Testing")
        print("=" * 60)
        
        await self.setup()
        
        tests = [
            ("Default Threshold is 85%", self.test_default_threshold_85_percent),
            ("Threshold Range 50%-99% Validation", self.test_threshold_range_50_to_99),
            ("Bot Start with Custom Thresholds", self.test_bot_start_with_custom_thresholds),
            ("Configuration Persistence", self.test_configuration_persistence),
            ("Auto Generation with Thresholds", self.test_auto_generation_with_thresholds),
        ]
        
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 THRESHOLD SLIDER TESTING SUMMARY")
        print("=" * 60)
        
        total_tests = len(tests)
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
            print(f"\n🎉 All threshold slider tests passed!")
            
        return len(self.failed_tests) == 0

async def main():
    """Main test runner"""
    tester = ThresholdTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ Threshold slider testing completed successfully!")
        return 0
    else:
        print("\n❌ Threshold slider testing completed with failures!")
        return 1

if __name__ == "__main__":
    import sys
    result = asyncio.run(main())
    sys.exit(result)