#!/usr/bin/env bash
#
# KarosL — roll the staging deployment back to the previous known-good commit.
#
# Reads ~/.karosl-deploy-history (written by scripts/deploy-staging.sh on
# every successful deploy) to find "the commit before the current one"
# without you needing to remember or look it up, checks it out, rebuilds,
# and restarts — the same mechanism as a forward deploy, just pointed
# backward. There is no container registry (docs/CI_CD.md's documented
# tradeoff), so this is "rebuild the old commit," not an instant image swap.
#
# What it does:
#   1. determines the rollback target: the second-to-last entry in
#      ~/.karosl-deploy-history (the one before the current deploy), or an
#      explicit --to=<sha>
#   2. checks out that commit (detached HEAD — a rollback target is a specific
#      point in history, not a branch tip)
#   3. docker compose build && docker compose up -d — ALWAYS with the https +
#      cloudwatch overlays applied if the target commit ships them (see
#      "Compose file set" below)
#   4. waits for health, checks /api/health/
#   5. records the rollback in ~/.karosl-deploy-history too, so a second
#      rollback (or a subsequent forward deploy) has an accurate history
#
# What it deliberately does NOT do:
#   - touch the database, volumes, or run `down -v` — a rollback that lost
#     data would be worse than the problem it was trying to fix
#   - attempt to reverse migrations. Django migrations are forward-only here;
#     rolling back to older code while the database already has newer
#     migrations applied is a real, known limitation of code-only rollback
#     (docs/CI_CD.md) — this script warns about it rather than guessing at
#     an automated migration downgrade, which would risk being genuinely
#     destructive to real data.
#   - delete or prune anything — old images/containers are left alone
#
# Usage (from the repo root on the staging server):
#   ./scripts/rollback-staging.sh                    # roll back to the previous recorded deploy
#   ./scripts/rollback-staging.sh --to=<sha>          # roll back to a specific commit
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET_SHA=""
for arg in "$@"; do
    case "$arg" in
        --to=*)  TARGET_SHA="${arg#--to=}" ;;
        --to)    die "--to requires a value, e.g. --to=abc1234" ;;
        -h|--help) sed -n '2,39p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

HISTORY_FILE="$HOME/.karosl-deploy-history"

# --- Determine the target ----------------------------------------------------
if [ -z "$TARGET_SHA" ]; then
    [ -f "$HISTORY_FILE" ] || die "No $HISTORY_FILE found — nothing to roll back to.
Pass an explicit target: ./scripts/rollback-staging.sh --to=<sha>"

    # The last line is the CURRENT deploy; the one before it is the rollback
    # target. tail -2 | head -1 gets the second-to-last line without needing
    # to know the file's total length.
    LINE_COUNT=$(wc -l < "$HISTORY_FILE")
    [ "$LINE_COUNT" -ge 2 ] || die "Only ${LINE_COUNT} entry in $HISTORY_FILE — no previous deploy recorded to roll back to.
Pass an explicit target: ./scripts/rollback-staging.sh --to=<sha>"

    TARGET_SHA=$(tail -2 "$HISTORY_FILE" | head -1 | awk '{print $2}')
    [ -n "$TARGET_SHA" ] || die "Could not parse a commit SHA from $HISTORY_FILE — it may be corrupted.
Pass an explicit target: ./scripts/rollback-staging.sh --to=<sha>"
fi

CURRENT_SHA=$(git rev-parse HEAD)
log "Current:  ${CURRENT_SHA}"
log "Rollback target: ${TARGET_SHA}"

[ "$CURRENT_SHA" != "$TARGET_SHA" ] || die "Already at ${TARGET_SHA} — nothing to roll back."

git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null \
    || die "${TARGET_SHA} is not a commit this repo knows about. Try 'git fetch' first, or check the SHA."

[ -f .env ] || die ".env not found in $REPO_ROOT — this script must run on the staging server, from the repo root."
[ -f docker-compose.yml ] || die "docker-compose.yml not found — run this from the repo root."

# --- Migration compatibility warning -----------------------------------------
# This script cannot safely determine whether the target commit's code is
# compatible with whatever migrations are already applied to the live
# database. It is not attempting to guess or auto-downgrade — see the header.
warn "This rolls back CODE ONLY. If a migration was applied since ${TARGET_SHA}, the"
warn "older code may not match the current database schema. Check"
warn "  git log ${TARGET_SHA}..${CURRENT_SHA} --oneline -- backend/apps/*/migrations/"
warn "before proceeding if you are not sure. Ctrl-C now to abort."
sleep 5

# --- Checkout -----------------------------------------------------------------
# Deliberately checks for MODIFIED TRACKED files only, not untracked ones —
# `git checkout` never touches untracked files (a stray .env.bak-* or a
# scratch script sitting in the repo root is harmless and none of this
# script's business), so `git status --porcelain` alone is the wrong check:
# it flags untracked clutter as a reason to refuse, which is a real false
# positive found while testing this script for the first time.
if ! git diff --quiet || ! git diff --cached --quiet; then
    die "Working tree has uncommitted changes to tracked files — refusing to check out a different commit.
Nothing has been touched. Resolve (commit, stash, or discard) and re-run:
$(git diff --name-only; git diff --cached --name-only)"
fi

log "Checking out ${TARGET_SHA} (detached HEAD)..."
git checkout --detach "$TARGET_SHA"

# --- Compose file set ---------------------------------------------------
# CRITICAL, and evaluated ONLY after the checkout above: a plain base-only
# `docker compose up -d` silently drops port 443 and the CloudWatch logging
# driver — this exact mistake took staging's HTTPS down for several minutes
# during scripts/deploy-staging.sh's own testing on 2026-08-19. Checked after
# checkout, not before, so this reflects what the ROLLBACK TARGET commit
# actually ships, not whatever was checked out when the script started (an
# old-enough target might legitimately predate one of these overlay files).
COMPOSE_FILES=(-f docker-compose.yml)
[ -f docker-compose.https.yml ] && COMPOSE_FILES+=(-f docker-compose.https.yml)
[ -f docker-compose.cloudwatch.yml ] && COMPOSE_FILES+=(-f docker-compose.cloudwatch.yml)
# RDS overlay: gated on .env's actual DB_HOST, not merely the file's presence
# — see the matching comment in deploy-staging.sh and docs/RDS_MIGRATION.md.
_db_host=$(grep -E '^DB_HOST=' .env | head -1 | cut -d= -f2- || true)
if [ -f docker-compose.rds.yml ] && [ -n "$_db_host" ] && [ "$_db_host" != "db" ]; then
    COMPOSE_FILES+=(-f docker-compose.rds.yml)
fi
log "Compose files: ${COMPOSE_FILES[*]}"

# --- Rebuild and restart ------------------------------------------------------
log "Building images for the rollback target..."
docker compose "${COMPOSE_FILES[@]}" build

log "Restarting services..."
# See the matching comment in deploy-staging.sh — once the old container-
# Postgres `db` service is decommissioned, a blanket `up -d` would silently
# recreate it via `backend`'s depends_on. --no-deps is the same idiom used
# during the original RDS cutover (docs/RDS_MIGRATION.md).
if [ -n "$_db_host" ] && [ "$_db_host" != "db" ]; then
    docker compose "${COMPOSE_FILES[@]}" up -d --no-deps backend frontend
else
    docker compose "${COMPOSE_FILES[@]}" up -d
fi

log "Waiting for services to report healthy (up to 120s)..."
deadline=$((SECONDS + 120))
while [ $SECONDS -lt $deadline ]; do
    if ! docker compose "${COMPOSE_FILES[@]}" ps --format '{{.Health}}' 2>/dev/null | grep -q 'starting'; then
        break
    fi
    sleep 5
done

log "Service status:"
docker compose "${COMPOSE_FILES[@]}" ps

# --- Verify -----------------------------------------------------------------
# Content-based check, not exit-code-based — see scripts/deploy-staging.sh for
# why: with the https overlay, port 80 301s to 443, and `curl -f` does not
# treat a 301 as failure, so an exit-code-only check would report success on
# a redirect page it never actually followed.
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
    printf '\n\n\033[1;32m==> Rollback complete. Stack is up and healthy at %s.\033[0m\n' "$TARGET_SHA"
    printf '%s ROLLBACK-TO %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TARGET_SHA" >> "$HISTORY_FILE"
else
    printf '\n'
    warn "Health check did not return OK after rollback. The stack may still be starting, or the"
    warn "rollback target itself is unhealthy. Investigate with:"
    warn "  docker compose ${COMPOSE_FILES[*]} ps"
    warn "  ./scripts/docker-logs.sh backend --tail 50"
    exit 1
fi

cat <<EOF

Currently on a DETACHED HEAD at ${TARGET_SHA}, not a branch. To roll forward again once fixed:
  git checkout cloud-deployment && ./scripts/deploy-staging.sh --pull
EOF
