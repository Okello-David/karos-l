# Changelog

## [Unreleased]

### Added / Fixed — Operational Cleanup and Observability sprint (2026-08-24)
- **RDS monitoring added**: 3 new CloudWatch alarms — `karosl-staging-rds-low-storage`
  (`FreeStorageSpace` < 2 GiB, 2×5min), `karosl-staging-rds-high-cpu` (`CPUUtilization` > 80%, 3×5min),
  `karosl-staging-rds-high-connections` (`DatabaseConnections` > 40, 2×5min) — thresholds chosen from real
  24h metric data pulled via `aws cloudwatch get-metric-statistics` immediately before creating them (free
  storage averaging ~18.3 GiB/20 GiB, CPU averaging 3.6%, connections ~0), not guessed. All three wired to
  the existing SNS topic (`karosl-staging-alerts`). **Verified end-to-end**: `karosl-staging-rds-high-cpu`
  manually forced to `ALARM` via `aws cloudwatch set-alarm-state`, `describe-alarm-history` confirmed the
  SNS publish action `"actionState":"Succeeded"`, then reset to `OK`. Total alarms: 7.
- **SNS re-confirmed** live via `aws sns list-subscriptions-by-topic` (real ARN, not `PendingConfirmation`)
  — no action needed, no duplicate subscription created.
- **Obsolete SSH CI/CD infrastructure retired**: confirmed via full workflow reads that `EC2_DEPLOY_KEY`
  and `EC2_USER` have zero references anywhere in current workflows/scripts (the self-hosted runner's
  `deploy` job runs `deploy-staging.sh --pull` directly, no SSH hop) — `EC2_HOST` is the one secret still
  actively used (by the `smoke-test` job) and was kept. Deleted `scripts/ci-deploy-entrypoint.sh` (confirmed
  dead — the SSH forced-command entrypoint the old key used to invoke) and the `EC2_DEPLOY_KEY`/`EC2_USER`
  GitHub Secrets. Fixed two stale claims in `docs/CI_CD.md` found during this review (an inaccurate
  `webfactory/ssh-agent` reference that never matched the actual workflow, and SSH-specific troubleshooting
  entries for a mechanism that no longer exists).
- **Real bug found and fixed**: `scripts/recover-staging.sh`'s container-recreation step omitted the
  CloudWatch and RDS compose overlays that `deploy-staging.sh`/`rollback-staging.sh` both correctly include
  — a real risk that a future recovery, triggered while RDS is live, would silently regress the backend's
  database connection back to the local container and drop CloudWatch log shipping. Fixed with the same
  conditional overlay-inclusion logic already used in the other two scripts; verified the logic produces the
  correct file list for both the RDS-live and pre-RDS cases.
- **Real bug fixed**: the known payment-recording double-success-toast issue
  (`docs/PRODUCTION_READINESS_REVIEW.md`, found 2026-08-20) was root-caused precisely —
  `OccupantDetail.jsx`'s `handlePaymentRecorded` callback fired its own `addToast` in addition to the one
  `RecordPaymentDialog` already fires for the same single API call. **Confirmed not a duplicate write**
  (single `POST /api/payments/` call; `Toast.jsx` has no dedup, so both calls simply both rendered). The
  identical pattern also existed for occupancy assignment in the same file
  (`handleAssigned`/`AssignOccupancyDialog`) — fixed both, removing the redundant parent-level `addToast`
  calls. New regression test `frontend/src/test/OccupantDetail.test.jsx` — verified it actually catches the
  regression by temporarily reintroducing the bug, confirming the test failed, then restoring the fix and
  confirming it passed again.
- **`.env.example` drift fixed**: added `DB_SSLMODE` (read by `settings.py`, required for the RDS
  connection, previously entirely absent from the example file); replaced a stale "Database (unchanged from
  local... `DB_HOST=db`)" comment block that predated the RDS migration with guidance for both the
  container-Postgres and RDS setups.
- **Backup JSON exports (`BackupService`) reviewed**: confirmed still a live, working, Super-Admin-gated
  feature (not obsolete/dead code), genuinely persisted via the `backend_backups` Docker volume. Documented
  (not implemented) a proposed future improvement — optionally mirroring its JSON output to S3 — since no
  evidence of an active need exists. Separately, untracked 153 backup JSON files
  (`git rm --cached`, `backend/backups/`) that predated a 2026-07-29 `.gitignore` fix and were still
  tracked in git; the files remain on disk, only removed from version control.
- **Old PostgreSQL container**: checked again with the actual date math — 7-day validation window from the
  2026-08-19 RDS cutover closes 2026-08-26, so as of this sprint (2026-08-24) 2 days remained. Left
  untouched, per the documented plan.
- **Cost review**: confirmed already lean — no NAT Gateway, no load balancer, no unused Elastic IP, minimal
  EBS/CloudWatch-log footprint. Nothing found requiring action. The unrelated `dc-intern-backend`
  instance/EIP confirmed present but not touched, per explicit scope.
- **Testing**: full backend suite 282/282, frontend lint clean (pre-existing warnings only), frontend tests
  53/53 (52 baseline + 1 new), frontend build clean.

### Fixed — RBAC hardening: user-management privilege escalation, named permission classes (2026-08-24)
- **Critical fix**: `AdminUserViewSet` (`backend/apps/administration/views.py`) required only
  `IsPropertyManager` for full user-account management (create/update/deactivate/list). Its update path
  (`AdminUserCreateSerializer`) has a writable `password` field — `is_superuser` was already read-only, so a
  Property Manager couldn't flip that flag directly, but **could reset any user's password, including a
  superuser's, via `PATCH /api/admin/users/<id>/`, then log in as that account.** A live
  privilege-escalation path, found and fixed this pass. Now requires `CanManageUsers` (`IsSuperAdmin`).
- **New named, per-capability permission classes** in `backend/apps/core/permissions.py`:
  `CanManageProperty`, `CanManageOccupants`, `CanManageOccupancy`, `CanRecordPayment`, `CanManageUsers`,
  `CanViewAuditLog`, `CanManageBackups` — thin subclasses of `IsPropertyManager`/`IsSuperAdmin`, no new
  authorization logic, applied across every business/admin/audit/backup viewset so each states its actual
  intent instead of a generic role name repeated at every call site.
- **Real bug fixed**: `OccupancyViewSet.summary` (aggregate dashboard stats — occupancy counts, rate,
  per-property breakdown, no per-occupant detail) had been accidentally swept into the Property-Manager-only
  gate along with occupancy's write actions during the earlier same-day permission-gap fix. Since the
  Dashboard/Overview page depends on this endpoint for every authenticated user, this would have broken the
  landing page for any Staff-tier user. Split out via `get_permissions()` to stay `IsAuthenticated`.
- **Formal 3-role RBAC matrix documented**: Super Administrator, Property Manager, Staff — new
  `docs/ARCHITECTURE_DECISIONS.md` (4 dated decision records: the role model, the AdminUserViewSet fix,
  property-scoping as a documented limitation not built this sprint, and why no object-level checks were
  added) and new `docs/SECURITY_HARDENING.md` (full endpoint-to-permission map, the finding, testing
  summary, known limitations).
- **Property-level scoping**: investigated and confirmed no `User`↔`Property` data model exists anywhere
  (no FK/M2M, checked models and migrations). Documented as a known, deliberate limitation rather than built
  this sprint — every Property Manager is equally trusted org-wide today, matching a single-organization,
  multi-property tool rather than multi-tenant SaaS. Flagged as a future product decision if delegated
  per-property managers are ever needed. See `docs/ARCHITECTURE_DECISIONS.md` AD-003.
- **Expanded test coverage**: new `AuthorizationMatrixTests` in `backend/apps/core/tests.py` — cross-role
  (unauthenticated/Staff/Property Manager/Super Admin) coverage including explicit elevation-prevention
  tests (a plain authenticated user never gains write access merely by being authenticated) and
  ID-substitution tests (a real, existing object's ID does not bypass a permission check that would
  otherwise deny access — including the specific AdminUserViewSet password-reset path, verified via a
  before/after password-hash comparison). New regression tests in
  `backend/apps/administration/tests.py` for the AdminUserViewSet fix specifically. **Full backend suite:
  281/281** (260 baseline + 21 new).
- **Frontend permission alignment** (UX only — backend authorization remains authoritative): new
  `frontend/src/utils/permissions.js` reads the already-returned `is_superuser`/`groups` fields from
  `authService.getUser()`. Administration's Users/Audit Log tabs hidden from non-superusers
  (`Administration.jsx`); Occupants/Payments/Administration/Backup nav items hidden from users who can't
  access them at all (`Sidebar.jsx`); Dashboard's write-only quick actions and Property-Manager-gated stat
  card/table sections hidden or given an "unavailable" state for Staff, rather than shown and erroring on
  use (`Dashboard.jsx`). Frontend test suite: 52/52 passing; build clean.

### Added — Disaster recovery & incident response documentation and testing (2026-08-24)
- **New `docs/DISASTER_RECOVERY.md`**: full DR/IR review — RPO/RTO objectives with evidence, database/EC2/
  application/deployment/data-corruption/backup-failure/security-incident/HTTPS-network recovery analysis,
  the results of a real recovery exercise performed this pass, and a final posture verdict. **Posture:
  YELLOW.**
- **New `docs/runbooks/`**: 7 procedural runbooks (`01-ec2-failure.md`, `02-rds-recovery.md`,
  `03-s3-backup-recovery.md`, `04-bad-deployment.md`, `05-database-corruption.md`,
  `06-security-incident.md`, `07-https-nginx-failure.md`), each with symptoms/severity/immediate
  actions/investigation/recovery/verification/rollback/escalation/lessons-learned sections.
- **Real recovery test executed** (not just described): `scripts/restore-from-s3.sh --latest` run against
  the real S3 backup bucket, restoring the newest backup (`karosl_db_2026-08-24_024045.sql.gz`) into a
  disposable local database (`karosl_dr_test_20260824`) — never the live database, never the local dev
  database. Verified via raw SQL and independently via the Django ORM (with `DB_NAME` overridden) across all
  9 required record types: properties (5), sections (5), units (13), occupants (19), occupancies (17, 14
  active), payments (16, summing to a coherent total), receipts (16), audit log (53), users (1). **Restore:
  15 seconds. Full verification: under 1 minute.** Disposable database dropped after verification; live
  database and existing backups untouched throughout.
- **`docs/runbooks/06-security-incident.md` is entirely net-new content** — confirmed via full-corpus search
  that no security-incident-response, credential-rotation-at-scale, or account-compromise documentation
  existed anywhere in this repo before this pass. Covers 5 scenarios (compromised application account, SSH,
  GitHub credentials, AWS credentials, suspicious database activity), reusing the one real precedent that
  existed (`docs/CI_CD.md`'s CI-deploy-key rotation sequence) as the model.
- **Real gaps found and documented, not smoothed over**: RDS-native point-in-time-recovery is untested
  (would require a temporary second RDS instance, deliberately not created without asking first); no
  CloudWatch alarm exists for the backup timer silently stopping (vs. failing, which is alarmed and proven);
  `.env` secrets (`SECRET_KEY`, RDS password) exist only on the EC2 instance with no second copy anywhere —
  recoverable only by rotation, not restoration, if the instance is lost; the new security-incident runbook
  is undrilled; the stale, unused `EC2_DEPLOY_KEY` GitHub Secret should be retired.
- Updated `docs/PROJECT_STATE.md`, `docs/RELEASE_PLAN.md`, `docs/PRODUCTION_READINESS_REVIEW.md` with the
  DR sprint's findings and the next-sprint recommendation.

### Fixed — Permission gap on business endpoints (`IsAuthenticated | IsPropertyManager` no-op) (2026-08-24)
- **Blocker resolved**: 12 viewsets across 8 apps (occupants, occupancy, payments, properties, sections, units,
  dashboard, reports) used `permission_classes = [IsAuthenticated | IsPropertyManager]`. Because `IsAuthenticated`
  alone already grants access to any logged-in user, the OR gate was a no-op — any authenticated user could create
  occupants, record payments, and modify occupancy regardless of group membership. This was the audit's top blocker
  (named in `docs/PRODUCTION_READINESS_REVIEW.md` §3/§12, flagged repeatedly across prior sessions, and deferred
  for a product decision per `docs/BUG_QUEUE.md`).
- **Decision**: Any authenticated user should not be able to perform writes on business data — restricted to
  Property Manager group only. Matches the precedent already applied to `apps/administration`. Read-only endpoints
  stay open to any authenticated user (viewing data was not the audit's concern).
- **Implementation**: Tightened write-capable viewsets to `[IsPropertyManager]` (occupants, occupancy, payments);
  simplified read-only viewsets to `[IsAuthenticated]` only (removed the no-op OR). Updated test suites:
  `apps/payments/tests.py`, `apps/occupants/tests.py`, `apps/occupancy/tests.py` each now add the "Property Manager"
  group to their primary test user (previously relied on the no-op OR). Added explicit negative-path tests asserting
  403 for plain non-manager staff users trying to create/modify data, matching the pattern in `apps/administration/tests.py`.
- **Verified safe for staging**: `karosadmin` demo account is a Django superuser; `IsPropertyManager.has_permission`
  short-circuits True for any superuser, so the change will not lock it out during client review.
- **Tests**: All 257/257 backend tests pass (36 payments, 53 occupants/occupancy, plus administration, dashboard, etc.).
- **Files changed**: `backend/apps/{payments,occupants,occupancy}/views.py` (permission_classes), `backend/apps/{properties,sections,units,dashboard,reports}/views.py` (remove no-op OR), `backend/apps/{payments,occupants,occupancy}/tests.py` (group setup + negative tests).
- **Result**: This closes the sole remaining blocker from the 2026-08-20 production-readiness audit. Updated
  `docs/PRODUCTION_READINESS_REVIEW.md` (§0) and `docs/BUG_QUEUE.md` (Deferred → Fixed).

### Fixed — SNS subscription confirmed, one of two audit blockers closed (2026-08-20, later the same day)
- Confirmed the `karosl-staging-alerts` SNS email subscription (`grbsderrick@gmail.com`), previously
  `PendingConfirmation` per the production-readiness audit — found the AWS confirmation email and
  clicked "Confirm subscription," then **independently verified via `aws sns list-subscriptions-by-topic`**
  (SubscriptionArn is now a real ARN, not `PendingConfirmation`). CloudWatch alarms now actually reach that
  inbox. Documentation-only change: added a dated update section to `docs/PRODUCTION_READINESS_REVIEW.md`
  (§0) rather than rewriting the original audit findings, which are preserved as written. **Closes the
  SNS-notification blocker; the permission gap (`IsAuthenticated | IsPropertyManager`) remains the sole
  outstanding blocker from the audit** (now resolved — see above).

### Added — Production-readiness audit and hardening (2026-08-20)
- **New `docs/PRODUCTION_READINESS_REVIEW.md`**: full audit against the live pilot covering architecture,
  security, database, backups, monitoring, CI/CD, cost, 12 failure-mode scenarios, and an evidence-based
  RPO/RTO assessment. **Verdict: READY WITH LIMITATIONS**, two named blockers (permission gap requiring a
  product decision; unconfirmed SNS email subscription).
- **Real bug fixed**: `backend/config/settings_production.py`'s `DB_SSLMODE`/`OPTIONS` TLS-enforcement
  logic was never actually loaded by Django (`DJANGO_SETTINGS_MODULE` always resolves to `config.settings`).
  Ported the same logic into `config/settings.py`, guarded to skip SQLite. Backend suite re-verified
  257/257 on both SQLite and Postgres.
- **CI/CD pipeline moved to a self-hosted runner** (`.github/workflows/deploy-staging.yml`): the pipeline's
  first-ever real GitHub Actions run failed — SSH from GitHub-hosted runners could never reach the
  instance (security group correctly restricts SSH to one `/32`; GitHub's published IP range, 5,645
  CIDRs, can't fit in a security group). Installed a self-hosted runner directly on the EC2 instance
  instead (systemd service, label `karosl-staging`), with a documented security invariant: never
  reachable from `ci.yml` or any fork-PR-triggerable workflow, since this repo is public. A `smoke-test`
  job stays on a GitHub-hosted runner so external reachability is still independently verified.
- **Second real bug fixed**: `scripts/deploy-staging.sh`'s password sanity check required
  `POSTGRES_PASSWORD` (the now-unused container's password) to equal `DB_PASSWORD` unconditionally — true
  only pre-RDS, and it broke every deploy since the RDS migration. Gated on the same `$_db_host` check
  already used for the RDS compose overlay.
- **First fully green end-to-end pipeline run**: all six jobs (backend ×2, frontend, Docker build, deploy,
  external smoke test) passed for real, confirmed independently via `./scripts/verify-staging.sh` (12/12).
- **CloudWatch `backup-failed` alarm investigated**: root cause was a deliberate test (upload to a
  nonexistent bucket, to prove the alarm fires), not a real incident. Working as designed; no fix needed.
- **Full live smoke test performed** through the real UI: login, dashboard, Property Explorer, a full
  property→section→unit→occupant→occupancy→payment→receipt→audit-trail chain with labeled test data
  created and cleaned up, and logout — every write independently confirmed via the Audit Log.
- **Small, safe hardening fixes**: `.gitignore` gained SSH-key patterns (`*.pem`, `*_rsa`, `*_ed25519`);
  untracked a stray gitignored log file; corrected a stale `ci.yml` baseline comment
  (237/237→257/257 backend, 45/45→52/52 frontend, 8→7 lint warnings); fixed two doc inaccuracies (the
  backup IAM role's real scope also covers CloudWatch Logs/metrics, not S3-only; a stale "still no RDS"
  claim in `docs/AWS_STAGING_CHECKLIST.md`).
- **Deliberately not fixed**: the `IsAuthenticated | IsPropertyManager` permission gap (confirmed still
  open on 8+ business viewsets) — flagged as the top blocker, left for a product decision per this pass's
  explicit scope, matching the team's existing stance in `docs/BUG_QUEUE.md`.

### Added — Amazon RDS PostgreSQL migration (2026-08-19)
- **New RDS instance `karosl-staging-postgres`**: PostgreSQL 16.14, `db.t4g.micro`, Single-AZ, 20 GiB gp3
  (autoscaling to 30), storage-encrypted, deletion protection enabled, publicly inaccessible. New security
  group `karosl-rds-sg`, ingress TCP 5432 from the EC2 app's security group only — no `0.0.0.0/0`. New DB
  subnet group across two AZs.
- **New `scripts/migrate-to-rds.sh`**: one-time dump/restore/verify migration tool, reusing
  `backup-to-s3.sh`'s dump-verification pattern. Row counts for all 9 record types confirmed identical
  between source and RDS before cutover.
- **`backend/config/settings_production.py`**: additive `DB_SSLMODE` support, inert without the env var.
  Deployed ahead of the data cutover.
- **New `docker-compose.rds.yml`** overlay, overriding `DB_HOST`/`DB_PORT` for the backend service — found
  necessary when the first cutover attempt crash-looped the backend, because `docker-compose.yml`'s base
  `environment:` block hardcodes both and beats `env_file`. `deploy-staging.sh`/`rollback-staging.sh`
  updated to include this overlay only when `.env`'s `DB_HOST` genuinely points away from `db`.
- **`scripts/backup-to-s3.sh` and `scripts/restore-from-s3.sh` made `DB_HOST`-aware**: both previously
  hardcoded operating against the local `db` container; since that container is deliberately kept running
  as a rollback safety net post-migration, its presence alone could no longer signal which database is
  live. Both now dump/restore over the network when `DB_HOST` points at RDS, still via the container's own
  `pg_dump`/`psql` binaries. Both run for real against RDS post-cutover: backup landed and verified
  encrypted in S3; restore into a disposable database on RDS matched the known-good row counts.
- **AWS Budget raised from $5 to $30/month** (account-wide, shared with an unrelated project) before RDS
  was created — the $5 ceiling was already breached ($9.37 actual spend).
- New `docs/RDS_MIGRATION.md`. `docker-compose.yml`'s `db` service and the old container/volume are kept,
  not removed, as a rollback safety net for a defined validation window.

### Added — Safe CI/CD pipeline (2026-08-19)
- **New `.github/workflows/deploy-staging.yml`**: `push` to `cloud-deployment` only (never PRs, never other
  branches) → backend tests (SQLite+PostgreSQL) → frontend lint/test/build → Docker build validation → (all
  must pass via `needs:`) → SSH deploy → external smoke test. `concurrency: group: staging-deploy,
  cancel-in-progress: false` — only one deploy at a time, queued not cancelled.
- **`ci.yml`**: `cloud-deployment` removed from its trigger (now `dev` + PRs only) so the same push doesn't
  run the test suite twice across two workflows.
- **Dedicated, forced-command-restricted SSH deploy key** — not the operator's admin key. Its
  `authorized_keys` entry (`command="...ci-deploy-entrypoint.sh",no-pty,...`) means whatever a client
  requests, sshd runs the entrypoint instead; a leaked key's blast radius is "trigger a deploy," not
  "arbitrary shell." New `scripts/ci-deploy-entrypoint.sh`. Private key piped straight from a scratch file
  into `gh secret set`, never printed. New GitHub Secrets: `EC2_HOST`, `EC2_USER`, `EC2_DEPLOY_KEY` — exactly
  these three, confirmed via `gh secret list`.
- **Three real bugs found and fixed during manual pre-CI testing** (the entire point of testing manually
  before enabling automation): (1) `scripts/deploy-staging.sh` never applied the HTTPS/CloudWatch compose
  overlays — running it as previously documented dropped port 443 on the live pilot for several minutes,
  caught by an external check and fixed immediately, then fixed at the root with a `COMPOSE_FILES`
  auto-detection used for every `docker compose` call in both `deploy-staging.sh` and the new
  `rollback-staging.sh`; (2) the internal health check hit plain HTTP, which 301-redirects to HTTPS under
  the overlay, and `curl -f` doesn't treat a 301 as failure — fixed by checking response content instead of
  exit code, matching `scripts/verify-staging.sh`'s existing correct pattern; (3) `rollback-staging.sh`'s
  dirty-working-tree guard used `git status --porcelain`, which flags harmless untracked files the same as
  real uncommitted changes, even though `git checkout` never touches untracked files — fixed to check
  tracked-file modifications specifically.
- **The port-443 incident from bug (1) recurred a second time** while testing "roll forward" after a
  rollback: checking out `cloud-deployment` and re-running `deploy-staging.sh` restored the still-unfixed,
  already-committed version of the script, since the fix existed only as an uncommitted local patch at that
  point. Same immediate restoration; the recurrence itself is the concrete reason this pass is committed and
  pushed promptly rather than left as local changes. Full log: `docs/CI_CD.md` §14.
- **`scripts/deploy-staging.sh` extended** (not rewritten): branch verification (refuses to deploy off
  `cloud-deployment` without an explicit `--branch=` override), a pre-deploy backup via the existing
  `scripts/backup-to-s3.sh` (`--no-backup` to skip), an explicit visible migration step (redundant with the
  entrypoint's own automatic migration, but gives CI logs a clearly-labeled section), and a deploy-history
  record (`~/.karosl-deploy-history`) for rollback to read.
- **New `scripts/rollback-staging.sh`**: reads the previous known-good commit from the deploy history (or an
  explicit `--to=<sha>`), checks it out, rebuilds, restarts, verifies. Never touches the database or
  volumes; explicitly does not attempt automated migration downgrades — a documented limitation of
  code-only rollback (no container registry, per this session's own cost/complexity constraints), not a
  silently-ignored gap.
- New `docs/CI_CD.md`. No RDS, ECS/Fargate, container registry, or other new AWS service introduced.

### Added — Basic CloudWatch observability (2026-08-19)
- **3 CloudWatch Logs groups**, 14-day retention: `/karosl/staging/django` (Django's existing WARNING+
  `karosl.log`), `/karosl/staging/nginx` (frontend container stdout via Docker's `awslogs` logging driver,
  new `docker-compose.cloudwatch.yml` overlay), `/karosl/staging/backup` (backup script `[EVENT]` output).
- **CloudWatch Agent installed** (`amazon-cloudwatch-agent`, 1.300067.1 via dnf) for file-based log tailing
  and `disk_used_percent`/`mem_used_percent` metrics at 5-minute resolution. Config at
  `deploy/cloudwatch/cloudwatch-agent.json`. Confirmed the installable version predates native journald
  support before designing around it, rather than assuming either way.
- **`deploy/systemd/karosl-backup.service`**: `ExecStart` now tees through `set -o pipefail; ... | tee -a
  ~/logs/karosl-backup.log`, giving the agent a stable file to tail without changing the existing
  `journalctl -u karosl-backup.service` behavior. The `pipefail` is load-bearing — without it a failed
  backup would report success to systemd. New `deploy/logrotate.d/karosl-backup` keeps that file small.
- **2 CloudWatch Logs metric filters** on `/karosl/staging/backup` → `KarosL/Staging` namespace:
  `BackupFailures` (matches `[EVENT] BACKUP_FAILED`/`UPLOAD_FAILED`) and `BackupSuccesses`. This is the
  monitoring integration `docs/S3_BACKUP_ARCHITECTURE.md` §11 described as deferred future work earlier
  today. Verified for real with a deliberate forced upload failure — metric incremented within ~1 minute.
- **4 CloudWatch alarms** → 1 new SNS topic (`karosl-staging-alerts`, email subscription pending
  confirmation) → 1 email: EC2 status-check-failed, sustained high CPU, low disk, backup failure. Each
  documented with threshold, notification behavior, and expected response in
  `docs/CLOUDWATCH_MONITORING.md`.
- **1 dashboard** (`KarosL-Staging`): CPU, status check, disk, backup successes/failures, alarm status.
- **New IAM inline policy** `karosl-cloudwatch-logs-metrics` on the existing `karosl-staging-backup-role` —
  `logs:*` scoped to `/karosl/staging/*`, plus `cloudwatch:PutMetricData` (the one action AWS doesn't
  support resource-scoping on). No new role, no long-lived credentials.
- **Two real bugs caught and fixed during setup**: (1) the tee-wrapper pipeline would have silently
  swallowed backup failures without `pipefail` — caught before relying on it, verified `systemctl is-failed`
  still reports correctly; (2) the disk alarm initially sat in a false `ALARM` because the CloudWatch Agent
  auto-tags `disk_used_percent` with dimensions the first alarm definition omitted — caught by comparing the
  alarm's `INSUFFICIENT_DATA`/missing-data reason against real `df -h` output, fixed, reverified against
  real data.
- New `docs/CLOUDWATCH_MONITORING.md`. No RDS, load balancer, NAT Gateway, or ECS/Fargate created.

### Added — S3 backup: explicit encryption check + monitoring-event structure (2026-08-19)
- **`scripts/backup-to-s3.sh`** now checks the uploaded object's actual `ServerSideEncryption` field via
  `head-object` (not just the bucket's default-encryption setting) and `die`s if it's empty; prints
  `encrypted: AES256` on success. Verified against a real upload.
- **Both `backup-to-s3.sh` and `restore-from-s3.sh`** now emit `[EVENT] BACKUP_STARTED`, `BACKUP_SUCCEEDED
  key=... bytes=... version=...`, `BACKUP_FAILED stage=...`, `UPLOAD_FAILED stage=...`,
  `RESTORE_TEST_SUCCEEDED key=... target_db=...`, and `RESTORE_TEST_FAILED stage=...` markers — a
  structured vocabulary a future CloudWatch Logs metric filter can match on. `--list`/`--dry-run` emit
  nothing (no real attempt happened). Verified on both paths: a real backup+restore produced
  `BACKUP_SUCCEEDED`/`RESTORE_TEST_SUCCEEDED`, and a deliberately-broken run (nonexistent bucket) produced
  `UPLOAD_FAILED stage=upload` with exit code 1 — the failure path fires correctly, not just the happy one.
- No CloudWatch resources created — this prepares the log structure only, per the brief's explicit "prepare
  the structure so CloudWatch monitoring can be added later," not "add monitoring now."
- `docs/S3_BACKUP_ARCHITECTURE.md` §§11–12 document the full event vocabulary and what a future CloudWatch
  setup would match against each marker.

### Added — S3 backup restructure + restore automation (2026-08-19)
- **New `scripts/restore-from-s3.sh`.** Automates the previously-manual disposable-database restore
  procedure (`docs/DEVOPS.md` §12). Cannot reach the live database under any flag combination — hard-refuses
  if `--target-db` matches the live `POSTGRES_DB` or `postgres`. Verified for real end to end: backup →
  restore → row counts matched the live database exactly → disposable database confirmed dropped → live
  database's own counts unchanged throughout.
- **`scripts/backup-to-s3.sh` restructured**: new key layout `database/karosl_db_<date>_<time>.sql.gz`
  (was `pg_dump/<year>/karosl-staging-<date>-<time>.sql.gz`); old objects left in place, nothing deleted or
  migrated. Upload confirmation now also captures and prints the S3 `VersionId`. New: after the first
  successful backup of a calendar month, an S3-to-S3 copy (no second `pg_dump`) lands at
  `database/monthly/<year>-<month>.sql.gz`.
- **Tiered S3 lifecycle**: 30-day expiration on `database/` (unchanged from before), new 400-day expiration
  on `database/monthly/`. The existing `pg_dump/` legacy rule is untouched.
- **IAM policy extended** to `database/*` (read+write), keeping `pg_dump/*` read-only for historical
  restores. Still no `s3:*`, no `s3:DeleteObject`, no other buckets — verified via `aws iam get-role-policy`.
- **New `docs/S3_BACKUP_ARCHITECTURE.md`** — the full reference: bucket, IAM policy, key layout, backup and
  restore process, retention rationale (including the documented S3 overlapping-rule/longest-retention-wins
  behavior the monthly tier relies on), security checklist, troubleshooting, disaster recovery.
- Reused the existing `karosl-staging-backups-908877263055` bucket rather than creating a new one — already
  met every requirement (private, versioned, SSE-S3, all four Public Access Block flags on), re-confirmed via
  AWS CLI before touching anything.

### Added — HTTPS via bare EC2 IP (2026-08-19)
- **`https://<EC2_PUBLIC_IP>` now shows a real, browser-trusted certificate** — a Let's Encrypt IP-address
  certificate, GA since 2026-01-15. The existing sslip.io-hostname HTTPS path was kept running unchanged,
  not replaced: two `server{}` blocks now share port 443 in `deploy/nginx/staging-https.conf.template`,
  picked via `default_server` (bare-IP/no-SNI) and SNI (hostname) respectively.
- **Certbot upgraded via an isolated venv** (`/opt/certbot-venv`, 5.7.0) rather than touching the dnf
  package (2.6.0, no IP-cert support) — required installing `python3.12` alongside the system Python 3.9,
  since certbot ≥5.0 needs Python ≥3.10. Renewal cut over via a systemd drop-in override
  (`/etc/systemd/system/certbot-renew.service.d/override.conf`), not by modifying the dnf package's files.
- **`docker-compose.https.yml`**: added `PUBLIC_IP` env var, `NGINX_ENVSUBST_FILTER` extended to
  `STAGING_DOMAIN|PUBLIC_IP`.
- **Renewal proven for real**: `certbot renew --cert-name <IP> --force-renewal` succeeded, the
  already-existing deploy-hook (`/etc/letsencrypt/renewal-hooks/deploy/reload-karosl-nginx.sh`, found from
  2026-07-31, not newly created) fired and reloaded nginx, `verify-staging.sh` was green immediately after
  with zero manual intervention.
- **`scripts/recover-staging.sh` extended** to issue/renew the IP cert alongside the hostname cert on future
  IP changes, and to sweep orphaned IP-cert lineages the same way it already swept hostname ones. Tested for
  real against the live running instance; caught and fixed a real bug in the process (the orphan-sweep
  regex needed to exclude the current IP, not just the current hostname, or it would have deleted the
  certificate it had just issued).
- **Full browser smoke test** against the bare-IP origin with a fresh login, zero console errors (no mixed
  content, no CORS, no CSRF), `AUDIT-TEST` records cleaned up afterward.
- Docs: new `docs/HTTPS_IP_CERTIFICATE.md`; updated `docs/DOMAIN_HTTPS_PLAN.md`, `docs/DEVOPS.md`,
  `docs/DEPLOYMENT.md`, `docs/AWS_STAGING_CHECKLIST.md`, `.env.example`.

### Verified — Live Pilot hardening audit (2026-08-19)
- **KarosL entered Live Pilot: staging now holds real accommodation records and runs continuously.** An
  audit, not a build — the mechanisms this phase needs (backup, recovery, HTTPS) already existed from
  2026-08-01; this pass proved they hold under real data rather than adding new ones.
- **Backup proven under the exact scenario it exists for.** `backup-to-s3.sh --dry-run` and a real run both
  succeeded (21 tables). `karosl-backup.timer` had not fired in 18 days (instance was off); its
  `Persistent=true` catch-up fired ~4 minutes after this boot, confirmed via `journalctl`, no failed units.
- **Data persistence confirmed under real load.** Row counts identical before and after a full
  `db`+`backend`+`frontend` restart (2 properties, 3 sections, 11 units, 16 occupants, 14 occupancies, 13
  payments, 13 receipts).
- **Full browser smoke test against the live HTTPS URL**, `karosadmin` login through Property Explorer:
  login, dashboard, property → section → unit creation, occupant registration, occupancy assignment,
  payment recording, receipt PDF generation. All `AUDIT-TEST`-prefixed records archived afterward; dashboard
  returned to the exact pre-test baseline. The payment and its receipt persist permanently — KarosL has no
  delete path for financial records, by design.
- **Two non-blocking findings:** a `Verify Tester` occupant left over from 2026-07-31 was never cleaned up
  (not touched today — not this audit's data to remove unilaterally); the Administration → Units page's
  property filter doesn't apply when "All Sections" is selected (section-level filtering works correctly).
- **Decision: staging no longer stops between sessions.** Live-pilot access needs the app reachable on the
  client's schedule. This makes the sslip.io IP-churn problem dormant, not fixed — see `docs/PROJECT_STATE.md`.
- **AWS footprint reconfirmed clean**: no RDS/NAT/ALB/extra EIP for KarosL (`aws ec2/rds/elbv2 describe-*`).
- Docs updated: `docs/PROJECT_STATE.md`, `docs/RELEASE_PLAN.md`, `docs/DEPLOYMENT.md`, `docs/DEVOPS.md`,
  `docs/AWS_STAGING_CHECKLIST.md`.

### Added — One-command staging recovery (2026-08-01)
- **`scripts/recover-staging.sh`** takes staging from *stopped* to *verified working* in one command, run from the workstation: start the instance (retrying AWS capacity errors) → repair the `.env` origins → issue a certificate for the new hostname → recreate the containers → delete orphaned certificates → verify from outside. **Idempotent** — re-running it against a healthy instance changes nothing and costs no Let's Encrypt quota.
- **`scripts/verify-staging.sh`** answers "is staging actually up?" honestly, from outside, exiting non-zero when it is not. Encodes the `DOMAIN_HTTPS_PLAN.md` §11 checklist — redirect, certificate identity/chain/expiry, `/api/health/`, SPA, deep link, 401 on a protected route, HSTS, and 8000/5432/5173 closed — so it stops being a list someone re-types from memory.
- **Why this was needed:** the instance has no Elastic IP, so its address changes on every start, and that had broken staging three times. The recovery was four manual steps across two machines.

### Discovered — a restart fails while reporting itself healthy (2026-08-01)
- Verified directly on the running instance: the containers store the current hostname in their environment (`STAGING_DOMAIN=...` on the frontend, `ALLOWED_HOSTS=...` on the backend) and all three run `restart: unless-stopped`. **On the next boot they come back with those stale values.**
- The result is a genuinely deceptive failure: all three containers report **healthy** — their healthchecks hit `localhost`, which never changes — and nginx serves the SPA with a **200**. Meanwhile it is presenting a certificate for a hostname that no longer resolves there, and Django returns **400 to every API call**. `docker compose ps` structurally cannot detect this, which is why `verify-staging.sh` checks from outside instead.
- **Ordering trap, now encoded in the script:** the old certificate must outlive the old containers. nginx refuses to start when `ssl_certificate` points at a missing file, so deleting the orphaned certificate *before* recreating the containers would leave the frontend unable to boot. Recreate first, delete second.
- **Also handled:** `StartInstances` can fail with `InsufficientInstanceCapacity` (it took 11 attempts on 2026-08-01), so the script retries rather than giving up; and if the workstation's own IP has moved, the security group blocks SSH — detected and reported, but only fixed with an explicit `--fix-ssh`, so a routine recovery never silently widens a firewall.

### Added — Reports built for real (2026-08-01)
- **The Reports page is no longer a placeholder.** Its three cards had shown disabled "Coming Soon" buttons since the feature was deferred from v1.0 on 2026-07-04. All three now produce real reports, viewable in the page and downloadable as CSV or XLSX. This closes the longest-standing entry in `docs/PROJECT_STATE.md`'s Known Gaps.
- **New `backend/apps/reports/`** — three read-only endpoints, **no new models and no new business rules**: `/api/reports/occupancy/` (capacity, occupied, available and occupancy rate per property), `/api/reports/financial/` (collections, outstanding, per-property split, payment-method breakdown, optional date range), and `/api/reports/occupants/` (every active occupant with assignment, contact details and balance).
- **Figures are reused, not reimplemented.** Occupancy uses the same capacity maths as `DashboardSummaryView`; balances go through `PaymentService._calculate_occupancy_charge`. A report therefore *cannot* disagree with what an occupant's own profile or the dashboard shows — which is the entire point of reusing rather than rewriting the calculation.
- **The financial date range filters payments only.** What someone owes today is not a function of which dates you happen to be looking at, so narrowing the window changes collections without pretending the debt moved with it. Covered by a test that asserts exactly that asymmetry.
- **Payments from occupants with no active unit are attributed to "Unassigned" rather than dropped.** That is a real case, not an error (BUG-022), and dropping them would make the per-property totals silently disagree with the headline figure. A test asserts the rows reconcile with the summary.
- **Guarded against the BUG-011 failure mode.** `ExportService` maps a header to a row key via a lossy `header.lower().replace(" ", "_")`; a mismatch produces a column that exists but is **always blank**, which is how three of the four original exports shipped. Headers are now declared beside their keys in `apps/reports/services`, and three tests check the transform itself, the keys the reports actually produce, and that no exported column is blank in every row.
- **Frontend:** `Reports.jsx` rewritten from placeholder to three selectable reports with summary tiles, responsive tables, a date filter, and CSV/Excel export, reusing the existing `Skeleton`/`EmptyState`/`Button` patterns and `formatUGX`. Two warts on that page fixed in passing: an unused `Card` import (one of the 8 known lint warnings) and a `window.location.href` navigation that forced a full page reload inside the SPA.

### Added — `manage.py seed_demo_data` (2026-08-01)
- **The repo's first management command.** Creates a realistic hostel dataset — 2 properties, 3 sections, 11 units, 16 occupants, 13 payments with receipts — for showing the app to someone.
- **Occupancy is deliberately uneven**: some units full, some partly filled, two left vacant. The Property Explorer's traffic-light visualisation is the strongest surface in the app and only demonstrates anything if the data exercises all three states.
- **It goes through the service layer** (`AdminService`, `StudentService`, `OccupancyService`, `PaymentService`) rather than writing rows directly, so everything it creates obeys the real validation, pricing and receipt-generation rules. A demo dataset that could not have been produced through the UI would be worse than none.
- **Safety:** refuses to run when business data already exists unless `--reset` is passed, and `--reset` deletes business data only — users, auth tokens and the audit log are never touched, since the audit trail is meant to be immutable and is also the record that the deletion happened.

### Verified — 2026-08-01
- **Backend 257/257** (237 + 20 new) and **frontend 52/52** (45 + 7 new), green in CI on **both SQLite and PostgreSQL**; `npm run build` clean; lint still exits 0 with one fewer warning.
- Exercised against the seeded dataset rather than only against fixtures: all three reports return plausible figures, per-property collections reconcile with the headline total, the date filter narrows collections while leaving outstanding unchanged, an empty future range returns zeros rather than an error, an invalid date returns 400, CSV exports have no blank columns, and the XLSX download is a real Excel workbook.

### Added — GitHub Actions CI (2026-08-01)
- **The test suites now run automatically.** New `.github/workflows/ci.yml`, triggered on pushes to `dev`/`cloud-deployment` and on every pull request. There was previously no `.github/` directory at all, so the 237-backend / 45-frontend baselines quoted throughout the docs were hand-run and hand-recorded — a regression was only ever caught if someone remembered to look.
- **Three parallel jobs, ~2m20s wall time.** Backend tests on a **SQLite *and* PostgreSQL matrix** (237/237 on both), frontend lint + test + build (45/45, build clean), and a `buildx bake` of both Docker images.
- **Why the PostgreSQL leg exists:** SQLite is the dev database, but PostgreSQL is what Docker and AWS staging run, and this codebase has already had bugs that live only at the database level (BUG-007, BUG-010 on the occupancy end-date CHECK constraint). Confirmed the legs are genuinely distinct rather than both silently SQLite — the logs show `test_karosl_ci` created on PostgreSQL against `file:memorydb_default?mode=memory&cache=shared` on SQLite. `fail-fast: false`, because when one leg fails, whether the other failed identically is usually the diagnosis.
- **Why the Docker job exists:** it builds both images from a clean checkout, which is the check that catches the class of bug where something only works locally because it was hand-installed into a developer's environment — exactly how the missing `openpyxl` dependency was found when this app was first containerized. It also sets up buildx explicitly, since Compose rejects buildx older than 0.17.0 (the incompatibility that broke the first EC2 deployment).
- **Two Compose traps handled:** `docker-compose.yml` declares `env_file: .env` and uses the `:?` operator on `POSTGRES_PASSWORD`, so Compose refuses to parse the file without a `.env` **even for a build-only invocation**. The job writes a throwaway one from the committed `.env.example` first, then runs `docker compose config --quiet` to validate the file before building.
- **Lint is gated but not made strict.** `oxlint` reports 8 pre-existing unused-import/variable warnings and exits 0, so CI catches real errors without a cleanup pass being a prerequisite for CI existing at all.
- **Deliberately absent:** no deploy step, no registry push, **no AWS credentials**. The repo is public, so anything a workflow can reach is effectively public; deployment stays the manual path in `docs/AWS_EC2_DEPLOYMENT.md`. Branch protection is a repo setting rather than a file and is left as a deliberate decision.

### Verified — CI was proven to fail, not just to pass (2026-08-01)
- A green CI that has never been shown to detect anything is not evidence of anything. A throwaway branch broke one backend assertion (`HTTP_401_UNAUTHORIZED` → `HTTP_418_IM_A_TEAPOT`) and one frontend assertion, and opened a pull request against `cloud-deployment`.
- **Both backend legs and the frontend job went red**, traced in the logs to precisely those two breaks — and the **Docker job correctly stayed green**, because the images genuinely still build. That the jobs disagreed is the point: they are independent and not falsely coupled.
- This also exercised the **`pull_request` trigger**, which the push trigger alone would never have tested. The PR was closed and both the local and remote branches deleted; the two test files are byte-identical to before.
- Noted while setting this up: the repository's default branch is **`dev`**, not `main` or `master`.

### Added — Automated PostgreSQL backups to S3 (2026-08-01)
- **Nightly `pg_dump` now ships to S3 automatically.** New `scripts/backup-to-s3.sh` (dump → verify → gzip → upload → prune local copies) and `deploy/systemd/karosl-backup.{service,timer}`, firing at 02:30 UTC. This closes the item both `docs/RELEASE_PLAN.md` and `docs/DOMAIN_HTTPS_PLAN.md` §12 rated the top remaining risk — HTTPS had made staging usable with real data while its only backup was a manual command and its only copy sat on the same EBS volume as the compute.
- **Bucket:** private (all four public-access blocks on), versioned, SSE-S3 encrypted, `eu-north-1`, with a lifecycle rule expiring objects at 30 days plus noncurrent-version and delete-marker purges — without which a nightly dump bills forever.
- **Access is an EC2 instance role** (`karosl-staging-backup-role`), so there are **no AWS keys on the box**: `aws sts get-caller-identity` returns the role ARN and `~/.aws/credentials` does not exist. The policy is scoped to `s3:PutObject`/`s3:GetObject` on the `pg_dump/` prefix and `s3:ListBucket` on that prefix only. **`s3:DeleteObject` is deliberately absent** — verified by attempting a delete and receiving `AccessDenied` — so a compromised instance can write and read backups but cannot erase backup history. Expiry is the bucket lifecycle's job.
- **`Persistent=true` on the timer.** The instance is stopped between sessions by design, so scheduled runs *will* be missed; without this the timer would skip to the following night and a stopped instance would never be backed up at all.
- **The script verifies before it trusts.** It asserts the dump is non-trivial in size and contains both `CREATE TABLE` statements and `COPY` data blocks, then confirms the uploaded object's size in S3 — an exit code alone does not catch a 0-byte dump, which looks identical to a successful one in `ls`.
- **`pg_dump` was chosen over refactoring `BackupService` to an S3 storage backend.** It is the only *complete* backup: `BackupService` covers 8 business models and deliberately excludes users, auth tokens, `AuditLog`, and `Backup` rows. Moving its JSON exports to S3 stays open as the smaller remaining half of Phase 4.
- **Scope guardrails held:** no RDS, no NAT Gateway, no load balancer, no ECS/Fargate, no Elastic IP, and **no new inbound security-group rule** — inbound is still exactly 22 (admin `/32`), 80, and 443.

### Verified — first backup, restore drill, and unattended run (2026-08-01)
- First real backup uploaded and confirmed present in S3 from an independent workstation session.
- **Restore drill: 21/21 tables match.** The dump was pulled back *from S3* rather than from the local copy, restored into a disposable `karosl_restore_test` database, and every table's row count compared against live — identical, zero errors, and the live database never touched. The drill derives its table list from the database rather than hardcoding it, so it covers `accounts_user`, `authtoken_token`, `audit_auditlog`, and `backup_backup` — precisely the tables `BackupService` cannot back up.
- **Unattended run proven through systemd**, not just by hand: `systemctl start karosl-backup.service` completed with `Finished karosl-backup.service`, and the timer is enabled with its next run scheduled.

### Fixed — staging was down again after the IP changed (2026-08-01)
- The instance had been stopped since 2026-07-31, so its public IP had moved `51.20.144.52` → `16.171.114.188`. Every API call returned `400` while the SPA still returned `200` — the same silent failure mode as last time, invisible from the home page. This is now the second occurrence, which is why the repair is scripted rather than documented again.
- **New `scripts/fix-staging-origins.sh`** reads the current public IP from IMDSv2 (no AWS credentials needed), derives the sslip.io hostname, backs up `.env`, and rewrites `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` / `STAGING_DOMAIN`. It **prints rather than runs** the certbot and compose commands: Let's Encrypt rate-limits against the shared `sslip.io` domain, so issuance stays a deliberate act. `ALLOWED_HOSTS` keeps `localhost`/`127.0.0.1`/`backend`, without which the backend container's healthcheck fails permanently while the app works fine.
- New certificate issued for `16-171-114-188.sslip.io` (expires 2026-10-30). **Re-verified:** HTTP 301s to HTTPS; `/api/health/` returns `{"status":"ok","database":"ok"}` over a browser-trusted certificate (`Verify return code: 0 (ok)`); SPA and deep-link refresh 200; `/api/properties/`, `/api/occupants/`, `/api/payments/` all 401 unauthenticated; HSTS present; 3/3 containers healthy; **`check --deploy` reports 0 issues**; no pending migrations; ports 8000/5432/5173 confirmed closed. The ACME challenge path was confirmed served over HTTP without redirect (404 for a nonexistent challenge, versus 301 for any other path), so renewal will keep working.

### Discovered — stale certificates accumulate on every IP change (2026-08-01)
- Each IP change orphans the previous hostname's certificate, and that certificate **can never renew again**, because the address no longer routes to this instance. `certbot-renew.timer` therefore begins logging a recurring failure, and the failures accumulate one per restart — a slow-growing noise source that would eventually mask a real renewal problem.
- Cleaned up this pass with `sudo certbot delete --cert-name 51-20-144-52.sslip.io`; one certificate now remains. Worth folding into `fix-staging-origins.sh` so the cleanup travels with the repair. **The strongest argument yet for a purchased domain**, which retires stale origins, stale certificates, and the shared-domain rate limit in one move.
- Renewal for the current certificate was confirmed with `certbot renew --cert-name 16-171-114-188.sslip.io --dry-run` → *"all simulated renewals succeeded"*, with the `reload-karosl-nginx.sh` deploy hook wired in. Note it takes **~6 minutes** to complete, which is long enough to look like a hang; certbot also holds a lock for the duration, so a second invocation reports *"Another instance of Certbot is already running"* rather than queuing.

### Added — Domain-based HTTPS on AWS staging (2026-07-31)
- **Staging now serves HTTPS at a domain** with a browser-trusted Let's Encrypt certificate, an HTTP→HTTPS 301 redirect, and unattended renewal. This removes the limitation that had blocked real use: the login POST no longer travels in plaintext.
- **Domain: `51-20-144-52.sslip.io`** — free wildcard DNS derived from the public IP, so a real certificate was obtained with no registrar, no DNS account, and no cost. Documented as a staging-grade choice; a purchased domain is recommended before real users.
- **Scope guardrails held:** no RDS, no NAT Gateway, no load balancer, no ECS/Fargate, no CloudFront, **no Elastic IP**, no secrets committed, PostgreSQL never exposed. Exactly one new inbound rule — **443 from `0.0.0.0/0`** (`sgr-0b29986c961ba61aa`) on `karosl-staging-sg`. Port 80 stays open deliberately: it carries the redirect *and* the `http-01` challenge that every renewal needs, so closing it would break renewal silently.
- **TLS terminates at the existing frontend nginx**, not at a load balancer — keeping the no-ALB cost guardrail intact. Certbot runs on the host in `--webroot` mode because the container owns port 80 (`--standalone` cannot bind it), and certificates are bind-mounted read-only.
- **No image rebuild was needed to enable HTTPS.** The nginx config is mounted rather than baked, with the domain injected through the official image's `envsubst` templating (`NGINX_ENVSUBST_FILTER` scoped to one variable so nginx's own `$host`/`$uri` survive). This avoids the documented `t3.micro` OOM risk on frontend builds and keeps **the real hostname out of every committed file**.
- **New:** `docs/DOMAIN_HTTPS_PLAN.md`, `deploy/nginx/staging-http.conf.template`, `deploy/nginx/staging-https.conf.template`, `docker-compose.acme.yml` (stage 1: serve the ACME challenge before any certificate exists), `docker-compose.https.yml` (stage 2: publish 443, mount certificates, flip the Django secure flags). Two stages because nginx refuses to start when `ssl_certificate` points at a file that does not exist yet.

### Fixed — staging API was down; stale origins after an IP change (2026-07-31)
- The instance had restarted and its public IP moved `13.62.49.29` → `51.20.144.52`, but the server `.env` still pinned the old address, so **every API call returned `400 DisallowedHost`**. The SPA still loaded — nginx serves static files regardless of Django — so the outage was invisible from the home page. Corrected the origins and restarted the backend; `/api/health/` returned `{"status":"ok","database":"ok"}` again. A restart runbook is now recorded in `docs/DOMAIN_HTTPS_PLAN.md` §9, since this recurs on every stop/start while there is no Elastic IP.

### Fixed — `SECURE_PROXY_SSL_HEADER` missing from the active settings module (2026-07-31)
- `backend/config/settings.py` never set it; the line exists only in `backend/config/settings_production.py`, which **nothing imports** (`DJANGO_SETTINGS_MODULE` is `config.settings`). Behind TLS-terminating nginx the request reaches Django over plain HTTP, so `request.is_secure()` is `False` and `SECURE_SSL_REDIRECT` would have redirected to HTTPS **forever**, taking the whole app down. Added as opt-in via `USE_X_FORWARDED_PROTO` (default off) rather than unconditionally, because trusting a client-settable header is only safe where clients cannot bypass the proxy — true here (Gunicorn is loopback-bound, nginx always overwrites the header), false for an exposed Gunicorn.
- Also added **`SECURE_REDIRECT_EXEMPT = [r'^api/health/$']`**: the backend `HEALTHCHECK` curls Gunicorn directly, bypassing nginx, so Django would answer 301 — and `curl -f` treats a 301 as success. The healthcheck would have kept reporting "healthy" while no longer verifying the database connectivity it exists to test. Not an external bypass: nginx still redirects every non-ACME HTTP request first.
- Made **`SECURE_HSTS_SECONDS` env-overridable** (default unchanged at one year). Staging uses **300s**: HSTS is a browser-side commitment that outlives the deployment, and the sslip.io hostname is derived from an ephemeral IP that will later belong to someone else.
- Kept `/healthz` served on port 80, un-redirected — the frontend image's `HEALTHCHECK` runs `wget http://127.0.0.1/healthz`, and following a redirect to `https://127.0.0.1/` fails certificate verification, marking a healthy container unhealthy.

### Verified — HTTPS staging, 15/15 (2026-07-31)
- `http://` → **301** to `https://`; SPA and deep-link refresh (`/dashboard`) both 200 over HTTPS; `/api/health/` → `{"status":"ok","database":"ok"}`; certificate `CN=51-20-144-52.sslip.io`, issuer Let's Encrypt, **`Verify return code: 0 (ok)`**, expires 2026-10-29; login endpoint returns a proper DRF validation error rather than a CSRF/CORS/gateway failure; `/properties/`, `/occupants/`, `/dashboard/`, `/payments/` all 401 unauthenticated; `Strict-Transport-Security: max-age=300`; all three containers `Up (healthy)`; **`manage.py check --deploy` reports 0 issues**, down from four TLS warnings; `certbot renew --dry-run` succeeded with `certbot-renew.timer` enabled and active; **8000/5432/5173 confirmed closed** from the internet, 80 and 443 open. No mixed content is possible — `VITE_API_BASE_URL=/api` is relative, so API calls are same-origin by construction.
- **Authenticated business workflow re-verified over HTTPS: 12/12** — login (40-char DRF token), dashboard, create property → section → unit, register occupant, assign occupancy, record payment with auto-generated receipt `RCP-2026-00003`, receipt download as a **valid 1-page PDF** (`application/pdf`, 2499 bytes), Property Explorer hierarchy, logout, and 401 on token reuse. Executed with a temporary superuser that was deleted afterwards together with every record it created; only `karosadmin` remains. Backend suite re-run locally after the settings change: **237/237 passing**.
- **Noted, not changed:** the staging database still holds properties `KG1`/`SMK1`, 5 students and 2 payments left over from the 2026-07-29 smoke test — worth clearing before any demo.

### Documented — Elastic IP cost correction (2026-07-31)
- Earlier docs implied an Elastic IP adds cost while running. It does not: since AWS began charging for all public IPv4, an EIP on a **running** instance costs the same ~$0.005/hr as the auto-assigned address. The real difference is that an EIP on a **stopped** instance keeps billing — which is precisely this project's usage pattern, and the reason none was allocated. `dc-intern-backend` remains a live example of that trap.

### Verified — Post-deployment verification & hardening of live AWS staging (2026-07-29)
- **No business features added, no UI changes, no application code changed, no new AWS resources created.** Verification and documentation only.
- **Smoke test: 14/14 workflows pass** against the live public IP as real authenticated HTTP calls — frontend load, login, session persistence, dashboard aggregates, create property → section → unit, register occupant, assign occupancy, record payment, receipt JSON + valid PDF download, Property Explorer hierarchy with live occupancy counts, logout with immediate token invalidation, and 401 on six protected routes. The **over-capacity guard** was additionally confirmed enforced (third assignment to a capacity-2 unit rejected with *"Unit 'A-101' is at full capacity (2)."*).
- **Container health: clean.** All three services `Up (healthy)`, `restart: unless-stopped`, **0 restarts** since launch; 40 migrations applied and `migrate --check` clean; **0 backend tracebacks/ERRORs, 0 PostgreSQL FATALs, 0 nginx 5xx**; Django admin statics, SPA bundle, and nginx `/healthz` all 200.
- **Security review: all checks pass.** `DEBUG=False`; `SECRET_KEY` 50 chars and not the insecure placeholder, present only in the server `.env` (mode `600`, gitignored, zero uncommitted files); `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`CORS_ALLOWED_ORIGINS` correctly scoped to the EC2 IP with `CORS_ALLOW_ALL_ORIGINS=False`; host sockets limited to `:80` public, `:22` restricted to the admin `/32`, and `:8000` **bound to loopback only**, with PostgreSQL not published to the host at all. Externally confirmed **8000, 5432, 5173 and 443 all closed**. **No `demo` account exists** — `karosadmin` is the only user. `check --deploy` yields 4 warnings, all TLS-related and expected for HTTP-only staging; notably no `W018` (DEBUG) or `W009` (weak SECRET_KEY).
- **Documented:** `docs/DEVOPS.md` §11 Observability (logs, error-counting, container/resource/disk inspection, application state) and §12 Backup & recovery for container PostgreSQL — including the distinction that KarosL's own `BackupService` covers only the 8 business models and **not** users, tokens, `AuditLog`, or `Backup` rows, so `pg_dump` is the only complete backup. `docs/AWS_EC2_DEPLOYMENT.md` §13a now carries a full cost-safety resource inventory.
- **Two scripting footguns recorded in `docs/DEVOPS.md` §10**, both of which cost real debugging time in this project: `UID` is readonly in bash (a captured id was silently replaced by the shell's own uid, producing a false workflow failure), and `docker compose exec -T` consumes the remainder of a piped/heredoc script unless given `< /dev/null`.
- **Flagged (not KarosL, not modified):** `eu-north-1` also contains `dc-intern-postgres` (RDS, running) and `dc-intern-backend` (EC2 stopped **with an Elastic IP still attached**, which bills hourly while idle). Both affect the shared account bill and budget alarm.

### Deployed — Cloud Engineering Phase: AWS Staging is LIVE (2026-07-29)
- **KarosL now runs on AWS.** Region `eu-north-1`, single `t3.micro` (`i-0afd1871b46296500`, tag `karosl-staging-ec2`) on Amazon Linux 2023, running the unmodified `docker-compose.yml` stack. Created via AWS CLI: key pair `karosl-staging-key`, security group `karosl-staging-sg` (`sg-065fb018e22aa18a5`), 10 GB encrypted gp3 root volume with delete-on-termination, IMDSv2 required, auto-assigned public IP.
- **Security group:** inbound SSH 22 from the admin workstation `/32` only, HTTP 80 from `0.0.0.0/0` (temporary staging); outbound default. **No 5432, no 8000, no 5173.** Verified externally that 8000 and 5432 are unreachable from the internet.
- **Not created, per scope:** RDS, NAT Gateway, load balancer, ECS/Fargate, Elastic IP, extra EBS volumes.
- **Verified live through the public IP:** all three containers healthy; 40 migrations applied against PostgreSQL; `/api/health/` → `{"status":"ok","database":"ok"}` (proving internet → security group → nginx → Gunicorn → PostgreSQL end to end); SPA serves with deep-link refresh via `try_files`; `/api/auth/login/` returns a Django validation error rather than a gateway error; `/api/properties/`, `/api/occupants/`, `/api/dashboard/` all return 401 unauthenticated.
- **Outstanding:** superuser `karosadmin` exists but has no password set, so the authenticated workflow walkthrough is not yet complete.
- No application code or business features changed to make this work — only environment values differ from local.

### Added — `cloud-deployment` branch (2026-07-29)
- The entire Docker/DevOps effort was untracked, so a clone of this repository could not be built or run anywhere. Committed the containerization, the settings fixes it surfaced, the AWS staging assets, and the helper scripts to a new `cloud-deployment` branch and pushed it, making the repo deployable. No secrets committed — only `.env.example` placeholders.

### Fixed — Amazon Linux 2023 buildx incompatibility (2026-07-29)
- `docker compose build` failed on a fresh AL2023 instance with `compose build requires buildx 0.17.0 or later`: the distro's docker package ships **buildx 0.12.1**, while Compose v2.30+/v5 delegates image building to buildx and rejects anything older. Fixed by installing a current buildx CLI plugin. `scripts/server-setup.sh` now detects the old version and installs a current one automatically; documented in `docs/AWS_EC2_DEPLOYMENT.md` §4.3b and the `docs/DEVOPS.md` §10 troubleshooting table. Ubuntu's `docker-ce` packages are unaffected.

### Documented — Cloud Engineering Phase: AWS Staging Preparation (2026-07-29)
- **No AWS resources created, nothing deployed, no application code or business features changed.** Documentation and deployment assets only, preparing Phase 2 of `docs/AWS_DEPLOYMENT_PLAN.md` (single EC2 + Docker Compose, PostgreSQL still in a container, HTTP only).
- `docs/AWS_STAGING_CHECKLIST.md` — new. The Phase 2 tick-list: AWS account safety (budget, alerts, region, root MFA, free-tier check, explicit no-NAT/no-ALB/no-RDS decisions), EC2 plan (AMI, smallest instance, small EBS, key pair, IP strategy), security-group rules with a full rationale for why PostgreSQL must never be publicly exposed, server setup, a 15-point verification list, and a two-tier cleanup list (per-session vs. teardown).
- `docs/AWS_EC2_DEPLOYMENT.md` — new. Step-by-step runbook with placeholder values only: connect over SSH, install Docker + the Compose v2 plugin on Amazon Linux 2023 *or* Ubuntu LTS, add swap on small instances, clone the repo, generate secrets and create the server `.env` by hand, build, start, run migrations, create the superuser, view logs, restart/stop, redeploy, handle a changed public IP, plus a troubleshooting section covering `DisallowedHost`, CSRF/CORS, database connection and migration failures, frontend-cannot-reach-backend, and missing static files.
- `docs/AWS_DEPLOYMENT_PLAN.md` — added a **"Required pre-deployment step (cost safety)"** section stating that **no AWS deployment proceeds before budget alerts are configured**, with the eight mandatory items (budget, alerts + confirmed delivery, region, no NAT Gateway, smallest EC2, no load balancer for staging, no RDS unless explicitly chosen, know the cleanup steps first) and a full stop/delete cleanup procedure. Cross-references and the Phase 2 entry now point at the two new documents.
- `docs/DEPLOYMENT.md` — added a deployment-target table (local verified / AWS staging prepared / AWS production deferred), the same cost-safety pre-deployment gate, and an "AWS Staging" next-step section.
- `docs/DEVOPS.md` — new §10 "Logging & Troubleshooting" (diagnostic command reference plus a symptom→cause→fix table), and §9 now leads with AWS staging as the immediate next step.
- `.env.example` (root) — added a fully annotated AWS staging block (commented placeholders only, no values); `backend/.env.example` — documented the HTTPS/secure-cookie env vars and recorded that auth is DRF Token, not JWT, so there is no JWT secret to configure; `frontend/.env.example` — documented why `VITE_API_BASE_URL` must stay `/api` on EC2.
- `scripts/server-setup.sh`, `scripts/deploy-staging.sh`, `scripts/docker-logs.sh` — new optional helpers. No secrets, no destructive actions (never `down -v`, never `system prune`, never `git reset`, never create or read a `.env`), each documenting the manual commands it wraps. `deploy-staging.sh` warns on the common `.env` misconfigurations and refuses to start when `POSTGRES_PASSWORD` and `DB_PASSWORD` disagree.

### Documented — three container-configuration facts established by reading the actual definitions (2026-07-29)
Each of these silently breaks an EC2 staging deployment, and none is obvious from the local setup where the defaults happen to work:
- `FRONTEND_PORT` defaults to `8080` but must be `80` on EC2 — the staging security group only opens port 80.
- `ALLOWED_HOSTS` must add the EC2 public IP **and keep `localhost`**: `backend/Dockerfile`'s `HEALTHCHECK` curls `http://localhost:8000/api/health/` from inside the container, and Django returns 400 for an unlisted `Host`, so dropping `localhost` marks the container permanently unhealthy even though the application is serving correctly.
- `VITE_API_BASE_URL` must stay `/api` — Vite inlines it at image-build time, so an absolute URL would bake the EC2 IP into the JS bundle and convert same-origin API calls into cross-origin ones.

### Verified — Docker & Cloud Readiness re-verification (2026-07-23)
- Re-ran the full local production-like Docker stack end-to-end on Docker Engine 29.1.3 / Compose v5.1.4 to confirm it still builds and runs correctly ahead of AWS EC2 deployment. No Docker artifacts needed changes — the containerization delivered on 2026-07-04 (`backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `.dockerignore` files, `docker-entrypoint.sh`, `nginx.conf`, `/api/health/`, `.env.example` files) was audited and verified working as-is; zero gaps found.
- **Verified (11/11):** both images build; `docker compose up` brings `db`/`backend`/`frontend` all healthy; PostgreSQL container runs; Django connects to Postgres; 40 migrations applied (`migrate --check` clean); superuser creation works; frontend loads through Nginx (`:8080`, SPA `index.html`, deep-link `/dashboard` refresh returns 200 via `try_files`); frontend reaches the API through the Nginx `/api` reverse-proxy (`:8080/api/health/` → 200); token login works through the proxy; a core write workflow (create property via `/api/admin/properties/`) persisted to PostgreSQL — confirmed by querying `properties_property` directly in the `db` container — and the authenticated dashboard summary returns live data through the full browser→Nginx→Gunicorn→Postgres chain.
- **Tests:** backend suite **237/237 passing inside the container against PostgreSQL**, and **237/237 passing natively (venv, SQLite)**; frontend `npm run build` clean and `npm test` **45/45 passing** natively — confirming the non-Docker local workflow is untouched. All verification-only data (test property, test superuser) was removed afterward.

### Documented — Cloud Engineering Phase: AWS Deployment Planning (2026-07-23)
- `docs/AWS_DEPLOYMENT_PLAN.md` — new. Cost-conscious, phased AWS plan produced **before any cloud provisioning**: a 6-phase path (local Docker sim → single EC2 + Docker Compose → Amazon RDS PostgreSQL → S3 for backups/media → CloudWatch logging/monitoring → optional ALB + ECS/Fargate), mandatory cost guardrails (AWS Budget + email alerts as a hard pre-provisioning gate; avoid NAT Gateway/ALB/oversized instances; watch RDS/EBS/snapshots/CloudWatch Logs/Elastic IP), the first single-EC2 three-tier architecture, the PostgreSQL-in-Docker vs. RDS tradeoff, the AWS service list (EC2, RDS, S3, CloudWatch Logs, IAM, ECR, Route 53, ACM), a four-tier environment plan, a secret-management plan (nothing in Git; GitHub Secrets for CI; IAM instance roles; Secrets Manager/SSM later), an off-AWS migration/exit plan, and "Before AWS"/"Before production" checklists. **No AWS resources created, nothing deployed, no application code or business features changed** — planning only.
- `docs/PROJECT_STATE.md`, `docs/RELEASE_PLAN.md` — updated with the AWS planning snapshot and the recommended Phase 2 next sprint (gated on budget alerts + the "Before AWS" checklist, including removing/rotating the `demo` account).

### Added — Cloud Engineering Phase: Containerization (2026-07-04)
- `backend/Dockerfile`, `backend/docker-entrypoint.sh`, `backend/.dockerignore` — production container: `python:3.12-slim`, Gunicorn (never `runserver`), automatic `migrate` + `collectstatic` on start, WhiteNoise-served static assets, `HEALTHCHECK` against the new health endpoint.
- `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore` — multi-stage build: `node:20-alpine` builds the Vite bundle, `nginx:1.27-alpine` serves it and reverse-proxies `/api/`, `/admin/`, `/static/` to the backend so the SPA's existing relative `/api` base URL works unchanged.
- `docker-compose.yml` — production-like local stack: PostgreSQL (named volume, healthchecked), backend, frontend, all with `HEALTHCHECK`s.
- `docker-compose.dev.yml` — optional containerized hot-reload dev loop (Django `runserver` + Vite dev server, bind-mounted source); the native venv/`npm run dev` workflow is untouched and remains the primary path.
- `GET /api/health/` (`backend/apps/core/views.py`) — new unauthenticated liveness/readiness endpoint, checks DB connectivity. New test `HealthCheckTests` in `backend/apps/core/tests.py`.
- `.env.example` (root), `frontend/.env.example` (new); `backend/.env.example` updated with Docker-focused guidance. `VITE_API_BASE_URL` build-time env var added (`frontend/src/services/api.js`, `frontend/vite.config.js`'s dev-proxy target also made configurable via `VITE_PROXY_TARGET` for the dev compose file) — defaults preserve existing behavior exactly.
- `docs/DEVOPS.md`, `docs/DEPLOYMENT.md` — new: architecture, local usage, migrations/superuser, env vars, static/media-to-S3 plan, health checks, known limitations, next steps toward AWS.

### Fixed — Cloud Engineering Phase: Containerization (2026-07-04)
- `openpyxl` (used by `ExportService._write_xlsx` for XLSX export) was installed in the local dev venv but never listed in `backend/requirements.txt` — invisible until a container built strictly from that file surfaced it as a test failure. Added to `requirements.txt`.
- `SECURE_SSL_REDIRECT`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SECURE` (`backend/config/settings.py`) were hardcoded to `not DEBUG`, assuming `DEBUG=False` always means requests arrive over HTTPS. The Docker Compose environment runs `DEBUG=False` with no TLS termination anywhere in the chain, so this forced HTTPS redirects and broke all plain-HTTP access (including Django admin login). Made independently env-configurable, defaulting to the previous behavior (`not DEBUG`) for backward compatibility; `docker-compose.yml` explicitly sets them to `False` for this local, TLS-less environment.
- `DB_NAME` (`backend/config/settings.py`) was always resolved as a filesystem path regardless of `DB_ENGINE`, which silently broke `DB_NAME=karosl` when switching to PostgreSQL (a plain database name, not a path) via environment variables alone. Path resolution now only applies when `DB_ENGINE` contains `sqlite3`.

### Documented — Cloud Engineering Phase: Containerization (2026-07-04)
- Reviewed static/media/backup file handling ahead of introducing cloud storage: only the backup JSON export files are genuine local-disk state needing a future move to S3; Django's own static assets stay local (served by WhiteNoise), and CSV/XLSX exports and receipt PDFs are already generated in-memory with no disk footprint at all. No S3 integration implemented — plan only. Full detail in `docs/DEVOPS.md` §6.

### Fixed — RC Final Stabilization Closeout (2026-07-04)
- Archived properties/sections could still receive new sections/units via Administration with no validation guard. Now rejected server-side with a friendly error message ("Cannot add a section to '...' because it is archived. Reactivate the property first." / equivalent for units). Files: `backend/apps/administration/services.py`, `backend/apps/administration/views.py`.
- `UnitTab`'s status badge (Administration → Units) rendered the raw lowercase enum value instead of Title Case. Now shows "Active"/"Maintenance"/"Archived"; no stored or API value changed. File: `frontend/src/pages/Administration.jsx`.

### Verified — RC Final Stabilization Closeout (2026-07-04)
- Backup Restore executed as a live dry-run against an isolated, disposable database (never the real dev database), with a realistic multi-entity dataset covering every backed-up model, including hard-deleted and corrupted records simulating real data loss. All data matched the pre-backup snapshot exactly after restore — **confirmed production-safe**. See `docs/BUG_QUEUE.md` for full detail, including two by-design scope notes (audit log and backup records are outside restore's scope; restored `updated_at` timestamps reflect restore time, not the original).

### Documented — RC Final Stabilization Closeout (2026-07-04)
- Reports placeholder formally recorded as deferred from v1.0 (not release-blocking) in `docs/PROJECT_STATE.md` and `docs/RELEASE_PLAN.md`.

### Fixed — Release Candidate Verification Pass
- Occupant search returned zero results when searching a person's full name (e.g. "Jane Doe") instead of a single word — only single-word searches worked, because the search matched each field independently rather than as a combined name. Now matches correctly regardless of word order or count. See BUG-026.
- The same full-name search bug existed in Payments search. Fixed identically. See BUG-027.
- Dashboard's own "Record Payment" quick action still dead-ended through the unrelated Occupants list, unlike the Payments page's already-fixed direct entry point. Now opens the same occupant picker and payment dialog as the Payments page. See BUG-028.

### Added — RC Stabilization: UI Workflow Completeness & Consistency Pass (from UI/UX Audit)
- Payments page now has a direct "Record Payment" action: click it, pick an occupant from a searchable list, and the existing payment form opens pre-filled with that occupant — no more dead end through the Occupants list. See BUG-021.

### Fixed — RC Stabilization: UI Workflow Completeness & Consistency Pass (from UI/UX Audit)
- Dashboard's Recent Payments table always showed "—" for Property because the payments API didn't expose it at all. Now shows the real property name when available, or "Property not specified" for the rare payment recorded before a unit was assigned. See BUG-022.
- Consolidated every duplicated/inline `formatUGX` currency-formatting implementation across the app into the one shared utility, fixing an inconsistency where one screen (Explorer's unit panel) always showed 2 decimal places while everywhere else in the app didn't. Display-only change; no calculations were touched. See BUG-023.
- `EmptyState` icons now match the stroke-width used by the rest of the app's icon set. See BUG-024.
- The breadcrumb's fallback label for unmapped routes is now derived from the actual page path instead of a generic "Page" placeholder. See BUG-025.

### Removed — RC Stabilization: UI Workflow Completeness & Consistency Pass (from UI/UX Audit)
- Deleted three confirmed-unused UI files after a full-codebase reference search found zero imports, routes, or references to any of them: `pages/Settings.jsx`, `components/dashboard/ActionCard.jsx`, `components/dashboard/ActivityCard.jsx`.

### Fixed — RC Stabilization: Responsive UI Consistency Pass (from UI/UX Audit)
- Payments and Receipts tables had no responsive column hiding (7 columns each, forcing horizontal scroll on mobile). Applied the same tiered `hidden sm:/md:/lg:/xl:table-cell` pattern already used on the Occupants table, keeping the highest-priority columns and the action column visible at every width. See BUG-017.
- Administration's 6-tab navigation had no overflow handling on narrow screens. Added horizontal scroll (matching the app's existing table overflow convention) so all tabs remain reachable and the active tab stays clearly indicated after scrolling. See BUG-018.
- Administration's Units and Users tables (7 and 6 columns) had no responsive column hiding. Applied the same tiered pattern, keeping identity, status, and action columns visible at every width. See BUG-019.
- `AssignOccupancyDialog`'s confirmation summary and date/billing fields used a fixed 2-column grid that was cramped on the smallest phone widths. Now single-column below `sm` (640px) and 2-column above, matching the same breakpoint already used for equivalent layouts elsewhere in the app. See BUG-020.

### Fixed — RC Stabilization: UI Trust Fixes (from UI/UX Audit)
- Explorer unit panel's "Record Payment" action routed to the occupant profile instead of a payment form (it called the same handler as "View Occupant"). Now routes with occupant context preserved and auto-opens the existing payment recording dialog on the occupant profile. See BUG-014.
- Sidebar showed a hardcoded fake user ("Property Manager" / manager@karosl.com), disagreeing with the real logged-in user shown in the Topbar. Sidebar now reads the same authenticated user as the Topbar. See BUG-015.
- Properties page always displayed "Active" status regardless of the property's actual state. The API backing the page did not expose the `is_active` field; added it and the page now renders a real Active/Archived badge. See BUG-016.

### Added
- Project foundation: Django backend with DRF, CORS, env support, custom User model, 8 apps
- Project documentation: VISION, REQUIREMENTS, DATABASE, WORKFLOWS, ROADMAP, CHANGELOG, MEETING_NOTES

### Frontend Application Shell (Sprint 6)

- **Layout** — responsive shell with left sidebar (desktop) and slide-out drawer (mobile). Sticky top bar with breadcrumb and user avatar. Main content area with scrollable pages.
- **Navigation** — 6 sections: Overview, Properties, Occupants, Payments, Reports, Administration. Each with SVG icons and active state highlighting.
- **Pages** — placeholder pages for all 6 sections with stat cards, data tables, and description text. 404 NotFound page.
- **Components** — 7 reusable components: Sidebar (desktop + mobile drawer with overlay), Topbar (sticky, breadcrumb, user area), PageContainer (title + description wrapper), Card (content container), Button (primary/secondary/ghost variants), EmptyState (with action slot), Breadcrumb (Home > Page hierarchy).
- **Routing** — React Router v7 with index route, 5 named routes, and a catch-all 404 route.
- **Design** — Tailwind CSS custom theme with soft blue primary palette, Inter font via Google Fonts, generous spacing for readability, semantic HTML with ARIA labels, responsive grid layouts, mobile-first breakpoints at `sm` (640px), `md` (768px), `lg` (1024px).
- **Typography** — Inter font family, 2xl/3xl page headings, base text at 16px equivalent, relaxed line-height for readability.

### Overview Dashboard (Sprint 7)

- **Dashboard sections** — 6 purpose-built sections: Occupancy Summary, Outstanding Payments, Properties Overview, Recent Payments, Quick Actions, Recent Activity.
- **Dashboard widget components** — 5 reusable dashboard-specific components:
  - `StatisticCard` — large metric display with value, subtitle, secondary stat, and optional action button
  - `ActionCard` — bordered button list for quick actions
  - `ActivityCard` — timeline-style feed with typed indicators (check-in, checkout, payment)
  - `PaymentTable` — responsive table with occupant, amount, date, property columns
  - `PropertySummaryCard` — property card with occupancy bar, filled/total count, percentage
- **Mock data** — `src/data/mockDashboard.js` with realistic property, payment, and activity data matching the backend domain model (properties: Karos, Upper Karos, Lion Cottage; occupants, payments in UGX).
- **Layout** — responsive grid: single column on mobile, 2 columns on tablet, 3 columns on desktop (`md:grid-cols-2 xl:grid-cols-3`). Properties cards row, payments table spans 2 of 3 columns alongside activity timeline.
- **Utility** — `src/utils/format.js` with `formatUGX` for Ugandan Shilling display.

### Occupant Management Module (Sprint 8)

- **Model** — added `national_id` field to Student model (optional, unique, blank). New migration `0002_student_national_id`.
- **Backend API** — RESTful occupant management endpoints at `/api/occupants/`:
  - `GET /api/occupants/` — paginated list with `?search=` (name, phone, student ID, national ID) and `?status=active|archived` filters
  - `POST /api/occupants/` — create occupant with full validation
  - `GET /api/occupants/{id}/` — retrieve occupant details
  - `PUT /api/occupants/{id}/` — full update
  - `PATCH /api/occupants/{id}/` — partial update
  - `POST /api/occupants/{id}/archive/` — archive (soft delete, sets `is_active=False`)
- **Service layer** — `StudentService` class in `apps/occupants/services/`: `list_students`, `get_student`, `create_student`, `update_student`, `archive_student`. All business logic in services, views remain thin.
- **Serializer** — `StudentSerializer` with email uniqueness validation, phone format validation, computed `full_name` field.
- **Views** — `StudentViewSet` (ViewSet) with thin methods delegating to services. `archive` custom action. Permission: `IsAuthenticated | IsPropertyManager`.
- **Backend tests** — 23 tests covering: create (success, required fields, duplicate email, optional blanks, unauthenticated), list (empty, pagination), search (by first/last name, phone, student ID, national ID, no results), filter (active, archived), retrieve (success, nonexistent), update (full, partial), archive (success, already archived, record preservation).
- **Frontend list page** (`Occupants.jsx`) — search bar, filter tabs (All/Active/Archived), responsive data table with name, email, phone, student ID, status columns, pagination controls, loading skeleton, error state with retry, empty state with CTA.
- **Frontend detail page** (`OccupantDetail.jsx`) — profile card with all occupant fields in 2-column grid, occupancy history placeholder, actions panel (Edit, Archive, Back), archive confirmation dialog, loading/error states.
- **Frontend form page** (`OccupantForm.jsx`) — unified create/edit form with 6 fields (first_name, last_name, email, phone, student_id_number, national_id), client-side validation with inline error messages, loading state for edit fetch, success redirect to list, error display.
- **API client** — `src/services/api.js` with token auth, error extraction, and typed methods (get/post/put/patch/delete). `src/services/occupants.js` with occupant-specific CRUD functions.
- **Custom hooks** — `useOccupants` (list with search/filter) and `useOccupant` (single record), both with loading/error/refetch pattern.
- **ConfirmDialog component** — reusable modal dialog with title, message, confirm/cancel buttons. Used for archive confirmation.
- **Component tests** — 10 tests with Vitest + React Testing Library covering ConfirmDialog (render closed, render open, confirm, cancel), Button (render, click, disabled, variant), EmptyState (title/description, action slot).
- **Formatting** — added `formatPhone` and `fullName` utilities to `src/utils/format.js`.
- **Vite proxy** — development proxy configured: `/api` → `http://localhost:8000`.

### Database Models (Sprint 2)

- **Property** — name, code (unique), address, description, is_active, timestamps
- **Section** — FK to Property, name, description, is_active, timestamps; unique constraint on (property, name)
- **Unit** — FK to Section, name, capacity, semester_price, monthly_price, is_active, timestamps; unique constraint on (section, name); indexes on capacity and is_active
- **Student** — first_name, last_name, email (unique), phone, student_id_number (unique), is_active, timestamps; index on (last_name, first_name)
- **Occupancy** — FK to Student, FK to Unit, start_date, end_date (nullable), billing_mode, is_active, created_at; check constraint on end_date > start_date; partial unique indexes on active student and active unit; model-level validation prevents duplicate active occupancy
- **Payment** — FK to Student, amount, payment_date, payment_method, reference, notes, timestamps; indexes on (student, payment_date) and payment_date

All models registered in Django Admin with search, filters, date hierarchy, and related field displays.

### Admin Improvements (Sprint 3)

- **PropertyAdmin** — SectionInline (name, is_active), fieldsets with collapsed audit section, `section_count` display column
- **SectionAdmin** — UnitInline (name, capacity, prices, is_active), `autocomplete_fields` for property, `list_select_related`, `unit_count` column
- **UnitAdmin** — OccupancyInline (student, dates, billing_mode), `autocomplete_fields` for section, `list_select_related`, `occupancy_status` column showing current/capacity
- **StudentAdmin** — OccupancyInline and PaymentInline with ordering, fieldsets, `get_queryset` uses `Prefetch` with `select_related` to avoid N+1 on `current_unit`, fullname and student ID in search
- **OccupancyAdmin** — `autocomplete_fields` for student and unit, `list_select_related`, fieldsets, student ID number in search
- **PaymentAdmin** — `autocomplete_fields` for student, `list_select_related`, fieldsets, student ID number in search
- **UserAdmin** — custom `fieldsets` and `add_fieldsets`, `readonly_fields` for `last_login` and `date_joined`
- Cross-app inlines provide hierarchical navigation: Property → Section → Unit → Occupancy
- All list views include `list_select_related` or `prefetch_related` to minimize database queries

### Architecture Improvements (Sprint 4)

- **Core app** (`apps.core`) — centralized shared infrastructure: `mixins.py` (TimeStampedModel), `constants.py` (BillingMode, PaymentMethod choices), `validators.py` (validate_positive), `exceptions.py` (KarosLError hierarchy), `permissions.py`, `utils.py`
- **Services layer** — `services/` package with `__init__.py` added to all 7 business apps (properties, sections, units, occupants, occupancy, payments, dashboard). Ready for business logic implementation without further structural changes.
- **Old shared modules removed** — `apps/base.py` and `apps/choices.py` migrated into `apps.core`; all existing imports updated across 6 model files.
- **Settings refactored** — settings.py reorganized into clearly labeled sections (Paths, Security, Application, Database, Authentication, i18n, Static files, CORS, DRF, Logging). No settings values changed.
- **Logging configured** — development logging with verbose console formatter, separate loggers for `django`, `django.request`, and `karosl` namespaces. Ready for production log file handlers.
- **Exception hierarchy** — `KarosLError` base class with `ConflictError`, `NotFoundError`, `PermissionDeniedError` subclasses.
- **Development guide** — `docs/DEVELOPMENT_GUIDE.md` documents folder organization, naming conventions, service layer usage, model/view responsibilities, and testing expectations.

### Authentication & Authorization (Sprint 5)

- **Authentication** — Token Authentication via `rest_framework.authtoken`. Three endpoints:
  - `POST /api/auth/login/` — returns token + user profile
  - `POST /api/auth/logout/` — deletes current token
  - `GET /api/auth/me/` — returns authenticated user profile
- **LoginSerializer** — validates credentials, checks active status, returns existing token on repeat login
- **UserSerializer** — exposes id, username, email, name, staff/superuser flags, group memberships
- **Logout** — deletes the token from the database (immediate revocation)
- **Default groups** — `post_migrate` signal creates "Property Manager" and "Staff" groups automatically
- **Permission classes** (`apps/core/permissions.py`) — `IsSuperAdmin`, `IsPropertyManager`, `IsStaff`, `IsStaffOrSuperAdmin`, `HasGroupPermission` (configurable group-based check)
- **Tests** — 14 tests covering login success, invalid credentials, missing fields, inactive user, logout, unauthenticated access, authenticated me endpoint, token reuse, group membership, permission class importability
- **Security** — inactive users rejected at login, 401 returned for unauthenticated requests, tokens immediately revoked on logout
