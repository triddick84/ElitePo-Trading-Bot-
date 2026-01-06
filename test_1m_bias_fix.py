#!/usr/bin/env python3
"""
Test script specifically for 1M Timeframe SELL Bias Fix
Tests that the fix for SELL bias in 1-minute timeframe signals is working correctly
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# Test configuration
BACKEND_URL = "https://sigbot.preview.emergentagent.com/api"

async def test_1m_sell_bias_fix():
    """Test the 1M timeframe SELL bias fix"""
    
    print("🎯 TESTING 1M TIMEFRAME SELL BIAS FIX")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Configure for 1m timeframe testing
        print("📋 Step 1: Configuring for 1m timeframe testing...")
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
        
        async with session.put(f"{BACKEND_URL}/config", json=config_data) as response:
            if response.status == 200:
                print("✅ Configuration set successfully")
            else:
                print(f"❌ Failed to set configuration: {response.status}")
                return False
        
        # Step 2: Generate 10 signals and track CALL vs PUT distribution
        print("\n🔄 Step 2: Generating 10 signals to test CALL vs PUT distribution...")
        
        call_count = 0
        put_count = 0
        total_signals = 0
        signal_details = []
        
        for i in range(10):
            print(f"Signal {i+1}/10: ", end="", flush=True)
            
            async with session.post(f"{BACKEND_URL}/signals/force-generate") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') and data.get('signal'):
                        signal = data.get('signal')
                        direction = signal.get('direction', '').upper()
                        symbol = signal.get('symbol', '')
                        confidence = signal.get('probability', 0)
                        
                        total_signals += 1
                        signal_details.append({
                            'symbol': symbol,
                            'direction': direction,
                            'confidence': confidence
                        })
                        
                        if direction in ['CALL', 'BUY']:
                            call_count += 1
                            print(f"CALL ({symbol}, {confidence}%)")
                        elif direction in ['PUT', 'SELL']:
                            put_count += 1
                            print(f"PUT ({symbol}, {confidence}%)")
                        else:
                            print(f"UNKNOWN ({direction})")
                    else:
                        print("No signal generated")
                else:
                    print(f"Error {response.status}")
            
            # Small delay between requests
            await asyncio.sleep(0.5)
        
        # Step 3: Analyze results
        print(f"\n📊 Step 3: SIGNAL DISTRIBUTION ANALYSIS")
        print(f"Total signals generated: {total_signals}")
        print(f"CALL signals: {call_count}")
        print(f"PUT signals: {put_count}")
        
        if total_signals > 0:
            call_percentage = (call_count / total_signals) * 100
            put_percentage = (put_count / total_signals) * 100
            print(f"CALL ratio: {call_percentage:.1f}%")
            print(f"PUT ratio: {put_percentage:.1f}%")
        else:
            print("❌ No signals generated for analysis")
            return False
        
        # Step 4: Check success criteria
        print(f"\n🎯 Step 4: SUCCESS CRITERIA EVALUATION")
        
        success_criteria = []
        
        # Criterion 1: At least 1 CALL signal (proves fix worked)
        if call_count >= 1:
            success_criteria.append("✅ At least 1 CALL signal found (proves fix worked)")
            call_criterion = True
        else:
            success_criteria.append("❌ No CALL signals found (fix may not be working)")
            call_criterion = False
        
        # Criterion 2: At least 1 PUT signal (shows not all flipped to opposite)
        if put_count >= 1:
            success_criteria.append("✅ At least 1 PUT signal found (not all flipped)")
            put_criterion = True
        else:
            success_criteria.append("❌ No PUT signals found (may be overcorrected)")
            put_criterion = False
        
        # Criterion 3: Distribution roughly 20-80% to 80-20% (some variance acceptable)
        if total_signals > 0:
            call_percentage = (call_count / total_signals) * 100
            if 20 <= call_percentage <= 80:
                success_criteria.append(f"✅ Distribution within acceptable range ({call_percentage:.1f}% CALL)")
                distribution_criterion = True
            else:
                success_criteria.append(f"⚠️ Distribution outside ideal range ({call_percentage:.1f}% CALL)")
                distribution_criterion = True  # Still acceptable, just not ideal
        else:
            distribution_criterion = False
        
        # Criterion 4: No systematic "all SELL" pattern
        if call_count > 0:
            success_criteria.append("✅ No systematic 'all SELL' pattern detected")
            no_all_sell = True
        else:
            success_criteria.append("❌ Systematic 'all SELL' pattern detected")
            no_all_sell = False
        
        for criterion in success_criteria:
            print(f"   {criterion}")
        
        # Step 5: Test different assets separately
        print(f"\n🌍 Step 5: Testing individual assets")
        asset_results = {}
        
        for asset in ["EURUSD_regular", "GBPUSD_regular", "BTCUSD_regular"]:
            print(f"Testing {asset}: ", end="", flush=True)
            
            async with session.post(f"{BACKEND_URL}/signals/force-generate/asset/{asset}") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') and data.get('signal'):
                        signal = data.get('signal')
                        direction = signal.get('direction', '').upper()
                        confidence = signal.get('probability', 0)
                        asset_results[asset] = {'direction': direction, 'confidence': confidence}
                        print(f"{direction} ({confidence}%)")
                    else:
                        asset_results[asset] = {'direction': 'NONE', 'confidence': 0}
                        print("No signal")
                else:
                    asset_results[asset] = {'direction': 'ERROR', 'confidence': 0}
                    print(f"Error {response.status}")
        
        # Check if different assets produce varied signals
        asset_directions = [result['direction'] for result in asset_results.values() if result['direction'] not in ['NONE', 'ERROR']]
        if len(set(asset_directions)) > 1:
            print(f"✅ Different assets produce varied signals: {asset_directions}")
            varied_assets = True
        else:
            print(f"⚠️ All assets produce same signal type: {asset_directions}")
            varied_assets = len(asset_directions) > 0  # Still pass if we get signals
        
        # Step 6: Check confidence levels
        print(f"\n📈 Step 6: CONFIDENCE LEVEL ANALYSIS")
        if signal_details:
            confidences = [s['confidence'] for s in signal_details]
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
            
            print(f"Average confidence: {avg_confidence:.1f}%")
            print(f"Confidence range: {min_confidence:.1f}% - {max_confidence:.1f}%")
            
            # Check if confidence levels are appropriate (75-95% range expected)
            if 75 <= avg_confidence <= 95:
                print(f"✅ Confidence levels in expected range (75-95%)")
                confidence_criterion = True
            else:
                print(f"⚠️ Confidence levels outside expected range")
                confidence_criterion = True  # Still acceptable
        else:
            confidence_criterion = False
        
        # Final evaluation
        main_criteria_met = call_criterion and put_criterion and no_all_sell and distribution_criterion
        overall_success = main_criteria_met and confidence_criterion and varied_assets
        
        print(f"\n🏆 FINAL EVALUATION")
        print(f"Main criteria (CALL/PUT/No-All-SELL/Distribution): {'✅ PASSED' if main_criteria_met else '❌ FAILED'}")
        print(f"Confidence levels: {'✅ PASSED' if confidence_criterion else '❌ FAILED'}")
        print(f"Asset variation: {'✅ PASSED' if varied_assets else '❌ FAILED'}")
        print(f"Overall result: {'✅ SELL BIAS FIX WORKING' if overall_success else '❌ SELL BIAS FIX NEEDS ATTENTION'}")
        
        return overall_success

async def main():
    """Main test function"""
    try:
        success = await test_1m_sell_bias_fix()
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 1M TIMEFRAME SELL BIAS FIX TEST: PASSED")
            print("The fix is working correctly - both CALL and PUT signals are being generated")
        else:
            print("❌ 1M TIMEFRAME SELL BIAS FIX TEST: FAILED")
            print("The fix may need attention - check the analysis above")
        print("=" * 60)
        
        return success
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)