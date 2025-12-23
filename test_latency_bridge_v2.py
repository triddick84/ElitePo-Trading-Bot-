#!/usr/bin/env python3
"""
Test Enhanced Latency Slider and Bridge Script v2.0 Updates
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime, timezone

# Test configuration
BACKEND_URL = "https://tradingbot-dash-11.preview.emergentagent.com/api"

class LatencyBridgeV2Tester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Test session initialized")
        
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
    
    # ========== LATENCY SLIDER ENHANCEMENT TESTS ==========
    
    async def test_latency_settings_get(self) -> bool:
        """Test GET /api/latency/settings - Should return current latency offset"""
        try:
            print("   ⏱️ Testing latency settings GET endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/latency/settings") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Latency settings GET endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'latency_offset']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    latency_offset = data.get('latency_offset')
                    print(f"   📊 Current Latency Offset: {latency_offset}s")
                    
                    return True
                else:
                    print(f"   ❌ Latency settings GET failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Latency settings GET test error: {e}")
            return False
    
    async def test_latency_settings_extended_range(self) -> bool:
        """Test PUT /api/latency/settings with extended range (-30 to +30)"""
        try:
            print("   ⏱️ Testing latency settings extended range")
            
            # Test cases: [value, should_succeed, description]
            test_cases = [
                (15.0, True, "Within new extended range"),
                (-25.0, True, "Within new extended negative range"),
                (0, True, "Reset to default"),
                (30.0, True, "Maximum positive"),
                (-30.0, True, "Maximum negative"),
                (35.0, False, "Should fail - outside range"),
                (-35.0, False, "Should fail - outside range")
            ]
            
            all_tests_passed = True
            
            for latency_offset, should_succeed, description in test_cases:
                print(f"   Testing latency offset: {latency_offset}s ({description})")
                
                async with self.session.put(f"{BACKEND_URL}/latency/settings?latency_offset={latency_offset}") as response:
                    if should_succeed:
                        if response.status == 200:
                            data = await response.json()
                            print(f"   ✅ Latency offset {latency_offset}s accepted")
                            print(f"   📊 Response: {data.get('message')}")
                        else:
                            print(f"   ❌ Expected success but got status {response.status} for {latency_offset}s")
                            error_text = await response.text()
                            print(f"   Error details: {error_text}")
                            all_tests_passed = False
                    else:
                        if response.status == 400:
                            print(f"   ✅ Latency offset {latency_offset}s correctly rejected")
                        else:
                            print(f"   ❌ Expected 400 error but got status {response.status} for {latency_offset}s")
                            error_text = await response.text()
                            print(f"   Error details: {error_text}")
                            all_tests_passed = False
            
            return all_tests_passed
                    
        except Exception as e:
            print(f"   Latency settings extended range test error: {e}")
            return False
    
    # ========== BRIDGE SCRIPT V2.0 TESTS ==========
    
    async def test_bridge_script_v2_endpoint(self) -> bool:
        """Test GET /api/bridge/script - Should return enhanced v2.0 script"""
        try:
            print("   🌉 Testing bridge script v2.0 endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/script") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge script endpoint accessible")
                    
                    script = data.get('script', '')
                    version = data.get('version', '')
                    
                    print(f"   📊 Script Version: {version}")
                    print(f"   📊 Script Length: {len(script)} characters")
                    
                    # Check for v2.0 features in the script
                    v2_features = [
                        ('SSID extraction', ['ssid', 'localStorage']),
                        ('balance monitoring', ['balance']),
                        ('heartbeat', ['heartbeat']),
                        ('multiple domain support', ['pocketoption.com', 'po.market']),
                        ('WebSocket interception', ['WebSocket'])
                    ]
                    
                    features_found = []
                    for feature_name, keywords in v2_features:
                        if any(keyword in script for keyword in keywords):
                            features_found.append(feature_name)
                    
                    print(f"   📊 v2.0 Features Found: {len(features_found)}/{len(v2_features)}")
                    for feature in features_found:
                        print(f"   ✅ {feature}")
                    
                    # Test passes if script is returned and has v2.0 features
                    return len(script) > 1000 and len(features_found) >= 3
                else:
                    print(f"   ❌ Bridge script endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge script v2.0 test error: {e}")
            return False
    
    async def test_bridge_ssid_update_endpoint(self) -> bool:
        """Test POST /api/bridge/ssid-update"""
        try:
            print("   🔑 Testing bridge SSID update endpoint")
            
            test_data = {
                "ssid": "test_ssid_12345",
                "isDemo": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/bridge/ssid-update", json=test_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge SSID update endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message', '')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    
                    return success is True
                else:
                    print(f"   ❌ Bridge SSID update failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge SSID update test error: {e}")
            return False
    
    async def test_bridge_balance_update_endpoint(self) -> bool:
        """Test POST /api/bridge/balance-update"""
        try:
            print("   💰 Testing bridge balance update endpoint")
            
            test_data = {
                "balance": 1000.00,
                "isDemo": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/bridge/balance-update", json=test_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge balance update endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message', '')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    
                    return success is True
                else:
                    print(f"   ❌ Bridge balance update failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge balance update test error: {e}")
            return False
    
    async def test_bridge_disconnected_endpoint(self) -> bool:
        """Test POST /api/bridge/disconnected"""
        try:
            print("   🔌 Testing bridge disconnected endpoint")
            
            test_data = {
                "url": "test_url",
                "code": 1000
            }
            
            async with self.session.post(f"{BACKEND_URL}/bridge/disconnected", json=test_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge disconnected endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message', '')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    
                    return success is True
                else:
                    print(f"   ❌ Bridge disconnected failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge disconnected test error: {e}")
            return False
    
    async def test_bridge_status_endpoint(self) -> bool:
        """Test GET /api/bridge/status"""
        try:
            print("   📊 Testing bridge status endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge status endpoint accessible")
                    
                    success = data.get('success')
                    is_connected = data.get('is_connected')
                    last_message_time = data.get('last_message_time')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Is Connected: {is_connected}")
                    print(f"   📊 Last Message Time: {last_message_time}")
                    
                    # Check for additional status fields
                    if 'connection_status' in data:
                        conn_status = data['connection_status']
                        print(f"   📊 Active Connections: {conn_status.get('active_connections', 0)}")
                        print(f"   📊 SSID Present: {conn_status.get('ssid_present', False)}")
                    
                    return success is True
                else:
                    print(f"   ❌ Bridge status failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge status test error: {e}")
            return False
    
    async def test_auto_trade_status_verification(self) -> bool:
        """Test GET /api/auto-trade/status - Verify still working"""
        try:
            print("   🤖 Testing auto-trade status endpoint (verification)")
            
            async with self.session.get(f"{BACKEND_URL}/auto-trade/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto-trade status endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'is_running', 'is_connected', 'is_auto_trade_enabled']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    print(f"   📊 Is Running: {data.get('is_running')}")
                    print(f"   📊 Is Connected: {data.get('is_connected')}")
                    print(f"   📊 Auto Trade Enabled: {data.get('is_auto_trade_enabled')}")
                    
                    return True
                else:
                    print(f"   ❌ Auto-trade status failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Auto-trade status test error: {e}")
            return False

    async def run_all_tests(self):
        """Run all latency and bridge v2.0 tests"""
        print("🚀 Testing Enhanced Latency Slider and Bridge Script v2.0 Updates")
        print("=" * 70)
        
        await self.setup()
        
        # Latency Slider Enhancement Tests
        latency_tests = [
            ("Latency Settings GET", self.test_latency_settings_get),
            ("Latency Settings Extended Range", self.test_latency_settings_extended_range),
        ]
        
        # Bridge Script v2.0 Tests
        bridge_v2_tests = [
            ("Bridge Script v2.0 Endpoint", self.test_bridge_script_v2_endpoint),
            ("Bridge SSID Update Endpoint", self.test_bridge_ssid_update_endpoint),
            ("Bridge Balance Update Endpoint", self.test_bridge_balance_update_endpoint),
            ("Bridge Disconnected Endpoint", self.test_bridge_disconnected_endpoint),
            ("Bridge Status Endpoint", self.test_bridge_status_endpoint),
        ]
        
        # Auto-Trade Status Verification
        verification_tests = [
            ("Auto-Trade Status Verification", self.test_auto_trade_status_verification),
        ]
        
        # Run Latency tests
        print("\n⏱️ RUNNING LATENCY SLIDER ENHANCEMENT TESTS")
        print("=" * 50)
        for test_name, test_func in latency_tests:
            await self.run_test(test_name, test_func)
        
        # Run Bridge v2.0 tests
        print("\n🌉 RUNNING BRIDGE SCRIPT V2.0 TESTS")
        print("=" * 40)
        for test_name, test_func in bridge_v2_tests:
            await self.run_test(test_name, test_func)
        
        # Run verification tests
        print("\n🔍 RUNNING VERIFICATION TESTS")
        print("=" * 30)
        for test_name, test_func in verification_tests:
            await self.run_test(test_name, test_func)
        
        await self.cleanup()
        
        # Print summary
        all_tests = latency_tests + bridge_v2_tests + verification_tests
        total_tests = len(all_tests)
        passed_tests = total_tests - len(self.failed_tests)
        
        print("\n" + "=" * 70)
        print("🏁 LATENCY & BRIDGE V2.0 TESTING SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {len(self.failed_tests)}")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   - {test}")
        else:
            print(f"\n✅ All tests passed!")
        
        print(f"\nSuccess Rate: {(passed_tests/total_tests)*100:.1f}%")

async def main():
    tester = LatencyBridgeV2Tester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())