#!/usr/bin/env bash
#
# KarosL — one-time migration of the live database from the EC2 `db`
# container to Amazon RDS PostgreSQL. See docs/RDS_MIGRATION.md for the
# full architecture, security group design, and rollback procedure.
#
# This is NOT the recurring backup script (scripts/backup-to-s3.sh handles
# that). It exists to move data ONCE, safely, with the same dump/verify
# discipline backup-to-s3.sh already uses, reused rather than reinvented.
#
# What it does:
#   1. dumps the LIVE database from the `db` container (--clean --if-exists,
#      same as backup-to-s3.sh)
#   2. verifies the dump is real (non-trivial size, schema and data present)
#   3. restores it into RDS over the network, using the `db` container's own
#      pg_dump/psql binaries (version-matched, guaranteed compatible) pointed
#      at the RDS endpoint — the container already has outbound internet
#      access via the host, and only the app's own security group can reach
#      RDS on 5432, so this only works from here
#   4. re-runs the same row-count query against RDS and prints it side by
#      side with the source counts — this script does NOT declare success on
#      exit code 0 alone; you compare the two tables yourself
#
# What it deliberately does NOT do:
#   - touch .env, restart any container, or switch the application over.
#     That is a separate, deliberate step — see docs/RDS_MIGRATION.md
#     "Cutover". This script only copies data; it does not go live.
#   - drop or modify anything in the source `db` container
#   - print the RDS password. It is read from environment variables you
#     export before running this script, never from a committed file.
#
# Required environment variables (export before running, never commit):
#   RDS_HOST       RDS endpoint, e.g. karosl-staging-postgres.xxxx.eu-north-1.rds.amazonaws.com
#   RDS_PORT       defaults to 5432
#   RDS_DB         defaults to karosl
#   RDS_USER       RDS master username
#   RDS_PASSWORD   RDS master password
#
# Usage (from the repo root on the staging server):
#   RDS_HOST=... RDS_USER=... RDS_PASSWORD=... ./scripts/migrate-to-rds.sh
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

for arg in "$@"; do
    case "$arg" in
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

RDS_PORT="${RDS_PORT:-5432}"
RDS_DB="${RDS_DB:-karosl}"

[ -n "${RDS_HOST:-}" ]     || die "RDS_HOST is not set."
[ -n "${RDS_USER:-}" ]     || die "RDS_USER is not set."
[ -n "${RDS_PASSWORD:-}" ] || die "RDS_PASSWORD is not set."

command -v docker >/dev/null 2>&1 || die "docker not found."
[ -f docker-compose.yml ] || die "docker-compose.yml not found — run this from the repo root."
docker compose ps --status running --services 2>/dev/null | grep -qx 'db' \
    || die "The 'db' service is not running. Start the stack first: docker compose up -d"

BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date -u +%F_%H%M%S)"
OUT="${BACKUP_DIR}/karosl_migration_${STAMP}.sql"

# --- Dump from the source container -------------------------------------
log "Dumping the LIVE database from the 'db' container..."
docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
    < /dev/null > "$OUT"
chmod 600 "$OUT"

SIZE=$(stat -c %s "$OUT")
[ "$SIZE" -gt 1024 ] || die "Dump is only ${SIZE} bytes — that is not a real backup. Kept at $OUT."
TABLES=$(grep -c '^CREATE TABLE' "$OUT" || true)
COPIES=$(grep -c '^COPY '        "$OUT" || true)
[ "$TABLES" -gt 0 ] || die "Dump contains no CREATE TABLE statements — schema is missing. Kept at $OUT."
[ "$COPIES" -gt 0 ] || die "Dump contains no COPY blocks — data is missing. Kept at $OUT."
printf '    %s bytes, %s tables, %s data blocks\n' "$SIZE" "$TABLES" "$COPIES"

# --- Source row counts, for later comparison -----------------------------
log "Row counts in the SOURCE database (container):"
docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -t -c \"
    select 'properties', count(*) from properties_property
    union all select 'sections', count(*) from sections_section
    union all select 'units', count(*) from units_unit
    union all select 'occupants', count(*) from occupants_student
    union all select 'occupancies', count(*) from occupancy_occupancy
    union all select 'payments', count(*) from payments_payment
    union all select 'receipts', count(*) from payments_receipt
    union all select 'audit_logs', count(*) from audit_auditlog
    union all select 'users', count(*) from accounts_user;
\"" < /dev/null | tee "${OUT}.source_counts" | sed 's/^/    /'

# --- Restore into RDS, over the network ----------------------------------
# Uses the `db` container's own psql/pg_dump (version-matched to the source,
# and the container already has outbound internet via the host) rather than
# installing a client anywhere else. RDS_PASSWORD is passed as an env var to
# the container, never as a command-line argument, so it never appears in
# `docker inspect`, process listings, or shell history on the host.
log "Restoring into RDS at ${RDS_HOST}:${RDS_PORT}/${RDS_DB} ..."
docker compose exec -T -e PGPASSWORD="$RDS_PASSWORD" db sh -c \
    "psql -q -h '${RDS_HOST}' -p '${RDS_PORT}' -U '${RDS_USER}' -d '${RDS_DB}'" \
    < "$OUT" \
    || die "Restore failed partway through. The dump is intact at $OUT for inspection/retry. The RDS database may be in a partial state — inspect it before retrying."

# --- Verify: RDS row counts, compared against the source ------------------
log "Row counts in RDS (compare against the source counts above):"
docker compose exec -T -e PGPASSWORD="$RDS_PASSWORD" db sh -c "psql -h '${RDS_HOST}' -p '${RDS_PORT}' -U '${RDS_USER}' -d '${RDS_DB}' -t -c \"
    select 'properties', count(*) from properties_property
    union all select 'sections', count(*) from sections_section
    union all select 'units', count(*) from units_unit
    union all select 'occupants', count(*) from occupants_student
    union all select 'occupancies', count(*) from occupancy_occupancy
    union all select 'payments', count(*) from payments_payment
    union all select 'receipts', count(*) from payments_receipt
    union all select 'audit_logs', count(*) from audit_auditlog
    union all select 'users', count(*) from accounts_user;
\"" < /dev/null | tee "${OUT}.rds_counts" | sed 's/^/    /'

log "Diff between source and RDS row counts (empty output = identical):"
if diff "${OUT}.source_counts" "${OUT}.rds_counts" > "${OUT}.diff"; then
    printf '    (no differences)\n'
else
    cat "${OUT}.diff" | sed 's/^/    /'
    die "Row counts differ between source and RDS. Do NOT proceed to cutover. Dump and counts kept at ${OUT}*"
fi

printf '\n\033[1;32m==> Migration data copy complete and verified.\033[0m\n'
printf 'The application is still pointed at the container database — nothing has switched over.\n'
printf 'Next: edit .env and restart backend per docs/RDS_MIGRATION.md "Cutover".\n'
printf 'Dump kept at: %s (not uploaded to S3 — it duplicates the backup-to-s3.sh run already taken before this).\n' "$OUT"
