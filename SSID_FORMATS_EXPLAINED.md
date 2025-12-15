# 🔐 Pocket Option SSID Formats - Complete Guide

## 🎯 TL;DR - Two Ways to Get SSID

Your app supports **BOTH** formats! Use whichever is easier for you.

| Method | Where to Find | Format | Recommended |
|--------|--------------|---------|-------------|
| **Cookie** | Application → Cookies → ssid | `A4zP7dZSXxYCq0X5z` | ✅ **Easier** |
| **WebSocket** | Network → WS → Messages | `42["auth",{"session":"...",..."uid":123}]` | ✅ **More Info** |

---

## Format 1: Simple Cookie SSID ✅ RECOMMENDED

### How to Get It:
1. Open Pocket Option: https://pocketoption.com/
2. Login to your account
3. Press **F12** (Developer Tools)
4. Click **"Application"** tab
5. Sidebar: **Storage → Cookies → https://pocketoption.com**
6. Find **"ssid"** in the list
7. **Copy the Value column** (e.g., `A4zP7dZSXxYCq0X5z`)

### What It Looks Like:
```
A4zP7dZSXxYCq0X5z
```

### How to Use It:
```bash
# Update SSID
curl -X POST "YOUR_URL/api/pocket-option/update-ssid?ssid=A4zP7dZSXxYCq0X5z"

# Test it
curl -X POST "YOUR_URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "A4zP7dZSXxYCq0X5z"}'
```

### ✅ Pros:
- Simple to copy
- Clean format
- Works perfectly with AsyncPocketOptionClient (your library)

### ⚠️ Cons:
- You need to manually provide UID (from env)
- Doesn't specify demo/live account (defaults to demo)

---

## Format 2: Full WebSocket Auth Message

### How to Get It:
1. Open Pocket Option: https://pocketoption.com/
2. Login to your account
3. Press **F12** (Developer Tools)
4. Click **"Network"** tab
5. Filter: Click **"WS"** (WebSocket)
6. Click on the WebSocket connection (e.g., `socket.io`)
7. Click **"Messages"** tab
8. Find a message starting with `42["auth"`
9. **Copy the entire message**

### What It Looks Like:
```
42["auth",{"session":"a:4:{s:10:\"session_id\";s:32:\"abc123...\";s:10:\"ip_address\";s:12:\"1.2.3.4\";...}","isDemo":1,"uid":53953294,"platform":1}]
```

### Breakdown:
```javascript
42["auth",{
  "session": "a:4:{...}",  // PHP serialized session (the actual SSID)
  "isDemo": 1,             // 1 = demo, 0 = live
  "uid": 53953294,         // Your user ID
  "platform": 1            // 1 = web, 3 = mobile
}]
```

### How to Use It:
```bash
# Update SSID (note: need to escape quotes for bash)
curl -X POST "YOUR_URL/api/pocket-option/update-ssid" \
  --data-urlencode 'ssid=42["auth",{"session":"...","isDemo":1,"uid":123}]'

# Test it (JSON format - easier)
curl -X POST "YOUR_URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "42[\"auth\",{\"session\":\"...\",\"isDemo\":1,\"uid\":123}]"}'
```

### ✅ Pros:
- Contains UID automatically
- Specifies demo/live account
- Complete authentication data

### ⚠️ Cons:
- More complex to copy/paste
- Need to escape quotes in bash commands
- Longer string

---

## 📊 Comparison: Which Library Uses Which?

| Library | Required Format | Your App Uses This? |
|---------|----------------|---------------------|
| `pocketoptionapi` (stable_api) | Full WebSocket message | ❌ No |
| `pocketoptionapi-async` (ChipaDevTeam) | **Either format!** | ✅ **YES** |
| Custom `pocket_option_v2.py` | Simple cookie → builds message | ✅ Yes (backup) |

### Your Current Setup:
You're using **`pocketoptionapi-async`** which is **FLEXIBLE** - it accepts:
- Simple cookie SSID: `A4zP7dZSXxYCq0X5z`
- Full auth message: `42["auth",{...}]`

---

## 🛠️ Updated Endpoints

Both endpoints now accept **BOTH formats**:

### 1. Update SSID
```bash
# Simple cookie format
curl -X POST "URL/api/pocket-option/update-ssid?ssid=YOUR_COOKIE_VALUE"

# Full WebSocket message format  
curl -X POST "URL/api/pocket-option/update-ssid" \
  --data-urlencode 'ssid=42["auth",{...}]'
```

### 2. Test SSID
```bash
# Simple cookie format
curl -X POST "URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "YOUR_COOKIE_VALUE"}'

# Full WebSocket message format
curl -X POST "URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "42[\"auth\",{...}]"}'
```

---

## 🎯 Recommendation

### For Quick Testing:
Use **Cookie format** (simpler to copy)
- Application → Cookies → ssid
- Just copy the value
- Update: `curl -X POST "URL/api/pocket-option/update-ssid?ssid=COOKIE_VALUE"`

### For Complete Setup:
Use **WebSocket message format** (more info)
- Network → WS → Messages
- Copy entire `42["auth",{...}]` message
- Automatically includes UID and demo/live setting

---

## 🔄 How Your App Uses It

### Internally, the flow is:

**Cookie Format** (You provide):
```
A4zP7dZSXxYCq0X5z
```
↓
**App reads UID from .env**:
```
POCKET_OPTION_UID=53953294
```
↓
**AsyncPocketOptionClient builds WebSocket message**:
```javascript
{
  "session": "A4zP7dZSXxYCq0X5z",
  "isDemo": 1,
  "uid": 53953294,
  "platform": 1
}
```

**WebSocket Format** (You provide):
```
42["auth",{"session":"a:4:{...}","isDemo":1,"uid":123}]
```
↓
**App extracts all values**:
- session → saved as POCKET_OPTION_SSID
- uid → saved as POCKET_OPTION_UID
- isDemo → used for demo/live selection

---

## ⚠️ Important Notes

1. **SSID Expiration**: Both formats expire! Cookie SSID may last longer than WebSocket session.
2. **Auto-Refresh**: The app can auto-refresh using Selenium (test with `/api/pocket-option/auto-login`)
3. **Stay Logged In**: Keep Pocket Option browser tab open to maintain session
4. **UID Matters**: Make sure POCKET_OPTION_UID in .env matches your actual user ID

---

## 🧪 Quick Test Commands

```bash
# Get your backend URL
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Test with cookie format
curl -X POST "$API_URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "YOUR_COOKIE_SSID"}'

# Test with WebSocket format
curl -X POST "$API_URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "42[\"auth\",{\"session\":\"...\",\"isDemo\":1,\"uid\":123}]"}'
```

---

## ✅ Success Looks Like:

```json
{
  "success": true,
  "message": "✅ Pocket Option connection SUCCESSFUL!",
  "connection": {
    "ssid_format": "simple_cookie",
    "balance": 10000.0,
    "candles_retrieved": 5
  }
}
```

**Both formats work - use whichever is easier for you!** 🎉
