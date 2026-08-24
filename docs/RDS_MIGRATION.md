# RDS Migration — PostgreSQL moved from the EC2 container to Amazon RDS

Status: **Live since 2026-08-19.** The application's database of record is now Amazon RDS PostgreSQL.
The original `db` container and its volume are still running, untouched, as a rollback safety net — see
"Old database — when it's safe to remove" below.

## Why

`docs/AWS_DEPLOYMENT_PLAN.md` has always named this "Phase 3," deliberately deferred until "the data's
value justifies the cost." The 2026-08-19 Live Pilot audit put real tenant/payment data on a single
container Postgres instance with no managed backups, no point-in-time recovery, and no independent
patching — a single point of failure for the one thing on this stack that actually matters. This
migration moves the database to a managed, backed-up, private-only RDS instance while leaving the EC2
host, Nginx, and Gunicorn exactly where they were.

## Architecture

```
Internet
  |
  v
EC2 (karosl-staging-ec2, t3.micro)
  |-- Nginx/React (frontend container)
  '-- Django/Gunicorn (backend container)
        |
        v  TCP 5432, private VPC only
      Amazon RDS PostgreSQL (karosl-staging-postgres)
```

The old `db` container is still present in `docker-compose.yml` and still running on the instance — it is
simply no longer what the application talks to. Nothing was deleted this sprint.

## RDS instance configuration

| Setting | Value | Why |
|---|---|---|
| Identifier | `karosl-staging-postgres` | |
| Engine / version | PostgreSQL 16.14 | Exact match to the container's `postgres:16-alpine` (16.14) — zero compatibility risk, no dump/restore translation needed |
| Instance class | `db.t4g.micro` | Smallest Graviton burstable class, free-tier eligible, matches `docs/AWS_DEPLOYMENT_PLAN.md`'s own Phase 3 recommendation |
| Storage | 20 GiB gp3, autoscaling to 30 GiB | The live database is 9.4 MB — 20 GiB is pure headroom, not a projected need |
| Deployment | **Single-AZ** | Explicit constraint — no Multi-AZ this sprint |
| Public accessibility | **Disabled** | Explicit constraint — reachable only from inside the VPC |
| Storage encryption | Enabled (AWS-managed KMS key) | Default-on, no extra cost, no reason not to |
| Automated backup retention | **1 day** | The account is on the AWS Free Tier, which caps RDS backup retention at 1 day regardless of what's requested — attempting 7 raised `FreeTierRestrictionError`. Matches the only other RDS instance already in this account. This is in addition to, not instead of, the independent `scripts/backup-to-s3.sh` pipeline (14+ day retention, off-AWS-account-boundary, already proven end-to-end below) |
| Deletion protection | **Enabled** | Cheap, fully reversible (can be disabled any time), appropriate for an instance holding live tenant/payment data |
| Master username | Matches the container's `DB_USER` (`karosl_user`) | Minimizes the diff in app configuration — same username, new instance |
| Master password | Freshly generated 40-character random string | Never reused from the container's password. Lives only in the server's `.env` (never committed) — see "Secrets" below |
| Parameter group | Default (`postgres16`) | No custom parameters needed |
| Tags | `Project=KarosL`, `Environment=staging` | |

## Networking

New security group **`karosl-rds-sg`** (`sg-0bd2df032ea18c46d`), in the same VPC as the EC2 instance
(`vpc-04664b7a9c5f76d68`):

```
EC2 security group (karosl-staging-sg, sg-065fb018e22aa18a5)
        |
        |  TCP 5432 — the ONLY inbound rule on karosl-rds-sg
        v
RDS security group (karosl-rds-sg, sg-0bd2df032ea18c46d)
        |
        v
karosl-staging-postgres
```

The single ingress rule sources from `sg-065fb018e22aa18a5` **by security-group reference, not a CIDR
block** — there is no `0.0.0.0/0` anywhere in this configuration, and nothing outside the EC2 instance's
own security group can reach port 5432. No egress rule was needed: the EC2 SG already allows all
outbound traffic. New DB subnet group `karosl-rds-subnet-group` spans `subnet-0d36cc95a8da7b99c`
(`eu-north-1a`) and `subnet-02b44929321b5ef7d` (`eu-north-1b`) — RDS requires at least two AZs in a
subnet group even for a Single-AZ instance.

Verified: `aws rds describe-db-instances` shows `PubliclyAccessible: false`;
`aws ec2 describe-security-groups` on `karosl-rds-sg` shows exactly one ingress rule, no CIDR ranges.

## Secrets

The RDS master password was generated locally (40 random characters), used once to create the instance
and once to write the server's `.env`, and never appears in any git-tracked file, GitHub Secret, commit,
or workflow log. It is not the same password the container database uses — a fresh credential for a fresh
instance, not a carried-over one. Application access stays password-based (matching the app's existing
model); no IAM database authentication was introduced, and no new IAM policy was needed for RDS itself — the
EC2 instance role (`karosl-staging-backup-role`) gained no RDS permissions. It does also carry an inline
CloudWatch Logs/metrics policy from separate, unrelated work — see `docs/S3_BACKUP_ARCHITECTURE.md` §3 for
its exact, current scope.

## Application configuration

`backend/config/settings_production.py` gained one small, additive change ahead of the actual cutover:

```python
'OPTIONS': {
    'connect_timeout': 5,
    **({'sslmode': os.getenv('DB_SSLMODE')} if os.getenv('DB_SSLMODE') else {}),
},
```

Inert without `DB_SSLMODE` set — container-Postgres deploys are byte-for-byte unaffected. This was
committed, pushed, tested by CI, and deployed to the server *before* the data cutover, so the code change
and the data change never landed as one indivisible step.

The actual cutover is `.env`-only, on the server, untracked by git:

```
DB_HOST=karosl-staging-postgres.c788aewsq3ct.eu-north-1.rds.amazonaws.com
DB_PORT=5432
DB_USER=karosl_user
DB_PASSWORD=<generated, never committed>
DB_NAME=karosl
DB_SSLMODE=require
```

`POSTGRES_*` variables (which configure the still-running container) were left untouched.

### A real bug found during the cutover itself

The first cutover attempt, done by just editing `.env` and restarting `backend`, **crash-looped the
backend** — Django kept connecting to `db` (172.18.0.2) instead of RDS, and failed auth there with the new
RDS password. Root cause: `docker-compose.yml`'s base file hardcodes `DB_HOST: db` and `DB_PORT: 5432` in
the `backend` service's own `environment:` block, and **an `environment:` value always beats `env_file`**
— the exact same class of footgun `docker-compose.https.yml`'s own header comment already documents for
`SECURE_SSL_REDIRECT`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SECURE`. Setting `DB_HOST` in `.env` alone
silently did nothing.

Recovered immediately by restoring the pre-cutover `.env` and restarting `backend` — the container
crash-looped for well under a minute; the `db` container and its data were never touched by any of this.

**Fixed at the root** with a new overlay, `docker-compose.rds.yml`:

```yaml
services:
  backend:
    environment:
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT:-5432}
```

`scripts/deploy-staging.sh` and `scripts/rollback-staging.sh` both now include this overlay
**automatically, but only when `.env`'s `DB_HOST` actually points away from `db`** — gated on the real
value, not merely the overlay file's presence, since applying it while `DB_HOST` is unset would set
`DB_HOST` to an empty string and break the container-Postgres path entirely. The retried cutover, with
this fix in place, succeeded cleanly: backend connected to RDS, ran `migrate --noinput` (`No migrations to
apply` — the restored `django_migrations` table already matched), and passed health checks.

### Restarting Django safely

`docker compose "${COMPOSE_FILES[@]}" up -d --no-deps backend` — `--no-deps` means only `backend` is
recreated; `frontend` (port 443, CloudWatch logging) and `db` are never touched by a cutover or a
rollback.

## Migration procedure

`scripts/migrate-to-rds.sh` (new, one-time — distinct from the recurring `scripts/backup-to-s3.sh`):

1. `./scripts/backup-to-s3.sh` first — a fresh, verified, off-site safety copy before touching anything.
2. Recorded pre-migration state: `git rev-parse HEAD`, `docker compose ps`, and the row-count baseline
   below.
3. `pg_dump --clean --if-exists` from the `db` container.
4. Verified the dump (non-trivial size, `CREATE TABLE`/`COPY` blocks present) — the same checks
   `backup-to-s3.sh` already runs, reused rather than reinvented.
5. Restored over the network into RDS, using the **same container's `pg_dump`/`psql` binaries**
   (version-matched, 16.14) pointed at the RDS endpoint. The container has outbound internet access via
   the host, and only `karosl-staging-sg` can reach RDS on 5432 — this only works from the app side.
6. Re-ran the row-count query against RDS and diffed it against the source counts — **the script does not
   accept exit code 0 alone**; it prints both tables and refuses to declare success if they differ.

## Data verification

Row counts, source (container) vs. RDS, captured by `migrate-to-rds.sh`:

| Table | Source | RDS | Match |
|---|---|---|---|
| properties | 4 | 4 | ✓ |
| sections | 5 | 5 | ✓ |
| units | 13 | 13 | ✓ |
| occupants | 18 | 18 | ✓ |
| occupancies | 16 | 16 | ✓ |
| payments | 15 | 15 | ✓ |
| receipts | 15 | 15 | ✓ |
| audit_logs | 46 | 46 | ✓ |
| users | 1 | 1 | ✓ |

Dump verified at 80,126 bytes / 21 tables / 21 data blocks before restore. `diff` between the source and
RDS count outputs was empty.

## Application verification

Post-cutover: `docker compose logs backend` showed a clean connection to the RDS endpoint, `Applying
database migrations... No migrations to apply` (confirming the restored `django_migrations` table matches
exactly), and Gunicorn booting normally. `curl -k https://localhost/api/health/` returned
`{"status":"ok","database":"ok"}`. The external `scripts/verify-staging.sh` check passed **12/12** against
the live HTTPS URL, backend now pointed at RDS.

**Browser walkthrough (2026-08-20)**: logged in as `karosadmin` and confirmed real data end-to-end through
the actual UI — Overview (18 occupants, 14/24 beds occupied, matching the row-count table above), Property
Explorer (both properties, correct unit counts), and Reports (Occupancy Reports showing 2 properties/24
capacity/14 occupied, matching Overview). Ran a labeled write-path check: created a property named
`RDS-MIGRATION-TEST-DELETE-ME` (code `RDSTST`) via Administration → Properties, got the
"Property created successfully" confirmation, then archived it immediately (`RDS-MIGRATION-TEST-DELETE-ME`
now shows `Archived`, alongside the pre-existing `AUDIT-TEST` entries from earlier audit passes). Confirms
writes through the UI land on RDS, not stale/cached data.

## S3 backup verification against RDS

The recurring backup/restore tooling needed a real fix, not just a config change: `scripts/backup-to-s3.sh`
and `scripts/restore-from-s3.sh` both hardcoded dumping/restoring against the local `db` container. Because
that container is deliberately kept running as a rollback safety net, its mere presence could no longer be
trusted to mean "this is the live database" — after cutover, the nightly backup would have silently kept
saving the frozen, pre-migration container data instead of RDS.

**Both scripts are now `DB_HOST`-aware**: when `.env`'s `DB_HOST` is `db` (or unset), they behave exactly
as before. When it points elsewhere (RDS), they dump/restore over the network using
`DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` from `.env`, still executed via the `db` container's own
`pg_dump`/`psql` binaries. This is also what makes the migration genuinely reversible: flipping `DB_HOST`
back to `db` flips the backup scripts back to local-container behavior with no further code changes.

Both were run for real against RDS after the fix:

- `./scripts/backup-to-s3.sh` — dumped from the RDS endpoint (log line: `Dumping the database from
  karosl-staging-postgres...:5432 (DB_HOST != db, remote target)`), 80,126 bytes / 21 tables / 21 data
  blocks (identical to the migration dump — no data has changed since cutover, as expected), uploaded and
  confirmed in S3 (`ServerSideEncryption: AES256`).
- `./scripts/restore-from-s3.sh --latest` — downloaded that backup, created a disposable
  `karosl_restore_test` database **on RDS itself**, restored into it, printed matching row counts, and
  dropped it. The live `karosl` database on RDS was never touched — the existing "never the live database"
  guardrail now reads `DB_NAME` from `.env` when `DB_HOST` is remote, instead of the container's own
  `POSTGRES_DB`, so it still holds.

## Rollback procedure

The migration is reversible by design — the container and its volume were never stopped, modified, or
deleted.

1. Restore `.env` from the pre-cutover backup: `cp .env.bak-pre-rds-cutover-<timestamp> .env`.
2. Restart backend with the same overlay-detection logic: `./scripts/deploy-staging.sh` (or the manual
   `docker compose "${COMPOSE_FILES[@]}" up -d --no-deps backend` — `docker-compose.rds.yml` is
   automatically excluded once `DB_HOST` is back to `db`).
3. Confirm health: `curl -k https://localhost/api/health/`, `./scripts/verify-staging.sh`.

This is a same-day operation with no data loss, because the container database was never touched by the
migration — it is simply frozen at its pre-migration state, which is exactly what a rollback needs.

**Important limitation**: any writes made against RDS after cutover are **not** present in the frozen
container database. A rollback after real usage means accepting data loss for whatever happened on RDS in
between, unless it's re-applied by hand from an RDS backup. This is why deletion protection is on and the
container is being kept, not deleted, for a real validation window (below) rather than treating "rollback"
as free at any point in time.

## Old database — when it's safe to remove

`karosl-db-1` and the `karosl_postgres_data` volume are kept **indefinitely for now**. Recommended: not
before **7 days of clean RDS operation** (matching RDS's own automated-backup window), and only as a
separate, deliberate decision — not bundled into this sprint. Removing them means running
`docker compose stop db` and `docker compose rm db` followed by `docker volume rm karosl_postgres_data`,
none of which has been done.

**Checked again during the 2026-08-24 operational cleanup sprint, with the actual date math, not a
guess**: migration cutover was 2026-08-19; the 7-day window closes 2026-08-26; as of 2026-08-24, **2 days
remain**. **Window not yet complete — left untouched, per this doc's own recommendation.** No code or
infrastructure change made for this. Revisit on/after 2026-08-26.

## Cost

| Item | Rate (eu-north-1) | Monthly |
|---|---|---|
| `db.t4g.micro`, Single-AZ, PostgreSQL | $0.016/hr | ~$11.68 |
| 20 GiB gp3 storage | ~$0.12/GB-mo | ~$2.40 |
| Automated backup storage | Free up to DB size (9.4 MB) | ~$0 |
| **New spend** | | **~$14/month** |

Confirmed via the AWS Pricing API for `eu-north-1`, matching `docs/AWS_DEPLOYMENT_PLAN.md`'s own
"$20-30/month for the EC2+RDS phase" range once added to the existing EC2/S3/CloudWatch footprint.

**Budget**: the account's only AWS Budget (`My Monthly Cost Budget`, shared across KarosL and an unrelated
project) was raised from $5/month to $30/month before RDS was created — the $5 ceiling was already
breached ($9.37 actual spend) and provided no real signal for this decision. Its existing 50%/80%/forecast
alert thresholds carry forward unchanged at the new ceiling.

## Remaining risks

- Rollback after real RDS usage means accepting data loss for anything written after cutover (see
  "Rollback procedure" above) — mitigated by RDS's own point-in-time recovery (1-day window) and the
  independent S3 backup pipeline, not by the container.
- RDS automated backup retention is capped at 1 day by the account's Free Tier status — the S3 pipeline
  (14+ day daily, longer monthly tier) is the real long-retention backup, not RDS's own.
- The container/volume being kept means the instance's 10 GB root volume still carries that data — not a
  new risk, just an existing one that persists a bit longer than a same-day migration would otherwise
  need.

## Next sprint

- Remove the container/volume once the 7-day validation window has passed cleanly — **not yet eligible as
  of 2026-08-24, 2 days remaining** (see "Old database — when it's safe to remove", above).
- ~~Consider RDS Performance Insights or a CloudWatch alarm on RDS free storage / CPU / connections~~ —
  **done 2026-08-24**: three RDS-specific CloudWatch alarms added (`FreeStorageSpace`, `CPUUtilization`,
  `DatabaseConnections`), wired to the existing SNS topic, verified end-to-end. See
  `docs/CLOUDWATCH_MONITORING.md` §7.
- The purchased-domain item (standing, unrelated to this migration) remains open.
