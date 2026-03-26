#!/usr/bin/env python3
"""
Critical Fixes Testing for GPT Signal Bot
Tests the three critical fixes mentioned in the review request
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime, timezone

# Test configuration
BACKEND_URL = "https://signal-bot-staging.preview.emergentagent.com/api"

class CriticalFixesTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Critical fixes testing session initialized")
        
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

    async def test_real_account_mode_persistence(self) -> bool:
        """
        Test 1: Real Account Mode Persistence
        1. GET /api/config - Check initial trading_mode value
        2. PUT /api/config with trading_mode="live" (along with other required fields)
        3. GET /api/config - Verify trading_mode is now "live"
        4. Verify the value persists in database
        """
        try:
            print("   🔍 Test 1: Real Account Mode Persistence")
            
            # Step 1: Get initial configuration
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    initial_config = await response.json()
                    initial_mode = initial_config.get('trading_mode')
                    print(f"   📊 Initial trading mode: {initial_mode}")
                else:
                    print(f"   ❌ Failed to get initial config: {response.status}")
                    return False
            
            # Step 2: Update configuration with trading_mode="live"
            live_config = {
                "trading_mode": "live",
                "selected_expirations": ["5s", "1m"],
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "sound_alerts_enabled": True,
                "popup_notifications": True,
                "invert_signals": False,
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"]
            }
            
            print("   🔄 Setting trading mode to 'live'...")
            async with self.session.put(f"{BACKEND_URL}/config", json=live_config) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Config update status: {data.get('status')}")
                else:
                    print(f"   ❌ Failed to update config: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
            
            # Step 3: Verify trading_mode is now "live"
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    updated_config = await response.json()
                    updated_mode = updated_config.get('trading_mode')
                    print(f"   📊 Updated trading mode: {updated_mode}")
                    
                    if updated_mode == "live":
                        print("   ✅ Trading mode successfully persisted as 'live'")
                        
                        # Verify other fields are also persisted
                        expirations = updated_config.get('selected_expirations', [])
                        threshold = updated_config.get('min_probability_threshold')
                        print(f"   📊 Selected expirations: {expirations}")
                        print(f"   📊 Probability threshold: {threshold}")
                        
                        return (updated_mode == "live" and 
                               "5s" in expirations and 
                               "1m" in expirations and
                               threshold == 85.0)
                    else:
                        print(f"   ❌ Trading mode not persisted correctly: expected 'live', got '{updated_mode}'")
                        return False
                else:
                    print(f"   ❌ Failed to verify config: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Real account mode persistence test error: {e}")
            return False

    async def test_expiration_time_changes_in_live_mode(self) -> bool:
        """
        Test 2: Expiration Time Changes in Real Account Mode
        1. Set trading_mode to "live" via PUT /api/config
        2. Change selected_expirations to ["15s", "30s"] while keeping trading_mode="live"
        3. Verify both values persist via GET /api/config
        """
        try:
            print("   🔍 Test 2: Expiration Time Changes in Real Account Mode")
            
            # Step 1: Set trading_mode to "live"
            live_config = {
                "trading_mode": "live",
                "selected_expirations": ["5s", "1m"],
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "sound_alerts_enabled": True,
                "popup_notifications": True,
                "invert_signals": False,
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"]
            }
            
            print("   🔄 Setting initial live mode configuration...")
            async with self.session.put(f"{BACKEND_URL}/config", json=live_config) as response:
                if response.status != 200:
                    print(f"   ❌ Failed to set initial live config: {response.status}")
                    return False
            
            # Step 2: Change selected_expirations while keeping trading_mode="live"
            updated_config = live_config.copy()
            updated_config["selected_expirations"] = ["15s", "30s"]
            
            print("   🔄 Changing expirations to ['15s', '30s'] while in live mode...")
            async with self.session.put(f"{BACKEND_URL}/config", json=updated_config) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Config update status: {data.get('status')}")
                else:
                    print(f"   ❌ Failed to update expirations: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
            
            # Step 3: Verify both trading_mode and selected_expirations persist
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    final_config = await response.json()
                    final_mode = final_config.get('trading_mode')
                    final_expirations = final_config.get('selected_expirations', [])
                    
                    print(f"   📊 Final trading mode: {final_mode}")
                    print(f"   📊 Final expirations: {final_expirations}")
                    
                    mode_correct = final_mode == "live"
                    expirations_correct = "15s" in final_expirations and "30s" in final_expirations
                    
                    if mode_correct and expirations_correct:
                        print("   ✅ Both trading mode and expirations persisted correctly in live mode")
                        return True
                    else:
                        print(f"   ❌ Persistence failed - Mode: {mode_correct}, Expirations: {expirations_correct}")
                        return False
                else:
                    print(f"   ❌ Failed to verify final config: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Expiration time changes in live mode test error: {e}")
            return False

    async def test_enhanced_auto_generate_endpoint(self) -> bool:
        """
        Test 3: Enhanced Auto-Generate Endpoint (used for continuous scanning)
        Test the POST /api/signals/auto-generate/enhanced endpoint with query parameters:
        - scan_all_assets=false
        - min_payout=80
        - min_accuracy=75
        - max_signals=5
        - continuous=false (single scan mode)
        """
        try:
            print("   🔍 Test 3: Enhanced Auto-Generate Endpoint")
            
            # Test parameters as specified in review request
            params = {
                "scan_all_assets": False,
                "min_payout": 80,
                "min_accuracy": 75,
                "max_signals": 5,
                "continuous": False
            }
            
            print(f"   📊 Testing with parameters: {params}")
            
            # Make request to enhanced auto-generate endpoint
            url = f"{BACKEND_URL}/signals/auto-generate/enhanced"
            query_string = "&".join([f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"
            
            print(f"   🔗 Request URL: {full_url}")
            
            async with self.session.post(full_url) as response:
                print(f"   📊 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check response structure
                    success = data.get('success')
                    message = data.get('message', '')
                    signals = data.get('signals', [])
                    assets_scanned = data.get('assets_scanned', 0)
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    print(f"   📊 Signals generated: {len(signals)}")
                    print(f"   📊 Assets scanned: {assets_scanned}")
                    
                    # Verify response structure
                    required_fields = ['success', 'message', 'signals']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify signal quality if any signals generated
                    if signals:
                        for i, signal in enumerate(signals[:3]):  # Check first 3 signals
                            probability = signal.get('probability', 0)
                            symbol = signal.get('symbol', 'Unknown')
                            direction = signal.get('direction', 'Unknown')
                            
                            print(f"   📊 Signal {i+1}: {symbol} {direction} ({probability}%)")
                            
                            # Verify signal meets minimum accuracy requirement
                            if probability < params['min_accuracy']:
                                print(f"   ❌ Signal {i+1} probability {probability}% below minimum {params['min_accuracy']}%")
                                return False
                    
                    # Verify max_signals limit is respected
                    if len(signals) > params['max_signals']:
                        print(f"   ❌ Too many signals generated: {len(signals)} > {params['max_signals']}")
                        return False
                    
                    print("   ✅ Enhanced auto-generate endpoint working correctly")
                    return True
                    
                elif response.status == 400:
                    # Check if it's an expected error (no assets selected, etc.)
                    error_text = await response.text()
                    print(f"   📊 Expected error (400): {error_text}")
                    
                    # This might be expected if no assets are configured
                    if "no assets" in error_text.lower():
                        print("   ✅ Expected error - no assets configured for scanning")
                        return True
                    else:
                        print(f"   ❌ Unexpected 400 error: {error_text}")
                        return False
                        
                else:
                    error_text = await response.text()
                    print(f"   ❌ Enhanced auto-generate failed: {response.status}")
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Enhanced auto-generate endpoint test error: {e}")
            return False

    async def test_health_check(self) -> bool:
        """Test basic health check endpoint"""
        try:
            async with self.session.get(f"{BACKEND_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Health status: {data.get('status')}")
                    print(f"   Bot running: {data.get('bot_running')}")
                    return data.get('status') == 'healthy'
                else:
                    print(f"   Health check failed with status: {response.status}")
                    return False
        except Exception as e:
            print(f"   Health check error: {e}")
            return False

    async def run_critical_tests(self):
        """Run the three critical tests from the review request"""
        print("🚀 Starting Critical Fixes Testing for GPT Signal Bot")
        print("=" * 80)
        print("Testing the three critical fixes mentioned in the review request:")
        print("1. Real Account Mode Persistence")
        print("2. Expiration Time Changes in Real Account Mode") 
        print("3. Enhanced Auto-Generate Endpoint")
        print("=" * 80)
        
        await self.setup()
        
        # Critical tests from review request
        tests = [
            ("Health Check", self.test_health_check),
            ("Real Account Mode Persistence", self.test_real_account_mode_persistence),
            ("Expiration Time Changes in Live Mode", self.test_expiration_time_changes_in_live_mode),
            ("Enhanced Auto-Generate Endpoint", self.test_enhanced_auto_generate_endpoint),
        ]
        
        # Run tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 CRITICAL FIXES TESTING SUMMARY")
        print("=" * 70)
        
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
            print(f"\n🎉 All critical tests passed!")
            
        return len(self.failed_tests) == 0

async def main():
    """Main test runner"""
    tester = CriticalFixesTester()
    success = await tester.run_critical_tests()
    
    if success:
        print("\n✅ All critical fixes are working correctly!")
        sys.exit(0)
    else:
        print("\n❌ Some critical fixes need attention!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())