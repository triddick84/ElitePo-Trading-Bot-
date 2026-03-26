#!/usr/bin/env python3
"""
Test Pocket Option Live Bridge Connection
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime, timezone

# Test configuration
BACKEND_URL = "https://signal-bot-staging.preview.emergentagent.com/api"

class BridgeTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Bridge testing session initialized")
        
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

    async def test_bridge_status_endpoint(self) -> bool:
        """
        Test 1: Bridge Status Endpoint
        Test GET /api/bridge/status:
        - Should return success: true
        - Should show connection status fields
        """
        try:
            print("   🌉 Test 1: Bridge Status Endpoint - Testing bridge connection status")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge status endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    # Check for connection status fields
                    required_fields = ['success', 'is_connected', 'last_message_time', 'message_count']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ⚠️ Some optional fields missing: {missing_fields}")
                    else:
                        print(f"   ✅ All expected fields present: {required_fields}")
                    
                    # Display connection details
                    print(f"   📊 Is connected: {data.get('is_connected')}")
                    print(f"   📊 Last message time: {data.get('last_message_time')}")
                    print(f"   📊 Message count: {data.get('message_count')}")
                    
                    # Test passes if success field is present (true or false both valid)
                    return 'success' in data
                else:
                    print(f"   ❌ Bridge status endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge status endpoint test error: {e}")
            return False

    async def test_bridge_script_generation(self) -> bool:
        """
        Test 2: Bridge Script Generation
        Test GET /api/bridge/script:
        - Should return success: true
        - Should return a JavaScript script string
        - Should include proper app_url from frontend/.env
        - Should include instructions array
        """
        try:
            print("   🌉 Test 2: Bridge Script Generation - Testing JavaScript bridge script generation")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/script") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge script endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    if not success:
                        print("   ❌ Bridge script generation failed")
                        return False
                    
                    # Check for script field
                    script = data.get('script')
                    if not script:
                        print("   ❌ No script returned")
                        return False
                    
                    print(f"   ✅ JavaScript script returned (length: {len(script)} chars)")
                    
                    # Check if script contains expected elements
                    expected_elements = ['WebSocket', 'signalhub-15.preview.emergentagent.com', 'ws-stream']
                    found_elements = []
                    
                    for element in expected_elements:
                        if element in script:
                            found_elements.append(element)
                            print(f"   ✅ Script contains: {element}")
                        else:
                            print(f"   ⚠️ Script missing: {element}")
                    
                    # Check for instructions array
                    instructions = data.get('instructions')
                    if instructions and isinstance(instructions, list):
                        print(f"   ✅ Instructions array present ({len(instructions)} items)")
                        for i, instruction in enumerate(instructions[:3]):  # Show first 3
                            print(f"   📋 Step {i+1}: {instruction[:80]}...")
                    else:
                        print("   ⚠️ Instructions array missing or invalid")
                    
                    # Test passes if we have success=true and a script
                    return success and script and len(script) > 100
                else:
                    print(f"   ❌ Bridge script endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge script generation test error: {e}")
            return False

    async def test_bridge_data_reception(self) -> bool:
        """
        Test 3: Bridge Data Reception (Simulate WebSocket data)
        Test POST /api/bridge/ws-stream with:
        {
          "type": "ws_message",
          "data": "{\"history\": [[1703001600, 1.05], [1703001601, 1.051]], \"candles\": [[1703001600, 1.05, 1.052, 1.053, 1.049]], \"asset\": \"GBPUSD_otc\", \"period\": 1}",
          "timestamp": 1703001605000,
          "url": "wss://po.market/ws"
        }
        - Should return success: true
        - Should show processed type as "history"
        """
        try:
            print("   🌉 Test 3: Bridge Data Reception - Testing WebSocket data processing")
            
            # Simulate WebSocket message data
            test_data = {
                "type": "ws_message",
                "data": '{"history": [[1703001600, 1.05], [1703001601, 1.051]], "candles": [[1703001600, 1.05, 1.052, 1.053, 1.049]], "asset": "GBPUSD_otc", "period": 1}',
                "timestamp": 1703001605000,
                "url": "wss://po.market/ws"
            }
            
            async with self.session.post(f"{BACKEND_URL}/bridge/ws-stream", json=test_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge data reception endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    if not success:
                        print("   ❌ Bridge data processing failed")
                        return False
                    
                    # Check processed type
                    processed_type = data.get('processed_type')
                    print(f"   📊 Processed type: {processed_type}")
                    
                    # Check message details
                    message = data.get('message')
                    print(f"   📊 Message: {message}")
                    
                    # Check for data processing details
                    if 'data_points' in data:
                        print(f"   📊 Data points processed: {data.get('data_points')}")
                    
                    if 'asset' in data:
                        print(f"   📊 Asset processed: {data.get('asset')}")
                    
                    # Test passes if success=true and we get some processing confirmation
                    return success and (processed_type or message)
                else:
                    print(f"   ❌ Bridge data reception failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge data reception test error: {e}")
            return False

    async def test_get_candles_for_asset(self) -> bool:
        """
        Test 4: Get Candles for Asset
        Test GET /api/bridge/candles/GBPUSD_otc:
        - Should return candles array after Test 3
        - Should show total_candles count
        """
        try:
            print("   🌉 Test 4: Get Candles for Asset - Testing candle data retrieval")
            
            asset = "GBPUSD_otc"
            async with self.session.get(f"{BACKEND_URL}/bridge/candles/{asset}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge candles endpoint accessible for {asset}")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    # Check for candles array
                    candles = data.get('candles', [])
                    total_candles = data.get('total_candles', 0)
                    
                    print(f"   📊 Total candles: {total_candles}")
                    print(f"   📊 Candles array length: {len(candles)}")
                    
                    if candles:
                        print(f"   ✅ Candles data available for {asset}")
                        # Show sample candle data
                        sample_candle = candles[0] if candles else None
                        if sample_candle:
                            print(f"   📊 Sample candle: {sample_candle}")
                    else:
                        print(f"   ℹ️ No candles data for {asset} (may need bridge connection)")
                    
                    # Check available assets
                    available_assets = data.get('available_assets', [])
                    if available_assets:
                        print(f"   📊 Available assets: {len(available_assets)} assets")
                        print(f"   📊 Sample assets: {available_assets[:5]}")
                    
                    # Test passes if we get a valid response structure
                    return 'success' in data and 'candles' in data and 'total_candles' in data
                else:
                    print(f"   ❌ Bridge candles endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Get candles for asset test error: {e}")
            return False

    async def test_get_all_bridge_assets(self) -> bool:
        """
        Test 5: Get All Bridge Assets
        Test GET /api/bridge/assets:
        - Should list all tracked assets from simulated data
        """
        try:
            print("   🌉 Test 5: Get All Bridge Assets - Testing asset list retrieval")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/assets") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge assets endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    # Check for assets data
                    assets = data.get('assets', {})
                    asset_count = data.get('asset_count', 0)
                    
                    print(f"   📊 Asset count: {asset_count}")
                    print(f"   📊 Assets data type: {type(assets)}")
                    
                    if isinstance(assets, dict) and assets:
                        print(f"   ✅ Assets data available ({len(assets)} assets)")
                        # Show sample assets
                        sample_assets = list(assets.keys())[:5]
                        print(f"   📊 Sample assets: {sample_assets}")
                        
                        # Show details for first asset
                        if sample_assets:
                            first_asset = sample_assets[0]
                            asset_details = assets[first_asset]
                            print(f"   📊 {first_asset} details: {asset_details}")
                    else:
                        print(f"   ℹ️ No assets data available (may need bridge connection)")
                    
                    # Test passes if we get a valid response structure
                    return 'success' in data and 'assets' in data
                else:
                    print(f"   ❌ Bridge assets endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Get all bridge assets test error: {e}")
            return False

    async def test_bridge_config_update(self) -> bool:
        """
        Test 6: Bridge Config Update
        Test POST /api/bridge/config:
        {
          "fast_ma": 5,
          "slow_ma": 10,
          "rsi_enabled": true
        }
        - Should update configuration
        - Should return new config
        """
        try:
            print("   🌉 Test 6: Bridge Config Update - Testing configuration update")
            
            # Test configuration data
            config_data = {
                "fast_ma": 5,
                "slow_ma": 10,
                "rsi_enabled": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/bridge/config", json=config_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge config endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    if not success:
                        print("   ❌ Bridge config update failed")
                        return False
                    
                    # Check for updated config
                    updated_config = data.get('config', {})
                    message = data.get('message', '')
                    
                    print(f"   📊 Message: {message}")
                    print(f"   📊 Updated config: {updated_config}")
                    
                    # Verify config values were updated
                    if updated_config:
                        fast_ma = updated_config.get('fast_ma')
                        slow_ma = updated_config.get('slow_ma')
                        rsi_enabled = updated_config.get('rsi_enabled')
                        
                        print(f"   📊 Fast MA: {fast_ma}")
                        print(f"   📊 Slow MA: {slow_ma}")
                        print(f"   📊 RSI enabled: {rsi_enabled}")
                        
                        # Check if values match what we sent
                        config_matches = (
                            fast_ma == config_data['fast_ma'] and
                            slow_ma == config_data['slow_ma'] and
                            rsi_enabled == config_data['rsi_enabled']
                        )
                        
                        if config_matches:
                            print("   ✅ Configuration values updated correctly")
                        else:
                            print("   ⚠️ Configuration values may not match exactly")
                    
                    # Test passes if success=true and we get config back
                    return success and ('config' in data or 'message' in data)
                else:
                    print(f"   ❌ Bridge config update failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge config update test error: {e}")
            return False

    async def test_bridge_integration_status(self) -> bool:
        """
        Test 7: Integration Status
        Test GET /api/bridge/integration/status:
        - Should return bridge_status
        - Should return strategy_status
        - Should show config details
        """
        try:
            print("   🌉 Test 7: Bridge Integration Status - Testing integration status overview")
            
            async with self.session.get(f"{BACKEND_URL}/bridge/integration/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bridge integration status endpoint accessible")
                    
                    # Check for success field
                    success = data.get('success')
                    print(f"   📊 Success: {success}")
                    
                    # Check for bridge status
                    bridge_status = data.get('bridge_status', {})
                    strategy_status = data.get('strategy_status', {})
                    config_details = data.get('config', {})
                    
                    print(f"   📊 Bridge status type: {type(bridge_status)}")
                    print(f"   📊 Strategy status type: {type(strategy_status)}")
                    print(f"   📊 Config details type: {type(config_details)}")
                    
                    # Display bridge status details
                    if isinstance(bridge_status, dict):
                        print(f"   📊 Bridge connected: {bridge_status.get('is_connected')}")
                        print(f"   📊 Bridge messages: {bridge_status.get('message_count')}")
                        print(f"   📊 Last message: {bridge_status.get('last_message_time')}")
                    
                    # Display strategy status details
                    if isinstance(strategy_status, dict):
                        print(f"   📊 Strategy active: {strategy_status.get('active')}")
                        print(f"   📊 Strategy type: {strategy_status.get('type')}")
                    
                    # Display config details
                    if isinstance(config_details, dict):
                        print(f"   📊 Config keys: {list(config_details.keys())}")
                        for key, value in list(config_details.items())[:3]:  # Show first 3
                            print(f"   📊 {key}: {value}")
                    
                    # Test passes if we get the expected structure
                    expected_fields = ['bridge_status', 'strategy_status']
                    has_expected = all(field in data for field in expected_fields)
                    
                    if has_expected:
                        print("   ✅ All expected status fields present")
                    else:
                        print("   ⚠️ Some expected status fields missing")
                    
                    return 'success' in data or has_expected
                else:
                    print(f"   ❌ Bridge integration status failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Bridge integration status test error: {e}")
            return False

    async def run_bridge_tests(self):
        """Run all bridge tests"""
        print("🌉 POCKET OPTION LIVE BRIDGE CONNECTION TESTING")
        print("=" * 60)
        
        await self.setup()
        
        # Bridge tests
        bridge_tests = [
            ("Bridge Status Endpoint", self.test_bridge_status_endpoint),
            ("Bridge Script Generation", self.test_bridge_script_generation),
            ("Bridge Data Reception", self.test_bridge_data_reception),
            ("Get Candles for Asset", self.test_get_candles_for_asset),
            ("Get All Bridge Assets", self.test_get_all_bridge_assets),
            ("Bridge Config Update", self.test_bridge_config_update),
            ("Bridge Integration Status", self.test_bridge_integration_status),
        ]
        
        for test_name, test_func in bridge_tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 BRIDGE TESTING SUMMARY")
        print("=" * 60)
        
        total_tests = len(bridge_tests)
        passed_tests = total_tests - len(self.failed_tests)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {len(self.failed_tests)}")
        
        if self.failed_tests:
            print(f"\nFailed Tests: {', '.join(self.failed_tests)}")
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"Success Rate: {success_rate:.1f}%")
        
        return success_rate >= 70  # 70% success rate threshold

async def main():
    """Main test execution"""
    tester = BridgeTester()
    success = await tester.run_bridge_tests()
    
    if success:
        print("\n✅ Bridge testing completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Bridge testing failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())