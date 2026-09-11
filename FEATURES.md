# AI's Elite PO Traders Bot — Features & Capabilities

> A production-grade AI-powered binary-options trading platform, purpose-built for **Pocket Option**. Combines a **FastAPI + MongoDB backend**, a **React dashboard**, a **Tampermonkey userscript** that drives the PO web platform, and a **Telegram bot** for hands-free signal routing.

---

## 🚀 High-level Value

| | |
|---|---|
| **Multi-asset auto-scanning** | 20+ OTC pairs scanned in parallel every 5 seconds. Top-5 winners rotate through the TM script so trades spread across assets — never all-in on one. |
| **Ensemble AI signals** | LightGBM booster + 60 per-asset Random-Forest micro-models + Rolling Micro-ML + Kyle-Lambda / Glosten-Milgrom microstructure gates + Ridicolous breakout — all combined with EV math and shadow-mode auditing. |
| **Real-money-aware risk gate** | **RiskGuard** (Capital-Guard-Pro-style) computes the safe next-trade amount, tracks session progress, and *auto-locks* trading when stop-loss / target / max-trades hit. Auto-scan respects this gate — no over-trading. |
| **Bidirectional Telegram** | Receive free-text signals from any Telegram channel/user → parsed and routed to PO. Send auto-scan winners + full command menu (`/status`, `/pause`, `/resume`, `/stake`). Pilot the bot entirely from a phone. |
| **Live-tunable strategy sliders** | Every knob (SMA fast/slow, ATR period, SuperTrend multiplier, MA-crossover types, confidence thresholds) is a slider that hot-reloads without restart. |
| **Fast** | Yfinance TTL cache, DB indexes, TTL caches on hot paths, GZip, backend-driven parallel scans, no-block async everywhere. |

---

## 🧠 The AI / ML Stack

| Layer | Purpose |
|---|---|
| **LightGBM booster (walk-forward CV)** | Global tabular model on engineered candle features (returns, volatility, momentum, range, session/time-of-day). |
| **60 per-asset Random Forests** | One RF per OTC asset trained on that asset's own history — captures per-pair quirks the global booster misses. |
| **Rolling Micro-ML** | 200-bar rolling window RF that retrains itself as new candles land, so it never drifts on regime changes. |
| **Kyle-Lambda / Glosten-Milgrom microstructure models** | Order-flow imbalance & adverse-selection gates. Blocks trades when the market is toxic. |
| **Ridicolous Breakout** | Pine-Script-ported breakout strategy tuned for 30-second binaries. |
| **Ensemble EV Gate** | Combines all of the above via Expected Value math (Kelly-lite): trade only when `EV > 0` after the payout haircut. |
| **Shadow Mode + Confidence Autotuner** | Every backtest logs a "shadow" P&L; the autotuner nightly recalibrates the confidence threshold so shadow-P&L is maximised. |
| **Adaptive Market Regime Detection** | Flags TREND / RANGE / VOLATILE regimes so the ensemble uses the right sub-strategy per regime. |

---

## 🛡️ RiskGuard — Session Discipline

Modelled on capitalguardpro.com. Three pillars:

1. **Minimum next-trade calculator** — `POST /api/riskguard/calculate`. Given `capital`, `payout_pct`, `target_profit`, `stop_loss`, `max_trades`, `trades_taken`, `current_pnl`, returns the safe stake — clamped by MIN_STAKE ($1), 25 % capital ceiling, and remaining-stop-loss budget.
2. **Session tracker** — one active session per user. Every win/loss/draw is recorded. Auto-closes when target / stop-loss / max-trades limits are hit.
3. **Auto-feed** — every TM `POST /api/trades/report` with an outcome streams directly into the active RiskGuard session. No manual "Record Win" taps.
4. **Auto-scan pre-flight gate** — `_route_to_tm` queries the RiskGuard session first. If status is `target_reached / stop_loss_hit / max_trades_reached`, the trade is **not routed** and the reason surfaces in the auto-scan status.

---

## 📞 Telegram Bot

Set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `backend/.env`.

### Commands (chat "/" menu)
| Cmd | Effect |
|---|---|
| `/status` | Current auto-scan state, active target, fallback stake, stats. |
| `/pause` | Stops the auto-scan loop. |
| `/resume` | Restarts the auto-scan loop. |
| `/stake <amt>` | Update fallback stake ($0.10-$10,000). Invalidates the active-target cache so the TM script picks up the new stake on next poll. |
| `/help` | Command crib sheet. |

### Free-text signal parser
Send `EURUSD_OTC CALL 60s` (or `EURUSDOTC PUT 1m`, `BTC/USD BUY 30`, etc.) — parsed and routed to `tampermonkey_settings.active_target`. TM script auto-switches the chart and places the trade on next poll.

---

## 🎛️ Strategy Builder

Custom rules built by combining indicator conditions. Every strategy can be **backtested** and **auto-tuned** for its confidence threshold.

### Indicator library (35+)
Moving averages: **SMA, EMA, WMA, TMA**, **3-MA Crossover** (pick any type per line — EMA+WMA+TMA, EMA+SMA+WMA, etc.) with **Guppy MA presets** (Short 3/8/21, Balanced 5/13/21, Hybrid, Long 30/50/60, Golden Cross 50/100/200). Oscillators: RSI, Stochastic, MACD, Awesome Oscillator, Momentum. Bands: Bollinger, Keltner, Donchian. Trend: SuperTrend, Ichimoku, ADX, Parabolic SAR. Volatility/Regime: ATR, Standard Deviation. Structure: Support/Resistance, Pivot Points, Fractals.

### Backtest Runner
`POST /api/strategies/backtest` → runs the strategy against the asset's historical candles → returns win/loss, WR, cumulative P&L, drawdown, sharpe.

### Confidence-threshold Autotuner
`POST /api/strategies/autotune-confidence` — walks confidence from 0.55 → 0.95 in 0.02 steps, picks the value that maximises shadow-P&L.

---

## ⚙️ Speed / Perf Layer

| | |
|---|---|
| **Yfinance TTL cache** | Cross-strategy 15 s cache on `Ticker.history` — auto-scan bursts (20 assets × 5 s tick) drop from 20× network calls to 1×. Stats at `GET /api/perf/yf-cache`. |
| **Active-target TTL cache** | 500 ms in-process cache on `tampermonkey_settings.active_target` — the TM script polls this every 400 ms so this alone cuts DB round-trips 90 %. |
| **DB indexes** | Compound indexes on `tm_trade_reports (user_id, at)`, `risk_guard_sessions (user_id, closed_at)`, `active_target_queue (id, updated_at)`, etc. |
| **GZip middleware** | Compresses `/api/*` responses over 1 KB. |
| **Parallel scans** | `asyncio.gather` runs 20+ per-asset `generate_signal` calls concurrently; each strategy `to_thread`-offloaded so `yfinance.download` doesn't block the loop. |
| **Warm reload** | Uvicorn `--reload` picks up backend edits without dropping websockets. Frontend hot reload via CRA. |

---

## 🔗 Tampermonkey Userscript

Injected into Pocket Option's web platform. Bundled from `/app/tampermonkey-src/` via **webpack**. Current version: **v8.146.0**.

### What it does on the PO page
- **AI Analysis tab** — live confidence badge, indicator readouts, "why this signal" audit trail.
- **Multi-second SNS timing** — precisely times entry to the second across seconds mode (5s / 10s / 15s / 30s / 60s / 5m).
- **Confidence-tiered stakes** — `stake_tiers` maps confidence bins to stake sizes (e.g. 0.65-0.75 → $1, 0.75-0.85 → $2, 0.85+ → $4). Fallback stake configurable via `/stake` Telegram command.
- **Auto-Invert Logic** — after N consecutive losses in a row, next N trades take the opposite direction. Audit trail visible in the AI tab.
- **App signal poller** — polls `/api/tampermonkey/active-target` every 400 ms; auto-switches chart to the winning asset and places the trade.
- **Active-target queue cycling** — cycles through the top-5 winners so trades spread across assets.
- **Live trade reporting** — every fill posts to `/api/trades/report`; every outcome to `/api/trades/outcome`. These feed both `tm_trade_reports` and RiskGuard.

---

## 🖥️ React Dashboard Pages

| Page | Purpose |
|---|---|
| **Dashboard** | High-level KPIs, top signals, recent trades, live P&L. |
| **Telegram Bot** | Live bot status, chat log, quick send. |
| **Pocket Option** | SSID health, connect/disconnect, TM bridge status, live prices, balance. |
| **Mobile Auto-Trade** | Phone-friendly controls: start/stop auto-scan, tap stake tier, one-thumb everything. |
| **RiskGuard** ⭐ | Big minimum-next-trade card, session progress tiles, Record Win/Loss/Draw, config form, history table. |
| **Microstructure** | Kyle-Lambda + Glosten-Milgrom outputs per asset, ensemble gate toggles. |
| **Elite Screener** | Rank every OTC pair by Elite Score, one-click "Send to TM". |
| **Integrations** | Connect Alpha Vantage, Discord, Slack, Twilio, etc. |
| **Signal Routing** | Configure how signals are dispatched (TM script, Telegram, email). |
| **TMA KYC Admin** | Approve user KYC submissions (admin only). |
| **Strategies** | Strategy Builder, backtest runner, autotuner. |
| **AI Models** | Train/re-train per-asset models, AUC audit. |
| **ML Lab** | Feature-importance charts, calibration plots, walk-forward CV panel. |
| **Latency** | Round-trip ping graphs to PO. |
| **User Approvals** | Admin queue for new user signups. |
| **Performance** | Win rate, P&L curves, Sharpe, drawdown across strategies. |
| **Settings** | Global toggles, theme, notification prefs. |

Every nav item uses a matching **lucide-react** icon, active state in cyan matching the modern **BotLogo** mark.

---

## 🔌 Third-Party Integrations

- **Pocket Option** — WebSocket v13.1 via SSID (session-bound).
- **Yfinance** — market data (with 15s TTL cache).
- **Telegram Bot API** — `python-telegram-bot` v22.8, both send + receive.
- **Emergent LLM Key** — universal key for AI features.
- **CoinGecko / Alpha Vantage / TwelveData** — optional supplementary data.
- **Twilio / SendGrid / Discord / Slack** — signal delivery.

---

## 🔒 Auth & Users

- JWT-based custom auth (email + password).
- Bcrypt-hashed passwords.
- Seeded admin: `seedtest@elitepo.com` / `SeedPass123!`, `newadmin@elitepo.com` / `AdminPass2!`.
- Regular test user: `testuser` / `test123`.
- KYC queue on the TMA admin page for new signups.
- Role-based nav (admin-only items hidden for regular users).

---

## 🧪 Test Coverage

Regression suite in `/app/backend/tests/`:

| File | Focus |
|---|---|
| `test_iter126_telegram.py` | Send/receive Telegram parser + endpoints. |
| `test_iter127_telegram_commands.py` | /pause /resume /status /stake /help commands. |
| `test_iter128_po_connection_resilience.py` | Dual-URL fallback for PO WebSocket. |
| `test_iter129_tma_and_triple_ma.py` | TMA math + 64 combos of 3-MA Crossover types. |
| `test_iter130_guppy_presets.py` | One-tap Guppy MA presets. |
| `test_iter131_riskguard.py` | Calculator math + session lifecycle. |
| `test_iter133_autofeed_and_nav.py` | TM auto-feed into RiskGuard + lucide nav. |
| `test_iter134_perf_and_gate.py` | yf_cache correctness + RiskGuard pre-flight gate. |

Run: `cd /app/backend && python -m pytest tests/ -v`.

---

## 📊 API Endpoint Cheatsheet

**Auth**: `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`
**Signals**: `GET /api/signals/latest`, `POST /api/signals/generate/single`, `POST /api/signals/auto-generate/start`
**Auto-Scan**: `POST /api/signals/auto-scan/start`, `POST /api/signals/auto-scan/stop`, `GET /api/signals/auto-scan/status`
**Strategies**: `POST /api/strategies/backtest`, `POST /api/strategies/autotune-confidence`
**RiskGuard**: `POST /api/riskguard/calculate`, `POST /api/riskguard/session/start`, `POST /api/riskguard/session/record-trade`, `GET /api/riskguard/session/current`, `GET /api/riskguard/sessions/history`, `GET /api/riskguard/stats/summary`
**TM Bridge**: `POST /api/trades/report`, `POST /api/trades/outcome`, `GET /api/tampermonkey/active-target`, `POST /api/tampermonkey/active-target`
**Telegram**: `GET /api/telegram/status`, `POST /api/telegram/send`, `GET /api/telegram/received-signals`
**Pocket Option**: `POST /api/auto-trade/connect`, `GET /api/auto-trade/status`, `POST /api/auto-trade/disconnect`
**Microstructure**: `GET /api/microstructure/kyle?asset=…`, `GET /api/microstructure/glosten_milgrom?asset=…`
**Perf**: `GET /api/perf/yf-cache`, `POST /api/perf/yf-cache/invalidate`

---

See **SETUP.md** for install / run / production-deploy instructions.
