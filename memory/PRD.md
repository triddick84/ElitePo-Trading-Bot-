# GPT Signal Bot - Product Requirements Document

## Original Problem Statement
Create a "GPT Signal Bot" for Pocket Option with a high win rate (80-90%+). The system should include:
- User login system for security
- AI-powered trading signal generation
- Telegram integration for signal notifications
- 3Commas signal bot integration via webhooks
- Market Regime Detection to prevent losing streaks

## Completed Features

### Core Infrastructure
- **JWT Authentication System** - Single admin user (triddick84) with protected routes
- **FastAPI Backend** - Full REST API with MongoDB persistence
- **React Frontend** - Streamlined 7-page navigation

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

### Signal Accuracy Improvements (Feb 2026)
- **Fixed undefined variable bug** - `user_timeframes` → `user_expirations`
- **Regime-Aware Confidence Boosters**:
  - High win rate (>70%) → confidence boost up to +3%
  - Low win rate (<40%) → confidence penalty up to -5%
  - Winning streak (3+) → streak boost up to +3%
- **Improved Quality Gates** - Signals no longer rejected for not meeting 90%+ threshold
- **Accuracy Statistics Endpoint** - `GET /api/trading/accuracy-stats`
  - Overall and recent win rates
  - Breakdown by direction (CALL/PUT)
  - Breakdown by symbol
  - AI-generated recommendations

### Integrations
- **Telegram Bot** - Signal notifications to user's chat
- **3Commas Webhooks** - Send signals to 3Commas bots
- **Pocket Option** - Manual trading mode (auto-trade blocked by IP)

## Architecture

```
/app/
├── backend/
│   ├── server.py                    # Main FastAPI application
│   ├── force_signal_generator.py    # Signal generation with regime detection
│   ├── market_regime_detector.py    # Streak tracking and auto-inversion
│   ├── signal_accuracy_optimizer.py # Multi-gate signal validation
│   ├── signal_accuracy_maximizer.py # 90%+ validation system
│   ├── auth_service.py              # JWT authentication
│   ├── threecommas_service.py       # 3Commas webhook integration
│   └── telegram_bot_service.py      # Telegram notifications
└── frontend/
    └── src/
        ├── App.js                   # Main app with protected routes
        └── components/
            ├── Dashboard.jsx        # Main trading dashboard
            ├── SettingsPage.jsx     # Configuration hub
            └── TelegramBotPage.jsx  # Telegram management
```

## Current Status

### Working
- Signal generation with regime-aware confidence boosters
- Trade result recording API with accuracy statistics
- Streak inversion after 3 consecutive losses
- All authentication flows
- Telegram notifications
- 3Commas webhook integration

### Known Limitations
- Pocket Option auto-trade blocked by cloud IP
- Manual trading mode required for Pocket Option

## P0 - Critical (Completed)
- [x] Fix "Losing Streak" Bug - Implement Market Regime Detector
- [x] Replace hardcoded "CALL" biases with regime-aware logic
- [x] Add trade result recording endpoint

## P1 - High Priority (Completed)
- [x] Improve Signal Accuracy - Added regime-aware confidence boosters
- [x] Fixed `user_timeframes` undefined variable bug
- [x] Added accuracy statistics endpoint

## P1 - High Priority (Next)
- [ ] Enhanced Signal Pop-up Notification with Normal/Inverted status
- [ ] Frontend display of accuracy statistics

## P2 - Medium Priority
- [ ] End-to-end custom strategy testing
- [ ] Backend refactoring (split server.py)
- [ ] Binance US & TradingView bot planning

## P3 - Future
- [ ] Fix Money Management Logic (Martingale)

## API Endpoints Reference

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/verify` - Verify JWT token

### Trading
- `POST /api/signals/force-generate` - Force generate signals
- `POST /api/trading/record-result` - Record trade outcome
- `GET /api/trading/regime-status` - Get regime detector status
- `POST /api/trading/reset-streak` - Reset streak counter
- `GET /api/trading/accuracy-stats` - Get accuracy statistics

### Configuration
- `GET /api/settings` - Get app settings
- `POST /api/settings` - Save app settings
- `GET /api/config` - Get trading config
- `PUT /api/config` - Update trading config

### Integrations
- `POST /api/3commas/send-signal` - Send signal to 3Commas
- `POST /api/telegram-bot/send-signal` - Send signal via Telegram

## Credentials
- **App Login**: username: `triddick84`, password: `Fallinone#1`

## Last Updated
February 22, 2026
