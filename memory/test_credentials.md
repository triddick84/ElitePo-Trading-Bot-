# Test Credentials

## User Account
- Username: testuser
- Password: test123
- Email: test@test.com
- Role: user

## Admin Account
- Username: triddick84
- Password: Fallinone#1
- Email: triddick84@admin.local
- Role: admin

## SEED_ADMINS — Production Seed (Iter 65)
- Username: seedtest
- Password: SeedPass123!
- Email: seedtest@elitepo.com
- Role: admin
- Source: `SEED_ADMINS` env var in backend/.env. To add more admins, comma-separate:
  `SEED_ADMINS="ops@x.com:p1!:ops,trader@x.com:p2!:trader"`
  Format: `email:password[:username]` (username derives from email local-part if omitted)
- Behavior: idempotent on startup — existing users are skipped; existing non-admin users with a matching email are promoted to admin.

## ML Endpoints (No Auth Required)
- LSTM/GRU: `/api/lstm-gru/stats`, `/api/lstm-gru/predict`, `/api/lstm-gru/train`
- PPO RL: `/api/ppo-rl/stats`, `/api/ppo-rl/predict`, `/api/ppo-rl/train`
- AI Ensemble: `/api/ai-ensemble/predict`
- Maximized ML: `/api/maximized-ml/stats`, `/api/maximized-ml/predict/{symbol}`, `/api/maximized-ml/train`

## TMA (Telegram Mini App) — Phase A
- Admin Telegram User ID: `6434316177` (matches `TMA_ADMIN_TELEGRAM_IDS` in backend/.env)
- Dev mode: `TMA_DEV_MODE=true` — enables `dev:<telegram_user_id>:<username>` synthetic initData bypass (turn OFF in production).
- Sign in as TMA admin via dashboard: navigate to sidebar `🛡️ TMA KYC Admin` and click "Sign in as TMA admin (dev bypass)". Uses admin ID from env.
- Sign in as user via TMA page: open `/tma/?dev_uid=<any-numeric-id>&dev_username=<any-string>` in a browser (Phase A dev flow).
- Preview URL (TMA): `https://auto-invert-engine.preview.emergentagent.com/tma/`
- Preview URL (Admin): `https://auto-invert-engine.preview.emergentagent.com/` → sidebar `TMA KYC Admin`

## Last Updated: Feb 2026 (TMA Phase A)
