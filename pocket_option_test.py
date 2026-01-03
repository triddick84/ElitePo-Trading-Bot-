#!/usr/bin/env python3
"""
Focused Pocket Option Integration Test
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://signalbot-36.preview.emergentagent.com/api"

async def test_pocket_option_integration():
    """Test Pocket Option integration specifically"""
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Pocket Option Integration")
        
        # Test integration status
        print("\n1. Testing Integration Status...")
        async with session.get(f"{BACKEND_URL}/integrations/status") as response:
            if response.status == 200:
                data = await response.json()
                pocket_option = data.get('integrations', {}).get('pocket_option', {})
                print(f"   Status: {pocket_option.get('status')}")
                print(f"   Account ID: {pocket_option.get('account_id')}")
                print(f"   Email: {pocket_option.get('email')}")
                if pocket_option.get('last_error'):
                    print(f"   Last Error: {pocket_option.get('last_error')}")
            else:
                print(f"   Failed: {response.status}")
        
        # Test integration initialization
        print("\n2. Testing Integration Initialization...")
        async with session.post(f"{BACKEND_URL}/integrations/test") as response:
            if response.status == 200:
                data = await response.json()
                results = data.get('results', {})
                pocket_option = results.get('pocket_option', {})
                print(f"   Status: {pocket_option.get('status')}")
                if pocket_option.get('last_error'):
                    print(f"   Error: {pocket_option.get('last_error')}")
                else:
                    print("   ✅ No errors!")
            else:
                print(f"   Failed: {response.status}")
                error_text = await response.text()
                print(f"   Error: {error_text}")

if __name__ == "__main__":
    asyncio.run(test_pocket_option_integration())