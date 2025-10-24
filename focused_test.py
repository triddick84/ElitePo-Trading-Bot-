#!/usr/bin/env python3
"""
Focused test for Force Signal Generation with Timing Verification
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Test configuration
BACKEND_URL = "https://smart-option-signals.preview.emergentagent.com/api"

async def test_force_signal_generation_with_timing_verification():
    """Test force signal generation endpoint with focus on timing and OTC signals"""
    session = aiohttp.ClientSession()
    
    try:
        print("🧪 Testing POST /api/signals/force-generate endpoint with timing verification")
        
        # Test force signal generation
        async with session.post(f"{BACKEND_URL}/signals/force-generate") as response:
            if response.status == 200:
                data = await response.json()
                
                # Verify basic response structure
                if not data.get('success'):
                    print(f"   ❌ Force generation failed: {data.get('message')}")
                    return False
                
                signals = data.get('signals', [])
                regular_signal = data.get('regular_signal')
                otc_signal = data.get('otc_signal')
                
                print(f"   ✅ Force generation successful: {len(signals)} signals generated")
                print(f"   Message: {data.get('message')}")
                
                # Verify both regular and OTC signals are present
                if not regular_signal:
                    print("   ❌ Regular signal missing from response")
                    return False
                
                if not otc_signal:
                    print("   ❌ OTC signal missing from response")
                    return False
                
                print("   ✅ Both regular and OTC signals present")
                
                # Verify precision_entry_time fields
                for signal_type, signal in [("Regular", regular_signal), ("OTC", otc_signal)]:
                    precision_time = signal.get('precision_entry_time')
                    if not precision_time:
                        print(f"   ❌ {signal_type} signal missing precision_entry_time")
                        return False
                    
                    # Verify it's a valid ISO timestamp
                    try:
                        parsed_time = datetime.fromisoformat(precision_time.replace('Z', '+00:00'))
                        print(f"   ✅ {signal_type} signal has valid precision_entry_time: {precision_time}")
                    except ValueError:
                        print(f"   ❌ {signal_type} signal has invalid precision_entry_time format: {precision_time}")
                        return False
                
                # Verify signal storage in database
                print("   Checking signal storage in database...")
                async with session.get(f"{BACKEND_URL}/signals/history?limit=10") as history_response:
                    if history_response.status == 200:
                        history_data = await history_response.json()
                        stored_signals = history_data.get('signals', [])
                        
                        # Look for our generated signals
                        force_signals = [s for s in stored_signals if s.get('id', '').startswith('FORCE_')]
                        
                        if len(force_signals) >= 2:  # Should have both regular and OTC
                            print(f"   ✅ Found {len(force_signals)} force-generated signals in database")
                            
                            # Verify precision_entry_time in stored signals
                            for stored_signal in force_signals[:2]:  # Check first 2
                                if stored_signal.get('precision_entry_time'):
                                    print(f"   ✅ Stored signal has precision_entry_time: {stored_signal.get('precision_entry_time')}")
                                else:
                                    print(f"   ❌ Stored signal missing precision_entry_time")
                                    return False
                        else:
                            print(f"   ⚠️ Only found {len(force_signals)} force signals in database (expected 2+)")
                    else:
                        print(f"   ❌ Failed to retrieve signal history: {history_response.status}")
                        return False
                
                # Verify countdown timer data calculation
                print("   Verifying countdown timer data calculation...")
                
                for signal_type, signal in [("Regular", regular_signal), ("OTC", otc_signal)]:
                    timeframe = signal.get('timeframe')
                    expiration_minutes = signal.get('expiration_minutes')
                    precision_time = signal.get('precision_entry_time')
                    symbol = signal.get('symbol')
                    direction = signal.get('direction')
                    probability = signal.get('probability')
                    
                    if not timeframe:
                        print(f"   ❌ {signal_type} signal missing timeframe")
                        return False
                    
                    if not expiration_minutes:
                        print(f"   ❌ {signal_type} signal missing expiration_minutes")
                        return False
                    
                    print(f"   ✅ {signal_type} signal details:")
                    print(f"      Symbol: {symbol}")
                    print(f"      Direction: {direction}")
                    print(f"      Probability: {probability}%")
                    print(f"      Timeframe: {timeframe}")
                    print(f"      Expiration: {expiration_minutes} minutes")
                    print(f"      Precision Entry Time: {precision_time}")
                    
                    # Verify timeframe is appropriate for signal type
                    if signal_type == "Regular" and timeframe not in ['5m', '15m', '30m', '1h', '5s', '15s', '30s']:
                        print(f"   ⚠️ Regular signal has unusual timeframe: {timeframe}")
                    elif signal_type == "OTC" and timeframe not in ['3m', '5m', '15m', '5s', '15s', '30s']:
                        print(f"   ⚠️ OTC signal has unusual timeframe: {timeframe}")
                
                print("   ✅ All timing verification tests passed!")
                return True
                
            else:
                print(f"   ❌ Force signal generation failed with status: {response.status}")
                error_text = await response.text()
                print(f"   Error details: {error_text}")
                return False
                
    except Exception as e:
        print(f"   Force signal generation timing test error: {e}")
        return False
    finally:
        await session.close()

async def main():
    print("🚀 Starting Force Signal Generation Timing Verification Test")
    print("=" * 70)
    
    success = await test_force_signal_generation_with_timing_verification()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ FORCE SIGNAL GENERATION TIMING TEST PASSED!")
    else:
        print("❌ FORCE SIGNAL GENERATION TIMING TEST FAILED!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())