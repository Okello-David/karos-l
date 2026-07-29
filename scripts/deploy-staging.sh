#!/usr/bin/env bash
#
# KarosL — build and (re)start the staging Docker Compose stack.
#
# An OPTIONAL convenience wrapper around the commands in
# docs/AWS_EC2_DEPLOYMENT.md §6 and §12. Every step it runs is a plain
# `docker compose` command you can type yourself; nothing here is required.
#
# What it does:
#   1. sanity-checks that .env exists and looks like a staging config
#   2. optionally `git pull` (--pull)
#   3. docker compose build
#   4. docker compose up -d
#   5. waits for all services to report healthy, then curls /api/health/
#
# What it deliberately does NOT do — all of these are destructive or
# security-sensitive, and stay manual and deliberate:
#   - `docker compose down -v`  (would delete the database)
#   - `docker system prune`     (would remove images/cache beyond this project)
#   - create or edit .env, or print any secret
#   - create a superuser, or run any data-modifying management command
#   - `git checkout` / `git reset` (never discards your changes)
#
# Migrations are NOT run here: backend/docker-entrypoint.sh runs `migrate`
# automatically on every backend container start, and Django's migration
# runner is idempotent.
#
# Usage (from the repo root on the staging server):
#   ./scripts/deploy-staging.sh            # build + up -d + verify
#   ./scripts/deploy-staging.sh --pull     # git pull first, then the above
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DO_PULL=false
for arg in "$@"; do
    case "$arg" in
        --pull) DO_PULL=true ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

# --- Preconditions ----------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found. Run ./scripts/server-setup.sh first."
docker compose version >/dev/null 2>&1 \
    || die "The Docker Compose v2 plugin is missing. See docs/AWS_EC2_DEPLOYMENT.md §4."
docker info >/dev/null 2>&1 \
    || die "Cannot talk to the Docker daemon. Is it running, and are you in the 'docker' group? (Log out and back in after being added.)"

[ -f .env ] || die ".env not found in $REPO_ROOT.
Create it by hand — never commit it:
  cp .env.example .env && chmod 600 .env
Then set the staging values from docs/AWS_EC2_DEPLOYMENT.md §5."

[ -f docker-compose.yml ] || die "docker-compose.yml not found — run this from the repo root."

# --- Config sanity checks (warn, never modify) ------------------------------
# These catch the mistakes that actually happen in staging. We warn rather
# than edit: .env is the operator's file and may be intentionally different.
log "Checking .env for common staging misconfigurations..."

grep -qE '^SECRET_KEY=django-insecure-' .env \
    && warn "SECRET_KEY is still the insecure placeholder. Generate a real one (docs/AWS_EC2_DEPLOYMENT.md §5.2)."
grep -qE '^POSTGRES_PASSWORD=change_this_password' .env \
    && warn "POSTGRES_PASSWORD is still the placeholder from .env.example."
grep -qE '^DEBUG=True' .env \
    && warn "DEBUG=True — must be False for any internet-reachable environment."
grep -qE '^CORS_ALLOW_ALL_ORIGINS=True' .env \
    && warn "CORS_ALLOW_ALL_ORIGINS=True — should be False."

# ALLOWED_HOSTS must keep localhost: the backend container's Docker HEALTHCHECK
# curls http://localhost:8000/api/health/, and Django 400s an unlisted Host.
if grep -qE '^ALLOWED_HOSTS=' .env && ! grep -E '^ALLOWED_HOSTS=' .env | grep -q 'localhost'; then
    warn "ALLOWED_HOSTS does not include 'localhost' — the backend container's"
    warn "healthcheck will fail permanently even though the app works. See §14."
fi

# POSTGRES_PASSWORD and DB_PASSWORD must match, or the backend cannot connect.
pg_pw=$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2- || true)
db_pw=$(grep -E '^DB_PASSWORD=' .env | head -1 | cut -d= -f2- || true)
if [ -n "$pg_pw" ] && [ -n "$db_pw" ] && [ "$pg_pw" != "$db_pw" ]; then
    die "POSTGRES_PASSWORD and DB_PASSWORD differ in .env — the backend will not be able to connect.
(Values not printed here on purpose.)"
fi

# --- Optional: update the working tree --------------------------------------
if [ "$DO_PULL" = true ]; then
    log "Pulling the latest commits..."
    if [ -n "$(git status --porcelain)" ]; then
        warn "Working tree has local changes; 'git pull' may refuse to merge."
        warn "Nothing will be discarded — resolve it yourself if the pull fails."
    fi
    git pull --ff-only
fi

# --- Build and start --------------------------------------------------------
log "Building images (first build on a small instance can take 5-15 minutes)..."
docker compose build

log "Starting services..."
docker compose up -d

# --- Wait for health --------------------------------------------------------
log "Waiting for services to report healthy (up to 120s)..."
deadline=$((SECONDS + 120))
while [ $SECONDS -lt $deadline ]; do
    # A service is "settled" once no container is still in the "starting" state.
    if ! docker compose ps --format '{{.Health}}' 2>/dev/null | grep -q 'starting'; then
        break
    fi
    sleep 5
done

log "Service status:"
docker compose ps

# --- Verify -----------------------------------------------------------------
# Hit the app through nginx on the published frontend port, exactly as a
# browser would, so this exercises the whole chain: nginx -> gunicorn -> postgres.
frontend_port=$(grep -E '^FRONTEND_PORT=' .env | head -1 | cut -d= -f2- || true)
frontend_port=${frontend_port:-8080}

log "Checking http://localhost:${frontend_port}/api/health/ ..."
if curl -fsS --max-time 10 "http://localhost:${frontend_port}/api/health/" 2>/dev/null; then
    printf '\n\n\033[1;32m==> Stack is up and the full chain (nginx -> gunicorn -> postgres) responds.\033[0m\n'
else
    printf '\n'
    warn "Health check did not return OK. The stack may still be starting."
    warn "Investigate with:"
    warn "  docker compose ps"
    warn "  ./scripts/docker-logs.sh backend --tail 50"
    warn "See the troubleshooting section: docs/AWS_EC2_DEPLOYMENT.md §14."
    exit 1
fi

cat <<EOF

Next steps:
  - First deploy? Create the admin account:
      docker compose exec backend python manage.py createsuperuser
  - Open the app:   http://<EC2_PUBLIC_IP>   (with FRONTEND_PORT=80)
  - Walk the verification list: docs/AWS_STAGING_CHECKLIST.md §4
  - Stop it when you are done testing to keep costs near zero:
      docker compose down   &&   (then stop the EC2 instance in the console)
EOF
