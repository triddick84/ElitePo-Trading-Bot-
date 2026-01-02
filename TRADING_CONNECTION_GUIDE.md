# 🚀 Pocket Option Trading Bot - Complete Connection Guide

## Overview

This guide explains how to connect and start automated trading with your GPT Signal Bot.

---

## Current System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Trading Strategies | ✅ Ready | 5-second & 1-minute strategies with S/R filtering |
| Signal Generation | ✅ Ready | High-probability signals generated |
| Health Monitoring | ✅ Ready | Alerts on SSID expiry and connection issues |
| Auto Reconnection | ✅ Ready | Attempts reconnect on connection loss |
| SSID Auto-Refresh | ⚠️ Manual | Requires manual browser extraction |
| Live Trading | ⚠️ Needs SSID | Requires valid SSID to execute trades |

---

## Connection Methods

### Method 1: Cloud Bot (This Server) - Recommended for Monitoring

**Pros:** Always running, accessible anywhere, generates signals
**Cons:** Needs manual SSID update every few hours

#### Step 1: Get Your SSID

1. Open **https://pocketoption.com** in Chrome/Firefox
2. **Login** to your account
3. Press **F12** (Developer Tools)
4. Go to **Network** tab
5. Click **WS** filter (WebSocket)
6. **Refresh the page** (F5)
7. Find WebSocket connection (wss://...)
8. Click on it → **Messages** tab
9. Find message: `42["auth",{"session":"...`
10. **Copy the ENTIRE message**

#### Step 2: Update SSID via API

```bash
# Using curl
curl -X POST "YOUR_API_URL/api/pocket-option/update-ssid" \
  --data-urlencode 'ssid=42["auth",{"session":"YOUR_SESSION","isDemo":1}]'
```

Or use the **Frontend Dashboard** → **SSID Connection Manager** component.

#### Step 3: Verify Connection

```bash
curl "YOUR_API_URL/api/pocket-option/status"
# Should show: "connected": true
```

#### Step 4: Start Auto Trading

```bash
curl -X POST "YOUR_API_URL/api/trading/auto/start"
```

---

### Method 2: Local Bot - Recommended for Execution

**Pros:** Better connection stability, runs on your machine
**Cons:** Requires your computer to be running

#### Step 1: Download Local Bot

```bash
# Option A: From API
curl "YOUR_API_URL/api/local-bot/download" | python3 -c "import sys,json; print(json.load(sys.stdin)['content'])" > pocket_option_local_bot.py

# Option B: Copy from server
# File location: /app/backend/local_bot/pocket_option_local_bot.py
```

#### Step 2: Install Dependencies

```bash
pip install websockets aiohttp requests pyperclip
```

#### Step 3: Run the Bot

```bash
python pocket_option_local_bot.py
```

#### Step 4: Follow Interactive Setup

The bot will:
1. Ask for your cloud server URL (optional)
2. Guide you to get SSID from browser
3. Connect to Pocket Option
4. Start fetching signals and executing trades

---

## API Endpoints Reference

### Connection Management

```bash
# Get connection status
GET /api/pocket-option/status

# Update SSID
POST /api/pocket-option/update-ssid?ssid=YOUR_SSID&is_demo=true

# Test connection
POST /api/pocket-option/test-connection

# Connect with full auth message
POST /api/pocket-option/connect
Body: {"auth_message": "42[\"auth\",...", "is_demo": true}
```

### Health Monitoring

```bash
# Get health status
GET /api/ssid/health/status

# Get alerts
GET /api/ssid/health/alerts?limit=50

# Start health monitor
POST /api/ssid/health/start

# Stop health monitor
POST /api/ssid/health/stop
```

### Trading

```bash
# Start auto trading
POST /api/trading/auto/start

# Stop auto trading
POST /api/trading/auto/stop

# Execute manual trade
POST /api/trading/execute
Body: {"asset": "EURUSD_otc", "direction": "call", "amount": 1, "expiration": 60}
```

### Signal Generation

```bash
# Get best 1-minute signal
POST /api/strategy/1m-high-probability/generate?asset=EURUSD&strategy=best

# Get consensus signal (multiple strategies agree)
POST /api/strategy/1m-high-probability/generate?asset=EURUSD&strategy=consensus

# Analyze with all strategies
POST /api/strategy/1m-high-probability/analyze-all?asset=EURUSD
```

---

## SSID Troubleshooting

### "SSID expired or invalid"

1. Login to Pocket Option in browser
2. Get a **fresh SSID** (follow steps above)
3. Update via API or frontend

### "Connection timeout"

- Check internet connection
- Try VPN if Pocket Option is blocked in your region
- Check if Pocket Option servers are up

### "Authentication failed"

- Make sure you copied the **complete** message including `42["auth",...`
- Check if you're using correct account type (demo/real)
- Try logging out and back into Pocket Option

### SSID keeps expiring quickly

- This is normal - SSIDs expire after 1-24 hours
- Use the **Local Bot** for better session management
- Enable health monitor alerts to know when to refresh

---

## Best Practices

### For Demo Trading (Testing)

1. Always start with demo account (`is_demo: true`)
2. Test all strategies with small amounts
3. Monitor performance for at least 1 week before real trading

### For Real Trading

1. ⚠️ **Risk Warning**: Binary options involve significant risk
2. Start with small amounts (1-2% of account per trade)
3. Set up alerts for SSID expiry
4. Keep a browser tab open with Pocket Option logged in
5. Monitor trades actively

### For SSID Management

1. Get SSID right after logging in (freshest possible)
2. Set up health monitor alerts
3. Keep Pocket Option tab open in browser
4. Have SSID extraction instructions bookmarked

---

## Files Reference

| File | Purpose |
|------|---------|
| `/app/backend/pocket_option_api_v2.py` | API client with keep-alive |
| `/app/backend/ssid_health_monitor.py` | Health monitoring & alerts |
| `/app/backend/local_bot/pocket_option_local_bot.py` | Standalone local bot |
| `/app/frontend/src/components/SSIDConnectionManager.jsx` | Frontend SSID UI |
| `/app/SSID_CONNECTION_GUIDE.md` | Quick reference guide |

---

## Support

### Common Issues

1. **Can't extract SSID**: Make sure you're on the correct WebSocket message
2. **Bot disconnects**: SSID expired - get fresh one
3. **Trades not executing**: Check connection status first
4. **Signals not generating**: Market data may be unavailable

### Getting Help

- Check API docs: `YOUR_API_URL/api/docs`
- Review logs: `/var/log/supervisor/backend.err.log`
- Test endpoints: Use the curl commands above

---

## Quick Start Checklist

- [ ] Get SSID from Pocket Option browser
- [ ] Update SSID via API or frontend
- [ ] Verify connection shows `connected: true`
- [ ] Start health monitor for alerts
- [ ] Test with demo account first
- [ ] Start auto trading when ready

---

*Last Updated: January 2026*
