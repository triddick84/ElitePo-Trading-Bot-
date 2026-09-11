# AI's Elite PO Traders Bot — Setup Guide

Complete instructions for **desktop (Windows / macOS / Linux)** and **mobile (Android / iOS)**.

---

## 📋 What You Need

| Requirement | Version | Where |
|---|---|---|
| **Emergent Platform account** | — | https://emergent.sh |
| **Pocket Option account** | — | https://po.market (demo works out-of-the-box) |
| **Telegram account** _(optional)_ | — | For phone-based signal + command control |
| **Google Chrome or Firefox** | current | To run the Tampermonkey userscript on PO |
| **Tampermonkey extension** | current | https://www.tampermonkey.net |

The app itself runs entirely in the Emergent cloud — no local install needed to use it. **Local install is only needed if you want to fork the source.**

---

## Part 1 — Using the Deployed App (recommended path)

### 1. Open the app URL
Your preview URL is shown in the Emergent chat as **REACT_APP_BACKEND_URL** with `/` at the end.
```
https://<your-app>.preview.emergentagent.com/
```

### 2. Log in
Use the seeded credentials:
- Regular user: `testuser` / `test123`
- Admin: `seedtest@elitepo.com` / `SeedPass123!`

Or register a fresh account from the login page.

### 3. Connect to Pocket Option
Left sidebar → **Pocket Option** page → click **Connect**. Green pill = live.
(If it fails, that means the platform-side WebSocket rejected the SSID. See **Refresh SSID** below.)

### 4. Configure your first trading session
Left sidebar → **RiskGuard** → set:
- **Capital** — your account balance
- **Payout %** — typical 0.80–0.90 for OTC (enter as decimal, e.g. `0.85`)
- **Target profit** — daily goal in $
- **Stop-loss** — max acceptable loss in $
- **Max trades** — hard cap on session trades

Click **Start Session**. The big card now shows your **Minimum Next Trade** amount.

### 5. Install the Tampermonkey userscript
5.1. Install the [Tampermonkey](https://www.tampermonkey.net) browser extension.
5.2. Open a new tab and navigate to:
```
<REACT_APP_BACKEND_URL>/pocket-option-auto-trader.user.js
```
5.3. Tampermonkey should prompt "Install this user-script?" → click **Install**.
5.4. Open **https://pocketoption.com/en/cabinet/demo-quick-high-low/** (or your real cabinet) — the AI panel now overlays the chart.

### 6. Enable Auto-Scanning
6.1. Left sidebar → **Mobile Auto-Trade** or **Dashboard** → click **Start Auto-Scan**.
6.2. Pick your asset universe (top-20 OTC pairs by default).
6.3. Set the min-confidence threshold (default `0.65`).
6.4. Watch the top winners rotate through the TM panel.

### 7. Optional — Wire up Telegram
7.1. Talk to [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → get your **BOT_TOKEN**.
7.2. Message your new bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` → copy the `chat.id`.
7.3. In Emergent chat, tell the agent to set these in `backend/.env`:
```
TELEGRAM_BOT_TOKEN=<your token>
TELEGRAM_CHAT_ID=<your chat id>
```
7.4. Restart backend (Emergent will do this automatically on save).
7.5. Open your bot's chat → tap `/` → the command menu (`/status`, `/pause`, `/resume`, `/stake`) appears.

---

## Part 2 — Setup for Desktop

### Chrome / Edge / Brave
1. Install Tampermonkey from [tampermonkey.net](https://www.tampermonkey.net) → Chrome Web Store.
2. Open Extensions → Tampermonkey → **Details** → toggle **Allow access to file URLs**.
3. Install the userscript following step 5 above.
4. Pin the Tampermonkey extension button so you can toggle scripts quickly.
5. Add the app URL to your bookmarks bar for one-click access.

### Firefox
1. Install Tampermonkey from Firefox Add-ons.
2. Follow the userscript install steps.

### Safari (macOS)
Safari's Tampermonkey requires a paid App Store version. Recommended: use Chrome or Firefox instead on macOS.

### Recommended monitor setup
- **Main monitor**: Pocket Option page with the TM AI panel overlaid.
- **Second monitor**: Emergent app dashboard tabs (Dashboard, RiskGuard, Auto-Scan status).
- **Optional third**: Telegram desktop app for `/status` command.

---

## Part 3 — Setup for Mobile

### Android
The full experience on Android:
1. Install **Kiwi Browser** (or Firefox Nightly) — the only mobile browsers that support desktop extensions.
2. Install Tampermonkey extension inside Kiwi.
3. Open the app URL in Kiwi → log in.
4. Open Pocket Option web (not the PO app!) in Kiwi → install the userscript.
5. Everything works: TM panel, auto-scan, RiskGuard, Telegram all fully mobile.

**Faster path (Telegram-only pilot)**:
1. Install the regular Telegram app.
2. Message your bot → tap `/` menu.
3. Send free-text signals like `EURUSD_OTC CALL 60s` — they route to PO automatically (assuming a browser session with the TM script is running on any device).
4. `/pause` and `/resume` control the entire trading bot from your phone.

### iOS
iOS Safari doesn't support Tampermonkey extensions. Two options:
1. **Userscript app**: Install the iOS **Userscripts** app from the App Store → import the userscript.
2. **Telegram-only**: Same as Android's "faster path" above — full control via Telegram bot commands, TM script running on any desktop browser you left open.

### Recommended mobile home-screen setup
- **Emergent App bookmark** (add to home-screen for quick access): opens **Mobile Auto-Trade** page directly.
- **Telegram bot chat** pinned to the top of Telegram.
- **PO web** bookmark (only if you're on Kiwi/Userscripts).

---

## Part 4 — For Developers (Local Fork)

If you cloned/forked the codebase:

### Backend
```bash
cd /app/backend
pip install -r requirements.txt
# Environment
cat > .env << 'EOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="elite_po_traders"
TELEGRAM_BOT_TOKEN=<yours>
TELEGRAM_CHAT_ID=<yours>
POCKET_OPTION_SSID="<a%3A4%3A%7B...>"
EOF
# Run
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd /app/frontend
yarn install
cat > .env << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8001
EOF
yarn start
```

### Tampermonkey bundle
```bash
cd /app/tampermonkey-src
# Bump version.txt FIRST
echo "8.147.0" > version.txt
npx webpack --mode production
# Output at ../frontend/public/pocket-option-auto-trader.user.js
```

### Run tests
```bash
cd /app/backend
python -m pytest tests/ -v
```

---

## Part 5 — Refresh Your PO Session (SSID)

Pocket Option sessions expire every ~24 h. When they do:

1. Log in to Pocket Option in a browser.
2. Open DevTools (F12) → **Application** tab → **Cookies** → find the `sid` cookie (long `a%3A4%3A%7B...` string).
3. Copy the entire value.
4. In Emergent, tell the agent: "Update `POCKET_OPTION_SSID` in `backend/.env` to `<value>`".
5. Backend auto-reloads. Click **Connect** on the Pocket Option page.

The app already has a background **SSID auto-refresh service** that tries to keep this fresh; the manual step is only needed as a fallback.

---

## Part 6 — Troubleshooting

| Symptom | Fix |
|---|---|
| **"Failed to connect to Pocket Option"** immediately | SSID expired — refresh (see Part 5). Also check `POST /api/auto-trade/connect` in the browser network tab for the exact error. |
| **TM panel not appearing on PO page** | Ensure the userscript is enabled in Tampermonkey → **Dashboard** → the script is green. Then hard-refresh Ctrl-F5 the PO page. |
| **Nav item icons look wrong / broken** | Hard refresh Ctrl-F5 to clear the old bundle. The app was recently migrated from emoji to lucide-react icons. |
| **Telegram bot doesn't respond** | Check `GET /api/telegram/status` — should show `configured:true`. If `false`, `.env` values weren't picked up — restart backend. |
| **Auto-scan runs but never places trades** | Two common causes: (a) RiskGuard session is locked — check the RiskGuard page's status pill; (b) `min_confidence` too high — lower to `0.60` and try again. |
| **`Yfinance cache 0% hit rate`** | Auto-scan interval is set longer than 15 s (the TTL). Either shorten scan interval or raise `YF_CACHE_TTL` env var. |
| **Tampermonkey updates aren't picked up** | The browser aggressively caches the userscript. Open Tampermonkey Dashboard → the script row → **Check for updates** → hard-refresh PO. |

---

## Part 7 — Going to Production

The Emergent preview URL is fine for personal daily use. For production:

1. Emergent chat → **Save to GitHub** to push the codebase.
2. Emergent chat → **Deploy** flow. Emergent handles:
   - MongoDB provisioning
   - Backend (FastAPI on port 8001)
   - Frontend (React static bundle behind CDN)
   - HTTPS + custom domain optional
3. Update `POCKET_OPTION_SSID` + `TELEGRAM_*` env vars in the production dashboard.
4. Re-install the Tampermonkey userscript from the new production URL.
5. That's it — production URL replaces the preview URL everywhere else.

---

## Part 8 — Support & Where to Ask

- **Feature request / bug** — talk to the Emergent chat agent in this app; the agent can read this codebase and ship changes live.
- **Trading-strategy questions** — see **FEATURES.md** for the full AI stack and how each layer contributes.
- **Emergent platform docs** — https://emergent.sh/docs
