# Droplet Manager

Droplet Manager is a full-stack control plane for DigitalOcean accounts with:
- email/password authentication
- encrypted DO API token vault
- DigitalOcean API proxy
- Windows reinstall command generation
- deploy wizard for Linux-to-Windows flows

## Stack

- Backend: FastAPI, SQLAlchemy 2, PostgreSQL, Redis, Alembic
- Frontend: React, Vite, TypeScript, Tailwind v3, shadcn/ui

## Local Development

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/droger
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me
TOKEN_ENCRYPTION_KEY=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173
SECURE_COOKIES=false
COOKIE_SAMESITE=lax
ADMIN_EMAIL=admin@dropletmanager.app
ADMIN_PASSWORD=AdminDroplet!42
RESEND_API_KEY=
SENDER_EMAIL=onboarding@resend.dev
```

Run API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Run migrations:

```bash
alembic upgrade head
```

Run tests:

```bash
python3 -m pytest backend/tests -q
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_BACKEND_URL=http://localhost:8001
```

Run app:

```bash
npm run dev
```

Typecheck + build:

```bash
npm run typecheck
npm run build
```
