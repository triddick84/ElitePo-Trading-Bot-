#!/usr/bin/env python3
"""
SSID Auto-Refresh and Telegram Signal Notification Integration Tests
Tests the newly implemented SSID and Telegram services
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone

# Add backend to path
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://pocket-trader-ai-8.preview.emergentagent.com/api"

class SSIDTelegramTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 SSID & Telegram testing session initialized")
        
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
    
    # ========== SSID AUTO-REFRESH SERVICE TESTS ==========
    
    async def test_ssid_status_endpoint(self) -> bool:
        """Test SSID Status Endpoint"""
        try:
            print("   🔑 Testing SSID status endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/ssid/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ SSID status endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['ssid_preview', 'is_valid']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    print(f"   📊 SSID Preview: {data.get('ssid_preview')}")
                    print(f"   📊 Is Valid: {data.get('is_valid')}")
                    print(f"   📊 Service Running: {data.get('service_running', 'N/A')}")
                    
                    return True
                else:
                    print(f"   ❌ SSID status endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   SSID status endpoint test error: {e}")
            return False
    
    async def test_ssid_start_auto_refresh(self) -> bool:
        """Test SSID Start Auto-Refresh"""
        try:
            print("   🔄 Testing SSID start auto-refresh")
            
            async with self.session.post(f"{BACKEND_URL}/ssid/start-auto-refresh") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ SSID auto-refresh start endpoint accessible")
                    print(f"   📊 Success: {data.get('success')}")
                    print(f"   📊 Message: {data.get('message')}")
                    
                    # Test passes if we get a proper response structure
                    return 'success' in data and 'message' in data
                else:
                    print(f"   ❌ SSID start auto-refresh failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   SSID start auto-refresh test error: {e}")
            return False
    
    async def test_ssid_stop_auto_refresh(self) -> bool:
        """Test SSID Stop Auto-Refresh"""
        try:
            print("   🛑 Testing SSID stop auto-refresh")
            
            async with self.session.post(f"{BACKEND_URL}/ssid/stop-auto-refresh") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ SSID auto-refresh stop endpoint accessible")
                    print(f"   📊 Success: {data.get('success')}")
                    print(f"   📊 Message: {data.get('message')}")
                    
                    # Should always succeed
                    success = data.get('success')
                    return success is True
                else:
                    print(f"   ❌ SSID stop auto-refresh failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   SSID stop auto-refresh test error: {e}")
            return False
    
    # ========== TELEGRAM NOTIFICATION SERVICE TESTS ==========
    
    async def test_telegram_status_endpoint(self) -> bool:
        """Test Telegram Status Endpoint"""
        try:
            print("   📱 Testing Telegram status endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/telegram/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Telegram status endpoint accessible")
                    
                    # Check for expected fields
                    configured = data.get('configured')
                    chat_id = data.get('chat_id')
                    enabled = data.get('enabled')
                    
                    print(f"   📊 Configured: {configured}")
                    print(f"   📊 Chat ID: {chat_id}")
                    print(f"   📊 Enabled: {enabled}")
                    print(f"   📊 Send Signals: {data.get('send_signals')}")
                    print(f"   📊 Send Errors: {data.get('send_errors')}")
                    
                    # Verify expected values
                    expected_chat_id = "6434316177"
                    if configured and chat_id == expected_chat_id:
                        print(f"   ✅ Telegram properly configured with expected chat ID")
                        return True
                    else:
                        print(f"   ⚠️ Telegram configuration issue - configured: {configured}, chat_id: {chat_id}")
                        return False
                else:
                    print(f"   ❌ Telegram status endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Telegram status endpoint test error: {e}")
            return False
    
    async def test_telegram_test_notification(self) -> bool:
        """Test Telegram Test Notification"""
        try:
            print("   📤 Testing Telegram test notification")
            
            async with self.session.post(f"{BACKEND_URL}/telegram/test") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Telegram test endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    
                    if success:
                        print(f"   ✅ Test notification sent successfully to Telegram")
                        return True
                    else:
                        print(f"   ❌ Test notification failed: {message}")
                        return False
                else:
                    print(f"   ❌ Telegram test endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Telegram test notification error: {e}")
            return False
    
    async def test_telegram_config_update(self) -> bool:
        """Test Telegram Config Update"""
        try:
            print("   ⚙️ Testing Telegram config update")
            
            # Test config update
            config_update = {
                "enabled": True,
                "send_signals": True,
                "send_errors": True,
                "send_status_updates": False,
                "send_ssid_alerts": True
            }
            
            async with self.session.put(f"{BACKEND_URL}/telegram/config", json=config_update) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Telegram config update endpoint accessible")
                    
                    success = data.get('success')
                    message = data.get('message')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Message: {message}")
                    
                    if success:
                        # Verify the update by checking status
                        async with self.session.get(f"{BACKEND_URL}/telegram/status") as status_response:
                            if status_response.status == 200:
                                status_data = await status_response.json()
                                
                                # Check if our updates were applied
                                send_status_updates = status_data.get('send_status_updates')
                                send_signals = status_data.get('send_signals')
                                
                                print(f"   📊 Updated send_signals: {send_signals}")
                                print(f"   📊 Updated send_status_updates: {send_status_updates}")
                                
                                # Verify specific update (send_status_updates should be False)
                                return send_status_updates is False and send_signals is True
                            else:
                                print(f"   ❌ Could not verify config update")
                                return False
                    else:
                        print(f"   ❌ Config update failed: {message}")
                        return False
                else:
                    print(f"   ❌ Telegram config update failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Telegram config update test error: {e}")
            return False
    
    # ========== INTEGRATED SIGNAL + TELEGRAM FLOW TESTS ==========
    
    async def test_generate_and_notify_signal(self) -> bool:
        """Test Integrated Signal + Telegram Flow"""
        try:
            print("   🚀 Testing integrated signal generation and Telegram notification")
            
            # Test parameters
            params = {
                "asset": "EURUSD_OTC",
                "timeframe": "5s",
                "send_telegram": "true"
            }
            
            async with self.session.post(f"{BACKEND_URL}/signals/generate-and-notify", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Generate-and-notify endpoint accessible")
                    
                    success = data.get('success')
                    signal = data.get('signal')
                    telegram_sent = data.get('telegram_sent')
                    
                    print(f"   📊 Success: {success}")
                    print(f"   📊 Telegram Sent: {telegram_sent}")
                    
                    if signal:
                        print(f"   📊 Signal ID: {signal.get('id')}")
                        print(f"   📊 Asset: {signal.get('symbol')}")
                        print(f"   📊 Direction: {signal.get('direction')}")
                        print(f"   📊 Probability: {signal.get('probability')}%")
                        print(f"   📊 Timeframe: {signal.get('timeframe')}")
                    
                    # Test passes if we get a signal and Telegram notification was attempted
                    if success and signal and telegram_sent is not None:
                        print(f"   ✅ Signal generated and Telegram notification {'sent' if telegram_sent else 'attempted'}")
                        return True
                    else:
                        print(f"   ⚠️ Partial success - signal: {bool(signal)}, telegram: {telegram_sent}")
                        return False
                else:
                    print(f"   ❌ Generate-and-notify endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Generate-and-notify test error: {e}")
            return False

    async def run_all_tests(self):
        """Run all SSID and Telegram tests"""
        print("🔑📱 SSID AUTO-REFRESH & TELEGRAM INTEGRATION TESTING")
        print("=" * 70)
        
        await self.setup()
        
        # SSID Auto-Refresh Service Tests
        ssid_tests = [
            ("SSID Status Endpoint", self.test_ssid_status_endpoint),
            ("SSID Start Auto-Refresh", self.test_ssid_start_auto_refresh),
            ("SSID Stop Auto-Refresh", self.test_ssid_stop_auto_refresh),
        ]
        
        # Telegram Notification Service Tests
        telegram_tests = [
            ("Telegram Status Endpoint", self.test_telegram_status_endpoint),
            ("Telegram Test Notification", self.test_telegram_test_notification),
            ("Telegram Config Update", self.test_telegram_config_update),
        ]
        
        # Integrated Flow Tests
        integration_tests = [
            ("Generate and Notify Signal", self.test_generate_and_notify_signal),
        ]
        
        # Run SSID tests
        print("\n🔑 RUNNING SSID AUTO-REFRESH SERVICE TESTS")
        print("=" * 50)
        for test_name, test_func in ssid_tests:
            await self.run_test(test_name, test_func)
        
        # Run Telegram tests
        print("\n📱 RUNNING TELEGRAM NOTIFICATION SERVICE TESTS")
        print("=" * 50)
        for test_name, test_func in telegram_tests:
            await self.run_test(test_name, test_func)
        
        # Run integration tests
        print("\n🚀 RUNNING INTEGRATED SIGNAL + TELEGRAM FLOW TESTS")
        print("=" * 55)
        for test_name, test_func in integration_tests:
            await self.run_test(test_name, test_func)
        
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 SSID & TELEGRAM TESTING SUMMARY")
        print("=" * 70)
        
        all_tests = ssid_tests + telegram_tests + integration_tests
        total_tests = len(all_tests)
        passed_tests = total_tests - len(self.failed_tests)
        
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {len(self.failed_tests)}")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   • {test}")
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 SSID & Telegram integration testing PASSED!")
        else:
            print("⚠️ SSID & Telegram integration testing needs attention")
        
        return success_rate >= 80


async def main():
    """Main test execution"""
    tester = SSIDTelegramTester()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)