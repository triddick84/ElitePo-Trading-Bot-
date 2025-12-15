# 🔐 Pocket Option Authentication Guide (CORRECTED)

## The Problem
Your SSID (Session ID) is needed for API authentication. The SSID is a **cookie value**, not a WebSocket message.

## ✅ CORRECT Method: Get SSID from Cookies

### Step-by-Step Instructions:

1. **Open Pocket Option** in your browser (Chrome or Brave recommended)
   - Go to: https://pocketoption.com/
   - **Log in to your account**

2. **Open Developer Tools** 
   - Press `F12` or `Right-click` → `Inspect`
   - Click on the **"Application"** tab (NOT Network!)

3. **Navigate to Cookies**
   - In the left-hand menu, under **"Storage"**, expand **"Cookies"**
   - Click on **"https://pocketoption.com"**

4. **Find the SSID Cookie**
   - In the list of cookies, look for the entry named **"ssid"** (lowercase)
   - You should see columns: Name, Value, Domain, Path, Expires, etc.

5. **Copy the SSID Value**
   - Click on the **"ssid"** row
   - In the "Value" column, you'll see a long string like: `A4zP7dZSXxYCq0X5z` or similar
   - **Copy this entire value** (it's usually 17-20 characters)

6. **If You Don't See SSID**:
   - Refresh the Pocket Option page
   - Navigate to your trading profile or dashboard
   - Disable any ad blockers
   - Make sure you're fully logged in

## 📝 What to Send Me:

Just the SSID value (cookie value), for example:
```
A4zP7dZSXxYCq0X5z
```

NOT the WebSocket message! Just the cookie value.

## 🔧 How to Test It:

Once you provide the SSID, I'll test it with:
```bash
curl -X POST "YOUR_API_URL/api/pocket-option/quick-auth-test" \
  -H "Content-Type: application/json" \
  -d '{"auth_message": "42[\"auth\",{\"session\":\"YOUR_SSID_HERE\",\"isDemo\":1,\"uid\":53953294,\"platform\":1}]"}'
```

Or you can update it directly in `/app/backend/.env`:
```
POCKET_OPTION_SSID=YOUR_NEW_SSID_HERE
```

## ⚠️ Important Notes:

- **Cookie-based SSID** may have longer validity than WebSocket tokens
- **Stay logged in**: Keep your Pocket Option browser tab open to maintain the session
- **Demo vs Live**: Make sure you're logged into the correct account type
- **Refresh regularly**: SSID still expires eventually, but may last longer than WebSocket tokens

## 🎯 What Happens Next:

Once you provide the fresh SSID:
1. I'll update it in the environment
2. Test the connection immediately
3. The auto-refresh system will use Selenium to get new SSIDs automatically
4. Enable real-time data streaming and order execution

---

**Ready?** Get the SSID from **Application → Cookies → ssid** and send it to me! ⚡
