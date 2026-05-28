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

## Last Updated: May 28, 2026
