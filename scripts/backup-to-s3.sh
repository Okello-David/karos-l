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
#   4. uploads to s3://$KAROSL_BACKUP_BUCKET/pg_dump/<year>/
#   5. prunes local copies, keeping the most recent $KEEP_LOCAL
#
# What it deliberately does NOT do:
#   - restore anything, ever (see docs/DEVOPS.md §12 — a --clean restore into
#     the live database destroys everything created since the dump)
#   - delete anything in S3 (the IAM role has no s3:DeleteObject, so a
#     compromised instance cannot erase backup history; the bucket's own
#     lifecycle rule handles expiry)
#   - print any credential
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help) sed -n '2,42p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

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
STAMP="$(date -u +%F-%H%M%S)"
BASENAME="karosl-staging-${STAMP}.sql"
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
log "Dumping the database from the 'db' container..."
docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
    < /dev/null > "$OUT"
chmod 600 "$OUT"

# --- Verify -----------------------------------------------------------------
# A dump that exists but is empty is the classic silent failure: pg_dump can
# exit non-zero *after* the shell has already created the output file, and an
# unverified 0-byte file looks exactly like a successful backup in `ls`.
log "Verifying the dump..."
SIZE=$(stat -c %s "$OUT")
[ "$SIZE" -gt 1024 ] || die "Dump is only ${SIZE} bytes — that is not a real backup. Kept at $OUT for inspection."

TABLES=$(grep -c '^CREATE TABLE' "$OUT" || true)
COPIES=$(grep -c '^COPY '        "$OUT" || true)
[ "$TABLES" -gt 0 ] || die "Dump contains no CREATE TABLE statements — schema is missing. Kept at $OUT."
[ "$COPIES" -gt 0 ] || die "Dump contains no COPY blocks — data is missing. Kept at $OUT."

printf '    %s bytes, %s tables, %s data blocks\n' "$SIZE" "$TABLES" "$COPIES"

log "Compressing..."
gzip -9 "$OUT"
OUT="${OUT}.gz"
chmod 600 "$OUT"

# --- Upload -----------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
    warn "--dry-run: not uploading. Dump kept at $OUT"
else
    KEY="pg_dump/$(date -u +%Y)/${BASENAME}.gz"
    log "Uploading to s3://${BUCKET}/${KEY} ..."
    aws s3 cp "$OUT" "s3://${BUCKET}/${KEY}" --region "$REGION" --only-show-errors \
        || die "Upload failed. The local dump is intact at $OUT — copy it off the box by hand."

    # Confirm it actually landed, rather than trusting the exit code alone.
    REMOTE_SIZE=$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --region "$REGION" \
        --query 'ContentLength' --output text 2>/dev/null || echo 0)
    [ "$REMOTE_SIZE" -gt 0 ] || die "Uploaded object is empty or unreadable in S3. Local dump kept at $OUT."
    printf '    confirmed in S3: %s bytes\n' "$REMOTE_SIZE"
fi

# --- Prune local copies -----------------------------------------------------
# S3 (with its lifecycle rule) is the durable copy; the instance only keeps a
# few recent dumps so a 10 GB root volume cannot fill up unattended.
log "Pruning local dumps, keeping the newest ${KEEP_LOCAL}..."
mapfile -t OLD < <(ls -1t "$BACKUP_DIR"/karosl-staging-*.sql.gz 2>/dev/null | tail -n +"$((KEEP_LOCAL + 1))")
if [ "${#OLD[@]}" -gt 0 ]; then
    printf '    removing %s old local dump(s)\n' "${#OLD[@]}"
    rm -f -- "${OLD[@]}"
fi

log "Backup complete."
printf '    local:  %s\n' "$OUT"
[ "$DRY_RUN" = false ] && printf '    remote: s3://%s/%s\n' "$BUCKET" "$KEY"
printf '\nTo restore, follow docs/DEVOPS.md §12 — into a DISPOSABLE database, never over the live one.\n'
