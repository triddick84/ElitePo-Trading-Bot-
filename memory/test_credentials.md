# Test credentials

Use these credentials for automated tests and login flows. Never delete or overwrite.

## Regular test user (grandfathered to active — pre-existed Iter 97)
- **Username**: `testuser`
- **Password**: `test123`
- **Status**: active

## Seed admin (from `SEED_ADMINS` env var, force-active on every startup — Iter 97 protected)
- **Username**: `seedtest`
- **Email**: `seedtest@elitepo.com`
- **Password**: `SeedPass123!`
- **Role**: admin
- **Status**: active

## Iter 97 admin-approval flow
New user registrations default to `status=pending` and CANNOT log in until an admin approves them.

**Test flow**:
1. POST `/api/auth/register` with new username → returns HTTP 202 + `pending:true`, no token.
2. POST `/api/auth/login` for that user → returns HTTP 403 with `detail.code=ACCOUNT_PENDING`.
3. Log in as seed admin (`seedtest` / `SeedPass123!`) → gets JWT.
4. `GET /api/auth/users/pending` (admin auth) → lists all pending users.
5. `POST /api/auth/users/{user_id}/approve` (admin auth) → sets status=active.
6. New user's login now succeeds.

**Admin actions**: `/approve`, `/reject`, `/suspend` (all admin-only). Cannot self-suspend. Cannot deactivate the last active admin.

To add more seed admins, comma-separate the `SEED_ADMINS` env var in `backend/.env`:
```
SEED_ADMINS=seedtest@elitepo.com:SeedPass123!,newadmin@elitepo.com:AdminPass2!
```


## Telegram integration (Iter 126)
- **Bot Token**: `8342619832:AAEdHnS_HKKariaDQaKHH6OT_pnLfp9dfIQ` (in `backend/.env` as `TELEGRAM_BOT_TOKEN`)
- **Chat ID**: `6434316177` (in `backend/.env` as `TELEGRAM_CHAT_ID`)
- **Bot Username**: `@ElitePocket_bot`
- **Endpoints**: `GET /api/telegram/status`, `POST /api/telegram/send`, `GET /api/telegram/received-signals`
