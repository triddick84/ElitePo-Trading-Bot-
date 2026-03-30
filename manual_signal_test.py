#!/usr/bin/env python3
"""
Focused test for manual signal generation endpoints
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://pocket-option-auto-2.preview.emergentagent.com/api"

async def test_manual_signal_endpoints():
    """Test the manual signal generation endpoints in sequence"""
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Manual Signal Generation Endpoints")
        print("=" * 50)
        
        # 1. Check initial auto generation status (should be false)
        print("\n1. Checking initial auto generation status...")
        async with session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
            data = await response.json()
            print(f"   Auto generation active: {data.get('auto_generation_active')}")
            print(f"   Bot running: {data.get('bot_running')}")
            print(f"   Status: {data.get('status')}")
            assert data.get('auto_generation_active') is False, "Auto generation should be false initially"
        
        # 2. Try single signal generation with bot stopped (should fail)
        print("\n2. Testing single signal generation with bot stopped...")
        await session.post(f"{BACKEND_URL}/bot/stop")
        async with session.post(f"{BACKEND_URL}/signals/generate/single") as response:
            assert response.status == 400, f"Expected 400 but got {response.status}"
            data = await response.json()
            print(f"   ✅ Got expected error: {data.get('detail')}")
        
        # 3. Start the bot
        print("\n3. Starting the bot...")
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
        
        async with session.post(f"{BACKEND_URL}/bot/start", json=config_data) as response:
            data = await response.json()
            print(f"   ✅ Bot started: {data.get('message')}")
        
        # 4. Test single signal generation with bot running
        print("\n4. Testing single signal generation with bot running...")
        async with session.post(f"{BACKEND_URL}/signals/generate/single") as response:
            assert response.status == 200, f"Expected 200 but got {response.status}"
            data = await response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
            if data.get('signal'):
                signal = data.get('signal')
                print(f"   Signal ID: {signal.get('id')}")
                print(f"   Symbol: {signal.get('symbol')}")
                print(f"   Direction: {signal.get('direction')}")
        
        # 5. Start auto generation
        print("\n5. Starting auto generation...")
        async with session.post(f"{BACKEND_URL}/signals/auto-generate/start") as response:
            assert response.status == 200, f"Expected 200 but got {response.status}"
            data = await response.json()
            print(f"   ✅ Auto generation started: {data.get('message')}")
            assert data.get('status') == 'active', "Status should be active"
        
        # 6. Check status (should be true)
        print("\n6. Checking status after start...")
        async with session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
            data = await response.json()
            print(f"   Auto generation active: {data.get('auto_generation_active')}")
            print(f"   Status: {data.get('status')}")
            assert data.get('auto_generation_active') is True, "Auto generation should be true"
            assert data.get('status') == 'active', "Status should be active"
        
        # 7. Stop auto generation
        print("\n7. Stopping auto generation...")
        async with session.post(f"{BACKEND_URL}/signals/auto-generate/stop") as response:
            assert response.status == 200, f"Expected 200 but got {response.status}"
            data = await response.json()
            print(f"   ✅ Auto generation stopped: {data.get('message')}")
            assert data.get('status') == 'stopped', "Status should be stopped"
        
        # 8. Verify status returns to false
        print("\n8. Verifying status after stop...")
        async with session.get(f"{BACKEND_URL}/signals/auto-generate/status") as response:
            data = await response.json()
            print(f"   Auto generation active: {data.get('auto_generation_active')}")
            print(f"   Status: {data.get('status')}")
            assert data.get('auto_generation_active') is False, "Auto generation should be false"
            assert data.get('status') == 'stopped', "Status should be stopped"
        
        print("\n🎉 All manual signal generation tests passed!")

if __name__ == "__main__":
    asyncio.run(test_manual_signal_endpoints())