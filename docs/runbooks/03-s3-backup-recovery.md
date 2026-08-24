# Runbook: S3 PostgreSQL Backup Recovery

**Covers:** restoring the `pg_dump`-based S3 backup into a disposable database, for verification, data
recovery, or as the primary recovery path if RDS itself is unavailable/destroyed. **This is the one recovery
path in the entire DR sprint that was actually executed and measured** — see
`docs/DISASTER_RECOVERY.md` §5 for the full test record. Everything in this runbook reflects real, proven
tool behavior, not estimates.

## Symptoms / when to use this runbook
- Need to inspect historical data (e.g. "what did this record look like yesterday") without touching live
  data.
- RDS itself is unavailable and you need database contents back on *any* PostgreSQL server, fast.
- Verifying backups are actually restorable (should be done periodically — see the note on this in
  `docs/DISASTER_RECOVERY.md` §1; this was proven once but there's no recurring schedule for it yet).
- A data-corruption incident (`docs/runbooks/05-database-corruption.md`) needs a known-good copy of specific
  records to manually re-apply.

## Severity
Varies by why you're running it — this action itself is **low-risk** (the script cannot touch the live
database, by design) regardless of how severe the underlying incident is.

## Immediate actions
1. Confirm you have `KAROSL_BACKUP_BUCKET` set (or in `.env`) and working AWS credentials with
   `s3:GetObject`/`s3:ListBucket` on the bucket.
2. `./scripts/restore-from-s3.sh --list` — read-only, shows every available backup with size and key. Do
   this first regardless of urgency; it costs nothing and confirms the backup pipeline has been producing
   real objects.

## Investigation
- Check the timestamp of the most recent object under `database/` (not `database/monthly/`) — this is your
  actual current RPO right now, not the theoretical worst case.
- If you need a specific point in time rather than "the latest," use `--key=database/karosl_db_<timestamp>.sql.gz`
  from the `--list` output instead of `--latest`.

## Recovery procedure
```bash
export KAROSL_BACKUP_BUCKET="<bucket-name>"   # or set in .env
export AWS_DEFAULT_REGION="eu-north-1"

# See what's available (read-only, no side effects):
./scripts/restore-from-s3.sh --list

# Restore the newest backup into a disposable database, keep it up for inspection:
./scripts/restore-from-s3.sh --latest --target-db=karosl_dr_<date> --keep

# Or a specific backup:
./scripts/restore-from-s3.sh --key=database/karosl_db_2026-08-24_024045.sql.gz --target-db=karosl_dr_<date>
```

**What the script does, proven by actual execution during this DR pass (2026-08-24):**
1. Finds/downloads the selected backup from S3 (~1-2s for an object this size — the database is currently
   small, 9-12 KB compressed).
2. Decompresses and verifies it's a real dump (non-trivial size, contains `CREATE TABLE` and `COPY` blocks)
   — the same checks `backup-to-s3.sh` runs before ever uploading, so a corrupt/truncated backup is caught
   here, not silently "restored" as garbage.
3. Creates the disposable target database.
4. Restores into it.
5. Prints row counts for the 7 core business tables automatically.
6. **Refuses outright if `--target-db` matches the live database name** (read from the running container's
   own environment, never from a flag you could fat-finger) — there is no override for this. This is the
   guardrail that makes this script safe to run without special caution.

**Measured timing (this pass, real execution, not estimated):** `--latest` end-to-end (download → verify →
create → restore → row-count print) = **15 seconds**, against a ~12 KB compressed backup with 21 tables.

## Verification
The script's own row-count output covers 7 tables (properties, sections, units, occupants, occupancies,
payments, receipts). For a complete verification matching what this DR pass actually did, also check the two
tables the script doesn't print by default:

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" -d <target-db> -c "
SELECT 'users' AS t, COUNT(*) FROM accounts_user
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_auditlog;"
```

For real confidence (not just row counts matching — content matching), also spot-check via the Django ORM
connected to the restored database:
```bash
docker compose exec -T -e DB_NAME=<target-db> backend python manage.py shell -c "
from apps.properties.models import Property
print(Property.objects.count(), Property.objects.first().code if Property.objects.exists() else None)"
```

## Rollback
Not applicable in the destructive sense — this script never modifies the live database. To undo the
*disposable* database itself:
```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE <target-db>;"' < /dev/null
```
(The script prints this exact command for you if you passed `--keep`.)

## Escalation
If the restore itself fails (corrupt dump, decompression error, row counts look wrong), that's a real signal
the backup pipeline has a problem — treat it as a `docs/runbooks/` backup-failure investigation
(`docs/DISASTER_RECOVERY.md` §8), not just a one-off retry. Try the previous day's backup object to isolate
whether it's one bad backup or a systemic issue.

## Lessons learned
**From the actual execution during this DR pass (2026-08-24):** the script worked exactly as documented on
the first attempt, no surprises. The only manual step needed beyond the script itself was checking the two
tables (`users`, `audit_logs`) it doesn't print automatically, and the Django-ORM-layer verification — both
worth considering as small additions to the script itself in a future pass, since they're cheap to add and
would make the script's own output a complete verification report rather than a partial one.
