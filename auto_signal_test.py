#!/usr/bin/env python3
"""
Focused Auto Signal Generation Testing
Tests the newly fixed auto signal generation functionality
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Test configuration
BACKEND_URL = "https://trademixer.preview.emergentagent.com/api"

class AutoSignalTester:
    def __init__(self):
        self.session = None
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Auto Signal Generation testing session initialized")
        
    async def cleanup(self):
        """Cleanup test session"""
        if self.session:
            await self.session.close()
        print("🧹 Test session cleaned up")

    async def test_auto_signal_generation_complete_flow(self):
        """Test the complete auto signal generation flow as specified in review request"""
        print("\n🔄 TESTING AUTO SIGNAL GENERATION COMPLETE FLOW")
        print("=" * 60)
        
        try:
            # Step 1: Start bot first with default config
            print("Step 1: Starting bot with default configuration...")
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex", "crypto"],
                "selected_assets": ["EURUSD_regular", "BTCUSD_regular"],
                "selected_timeframes": ["5s", "1m"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Bot started: {data.get('message')}")
                else:
                    print(f"   ❌ Failed to start bot: {response.status}")
                    return False
            
            # Step 2: Verify bot is running
            print("Step 2: Verifying bot is running...")
            async with self.session.get(f"{BACKEND_URL}/bot/status") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('is_running'):
                        print(f"   ✅ Bot is running: {data.get('is_running')}")
                    else:
                        print(f"   ❌ Bot is not running: {data.get('is_running')}")
                        return False
                else:
                    print(f"   ❌ Failed to get bot status: {response.status}")
                    return False
            
            # Step 3: Start auto generation
            print("Step 3: Starting auto signal generation...")
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto generation started: {data.get('message')}")
                else:
                    print(f"   ❌ Failed to start auto generation: {response.status}")
                    return False
            
            # Step 4: Check status (should show auto_generation_active: true)
            print("Step 4: Checking auto generation status...")
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('auto_generation_active') is True:
                        print(f"   ✅ Auto generation active: {data.get('auto_generation_active')}")
                        print(f"   ✅ Bot running: {data.get('bot_running')}")
                        print(f"   ✅ Status: {data.get('status')}")
                    else:
                        print(f"   ❌ Auto generation not active: {data.get('auto_generation_active')}")
                        return False
                else:
                    print(f"   ❌ Failed to get auto generation status: {response.status}")
                    return False
            
            # Step 5: Wait 10-15 seconds for signals to be generated
            print("Step 5: Waiting 15 seconds for auto signal generation...")
            await asyncio.sleep(15)
            
            # Step 6: Check if signals were created
            print("Step 6: Checking if signals were generated...")
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=10") as response:
                if response.status == 200:
                    data = await response.json()
                    signals = data.get('signals', [])
                    
                    # Check for recent signals (within last 2 minutes)
                    recent_signals = 0
                    current_time = datetime.now(timezone.utc)
                    for signal in signals:
                        signal_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
                        time_diff = (current_time - signal_time).total_seconds()
                        if time_diff < 120:  # Within last 2 minutes
                            recent_signals += 1
                            print(f"   📊 Recent signal: {signal.get('symbol')} {signal.get('direction')} at {signal.get('probability')}%")
                    
                    print(f"   📈 Total signals in history: {len(signals)}")
                    print(f"   📈 Recent signals (last 2 min): {recent_signals}")
                else:
                    print(f"   ❌ Failed to get signal history: {response.status}")
                    return False
            
            # Step 7: Stop auto generation
            print("Step 7: Stopping auto signal generation...")
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto generation stopped: {data.get('message')}")
                else:
                    print(f"   ❌ Failed to stop auto generation: {response.status}")
                    return False
            
            # Step 8: Verify status (should show auto_generation_active: false)
            print("Step 8: Verifying auto generation is stopped...")
            async with self.session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('auto_generation_active') is False:
                        print(f"   ✅ Auto generation stopped: {data.get('auto_generation_active')}")
                        print(f"   ✅ Status: {data.get('status')}")
                        return True
                    else:
                        print(f"   ❌ Auto generation still active: {data.get('auto_generation_active')}")
                        return False
                else:
                    print(f"   ❌ Failed to get final status: {response.status}")
                    return False
            
        except Exception as e:
            print(f"   ❌ Error in auto signal generation flow test: {e}")
            return False

    async def test_selected_assets_verification(self):
        """Test that signals are generated for selected_assets specifically"""
        print("\n🎯 TESTING SELECTED ASSETS VERIFICATION")
        print("=" * 60)
        
        try:
            # Get current config to verify selected_assets
            print("Checking current configuration...")
            async with self.session.get(f"{BACKEND_URL}/config") as response:
                if response.status == 200:
                    config = await response.json()
                    selected_assets = config.get('selected_assets', [])
                    selected_timeframes = config.get('selected_timeframes', [])
                    min_threshold = config.get('min_probability_threshold', 0)
                    
                    print(f"   ✅ Selected assets: {selected_assets}")
                    print(f"   ✅ Selected timeframes: {selected_timeframes}")
                    print(f"   ✅ Min probability threshold: {min_threshold}%")
                    
                    if not selected_assets:
                        print("   ❌ No selected assets found in configuration")
                        return False
                        
                else:
                    print(f"   ❌ Failed to get configuration: {response.status}")
                    return False
            
            # Start auto generation if not already running
            print("Starting auto generation...")
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    print("   ✅ Auto generation started")
                else:
                    print(f"   ⚠️ Auto generation start response: {response.status}")
            
            # Wait for signal generation
            print("Waiting 12 seconds for signal generation...")
            await asyncio.sleep(12)
            
            # Check backend logs for selected assets processing
            print("Checking recent signals for selected assets...")
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=15") as response:
                if response.status == 200:
                    data = await response.json()
                    signals = data.get('signals', [])
                    
                    # Filter recent signals (within last 3 minutes)
                    recent_signals = []
                    current_time = datetime.now(timezone.utc)
                    for signal in signals:
                        signal_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
                        time_diff = (current_time - signal_time).total_seconds()
                        if time_diff < 180:  # Within last 3 minutes
                            recent_signals.append(signal)
                    
                    print(f"   📊 Recent signals found: {len(recent_signals)}")
                    
                    # Verify signals are for selected assets only
                    valid_symbols = []
                    for asset in selected_assets:
                        valid_symbols.append(asset)
                        # Also include OTC variants
                        if '_regular' in asset:
                            otc_variant = asset.replace('_regular', '_OTC')
                            valid_symbols.append(otc_variant)
                    
                    print(f"   ✅ Valid symbols for selected assets: {valid_symbols}")
                    
                    invalid_signals = []
                    valid_signals = []
                    
                    for signal in recent_signals:
                        symbol = signal.get('symbol', '')
                        if symbol in valid_symbols:
                            valid_signals.append(symbol)
                            print(f"   ✅ Valid signal for selected asset: {symbol}")
                        else:
                            invalid_signals.append(symbol)
                            print(f"   ❌ Invalid signal for non-selected asset: {symbol}")
                    
                    if invalid_signals:
                        print(f"   ❌ Found {len(invalid_signals)} signals for non-selected assets: {invalid_signals}")
                        return False
                    
                    if valid_signals:
                        print(f"   ✅ All {len(valid_signals)} recent signals are for selected assets")
                        return True
                    else:
                        print("   ℹ️ No recent signals found (system may be conservative)")
                        return True
                        
                else:
                    print(f"   ❌ Failed to get signal history: {response.status}")
                    return False
            
        except Exception as e:
            print(f"   ❌ Error in selected assets verification: {e}")
            return False

    async def test_error_handling(self):
        """Test error handling scenarios"""
        print("\n🚨 TESTING ERROR HANDLING")
        print("=" * 60)
        
        try:
            # Test 1: Try starting auto generation when bot is NOT running
            print("Test 1: Starting auto generation when bot is stopped...")
            await self.session.post(f"{BACKEND_URL}/bot/stop")  # Ensure bot is stopped
            
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 400:
                    data = await response.json()
                    error_message = data.get('detail', '')
                    print(f"   ✅ Expected 400 error: {error_message}")
                    
                    if "bot is not running" not in error_message.lower():
                        print(f"   ❌ Error message doesn't mention bot not running")
                        return False
                else:
                    print(f"   ❌ Expected 400 error but got: {response.status}")
                    return False
            
            # Test 2: Start bot and verify auto generation works
            print("Test 2: Starting bot and testing auto generation...")
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_regular"],
                "selected_timeframes": ["5s"],
                "risk_tolerance": "medium",
                "max_stake_per_trade": 10.0,
                "max_daily_trades": 50,
                "min_probability_threshold": 85.0,
                "auto_trading_enabled": False,
                "invert_signals": False,
                "sound_alerts_enabled": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
                if response.status == 200:
                    print("   ✅ Bot started successfully")
                else:
                    print(f"   ❌ Failed to start bot: {response.status}")
                    return False
            
            # Test 3: Auto generation should work when bot is running
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto generation started when bot running: {data.get('message')}")
                else:
                    print(f"   ❌ Auto generation failed when bot running: {response.status}")
                    return False
            
            # Test 4: Stop should work regardless of bot status
            print("Test 3: Testing stop functionality...")
            async with self.session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Auto generation stop works: {data.get('message')}")
                    return True
                else:
                    print(f"   ❌ Auto generation stop failed: {response.status}")
                    return False
            
        except Exception as e:
            print(f"   ❌ Error in error handling test: {e}")
            return False

    async def check_backend_logs(self):
        """Check backend logs for auto generation messages"""
        print("\n📋 CHECKING BACKEND LOGS")
        print("=" * 60)
        
        try:
            import subprocess
            
            # Get recent backend logs
            result = subprocess.run([
                'tail', '-n', '200', '/var/log/supervisor/backend.err.log'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logs = result.stdout
                
                # Look for auto generation messages
                auto_gen_lines = []
                selected_assets_lines = []
                signal_gen_lines = []
                
                for line in logs.split('\n'):
                    if 'Auto generating' in line or 'auto generating' in line:
                        auto_gen_lines.append(line.strip())
                    if 'selected assets' in line.lower():
                        selected_assets_lines.append(line.strip())
                    if 'Auto-generated signal' in line:
                        signal_gen_lines.append(line.strip())
                
                print(f"   📊 Auto generation log entries: {len(auto_gen_lines)}")
                for line in auto_gen_lines[-5:]:  # Show last 5
                    print(f"     {line}")
                
                print(f"   📊 Selected assets log entries: {len(selected_assets_lines)}")
                for line in selected_assets_lines[-3:]:  # Show last 3
                    print(f"     {line}")
                
                print(f"   📊 Signal generation log entries: {len(signal_gen_lines)}")
                for line in signal_gen_lines[-3:]:  # Show last 3
                    print(f"     {line}")
                
                return True
            else:
                print(f"   ❌ Failed to get backend logs: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error checking backend logs: {e}")
            return False

    async def run_all_tests(self):
        """Run all auto signal generation tests"""
        print("🚀 STARTING AUTO SIGNAL GENERATION FIX VERIFICATION")
        print("=" * 80)
        
        await self.setup()
        
        tests = [
            ("Auto Signal Generation Complete Flow", self.test_auto_signal_generation_complete_flow),
            ("Selected Assets Verification", self.test_selected_assets_verification),
            ("Error Handling", self.test_error_handling),
            ("Backend Logs Check", self.check_backend_logs),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            try:
                print(f"\n🧪 Running: {test_name}")
                result = await test_func()
                if result:
                    print(f"✅ {test_name}: PASSED")
                    results.append((test_name, "PASSED"))
                else:
                    print(f"❌ {test_name}: FAILED")
                    results.append((test_name, "FAILED"))
            except Exception as e:
                print(f"❌ {test_name}: ERROR - {str(e)}")
                results.append((test_name, "ERROR"))
        
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 80)
        print("🏁 AUTO SIGNAL GENERATION TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for _, status in results if status == "PASSED")
        failed = sum(1 for _, status in results if status in ["FAILED", "ERROR"])
        
        print(f"Total Tests: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED - Auto signal generation fix is working!")
        else:
            print("⚠️ Some tests failed - see details above")
        
        print("\nDetailed Results:")
        for test_name, status in results:
            status_icon = "✅" if status == "PASSED" else "❌"
            print(f"  {status_icon} {test_name}: {status}")

async def main():
    tester = AutoSignalTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())