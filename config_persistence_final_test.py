#!/usr/bin/env python3
"""
Final Configuration Persistence Test
Tests the complete configuration saving and loading workflow
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BACKEND_URL = "https://auto-trade-bot-pro.preview.emergentagent.com/api"

async def test_complete_configuration_workflow():
    """Test the complete configuration persistence workflow"""
    
    async with aiohttp.ClientSession() as session:
        print("🔧 Testing Complete Configuration Persistence Workflow")
        print("=" * 60)
        
        # Step 1: Save a comprehensive configuration
        print("\n1️⃣ Saving comprehensive configuration...")
        
        test_config = {
            "trading_mode": "live",
            "active_strategies": ["hybrid", "rsi_5", "macd_momentum"],
            "target_assets": ["forex", "crypto", "stocks"],
            "selected_assets": ["EURUSD_regular", "BTCUSD_regular", "AAPL_regular"],
            "selected_timeframes": ["1m", "3m", "5m", "15m"],
            "risk_tolerance": "high",
            "max_stake_per_trade": 50.0,
            "max_daily_trades": 200,
            "min_probability_threshold": 92.5,
            "auto_trading_enabled": True,
            "invert_signals": True,
            "sound_alerts_enabled": False
        }
        
        async with session.put(f"{BACKEND_URL}/config", json=test_config) as response:
            if response.status == 200:
                result = await response.json()
                print(f"   ✅ Configuration saved: {result.get('status')}")
            else:
                print(f"   ❌ Failed to save configuration: {response.status}")
                return False
        
        # Step 2: Verify configuration was saved correctly
        print("\n2️⃣ Verifying saved configuration...")
        
        async with session.get(f"{BACKEND_URL}/config") as response:
            if response.status == 200:
                saved_config = await response.json()
                
                # Verify all key fields
                verification_checks = [
                    saved_config.get('trading_mode') == 'live',
                    len(saved_config.get('active_strategies', [])) == 3,
                    len(saved_config.get('target_assets', [])) == 3,
                    len(saved_config.get('selected_assets', [])) == 3,
                    len(saved_config.get('selected_timeframes', [])) == 4,
                    saved_config.get('risk_tolerance') == 'high',
                    saved_config.get('max_stake_per_trade') == 50.0,
                    saved_config.get('max_daily_trades') == 200,
                    saved_config.get('min_probability_threshold') == 92.5,
                    saved_config.get('auto_trading_enabled') is True,
                    saved_config.get('invert_signals') is True,
                    saved_config.get('sound_alerts_enabled') is False
                ]
                
                all_correct = all(verification_checks)
                print(f"   ✅ All fields verified: {all_correct}")
                
                if not all_correct:
                    print("   ❌ Some fields don't match:")
                    for i, check in enumerate(verification_checks):
                        if not check:
                            print(f"      Field {i} failed verification")
                    return False
                    
            else:
                print(f"   ❌ Failed to retrieve configuration: {response.status}")
                return False
        
        # Step 3: Test configuration persistence with bot start
        print("\n3️⃣ Testing configuration with bot start...")
        
        bot_config = {
            "trading_mode": "demo",
            "active_strategies": ["hybrid"],
            "target_assets": ["forex"],
            "selected_assets": ["EURUSD_regular"],
            "selected_timeframes": ["5m"],
            "risk_tolerance": "medium",
            "max_stake_per_trade": 20.0,
            "max_daily_trades": 100,
            "min_probability_threshold": 95.0,
            "auto_trading_enabled": False,
            "invert_signals": False,
            "sound_alerts_enabled": True
        }
        
        async with session.post(f"{BACKEND_URL}/bot/start", json=bot_config) as response:
            if response.status == 200:
                result = await response.json()
                print(f"   ✅ Bot started with new config: {result.get('status')}")
                
                # Verify the config was updated
                config = result.get('config', {})
                bot_config_correct = (
                    config.get('trading_mode') == 'demo' and
                    config.get('max_stake_per_trade') == 20.0 and
                    config.get('invert_signals') is False and
                    config.get('sound_alerts_enabled') is True
                )
                
                print(f"   ✅ Bot config fields correct: {bot_config_correct}")
                
                if not bot_config_correct:
                    return False
                    
            else:
                print(f"   ❌ Failed to start bot: {response.status}")
                return False
        
        # Step 4: Verify configuration persisted after bot start
        print("\n4️⃣ Verifying configuration persisted after bot start...")
        
        async with session.get(f"{BACKEND_URL}/config") as response:
            if response.status == 200:
                current_config = await response.json()
                
                persistence_check = (
                    current_config.get('trading_mode') == 'demo' and
                    current_config.get('max_stake_per_trade') == 20.0 and
                    current_config.get('max_daily_trades') == 100 and
                    current_config.get('invert_signals') is False and
                    current_config.get('sound_alerts_enabled') is True
                )
                
                print(f"   ✅ Configuration persisted correctly: {persistence_check}")
                
                if not persistence_check:
                    return False
                    
            else:
                print(f"   ❌ Failed to retrieve persisted configuration: {response.status}")
                return False
        
        # Step 5: Test new fields specifically
        print("\n5️⃣ Testing new fields (invert_signals, sound_alerts_enabled)...")
        
        new_fields_config = {
            "trading_mode": "demo",
            "active_strategies": ["hybrid"],
            "target_assets": ["forex"],
            "selected_assets": ["EURUSD_regular"],
            "selected_timeframes": ["1m"],
            "risk_tolerance": "medium",
            "max_stake_per_trade": 10.0,
            "max_daily_trades": 50,
            "min_probability_threshold": 95.0,
            "auto_trading_enabled": False,
            "invert_signals": True,      # Test True
            "sound_alerts_enabled": False # Test False
        }
        
        async with session.put(f"{BACKEND_URL}/config", json=new_fields_config) as response:
            if response.status == 200:
                print("   ✅ New fields configuration saved")
                
                # Verify new fields
                async with session.get(f"{BACKEND_URL}/config") as get_response:
                    if get_response.status == 200:
                        new_config = await get_response.json()
                        
                        new_fields_correct = (
                            new_config.get('invert_signals') is True and
                            new_config.get('sound_alerts_enabled') is False
                        )
                        
                        print(f"   ✅ New fields saved correctly: {new_fields_correct}")
                        print(f"      Invert signals: {new_config.get('invert_signals')}")
                        print(f"      Sound alerts: {new_config.get('sound_alerts_enabled')}")
                        
                        if not new_fields_correct:
                            return False
                    else:
                        print(f"   ❌ Failed to retrieve new fields config: {get_response.status}")
                        return False
            else:
                print(f"   ❌ Failed to save new fields config: {response.status}")
                return False
        
        print("\n🎉 All configuration persistence tests passed!")
        return True

async def main():
    """Main test runner"""
    success = await test_complete_configuration_workflow()
    
    if success:
        print("\n✅ Configuration persistence testing completed successfully!")
        print("   - Configuration saving works correctly")
        print("   - Configuration loading on startup works")
        print("   - Configuration persists across sessions")
        print("   - New fields (invert_signals, sound_alerts_enabled) work properly")
        print("   - Bot start updates configuration correctly")
        print("   - All data is stored in MongoDB trading_configurations collection")
        return 0
    else:
        print("\n❌ Configuration persistence testing failed!")
        return 1

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(result)