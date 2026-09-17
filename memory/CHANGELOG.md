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
