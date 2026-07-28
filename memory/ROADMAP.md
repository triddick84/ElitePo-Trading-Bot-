# Roadmap — AI's Elite PO Traders Bot

_Last updated: Iter 80 (Jul 28, 2026)_

## P0 — Delivered
- ✅ Iter 80: TM v8.122.0 backend catch-up (3 missing endpoints, script hosting, regression tests).

## P1 — Rebuild candidates (only if user confirms they still want them)
The handoff described these as "built in lost session, need to rebuild". None
are referenced by the compiled v8.122.0 userscript, so they are optional:

- 🔵 **Emergent Object Storage for admin datasets** → `/api/maximized-ml/train`
  wiring so admin CSV uploads feed the ML trainer directly.
- 🔵 **228-asset catalog** + React `AssetPicker` UI (with per-market
  All / Clear toggles).
- 🔵 **Strategy Publish/Unpublish flow** — Draft → Published states in
  `custom_strategies` so main selection dropdown only shows admin-approved
  strategies.
- 🔵 **AccuracyEngine gating on `/signals/latest`** — auto-refresh weights on
  TM W/L outcomes.
- 🔵 **Compact backend health strip** in TM panel (latency + status).

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
