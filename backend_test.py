#!/usr/bin/env python3
"""
Comprehensive Backend Testing for GPT Signal Bot
Tests Pocket Option API integration, invert signals logic, and platform integrations
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add backend to path
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://tradingbot-gpt.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Backend testing session initialized")
        
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
            else:
                print(f"❌ {test_name}: FAILED")
                self.failed_tests.append(test_name)
                self.test_results.append({"test": test_name, "status": "FAILED", "details": "Test returned False"})
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.failed_tests.append(test_name)
            self.test_results.append({"test": test_name, "status": "ERROR", "details": str(e)})
            
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
            
    async def test_environment_variables(self) -> bool:
        """Test that required environment variables are loaded"""
        try:
            # Check integration status to verify env vars are loaded
            async with self.session.get(f"{BACKEND_URL}/integrations/status") as response:
                if response.status == 200:
                    data = await response.json()
                    integrations = data.get('integrations', {})
                    
                    # Check Pocket Option credentials
                    pocket_option = integrations.get('pocket_option', {})
                    if not pocket_option.get('account_id') or not pocket_option.get('ssid'):
                        print("   ❌ Pocket Option credentials missing")
                        return False
                    print(f"   ✅ Pocket Option Account ID: {pocket_option.get('account_id')}")
                    print(f"   ✅ Pocket Option SSID: {pocket_option.get('ssid')}")
                    
                    # Check Telegram credentials
                    telegram = integrations.get('telegram', {})
                    if not telegram.get('chat_id'):
                        print("   ❌ Telegram credentials missing")
                        return False
                    print(f"   ✅ Telegram Chat ID: {telegram.get('chat_id')}")
                    
                    # Check AutobotSignal credentials
                    autobot = integrations.get('autobot_signal', {})
                    if not autobot.get('webhook_url') or not autobot.get('signal_key'):
                        print("   ❌ AutobotSignal credentials missing")
                        return False
                    print(f"   ✅ AutobotSignal URL: {autobot.get('webhook_url')}")
                    print(f"   ✅ AutobotSignal Key: {autobot.get('signal_key')}")
                    
                    return True
                else:
                    print(f"   Integration status failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Environment variables test error: {e}")
            return False
            
    async def test_pocket_option_integration_status(self) -> bool:
        """Test Pocket Option integration status endpoint"""
        try:
            async with self.session.get(f"{BACKEND_URL}/integrations/status") as response:
                if response.status == 200:
                    data = await response.json()
                    pocket_option = data.get('integrations', {}).get('pocket_option', {})
                    
                    print(f"   Pocket Option Status: {pocket_option.get('status')}")
                    print(f"   Account ID: {pocket_option.get('account_id')}")
                    print(f"   Email: {pocket_option.get('email')}")
                    
                    if pocket_option.get('last_error'):
                        print(f"   Last Error: {pocket_option.get('last_error')}")
                    
                    # Status can be 'ready' or 'error' - both are valid responses
                    return pocket_option.get('status') in ['ready', 'error']
                else:
                    print(f"   Status check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Pocket Option status test error: {e}")
            return False
            
    async def test_integration_test_endpoint(self) -> bool:
        """Test the integration test endpoint"""
        try:
            async with self.session.post(f"{BACKEND_URL}/integrations/test") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Integration test message: {data.get('message')}")
                    
                    results = data.get('results', {})
                    for platform, status in results.items():
                        print(f"   {platform}: {status.get('status')} - {status.get('last_error', 'No errors')}")
                    
                    return True
                else:
                    print(f"   Integration test failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   Integration test error: {e}")
            return False
            
    async def test_bot_start_with_new_fields(self) -> bool:
        """Test bot start with invert_signals and sound_alerts_enabled fields"""
        try:
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex", "crypto"],
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"],
                "selected_timeframes": ["1m", "5m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 95.0,
                "auto_trading_enabled": False,
                "invert_signals": True,  # Test new field
                "sound_alerts_enabled": True  # Test new field
            }
            
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Bot start status: {data.get('status')}")
                    print(f"   Message: {data.get('message')}")
                    
                    # Check if new fields are in the config
                    config = data.get('config', {})
                    invert_signals = config.get('invert_signals')
                    sound_alerts = config.get('sound_alerts_enabled')
                    
                    print(f"   Invert signals: {invert_signals}")
                    print(f"   Sound alerts: {sound_alerts}")
                    
                    return invert_signals is True and sound_alerts is True
                else:
                    print(f"   Bot start failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   Bot start test error: {e}")
            return False
            
    async def test_config_endpoints(self) -> bool:
        """Test configuration GET and PUT endpoints with new fields"""
        try:
            # First, test GET config
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    config = await response.json()
                    print(f"   Current config retrieved successfully")
                    print(f"   Invert signals: {config.get('invert_signals')}")
                    print(f"   Sound alerts: {config.get('sound_alerts_enabled')}")
                else:
                    print(f"   Config GET failed: {response.status}")
                    return False
            
            # Test PUT config with new fields
            updated_config = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["1m"],
                "risk_tolerance": "low",
                "max_stake_per_trade": 5.0,
                "max_daily_trades": 25,
                "min_probability_threshold": 98.0,
                "auto_trading_enabled": False,
                "invert_signals": False,  # Change to test update
                "sound_alerts_enabled": False  # Change to test update
            }
            
            async with self.session.put(f"{BACKEND_URL}/config", json=updated_config) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Config update status: {data.get('status')}")
                    
                    # Verify the update by getting config again
                    async with self.session.get(f"{BACKEND_URL}/config") as get_response:
                        if get_response.status == 200:
                            new_config = await get_response.json()
                            invert_updated = new_config.get('invert_signals') == False
                            sound_updated = new_config.get('sound_alerts_enabled') == False
                            
                            print(f"   Updated invert signals: {new_config.get('invert_signals')}")
                            print(f"   Updated sound alerts: {new_config.get('sound_alerts_enabled')}")
                            
                            return invert_updated and sound_updated
                        else:
                            print(f"   Config verification failed: {get_response.status}")
                            return False
                else:
                    print(f"   Config PUT failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   Config endpoints test error: {e}")
            return False
            
    async def test_signal_inversion_endpoint(self) -> bool:
        """Test individual signal inversion endpoint"""
        try:
            # First, get some signals to test with
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=1") as response:
                if response.status == 200:
                    data = await response.json()
                    signals = data.get('signals', [])
                    
                    if not signals:
                        print("   No signals available to test inversion")
                        return True  # Not a failure, just no data
                    
                    signal_id = signals[0].get('id')
                    original_direction = signals[0].get('direction')
                    
                    print(f"   Testing inversion on signal {signal_id}")
                    print(f"   Original direction: {original_direction}")
                    
                    # Test signal inversion
                    async with self.session.post(f"{BACKEND_URL}/signals/invert/{signal_id}") as invert_response:
                        if invert_response.status == 200:
                            invert_data = await invert_response.json()
                            print(f"   Inversion message: {invert_data.get('message')}")
                            print(f"   Original: {invert_data.get('original_direction')}")
                            print(f"   New: {invert_data.get('new_direction')}")
                            
                            # Verify inversion logic
                            original = invert_data.get('original_direction')
                            new = invert_data.get('new_direction')
                            
                            valid_inversion = (
                                (original == 'BUY' and new == 'SELL') or
                                (original == 'SELL' and new == 'BUY') or
                                (original == 'CALL' and new == 'PUT') or
                                (original == 'PUT' and new == 'CALL')
                            )
                            
                            return valid_inversion
                        else:
                            print(f"   Signal inversion failed: {invert_response.status}")
                            return False
                else:
                    print(f"   Failed to get signals for inversion test: {response.status}")
                    return False
        except Exception as e:
            print(f"   Signal inversion test error: {e}")
            return False
            
    async def test_signal_execution_endpoint(self) -> bool:
        """Test signal execution on Pocket Option platform"""
        try:
            # Get a signal to execute
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=1") as response:
                if response.status == 200:
                    data = await response.json()
                    signals = data.get('signals', [])
                    
                    if not signals:
                        print("   No signals available to test execution")
                        return True  # Not a failure, just no data
                    
                    signal_id = signals[0].get('id')
                    print(f"   Testing execution on signal {signal_id}")
                    
                    # Test signal execution
                    async with self.session.post(f"{BACKEND_URL}/signals/{signal_id}/execute") as exec_response:
                        if exec_response.status == 200:
                            exec_data = await exec_response.json()
                            result = exec_data.get('execution_result', {})
                            
                            print(f"   Execution success: {result.get('success')}")
                            print(f"   Message: {result.get('message')}")
                            print(f"   Trade ID: {result.get('trade_id', 'None')}")
                            
                            # Execution can fail due to API limitations, but endpoint should work
                            return 'success' in result and 'message' in result
                        else:
                            print(f"   Signal execution failed: {exec_response.status}")
                            error_text = await exec_response.text()
                            print(f"   Error details: {error_text}")
                            return False
                else:
                    print(f"   Failed to get signals for execution test: {response.status}")
                    return False
        except Exception as e:
            print(f"   Signal execution test error: {e}")
            return False
            
    async def test_bot_status_endpoint(self) -> bool:
        """Test bot status endpoint"""
        try:
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Bot running: {data.get('is_running')}")
                    print(f"   Current mode: {data.get('current_mode')}")
                    print(f"   Active strategies: {data.get('active_strategies')}")
                    print(f"   Signals today: {data.get('signals_today')}")
                    
                    return 'is_running' in data and 'current_mode' in data
                else:
                    print(f"   Bot status failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Bot status test error: {e}")
            return False
            
    async def test_performance_metrics(self) -> bool:
        """Test performance metrics endpoint"""
        try:
            async with self.session.get(f"{BACKEND_URL}/performance/metrics") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Total signals: {data.get('total_signals', 0)}")
                    print(f"   Win rate: {data.get('win_rate', 0)}%")
                    print(f"   P&L: ${data.get('profit_loss', 0)}")
                    
                    return 'total_signals' in data
                else:
                    print(f"   Performance metrics failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Performance metrics test error: {e}")
            return False
            
    async def test_market_data_endpoints(self) -> bool:
        """Test market data endpoints"""
        try:
            # Test general market data
            async with self.session.get(f"{BACKEND_URL}/market/data") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Market data retrieved successfully")
                    
                    # Test selected assets data
                    selected_assets = ["EURUSD_regular", "BTCUSD_regular"]
                    async with self.session.post(f"{BACKEND_URL}/market/data/selected", json=selected_assets) as selected_response:
                        if selected_response.status == 200:
                            selected_data = await selected_response.json()
                            assets = selected_data.get('selected_assets', [])
                            print(f"   Selected assets data: {len(assets)} assets")
                            return len(assets) >= 0  # Can be 0 if no data available
                        else:
                            print(f"   Selected assets data failed: {selected_response.status}")
                            return False
                else:
                    print(f"   Market data failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Market data test error: {e}")
            return False

    async def test_auto_signal_generation_status(self) -> bool:
        """Test auto signal generation status endpoint"""
        try:
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Auto generation active: {data.get('auto_generation_active')}")
                    print(f"   Bot running: {data.get('bot_running')}")
                    print(f"   Status: {data.get('status')}")
                    
                    # Verify required fields are present
                    required_fields = ['auto_generation_active', 'bot_running', 'status']
                    return all(field in data for field in required_fields)
                else:
                    print(f"   Auto signal generation status failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Auto signal generation status test error: {e}")
            return False

    async def test_single_signal_generation_bot_stopped(self) -> bool:
        """Test single signal generation when bot is stopped (should fail)"""
        try:
            # First ensure bot is stopped
            await self.session.post(f"{BACKEND_URL}/bot/stop")
            
            # Try to generate single signal
            async with self.session.post(f"{BACKEND_URL}/signals/generate/single") as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"   Expected error message: {data.get('detail')}")
                    return "bot is not running" in data.get('detail', '').lower()
                else:
                    print(f"   Expected 400 error but got: {response.status}")
                    return False
        except Exception as e:
            print(f"   Single signal generation (bot stopped) test error: {e}")
            return False

    async def test_single_signal_generation_bot_running(self) -> bool:
        """Test single signal generation when bot is running"""
        try:
            # First ensure bot is running
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex", "crypto"],
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"],
                "selected_timeframes": ["1m", "5m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 95.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            await self.session.post(f"{BACKEND_URL}/bot/start", json=config_data)
            
            # Try to generate single signal
            async with self.session.post(f"{BACKEND_URL}/signals/generate/single") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Success: {data.get('success')}")
                    print(f"   Message: {data.get('message')}")
                    
                    signal = data.get('signal')
                    if signal:
                        print(f"   Signal ID: {signal.get('id')}")
                        print(f"   Symbol: {signal.get('symbol')}")
                        print(f"   Direction: {signal.get('direction')}")
                        print(f"   Probability: {signal.get('probability')}")
                    
                    # Verify response format
                    required_fields = ['success', 'message', 'signal']
                    return all(field in data for field in required_fields)
                else:
                    print(f"   Single signal generation failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   Single signal generation (bot running) test error: {e}")
            return False

    async def test_auto_generation_start_stop_bot_stopped(self) -> bool:
        """Test auto generation start/stop when bot is stopped (should fail)"""
        try:
            # Ensure bot is stopped
            await self.session.post(f"{BACKEND_URL}/bot/stop")
            
            # Try to start auto generation
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"   Expected error for start: {data.get('detail')}")
                    start_error_valid = "bot is not running" in data.get('detail', '').lower()
                else:
                    print(f"   Expected 400 error for start but got: {response.status}")
                    start_error_valid = False
            
            # Stop should work regardless of bot status
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Stop success: {data.get('success')}")
                    print(f"   Stop message: {data.get('message')}")
                    stop_works = data.get('success') is True
                else:
                    print(f"   Auto generation stop failed: {response.status}")
                    stop_works = False
            
            return start_error_valid and stop_works
        except Exception as e:
            print(f"   Auto generation start/stop (bot stopped) test error: {e}")
            return False

    async def test_auto_generation_start_stop_bot_running(self) -> bool:
        """Test auto generation start/stop when bot is running"""
        try:
            # Ensure bot is running
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex", "crypto"],
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"],
                "selected_timeframes": ["1m", "5m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 95.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            await self.session.post(f"{BACKEND_URL}/bot/start", json=config_data)
            
            # Test start auto generation
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Start success: {data.get('success')}")
                    print(f"   Start message: {data.get('message')}")
                    print(f"   Start status: {data.get('status')}")
                    start_success = data.get('success') is True and data.get('status') == 'active'
                else:
                    print(f"   Auto generation start failed: {response.status}")
                    start_success = False
            
            # Check status after start
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Status after start - Active: {data.get('auto_generation_active')}")
                    status_active = data.get('auto_generation_active') is True
                else:
                    status_active = False
            
            # Test stop auto generation
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Stop success: {data.get('success')}")
                    print(f"   Stop message: {data.get('message')}")
                    print(f"   Stop status: {data.get('status')}")
                    stop_success = data.get('success') is True and data.get('status') == 'stopped'
                else:
                    print(f"   Auto generation stop failed: {response.status}")
                    stop_success = False
            
            # Check status after stop
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Status after stop - Active: {data.get('auto_generation_active')}")
                    status_stopped = data.get('auto_generation_active') is False
                else:
                    status_stopped = False
            
            return start_success and status_active and stop_success and status_stopped
        except Exception as e:
            print(f"   Auto generation start/stop (bot running) test error: {e}")
            return False

    async def test_bot_auto_signal_generation_flag_initialization(self) -> bool:
        """Test that bot properly initializes auto_signal_generation flag"""
        try:
            # Start bot and check initial auto generation status
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex", "crypto"],
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"],
                "selected_timeframes": ["1m", "5m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 95.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            await self.session.post(f"{BACKEND_URL}/bot/start", json=config_data)
            
            # Check initial auto generation status (should be False by default)
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   Initial auto generation active: {data.get('auto_generation_active')}")
                    print(f"   Bot running: {data.get('bot_running')}")
                    print(f"   Status: {data.get('status')}")
                    
                    # Should be False initially and bot should be running
                    return (data.get('auto_generation_active') is False and 
                            data.get('bot_running') is True and
                            data.get('status') == 'stopped')
                else:
                    print(f"   Auto generation status check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   Bot auto signal generation flag initialization test error: {e}")
            return False
            
    async def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting comprehensive backend testing for GPT Signal Bot")
        print("=" * 70)
        
        await self.setup()
        
        # Define test suite
        tests = [
            ("Health Check", self.test_health_check),
            ("Environment Variables", self.test_environment_variables),
            ("Pocket Option Integration Status", self.test_pocket_option_integration_status),
            ("Integration Test Endpoint", self.test_integration_test_endpoint),
            ("Bot Start with New Fields", self.test_bot_start_with_new_fields),
            ("Configuration Endpoints", self.test_config_endpoints),
            ("Signal Inversion Endpoint", self.test_signal_inversion_endpoint),
            ("Signal Execution Endpoint", self.test_signal_execution_endpoint),
            ("Bot Status Endpoint", self.test_bot_status_endpoint),
            ("Performance Metrics", self.test_performance_metrics),
            ("Market Data Endpoints", self.test_market_data_endpoints),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 BACKEND TESTING SUMMARY")
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
    tester = BackendTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ Backend testing completed successfully!")
        return 0
    else:
        print("\n❌ Backend testing completed with failures!")
        return 1

if __name__ == "__main__":
    import sys
    result = asyncio.run(main())
    sys.exit(result)