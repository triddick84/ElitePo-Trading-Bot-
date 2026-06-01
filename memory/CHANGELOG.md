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
