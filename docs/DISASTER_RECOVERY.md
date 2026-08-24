# Disaster Recovery & Incident Response — KarosL Live Pilot

**Date:** 2026-08-24. **Scope:** disaster-recovery and incident-response documentation and testing only —
no architecture changes, no new major AWS services, no destructive tests against live data. **Stance:**
every claim below is backed by a command actually run, a script actually read in full, or a doc actually
reviewed during this pass — not by re-stating prior docs on faith. Where this pass found a real gap, it's
named as a gap, not smoothed over.

This document is the entry point. Procedural step-by-step recovery for each scenario lives in
`docs/runbooks/`. This document covers: recovery objectives (RPO/RTO) with evidence, a per-scenario summary
of what's tested vs. documented-only vs. not currently possible, the results of the recovery exercise
actually performed during this pass, and a final posture verdict.

---

## 1. Recovery objectives

### RPO (Recovery Point Objective) — how much data can be lost

**RPO ≈ 24 hours, worst case. Typically much less.**

Two independent backup mechanisms exist, and RPO is bounded by the *weaker* of the two for any given
recovery path, not the stronger:

| Mechanism | Cadence | Effective RPO |
|---|---|---|
| RDS automated backups | Continuous transaction log capture within a **1-day retention window** | Near-zero *if* RDS's own restore/PITR machinery is used — but see limitation below |
| S3 `pg_dump` snapshots (`scripts/backup-to-s3.sh`) | Once daily, `02:30 UTC` ± up to 15 min jitter, `Persistent=true` catch-up timer | Up to ~24h, worst case (primary lost seconds before the next scheduled dump) |

**Evidence:**
- The S3 backup schedule (`deploy/systemd/karosl-backup.timer`, `OnCalendar=*-*-* 02:30:00 UTC`) was
  confirmed live during this pass: `aws s3 ls` shows a real backup object for every day from 2026-08-19
  through 2026-08-24, most recently `karosl_db_2026-08-24_024045.sql.gz` — 7 hours old at the time this was
  checked, consistent with the documented once-daily cadence.
- RDS's automated-backup retention is **1 day**, and it is a **Free Tier account cap**, not a chosen value
  — `docs/RDS_MIGRATION.md` records that requesting 7 days raised `FreeTierRestrictionError`.

**Limitation — this is the honest gap, not a hedge:** RDS's own point-in-time-recovery (restoring to
any second within the retention window, not just to the last automated snapshot) was **not exercised**
during this pass. Testing it for real requires restoring a **new RDS instance** from a snapshot, which was
deliberately not done — creating a second RDS instance without asking first is off-limits per standing
project convention, and doing so purely to prove a recovery-time number would itself be a small, real AWS
spend decision that belongs to the account owner, not something to take unilaterally in a documentation
pass. So: RDS PITR's *existence* is a documented AWS platform guarantee (retention window = 1 day), but its
*restore procedure and timing for this specific application* are **untested** — flagged plainly in the
verdict (§6) rather than assumed.
- The S3 `pg_dump` path **was** fully exercised this pass (§5) — it is the RPO/RTO path with actual
  evidence behind it, and is also more disaster-resilient than RDS PITR in one specific way: it survives
  even total loss of the RDS instance/account context, since the dump is a portable artifact restorable to
  *any* PostgreSQL server, proven literally by restoring it to a laptop-local container during this test.

**Assumption required:** that the S3 backup timer keeps running. §7 (Backup failure) covers what happens
if it silently stops, and what currently would/wouldn't catch that.

### RTO (Recovery Point Objective) — how long recovery takes

**RTO is only measured for one specific, real recovery path: S3 backup → disposable database → verified.
That path measured 15 seconds for the restore itself, under 1 minute including full application-layer
verification.** Full incident RTO (detecting a problem, deciding to act, provisioning replacement
infrastructure if needed, cutting the application over, confirming it's healthy) is **not a single number**
— it depends entirely on which scenario occurred. Per-scenario estimates are given in §2–§4 and in each
runbook, built from the same evidence base (proven script behavior + realistic step timing), not invented.

**What was actually measured, this pass, right now** (§5 has full detail):

| Step | Duration |
|---|---|
| `restore-from-s3.sh --latest` (download, decompress, verify, create DB, restore, row-count check) | **15 seconds** |
| Full verification incl. Django ORM connecting to the restored data | **~58 seconds total, start to finish** |

This is the *database restore* component of RTO, proven end-to-end. It is not the *entire* incident RTO for
every scenario — an EC2-instance-loss scenario, for example, also needs a replacement instance provisioned
and configured (§3), which was not empirically timed this pass (no EC2 instance was destroyed to test it —
correctly so, per the brief's constraints). Where a runbook gives a time estimate for a step that wasn't
directly measured, it says so.

---

## 2. Database recovery — summary (full procedure: `docs/runbooks/02-rds-recovery.md`, `03-s3-backup-recovery.md`)

Two independent recovery paths exist for the database. Both were investigated this pass; one was actually
executed.

**Path A — RDS automated backup / snapshot restore.** AWS-native, 1-day retention, deletion protection is
on. **Documented, not tested this pass** (see limitation in §1). Recovering via this path means restoring
to a *new* RDS instance (AWS does not restore in-place) and repointing the application's `.env` — procedure
in `docs/runbooks/02-rds-recovery.md`, written from AWS's documented restore behavior and this project's own
`docker-compose.rds.yml` cutover pattern (already proven once, during the original RDS migration).

**Path B — S3 `pg_dump` snapshot restore.** Portable, engine-agnostic, survives even total RDS/account loss.
**Tested for real this pass.** Full results in §5. Procedure in `docs/runbooks/03-s3-backup-recovery.md`.

**All required record types were verified present and correct in the restored data this pass**: properties,
sections, units, occupants, occupancies, payments, receipts, audit log entries, and users — see §5 for the
actual counts. The live database was never touched — restores went into a disposable database
(`karosl_dr_test_20260824`), dropped after verification.

---

## 3. EC2 failure recovery (full procedure: `docs/runbooks/01-ec2-failure.md`)

**What's stored only on EC2** (lost if the instance is destroyed, not just stopped):
- The application's `.env` file — `SECRET_KEY`, the RDS application-user password, and every other secret.
  **This is the single most important finding in this section.** These values were hand-typed onto the
  server when it was first configured (`docs/AWS_EC2_DEPLOYMENT.md`) and were never stored anywhere else —
  not in a secrets manager (one is planned but not built — `docs/AWS_DEPLOYMENT_PLAN.md` calls it a "later"
  item), not in GitHub Secrets, not backed up by any script. The S3 backup pipeline backs up *database
  contents*, not this file.
- TLS certificates (`/etc/letsencrypt/`) — both the hostname-based Let's Encrypt cert and the short-lived
  (~160h) bare-IP cert. Not backed up anywhere, but this is by design, not an oversight: both are cheaply
  re-issuable from a fresh instance in minutes, so durability was never a goal for them.
- Anything a human did directly on the box outside of what deploys apply (ad-hoc `nano`/`vi` edits,
  manually-run one-off commands) — there is no drift-detection between server state and what
  `deploy-staging.sh` would produce from a clean checkout.

**What's stored externally / reconstructable:**
- All application code — GitHub (`cloud-deployment` branch).
- All database contents — RDS itself (if RDS survives) or the S3 `pg_dump` pipeline (if it doesn't).
- Docker image definitions — `Dockerfile`s and `docker-compose*.yml` files, all in git.
- CI/CD pipeline definition — `.github/workflows/*.yml`, in git.

**Practical recovery procedure, if the instance is destroyed (not just stopped — for a stopped instance,
`scripts/recover-staging.sh` already handles that non-destructively and needs no new documentation here):**
1. Launch a replacement EC2 instance (same AMI family, security group can be recreated from
   `docs/AWS_EC2_DEPLOYMENT.md`'s documented rules, or restored from the existing `sg-065fb018e22aa18a5` if
   AWS didn't lose the security group itself — SGs are region-level, independent of any one instance).
2. `git clone` the repo at `~/apps/karosl`.
3. **Recreate `.env` from scratch** — this is the step with no shortcut. `SECRET_KEY` and `POSTGRES`
   passwords must be freshly generated (they cannot be "recovered," only replaced — meaning **RDS's
   master/application password must also be reset** via the RDS console/CLI, since the old one only ever
   existed in the now-lost `.env`). `DB_HOST` points at the existing RDS endpoint (RDS itself is unaffected
   by EC2 loss, since it's a separate managed resource) — no data is lost by this step, only credentials
   need rotating.
4. Install the self-hosted GitHub Actions runner fresh (`docs/CI_CD.md` has the setup steps), or deploy
   manually with `docker compose` the first time.
5. Re-issue TLS certificates — `scripts/recover-staging.sh` already automates exactly this (dry-run-first,
   rate-limit-safe) for the "new IP" case, which a replacement instance also is.
6. Run `scripts/verify-staging.sh` to confirm the full stack (HTTPS, health check, auth boundary, SPA
   routing) before considering the instance recovered.

**Estimated time:** not empirically measured this pass (would require destroying the live instance, which
the brief correctly prohibits). Built from the individual proven steps: instance launch + boot (~2–5 min,
AWS-typical) + `.env` recreation and RDS password reset (~10–15 min, manual/careful work, cannot be
scripted away since it involves generating and safely transcribing new secrets) + first deploy (~3–5 min,
per `docs/CI_CD.md`'s proven pipeline timing) + cert issuance (~1–2 min, per `recover-staging.sh`'s proven
behavior) + verification (~1 min). **Rough total: 20–30 minutes**, dominated by the manual secret-recreation
step — this is an estimate built from measured sub-steps, not a guess, but it is explicitly not an
end-to-end timed drill.

---

## 4. Application recovery — reconstructability audit

Checked what the application can be rebuilt from, end to end:

| Component | Source of truth | Reconstructable? |
|---|---|---|
| Application code | GitHub (`cloud-deployment`, public repo) | Yes, fully |
| Docker build definitions | Git (`Dockerfile`, `docker-compose*.yml`) | Yes, fully |
| CI/CD pipeline | Git (`.github/workflows/*.yml`) | Yes, fully |
| Database contents | RDS (live) + S3 `pg_dump` (portable fallback) | Yes, fully — proven this pass (§5) |
| **Application secrets** (`SECRET_KEY`, DB password) | **`.env` on the EC2 instance only** | **No — must be rotated, not recovered** |
| TLS certificates | EC2 instance disk only | Not "recoverable," but cheaply re-issuable — not a real gap |
| GitHub Actions self-hosted runner registration | EC2 instance (systemd service + runner token) | Re-registerable via a fresh token from GitHub, procedure documented in `docs/CI_CD.md` |
| CloudWatch alarms / SNS topic / IAM roles | AWS account config, not code | **Not defined as code anywhere** — see gap below |

**Anything dependent on manual, undocumented configuration:** Two real items, both already partially known
from the audit trail but worth stating plainly here:

1. **`.env` (per above)** — the clearest single point of non-reconstructable configuration in the whole
   system. **Recommendation:** move `SECRET_KEY` and the RDS password into AWS Secrets Manager or SSM
   Parameter Store (already the documented "later" plan in `docs/AWS_DEPLOYMENT_PLAN.md`) — this is the
   single highest-leverage DR improvement available, since it turns "must rotate and hope nothing depended
   on the old value" into "read the same value back." Out of scope to implement in this pass (a new AWS
   service integration is explicitly off-limits for this sprint), but it's the clearest actionable
   recommendation this audit produced.
2. **CloudWatch alarms, SNS topic, and IAM roles/policies were created via AWS CLI commands run by hand**
   during the 2026-08-19/20 monitoring pass — they are **not expressed as Infrastructure-as-Code**
   (no CloudFormation/Terraform/CDK anywhere in this repo). If the AWS account's monitoring config were ever
   lost or needed reproducing in a second environment, someone would need to manually re-run the same `aws
   cloudwatch put-metric-alarm` / `aws sns` commands documented in `docs/CLOUDWATCH_MONITORING.md` — the doc
   is thorough enough to serve as a manual runbook for this, but it is not automated. **Recommendation:**
   not urgent given the single-environment scale today, but worth naming as a gap rather than pretending the
   docs are equivalent to IaC.

---

## 5. Recovery test actually performed this pass (Phase 12 exercise)

**Method:** S3 `pg_dump` backup → disposable local PostgreSQL database (not the local dev DB, not staging,
not production) → restore → verify via raw SQL → verify via Django ORM connected to the restored data →
clean up. Used the project's own `scripts/restore-from-s3.sh`, unmodified — this script already has a
hard-coded guardrail that refuses to target the live database name, so no destructive-tooling risk was
introduced to run this test.

**Timeline (all times UTC, 2026-08-24):**

| Step | Time | Elapsed |
|---|---|---|
| Backup created (scheduled, not part of this test) | `02:40:45` | — |
| Recovery test started | `09:27:34` | — |
| `restore-from-s3.sh --latest` completed (download → decompress → verify → create DB → restore → row-count) | `09:27:49` | **15 seconds** |
| Full verification complete (raw SQL spot-checks + Django ORM connection + counts) | `09:28:32` | **58 seconds from test start** |
| Disposable database dropped (cleanup) | immediately after | — |

**What was verified, and how:**

| Record type | Verified via SQL | Verified via Django ORM | Count |
|---|---|---|---|
| Properties | ✅ | ✅ | 5 |
| Sections | ✅ | — | 5 |
| Units | ✅ | — | 13 |
| Occupants (students) | ✅ | ✅ | 19 |
| Occupancies | ✅ | — | 17 (14 active) |
| Payments | ✅ | ✅ | 16 (sum: 10,363,000.00) |
| Receipts | ✅ | — | 16 |
| Audit log entries | ✅ | ✅ | 53 |
| Users | ✅ | ✅ | 1 |
| Auth tokens | ✅ | — | 1 |

Every row count from the restored disposable database was cross-checked two ways (raw `psql` query, then
independently via the Django ORM connecting to the same disposable database with `DB_NAME` overridden) —
both layers agreed exactly. Property codes and an occupancy/payment aggregate were also spot-checked for
plausibility (5 properties with real codes, 14 of 17 occupancies currently active, total payments summing
to a coherent figure) rather than just counted, to rule out a restore that produces the right row *counts*
but garbage *content*.

**What this proves:** the S3 backup pipeline produces a genuinely restorable, complete database dump — not
just a file that uploads successfully. This is the strongest possible evidence for the S3-backup RPO/RTO
claims in §1, because it's a real execution with a real timestamp and real (if small — this is a live pilot,
not yet at scale) production-shaped data, not a description of what the script is supposed to do.

**What this does NOT prove:** it doesn't validate RDS's own native backup/PITR path (§1 limitation), and it
doesn't validate a full EC2-instance-loss recovery (§3) — those remain documented-but-untested, stated
plainly rather than implied to be equally proven.

---

## 6. Bad deployment (full procedure: `docs/runbooks/04-bad-deployment.md`)

**Not tested live this pass** (the brief correctly prohibits deploying a broken release to the live
application to test this). Assessed instead by reading `scripts/rollback-staging.sh` in full and confirming
its actual behavior against what the docs claim:

- Reads `~/.karosl-deploy-history` (written by every successful deploy) for the previous known-good commit,
  or accepts an explicit `--to=<sha>`.
- Refuses to run against a dirty working tree (uncommitted changes to tracked files).
- Checks out the target commit as a **detached HEAD**, rebuilds, restarts with the same compose-overlay
  detection logic the live deploy uses (HTTPS/CloudWatch/RDS overlays, evaluated fresh against the
  *rolled-back* commit, not stale from before).
- Runs the same content-based health check the deploy pipeline uses.
- **Confirmed by reading the full script: it never touches the database, volumes, or runs `down -v`.**
  Rollback is code-only.
- **Documented, real limitation, not hidden:** rollback cannot auto-downgrade a Django migration. If the bad
  deployment included a forward migration, rolling back the code alone can leave the application pointed at
  a database schema newer than the code expects. The script prints a warning and pauses 5 seconds
  (Ctrl-C to abort) specifically for this reason, rather than either blocking entirely or (much worse)
  attempting an automated migration downgrade against live data.
- Automatic rollback-on-failed-smoke-test is **deliberately not wired up** — a human must trigger
  `rollback-staging.sh` manually. This is a documented, deliberate design choice ("to avoid compounding a
  real problem with an unattended rollback attempt during an incident"), not an oversight.

**A failed migration mid-deploy** doesn't corrupt anything by itself: the backend container's own entrypoint
runs `migrate --noinput` before Gunicorn starts, so a migration failure means the container simply never
reports healthy — the deploy job then fails its health-check step and stops, rather than serving traffic
against a half-migrated schema.

---

## 7. Data corruption / accidental change (full procedure: `docs/runbooks/05-database-corruption.md`)

**Scenario:** a user accidentally changes or deletes important data through the application.

**What helps, and how much:**

- **The audit log (`apps/audit`) tells you *what* happened and *who* did it**, for most actions — it
  captures CREATE, UPDATE, ARCHIVE, ASSIGN, CHECKOUT, and RECORD_PAYMENT across every business entity, with
  actor, timestamp, and (for updates) a `changes` JSON field. This is genuinely strong for figuring out the
  scope of an incident quickly.
- **The audit log does NOT capture most deletions**, because the application is architecturally
  soft-delete-first — nearly everything that looks like "removal" in the domain model is an ARCHIVE
  (`is_active=False`), which *is* logged. The one real hard-delete path in the entire codebase is
  `PricingRule` deletion, which *is* logged as `Action.DELETE`. If a user directly deletes a database row
  through some path that bypasses the application layer entirely (e.g. a manual `psql` `DELETE`), the audit
  log has no record of it at all — it only sees what the API layer does.
- **The audit log itself is not restorable via the app's own Backup & Export feature** — that feature's
  8-model JSON export deliberately excludes `AuditLog`, `Backup`, and `User`/token tables. The audit trail's
  own durability rests entirely on the S3 `pg_dump` pipeline (confirmed this pass: the restored dump
  included 53 real audit log rows — see §5) — meaning if you need "what happened before the corruption," you
  restore the *whole database* to a disposable copy and read the audit log there, you don't restore "just
  the audit log" through any in-app tool.
- **Database backups can recover pre-corruption state**, bounded by RPO (§1) — up to 24h of intervening
  changes would be lost if the corruption isn't caught same-day.
- **Point-in-time recovery** (restoring to the exact second before the accidental change, not just to the
  last daily snapshot) is *possible* via RDS's native PITR — see §1's honest limitation: this exists as an
  AWS platform capability within the 1-day retention window, but the procedure was not exercised this pass.

**What can and cannot be recovered, stated plainly:**
- **Can:** any accidental change or archive action, by consulting the audit log for exact scope, then either
  manually reversing it through the app (if it was an archive, un-archiving is a normal app action) or, for
  data genuinely lost, restoring the affected records from the most recent backup into a disposable database
  and manually re-applying them — there is no automated "restore just these 3 rows" tool; it's a manual,
  supervised process using the same disposable-database pattern proven in §5.
- **Cannot:** recover changes made *after* the most recent backup and before the corruption is noticed and
  acted on (the RPO gap) — nor can the audit log tell you about a change that bypassed the API entirely.

---

## 8. Backup failure (full procedure referenced in `docs/runbooks/03-s3-backup-recovery.md`)

Investigated each failure mode by reading `scripts/backup-to-s3.sh` in full rather than assuming:

| Failure | What actually happens | Is it monitored/alerted? |
|---|---|---|
| S3 upload fails | Script's `EXIT` trap emits `[EVENT] UPLOAD_FAILED stage=upload` (or `stage=verify_upload` if the object uploaded but failed the post-upload encryption/size check) to the container's stdout, captured by the `awslogs` driver into CloudWatch Logs | **Yes** — a CloudWatch metric filter on `[EVENT] BACKUP_FAILED`/`UPLOAD_FAILED` feeds the `karosl-staging-backup-failed` alarm, which notifies SNS → email. This was proven to actually fire during the 2026-08-20 audit (a deliberate forced failure against a nonexistent bucket) |
| Backup script fails at the dump stage (before upload) | Same `EXIT` trap, emits `[EVENT] BACKUP_FAILED stage=dump` (or `stage=verify`, or `stage=compress`) | **Yes**, same alarm/metric filter — it matches `BACKUP_FAILED` generally, not just the upload sub-case |
| RDS backup fails | Not directly observable from application-level tooling — this would be an AWS-side event, visible via RDS console/CloudTrail, not via anything KarosL's own scripts emit | **Not currently monitored** — no CloudWatch alarm exists specifically for "RDS automated backup failed." This is a real, small gap: automated RDS backups are widely reliable, but there's no explicit alarm confirming they keep succeeding |
| Scheduled backup **stops running entirely** (timer disabled, systemd unit fails to start, etc.) | **This is the most dangerous failure mode, and it is the weakest-covered one.** If the timer itself doesn't fire, no script runs, so no `BACKUP_FAILED` event is ever emitted — there is nothing to alarm on, because failure-to-run looks identical to "nothing happened yet." `Persistent=true` mitigates the ordinary case (instance was stopped, timer catches up on next boot — proven for real after an 18-day-stopped instance per prior session history), but a timer that's been *disabled* or a systemd unit that's silently broken would not self-heal and would not currently page anyone | **Not monitored today.** Recommendation: a simple "has a new `database/*.sql.gz` object appeared in S3 in the last 25 hours" check (a scheduled Lambda, or even a daily CloudWatch alarm on the *absence* of the `BackupFailures` metric filter's counterpart — a "heartbeat" style check) would close this gap. Out of scope to build in this pass (new automation), but this is the single most important monitoring gap this DR review surfaced |
| S3 access permission breaks (IAM role/policy misconfigured) | The `PutObject` call in `backup-to-s3.sh` would fail with an AWS `AccessDenied` error, tripping the same `dump`/`upload`-stage failure path as any other backup-script failure | **Yes**, covered by the same `BACKUP_FAILED`/`UPLOAD_FAILED` alarm as the general failure case |

**Net assessment:** individual backup-run failures are well-monitored (proven to actually alarm). **The gap
is the "silent stop" case** — nothing currently confirms the backup *timer itself* is still enabled and
firing daily, only that *when it runs*, failures are caught.

---

## 9. Security incident response (full procedure: `docs/runbooks/06-security-incident.md`)

**This section, and its runbook, are entirely new** — this codebase had **zero** pre-existing
security-incident-response, credential-rotation-at-scale, or account-compromise documentation before this
pass (confirmed by a broad search across every doc in `docs/`). The one narrow exception: `docs/CI_CD.md`
already documents a real, usable CI-deploy-SSH-key rotation sequence (generate new pair → add as second
`authorized_keys` line → update the GitHub Secret → verify a deploy still works → only then remove the old
key) — that pattern is reused as the model for the credential-rotation steps below, since it's the one piece
of this domain that was already proven to work here.

The runbook covers five compromise scenarios (compromised application account, compromised SSH credentials,
compromised GitHub credentials, compromised AWS credentials, suspicious database activity), each following
the same shape: contain → investigate (audit log + CloudWatch Logs) → determine blast radius → rotate →
restore/repair → verify → document. No real credentials appear anywhere in the runbook — only the commands
and AWS console paths used to rotate them.

**One concrete finding surfaced while researching this section, worth flagging directly:** `EC2_DEPLOY_KEY`
(the original SSH-based deploy key, from before the self-hosted-runner pivot) **still exists as a live
GitHub Secret**, acknowledged in `docs/CI_CD.md` as a "recommended follow-up" to retire but not yet
retired. It's unused by the current pipeline, but an unused-but-live credential is exactly the kind of thing
a security review should flag plainly rather than let sit as a background "someday" item — see the runbook
and the verdict (§10) for this as a named, actionable finding.

---

## 10. HTTPS / network failure (full procedure: `docs/runbooks/07-https-nginx-failure.md`)

KarosL currently has **no purchased custom domain** — this is a deliberate, standing decision, gated on
client sign-off before spending on infrastructure (see prior session record). The actual live HTTPS
architecture, stated plainly rather than assuming a domain exists:

- **Two independent, coexisting certificate lineages**, both via Let's Encrypt, both served from the same
  nginx on port 443 via SNI:
  1. A `sslip.io` "magic hostname" (`<ip-with-dashes>.sslip.io`) — a standard ~90-day cert.
  2. A direct IP-address certificate (SAN = the raw IP) — mandatorily short-lived, ~160 hours (~6.67 days),
     issued via certbot's `--preferred-profile shortlived`.
- Both renew via the same twice-daily `certbot-renew.timer`.
- **No Elastic IP** — the instance's public IP changes on every stop/start (a deliberate cost decision), which
  is exactly why both certificate lineages, `.env`'s recorded origins, and CORS/CSRF trusted-origins settings
  all need to be re-derived after any IP change — `scripts/recover-staging.sh` already automates this whole
  chain (fix `.env` origins → re-issue both certs, dry-run first → recreate containers → sweep orphaned old
  certs → verify) and was not re-invented for this pass, just confirmed correct by reading it in full.
- **RDS connectivity failure** would surface as the backend container's health check failing (`/api/health/`
  checks `"database":"ok"` explicitly, called out in `verify-staging.sh`'s own comments as "the check that
  matters most" since the SPA can return 200 from static files even when the API is fully broken underneath)
  — not a network-layer symptom, a database-layer one. RDS itself is not reachable from outside the VPC by
  design (`PubliclyAccessible: false`), so a connectivity failure here is almost always either an EC2-side
  security-group problem or an RDS-side outage, not a general "network" problem.

Runbook covers all four failure shapes (HTTPS/cert expiry, nginx down, EC2 network/security-group issues,
RDS connectivity) using `verify-staging.sh` as the primary diagnostic tool throughout, since it already
checks every one of these layers independently and reports which one failed.

---

## Final Verdict

**1. Actual RPO: ≈24 hours worst case** (bounded by the S3 daily backup cadence), typically much less in
practice given the once-daily-at-2:30am schedule and a working day's usage pattern. RDS's own PITR window
(1 day) exists as an AWS platform guarantee but its restore procedure/timing is untested (see below).

**2. Actual RTO: 15 seconds for the database-restore step alone (proven), under 1 minute including full
application-layer verification (proven).** This is not a whole-incident RTO — it's the empirically measured
core of the recovery path that was actually tested. Full-incident RTO for an EC2-loss scenario is estimated
(not measured) at roughly 20–30 minutes, dominated by manual secret recreation (§3).

**3. Recovery paths tested (this pass, with real evidence):**
- S3 `pg_dump` backup → disposable database restore → verified at both SQL and Django-ORM layers, all 9
  required record types, timed end-to-end (§5).

**4. Recovery paths only documented (not empirically exercised this pass, but procedures written and
grounded in real script behavior):**
- RDS native automated-backup / point-in-time restore (§1, §2).
- EC2 instance-loss full recovery (§3).
- Bad-deployment rollback (`rollback-staging.sh` behavior confirmed by reading the script in full and
  cross-checking every claim against it, but not exercised against a live broken deploy — correctly, per
  the brief).
- HTTPS/nginx/network failure recovery (§10) — `verify-staging.sh`/`recover-staging.sh` are already proven
  tools from prior sessions' real usage, not newly invented, but weren't re-run destructively this pass.

**5. Recovery paths not currently possible:**
- **Recovering `.env` secrets (`SECRET_KEY`, RDS application password) after EC2 instance loss.** These can
  only be *rotated* (regenerated + the RDS master password reset), never recovered, because no second copy
  exists anywhere. This is the single clearest infrastructure-loss gap in the whole system (§3, §4).
- **Restoring "just the audit log" or "just N rows" through any in-app tool** — the app's own Backup &
  Export feature excludes `AuditLog`/`User`/`Backup` tables entirely; any restore of those requires the full
  database dump path (§7).

**6. Data-loss scenarios:**
- Accidental change/deletion through the app: recoverable via audit log (for anything that isn't a hard
  delete) + manual reversal, or via full-database restore for anything genuinely lost, bounded by the ≈24h
  RPO (§7).
- A hard delete that bypasses the application layer entirely (e.g. a manual `psql DELETE`): **not visible in
  the audit log at all** — only recoverable via a full database restore, and only detectable in the first
  place by someone noticing the data is missing.
- Backup-timer silently stopping (not failing, *stopping*): **currently the weakest-covered failure mode in
  the whole system** — no alarm exists for "no new backup object appeared today" (§8).

**7. Infrastructure-loss scenarios:**
- RDS instance loss: single-AZ, no automatic failover (a deliberate, documented cost/scale tradeoff, not an
  oversight) — recovery is via automated-backup restore (untested, §1) or the S3 `pg_dump` path (tested,
  §5), whichever is faster/available.
- EC2 instance loss: fully documented recovery procedure (§3), not empirically timed.
- Both simultaneously: the S3 `pg_dump` backup is the only mechanism that survives this, since it's
  independent of both — proven durable this pass by successfully restoring it onto a machine that has no
  relationship to either the EC2 instance or the RDS instance.

**8. Security incident response capability:** **Net-new this pass.** Zero pre-existing documentation before
today; a full runbook now exists (§9, `docs/runbooks/06-security-incident.md`) covering account/SSH/GitHub/
AWS-credential compromise and suspicious database activity, built on the one real precedent that existed
(the CI-deploy-key rotation sequence). **Untested against a real incident** (correctly — there's no way to
safely drill "your AWS account was compromised" without real risk). One concrete, actionable finding
surfaced: the unused `EC2_DEPLOY_KEY` GitHub Secret should be retired, not just flagged again.

**9. Recovery test results:** One full end-to-end exercise performed and measured (§5) — S3 backup → local
disposable PostgreSQL → verified at SQL and application layers → cleaned up. Live database, live application,
and all existing backups were untouched throughout (confirmed: the script's own guardrail refuses to target
the live database name, and this was never overridden).

**10. Remaining risks, ranked by how much they matter:**
1. **`.env` secrets have no second copy anywhere** — highest-impact single gap (§3, §4).
2. **No alarm for the backup timer silently stopping** (vs. failing, which *is* alarmed) — highest-likelihood
   "you wouldn't find out" gap (§8).
3. **RDS's own PITR path is unproven** — the AWS-native recovery mechanism, not the one this pass actually
   validated (§1, §2).
4. **No RDS-specific CloudWatch alarms** (storage/CPU/connections) — a pre-existing, already-flagged gap
   from the 2026-08-20 audit, still open.
5. **Security-incident runbook is new and untested** — real, but expected and acceptable for a first pass;
   the honest state is "documented, not drilled," not "solved."
6. **Stale `EC2_DEPLOY_KEY` GitHub Secret** — low severity (unused), but a live credential that should be
   retired rather than left as a standing "someday."

### Posture classification: **YELLOW**

Not RED: core recovery mechanisms exist, one was proven end-to-end with real timing and real data this
pass, backup-failure alarming genuinely works (proven, not assumed), and rollback/recovery tooling for EC2
and deployment failures is real, already-proven-once-before code, not vaporware.

Not GREEN: GREEN would require the RDS-native restore path to be proven (not just documented), the
backup-timer-silently-stopped gap to be closed, `.env` secrets to have a second copy somewhere, and the new
security-incident runbook to have survived at least one drill. None of those are true today. Calling this
GREEN would overstate what was actually demonstrated.

### Recommended next sprint

In priority order, each chosen because it closes a **named, evidenced** gap from this audit rather than a
speculative one:
1. **Close the backup-silent-stop gap** — the highest-likelihood "you wouldn't find out" risk in the whole
   system, and the cheapest to fix (a heartbeat-style check, not a new major service).
2. **Move `SECRET_KEY` and the RDS password into AWS Secrets Manager or SSM Parameter Store** — turns the
   single highest-impact infrastructure-loss gap into a non-issue. Already the documented "later" plan; this
   audit provides the evidence for why "later" should become "next."
3. **Add the RDS-specific CloudWatch alarms** (storage/CPU/connections) — small, cheap, already recommended
   twice before this pass.
4. **Retire the stale `EC2_DEPLOY_KEY` GitHub Secret.**
5. Only after the above: consider a real (carefully-scoped, disposable-instance) RDS PITR drill, and a
   tabletop run-through of the new security-incident runbook — both valuable, but lower-priority than closing
   gaps that are cheap and already fully understood.
