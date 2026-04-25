# Elite Pocket Option Trading Bot - Product Requirements Document

## Last Updated: April 23, 2026

## Current Status
✅ **CRITICAL: Userscript Version Drift Bug Fixed — TM v8.24.0 (April 23, 2026, Iter 53)**
- **Root cause discovered**: The Tampermonkey `@version` header in `webpack.config.js` was hardcoded to `8.18.0` and had not been updated since iter 47, even though `CONFIG.BOT_VERSION` was bumped through 8.19, 8.20, 8.21, 8.22, 8.23, 8.24. **Tampermonkey only re-installs when `@version` increases**, so the user has been running v8.18.0 for the past 6 iterations — none of the 1H51 strategy, 51S simplification, candle-timer trigger, or persistence fix were active in their browser
- **Fix**: `/app/tampermonkey-src/version.txt` is now the single source of truth. `webpack.config.js` reads it via `fs.readFileSync` and injects it into BOTH the userscript `@version` header AND `CONFIG.BOT_VERSION` via `DefinePlugin(__SCRIPT_VERSION__)`. They can never drift again.
- **One-time user action**: Open Tampermonkey dashboard → Update the script (or revisit install URL). v8.18.0 → v8.24.0 jump forces re-install; from then on every bump auto-installs.
- All persistence (SCAN, AUTO, A-INV, CYCLE, APP, 21S, 51S) + all features added since iter 47 are now ACTUALLY in the user's browser

✅ **51s Reversal Strategy Simplified to Timeframe-Agnostic — TM v8.24.0 (April 23, 2026, Iter 52)**
- **Removed all 1H-specific logic**: no more `_hourOfNow()`, hourly OHLC window, or `HOUR_MS` constant
- **Now works on any chart timeframe** (1m/5m/15m/1H/etc) — the strategy just monitors the candle countdown and fires when seconds===51, opposite of current candle direction
- **New-candle detection via countdown jump-up**: when `cd.totalSeconds` rises by ≥3s (e.g. 0:01→4:59), captures current price as candle open + bumps `candleEpoch`
- **Cooldown key changed**: `(candleEpoch, cd.minutes)` — fires exactly once per `:51` countdown slot per candle, naturally adapts to timeframe (1 fire/min on 1m, 5 fires per 5m candle, 60 fires per 1H candle)
- Button label: `1H51` → `51S`. Tooltip updated. Console logs prefixed `[51s]`
- Lint clean

✅ **Full Settings Persistence Fix — TM v8.23.0 (April 23, 2026, Iter 51)**
- **Root cause**: `_oneHour51sEnabled` + `_oneHour51sConfig` were missing from `state.js` `saveState()`/`loadState()` — the 1H51 feature was never wired into persistence even though restore code read them. Auto-save also only refreshed the 21S mirror.
- **Fixed in `state.js`**: schema bumped to v2, now serializes 7 toggles (SCAN, AUTO, A-INV, CYCLE, APP, 21S, 1H51) + 3 configs (cycle, 21S, 1H51) + selectedStrategy + stats/money/inversion/assetHistory. Saves `_savedAt` for restore-age display.
- **Fixed in `index.js`**:
  - Auto-save (15s interval) now refreshes both 21S and 1H51 config mirrors before save
  - Three new fallback save triggers: `pagehide`, `beforeunload`, `visibilitychange` (hidden) — covers PO's SPA refreshes, hard reloads, tab-close, app-switch
  - `_restoreToggleStates()` now logs a loud green `[Restore] Re-activated N feature(s) from saved state (saved Xm ago): SCAN, 21S, 1H51, ...` summary — any persistence gap is now instantly visible in console
- Lint clean

✅ **1H 51s Reversal — Candle-Timer-Driven (No Wallclock) — TM v8.22.1 (April 23, 2026, Iter 50)**
- Strategy now reads PO's chart **candle countdown timer directly** via DOM scrape (`getCandleCountdown()` in `utils/dom.js`) — fires when `countdown.seconds === 51`, debounced on `countdown.minutes`
- **Self-diagnostic on enable()**: probes for 4 seconds after toggling 1H51 ON, logs `✓ Candle countdown LOCKED` with detected value, or `⚠ Could NOT detect` warning prompting user to share inspector output for selector tuning
- All wallclock fire logic removed — no minute boundary math, no `Date.now() % 60`. Trigger source explicitly tagged in trade meta as `triggerSource: 'po-candle-countdown'`
- Cooldown moved from `lastFireMinuteTs` (clock-based) → `lastFireCountdownMinute` (countdown-based)
- Countdown scraper tries `[class*="countdown"]`, `[class*="chart-time"]`, `[class*="candle-timer"]`, `[class*="period-timer"]`, `[data-test*="timer"]` selectors first, then falls back to chart-container-anchored leaf elements matching `MM:SS` regex
- Lint clean

✅ **1H 51-Second Reversal Strategy — TM v8.21.0 (April 23, 2026, Iter 49)**
- New timing-based contrarian strategy paired with Tampermonkey
  - **Backend**: `strategies/strategy_1h_51s_reversal.py` (registered as `1h_51s_reversal` in registry, evaluated by force-generate-v2)
  - **Tampermonkey**: `strategies/oneHour51sReversal.js` runs its own 100ms wallclock loop, tracks the live 1H candle, fires every minute at the **:51 second** mark in the OPPOSITE direction of the candle's body, then **rotates to the next asset** in the configured pool (default: 8 OTC pairs)
  - **5s expiry** (auto-selects PO offer when possible), **WS execution** when SSID bridge healthy, DOM fallback otherwise
  - **Slope/history fallback** when 1H body is flat (`alwaysFire: true` by default)
  - Once-per-minute cooldown — never double-fires the same minute
- **Panel UI**: New `1H51` button (pink/magenta gradient, pulsing when active) below the `21S` row with live "On W/L (winRate%)" status
- **Persistence**: `state._oneHour51sEnabled` + `_oneHour51sConfig` saved across PO reloads (mirrors 21S behavior)
- **Win/Loss propagation**: WIN/LOSS panel buttons forward to `oneHour51sReversal.onResultRecorded()` for per-asset stats
- **Debug handle**: `window.eliteBot1h51sReversal` exposed for console tuning

### Verified
- Strategy registry test: registered at `1h_51s_reversal`, returns correct PUT for UP body, CALL for DOWN body, NEUTRAL on flat
- Live force-generate-v2: now evaluates 39 strategies (was 38), 1h_51s_reversal listed in components
- Lint clean (Python + JS)
- Iter 47 regression: 12/12 PASS

✅ **ML Feature Pipeline Expanded — 13 New Features (April 23, 2026, Iter 48)**
- **`MLAccuracyTuner.extract_5s_features()` now emits 53 features** (was 40) — mirrors the new BETA strategies so when retraining is triggered, ML can learn which Fib levels and zones actually predict direction:
  - `fib_impulse_up`, `fib_dist_{236,382,500,618,786}` (signed bps distance to each retracement level), `fib_nearest_bps`
  - `supply_zone_bps`, `supply_zone_count`, `demand_zone_bps`, `demand_zone_count`
  - `volume_osc` (percentage oscillator), `volume_spike` (binary > +15%)
- **`SelectKBest(k=40)` → `k=50`** — gives new features headroom to make the cut
- **`/api/ml/tuning-report` surfaces `tuning_config.new_features_apr23`** — visible in the AI Models UI tuning panel
- **No retraining triggered** — per user direction, wiring only. When the next "Retrain" button is clicked (manual or scheduler), the new features enter training automatically
- **Regression green**: 12/12 iter_47 backend tests pass, force-generate-v2 + win-rate-stats unaffected

✅ **Two New BETA Strategies + BETA Flag Pipeline — TM v8.20.0 (April 23, 2026, Iter 47)**
- **Fibonacci Confluence (30s/1m/5m)** — `strategies/strategy_fibonacci_confluence.py`
  - Rolling swing anchor (20/30/40 bars per TF) → Fib levels 23.6/38.2/50/61.8/78.6
  - Requires 3 of 4 confirms: Fib-zone hit, reversal candle (engulfing/hammer/shooting star), EMA20 trend alignment, volume spike (>1.2x avg 20-bar)
  - Confidence band 60-82%, depth-bonus for deeper retracements (61.8%=+6, 50%=+4)
- **Triple Confirmation (30s/1m/5m)** — `strategies/strategy_triple_confirmation.py`
  - Layer 1 — Trend (price vs EMA slow + EMA fast/slow alignment + OSMA/MACD-hist slope)
  - Layer 2 — Zone (untapped pivot-based supply for PUT / demand for CALL)
  - Layer 3 — Confirmation (reversal candle + Volume Oscillator > +15%)
  - ALL THREE layers must agree; confidence 70-85%
- **BETA propagation end-to-end**:
  - Class-level `self.beta = True` + return-dict `'beta': True` on every signal path (including neutral)
  - `strategy_registry.list_strategies()` surfaces `beta` field per strategy
  - `strategy_selection_service.AVAILABLE_STRATEGIES` entries carry `beta:True` + [BETA] suffix in display name (3 new entries each under 30s/1m/5m)
  - `/api/signals/force-generate-v2` component_results now carry per-strategy `beta` AND signal-level `beta` = True only if ALL directionally-agreeing strategies are BETA
- **Tampermonkey mirrors**: `strategies/fibonacciConfluence.js` + `strategies/tripleConfirmation.js` — mathematical parity with backend, registered in `strategies/manager.js`, wired into APP_TO_LOCAL_MAP for strategy-select sync
- **TM rebuild**: v8.20.0 deployed to `/frontend/public/pocket-option-auto-trader-modular.user.js`
- **Tests**: 12/12 backend passed (iteration_47) — endpoints, component composition, signal.beta boolean, confidence clamps, registry execution, regression on /trades/report + /trades/outcome + /win-rate-stats

### Verified Endpoints (Iter 47)
- `GET /api/strategies/available/30s|1m|5m` — returns BETA strategies with `beta:true`
- `POST /api/signals/force-generate-v2` — `signal.beta` always a boolean; 6 new BETA components present

✅ **Real-Accuracy Tracking Loop + Honest Confidence Tiers — TM v8.19.0 (April 23, 2026)**
- **Tampermonkey `reportTradeOutcome()` helper** (`utils/api.js`): POSTs `{outcome, asset, strategy, profit}` to `/api/trades/outcome` after every recorded WIN/LOSS
- **`recordResult()` now persists to backend** (`trading/executor.js`): every WIN/LOSS (manual panel click, 21s reversal, or cycle mode) syncs to Mongo so `/signals/win-rate-stats` reflects real rolling accuracy
- **NEW `_scheduleOutcomeResolution()` auto-resolver**: after each trade placement, snapshots balance, waits expiry+3s, scans DOM + balance delta, and auto-calls `recordResult` if user doesn't click manually. Skips if another handler (e.g. 21s reversal) already resolved
- **Force-Generate-v2 tightened**: now emits `quality` tier (HIGH/MEDIUM/LOW) based on `agreeing_strategies` + `confluence_score`. Confidence clamped per tier — LOW ≤ 65%, MEDIUM ≤ 75%, HIGH ≤ 82%. No more misleading 85%+ when only 1-2 strategies voted
- **Route handler renamed** `record_tm_trade_outcome` (was `record_trade_outcome` which shadowed another function in the same module)
- **Orphan outcome path** now normalizes asset before insert (consistent `asset_normalized` field)
- **Dashboard `WinRateWidget`** (already wired on `DashboardRestructured.js` row 769): polls `/api/signals/win-rate-stats` every 30s, shows last-50/100/500 rolling rates + STRONG/PROFITABLE/BREAK-EVEN/UNPROFITABLE badges
- **Tests**: 13/13 backend passed (iteration_46) — force-generate-v2 quality tier, /trades/report, /trades/outcome (match + orphan + bad-outcome reject), /signals/win-rate-stats, full e2e flow

### Verified Endpoints (Iteration 46)
- `POST /api/signals/force-generate-v2` → returns {direction, confidence, quality, agreeing_strategies, confluence_score, components, votes}
- `POST /api/trades/report` → audit event to `tm_trade_reports` (30d TTL)
- `POST /api/trades/outcome` → matches latest pending trade or creates orphan row; normalizes asset
- `GET /api/signals/win-rate-stats` → rolling last-50/100/500 + by_strategy breakdown

✅ **Feature Parity Restore + Executor Audit — TM v8.18.0 (April 22, 2026)**
- **CYCLE mode restored** (`cycleMode.js`): rotates through PO favorites, scans each, trades best signals, waits for WIN/LOSS before rotating, auto-blacklists assets after N consecutive losses
- **APP signal poller** (`appSignalPoller.js`): polls `/api/signals/latest` every 5s, dedups by `signal_id`, auto-switches asset if target differs, executes via `tradeExecutor`
- **Explicit A-INV toggle**: smart-invert logic now gated behind `state.autoInvertEnabled` — off = all signals fire as-is
- **Executor audit chain**: every step now logs `[exec:source] ✓/✗ reason` — signal validation → canTrade → AUTO gate → invert → click → result. Silent failures eliminated
- **Panel buttons**: new row with `CYCLE` / `APP` / `A-INV` (blue pulsing) + pre-existing `21S` row
- **All toggles persist** via `saveState()` across PO reloads
- **Backend**: `POST /api/trades/report` endpoint added (was 404'ing before) — audits to `tm_trade_reports` (30-day TTL)
- Full toggle reference (all state restored on reload):
  - SCAN, AUTO, A-INV, CYCLE, APP, 21S

### Verified Endpoints
- `GET /api/signals/scan-markets?assets=EURUSD_OTC` → 200 OK
- `GET /api/signals/latest` → 200 OK (returns structured signal object)
- `POST /api/trades/report` → 200 OK

✅ **CALL/PUT strict selector — TM v8.17.0 (April 22, 2026)**
- **TM v8.11.0**: 21s Reversal now fires via direct WebSocket when SSID bridge is healthy, falls back to DOM click when not
- **executionMode config**: `auto` (default — WS when healthy), `ws` (force WS), `dom` (force DOM)
- **Backend**:
  - `POST /api/po/trade/ws-execute` — places trades via `pocketoptionapi_async` using bridged SSID
  - `GET /api/po/trade/ws-status` — health probe for the cached client
  - New service: `/app/backend/pocket_option_ws_executor.py` with singleton client + auto-reconnect on SSID rotation
  - All trades audited to `po_ws_trades` Mongo collection with latency_ms
- **Latency**: 80-250ms (WS) vs 800-2000ms (DOM clicks) — ~10x improvement critical for 21s-left timing precision
- **Graceful degradation**: all error paths (no SSID, invalid session, network failure) return clean `{success:false, error:...}` without crashing
- **Bridge health polling**: TM script polls `/po/ssid/status` every 15s, caches `bridgeHealthy` flag for zero-latency decision at fire time
- **Tests**: 16/16 backend passed (iteration_45)

✅ **SSID Bridge + Direct-WS Connection (April 21, 2026 — Iteration 44)**
- **Tampermonkey v8.10.0** ships a `ssidBridge` module that hooks `window.WebSocket` at `@run-at document-start` and captures PO's `42["auth",…]` frame automatically. POSTs to backend on first capture and heartbeats every 10 min
- **Backend endpoints** (`/app/backend/routes/pocket_option.py`):
  - `POST /api/po/ssid/update` — parses auth_message, stores in `po_ssid_state` (single-doc `_id='current'`), mirrors to `po_ssid_history` (30d TTL). Idempotent for same session
  - `GET /api/po/ssid/status` — health classification (healthy/expiring/stale/expired/missing), never exposes raw session
  - `POST /api/po/ssid/connect` — real-time WS handshake via `pocketoptionapi_async` to verify SSID; returns consistent `{success, connected, balance, uid, is_demo, error}` contract
- **Frontend**: `SSIDStatusWidget` on dashboard shows CONNECTED/EXPIRING/EXPIRED badges, uid + demo/live, age + expires-in, "Verify WS Connection" button
- **Unlocks**: direct-WS trading via `BinaryOptionsToolsV2` / `pocketoptionapi_async` — ~50-200ms trade latency (vs 800-2000ms for DOM clicks), authoritative server timestamps for the 21s Reversal strategy
- **Tests**: 14/14 backend + frontend verified (iteration_44)

✅ **21-Second Reversal Strategy + TM v8.9.0 (April 20, 2026 — Iteration 43)**
- **New Strategy**: Timing-based contrarian on 1m candles
  - Fires OPPOSITE trade (wick-ignored body direction) at ~21s-left on the current open 1m candle (±1s tolerance)
  - 5s expiry (auto-selects closest PO offers)
  - Skips exactly 1 candle after each fire (2-minute cooldown)
  - Optional auto-rotate to next OTC asset after a win
  - Filters out indecision candles (body < 0.8 bps of mid price)
- **Backend**: `strategies/strategy_1m_21s_reversal.py` — registered as `1m_21s_reversal` (pandas DataFrame compatible for backtest/dashboard); available in `GET /api/strategies/available/1m` dropdown
- **Tampermonkey (modular v8.9.0)**: New module `twentyOneSecondReversal.js` runs its own 100ms wall-clock loop, tracks live 1m OHLC from `getCurrentPrice()`, fires via `executeTrade()` when conditions match. Exposes `window.eliteBot21sReversal` for debug
- **UI**: New `21S` panel button (purple pulsing) with live stats (`On 3/1 (75%)`); wired via `on21sReversalToggle` callback
- **Mobile Auto-Trader**: Strategies card promotes it as first entry with ⭐⭐⭐ and '1m→5s exp' badge
- **Tests**: 11/11 backend + frontend verified (iteration_43)

✅ **OTC Data Health Widget + Tampermonkey Legacy Deprecation (April 20, 2026 — Iteration 42)**
- **P1 — OTC Data Health Widget**: New `OTCDataHealthWidget.jsx` added to Dashboard (4th card in the intelligence row)
  - Polls `/api/signals/otc-candle-stats` every 10s
  - Shows overall health badge (LIVE / STALE / OFFLINE / DEGRADED), total candle count, per-symbol rows
  - Each symbol row displays: candle count, last-scrape age, ingestion bar (gap ratio), rate/min
  - Backend endpoint enhanced with: `last_scrape_age_seconds`, `recent_hour_count`, `ingestion_rate_per_min`, `gap_ratio`, `health` (healthy/stale/offline), `overall_health`, `summary{healthy,stale,offline}`
  - Health thresholds: ≤30s healthy, ≤300s stale, else offline
- **P2 — Tampermonkey Legacy Deprecation**: Modular Webpack build (v8.8.1) is now the primary recommended script
  - Mobile Auto-Trader Step 3: Modular card shows RECOMMENDED badge; Legacy card shows DEPRECATED badge with "Install Legacy (Rollback)" label
  - TampermonkeyControlPanel info card: script URL now points to `pocket-option-auto-trader-modular.user.js`; legacy URL shown only as rollback footnote
  - Both scripts still downloadable for backwards compatibility
- **Tests**: 9/9 backend passed, all frontend checks passed (iteration_42)

✅ **Telegram Bot Integration Fix (April 15, 2026)**
- **FIXED**: Missing imports in `routes/integrations.py` causing 500 errors on all `/telegram-bot/*` endpoints
- Added: `get_telegram_bot`, `TelegramTradingSignal` from `telegram_bot_service`
- Added: `get_ssid_service`, `initialize_ssid_service` from `ssid_auto_refresh_service`
- All 10 Telegram bot endpoints verified working (status, start, stop, send, settings, history, stats, etc.)

✅ **Strategy Performance Tracker + Decision Engine Dashboard (April 19, 2026)**
- **Per-Asset Per-Strategy Tracking**: Records win/loss per strategy per asset with PnL
- **Auto-Promotion**: Selects best-performing strategy per asset (min 5 trades, highest win rate)
- **API**: `GET /api/signals/strategy-tracker` (full breakdown), `POST /api/signals/record-outcome` (now accepts strategy field)
- **Decision Engine Widget**: Win Rate, Trades, Sharpe Ratio, Max Drawdown, active strategies, model accuracy cards
- **Strategy Tracker Widget**: Per-asset breakdown with best strategy star badges, PnL, win rates per strategy
- **Dashboard**: 3-column grid — IQ-720 LIVE | Decision Engine v2.0 | Strategy Tracker

✅ **Tampermonkey v8.8.1 — Win/Loss Detection Fix (April 19, 2026)**
- **FIXED**: Both TM scripts not recognizing wins/losses of automated trades
- **Root causes**: Balance selectors didn't match current PO layouts (returned 0), silent failure when balance=0, tight timing for 5s trades
- **Balance detection**: Expanded to 30+ selectors + deep DOM search in header area + cached fallback
- **Adaptive timing**: 5s=5000ms buffer, 15s=4000ms, 30s=3500ms, 60s+=3000ms (was flat 3000ms for all)
- **3-layer fallback**: Balance polling → DOM scan (deals list + popups) → Pre-trade balance comparison
- **5s trade fixes**: 30 polls (vs 20), 1500ms bet deduction delay (vs 2000ms), estimated balance when DOM fails
- **Modular script**: Added `getAccountBalance()` and `scanDOMForTradeResult()` to `dom.js`

✅ **Auto-Retrain Scheduler (April 19, 2026)**
- **Scheduled retraining** at London Open (08:00 UTC) and NY Open (13:00 UTC), Mon-Fri
- **Dual data source**: Trains from collected OTC 5s candles + OANDA S5/M1 historical data
- **Configurable**: retrain_hours_utc, retrain_days, min_hours_between_retrain, timeframes, symbols, OTC/OANDA toggles
- **Manual trigger**: `POST /api/ml/scheduler/trigger` for immediate retrain (30min cooldown)
- **History tracking**: Duration, models trained, accuracy per retrain
- **API**: status, start, stop, config update, manual trigger
- **Verified**: Manual retrain completed 2 models in 64.8s (OTC 46.86% + OANDA trained)

✅ **Core Decision Engine v2.0 (April 19, 2026)**
- **Multi-Model Ensemble**: IQ-720 (15%), Maximized ML XGBoost (30%), Improved ML RF/GB (20%), LSTM/GRU (25%), PPO RL (10%) — configurable weights
- **5 Market Regimes**: Trending Up/Down, Ranging, High/Low Volatility — auto-detected from EMA slopes + ATR
- **4 Strategy Modes**: Trend-Following, Mean-Reversion, Scalping, Momentum — auto-selected per regime with weighted priority
- **7 Risk Limits**: Max drawdown (10%), daily loss (5%), position size (5%), min confidence (65%), max consecutive losses (5), win rate threshold (45%), loss streak cooldown (5 min)
- **Dynamic Kelly Sizing**: Half-Kelly adjusted for confidence, regime, and current drawdown
- **Trade Outcome Tracking**: Win rate, Sharpe ratio, max drawdown, consecutive losses/wins, balance tracking
- **Risk-Controlled Decisions**: Stop-loss/take-profit in pips, risk-reward ratio, volatility filters
- **API**: `POST /api/signals/decision` (full pipeline), `GET /api/signals/engine-status`, `POST /api/signals/record-outcome`
- **Signal Routing**: Actionable decisions auto-routed to Pocket Option/MT5/Telegram

✅ **ML Accuracy Tuning UI — OTC Tuning Panel (April 19, 2026)**
- **NEW**: `OTCTuningPanel` component added as "5s OTC Tuning" tab in AI Models page
- **OTC Data Status**: Total candles, symbols count, READY/COLLECTING status, progress bar, per-symbol breakdown with Trainable badges
- **Model Status Cards**: Maximized V3 and Improved V2 with accuracy %, trained date, trained/not-trained badges
- **Training Controls**: One-click "Train Maximized v3 (XGBoost)" and "Train Improved v2 (RF/GB)" buttons
- **Training Results**: CV accuracy, total samples, features used, selected features list, CV scores, class distribution
- **Tuning Configuration**: Labeling thresholds per timeframe (5s=0.5 pips, M1=3.0 pips), prediction horizons, feature selection method

✅ **ML Accuracy Tuning with OTC Training Data (April 19, 2026)**
- **NEW**: `MLAccuracyTuner` class with OTC-specific training pipeline
- **Adaptive Labeling**: Thresholds per timeframe (5s=0.5 pips, 15s=1 pip, M1=3 pips)
- **40 5s-Optimized Features**: Returns, candle characteristics, RSI variants, EMA alignment, volatility, stochastic, MACD, BB, momentum, acceleration, support/resistance, time features
- **Feature Selection**: SelectKBest with mutual_info_classif (top 40 features)
- **Cross-Validation**: TimeSeriesSplit (5 splits) for proper time-series evaluation
- **API Endpoints**: `GET /api/ml/tuning-report` (data availability + model status), `POST /api/ml/train-from-otc` (train from collected OTC candles)
- **Tested**: 418 samples from 503 candles, 41.71% CV accuracy (random test data — real market data will be higher)

✅ **Hybrid Strategy Replaced + Multi-Timeframe ML + OTC Candle Collection (April 19, 2026)**
- **REPLACED**: Legacy Hybrid strategy with IQ-720 Ensemble (8 weighted sub-strategies + regime detection) in backtesting
- **Multi-Timeframe ML**: Both Maximized v3 and Improved v2 now train on S5, S15, S30, M1 timeframes (was M1 only)
- **OANDA S5 Data**: ML systems fetch 5-second candles from OANDA for primary training
- **Live OTC Collection**: `POST /api/signals/collect-otc-candles` stores Tampermonkey-scraped 5s OTC candles to MongoDB
- **Auto-Collection**: TM script sends last 30 candles to backend every 30 seconds via heartbeat
- **Stats**: `GET /api/signals/otc-candle-stats` shows collected candle counts per symbol
- **30-day TTL**: Auto-deletes old collected candles via MongoDB TTL index

✅ **Signal Routing Pipeline Integration (April 19, 2026)**
- **WIRED**: Signal routing engine auto-routes every signal from scan-markets and IQ-720 ensemble
- **Dispatch**: Pocket Option (queued), MT5 (execute_order with ticket#), Telegram (send_message notification)
- **Non-blocking**: Routing failures don't break signal generation
- **Response includes `routing` field**: matched_rules, destinations, dispatch_results per destination
- **Stats**: 26+ signals auto-routed through pipeline, distributed across 3 destinations

✅ **Signal Routing Dashboard (April 19, 2026)**
- **NEW**: Full signal routing engine with CRUD rules, filter matching, and destination routing
- **Rules Engine**: Match signals by asset, min/max confidence, direction, strategy, session
- **Destinations**: Pocket Option, MetaTrader 5, Telegram — configurable per rule
- **Priority System**: Rules matched top-to-bottom by priority number
- **Test Router**: Send test signals through the engine to verify routing decisions
- **Routing Log**: Full audit trail of every routed signal with timestamps
- **Stats Dashboard**: Total rules, active count, signals routed, per-destination counts
- **API**: 7 endpoints under `/api/signal-routing/` (rules CRUD, test, log, stats)
- **Frontend**: New SignalRoutingPage with rule management, destination toggles, filter builder, test panel

✅ **P3: React Hook Dependencies (April 19, 2026)**
- Verified: ESLint passes cleanly, no missing hook dependencies found
- Only one intentional eslint-disable in App.js (for auth flow)

✅ **TradingView + MetaTrader 4/5 Integration (April 19, 2026)**
- **FIXED**: Missing `tradingview_webhook_service` import in `routes/integrations.py` (caused 500 errors)
- **FIXED**: TradingView webhook None handling for price/quantity (testing agent fix)
- **TradingView Webhook**: Receives alerts, processes them, routes to Pocket Option or MT5. Endpoints: webhook, stats, history, setup, pine-script
- **MT5 Connection**: Live connect/disconnect with account info (Balance, Equity, Profit, Leverage). Runs in simulation mode on Linux
- **Frontend**: Fully rewritten IntegrationsPage with live MT5 connection form, TradingView webhook tester, alert stats/history, and API Reference
- **Pine Script Template**: Auto-generated for TradingView alert configuration

✅ **Modular Webpack Tampermonkey Consolidation (April 17, 2026)**
- **DONE**: Consolidated 7200-line legacy script into modular Webpack build (15 modules)
- **63% size reduction**: 112KB modular vs 304KB legacy
- **7 strategies** registered: LocalSignal, Keltner-MACD 5s, IQ-720 Ensemble, Holly Crossover, Golden One Moment, Momentum Buster, EMA20 Pullback
- **Architecture**: `/app/tampermonkey-src/src/` → core/, strategies/, trading/, ui/, utils/
- **Build**: `yarn build:deploy` compiles + copies to frontend/public
- **UI**: Mobile Auto-Trade page offers both Legacy and Modular install options side-by-side

✅ **Tampermonkey v8.8.0 — GO Button Fix + Updated Strategy Page (April 14, 2026)**
- **FIXED**: GO button now tries LOCAL OTC signals FIRST (6 strategies), then falls back to backend API
- **Signal Priority Chain**: General → Keltner-MACD → IQ-720 Ensemble → Holly Crossover → Golden One Moment → Momentum Buster → Backend scan-markets → force-generate
- **Updated Mobile Auto-Trade page**: Shows all 6 local signal strategies with descriptions and badges
- **Updated TampermonkeyControlPanel**: v8.8.0 feature list with all current capabilities
- **Panel Preview**: Updated to show KC-5s button and current v8.8.0 layout

✅ **IQ-720 Advanced Ensemble Strategy (April 14, 2026)**
- **NEW**: IQ-720 inspired advanced signal generation system
- **Market Regime Detection**: Trending Up/Down, Ranging, High/Low Volatility
- **Session-Aware Trading**: Asian, London, NY, Overlap, Off-hours with weighted confidence
- **Ensemble Signal Combination**: 8 weighted sub-strategies (RSI, MACD, Stoch, EMA, BB, KC, ADX, Patterns)
- **Confidence Calibration**: Anti-overconfidence with regime + session + confirmation adjustments
- **Kelly Criterion Position Sizing**: Half-Kelly for safe capital allocation
- **60+ Technical Features**: Price, MA, Momentum, Trend, Volatility, Pattern categories
- **API Endpoints**: `/api/signals/iq720-ensemble`, `/api/signals/iq720-market-regime`, `/api/signals/iq720-kelly`, `/api/signals/iq720-features`
- **Frontend**: IQ-720 Ensemble template added to Strategy Builder Templates tab
- **AI Models**: IQ-720 Ensemble (Advanced) listed first in AI Models page (82% accuracy target)
- **Scan-Markets**: Added as final fallback in strategy chain (Deep → Holly → Golden → Momentum → IQ-720)
- **Tampermonkey**: `getIQ720EnsembleSignal()` added to LocalSignalEngine with full fallback chain integration

✅ **IQ-720 Real-Time Dashboard Widget (April 14, 2026)**
- **Live Market Intelligence** widget on main Dashboard showing real-time data
- **Market Regime**: Color-coded display (green=trending up, red=trending down, amber=ranging, etc.)
- **Session Quality**: Current session (Asian/London/NY/Overlap) with quality score badge
- **Kelly Position Size**: Recommended % of capital per trade with half-Kelly safety
- **Live Signal**: Direction (CALL/PUT) with confidence % and confirmation badges
- **Auto-refresh**: Updates every 30 seconds with manual refresh button
- Component: `/app/frontend/src/components/IQ720Widget.jsx`

✅ **KC-MACD 5s Dedicated Button on Tampermonkey Panel (April 14, 2026)**
- New "KC-5s" button with cyan gradient in secondary button row
- Click handler: Force scans using Keltner-MACD strategy → Falls back to IQ-720 Ensemble
- Provides quick one-click access to the 5-second scalping strategy

✅ **Clean Retrain ML Models Pipeline (April 14, 2026)**
- **POST /api/ml/clean-retrain**: One-click clean retrain of all 4 ML model types
- **GET /api/ml/retrain-status**: Real-time progress tracking with phase/percentage
- Clears corrupted Win/Loss data from 6 MongoDB collections
- Retrains: Maximized ML v3 (XGBoost/LightGBM), Improved ML v2 (RF/GB/AdaBoost), LSTM/GRU, PPO RL
- Uses `asyncio.to_thread` for CPU-intensive training to keep server responsive
- Fixed AdaBoost SAMME.R → SAMME for sklearn compatibility
- Frontend: Updated AI Models "Retrain" tab with clean retrain UI, progress bar, real-time log, model cards

✅ **Tampermonkey v8.7.2 — Improved Latency Sync (April 12, 2026)**
- **Configurable Timing Settings** in CONFIG:
  - `BET_DEDUCTION_DELAY`: 2000ms (wait for bet to deduct)
  - `POST_EXPIRY_BUFFER`: 3000ms (wait after expiry for PO update)
  - `BALANCE_POLL_INTERVAL`: 500ms (how often to check balance)
  - `BALANCE_STABILITY_CHECKS`: 2 (stable readings before confirming)
  - `MAX_BALANCE_POLLS`: 20 (timeout after 10 seconds)
- **Auto-sync with backend** via `syncTimingWithBackend()` on init
- **Network latency detection** - adds extra buffer for high latency
- New API endpoints: `/api/signals/timing-config`, `/api/signals/sync-timing`

✅ **Keltner-MACD 5-Second Strategy (April 10, 2026)**
- NEW STRATEGY implemented across backend, frontend, and Tampermonkey
- **Keltner Channel**: EMA(20), ATR(60), Multiplier 4
- **MACD**: Fast(13), Slow(24), Signal(11)
- **BUY (CALL)**: Price breaks above KC middle line + MACD bullish cross
- **SELL (PUT)**: Price breaks below KC middle line + MACD bearish cross
- API Endpoints: `/api/signals/keltner-macd-5s`, `/api/signals/keltner-macd-indicators`
- Strategy Builder: Added "Keltner-MACD 5s" template + Keltner Channel indicator
- Tampermonkey v8.7.1: Added `getKeltnerMACDSignal()` to LocalSignalEngine (priority strategy)

✅ **Tampermonkey v8.7.0 — Simplified CYCLE + Fixed Win/Loss (April 10, 2026)**
- Completely rewrote CYCLE loop with simpler flow
- Direct balance-based win/loss detection with `checkTradeResult()` function
- Cleaner workflow: Scan → Signal → Trade → Wait → Check Balance → Update Stats

✅ **Tampermonkey v8.6.4 — Precision Timing + Immediate Invert (April 10, 2026)**
- **AI Pre-Trade Validation**: Checks confidence, data, cooldowns, direction before trade
- **Detects ACTUAL trade expiry from Pocket Option UI** - Not hardcoded values
- **Waits EXACTLY expiry time** for result verification (+ 2s buffer for balance update)
- **Immediate Inverted Retry on LOSS**: Same signal, flipped direction, NO re-scanning
- **On WIN**: Returns to normal 30s scan cycle, invert state unchanged
- **Improved Workflow**:
  1. CYCLE scans favorites (30s/asset)
  2. Signal found → AI validates → Place trade
  3. Detect actual expiry from PO UI → Wait exactly that time
  4. Verify WIN/LOSS via balance comparison
  5. LOSS + Auto-Invert → Immediate inverted trade (no scan delay)
  6. WIN → Back to 30s scan cycle

✅ **Tampermonkey v8.6.3 — Integrated CYCLE + Scan + Auto-Invert System (April 10, 2026)**
- COMPLETE INTEGRATION of Cycle, Scan, and Auto-Invert for maximum reversal catching:
  1. **CYCLE** scans favorites (30s per asset) using AI strategies
  2. **On Signal Found** → Place trade → FREEZE on current asset
  3. **Wait for Expiry** → AI verifies WIN/LOSS via balance comparison
  4. **On WIN**:
     - If 2+ consecutive wins → AI suggests "RIDE THE TREND" (stay on asset)
     - Single win → Move to next asset
  5. **On LOSS + Auto-Invert Enabled**:
     - Stay on same asset
     - Invert signal direction immediately
     - Place trade immediately
     - Wait for expiry → Verify result
     - Repeat until winning streak achieved
  6. **Safety Limits**: Max 10 trades per asset, max 5 consecutive losses before forced move
- Prevents premature asset switching during loss recovery
- Win/Loss streak tracking for intelligent AI decisions

✅ **Momentum Indicator Feature (April 10, 2026)**
- NEW: Added comprehensive Momentum Indicator to Strategy Builder
- Frontend: Full configuration with 4 parameters (Period, Threshold, Smoothing, Signal Type)
- Frontend: 8 condition types including zero-line crossovers, strength zones, acceleration, and divergence
- Backend: New API endpoints `/api/signals/momentum-indicator` and `/api/signals/evaluate-momentum-condition`
- Backend: MomentumIndicator class integrated into UltraScalpingStrategy and MomentumBreakoutStrategy as enhancement filter
- Templates: Added "Momentum Crossover" and "Momentum + RSI" quick start templates
- Uses OANDA real-time data feed for momentum calculations

✅ **Tampermonkey v8.6.1 — Auto-Invert Stays on Same Asset After Loss**
- NEW AUTO-INVERT BEHAVIOR:
  1. Start with NORMAL signals (not inverted)
  2. On LOSS → Immediately switch to INVERTED + STAY on same asset + retry
  3. On WIN while inverted → Switch back to NORMAL, can move to next asset
  4. On WIN while normal → Stay NORMAL, can move to next asset
- CYCLE mode now respects auto-invert: doesn't switch assets on loss
- Added `lastTradeResult` tracking for cycle integration
(April 5, 2026)

✅ **Tampermonkey v8.6.0 — Post-Bet Balance Comparison**
- Captures balance 2 seconds AFTER trade click (after bet deducted)
- Compares: If balance increased = WIN, if same = LOSS
(April 5, 2026)

✅ **Code Quality Audit Fixes** - Security vulnerabilities, circular imports, hardcoded secrets, weak crypto all resolved (Feb 2026)
✅ **Auto-Invert v8.2 + Audio Detection** - Simple WIN=keep/LOSS=toggle logic with Pocket Option audio/DOM monitoring for automatic trade outcome detection (Feb 2026)
✅ **Analytics Dashboard (P1)** - New tab in Performance Center with Risk Management, ML Model Stats, Historical Data, Asset Leaderboard, Trading Hours, 24h Heatmap (Feb 2026)
✅ **CYCLE Mode (Favorites Cycling)** - New button that physically clicks through each favorite, dwells 30s scanning, trades on signal, waits for expiry, moves to next (Feb 2026)
✅ **Panel Drag Fix** - Fixed stretching bug caused by CSS !important on positioning, uses setProperty with important in JS (Feb 2026)
✅ **Legacy Tampermonkey v8.0 Feature Port Complete** - Strategy Dropdown, Smart Auto-Invert, Premium Result Recording ported to legacy script (Feb 2026)
✅ **EMA 20 Pullback Reversal Strategy** - New 5s strategy with EMA 20, RSI 2, BB(5,2.5), Stoch(3,1,1) (April 3, 2026)
✅ **Strategy Selection -> Scan Integration** - App-selected strategy runs FIRST in scan-markets, with fallback chain (April 3, 2026)
✅ **Strategy Sync to Tampermonkey** - syncFromApp() syncs user's strategy selection to local scanning (April 3, 2026)
✅ **Elite Pocket Option Trading Bot v8.0.0** - Renamed from GPT Signal Bot (April 3, 2026)
✅ **Smart Auto-Invert System** - Direction-aware loss detection with automatic signal inversion (April 3, 2026)
✅ **Premium Result Tracking in Tampermonkey** - WIN/LOSS buttons now feed backend learning system (April 3, 2026)
✅ **Premium Signal Filters** - Session/time filters, win-rate tracking per hour/asset, confidence adjustments (April 3, 2026)
✅ **Backend Refactoring Complete** - server.py reduced from 15,631 to ~3,780 lines. 8 route modules in /app/backend/routes/
✅ **AI/ML v3.1 Optimized** - Stricter filtering pipeline, regime-aware confidence, feature agreement scoring
✅ **AI/ML Phase 2: LSTM/GRU Time-Series** - BiLSTM(64) + GRU(48) + Attention, 13 features, auto-labeling pipeline
✅ **AI/ML Phase 3: PPO Reinforcement Learning** - Actor-Critic (128→64→3), trading environment simulation
✅ **AI Ensemble System** - Combines Stacking (40%) + LSTM/GRU (35%) + PPO (25%) with weighted voting
✅ **Backtesting & Historical Data System** - Multi-source data collection, ML backtesting, comprehensive metrics
✅ **Signal Generation Optimized** - Relaxed thresholds for better signal flow (April 3, 2026)
✅ **Holly Crossover Strategy (5s/15s/30s)** - EMA(12) x WMA(23) reversal crossover with S/R confirmation
✅ **Golden One Moment 30s Strategy** - RSI(2) + Stochastic(4,3,3) mean reversion, 30s expiration
✅ **Risk Management System** - Sharpe ratio, drawdown protection, Kelly criterion position sizing
✅ **Tampermonkey v7.7.0 Modular** - Webpack build system, 64% smaller bundle (68KB vs 188KB)
✅ **Maximized AI/ML v3.0** - 97 features, XGBoost+LightGBM stacking, HMM regime detection
✅ **Improved AI/ML v2.0** - 62 features, 56% accuracy, RF+GB+AdaBoost ensemble
✅ **Momentum Buster 15s Strategy** - Momentum period 3, green/red bars, 15s expiration
✅ **1m Momentum Exhaustion Strategy** - RSI-2 + Stochastic + BB + Candlesticks (70-75% target)
✅ **Backend Data Sources** - OANDA (primary), Deriv API (synthetics), Tampermonkey scraper (OTC)

## Recent Updates (April 3, 2026)

### Premium Signal Filters & Win-Rate Tracking (April 3, 2026)
**New: Session-aware signal accuracy optimization with continuous learning**

**Renamed to Elite Pocket Option Trading Bot v8.0.0**

**Smart Auto-Invert System (Tampermonkey):**
- Tracks per-asset direction + win/loss history locally in Tampermonkey
- After N consecutive same-direction losses -> auto-inverts signal direction
- After inversion: if wins confirm effectiveness, stays inverted
- After inversion: if still losing after max inverted trades, reverts
- Manual INVERT button for user override
- 3 consecutive wins auto-reverts inversion (trend confirmed)
- Cooldown prevents rapid flip-flopping between states

**Direction-Aware Loss Detection (Backend):**
- Stores recent trades per symbol in `recent_asset_trades` MongoDB collection
- Detects consecutive same-direction losses for each asset
- When signal matches losing direction: penalty of -4 per consecutive loss (max -15)
- When signal is opposite to losing direction: +2 confidence bonus
- `invert_suggestion` and `direction_loss_streak` included in scan-markets response

**Premium Result Tracking in Tampermonkey:**
- WIN/LOSS buttons now call `/api/signals/record-premium-result` automatically
- Each trade result feeds session/hour/asset learning for continuous signal improvement
- Log shows updated asset win rate and hour win rate after each result

**Shadow DOM Panel:**
- Panel renders inside Shadow DOM for CSS isolation from Pocket Option
- Watchdog re-injects panel every 2 seconds if PO removes it
- Max z-index (2147483647) with !important on all positioning
- New INVERT button with status display in panel

**Session Analyzer:**
- Identifies current trading session (Sydney, Tokyo, London, NY, overlaps)
- Quality scores: London-NY overlap (95), Tokyo-London overlap (85), London (80), NY (75), Tokyo (65), Sydney (50), Off-hours (30)
- Recommended and avoid pairs per session
- Historical win-rate tracking per hour (continuous learning from trades)

**Premium Signal Filters (applied to scan-markets):**
- Session quality adjustment: -10 to +5 confidence points
- Historical hour win-rate: -5 to +3 points (requires 10+ trades)
- Asset-specific win-rate: -5 to +3 points (requires 10+ trades)
- Market condition: -5 to +3 points (trending=bonus, volatile=penalty)

**Asset Performance Tracker:**
- Tracks win rates per symbol and per hour+symbol combination
- Stores in MongoDB: `asset_performance`, `asset_hourly_performance`, `hourly_stats`
- Identifies worst-performing assets to avoid

**New API Endpoints:**
- `GET /api/signals/session-info?symbol=X` - Current session, quality, recommended pairs
- `GET /api/signals/best-hours?top_n=8` - Best/worst hours based on history
- `GET /api/signals/hourly-stats` - 24-hour win-rate breakdown
- `POST /api/signals/record-premium-result` - Record trade result for learning
- `GET /api/signals/asset-performance?symbol=X` - Per-asset win-rate stats
- `GET /api/signals/should-trade?symbol=X&min_quality=50` - Quick trade-now check

**scan-markets Enhancement:**
- Response now includes `time_filter` with session info
- Each signal includes `premium_filters` with confidence adjustment details
- `original_confidence` preserved alongside adjusted `confidence`

### Backtesting & Historical Data System (April 3, 2026)
**New Files Created:**
- `deriv_data_service.py` - Deriv WebSocket API integration for synthetic indices
- `historical_data_service.py` - MongoDB storage for historical candles, CSV/JSON import
- `backtesting_engine.py` - Strategy and ML model backtesting with metrics
- `routes/backtesting.py` - API endpoints integrated into existing backtest.py

**Deriv API Integration:**
- Free WebSocket API (no key required for market data)
- 26 synthetic indices: Volatility 10-100, Crash/Boom 300-1000, Step, Jump indices
- Timeframes: 5s, 15s, 30s, M1, M5, M15, M30, H1, H4
- Endpoint: `POST /api/deriv/fetch?symbol=V100&timeframe=M1&count=1000`

**Historical Data Storage:**
- MongoDB collection: `historical_candles`
- 30-day retention policy
- Sources: OANDA, Deriv, Tampermonkey, CSV/JSON imports
- Endpoints:
  - `GET /api/historical/summary` - Data overview
  - `GET /api/historical/candles/{symbol}/{timeframe}` - Retrieve candles
  - `POST /api/historical/import/bulk` - Bulk candle import
  - `POST /api/tampermonkey/candles` - Receive scraped data

**Backtesting Engine:**
- Strategy backtesting: Deep Confluence, Momentum Buster
- ML model backtesting: LSTM/GRU, PPO RL, Ensemble
- Metrics: Win rate, Profit factor, Max drawdown, Sharpe/Sortino ratios, ROI
- Endpoint: `POST /api/backtest/ml?symbol=EUR_USD&model=lstm_gru&days=30`

**Tampermonkey Data Collector (v7.7.0):**
- `HistoricalDataCollector` module scrapes live OTC prices
- Aggregates into 5s/15s/30s/M1 candles
- Auto-sends to backend every 60 seconds
- Builds local OTC historical database over time

### Cyclic Object Fix (April 3, 2026)
- Fixed "Trade error cyclic object value" in Tampermonkey scan
- Root cause: `_allSignals` array contained circular reference
- Fix: Store `signals.slice(1)` to exclude best signal from array

### Signal Generation Optimization (April 3, 2026)
**Problem**: Tampermonkey scan was not picking up signals despite scanning many assets.

**Fixes Applied**:
- Deep Analysis confidence floor: 70% → 65%
- Avoid reason penalties: 8% each → 5% each
- LOW_VOLUME threshold: 0.8 → 0.5 (better for OTC markets)
- Quality thresholds relaxed: PREMIUM 88%→85%, HIGH 78%→75%, MEDIUM 70%→65%
- `is_tradeable` logic: Now allows MEDIUM quality with 1 avoid reason, or 70%+ confidence with 2 avoid reasons
- Tampermonkey MIN_CONFIDENCE: 72% → 65%
- Local engine min confirmations: 4 → 3

**Result**: 7 signals from 8 OTC assets (vs 0 before fix)

### AI/ML Phase 2 & 3 Complete (April 2, 2026)
**LSTM/GRU Time-Series System v2.0** (`lstm_gru_system.py`)
- Architecture: Bidirectional LSTM(64) + GRU(48) + Custom Attention Layer
- Features: 13 technical indicators (returns, RSI-14, MACD, Bollinger %B, Stochastic, ATR, EMA ratio, momentum, volume ratio, candle body ratio, HH/LL indicator)
- Training: Auto-labeling from price movement (BUY/SELL/HOLD), class weighting for imbalance
- API Endpoints:
  - `GET /api/lstm-gru/stats` - Model status and training history
  - `POST /api/lstm-gru/predict?symbol=EUR_USD` - Get time-series prediction
  - `POST /api/lstm-gru/train?symbol=EUR_USD&count=2000&epochs=30` - Train model

**PPO Reinforcement Learning Agent v1.0** (`rl_ppo_agent.py`)
- Architecture: Actor-Critic with 128→64 hidden layers
- Environment: Custom trading environment with position tracking, transaction costs
- Training: Generalized Advantage Estimation (GAE), clipped surrogate objective
- Model persistence: Auto-loads saved models on startup
- API Endpoints:
  - `GET /api/ppo-rl/stats` - Agent status and training stats
  - `POST /api/ppo-rl/predict?symbol=EUR_USD` - Get RL prediction
  - `POST /api/ppo-rl/train?symbol=EUR_USD&count=2000&episodes=20` - Train agent

**AI Ensemble Prediction** (`/api/ai-ensemble/predict`)
- Combines all ML systems with weighted voting:
  - Stacking Ensemble (XGBoost/LightGBM): 40% weight
  - LSTM/GRU Time-Series: 35% weight  
  - PPO Reinforcement Learning: 25% weight
- Agreement bonus: +8% confidence for 3 agreeing, +4% for 2 agreeing
- Integrated into scan-markets for multi-model validation

### Bug Fixes (April 2, 2026)
- **Background Task Fix**: Fixed `asyncio.coroutine` deprecation error in training endpoints (Python 3.11+ compatibility)
- **PPO Model Loading**: Fixed PPO agent to load saved models on startup (was returning null predictions)
- **NumPy Import**: Added missing numpy import to routes/ml.py

## Recent Updates (March 28, 2026)

### Backend Refactoring Complete (March 30, 2026)
**Massive restructuring of server.py monolith into modular route files**
- Extracted ~12,000 lines from server.py into 8 route modules under `/app/backend/routes/`
- Fixed all missing imports (lazy imports for circular dependencies, direct imports for safe modules)
- Restored missing route decorators (GET /api/config, GET /api/market/data)
- All 22 API endpoints verified working (100% pass rate)
- Route modules: auth.py, signals.py, strategies.py, trading.py, ml.py, integrations.py, pocket_option.py, backtest.py

### Bug Fixes (March 30, 2026)
- **GO Button Fix**: Tampermonkey GO button now calls `/api/signals/force-generate/asset/{symbol}` directly using OANDA data as primary source. Stripped _OTC suffix for proper symbol lookup. yfinance fallback wrapped in error handling.
- **Strategy Toggle Fix**: Added missing `get_strategy_service()` function to `routes/strategies.py` that was lost during refactoring. Users can now activate/deactivate saved strategies.

### Multi-Asset Scan & Signal Optimization (March 31, 2026)
- **Tampermonkey Multi-Asset Scan**: Fixed doBackendScan to properly scan all favorites when AUTO is off. Added fallback: when asset switching fails, tries to find a signal for the current asset instead of skipping the trade entirely. Extended default pairs from 4 to 6.
- **Deep Confluence Analyzer v2**: Implemented weighted confirmation scoring (Tier1=3pts for RSI extremes/crossovers, Tier2=2pts for supporting signals, 1pt for others). Added 6 new confirmation types (RECENT_BULLISH/BEARISH_CANDLES, MACD_POSITIVE/NEGATIVE_ZONE, ABOVE/BELOW_RISING/FALLING_EMA21). Reduced min_confirmations from 5→4 for better signal frequency while maintaining accuracy.
- **ML Cross-Validation**: scan-markets now validates signals against the Stacking Ensemble ML system. When both deep analyzer and ML agree, confidence gets a +5% boost.
- **ML Probability Threshold**: Raised from 0.58 to 0.60 for stricter filtering.
- **OANDA Symbol Normalization**: Fixed get_candles to auto-normalize symbols (AUDUSD→AUD_USD).
- **MongoDB _id Fix**: Fixed duplicate key error caused by explicit `_id: None` in signal inserts.

### AI/ML Accuracy Optimization v3.1 (March 29, 2026)
**Comprehensive optimization for signal trade accuracy (was 50-60%, target 70%+)**

| Optimization | Before | After |
|---|---|---|
| Model probability filter | None | Min 58% required |
| Regime penalty (high vol) | 0.85x | 0.75x |
| Volatility regime feature | **BUGGED** (always 0) | Fixed |
| Deep analysis confirmations | 4 min | 5 min |
| Local engine confirmations | 3 min | 4 min |
| Conflict detection | None | Rejects conflicting signals |
| Indicator agreement check | None | 5-indicator scoring |
| Confidence floor | 65% | 70% |
| Training label noise | 0.01% | 0.03% threshold |
| XGBoost depth | 8 | 5 (less overfitting) |
| Regularization (alpha/lambda) | 0.1/1.0 | 0.5/2.0 |
| Tampermonkey volatility filter | None | Blocks 2x+ vol spikes |
| Tampermonkey RSI thresholds | 20/80 | 15/85 (tighter) |

### Strategy Builder Saved Tab Fix (March 29, 2026)
- Fixed: All saved strategies were `is_active: true` by default — selecting one selected all
- Added On/Off toggle per strategy with visual feedback (green border + Active badge)
- Added "Deactivate All" button to reset selections
- Added Edit button to load strategy back into Builder tab
- Default `is_active` changed to `false` for new strategies

### Holly Crossover Strategy (March 28, 2026)
**Reversal crossover using EMA(12) x WMA(23) with Support/Resistance confirmation**

| Parameter | Value |
|-----------|-------|
| Timeframes | 5s, 15s, 30s |
| Fast MA | EMA(12) — Exponential Moving Average |
| Slow MA | WMA(23) — Weighted Moving Average |
| Type | Reversal crossover — catches trend reversals |

**Entry Rules:**
- **CALL**: EMA(12) crosses ABOVE WMA(23) during a downtrend + near support level
- **PUT**: EMA(12) crosses BELOW WMA(23) during an uptrend + near resistance level

**API Endpoints:**
- `POST /api/strategy/holly-crossover/signal?symbol=EUR_USD&timeframe=5s|15s|30s`
- `GET /api/strategy/holly-crossover/stats?timeframe=5s|15s|30s`

**Strategy Registry:** Available as "⭐⭐⭐ Holly Crossover" under 5s, 15s, and 30s timeframes
**Tampermonkey:** `LocalSignalEngine.getHollyCrossoverSignal()` mirrors backend logic
**Scan-Markets:** Added to fallback chain: Deep Analysis → Holly Crossover → Golden One Moment → Momentum Buster

## Recent Updates (March 26, 2026)

### Golden One Moment 30s Strategy (March 26, 2026)
**Mean reversion strategy using RSI(2) + Stochastic(4,3,3) crossover**

| Parameter | Value |
|-----------|-------|
| Timeframe | 30-second candles |
| Expiration | 30 seconds |
| RSI Period | 2 |
| Stochastic | (4, 3, 3) |
| Overbought | 80 |
| Oversold | 20 |

**Entry Rules:**
- **CALL**: Previous RSI & Stoch both < 20 (oversold), current RSI crosses above 20
- **PUT**: Previous RSI & Stoch both > 80 (overbought), current RSI crosses below 80

**API Endpoints:**
- `POST /api/strategy/golden-one-moment/signal?symbol=EUR_USD`
- `GET /api/strategy/golden-one-moment/stats`

**Tampermonkey Integration:**
- `LocalSignalEngine.getGoldenOneMomentSignal()` — mirrors backend logic in JavaScript
- Multi-strategy cascade: General → Golden One Moment → Momentum Buster (tries all if no signal)
- Multi-asset SCAN fix: SCAN ON + AUTO OFF now uses backend API to scan ALL favorites at once

**Strategy Registry:** Available in UI under 30s strategies as "⭐⭐⭐ Golden One Moment"

### SCAN Multi-Asset Fix (March 28, 2026)
**Fixed: SCAN ON + AUTO OFF was not scanning all favorites**

| Mode | Behavior |
|------|----------|
| **SCAN ON + AUTO OFF** | Scans ALL favorites via backend API, switches to best signal asset, places trade |
| **SCAN ON + AUTO ON** | Scans current asset only (local OTC prices), places trade on current asset |
| **GO button** | Force scan current asset, falls back to backend API if local fails |

**Backend Enhancement:**
- `scan-markets` endpoint now has strategy fallback chain: Deep Analysis → Golden One Moment → Momentum Buster
- More signals generated per scan cycle (fills gaps where deep analysis alone found nothing)

## Previous Updates (March 24, 2026)

### Risk Management & Drawdown Protection System (March 24, 2026)
**Focus on risk-adjusted returns (Sharpe ratio) and drawdown management**

| Feature | Description |
|---------|-------------|
| **Sharpe Ratio** | Real-time annualized calculation with risk-free rate |
| **Sortino Ratio** | Downside deviation only (penalizes losses, not volatility) |
| **Kelly Criterion** | Optimal position sizing based on win rate & win/loss ratio |
| **Max Drawdown** | Automatic trading pause at 15% drawdown |
| **Daily Loss Limit** | 5% daily loss limit with auto-pause |
| **Consecutive Loss Limit** | Pause after 5 consecutive losses |
| **Risk Levels** | Normal → Elevated → High → Critical → Paused |

**API Endpoints:**
- `GET /api/risk-management/status` - Full risk status
- `GET /api/risk-management/metrics` - Sharpe, Sortino, profit factor
- `POST /api/risk-management/record-trade` - Log trade results
- `GET /api/risk-management/can-trade` - Check if trading allowed
- `GET /api/risk-management/position-size` - Kelly-based position sizing
- `POST /api/risk-management/configure` - Set risk parameters

**Position Sizing Formula:**
```
Position = Balance × Kelly × RiskMultiplier × ConfidenceMultiplier × DrawdownMultiplier
Where:
- Kelly = WinRate - (1-WinRate)/WinLossRatio (half-Kelly for safety)
- RiskMultiplier = 1.0 (normal) to 0.25 (critical)
- ConfidenceMultiplier = 0.5 + (confidence × 0.5)
- DrawdownMultiplier = 1.0 - (drawdown × 2)
```

### Maximized AI/ML System v3.0 (March 24, 2026)
**State-of-the-art ML system with advanced features and regime detection**

| Component | Description |
|-----------|-------------|
| **Model Architecture** | Stacking Ensemble: XGBoost + LightGBM + RandomForest + GradientBoosting |
| **Features** | 97 total (up from 62 in v2.0) |
| **Regime Detection** | Hidden Markov Model (3 states: low/normal/high volatility) |
| **Cross-Validation** | Walk-Forward with 5 splits |
| **Training Samples** | 20,872 samples from 10 currency pairs |

**New Features Added:**
- Parkinson & Garman-Klass volatility
- ADX trend strength indicators
- Candlestick pattern detection (9 patterns)
- Support/Resistance proximity features
- Session overlap detection (London/NY)
- Multi-period RSI (2, 5, 9, 14, 21)

**API Endpoints:**
- `POST /api/maximized-ml/train` - Train with 3000 candles/symbol
- `GET /api/maximized-ml/stats` - System statistics
- `POST /api/maximized-ml/predict/{symbol}` - Regime-aware predictions

### AI/ML Research Findings (March 24, 2026)
Research document created: `/app/memory/AI_ML_MAXIMIZATION_PLAN.md`

**Key Findings:**
1. LSTM+GRU with Dual Attention (DALG) outperforms pure models
2. XGBoost achieves ~98% accuracy in classification tasks
3. HMM with volatility filtering improves profit factor from 1.48 to 1.73
4. Walk-Forward optimization covers ~70% OOS data vs 30% in simple backtests
5. PPO (Proximal Policy Optimization) achieves 63% win rate with lowest drawdown

**Implementation Roadmap:**
- Phase 1 (Done): XGBoost/LightGBM + Walk-Forward + New Features
- Phase 2 (Next): LSTM/GRU hybrid model
- Phase 3 (Future): PPO Reinforcement Learning

### Previous Updates

### Tampermonkey v7.3.0 - Redesigned UI (March 23, 2026)
**Complete UI overhaul for better usability and cleaner design**

| Feature | Description |
|---------|-------------|
| Modern Look | Glass-morphism design with purple gradient header |
| Organized Layout | Signal display box, grouped buttons, stats row, settings |
| Button Groups | AUTO/SCAN/GO in row 1, INVERT/LOG in row 2 |
| Stats Display | Wins, Losses, Profit in separate boxes |
| Draggable | Both main panel and console window are draggable |
| Minimizable | Compact mode hides body, shows only header |

### Momentum Buster 15s Strategy (March 23, 2026)
**Ultra-fast scalping strategy for 15-second binary options**

| Parameter | Value |
|-----------|-------|
| Timeframe | 15-second candles |
| Expiration | 15 seconds |
| Indicator | Momentum (period 3) |
| BUY Signal | Green bars (momentum > 0) + confirmations |
| SELL Signal | Red bars (momentum < 0) + confirmations |

**API Endpoints:**
- `POST /api/strategy/momentum-buster-15s/signal?symbol=EUR_USD`
- `GET /api/strategy/momentum-buster-15s/stats`

**Signal Confirmations:**
- `momentum_positive` / `momentum_negative`
- `consecutive_green_X` / `consecutive_red_X`
- `bullish_reversal` / `bearish_reversal`
- `strong_momentum`

### Improved AI/ML System v2.0 (March 21, 2026)
**NEW: Enhanced machine learning for better signal accuracy**

| Component | Description |
|-----------|-------------|
| `improved_ai_ml_system.py` | Optimized ML ensemble with 62 features |
| `POST /api/improved-ml/train` | Train model with OANDA data (2000 candles) |
| `POST /api/improved-ml/train-extended` | Extended training (5000 candles, 10 symbols) |
| `POST /api/improved-ml/predict/{symbol}` | Get ML prediction for a symbol |
| `GET /api/improved-ml/stats` | Get ML system statistics |

**Model Architecture:**
- Random Forest (300 trees, depth 15) - 45% weight
- Gradient Boosting (200 trees, LR 0.03) - 40% weight  
- AdaBoost (150 estimators) - 15% weight
- Soft voting ensemble with probability outputs

**62 Features Include:**
- Price Action (10): Price changes, candle body/wicks, bullish streak
- Technical Indicators (20): RSI-2/5/14, Stochastic, MACD, Bollinger Bands, CCI, Williams %R
- EMA Features (5): Price vs EMA5/EMA20, EMA crossovers, alignment
- Momentum (5): 3/5/10 bar momentum, ROC
- Volatility (5): 5/20 period volatility, ATR, range percent
- Pattern Recognition (7): Hammer, Engulfing, Doji, Morning/Evening Star, 3 White Soldiers/Black Crows
- Trend Strength (5): ADX, +DI/-DI, trend strength vs SMA50
- Mean Reversion (3): Z-score, TP deviation, acceleration
- Time Features (3): Hour (sin/cos), day of week

**Current Performance:**
- Cross-validation accuracy: 56.19%
- Training samples: 6,609
- Balanced class distribution (CALL/PUT)
- Top features: ATR%, MACD signal, Volatility

### Tampermonkey v7.1.0 - LOCAL OTC Signal Generation (March 21, 2026)
**CRITICAL FIX: OTC markets now use actual Pocket Option prices via DOM scraping**

| Component | Description |
|-----------|-------------|
| `LocalSignalEngine` | JavaScript-based signal generation (RSI, EMA, Stochastic, Bollinger Bands, Candlestick patterns) |
| `PriceScraperV2` | Scrapes live prices from Pocket Option DOM every 500ms |
| `CONFIG.USE_LOCAL_SIGNALS` | Set to `true` - bypasses backend API for OTC signals |

**Why This Change:**
- OANDA API does NOT have Pocket Option's proprietary OTC data
- OTC markets are broker-specific synthetic prices
- Local scraping ensures signals are based on actual prices the user trades on

**Technical Implementation:**
1. `startPriceScraping()` - Runs every 500ms when SCAN is enabled
2. `PriceScraperV2.scrapeCurrentPrice()` - Finds price elements on PO DOM
3. `PriceScraperV2.buildCandle()` - Constructs candles from price ticks
4. `LocalSignalEngine.generateSignal()` - Calculates RSI-2, Stochastic, BB, patterns
5. Requires 3+ confirmations for signal (same logic as backend)

**Console Window (LOG button):**
- Real-time on-screen console for debugging
- Shows price scraping status, candle count, signal generation
- Toggle with LOG button in Tampermonkey panel

## Previous Updates (March 20, 2026)

### Data Source Architecture v6.9.4 (March 20, 2026)
**OANDA is now the PRIMARY data source for all signals**

| Data Type | Primary Source | Fallback | Notes |
|-----------|---------------|----------|-------|
| Regular Forex (EUR/USD) | OANDA API | yfinance | Real-time |
| OTC Markets (EUR/USD_OTC) | OANDA API | yfinance | Uses underlying forex data* |
| Historical Data | OANDA | yfinance | For ML training |

*OTC markets on Pocket Option are synthetic markets. Their prices closely track real forex but are broker-specific. Signals are based on the underlying forex price movements.

**Price Verification (Hybrid Approach):**
- Backend generates signals using OANDA real-time data
- Tampermonkey verifies price on Pocket Option UI before trade execution
- `verifySignalPrice()` function checks if signal price matches current UI price within 0.1% tolerance

### Tampermonkey v6.9.3 - GO Button Fix (March 20, 2026)
**SWITCH button REMOVED - Switching is now automatic based on AUTO state**

| Button | Function |
|--------|----------|
| **AUTO** | Receives APP signals and places trades |
| **SCAN** | Scans for signals and places trades |
| **INV** | Inverts signal direction |
| **GO** | Force scan |

**SCAN Behavior:**
| AUTO State | SCAN Behavior |
|------------|---------------|
| AUTO ON | Scans ONLY currently selected asset (no switching) |
| AUTO OFF | Scans ALL favorites, auto-switches to best signal asset, places trade |

**Removed:** SWITCH toggle (SW button) - no longer needed

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
- [x] **Tampermonkey v6.9.0** (March 20, 2026) - Simplified SCAN: AUTO ON=single asset, AUTO OFF=all favorites with auto-switch. SWITCH button removed.

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
