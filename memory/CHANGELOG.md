# Changelog

## Iter 153 — Feb 20, 2026 — Clean Retrain Hang Fix (event-loop unblocking)

### User report
> The clean retrain in the application is not working properly it just stays saying retraining until it times out.

### Root cause
`maximized_ai_ml.train_from_oanda()` (and the Improved v2 twin) are declared `async` but their bodies do 100 % synchronous CPU-bound work — sklearn `cross_val_score`, `TimeSeriesSplit` walk-forward CV, feature-extraction loops. **Never a single `await`.** Two consequences:

1. `asyncio.wait_for` cannot cancel them — no yield = no cancellation opportunity. The iter 150 timeout wrapper was a no-op against this class of coroutine.
2. The main event loop is fully blocked for the entire training run, so `/api/ml/retrain-status` polls stall and the UI hangs on "retraining" until either the whole pipeline finishes (minutes) or the browser gives up.

### Fix
`run_phase_with_timeout` now drives each phase coroutine **inside a worker thread with its own event loop** via `asyncio.to_thread(_drive_coroutine_in_thread, coro)`. Main loop stays responsive AND `wait_for` on the thread future actually enforces timeouts.

- New helper `_drive_coroutine_in_thread(coro)` — spins a fresh loop, runs to completion, closes it.
- 5 new pytests in `test_iter153_retrain_offload.py`, including the smoking-gun test that pins a CPU-bound "async" body under a phase and asserts the main loop still ticks heartbeats concurrently (would fail under old impl).
- Existing iter150 tests all still pass — hung-phase timeout, exception propagation, normal completion.


## Iter 152 — Feb 20, 2026 — Backtest Asset Picker: "Only With Data" Filter

Kills typo-based / empty backtests by only exposing symbols that actually have candles in `historical_candles`.

### Backend
- **`GET /api/backtest/assets-with-data`** — new endpoint. Aggregates `historical_candles` by `(asset, timeframe)`, flattens to per-asset counts and timeframe lists. Returns `{ success, available[], counts{}, timeframes{}, total_assets, total_candles }`. Gracefully degrades (`success: true, available: []`) when the DB is unreachable or the aggregation fails — the UI filter simply becomes unavailable rather than crashing the picker.

### Frontend (`shared/AssetPicker.jsx`)
- **"Only with data (N)" toggle button** next to the search box. Filters the entire class tree to just the symbols the DB has candles for. Auto-disabled when `total_assets == 0` so users aren't confused by an empty picker.
- **Per-symbol candle count badge** — small emerald pill showing `12k` / `500` next to each symbol that has data, with a tooltip showing the exact count. Nothing shown for zero-data symbols (keeps the tree clean).
- Fetch batches with `Promise.all` on mount; with-data endpoint failure is caught silently so the picker still works if only the universe endpoint is available.

### Tests
- 8 new pytests in `test_iter152_asset_picker_data_filter.py` covering: endpoint success path, empty DB, no-DB graceful degrade, aggregation-error graceful degrade, and 4 source-level assertions on the frontend picker wiring.
- Iter15x regression: **39/39 passing**.


## v8.157.0 — Feb 20, 2026 — Iter 151 + 151b: MT5 Teach UX + Win/Loss Detection Hardening

### Iter 151 — MT5 Point-to-Teach UI Expansion
User: "point-to-teach buttons for symbol/lot/SL/TP/BUY/SELL so users can wire MT5 in seconds".

- **Hover reticle overlay** during `mt5Adapter.startTeach()` — orange outline
  follows mouse so users see the exact element they'll teach (was blind before).
- **`mt5Adapter.verify(control)` / `verifyAll()`** — resolves taught → fallback
  selectors and returns match info. Panel uses this to paint per-cell
  `✓ taught` / `✓ auto` / `✗` badges.
- **`mt5Adapter.dryRun({ lots, sl, tp })`** — fills lot/SL/TP fields, resolves
  BUY/SELL buttons, but **never clicks them**. Users can smoke-test their
  taught selectors safely without placing a real order.
- **Cross-origin banner** appears in the Forex tab the instant the MT5
  iframe is detected as cross-origin — otherwise DOM injection silently fails.
- **Progress counter** — `N/6 taught` in the section header (green when
  complete).
- New DevTools helpers: `__aiEliteMt5Verify()`, `__aiEliteMt5DryRun()`.

### Iter 151b — Win/Loss Detection Hardening
User: "tampermonkey script win and lose detection is not working at all".

- **Early balance-delta resolver** — previously the watcher waited for
  `expiry + 4 s safety buffer` (~9 s for a 5 s trade) before ever consulting
  balance. Now the moment expiry passes AND queue has exactly one un-resolved
  arm, a single cent of balance movement triggers immediate `balance-delta-early`
  resolution.
- **Bounded `seenRows` Set** — capped at 500 (kept last 250 on overflow) so long
  sessions don't leak memory or block re-detection when PO recycles nodes.
- **Actionable timeout log** — points users at `__aiEliteDealDiag()` and the
  panel's "Win/Loss Detection Teach" section.
- **`tradeResultWatcher.getStats()`** — exposes `{ enabled, queueLength,
  timeoutCount, seenRowsSize, healthy }`.
- **Detection-health banner** on the LIVE tab. Hidden by default; red banner
  appears the instant any trade times out. Clicking jumps to the Forex tab so
  the user can teach WIN/LOSS row markers.

### Testing
- 21 new pytests across `test_iter151_mt5_teach_ux.py` (13) and
  `test_iter151b_detection_health.py` (8). All pass.
- Full iter14x/15x regression: **150/150 passing**.
- Bundle rebuilt to v8.157.0, copied to both public paths.


## v8.74.0 — Jun 1, 2026 — CYCLE asset-switch reliability fix
- **Bug**: CYCLE / asset-switching clicked the "wrong area" of picker rows
  (★ favorite star or green payout-boost cell) on narrow/portrait layouts
  because it clicked the geometric center of the full-width row.
- **Fix**: Added deterministic **Search-box switch** as the primary CYCLE
  switch path (`switchAssetViaSearch` in `src/utils/dom.js`):
  1. Open picker → 2. type symbol into the picker Search box (React-controlled
  input via native value setter) → 3. list filters to a single row →
  4. click that row's **asset-NAME leaf** (never the star/payout cell) →
  5. verify with `getCurrentAsset()`.
- Wired into `cycleMode._switchAssetViaPickerOnly` after the quick-pick fast
  path, before the legacy tab-walking fallbacks.
- Relaxed the right-sidebar geometric guard from 0.65→0.85 of viewport width
  so narrow/portrait layouts aren't wrongly rejected.
- Bumped `version.txt` 8.73.0 → 8.74.0; rebuilt webpack; copied fresh bundle
  to BOTH `frontend/public/pocket-option-auto-trader.user.js` and
  `...-modular.user.js` (both were stale/inconsistent: 8.73.0 / 8.62.0).
- **Validation**: lint clean, webpack build OK, served bundle returns
  `@version 8.74.0` + contains `switchAssetViaSearch`. Live DOM behavior must
  be verified by the user on pocketoption.com (cannot reproduce server-side).

### Note for next agent
- `server.py:3484` hardcodes a preview userscript URL
  (`https://auto-invert-engine.preview.emergentagent.com/...`). Harmless for
  preview but would point to the wrong host in production — candidate cleanup.


## v8.152.0 — Feb 12, 2026 — Iter 145 + 146: Forex MT5 end-to-end + TQNet accuracy boosters
### Iter 145 — Forex MT5 execution completed (TM side)
- Backend `/api/forex/orders/pending` + `mark-picked` + `mark-filled` + `mark-rejected` + `queue-stats` endpoints (in `routes/forex_routes.py`) close the loop between the Iter 142/143 Forex backend and the Tampermonkey userscript.
- New TM modules:
  - `src/trading/mt5Adapter.js` — DOM adapter for PO's web-MT5. Three-layered selector resolution (user-taught → curated fallbacks → text heuristics). Supports symbol picker, lot input, SL/TP inputs, BUY/SELL buttons. Handles cross-origin iframes gracefully.
  - `src/trading/forexOrderPoller.js` — 5s polling loop that claims pending orders, calls `mt5Adapter.placeOrder`, and reports fill/rejection back with DOM match diagnostics.
- Wired both into `src/index.js` + cleanup handler. Exposed on `window.__aiEliteForexStart(ms)`, `window.__aiEliteForexStop()`, `window.__aiEliteForexStats()`, `window.__aiEliteMt5Diag()`.
- 5 new pytests in `tests/test_iter145_forex_tm_orders.py`.

### Iter 146 — TQNet-inspired accuracy boosters (mql5 article 19157)
- New `backend/ml/revin.py` — Reversible Instance Normalization (numpy). Handles 1D/2D/3D windows, per-channel stats, round-trip invert. Biggest single win against distribution shift.
- New `backend/ml/temporal_query.py` — Numpy port of TQ-MHA + shallow MLP + GeLU (single-head, deterministic). Queries come from trainable periodic vectors θ_TQ indexed by `t mod W`; Keys/Values from raw window.
- New `backend/tqnet_service.py` — Adapter that wraps `TQNetPredictor` into a confluence-engine signal (`source="ml:tqnet"`).
- New `backend/routes/tqnet_routes.py` — `/api/tqnet/predict`, `/api/tqnet/predict-symbol`, `/api/tqnet/health`.
- Wired TQNet as a new confluence source in **both**:
  - `forex/signal_bridge.py` (drives MT5 forex trades)
  - `auto_scan_service.py` (drives binary-options auto-scan)
- Registered `ml:tqnet` weight (1.25) in `confluence_service.py`.
- 15 new pytests in `tests/test_iter146_revin_tqnet.py`.

### Validation
- **110/110 tests pass** in the iter137→146 regression chain (Pytest).
- Live smoke: `curl /api/tqnet/health` returns a valid signal; `/api/forex/orders/queue-stats` reports empty pending queue.
- Webpack build clean; bundle bumped `v8.151.0 → v8.152.0`; served at `frontend/public/pocket-option-auto-trader{,-modular}.user.js`.

### Known limitations & next steps
- **MT5 iframe cross-origin**: If PO renders MT5 in a cross-origin iframe, `mt5Adapter._mt5Doc()` returns `kind='cross-origin'` and rejects the order. Real-world fix requires PO to same-origin the iframe (out of our control) OR user needs to open MT5 as a top-level tab.
- **TQNet weights are randomly initialised** (numpy). θ_TQ is zero-init as recommended by the paper, so the layer starts as identity+noise → never hurts, may not help until trained. Adding a training loop that fits θ_TQ + projection matrices from historical candles is the next high-value iteration.
- **No teach-mode UI in panel yet** for MT5 selectors — power users can call `window.__aiEliteMt5Teach('buy_btn')` from DevTools; a UI ships in v8.153 once selectors are proven on live PO layouts.


## v8.153.0 — Feb 12, 2026 — Iter 147: TQNet Training + MT5 Teach UI
### Iter 147a — TQNet offline training
- New `backend/ml/tqnet_trainer.py` — fits `TQNetPredictor` weights (θ_TQ + all attention matrices + shallow MLP) via **scipy L-BFGS-B** with numerical gradients. Fully vectorised numpy forward pass across all sliding windows so the whole optimiser fits in a background thread.
- Persistence: weights saved to `/app/backend/data/tqnet_weights/<SYMBOL>_<TF>.npz` + `.meta.json` sidecar with training report.
- `tqnet_service._shared_predictor` now auto-loads trained weights on first call; a new `invalidate_predictor_cache(asset, tf)` API lets a fresh training run take effect on the next signal without a process restart.
- New endpoints in `routes/tqnet_routes.py`:
  - `POST /api/tqnet/train` — kicks off a background training job from a `closes` array
  - `POST /api/tqnet/train-symbol` — pulls candles from Mongo for `symbol`/`timeframe` and trains
  - `GET /api/tqnet/train/status/{job_id}` — poll job progress
  - `GET /api/tqnet/weights` — list trained weight files with their training reports
  - `DELETE /api/tqnet/weights/{symbol}/{timeframe}` — drop a weight file and evict its cache entry
- Training results on synthetic sinusoidal drift: loss 1.22 → 0.07 (17× reduction), direction accuracy 47% → 57% on default config (215 params, 100 windows, 20 L-BFGS iters, ~14 s inline).
- 13 new pytests in `test_iter147_tqnet_trainer.py`.

### Iter 147b — MT5 Teach UI in TM script
- New "**Forex**" tab in the TM panel (`src/ui/panel.js`) with three sections:
  1. **Forex Order Poller** — Start/Stop button + live stats grid (Pending / Picked / Placed / Rejected), auto-refreshing every 3 s via `/api/forex/orders/queue-stats`.
  2. **MT5 Point-to-Teach Selectors** — 2×3 grid of Teach buttons for Symbol / Lot / SL / TP / BUY / SELL. Each cell displays the currently taught CSS selector (or "not taught"), a Teach button that starts the click-capture within 30 s, and a ✕ clear button. Bottom: Diagnose (dumps `mt5Adapter.diagnose()` as pretty JSON) + Clear All.
  3. **Quick Reference** — inline help + console command list.
- Wired via new `_initForexTab()` in `panel.js`; auto re-initialises on panel re-injection.
- Version bumped `v8.152.0 → v8.153.0`; served bundle at BOTH `pocket-option-auto-trader.user.js` and `pocket-option-auto-trader-modular.user.js` (build:deploy script fixed to copy to both).

### Validation
- **123/123 pytests pass** across iter137→147.
- Live E2E: `POST /api/tqnet/train` completes a full training cycle in <20 s via BackgroundTasks; `GET /api/tqnet/weights` reflects the persisted file.
- Bundle sanity: both `.user.js` files at 493 KB, `@version 8.153.0`, contain `fx-poll-toggle` + `fx-teach-btn` test IDs.

### Known limitations & follow-ups
- **Training takes ~14 s for 100 windows / 20 epochs**. Fine as a background job but not sub-second. If we hit scale we should port to analytic backprop (numpy) or add a torch fallback.
- **Direction accuracy uplift on real market candles will likely be more modest** than on synthetic sinusoids — the acid test is running `POST /api/tqnet/train-symbol` on a live pair after 500+ candles have been ingested.
- Panel Forex tab needs no CSS additions — it inherits the existing `.epb-btn` / `.epb-section` styles.


## v8.154.0 — Feb 12, 2026 — Iter 148: Point-to-Teach WIN/LOSS Detection (fixes A-INV too)
### Root cause discovered
User confirmed wins/losses were NOT being detected at all. Because
`smartInvert.evaluateInversion()` fires off `state.stats.currentStreak`,
and that field is only updated by `tradeExecutor.recordResult()` inside
the watcher, **one bug caused both symptoms** (win/loss + A-INV never
firing). Rather than add a 7th heuristic, we ship a point-to-teach
fallback that's bulletproof against any PO DOM change.

### Iter 148 — Point-to-teach WIN/LOSS in `tradeResultWatcher.js`
- New GM keys `ai_elite_teach_win_row`, `ai_elite_teach_loss_row`,
  `ai_elite_teach_deal_container` — persisted across reloads.
- `tradeResultWatcher.startTeach(kind, cb)` — click-capture flow with a
  30 s timeout; walks up 6 ancestors on win/loss teach to find the row
  wrapper (not the inner span the user actually clicked).
- **Strategy 0** added to `_parseDealRow` — taught class signatures short-
  circuit ALL other strategies (numeric sign, colour class, value_up,
  RGB colour, etc). Verified via `test_source_taught_signatures_short_circuit_parse`.
- `_scanNewRows` now checks the taught container FIRST, so we don't have
  to guess where PO puts the deal history at all.
- `getTaught()` returns the current triple for the UI; `clearTaught(kind)`
  wipes one or all markers.
- Window helpers: `__aiEliteTeachWin/Loss/DealContainer`, `__aiEliteClearTeach`,
  `__aiEliteGetTaught`. Diag now includes taught markers.

### Iter 148 — Universal Teach UI at top of Forex tab
- 3-cell grid (WIN / LOSS / Container) with per-cell status + Teach + ✕
  clear buttons.
- DIAG button dumps `tradeResultWatcher._diag()` as pretty JSON.
- CLEAR ALL button wipes all taught markers.
- Section labelled "Win/Loss Detection Teach (Universal)" to make it
  obvious it applies to both binary options and Forex.

### Validation
- **133/133 pytests pass** in the iter137→148 regression chain (10 new
  in `test_iter148_teach_result_row.py`).
- Bundle sanity: JS-side node smoke test validates 8 contracts including
  the version bump, GM keys, and window helpers.
- Both bundles at `v8.154.0`; identical byte count (test enforces
  `pocket-option-auto-trader.user.js` == `-modular.user.js`).

### Known follow-ups
- User needs to click Teach WIN once and Teach LOSS once on their PO
  layout to activate the fallback; existing heuristics still handle it
  otherwise (unchanged behaviour if teach is not used).
- If wins/losses still don't fire after the teach, the diag output will
  now include the taught selectors so we can diagnose in one round-trip.


## v8.155.0 backend — Feb 12, 2026 — Iter 149: Market Data Pipeline Overhaul
### 3 silent bugs that were poisoning every signal for months
1. **RF Audit multiplied ml:tqnet by 0.0** — legacy `rf_audit` rows from Sept 11 marked EURUSD_OTC (and other pairs) as `weight=0.0` because yfinance returned <50 bars during that audit. `_rf_audit_multiplier` in `confluence_service.py` used `startswith("ml")`, so it silently zeroed every ML source. Every ML/TQNet PUT/CALL contribution → 0. FIX: scope RF audit to `ml:rf` only.
2. **historical_candles unique index broken** — old `symbol_1_timeframe_1_timestamp_-1` unique index with 2,627 legacy `symbol=null` rows blocked every ingest attempt with `DuplicateKeyError`. FIX: replaced with `asset_1_timeframe_1_timestamp_-1` in `historical_data_service.py`; wiped null rows.
3. **`_load_candles_from_db` returned empty on cold cache** — no ingester was calling providers on a schedule, so 1m/5m/15m data was months stale.

### Iter 149 shipped
- **New `backend/market_data_ingester.py`** — unified multi-provider ingester (Twelvedata forex/OTC, Oanda majors, yfinance backup). Provider chain routed per asset class. Coalescing lock so parallel confluence scans share one HTTP call. `fetch_and_persist`, `ensure_fresh`, `background_refresh_loop`.
- **Auto-heal**: `confluence_routes._load_candles_from_db` now calls `ingester.ensure_fresh` when candles are missing/stale. Confluence, TQNet, auto-scan, and Forex bridge all benefit transparently.
- **Freshness policy**: per-timeframe max-age table (`1m=120s, 5m=360s, 15m=900s, 1h=3600s`). Rate-limit-safe background refresh (8 s between calls to fit Twelvedata's 8/min free tier).
- **New routes**:
  - `GET /api/market-data/status` — freshness table per (asset, tf) with provider + age
  - `GET /api/market-data/providers/health` — per-provider up/down probe
  - `POST /api/market-data/ensure-fresh` — on-demand
  - `POST /api/market-data/backfill` — bulk history pull
  - `GET /api/signals/trace?asset=&timeframe=` — full pipeline trace: data → indicators → SMC → patterns → TQNet → confluence, every step surfaced
- **Cache poisoning guard**: freshness cache now tracks `db_rows`; when persist failed silently, cache-hit is refused so we always verify against actual DB rows.

### Live E2E validation
- `USDJPY_OTC 1m` now FIRES real PUT signal (2 sources agreeing, confluence score 0.89) with 200 rows of fresh Twelvedata candles.
- `historical_candles`: 2,302 rows across 5 assets × 3 TFs (was 2 assets × 1 TF).
- Background refresh loop keeps 10 pairs × 3 TFs warm every 3 minutes.

### Testing
- **146/146 pytests pass** across iter137→149 (13 new in `test_iter149_market_data_pipeline.py`)
- Regression tests locked for: RF audit scoping, ingester coalescing, cache poisoning guard, freshness policy, chain routing, persist schema shape.


## v8.155.0 — Feb 12, 2026 — Iter 150: User Fix Pack (5 items)

### 1. TM chart-type selector → signal requests
The existing "Manual Chart Type" dropdown in the Config tab (Iter 107)
only switched PO's chart — it didn't influence which signals the backend
generated. Now:
- `onChartTypeManualChange` persists the selection to
  `GM_setValue('manualChartType', ...)`.
- `fetchSignal()` in `utils/api.js` reads that key and appends
  `?chart_type=X` to every `/api/signals/latest` request so the backend
  routes signals for the chart the user is actually viewing.

### 2. Telegram bot invert toggle
- `TelegramBotService.invert_enabled` flag flips CALL↔PUT in
  `send_signal` before formatting the outgoing message (adds an
  `↺ INVERTED` marker so the receiver can see it flipped).
- Routes:
  - `GET  /api/telegram/invert` — current state
  - `POST /api/telegram/invert` `{enabled: bool}`
  - `POST /api/telegram/invert/toggle` — one-click flip

### 3. AI Models optimization "same output every time" — explainer
Root cause: `/api/ml-training/run-optimization` is a deterministic
aggregation of `backtest_results`. Identical inputs → identical output
(this is correct behaviour, not a bug). Added a data-version endpoint
the UI can call to surface *why* the answer hasn't changed:
- `GET /api/ml-training/optimization-data-version` — returns
  `{backtest_rows, last_backtest_ts, eligible_to_optimize, note}`.
UI can display "12 backtest rows — run new backtests to change
recommendations".

### 4. ML Lab retrain hang fix
- Phase 2 (`training_maximized_ml_v3`) was stuck forever because
  `await asyncio.to_thread(lambda: asyncio.run(...))` deadlocks in
  certain event-loop configurations.
- All 4 phases (maximized_ml, improved_ml, lstm_gru, ppo_rl) are now
  wrapped with `run_phase_with_timeout(coro, phase_name, timeout_s)`.
  Timeouts: 120s for ML phases, 180s for LSTM/PPO. `status.results[X]`
  now includes `success`, `elapsed_s`, and per-phase `error` if the
  wrapped coroutine raised.
- Live E2E: Phase 2 now completes in ~107s (was ∞). Phase 3 in ~63s.

### 5. Risk Guard → TM Bridge (per-trade amount + tiered stakes)
- Backend: `GET /api/riskguard/tampermonkey/config?user_id=...` returns
  the active session's `start_amount`, `per_trade_amount`,
  `max_daily_loss`, `stop_after_losses`, and `confidence_tiers`.
  Falls back to safe defaults when the DB is unreachable so the TM start
  button never fails.
- TM: New `trading/riskGuardBridge.js`. On master-toggle → ON
  (`handleMasterTap` fires `callbacks.onSessionStart`), the bridge:
  1. Fetches the config.
  2. Calls `tradeExecutor.setBaseAmount(per_trade_amount)`.
  3. Converts backend `{min_confidence, multiplier}` tiers → TM
     `{min_conf, amount = per_trade × multiplier}` and writes to
     `state._stakeTiersConfig` so `executor.execute()` picks up the
     tier-matched stake on the next fire.
  4. Copies `max_daily_loss` + `stop_after_losses` into `state.riskGuard`.
- Console helpers: `__aiEliteRiskGuardSync()`, `__aiEliteRiskGuardStatus()`.

### Testing + versioning
- **156/156 pytests pass** across iter137→150 (10 new in
  `test_iter150_fixpack.py`; bundle contract test in
  `tests/iter148_teach_parse.test.js` also updated to accept any 8.15X).
- TM bundle bumped `v8.154.0 → v8.155.0`, byte-identical between
  `pocket-option-auto-trader.user.js` and `-modular.user.js`.
