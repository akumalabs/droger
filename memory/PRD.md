# Droplet Manager — PRD

## Problem Statement (verbatim)
Build a web app to manage Digital Ocean droplets using an API token, with the ability to install Windows OS via the akumalabs/reinstall kernel.sh script. (v2) Add login/register accounts, store multiple DO API tokens per user, switch between accounts, deploy-Linux-then-install-Windows wizard.

## Architecture
- **Backend**: FastAPI + MongoDB + httpx async proxy to `api.digitalocean.com/v2`
  - `auth.py` — JWT email/password (access 1d / refresh 7d, bcrypt, brute-force lockout per email) + Emergent Google OAuth session exchange. Both paths produce httpOnly cookies that `get_current_user` resolves uniformly.
  - `crypto_utils.py` — Fernet symmetric encryption for DO tokens at rest (`TOKEN_ENCRYPTION_KEY` env).
  - `server.py` — `/api/auth/*`, `/api/do-tokens/*` vault, `/api/do/*` proxy (requires auth + `?token_id=` query), `/api/do/windows-versions` (public), `/api/do/windows-script`, `/api/wizard/deploy-windows`.
  - MongoDB collections: `users`, `user_sessions`, `login_attempts`, `do_tokens`, `wizard_jobs`.
- **Frontend**: React + react-router + shadcn UI + phosphor-icons + sonner toasts. `AuthProvider` wraps app; `DOTokenProvider` wraps protected routes; axios has `withCredentials: true` and auto-injects `token_id` for `/do/*` calls.

## What's been implemented
### v1 (2026-02-22)
- Session-scoped DO token flow, droplet CRUD, power actions, snapshots, console link, Windows install command generator, dark Swiss UI.

### v2 (2026-02-22)
- **Accounts** — JWT register/login/logout/me/refresh + Emergent Google social login
- **DO token vault** — multi-token per user, encrypted at rest (Fernet), validated against DO on save, rename/delete/switch
- **Token switcher** in top nav; **Settings** page to manage vault
- **Deploy wizard** — 3-step flow: Linux specs → Windows config → live droplet polling with command/console link
- **Brute-force lockout** per email (proxy-IP independent) — 5 fails = 15-min lockout, 429 response
- **Admin seeding** from env on startup
- CORS auto-swaps wildcard → explicit origins when credentials=true
- 23 backend tests passing (22/23 initially, 1 critical lockout bug fixed after review)

## Seeded admin
`admin@dropletmanager.app` / `AdminDroplet!42` (see `/app/memory/test_credentials.md`)

## Backlog / Next Action Items
- P1: Monitoring graphs (CPU/disk/bandwidth) on droplet detail
- P1: Floating IPs + Domains/DNS management
- P2: Firewalls, VPCs, native MongoDB BSON datetimes, long-lived Win11 ISO hosting
- P2: Split server.py into `backend/routers/{auth,tokens,do,wizard}.py`
- P2: TTL index on `login_attempts`; trusted-proxy `X-Forwarded-For` handling if IP-based limiting is added later
- P2: Email verification + password-reset flow (infra already wired via `password_reset_tokens`)

## Personas
- DevOps engineer managing multiple DO client accounts from a single console
- Sysadmin deploying Windows-on-DO droplets for RDP / game-server / specialty workloads
- Agency / reseller onboarding client DO tokens without juggling dashboards
