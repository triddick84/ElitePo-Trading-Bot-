#!/usr/bin/env python3
"""
Debug the actual response structure from force signal generation
"""

import asyncio
import aiohttp
import json

BACKEND_URL = "https://signal-bot-preview.preview.emergentagent.com/api"

async def debug_response():
    async with aiohttp.ClientSession() as session:
        print("🔍 Debugging force signal generation response")
        
        async with session.post(f"{BACKEND_URL}/signals/force-generate") as response:
            if response.status == 200:
                data = await response.json()
                print("Full response structure:")
                print(json.dumps(data, indent=2, default=str))
            else:
                print(f"Error: {response.status}")
                print(await response.text())

if __name__ == "__main__":
    asyncio.run(debug_response())