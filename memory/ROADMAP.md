# Roadmap — AI's Elite PO Traders Bot

_Last updated: Iter 87 (Aug 4, 2026)_

## P0 — Delivered
- ✅ Iter 80: TM v8.122.0 backend catch-up.
- ✅ Iter 81: AccuracyEngine gating on `/signals/latest`.
- ✅ Iter 82: Strategy Publish/Unpublish flow.
- ✅ Iter 83: Reusable `AssetPicker` (366 symbols, Regular/OTC bulk).
- ✅ Iter 84: ML accuracy uplift (dynamic ensemble weighting, regime bias, PPO reward shaping).
- ✅ Iter 85: AI Trading Synthwave theme (React app + TM panel — neon cyan on void navy).
- ✅ Iter 86: Microstructure + Latency + Pair-Confluence gates on `/signals/latest`.
- ✅ Iter 87: Short-TF ML training (5s/10s/15s/30s) + fix lowercase `_otc` failure.
- ✅ Iter 88: Ensemble Model Registration in train-on-price-data (3 models side-by-side).
- ✅ Iter 89: GZip compression + Signal pre-generation buffer + Live Latency Dashboard.
- ✅ Iter 90: Ichimoku Cloud indicator (previously declared but not implemented).

## P1 — Remaining rebuild queue (user-approved order b→a→c→d→e; b + c + d done)
- ⏭️ **Next: a) Backend health strip in TM panel** — still needs your call on a1/a2/a3.
- 🔵 **e) Emergent Object Storage for admin datasets** — needs playbook + admin-only confirm.

## P1.5 — ML accuracy Tier 3 (optional next-level uplift)
- 🔵 Cross-validation calibration (Platt scaling / isotonic) so `confidence` values are actual probabilities.
- 🔵 Kelly-criterion confidence gate — only surface signals where fractional Kelly > 0 after payout.
- 🔵 Transformer time-series model as 4th ensemble member (Temporal Fusion Transformer).
- 🔵 Walk-forward validation on 10k+ candles/asset.

## P2 — Small backlog items
- 🟢 Roll `<AssetPicker>` into other pages that still have their own asset UI:
  Data Collection Dashboard, ML Lab, Pocket Option page (trivial swap now the
  component exists).
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
