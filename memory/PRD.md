# Droplet Manager — PRD

## Problem Statement (verbatim)
Build a web app to manage Digital Ocean droplets using an API token, with the ability to install Windows OS via the akumalabs/reinstall kernel.sh script.

**v2**: accounts + multi-token vault + deploy wizard.
**v3 (P2)**: email verification, password reset, router split, TTL indexes.

## Architecture (after v3 refactor)
```
/app/backend/
├── server.py            # app entry, CORS, startup (indexes + admin seed)
├── db.py                # shared Motor AsyncIOMotorClient
├── deps.py              # current_user FastAPI dependency
├── auth.py              # JWT, bcrypt, lockout (native datetime), Emergent OAuth
├── crypto_utils.py      # Fernet encryption for DO tokens
├── mailer.py            # Resend async wrapper (console-log fallback)
└── routers/
    ├── auth_routes.py   # /api/auth/*
    ├── tokens.py        # /api/do-tokens/* + resolve_token() helper
    ├── do_proxy.py      # /api/do/*
    ├── windows.py       # /api/do/windows-versions, /windows-script
    └── wizard.py        # /api/wizard/deploy-windows
```

## What's been implemented

### v1 (2026-02-22)
- Session-scoped DO token flow, droplet CRUD, power actions, snapshots, console link, Windows install command generator, dark Swiss UI.

### v2 (2026-02-22)
- JWT email/password auth + Emergent Google social login
- Per-user encrypted DO token vault (Fernet), multi-token switcher
- Settings page, Deploy wizard (3-step with polling)
- Brute-force lockout per email, CORS auto-config for credentials

### v3 (2026-02-22) — P2 hardening
- **Email verification** via Resend:
  - Register creates row in `email_verification_tokens` + sends email
  - `/api/auth/verify-email` and `/api/auth/resend-verification`
  - Non-blocking: `email_verified: false` users have full access + top-bar banner
  - Google OAuth users auto-verified
- **Password reset** via Resend:
  - `/api/auth/forgot-password` (no enumeration leak)
  - `/api/auth/reset-password` (clears lockout on success)
- **TTL indexes** on `login_attempts` (900s), `email_verification_tokens` and `password_reset_tokens` (expires_at=0)
- **Router split**: server.py reduced from 590 lines → 110 lines
- **Tests**: 39/39 passing (23 regression + 16 new P2)

## Seeded admin
`admin@dropletmanager.app` / `AdminDroplet!42` (see `/app/memory/test_credentials.md`)

## Backlog / Next Action Items
- P1: Monitoring graphs (CPU/disk/bandwidth) on droplet detail
- P1: Floating IPs + Domains/DNS management
- P2: Rate-limit `/api/auth/forgot-password` + `/resend-verification` (Resend quota protection)
- P2: Retry-with-backoff in `mailer.send_email` for transient Resend rate-limits (2 req/sec free-tier)
- P2: 2FA, sessions list, pane-of-glass multi-account droplet view

## Known Notes
- Win11 ISO URL has `exp=1774981663` (expires 2026-04) — swap in `WINDOWS_VERSIONS` when it expires
- Resend free tier is 2 req/sec; current mailer logs failures but does not retry
- Verification/reset links point to `FRONTEND_URL` env (currently the preview domain)
