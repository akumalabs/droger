# Deployment Guide — Droplet Manager

## Architecture

- FastAPI backend (`backend/app/main.py`)
- PostgreSQL (primary database)
- Redis (rate limits, lockouts, queues)
- Vite frontend static build (`frontend/dist`)

## Required Environment Variables

Backend (`backend/.env`):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/droger
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<strong-secret>
TOKEN_ENCRYPTION_KEY=<fernet-key>
FRONTEND_URL=https://dm.yourdomain.com
CORS_ORIGINS=https://dm.yourdomain.com
SECURE_COOKIES=true
COOKIE_SAMESITE=none
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<strong-password>
RESEND_API_KEY=re_...
SENDER_EMAIL=no-reply@yourdomain.com
```

Frontend (`frontend/.env`):

```env
VITE_BACKEND_URL=https://api.dm.yourdomain.com
```

## Backend Deploy

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Frontend Deploy

```bash
cd frontend
npm install
npm run build
```

Serve `frontend/dist` with your web server and proxy `/api/*` to backend.

## Health Check

- `GET /api/` returns `{"service":"Droplet Manager API","status":"ok"}`
- `GET /api/health` returns `{"ok":true}`
