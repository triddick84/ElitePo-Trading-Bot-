# Roadmap — AI's Elite PO Traders Bot

_Last updated: Iter 80 (Jul 28, 2026)_

## P0 — Delivered
- ✅ Iter 80: TM v8.122.0 backend catch-up (3 missing endpoints, script hosting, regression tests).
- ✅ Iter 81: AccuracyEngine gating on `/signals/latest` — rolling per-(asset, strategy) win-rate gate, live-tested against real historical data (13 combos gated at default 45% threshold).
- ✅ Iter 82: Strategy Publish/Unpublish flow — custom strategies now selectable per-timeframe via `/api/strategies/select` (React + Tampermonkey), independent `is_active`/`is_published` states, UI badges + toasts.

## P1 — Remaining rebuild queue (user-approved order b→a→c→d→e; b + c done)
- ⏭️ **Next: a) Backend health strip in TM panel** — needs user's answer on a1/a2/a3 (rebuild modular sources vs. patch dist vs. skip).
- 🔵 **d) 228-asset AssetPicker** — needs user's answer on embed location.
- 🔵 **e) Emergent Object Storage for admin datasets** — needs playbook + admin-only confirm.

## P2 — Small backlog items
- 🟢 "Remember this device / stay signed in for 30 days" JWT refresh token.
- 🟢 Backend smoke-test script that curls every route module's key endpoints
  for instant regression checking on deploy.
- 🟢 Rebuild `tampermonkey-src` modular ES6 to match v8.122.0 (currently the
  compiled bundle is authoritative; sources are at 8.75.0). Only needed if
  we want to make further code changes to the TM script.

## Debt / Known issues
- ⚠️ ML heavy imports (xgboost/tensorflow) must remain lazy-loaded inside
  functions. Verified intact after rollback.
- ⚠️ `tampermonkey-src/version.txt` is now 8.122.0 but the on-disk modular
  sources are still 8.75.0 — noted so no one confuses them.
