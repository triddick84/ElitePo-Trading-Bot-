"""
Local Bot README and Setup Instructions
========================================
"""

README_CONTENT = """
# 🤖 Pocket Option Local Trading Bot

A standalone trading bot that runs on YOUR local machine for better reliability and connection stability.

## Why Run Locally?

| Feature | Cloud Bot | Local Bot |
|---------|-----------|-----------|
| Connection Stability | ⚠️ May have latency | ✅ Direct connection |
| SSID Refresh | ❌ Manual only | ✅ Can extract from browser |
| Trade Execution | ⚠️ Cloud routing | ✅ Direct to Pocket Option |
| Privacy | Data goes through cloud | Data stays local |

## Requirements

- Python 3.8 or higher
- Chrome or Firefox browser
- Internet connection

## Installation

### Step 1: Create a folder for the bot

```bash
mkdir pocket_option_bot
cd pocket_option_bot
```

### Step 2: Download the bot script

Save `pocket_option_local_bot.py` to this folder.

### Step 3: Install dependencies

```bash
pip install websockets aiohttp requests pyperclip
```

### Step 4: Run the bot

```bash
python pocket_option_local_bot.py
```

## Usage

### First Time Setup

1. Run the bot: `python pocket_option_local_bot.py`
2. Enter your cloud server URL (optional - for signal fetching)
3. The bot will open Pocket Option in your browser
4. Login to your account
5. Follow the instructions to extract your SSID
6. Paste the SSID into the bot
7. Choose Demo or Real account
8. Bot starts trading!

### Getting Your SSID

The SSID is your session token. Here's how to get it:

1. **Open Developer Tools** (F12 in Chrome/Firefox)
2. Go to **Network** tab
3. Click **WS** filter (WebSocket)
4. **Refresh the page** (F5)
5. Find the WebSocket connection
6. Click on it → **Messages** tab
7. Find: `42["auth",{"session":"...`
8. **Copy the entire message**

### Important Notes

⚠️ **SSID Expires**: Your SSID will expire after 1-24 hours. The bot will warn you 30 minutes before estimated expiry.

⚠️ **Demo First**: Always test on demo account first before using real money.

⚠️ **Risk Warning**: Binary options trading involves significant risk. Never trade money you can't afford to lose.

## Configuration

You can customize the bot by editing these settings:

```python
# In pocket_option_local_bot.py

# Signal check interval (seconds)
self.signal_check_interval = 5

# Heartbeat interval (seconds)
self.heartbeat_interval = 25

# Reconnect delay (seconds)
self.reconnect_delay = 5

# Max reconnect attempts
self.max_reconnect_attempts = 10
```

## Connecting to Cloud Server

If you have a cloud server running the GPT Signal Bot, you can connect to it:

1. Enter your cloud server URL when prompted
2. The bot will fetch signals from: `{server}/api/strategy/1m-high-probability/generate`
3. Signals with confidence >= 70% will be executed

## Troubleshooting

### "Connection refused" error
- Check your internet connection
- Make sure Pocket Option is accessible in your region
- Try using a VPN if needed

### "Authentication failed" error
- Your SSID may be expired
- Get a fresh SSID from browser
- Make sure you copied the complete message

### "Trade not executed" error
- Check your account balance
- Make sure you're using the correct account type (demo/real)
- Check if the asset is available for trading

### Bot disconnects frequently
- This is normal - SSID expires periodically
- The bot will attempt to reconnect automatically
- Get a new SSID when prompted

## Files

- `pocket_option_local_bot.py` - Main bot script
- `pocket_option_bot.log` - Log file (created when bot runs)

## Support

For issues with:
- **This bot**: Check the GitHub repository
- **Pocket Option**: Contact Pocket Option support
- **Cloud server**: Check your cloud server logs

## Disclaimer

This bot is provided for educational purposes. Trading binary options involves substantial risk. Past performance does not guarantee future results. The developers are not responsible for any financial losses.
"""

if __name__ == "__main__":
    print(README_CONTENT)
