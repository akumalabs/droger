# Deployment Guide — Droplet Manager

Two production-ready paths are documented below:

1. **VPS** (Ubuntu 22.04 — DigitalOcean Droplet / Hetzner / Linode / EC2)
2. **Render.com** (managed, zero-ops)

Before you start, make sure your repo is on GitHub (Emergent → "Save to GitHub" button).

---

## 0. Generate the required secrets (both paths)

Run these on any machine with Python 3.9+ to produce two critical values that must stay the **same forever** (if `TOKEN_ENCRYPTION_KEY` changes, every stored DO token becomes garbage):

```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
python3 -c "from cryptography.fernet import Fernet; print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Keep the output in a password manager. You will paste these values into the host's env-vars panel.

---

# Path A — VPS (Ubuntu 22.04)

## A1. Prepare a server

Create a DigitalOcean droplet (or Hetzner / Linode / EC2):
- 2 vCPU / 2 GB RAM is plenty
- Ubuntu 22.04 LTS
- Add your SSH key
- Open ports 22, 80, 443

Point an A-record (e.g., `dm.yourdomain.com`) at the server IP.

SSH in as root and create a deploy user:

```bash
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Switch to `deploy` for the remainder.

## A2. System dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential nginx supervisor python3 python3-pip python3-venv \
    ca-certificates gnupg
```

Install Node 20 and yarn:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g yarn
```

Install MongoDB 7 (or skip this step and use MongoDB Atlas free tier):

```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] \
    https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl enable --now mongod
```

## A3. Clone the repo

```bash
cd /opt
sudo git clone https://github.com/<you>/<repo>.git dm
sudo chown -R deploy:deploy /opt/dm
cd /opt/dm
```

## A4. Backend setup

```bash
cd /opt/dm/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

Create `/opt/dm/backend/.env` (use the secrets you generated in step 0):

```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="droplet_manager"
CORS_ORIGINS="https://dm.yourdomain.com"
JWT_SECRET="...paste your 64-char hex..."
TOKEN_ENCRYPTION_KEY="...paste your Fernet key..."
ADMIN_EMAIL="admin@yourdomain.com"
ADMIN_PASSWORD="<strong-password>"
FRONTEND_URL="https://dm.yourdomain.com"
RESEND_API_KEY="re_..."
SENDER_EMAIL="no-reply@yourdomain.com"
```

`chmod 600 /opt/dm/backend/.env`

## A5. Frontend build

```bash
cd /opt/dm/frontend
# Set backend URL once (used at build time by CRA)
echo 'REACT_APP_BACKEND_URL=https://dm.yourdomain.com' > .env
echo 'WDS_SOCKET_PORT=443' >> .env
yarn install --frozen-lockfile
yarn build
```

The production build is emitted to `/opt/dm/frontend/build`.

## A6. Supervisor config for the backend

Create `/etc/supervisor/conf.d/dm-backend.conf`:

```ini
[program:dm-backend]
directory=/opt/dm/backend
command=/opt/dm/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
user=deploy
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/dm-backend.err.log
stdout_logfile=/var/log/dm-backend.out.log
environment=PYTHONUNBUFFERED="1"
```

```bash
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl status dm-backend
```

## A7. Nginx config

Create `/etc/nginx/sites-available/dm`:

```nginx
server {
    listen 80;
    server_name dm.yourdomain.com;

    # React build
    root /opt/dm/frontend/build;
    index index.html;

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable & reload:

```bash
sudo ln -s /etc/nginx/sites-available/dm /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## A8. SSL with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d dm.yourdomain.com
```

Certbot will edit the nginx config, install the certificate, and set up auto-renewal. Visit `https://dm.yourdomain.com/login` — you should see the sign-in page.

## A9. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## A10. Updates (pull + rebuild)

```bash
cd /opt/dm
git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt && deactivate
cd ../frontend && yarn install --frozen-lockfile && yarn build
sudo supervisorctl restart dm-backend
sudo systemctl reload nginx
```

---

# Path B — Render.com

Render needs **three** services: (1) MongoDB, (2) backend web service, (3) frontend static site.

## B1. MongoDB

Render does not have managed MongoDB. Two options:

- **MongoDB Atlas free tier** (recommended): create an M0 cluster at mongodb.com/atlas → Database Access → create a user → Network Access → allow `0.0.0.0/0` → Connect → "Drivers" → copy the `mongodb+srv://...` URI. Remember to include the database name at the end or set `DB_NAME` env var separately.

- **Render private MongoDB**: create a Render "Private Service" using the official `mongo:7` Docker image with a 1 GB disk — cheaper than Atlas past free tier but you manage upgrades yourself.

## B2. Backend — Web Service

1. Render Dashboard → **New → Web Service** → "Connect a repository" → pick your GitHub repo.
2. Configure:
   - **Name**: `dm-backend`
   - **Root directory**: `backend`
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Instance type**: Starter ($7/mo) is enough
3. **Environment → Add env vars** (uppercase keys, paste values):

   | Key | Value |
   |---|---|
   | `MONGO_URL` | `mongodb+srv://user:pass@cluster.mongodb.net/` |
   | `DB_NAME` | `droplet_manager` |
   | `JWT_SECRET` | (from step 0) |
   | `TOKEN_ENCRYPTION_KEY` | (from step 0) |
   | `ADMIN_EMAIL` | `admin@yourdomain.com` |
   | `ADMIN_PASSWORD` | `<strong-password>` |
   | `FRONTEND_URL` | `https://dm-frontend.onrender.com` (set after step B3) |
   | `CORS_ORIGINS` | `https://dm-frontend.onrender.com` |
   | `RESEND_API_KEY` | `re_...` |
   | `SENDER_EMAIL` | `no-reply@yourdomain.com` |

4. Click **Create Web Service**. Render will build and deploy. Note the URL it assigns (e.g., `https://dm-backend.onrender.com`).

## B3. Frontend — Static Site

1. Render Dashboard → **New → Static Site** → same repo.
2. Configure:
   - **Name**: `dm-frontend`
   - **Root directory**: `frontend`
   - **Build command**: `yarn install --frozen-lockfile && yarn build`
   - **Publish directory**: `build`
3. **Environment → Add env var**:

   | Key | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | `https://dm-backend.onrender.com` (from B2) |

4. **Redirect/Rewrite rules** — add an SPA rewrite so deep links like `/droplets/123` don't 404:

   | Source | Destination | Action |
   |---|---|---|
   | `/*` | `/index.html` | Rewrite |

5. Click **Create Static Site**.

## B4. Wire the two services together

Once both are live:

- Go back to the **backend** service → Environment → set `FRONTEND_URL` and `CORS_ORIGINS` to the static-site URL (`https://dm-frontend.onrender.com`) → Save → Render redeploys automatically.
- Then go to the **frontend** service → Environment → confirm `REACT_APP_BACKEND_URL` points to the backend → Manual Deploy → "Clear build cache & deploy".

## B5. Custom domain (optional)

Render lets you add a custom domain to both services under Settings → Custom Domains. Add `dm.yourdomain.com` to the static site and `api.dm.yourdomain.com` to the backend, update `FRONTEND_URL`, `CORS_ORIGINS`, and `REACT_APP_BACKEND_URL` accordingly.

## B6. Auto-deploy on push

Render auto-deploys on every push to the branch you configured. To hot-patch env vars without redeploying code, use the Environment tab and click **Save, Deploy Latest**.

---

## Common gotchas

- **`TOKEN_ENCRYPTION_KEY` rotation** — if you lose this key, the Fernet ciphertexts in `do_tokens.token_encrypted` can never be decrypted. Users will have to re-add every DO token. Back it up.
- **Cookies across subdomains** — the auth cookies are `SameSite=None; Secure`. That works for different subdomains as long as both are HTTPS. If you split frontend and backend onto entirely different apex domains, you'll still get cookie rejection unless you add `Domain=.yourdomain.com`. Stick with subdomains of the same apex on Render for simplicity.
- **Google OAuth button** — `auth.emergentagent.com` only works when the app runs on an Emergent preview/deploy domain. When self-hosted, users can still register/login with email+password, but the Google button will bounce. To re-enable, swap in your own Google OAuth app and Firebase/Auth0/NextAuth flow (bigger refactor — not currently wired).
- **Resend sender domain** — you set `no-reply@mail.akumalabs.com`. When hosted elsewhere, change `SENDER_EMAIL` to an address on a domain verified in your Resend account.
- **MongoDB Atlas network** — don't forget to allow your Render/VPS egress IP (or `0.0.0.0/0` with a strong username/password).
- **CORS** — keep `CORS_ORIGINS` set to the **exact** frontend origin (including scheme). Wildcard `*` is auto-rejected by the server because the cookies require `allow_credentials=True`.

---

## Quick checklist after deploy

- [ ] `GET /api/` returns `{"service": "Droplet Manager API", "status": "ok"}`
- [ ] `/login` page renders
- [ ] Registration creates a user and sends a verification email (check Resend dashboard → Logs)
- [ ] Admin account `ADMIN_EMAIL` / `ADMIN_PASSWORD` can log in
- [ ] MongoDB `db.users.find()` shows the admin user
- [ ] Indexes on `login_attempts.last_attempt` (TTL 900s), `email_verification_tokens.expires_at` (TTL 0), `password_reset_tokens.expires_at` (TTL 0)
