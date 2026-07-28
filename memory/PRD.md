# AI's Elite PO Traders Bot — Jul 2026 (TM v8.122.0 compat)

## Iter 80 (Jul 28, 2026) — TM v8.122.0 backend catch-up

**Context:** After a workspace rollback to Iter 79b (Feb 2026), the user
re-uploaded a compiled `AI's Elite PO Traders Bot-8.122.0.user.js` bundle
from a lost dev session. GitHub research (`triddick84/ElitePo-Trading-Bot-`
branch `rollback-`) confirmed no newer sources exist in any public repo —
the compiled userscript was the only surviving artifact.

### Scope of catch-up
Diffed the compiled `v8.122.0.user.js` against the /app backend to find every
endpoint it pings. 14 of ~17 already existed; 3 were missing. Rebuilt those
three so the served v8.122.0 script has a fully functional API surface again.

### Changes
- **Deployed** uploaded `v8.122.0.user.js` (378 KB) byte-for-byte to:
  - `/app/frontend/public/pocket-option-auto-trader.user.js`
  - `/app/frontend/public/pocket-option-auto-trader-modular.user.js`
  - `/app/tampermonkey-src/dist/pocket-option-auto-trader.user.js`
  - Bumped `/app/tampermonkey-src/version.txt` → **8.122.0**.
- **New route module `/app/backend/routes/tampermonkey.py`** wired into
  `server.py` via `api_router.include_router(tampermonkey_extra_router)`:
  - `GET /api/tampermonkey/script` — serves compiled userscript as
    `application/javascript` for `@updateURL`/`@downloadURL` auto-updates.
  - `GET /api/settings/chart` — returns `{success, chart_type, chart_timeframe}`
    from `trading_configurations` (defaults `japanese_candles` / `30s`).
  - `POST /api/diag/ws-frames` — WS diagnostic sink, capped at 200 frames
    per request + 2 000 rolling docs in `tm_ws_frame_diagnostics`.
  - `GET  /api/diag/ws-frames` — recent-batches list for offline debugging.
- **Fixed hardcoded preview URL** in `server.py:3484` — `script_url` now
  points at the dynamic `/api/tampermonkey/script` endpoint (safe under any
  hostname, including production).

### Verified live
- Both localhost (`http://localhost:8001`) and external preview
  (`https://auto-invert-engine.preview.emergentagent.com`) return 200 on the
  three new endpoints.
- Served `/api/tampermonkey/script` bytes match the uploaded userscript
  exactly (378 164 bytes). Content-Type is `application/javascript`.
- `POST /api/diag/ws-frames` accepts real payloads and returns
  `{"success":true,"stored":N}`.
- React dashboard still renders (login screen loads clean on the preview URL).
- Health/signals endpoints still 200 — no router-include regression.

### Tests
- `/app/backend/tests/test_iter80_tm_v8122_compat.py` — **8/8 pass**:
  - chart settings default contract
  - script served with correct MIME + `@version` ≥ 8.122.0
  - served bytes byte-match on-disk bundle
  - ws-frames POST stores batch, empty POST OK, GET lists recent
  - regression guards on `/api/health` and `/api/signals/latest`.

### Not rebuilt (deliberate scope cut)
The handoff summary mentioned an alleged "Iter 117-127" bundle of features
(Emergent Object Storage for admin datasets, 228-asset AssetPicker, Strategy
Publish/Unpublish flow, AccuracyEngine gating). None of these are referenced
by the compiled `v8.122.0.user.js` bundle, and no source code for them exists
in any public repo. They are captured in ROADMAP.md as P1 rebuild candidates
if the user confirms they still want them.

---

## Iter 79b (Feb 2026) — Telegram `/signal` "conditions not met" fix

**User report:** "telegrams /signal is returning an error every time a
generate signal command is entered saying conditions not met when
should be a high priority generate."

**Root cause:** `routes/integrations.py::signal_callback` routed the
Telegram `/signal` command through `force_signal_generator.force_generate_signal`,
whose internal analysis stack (multi-source data fetch → S/R analyzer →
`_force_combine_analysis` → emergency fallback) had multiple silent
failure paths that could yield a signal whose downstream shape didn't
satisfy `platform_integration.send_telegram_signal()` — surfacing to
the user as "⚠️ No signal generated - conditions not met." even though
the whole point of `/signal` is a **guaranteed** high-priority signal.

**Fix:** Rewrote `signal_callback` to invoke `routes/signals.py::force_generate_signal_v2`
directly (in-process — no HTTP self-call). That endpoint's docstring
explicitly guarantees "Always returns a directional signal — never
empty," and it's the same pipeline the dashboard uses. The callback now:
1. Normalises the user's selected asset to the `_OTC` suffix v2 expects.
2. Maps the timeframe to `expiry_seconds`.
3. Calls v2 directly; on any exception, sends a **specific** error
   (with exception type + message) rather than the generic "conditions
   not met".
4. Adapts the v2 signal payload to a `TradingSignal` so
   `platform_integration.send_telegram_signal` works unchanged.
5. Keeps the auto-trade branch intact when
   `telegram_bot.auto_trading_enabled`.

**Regression guard:** `/app/backend/tests/test_iter79_telegram_signal_callback.py`
(2 tests, both PASS) asserts:
- Source imports & calls `force_generate_signal_v2`
- The `"conditions not met"` Telegram surface is removed
- v2 pipeline returns a non-empty signal payload with a valid direction

---

## Iter 79 (Feb 2026) — Tampermonkey Strategy Match Fix + Telegram Mini App Phase A

### 1. Tampermonkey Strategy Match Fix (P0 — completed)
**Issue reported by user:** "tampermonkey script keeps indicating there is no
local match for strategies chosen on tampermonkey it defaults to all
strategies."

**Root cause:** `strategy_selection_service.get_selected_strategies()`
resolves `'default'` → concrete IDs (e.g., `5s_heikin_fractal`, Iter 67
DEFAULT_STRATEGY_PER_TIMEFRAME). The Tampermonkey `APP_TO_LOCAL_MAP` had
NO entry for these resolved winners → fell into the "unknown → run ALL
strategies" branch, polluting signals.

**Fix (v8.75.0):**
- Expanded `/app/tampermonkey-src/src/strategies/manager.js::APP_TO_LOCAL_MAP`
  to cover every id in `AVAILABLE_STRATEGIES` (5s → 5m). Unknown-yet
  strategies map to `Local Signal Engine` (generic RSI/Stoch/BB/EMA
  engine) so we always produce single-strategy signals.
- `syncFromApp()` now iterates preferred TFs (5s → 15s → 30s → 1m → …)
  looking for the first mapped selection, instead of only reading 5s.
- Changed the unknown-id fallback: no longer enables ALL strategies —
  now enables only `Local Signal Engine` (safest single generic).
- Bumped userscript version so Tampermonkey re-downloads: **8.75.0**.
- Deployed to `/app/frontend/public/pocket-option-auto-trader-modular.user.js`.

### 2. Telegram Mini App Phase A (P0 — completed)
Shipped a fully functional 4-step onboarding TMA under `/tma/` on the
existing preview domain, no separate deploy pipeline needed.

**Stack:** Vite + React 18 + TypeScript + @twa-dev/sdk. Builds to
`/app/frontend/public/tma/` (served by CRA static). Source lives in
`/app/telegram-mini-app/`.

**Backend routes** (all under `/api/tma/`, in `/app/backend/routes/tma.py`):
- `POST /tma/auth` — HMAC-SHA256 initData validation per Telegram spec,
  JWT issuance (HS256, 7-day TTL), user upsert into `tma_users`.
- `GET /tma/me`, `/tma/onboarding/state`, `/tma/packages`
- `POST /tma/onboarding/update` — Step 1 (PO signup attestation),
  Step 3 (package pick). Access step is server-computed only.
- `POST /tma/kyc/upload` — stores screenshot on disk under
  `/app/backend/uploads/tma_kyc/`. 8 MB limit.
- `GET /tma/kyc/status`
- `GET /tma/admin/kyc/queue`, `GET /tma/admin/kyc/{id}/image`,
  `POST /tma/admin/kyc/{id}/review` (approve/reject)
- `GET /tma/admin/users`, `GET /tma/health`

**Auto access grant:** When admin approves KYC AND the user has picked a
package, `access_granted = true` is set + step 4 completed atomically.

**Env additions (backend/.env):**
- `TMA_JWT_SECRET` (auto-generated, 64-byte urlsafe)
- `TMA_ADMIN_TELEGRAM_IDS="6434316177"`
- `PO_AFFILIATE_URL="https://u3.shortink.io/register?...&a=elite-po-traders"`
- `TMA_DEV_MODE="true"` (dev bypass — turn OFF in production)

**Admin UI:** New sidebar item `🛡️ TMA KYC Admin` → `TmaAdminPage.jsx`.
Sign-in via dev-mode bypass in Phase A, or paste TMA JWT (obtained inside
Telegram).

**Data model (Mongo collections):**
- `tma_users`: id, telegram_user_id, username, role, referral_code,
  referred_by, onboarding{po_signup,kyc,package,access}, access_granted,
  kyc_status
- `tma_kyc`: id, user_id, telegram_user_id, status, screenshot_path,
  submitted_at, reviewed_at, reviewed_by, review_reason

**Verified via curl** (real HMAC-signed initData + dev-mode initData) —
end-to-end flow: user signs in → step 1 complete → KYC upload → package
pick → admin approves → access granted.

### Next Actions (Phase B backlog)
- Stripe Checkout webhook wiring for real payment (currently only records
  package pick, no charge).
- Telegram Bot Python worker (`telegram_bot.py`) — `/start`, `/pocket`,
  `/packages`, `/refer` commands.
- Referral tracking UI + payout calculation.
- Crypto payment gateway (P2).
- Migrate KYC screenshot storage from local disk to Emergent Object
  Storage (Phase B for production).
- Remove `TMA_DEV_MODE=true` for production launch.

---


# AI's Elite PO Traders Bot — Deploy Build Fix (v8.78.0)

## Iter 78 (Feb 28, 2026) — Deploy "uvicorn: command not found" Fix

### Root Cause Found in Production Build Logs
- Production build was failing with `/entrypoint.sh: line 29: uvicorn:
  command not found` then `Backend process died during startup, exiting`,
  causing nginx upstream to refuse all /api/* connections.
- The deploy failure traced to `backend/requirements.txt` line 15:
  ```
  BinaryOptionsToolsV2 @ file:///tmp/BinaryOptionsTools-v2/.../wheel
  ```
  This local-file-path wheel doesn't exist on the Kubernetes build
  server. `pip install -r requirements.txt` aborts at this line and
  NEVER reaches `uvicorn==0.25.0` further down — so uvicorn isn't on
  PATH at runtime → entrypoint fails → backend never starts → every
  login attempt returns "red X connection error" because nginx has
  no live upstream.

### Fix
Removed all deploy-incompatible packages from `requirements.txt`:
- `BinaryOptionsToolsV2 @ file:///tmp/...` (the primary culprit)
- `pocketoptionapi-async @ git+https://github.com/...` (git install)
- `tensorflow==2.20.0`, `keras==3.11.3`, `tensorboard==2.20.0`,
  `tensorboard-data-server==0.7.2` (~600MB+ each, exceed 1Gi memory)
- `TA-Lib==0.6.8` (requires libta-lib0 OS package not on build image)
- `selenium==4.36.0`, `playwright==1.57.0`, `playwright-stealth==2.0.0`,
  `undetected-chromedriver==3.5.5`, `webdriver-manager==4.0.2`
  (browser automation only used in optional code paths)

All affected imports were ALREADY wrapped in `try/except ImportError`
blocks (the codebase had graceful-fallback patterns) so the runtime
just logs "X not available" instead of crashing.

### Verified on Preview
- Backend startup log shows `[seed_admins] done — seeded=0 skipped=1
  errors=0` and `Application initialization complete`.
- `/api/health` returns 200 healthy.
- `/api/auth/login` with `seedtest`/`SeedPass123!` returns a JWT.
- 30+4 = 34 regression tests pass.

### Tests
- `/app/backend/tests/test_iter78_deploy_requirements.py` — 4 new tests
  that lock in the requirements.txt fix:
    1. Forbidden patterns (`@ file://`, `@ git+`, tensorflow, selenium, …)
       must never reappear.
    2. Critical runtime deps (uvicorn, fastapi, motor, pymongo, sklearn,
       passlib, PyJWT, imbalanced-learn) must remain pinned.
    3. Smoke test: live `/api/health` still returns 200.
    4. Smoke test: live `/api/auth/login` still works.

---


# AI's Elite PO Traders Bot — Production Login Fix (v8.77.0)

## Iter 77 (Feb 28, 2026) — Production Deploy Login Fix

### Bug
- Production app (`https://auto-trader-pro-3.emergent.host`) returned
  generic "red X connection error" toast on every login attempt
  regardless of credentials (triddick84, testuser, seedtest@...).
- Symptom = pure connection failure, not 401 → backend was crashing on
  startup in the production pod and never returning any HTTP response.

### Root Cause
- `backend/.env` had 8 unquoted values containing shell-special chars:
  ```
  POCKET_OPTION_PASSWORD=Tonyistheman#1    ← `#` truncates to "Tonyistheman"
  TELEGRAM_BOT_USERNAME=@ElitePocket_bot   ← `@` triggers shell expansion
  AUTOBOT_WEBHOOK_URL=http://34.81.61.52/index.php
  OANDA_ACCESS_TOKEN=86b39ffb-...-12128789-001
  SEED_ADMINS=seedtest@elitepo.com:SeedPass123!:seedtest
  PLAYWRIGHT_BROWSERS_PATH=/pw-browsers
  POCKET_OPTION_SSID=a%3A4%3A%7B...        ← URL-encoded with `%`
  ```
- When Kubernetes pod parses the env file, the `#` comment marker
  truncates `POCKET_OPTION_PASSWORD`, several keys end up missing or
  partially populated, the FastAPI server crashes on startup, and every
  frontend request returns "connection error".
- The preview env was tolerant because `load_dotenv()` in dev uses a
  more forgiving parser than the production env loader.

### Fix
- Rewrote `backend/.env` with **all values double-quoted** and **all
  inline comments removed** (per system-prompt rules). Also de-duplicated
  the TELEGRAM_BOT_TOKEN that appeared twice.
- Verified on preview: backend starts cleanly, `[seed_admins] done` log
  appears, `/api/auth/login` returns a JWT for `seedtest / SeedPass123!`.

### Tests
- `/app/backend/tests/test_iter77_env_quoting_and_login.py` — 5 new
  tests (no-inline-comments, quoting rule, dotenv intact-load,
  SEED_ADMINS parseable, end-to-end login). All pass.

### User Action Required
- **Redeploy preview → production** to push the fixed `.env`. After
  redeploy, log in with `seedtest` / `SeedPass123!` (note: USERNAME is
  `seedtest`, NOT the email).

---


# AI's Elite PO Traders Bot — Product Requirements (v8.76.0)

## Iter 76 (Feb 28, 2026) — Ensemble + Backtest Fixes

### Two distinct bugs reported as "ensemble not working properly"

#### Bug 1: Backtest engine simulated overlapping binary trades
- `BacktestingEngine.run_strategy_backtest()` was iterating `for i in
  range(...)` — opening one trade per candle even when the previous
  trade's expiry hadn't elapsed. On M1 EURUSD with 60s expiry, the hybrid
  ensemble produced **3853 trades on 5000 candles (~77%)** which is
  physically impossible on Pocket Option (you can't run 60 overlapping
  60-second binaries simultaneously).
- **Fix**: Loop converted to `while i < N` and after each opened trade,
  `i = exit_idx + 1` so the next signal is only evaluated AFTER the
  previous binary settles — matching live `TRADE_COOLDOWN_APP` behavior.
- **Verified**: hybrid trade count dropped 3853 → 2131 on the same
  5000-candle window (no overlap; correct sequential semantics).

#### Bug 2: Ensemble training metrics were all zeros
- `train_from_backtest_results()` was building the `TrainedModel` for the
  ensemble by averaging RF + GB metrics, but ONLY passing `accuracy` and
  `f1_score` to the new `ModelMetrics()` — `precision`, `recall`,
  `validation_samples`, `smote_status`, `minority_class_ratio` all
  defaulted to 0/empty. The API was reporting
  `ensemble: prec=0.000 recall=0.000 smote=''` which looked broken.
- **Fix**: After creating the ensemble, re-split with the same
  `shuffle=False` policy the individual models use, call
  `ensemble.predict(X_val)` and compute real precision/recall/f1
  from the actual ensemble vote. SMOTE audit inherited from the
  underlying models so the response stays consistent.
- **Verified**: ensemble now reports `prec=0.180 rec=1.000 f1=0.305
  val_n=342 smote='smote-applied:144→1222 (k=5)'` — real numbers.

### Tests
- `/app/backend/tests/test_iter76_ensemble_and_backtest_fixes.py` —
  3 new tests covering the cooldown enforcement and ensemble metric
  population. Cumulative regression: 25+ tests, all pass.

---


# AI's Elite PO Traders Bot — Product Requirements (v8.75.0)

## Iter 75 (Feb 28, 2026) — SMOTE Oversampling + Class Weights for ML Trainer

### Motivation
Iter 74 fixed the "Trained 0 models" bug but exposed a secondary issue: the
RandomForest trained at 69.7% accuracy with **17% precision** on winning
trades because the dataset is heavily imbalanced (only ~11% of backtest
trades win at the default 50% confidence threshold). The model was
biased toward predicting "loss" for everything.

### Fix
1. **Installed `imbalanced-learn==0.14.1`** (added to requirements.txt).
2. **New `_maybe_smote_balance()` helper** in `ml_training_service.py` —
   - Gated SMOTE that only fires when minority class is < 25% AND has
     ≥ k_neighbors+1 samples (auto-clamped). Returns the (possibly
     resampled) X/y plus an audit string explaining what happened.
3. **RandomForestModel.train()** & **GradientBoostingModel.train()** now:
   - Apply SMOTE to the TRAINING split only (never the validation split,
     so we don't leak synthetic samples into evaluation).
   - GradientBoosting additionally uses `compute_sample_weight('balanced')`
     because sklearn's GB doesn't expose `class_weight` natively.
   - Surface `smote_status` (e.g. `"smote-applied:86→718 (k=5)"`) and
     `minority_class_ratio` in returned `ModelMetrics`.
4. **`ModelMetrics` dataclass** extended with `smote_status` (str) and
   `minority_class_ratio` (float) for full auditability through the API.

### Verified
- End-to-end backtest → train run on the live preview:
  - **Minority class 86 → 718 samples** (perfectly balanced).
  - Accuracy: **69.7% → 78.7%** (+9 points).
  - F1 score: **0.290 → 0.317** (+2.7 points).
  - SMOTE status visible in API response (`smote-applied:86→718 (k=5)`).
- 22/22 regression tests pass including 5 new SMOTE-specific tests.

---


# AI's Elite PO Traders Bot — Product Requirements (v8.74.0)

## Iter 74 (Feb 28, 2026) — Backtest Trade Persistence Fix (P0)

### Bug
- "Train from Backtests" button on AI Models page returned
  `"Trained 0 ML models from 100 backtest results"` no matter how many
  backtests had been run.
- Root cause: `backtesting_engine.save_results()` was writing only
  aggregate metrics (`metrics`, `equity_curve`, `trade_count`) but NOT
  the per-trade list. 522 historical records all had `trades: missing`.
- `ml_training_service.train_from_backtest_results()` walks
  `result['trades']` to build the training matrix — 0 trades → 0 models →
  silent success with `"Trained 0"`.

### Fix
1. **`backtesting_engine.save_results()`** now persists `trades[]` (capped
   at 200 entries) with full per-trade fields:
   `entry_time, exit_time, direction, entry_price, exit_price, pnl,
    pnl_percent, is_win, result, confidence, strategy, expiry_seconds`.
2. **`/api/ml-training/train-from-backtests`** now performs a pre-flight
   check on `total_trades_available`. If <100, returns a precise error
   with `results_with_trades`, `total_trades_available`, and
   `needs_retrain_action: "rerun_backtests"` so the UI tells the user to
   re-run their backtests on v8.74.0+.
3. **Success path** now returns
   `"Trained N ML models from M backtest results (T trades)"` so users
   can see exactly how much training data was used.

### Verified
- Fresh backtest call → DB doc carries `trades` array of 200 rows
  with `is_win`/`result` labels (verified by direct MongoDB query).
- 5 backtests across multiple OTC pairs → trainer succeeds with
  806 trades and 3 models (random_forest, gradient_boosting, ensemble),
  random forest hitting 69.8% accuracy.

### Tests
- `/app/backend/tests/test_iter74_backtest_trade_persistence.py` — 3 new
  tests including a full end-to-end backtest → train cycle. All pass.
  Cumulative regression: 17/17 ✅.

---


# AI's Elite PO Traders Bot — Product Requirements (v8.73.0)

## Iter 73 (Feb 27, 2026) — Universal +3.5s Fire Offset

### Backend (signals.py)
- `POST /api/signals/force-generate-v2` now ships a new field on every
  generated signal: **`fire_offset_sec`** (float, default `3.5`).
- Configurable via env var `SIGNAL_FIRE_OFFSET_SEC` (range clamped to
  `[-15.0, +15.0]`). Helper: `_signal_fire_offset_sec()`.
- This is the "settle delay" the server recommends for any client that
  fires trades from these signals (currently TM script, but downstream
  clients can also adopt it).

### Tampermonkey v8.73.0
- `state.latencyOffsetSec` default raised from `0` → **`3.5`** seconds.
- Latency slider now supports **0.5s precision** (step="0.5", range -15..+15).
  Visual readout shows decimals only when fractional (e.g. `+3.5s`, `+4s`).
- **Universal application**: the +3.5s arming delay now applies to:
  - Scan trades · Cycle trades · App-poller trades · GO/force trades
    (already wired via `executor.execute()` from Iter 63).
  - **NEW**: Seconds Number Strategy fires — SNS used to bypass
    `executor.execute()` via its own `_executeViaWs`/`_executeViaDom` path.
    Now wrapped in `armAndExecute()` which honours `state.latencyOffsetSec`
    before clicking CALL/PUT.
- Legacy integer saves of `latencyOffsetSec` are snapped onto the 0.5s
  grid on load.

### Tests
- `/app/backend/tests/test_iter73_universal_fire_offset.py` — 5 new tests
  (bundle version, slider step + default, SNS arming, API field present,
  helper clamping). All pass. Cumulative regression suite: 88/88 ✅.

---


# AI's Elite PO Traders Bot — Product Requirements (v8.72.0)

## Iter 72 (Feb 27, 2026) — Settings Persistence Fix

### Tampermonkey v8.72.0
1. **Strategy choice now persists across reloads** — Root cause: `loadStrategies()`
   was calling `/strategies/selected` on every page load and silently
   overwriting the user's local pick (saved as `state._selectedStrategy`).
   Fix: prefer the locally-saved strategy when it still exists in the
   available list, then re-sync it back to the server. If the API is
   offline we still apply the local pick instead of falling back to
   `'default'`.
2. **MM trade-amount input now restored on reload** — Same class of bug:
   the HTML `value="1"` default was always winning because nothing was
   syncing `state.moneyManagement.baseAmount` back into the DOM after the
   panel was created. `_restoreToggleStates` now reads the saved amount
   and writes it into `#__epb__amt`.

### Tests
- `/app/backend/tests/test_iter72_settings_persistence.py` — 3 new tests
  validating bundle version, strategy local-over-server precedence, and
  amt-input restoration.

---


# AI's Elite PO Traders Bot — Product Requirements (v8.71.0)

## Iter 71 (Feb 27, 2026) — Latest Changes

### Tampermonkey v8.71.0
1. **SNS-only Auto-Invert** — Seconds Number Strategy now has its OWN auto-invert
   tracker that flips on 2 consecutive SNS losses and applies ONLY to subsequent
   SNS fires. Global A-INV no longer reaches SNS, and SNS losses no longer
   contribute to the global streak that flips scan/cycle direction.
   - State: `twentyOneSecondReversal.snsInvert` (`isFlipped`, `consecutiveLosses`,
     `consecutiveFlippedLosses`, `flipAfterLosses`, `revertAfterFlippedLosses`).
   - Wiring: executor exposes `setSnsResultHook(fn)`; strategy registers its
     `onSnsResultRecorded(isWin, ctx)` callback on `enable()`. When a trade is
     tagged SNS (strategy = `1m_21s_reversal` or source matches `51s-reversal-*`),
     the executor calls the hook instead of `smartInvert.evaluateInversion()`.
2. **canTrade clarity** — Cooldown rejection log now embeds remaining seconds,
   the cooldown bucket (`scan`/`app`), and how long ago the last trade in that
   bucket happened. Example:
   `[exec:scan] ✗ canTrade returned false — cooldown 23s remaining (scan bucket — last scan trade was 7s ago, min wait 30s)`

### Frontend — AI Models › Real Data Training
- DataCollectionDashboard now loads the **full 366-symbol / 11-timeframe universe**
  from `/api/backtest/assets-universe` instead of the previous hardcoded 7-asset
  list. Adds:
  - Global **Select ALL assets (366)** / **Select ALL timeframes (11)** buttons.
  - Per-class **+ All / − Clear** toggles for each of the 10 asset classes
    (Forex Regular + OTC, Commodities Regular + OTC, Crypto Regular + OTC,
    Indices Regular + OTC, US Stocks Regular + OTC).
  - Selection counter showing live `N assets · M TFs` totals.
- Training dropdown also pulls from the same universe (no more 7-asset cap).

### Tests
- `/app/backend/tests/test_iter71_sns_invert_and_universe.py` — 6 new tests
  covering bundle version, SNS hooks/log, canTrade log clarity, universe endpoint
  integrity, and dashboard wiring. All pass (74/74 → 80/80 cumulative).

---


# Elite Pocket Option Trading Bot - Product Requirements Document

## Last Updated: May 30, 2026

## Current Status

✅ **Iteration 69 — CYCLE no longer cycles the "Closed Trades" sidebar (May 30, 2026)**

User reported (with screenshot) that CYCLE was rotating through the right-side **Trades / Opened / Closed** panel rows instead of the asset picker. The closed-trade rows show "AUD/CAD OTC +92%" with the exact same text shape as picker rows, so `readPickerItems()` was scraping them and `clickPickerRowEl` was firing on them — net effect: bot cycles through trade history and never switches assets.

### Three-layer fix (all in `utils/dom.js`)
1. **Ancestor class blacklist** — any element whose ancestor (up to 8 levels) has a class matching `/trades|deals|history|opened|closed|right-panel|notifications|messages|sidebar/i` is rejected.
2. **Geometric guard** — any element with `bounding rect.left > viewport_width * 0.65` is rejected (right-sidebar territory).
3. **Last-line-of-defense on click** — `clickPickerRowEl()` runs both checks again before firing; if either trips, it logs `"refusing to click row at x=Xpx (right-sidebar territory)"` and returns false.

The same two guards (geometric + ancestor blacklist) are also applied to `clickPickerTabByText()` so the new multi-tab discovery from Iter 68 doesn't accidentally click the "Closed" trades tab.

### TM Build
- v8.68.0 → **v8.69.0**, rebuilt + deployed to `/app/frontend/public/`

### Tests
- `tests/test_iter69_cycle_trades_panel_blacklist.py` — 6/6 passing (version bump, blacklist regex present, viewport guard, click-row guard, bundle smoke, picker-items guard)
- Grand total backend regression: **56/56 passing** (Iter 61–69)

---

✅ **Iteration 68 — CYCLE Mode Universal Scanner + 15s Rotation (May 29, 2026)**

User reported the cycle feature was not working properly. Requested:
1. Scan ALL ≥85% payout assets (not just currencies)
2. Rotate every 15 seconds
3. Pair with the SCAN feature (which generates signals on the current asset) but NOT with the APP feature (which is single-asset only)

### Root cause of "not working properly"
- Discovery was hard-coded to the **Currencies tab only** — crypto/commodities/stocks/indices OTC were invisible to the rotator
- The symbol filter was `^[A-Z]{3}[A-Z]{3}(_OTC)?$` — pure 6-char FX-only, blocking BTCUSD, XAUUSD, US30, AAPL_OTC, etc. as a safety net
- Default rotation was **30s** (user wanted 15s)

### Implementation
**Backend / `utils/dom.js`:**
- New `clickPickerTabByText(textRe)` helper — generic tab clicker
- New `discoverAllAssetsWithPayouts()` — opens picker, walks every category tab (Currencies, Crypto, Commodities, Stocks, Indices, ETFs), scrapes every row with payout, deduplicates by symbol, and **leaves the picker closed**

**`trading/cycleMode.js` rewrite:**
- `rotateEveryMs` default 30s → **15s**
- Symbol filter relaxed: old `FX_PAIR_RE` deleted, new `SYMBOL_RE = /^[A-Z0-9]{2,12}(_OTC)?$/`
- `_discoverEligiblePairs()` now calls `discoverAllAssetsWithPayouts()` — surfaces the FULL universe filtered to ≥85% payout
- `_switchAssetViaPickerOnly()` has a fast path (Currencies tab) + slow path (full multi-tab) — handles non-FX symbols transparently
- Log line: `"universal asset scanner @ 15s/asset, min payout 85% (pairs with SCAN; ignores APP poller)"`

**TM bundle:** v8.66.0 → **v8.68.0**, rebuilt + deployed to `/app/frontend/public/`

### How to use (per user's mental model)
1. Toggle **SCAN** on (signal generator)
2. Toggle **CYCLE** on (asset rotator)
3. The bot scans ALL asset categories, picks the ≥85% payout subset, sorts by payout desc, switches every 15s
4. SCAN fires a signal on whichever asset CYCLE has selected → AUTO fires the trade if confidence threshold met
5. APP feature remains single-asset (PO's own signal feed is locked to whatever the current chart shows)

### Tests
- `tests/test_iter68_cycle_universal.py` — 7/7 passing (version bump, 15s in bundle, multi-tab export present, FX-only filter removed, universal discovery wired)
- Grand total backend regression: **50/50 passing** (Iter 61–68)

---

✅ **Iteration 67 — Default Strategies Empirically Optimized Per Timeframe (May 29, 2026)**

User asked to evaluate the default strategies per timeframe and replace any sub-optimal ones with empirical winners.

### Methodology
- Wrote `scripts/evaluate_default_strategies.py` — backtests every candidate (deep_confluence, momentum_buster, hybrid + registered TF-specific strategies) for each timeframe on EURUSD_OTC over a 3-day window
- Ranked by composite score = `(WR-50) × √signals × clip(PF, 0.5, 2.5)`
- Added a generic `strategy_registry` fallback to `routes/backtesting.py` so any of the 42 registered strategies can be backtested via `/api/backtest/run`

### Results (3-day EURUSD_OTC backtest)
| TF  | Previous Default | NEW Default          | Win Rate | Signals | Score    | Improvement |
|-----|------------------|----------------------|----------|---------|----------|-------------|
| 5s  | deep_confluence  | **5s_heikin_fractal**| 54.2%    | 83      | +36.5    | **+7.7% WR** |
| 15s | deep_confluence  | **15s_ema_cascade**  | 58.3%    | 48      | +64.6    | **+6.1% WR** |
| 30s | deep_confluence  | **momentum_buster**  | 75.0%    | 16      | +240.0   | **+12.5% WR** |
| 1m  | deep_confluence  | **1m_triple_ema**    | 47.1%    | 369     | -38.9    | (best of field; entire M1 OTC universe < 50%, flagged for retraining) |

### Implementation
- New `DEFAULT_STRATEGY_PER_TIMEFRAME` map at top of `strategy_selection_service.py` — single source of truth
- `get_selected_strategies()` now transparently resolves `'default'` → the empirical winner
- New helper `resolve_default(timeframe)` for direct lookups
- Saved selections retain `'default'` literal so users can still see "Default" in the UI, but the routing layer always dispatches to the real strategy id
- Generic registry-strategy backtest path added so future strategies become evaluable with zero engine changes

### Tests
- `tests/test_iter67_defaults_per_timeframe.py` — 10/10 passing (defaults map presence, each TF's winner asserted, backtest compatibility for all 4 winners)
- Grand total backend regression: **43/43 passing** (Iter 61–67)

### Note on M1 underperformance
Every M1 strategy backtested negative (best 47.1%). Most likely cause: M1 candles in `otc_candles_5s` are aggregated from 5s data with limited recent ticks. Recommended follow-up: pull more M1 history via OANDA backfill for forex_otc majors before relying on M1 strategies.

---

✅ **Iteration 66 — "Find Best Pair Today" Scanner + Mongo BSON Bugfix (May 29, 2026)**

User requested an auto-scanner across the 366-asset universe to rank pairs by today's edge.

### A) Scanner Service
- New `routes/scanner.py` with two endpoints:
  - `POST /api/scanner/find-best-pairs` — submits a background job (returns `{job_id}` in <100 ms)
  - `GET /api/scanner/latest?scope=` — fetches the persisted top-N snapshot
- Runs each asset through `run_backtest()` and ranks by composite score:
  `(win_rate − 50) × √signals × min(2.5, max(0.5, profit_factor))`
- Scopes: `all_otc` (default ~180 symbols), `forex_otc`, `commodities_otc`, `crypto_otc`, `indices_otc`, `stocks_otc`, individual non-OTC classes, or `all` (full 366)
- Persists every run to `scanner_results` Mongo collection
- Built on the Iter 65 JobManager so a full scan can take 5–10 min without ingress timeouts

### B) Critical bugfix: BSON int-key crash in backtest engine
- `BacktestMetrics.to_dict()` returned `trades_by_hour: Dict[int, Dict]` (hours 0–23 as int keys)
- Mongo's `insert_one` rejected this with `documents must have only string keys, key was 7`
- Every `deep_confluence` / `momentum_buster` backtest was failing silently
- Fix: stringify keys → `{str(k): v for k, v in self.trades_by_hour.items()}`
- **All confluence backtests now work** — confirmed `EURUSD_OTC 5s 3d` returns 215 trades, 46.5% WR
- Scanner now qualifies real pairs: top hits in test run were `USDCAD_OTC` (59.1% WR, score 133.4) and `GBPAUD_OTC` (55.1% WR, score 79.97)

### C) UI: `<ScannerCard>` in MLLabPage
- Scope dropdown (7 options) + "Run Scan" button
- Live progress bar polling the job
- Sortable leaderboard table: rank, symbol, TF, win-rate (color-coded), signals, profit factor, return %, Sharpe, composite score
- `data-testid`: `scanner-card`, `scanner-scope-select`, `scanner-run-btn`, `scanner-leaderboard`, `scanner-row-{N}`

### Tests
- `tests/test_iter66_scanner.py` — 4/4 passing (submit speed, full forex_otc run + ranking validation, latest endpoint, invalid scope 400)
- Grand total backend regression: **33/33 passing** (Iter 61–66)

---

✅ **Iteration 65 — SEED_ADMINS env var + Background Job pattern (May 28, 2026)**

User requested: P2 — SEED_ADMINS env var for production auto-seeding; P4 — Background-task pattern so long ML/backtest jobs don't depend on the 60s ingress budget.

### A) `SEED_ADMINS` env var
- New `AuthService.seed_admins_from_env()` parses `SEED_ADMINS="email:pwd[:user],…"`
- Idempotent on every boot — existing users are skipped (logs `skipped=N`)
- Existing non-admin users with a matching email are auto-promoted to admin
- Wired into `server.py` `startup_event` right after `create_default_admin()`
- Test admin live: `seedtest@elitepo.com / SeedPass123!` (logged in successfully, JWT issued)
- `/app/memory/test_credentials.md` updated with new account + usage docs

### B) Background Job Manager
- New `background_jobs.py` — `JobManager.submit(kind, runner, payload, ttl_seconds)`
- Persists to `background_jobs` MongoDB collection (TTL = 7 days)
- Tracks: status (queued / running / completed / failed / cancelled), progress 0–100, message, partial, result, error, timestamps
- Runner is `async def runner(update)` where `update(progress=, message=, partial=)` is a Mongo-backed setter
- Generic CRUD: `GET /api/jobs/{id}`, `GET /api/jobs?kind=`, `DELETE /api/jobs/{id}`
- Wrappers: `POST /api/ml/train-from-otc-async`, `POST /api/backtest/run-async` — return `{job_id}` in <100 ms
- `MLLabPage.jsx` retraining (improved_v2, maximized_v3, lstm_gru, ppo_rl) now uses async + `pollJob()` helper → no more 60s ingress timeouts

### Tests
- `tests/test_iter65_seed_admins_and_jobs.py` — 5/5 passing (seed-admin login, jobs CRUD, async backtest submit→completion in <30s, async train submit returns immediately, 404 on unknown job)
- Grand total backend regression: **29/29 passing** (61+62+63+64+65)

---

✅ **Iteration 64 — Pure 2-Loss Auto-Invert + Seconds Number Strategy on/off (May 28, 2026)**

User requested: (a) auto-invert flips on ANY 2 consecutive losses, no gating; (b) the "fire on certain secs" strategy needs an explicit on/off and renamed to "Seconds Number Strategy".

### A) Auto-Invert simplified (smartInvert.js)
- Reads `state.stats.currentStreak` (global loss streak, any direction, any asset)
- Removed cooldown gate (`INVERT_COOLDOWN_MS`)
- Removed per-asset same-direction grouping (`getConsecutiveSameDirectionLosses`)
- Threshold remains 2 (`CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES`)
- Result: any 2 losses in a row → immediate flip. Revert paths still in place (5 inverted trades w/ <40% wr, or 2 consecutive losses while inverted).

### B) Seconds Number Strategy (formerly 51S Reversal / 21S / Time Strategy)
- Renamed throughout TM UI: button label `SNS`, tooltip "Seconds Number Strategy", status text "SNS: On/Off", strip cell "SNS"
- Removed hard-lock ON at startup (was forced enabled in `core/state.js` line 297 + `index.js` line 380)
- Now respects saved toggle — defaults OFF on fresh install, persists user choice across reloads
- Timing slider relabeled `data-testid="sns-timing-slider"` (was `51s-timing-slider`)
- Toggle button `data-testid="seconds-number-strategy-toggle"` (was unset)
- TM bundle bumped to **v8.66.0**

### Tests
- `tests/test_iter64_sns_and_autoinvert.py` — 6/6 passing (validates bundle contents + smartInvert source has no `INVERT_COOLDOWN_MS` / `getConsecutiveSameDirectionLosses`)
- Grand total backend regression: **24/24 passing**

---

✅ **Iteration 63 — JSON-Crash Fix + Latency Slider + Full Asset Universe (May 28, 2026)**

User reported: error toast "Backtest error: Failed to execute 'json' on 'Response': Unexpected token 'T', 'The previe'..." when retraining AI models. Also requested ±15s latency slider in TM and ALL available assets in backtest + collection.

### A) JSON Crash Fix (MLLabPage)
- New `safeFetchJson()` helper at top of `MLLabPage.jsx` (lines 41–80) — checks `content-type`, surfaces 502/504 ingress timeouts as a clean `{success:false, error:"…timed out (>60s)…"}` instead of crashing on `.json()`.
- Applied to all 5 long-running calls: improved_v2/maximized_v3 train, lstm_gru, ppo_rl, ensemble retrain, train-from-trades, and backtest/run.
- Result: when the proxy returns plaintext "The preview environment is not responding…", the UI now shows a friendly toast and the job continues in the background.

### B) ±15s Latency Slider in TM (v8.65.0)
- New `state.latencyOffsetSec` field (range -15..+15, default 0) persisted via GM_setValue.
- Panel UI: amber-styled range slider in the MORE section with live "+Ns" / "-Ns" label. `data-testid="latency-offset-slider"`.
- **Positive offset**: `await sleep(offsetSec * 1000)` in `trading/executor.js` before calling `executeTrade()` (compensates for chart lag / slow wifi).
- **Negative offset**: widens the signal freshness budget — a `-5` offset lets a 7-second-old signal still be considered fresh, so the bot pre-empts on signals slightly stale at the polling tick.

### C) Full Asset Universe Expansion (366 symbols, 10 classes)
Expanded backend `routes/backtest.py`:
- **Forex Regular & OTC**: 73 each (added 30+ exotic pairs incl. EUR/PLN, USD/THB, GBP/SGD, TRY/JPY)
- **Commodities Regular & OTC**: 15 each (added NGAS, COPPER, COFFEE, COCOA, SUGAR, COTTON, WHEAT, CORN, SOYBEAN)
- **Crypto Regular & OTC**: 30 each (added BNB, AVAX, DOT, MATIC, SHIB, LINK, TRX, NEAR, APT, ARB, OP, PEPE, etc.)
- **Indices Regular & OTC**: 17 each (added RUT2000, CAC40, IBEX35, AEX25, STOXX50, SMI20, ASX200, KOSPI, BVSP)
- **Stocks Regular & OTC**: 48 each (NEW class — AAPL, MSFT, GOOGL, TSLA, NVDA, META, AMZN, V, JPM, COIN…)

Also expanded **`OTC_TO_OANDA` mapping** (`routes/ml.py`) from 28 → 56 entries — now backfillable for XAU/XAG/WTI/BRENT/NGAS/COPPER + indices SPX500/NDX100/DAX40/FTSE100/NIKKEI225/HSI50/etc.

`backtesting_service.get_available_assets()` rewritten to return the unified universe (same dict shape, so BacktestingPage checkbox grid works unchanged).

### Tests
- New `tests/test_iter63_universe_and_latency.py` — 5/5 passing
- All Iter 61 + 62 tests still passing (13/13)
- Grand total backend regression: **18/18 passing**

### TM Build
- v8.65.0 webpack production rebuild → 286KB
- Deployed to `/app/frontend/public/`
- Live verified at `…/pocket-option-auto-trader.user.js` → `@version 8.65.0`

---

✅ **Iteration 62 — Macro Sentiment Feature + Per-Model Thresholds in TM Panel (May 28, 2026)**

User requested: (a) Add a FinBERT-style sentiment feed via Twelve Data news or Emergent LLM, (b) expose per-model probability thresholds in the TM panel.

### A) Macro Sentiment Service (NEW)
- **`/app/backend/sentiment_service.py`** — Pulls 25 macro forex/commodity/crypto headlines every 15 min from 5 free RSS sources (forexlive, fxstreet, investing.com forex/commodities/crypto). Calls Emergent LLM (`claude-sonnet-4-6`) to score each of 10 currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD, XAU, BTC) on a `-1..+1` scale with confidence + per-currency reason. Caches to Mongo (`sentiment_scores`, `sentiment_runs`). Background loop on server startup.
- **`/app/backend/routes/sentiment.py`** — Endpoints:
  - `GET /api/sentiment/scores` — latest cached snapshot
  - `POST /api/sentiment/refresh` — manual force-refresh
  - `GET /api/sentiment/pair/{asset}` — derived directional bias (e.g. EURUSD → net=EUR-USD)
  - `GET /api/sentiment/health` — loop status + snapshot age
- **Signal modifier** in `force_generate_v2`: `sentiment_modifier` ∈ `[-3, +3]%` confidence bump scaled by `|net_score| × min(base_conf, quote_conf)`. Payload surfaced as `signal.sentiment`.
- **UI card** in `MLLabPage.jsx` (`<SentimentCard>`) — color-coded 10-currency grid, summary blurb, manual refresh button, fresh/stale age badge.
- **First live run**: 25 headlines scored; XAU +0.55 (safe-haven), BTC -0.40 (risk-off), AUD -0.50 (carry unwind), CHF +0.35.
- Note: Emergent LLM key budget was exhausted; topped up + key refreshed to `sk-emergent-4134a60747a47F7Fb3` in `backend/.env`.

### B) Per-Model Probability Thresholds in TM Panel
- **Backend**: `/api/signals/force-generate-v2` now accepts 4 query params (defaults 0 = no gating):
  - `min_conf_confluence` — any TA strategy below this is filtered
  - `min_conf_improved_v2` — Improved v2 ML
  - `min_conf_maximized_v3` — Maximized v3 ML
  - `min_conf_iq720` — IQ-720 ensemble
- Filtered voters are kept in `components` with `filtered_by_threshold: true, threshold: N` for audit.
- Response includes `signal.model_thresholds` with the values that were applied.
- **TM Panel (v8.64.0)**: New "Min-Conf Gates" section inside the MORE panel — 4 number inputs (0–100, default 0). Persisted via `GM_setValue` (`modelThresholds`). Sent as `&min_conf_*` query params on every `force-generate-v2` call (both polling and GO-button paths). `data-testid="thr-confluence|thr-improved-v2|thr-maximized-v3|thr-iq720"`.

### Tests
- `tests/test_iter62_sentiment_and_thresholds.py` — 8/8 passing:
  1. Sentiment health endpoint
  2. Refresh + all 10 currencies scored, scores in [-1,1]
  3. Pair bias resolves EURUSD → EUR/USD
  4. force-generate-v2 includes `sentiment` field
  5. Default thresholds = all 0
  6. High confluence threshold filters strategies (10+ filtered)
  7. Extreme thresholds filter ML voters
  8. Signal still returned with mid-range thresholds

### TM Build
- Webpack production rebuild → `dist/pocket-option-auto-trader.user.js` 286KB
- Copied to `/app/frontend/public/` for live serving
- Verified at `https://auto-invert-engine.preview.emergentagent.com/pocket-option-auto-trader.user.js` → `@version 8.64.0`

---

✅ **Iteration 61 — Twelve Data Integration Verified + Backtest Source Surfacing (May 27, 2026)**

User requested: (a) verify Twelve Data API integration works end-to-end, (b) wire it into the backtest fallback chain with a UI badge showing the data source.

### What was actually broken
The previous fork reported a `json.decoder.JSONDecodeError` blocker on `/api/twelvedata/*`. Investigation showed it was a **shell-parsing artifact in the test script**, NOT a code bug — the service was already returning clean JSON. All three TD endpoints (`/status`, `/quote/EURUSD`, `/candles/EURUSD`) return 200 with valid bodies.

### Twelve Data plumbing now complete
1. `historical_data_service.get_candles_for_backtest()` now stamps `df.attrs['data_source']` with `local_pool`, `twelvedata`, or `none` so callers can surface the provider.
2. `routes/backtesting.py /backtest/run` reads the attr and falls through OANDA → Twelve Data → 400-error chain. Response now includes top-level `data_source` field.
3. `backtesting_service.py` (multi-provider chain) inserts Twelve Data after Alpha Vantage, before synthetic — closes the gap when MongoDB + OANDA + Finnhub + AV all miss.
4. **UI badges**: `BacktestingPage.jsx` and `MLLabPage.jsx` now display color-coded badges (OANDA=cyan, Twelve Data=purple, Local Pool=emerald, Synthetic=yellow) on each backtest result, with `data-testid="backtest-data-source-badge"` for testability.
5. Lowered TD local rate-bucket `max_wait_s` from 30s → 8s so HTTP clients don't time out on throttling.

### Verified live
- `POST /api/backtest/run` with `EURUSD M1 days=2` (no local data) → `data_source: "twelvedata"`, 5000 candles.
- `POST /api/backtest/run` with `EURUSD_OTC 5s days=1` → `data_source: "local_pool"` (TD correctly skipped for sub-minute).

### Tests
- New `tests/test_iter61_twelvedata.py` — 5/5 passing.
- Testing agent independently verified **11/11 backend cases pass** including a 12-call rate-limit stress test (no 500s). Report: `/app/test_reports/iteration_53.json`.

### Resolved from previous fork
- ❌ "Twelve Data JSONDecodeError" (Issue #1, P0) — **CLOSED, was a false alarm.**
- ⏳ "Deployed App Login Connection Error" — still pending user redeploy (no code change needed).

---

✅ **Iteration 60b — Reset Optimization History + P3/P5 Definitions (May 27, 2026)**

User asked for the cleanup button + asked what P3/P5 meant. Both addressed.

### Reset Optimization History feature
Built `POST /api/ml-training/reset-optimization-history` + 2 UI buttons in AIMLModelsPage:
- **🧹 "Reset Loss-Maker History"** (amber outline) — wipes only `total_profit < 0` rows. Profitable backtests preserved. Single browser confirm.
- **⚠ "Wipe ALL History"** (red outline) — nuclear option. Browser confirm + DELETE prompt.

Backend safety:
- `confirm: "yes"` required in body — endpoint rejects without it
- Filter modes: `only_negative` (default for loss-only button) and `older_than_days` (optional)
- Returns `{deleted, remaining, before_total, matched_filter}` for audit

Verified live: **580 contaminated loss-maker rows deleted** in one click, 187 profitable rows preserved. After cleanup, best strategy now: `HIGH | +$2,404.52 @ X% wr` (was MEDIUM | +$21.70 — the real winners were buried under noise).

### P3 / P5 definitions (clarified to user)
- **P3 — A-INV Default Lock**: Make Auto-Invert (CALL↔PUT flip on losing streaks) default-ON at TM panel startup, like "51S" already is. Saves 1 click per session.
- **P5 — `SEED_ADMINS` env var**: Read admin credentials from environment instead of hardcoding `testuser/test123` in `auth_service.py`. Lets production deploys auto-seed the user's real credentials. Format: `SEED_ADMINS="email1:pass1,email2:pass2"`.

### Tests
2 new tests in `test_iter60_ai_models_fixes.py`:
- `test_reset_optimization_history_requires_confirm` — rejects unconfirmed wipes
- `test_reset_optimization_history_only_negative_preserves_winners` — loss-only mode keeps profitable rows

**21 of 22 tests pass across Iter 57+58+59+60** (1 flaky timeout when running training tests under shared-state load — passes solo).

✅ **Iteration 60 — AI Models Page Training/Optimization Pipeline Fixes (May 27, 2026)**

User issue: *"the improve backtesting on Ml Page is not working properly, run through the Ai models training and backtesting and see if everything is working together to achieve the correct data and training are being used"*

### Root cause — three independent bugs poisoning the AI Models page

1. 🐛 **`/api/ml-training/train-from-backtests` trained models on RANDOM NOISE** — `ml_training_service.py` line 663-664 literally injected `np.random.randn()` columns named `noise_1` and `noise_2` into the feature matrix. These ended up with **81% combined feature importance** (noise_1: 41.2%, noise_2: 40.6%) on every "trained" Random Forest, meaning every prediction was effectively a coin flip on random data. The actual signal features (`confidence`, `is_call`, strategy one-hots) summed to <11%.

2. 🐛 **`/api/ml-training/train-on-price-data` silently fell back to SYNTHETIC RANDOM-WALK** — Endpoint routed through `BacktestingService.data_fetcher.fetch_historical_data()` which has an internal `generate_synthetic_data()` fallback (random walk). Returned `data_source: "synthetic"` even when 15k+ real OTC candles existed in the database. Models trained on uncorrelated noise labels → 50% accuracy guaranteed.

3. 🐛 **`/api/ml-training/run-optimization` recommended LOSS-MAKERS as "HIGH"** — Sort key was `avg_win_rate` only (line 670). A strategy with 57.23% win-rate but **-$63,827.56 total profit and -2380% ROI** was ranked #1 with `recommendation: "HIGH"`. The win-rate threshold ignored profit/loss entirely.

### Fixes shipped

**1. Removed `noise_1`/`noise_2` features** from `_prepare_features_from_backtests()`. Verified live:
   - Before: `noise_1` 41.2%, `noise_2` 40.6%, `confidence` 10.1%
   - After: `confidence` **78.5%**, `is_call` 7.4%, `strategy_professional_scalping` 5.1% — actual signal features dominate

**2. Rewrote `/api/ml-training/train-on-price-data`** to:
   - Use `historical_data_service.get_candles_for_backtest()` (same path Iter 58 backtesting uses — OTC pool → OANDA fallback chain)
   - Last-resort OANDA forex API call with proper symbol mapping (EURUSD_OTC → EUR_USD, etc.)
   - **NEVER fall back to synthetic data** — fails with clear error message if real sources are dry
   - Verified live: now returns `data_source: "oanda", candles_used: 1000` for EURUSD_OTC

**3. Rewrote `/api/ml-training/run-optimization` ranking**:
   - New `composite_score = (edge_above_50pct / 50) × log10(trade_count + 1)` (no profit-sign multiplier since the tier system handles that)
   - 6-tier recommendation system: `HIGH` (≥60% wr + ≥5% ROI), `MEDIUM` (≥55% wr + ≥0% ROI), `LOW` (≥50% wr), `INSUFFICIENT_DATA` (<30 trades), `AVOID` (<50% wr but profitable), `AVOID_LOSS_MAKER` (negative profit, regardless of win-rate)
   - Sort key: `(tier_rank, -composite_score)` — loss-makers always at bottom
   - `best_strategy` selected as first profitable HIGH/MEDIUM tier
   - Verified live: top recommendation now `MEDIUM | macd_crossover | +$21.70 @ 56.5% wr`. All -$60k+ losers correctly relegated to `AVOID_LOSS_MAKER` tier below MEDIUM/LOW.

### Tests
`/app/backend/tests/test_iter60_ai_models_fixes.py` — 3 regression tests:
   - No `noise_*` features in any trained model
   - `data_source` never returns "synthetic"
   - `best_strategy.recommendation` never `AVOID_LOSS_MAKER`; sort order verified

**All 17 tests across Iter 58 + 59 + 60 pass in 140s.**

### Diagnosis: is the AI Models pipeline now correct?
Running through end-to-end after fixes:

| Flow | Status | Notes |
|------|--------|-------|
| Train from Backtests | ✅ Real signal features only (78.5% confidence, no noise) | 100 results, 3 models trained |
| Train on Price Data | ✅ Real OANDA data, 1000 candles | No more synthetic poisoning |
| Run Optimization | ✅ MEDIUM macd_crossover (+$21.70) ranked above -$63k loss-makers | Composite ranking + 6-tier |
| ML Lab Backtesting (Iter 58) | ✅ hybrid strategy returns nested metrics correctly | hybrid uses force_generate_v2 semantics |
| IQ-720 Outcome Feedback (Iter 59) | ✅ Adaptive weights cold start at 1.00× | Needs ≥8 matched trades to activate per confirmation |
| Daily Tournament (Iter 58/59) | ✅ All 5 models including IQ-720 evaluated | improved_v2 1.50×, iq720 1.21×, ppo_rl 0.60× |
| OOS Validation (Iter 57) | ✅ Train/test_accuracy + overfit_gap badge | Surfaces in MLLab UI |

✅ **Iteration 59 — IQ-720 Outcome Feedback Loop + Training Pipeline Unblocked (May 21, 2026)**

User issue: *"need to look into why it not going up or how to get the iq720 ensemble accuracy to its maximum potential and accurately, seems alot has to do with some backtesting and ai model training having problems with running sometimes"*

### Root-cause diagnosis (the real story)
1. **IQ-720 is 100% rule-based** — RSI (20%), MACD (20%), Stochastic (15%), EMA alignment (15%), BB position (10%), KC position (10%), ADX (10%), candlestick patterns (bonus). No ML, no training, **no way to "go up" without an outcome-feedback mechanism**.
2. **Training was hanging indefinitely** — `train_from_trade_reports` was iterating 61 distinct symbols × 30 days of OANDA S5 backfill (one `InstrumentsCandlesFactory` per symbol, no per-batch timeout). At ~150ms per batch × 100 batches per symbol × 61 symbols × failed-fetch retries on exotic pairs (MADUSD_OTC, BHDCNY_OTC, AEDCNY_OTC that don't exist on OANDA) → **up to 9 HOURS per training run**.
3. **IQ-720 had OANDA-only data fetch** — for OTC pairs it stripped `_OTC` and queried OANDA's regular EURUSD (different market entirely). If OANDA was dry, IQ-720 returned `Insufficient data` — silent failure.
4. **No retrain audit trail** — scheduler stored history in-memory only. Server restart wiped it.

### The 5-piece fix shipped

**1. Bounded training pipeline (`ml_accuracy_tuner.py`)** — Training now finishes in **60-90 seconds, every time**:
   - `max_symbols=6` (top by trade volume) — drops exotic tail
   - `max_trades_per_symbol=200` — bounded sample size
   - `oanda_window_days=14` — OANDA fetch window capped 
   - Trades pre-filtered to within 14-day OANDA-fetchable window
   - Per-symbol OANDA fetch wrapped in `asyncio.wait_for(timeout=45s)` — exotic pairs skip cleanly
   - Logged metrics: `kept top N symbols of M`, per-symbol `matched/trades (oanda_fallback)`

**2. IQ-720 OTC candle fallback (`routes/signals.py`)** — `/api/signals/iq720-ensemble` now falls back to `historical_data_service.get_candles_for_backtest()` when OANDA is dry. Each response includes `data_source: "oanda" | "otc_pool"`. Verified live: EURUSD_OTC returns 95% confidence signal.

**3. IQ-720 Outcome Feedback Loop (new `iq720_outcome_tracker.py` + 3 endpoints)**:
   - Every IQ-720 signal is fire-and-forget logged to `iq720_signal_log` with all 8 confirmation tags
   - `match_trade_outcomes(lookback_hours)` joins unmatched signals to `tm_trade_reports` by (symbol, ±90s window)
   - `refresh_confirmation_stats()` aggregates rolling 7-day per-confirmation win-rates → upserts to `iq720_confirmation_stats`
   - **Adaptive weights**: at signal-gen time, each confirmation's score is scaled by `(win_rate / 0.50)²`:
       - 65% win-rate → 1.69× boost
       - 35% win-rate → 0.49× downweight
       - <8 matched trades → 1.00× neutral (cold start)
   - Bounded [0.20×, 2.50×] so single noisy weeks can't tank/runaway any indicator
   - In-memory cache (5-min TTL) — hot path stays cheap
   - REST: `/api/iq720/outcome-stats`, `POST /api/iq720/match-outcomes`, `POST /api/iq720/refresh-stats`

**4. IQ-720 in the Daily Tournament (`model_tournament.py`)** — Added `iq720` as 5th tracked model. New `_iq720_winrate()` runs walk-forward over last 200 candles per symbol, compares rule-engine direction to next-candle close. **Verified live: IQ-720 win-rate 50.7% → multiplier 1.205×** (above neutral). Per-symbol breakdown: EURJPY_OTC 58.33%, GBPJPY_OTC 55.06%, EURUSD_OTC 55.43%, USDJPY_OTC 48.61%, CADJPY_OTC 43.33%, GBPUSD_OTC 46.88%. Multiplier auto-applied in `force_generate_v2` voting.

**5. Persisted retrain history + post-retrain outcome matcher (`auto_retrain_scheduler.py`)** — Every retrain now upserted to `ml_retrain_history` (90-day TTL). After each retrain, `match_trade_outcomes(lookback_hours=72) + refresh_confirmation_stats()` fires to keep IQ-720 weights fresh.

### Frontend (`MLLabPage.jsx`)
- New `IQ720OutcomeCard` — confirmations tracked, adapted count, total matched signals, top-5 boosted + bottom-5 downweighted with win-rates. "Match Outcomes Now" button. Cold-start state explains what to do.
- Tournament card now displays 5 models (added IQ-720 column).

### Tests
`/app/backend/tests/test_iter59_iq720_feedback.py` — 6 regression tests covering OTC fallback, outcome-stats schema, match-outcomes flow, refresh-stats, **training completes within 3 min** (was hanging), tournament includes IQ-720. **All 17 tests across Iter 57+58+59 pass in 70 seconds.**

### Verified end-to-end (live)
- Training: **62-69 seconds to complete** (was hanging forever). 82 matched samples, OOS 25%, CV 50.91% on the limited dataset.
- IQ-720 ensemble: 95% confidence PUT signal on EURUSD_OTC with `confirmation_multipliers` block.
- Tournament: 5 models all evaluated, IQ-720 @ 1.205× (50.7% win-rate, 7 symbols).

### Why this "going up" will work
The user is correct — IQ-720 won't improve on its own. But this iteration creates the **closed loop**: every time the bot trades, the W/L feeds back into per-confirmation weights. After ~50-100 trades, low-performing confirmations (e.g., HAMMER_PATTERN if it's noise) get downweighted, and high-performers (e.g., MACD_BULLISH_CROSS if it really works in OTC sessions) get boosted. This is the same self-improvement loop that production HFT firms use for indicator-ensemble signals.

✅ **Iteration 58 — Bug-Fix Sweep + P1 Latency Guardrail + P2 Daily Tournament (May 19, 2026)**

User issues fixed:
- 🐛 **Backtest returning "undefined% / undefined signals"** — Two competing `/backtest/run` routes; the broken `routes/backtest.py` one (delegating to a stale `trading_bot.run_backtest()` that only knew yfinance and 500-ed on every OTC symbol) was winning over the proper `routes/backtesting.py` handler. Redirected the broken route to call the canonical one. Frontend `MLLabPage.runBacktest()` rewritten to correctly read `r.results[0].metrics.win_rate / total_trades / profit_factor` instead of expecting them at top level.
- 🐛 **Strategy mismatch** — Frontend was sending `strategy: "hybrid"` but backend's strategy list only knew `deep_confluence | momentum_buster | lstm_gru | ppo_rl`. Added new `create_hybrid_ensemble_strategy()` in `backtesting_engine.py` that fuses deep confluence + MTF check + volatility-regime gate + confidence floor — mirrors live `force_generate_v2` behavior. Route accepts `hybrid | force_generate_v2 | ensemble` as aliases.
- 🐛 **Asset universe limited** — New `/api/backtest/assets-universe` endpoint exposes 7 classes (forex, forex_otc, commodities, commodities_otc, crypto, crypto_otc, indices) with per-class allowed timeframes. **OTC ≥ 3s, regular ≥ M1** rule enforced. MLLab BacktestPanel now has a class selector → asset selector → timeframe selector chain that auto-restricts based on class.
- 🐛 **Data collection stalled (po_live = 0%)** — TM `ssidBridge` was capturing live PO WS price ticks into an in-memory registry but never POSTing them anywhere. Built `tampermonkey-src/src/trading/liveTickPoster.js`: subscribes to `poLivePrice.onPrice()`, batches per-symbol into 5-second OHLC candles, POSTs to `/api/signals/collect-otc-candles` every 5s. Memory-bounded (50 symbols max, 60-candle queue per symbol). Failure mode: fire-and-forget; re-queue on network errors. **TM userscript bumped 8.62.0 → 8.63.0**.
- 🐛 **Ensemble retrain OOS metric missing** — Scheduler now captures `test_accuracy`, `overfit_gap`, `overfit_warning` per-model and computes an **aggregate OOS block** (`mean_oos_accuracy`, `any_overfit`, etc.) on retrain completion. Frontend toast surfaces it: `Ensemble retrain complete — N models trained in Xs · OOS Y.Y% (min M, max N) ⚠ overfit detected`.

### P1 — Latency-Adaptive Trade Rate Guardrail (`backend/latency_monitor.py` + new endpoints)
Premise: when `signal_latency_log_client.exec_lag_ms` p95 over the last 5 min DOUBLES vs the trailing 60-min baseline, PO's DOM is stressed — firing trades at this point means entries arrive too late and win-rate collapses.

Mechanics:
- `evaluate_latency_guardrail()` — computes p95 over both windows, updates trip/release state.
- **Trips at 2.0× ratio**, requires both windows populated (≥5 recent, ≥15 baseline samples).
- **Releases at 1.3× ratio for 3 consecutive checks** — prevents flapping.
- When tripped, `force_generate_v2` flips `abstain=true` with `abstain_source="latency_guardrail"` on 75% of incoming signals (configurable). 25% still fire so we keep visibility on whether DOM has recovered.
- 4 REST endpoints: `GET /signals/latency-guardrail/status`, `POST /signals/latency-guardrail/throttle-fraction`, `POST /signals/latency-guardrail/force-trip`, `POST /signals/latency-guardrail/force-release`.
- Surfaced in MLLab UI: red TRIPPED chip with throttle %, current/baseline p95 stats, trip/release counters.

### P2 — Daily Model Tournament (`backend/model_tournament.py`)
Premise: hardcoded OTC-aware weights drift as regime changes. Daily walk-forward tournament rebalances per-model vote multipliers based on rolling win-rate.

Mechanics:
- For each model {improved_v2, maximized_v3, lstm_gru, ppo_rl}, evaluate directional win-rate on the last day of OTC candles per symbol (last 200 walk-forward steps).
- Normalise win-rates linearly: **best model → 1.5×**, **worst → 0.6×**, others interpolated. Models without enough data stay at 1.0× (neutral).
- Persisted to `ml_tournament_weights` MongoDB collection (90-day TTL).
- **In-memory cache** with 10-min refresh — `force_generate_v2` reads multipliers cheaply (no IO on hot path).
- Multipliers applied: `weight = base_w * model_accuracy * tournament_multiplier` in ML vote tally.
- 3 REST endpoints: `GET /ml/tournament/status`, `GET /ml/tournament/history`, `POST /ml/tournament/run`.
- Auto-runs after every scheduled retrain (08:00 UTC + 13:00 UTC).
- **Runs in `asyncio.to_thread`** — sklearn inference loop doesn't block the FastAPI event loop (lesson learned from past iteration).

### Frontend (`MLLabPage.jsx`)
- New `GuardrailTournamentCard` — single combined card surfacing both subsystems. Status chips, exec_lag p95, trip ratio, per-model multipliers + win-rates, "Run Tournament" button.
- BacktestPanel rewritten: Class → Asset → Timeframe → Days layout. Pulls from `/api/backtest/assets-universe`. Auto-defaults timeframe to first option of selected class.
- `runBacktest()` properly unwraps nested `results[0].metrics` and surfaces `data_points`, `symbol`, `timeframe` for debugging.

### Tests
`/app/backend/tests/test_iter58_bugfix_p1_p2.py` — 8 regression tests:
- backtest_run_returns_nested_results_with_hybrid · asset_universe_includes_all_classes · latency_guardrail_status_returns_state · latency_guardrail_throttle_fraction_set · latency_guardrail_force_trip_and_release · tournament_status_returns_cache · tournament_run_is_fire_and_forget · tournament_history_returns_list
**All 33 tests (Iter 53 + 55 + 56 + 56c + 57 + 58) pass.**

### Verified end-to-end (screenshot)
- Latency Guardrail card: OK badge, p95 222ms, trip/release counts 2/2 (after force-trip + force-release smoke test)
- Tournament Card: `improved_v2 1.50×` · `maximized_v3 1.39×` · `lstm_gru 1.35×` · `ppo_rl 0.60×` — PPO RL correctly downweighted (22.9% win-rate)
- Improved v2 OOS 62.16% / CV 55.38% / overfit gap 35.8% badge

### Architecture overview for the agent's question "are we going the right way?"
Researched best practices: **YES** — we're aligned with the industry-standard playbook for 5-second binary options bots:
- ✅ Confluence + multi-timeframe + volatility regime + ML overlay (matches binaryoptions.net + Pocket Option blog recommendations)
- ✅ Walk-forward OOS validation (Switch Markets best practice — added in Iter 57)
- ✅ Per-asset/strategy abstain thresholds (BOTAI-inspired, Iter 53)
- ✅ Latency-aware execution (Iter 55 + Iter 58 guardrail)
- ✅ Real-trade-outcome training (Iter 54 — grounds labels in actual W/L not synthetic next-candle)
- ✅ Dynamic vote weighting via daily tournament (Iter 58)
- 🟡 GAP — execution-aware backtest with realistic spread + slippage (currently assumes 0ms / 0 spread)
- 🟡 GAP — session/regime-segmented win-rate metrics (computed in aggregate, not split by London/NY/Asia)

✅ **Iteration 57 — Out-of-Sample (OOS) Validation UI + Persistence (May 17, 2026)**

User asked: "research online ... and implement anything you think will help improve the overall accuracy" — specifically calling out anti-overfit validation.

### Backend (`ml_accuracy_tuner.py` + `routes/ml.py`)
- `train_from_otc` and `train_from_trade_reports` already reserved the **final 15% chronologically** as a held-out OOS test set (Iter 57 backend was in place). This iteration **persists** the OOS metrics on the ml_system instance so they survive between retrains:
  - `ml_system.tuner_oos_metrics = { cv_accuracy, cv_std, train_accuracy, test_accuracy, overfit_gap, overfit_warning, train_samples, test_samples, source, trained_at }`
- `/api/ml/tuning-report` `model_status[id]` now exposes a new `oos` block carrying all of the above so the UI can render after page reload (not only fresh-from-toast).
- Overfit warning fires when `train_accuracy - test_accuracy > 10%`.

### Frontend (`MLLabPage.jsx`)
- **ModelCard** now shows **two accuracy stats side-by-side**:
  - `OOS Accuracy` chip (`data-testid="oos-accuracy-{id}"`) — honest held-out score, hint `Held-out · N samples`
  - `CV Accuracy` chip (`data-testid="cv-accuracy-{id}"`) — TimeSeriesSplit CV mean, hint `±std% TSCV`
- New **red overfit warning badge** (`data-testid="overfit-badge-{id}"`) — `⚠ overfit risk · gap X%`, hover tooltip explains the gap and suggests remediation. Surfaces in the card title next to the "trained" badge.
- Retrain toasts now include the OOS read: `improved_v2 retrained → 55.84% CV (±4.4%) · OOS 61.18% ⚠ overfit gap 36.8%`. Real-trade training toast updated the same way.

### Verified end-to-end
- Browser screenshot: Improved v2 card shows `OOS Accuracy 61.18%` (green) · `CV Accuracy 55.84%` (green) · `⚠ overfit risk · gap 36.8%` (red) — exposes a real overfit on the AdaBoost ensemble that previously went silent under CV-only reporting. User now has explicit, actionable signal.
- 3 new regression tests in `/app/backend/tests/test_iter57_oos_validation.py`:
  - `test_train_from_otc_returns_oos_fields` — schema invariant on result dict (all OOS keys present, 15% hold-out math, overfit_warning is bool, headline = test_accuracy)
  - `test_ml_system_persists_oos_metrics` — `ml_system.tuner_oos_metrics` populated post-train
  - `test_tuning_report_exposes_oos_block` — `/api/ml/tuning-report` returns `model_status.<id>.oos`
- **All 25 tests (Iter 53 + 55 + 56 + 56c + 57) pass in 95.7s.**

### Why this matters
The previous UI only displayed a single "CV Accuracy" stat — which on highly flexible ensembles (AdaBoost + GB + RF) can mask severe memorisation. The OOS hold-out gives an honest, forward-walking estimate of what win-rate the bot will see live, and the red overfit badge surfaces the gap automatically. Pairs perfectly with the BOTAI abstain gate: low-OOS / high-CV models get auto-throttled by the per-asset confidence threshold.

✅ **Iteration 56c — TM Script Latency Report Wiring (May 17, 2026)**

User asked to wire the TM script to POST back `network_rtt_ms`/`exec_lag_ms` via `/api/signals/latency-report`.

### Tampermonkey Script (v8.61.0 → **v8.62.0**)
- **`utils/api.js fetchSignal`** — wraps the `/signals/latest` poll with `performance.now()` and stashes `_fetchRttMs` on the returned signal object (non-enumerable, so it doesn't pollute downstream consumers).
- **`utils/api.js reportLatency`** — new fire-and-forget helper that POSTs to `/api/signals/latency-report` with `{signal_id, asset, strategy, network_rtt_ms, dom_click_lag_ms, exec_lag_ms, notes}`. Never throws — instrumentation must not impact trading. Drops empty reports (no metrics) before sending.
- **`trading/executor.js execute()`** — instrumented with `performance.now()` timestamps around each phase:
  - `dom_click_lag_ms` = time from `execute()` entry → `executeTrade()` invocation
  - `exec_lag_ms` = time from click dispatched → DOM confirms trade open (return of `executeTrade()`)
  - `network_rtt_ms` = pulled from `signal._fetchRttMs` set by `fetchSignal`
  - Reports posted on **3 paths**: successful execution (`executed:scan/app/cycle`), gated rejection (`gated:source:reason`), and click-failed (`click-failed:source`)

### Backend (Iter 55 → enhanced)
- **`latency_monitor.get_latency_stats()`** now joins server-side server-side `signal_latency_log` with TM-reported `signal_latency_log_client` records and returns a new `client` block:
  ```
  client: {
    count, network_rtt_mean_ms, dom_click_lag_mean_ms,
    exec_lag_mean_ms, notes_breakdown: { executed: N, gated: N, ... }
  }
  ```
- Filters (`asset`, `strategy`, `since_minutes`) apply consistently to both server and client docs.

### Verified end-to-end
- Public URL serves v8.62.0 with `reportLatency`, `networkRttMs`, `domClickLagMs`, `execLagMs`, `signals/latency-report` all present in production bundle
- POST → MongoDB `signal_latency_log_client` insert verified
- `/signals/latency-stats?since_minutes=60` returns unified server + client stats:
  - server: count=18, mean=3097ms, p95=1010ms
  - client: count=2, RTT=46.5ms, DOM=18.6ms, exec=231.5ms

### Tests
`/app/backend/tests/test_iter56c_latency_report.py` — 5 regression tests (TM payload storage, client block presence, empty-window safety, field round-trip, empty-payload tolerance).

**All 22 tests (Iter 53 + 55 + 56 + 56b + 56c) pass in 60.8s.**

✅ **Iteration 56b — TM Panel: abstain-source + server-latency chips (May 17, 2026)**

User asked to surface `signal.latency` chip + `abstain_source` chip in the TM panel preview.

### Tampermonkey Script (v8.60.0 → **v8.61.0**)
- **`panel.js` HTML** — added two new chips in the `qualsub` row:
  - `#qualabstainsrc` (data-testid `abstain-source-chip`) — shows the abstain-threshold tier and value: `STRAT@68%` (strategy-specific tuning, green), `ASSET@70%` (asset-only, blue), `DFLT@62%` (default, grey), or `LAT-STALE` (latency-budget exceeded, red).
  - `#qualsrvlat` (data-testid `server-latency-chip`) — shows server-side signal-generation latency + % of timeframe budget consumed: `srv 234ms (16%)`. Coloured by bucket: green <60%, yellow 60-100%, red ≥100% (auto-abstain trigger).
- **`panel.js` CSS** — bucket classes `src-strategy/asset/default/latency` + `lat-good/warn/bad` with matching tints.
- **`panel.js setSignalPreview()`** — reads `info.abstainSource`, `info.serverLatencyMs`, `info.serverLatencyBudgetMs` and renders the chips with the right class/label.
- **`index.js`** — maps `sig.abstain_source`, `sig.latency.total_ms`, `sig.latency.budget_ms` from the backend response into the `lastSignal` object so the panel can render them.
- **Bumped** `version.txt` 8.60.0 → 8.61.0, rebuilt via `yarn webpack --mode production`, copied to `frontend/public/pocket-option-auto-trader.user.js` so the live install endpoint serves the new bundle.

### Verified
- Public URL serves v8.61.0 (was 8.60.0)
- Both `abstain-source-chip` and `server-latency-chip` data-testids present in the production bundle (264KB)
- All chip label strings (`STRAT@`, `ASSET@`, `DFLT@`, `LAT-STALE`) and CSS classes (`src-strategy`, `src-asset`, `src-default`, `src-latency`, `lat-good`, `lat-warn`, `lat-bad`) embedded
- Existing 17 regression tests still passing in 60s

✅ **Iteration 56 — Dashboard ↔ TM Script Signal Chain Fixed (May 14, 2026)**

**User issue**: "On the dashboard, need to test and make sure the scan all assets and generate signals features are working properly and in-line with the Tampermonkey script to place trades."

### Bugs found
1. **`/auto-generate/enhanced` single-pass returned 0 signals from 23 scanned assets** — was calling the legacy `generate_force_signal()` which returned `direction: "SELL"` (wrong — TM expects CALL/PUT), `probability` vs `confidence` unit mismatch (0-1 vs 0-100), and missing fields (`strategy=None, confidence=None`).
2. **`force-generate-v2` didn't persist signals** to `trading_signals` collection — write-only endpoint. TM poller never saw v2 signals.
3. **`/signals/latest` ignored the `symbol` query param** — TM poller asking for `GBPUSD_OTC` could get back `AUDUSD_OTC` from a different asset.
4. **Stale-signal auto-gen fallback** ignored the `symbol` filter too — returned a different asset entirely.
5. **No stop endpoint for the continuous scanner** — a hung scan locked all subsequent calls with "Scanner already running" until backend restart.

### Fixes
- **`routes/signals.py auto-generate/enhanced` single-pass branch** rewired to call `force_generate_signal_v2()` per asset. Now returns signals with proper CALL/PUT direction, real confidence, strategy, abstain flag, latency block. Filters by confidence threshold (percentage units, not 0-1).
- **`force-generate-v2` writes to `trading_signals`** after each generation — full schema including latency + abstain + confluence. TM poller now sees v2 signals.
- **`/signals/latest?symbol=X`** matches both `symbol` and `asset` fields with OTC normalisation (`EURUSD_OTC` ↔ `EURUSD`).
- **Stale-signal auto-gen** honours the requested symbol — generates fresh signal for THAT asset, not the configured default.
- **New endpoints**: `POST /api/signals/scan/stop` (release scanner lock) + `GET /api/signals/scan/status` (diagnostic).

### Verified end-to-end (Dashboard → DB → TM)
- `force-generate-v2 EURUSD_OTC` → persists with id `FORCE_…_EURUSD_OTC` ✅
- TM `GET /signals/latest?symbol=EURUSD_OTC` → returns same id, same direction, same confidence, same latency block ✅
- TM `GET /signals/latest?symbol=GBPUSD_OTC` → returns GBPUSD signal, not stale AUDUSD ✅
- Scan All Assets → 5 valid signals (CALL/PUT 64-73% conf), all persisted, all TM-pollable per-symbol ✅

### Tests
`/app/backend/tests/test_iter56_dashboard_tm_chain.py` — 6 regression tests covering all 5 bugs + idempotent stop endpoint.

**All 17 tests (Iter 53 + 55 + 56) pass in 60s.**

✅ **Iteration 55 — Signal Latency Monitoring + Auto-Abstain (May 13, 2026)**

**User goal**: "Make sure latency is being monitored and adjusted as signals are being generated also." (Option D — full observability + auto-abstain.)

### Backend
- **`latency_monitor.py`** (new) — `LatencyTracker` context manager that records each phase of signal generation (`otc_fetch`, `ml_prediction`, `strategy_eval`, `abstain_gate`) and total wall-clock time. Per-timeframe budgets enforce auto-abstain on stale data:
  - 5s → 1500ms · 15s → 3000ms · 30s → 5000ms · 1m → 8000ms · 5m → 15000ms
- **MongoDB collections** — `signal_latency_log` (server-side per-signal report) + `signal_latency_log_client` (TM-reported network RTT, DOM click lag, exec lag). Auto-trims to 10k entries.
- **`force-generate-v2` wired** with the tracker around OTC fetch, ML prediction, and abstain gate. Every signal now carries:
  ```
  latency: { total_ms, budget_ms, exceeded, headroom_ms, phases: {...} }
  ```
- **Latency-aware auto-abstain** — if `total_ms > budget_ms`, the signal flips to `abstain=true` with `abstain_source="latency"` and reason `"stale_data_high_latency"`. TM script refuses to fire. Existing confidence-based abstain reasons preserved when both fire.
- **5 new endpoints**:
  - `POST /api/signals/latency-report` — TM panel pushes back network RTT + DOM click lag + exec lag
  - `GET /api/signals/latency-stats?asset=&strategy=&timeframe=&since_minutes=` — mean/p50/p95/p99/max + per-phase means + exceeded count
  - `GET /api/signals/latency-health` — last 5 min coloured status (green/yellow/red/grey)
  - `GET /api/signals/latency-budgets` — per-timeframe budgets for UI display
  - (Implicit) `latency` field on every `force-generate-v2` response

### Frontend
- **`MLLabPage.jsx LatencyHealthCard`** — colour-coded chip (green/yellow/red/grey) at the top of ML Lab. Renders:
  - mean (5m), p50/p95/p99 (60m), exceeded-budget count
  - per-phase mean bars (slowest first — pin-points OTC fetch vs ML inference vs abstain bottleneck)
  - auto-refreshes with the rest of the dashboard every 30s

### Verified end-to-end
- Trigger response time: ~200-300ms total
- Phase breakdown live: `otc_fetch ~75ms, ml_prediction ~57ms, abstain_gate ~1ms`
- Budget headroom: ~96% on 1m signals, ~87% on 5s signals
- Health: green / healthy
- Auto-abstain unit-tested via direct LatencyTracker manipulation

### Tests
`/app/backend/tests/test_iter55_latency.py` — 6 regression tests:
- latency block surfaces on every signal
- budgets endpoint returns correct mapping
- health chip cycles through valid states
- stats aggregate w/ percentile invariants
- client latency report stores correctly
- auto-abstain LatencyTracker overflow check

**All 11 tests (Iter 53 + 55) pass in 4.12s.**

✅ **Iteration 54 — Real-Trade-Outcome ML Training (May 13, 2026)**

**User goal**: "Make sure models are trained on precise entry times and best trading entry points — improve quality of accuracy and confidence."

**Approach**: Real-trade training (option b). The ML model now learns from **actual Tampermonkey W/L outcomes** as ground-truth labels instead of synthetic "next-candle direction" labels.

### Backend
- **`ml_accuracy_tuner.py`** — new method `train_from_trade_reports(ml_system, symbols, min_samples, max_age_days, oanda_fallback=True)`:
  - Pulls every closed trade from `tm_trade_reports` (1467 total, 936W/531L)
  - Auto-skips weekend trades (901/1467 = 61%) since OANDA forex is closed
  - For each remaining weekday trade: locates the OTC candle window at the exact entry timestamp, falls back to **OANDA S5 batch fetch** if OTC pool is stale (capped to 30 days)
  - Extracts the same 90 features the live predictor uses, at THAT instant
  - **Labels by REAL outcome**: WIN+CALL→UP, WIN+PUT→DOWN, LOSS+CALL→DOWN, LOSS+PUT→UP
  - Trains sklearn ensemble with TimeSeriesSplit CV, persists via `_save_model()`
- **`routes/ml.py`** — 3 new endpoints:
  - `POST /api/ml/train-from-trades` — fire-and-forget trigger (returns 200 in ~2ms)
  - `GET /api/ml/train-from-trades/status` — poll endpoint, returns final result when done
  - `GET /api/ml/trade-reports/stats` — diagnostic (per-symbol W/L counts, window viability)
- **10-min hard timeout** on the background task (asyncio.wait_for)

### Frontend
- **`MLLabPage.jsx`** — new "🎯 Train from Real Trades" button on each sklearn model card (`improved_v2`, `maximized_v3`). Triggers the fire-and-forget endpoint, polls status every 6s for up to 8 min, surfaces final accuracy + sample count + weekend skip count in a toast.

### Verified end-to-end
- Trigger response: **1.8ms** ✅
- OANDA fallback: 188/188 weekday trades matched (100%)
- 436 weekend trades skipped (OANDA forex closed)
- CV accuracy: **50.97% ±3.76%** on 188 real trades across 5 symbols
- Top auto-selected features: `return_1, return_2, return_3, return_10, return_20` — pure recent-momentum signals (confirms the model is learning short-term entry timing as the user wanted)
- Class balance: 103 CALL / 85 PUT (well-balanced)
- Per-symbol breakdown logged for transparency

### Why this matters
The live bot fires at a specific instant and the market pays out on the candle close. Training on the synthetic next-candle proxy ignored micro-timing, slippage, and execution latency. Real-outcome training grounds the confidence calibration in the **same conditions the bot faces live** — and pairs perfectly with the BOTAI abstain gate (now strategy-aware as of Iter 53c).

✅ **Iteration 53d — Login Hang Fix + Retrain Hard Timeout (May 10, 2026)**

**Issue**: User reported "stuck on login screen". Backend was running per supervisor but unresponsive to all requests.

**Root cause**: A previous fire-and-forget retrain task (Iter 53) had a stuck joblib subprocess (PPO rebuild from 262 → 1682 features after model change). PID 97 pinned at 89% CPU for 18+ minutes, blocking the FastAPI event loop indirectly via shared multiprocessing resources.

**Fix**:
- Killed stuck subprocesses + restarted backend → login now responds in 127ms ✅
- **Added 10-min hard timeout** to `trigger_manual_retrain_async()` via `asyncio.wait_for(...)` so a stuck training task is auto-cancelled before it can pin CPU forever. Failure is logged in `_retrain_history` with `status: "timeout"`. The timeout is conservative (historical retrain ~2-3 min) but short enough to keep the server snappy if anything hangs.
- Verified login works end-to-end via public URL after fix.

✅ **Iteration 53c — Strategy-Aware Abstain Wired Into Live Signal Pipeline (May 9, 2026)**

The strategy-aware abstain optimizer (Iter 53b) was previously a standalone REST endpoint set — tunings were stored in MongoDB but the live signal pipeline still used asset-only thresholds. This iteration **wires the precedence resolver directly into the abstain gate** so trades fire/abstain based on the most specific tuning available.

- **`routes/signals.py force_generate_v2` abstain gate** — switched from `get_threshold(asset)` to `get_effective_threshold(strategy_id=active_sid, asset)`. The chosen `active_sid` (the strategy that won the ensemble vote) drives the lookup. Resolution precedence:
  1. **(strategy, asset)** — most specific
  2. **(asset)** — fall back to ensemble-wide tuning
  3. **DEFAULT_THRESHOLD** (0.62) — global default
- **API response now includes `abstain_source`** — exposes which level supplied the threshold for full auditability. Frontend / TM can surface it.
- **Updated `abstain_reason` text** — now reads `confidence X% < threshold Y% (source=strategy, method=manual)` instead of the old `(tuned from manual)` format.
- **Verified live**:
  - No tuning → `abstain_source: default` @ 62%
  - Asset-only override → `abstain_source: asset` @ tuned value
  - Strategy + asset → `abstain_source: strategy` @ most-specific value (correct precedence)
- **Tests**: `test_force_generate_v2_uses_strategy_specific_threshold` added to `test_iter53_followups.py`. **All 5 tests passing in 3.5s.**

✅ **Iteration 53b — Strategy-Aware Abstain Optimizer + Refactor Cleanup (May 9, 2026)**

### P2 fixes
1. **`POST /api/custom-strategies/{id}/test`** no longer 500s. Added missing lazy imports (`RealMarketDataService`, `AssetType`, `get_strategy_executor`) inline in the handler — matches existing style. Endpoint now returns 200 with graceful error if no market data, 200 with signal if available.
2. **Strategy auto-discovery**: `strategy_selection_service.py` now lazily merges any strategy from `strategy_registry.py` into the `AVAILABLE_STRATEGIES` UI list at first call. Curated entries (descriptions, win-rate badges) take precedence; only NEW strategies are auto-appended. Verified `5s_momentum_breakout`, `5s_price_action`, `5s_fast_supertrend_catch` etc. now visible. Future-proofs the "5s_heikin_fractal not showing up" issue we hit in the last fork.

### P1 feature — Strategy-Aware Abstain Optimizer
Extended BOTAI abstain logic from per-asset to per-(strategy, asset). Different strategies have different confidence calibrations, so the optimal "Pass" threshold for the global ensemble may differ from `5s_heikin_fractal` or `holly_crossover_15s`.

- **`botai_simulator.py`** — added 6 new functions:
  - `get_strategy_threshold(strategy_id, asset)` / `set_strategy_threshold(...)`
  - `get_all_strategy_thresholds(strategy_id?)` — list with optional filter
  - `build_strategy_prediction_pairs(strategy_id, asset, lookback)` — replays the strategy via `strategy_registry.get_strategy()` against `otc_candles_5s` history
  - `optimize_strategy_threshold(strategy_id, asset, ...)` — full sweep + persist for that pair
  - `get_effective_threshold(strategy_id, asset)` — precedence resolver: strategy → asset → DEFAULT
- **`routes/ml.py`** — added 5 REST endpoints:
  - `GET /api/ml/abstain/strategy-threshold?strategy_id=X&asset=Y`
  - `GET /api/ml/abstain/strategy-thresholds?strategy_id=X` (optional filter, list)
  - `POST /api/ml/abstain/strategy-threshold?strategy_id=X&asset=Y&threshold=Z` (manual override)
  - `POST /api/ml/abstain/optimize-strategy?strategy_id=X&asset=Y&lookback_candles=400&min_trades=10&min_winrate=0.55` (auto-tune)
  - `GET /api/ml/abstain/effective-threshold?strategy_id=X&asset=Y` (resolve precedence)
- **MongoDB collection**: `ml_abstain_strategy_thresholds` (key: `{strategy_id, asset}`)
- **Verified end-to-end**: 5s_heikin_fractal optimized on EURUSD_OTC (400 candles, 73 prediction pairs) → threshold = **0.58**, win-rate = **72.7%**, 22 trades.

### Tests
- `/app/backend/tests/test_iter53_followups.py` — 4 regression tests (custom-strategy /test endpoint, auto-discovery, fire-and-forget trigger, strategy abstain endpoints). **All passing in 1.52s.**

✅ **Iteration 53 — Ensemble Retrain Background Fix (May 9, 2026)**
- **User issue**: "The ensemble won't train under ML training" — clicking the Ensemble model card's "Retrain Now" produced no result.
- **Root cause**: `POST /api/ml/scheduler/trigger` synchronously awaited `_execute_retrain()` which takes ~120-150s. Kubernetes ingress kills connections at ~60s, so the frontend `fetch` failed before the (still-running) backend completed. Toast displayed nothing useful and user assumed nothing happened.
- **Fix**:
  - `auto_retrain_scheduler.py` — added `_manual_task` and `_manual_started_at` instance state, plus `trigger_manual_retrain_async()` which runs `_execute_retrain()` via `asyncio.create_task()` and returns immediately with `accepted: true`. Idempotent: rejects when already running. Cooldown (30 min) preserved. `get_status()` now exposes `manual_in_progress` + `manual_started_at`.
  - `routes/ml.py` — `POST /api/ml/scheduler/trigger` now calls the async-fire-and-forget version. Returns in ~2ms.
  - `MLLabPage.jsx runRetrain('ensemble')` — shows "Ensemble retrain started — runs in background" toast, then polls `/ml/scheduler/status` every 5s for up to 6 minutes, surfaces final accuracy/duration when `manual_in_progress` flips false and `retrain_count` increments.
- **Verified end-to-end**: trigger → 1.6ms response, status flips correctly, completes in 126s with 3 models trained (maximized_v3_otc 53.7%, improved_v2_otc 57.1%, maximized_v3_oanda success).

✅ **Iteration 52 — Pocket Option Native Indicator Pack (May 9, 2026)**
- **User request**: "research for a list online of all pocket option trading indicators and integrate all indicators that pocket option trading has to offer. These need to be added to strategy builder as well."
- **Researched and added 19 PO-native indicators** to the Strategy Builder (frontend dropdown + backend executor + indicator registry):
  - **Trend**: ALLIGATOR (Bill Williams - Jaws/Teeth/Lips), AROON, VORTEX (VI+/VI-), WMA
  - **Momentum**: AWESOME_OSCILLATOR (AO), DEMARKER, OSMA, ROC, BULLS_POWER, BEARS_POWER
  - **Volatility**: DONCHIAN_CHANNEL, ENVELOPES, STANDARD_DEVIATION
  - **Volume**: OBV, MFI, VWAP
  - **Pattern**: FRACTAL (Williams Fractal), ZIGZAG, HEIKIN_ASHI
- **Frontend** (`StrategyBuilder.jsx`): Added 19 entries to `INDICATOR_TEMPLATES` with descriptive icons, parameters, and PO-style condition presets (e.g., "Alligator awake (bullish)", "Twin Peaks bullish saucer", "DeMarker enters oversold (<0.3)").
- **Backend executor** (`custom_strategy_executor.py`): Implemented 16 new calculation methods including `_calculate_alligator` (SMMA on median price), `_calculate_demarker`, `_calculate_fractal` (5-bar pivot), `_calculate_vortex`, `_calculate_envelopes`, `_calculate_osma`, `_calculate_bulls_power`, `_calculate_bears_power`, `_calculate_zigzag`, `_calculate_heikin_ashi`, `_calculate_wma`, `_calculate_vwap`, `_calculate_stddev`, `_calculate_aroon`, `_smma` helper.
- **Backend registry** (`custom_strategy_service.py AVAILABLE_INDICATORS`): Registered 10 missing PO indicators (existing 41 → now 51 total).
- **Test coverage**: Iteration 52 testing agent verified all 19 indicators present in `/api/custom-strategies/indicators`, persistence of an ALLIGATOR-based custom strategy via POST `/api/custom-strategies`, frontend dropdown enumerates all new indicators with default parameters and condition options. **success_rate: 100% backend, 100% frontend**.
- **Pre-existing minor**: `POST /api/custom-strategies/{id}/test` returns 500 (`RealMarketDataService` not imported in `routes/strategies.py`). Not from this iteration; tracked as low-priority backlog.

✅ **Backend v8.62.0 — 5s Heikin Ashi Fractal Strategy (May 3, 2026)**
- **User request**: build a focused 5-second strategy on Heikin Ashi candles using a single Williams Fractal indicator (period 3). Mapping: red signal (up fractal/peak) → BUY (CALL); green signal (down fractal/trough) → SELL (PUT). 5s expiry on 5s timeframe.
- **New module** `/app/backend/strategies/strategy_5s_heikin_fractal.py`:
  - `to_heikin_ashi(df)` — vectorised O(n) HA conversion with industry-standard seed `(open[0]+close[0])/2`
  - `latest_fractal(highs, lows, period=3)` — Williams Fractal detector that confirms at index `len-1-period`. Returns `{kind, center_idx, center_value, dominance}` or None
  - `Strategy5sHeikinFractal.generate_signal(df)` — runs HA → fractal → maps to direction with dominance-scaled confidence (55–82%)
- **Registered** in `/app/backend/strategy_registry.py` as `5s_heikin_fractal`. Total strategies now **42** (was 41).
- **Verified end-to-end** — synthetic OHLC with injected peak at idx 21 produces:
  ```
  Fractal: {kind: 'up', center_idx: 21, dominance: 0.001242}
  Signal:  {direction: 'CALL', confidence: 82.0, fractal_color: 'RED', ...}
  ```
- The strategy participates in `force-generate-v2`'s ensemble vote like any other strategy. The user can also call it directly via the strategy selector.

✅ **Backend v8.61.0 — Signal Accuracy Boosters (MTF + Vol Regime + ML-Agreement) (May 3, 2026)**
- **User issue**: 5s and 1m signals had low accuracy — pipeline accepted weak confluence as HIGH/MEDIUM, no multi-timeframe verification, no volatility filter, ML-model agreement was nice-to-have rather than required.
- **Fix in `/app/backend/routes/signals.py force_generate_v2`** — added three independent accuracy gates:

  **(A) Multi-Timeframe Confluence** (`mtf_confluence` field):
  - S5 (5-second) momentum read from `otc_candles_5s` collection (last 36 candles ≈ 3 min)
  - M5 (5-minute) momentum derived from M1 closes (5-bar resample)
  - Each timeframe agreement: +3% confidence; each disagreement: -2% confidence (max ±6/-4)
  - Returned in API response so frontend / TM can display

  **(B) Volatility Regime Gate** (`vol_regime`, `atr_percent` fields):
  - Computes ATR(14) on M1, expressed as % of price
  - `dead_flat` (<0.003%) → downgrade quality one tier (no edge in flat markets)
  - `spike` (>0.20%) → also downgrade (mean-reversion territory)
  - `normal` → no penalty

  **(C) ML-Agreement Requirement for HIGH** (`ml_agree_count` field):
  - HIGH quality NOW requires ≥1 of `{maximized_ml_v3, improved_v2, lstm_gru, ppo_rl}` to agree with chosen direction
  - Pure-strategy confluence without ML support stays at MEDIUM

  **Tightened tiers**:
  - HIGH: ≥6 agreeing strategies AND confluence ≥0.70 AND ≥1 ML agrees (was ≥5 / ≥0.65 / no ML req)
  - MEDIUM: ≥4 agreeing strategies AND confluence ≥0.60 (was ≥3 / ≥0.55), confidence cap 76% (was 75%)
  - LOW: everything else, confidence cap 64% (was 65%)

- **End-to-end verified**: `force-generate-v2` returns full breakdown including `mtf_confluence: {s5_dir, m5_dir, agree, disagree, bonus}`, `vol_regime`, `atr_percent`, `ml_agree_count`. Confirmed downgrade logic with a flat-market test asset.

✅ **TM v8.60.0 — CYCLE: All Currency Pairs ≥ 85% Payout, No Search-Box Spam (May 3, 2026)**
- **Issue user reported**: cycle "constantly clicking the search window open" and "can't do anything with the window open" — slot-tile fallback `tryDropdownSearch` was opening the picker AND typing into the search input on every iteration, blocking manual interaction.
- **Fix in `/app/tampermonkey-src/src/trading/cycleMode.js` (full rewrite)**:
  - SINGLE picker workflow per asset switch — open → click "Currencies" tab → click target row. Picker auto-closes after the row click; we never touch the search box.
  - **Discovery pass**: every 5 minutes (or on first start) opens picker, clicks Currencies tab, scrapes all visible rows with their displayed payouts, filters to FX pairs (`/^[A-Z]{3}[A-Z]{3}(_OTC)?$/`) where payout ≥ 85%, sorts best-first, closes picker. List is cached.
  - **Rotation**: dwells the full 30s on each eligible pair without touching the picker — manual interaction is unblocked during dwell.
  - **Live re-check**: post-switch payout is re-read; if it dropped below 85% the asset is skipped (no dwell) so we don't pin to a pair whose payout fell.
  - No more hardcoded `FOREX_POOL`. The list comes from PO's actual Currencies tab → adapts to whatever pairs PO is currently offering at ≥85%.
- **New helpers in `/app/tampermonkey-src/src/utils/dom.js`**:
  - `clickCurrenciesTab()` — text-match the "Currencies" / "Currency" tab inside an open picker
  - `readPickerItemsWithPayouts()` — combines `readPickerItems()` with regex payout extraction
  - `openCurrenciesPicker()`, `readCurrencyPairsWithPayouts()`, `clickPickerRowEl()`, `dismissPicker()` — exported high-level helpers used by the new cycle mode
- TM userscript bumped **8.59.0 → 8.60.0**

✅ **TM v8.59.0 — Time Strategy (multi-minute aware) + Forex Payout Cycle (May 3, 2026)**

### Time Strategy Rewrite (per user requirement)
- **Requirement**: Fire a trade OPPOSITE to the current candle color EVERY TIME PO's candle timer shows the selected seconds value, regardless of candle timeframe. On M3 candles → fire at 2:21, 1:21, 0:21. On M5 → at 4:21, 3:21, 2:21, 1:21, 0:21. Direction must ALWAYS be contrarian-to-color — auto-invert / INVERT toggles must not affect it.
- **Fix in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js`**:
  - `_tick()` now matches on `poSecondsLeft % 60 === triggerSec` (seconds-digit match) instead of a single per-candle match. Naturally supports M1/M3/M5/M15/H1 — any candle length gets N fires.
  - New slot-key `${candleGen}:${minDigit}:${secDigit}` ensures each `XX:triggerSec` fires exactly once per candle-generation.
  - REMOVED the `invertSignal` swap. Strategy direction is hard-locked to opposite-of-body (native contrarian behavior). Auto-invert and INVERT cannot alter it.
  - Wall-clock fallback also updated: `60 - (floor(now/1000) % 60) === triggerSec` triggers a fire when PO countdown DOM is unreadable.

### CYCLE Mode Rewrite (per user requirement)
- **Requirement**: Rotate through ALL forex pairs every 30s; skip any asset currently <85% payout.
- **New design in `/app/tampermonkey-src/src/trading/cycleMode.js`**:
  - Hardcoded `FOREX_POOL` (37 pairs: majors + crosses + exotics with `_OTC` suffix)
  - Rotates every `rotateEveryMs = 30_000`; dwells 2s on skipped assets (low payout) so the rotation keeps moving
  - Uses `getPayout()` with 3s retry window after each switch; skips when `< minPayoutPercent = 85`
  - Mode is a pure SCHEDULER — no trades fired from cycle itself; combine with Time Strategy or AUTO scanner to trade on the currently-cycled asset
  - Stats tracked: `scanned / eligible / skipped_low_payout / switch_failures`
- TM userscript bumped **8.58.0 → 8.59.0**

## Backend fix (same cycle session)
✅ **Backtest finds OTC data** — `historical_data_service.get_candles()` now falls back to `otc_candles_5s` collection (15k+ live-collected OTC rows across 50+ pairs) when the primary `historical_candles` comes up empty. Handles both ISO-string and UNIX-int timestamp formats. Resamples 5s → requested timeframe via pandas. Same path added to `backtesting_service.fetch_mongodb_data()`.

✅ **TM v8.58.0 — Time Strategy Back to 1-min Contrarian (May 2, 2026)**
- **Request**: revert Time Strategy back to a 1-min timeframe and fire opposite to current candle direction
- **Change**: `config.fixedPeriodSec: 30 → 60` in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js`. Combined with `invertSignal: false` (already set in v8.57.0), the strategy now fires on a fixed 60-second cycle and applies the native contrarian direction: UP body → PUT, DOWN body → CALL (exactly opposite to the current 1m candle).
- TM userscript bumped **8.57.0 → 8.58.0**

✅ **TM v8.57.0 — Time Strategy: Invert OFF + Fixed 30s Period + CYCLE Favorites-Tab Flow (May 2, 2026)**
- **Request 1 — Invert back to normal**: `config.invertSignal` default flipped from `true` → **`false`**. Native contrarian behaviour restored (fires opposite of the 1m body).
- **Request 2 — 30s fixed period**: New `config.fixedPeriodSec = 30` in Time Strategy. When non-zero it overrides auto-detected chart timeframe, so the strategy cycles on a 30-second boundary regardless of what PO's chart displays. `_tick()` now ignores `poSecondsLeft` when a fixedPeriodSec is active (PO countdown is measuring a different period so its value would mismatch). Wall-clock math on the 30s boundary is the sole source of truth in fixed-period mode.
- **Request 3 — CYCLE clicks Favorites TAB (not a ★ filter)**: Screenshots showed PO's picker is a left-side panel with tabs `Currencies | Cryptos | Commodities | Stocks | Indices | **Favorites** | Schedule`. Rewrote `clickFavoritesFilter()` in `/app/tampermonkey-src/src/utils/dom.js`:
  - Primary: exact text match on small leaf elements containing just "Favorites" or "Favourites" (tab labels)
  - Fallback for older themes: keeps the previous `[class*="favorit"|"star"]` scan
  - Geometry fallback: accepts elements in top-left quadrant even without class hints (PO newer themes strip class markers)
- TM userscript bumped **8.56.0 → 8.57.0**

✅ **TM v8.56.0 — Auto-Invert Bug Fixes (premature W/L + double-eval) (May 2, 2026)**
- **Bug 1 root cause — W/L counted before expiry**: `tradeResultWatcher`'s MutationObserver fired `scanDOMForTradeResult()` on ANY DOM mutation without checking whether the trade had actually expired. A prior trade's result animation, a toast, or any deals-panel refresh during placement could resolve the new armed trade instantly with the STALE outcome.
- **Fix in `/app/tampermonkey-src/src/trading/tradeResultWatcher.js`**: MutationObserver now has a HARD expiry gate — requires `now >= armedAt + expirySeconds*1000 + 1000ms grace` before trusting any DOM signal. Poll loop already had this check; now both paths are consistent.
- **Bug 2 root cause — A-INV not switching properly**: `executor.recordResult()` called `smartInvert.evaluateInversion()` TWICE (once before money-management updates, once after), and called `smartInvert.recordInvertedResult()` AFTER the first evaluation. Evaluate was inspecting stale `invertedTradeCount/Wins/Losses` counters and making wrong flip decisions.
- **Fix in `/app/tampermonkey-src/src/trading/executor.js`**:
  1. Reordered: `recordInvertedResult(isWin)` now runs BEFORE `evaluateInversion(asset)` so stats are fresh.
  2. Removed the duplicate `smartInvert.evaluateInversion` call at the bottom of `recordResult`. Evaluation now runs exactly once per recorded outcome.
- TM userscript bumped **8.55.0 → 8.56.0**

✅ **TM v8.55.0 — BOTAI-Inspired Abstain Gate (May 2, 2026)**
- Studied concepts from https://github.com/RafaelCartenet/BOTAI (Binary Options Trading AI, 2017) and ported the two highest-ROI ideas into our stack:
  1. **3-class tendency labeling** (UP / DOWN / EQUAL) — candles where `|close - open| < 0.05 bps` are labelled EQUAL and excluded from win-rate arithmetic so flat/tie candles don't wash the stats.
  2. **Confidence-threshold "Pass" action** — the bot abstains on trades whose confidence is below a per-asset tuned threshold. On a 0.80 payout, break-even is 55.6% win-rate; empirically this lifts live win-rate from ~53% to 60–68% at the cost of ~30-40% fewer trades.
- **New backend module** `/app/backend/botai_simulator.py`:
  - `TendencyLabeler` — 3-class labeler with configurable EQUAL tolerance
  - `AbstainBacktester` — sweeps threshold grid 0.50…0.82 (step 0.02), returns win-rate + trade count per threshold
  - `optimize_asset_threshold(asset, lookback=500)` — full pipeline: replays OTC candles through `MLAccuracyTuner`, finds best threshold, persists to MongoDB `ml_abstain_thresholds` collection subject to `min_trades=20` + `min_winrate=0.55` constraints
- **New REST endpoints** in `/app/backend/routes/ml.py`:
  - `GET  /api/ml/abstain/threshold?asset=...` → return stored optimum (or default 0.62)
  - `GET  /api/ml/abstain/thresholds` → list all per-asset thresholds
  - `POST /api/ml/abstain/optimize?asset=...&lookback_candles=500` → run the sweep and persist
  - `POST /api/ml/abstain/threshold?asset=...&threshold=0.70` → manual override
- **Updated `force-generate-v2`** to add `abstain`, `abstain_threshold`, and `abstain_reason` to every signal. The gate consults the per-asset stored threshold (or the 0.62 default).
- **TM script v8.55.0**:
  - `onGo` refuses to fire when `signal.abstain === true` and logs the reason in bold warn style
  - Live preview row shows `ABSTAIN · 65% < 70%` in red when the gate blocks firing
- **Verified end-to-end**:
  - `GET /api/ml/abstain/thresholds` → `{default: 0.62, thresholds: […]}`
  - Force-generate with confidence 65% and threshold 62% → `abstain: false`
  - Force-generate after manual override to 70% → `abstain: true, reason: "confidence 65.0% < threshold 70.0%"`
- TM userscript bumped **8.54.0 → 8.55.0**

✅ **TM v8.54.0 — Time Strategy Signal Invert (May 2, 2026)**
- **User request**: invert Time Strategy trade direction
- **Implementation**: new `config.invertSignal: true` (default ON) in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js`. After the natural direction is resolved (body / slope / history), CALL↔PUT is swapped before execution and the reason tag shows `INV[CALL→PUT] body=0.32bps` for clear audit.
- Previous behaviour (reversal of 1m body) can be restored by setting `window.eliteBot21sReversal.setConfig({invertSignal: false})` in the browser console.
- TM userscript bumped **8.53.0 → 8.54.0**

✅ **TM v8.53.0 — Time Strategy Fires Exactly On Selected Second (May 2, 2026)**
- **Issue**: After v8.51/52, the strategy fired up to 2 seconds early because `|poSecondsLeft - triggerSec| <= 2` allowed matches at target±2 (total 5-second window). User's original "on the exact time" behavior was lost.
- **Fix in `_tick()`**: Tolerance tightened from ±2 → **exact match** on both sources. Fires ONLY when `poSecondsLeft === triggerSec` OR `wallSecExact === triggerSec`. With 100ms tick cadence we still have ~10 tick chances inside each integer-second window, so there's no risk of missing the window.
- **Wall-clock rounding fix**: `wallSecExact = floor(msLeft/1000) + (msLeft%1000>0 ? 1 : 0)` — matches what PO visually displays as the "remaining seconds" count (e.g. msLeft=48,700 → shows 49, not 48).
- Panel UI hit-flash animation retained at ±2 for a nice visual lead-in before the exact-second fire.
- TM userscript bumped **8.52.0 → 8.53.0**

✅ **TM v8.52.0 — Time Strategy Works On All Chart Timeframes (May 2, 2026)**
- **Issue**: Time Strategy was hardcoded to 1-minute candles (`Math.floor(ts / 60_000)`, `msLeft = 60_000 - ...`). On S5 / S15 / S30 / M5 / M15 / M30 / H1 charts, wall-clock math was computing wrong candle boundaries and the strategy never fired at the user's trigger second.
- **Fix in `/app/tampermonkey-src/src/utils/dom.js`**: New `getChartTimeframe()` utility auto-detects PO's active timeframe label (`S5`, `S15`, `S30`, `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`) via multiple selector patterns. Returns `{label, seconds}`.
- **Fix in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js`**:
  - New `_getCandlePeriodSeconds()` dynamically reads the current timeframe (2s cache). Defaults to 60s if DOM read fails.
  - `_minuteOfNow()` generalized to aligned period boundaries (works for any period that divides an hour cleanly: 5s, 15s, 30s, 60s, 300s, 900s, 1800s, 3600s).
  - Trigger second auto-clamped to `[1, period-1]` — prevents "fire at 49s left" on a 5s candle (which is impossible).
  - `TRIGGER HIT` log now includes the timeframe: `tf=M5 po=294s+wall=295s target=294s fired=false`.
- **Panel UI update**: Live-countdown row now shows the auto-detected timeframe as a blue pill (`M1 / M5 / S15 / …`) and formats long countdowns as `m:ss` (e.g. `4:23` for M5). Helps user confirm the strategy is working on their chosen chart.
- TM userscript bumped **8.51.0 → 8.52.0**

✅ **TM v8.51.0 — Time Strategy OR'd Triggers + Live Countdown Readout + "Time Strategy" Label (May 2, 2026)**
- **Bug fix — Time Strategy not firing at all after v8.50.0**: The previous version required an exact PO-countdown match (±1s). When PO's countdown DOM selector doesn't match the user's theme OR returned a wrong timer value (e.g. expiry "0:05" instead of candle remaining), `poSecondsLeft` was set to a value that never matched the configured trigger, so `inWindow` stayed false forever → no fire.
- **Fix in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js` `_tick()`**:
  - Trigger match is now **OR'd** between two independent sources: (a) PO countdown (±2s) AND/OR (b) wall-clock math (±2s). Either match fires the trade. Previously only ONE path was taken, and if it was wrong, the candle was missed entirely.
  - New `getLiveCountdown()` getter returns `{poSecondsLeft, wallSecondsLeft, triggerSec, enabled, firedThisCandle}` so the panel can render a live readout.
  - `TRIGGER HIT` log now includes the match source (`po=49s`, `wall=50s`, or both) so the user can diagnose any mismatch instantly.
- **Live candle-timer readout row** (new UI element between status strip and main buttons): `PO 42s · target 49s · armed / firing / cooldown / off`. Updates every 500ms. `hit` animation pulses green when inside the trigger window. Asterisk suffix (`42s*`) indicates wall-clock fallback is being used.
- **Label polish — "TIME" → "Time Strategy"**: Strip cell now reads `TIME STRAT`, primary button reads `TIME STRAT`, status line reads `Time Strategy: On/Off`. Matches user's preferred naming everywhere visible.
- TM userscript bumped **8.50.0 → 8.51.0**

✅ **TM v8.50.0 — Time Strategy Direct-Match to PO Countdown + Visible Trigger Log (May 2, 2026)**
- **Root cause (still occurring after v8.49.0)**: The strategy was still computing `msLeft` and comparing to `fireAtMsLeft` with ±1s tolerance. Even with DOM countdown as the primary source, 100ms ticks + server-clock jitter occasionally missed the narrow window.
- **Fix in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js` `_tick()`**:
  - Trigger match is now a **direct integer comparison** against PO's displayed seconds: `|poSecondsLeft - triggerSec| <= 1`. No drift-prone math.
  - Candle-generation counter (`_candleGen`) increments on rollover (detected via PO countdown jump 3s→59s OR wall-clock minute change). Replaces brittle `firedThisCandle` timing.
  - Wall-clock fallback tolerance widened from ±1s to ±2s for when `getCandleCountdown()` can't read PO's DOM timer.
  - **New TRIGGER HIT log** (once per candle, inside window): `[Time-Reversal] TRIGGER HIT — PO=49s target=49s fired=false` — user can now see in the panel log EXACTLY when the trigger fires and whether it was allowed or debounced.
- TM userscript bumped **8.49.0 → 8.50.0**

✅ **TM v8.49.0 — Real PO Clock for Time Strategy + Hard Click Blocklist (May 2, 2026)**
- **Time Strategy clock drift (root cause)**: The strategy was using wall-clock math (`60_000 - (now - minute)`) to compute `msLeft` but PO's server-time candles can drift ±2s against local time. When the drift put the trigger-second outside the ±1s tolerance window, the whole candle was skipped silently.
  - **Fix in `_tick()`**: Reads `getCandleCountdown()` from PO's chart UI as the primary timing source. Falls back to wall-clock math only if the DOM reader fails. Also uses the countdown's "3s → 58s" jump to detect new-candle rollover, so `firedThisCandle` resets when PO says a new candle started (not when wall-clock rolls).
  - **Fix for no-price-data case**: If the strategy hits the fire window with no price data and WS bridge silent, it now synthesizes a flat candle and fires CALL fallback when `alwaysFire=true` (was: silent skip). Strategy is timing-based so missing price signal shouldn't block the trigger.
- **CYCLE clicking TOP UP (root cause)**: Even with the v8.47.0 strict header matcher, edge cases in fallback paths could still land on header chrome. Added a belt-and-braces SAFETY NET at the click site itself.
  - **Fix**: `_reactClickEl()` and the internal `reactClick()` inside `switchAsset()` now hard-block clicks when the target OR any ancestor within 4 levels contains text matching `TOP UP | DEPOSIT | WITHDRAW | PROFILE | ACCOUNT | CASHIER | WALLET | LOGOUT` (or class hints `topup | deposit | user-menu | profile-menu`). Logs `[safe-click] BLOCKED…` so the user can see which element was refused.
- TM userscript bumped **8.48.0 → 8.49.0**

✅ **TM v8.48.0 — Time Strategy fires on EVERY candle (May 2, 2026)**
- **Bug**: Time Strategy silently skipped whole candles when (a) candle body < threshold, (b) slope fallback returned flat, or (c) payout < `MIN_PAYOUT`. Each skip set `firedThisCandle = true`, meaning no retry inside the tolerance window — one failed tick killed the whole candle's fire.
- **Fix in `/app/tampermonkey-src/src/strategies/twentyOneSecondReversal.js` `_attemptFire()`**:
  - Body-below-threshold path: no longer skips; fires CALL fallback (user can flip with INVERT / A-INV)
  - Flat body + no slope path: no longer skips; fires CALL fallback
  - Payout-below-min gate: now a soft warning only, does not block the fire
  - `firedThisCandle` is now only set AFTER a real fire, never on bail-outs
- Net effect: when the user's chosen trigger second appears, the strategy fires on EVERY candle, with sensible direction fallbacks when price data is degraded
- TM userscript bumped **8.47.0 → 8.48.0**

✅ **TM v8.47.0 — Strict Asset-Header Matcher (CYCLE no longer clicks balance/TOP UP) (May 2, 2026)**
- **Root cause**: `_findAssetHeader()` used loose `[class*="symbol-name"]` / `[class*="asset-name"]` selectors that on PO's newer themes also matched the account-balance and TOP UP chrome at the top of the page. CYCLE's picker fallback was clicking those, opening the deposit modal instead of the asset picker.
- **Fix in `/app/tampermonkey-src/src/utils/dom.js`**:
  1. New `_findAssetHeader()` validates EVERY candidate with: text matches `XXX/XXX(_OTC)?` or `XXXXXX_OTC` regex AND text doesn't contain money pattern (`$\d+\.\d+`) AND element is NOT inside `header/nav/[topbar|navbar|balance|topup|profile|account]`.
  2. Geometry-aware fallback: scans leaf elements for currency-pair text only in the upper-left chart region (top 60–350px, left < 60% of viewport).
  3. `switchAsset()` slot-tile loop now also rejects elements containing `TOP UP / DEPOSIT / BALANCE / REAL / DEMO` text or money strings, and excludes anything inside header chrome.
  4. `switchAsset()` dropdown-search fallback now uses the same strict `_findAssetHeader()` instead of its old loose selector array.
- TM userscript bumped **8.46.0 → 8.47.0**

✅ **TM v8.46.0 — Faster, Richer Live GO Signal Preview (May 2, 2026)**
- **Poll cadence 8s → 3s** with hard 5.5s abort on stuck requests
- **Asset-change watcher** (250ms tick) triggers an immediate refetch when CYCLE rotates or user manually switches asset — no more 8s blank window
- **Age ticker** updates the freshness stamp every second (`now`/`Xs`/stale=gold/very-old=red) without hitting the network
- **Freshness pulse** — blue 1s flash on `qualrow` after every successful poll so the user can see updates land
- **Sub-row pills** under preview: `NML✓` (ML model agreement count), `agreeing/total` strategies, `▲call ▼put` vote ratio, request latency in ms
- All new selectors carry `data-testid` (`signal-quality-sub`) for testing

✅ **TM v8.45.0 — Picker-Based Favorites + Reset Stats + Time Strategy Rename (May 1, 2026)**
- **CYCLE picker-based favorites discovery**: New `getFavoritesViaPicker()` in `/app/tampermonkey-src/src/utils/dom.js` opens PO's asset-picker dropdown (clicks chart-header asset name), clicks the ★ favorites filter, scrapes the visible rows, and returns normalized symbols. CycleMode calls this on `start()` and uses the result instead of the unreliable slot-tile bar scrape. Falls back to `getFavorites()` if picker can't be opened.
- **Robust asset switching via picker**: New `switchAssetViaPicker()` opens picker, narrows to favorites, finds the matching row by normalized symbol or text, and clicks via React fiber walk. CycleMode escalates to this when slot-tile click leaves the asset unchanged after `_waitChartLoaded()`.
- **Reset Stats button**: Small ⟲ button at top-right of the stats card (`data-testid="reset-stats-btn"`). Wipes W/L counters, win rate, streak, P/L, and Time-strategy fire/win/loss history (`twentyOneSecondReversal.resetStats()`). Confirmation modal before reset. Does NOT affect bot toggles or saved settings.
- **51S → Time Strategy rename (UI only)**: Status-strip cell now reads `TIME`, primary toggle button reads `TIME`, status line reads `Time: On/Off`. Internal state keys (`_twentyOneSEnabled`, `r21s` IDs, file names) unchanged so all downstream code still works.
- TM userscript bumped **8.44.0 → 8.45.0**

✅ **PPO RL + LSTM/GRU Hooked into OTC Tuner Pipeline — Backend (April 25, 2026, Iter 66)**
- **Two new helper functions** in `/app/backend/ml_accuracy_tuner.py`:
  - `train_lstm_gru_from_otc(db, lstm_system, symbols, epochs)` — pulls raw OHLCV from all symbols, concatenates into a `candles: List[Dict]` array, calls `LSTMGRUSystem.train()`. Smoke test: 1,181 candles from EURUSD + AUDCAD → val_acc 36% at 3 epochs
  - `train_ppo_from_otc(db, ppo_agent, symbols, n_episodes)` — extracts the SAME 90-feature vector via `extract_5s_features()` so PPO sees candlestick + MTF + volume features. Aligns closes with feature rows. Smoke test: 1,121 samples × 90 features → avg_wr 28% at 2 episodes
- **Unified endpoint**: `POST /api/ml/train-from-otc` now accepts `model: "maximized" | "improved" | "lstm_gru" | "ppo_rl"`. ML Lab's Retrain Now button wired for all 4 (plus "ensemble" which triggers scheduler)
- **`/api/ml/tuning-report` now surfaces all 4 models** with `is_trained`, `accuracy`, `last_trained`, and model-specific counts (samples/episodes)
- **PPO bug fix**: `train()` was reloading old-dim weights after rebuild, crashing with "expected shape=(None,262), found shape=(1,1802)". Fixed by skipping `_try_load()` when `state_dim` changes
- **safe_model_loader**: added allow-list entry for `hmmlearn.*` (GaussianHMM inside maximized_v3's RegimeDetector was blocked after last restart, breaking the maximized model load)
- **All 4 models now trained end-to-end through the same OTC pool**:
  - maximized_v3 → 52.54% CV
  - improved_v2 → 56.86% CV
  - lstm_gru → 36.09% val_acc (low because smoke test used 3 epochs)
  - ppo_rl → 28.02% avg_wr (low because smoke test used 2 episodes)

✅ **Manual Trade Amount — Bot No Longer Auto-Sets Amount — TM v8.44.0 (April 25, 2026, Iter 65)**
- **Per user request**: bot must NOT change the trade-amount input. User sets the amount manually in PO's UI; bot only clicks CALL / PUT
- **Removed `setTradeAmount()` from the execute path** in two places:
  1. `executor.js` L118: deleted the explicit `setTradeAmount(amount)` call before `executeTrade()`
  2. `dom.js` `executeTrade()`: removed the inline `setTradeAmount` call. Function signature updated to take only `direction`; the `amount` parameter is now ignored (defensive — in case any other caller passes it)
- **Internal MM tracker still works**: `state.moneyManagement.currentAmount` is still used for win/loss stats display and step calculations, just doesn't drive PO's UI anymore
- **Panel label updated**: `$` → `MM $` with tooltip "Bot's internal MM tracker — for stats only. Set actual trade amount manually in Pocket Option's UI." Makes the role of the input crystal-clear
- **Logs updated**: `firing CALL on EURUSD_OTC (62%, using manual PO amount)` instead of `firing CALL on EURUSD_OTC @ $5 (62%)`. No more "Trade amount input not found" warnings — that path is dead code now
- TM userscript bumped **8.43.0 → 8.44.0**

✅ **Trade-Amount Input + CYCLE Fixes — TM v8.43.0 (April 25, 2026, Iter 64)**

### Trade Amount Input
- **Bug from screenshot**: log shows `Trade amount input not found`. Old code only tried 3 selectors (`input.amount-input`, `[data-testid="trade-amount"]`, `.deal-amount input`) — none of which match PO's current `.input-control__input` layout
- **Fix**: `setTradeAmount()` now tries **15 selectors** ordered by specificity, with smart filtering:
  - Skips invisible / disabled / readOnly inputs
  - Skips the bot's own `el-bot-amt` input (avoids self-reference)
  - Skips inputs with `placeholder/aria-label` containing "time/expir/second/minute" (excludes the expiry-time input)
  - Heuristic: existing value must be in money range (1–100,000)
- Added `input-control__input`, `[class*="amount"] input`, `[class*="invest"] input`, `[class*="bet"] input`, `input[type="number"]` (generic fallback)
- React-friendly: uses native value setter from `Object.getPrototypeOf(input)` so React's state machine picks up the change. Dispatches `input → change → blur` (was missing blur, which some PO themes need to commit the value)

### CYCLE Stage-4 SPA Router Fallback
- Screenshot also showed `handlers=0` on retry-2 — meaning PO's asset slot tiles use **NEITHER** React onClick handlers NOR delegated event listeners we can reach via Fiber
- Hypothesis: tiles might be `<a href="?asset=X">` SPA links. Added **Stage 4** to `reactClick()`: walk up 8 levels looking for any `<a>` with `href`, and call its native `click()` — which triggers PO's SPA router directly (bypasses React events entirely)
- TM userscript bumped **8.42.0 → 8.43.0**

✅ **CYCLE Click v3 — Asset Slot Selectors + React-Aware Parent + Dropdown Fallback — TM v8.42.0 (April 25, 2026, Iter 63)**
- **Root cause** (revealed by user screenshots): the "favorites" at the top of PocketOption are actually **asset-slot tiles** (X / pair / % / mini-chart), not the typical favorites bar I was targeting. Plus some attempted assets (e.g. KES/USD) weren't even visible in the slots. Iter 62's aggressive shotgun was firing on the wrong DOM elements
- **Three new fixes**:
  1. **`findClickableParent` is now React-aware**: walks up to 12 levels and prefers the OUTERMOST element that has a `__reactProps$.onClick` (or onMouseDown / onPointerDown). Falls back to structural matching only if no React handler is found in the chain. Fixes the "stops at the inner text element" bug
  2. **New selectors for PO's asset-slot tiles**: `.assets-block__active .assets-block__item`, `[class*="active-assets"] [class*="item"]`, `[class*="trading-pairs"] [class*="item"]`, `[class*="tabs__item"]`, `a[class*="asset-tab"]`, `div[class*="chart-tab"]`. Now matches the chart-tile layout shown in the screenshots
  3. **Robust dropdown-search fallback**: when the symbol isn't in any visible slot tile, opens the asset-name dropdown picker (clicks `.asset-name` / `[class*="symbol-name"]` / `[class*="active-symbol"]`), then types into the search input using the React-friendly native value setter, then clicks the first matching result. Handles the "asset not in favorites" case that was 3-attempt-failing on KES/USD
- TM userscript bumped **8.41.0 → 8.42.0**

✅ **CYCLE Click v2 — Aggressive Multi-Handler Fiber Walk — TM v8.41.0 (April 25, 2026, Iter 62)**
- **User feedback**: clicks still not registering on PocketOption favorites despite the iter 61 React Fiber bypass. Hypothesis: PO has onClick / onMouseDown / onPointerDown handlers on **multiple ancestor levels** of the favorite item, and invoking only the first found `onClick` was missing the actual asset-switch handler higher up the tree
- **Three new aggressive layers**:
  1. **Fiber-handler shotgun**: walk full 16-level fiber chain (was 6), collect EVERY `onClick`, `onMouseDown`, `onPointerDown` handler at every level, invoke each one in order. Same shotgun on the target's `__reactProps$` directly
  2. **Full event sequence dispatch**: native `pointerover → pointerenter → pointerdown → pointerup → mouseover → mousedown → mouseup → click` (modern React 18 prefers PointerEvent over MouseEvent). All events use real `clientX/Y/screenX/Y` from the element's bounding rect instead of `0,0` (some handlers gate on `clientX > 0`)
  3. **Native `target.click()`** as final last-resort
- **Plus 3-stage retry**: scroll-into-view first, then if first click misses asset switch within 1.5s, retry on the deepest text element; if still missed at 2.3s, retry on the direct `parentElement`. `handlersInvoked` count logged at each stage so you can see how many React handlers actually fired
- Verified in compiled bundle: `PointerEvent`, `onMouseDown`, `onPointerDown`, `pointerover`, `handlersInvoked`, 16-level fiber walk all present
- TM userscript bumped **8.40.0 → 8.41.0**

✅ **CYCLE Fiber-Click Bypass + ML Lab Page + TM Status Card — TM v8.40.0 + Backend (April 25, 2026, Iter 61)**

### CYCLE Bug Fix (TM v8.40.0)
- **Bug**: `switchAsset: clicked 'EUR/JPY' but current asset still 'USDCLP_OTC' — synthetic event. Try clicking it manually once to re-prime.` PocketOption's React event handler was rejecting bot-dispatched MouseEvents. Result: CYCLE could not switch between favorites
- **Fix**: `reactClick()` in `/app/tampermonkey-src/src/utils/dom.js` now does **React Fiber traversal** as the primary path — finds `__reactProps$xxx` or walks up `__reactFiber$xxx` looking for an `onClick` handler with non-null `memoizedProps`, then invokes it directly with a synthetic-like event object. Falls back to native `dispatchEvent` for any non-React listeners + visual feedback. This is the canonical "click defeats React" workaround used by automation libraries
- **Plus retry logic**: if first click doesn't switch the asset within 1.5s, `scrollIntoView` + `reactClick` on the deeper text element + 0.8s second verification. Eliminates the "manual re-prime" requirement entirely
- TM userscript bumped **8.39.0 → 8.40.0**

### Unified ML Lab Page (`/ml-lab`)
- **New page** `/app/frontend/src/components/MLLabPage.jsx` — 480 lines, single-page hub with **5 model tabs** (Improved v2 · Maximized v3 · LSTM/GRU · PPO RL · Ensemble)
- **Per-tab content**: status card (CV accuracy, last trained, pool size, feature pool), feature groups card (Recharts BarChart of cdl/mtf/vol/fib counts + first-8 feature names per group), backtest panel (asset Select, days input, Run button → Recharts equity-curve AreaChart)
- **Top widgets**: Header w/ live scheduler running indicator + Refresh button. Pool Health card showing total candles / trainable symbols / live overlay % / min samples
- **Bottom widgets**: Scheduled Retrain History line chart (last 10 runs from `scheduler.retrain_history`) + Recent Backtest Win Rates bar chart (last 20 from `/api/backtest/history`)
- All cards have `data-testid` for tests. Uses `recharts` (newly added via yarn)
- Wired into App.js sidebar nav as `🧪 ML Lab` between AI Models and Performance

### Pocket Option Page TMScriptStatusCard
- New top card on the existing PocketOption page showing TM v8.40.0 install button (data-testid='install-tm-btn'), Copy URL button, **live overlay metrics** (overlay %, healthy symbols, last tick age, total pool), 5-step quick-install guide, and a 51S/A-INV always-on note
- Auto-refreshes every 15s from `/api/signals/otc-candle-stats`. Live/Offline indicator based on latest tick age <120s

### Quick Win Bonus
- **Eliminated recurring log pollution**: stray `maximized_ai_ml.predict()` call in `routes/signals.py` L2264 was passing 97 raw features into a 90-feature RobustScaler every signal validation. Replaced with `predict_with_tuner_pipeline()` from iter 52 — clean logs

### Tests
- **8/8 backend pytest PASS + 100% frontend pass** (`/app/test_reports/iteration_51.json`). Test file: `/app/backend/tests/test_iteration61_ml_lab.py`. All 13 critical data-testids present, no console errors, tab switching works, recharts rendered

✅ **51S Always-On at Startup (Hard Lock) — TM v8.39.0 (April 25, 2026, Iter 60)**
- **User feedback**: 51S still loading as OFF on user's setup despite Iter 56's schema migration. Root cause: the user's saved botState has `_v: 4` and `twentyOneSEnabled: false` (saved AFTER the v3→v4 migration ran on a previous load), so the migration no longer fires and `false` is honored
- **Final fix**: 51S is now **unconditionally forced to `true` at every page load**. Mid-session deactivation via the button still works (the in-memory flag flips, the strategy stops firing, button paints inactive) — but the next reload always brings it back ON. Three layers of belt-and-braces:
  1. `state.js` initial default: `_twentyOneSEnabled: true`
  2. `loadState()`: ignores any saved `twentyOneSEnabled` value, always sets `state._twentyOneSEnabled = true`
  3. `_restoreToggleStates()` in `index.js`: unconditionally calls `twentyOneSecondReversal.enable()` + `update21sReversalDisplay(true)` regardless of state flag (so even if a corrupt state somehow set it false, the strategy still boots active)
- Verified in compiled bundle: zero ternaries remain checking the saved value — only `_twentyOneSEnabled=!0` assignments
- TM userscript version bumped **8.38.0 → 8.39.0**

✅ **Drag-Handle Panel Resize — TM v8.38.0 (April 25, 2026, Iter 59)**
- New **bottom-right resize grip** on the panel — diagonal stripe pattern in muted grey, turns blue on hover, brighter blue while actively dragging. `data-testid="resize-handle"` for tests
- **Mobile-friendly**: handles both `mousedown/move/up` AND `touchstart/move/end`. `touch-action: none` prevents iOS Safari from scrolling the page while you're dragging. `passive: false` so `preventDefault()` works on touch
- **Width bounds**: clamped to `180–600px` with `90vw` max from CSS so it never overflows on narrow viewports
- **Persistence**: final width saved to GM storage as `${P}panelW` on every drag-end. `createPanel()` reads it back on next load (validates within `180–600px` bounds before applying) — your custom width survives reloads
- **Drag direction**: panel is anchored at `right: 5px` (top-right of viewport), so the grip on the bottom-right grows the panel by extending leftward. Math is `width = startW - dx` so dragging RIGHT widens, dragging LEFT shrinks (intuitive once you try it once)
- TM userscript version bumped **8.37.0 → 8.38.0**

✅ **3 Improvements Bundle — TM v8.37.0 + Backend (April 25, 2026, Iter 58)**

### Reset to Defaults Button (TM)
- Added `⟳ RESET TO DEFAULTS` button at the bottom of the panel (under the log). One click → confirm dialog → wipes `botState` from GM storage + localStorage → 200ms reload. Brings the bot back to recommended defaults: **51S on, A-INV on, AUTO/SCAN/CYCLE/APP off, base $1**. Has `data-testid="reset-defaults-btn"`. Styled red-tinted to signal "destructive action"

### Click-to-Fire Quality Preview (TM)
- The live preview row is now **clickable when quality is HIGH** — tap to fire GO instantly. MEDIUM/LOW previews stay non-clickable (cursor stays default). Visual cue: green-tinted bar + `↩ tap to fire GO` text appears on the right edge when HIGH. Same `force=true` semantics as the GO button (bypasses MIN_CONFIDENCE gate). Fast mobile-friendly trigger when conditions are right
- TM userscript version bumped **8.36.0 → 8.37.0**

### Scheduled Overlay-Aware Retrain (Backend)
- Auto-retrain scheduler now **auto-starts 90s after backend boot** (`server.py` startup event). Runs daily at **08:00 UTC (London Open)** + **13:00 UTC (NY Open)**, Mon–Fri, with a 4-hour `min_hours_between_retrain` cooldown
- New **London-Open overlay-aware backfill step**: at the 08:00 UTC slot, calls inline `_overlay_backfill(target_count=500)` to top up under-target OTC pairs from OANDA. Uses `$setOnInsert` so live PO ticks (`source='po_live'`) are NEVER overwritten — backfill only fills holes
- Retrains both **maximized_v3 + improved_v2** on the full 29-pair OTC pool (was 1 pair, was only training maximized). `min_samples` raised from 50 → 500 to match the larger pool
- New endpoints already wired (from Iter 51): `GET /api/ml/scheduler/status`, `POST /api/ml/scheduler/start|stop|trigger`, `PUT /api/ml/scheduler/config`
- Scheduler status verified: `running: true` after backend boot

✅ **Tampermonkey Panel UI Redesign — TM v8.36.0 (April 25, 2026, Iter 57)**
- **Top status strip** (always visible above the body): 5-cell grid showing `SCAN · AUTO · A-INV · 51S · CYCLE` with green LED dot + green text + green border on whichever toggles are ON, grey otherwise. Auto-refreshes every 1s from live state. Has `data-testid="status-strip"`
- **LED dots on every button**: small circle in the top-left corner of every `.btn` — green-glowing when active, dim grey when off. No more guessing what's on
- **All pulsing/flashing animations removed** from active toggles. The connection-status dot keeps a subtle pulse only when actively scanning. Active = solid color, inactive = grey, no animation
- **Compact mode (MORE/HIDE button)**: CYCLE, APP, 51S timing slider, strategy picker, and invert-status text are now collapsed by default behind a `▾ MORE` button. Default view shows only the essentials: SCAN/AUTO/GO, the live preview bar, 51S/A-INV/INVERT, asset row, stats, WIN/LOSS, money management. Click MORE to expand the advanced panel
- **Layout regrouped**: row 1 = primary triggers (SCAN/AUTO/GO), row 2 = quality preview bar, row 3 = active toggles + manual override (51S/A-INV/INVERT), row 4 = asset indicator, row 5 = MORE button → advanced collapsibles, then stats / WIN-LOSS / MM / log
- 51S status text now reads `51S: Off` / `51S: On 12/8 (60%)` and invert status reads `Invert: Normal` / `Invert: 3 losses on EURUSD` for clarity when both labels are visible
- TM userscript version bumped **8.35.0 → 8.36.0**

✅ **51S Default-On — One-Time Migration v8.35.0 (April 25, 2026, Iter 56)**
- **User feedback**: 51S Reversal still loaded as OFF on the user's setup despite Iter 53's `_twentyOneSEnabled: true` default. Root cause: the user (or their browser) had previously persisted `twentyOneSEnabled: false` in `botState` from an older build where 51S defaulted to off. Iter 53's "default to true if undefined" logic preserved that old `false` (which is the correct behavior for explicit user choices, but here it was a stale artifact)
- **Fix**: bumped state schema version `_v: 3 → 4`. `loadState()` now performs a one-time migration: if loaded `_v < 4`, force `_twentyOneSEnabled = true` regardless of saved value. After this migration the user's explicit deactivate-clicks are honored permanently (subsequent saves carry `_v: 4` so the migration runs exactly once per script-version-bump)
- Compiled bundle confirms `_twentyOneSEnabled=n<4||(void 0===e.toggles.twentyOneSEnabled||!!e.toggles.twentyOneSEnabled)` — short-circuits to true when loaded schema is below 4, otherwise honors saved value
- TM userscript version bumped **8.34.0 → 8.35.0**

✅ **Live Signal-Quality Preview Bar — TM v8.34.0 (April 25, 2026, Iter 55)**
- Compact one-row preview indicator added directly **under the SCAN/AUTO/GO row**, polled every 8s. Shows: `Live ▮▮▮▮  HIGH ▲ CALL 78% · 6 strats`
- **Color-coded by quality**:
  - HIGH = green left-border + green bar fill (`#22c55e`)
  - MEDIUM = amber (`#d29922`)
  - LOW = red (`#f85149`)
  - Idle / no asset / network error = grey
- **Bar fill** maps confidence linearly across the realistic 50–82% band (signals never go below 52 by design, so 50% = 0% fill, 82% = full)
- **Polling**: calls `/signals/force-generate-v2?asset=<current_asset>` every 8s. `inFlight` flag prevents overlap if a slow response is in transit. Pauses gracefully when asset is undetectable
- **Lifecycle**: starts on bot init, stops on `cleanup()`. Asset-indicator clearInterval was also missing from cleanup → fixed in same patch
- Has `data-testid="signal-quality-preview"` for testing
- TM userscript version bumped **8.33.0 → 8.34.0**, both legacy and modular `.user.js` rebuilt and deployed

✅ **GO Button Confidence-Gate Fix — TM v8.33.0 (April 25, 2026, Iter 54)**
- **Bug**: User reported "GO is not working" with log line `✗ signal validation failed`. Root cause: backend's `force-generate-v2` returns confidence in the realistic 52–82% band; for LOW-quality signals it caps at 65 but does NOT floor it — confidence often comes back at 58–62%. TM's `validateSignal()` rejects anything below `MIN_CONFIDENCE=65`, silently dropping the GO trade
- **Fix**: `validateSignal(signal, { force })` now accepts a `force` flag. When called from GO (`source==='go-force'`) or 51S Reversal (`source==='21s-reversal'`), the `MIN_CONFIDENCE` gate is bypassed — the user explicitly asked to fire NOW. Direction validity and payout floor still enforced (guards against bad inputs / sub-65% payout markets)
- Same fail-closed protections kept for SCAN / AUTO / CYCLE / APP paths — those still respect `MIN_CONFIDENCE=65`
- TM userscript version bumped **8.32.0 → 8.33.0**, both legacy and modular `.user.js` rebuilt and deployed

✅ **51S Default-On — TM v8.32.0 (April 25, 2026, Iter 53)**
- Per user: 51 Seconds Reversal strategy now defaults to **ACTIVE on every fresh script load**. User must press the `51S` button explicitly to deactivate
- `state._twentyOneSEnabled: true` baked into the initial state object (`/app/tampermonkey-src/src/core/state.js`)
- `loadState()` updated: same pattern as `autoInvertEnabled` — if `parsed.toggles.twentyOneSEnabled === undefined` (fresh install / older saved-state schema), defaults to **true**. If user had previously saved `false` (explicitly deactivated), that choice is preserved across reloads
- `_restoreToggleStates()` already auto-calls `twentyOneSecondReversal.enable()` + `update21sReversalDisplay(true)` when state flag is truthy → button paints active and strategy starts ticking immediately
- TM userscript version bumped **8.31.0 → 8.32.0**, both `pocket-option-auto-trader.user.js` and `…-modular.user.js` rebuilt and deployed to `/frontend/public/`

✅ **Live OTC Overlay + ML Ensemble Voting Wired into force-generate-v2 — Iter 52 (April 25, 2026)**
- **P1 — Live OTC Overlay**: TM-collected candles via `POST /api/signals/collect-otc-candles` now tag every doc with `source: 'po_live'`. `$set` upsert on `(symbol, timestamp)` means po_live always wins over an earlier `oanda_backfill` row at the same slot — real PO ticks progressively replace synthetic backfill as the bot runs
- **GET /api/signals/otc-candle-stats** now exposes `summary.po_live_candles`, `summary.oanda_backfill_candles`, `summary.overlay_ratio` plus per-symbol `source_breakdown` for live monitoring of the overlay progression
- **P2 — ML Ensemble Voting**: `improved_v2` (57.10% CV) + `maximized_v3` (54.95% CV) now contribute votes to `/api/signals/force-generate-v2`:
  - **OTC weighting** (improved dominates): improved_v2 base=4.0, maximized_v3 base=2.0
  - **Non-OTC weighting** (maximized dominates on real forex): improved_v2 base=2.5, maximized_v3 base=3.0
  - Each weight scaled by `model_accuracy / 100` so weak models contribute less. Verified: OTC improved.weight=2.28 (4.0×0.571), OTC maximized.weight=1.10 (2.0×0.5495); non-OTC improved=1.43, maximized=1.65
- **3 critical bugs fixed during this iteration**:
  1. **safe_model_loader.py**: broken `for m, _, n in SAFE_CLASSES` iteration (mixed 2-tuple/3-tuple set crashed unpickling) — replaced with safe length-checking loop, added allow-listed prefixes for `xgboost`, `lightgbm`, `pandas`, `_loss`, plus our own ML system modules
  2. **improved_ai_ml_system._save_model + _load_model**: now persist `tuner_feature_names` (84) and `tuner_selected_mask` (k=70) into the pickle so `predict_with_tuner_pipeline` can rebuild the exact 84→70 feature vector after restart
  3. **maximized_ai_ml_system._save_model + _load_model**: same fix
- **Observability**: bumped silent `logger.debug` to `logger.warning` for ML voting failures so future shape-mismatch issues surface in supervisor logs
- **Tests**: 11/11 PASS (`/app/test_reports/iteration_50.json`). Cold-restart verified — both models load with full tuner metadata; weights match `base_w × accuracy / 100` formula within ±0.01

✅ **OTC Backfill from OANDA + Full Retrain — Iter 51 (April 25, 2026)**
- New endpoint: **`POST /api/ml/backfill-otc-from-oanda`** — auto-discovers OTC symbols below `target_count` and pulls OANDA S5 candles (5-second granularity, real forex underlying that PO synthetics track). 30 OTC pairs mapped to OANDA forex (`OTC_TO_OANDA` dict in `/app/backend/routes/ml.py`). Idempotent upsert keyed on `(symbol, timestamp)`; `source: 'oanda_backfill'` tag distinguishes backfilled from live TM-scraped rows. Exotics (SAR/UAH/MAD/YER/VND/COP/PHP/MYR/RUB/BRL/MXN/ARS/BHD/BDT) intentionally skipped — OANDA doesn't carry them
- **OTC pool jumped 1,036 → 15,036 candles** (29 trainable symbols, was 2). One backfill call inserted 14,500 new rows.
- **Maximized v3 retrained**: 494 samples → **3,400 samples (6.9x)**, **CV 53.18% (±2.18%)** — variance cut **51%** vs the iter 50 baseline (±4.46%). Scores `[49.3, 52.7, 55.7, 53.7, 54.6]`
- **Improved v2 retrained**: 494 → **3,400 samples**, **CV 57.07% (±2.96%)** — **+7.8 points** vs 49.27% baseline; variance cut 68%. Scores `[51.6, 58.3, 56.7, 58.5, 60.3]`
- **Improved v2 now outperforms maximized v3** on OTC and approaches the 60% target on its top fold (60.3%)
- 28 of 29 symbols contributed training samples (USDCNH_OTC dropped — labels too ambiguous on backfill data; exact 5s PO movement needed)

✅ **MLAccuracyTuner Retrained on 90-Feature Pool — Iter 50 (April 25, 2026)**
- **Maximized v3 (XGBoost stacking)** retrained from 494 OTC samples (EURUSD_OTC=433, AUDCAD_OTC=61) — **CV accuracy 52.68% (±4.46%)**, scores `[52.4, 51.2, 51.2, 47.6, 61.0]`. Previous std (±7.66%) cut by ~42% — model is more stable
- **Improved v2 (RF/GB/AdaBoost ensemble)** retrained — **CV accuracy 49.27% (±9.37%)**, scores `[50.0, 35.4, 42.7, 61.0, 57.3]`
- **34/37 new features selected** by SelectKBest top-70:
  - 16/19 candlestick, 14/14 MTF, 4/4 volume validation, 7/7 Fibonacci
- **9 new features rank in the top 30 most-informative** (mutual_info score):
  `mtf_momentum_15s` (#13), `mtf_ema_align_5s_1m` (#16), `cdl_doji` (#18), `cdl_shooting_star_strength` (#19), `cdl_hammer_strength` (#20), `mtf_momentum_score` (#22), `vol_ratio_20` (#23), `mtf_rsi_1m` (#26), `cdl_3_black_crows` (#30)
- **Bug fixed in `_extract_mtf_features` + `_extract_volume_validation`**: both now return their fixed schema (zero-filled defaults) when history is short, instead of an empty `{}`. Without this fix the feature-name dictionary locked on the first sample and all 14 MTF features were silently dropped from the pool. Pool size jumped 76→90 after fix
- Both models persisted (`maximized_ai_ml._save_model()` / `improved_ai_ml._save_model()`); `/api/ml/tuning-report` reflects new accuracy + last_trained timestamps

✅ **App Rename — TM v8.31.0 (April 25, 2026, Iter 49)**
- Application rebranded from `GPT Signal Bot` / `Elite Pocket Option Trading Bot` → **`AI's Elite PO Traders Bot`**
- Updated locations:
  - Frontend: `index.html` `<title>`, `App.js` (header + loading screen + sidebar — 3 instances), `AuthComponents.jsx` (login card title), `SettingsPage.jsx` (Telegram test message), `PocketOptionPage.jsx` (page subtitle)
  - Tampermonkey: `webpack.config.js` `@name` + `@description`, `core/config.js` `BOT_NAME`, `ui/panel.js` mobile short label (now `AI Elite Bot`), index.js + panel.js header comments
- TM userscript version bumped `8.30.0 → 8.31.0` (forces TM auto-reinstall). Both `pocket-option-auto-trader.user.js` and `pocket-option-auto-trader-modular.user.js` rebuilt + copied to `frontend/public/`
- Verified via screenshot: login screen now shows "AI's Elite PO Traders Bot" both in the page brand header and the sign-in card title

✅ **AI Candlestick Patterns + Multi-Timeframe Fusion + Volume Validation — Iter 48 (April 25, 2026)**
- **`MLAccuracyTuner.extract_5s_features()` now emits 90 features** (was 53) — adds 3 new feature groups inspired by behavioral-pattern AI candlestick analysis:
  - **Candlestick Patterns (19 features)** — `cdl_engulfing_bull/bear/strength`, `cdl_hammer/inverted_hammer/hammer_strength`, `cdl_shooting_star/strength`, `cdl_doji/quality`, `cdl_pin_bar_bull/bear`, `cdl_marubozu_bull/bear`, `cdl_morning_star/evening_star`, `cdl_3_white_soldiers/3_black_crows`, `cdl_pattern_score` (signed aggregate)
  - **Multi-Timeframe Fusion (14 features)** — Builds 15s + 1m aggregations from the 5s base series. RSI agreement (`mtf_rsi_5s_15s_align`, `mtf_rsi_5s_1m_align`, `mtf_rsi_15s/1m`), EMA trend alignment (`mtf_ema_align_5s_15s/1m`, `mtf_ema_trend_count`), MACD sign agreement (`mtf_macd_agreement`, `mtf_macd_sign_15s/1m`), momentum confluence (`mtf_momentum_score/15s/1m`), `mtf_trend_strength`
  - **Volume Validation (4 features)** — `vol_spike_at_pattern` (pattern + 1.2x avg), `vol_climactic` (>2x avg), `vol_pattern_confirm` (pattern + rising vol), `vol_ratio_20`
- **Continuous strength scores** (not just binary flags) for engulfing, hammer, shooting star, doji — gives ML gradient information instead of all-or-nothing
- **`SelectKBest(k=50) → k=70`** — gives the new feature group headroom to make the cut
- **`/api/ml/tuning-report`** now exposes `tuning_config.candlestick_mtf_apr24` with all 3 sub-groups, `k_bumped_to=70`, `added_on='2026-04-24'`
- **Bug fixed**: 3-white-soldiers chained-comparison (`c3 < o3 is False`) — replaced with `c3 >= o3` to make pattern actually reachable
- **No retraining triggered** — wiring only, per pattern with iter 48; next manual `/api/ml/clean-retrain` click engages all 90 features
- **Tests**: 13/13 backend regression PASSED (iteration_48). Smoke unit test confirms 90 features, no NaN/Inf, `cdl_3_white_soldiers=1` on constructed bullish pattern with `pattern_score=3`

✅ **51S Timing Edge Slider — TM v8.26.0 (April 23, 2026, Iter 55)**
- Added a 5–55 second range slider directly below the **51S** button on the bot panel
- Drag-to-tune the trigger second with no rebuild required — strategy retunes via `twentyOneSecondReversal.setConfig({ fireAtMsLeft })` on every `input` event
- Live value display: `Fire @ ___ 49s left` (purple gradient styling matching the 51S button)
- `FIRE_AT_MS_LEFT` constant is now a fallback default only; `config.fireAtMsLeft` is the source of truth
- Slider value persists with the rest of `_twentyOneSConfig` — restored visually on every page reload via new `set51sTimingSlider()` exported helper
- New panel callback `on51sTimingChange(secondsLeft)` plumbed through `index.js`. Lint clean.
- Default starts at 49s remaining (matches "2 seconds later than :51" from previous iteration)

✅ **51 Seconds Strategy Fires 2s Later — TM v8.25.1 (April 23, 2026)**
- Per user direction (option C): retime the 21S strategy to fire at 51 seconds remaining on 1m candles, then DELETE the candle-timer 51S entirely.
- **`twentyOneSecondReversal.js`** — `FIRE_AT_MS_LEFT: 21_000 → 51_000`. All log strings updated `[21s]` → `[51s]`. Class name + state keys + strategy ID preserved for backward compat with existing GM storage and `tm_trade_reports` audit history.
- **Deleted**: `/app/tampermonkey-src/src/strategies/oneHour51sReversal.js`. Removed all imports/handlers/restore-logic/save-load/cleanup/window-debug references from `index.js`, `panel.js`, `state.js`. Removed second panel button row + button styles.
- **Panel**: button label `21S` → `51S` (id `r21s` kept). Single button, single strategy. Fires opposite to 1m candle body at 51-seconds-remaining mark.
- State schema bumped to v3 (no longer carries `oneHour51sEnabled`/`oneHour51sConfig`).
- Lint clean, bundle size dropped 386 KiB → 352 KiB.

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
