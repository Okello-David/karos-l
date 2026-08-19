#!/usr/bin/env bash
#
# KarosL — download a backup from S3 and restore it into a DISPOSABLE database.
#
# This is the automated form of the manual procedure in docs/DEVOPS.md §12 /
# docs/S3_BACKUP_ARCHITECTURE.md. It exists to prove backups are actually
# restorable, not just uploaded — an unverified backup is a hope, not a
# backup.
#
# What it does:
#   1. lists or selects a backup object from s3://$KAROSL_BACKUP_BUCKET/database/
#   2. downloads it and verifies it decompresses to a real dump (non-trivial
#      size, schema and data blocks present — same checks backup-to-s3.sh runs
#      before ever uploading)
#   3. creates a throwaway database (default: karosl_restore_test) and
#      restores the dump into THAT — never the live database
#   4. runs a row-count sanity check against the restored data and prints it
#   5. drops the throwaway database when done, unless --keep is passed
#
# What it deliberately does NOT do — this is the whole point of the script:
#   - restore into the live database. There is no flag, override, or code
#     path that does this. If --target-db is given a name that matches the
#     live POSTGRES_DB (read from the running container's own environment,
#     never from .env), the script refuses immediately and does nothing else.
#   - delete the S3 object, or any other backup
#   - print any credential
#
# A REAL production restore (replacing live data with a backup) is not what
# this script is for. It is a rare, high-stakes, human-supervised operation —
# see "Production restore (manual, deliberate)" in docs/S3_BACKUP_ARCHITECTURE.md.
#
# Monitoring: emits [EVENT] RESTORE_TEST_SUCCEEDED / RESTORE_TEST_FAILED for
# real restore attempts only (not --list, not --dry-run). See
# docs/S3_BACKUP_ARCHITECTURE.md "Monitoring preparation".
#
# Credentials: the database user is read from the container's own environment
# via peer/local-socket trust, same as backup-to-s3.sh — no password is ever
# handled by this script. AWS access comes from the EC2 instance role.
#
# Configuration (environment, or the server .env):
#   KAROSL_BACKUP_BUCKET   required. S3 bucket name. Not committed on purpose.
#   AWS_DEFAULT_REGION     optional. Defaults to eu-north-1.
#
# Usage (from the repo root on the staging server):
#   ./scripts/restore-from-s3.sh --list                  # show available backups, do nothing else
#   ./scripts/restore-from-s3.sh --latest                # restore the newest daily backup (default if no selector given)
#   ./scripts/restore-from-s3.sh --key=database/karosl_db_2026-08-19_150000.sql.gz
#   ./scripts/restore-from-s3.sh --latest --keep                  # leave the disposable database up for inspection
#   ./scripts/restore-from-s3.sh --latest --target-db=my_check_db  # flags take "=value", not a separate argument
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }
event() { printf '[EVENT] %s\n' "$1"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LIST_ONLY=false
LATEST=false
KEY=""
TARGET_DB="karosl_restore_test"
KEEP=false

for arg in "$@"; do
    case "$arg" in
        --list)          LIST_ONLY=true ;;
        --latest)        LATEST=true ;;
        --key=*)         KEY="${arg#--key=}" ;;
        --key)           die "--key requires a value, e.g. --key=database/karosl_db_...sql.gz" ;;
        --target-db=*)   TARGET_DB="${arg#--target-db=}" ;;
        --target-db)     die "--target-db requires a value" ;;
        --keep)          KEEP=true ;;
        --dry-run)       DRY_RUN=true ;;
        -h|--help)       sed -n '2,49p' "$0"; exit 0 ;;
        *)                die "Unknown argument '$arg'. Try --help." ;;
    esac
done
DRY_RUN="${DRY_RUN:-false}"

# --target-db must be a plain SQL identifier — this also happens to close off
# any injection concerns from interpolating it into the psql commands below.
[[ "$TARGET_DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] \
    || die "--target-db '${TARGET_DB}' is not a plain identifier (letters, digits, underscore, not starting with a digit)."

# --- Configuration ------------------------------------------------------
if [ -z "${KAROSL_BACKUP_BUCKET:-}" ] && [ -f .env ]; then
    KAROSL_BACKUP_BUCKET=$(grep -E '^KAROSL_BACKUP_BUCKET=' .env | head -1 | cut -d= -f2- || true)
fi
BUCKET="${KAROSL_BACKUP_BUCKET:-}"
REGION="${AWS_DEFAULT_REGION:-eu-north-1}"
[ -n "$BUCKET" ] || die "KAROSL_BACKUP_BUCKET is not set. Set it in the environment or the server .env."

# --- Preconditions -------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found."
docker compose version >/dev/null 2>&1 || die "The Docker Compose v2 plugin is missing."
command -v aws >/dev/null 2>&1 || die "The AWS CLI is not installed."
[ -f docker-compose.yml ] || die "docker-compose.yml not found — run this from the repo root."
docker compose ps --status running --services 2>/dev/null | grep -qx 'db' \
    || die "The 'db' service is not running. Start the stack first: docker compose up -d"

# --- List available backups ----------------------------------------------
if [ "$LIST_ONLY" = true ]; then
    log "Backups under s3://${BUCKET}/database/ ..."
    aws s3 ls "s3://${BUCKET}/database/" --recursive --region "$REGION" \
        | sort -k1,2 \
        || die "Could not list s3://${BUCKET}/database/"
    exit 0
fi

# --- Select the backup to restore -----------------------------------------
if [ -z "$KEY" ]; then
    LATEST=true   # --latest is the default selector when none is given
fi

if [ -n "$KEY" ] && [ "$LATEST" = true ]; then
    die "Pass either --key or --latest, not both."
fi

if [ "$LATEST" = true ]; then
    log "Finding the newest daily backup (excludes database/monthly/)..."
    KEY=$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "database/" --region "$REGION" \
        --query "sort_by(Contents[?!starts_with(Key, 'database/monthly/')], &LastModified)[-1].Key" \
        --output text 2>/dev/null || true)
    [ -n "$KEY" ] && [ "$KEY" != "None" ] \
        || die "No backups found under s3://${BUCKET}/database/. Run ./scripts/backup-to-s3.sh first."
fi
log "Selected: s3://${BUCKET}/${KEY}"

# --- Guardrail: never the live database ------------------------------------
# Read the live database name from the container's own environment — never
# from .env, and never trust a flag alone to decide this.
LIVE_DB=$(docker compose exec -T db sh -c 'echo "$POSTGRES_DB"' < /dev/null 2>/dev/null || true)
if [ -n "$LIVE_DB" ] && [ "$TARGET_DB" = "$LIVE_DB" ]; then
    die "--target-db '${TARGET_DB}' is the LIVE database. Refusing.
This script only ever restores into a disposable database it creates itself.
A real production restore is a separate, manual, human-supervised procedure —
see docs/S3_BACKUP_ARCHITECTURE.md, 'Production restore (manual, deliberate)'."
fi
[ "$TARGET_DB" != "postgres" ] || die "--target-db 'postgres' is the system default database. Refusing."

if [ "$DRY_RUN" = true ]; then
    log "--dry-run: would download ${KEY}, restore into '${TARGET_DB}', verify, then $( [ "$KEEP" = true ] && echo 'keep it' || echo 'drop it' )."
    exit 0
fi

# From here on this is a real restore-test attempt — any non-zero exit is a
# failed one. --list and --dry-run never reach this point, so neither emits
# an event; only genuine attempts do.
RESTORE_STAGE="download"
on_exit() {
    local rc=$?
    [ "$rc" -eq 0 ] && return
    event "RESTORE_TEST_FAILED stage=${RESTORE_STAGE}"
}
trap on_exit EXIT

# --- Download ---------------------------------------------------------------
BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
GZ_FILE="${BACKUP_DIR}/$(basename "$KEY")"

log "Downloading s3://${BUCKET}/${KEY} ..."
aws s3 cp "s3://${BUCKET}/${KEY}" "$GZ_FILE" --region "$REGION" --only-show-errors \
    || die "Download failed."
chmod 600 "$GZ_FILE"

# --- Decompress and verify ---------------------------------------------------
RESTORE_STAGE="decompress_verify"
SQL_FILE="${GZ_FILE%.gz}"
log "Decompressing..."
gunzip -kf "$GZ_FILE"   # -k: keep the .gz too, in case this file is inspected again
[ -f "$SQL_FILE" ] || die "Decompression did not produce ${SQL_FILE}."
chmod 600 "$SQL_FILE"

log "Verifying the dump..."
SIZE=$(stat -c %s "$SQL_FILE")
[ "$SIZE" -gt 1024 ] || die "Dump is only ${SIZE} bytes — that is not a real backup."
TABLES=$(grep -c '^CREATE TABLE' "$SQL_FILE" || true)
COPIES=$(grep -c '^COPY '        "$SQL_FILE" || true)
[ "$TABLES" -gt 0 ] || die "Dump contains no CREATE TABLE statements — schema is missing."
[ "$COPIES" -gt 0 ] || die "Dump contains no COPY blocks — data is missing."
printf '    %s bytes, %s tables, %s data blocks\n' "$SIZE" "$TABLES" "$COPIES"

# --- Restore into the disposable database -----------------------------------
RESTORE_STAGE="create_db"
log "Creating disposable database '${TARGET_DB}'..."
docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c \"CREATE DATABASE ${TARGET_DB};\"" \
    < /dev/null || die "Could not create ${TARGET_DB}. Does it already exist? Drop it by hand first if so."

RESTORE_STAGE="restore"
log "Restoring into '${TARGET_DB}'..."
docker compose exec -T db sh -c "psql -q -U \"\$POSTGRES_USER\" -d ${TARGET_DB}" < "$SQL_FILE" \
    || die "Restore failed partway through. '${TARGET_DB}' may be in a partial state — drop it by hand:
  docker compose exec -T db sh -c 'psql -U \"\$POSTGRES_USER\" -d postgres -c \"DROP DATABASE ${TARGET_DB};\"' < /dev/null"

# --- Verify expected records --------------------------------------------------
RESTORE_STAGE="verify_records"
log "Row counts in '${TARGET_DB}' (compare against docs/PROJECT_STATE.md's known-good baseline):"
docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d ${TARGET_DB} -t -c \"
    select 'properties', count(*) from properties_property
    union all select 'sections', count(*) from sections_section
    union all select 'units', count(*) from units_unit
    union all select 'occupants', count(*) from occupants_student
    union all select 'occupancies', count(*) from occupancy_occupancy
    union all select 'payments', count(*) from payments_payment
    union all select 'receipts', count(*) from payments_receipt;
\"" < /dev/null | sed 's/^/    /'

# --- Cleanup -------------------------------------------------------------------
RESTORE_STAGE="cleanup"
if [ "$KEEP" = true ]; then
    warn "Leaving '${TARGET_DB}' in place (--keep). Drop it when done:"
    printf '  docker compose exec -T db sh -c '\''psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE %s;"'\'' < /dev/null\n' "$TARGET_DB"
else
    log "Dropping disposable database '${TARGET_DB}'..."
    docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c \"DROP DATABASE ${TARGET_DB};\"" \
        < /dev/null || warn "Could not drop ${TARGET_DB} — drop it by hand."
fi

RESTORE_STAGE="done"
event "RESTORE_TEST_SUCCEEDED key=${KEY} target_db=${TARGET_DB}"
log "Restore verification complete."
printf '    source: s3://%s/%s\n' "$BUCKET" "$KEY"
printf '    the live database was never touched by this script.\n'
