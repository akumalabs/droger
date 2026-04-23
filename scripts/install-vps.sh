#!/usr/bin/env bash
# =============================================================================
# Droplet Manager — one-shot VPS installer (Ubuntu 22.04 / Debian 12)
# =============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/scripts/install-vps.sh | sudo bash
#
# Or after cloning:
#   sudo bash scripts/install-vps.sh
#
# Fully non-interactive (for CI / cloud-init):
#   sudo DOMAIN=dm.example.com \
#        ADMIN_EMAIL=admin@example.com \
#        ADMIN_PASSWORD=changeme123 \
#        RESEND_API_KEY=re_xxx \
#        SENDER_EMAIL=no-reply@example.com \
#        REPO_URL=https://github.com/you/repo.git \
#        SSL_EMAIL=me@example.com \
#        ASSUME_YES=1 \
#        bash scripts/install-vps.sh
# =============================================================================

set -Eeuo pipefail

# ----------------------------- Pretty output -------------------------------- #
if [[ -t 1 ]]; then
    BLUE=$'\033[1;34m'; GREEN=$'\033[1;32m'; YELLOW=$'\033[1;33m'
    RED=$'\033[1;31m'; CYAN=$'\033[1;36m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
    BLUE= GREEN= YELLOW= RED= CYAN= DIM= RESET=
fi
log()  { echo -e "${BLUE}==>${RESET} $*"; }
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
die()  { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }
hr()   { echo -e "${DIM}---------------------------------------------------------------${RESET}"; }

trap 'die "Aborted at line $LINENO. See ${LOG_FILE:-/tmp/dm-install.log} for details."' ERR

# ----------------------------- Pre-flight ----------------------------------- #
[[ $EUID -eq 0 ]] || die "Run as root (use sudo)."

LOG_FILE="/var/log/dm-install.log"
: > "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

log "Droplet Manager installer"
hr

. /etc/os-release
case "$ID" in
    ubuntu|debian) ok "Detected $PRETTY_NAME" ;;
    *) die "Unsupported OS: $ID (Ubuntu 22.04+/Debian 12+ only)." ;;
esac

# ----------------------------- Defaults & prompts --------------------------- #
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/dm}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
DOMAIN="${DOMAIN:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
RESEND_API_KEY="${RESEND_API_KEY:-}"
SENDER_EMAIL="${SENDER_EMAIL:-}"
SSL_EMAIL="${SSL_EMAIL:-}"
ENABLE_SSL="${ENABLE_SSL:-auto}"       # auto | yes | no
INSTALL_MONGO="${INSTALL_MONGO:-yes}"  # yes | no (skip if using Atlas)
MONGO_URL_OVERRIDE="${MONGO_URL_OVERRIDE:-}"
ASSUME_YES="${ASSUME_YES:-0}"

ask() {
    local var="$1" prompt="$2" default="${3:-}" secret="${4:-0}"
    local current="${!var:-}"
    if [[ -n "$current" ]]; then return; fi
    if [[ "$ASSUME_YES" = "1" ]]; then
        [[ -n "$default" ]] || die "$var is required (non-interactive mode)."
        printf -v "$var" '%s' "$default"
        return
    fi
    if [[ "$secret" = "1" ]]; then
        read -srp "$prompt${default:+ [$default]}: " val; echo
    else
        read -rp "$prompt${default:+ [$default]}: " val
    fi
    printf -v "$var" '%s' "${val:-$default}"
}

log "Configuration"
hr
ask REPO_URL       "GitHub repo URL (https://github.com/you/repo.git)"
ask REPO_BRANCH    "Branch"                "main"
ask DOMAIN         "Domain (A-record pointing at this server)"
ask ADMIN_EMAIL    "Admin email"
ask ADMIN_PASSWORD "Admin password" "" 1
ask RESEND_API_KEY "Resend API key (re_...) — leave blank to skip email"
ask SENDER_EMAIL   "Sender email (must be on a Resend-verified domain)" "no-reply@${DOMAIN}"
ask SSL_EMAIL      "Email for Let's Encrypt certificate"               "$ADMIN_EMAIL"
ask INSTALL_MONGO  "Install MongoDB locally? (yes/no — no = use Atlas)" "yes"
if [[ "$INSTALL_MONGO" != "yes" ]]; then
    ask MONGO_URL_OVERRIDE "MongoDB URI (mongodb+srv://...)"
fi

[[ -n "$REPO_URL" && -n "$DOMAIN" && -n "$ADMIN_EMAIL" && -n "$ADMIN_PASSWORD" ]] \
    || die "REPO_URL, DOMAIN, ADMIN_EMAIL, ADMIN_PASSWORD are required."

# ----------------------------- Deploy user ---------------------------------- #
log "Creating deploy user '$DEPLOY_USER'"
if ! id -u "$DEPLOY_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    usermod -aG sudo "$DEPLOY_USER"
    ok "Created user $DEPLOY_USER"
else
    ok "User $DEPLOY_USER already exists"
fi

# ----------------------------- APT packages --------------------------------- #
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    git curl ca-certificates gnupg lsb-release \
    nginx supervisor \
    python3 python3-pip python3-venv python3-dev build-essential \
    ufw >/dev/null
ok "System packages installed"

# Node 20
if ! command -v node &>/dev/null || [[ "$(node -v | cut -c2- | cut -d. -f1)" -lt 20 ]]; then
    log "Installing Node 20"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
    apt-get install -y -qq nodejs >/dev/null
fi
ok "Node $(node -v)"

if ! command -v yarn &>/dev/null; then
    npm install -g yarn >/dev/null 2>&1
fi
ok "Yarn $(yarn -v)"

# MongoDB
if [[ "$INSTALL_MONGO" = "yes" ]]; then
    if ! command -v mongod &>/dev/null; then
        log "Installing MongoDB 7"
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
            | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
        codename=$(lsb_release -cs)
        # jammy works for both ubuntu 22.04 and debian 12
        [[ "$codename" = "bookworm" ]] && codename=jammy
        [[ "$codename" = "noble" ]] && codename=jammy
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu $codename/mongodb-org/7.0 multiverse" \
            > /etc/apt/sources.list.d/mongodb-org-7.0.list
        apt-get update -qq
        apt-get install -y -qq mongodb-org >/dev/null
    fi
    systemctl enable --now mongod
    ok "MongoDB running"
    MONGO_URL="mongodb://localhost:27017"
else
    MONGO_URL="$MONGO_URL_OVERRIDE"
    [[ -n "$MONGO_URL" ]] || die "MONGO_URL_OVERRIDE required when INSTALL_MONGO=no."
    ok "Using external MongoDB"
fi

# ----------------------------- Clone repo ----------------------------------- #
log "Cloning $REPO_URL@$REPO_BRANCH → $INSTALL_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" fetch --all --quiet
    sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" reset --hard "origin/$REPO_BRANCH"
    ok "Repo updated"
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    chown "$DEPLOY_USER":"$DEPLOY_USER" "$(dirname "$INSTALL_DIR")" || true
    sudo -u "$DEPLOY_USER" git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
    ok "Repo cloned"
fi
chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$INSTALL_DIR"

# ----------------------------- Backend .env --------------------------------- #
log "Generating backend/.env"
ENV_FILE="$INSTALL_DIR/backend/.env"

gen_jwt()    { python3 -c "import secrets; print(secrets.token_hex(32))"; }
gen_fernet() { python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
               || { pip3 install -q cryptography && python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"; }; }

# If .env already exists, preserve its secrets (idempotent)
if [[ -f "$ENV_FILE" ]]; then
    EXISTING_JWT=$(grep -E '^JWT_SECRET=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')
    EXISTING_FERNET=$(grep -E '^TOKEN_ENCRYPTION_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')
    warn "Existing .env found — preserving JWT_SECRET and TOKEN_ENCRYPTION_KEY"
fi
JWT_SECRET="${EXISTING_JWT:-$(gen_jwt)}"
TOKEN_ENCRYPTION_KEY="${EXISTING_FERNET:-$(gen_fernet)}"

cat > "$ENV_FILE" <<EOF
MONGO_URL="$MONGO_URL"
DB_NAME="droplet_manager"
CORS_ORIGINS="https://$DOMAIN"
JWT_SECRET="$JWT_SECRET"
TOKEN_ENCRYPTION_KEY="$TOKEN_ENCRYPTION_KEY"
ADMIN_EMAIL="$ADMIN_EMAIL"
ADMIN_PASSWORD="$ADMIN_PASSWORD"
FRONTEND_URL="https://$DOMAIN"
RESEND_API_KEY="$RESEND_API_KEY"
SENDER_EMAIL="$SENDER_EMAIL"
EOF
chown "$DEPLOY_USER":"$DEPLOY_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok "backend/.env written"

# ----------------------------- Python venv + deps --------------------------- #
log "Setting up Python venv"
sudo -u "$DEPLOY_USER" bash -c "
    cd '$INSTALL_DIR/backend'
    python3 -m venv venv
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
"
ok "Backend dependencies installed"

# ----------------------------- Frontend build ------------------------------- #
log "Building frontend"
sudo -u "$DEPLOY_USER" bash -c "
    cd '$INSTALL_DIR/frontend'
    cat > .env <<EOF2
REACT_APP_BACKEND_URL=https://$DOMAIN
WDS_SOCKET_PORT=443
EOF2
    yarn install --frozen-lockfile --silent
    yarn build
"
ok "Frontend built → $INSTALL_DIR/frontend/build"

# ----------------------------- Supervisor ----------------------------------- #
log "Configuring supervisor"
cat > /etc/supervisor/conf.d/dm-backend.conf <<EOF
[program:dm-backend]
directory=$INSTALL_DIR/backend
command=$INSTALL_DIR/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
user=$DEPLOY_USER
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/dm-backend.err.log
stdout_logfile=/var/log/dm-backend.out.log
environment=PYTHONUNBUFFERED="1"
EOF
supervisorctl reread >/dev/null
supervisorctl update >/dev/null
supervisorctl restart dm-backend >/dev/null 2>&1 || supervisorctl start dm-backend >/dev/null
sleep 2
if supervisorctl status dm-backend | grep -q RUNNING; then
    ok "Backend is running on 127.0.0.1:8001"
else
    die "Backend failed to start. See /var/log/dm-backend.err.log"
fi

# ----------------------------- Nginx ---------------------------------------- #
log "Configuring nginx"
NGINX_CONF="/etc/nginx/sites-available/dm"
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $INSTALL_DIR/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)\$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/dm
[[ -f /etc/nginx/sites-enabled/default ]] && rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null
systemctl reload nginx
ok "Nginx reloaded"

# ----------------------------- Firewall ------------------------------------- #
log "Configuring UFW"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
yes | ufw enable >/dev/null 2>&1 || true
ok "Firewall rules applied"

# ----------------------------- SSL (Let's Encrypt) -------------------------- #
if [[ "$ENABLE_SSL" = "auto" || "$ENABLE_SSL" = "yes" ]]; then
    if [[ -z "$SSL_EMAIL" ]]; then
        warn "SSL_EMAIL not set — skipping Let's Encrypt (you can run certbot manually later)"
    elif [[ "$DOMAIN" =~ ^[0-9.]+$ ]]; then
        warn "DOMAIN is an IP — skipping SSL (Let's Encrypt requires a real hostname)"
    else
        log "Installing Let's Encrypt certificate for $DOMAIN"
        apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
        if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$SSL_EMAIL" --redirect; then
            ok "HTTPS enabled"
        else
            warn "Certbot failed (DNS may not be propagated yet). Re-run: sudo certbot --nginx -d $DOMAIN"
        fi
    fi
fi

# ----------------------------- Healthcheck ---------------------------------- #
log "Running health check"
sleep 2
if curl -fsS --max-time 5 "http://127.0.0.1:8001/api/" >/dev/null; then
    ok "Backend /api/ responding"
else
    warn "Backend /api/ did not respond — check /var/log/dm-backend.err.log"
fi

# ----------------------------- Summary -------------------------------------- #
hr
echo -e "${GREEN}Deployment complete.${RESET}"
hr
cat <<EOF

  URL            : https://$DOMAIN
  Admin login    : $ADMIN_EMAIL
  Admin password : (set in $ENV_FILE)
  Install dir    : $INSTALL_DIR
  Deploy user    : $DEPLOY_USER

  Backend logs   : tail -f /var/log/dm-backend.err.log
  Backend ctl    : sudo supervisorctl restart dm-backend
  Nginx config   : $NGINX_CONF
  Env file       : $ENV_FILE   (contains JWT_SECRET + TOKEN_ENCRYPTION_KEY — back them up!)

  Updating:
    cd $INSTALL_DIR && sudo -u $DEPLOY_USER git pull
    cd backend && sudo -u $DEPLOY_USER venv/bin/pip install -r requirements.txt
    cd ../frontend && sudo -u $DEPLOY_USER yarn install --frozen-lockfile && sudo -u $DEPLOY_USER yarn build
    sudo supervisorctl restart dm-backend && sudo systemctl reload nginx

EOF
${CYAN:+printf '%s' "$CYAN"}echo -e "Open ${CYAN}https://$DOMAIN${RESET} to finish setup."
