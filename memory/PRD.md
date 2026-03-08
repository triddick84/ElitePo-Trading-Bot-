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

### ✅ Working (March 8, 2026)
- **User Authentication** - Login working correctly with JWT tokens
- **Deep Market Analysis System** - Multi-indicator confluence for improved win rate
  - RSI/MACD divergence detection
  - Support/Resistance level detection
  - Candlestick pattern recognition
  - Volume confirmation filtering
  - Market structure analysis
  - Minimum 4 confirmations required
- **MetaTrader 5 Integration** - ZeroMQ bridge for remote MT5 trading
  - Place market orders
  - Manage positions (open/close)
  - Get account info
  - Simulated mode when MT5 not connected
- **TradingView Webhook Integration** - Receive alerts and execute trades
  - Webhook endpoint for alerts
  - Pine Script template generator
  - Multi-destination routing (MT5, Pocket Option, Internal)
  - Alert history and statistics
- Signal generation with 15-second intervals
- Tampermonkey v5.3.0 with trade expiration switching
- All navigation pages working

### ⚠️ Known Limitations
- Pocket Option auto-trade blocked by cloud IP (workaround: mobile userscript)
- MT5 ZeroMQ requires Windows MT5 terminal with ZeroMQ EA installed
- TradingView webhooks require TradingView Pro subscription

## API Endpoints Reference

### High Accuracy Signal Generation (NEW)
- `POST /api/signals/high-accuracy/generate` - Generate signal with multi-confirmation
- `GET /api/signals/high-accuracy/strategies` - Get list of available strategies
- `GET /api/signals/high-accuracy/performance` - Get performance statistics
- `POST /api/signals/high-accuracy/record-result` - Record win/loss for tracking

### MetaTrader 5 Integration (NEW)
- `GET /api/mt5/status` - Get MT5 connection status
- `POST /api/mt5/connect` - Connect to MT5 terminal
- `GET /api/mt5/account` - Get account info (balance, equity, margin)
- `GET /api/mt5/symbol/{symbol}` - Get symbol info (bid, ask, spread)
- `POST /api/mt5/order` - Execute trading order
- `POST /api/mt5/signal/process` - Process signal with confidence threshold
- `GET /api/mt5/positions` - Get open positions
- `POST /api/mt5/positions/{ticket}/close` - Close position
- `PUT /api/mt5/positions/{ticket}/modify` - Modify SL/TP
- `GET /api/mt5/history` - Get trade history

### Pocket Option Real-Time Market Data (NEW)
- `POST /api/pocket-option/realtime/connect` - Connect to PO WebSocket for live data
- `POST /api/pocket-option/realtime/subscribe/{symbol}` - Subscribe to asset price updates
- `GET /api/pocket-option/realtime/market-data/{symbol}` - Get current price + indicators
- `GET /api/pocket-option/realtime/signal/{symbol}` - Generate signal from PO data
- `GET /api/pocket-option/realtime/candles/{symbol}` - Get candle history
- `GET /api/pocket-option/realtime/status` - Check connection status
- `POST /api/pocket-option/realtime/disconnect` - Disconnect from PO

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
- [x] Pocket Option Real-Time Market Data Integration
- [x] Combined signal generation (OANDA + Pocket Option)
- [x] High-Accuracy Trading Strategies (5s, 15s, 30s, 1m expiries)
- [x] Multi-confirmation signal generation (4-5 confirmations required)
- [x] AI Learning config save/load functionality verified
- [x] **MetaTrader 5 Integration** (simulation mode on Linux, full support on Windows)
- [x] MT5 Order Execution (BUY/SELL/CALL/PUT)
- [x] MT5 Position Management (open, close, modify)
- [x] MT5 Account Monitoring (balance, equity, margin)

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
- `/app/test_reports/iteration_6.json` - **Full regression test (17/17 backend, 100% frontend)** - March 5, 2026

## Last Updated
March 5, 2026
- **Fixed critical login bug** - SyntaxError in server.py caused by incomplete function and orphaned code
- All tests passing (100% success rate - 17/17 backend, all frontend)
- Verified: Login, Dashboard, Navigation, Timeframe selection, High-accuracy strategies, Market scanning
