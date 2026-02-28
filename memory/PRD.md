# GPT Signal Bot - Product Requirements Document

## Original Problem Statement
Create a "GPT Signal Bot" for Pocket Option with a high win rate (80-90%+). The system should include:
- User login system for security
- AI-powered trading signal generation
- Telegram integration for signal notifications
- 3Commas signal bot integration via webhooks
- Market Regime Detection to prevent losing streaks
- Latency correction for optimal signal timing
- Mobile auto-trader via Tampermonkey userscript

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

### Latency Correction System (Feb 2026)
- **Three Modes**: AUTO, MANUAL, DISABLED
- **Per-Timeframe Buffers** - Optimized for each timeframe

### OANDA V20 API Integration (Feb 2026)
- **Real-time Price Data** - Live market prices from OANDA
- **Historical Data Fetching** - Large dataset retrieval for AI training
- **17 Technical Indicators** - RSI, MACD, Bollinger Bands, EMA, etc.
- **Model Training** - TrendFollowing 57%, MeanReversion 55%, PatternRecognition 79%

### Auto Signal Generator (Feb 28, 2026) ✅ UPDATED
- **15-Second Interval** - Generates signals every 15 seconds (changed from 60s)
- **Background Task** - Continuous signal generation without blocking server
- **Enhanced AI Integration** - Uses OANDA data + technical analysis
- **API Endpoints**: `/api/signals/auto/start`, `/api/signals/auto/stop`, `/api/signals/auto/status`

### Tampermonkey Auto-Trader v3.0 (Feb 28, 2026) ✅ NEW
Complete rewrite with comprehensive features:
- **Comprehensive Data Display**:
  - Signal direction (CALL/PUT) with color coding
  - Symbol, confidence percentage
  - Signal age in seconds
  - Last fetch timestamp
  - Trade statistics (wins/losses/win rate)
- **Control Buttons**:
  - **AUTO ON/OFF** - Toggle automatic trade execution
  - **FETCH NOW** - Manual signal fetch
  - **RESET** - Reset bot state and start fresh
  - **SOUND** - Toggle sound notifications
- **Visual Indicators**:
  - Status dot (green=connected, yellow=trading, red=error)
  - Connection status text
  - Real-time log display
- **Enhanced Functionality**:
  - 5-second polling interval
  - Signal age validation (max 60 seconds)
  - Trade cooldown (5 seconds)
  - Persistent state via GM_setValue/GM_getValue
  - Sound alerts for CALL/PUT signals
  - Desktop notifications
- **Draggable Panel** - Touch and mouse drag support

### Strategy Selection System (Feb 28, 2026) ✅ VERIFIED
- **End-to-end working** - UI selection flows to backend signal generation
- **Multiple strategies per timeframe**:
  - 5s: Micro Compression, Keltner Breakout, Candlestick Patterns
  - 1m: Triple SuperTrend, EMA Pullback, ZigZag + Double MA
  - 15s, 30s, 2m, 3m, 5m: Various strategies available
- **API Endpoints**:
  - `GET /api/strategies/available` - All strategies
  - `GET /api/strategies/available/{timeframe}` - Timeframe-specific
  - `GET /api/strategies/selected` - Current selections
  - `POST /api/strategies/select` - Update selection

### Integrations
- **Telegram Bot** - Signal notifications with trade tracking commands
- **3Commas Webhooks** - Send signals to 3Commas bots
- **OANDA V20** - Real-time and historical market data
- **Pocket Option** - Manual trading + mobile userscript auto-trader

## Architecture

```
/app/
├── backend/
│   ├── server.py                    # Main FastAPI application (auto signal at 15s)
│   ├── force_signal_generator.py    # Signal generation with strategy selection
│   ├── strategy_selection_service.py # Strategy management
│   ├── market_regime_detector.py    # Streak tracking and auto-inversion
│   ├── latency_optimizer.py         # Latency correction with 3 modes
│   ├── enhanced_oanda_service.py    # OANDA V20 integration
│   ├── enhanced_ai_trading_system.py # AI/ML models
│   └── auth_service.py              # JWT authentication
└── frontend/
    ├── public/
    │   └── pocket-option-auto-trader.user.js  # v3.0 Tampermonkey script
    └── src/
        ├── App.js                   # Main app with protected routes
        └── components/
            ├── Dashboard.jsx        # Main trading dashboard
            └── SettingsPage.jsx     # Settings with Latency tab
```

## Current Status

### ✅ Working
- Signal generation with 15-second intervals
- Tampermonkey v3.0 with all requested features
- Strategy selection (end-to-end verified)
- Latency correction with AUTO/MANUAL/DISABLED modes
- Trade result recording via API and Telegram commands
- Streak inversion after 3 consecutive losses
- All authentication flows

### ⚠️ Known Limitations
- Pocket Option auto-trade blocked by cloud IP (workaround: mobile userscript)
- OANDA may return HOLD during unclear market conditions

## API Endpoints Reference

### Auto Signal Generator (15-second interval)
- `POST /api/signals/auto/start` - Start auto generation
- `POST /api/signals/auto/stop` - Stop auto generation
- `GET /api/signals/auto/status` - Check status
- `GET /api/signals/latest` - Get latest signal for userscript

### Strategy Selection
- `GET /api/strategies/available` - All strategies
- `GET /api/strategies/available/{timeframe}` - Timeframe-specific
- `GET /api/strategies/selected` - Current selections
- `POST /api/strategies/select` - Update selection

### Trading & Regime
- `POST /api/signals/force-generate` - Force generate signals
- `POST /api/trading/record-result` - Record trade outcome
- `GET /api/trading/regime-status` - Get regime detector status

### Latency
- `GET /api/latency/status` - Get latency settings
- `POST /api/latency/set-mode` - Set mode (auto/manual/disabled)

## Completed Tasks
- [x] Fix Tampermonkey Auto-Trader v3.0 with comprehensive data display
- [x] Add AUTO ON/OFF switch, FETCH NOW, RESET buttons
- [x] Change auto signal generation to 15-second interval
- [x] End-to-end strategy selection verification
- [x] OANDA V20 API Integration
- [x] Enhanced AI/ML System (TrendFollowing, MeanReversion, PatternRecognition)
- [x] Market Regime Detector
- [x] Latency Correction System
- [x] Dashboard UI Controls

## P1 - High Priority (Next)
- [ ] MetaTrader5 integration (playbook received, needs implementation)
- [ ] TradingView webhook integration (playbook received, needs implementation)
- [ ] Backend refactoring (split server.py into routes modules)

## P2 - Medium Priority
- [ ] Clean up Pocket Option page - remove unused code
- [ ] Enhanced Signal Pop-up with Normal/Inverted status indicator
- [ ] Frontend accuracy statistics dashboard widget

## P3 - Future
- [ ] Fix Money Management Logic (Martingale)
- [ ] Residential proxy integration for Pocket Option auto-trade

## Credentials
- **App Login**: username: `triddick84`, password: `Fallinone#1`
- **OANDA**: Configured in backend/.env

## Test Reports
- `/app/test_reports/iteration_1.json` - Market Regime Detector tests
- `/app/test_reports/iteration_2.json` - Latency Correction tests
- `/app/test_reports/iteration_3.json` - Auto Signal Generator tests (9/9 passed)

## Last Updated
February 28, 2026
- Tampermonkey userscript v3.0 with comprehensive data display
- Auto signal generator now runs at 15-second intervals
- Strategy selection verified end-to-end
- All tests passing (100% success rate)
