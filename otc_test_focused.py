#!/usr/bin/env python3
"""
Focused OTC Market Testing for GPT Signal Bot
Tests specifically the OTC market signal generation functionality
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://pocket-gpt-signals.preview.emergentagent.com/api"

async def test_otc_market_functionality():
    """Test OTC market signal generation functionality"""
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing OTC Market Signal Generation")
        print("=" * 50)
        
        # Test 1: General force generation with OTC support
        print("\n1. Testing general force signal generation with OTC support")
        async with session.post(f"{BACKEND_URL}/signals/force-generate") as response:
            if response.status == 200:
                data = await response.json()
                
                print(f"   Success: {data.get('success')}")
                print(f"   Message: {data.get('message')}")
                
                signals = data.get('signals', [])
                regular_signal = data.get('regular_signal')
                otc_signal = data.get('otc_signal')
                
                print(f"   Total signals: {len(signals)}")
                print(f"   Regular signal present: {regular_signal is not None}")
                print(f"   OTC signal present: {otc_signal is not None}")
                
                if regular_signal and otc_signal:
                    print("\n   Regular Signal Details:")
                    print(f"   - Symbol: {regular_signal.get('symbol')}")
                    print(f"   - Market Type: {regular_signal.get('market_type')}")
                    print(f"   - Timeframe: {regular_signal.get('timeframe')}")
                    print(f"   - Expiration: {regular_signal.get('expiration_minutes')} min")
                    print(f"   - Probability: {regular_signal.get('probability')}%")
                    
                    print("\n   OTC Signal Details:")
                    print(f"   - Symbol: {otc_signal.get('symbol')}")
                    print(f"   - Market Type: {otc_signal.get('market_type')}")
                    print(f"   - Timeframe: {otc_signal.get('timeframe')}")
                    print(f"   - Expiration: {otc_signal.get('expiration_minutes')} min")
                    print(f"   - Probability: {otc_signal.get('probability')}%")
                    
                    # Check OTC justification
                    otc_justification = otc_signal.get('justification', '')
                    if '📈 OTC Market - 24/7 availability' in otc_justification:
                        print("   ✅ OTC justification contains market availability info")
                    else:
                        print("   ❌ OTC justification missing market availability info")
                    
                    # Check analysis details for OTC boost
                    analysis_details = data.get('analysis_details', {})
                    otc_boost = analysis_details.get('otc_boost_applied', 0)
                    print(f"   OTC boost applied: {otc_boost}")
                    
                    # Verify market type differentiation
                    timeframe_diff = (regular_signal.get('timeframe') == '5m' and 
                                    otc_signal.get('timeframe') == '3m')
                    
                    expiration_diff = (otc_signal.get('expiration_minutes', 0) <= 15 and
                                     regular_signal.get('expiration_minutes', 0) >= 5)
                    
                    symbol_diff = ('_regular' in regular_signal.get('symbol', '') and
                                 '_OTC' in otc_signal.get('symbol', ''))
                    
                    print(f"\n   Market Differentiation Check:")
                    print(f"   - Timeframe difference: {timeframe_diff} (Regular: {regular_signal.get('timeframe')}, OTC: {otc_signal.get('timeframe')})")
                    print(f"   - Expiration difference: {expiration_diff}")
                    print(f"   - Symbol difference: {symbol_diff}")
                    
                    if timeframe_diff and expiration_diff and symbol_diff:
                        print("   ✅ OTC market differentiation working correctly")
                    else:
                        print("   ❌ OTC market differentiation has issues")
                else:
                    print("   ❌ Missing regular or OTC signal")
            else:
                print(f"   ❌ Force generation failed: {response.status}")
                error_text = await response.text()
                print(f"   Error: {error_text}")
        
        # Test 2: Specific asset OTC generation
        print("\n2. Testing specific asset OTC generation")
        async with session.post(f"{BACKEND_URL}/signals/force-generate/asset/EURUSD") as response:
            if response.status == 200:
                data = await response.json()
                
                regular_signal = data.get('regular_signal')
                otc_signal = data.get('otc_signal')
                
                if regular_signal and otc_signal:
                    expected_regular = "EURUSD_regular"
                    expected_otc = "EURUSD_OTC"
                    
                    regular_symbol = regular_signal.get('symbol', '')
                    otc_symbol = otc_signal.get('symbol', '')
                    
                    print(f"   Expected regular: {expected_regular}, Got: {regular_symbol}")
                    print(f"   Expected OTC: {expected_otc}, Got: {otc_symbol}")
                    
                    if expected_regular in regular_symbol and expected_otc in otc_symbol:
                        print("   ✅ Asset symbol handling working correctly")
                    else:
                        print("   ❌ Asset symbol handling has issues")
                else:
                    print("   ❌ Missing signals for specific asset test")
            else:
                print(f"   ❌ Specific asset generation failed: {response.status}")
        
        # Test 3: Database storage verification
        print("\n3. Testing database storage of OTC signals")
        await asyncio.sleep(2)  # Wait for database storage
        
        async with session.get(f"{BACKEND_URL}/signals/history?limit=5") as response:
            if response.status == 200:
                data = await response.json()
                signals = data.get('signals', [])
                
                regular_found = False
                otc_found = False
                
                for signal in signals:
                    symbol = signal.get('symbol', '')
                    market_type = signal.get('market_type', '')
                    
                    if 'regular' in symbol and market_type == 'regular':
                        regular_found = True
                        print(f"   ✅ Regular signal in database: {symbol}")
                    
                    if 'OTC' in symbol and market_type == 'otc':
                        otc_found = True
                        print(f"   ✅ OTC signal in database: {symbol}")
                        
                        # Check technical analysis
                        tech_analysis = signal.get('technical_analysis', {})
                        if tech_analysis.get('market_type') == 'otc':
                            print("   ✅ OTC market_type stored in technical_analysis")
                        if tech_analysis.get('otc_boost_applied', 0) > 0:
                            print("   ✅ OTC boost information stored")
                
                if regular_found and otc_found:
                    print("   ✅ Both signal types stored correctly in database")
                else:
                    print(f"   ❌ Missing signals in database - Regular: {regular_found}, OTC: {otc_found}")
            else:
                print(f"   ❌ Failed to retrieve signal history: {response.status}")

if __name__ == "__main__":
    asyncio.run(test_otc_market_functionality())