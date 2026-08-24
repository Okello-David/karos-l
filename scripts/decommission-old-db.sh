#!/usr/bin/env bash
#
# KarosL — stop and remove the old container-Postgres `db` service, kept
# running since the 2026-08-19 RDS migration as a same-day rollback safety
# net (docs/RDS_MIGRATION.md). Run only once the documented 7-day validation
# window has passed cleanly (2026-08-19 + 7 days = 2026-08-26).
#
# What it does:
#   1. verifies .env's DB_HOST genuinely points at RDS, not "db" — refuses
#      to run otherwise, since that would mean the app is still using this
#      container and stopping it would take the site down
#   2. verifies the app's own health check reports the database as healthy
#      (i.e. RDS is confirmed working right now, before touching anything)
#   3. docker compose stop db && docker compose rm -f db
#   4. re-checks app health afterward
#
# What it deliberately does NOT do:
#   - delete the `postgres_data` volume. The container is removed; its data
#     stays on disk, untouched, as a further rollback artifact. Volume
#     deletion is a separate, later, deliberate decision — not bundled here.
#   - edit docker-compose.yml or any compose file. The `db` service
#     definition stays (local dev's non-RDS path still needs it); this
#     script only stops the currently-running staging instance of it.
#     deploy-staging.sh/rollback-staging.sh/recover-staging.sh already know
#     not to recreate it once DB_HOST points at RDS (--no-deps backend
#     frontend), so it won't silently come back on the next deploy.
#
# Usage (from the repo root on the staging server, or via
# .github/workflows/decommission-old-db.yml on the self-hosted runner):
#   ./scripts/decommission-old-db.sh
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

[ -f .env ] || die ".env not found — run this from the repo root on the staging server."
[ -f docker-compose.yml ] || die "docker-compose.yml not found."

docker compose version >/dev/null 2>&1 \
    || die "docker compose (v2, no hyphen) not found."

# --- 1. Confirm RDS is genuinely in use -------------------------------------
_db_host=$(grep -E '^DB_HOST=' .env | head -1 | cut -d= -f2- || true)
if [ -z "$_db_host" ] || [ "$_db_host" = "db" ]; then
    die "DB_HOST in .env is '$_db_host', not an RDS endpoint. The app is still
using the 'db' container as its live database — stopping it now would take
the site down. Refusing to proceed."
fi
log "Confirmed: DB_HOST=$_db_host (RDS, not the local container)."

# --- 2. Confirm the app is healthy against RDS, right now -------------------
if ! command -v curl >/dev/null 2>&1; then
    warn "curl not found — skipping the pre-flight health check. Verify manually before proceeding."
else
    health=$(curl -fsSk --max-time 10 https://localhost/api/health/ 2>/dev/null || true)
    case "$health" in
        *'"database":"ok"'*) log "Confirmed: /api/health/ reports the database healthy." ;;
        *) die "The app's own health check does not report the database as healthy
right now (got: '$health'). Do not proceed — investigate first." ;;
    esac
fi

# --- 3. Is the db container even running? -----------------------------------
if ! docker compose ps db --status running 2>/dev/null | grep -q db; then
    warn "'db' container is not currently running — nothing to stop. Removing any stopped/leftover container anyway."
fi

# --- 4. Stop and remove the container (never the volume) --------------------
log "Stopping 'db'..."
docker compose stop db

log "Removing the 'db' container (the postgres_data volume is left untouched)..."
docker compose rm -f db

# --- 5. Re-verify health after the change ------------------------------------
if command -v curl >/dev/null 2>&1; then
    log "Re-checking app health after removal..."
    sleep 2
    health=$(curl -fsSk --max-time 10 https://localhost/api/health/ 2>/dev/null || true)
    case "$health" in
        *'"database":"ok"'*) log "Confirmed: app is still healthy against RDS after removing the old container." ;;
        *) die "Health check failed AFTER removing the container (got: '$health'). This
should not be possible if step 2 passed, since the app was already using RDS
exclusively — investigate immediately. The container has already been
removed; docker-compose.yml still defines the service if it needs to be
brought back manually while you investigate (docker compose up -d db)." ;;
    esac
fi

log "Done. The old 'db' container is stopped and removed."
log "The 'postgres_data' volume was NOT deleted — it remains as a rollback"
log "artifact until a separate, deliberate decision is made to remove it too"
log "(see docs/RDS_MIGRATION.md)."
