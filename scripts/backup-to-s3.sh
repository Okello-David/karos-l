#!/usr/bin/env bash
#
# KarosL — take a full PostgreSQL dump and upload it to S3.
#
# This is the automated form of the manual procedure in docs/DEVOPS.md §12.
# It is the ONLY complete backup KarosL has: pg_dump captures every table,
# including users, auth tokens, AuditLog, and Backup rows, all of which
# KarosL's own BackupService deliberately excludes.
#
# Designed to be run unattended by a systemd timer (deploy/systemd/), and
# by hand whenever you want a dump before doing something risky.
#
# What it does:
#   1. dumps the database from inside the running `db` container
#   2. VERIFIES the dump is real (non-trivial size, schema and data blocks)
#   3. gzips it
#   4. uploads to s3://$KAROSL_BACKUP_BUCKET/database/, confirms via head-object
#      (size + S3 VersionId, since the bucket is versioned)
#   5. copies it once more to database/monthly/<year>-<month>.sql.gz if that
#      month doesn't have one yet (S3-side copy, no second pg_dump) — the
#      longer-retained tier documented in docs/S3_BACKUP_ARCHITECTURE.md
#   6. prunes local copies, keeping the most recent $KEEP_LOCAL
#
# Older backups from before 2026-08-19 live under s3://.../pg_dump/<year>/ —
# left in place, not migrated. See docs/S3_BACKUP_ARCHITECTURE.md.
#
# What it deliberately does NOT do:
#   - restore anything, ever (see docs/DEVOPS.md §12 — a --clean restore into
#     the live database destroys everything created since the dump)
#   - delete anything in S3 (the IAM role has no s3:DeleteObject, so a
#     compromised instance cannot erase backup history; the bucket's own
#     lifecycle rule handles expiry)
#   - print any credential
#
# Monitoring: emits [EVENT] BACKUP_STARTED / BACKUP_SUCCEEDED / BACKUP_FAILED /
# UPLOAD_FAILED lines (real runs only — --dry-run emits none), landing in
# journald via the systemd timer same as everything else. See
# docs/S3_BACKUP_ARCHITECTURE.md "Monitoring preparation" for what a future
# CloudWatch Logs metric filter would match against each.
#
# Credentials: the database password is read from the container's own
# environment, so it never reaches a command line or shell history. AWS
# access comes from the EC2 instance role — there are no AWS keys on the box.
#
# Configuration (environment, or the server .env):
#   KAROSL_BACKUP_BUCKET   required. S3 bucket name. Not committed on purpose.
#   AWS_DEFAULT_REGION     optional. Defaults to eu-north-1.
#   KEEP_LOCAL             optional. Local dumps to retain. Defaults to 3.
#
# Usage (from the repo root on the staging server):
#   KAROSL_BACKUP_BUCKET=<bucket> ./scripts/backup-to-s3.sh
#   ./scripts/backup-to-s3.sh --dry-run    # dump and verify, do not upload
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }
# Machine-recognizable event marker for a future CloudWatch Logs metric
# filter (see docs/S3_BACKUP_ARCHITECTURE.md). Real runs only — --dry-run
# emits none, since it has no durable outcome worth monitoring for.
event() { [ "${DRY_RUN:-false}" = true ] && return; printf '[EVENT] %s\n' "$1"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help) sed -n '2,53p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

# Any non-zero exit from here on is a failed backup attempt. BACKUP_STAGE
# tracks where it happened so the trap can tell an upload failure (the
# backup itself was fine, S3 rejected it) from everything else.
BACKUP_STAGE="preconditions"
on_exit() {
    local rc=$?
    [ "$rc" -eq 0 ] && return
    case "$BACKUP_STAGE" in
        upload|verify_upload) event "UPLOAD_FAILED stage=${BACKUP_STAGE}" ;;
        *)                    event "BACKUP_FAILED stage=${BACKUP_STAGE}" ;;
    esac
}
trap on_exit EXIT
event "BACKUP_STARTED"

# --- Configuration ----------------------------------------------------------
# The server .env is the one place staging config already lives; read the
# bucket from there if the environment does not already carry it.
if [ -z "${KAROSL_BACKUP_BUCKET:-}" ] && [ -f .env ]; then
    KAROSL_BACKUP_BUCKET=$(grep -E '^KAROSL_BACKUP_BUCKET=' .env | head -1 | cut -d= -f2- || true)
fi
BUCKET="${KAROSL_BACKUP_BUCKET:-}"
REGION="${AWS_DEFAULT_REGION:-eu-north-1}"
KEEP_LOCAL="${KEEP_LOCAL:-3}"

BACKUP_DIR="$HOME/backups"
STAMP="$(date -u +%F_%H%M%S)"
BASENAME="karosl_db_${STAMP}.sql"
OUT="${BACKUP_DIR}/${BASENAME}"

# --- Preconditions ----------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found."
docker compose version >/dev/null 2>&1 || die "The Docker Compose v2 plugin is missing."
[ -f docker-compose.yml ] || die "docker-compose.yml not found — run this from the repo root."

docker compose ps --status running --services 2>/dev/null | grep -qx 'db' \
    || die "The 'db' service is not running. Start the stack first: docker compose up -d"

if [ "$DRY_RUN" = false ]; then
    [ -n "$BUCKET" ] || die "KAROSL_BACKUP_BUCKET is not set.
Set it in the environment or add it to the server .env (never committed):
  KAROSL_BACKUP_BUCKET=<your-bucket-name>
Or run with --dry-run to dump and verify without uploading."
    command -v aws >/dev/null 2>&1 || die "The AWS CLI is not installed. See docs/DEVOPS.md §12."
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# --- Dump -------------------------------------------------------------------
# `< /dev/null` is mandatory, not decorative: `docker compose exec -T` will
# otherwise swallow the rest of this script when it is piped or heredoc'd
# into a shell. Recorded as a real footgun in docs/DEVOPS.md §10.
#
# DB_HOST-aware: the live database moved to RDS on 2026-08-19
# (docs/RDS_MIGRATION.md) but the `db` container is deliberately kept running
# as a rollback safety net — so "is the db container running" alone can no
# longer tell this script which database is actually live. When .env's
# DB_HOST is "db" (or unset), dump the local container exactly as before.
# Otherwise, dump the remote host over the network — still using the `db`
# container's own pg_dump binary (version-matched to what created the data),
# just pointed elsewhere, and reading DB_USER/DB_PASSWORD/DB_NAME (the app's
# actual, live credentials) rather than the container's own frozen
# POSTGRES_* values. This is what makes a rollback (DB_HOST back to "db")
# restore this script's old behavior with no further changes.
BACKUP_STAGE="dump"
_db_host=$(grep -E '^DB_HOST=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -z "$_db_host" ] || [ "$_db_host" = "db" ]; then
    log "Dumping the database from the 'db' container..."
    docker compose exec -T db sh -c \
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
        < /dev/null > "$OUT"
else
    _db_port=$(grep -E '^DB_PORT=' .env | head -1 | cut -d= -f2- || echo 5432)
    _db_name=$(grep -E '^DB_NAME=' .env | head -1 | cut -d= -f2-)
    _db_user=$(grep -E '^DB_USER=' .env | head -1 | cut -d= -f2-)
    _db_password=$(grep -E '^DB_PASSWORD=' .env | head -1 | cut -d= -f2-)
    [ -n "$_db_name" ] && [ -n "$_db_user" ] && [ -n "$_db_password" ] \
        || die "DB_HOST is '${_db_host}' but DB_NAME/DB_USER/DB_PASSWORD are not all set in .env."
    log "Dumping the database from ${_db_host}:${_db_port} (DB_HOST != db, remote target)..."
    docker compose exec -T -e PGPASSWORD="$_db_password" db sh -c \
        "pg_dump -h '${_db_host}' -p '${_db_port}' -U '${_db_user}' -d '${_db_name}' --clean --if-exists" \
        < /dev/null > "$OUT"
fi
chmod 600 "$OUT"

# --- Verify -----------------------------------------------------------------
# A dump that exists but is empty is the classic silent failure: pg_dump can
# exit non-zero *after* the shell has already created the output file, and an
# unverified 0-byte file looks exactly like a successful backup in `ls`.
BACKUP_STAGE="verify_dump"
log "Verifying the dump..."
SIZE=$(stat -c %s "$OUT")
[ "$SIZE" -gt 1024 ] || die "Dump is only ${SIZE} bytes — that is not a real backup. Kept at $OUT for inspection."

TABLES=$(grep -c '^CREATE TABLE' "$OUT" || true)
COPIES=$(grep -c '^COPY '        "$OUT" || true)
[ "$TABLES" -gt 0 ] || die "Dump contains no CREATE TABLE statements — schema is missing. Kept at $OUT."
[ "$COPIES" -gt 0 ] || die "Dump contains no COPY blocks — data is missing. Kept at $OUT."

printf '    %s bytes, %s tables, %s data blocks\n' "$SIZE" "$TABLES" "$COPIES"

BACKUP_STAGE="compress"
log "Compressing..."
gzip -9 "$OUT"
OUT="${OUT}.gz"
chmod 600 "$OUT"

# --- Upload -----------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
    warn "--dry-run: not uploading. Dump kept at $OUT"
else
    BACKUP_STAGE="upload"
    KEY="database/${BASENAME}.gz"
    log "Uploading to s3://${BUCKET}/${KEY} ..."
    aws s3 cp "$OUT" "s3://${BUCKET}/${KEY}" --region "$REGION" --only-show-errors \
        || die "Upload failed. The local dump is intact at $OUT — copy it off the box by hand."

    # Confirm it actually landed, rather than trusting the exit code alone.
    # The bucket is versioned, so a real upload always has a VersionId — an
    # empty one here would mean head-object found nothing.
    BACKUP_STAGE="verify_upload"
    REMOTE_SIZE=$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --region "$REGION" \
        --query 'ContentLength' --output text 2>/dev/null || echo 0)
    [ "$REMOTE_SIZE" -gt 0 ] || die "Uploaded object is empty or unreadable in S3. Local dump kept at $OUT."
    REMOTE_VERSION=$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --region "$REGION" \
        --query 'VersionId' --output text 2>/dev/null || echo "")
    printf '    confirmed in S3: %s bytes, version %s\n' "$REMOTE_SIZE" "${REMOTE_VERSION:-<none>}"

    # Confirm it's actually encrypted, not just present — the bucket has
    # default SSE-S3 encryption, but a bucket-level setting is a policy, not
    # a guarantee about any one object; check the object itself.
    REMOTE_ENCRYPTION=$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --region "$REGION" \
        --query 'ServerSideEncryption' --output text 2>/dev/null || echo "")
    [ -n "$REMOTE_ENCRYPTION" ] && [ "$REMOTE_ENCRYPTION" != "None" ] \
        || die "Uploaded object is NOT encrypted (ServerSideEncryption empty). Check the bucket's default encryption config."
    printf '    encrypted: %s\n' "$REMOTE_ENCRYPTION"

    # --- Monthly tier: one longer-retained copy per calendar month ----------
    # S3-to-S3 copy, not a second pg_dump — cheap, and the daily object it
    # copies from has already been verified above. See
    # docs/S3_BACKUP_ARCHITECTURE.md for the retention rationale.
    MONTHLY_KEY="database/monthly/$(date -u +%Y-%m).sql.gz"
    if aws s3api head-object --bucket "$BUCKET" --key "$MONTHLY_KEY" --region "$REGION" >/dev/null 2>&1; then
        log "Monthly copy for $(date -u +%Y-%m) already exists — skipping."
    else
        log "First backup of the month — copying to s3://${BUCKET}/${MONTHLY_KEY} ..."
        aws s3 cp "s3://${BUCKET}/${KEY}" "s3://${BUCKET}/${MONTHLY_KEY}" --region "$REGION" --only-show-errors \
            && printf '    monthly copy confirmed: %s\n' "$MONTHLY_KEY" \
            || warn "Monthly copy failed — the daily backup above is still intact and complete."
    fi
fi

# --- Prune local copies -----------------------------------------------------
# S3 (with its lifecycle rule) is the durable copy; the instance only keeps a
# few recent dumps so a 10 GB root volume cannot fill up unattended.
BACKUP_STAGE="prune"
log "Pruning local dumps, keeping the newest ${KEEP_LOCAL}..."
mapfile -t OLD < <(ls -1t "$BACKUP_DIR"/karosl_db_*.sql.gz 2>/dev/null | tail -n +"$((KEEP_LOCAL + 1))")
if [ "${#OLD[@]}" -gt 0 ]; then
    printf '    removing %s old local dump(s)\n' "${#OLD[@]}"
    rm -f -- "${OLD[@]}"
fi

BACKUP_STAGE="done"
event "BACKUP_SUCCEEDED key=${KEY:-<dry-run>} bytes=${REMOTE_SIZE:-0} version=${REMOTE_VERSION:-<none>}"
log "Backup complete."
printf '    local:  %s\n' "$OUT"
[ "$DRY_RUN" = false ] && printf '    remote: s3://%s/%s\n' "$BUCKET" "$KEY"
printf '\nTo restore: ./scripts/restore-from-s3.sh --latest — always into a DISPOSABLE database, never the live one.\n'
