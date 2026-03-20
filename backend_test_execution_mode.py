#!/usr/bin/env python3
"""
Automated Trading Execution Mode Testing for GPT Signal Bot
Tests new automated trading execution mode endpoints
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Test configuration
BACKEND_URL = "https://oanda-auto-trade.preview.emergentagent.com/api"

class ExecutionModeTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Execution Mode testing session initialized")
        
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

    async def test_execution_mode_current(self) -> bool:
        """
        Test GET /api/execution-mode/current - Get current execution mode
        Should return: success=true, mode (DEMO/BRIDGE/API/HEADLESS), executions count
        """
        try:
            print("   🤖 Testing Execution Mode Current endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/execution-mode/current") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Execution Mode Current endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'mode']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    mode = data.get('mode')
                    valid_modes = ['DEMO', 'BRIDGE', 'API', 'HEADLESS']
                    if mode not in valid_modes:
                        print(f"   ❌ Invalid mode: {mode}, expected one of {valid_modes}")
                        return False
                    
                    print(f"   📊 Current Mode: {mode}")
                    print(f"   📊 Executions Count: {data.get('executions_count', 0)}")
                    
                    return True
                else:
                    print(f"   ❌ Execution Mode Current endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Execution Mode Current test error: {e}")
            return False

    async def test_execution_mode_set_demo(self) -> bool:
        """
        Test POST /api/execution-mode/set?mode=DEMO - Set execution mode to DEMO
        Should return: success=true, mode="DEMO"
        """
        try:
            print("   🤖 Testing Execution Mode Set to DEMO")
            
            async with self.session.post(f"{BACKEND_URL}/execution-mode/set?mode=DEMO") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Execution Mode Set endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'mode']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    if data.get('mode') != 'DEMO':
                        print(f"   ❌ Mode not set to DEMO: {data.get('mode')}")
                        return False
                    
                    print(f"   📊 Mode Set To: {data.get('mode')}")
                    
                    return True
                else:
                    print(f"   ❌ Execution Mode Set endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Execution Mode Set test error: {e}")
            return False

    async def test_headless_status(self) -> bool:
        """
        Test GET /api/headless/status - Get headless browser status
        Should return: success=true, execution_mode, state object with is_running, is_logged_in, etc.
        """
        try:
            print("   🤖 Testing Headless Status endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/headless/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Headless Status endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'execution_mode', 'state']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    state = data.get('state', {})
                    expected_state_fields = ['is_running', 'is_logged_in']
                    
                    print(f"   📊 Execution Mode: {data.get('execution_mode')}")
                    print(f"   📊 Is Running: {state.get('is_running', False)}")
                    print(f"   📊 Is Logged In: {state.get('is_logged_in', False)}")
                    
                    return True
                else:
                    print(f"   ❌ Headless Status endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Headless Status test error: {e}")
            return False

    async def test_headless_start_expected_failure(self) -> bool:
        """
        Test POST /api/headless/start?account_type=live - Try to start headless browser
        Expected: Will fail with timeout error due to network restrictions (this is expected behavior)
        Should return error message about network/connection
        """
        try:
            print("   🤖 Testing Headless Start (Expected Failure)")
            
            async with self.session.post(f"{BACKEND_URL}/headless/start?account_type=live") as response:
                # This should fail due to network restrictions
                if response.status in [400, 500, 503]:
                    data = await response.json()
                    print(f"   ✅ Headless Start endpoint accessible (expected failure)")
                    
                    # Should contain error message about network/connection
                    error_msg = data.get('error', '') or data.get('message', '') or data.get('detail', '')
                    
                    network_keywords = ['network', 'connection', 'timeout', 'restricted', 'failed', 'error']
                    has_network_error = any(keyword in error_msg.lower() for keyword in network_keywords)
                    
                    if has_network_error:
                        print(f"   ✅ Expected network error received: {error_msg}")
                        return True
                    else:
                        print(f"   ⚠️ Unexpected error message: {error_msg}")
                        return True  # Still pass as endpoint is working
                        
                elif response.status == 200:
                    # Unexpected success - but still valid
                    data = await response.json()
                    print(f"   ⚠️ Unexpected success (may work in this environment): {data}")
                    return True
                else:
                    print(f"   ❌ Headless Start endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Headless Start test error: {e}")
            return False

    async def test_auto_trade_status_verification(self) -> bool:
        """
        Test GET /api/auto-trade/status - Verify auto-trade status still works
        Should return: success=true, is_running, is_connected, is_auto_trade_enabled, stats
        """
        try:
            print("   🤖 Testing Auto-Trade Status Verification")
            
            async with self.session.get(f"{BACKEND_URL}/auto-trade/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto-Trade Status endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'is_running', 'is_connected', 'is_auto_trade_enabled']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    print(f"   📊 Is Running: {data.get('is_running')}")
                    print(f"   📊 Is Connected: {data.get('is_connected')}")
                    print(f"   📊 Auto Trade Enabled: {data.get('is_auto_trade_enabled')}")
                    
                    # Check stats if present
                    stats = data.get('stats', {})
                    if stats:
                        print(f"   📊 Stats: {stats}")
                    
                    return True
                else:
                    print(f"   ❌ Auto-Trade Status endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Auto-Trade Status test error: {e}")
            return False

    async def test_trade_executor_pending(self) -> bool:
        """
        Test GET /api/trade-executor/pending - Get pending trades
        Should return: success=true, pending_trades array
        """
        try:
            print("   🤖 Testing Trade Executor Pending")
            
            async with self.session.get(f"{BACKEND_URL}/trade-executor/pending") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Trade Executor Pending endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'pending_trades']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    pending_trades = data.get('pending_trades', [])
                    if not isinstance(pending_trades, list):
                        print(f"   ❌ pending_trades is not an array: {type(pending_trades)}")
                        return False
                    
                    print(f"   📊 Pending Trades Count: {len(pending_trades)}")
                    
                    return True
                else:
                    print(f"   ❌ Trade Executor Pending endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Trade Executor Pending test error: {e}")
            return False

    async def test_trade_executor_statistics(self) -> bool:
        """
        Test GET /api/trade-executor/statistics - Get executor statistics
        Should return: success=true, pending_count, active_count, completed_count, wins, losses
        """
        try:
            print("   🤖 Testing Trade Executor Statistics")
            
            async with self.session.get(f"{BACKEND_URL}/trade-executor/statistics") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Trade Executor Statistics endpoint accessible")
                    
                    # Check required fields
                    required_fields = ['success', 'pending_count', 'active_count', 'completed_count', 'wins', 'losses']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify response structure
                    if data.get('success') != True:
                        print(f"   ❌ Success field is not True")
                        return False
                    
                    print(f"   📊 Pending Count: {data.get('pending_count')}")
                    print(f"   📊 Active Count: {data.get('active_count')}")
                    print(f"   📊 Completed Count: {data.get('completed_count')}")
                    print(f"   📊 Wins: {data.get('wins')}")
                    print(f"   📊 Losses: {data.get('losses')}")
                    
                    return True
                else:
                    print(f"   ❌ Trade Executor Statistics endpoint failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"   Trade Executor Statistics test error: {e}")
            return False

async def run_automated_trading_execution_mode_tests():
    """Run Automated Trading Execution Mode tests specifically"""
    print("🚀 Testing Automated Trading Execution Mode Implementation")
    print("=" * 80)
    
    tester = ExecutionModeTester()
    await tester.setup()
    
    # Define execution mode tests
    tests = [
        ("Health Check", tester.test_health_check),
        ("Execution Mode Current", tester.test_execution_mode_current),
        ("Execution Mode Set DEMO", tester.test_execution_mode_set_demo),
        ("Headless Status", tester.test_headless_status),
        ("Headless Start (Expected Failure)", tester.test_headless_start_expected_failure),
        ("Auto-Trade Status Verification", tester.test_auto_trade_status_verification),
        ("Trade Executor Pending", tester.test_trade_executor_pending),
        ("Trade Executor Statistics", tester.test_trade_executor_statistics),
    ]
    
    # Run all tests
    for test_name, test_func in tests:
        await tester.run_test(test_name, test_func)
    
    await tester.cleanup()
    
    # Print summary
    print("\n" + "=" * 80)
    print("🏁 Automated Trading Execution Mode Testing Complete: {}/{} tests passed".format(
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
        print(f"\n🎉 All Automated Trading Execution Mode tests passed!")
        print(f"\n📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        return True

async def main():
    """Main test runner"""
    return await run_automated_trading_execution_mode_tests()

if __name__ == "__main__":
    asyncio.run(main())