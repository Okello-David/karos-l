# S3 Backup Architecture

Status: **live since 2026-08-01, restructured and restore-automated 2026-08-19.** This is the reference
doc for how KarosL's PostgreSQL backups get off the EC2 instance, where they live, how long they're kept,
and how to prove — not just assume — that they're restorable.

This doc assumes you've read `docs/DEVOPS.md` §12 (the original manual procedure, still correct and still
what the automation runs) and `docs/AWS_STAGING_CHECKLIST.md` (the security-group/account context). This
doc is the deeper reference for the S3 side specifically.

---

## 1. The bucket

**`karosl-staging-backups-908877263055`**, `eu-north-1`. This is the *existing* bucket from the 2026-08-01
sprint — reused here, not recreated. It already satisfied every requirement a fresh bucket would need to be
built to meet, confirmed directly via AWS CLI on 2026-08-19:

| Requirement | Status |
|---|---|
| Private, no public access | ✅ all four Public Access Block flags `true`; no bucket policy; ACL is owner-only `FULL_CONTROL` |
| Versioning | ✅ `Enabled` |
| Encryption | ✅ SSE-S3 (`AES256`, bucket key enabled) |
| Environment-specific, globally unique name | ✅ `karosl-staging-` prefix + AWS account ID suffix |

**Why this bucket and not a fresh `karosl-backups-<suffix>` one:** recreating it would mean either losing
the existing backup history or running a migration copy for zero functional gain — the existing bucket
already meets every stated requirement. Reuse, don't rebuild.

## 2. Key layout

```
s3://karosl-staging-backups-908877263055/
├── database/                          ← current, since 2026-08-19
│   ├── karosl_db_2026-08-19_123511.sql.gz     (daily, one per backup run)
│   └── monthly/
│       └── 2026-08.sql.gz                     (one per calendar month, first successful daily copied here)
└── pg_dump/                           ← legacy, 2026-08-01 through 2026-08-19, left in place
    └── 2026/
        └── karosl-staging-2026-08-01-131822.sql.gz
```

The `database/` prefix and `karosl_db_<date>_<time>.sql.gz` filename are what `scripts/backup-to-s3.sh`
writes today. The `pg_dump/<year>/karosl-staging-<date>-<time>.sql.gz` objects predate this restructure —
**left exactly where they are, not migrated or deleted.** They're still readable (the IAM policy below keeps
read access) and still restorable by hand following `docs/DEVOPS.md` §12's original commands.

Application uploads and receipts (if any land in S3 in future) must never share this bucket's `database/`
prefix — this bucket and this prefix are database backups only, by design (Task 5 of the brief this doc
documents).

## 3. IAM — least privilege, no keys on the box

Role `karosl-staging-backup-role` / instance profile `karosl-staging-backup-profile`, attached to the EC2
instance. **No AWS access keys anywhere on the box** — confirm with `aws sts get-caller-identity` (reports
the role, not a user) and the absence of `~/.aws/credentials`.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "WriteAndReadDatabaseBackups",
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:GetObject"],
            "Resource": "arn:aws:s3:::karosl-staging-backups-908877263055/database/*"
        },
        {
            "Sid": "ReadLegacyBackupsForRestore",
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::karosl-staging-backups-908877263055/pg_dump/*"
        },
        {
            "Sid": "ListOnlyTheBackupPrefixes",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::karosl-staging-backups-908877263055",
            "Condition": {
                "StringLike": {
                    "s3:prefix": ["database/*", "database", "pg_dump/*", "pg_dump"]
                }
            }
        }
    ]
}
```

Deliberately **not** granted, and verified absent: `s3:*`, `s3:DeleteObject` (a compromised instance can
write and read backups but cannot erase backup history — expiry is the bucket's lifecycle rules' job, not
the instance's), access to any other bucket, any bucket-administration action (`PutBucketPolicy`,
`PutBucketAcl`, etc.), public-access grants of any kind.

`pg_dump/*` is read-only now — nothing writes there anymore, but `restore-from-s3.sh` and manual restores
can still reach historical backups from before the restructure.

**Correction (production-readiness audit, 2026-08-20):** `karosl-staging-backup-role` is not S3-only — it
also carries a second inline policy, `karosl-cloudwatch-logs-metrics`, added alongside the CloudWatch work
(`docs/CLOUDWATCH_MONITORING.md`): `logs:CreateLogGroup`/`CreateLogStream`/`PutLogEvents`/
`DescribeLogStreams` scoped to `arn:...:log-group:/karosl/staging/*`, plus `cloudwatch:PutMetricData`
(unscoped resource — this action doesn't support resource-level restriction). The role's real scope is
**S3 write/read (no delete) + CloudWatch Logs/metrics write**, still with no `s3:DeleteObject` and no
access outside these two purposes — verified via `aws iam list-role-policies` / `get-role-policy`.

## 4. Backup process

`scripts/backup-to-s3.sh`, run nightly by `karosl-backup.timer` (`deploy/systemd/`, `OnCalendar=*-*-* 02:30:00 UTC`,
`Persistent=true` so a missed run — e.g. the instance was stopped — fires shortly after the next boot instead
of being silently skipped forever). **Proven, not just configured:** on 2026-08-19, after 18 days stopped,
the catch-up run fired ~4 minutes into the new boot and landed in S3, confirmed via `journalctl`.

```bash
./scripts/backup-to-s3.sh              # dump, verify, upload, prune
./scripts/backup-to-s3.sh --dry-run    # dump and verify only, no upload
```

Steps: `pg_dump --clean --if-exists` from inside the running `db` container (credentials read from the
container's own environment — never a command line, never a log) → verify the dump is real (size > 1024
bytes, `CREATE TABLE` and `COPY` blocks present — catches the classic "0-byte dump looks successful in
`ls`" silent failure) → `gzip -9` → upload to `database/` → confirm via `head-object` (non-zero size **and**
a real `VersionId`, since the bucket is versioned — Task 7's "verify a version exists," free because
versioning was already on) → if this is the first successful backup of the calendar month, an S3-to-S3 copy
(no second `pg_dump`) to `database/monthly/<year>-<month>.sql.gz` → prune local copies in `~/backups`,
keeping the newest 3.

Filename: `karosl_db_YYYY-MM-DD_HHMMSS.sql.gz`, e.g. `karosl_db_2026-08-19_123511.sql.gz`.

## 5. Restore process

### Automated restore into a disposable database — the normal case

`scripts/restore-from-s3.sh`. **This script can never reach the live database** — not "by default," never.
It only ever creates and restores into a database it creates itself (default `karosl_restore_test`), and
hard-refuses — no override flag exists — if `--target-db` is given a name matching the live `POSTGRES_DB`
(read from the `db` container's own environment, never from `.env`) or `postgres` (the system database).

```bash
./scripts/restore-from-s3.sh --list                              # show available backups, do nothing else
./scripts/restore-from-s3.sh --latest                             # the common case: prove the newest backup restores cleanly
./scripts/restore-from-s3.sh --key=database/monthly/2026-08.sql.gz
./scripts/restore-from-s3.sh --latest --keep                      # leave the disposable database up to poke at
./scripts/restore-from-s3.sh --latest --target-db=my_check_db     # note: flags take "=value"
```

Flow: select a backup (newest under `database/`, excluding `database/monthly/`, unless `--key` is given) →
download → decompress → verify (same size/schema/data checks as the backup script) → `CREATE DATABASE` →
restore → print row counts for `properties`, `sections`, `units`, `occupants`, `occupancies`, `payments`,
`receipts` next to `docs/PROJECT_STATE.md`'s documented baseline → `DROP DATABASE` (unless `--keep`).

**Verified end to end on 2026-08-19:** a real backup was taken, restored via this script, row counts
(3 properties / 4 sections / 12 units / 17 occupants / 15 occupancies / 14 payments / 14 receipts) matched
the live database exactly, the disposable database was confirmed dropped afterward, and the live database's
own row counts were unchanged before and after — plus both `verify-staging.sh` targets (hostname and bare
IP) stayed at 12/12 throughout, proving the running application was never touched.

### Production restore (manual, deliberate) — not automated, on purpose

Replacing live data with a backup is rare, high-stakes, and needs a human watching every step — it is
deliberately **not** a one-command script action. If it is ever genuinely needed:

1. Take a fresh `./scripts/backup-to-s3.sh` **before** touching anything — a pre-restore safety net.
2. Stop the backend so nothing writes to the database mid-restore: `docker compose stop backend`.
3. Download and decompress the chosen backup (`aws s3 cp` + `gunzip`, same as the automated script's steps).
4. Restore with `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` — the dump's `--clean --if-exists` header drops
   and recreates every table first, so this **destroys everything created since the dump.** There is no
   undo except the safety backup from step 1.
5. Spot-check row counts and a few real records against what you expect.
6. `docker compose start backend`, then run `./scripts/verify-staging.sh` on both access paths.

## 6. Retention

| Tier | Prefix | Lifetime | Rationale |
|---|---|---|---|
| Daily | `database/` | 30 days | Covers "someone notices a data problem within a month" — the realistic detection window for a live pilot at this scale. |
| Monthly | `database/monthly/` | 400 days | One snapshot per calendar month, kept over a year, for "what did the data look like N months ago" — a much rarer need, so a much sparser set is enough. |
| Legacy | `pg_dump/` | 30 days | Unchanged from before the restructure; ages out naturally, nothing new written here. |

**Overlap note:** `database/monthly/...` objects match both the `database/` 30-day rule (by prefix) and the
`database/monthly/` 400-day rule. This is intentional, not a bug — S3's documented behavior for overlapping
lifecycle rules with conflicting expirations is to apply whichever rule results in the **longer** retention,
so monthly objects correctly live for 400 days despite also matching the shorter daily rule.

**Cost tradeoff:** each dump is ~10-12 KB at current data volume. Even the 400-day monthly tier costs
fractions of a cent per year — the real tradeoff here is not storage dollars, it's restore-window coverage
versus S3 request/list clutter. At this scale, err toward keeping more: nothing in this design deletes
anything within its stated window, and lifecycle expirations only ever get *more* conservative to change,
never less, without a deliberate edit.

**"Do not blindly delete backups"**: no code path here ever issues `s3:DeleteObject` directly — expiry is
entirely the bucket's own lifecycle configuration, which is declarative, visible via
`aws s3api get-bucket-lifecycle-configuration`, and requires a deliberate `put-bucket-lifecycle-configuration`
call to change.

## 7. Scheduling

`deploy/systemd/karosl-backup.timer` + `karosl-backup.service`, installed via:
```bash
sudo cp deploy/systemd/karosl-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now karosl-backup.timer
```

| | |
|---|---|
| Frequency | Daily, 02:30 UTC + up to 15 min random delay |
| Location | `~/backups` on the instance (local, pruned to 3), `s3://.../database/` (durable) |
| Failure behavior | `Type=oneshot` service; a failed run shows in `systemctl --failed` and in `journalctl -u karosl-backup.service`. `Persistent=true` means a run missed while the instance was stopped fires shortly after the next boot instead of being silently skipped. |
| Log location | journald — `journalctl -u karosl-backup.service` |
| How to verify backups are occurring | `systemctl list-timers karosl-backup.timer` (last/next run), `aws s3 ls s3://karosl-staging-backups-908877263055/database/ --recursive` (newest object should be ≤ ~24h old), or just run `./scripts/restore-from-s3.sh --latest` periodically — the strongest verification, since it proves restorability, not just presence. |

## 8. Security checklist (Task 10)

| Check | Status | Evidence |
|---|---|---|
| Bucket not public | ✅ | No bucket policy; ACL owner-only |
| Public Access Block enabled | ✅ | All four flags `true`, checked 2026-08-19 |
| No AWS credentials in Git | ✅ | No committed `.env` files; `git log --all -p -- '*.env'` clean; `.gitignore` covers `.env`, `backend/.env`, `frontend/.env`, `backend/backups/` |
| EC2 uses IAM role, not keys | ✅ | `karosl-staging-backup-role` via instance profile; no `~/.aws/credentials` on the box |
| Backup objects encrypted | ✅ | SSE-S3/AES256, bucket default |
| PostgreSQL remains private | ✅ | Port 5432 never in the security group's inbound rules; `verify-staging.sh` checks this externally on every run |
| Restore requires authenticated access | ✅ | SSH key + `docker compose exec` on the instance, or AWS account access from a workstation — no public path to any backup object |

## 9. Troubleshooting

- **`--target-db` refused with "is the LIVE database"** — working as intended. Use the default disposable
  name or a clearly different one; see "Production restore" above if you genuinely mean to restore over live
  data.
- **`No backups found under s3://.../database/`** — either backups genuinely haven't started (`systemctl
  list-timers karosl-backup.timer`) or you're checking the wrong bucket/region — confirm `KAROSL_BACKUP_BUCKET`
  in `.env`.
- **Monthly copy skipped every day** — expected once one exists for the current month; check with
  `aws s3 ls s3://.../database/monthly/`.
- **A backup silently stopped appearing** — check `systemctl --failed` first, then `journalctl -u
  karosl-backup.service --since "2 days ago"`. A failed `pg_dump` (e.g. `db` container down) fails loudly
  (`die`) rather than uploading a partial file.

## 10. Disaster recovery

If the EC2 instance is lost entirely: provision a new instance (`docs/AWS_EC2_DEPLOYMENT.md`), deploy the
repo, bring up `docker-compose.yml` with a fresh `db` volume, then follow "Production restore" above using
the newest object under `s3://karosl-staging-backups-908877263055/database/` — the S3 bucket and its
contents are entirely independent of the EC2 instance's lifetime, which is the whole point of getting
backups off the box in the first place.

## 11. Monitoring preparation (2026-08-19)

No CloudWatch resources exist yet — this section documents the log-based hooks a future setup would use,
not a monitoring system that's actually running today. "Prepare the structure," not "add monitoring."

Both scripts emit a single-line `[EVENT] <NAME> <key=value ...>` marker at the points that matter, to
stdout, which lands in journald via the existing `karosl-backup.timer`/`.service` (same destination as every
other line either script prints — no new logging infrastructure). `--list` and `--dry-run` invocations emit
no events; only real attempts do, so the event stream reflects actual backup/restore activity, not every
time someone checks what's available.

| Event | Emitted by | When |
|---|---|---|
| `BACKUP_STARTED` | `backup-to-s3.sh` | Immediately, before any real work (dump/preconditions) |
| `BACKUP_SUCCEEDED key=... bytes=... version=...` | `backup-to-s3.sh` | After upload, size check, and the encryption check (§ below) all pass |
| `BACKUP_FAILED stage=<preconditions\|dump\|verify_dump\|compress\|prune>` | `backup-to-s3.sh` | Any failure before or unrelated to the S3 upload itself |
| `UPLOAD_FAILED stage=<upload\|verify_upload>` | `backup-to-s3.sh` | The dump was fine; S3 rejected it, or what landed doesn't verify (empty, or not encrypted) |
| `RESTORE_TEST_SUCCEEDED key=... target_db=...` | `restore-from-s3.sh` | Full flow (download → decompress → restore → verify → cleanup) completed |
| `RESTORE_TEST_FAILED stage=<download\|decompress_verify\|create_db\|restore\|verify_records\|cleanup>` | `restore-from-s3.sh` | Any failure during a real (non-`--list`, non-`--dry-run`) restore attempt |

Verified for real (not just read from the code): a deliberately-broken run (`KAROSL_BACKUP_BUCKET` pointed
at a bucket that doesn't exist) produced exactly `[EVENT] UPLOAD_FAILED stage=upload` and exit code 1 — the
failure path fires correctly, not just the happy path.

**What a future CloudWatch setup would do with this** (not built now): a CloudWatch Logs agent shipping
journald's `karosl-backup.service`/on-demand-run output, with metric filters matching `[EVENT] BACKUP_FAILED`,
`[EVENT] UPLOAD_FAILED`, and `[EVENT] RESTORE_TEST_FAILED` into an alarm, plus a metric filter on the
*absence* of `[EVENT] BACKUP_SUCCEEDED` within a 24h window (catches the timer silently not firing at all,
which a failure-only alarm would miss). None of this requires changing the event format above when it's
eventually built — the vocabulary is deliberately stable.

## 12. Explicit per-object encryption check (2026-08-19)

`backup-to-s3.sh` now checks the actual uploaded object's `ServerSideEncryption` field via `head-object`
(not just the bucket's default-encryption setting) and `die`s if it's empty — printing `encrypted: AES256`
on success. Verified against a real upload today. This closes the gap between "the bucket has default
encryption configured" (a policy) and "this specific object is actually encrypted" (a fact about the
object) — the two aren't quite the same claim, and only the second is what actually matters for a given
backup.
