# 🚀 Quick SSID Update Guide

## Step 1: Get SSID from Browser Cookies

1. Open **Pocket Option** in Chrome/Brave: https://pocketoption.com/
2. **Login** to your account
3. Press **F12** to open Developer Tools
4. Click **"Application"** tab (top menu)
5. In left sidebar: **Storage → Cookies → https://pocketoption.com**
6. Find the cookie named **"ssid"** (lowercase)
7. **Copy the Value** (looks like: `A4zP7dZSXxYCq0X5z`)

## Step 2: Update SSID in Your App

### Option A: Via API (Easiest)
```bash
# Replace YOUR_SSID with the value you copied
curl -X POST "YOUR_BACKEND_URL/api/pocket-option/update-ssid?ssid=YOUR_SSID"
```

Example:
```bash
curl -X POST "https://your-app.com/api/pocket-option/update-ssid?ssid=A4zP7dZSXxYCq0X5z"
```

### Option B: Via Environment File
1. Edit `/app/backend/.env`
2. Update this line:
```
POCKET_OPTION_SSID=YOUR_NEW_SSID_HERE
```
3. Restart backend: `sudo supervisorctl restart backend`

## Step 3: Test Connection

```bash
curl -X POST "YOUR_BACKEND_URL/api/pocket-option/test-auto-refresh"
```

## ✅ Expected Result

If successful, you'll see:
```json
{
  "success": true,
  "message": "✅ Connection successful",
  "connection": {
    "balance": 10000.00,
    "candles_retrieved": 5
  }
}
```

## ⚠️ Troubleshooting

**If you get "Connection failed":**
1. Make sure you copied the **exact value** from the cookie
2. Make sure you're **logged in** to Pocket Option
3. Try refreshing the Pocket Option page and getting a fresh SSID
4. Check that you copied from **Cookies**, not WebSocket messages

**If SSID expires quickly:**
- Keep your Pocket Option browser tab open
- The SSID may still expire after some time
- You can enable auto-refresh (uses Selenium to automatically get new SSIDs)

## 🔄 Auto-Refresh (Advanced)

The app can automatically refresh SSID when it expires, but requires Chrome/ChromeDriver:

```bash
# Test if auto-refresh works
curl -X POST "YOUR_BACKEND_URL/api/pocket-option/auto-login"
```

If this works, the app will automatically get fresh SSIDs without manual intervention.

---

## 📝 Quick Commands Reference

```bash
# 1. Update SSID
curl -X POST "URL/api/pocket-option/update-ssid?ssid=YOUR_SSID"

# 2. Test connection
curl -X POST "URL/api/pocket-option/test-auto-refresh"

# 3. Test auto-login (Selenium)
curl -X POST "URL/api/pocket-option/auto-login"

# 4. Check status
curl "URL/api/pocket-option/status"

# 5. Get balance
curl "URL/api/pocket-option/balance"
```

Replace `URL` with your actual backend URL (from `REACT_APP_BACKEND_URL`)
