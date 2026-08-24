# Runbook: RDS Recovery

**Covers:** recovering the database via RDS's own native automated-backup / point-in-time-recovery
mechanism. For the S3 `pg_dump` restore path instead (portable, proven, works even if RDS itself is
destroyed), see `docs/runbooks/03-s3-backup-recovery.md`.

**Honest status of this runbook: written from AWS's documented RDS restore behavior and this project's own
proven RDS-cutover pattern (`docker-compose.rds.yml`, used once already during the original migration), but
the specific restore-and-repoint sequence below has NOT been executed end-to-end during this DR pass** —
doing so requires creating a temporary second RDS instance, which was deliberately not done without asking
first (see `docs/DISASTER_RECOVERY.md` §1). Treat timings here as estimates, not measurements.

## Symptoms
- RDS instance shows `failed`, `incompatible-restore`, or another non-`available` status in
  `aws rds describe-db-instances`.
- Application health check fails specifically on the `"database"` field (not TLS, not the app container
  itself) — confirms this is a database-layer problem, not EC2/network.
- Data corruption discovered that's too broad or too old for the audit-log-plus-manual-fix approach in
  `docs/runbooks/05-database-corruption.md` — i.e. you need to go back to a specific point in time, not fix
  a handful of rows.

## Severity
**Critical** if the instance is genuinely lost/corrupted. **Medium** if this is a targeted PITR for a
data-corruction incident (the app can keep running against the current instance while you restore
separately for comparison/recovery).

## Immediate actions
1. Confirm current instance status: `aws rds describe-db-instances --db-instance-identifier
   karosl-staging-postgres --query 'DBInstances[].{Status:DBInstanceStatus,Endpoint:Endpoint.Address}'`.
2. **Do not delete or modify the existing instance** while investigating — deletion protection is on, which
   already prevents accidental deletion, but confirm no one is about to force it off.
3. If this is a "need to go back in time" scenario (not an instance failure), consider whether
   `docs/runbooks/03-s3-backup-recovery.md`'s disposable-restore path answers the question first — it's
   faster to execute (proven: 15 seconds) and doesn't require creating a new RDS instance at all. Reserve
   this runbook for when RDS-native PITR is genuinely the right tool (need a point in time *between* daily
   S3 snapshots, or the RDS instance itself is the thing that's broken).

## Investigation
- `aws rds describe-db-instances` for current state and any `StatusInfos` detail.
- `aws rds describe-events --source-identifier karosl-staging-postgres --source-type db-instance` for the
  event history leading up to the problem.
- `aws rds describe-db-snapshots --db-instance-identifier karosl-staging-postgres` to see what automated
  snapshots exist (1-day retention — recent, but limited) and their creation timestamps, to know your actual
  available PITR window right now.
- CloudWatch: check for any RDS-related alarm activity (note: no RDS-specific alarm currently exists — see
  `docs/DISASTER_RECOVERY.md` §8/§10 remaining risks — so this may come back empty even during a real RDS
  problem; don't mistake silence for "nothing happened").

## Recovery procedure
**RDS restores always create a brand-new instance — there is no in-place restore.** This means the
application must be repointed afterward, not just "wait for the same endpoint to come back."

1. Choose the restore point:
   - **From an automated snapshot** (simplest): `aws rds describe-db-snapshots
     --db-instance-identifier karosl-staging-postgres` to list available snapshots, pick one.
   - **Point-in-time** (any second within the 1-day retention window): use
     `aws rds restore-db-instance-to-point-in-time` with a specific `--restore-time`, or
     `--use-latest-restorable-time` for "as current as possible."
2. Restore to a **new** instance identifier (e.g. `karosl-staging-postgres-restored`) — AWS requires this,
   you cannot restore over the live instance:
   ```
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier karosl-staging-postgres \
     --target-db-instance-identifier karosl-staging-postgres-restored \
     --use-latest-restorable-time \
     --db-instance-class db.t4g.micro \
     --no-publicly-accessible
   ```
   Match the source instance's networking (VPC subnet group, security group `karosl-rds-sg`) so the
   restored instance is reachable from the same EC2 security group without extra changes.
3. Wait for the new instance to reach `available` (`aws rds wait db-instance-available
   --db-instance-identifier karosl-staging-postgres-restored`).
4. **Verify before cutting over** — do not repoint the live application until you've confirmed the restored
   data is what you expect. Options: connect directly with `psql` from the EC2 instance (temporarily, using
   the master password) and spot-check row counts/content, following the same verification pattern proven in
   `docs/runbooks/03-s3-backup-recovery.md` (row counts across all 9 record types, plus a content spot-check,
   not just counts).
5. **Cut over** — this is the step with real consequences, do it deliberately:
   - Update `.env`'s `DB_HOST` on the EC2 instance to the restored instance's new endpoint.
   - Restart the backend container (`docker compose -f docker-compose.yml -f docker-compose.rds.yml
     [...other active overlays...] up -d backend`) — do not run a full `down`/`up`, just recreate the
     backend service so it picks up the new `DB_HOST`.
6. Once confirmed stable, decide the fate of the old instance — do not delete it immediately; keep it as a
   rollback safety net for a defined window, mirroring the pattern already used for the pre-RDS-migration
   container database (`docs/RDS_MIGRATION.md`).

## Verification
- `./scripts/verify-staging.sh` — specifically the `/api/health/` check's `"database":"ok"` field.
- Row-count comparison across all 9 record types (properties, sections, units, occupants, occupancies,
  payments, receipts, audit log, users) against the last known-good baseline — same pattern proven in
  `docs/runbooks/03-s3-backup-recovery.md` §5 of the master doc.
- A full smoke test through the real UI (login → view a property → view a payment) before declaring the
  incident resolved, not just an API-level health check.

## Rollback
Repoint `.env`'s `DB_HOST` back to the original instance's endpoint and restart the backend container — the
original instance is never deleted or modified by this procedure, only used as the restore *source*, so
rolling back is always available as long as you haven't yet decided to delete it.

## Escalation
If the restore itself fails, or the restored data doesn't match expectations at any point-in-time you try,
stop and fall back to the S3 `pg_dump` path (`docs/runbooks/03-s3-backup-recovery.md`) — it's independent of
whatever is wrong with RDS's snapshot chain, and is the proven, faster path.

## Lessons learned (fill in after a real incident or drill)
_Record here: actual restore time observed, whether the chosen restore point matched expectations on the
first try, and update `docs/DISASTER_RECOVERY.md` §1/§2 with a real measured RTO once this runbook has
actually been executed once — the current RTO figures for this specific path are estimates, not
measurements._
