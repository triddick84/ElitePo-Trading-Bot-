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

### Setup Instructions

#### 1. Install Python
Download Python 3.10+ from https://python.org

#### 2. Install Dependencies
```bash
cd pocket_option_desktop_bot
pip install -r requirements.txt
playwright install chromium
```

#### 3. Configure Settings
Edit `config.py` with your details:
- Pocket Option email/password
- 2Captcha API key
- Cloud server URL

#### 4. Run the Bot
```bash
python main.py
```

### Features

- ✅ Auto-login with CAPTCHA solving
- ✅ Maintains persistent connection
- ✅ Polls cloud server for signals
- ✅ Executes trades automatically
- ✅ Reports results to cloud dashboard
- ✅ Reconnects on disconnection
- ✅ Telegram notifications

### Commands

While running, you can type:
- `status` - Show connection status
- `balance` - Show current balance
- `trades` - Show recent trades
- `stop` - Stop the bot
- `restart` - Restart connection

### Troubleshooting

**CAPTCHA keeps appearing:**
- Make sure your 2Captcha account has balance
- Check API key is correct

**Connection drops:**
- The bot auto-reconnects every 30 seconds
- Check your internet connection

**Trades not executing:**
- Verify cloud server is generating signals
- Check the web UI signal history
