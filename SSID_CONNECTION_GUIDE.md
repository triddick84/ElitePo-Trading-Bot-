# Pocket Option SSID Connection Guide

## Overview

This guide explains how to maintain a persistent connection with Pocket Option using the BinaryOptionsToolsV2 library.

## Current Limitation

**SSID sessions expire periodically** (typically within 1-24 hours). There is currently no fully automatic way to refresh the SSID without user interaction due to:

1. Pocket Option uses reCAPTCHA on login - blocking automated login
2. SSIDs are session-based tokens that expire server-side
3. No official API endpoint for session refresh exists

## Available Solutions

### Solution 1: Manual SSID Update (Recommended)

The most reliable method is manual SSID extraction:

1. **Open Pocket Option** in your browser
2. **Login** to your account
3. **Open Developer Tools** (F12)
4. Go to **Network → WS** (WebSocket filter)
5. **Refresh the page**
6. Find the WebSocket connection
7. Look for the `42["auth",{...}]` message
8. **Copy the entire message**
9. Paste into the bot's SSID update endpoint

**API Endpoint:**
```bash
curl -X POST "YOUR_API_URL/api/pocket-option/update-ssid" \
  --data-urlencode 'ssid=42["auth",{"session":"...","isDemo":1,...}]'
```

### Solution 2: Browser Extension (User-Side)

Users can install a browser extension that:
1. Monitors Pocket Option WebSocket traffic
2. Captures fresh SSIDs automatically
3. Sends them to the bot via webhook

**Recommended Extensions:**
- Custom user script with TamperMonkey/Greasemonkey
- Chrome extension for WebSocket monitoring

### Solution 3: Local Bot with Browser Bridge

Run a local bot on your machine that:
1. Keeps a browser session open
2. Monitors for session refreshes
3. Forwards SSIDs to the cloud server

**File:** `/app/backend/pocket_option_local_bot.py`

### Solution 4: SSID Health Monitoring

The bot includes SSID health monitoring:

```python
from ssid_manager import get_ssid_manager

manager = get_ssid_manager()

# Check status
status = manager.get_status()
print(f"Valid: {status['is_valid']}")
print(f"Expiring Soon: {status['is_expiring_soon']}")

# Set callback for expiration
manager.on_ssid_expired = notify_user_to_refresh
```

## API Endpoints

### Check SSID Status
```bash
GET /api/pocket-option/ssid/status
```

### Update SSID
```bash
POST /api/pocket-option/update-ssid?ssid=YOUR_SSID_HERE
```

### Test Connection
```bash
POST /api/pocket-option/connect
{
  "auth_message": "42[\"auth\",{...}]",
  "is_demo": true
}
```

## Best Practices

1. **Set up notifications** - Configure the bot to alert you when SSID is expiring
2. **Keep browser session open** - Stay logged in to Pocket Option
3. **Use the local bot** - For more reliable execution, run the local bot
4. **Extract SSID proactively** - Get a fresh SSID before trading sessions

## Troubleshooting

### SSID Expired
- Get a fresh SSID from browser
- Make sure you're logged in
- Check if account is suspended

### Connection Timeout
- Pocket Option servers may be unreachable from cloud
- Use local bot for better connectivity
- Check your network/firewall settings

### Invalid SSID Format
- Include the full `42["auth",{...}]` message
- Don't modify the JSON structure
- Check for copy/paste errors

## Files Reference

- `/app/backend/pocket_option_api_v2.py` - API client
- `/app/backend/ssid_manager.py` - SSID management
- `/app/backend/pocket_option_local_bot.py` - Local bot script
- `/app/AUTOMATED_TRADING_GUIDE.md` - Full automation guide
