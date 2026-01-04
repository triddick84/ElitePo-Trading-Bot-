# Pocket Option Desktop Trading Client

Automated trading client for Pocket Option using Chrome browser automation.

## Features

- **Browser-Based Trading**: Uses undetected_chromedriver to bypass bot detection
- **Multiple Strategies**: Simple MA crossover, RSI, and advanced divergence strategies
- **Martingale Support**: Optional bet progression for loss recovery
- **Risk Management**: Take profit, stop loss, and hourly trade limits
- **GUI Interface**: Easy-to-use Tkinter interface for configuration
- **Demo & Live Support**: Works with both demo and live accounts

## Architecture

This client follows the approach from [VitalySvyatyuk's pocket_option_trading_bot](https://github.com/VitalySvyatyuk/pocket_option_trading_bot):

1. **Browser Automation**: Uses undetected_chromedriver to control Chrome
2. **WebSocket Data**: Reads market data from browser's WebSocket performance logs
3. **UI Trading**: Executes trades by clicking the CALL/PUT buttons in the web interface
4. **Persistent Session**: Uses Chrome profile to maintain login session

## Prerequisites

1. **Google Chrome** installed on your system
2. **Python 3.8+** with pip
3. **Pocket Option account** (demo or live)

## Installation

```bash
# Navigate to desktop client directory
cd /app/backend/desktop_client

# Install dependencies
pip install -r requirements.txt

# For TA-Lib on Linux, you may need:
sudo apt-get install ta-lib

# For TA-Lib on Mac:
brew install ta-lib
```

## Usage

### Option 1: GUI (Recommended)

```bash
python gui.py
```

This opens a graphical interface where you can:
- Select Demo or Live account
- Configure trading strategies
- Set risk management parameters
- Monitor trading activity

### Option 2: Command Line

```bash
# Demo account
python trading_bot.py --demo

# Live account (use with caution!)
python trading_bot.py --live

# With Martingale
python trading_bot.py --demo --martingale --amount 1

# Headless mode (no browser window)
python trading_bot.py --demo --headless
```

## Configuration

### Strategies

1. **MA Crossover**: Fast/Slow moving average crossover
2. **RSI**: Overbought/Oversold reversals
3. **Enhanced Divergence**: RSI divergence + MACD momentum exhaustion
4. **Professional Scalping**: Multi-filter institutional approach

### Risk Management

- **Trade Amount**: Base bet size ($1-$1000)
- **Min Payout**: Minimum required payout % (default: 80%)
- **Martingale**: Progressive bet sizing after losses
- **Take Profit**: Stop trading after reaching profit target
- **Stop Loss**: Stop trading after reaching loss limit
- **Vice Versa**: Invert all signals (CALL→PUT, PUT→CALL)

## How It Works

1. **Login**: Open Chrome with your Pocket Option session
2. **Data Capture**: Monitor WebSocket messages for price data
3. **Strategy Analysis**: Run configured strategies on candle data
4. **Signal Generation**: Wait for strategy consensus
5. **Trade Execution**: Click CALL or PUT button when signal appears
6. **Martingale**: Adjust bet size based on win/loss

## Important Notes

⚠️ **Risk Warning**: Binary options trading involves significant risk. Only trade with money you can afford to lose.

⚠️ **Chrome Session**: You must be logged into Pocket Option in Chrome before starting the bot.

⚠️ **Demo First**: Always test on a demo account before using real money.

⚠️ **Monitoring**: Keep an eye on the bot, especially when using live account.

## Troubleshooting

### Chrome driver issues
```bash
# Update undetected-chromedriver
pip install --upgrade undetected-chromedriver
```

### TA-Lib installation fails
```bash
# Use pre-compiled version (Windows)
pip install TA-Lib-Precompiled

# Or use pandas-ta as alternative
pip install pandas-ta
```

### Bot not detecting prices
- Make sure you're on the trading page
- Check that WebSocket connection is active
- Try refreshing the page

## Files

- `gui.py` - Tkinter graphical interface
- `trading_bot.py` - Main trading logic
- `driver.py` - Chrome driver setup
- `strategies.py` - Strategy implementations
- `requirements.txt` - Python dependencies
- `bot_settings.json` - Saved configuration (auto-created)

## License

For personal use only. Not for commercial distribution.
