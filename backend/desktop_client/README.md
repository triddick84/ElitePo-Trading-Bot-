# Pocket Option Desktop Trading Client

## Hybrid Trading System

This desktop client works with your cloud-based GPT Signal Bot to execute trades.

### How It Works

1. **Cloud Server** (your web UI) generates trading signals using your custom strategies
2. **Desktop Client** (this script) handles:
   - Logging into Pocket Option (bypasses IP blocking)
   - Solving CAPTCHAs automatically with 2Captcha
   - Executing trades based on signals from the cloud
   - Reporting results back to the cloud

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Install Python
Download Python 3.10+ from https://python.org
- ✅ Make sure to check "Add Python to PATH" during installation

### Step 2: Extract Files
Extract the downloaded ZIP to a folder on your PC, e.g.:
```
C:\Users\YourName\Desktop\pocket_option_bot\
```

### Step 3: Install Dependencies
Open Command Prompt (Windows) or Terminal (Mac/Linux) in that folder:

```bash
# Install Python packages
pip install -r requirements.txt

# IMPORTANT: Install Playwright browser (required!)
python -m playwright install chromium
```

⚠️ **The `playwright install chromium` step is REQUIRED!** This downloads the browser (~100MB) that the bot uses to login.

### Step 4: Configure Settings
Edit `config.py` with your details:
- Your Pocket Option email/password
- Your 2Captcha API key (get one at https://2captcha.com)
- Cloud server URL (already set to your server)

### Step 5: Run the Bot
```bash
python main.py
```

---

## ⚠️ Common Issues

### "Executable doesn't exist" or "Browser not installed"
**Solution:** Run this command:
```bash
python -m playwright install chromium
```

### "playwright is just installed"
**Solution:** Same as above - you need to download the browser:
```bash
python -m playwright install chromium
```

### CAPTCHA keeps appearing
- Make sure your 2Captcha account has balance
- Check API key is correct in `config.py`

### Connection drops
- The bot auto-reconnects every 30 seconds
- Check your internet connection

### Trades not executing
- Verify cloud server is generating signals
- Check the web UI signal history

---

## 📋 Features

- ✅ Auto-login with CAPTCHA solving
- ✅ Maintains persistent connection
- ✅ Polls cloud server for signals
- ✅ Executes trades automatically
- ✅ Reports results to cloud dashboard
- ✅ Reconnects on disconnection
- ✅ Telegram notifications (optional)

---

## 🎮 Commands

While running, you can type:
- `status` - Show connection status
- `balance` - Show current balance
- `trades` - Show recent trades
- `stop` - Stop the bot
- `restart` - Restart connection

---

## 📁 Files

```
pocket_option_desktop_bot/
├── main.py          # Main bot script
├── config.py        # Your settings (edit this!)
├── requirements.txt # Python dependencies
└── README.md        # This file
```

---

## 🔧 Full Installation Commands (Copy/Paste)

**Windows (Command Prompt):**
```cmd
cd C:\path\to\pocket_option_desktop_bot
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

**Mac/Linux (Terminal):**
```bash
cd ~/path/to/pocket_option_desktop_bot
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

---

## 💰 2Captcha Setup

1. Go to https://2captcha.com
2. Create an account
3. Add funds ($3-5 is enough for many logins)
4. Go to API Settings
5. Copy your API key
6. Paste it in `config.py` as `TWOCAPTCHA_API_KEY`

Each CAPTCHA solve costs ~$0.003

---

## Need Help?

If you encounter issues:
1. Check the `trading_bot.log` file for error details
2. Make sure Python 3.10+ is installed
3. Verify all dependencies are installed
4. Confirm `python -m playwright install chromium` was run
