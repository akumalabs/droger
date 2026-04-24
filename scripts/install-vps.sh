#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -t 1 ]]; then
  GREEN=$'\033[1;32m'
  RED=$'\033[1;31m'
  BLUE=$'\033[1;34m'
  YELLOW=$'\033[1;33m'
  RESET=$'\033[0m'
else
  GREEN=
  RED=
  BLUE=
  YELLOW=
  RESET=
fi

log() { echo -e "${BLUE}==>${RESET} $*"; }
ok() { echo -e "${GREEN}✓${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
die() { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }

trap 'die "Failed at line $LINENO"' ERR

STATE_FILE="/var/lib/dm-installer.env"
DEPLOY_USER="deploy"
INSTALL_DIR="/opt/dm"

ASSUME_YES="${ASSUME_YES:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)
      rm -f "$STATE_FILE"
      echo "Installer state reset"
      exit 0
      ;;
    --non-interactive|-y)
      ASSUME_YES=1
      shift
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done
export ASSUME_YES

[[ $EUID -eq 0 ]] || die "Run as root"

source /etc/os-release
case "$ID" in
  ubuntu|debian) ;;
  *) die "Unsupported OS: $ID" ;;
esac

generate_hex() {
  local size="$1"
  od -An -N"$size" -tx1 /dev/urandom | tr -d ' \n'
}

generate_fernet_key() {
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'
}

sql_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

env_escape() {
  printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

save_state() {
  umask 077
  {
    echo "#!/usr/bin/env bash"
    declare -p REPO_URL
    declare -p REPO_BRANCH
    declare -p DOMAIN
    declare -p SSL_EMAIL
    declare -p ENABLE_SSL
    declare -p ADMIN_EMAIL
    declare -p ADMIN_PASSWORD
    declare -p RESEND_API_KEY
    declare -p SENDER_EMAIL
    declare -p POSTGRES_DB
    declare -p POSTGRES_USER
    declare -p POSTGRES_PASSWORD
    declare -p JWT_SECRET
    declare -p TOKEN_ENCRYPTION_KEY
  } > "$STATE_FILE"
  chmod 600 "$STATE_FILE"
}

if [[ -f "$STATE_FILE" ]]; then
  log "Loading previous state"
  source "$STATE_FILE"
fi

ask() {
  local var="$1"
  local prompt="$2"
  local default="${3:-}"
  local secret="${4:-0}"
  local current="${!var:-}"
  if [[ -n "$current" ]]; then
    printf -v "$var" '%s' "$current"
    return
  fi
  if [[ "${ASSUME_YES:-0}" == "1" ]]; then
    printf -v "$var" '%s' "$default"
    return
  fi
  if [[ ! -e /dev/tty ]]; then
    if [[ -n "$default" ]]; then
      printf -v "$var" '%s' "$default"
      return
    fi
    die "$var required"
  fi
  local value=""
  if [[ "$secret" == "1" ]]; then
    read -srp "$prompt${default:+ [$default]}: " value < /dev/tty
    echo
  else
    read -rp "$prompt${default:+ [$default]}: " value < /dev/tty
  fi
  printf -v "$var" '%s' "${value:-$default}"
}

valid_identifier() {
  [[ "$1" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]
}

require_non_empty() {
  local name="$1"
  local value="$2"
  [[ -n "$value" ]] || die "$name is required"
}

confirm_or_die() {
  local message="$1"
  if [[ "$ASSUME_YES" == "1" ]]; then
    die "$message"
  fi
  if [[ ! -e /dev/tty ]]; then
    die "$message"
  fi
  local answer
  read -rp "$message Continue anyway? (yes/no): " answer < /dev/tty
  [[ "$answer" == "yes" ]] || die "Aborted"
}

run_preflight_checks() {
  log "Running preflight checks"

  local mem_mb
  local disk_mb
  mem_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
  disk_mb="$(df -Pm / | awk 'NR==2 {print $4}')"

  (( mem_mb >= 1024 )) || die "At least 1GB RAM required (detected ${mem_mb}MB)"
  (( disk_mb >= 5120 )) || die "At least 5GB free disk required (detected ${disk_mb}MB)"

  local port_lines
  port_lines="$(ss -ltnp 2>/dev/null | awk 'NR>1 && $4 ~ /:80$|:443$/ {print $0}')"
  if [[ -n "$port_lines" ]]; then
    if echo "$port_lines" | grep -q "nginx"; then
      warn "Ports 80/443 are already used by nginx"
    else
      die "Ports 80/443 are already in use by another process"
    fi
  fi

  local domain_ip
  local public_ip
  domain_ip="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1 {print $1}')"
  public_ip="$(curl -fsS https://api.ipify.org || true)"

  if [[ "$ENABLE_SSL" == "yes" ]]; then
    [[ -n "$domain_ip" ]] || die "Could not resolve $DOMAIN. Set DNS A record before SSL"
    if [[ -n "$public_ip" && "$domain_ip" != "$public_ip" ]]; then
      confirm_or_die "DNS for $DOMAIN resolves to $domain_ip but this server public IP is $public_ip."
    fi
  fi

  ok "Preflight checks passed"
}

ensure_locked_dependencies() {
  log "Validating dependency lock files"

  [[ -f "$INSTALL_DIR/backend/requirements.txt" ]] || die "Missing backend/requirements.txt"
  [[ -f "$INSTALL_DIR/frontend/package-lock.json" ]] || die "Missing frontend/package-lock.json; run npm install locally and commit lockfile"

  local unpinned
  unpinned="$(grep -Ev '^\s*($|#)' "$INSTALL_DIR/backend/requirements.txt" | grep -Ev '==')" || true
  if [[ -n "$unpinned" ]]; then
    die "All backend requirements must be pinned with ==. Unpinned entries detected."
  fi

  ok "Dependency lock validation passed"
}

run_smoke_checks() {
  log "Running smoke checks"

  supervisorctl status dm-backend | grep -q RUNNING || die "Supervisor service dm-backend is not running"

  local health_local
  health_local="$(curl -fsS --max-time 10 http://127.0.0.1:8001/api/health || true)"
  echo "$health_local" | grep -q '"ok"' || die "Backend health check failed at 127.0.0.1:8001"

  local health_nginx
  health_nginx="$(curl -fsS --max-time 10 -H "Host: $DOMAIN" http://127.0.0.1/api/health || true)"
  echo "$health_nginx" | grep -q '"ok"' || die "Nginx proxy health check failed"

  if [[ "$ENABLE_SSL" == "yes" ]]; then
    local health_https
    health_https="$(curl -fsS --max-time 10 "https://$DOMAIN/api/health" || true)"
    echo "$health_https" | grep -q '"ok"' || warn "HTTPS health check failed; verify DNS/certificate"
  fi

  ok "Smoke checks passed"
}

ask REPO_URL "Git repo URL"
ask REPO_BRANCH "Git branch" "main"
ask DOMAIN "Public domain (example.com)"
ask SSL_EMAIL "Let's Encrypt email"
ask ENABLE_SSL "Enable SSL with Let's Encrypt? (yes/no)" "yes"
ask ADMIN_EMAIL "Admin email"
ask ADMIN_PASSWORD "Admin password" "" 1
ask RESEND_API_KEY "Resend API key (optional)" ""
ask SENDER_EMAIL "Sender email" "no-reply@$DOMAIN"
ask POSTGRES_DB "PostgreSQL database" "droger"
ask POSTGRES_USER "PostgreSQL user" "droger"
ask POSTGRES_PASSWORD "PostgreSQL password" "$(generate_hex 24)" 1
ask JWT_SECRET "JWT secret" "$(generate_hex 32)" 1
ask TOKEN_ENCRYPTION_KEY "Token encryption key (Fernet)" "$(generate_fernet_key)" 1

require_non_empty "REPO_URL" "$REPO_URL"
require_non_empty "DOMAIN" "$DOMAIN"
require_non_empty "SSL_EMAIL" "$SSL_EMAIL"
require_non_empty "ADMIN_EMAIL" "$ADMIN_EMAIL"
require_non_empty "ADMIN_PASSWORD" "$ADMIN_PASSWORD"

[[ "$ENABLE_SSL" == "yes" || "$ENABLE_SSL" == "no" ]] || die "ENABLE_SSL must be yes or no"

valid_identifier "$POSTGRES_DB" || die "POSTGRES_DB must match [a-zA-Z_][a-zA-Z0-9_]*"
valid_identifier "$POSTGRES_USER" || die "POSTGRES_USER must match [a-zA-Z_][a-zA-Z0-9_]*"

save_state
ok "State saved to $STATE_FILE"

run_preflight_checks

export DEBIAN_FRONTEND=noninteractive

log "Installing system packages"
apt-get update -qq
apt-get install -y -qq \
  git curl nginx supervisor ufw \
  python3 python3-venv python3-pip python3-full \
  build-essential postgresql postgresql-contrib redis-server >/dev/null

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi

systemctl enable --now postgresql
systemctl enable --now redis-server

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG sudo "$DEPLOY_USER"
fi

mkdir -p "$INSTALL_DIR"
chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$INSTALL_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Updating repository"
  sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" fetch --all --prune
  sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" checkout "$REPO_BRANCH"
  sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" reset --hard "origin/$REPO_BRANCH"
  sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" clean -fd
else
  log "Cloning repository"
  rm -rf "$INSTALL_DIR"
  sudo -u "$DEPLOY_USER" git clone --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

ensure_locked_dependencies

POSTGRES_DB_SQL="$(sql_escape "$POSTGRES_DB")"
POSTGRES_USER_SQL="$(sql_escape "$POSTGRES_USER")"
POSTGRES_PASSWORD_SQL="$(sql_escape "$POSTGRES_PASSWORD")"

log "Configuring PostgreSQL"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO
\$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${POSTGRES_USER_SQL}') THEN
    CREATE ROLE "${POSTGRES_USER}" LOGIN PASSWORD '${POSTGRES_PASSWORD_SQL}';
  ELSE
    ALTER ROLE "${POSTGRES_USER}" WITH LOGIN PASSWORD '${POSTGRES_PASSWORD_SQL}';
  END IF;
END
\$\$;
SQL

if [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB_SQL}'")" != "1" ]]; then
  sudo -u postgres createdb -O "$POSTGRES_USER" "$POSTGRES_DB"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE \"${POSTGRES_DB}\" TO \"${POSTGRES_USER}\";"

PUBLIC_SCHEME="http"
SECURE_COOKIES="false"
COOKIE_SAMESITE="lax"
if [[ "$ENABLE_SSL" == "yes" ]]; then
  PUBLIC_SCHEME="https"
  SECURE_COOKIES="true"
  COOKIE_SAMESITE="none"
fi
PUBLIC_ORIGIN="${PUBLIC_SCHEME}://${DOMAIN}"

log "Writing backend environment"
cat > "$INSTALL_DIR/backend/.env" <<EOF
DATABASE_URL="postgresql+asyncpg://$(env_escape "$POSTGRES_USER"):$(env_escape "$POSTGRES_PASSWORD")@127.0.0.1:5432/$(env_escape "$POSTGRES_DB")"
REDIS_URL="redis://127.0.0.1:6379/0"
JWT_SECRET="$(env_escape "$JWT_SECRET")"
TOKEN_ENCRYPTION_KEY="$(env_escape "$TOKEN_ENCRYPTION_KEY")"
FRONTEND_URL="$(env_escape "$PUBLIC_ORIGIN")"
CORS_ORIGINS="$(env_escape "$PUBLIC_ORIGIN")"
SECURE_COOKIES="$(env_escape "$SECURE_COOKIES")"
COOKIE_SAMESITE="$(env_escape "$COOKIE_SAMESITE")"
ADMIN_EMAIL="$(env_escape "$ADMIN_EMAIL")"
ADMIN_PASSWORD="$(env_escape "$ADMIN_PASSWORD")"
RESEND_API_KEY="$(env_escape "$RESEND_API_KEY")"
SENDER_EMAIL="$(env_escape "$SENDER_EMAIL")"
EOF

chown "$DEPLOY_USER":"$DEPLOY_USER" "$INSTALL_DIR/backend/.env"
chmod 600 "$INSTALL_DIR/backend/.env"

log "Installing backend dependencies and migrations"
sudo -u "$DEPLOY_USER" bash -lc "cd '$INSTALL_DIR/backend' && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head"

log "Building frontend"
sudo -u "$DEPLOY_USER" bash -lc "cd '$INSTALL_DIR/frontend' && printf 'VITE_BACKEND_URL=%s\n' '$PUBLIC_ORIGIN' > .env && if [ -f package-lock.json ]; then npm ci; else npm install; fi && npm run build"

log "Configuring supervisor"
cat > /etc/supervisor/conf.d/dm-backend.conf <<EOF
[program:dm-backend]
directory=$INSTALL_DIR/backend
command=$INSTALL_DIR/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
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
supervisorctl restart dm-backend >/dev/null || supervisorctl start dm-backend >/dev/null

log "Configuring nginx"
cat > /etc/nginx/sites-available/dm <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $INSTALL_DIR/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri /index.html;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/dm /etc/nginx/sites-enabled/dm
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if [[ "$ENABLE_SSL" == "yes" ]]; then
  log "Configuring SSL"
  apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
  certbot --nginx --non-interactive --agree-tos --email "$SSL_EMAIL" -d "$DOMAIN" --redirect || warn "Certbot failed, continuing with HTTP"
fi

ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

run_smoke_checks

ok "Deployment complete"
echo "${PUBLIC_SCHEME}://${DOMAIN}"
