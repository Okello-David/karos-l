#!/usr/bin/env bash
#
# KarosL — build and (re)start the staging Docker Compose stack.
#
# Originally an OPTIONAL convenience wrapper around the commands in
# docs/AWS_EC2_DEPLOYMENT.md §6 and §12 — now also what
# .github/workflows/deploy-staging.yml runs over SSH (docs/CI_CD.md). Every
# step is still a plain command you could type yourself; nothing here is
# magic CI-only behavior.
#
# What it does:
#   1. sanity-checks that .env exists and looks like a staging config
#   2. verifies the checked-out branch is the deploy branch (--branch to
#      override for a deliberate manual deploy of something else)
#   3. optionally `git pull` (--pull)
#   4. takes a pre-deploy backup via scripts/backup-to-s3.sh (--no-backup to skip)
#   5. docker compose build, ALWAYS with the https + cloudwatch overlays applied
#      (see "Compose file set" below — a plain base-only `up -d` silently drops
#      port 443 and log shipping; this took staging's HTTPS down for several
#      minutes during this script's own testing on 2026-08-19 before being
#      caught and fixed, so this is not a hypothetical warning)
#   6. docker compose up -d, same file set
#   7. waits for all services to report healthy
#   8. runs migrations as an explicit, visible step (belt-and-braces: the
#      entrypoint already does this on container start — see below — but a
#      dedicated step gives migration output its own clearly-labeled section
#      in CI logs rather than being buried in container startup output)
#   9. curls /api/health/
#  10. records the deployed commit SHA to ~/.karosl-deploy-history, which
#      scripts/rollback-staging.sh reads
#
# What it deliberately does NOT do — all of these are destructive or
# security-sensitive, and stay manual and deliberate:
#   - `docker compose down -v`  (would delete the database)
#   - `docker system prune`     (would remove images/cache beyond this project)
#   - create or edit .env, or print any secret
#   - create a superuser, or run any data-modifying management command
#   - `git checkout` to someone else's branch/commit without --branch/--pull
#     saying so explicitly (never silently discards your changes)
#
# Migrations still ALSO run automatically: backend/docker-entrypoint.sh runs
# `migrate` on every backend container start, and Django's migration runner
# is idempotent, so running it twice (once via the entrypoint, once via this
# script's explicit step) is harmless — a failure in either place fails the
# deploy.
#
# Usage (from the repo root on the staging server):
#   ./scripts/deploy-staging.sh            # build + up -d + verify
#   ./scripts/deploy-staging.sh --pull     # git pull first, then the above
#   ./scripts/deploy-staging.sh --pull --no-backup   # skip the pre-deploy backup (fast manual iteration)
#   ./scripts/deploy-staging.sh --branch=some-other-branch --pull   # deliberate deploy of a non-default branch (note: flags take "=value")
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DO_PULL=false
DO_BACKUP=true
EXPECTED_BRANCH="cloud-deployment"
for arg in "$@"; do
    case "$arg" in
        --pull) DO_PULL=true ;;
        --no-backup) DO_BACKUP=false ;;
        --branch=*) EXPECTED_BRANCH="${arg#--branch=}" ;;
        --branch) die "--branch requires a value, e.g. --branch=cloud-deployment" ;;
        -h|--help) sed -n '2,52p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

# --- Branch check -------------------------------------------------------
# The one thing this script refuses to do silently: deploy whatever happens
# to be checked out without confirming it's the branch staging is meant to
# track. --branch=<name> makes deploying something else a deliberate,
# explicit act instead of an accident.
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] \
    || die "On branch '${CURRENT_BRANCH}', expected '${EXPECTED_BRANCH}'.
Pass --branch=${CURRENT_BRANCH} if this is deliberate, or check out ${EXPECTED_BRANCH} first."

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

# --- Compose file set ---------------------------------------------------
# CRITICAL: staging runs with the HTTPS and CloudWatch overlays applied
# (docs/HTTPS_IP_CERTIFICATE.md, docs/CLOUDWATCH_MONITORING.md) — plain
# `docker compose up -d` with only the base file drops port 443 and the
# awslogs logging driver entirely, recreating containers WITHOUT them. This
# is not hypothetical: it happened during this script's own testing on
# 2026-08-19 and took HTTPS down for several minutes before being caught and
# fixed. Every docker compose invocation below MUST use $COMPOSE_FILES.
COMPOSE_FILES=(-f docker-compose.yml)
[ -f docker-compose.https.yml ] && COMPOSE_FILES+=(-f docker-compose.https.yml)
[ -f docker-compose.cloudwatch.yml ] && COMPOSE_FILES+=(-f docker-compose.cloudwatch.yml)
# RDS overlay: gated on .env's actual DB_HOST, not merely the file's presence.
# docker-compose.yml hardcodes DB_HOST=db/DB_PORT=5432 in its own environment:
# block, which beats env_file — applying this overlay while DB_HOST is unset
# would set DB_HOST to an empty string and break the container-Postgres path.
# See docker-compose.rds.yml and docs/RDS_MIGRATION.md.
_db_host=$(grep -E '^DB_HOST=' .env | head -1 | cut -d= -f2- || true)
if [ -f docker-compose.rds.yml ] && [ -n "$_db_host" ] && [ "$_db_host" != "db" ]; then
    COMPOSE_FILES+=(-f docker-compose.rds.yml)
fi
log "Compose files: ${COMPOSE_FILES[*]}"

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

# --- Pre-deploy backup -------------------------------------------------------
# Before the new code's migrations touch the schema. Reuses today's backup
# work rather than duplicating it — see docs/S3_BACKUP_ARCHITECTURE.md.
if [ "$DO_BACKUP" = true ]; then
    log "Taking a pre-deploy backup..."
    if [ -x ./scripts/backup-to-s3.sh ]; then
        ./scripts/backup-to-s3.sh || warn "Pre-deploy backup failed — continuing anyway (deploy is not blocked on it), but check why."
    else
        warn "scripts/backup-to-s3.sh not found or not executable — skipping pre-deploy backup."
    fi
else
    warn "--no-backup: skipping the pre-deploy backup."
fi

# --- Build and start --------------------------------------------------------
log "Building images (first build on a small instance can take 5-15 minutes)..."
docker compose "${COMPOSE_FILES[@]}" build

log "Starting services..."
docker compose "${COMPOSE_FILES[@]}" up -d

# --- Wait for health --------------------------------------------------------
log "Waiting for services to report healthy (up to 120s)..."
deadline=$((SECONDS + 120))
while [ $SECONDS -lt $deadline ]; do
    # A service is "settled" once no container is still in the "starting" state.
    if ! docker compose "${COMPOSE_FILES[@]}" ps --format '{{.Health}}' 2>/dev/null | grep -q 'starting'; then
        break
    fi
    sleep 5
done

log "Service status:"
docker compose "${COMPOSE_FILES[@]}" ps

# --- Migrations (explicit, visible step) ------------------------------------
# backend/docker-entrypoint.sh already ran `migrate --noinput` when the
# container started, above — if that failed, the container never reached a
# healthy state and the wait loop above already reflects it. This re-run is
# purely for CI-log clarity (Task 7: "capture migration output in CI logs" as
# its own labeled section) and costs nothing extra: Django's migration
# runner is idempotent, a second run against an already-migrated database
# does nothing and exits 0.
log "Confirming migrations (idempotent; already applied by the container's own startup)..."
docker compose "${COMPOSE_FILES[@]}" exec -T backend python manage.py migrate --noinput \
    || die "Migrations failed. This is NOT a destructive operation — nothing was rolled back — but the
deploy cannot be considered healthy. Check: docker compose ${COMPOSE_FILES[*]} logs backend --tail 100"

# --- Verify -----------------------------------------------------------------
# Hit the app through nginx exactly as a browser would, so this exercises the
# whole chain: nginx -> gunicorn -> postgres.
#
# When the https overlay is active, SECURE_SSL_REDIRECT makes port 80 301 to
# 443 for everything except /healthz and the ACME path (staging-https.conf.template)
# — so checking plain http://localhost/api/health/ would just fetch a
# redirect page, not the real response. `curl -f` does NOT treat a 301 as a
# failure, so a naive exit-code check would report success while never
# having reached Django at all. Found and fixed during this script's own
# testing on 2026-08-19, alongside the missing-overlay incident above.
# Checking response CONTENT rather than trusting the exit code (same pattern
# scripts/verify-staging.sh already uses for the external check) catches both
# problems at once. -k on the HTTPS check is deliberate and safe here: the
# certificate's SAN is the public IP/hostname, not "localhost", and this is a
# loopback check on the box itself, not a path an attacker can intercept.
if [[ " ${COMPOSE_FILES[*]} " == *" docker-compose.https.yml "* ]]; then
    HEALTH_URL="https://localhost/api/health/"
    CURL_EXTRA=(-k)
else
    frontend_port=$(grep -E '^FRONTEND_PORT=' .env | head -1 | cut -d= -f2- || true)
    frontend_port=${frontend_port:-8080}
    HEALTH_URL="http://localhost:${frontend_port}/api/health/"
    CURL_EXTRA=()
fi

log "Checking ${HEALTH_URL} ..."
health_body=$(curl -fsS "${CURL_EXTRA[@]}" --max-time 10 "$HEALTH_URL" 2>/dev/null || true)
printf '%s\n' "$health_body"
if echo "$health_body" | grep -q '"status":"ok"' && echo "$health_body" | grep -q '"database":"ok"'; then
    printf '\n\n\033[1;32m==> Stack is up and the full chain (nginx -> gunicorn -> postgres) responds.\033[0m\n'

    # --- Record the deployed commit ------------------------------------------
    # scripts/rollback-staging.sh reads this to find "the commit before the
    # current one" without the operator needing to remember or look it up.
    # Append-only, never trimmed here — it's a handful of bytes per deploy.
    DEPLOYED_SHA=$(git rev-parse HEAD)
    printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$DEPLOYED_SHA" >> "$HOME/.karosl-deploy-history"
    log "Recorded ${DEPLOYED_SHA} in ~/.karosl-deploy-history"
else
    printf '\n'
    warn "Health check did not return OK. The stack may still be starting."
    warn "Investigate with:"
    warn "  docker compose ${COMPOSE_FILES[*]} ps"
    warn "  ./scripts/docker-logs.sh backend --tail 50"
    warn "See the troubleshooting section: docs/AWS_EC2_DEPLOYMENT.md §14."
    exit 1
fi

cat <<EOF

Next steps:
  - First deploy? Create the admin account:
      docker compose ${COMPOSE_FILES[*]} exec backend python manage.py createsuperuser
  - Open the app: https://<EC2_PUBLIC_IP> or the sslip.io hostname — docs/HTTPS_IP_CERTIFICATE.md
  - Walk the verification list: docs/AWS_STAGING_CHECKLIST.md §4
  - Staging now stays running continuously during Live Pilot — docs/PROJECT_STATE.md — do not stop the
    instance as a matter of routine.
EOF
