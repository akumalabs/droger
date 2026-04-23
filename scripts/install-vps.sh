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

#!/usr/bin/env bash
set -Eeuo pipefail

# =============================================================================
# Droplet Manager — Production VPS Installer (Fixed + Stateful + Safe)
# =============================================================================

# ----------------------------- Colors -------------------------------------- #
if [[ -t 1 ]]; then
    GREEN=$'\033[1;32m'; RED=$'\033[1;31m'; BLUE=$'\033[1;34m'
    YELLOW=$'\033[1;33m'; RESET=$'\033[0m'
else
    GREEN= RED= BLUE= YELLOW= RESET=
fi

log() { echo -e "${BLUE}==>${RESET} $*"; }
ok()  { echo -e "${GREEN}✓${RESET} $*"; }
warn(){ echo -e "${YELLOW}!${RESET} $*"; }
die() { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }

trap 'die "Failed at line $LINENO. Check logs."' ERR

# ----------------------------- Reset mode ---------------------------------- #
STATE_FILE="/var/lib/dm-installer.env"

if [[ "${1:-}" == "--reset" ]]; then
    rm -f "$STATE_FILE"
    echo "Installer state reset."
    exit 0
fi

# ----------------------------- Preflight ----------------------------------- #
[[ $EUID -eq 0 ]] || die "Run as root"

. /etc/os-release
case "$ID" in
    ubuntu|debian) ok "OS: $PRETTY_NAME" ;;
    *) die "Unsupported OS" ;;
esac

# ----------------------------- Load state ---------------------------------- #
if [[ -f "$STATE_FILE" ]]; then
    log "Loading previous install state"
    set -a
    source "$STATE_FILE"
    set +a
fi

# ----------------------------- Ask helper ---------------------------------- #
ask() {
    local var="$1" prompt="$2" default="${3:-}" secret="${4:-0}"
    local current="${!var:-}"

    [[ -n "$current" ]] && { printf -v "$var" '%s' "$current"; return; }

    if [[ "${ASSUME_YES:-0}" == "1" ]]; then
        printf -v "$var" '%s' "$default"
        return
    fi

    [[ -e /dev/tty ]] || die "$var required (no TTY)"

    if [[ "$secret" == "1" ]]; then
        read -srp "$prompt${default:+ [$default]}: " val < /dev/tty; echo
    else
        read -rp "$prompt${default:+ [$default]}: " val < /dev/tty
    fi

    val="${val:-$default}"
    printf -v "$var" '%s' "$val"
}

# ----------------------------- Config -------------------------------------- #
log "Configuration"

ask REPO_URL "Git repo URL"
ask REPO_BRANCH "Branch" "main"
ask DOMAIN "Domain"
ask ADMIN_EMAIL "Admin email"
ask ADMIN_PASSWORD "Admin password" "" 1
ask RESEND_API_KEY "Resend API key"
ask SENDER_EMAIL "Sender email" "no-reply@$DOMAIN"
ask SSL_EMAIL "SSL email" "$ADMIN_EMAIL"
ask INSTALL_MONGO "Install MongoDB? (yes/no)" "yes"
ask MONGO_URL_OVERRIDE "MongoDB URI (if no MongoDB)" ""

# ----------------------------- Save state ---------------------------------- #
log "Saving state"

mkdir -p "$(dirname "$STATE_FILE")"

cat > "$STATE_FILE" <<EOF
REPO_URL="$REPO_URL"
REPO_BRANCH="$REPO_BRANCH"
DOMAIN="$DOMAIN"
ADMIN_EMAIL="$ADMIN_EMAIL"
ADMIN_PASSWORD="$ADMIN_PASSWORD"
RESEND_API_KEY="$RESEND_API_KEY"
SENDER_EMAIL="$SENDER_EMAIL"
SSL_EMAIL="$SSL_EMAIL"
INSTALL_MONGO="$INSTALL_MONGO"
MONGO_URL_OVERRIDE="$MONGO_URL_OVERRIDE"
EOF

chmod 600 "$STATE_FILE"
ok "State saved"

# ----------------------------- System deps --------------------------------- #
log "Installing system packages"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    git curl nginx supervisor ufw \
    python3 python3-venv python3-full python3-pip \
    build-essential >/dev/null

# Node
if ! command -v node &>/dev/null || [[ "$(node -v | cut -c2- | cut -d. -f1)" -lt 20 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
    apt-get install -y -qq nodejs >/dev/null
fi

# ----------------------------- MongoDB ------------------------------------- #
if [[ "$INSTALL_MONGO" == "yes" ]]; then
    if ! command -v mongod &>/dev/null; then
        curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb.gpg

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/mongodb.gpg] \
https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" \
        > /etc/apt/sources.list.d/mongodb.list

        apt-get update -qq
        apt-get install -y -qq mongodb-org >/dev/null || true
    fi
    systemctl enable --now mongod || true
    MONGO_URL="mongodb://localhost:27017"
else
    MONGO_URL="$MONGO_URL_OVERRIDE"
fi

[[ -n "$MONGO_URL" ]] || die "MongoDB URL missing"

# ----------------------------- Deploy user --------------------------------- #
DEPLOY_USER="deploy"

if ! id "$DEPLOY_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    usermod -aG sudo "$DEPLOY_USER"
fi

# ----------------------------- Repo ---------------------------------------- #
INSTALL_DIR="/opt/dm"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    sudo -u "$DEPLOY_USER" git -C "$INSTALL_DIR" pull
else
    sudo -u "$DEPLOY_USER" git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ----------------------------- Backend ------------------------------------- #
log "Backend setup"

ENV_FILE="$INSTALL_DIR/backend/.env"

cat > "$ENV_FILE" <<EOF
MONGO_URL="$MONGO_URL"
DB_NAME="dm"
DOMAIN="$DOMAIN"
ADMIN_EMAIL="$ADMIN_EMAIL"
ADMIN_PASSWORD="$ADMIN_PASSWORD"
RESEND_API_KEY="$RESEND_API_KEY"
SENDER_EMAIL="$SENDER_EMAIL"
EOF

chown "$DEPLOY_USER":"$DEPLOY_USER" "$ENV_FILE"

sudo -u "$DEPLOY_USER" bash -c "
cd $INSTALL_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
"

# ----------------------------- Frontend ------------------------------------ #
log "Frontend build"

sudo -u "$DEPLOY_USER" bash -c "
cd $INSTALL_DIR/frontend
echo 'REACT_APP_BACKEND_URL=https://$DOMAIN' > .env
yarn install --silent
yarn build
"

# ----------------------------- Supervisor ---------------------------------- #
cat > /etc/supervisor/conf.d/dm.conf <<EOF
[program:dm]
directory=$INSTALL_DIR/backend
command=$INSTALL_DIR/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
autostart=true
autorestart=true
stderr_logfile=/var/log/dm.err.log
stdout_logfile=/var/log/dm.out.log
user=$DEPLOY_USER
EOF

supervisorctl reread >/dev/null
supervisorctl update >/dev/null

# ----------------------------- Nginx --------------------------------------- #
cat > /etc/nginx/sites-available/dm <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $INSTALL_DIR/frontend/build;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
    }

    location / {
        try_files \$uri /index.html;
    }
}
EOF

ln -sf /etc/nginx/sites-available/dm /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# ----------------------------- Finish -------------------------------------- #
ok "Deployment complete"
echo "https://$DOMAIN"
