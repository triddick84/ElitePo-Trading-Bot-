#!/usr/bin/env python3
"""
Detailed test to understand the SELL bias issue
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://sigbot.preview.emergentagent.com/api"

async def test_bias_detailed():
    """Test to understand the bias issue in detail"""
    
    print("🔍 DETAILED BIAS ANALYSIS")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Configure for 1m timeframe
        config_data = {
            "trading_mode": "demo",
            "active_strategies": ["hybrid"],
            "target_assets": ["forex", "crypto"],
            "selected_assets": ["EURUSD_regular", "GBPUSD_regular", "BTCUSD_regular"],
            "selected_timeframes": ["1m"],
            "risk_tolerance": "medium",
            "max_stake_per_trade": 10.0,
            "max_daily_trades": 50,
            "min_probability_threshold": 75.0,
            "auto_trading_enabled": False,
            "invert_signals": False,
            "sound_alerts_enabled": True
        }
        
        await session.put(f"{BACKEND_URL}/config", json=config_data)
        
        print("🔄 Testing main force-generate endpoint (5 times):")
        main_results = []
        for i in range(5):
            async with session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') and data.get('signal'):
                        signal = data.get('signal')
                        direction = signal.get('direction', '').upper()
                        symbol = signal.get('symbol', '')
                        confidence = signal.get('probability', 0)
                        main_results.append({'direction': direction, 'symbol': symbol, 'confidence': confidence})
                        print(f"  {i+1}: {direction} ({symbol}, {confidence}%)")
                    else:
                        print(f"  {i+1}: No signal")
                else:
                    print(f"  {i+1}: Error {response.status}")
            await asyncio.sleep(0.3)
        
        print(f"\n🎯 Testing individual asset endpoints:")
        individual_results = []
        for asset in ["EURUSD_regular", "GBPUSD_regular", "BTCUSD_regular"]:
            print(f"  {asset}:", end=" ")
            async with session.post(f"{BACKEND_URL}/signals/force-generate/asset/{asset}") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') and data.get('signal'):
                        signal = data.get('signal')
                        direction = signal.get('direction', '').upper()
                        confidence = signal.get('probability', 0)
                        individual_results.append({'direction': direction, 'asset': asset, 'confidence': confidence})
                        print(f"{direction} ({confidence}%)")
                    else:
                        print("No signal")
                else:
                    print(f"Error {response.status}")
        
        # Analysis
        print(f"\n📊 ANALYSIS:")
        
        # Main endpoint analysis
        main_directions = [r['direction'] for r in main_results]
        main_call_count = sum(1 for d in main_directions if d in ['CALL', 'BUY'])
        main_put_count = sum(1 for d in main_directions if d in ['PUT', 'SELL'])
        
        print(f"Main endpoint (/signals/force-generate):")
        print(f"  CALL/BUY: {main_call_count}")
        print(f"  PUT/SELL: {main_put_count}")
        print(f"  Directions: {main_directions}")
        
        # Individual endpoint analysis
        individual_directions = [r['direction'] for r in individual_results]
        individual_call_count = sum(1 for d in individual_directions if d in ['CALL', 'BUY'])
        individual_put_count = sum(1 for d in individual_directions if d in ['PUT', 'SELL'])
        
        print(f"\nIndividual endpoints (/signals/force-generate/asset/X):")
        print(f"  CALL/BUY: {individual_call_count}")
        print(f"  PUT/SELL: {individual_put_count}")
        print(f"  Directions: {individual_directions}")
        
        # Conclusion
        print(f"\n🎯 CONCLUSION:")
        if main_call_count == 0 and main_put_count > 0:
            print("❌ Main endpoint shows SELL bias (all PUT/SELL signals)")
        elif main_call_count > 0 and main_put_count > 0:
            print("✅ Main endpoint shows mixed signals (bias fixed)")
        else:
            print("⚠️ Main endpoint results inconclusive")
            
        if individual_call_count > 0 and individual_put_count > 0:
            print("✅ Individual endpoints show mixed signals (working correctly)")
        else:
            print("⚠️ Individual endpoints may have bias")
        
        # Check if the issue is specific to the main endpoint
        if main_call_count == 0 and individual_call_count > 0:
            print("\n🔍 DIAGNOSIS: The SELL bias appears to be in the main force-generate endpoint")
            print("   Individual asset endpoints work correctly, but the main endpoint has bias")
            print("   This suggests the issue is in the asset selection or fallback logic")
        
        return main_call_count > 0  # Return True if we got at least one CALL from main endpoint

if __name__ == "__main__":
    asyncio.run(test_bias_detailed())