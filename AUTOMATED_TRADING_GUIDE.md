# Pocket Option Automated Trading - Implementation Guide

## Overview

This guide explains how the automated trading system works and how to set it up for real trading on Pocket Option.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR COMPUTER                            │
│  ┌────────────────────────────────────────────────────────────┐│
│  │           pocket_option_local_bot.py                       ││
│  │  - Logs into Pocket Option                                 ││
│  │  - Polls cloud server for signals                          ││
│  │  - Executes trades automatically                           ││
│  └────────────────────────────────────────────────────────────┘│
│                              │                                  │
│                         Trades ↓                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │             Pocket Option Website                          ││
│  │  - Real trading platform                                   ││
│  │  - Your account balance                                    ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ↑↓
                     Signals & Status
                              ↑↓
┌─────────────────────────────────────────────────────────────────┐
│                      CLOUD SERVER                               │
│  ┌────────────────────────────────────────────────────────────┐│
│  │           Trading Signal Generator                         ││
│  │  - AI/ML models                                            ││
│  │  - Technical analysis                                      ││
│  │  - Strategy engine                                         ││
│  │  - Signal queue for local bot                              ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Why This Architecture?

The cloud server cannot directly connect to Pocket Option due to:
1. Network restrictions in the cloud environment
2. IP-based access controls by Pocket Option
3. Geographic/firewall restrictions

The solution is a **hybrid approach**:
- **Cloud server**: Generates trading signals using AI/ML
- **Local bot**: Runs on your computer and executes trades

## Quick Start

### Step 1: Download the Local Bot

Download `pocket_option_local_bot.py` from the backend server.

### Step 2: Install Requirements

```bash
pip install playwright requests aiohttp
playwright install chromium
```

### Step 3: Configure the Bot

Edit the configuration section in `pocket_option_local_bot.py`:

```python
# Your Pocket Option credentials
PO_EMAIL = "your-email@example.com"
PO_PASSWORD = "your-password"

# Cloud server URL
CLOUD_SERVER_URL = "https://signalbot-34.preview.emergentagent.com"

# Account type: "demo" or "live"
ACCOUNT_TYPE = "live"  # Start with "demo" for testing

# Trade settings
DEFAULT_TRADE_AMOUNT = 1.0  # dollars
MIN_CONFIDENCE = 80.0  # minimum signal confidence
```

### Step 4: Run the Bot

```bash
python pocket_option_local_bot.py
```

The bot will:
1. Open a Chrome browser (visible so you can monitor)
2. Log into Pocket Option
3. Navigate to the trading page
4. Start polling the cloud server for signals
5. Execute trades automatically when signals are received

## Execution Modes

The system supports multiple execution modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| DEMO | Simulates trades locally | Testing the signal system |
| BRIDGE | Uses browser JS injection | Advanced users |
| HEADLESS | Server-side browser | Blocked by network |
| LOCAL | Uses the local bot | **Recommended for real trading** |

### Setting Execution Mode

```bash
# Check current mode
curl https://your-server/api/execution-mode/current

# Set mode (for testing)
curl -X POST "https://your-server/api/execution-mode/set?mode=DEMO"
```

## API Endpoints

### Signal Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/signals/generate` | POST | Generate a new trading signal |
| `/api/trade-executor/pending` | GET | Get pending trades for local bot |
| `/api/trade-executor/confirm-execution` | POST | Confirm trade was executed |
| `/api/trade-executor/report-result` | POST | Report trade result (win/loss) |

### Automated Trading

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auto-trade/status` | GET | Get auto-trading status |
| `/api/auto-trade/enable` | POST | Enable/disable auto-trading |
| `/api/auto-trade/settings` | PUT | Update trading settings |
| `/api/auto-trade/history` | GET | Get trade history |

### Headless Browser (For Testing)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/headless/start` | POST | Start headless browser |
| `/api/headless/stop` | POST | Stop headless browser |
| `/api/headless/status` | GET | Get browser status |

## Best Practices

### For Demo Trading
1. Always test with DEMO account first
2. Verify signals are being generated correctly
3. Monitor the local bot's execution

### For Live Trading
1. Start with small trade amounts ($1)
2. Set conservative confidence thresholds (80%+)
3. Monitor your account balance
4. Keep the local bot running on a stable computer
5. Use a wired internet connection

### Risk Management
- Never trade more than you can afford to lose
- Set daily/weekly loss limits
- Monitor the bot regularly
- Use the money management settings

## Troubleshooting

### Local Bot Won't Connect to Pocket Option
- Check your internet connection
- Verify credentials are correct
- Try a different browser
- Check if Pocket Option is accessible in your region

### Signals Not Being Executed
- Verify the local bot is running
- Check the cloud server URL is correct
- Ensure auto-trading is enabled
- Check minimum confidence settings

### Trade Execution Failures
- Verify sufficient balance
- Check trade amount settings
- Ensure you're on the correct trading page
- Try refreshing the page

## Files Reference

| File | Description |
|------|-------------|
| `browser_automation.py` | Playwright browser automation (server-side) |
| `auto_execution_mode.py` | Execution mode manager |
| `trade_executor.py` | Trade execution queue manager |
| `pocket_option_local_bot.py` | Local bot for your computer |
| `automated_trading_service.py` | Signal-to-trade orchestration |

## Support

If you encounter issues:
1. Check the backend logs: `tail -f /var/log/supervisor/backend.err.log`
2. Check the local bot console output
3. Verify network connectivity
4. Test endpoints using curl

## Important Notes

⚠️ **Trading Binary Options involves significant risk of loss.**

- The automated trading system is a tool, not a guarantee of profits
- Past performance does not indicate future results
- Always understand the risks before trading
- Use demo accounts for testing before live trading
