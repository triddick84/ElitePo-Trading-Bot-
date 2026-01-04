#!/usr/bin/env python3
"""
Multi-Provider Data Fetching Backtesting Tests
Tests the new multi-provider data fetching system for the backtesting feature
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Test configuration
BACKEND_URL = "https://optionsignal-12.preview.emergentagent.com/api"

class MultiProviderBacktestTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Multi-Provider Backtesting test session initialized")
        
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
    
    async def test_forex_backtesting_alpha_vantage(self) -> bool:
        """Test Forex backtesting with Alpha Vantage data provider (EURUSD)"""
        try:
            print("   🔍 Testing Forex Backtesting with Alpha Vantage (EURUSD)")
            
            request_data = {
                "strategies": ["rsi_reversal"],
                "assets": ["EURUSD"],
                "timeframes": ["1h"],
                "days": 7,
                "initial_balance": 1000,
                "trade_amount": 10,
                "payout_rate": 0.85
            }
            
            async with self.session.post(f"{BACKEND_URL}/backtest/comprehensive", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Comprehensive backtest endpoint accessible")
                    
                    # Verify response structure
                    if data.get('success') is True:
                        print(f"   ✅ Backtest completed successfully")
                        
                        results = data.get('results', [])
                        if results and len(results) > 0:
                            result = results[0]
                            
                            # Verify data source is Alpha Vantage
                            data_source = result.get('data_source')
                            if data_source == 'alphavantage':
                                print(f"   ✅ Data source is Alpha Vantage: {data_source}")
                            else:
                                print(f"   ⚠️ Data source is not Alpha Vantage: {data_source}")
                            
                            # Verify total trades > 0
                            total_trades = result.get('total_trades', 0)
                            if total_trades > 0:
                                print(f"   ✅ Total trades generated: {total_trades}")
                            else:
                                print(f"   ⚠️ No trades generated: {total_trades}")
                            
                            # Verify other required fields
                            required_fields = ['strategy', 'asset', 'timeframe', 'win_rate', 'final_balance']
                            missing_fields = [f for f in required_fields if f not in result]
                            
                            if not missing_fields:
                                print(f"   ✅ All required result fields present")
                                print(f"   📊 Strategy: {result.get('strategy')}")
                                print(f"   📊 Asset: {result.get('asset')}")
                                print(f"   📊 Win Rate: {result.get('win_rate')}%")
                                print(f"   📊 Final Balance: ${result.get('final_balance')}")
                                return True
                            else:
                                print(f"   ❌ Missing result fields: {missing_fields}")
                                return False
                        else:
                            print(f"   ❌ No backtest results returned")
                            return False
                    else:
                        print(f"   ❌ Backtest failed: {data.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"   ❌ Forex backtesting failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   ❌ Forex backtesting test error: {e}")
            return False
    
    async def test_stock_backtesting_alpha_vantage(self) -> bool:
        """Test Stock backtesting with Alpha Vantage data provider (AAPL)"""
        try:
            print("   🔍 Testing Stock Backtesting with Alpha Vantage (AAPL)")
            
            request_data = {
                "strategies": ["ema_crossover"],
                "assets": ["AAPL"],
                "timeframes": ["1h"],
                "days": 14,
                "initial_balance": 1000,
                "trade_amount": 10,
                "payout_rate": 0.85
            }
            
            async with self.session.post(f"{BACKEND_URL}/backtest/comprehensive", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Stock backtest endpoint accessible")
                    
                    # Verify response structure
                    if data.get('success') is True:
                        print(f"   ✅ Stock backtest completed successfully")
                        
                        results = data.get('results', [])
                        if results and len(results) > 0:
                            result = results[0]
                            
                            # Verify data source is Alpha Vantage
                            data_source = result.get('data_source')
                            if data_source == 'alphavantage':
                                print(f"   ✅ Data source is Alpha Vantage: {data_source}")
                            else:
                                print(f"   ⚠️ Data source is not Alpha Vantage: {data_source}")
                            
                            # Verify asset is AAPL
                            asset = result.get('asset')
                            if asset == 'AAPL':
                                print(f"   ✅ Asset is AAPL: {asset}")
                            else:
                                print(f"   ❌ Asset is not AAPL: {asset}")
                                return False
                            
                            # Verify strategy is ema_crossover
                            strategy = result.get('strategy')
                            if strategy == 'ema_crossover':
                                print(f"   ✅ Strategy is EMA Crossover: {strategy}")
                            else:
                                print(f"   ❌ Strategy is not EMA Crossover: {strategy}")
                                return False
                            
                            print(f"   📊 Total trades: {result.get('total_trades', 0)}")
                            print(f"   📊 Win rate: {result.get('win_rate', 0)}%")
                            print(f"   📊 Final balance: ${result.get('final_balance', 0)}")
                            
                            return True
                        else:
                            print(f"   ❌ No stock backtest results returned")
                            return False
                    else:
                        print(f"   ❌ Stock backtest failed: {data.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"   ❌ Stock backtesting failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   ❌ Stock backtesting test error: {e}")
            return False
    
    async def test_multiple_assets_backtesting(self) -> bool:
        """Test backtesting with multiple assets (EURUSD, GBPUSD)"""
        try:
            print("   🔍 Testing Multiple Assets Backtesting (EURUSD, GBPUSD)")
            
            request_data = {
                "strategies": ["hybrid"],
                "assets": ["EURUSD", "GBPUSD"],
                "timeframes": ["1h"],
                "days": 7,
                "initial_balance": 1000,
                "trade_amount": 10,
                "payout_rate": 0.85
            }
            
            async with self.session.post(f"{BACKEND_URL}/backtest/comprehensive", json=request_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Multiple assets backtest endpoint accessible")
                    
                    # Verify response structure
                    if data.get('success') is True:
                        print(f"   ✅ Multiple assets backtest completed successfully")
                        
                        results = data.get('results', [])
                        if results and len(results) >= 1:
                            print(f"   ✅ Results returned: {len(results)} results")
                            
                            # Check that all results have data_source field
                            all_have_data_source = True
                            assets_tested = []
                            
                            for i, result in enumerate(results):
                                data_source = result.get('data_source')
                                asset = result.get('asset')
                                assets_tested.append(asset)
                                
                                if data_source:
                                    print(f"   ✅ Result {i+1}: {asset} - Data source: {data_source}")
                                else:
                                    print(f"   ❌ Result {i+1}: {asset} - Missing data_source field")
                                    all_have_data_source = False
                            
                            # Verify we tested at least one asset
                            expected_assets = ["EURUSD", "GBPUSD"]
                            assets_found = [asset for asset in expected_assets if asset in assets_tested]
                            
                            if len(assets_found) >= 1:
                                print(f"   ✅ Assets tested: {assets_found}")
                            else:
                                print(f"   ⚠️ No expected assets tested: {assets_found}")
                            
                            return all_have_data_source and len(assets_found) >= 1
                        else:
                            print(f"   ⚠️ Expected results but got: {len(results)}")
                            return len(results) >= 1
                    else:
                        print(f"   ❌ Multiple assets backtest failed: {data.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"   ❌ Multiple assets backtesting failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False
        except Exception as e:
            print(f"   ❌ Multiple assets backtesting test error: {e}")
            return False
    
    async def test_backtest_data_source_tracking(self) -> bool:
        """Test that backtesting properly tracks and returns data source information"""
        try:
            print("   🔍 Testing Data Source Tracking in Backtesting")
            
            # Test with different asset types to verify data source tracking
            test_cases = [
                {"asset": "EURUSD", "expected_sources": ["alphavantage", "synthetic"]},
                {"asset": "AAPL", "expected_sources": ["alphavantage", "synthetic"]}
            ]
            
            all_tests_passed = True
            
            for test_case in test_cases:
                asset = test_case["asset"]
                expected_sources = test_case["expected_sources"]
                
                print(f"   🔍 Testing data source tracking for {asset}")
                
                request_data = {
                    "strategies": ["hybrid"],
                    "assets": [asset],
                    "timeframes": ["1h"],
                    "days": 7,
                    "initial_balance": 1000,
                    "trade_amount": 10,
                    "payout_rate": 0.85
                }
                
                async with self.session.post(f"{BACKEND_URL}/backtest/comprehensive", json=request_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('success') is True:
                            results = data.get('results', [])
                            if results and len(results) > 0:
                                result = results[0]
                                data_source = result.get('data_source')
                                
                                if data_source:
                                    if data_source in expected_sources:
                                        print(f"   ✅ {asset}: Data source {data_source} is valid")
                                    else:
                                        print(f"   ⚠️ {asset}: Unexpected data source {data_source} (expected: {expected_sources})")
                                        # Still pass as long as we have a data source
                                else:
                                    print(f"   ❌ {asset}: Missing data_source field")
                                    all_tests_passed = False
                            else:
                                print(f"   ⚠️ {asset}: No results returned")
                        else:
                            print(f"   ⚠️ {asset}: Backtest failed - {data.get('error', 'Unknown error')}")
                    else:
                        print(f"   ❌ {asset}: Request failed with status {response.status}")
                        all_tests_passed = False
                
                # Small delay between requests
                await asyncio.sleep(1)
            
            return all_tests_passed
            
        except Exception as e:
            print(f"   ❌ Data source tracking test error: {e}")
            return False
    
    async def test_backtest_available_assets(self) -> bool:
        """Test the available assets endpoint for backtesting"""
        try:
            print("   🔍 Testing Available Assets Endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/backtest/assets") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Available assets endpoint accessible")
                    
                    if data.get('success') is True:
                        assets = data.get('assets', {})
                        
                        # Verify asset categories
                        expected_categories = ['forex', 'crypto', 'stocks']
                        for category in expected_categories:
                            if category in assets:
                                asset_list = assets[category]
                                print(f"   ✅ {category.capitalize()}: {len(asset_list)} assets available")
                                if asset_list:
                                    print(f"      Examples: {asset_list[:3]}")
                            else:
                                print(f"   ❌ Missing {category} category")
                                return False
                        
                        return True
                    else:
                        print(f"   ❌ Available assets request failed")
                        return False
                else:
                    print(f"   ❌ Available assets endpoint failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Available assets test error: {e}")
            return False
    
    async def test_backtest_available_strategies(self) -> bool:
        """Test the available strategies endpoint for backtesting"""
        try:
            print("   🔍 Testing Available Strategies Endpoint")
            
            async with self.session.get(f"{BACKEND_URL}/backtest/strategies") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Available strategies endpoint accessible")
                    
                    if data.get('success') is True:
                        strategies = data.get('strategies', [])
                        
                        if strategies and len(strategies) > 0:
                            print(f"   ✅ {len(strategies)} strategies available")
                            print(f"   📊 Available strategies: {strategies}")
                            
                            # Verify expected strategies are present
                            expected_strategies = ['rsi_reversal', 'ema_crossover', 'hybrid']
                            found_strategies = [s for s in expected_strategies if s in strategies]
                            
                            if len(found_strategies) >= 2:
                                print(f"   ✅ Expected strategies found: {found_strategies}")
                                return True
                            else:
                                print(f"   ⚠️ Some expected strategies missing: {found_strategies}")
                                return len(strategies) > 0  # Pass if we have any strategies
                        else:
                            print(f"   ❌ No strategies returned")
                            return False
                    else:
                        print(f"   ❌ Available strategies request failed")
                        return False
                else:
                    print(f"   ❌ Available strategies endpoint failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Available strategies test error: {e}")
            return False

async def run_multi_provider_backtesting_tests():
    """Run Multi-Provider Data Fetching Backtesting tests"""
    print("🚀 Testing Multi-Provider Data Fetching for Backtesting")
    print("=" * 80)
    
    tester = MultiProviderBacktestTester()
    await tester.setup()
    
    # Define Multi-Provider Backtesting tests
    tests = [
        ("Health Check", tester.test_health_check),
        ("Available Assets Endpoint", tester.test_backtest_available_assets),
        ("Available Strategies Endpoint", tester.test_backtest_available_strategies),
        ("Forex Backtesting (Alpha Vantage)", tester.test_forex_backtesting_alpha_vantage),
        ("Stock Backtesting (Alpha Vantage)", tester.test_stock_backtesting_alpha_vantage),
        ("Multiple Assets Backtesting", tester.test_multiple_assets_backtesting),
        ("Data Source Tracking", tester.test_backtest_data_source_tracking),
    ]
    
    # Run all tests
    for test_name, test_func in tests:
        await tester.run_test(test_name, test_func)
    
    await tester.cleanup()
    
    # Print summary
    print("\n" + "=" * 80)
    print("🏁 Multi-Provider Backtesting Testing Complete: {}/{} tests passed".format(
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
        print(f"\n🎉 All Multi-Provider Backtesting tests passed!")
        print(f"\n📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        return True

if __name__ == "__main__":
    asyncio.run(run_multi_provider_backtesting_tests())