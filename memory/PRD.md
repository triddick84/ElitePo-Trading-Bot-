# GPT Signal Bot - Product Requirements Document

## Last Updated: March 20, 2026

## Current Status
✅ **Tampermonkey v6.8.5** - Fixed multi-asset SCAN with SWITCH enabled
✅ **Tampermonkey v6.8.0** - Complete Money Management System with Smart Martingale
✅ **Ultra High Accuracy 5s Strategy** - Research-based 85%+ confidence signals
✅ **Enhanced AI ML System** - Ensemble model with historical data training

## Recent Updates (March 20, 2026)

### Tampermonkey v6.8.5 - Multi-Asset SCAN Fix (March 20, 2026)
**Fixed: SCAN + SWITCH Logic for Multiple Assets**
- When SWITCH is ON and AUTO is OFF, the script now correctly scans ALL favorited assets
- Fixed `doScan()` function to always re-detect favorites bar before scanning
- Fixed asset list building with proper `_OTC` suffix handling
- Improved `executeScanTrade()` to correctly match and click favorites
- Fixed `matchingFav.name` → `matchingFav.symbol` bug
- Added comprehensive logging for debugging asset switching
- Backend `/signals/scan-markets` endpoint verified working with comma-separated assets

### NEW: 1m Momentum Exhaustion Reversal Strategy (March 20, 2026)
**High-probability reversal strategy for OTC forex pairs**

| Indicator | Parameters | Purpose |
|-----------|------------|---------|
| RSI-2 | Period 2, OB/OS: 90/10 | Extreme momentum detection |
| Stochastic | (5,3,3), OB/OS: 80/20 | Crossover confirmation |
| Bollinger Bands | (20,2) | Price extremes at bands |
| MACD | (8,17,9) | Momentum exhaustion |
| Candlestick Patterns | Hammer, Engulfing, Doji, Star | Visual confirmation |

**Entry Rules:**
- **CALL**: RSI-2 < 10 + Stoch bullish cross from <20 + Price at lower BB + Bullish candle + MACD bearish exhaustion
- **PUT**: RSI-2 > 90 + Stoch bearish cross from >80 + Price at upper BB + Bearish candle + MACD bullish exhaustion
- Requires minimum 3 of 5 confirmations
- ATR filter skips choppy/volatile markets

**Target Win Rate:** 70-75%
**Strategy ID:** `1m_momentum_exhaustion`
**Available in UI:** Strategies → 1m Timeframe Strategy → ⭐⭐⭐ Momentum Exhaustion Reversal

**Button Logic (Unchanged):**
| Mode | AUTO | SWITCH | SCAN | Behavior |
|------|------|--------|------|----------|
| App Signals Only | ON | OFF | OFF | Only places trades from app signals |
| Single Asset Scan | OFF | OFF | ON | Scans current asset only |
| Multi-Asset Scan | OFF | ON | ON | Scans ALL favorites, switches to best signal |

## Recent Updates (March 16, 2026)

### NEW: 1m Quad SMA/EMA Crossover Strategy (March 16, 2026)
Based on user specification for Japanese Candlestick chart:
- **White: 2 SMA**
- **Yellow: 5 SMA**
- **Pink: 10 SMA**
- **Blue: 20 EMA**

**Crossover Rules:**
| Rule | Condition | Action |
|------|-----------|--------|
| 1st | White(2) crosses Yellow(5) | Go WITH Trend |
| 2nd | Yellow(5) + White(2) both cross Pink(10) | Go AGAINST Trend |
| 3rd | White(2) + Yellow(5) both cross Blue(20) | Go WITH Trend |
| 4th | Pink(10) crosses Blue(20) | Go AGAINST last Trend (reversal signal) |
| Special | White(2) crosses ALL lines in one candle | Go AGAINST Trend (high priority) |

**Strategy Selection:** Available in UI under 1m strategies as "⭐⭐ Quad SMA/EMA Crossover"
**Target Win Rate:** 80-85%

### Tampermonkey v6.8.0 - Money Management System (March 16, 2026)
**NEW: Complete Money Management with Smart Martingale**
- **Balance Tracking** - User can input account balance, auto-detect from Pocket Option UI
- **Risk-Based Trade Sizing** - Calculate trade amounts as % of balance (default 2%)
- **Payout-Aware Martingale** - Smart recovery that calculates exact amounts needed to recover losses + profit
- **Trade Amount UI Control** - Automatically sets trade amount on Pocket Option input field
- **Session Tracking** - Track trades, P/L, balance changes throughout session

**Money Management UI Panel includes:**
- Balance display and input ($)
- Current payout % display (auto-detected)
- Current trade amount display
- Session P/L tracking  
- Risk % setting (0.5-10%)
- Target profit setting for recovery ($)
- "Detect Balance" button - reads balance from PO UI
- "Apply to UI" button - sets trade amount on PO input field
- ON/OFF toggle for Smart Martingale

**How Smart Martingale Works:**
1. User sets balance (e.g., $100), risk % (e.g., 2%), target profit (e.g., $0.50)
2. Base trade = $100 × 2% = $2.00
3. On WIN: Reset to base trade, update balance with profit
4. On LOSS: Calculate next amount = (Total Loss + Target Profit) / (Payout / 100)
   - Example: Lost $2 at 92% payout → Next trade = ($2 + $0.50) / 0.92 = $2.72
5. On subsequent losses, the formula accumulates total losses to recover
6. On WIN during martingale: Recover all losses + make profit, reset to base

### Previous v6.7.0 Features (Still Active)
- **Manual WIN/LOSS Buttons** - User presses to record trade results
- **Auto-Invert on LOSS** - Toggles signal inversion when LOSS pressed
- **Legacy Martingale System** - Configurable base amount, multiplier, max steps
- **Sound Notifications** - Win/Loss/Stop sounds with toggle
- **Session Stats** - Wins, losses, streak, P/L tracking

### Ultra High Accuracy 5s Strategy
Based on research of highest win rate binary options algorithms:
- Multi-confirmation entry system (requires ALL conditions)
- RSI-2 micro-momentum detection
- Stochastic divergence filter
- Bollinger Band squeeze/expansion
- Candlestick pattern recognition (Pin bars, Engulfing)
- Support/Resistance level proximity
- Minimum 85% confidence threshold

### Enhanced AI ML System
- RandomForest + GradientBoosting ensemble
- 25+ technical indicator features
- Historical data training from validated signals
- Synthetic data generation when real data unavailable
- Model persistence to disk
- Real-time predictions with confidence scores

### New API Endpoints
- `POST /api/enhanced-ml/train` - Train ML model
- `GET /api/enhanced-ml/stats` - Get ML statistics
- `POST /api/enhanced-ml/predict/{symbol}` - Get ML prediction
- `POST /api/ultra-accuracy/signal/{symbol}` - Get ultra-accuracy signal
- `GET /api/ultra-accuracy/scan` - Scan multiple assets

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

### Tampermonkey Auto-Trader v6.0.0 (Mar 10, 2026) ✅ COMPLETE REWRITE
**Button Logic Reconfigured:**

| Button | Function |
|--------|----------|
| **AUTO** | Only places trades from incoming APP SIGNALS (requires SCAN OFF, SWITCH OFF) |
| **SWITCH** | When ON: Tampermonkey can switch between assets during scanning. When OFF: stays on current asset |
| **SCAN** | Tampermonkey scans for signals on current asset (SWITCH OFF) or all favorites (SWITCH ON) |
| **INVERT** | LOCAL toggle - overrides app setting. User controls inversion in Tampermonkey |
| **FETCH** | If SCAN ON: force scan. If SCAN OFF: check for app signals |
| **RESET** | Restores all buttons to OFF (default state) |

**For App Signals:** AUTO: ON, SWITCH: OFF, SCAN: OFF
**For Scanning Current Asset:** SCAN: ON, SWITCH: OFF
**For Scanning All Favorites:** SCAN: ON, SWITCH: ON

**Trade Cooldowns:**
- App signals: 5 seconds between trades
- Scan signals: 30 seconds between trades

**Sound Notifications (TWO DIFFERENT SOUNDS):**
- App signal trades: High-pitched short beep (880Hz)
- Scan signal trades: Low-pitched longer beep (440Hz)

**Default State:** All buttons OFF - user enables features as needed

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
- [x] **Money Management System v6.8.0** (March 16, 2026) - Complete with Smart Martingale, balance tracking, payout-aware recovery
- [x] **Tampermonkey v6.8.1** (March 16, 2026) - Fixed critical double-trade bug with enhanced trade guards
- [x] **AI/ML Training Pipeline** (March 16, 2026) - Fixed OANDA data integration for ML model training (720+ candles per training)
- [x] **Multi-Asset SCAN v6.8.5** (March 20, 2026) - Fixed SCAN+SWITCH to scan ALL favorites, not just current asset
- [x] **1m Momentum Exhaustion Strategy** (March 20, 2026) - RSI-2 + Stochastic + BB + Candlesticks reversal strategy (70-75% target)

## P1 - High Priority (Next)
- [ ] Full backend refactoring (split server.py into routes modules) - 14768 lines needs modularization
- [ ] Clean up more unused strategy files

## P2 - Medium Priority
- [ ] Enhanced Signal Pop-up with Normal/Inverted status indicator
- [ ] Frontend accuracy statistics dashboard widget

## P3 - Future
- [x] ~~Fix Money Management Logic (Martingale)~~ - COMPLETED v6.8.0
- [x] ~~Fix AI/ML training data pipeline~~ - COMPLETED (OANDA integration working)
- [x] ~~Fix critical double-trade bug~~ - COMPLETED v6.8.1
- [ ] Further ML model tuning for higher accuracy

## Credentials
- **App Login**: username: `triddick84`, password: `Fallinone#1`
- **OANDA**: Configured in backend/.env

## Test Reports
- `/app/test_reports/iteration_1.json` - Market Regime Detector tests
- `/app/test_reports/iteration_2.json` - Latency Correction tests
- `/app/test_reports/iteration_3.json` - Auto Signal Generator tests (9/9 passed)
- `/app/test_reports/iteration_6.json` - **Full regression test (17/17 backend, 100% frontend)** - March 5, 2026

## Last Updated
March 15, 2026

### v6.6.0 - Win/Loss Recognition System (March 15, 2026)
**Win/Loss Detection:**
- Automatic detection via trade result popups AND balance change monitoring
- Tracks wins, losses, consecutive streaks, and session P/L
- Trade history stored (last 50 trades)

**Auto-Invert on Loss:**
- Toggle: AUTO-INV ON/OFF - enables auto-inversion system
- Toggle: AUTO-PLACE ON/OFF - auto-place trade after loss vs just invert next signal
- Logic: Loss → Invert, Win while inverted → Stay inverted, Double loss → Flip back

**Stop Conditions:**
- Adjustable max consecutive losses (default 3)
- Stop loss amount setting (stops if session loss exceeds amount)
- Auto-disables all trading when stop condition met

**Sound Notifications:**
- Win sound (ascending happy tone)
- Loss sound (descending sad tone)
- Stop sound (alert for stop condition)
- Toggle: SOUND ON/OFF

**Backend Integration:**
- `POST /api/tampermonkey/stats` - Store win/loss stats from Tampermonkey
- `GET /api/tampermonkey/stats` - Retrieve stats for display
- `POST /api/tampermonkey/stats/reset` - Reset stats

**Frontend Display:**
- Session Statistics card with Wins/Losses/Streak/P&L
- Auto-Invert status indicator
- Recent trades history display
- Reset Stats button

### v6.5.0 - Favorites Bar + Control System (March 15, 2026)
- SCAN/SWITCH now use visual favorites bar
- Signal Source Selection (App AI, TradingView, MT4, MT5, TM Scan)
- Strategy Selection (10 strategies)
- Live Connection Status with heartbeat

### Previous Updates
- v6.4.2: Removed opposite trade block per user request
- March 5, 2026: Fixed critical login bug
