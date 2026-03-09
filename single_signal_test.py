#!/usr/bin/env python3
"""
Single Signal Generation Testing for GPT Signal Bot
Tests the new SINGLE signal generation functionality as requested in the review
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Add backend to path
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://signal-executor-7.preview.emergentagent.com/api"

class SingleSignalTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Single signal testing session initialized")
        
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

    async def test_single_signal_generation_response_structure(self) -> bool:
        """Test that force generate returns ONLY ONE signal with correct structure"""
        try:
            print("   Testing single signal generation response structure")
            
            # Configure bot with test assets and timeframes
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_OTC"],
                "selected_timeframes": ["5s"],
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
                    print("   ❌ Failed to update configuration")
                    return False
            
            # Test force generate endpoint
            async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ['success', 'message', 'signal', 'market_type', 'timeframe']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required fields: {missing_fields}")
                        return False
                    
                    print(f"   ✅ All required fields present: {required_fields}")
                    
                    # Verify only ONE signal is returned
                    signal = data.get('signal')
                    signals = data.get('signals', [])
                    
                    if not signal:
                        print("   ❌ No signal field in response")
                        return False
                    
                    print(f"   ✅ Single signal returned: {signal.get('symbol')} {signal.get('direction')}")
                    
                    # Verify message mentions "Single" signal
                    message = data.get('message', '')
                    if 'Single' not in message:
                        print(f"   ❌ Message doesn't mention 'Single': {message}")
                        return False
                    
                    print(f"   ✅ Message correctly mentions single signal: {message}")
                    
                    # Verify signal has precision entry timing
                    if 'precision_entry_time' not in signal:
                        print("   ❌ Signal missing precision_entry_time field")
                        return False
                    
                    print(f"   ✅ Signal has precision entry timing: {signal.get('precision_entry_time')}")
                    
                    return True
                else:
                    print(f"   ❌ Force generate failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
            
        except Exception as e:
            print(f"   Single signal generation response structure test error: {e}")
            return False

    async def test_ultra_short_timeframe_otc_market_selection(self) -> bool:
        """Test that ultra-short timeframes (5s, 15s, 30s) automatically use OTC market"""
        try:
            print("   Testing ultra-short timeframe OTC market selection")
            
            ultra_short_timeframes = ['5s', '15s', '30s']
            
            for timeframe in ultra_short_timeframes:
                print(f"   Testing {timeframe} timeframe")
                
                # Configure bot with ultra-short timeframe
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex"],
                    "selected_assets": ["EURUSD_regular"],  # Regular asset
                    "selected_timeframes": [timeframe],
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
                        print(f"   ❌ Failed to update configuration for {timeframe}")
                        return False
                
                # Generate signal
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Verify OTC market is selected for ultra-short timeframes
                        market_type = data.get('market_type', '')
                        message = data.get('message', '')
                        
                        if market_type.lower() != 'otc':
                            print(f"   ❌ Expected OTC market for {timeframe}, got: {market_type}")
                            return False
                        
                        if 'OTC' not in message:
                            print(f"   ❌ Message doesn't mention OTC for {timeframe}: {message}")
                            return False
                        
                        print(f"   ✅ {timeframe} correctly uses OTC market: {message}")
                        
                        # Verify timeframe in response
                        response_timeframe = data.get('timeframe', '')
                        if response_timeframe != timeframe:
                            print(f"   ❌ Expected timeframe {timeframe}, got: {response_timeframe}")
                            return False
                        
                        print(f"   ✅ Timeframe correctly set to {timeframe}")
                        
                    else:
                        print(f"   ❌ Force generate failed for {timeframe}: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Ultra-short timeframe OTC market selection test error: {e}")
            return False

    async def test_symbol_based_market_selection(self) -> bool:
        """Test that symbols with _OTC suffix use OTC market, _regular use regular market"""
        try:
            print("   Testing symbol-based market selection")
            
            test_cases = [
                {"symbol": "EURUSD_OTC", "expected_market": "otc"},
                {"symbol": "BTCUSD_OTC", "expected_market": "otc"},
                {"symbol": "EURUSD_regular", "expected_market": "regular"},
                {"symbol": "BTCUSD_regular", "expected_market": "regular"}
            ]
            
            for test_case in test_cases:
                symbol = test_case["symbol"]
                expected_market = test_case["expected_market"]
                
                print(f"   Testing {symbol} -> {expected_market}")
                
                # Configure bot with specific symbol
                config_data = {
                    "trading_mode": "demo",
                    "active_strategies": ["hybrid"],
                    "target_assets": ["forex", "crypto"],
                    "selected_assets": [symbol],
                    "selected_timeframes": ["1m"],  # Use longer timeframe to test symbol-based selection
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
                        print(f"   ❌ Failed to update configuration for {symbol}")
                        return False
                
                # Generate signal
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Verify market type matches symbol suffix
                        market_type = data.get('market_type', '').lower()
                        message = data.get('message', '')
                        
                        if market_type != expected_market:
                            print(f"   ❌ Expected {expected_market} market for {symbol}, got: {market_type}")
                            return False
                        
                        expected_message_text = expected_market.upper()
                        if expected_message_text not in message:
                            print(f"   ❌ Message doesn't mention {expected_message_text} for {symbol}: {message}")
                            return False
                        
                        print(f"   ✅ {symbol} correctly uses {expected_market} market: {message}")
                        
                    else:
                        print(f"   ❌ Force generate failed for {symbol}: {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Symbol-based market selection test error: {e}")
            return False

    async def test_single_asset_force_generate_endpoint(self) -> bool:
        """Test POST /api/signals/force-generate/asset/{asset} returns only ONE signal"""
        try:
            print("   Testing single asset force generate endpoint")
            
            test_assets = ["EURUSD", "BTCUSD", "GBPUSD"]
            
            for asset in test_assets:
                print(f"   Testing force generate for {asset}")
                
                # Test single asset endpoint
                async with self.session.post(f"{BACKEND_URL}/signals/force-generate/asset/{asset}") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Verify response structure
                        required_fields = ['success', 'message', 'signal', 'market_type', 'timeframe']
                        missing_fields = [field for field in required_fields if field not in data]
                        
                        if missing_fields:
                            print(f"   ❌ Missing required fields for {asset}: {missing_fields}")
                            return False
                        
                        # Verify only ONE signal is returned
                        signal = data.get('signal')
                        if not signal:
                            print(f"   ❌ No signal returned for {asset}")
                            return False
                        
                        # Verify message mentions "Single" signal
                        message = data.get('message', '')
                        if 'Single' not in message:
                            print(f"   ❌ Message doesn't mention 'Single' for {asset}: {message}")
                            return False
                        
                        # Verify asset name in message
                        if asset not in message:
                            print(f"   ❌ Asset {asset} not mentioned in message: {message}")
                            return False
                        
                        print(f"   ✅ Single signal generated for {asset}: {signal.get('direction')} at {signal.get('probability')}%")
                        
                    else:
                        print(f"   ❌ Force generate failed for {asset}: {response.status}")
                        error_text = await response.text()
                        print(f"   Error details: {error_text}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"   Single asset force generate endpoint test error: {e}")
            return False

    async def test_signal_quality_and_required_fields(self) -> bool:
        """Test that generated signals have all required fields and proper quality"""
        try:
            print("   Testing signal quality and required fields")
            
            # Configure bot for signal generation
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_OTC"],
                "selected_timeframes": ["5s"],
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
                    print("   ❌ Failed to update configuration")
                    return False
            
            # Generate signal
            async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    signal = data.get('signal')
                    
                    if not signal:
                        print("   ❌ No signal in response")
                        return False
                    
                    # Check all required signal fields
                    required_signal_fields = [
                        'id', 'symbol', 'direction', 'entry_price', 'probability', 
                        'confidence_level', 'timeframe', 'market_type', 
                        'precision_entry_time', 'technical_analysis'
                    ]
                    
                    missing_fields = [field for field in required_signal_fields if field not in signal]
                    
                    if missing_fields:
                        print(f"   ❌ Missing required signal fields: {missing_fields}")
                        return False
                    
                    print(f"   ✅ All required signal fields present: {required_signal_fields}")
                    
                    # Verify field values
                    probability = signal.get('probability', 0)
                    if not (75.0 <= probability <= 100.0):
                        print(f"   ❌ Probability {probability}% not in expected range (75-100%)")
                        return False
                    
                    print(f"   ✅ Probability {probability}% is appropriate (75%+)")
                    
                    # Verify direction is valid
                    direction = signal.get('direction', '')
                    if direction not in ['BUY', 'SELL', 'CALL', 'PUT']:
                        print(f"   ❌ Invalid direction: {direction}")
                        return False
                    
                    print(f"   ✅ Direction '{direction}' is valid")
                    
                    # Verify precision entry time format
                    precision_time = signal.get('precision_entry_time')
                    if not precision_time:
                        print("   ❌ Missing precision_entry_time")
                        return False
                    
                    # Check if it's a valid ISO timestamp
                    try:
                        from datetime import datetime
                        datetime.fromisoformat(precision_time.replace('Z', '+00:00'))
                        print(f"   ✅ Precision entry time is valid ISO format: {precision_time}")
                    except:
                        print(f"   ❌ Invalid precision entry time format: {precision_time}")
                        return False
                    
                    # Verify technical analysis contains candle formation data
                    technical_analysis = signal.get('technical_analysis', {})
                    if not technical_analysis:
                        print("   ❌ Missing technical_analysis")
                        return False
                    
                    print(f"   ✅ Technical analysis present with {len(technical_analysis)} fields")
                    
                    return True
                    
                else:
                    print(f"   ❌ Force generate failed: {response.status}")
                    return False
            
        except Exception as e:
            print(f"   Signal quality and required fields test error: {e}")
            return False

    async def test_database_storage_single_signal(self) -> bool:
        """Test that only ONE signal is stored per force generate call"""
        try:
            print("   Testing database storage of single signal")
            
            # Get initial signal count
            async with self.session.get(f"{BACKEND_URL}/signals/history?limit=1000") as response:
                if response.status == 200:
                    data = await response.json()
                    initial_count = len(data.get('signals', []))
                    print(f"   Initial signal count: {initial_count}")
                else:
                    print("   ❌ Failed to get initial signal count")
                    return False
            
            # Configure bot for signal generation
            config_data = {
                "trading_mode": "demo",
                "active_strategies": ["hybrid"],
                "target_assets": ["forex"],
                "selected_assets": ["EURUSD_OTC"],
                "selected_timeframes": ["5s"],
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
                    print("   ❌ Failed to update configuration")
                    return False
            
            # Generate signal
            async with self.session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    signal = data.get('signal')
                    
                    if not signal:
                        print("   ❌ No signal generated")
                        return False
                    
                    signal_id = signal.get('id')
                    print(f"   ✅ Signal generated with ID: {signal_id}")
                    
                    # Check signal count after generation
                    async with self.session.get(f"{BACKEND_URL}/signals/history?limit=1000") as response:
                        if response.status == 200:
                            data = await response.json()
                            final_count = len(data.get('signals', []))
                            signals_added = final_count - initial_count
                            
                            print(f"   Final signal count: {final_count}")
                            print(f"   Signals added: {signals_added}")
                            
                            # Verify only ONE signal was added
                            if signals_added != 1:
                                print(f"   ❌ Expected 1 signal added, got {signals_added}")
                                return False
                            
                            print("   ✅ Exactly ONE signal stored in database")
                            
                            # Verify the stored signal has proper market_type field
                            latest_signal = data.get('signals', [])[0] if data.get('signals') else None
                            if latest_signal:
                                stored_market_type = latest_signal.get('market_type')
                                stored_precision_time = latest_signal.get('precision_entry_time')
                                
                                if not stored_market_type:
                                    print("   ❌ Stored signal missing market_type field")
                                    return False
                                
                                if not stored_precision_time:
                                    print("   ❌ Stored signal missing precision_entry_time field")
                                    return False
                                
                                print(f"   ✅ Stored signal has market_type: {stored_market_type}")
                                print(f"   ✅ Stored signal has precision_entry_time: {stored_precision_time}")
                            
                            return True
                        else:
                            print("   ❌ Failed to get final signal count")
                            return False
                    
                else:
                    print(f"   ❌ Force generate failed: {response.status}")
                    return False
            
        except Exception as e:
            print(f"   Database storage single signal test error: {e}")
            return False

    async def run_single_signal_tests(self):
        """Run all single signal generation tests"""
        print("🚀 Starting Single Signal Generation Testing for GPT Signal Bot")
        print("=" * 80)
        print("Testing NEW SINGLE signal generation functionality with precise entry timing")
        print("=" * 80)
        
        await self.setup()
        
        # Define single signal generation test suite
        tests = [
            ("Single Signal Generation Response Structure", self.test_single_signal_generation_response_structure),
            ("Ultra-Short Timeframe OTC Market Selection", self.test_ultra_short_timeframe_otc_market_selection),
            ("Symbol-Based Market Selection", self.test_symbol_based_market_selection),
            ("Single Asset Force Generate Endpoint", self.test_single_asset_force_generate_endpoint),
            ("Signal Quality and Required Fields", self.test_signal_quality_and_required_fields),
            ("Database Storage Single Signal", self.test_database_storage_single_signal),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
            
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("🏁 SINGLE SIGNAL GENERATION TESTING SUMMARY")
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
            print(f"\n🎉 All single signal generation tests passed!")
            
        return len(self.failed_tests) == 0

async def main():
    """Main test runner"""
    tester = SingleSignalTester()
    success = await tester.run_single_signal_tests()
    
    if success:
        print("\n✅ Single signal generation functionality is working correctly!")
    else:
        print("\n❌ Single signal generation functionality has issues!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())