#!/usr/bin/env python3
"""
Debug specific asset generation
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://signalhub-15.preview.emergentagent.com/api"

async def debug_specific_asset():
    async with aiohttp.ClientSession() as session:
        print("🔍 Debugging specific asset generation")
        
        async with session.post(f"{BACKEND_URL}/signals/force-generate/asset/EURUSD") as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print("Full response structure:")
                print(json.dumps(data, indent=2, default=str))
            else:
                print(f"Error: {response.status}")
                print(await response.text())

if __name__ == "__main__":
    asyncio.run(debug_specific_asset())