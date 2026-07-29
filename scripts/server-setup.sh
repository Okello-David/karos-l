#!/usr/bin/env bash
#
# KarosL — one-time host setup for an AWS EC2 staging instance.
#
# Installs Docker Engine, the Docker Compose v2 plugin, and git on a fresh
# Amazon Linux 2023 or Ubuntu LTS instance, then adds the current user to the
# "docker" group.
#
# This is an OPTIONAL convenience wrapper around the manual steps in
# docs/AWS_EC2_DEPLOYMENT.md §4 — that document remains the source of truth.
# Read it if anything here fails; nothing in this script is magic.
#
# What it deliberately does NOT do:
#   - create, read, or modify any .env file (secrets are entered by hand on
#     the server — see docs/AWS_EC2_DEPLOYMENT.md §5)
#   - clone the repository (you choose the branch and directory)
#   - build, start, or stop any container
#   - remove or overwrite anything already installed
#
# Usage (on the EC2 instance, NOT on your laptop):
#   ./scripts/server-setup.sh
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "Run this as a normal user (it calls sudo itself), not as root."
command -v sudo >/dev/null 2>&1 || die "sudo is required but not installed."

# --- Detect the distribution ------------------------------------------------
[ -r /etc/os-release ] || die "Cannot read /etc/os-release; unsupported system."
# shellcheck disable=SC1091
. /etc/os-release
log "Detected: ${PRETTY_NAME:-$ID}"

# --- Install Docker ---------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
    log "Docker already installed ($(docker --version)) — skipping install."
else
    case "$ID" in
        amzn)
            log "Installing Docker + git (Amazon Linux)..."
            sudo dnf update -y
            sudo dnf install -y docker git
            ;;
        ubuntu|debian)
            log "Installing Docker from Docker's official apt repository..."
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg git
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/${ID}/gpg" \
                | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
                | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        *)
            die "Unsupported distribution '$ID'. Follow docs/AWS_EC2_DEPLOYMENT.md §4 manually."
            ;;
    esac
fi

log "Enabling and starting the Docker daemon..."
sudo systemctl enable --now docker

# --- Compose v2 plugin ------------------------------------------------------
# Ubuntu gets it from docker-compose-plugin above; Amazon Linux does not ship
# it at all, so install it into the CLI plugin directory.
if docker compose version >/dev/null 2>&1; then
    log "Docker Compose plugin present ($(docker compose version --short 2>/dev/null || echo v2))."
else
    log "Installing the Docker Compose v2 plugin..."
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -SL \
        "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# --- Non-root docker access -------------------------------------------------
if id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    log "User '$USER' is already in the docker group."
else
    log "Adding '$USER' to the docker group..."
    sudo usermod -aG docker "$USER"
    warn "Group membership only applies to a NEW login session."
    warn "Log out and SSH back in before running any docker command."
fi

# --- Advisory: swap on small instances --------------------------------------
# The frontend image build runs `npm ci && npm run build`, which can be OOM-
# killed on a 1 GB instance. We only warn — adding swap silently would be a
# system change the operator did not ask for.
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
swap_mb=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$mem_mb" -lt 2000 ] && [ "$swap_mb" -lt 512 ]; then
    warn "Only ${mem_mb} MB RAM and ${swap_mb} MB swap detected."
    warn "The frontend 'npm run build' may be OOM-killed. Consider adding swap —"
    warn "see docs/AWS_EC2_DEPLOYMENT.md §4.5 for the exact commands."
fi

# --- Next steps -------------------------------------------------------------
cat <<'EOF'

==> Host setup complete.

Next steps (docs/AWS_EC2_DEPLOYMENT.md §4.4 onward):

  1. Log out and SSH back in   # required for docker group membership
  2. docker compose version    # confirm v2.x
  3. git clone <REPO_URL> <APP_DIR> && cd <APP_DIR>
  4. cp .env.example .env && chmod 600 .env
     Then edit it. For staging you MUST set, at minimum:
       FRONTEND_PORT=80
       ALLOWED_HOSTS=<EC2_PUBLIC_IP>,localhost,127.0.0.1,backend
       CSRF_TRUSTED_ORIGINS=http://<EC2_PUBLIC_IP>
       CORS_ALLOWED_ORIGINS=http://<EC2_PUBLIC_IP>
       SECRET_KEY / POSTGRES_PASSWORD / DB_PASSWORD  (freshly generated)
  5. ./scripts/deploy-staging.sh

Never commit .env, and never paste its contents into a chat or ticket.
EOF
