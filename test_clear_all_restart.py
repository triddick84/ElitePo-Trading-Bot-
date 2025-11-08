#!/usr/bin/env python3
"""
Focused Testing for Clear All Sessions and Restart Functionality
Tests the new bot stop enhancement, clear all sessions, and restart functionality
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime, timezone

# Add backend to path
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://optionai-4.preview.emergentagent.com/api"

class ClearAllRestartTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Clear All & Restart testing session initialized")
        
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

    async def test_bot_stop_enhancement(self) -> bool:
        """Test enhanced bot stop functionality that stops candle sync and auto generation"""
        try:
            print("   Testing enhanced bot stop functionality")
            
            # Start bot with test configuration
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["5s", "1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Start bot
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status != 200:
                    print("   ❌ Failed to start bot for stop enhancement test")
                    return False
            
            print("   ✅ Bot started successfully")
            
            # Enable candle sync mode
            async with self.session.post(f"{BACKEND_URL}/bot/candle-sync/enable") as response:
                if response.status == 200:
                    print("   ✅ Candle sync enabled")
                else:
                    print(f"   ⚠️ Candle sync enable failed: {response.status} (may be expected)")
            
            # Start auto signal generation
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    print("   ✅ Auto signal generation started")
                else:
                    print(f"   ❌ Auto signal generation start failed: {response.status}")
                    return False
            
            # Verify candle sync status before stop
            async with self.session.get(f"{BACKEND_URL}/bot/candle-sync/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Candle sync before stop - enabled: {data.get('enabled')}")
                
            # Verify auto generation status before stop
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Auto generation before stop - active: {data.get('auto_generation_active')}")
            
            # Stop the bot using enhanced stop endpoint
            async with self.session.post(f"{BACKEND_URL}/bot/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Stop response: {data}")
                    
                    # Verify response shows all processes stopped
                    expected_fields = {
                        'bot_running': False,
                        'candle_sync_stopped': True,
                        'auto_generation_stopped': True
                    }
                    
                    for field, expected_value in expected_fields.items():
                        actual_value = data.get(field)
                        if actual_value != expected_value:
                            print(f"   ❌ Expected {field}={expected_value}, got {actual_value}")
                            return False
                        print(f"   ✅ {field}: {actual_value}")
                    
                else:
                    print(f"   ❌ Bot stop failed: {response.status}")
                    return False
            
            # Verify candle sync is disabled after stop
            async with self.session.get(f"{BACKEND_URL}/bot/candle-sync/status") as response:
                if response.status == 200:
                    data = await response.json()
                    candle_sync_enabled = data.get('enabled', True)
                    print(f"   Candle sync after stop - enabled: {candle_sync_enabled}")
                    
                    if candle_sync_enabled:
                        print("   ❌ Candle sync should be disabled after bot stop")
                        return False
                    else:
                        print("   ✅ Candle sync properly disabled after stop")
            
            # Verify bot status shows not running
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    is_running = data.get('is_running', True)
                    print(f"   Bot status after stop - running: {is_running}")
                    
                    if is_running:
                        print("   ❌ Bot should not be running after stop")
                        return False
                    else:
                        print("   ✅ Bot status correctly shows not running")
            
            return True
            
        except Exception as e:
            print(f"   Bot stop enhancement test error: {e}")
            return False

    async def test_clear_all_sessions_functionality(self) -> bool:
        """Test clear all sessions endpoint functionality"""
        try:
            print("   Testing clear all sessions functionality")
            
            # Start bot and enable features
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["5s", "1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Start bot
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status != 200:
                    print("   ❌ Failed to start bot for clear all sessions test")
                    return False
            
            # Enable candle sync
            await self.session.post(f"{BACKEND_URL}/bot/candle-sync/enable")
            
            # Start auto generation
            await self.session.post(f"{BACKEND_URL}/signals/auto-generate/start")
            
            print("   ✅ Bot started with candle sync and auto generation enabled")
            
            # Call clear all sessions endpoint
            async with self.session.post(f"{BACKEND_URL}/bot/clear-all") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Clear all response: {data}")
                    
                    # Verify response structure
                    expected_status = data.get('status')
                    if expected_status not in ['success', 'warning']:
                        print(f"   ❌ Expected success/warning status, got: {expected_status}")
                        return False
                    
                    details = data.get('details', {})
                    expected_details = {
                        'bot_running': False,
                        'candle_sync_enabled': False,
                        'auto_signal_generation': False,
                        'active_signals_cleared': True
                    }
                    
                    for field, expected_value in expected_details.items():
                        actual_value = details.get(field)
                        if actual_value != expected_value:
                            print(f"   ❌ Expected {field}={expected_value}, got {actual_value}")
                            return False
                        print(f"   ✅ {field}: {actual_value}")
                    
                else:
                    print(f"   ❌ Clear all sessions failed: {response.status}")
                    return False
            
            # Verify bot status shows everything is stopped/cleared
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    is_running = data.get('is_running', True)
                    
                    if is_running:
                        print("   ❌ Bot should not be running after clear all")
                        return False
                    else:
                        print("   ✅ Bot status correctly shows not running after clear all")
            
            # Test clear all when bot is already stopped (should succeed gracefully)
            async with self.session.post(f"{BACKEND_URL}/bot/clear-all") as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Clear all succeeds gracefully when bot already stopped")
                else:
                    print(f"   ❌ Clear all should succeed when bot already stopped: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   Clear all sessions test error: {e}")
            return False

    async def test_restart_bot_functionality(self) -> bool:
        """Test restart bot endpoint functionality"""
        try:
            print("   Testing restart bot functionality")
            
            # Configure and start bot
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["5s", "1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            # Start bot initially
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status != 200:
                    print("   ❌ Failed to start bot for restart test")
                    return False
            
            # Enable candle sync
            await self.session.post(f"{BACKEND_URL}/bot/candle-sync/enable")
            print("   ✅ Bot started and candle sync enabled")
            
            # Call restart endpoint
            async with self.session.post(f"{BACKEND_URL}/bot/restart") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Restart response: {data}")
                    
                    # Verify response shows successful restart
                    expected_fields = {
                        'bot_running': True,
                        'configuration_loaded': True
                    }
                    
                    for field, expected_value in expected_fields.items():
                        actual_value = data.get(field)
                        if actual_value != expected_value:
                            print(f"   ❌ Expected {field}={expected_value}, got {actual_value}")
                            return False
                        print(f"   ✅ {field}: {actual_value}")
                    
                    # Check if success status is present
                    if data.get('status') != 'success':
                        print(f"   ❌ Expected success status, got: {data.get('status')}")
                        return False
                    
                else:
                    print(f"   ❌ Bot restart failed: {response.status}")
                    return False
            
            # Verify bot starts with previous configuration
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    is_running = data.get('is_running', False)
                    
                    if not is_running:
                        print("   ❌ Bot should be running after restart")
                        return False
                    else:
                        print("   ✅ Bot status correctly shows running after restart")
            
            # Verify configuration is maintained
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    config = await response.json()
                    
                    # Check key configuration values are maintained
                    if config.get('risk_tolerance') != 'medium':
                        print("   ❌ Configuration not maintained after restart")
                        return False
                    else:
                        print("   ✅ Configuration properly maintained after restart")
            
            # Test restart when bot is stopped (should start fresh)
            await self.session.post(f"{BACKEND_URL}/bot/stop")
            
            async with self.session.post(f"{BACKEND_URL}/bot/restart") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('bot_running') and data.get('status') == 'success':
                        print("   ✅ Restart works when bot is stopped")
                    else:
                        print(f"   ❌ Restart from stopped state failed: {data}")
                        return False
                else:
                    print(f"   ❌ Restart from stopped state failed: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   Restart bot test error: {e}")
            return False

    async def test_session_persistence_during_operations(self) -> bool:
        """Test session persistence during stop/clear/restart operations"""
        try:
            print("   Testing session persistence during operations")
            
            # Start bot
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 75.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            await self.session.post(f"{BACKEND_URL}/bot/start", json=config_data)
            
            # Generate some signals (force generate)
            signals_before = []
            try:
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate/asset/EURUSD") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') and data.get('signals'):
                            signals_before = data.get('signals', [])
                            print(f"   ✅ Generated {len(signals_before)} signals before operations")
            except:
                print("   ℹ️ Could not generate test signals (acceptable)")
            
            # Check signals in database before stop
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=5") as response:
                if response.status == 200:
                    data = await response.json()
                    signals_in_db_before = len(data.get('signals', []))
                    print(f"   Signals in database before stop: {signals_in_db_before}")
                else:
                    signals_in_db_before = 0
            
            # Stop bot
            await self.session.post(f"{BACKEND_URL}/bot/stop")
            
            # Verify signals are still in database (stop doesn't delete data)
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=5") as response:
                if response.status == 200:
                    data = await response.json()
                    signals_after_stop = len(data.get('signals', []))
                    print(f"   Signals in database after stop: {signals_after_stop}")
                    
                    if signals_after_stop < signals_in_db_before:
                        print("   ❌ Signals were deleted during stop (should be preserved)")
                        return False
                    else:
                        print("   ✅ Signals preserved in database after stop")
            
            # Clear all sessions
            await self.session.post(f"{BACKEND_URL}/bot/clear-all")
            
            # Verify bot state is reset but signals remain in DB
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=5") as response:
                if response.status == 200:
                    data = await response.json()
                    signals_after_clear = len(data.get('signals', []))
                    print(f"   Signals in database after clear all: {signals_after_clear}")
                    
                    if signals_after_clear < signals_in_db_before:
                        print("   ❌ Signals were deleted during clear all (should be preserved)")
                        return False
                    else:
                        print("   ✅ Signals preserved in database after clear all")
            
            # Verify bot state is properly reset
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('is_running'):
                        print("   ❌ Bot should not be running after clear all")
                        return False
                    else:
                        print("   ✅ Bot state properly reset after clear all")
            
            return True
            
        except Exception as e:
            print(f"   Session persistence test error: {e}")
            return False

    async def test_error_handling_edge_cases(self) -> bool:
        """Test error handling for edge cases in clear all and restart operations"""
        try:
            print("   Testing error handling edge cases")
            
            # Test clear all multiple times (should succeed each time)
            for i in range(3):
                async with self.session.post(f"{BACKEND_URL}/bot/clear-all") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ Clear all attempt {i+1}: {data.get('status')}")
                    else:
                        print(f"   ❌ Clear all attempt {i+1} failed: {response.status}")
                        return False
            
            # Test restart when bot is stopped (should start fresh)
            async with self.session.post(f"{BACKEND_URL}/bot/restart") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') or data.get('bot_running'):
                        print("   ✅ Restart succeeds when bot is stopped")
                    else:
                        print(f"   ❌ Restart failed when bot stopped: {data.get('message')}")
                        return False
                else:
                    print(f"   ❌ Restart when stopped failed: {response.status}")
                    return False
            
            # Test stop when already stopped (should succeed gracefully)
            await self.session.post(f"{BACKEND_URL}/bot/stop")  # Stop first
            
            async with self.session.post(f"{BACKEND_URL}/bot/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Stop succeeds gracefully when already stopped")
                else:
                    print(f"   ❌ Stop should succeed when already stopped: {response.status}")
                    return False
            
            # Test restart multiple times
            for i in range(2):
                async with self.session.post(f"{BACKEND_URL}/bot/restart") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') or data.get('bot_running'):
                            print(f"   ✅ Restart attempt {i+1} successful")
                        else:
                            print(f"   ❌ Restart attempt {i+1} failed: {data.get('message')}")
                            return False
                    else:
                        print(f"   ❌ Restart attempt {i+1} failed: {response.status}")
                        return False
                
                # Small delay between restarts
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            print(f"   Error handling edge cases test error: {e}")
            return False

    async def run_clear_all_restart_tests(self):
        """Run all Clear All Sessions and Restart tests"""
        print("🚀 Starting Clear All Sessions and Restart Functionality Testing")
        print("=" * 80)
        
        await self.setup()
        
        # Define test suite for Clear All Sessions and Restart functionality
        tests = [
            ("Bot Stop Enhancement", self.test_bot_stop_enhancement),
            ("Clear All Sessions Functionality", self.test_clear_all_sessions_functionality),
            ("Restart Bot Functionality", self.test_restart_bot_functionality),
            ("Session Persistence During Operations", self.test_session_persistence_during_operations),
            ("Error Handling Edge Cases", self.test_error_handling_edge_cases),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 CLEAR ALL SESSIONS & RESTART TESTING SUMMARY")
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
            print(f"\n🎉 All tests passed!")
            
        return len(self.failed_tests) == 0

async def main():
    """Main test runner"""
    tester = ClearAllRestartTester()
    success = await tester.run_clear_all_restart_tests()
    
    if success:
        print("\n✅ All Clear All Sessions and Restart tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    import sys
    result = asyncio.run(main())
    sys.exit(result)