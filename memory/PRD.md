# GPT Signal Bot - Product Requirements Document

## Original Problem Statement
Create a "GPT Signal Bot" for Pocket Option with a high win rate (80-90%+). The system should include:
- User login system for security
- AI-powered trading signal generation
- Telegram integration for signal notifications
- 3Commas signal bot integration via webhooks
- Market Regime Detection to prevent losing streaks
- Latency correction for optimal signal timing

## Completed Features

### Core Infrastructure
- **JWT Authentication System** - Single admin user (triddick84) with protected routes
- **FastAPI Backend** - Full REST API with MongoDB persistence
- **React Frontend** - Streamlined 7-page navigation with Latency settings tab

### Trading Signal System
- **Force Signal Generation** - Generate high-confidence signals on demand
- **Multiple Timeframes** - Support for 5s, 15s, 30s, 1m, 2m, 3m, 5m
- **Strategy Registry** - Modular strategy selection per timeframe
- **Technical Analysis** - RSI, MACD, Bollinger Bands, EMA crossovers, candlestick patterns

### Market Regime Detector (Feb 2026)
- **Streak Tracking** - Monitors consecutive wins/losses
- **Auto-Inversion** - Automatically inverts signals after 3 consecutive losses
- **Win Rate Monitoring** - Tracks recent win rate and adjusts accordingly
- **API Endpoints**:
  - `POST /api/trading/record-result` - Record trade outcomes
  - `GET /api/trading/regime-status` - Get current regime status
  - `POST /api/trading/reset-streak` - Reset streak counter
  - `GET /api/trading/accuracy-stats` - Get detailed accuracy statistics

### Latency Correction System (Feb 2026)
- **Three Modes**:
  - **AUTO (default)** - System learns from trade results and auto-adjusts timing
  - **MANUAL** - User sets a fixed offset for fine-tuning
  - **DISABLED** - No latency correction applied
- **Per-Timeframe Buffers** - Optimized for each timeframe:
  - 5s: 2.5s early, 15s: 3.0s early, 30s: 3.5s early, 1m: 4.0s early, 2m: 5.0s early
- **API Endpoints**:
  - `GET /api/latency/status` - Get current latency settings
  - `POST /api/latency/set-mode` - Switch between auto/manual/disabled
  - `POST /api/latency/set-manual-offset` - Set manual offset (-10s to +10s)
  - `POST /api/latency/record-timing-feedback` - Feed timing feedback for auto-learning
  - `POST /api/latency/reset` - Reset to defaults

### Telegram Bot Commands (Feb 2026)
- **/signal** - Generate trading signal
- **/win [symbol] [direction]** - Record a winning trade (feeds regime detector)
- **/loss [symbol] [direction]** - Record a losing trade (feeds regime detector)
- **/regime** - Get market regime detector status
- **/latency** - Get latency correction status
- **/status** - Bot status
- **/settings** - Current settings
- **/help** - All commands

### Integrations
- **Telegram Bot** - Signal notifications with trade tracking commands
- **3Commas Webhooks** - Send signals to 3Commas bots
- **Pocket Option** - Manual trading mode (auto-trade blocked by cloud IP)

## Architecture

```
/app/
├── backend/
│   ├── server.py                    # Main FastAPI application
│   ├── force_signal_generator.py    # Signal generation with regime detection
│   ├── market_regime_detector.py    # Streak tracking and auto-inversion
│   ├── latency_optimizer.py         # Latency correction with 3 modes
│   ├── signal_accuracy_optimizer.py # Multi-gate signal validation
│   ├── telegram_bot_service.py      # Telegram bot with win/loss tracking
│   ├── auth_service.py              # JWT authentication
│   └── threecommas_service.py       # 3Commas webhook integration
└── frontend/
    └── src/
        ├── App.js                   # Main app with protected routes
        └── components/
            ├── Dashboard.jsx        # Main trading dashboard
            ├── SettingsPage.jsx     # Settings with Latency tab
            └── TelegramBotPage.jsx  # Telegram management
```

## Current Status

### Working
- Signal generation with regime-aware confidence boosters
- Latency correction with AUTO/MANUAL/DISABLED modes
- Trade result recording via API and Telegram commands
- Streak inversion after 3 consecutive losses
- All authentication flows
- Telegram notifications with /win /loss tracking
- 3Commas webhook integration
- **Dashboard Quick Controls** - Invert Signals toggle and Lost? Invert & Generate button
- **Mobile Auto-Trader** - Tampermonkey userscript for Pocket Option on Android

### Known Limitations
- Pocket Option auto-trade blocked by cloud IP (workaround: mobile userscript)
- Manual trading mode required for Pocket Option desktop

## Completed Tasks
- [x] Fix "Losing Streak" Bug - Market Regime Detector
- [x] Signal Accuracy Improvements - Regime-aware confidence boosters
- [x] Latency Correction System - AUTO/MANUAL/DISABLED modes
- [x] Settings UI - Latency tab with mode switching and stats
- [x] Telegram Commands - /win /loss /regime /latency commands
- [x] Dashboard UI Controls - Invert Signal toggle + "Lost? Invert & Generate" quick button
- [x] Latency Mode Toggle on Dashboard - Auto/Manual quick switcher
- [x] Mobile Auto-Trader Userscript - Tampermonkey-based client-side automation
- [x] Expanded Asset Lists - Full forex, crypto, stocks, commodities, indices coverage

## P1 - High Priority (Next)
- [ ] Implement actual trading logic for custom PDF strategies in force_signal_generator.py
- [ ] MetaTrader5 integration (playbook received, needs implementation)
- [ ] TradingView webhook integration (playbook received, needs implementation)

## P2 - Medium Priority
- [ ] End-to-end custom strategy testing (verify strategy logic is actually executed)
- [ ] Backend refactoring (split server.py into routes modules)
- [ ] Clean up Pocket Option page - remove unused code
- [ ] Enhanced Signal Pop-up with Normal/Inverted status indicator
- [ ] Frontend accuracy statistics dashboard widget

## P3 - Future
- [ ] Fix Money Management Logic (Martingale)
- [ ] Residential proxy integration for Pocket Option auto-trade

## API Endpoints Reference

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/verify` - Verify JWT token

### Trading & Regime
- `POST /api/signals/force-generate` - Force generate signals
- `POST /api/trading/record-result` - Record trade outcome
- `GET /api/trading/regime-status` - Get regime detector status
- `POST /api/trading/reset-streak` - Reset streak counter
- `GET /api/trading/accuracy-stats` - Get accuracy statistics

### Latency
- `GET /api/latency/status` - Get latency settings
- `POST /api/latency/set-mode` - Set mode (auto/manual/disabled)
- `POST /api/latency/set-manual-offset` - Set manual offset
- `POST /api/latency/record-timing-feedback` - Record timing feedback
- `POST /api/latency/reset` - Reset latency to defaults

### Configuration
- `GET /api/settings` - Get app settings
- `POST /api/settings` - Save app settings
- `GET /api/config` - Get trading config
- `PUT /api/config` - Update trading config

### Signal Inversion
- `POST /api/signals/toggle-invert` - Toggle global signal inversion ON/OFF
- `GET /api/signals/invert-status` - Get current inversion status
- `POST /api/signals/invert/{signal_id}` - Invert a specific signal

### Integrations
- `POST /api/3commas/send-signal` - Send signal to 3Commas
- `POST /api/telegram-bot/send-signal` - Send signal via Telegram

## Credentials
- **App Login**: username: `triddick84`, password: `Fallinone#1`

## Test Reports
- `/app/test_reports/iteration_1.json` - Market Regime Detector tests (11/11 passed)
- `/app/test_reports/iteration_2.json` - Latency Correction tests (22/22 passed)

## Last Updated
February 25, 2026 - Implemented OANDA V20 API integration and Enhanced AI Trading System with:
- Trend Following (Gradient Boosting ML)
- Mean Reversion (Random Forest ML)
- Pattern Recognition (Neural Network MLP)
- Custom Strategy Integration from Strategy Builder
- Continuous Learning from trade outcomes
