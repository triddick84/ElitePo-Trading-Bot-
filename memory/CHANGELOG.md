# Changelog

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
