# Release Plan

## Production-readiness audit and hardening — 2026-08-20

Full audit against the live pilot — architecture, security, database, backups, monitoring, CI/CD, cost,
failure modes, RPO/RTO. Full record: `docs/PRODUCTION_READINESS_REVIEW.md`.

**Verdict: READY WITH LIMITATIONS.** Two named blockers, not a hedge: (1) the `IsAuthenticated |
IsPropertyManager` permission gap lets any authenticated user write payments/occupants on live tenant
data — a product decision, deliberately not fixed unilaterally this pass; (2) the CloudWatch alarm SNS
email subscription is unconfirmed, so no alarm currently reaches anyone — a one-click fix only the account
owner can do. Everything else audited (RDS config, S3/backup posture, IAM scope, CI/CD, cost) is solid.

**The pipeline itself got its first real test and failed twice before passing.** The CI/CD work from
2026-08-19 had never actually run on GitHub Actions — only tested manually over SSH. Its first real run
failed immediately (SSH unreachable from GitHub's hosted-runner IPs; the security group correctly restricts
SSH to the operator's own `/32`, and GitHub's IP range — 5,645 CIDRs — can't fit in a security group at
all). Fixed with a self-hosted runner on the instance itself, with a documented security invariant given
the repo is public. A second real bug (password sanity check never updated for RDS) was caught immediately
after by the same run. Third run: fully green, tests → build → deploy → external smoke test, all real.

Also fixed: `backend/config/settings_production.py` (the module believed to enforce RDS TLS) was never
actually loaded by Django — its logic was dead code. Ported into the settings module actually in use;
re-verified 257/257 on both database backends.

### Recommendation for the next sprint

Confirm the SNS email subscription (5 minutes). Get a product decision on the permission gap. Run a real,
timed disaster-recovery drill — RPO is evidenced (≤24h worst case) but RTO is not yet measured. The
purchased-domain item remains the other standing item, gated on client sign-off, unrelated to this pass.

---

## RDS migration — 2026-08-19

PostgreSQL moved from the EC2 `db` container to Amazon RDS (`db.t4g.micro`, Single-AZ, private-only) —
`docs/AWS_DEPLOYMENT_PLAN.md`'s Phase 3, executed now that real tenant/payment data justifies it. Data
migrated and verified row-for-row, application cut over via `.env` only, S3 backup/restore tooling proven
against the new database, old container kept as a rollback safety net. Full record:
`docs/RDS_MIGRATION.md`.

**One real bug found during the cutover**: `docker-compose.yml` hardcodes `DB_HOST`/`DB_PORT` in the
backend's own `environment:` block, which beats `env_file` — setting `DB_HOST` in `.env` alone silently did
nothing, and the first cutover attempt crash-looped the backend for under a minute before being caught and
fixed with a new, conditionally-applied Compose overlay. No data was at risk — the container database was
never touched by the attempt.

### Recommendation for the next sprint

Remove the old container/volume once a clean validation window has passed (`docs/RDS_MIGRATION.md`).
Consider a CloudWatch alarm on RDS free storage/CPU/connections. The purchased-domain item remains the
other standing item, unrelated to this pass.

---

## Safe CI/CD pipeline — 2026-08-19

`git push` to `cloud-deployment` now tests, build-validates, and deploys automatically — a deliberate
reversal of `ci.yml`'s original "deployment stays manual" stance, made safe via a dedicated, forced-command
-restricted SSH key rather than the operator's own credentials. **No registry, no ECS/Fargate, no RDS — same
Docker Compose architecture, same EC2 instance, just automated.**

**The most important result of this pass wasn't the pipeline — it was catching three real bugs in the
*existing* manual deploy tooling before they could bite during an actual automated run.** Testing
`deploy-staging.sh` manually, exactly as documented, dropped staging's HTTPS for several minutes (the script
never applied the HTTPS/CloudWatch compose overlays — a latent gap, not something this pass introduced).
Fixed at the root in both `deploy-staging.sh` and the new `rollback-staging.sh`. A second bug (a health
check that reported success on an unfollowed redirect) was found immediately after while re-verifying the
first fix. A **third** bug turned up testing `rollback-staging.sh` itself: its dirty-working-tree guard
flagged harmless untracked files as a reason to refuse. While proving the first fix out, the same HTTPS-drop
incident recurred a second time — rolling forward landed on the still-unfixed, already-committed version of
`deploy-staging.sh`, because the fix existed only as an uncommitted local patch at that point. That
recurrence is the concrete reason this work is committed and pushed promptly rather than left as local
changes. Full account: `docs/CI_CD.md` §2 and §14, `docs/PROJECT_STATE.md`.

### Recommendation for the next sprint

The purchased domain remains the standing item. New from this pass: consider a lightweight image-registry
step (even just GHCR, no new AWS spend) once build time on the `t3.micro` becomes a real friction point —
documented now as the accepted tradeoff (`docs/CI_CD.md` §9), not an urgent gap.

---

## Basic CloudWatch observability — 2026-08-19

The one genuinely from-scratch build today — every other pass this session audited and extended work that
already existed; CloudWatch monitoring did not. 3 log groups, a newly-installed CloudWatch Agent (file
tailing — the dnf-installable version predates journald support, confirmed rather than assumed), Docker's
`awslogs` driver for nginx, 2 metric filters turning the backup script's `[EVENT]` markers from earlier
today into real metrics, 4 alarms, 1 SNS topic, 1 dashboard. **No RDS/ALB/NAT/Fargate, no new EC2 role
(extended the existing one), no long-lived credentials.**

Two real bugs caught and fixed during setup, not left for later: a `tee`-wrapper pipeline that would have
silently swallowed backup failure exit codes (fixed with `set -o pipefail`, verified `systemctl is-failed`
still works), and a disk-usage alarm that sat in a false `ALARM` because the CloudWatch Agent auto-tags its
disk/mem metrics with dimensions the first alarm definition didn't account for (fixed, verified against real
data). Every log-delivery and metric path was exercised for real — a genuine 401, a genuine successful
backup, and a genuine forced failure — not just configured and assumed working.

### Recommendation for the next sprint

The purchased domain is still the standing recommendation. New from this pass: **confirm the SNS email
subscription** (a one-click action, not engineering work) — until then, alarms fire but nothing arrives.
Also worth a look once there's been a full day of real traffic: whether the alarm thresholds (80% CPU,
85% disk) are actually the right levels for this workload, now that there's real data to check them against.

---

## S3 backup: explicit encryption check + monitoring-event structure — 2026-08-19

Small delta on top of the S3 backup work below, against a fuller brief covering the same ground. **No new
AWS resources, no bucket/IAM changes** — just two closed gaps: an explicit per-object encryption check
(the bucket's default-encryption *policy* isn't quite the same claim as "this object is encrypted," so
check the object), and a `[EVENT]`-prefixed log vocabulary on both scripts so a future CloudWatch setup has
something structured to filter on. Verified on both the success path and a deliberate failure. Full detail:
`docs/S3_BACKUP_ARCHITECTURE.md` §§11–12.

### Recommendation for the next sprint

Unchanged — the purchased domain remains the top item.

---

## S3 backup restructure + restore automation — 2026-08-19

Same-day follow-on to the HTTPS-via-IP work below, against a fuller backup-architecture brief. **No new AWS
resources** — reused the existing bucket and IAM role rather than creating parallel ones. Closed the two
real gaps: restore was manual-only (now automated, and provably safe — it cannot reach the live database),
and retention was flat 30-day-everything (now tiered: 30-day daily, 400-day monthly). Full detail and
verification evidence: `docs/S3_BACKUP_ARCHITECTURE.md`, `docs/PROJECT_STATE.md`.

### Recommendation for the next sprint

Unchanged from the entries below — the purchased domain remains the top item. Worth adding to the list now
that restore is automated: exercising `restore-from-s3.sh` periodically (not just once, today) is the
strongest ongoing proof backups stay good — consider folding a periodic run into whatever comes after the
domain work, rather than letting "we tested it once" quietly become the only evidence it ever works.

---

## HTTPS via bare EC2 IP — 2026-08-19

Enabled `https://<EC2_PUBLIC_IP>` with a real, browser-trusted certificate — a genuinely new capability
(Let's Encrypt IP-address certificates only went GA 2026-01-15), not a rebuild of the existing sslip.io
HTTPS path, which was kept running unchanged alongside it. **No domain purchased, no RDS/ALB/NAT/CloudFront,
no security-group change, no application code changed.**

**Result: two independent, verified HTTPS access paths, sharing port 443 via `default_server` + SNI, with
automated renewal proven by forcing it rather than waiting.**

- Certbot on the instance was too old (`dnf`-packaged 2.6.0) for IP-cert support; installed a modern one
  (5.7.0) into an isolated venv — cutting the AL2023 system Python 3.9 → 3.12 requirement was itself a real
  finding, not assumed from generic docs.
- A deploy-hook that reloads nginx after renewal **already existed** from 2026-07-31, found rather than
  built — closes what would otherwise have been a real gap for both certs, not just the new one.
- Forced a real renewal (`--force-renewal`) rather than waiting for the ~6-day natural expiry: succeeded,
  deploy-hook fired, app stayed up with zero manual intervention.
- Full browser smoke test against the bare-IP origin, fresh login (separate cookie origin), zero console
  errors, `AUDIT-TEST` records cleaned up afterward, dashboard back at exact baseline.
- `scripts/recover-staging.sh` extended so a *future* IP change (the underlying problem this whole area
  exists to manage) repairs both certificates, not just the hostname one — tested for real against the
  live, already-running instance (idempotent skip-path), including the orphan-sweep regex fix that keeps it
  from deleting the certs it just issued.
- Full detail: `docs/HTTPS_IP_CERTIFICATE.md`.

### Recommendation for the next sprint

Unchanged — the purchased domain remains the top item, now covering two HTTPS paths worth simplifying into
one once it lands.

---

## Live Pilot hardening audit — 2026-08-19

KarosL entered a controlled **Live Pilot**: real accommodation records now go into staging. The brief asked
to "harden the deployment," but most of that work was already done by the 2026-08-01 sprints below — this
was an audit to prove it, not a build. **No application code changed, no new AWS resources, no destructive
operations against live data.**

**Result: every mechanism the live-pilot bar requires was exercised and passed, and the instance now stays
up continuously instead of stopping between sessions.**

- Data survival, backup (dry-run + real + the `Persistent=true` catch-up firing correctly after 18 days
  off), container restart recovery, and a full browser smoke test (login through Property Explorer, using
  `AUDIT-TEST`-prefixed records archived afterward) were all verified directly against the running instance
  — see `docs/PROJECT_STATE.md` for the detail and evidence.
- **The decision that actually changes something:** staging stops being stopped between sessions. Live-pilot
  data entry needs the app reachable when the client or her staff use it, not only when an engineer starts
  it. This makes the sslip.io IP-churn problem dormant for now (no restarts, no new IP, no broken cert) but
  does not fix it — a purchased domain remains the real fix.
- Two non-blocking findings recorded for later cleanup: a leftover `Verify Tester` occupant from the
  2026-07-31 pass that was never removed, and the Units admin page's property filter not applying when
  "All Sections" is selected.

### Recommendation for the next sprint

**The purchased domain, now for a stronger reason than before.** It was previously "nice to have before
real users"; it is now "the instance runs continuously with real user data on it, and the only thing
standing between that and a broken cert is nobody restarting it." Second priority, unchanged from the last
two passes: **"move occupant to another unit"** — still the most likely real gap to surface now that actual
staff, not a demo, are using the app day to day.

---

## Demo-readiness pass: Reports built, staging seeded — 2026-08-01

The domain sprint was **deferred** (it needs a purchased domain, and the budget for that follows client
sign-off), and the client's review is of the **app**, not the infrastructure. So this pass targeted what
she will actually see. **No AWS resources created. No access-control changes.**

**Result: the app no longer advertises an unfinished feature, and staging demos with realistic data.**

- **Reports built for real** — three working reports (occupancy, financial, occupants), each exportable as
  CSV or XLSX. Closes the oldest entry in `PROJECT_STATE.md`'s Known Gaps, open since 2026-07-04.
- **Figures reuse existing calculations** rather than reimplementing them, so a report cannot disagree with
  the dashboard or an occupant's own balance. Confirmed live: the occupancy report and the dashboard both
  report 24 capacity / 14 occupied / 58%.
- **`manage.py seed_demo_data`** — the repo's first management command. 2 properties, 11 units, 16
  occupants, 13 payments, with **deliberately uneven occupancy** so the Explorer shows full (2/2), partial
  (3/4) and vacant (0/2) units rather than one flat colour.
- **The `KG1`/`SMK1` smoke-test residue is gone**, finally — flagged in three consecutive passes. Removed
  via `seed_demo_data --reset`, after a verified backup to S3.
- **Tests: backend 257/257, frontend 52/52**, green in CI on both SQLite and PostgreSQL.

### Staging is live and demo-ready

`https://16-171-227-174.sslip.io` — HTTP 301s to HTTPS, certificate valid to 2026-10-30 (`Verify return
code: 0`), 3/3 containers healthy, `check --deploy` **0 issues**, no pending migrations, report routes 401
unauthenticated, receipt PDFs generate. `karosadmin` remains the only account; the temporary account used
for verification was deleted and its token confirmed rejected afterwards.

### The IP moved for the third time

Starting the instance changed the address again (`16.171.114.188` → `16.171.227.174`), requiring an origin
repair, a new certificate, and deletion of the orphaned one. `scripts/fix-staging-origins.sh` made this
routine, but **routine is not the same as solved**. Three occurrences in three sessions is the argument for
the deferred domain sprint, which removes the cause rather than the symptom.

### Recommendation for the next sprint

**Whatever the client's feedback says.** That is the point of showing her the app, and pre-committing to a
technical sprint before hearing it would waste the review. Failing that: the **purchased domain** once
budget allows, then the "move occupant to another unit" workflow — a real gap a property manager hits in
normal daily use, and the most likely thing to surface in a hands-on review.

---

## Cloud Engineering Phase: Continuous Integration — 2026-08-01

Executes the sprint recommended below ("CI is the best next step"). **No application code changed, no
business features added, no UI changes, no AWS resources created, no secrets added to the repository.**

**Result: the test baselines are now machine-enforced instead of hand-recorded.**

- **`.github/workflows/ci.yml`** — three parallel jobs on pushes to `dev`/`cloud-deployment` and every PR:
  backend tests on a **SQLite + PostgreSQL matrix** (237/237 on both), frontend lint/test/build (45/45),
  and a build of both Docker images. **~2m20s** total wall time.
- **Verified by making it fail.** A throwaway PR broke one backend and one frontend assertion; both backend
  legs and the frontend job went red, the Docker job correctly stayed green, and the `pull_request` trigger
  was exercised in the process. Branch and PR deleted afterwards.
- **Verification only — no deploy.** The repo is public, so no AWS credentials were added. Pushing images
  to ECR remains open and is a separate, deliberate decision.

### Open follow-ups

1. **Branch protection is not enabled.** CI reports status but nothing yet *requires* it to pass before a
   merge. That is a GitHub repo setting rather than a file, so it needs to be turned on in the UI.
2. **Eight pre-existing lint warnings** remain (unused imports/variables in `Reports.jsx`, `NotFound.jsx`,
   `Administration.jsx`, `Toast.test.jsx`). `oxlint` exits 0 on them, so CI is green; clearing them would
   let lint be made strict later.

### Recommendation for the next sprint: **a purchased domain**

With backups and CI done, the highest-value remaining item is a **real domain**. It retires an entire
recurring failure mode at its root: staging has now broken twice on the same cause (the IP changes on
stop/start, so origins go stale, the certificate stops matching, and the old certificate is orphaned and
can never renew). A domain removes all three at once, and costs far less than RDS. **RDS still defers**
until KarosL holds data it cannot afford to lose.

---

## Cloud Engineering Phase: Automated Backups to S3 — 2026-08-01

Executes the sprint recommended below as item 2 ("S3 for backups"), taken ahead of RDS exactly as that
recommendation ordered it. **No application code changed, no business features added, no UI changes.**
New AWS resources: one S3 bucket, one IAM role + instance profile. **No RDS, no NAT Gateway, no load
balancer, no Elastic IP, and no new inbound port.**

**Result: the largest remaining durability gap is closed.** Backups are automated, verified, off-instance,
and proven restorable.

- **Nightly `pg_dump` → S3**, via `scripts/backup-to-s3.sh` and a systemd timer at 02:30 UTC. The script
  verifies each dump before uploading (non-zero size, `CREATE TABLE` present, `COPY` blocks present) —
  a 0-byte dump that looks successful in `ls` is the classic silent backup failure, and an exit code alone
  does not catch it. It then confirms the object's size in S3 rather than trusting the upload's exit code.
- **`Persistent=true` on the timer**, because this instance is stopped between sessions by design. Without
  it a missed nightly run would silently skip to the following night, and a stopped instance would never
  be backed up at all.
- **Restore drill passed 21/21** — pulled from S3, restored into a disposable database, row counts
  identical to live, live database never touched.
- **Least privilege proven by attempting the operations:** the instance role can write and read the backup
  prefix; `s3:DeleteObject` and out-of-prefix `ListBucket` both return `AccessDenied`. No AWS keys on the box.
- **`pg_dump` over `BackupService`** — the app's own backup covers 8 business models and excludes users,
  tokens, `AuditLog`, and `Backup` rows. Moving `BackupService`'s JSON exports to S3 remains open, but it
  is now the smaller half of Phase 4.

### Also done

Staging was **found broken on arrival** (stopped since 2026-07-31 → new IP → `400` on every API call while
the SPA still served `200`). Repaired with the new `scripts/fix-staging-origins.sh`; new certificate
issued; the full HTTPS verification list re-passed with `check --deploy` at **0 issues**.

### Open items from this sprint

1. **Stale certificates orphan on every IP change** — the previous hostname's certificate can never renew
   again, so `certbot-renew.timer` would accumulate one recurring failure per restart. The stale one was
   deleted this pass; **folding that cleanup into `fix-staging-origins.sh` is the follow-up**, so it
   travels with the repair instead of depending on someone remembering.
2. **Leftover smoke-test data still on staging.** Blocked by a tooling guard, not a product problem. A
   ready-to-run script is staged on the instance at `~/purge-smoketest-data.py` (business data only; the
   audit log is preserved deliberately). A verified backup was taken immediately before the attempt.

### Recommendation for the next sprint: **CI, then a real domain**

Backups and TLS are done; the remaining infrastructure items are no longer urgent. **CI is the best next
step** — GitHub Actions running `manage.py test` and `npm test`/`npm run build` costs nothing, creates no
AWS resources, and protects the 237/45 baselines that today are only ever verified by hand. After that, a
**purchased domain** is the highest-value AWS item: it retires the entire IP-change failure mode at its
root — stale origins, stale certificates, and the shared-`sslip.io` rate limit all disappear at once, and
it is far cheaper than RDS. **RDS still defers** until KarosL holds data it cannot afford to lose.

---

## Cloud Engineering Phase: Post-Deployment Verification & Hardening — 2026-07-29

Verification and documentation pass against the live AWS staging deployment. **No business features, no UI changes, no application code changed, no new AWS resources created.**

**Result: staging is stable and secure enough for its purpose. No blockers found in the application.**

- **Smoke test 14/14** through the live public IP, plus the over-capacity guard — full chain from browser through security group → nginx → Gunicorn → PostgreSQL, including receipt PDF generation and token invalidation on logout.
- **Container health clean** — 3/3 healthy, 0 restarts, 40 migrations applied, 0 tracebacks, 0 db FATALs, 0 nginx 5xx.
- **Security review all-pass** — `DEBUG=False`, strong `SECRET_KEY` confined to the server `.env`, correct host/CSRF/CORS scoping, only port 80 public, 8000 on loopback, 5432 unpublished, SSH restricted to the admin `/32`, and **no demo account**.
- **Backup/recovery procedure documented** in `docs/DEVOPS.md` §12, including the safe disposable-database restore pattern and the explicit warning that a `--clean` restore into the live database destroys everything created since the dump.

### Known limitations, accepted for staging

No HTTPS (login credentials cross the wire in plaintext); no automated backups; single point of failure; ephemeral public IP; `BackupService` does not cover users/tokens/audit log.

### Recommendation for the next sprint: **HTTPS / domain — before RDS, before S3**

The three candidate next steps are not equally urgent, and the ordering matters:

1. **HTTPS + domain — do this next.** It is the only limitation that is a genuine *security* defect rather than a durability one. Right now every login POST, including the admin password, crosses the internet in cleartext, and all four `check --deploy` warnings resolve the moment TLS exists. It also removes the ephemeral-IP friction (a DNS name survives what an IP does not), and it is the cheapest of the three — a Let's Encrypt certificate on the existing nginx container costs nothing, with no new AWS resources. Concretely: register/point a domain, add an ACME companion or certbot to the frontend container, open 443 in the security group, then flip `SECURE_SSL_REDIRECT`, `CSRF_COOKIE_SECURE`, and `SESSION_COOKIE_SECURE` back to `True` and update the origins to `https://`.
2. **S3 for backups — second.** Manual `pg_dump` on the same instance that holds the only copy of the data is the largest *durability* gap. This is cheap (pennies) and small in scope, and it is what makes the staging data survive losing the instance.
3. **RDS — defer.** It is the most expensive step and buys managed durability that staging does not yet need, given it holds only synthetic data. Take it when KarosL is about to hold data you cannot afford to lose — which is a production decision, not a staging one.

Do **not** treat "proceed to RDS" as the default next move because it is the next numbered phase in `docs/AWS_DEPLOYMENT_PLAN.md`. The phases are ordered by architectural progression, not by urgency; TLS is the item with a real security consequence today.

---

## Cloud Engineering Phase: AWS Staging Preparation — 2026-07-29

Documentation and deployment-assets pass. **No AWS resources created, nothing deployed, no application code, architecture, or business features changed.** KarosL has passed local Docker production simulation, so this pass produced everything needed to *execute* Phase 2 of `docs/AWS_DEPLOYMENT_PLAN.md`: a single EC2 instance running the same Compose stack (Nginx/React → Gunicorn/Django → PostgreSQL container) over HTTP.

**Delivered:**
- `docs/AWS_STAGING_CHECKLIST.md` — account safety, EC2 plan, security-group rules, server setup, verification, cleanup.
- `docs/AWS_EC2_DEPLOYMENT.md` — the full command runbook (placeholders only, no secrets) with a troubleshooting section.
- A mandatory **cost-safety pre-deployment step** in `docs/AWS_DEPLOYMENT_PLAN.md` and `docs/DEPLOYMENT.md`, plus documented stop/delete cleanup procedures.
- Staging env-var documentation across all three `.env.example` files; a troubleshooting reference in `docs/DEVOPS.md` §10.
- Three optional, non-destructive helper scripts under `scripts/`.

**The gate:** **no AWS deployment proceeds before an AWS Budget with email alerts is configured and a test alert is confirmed received.** Staging is deliberately scoped to *one* small EC2 instance — no RDS, no load balancer, no NAT Gateway, no HTTPS, no real tenant data.

**Three findings that will save a deployment:** `FRONTEND_PORT` must be `80` on EC2 (default 8080, and only 80 is open); `ALLOWED_HOSTS` must keep `localhost` alongside the EC2 IP or the backend container's healthcheck fails permanently while the app works; and `VITE_API_BASE_URL` must stay `/api` because Vite inlines it at build time. Also confirmed: auth is **DRF Token, not JWT**, so `SECRET_KEY` is the only cryptographic secret to manage.

**Verified in this pass:** `scripts/deploy-staging.sh` and `scripts/docker-logs.sh` were executed end-to-end against the live local stack (build → `up -d` → health wait → `/api/health/` returning `{"status":"ok","database":"ok"}` through the full nginx→gunicorn→postgres chain). `scripts/server-setup.sh` is syntax-checked only — it installs system packages and can only be genuinely exercised on a fresh EC2 instance.

**Recommendation:** execute the staging deployment following `docs/AWS_STAGING_CHECKLIST.md` in order, starting with the budget gate. Defer HTTPS/domain, RDS, S3, and CloudWatch to their own subsequent sprints.

### Recommended next sprint (execute AWS staging)

1. **Budget + email alerts first**, and confirm an alert email arrives — before any other console page.
2. Complete the "Before AWS" checklist (`docs/AWS_DEPLOYMENT_PLAN.md` Task 8), including **removing or rotating the `demo`/`demo12345` account** before anything is internet-reachable.
3. Launch one `t3.micro`, security group = SSH from your IP + HTTP 80 only, then work through `docs/AWS_EC2_DEPLOYMENT.md`.
4. Run the §4 verification list in `docs/AWS_STAGING_CHECKLIST.md`, including the instance-reboot data-persistence check.
5. Stop the instance between testing sessions; follow the cleanup list when finished.
6. **Next sprint after that:** domain + HTTPS (which is also when `SECURE_SSL_REDIRECT`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SECURE` get switched back on), then RDS (Phase 3).

---

## Cloud Engineering Phase: Docker & Cloud Readiness Re-verification — 2026-07-23

Re-verification pass, no code or Docker-artifact changes. Confirmed the local production-like Docker stack (Nginx → React build → Gunicorn/Django → PostgreSQL) still builds and runs end-to-end on Docker Engine 29.1.3 / Compose v5.1.4, as the direct dress rehearsal for the AWS EC2 deployment (Phase 2 of `docs/AWS_DEPLOYMENT_PLAN.md`).

**Verified (11/11):** images build; `db`/`backend`/`frontend` all reach healthy; PostgreSQL container runs; Django↔Postgres connection good; 40 migrations applied, `migrate --check` clean; superuser creation works; SPA served through Nginx with deep-link refresh working; API reachable through the Nginx `/api` reverse-proxy; token login works through the proxy; create-property write persisted to and confirmed in PostgreSQL, dashboard summary live through the full chain; the native (non-Docker) workflow re-confirmed working.

**Tests:** backend **237/237 in-container (PostgreSQL)** and **237/237 native (SQLite)**; frontend `npm run build` clean, `npm test` **45/45**.

**Result:** the Docker environment is confirmed deployment-ready. **No blockers.** Proceed to AWS Phase 2 (single EC2 + Docker Compose) per the recommended next sprint in the AWS Deployment Planning entry below — gated, as always, on the AWS Budget + email alerts being created first and the "Before AWS" checklist being green (including removing/rotating the `demo` account).

---

## Cloud Engineering Phase: AWS Deployment Planning — 2026-07-23

Documentation-only pass. **No AWS resources created, nothing deployed, no application code or business features changed.** Produced `docs/AWS_DEPLOYMENT_PLAN.md`, which defines a cost-conscious, phased AWS path before any provisioning happens.

**Delivered:** a full AWS deployment plan covering — a 6-phase path (local Docker sim → single EC2 + Compose → RDS PostgreSQL → S3 for backups → CloudWatch → optional ALB+ECS), mandatory cost guardrails (AWS Budget + email alerts as a hard pre-provisioning gate; NAT-Gateway/ALB/oversized-instance avoidance; the EBS/snapshot/CloudWatch-Logs/Elastic-IP cost traps), the first single-EC2 three-tier architecture, the Docker-Postgres-vs-RDS tradeoff, the AWS service list (EC2, RDS, S3, CloudWatch Logs, IAM, ECR, Route 53, ACM), a four-tier environment plan (native dev → Docker local → AWS staging → AWS production), a secret-management plan (nothing in Git; GitHub Secrets for CI; IAM instance roles; Secrets Manager/SSM later), an off-AWS migration/exit plan, and "Before AWS"/"Before production" checklists.

**Grounded in existing state:** the plan reuses the already-verified `docker-compose.yml` stack unchanged and cites `docs/DEVOPS.md` §6/§8/§9 for the concrete migration seams (backups→S3 is the only real local-disk state; RDS is an env-vars-only swap; migrate-on-start must become a one-shot job before scaling replicas).

**Recommendation:** the next sprint executes **Phase 2** — but only after the "Before AWS" checklist is green, and the AWS Budget + email alerts are the very first thing created in the account. See "Recommended next sprint" below.

### Recommended next sprint (AWS Phase 2 — single EC2)

1. **Gate first:** create the AWS Budget + email alerts and confirm an alert email arrives — *before touching any other console page.*
2. Complete the "Before AWS" checklist (`docs/AWS_DEPLOYMENT_PLAN.md` Task 8): re-verify Docker/tests/`.env.example`/no-secrets, re-run a backup restore, and **remove or rotate the `demo`/`demo12345` account** before anything is internet-reachable.
3. Provision one small (free-tier-eligible) EC2 instance, install Docker + Compose, attach an Elastic IP, open only 22/80/443, and run the existing stack with a production `.env` (Postgres still in-container for staging).
4. Smoke-test end to end via the EC2 IP/test domain; confirm backups survive a reboot.
5. Defer RDS (Phase 3), S3 (Phase 4), and CloudWatch (Phase 5) to subsequent sprints — each is an isolated, independently-shippable swap.

---

## Cloud Engineering Phase: Containerization — 2026-07-04

KarosL entered the Cloud Engineering Phase after RC stabilization closed out (see the Final Stabilization Closeout section below). This phase's goal: prove KarosL runs outside the developer's native machine setup, as the direct prerequisite to AWS deployment. Full architecture and usage detail in `docs/DEVOPS.md`; build/run/verify steps in `docs/DEPLOYMENT.md`.

**Delivered:** backend Dockerfile (Gunicorn, migrations + collectstatic on start, WhiteNoise static serving), frontend Dockerfile (multi-stage Vite build → Nginx, reverse-proxying `/api`/`/admin`/`/static` to the backend), `docker-compose.yml` (production-like: Postgres + backend + frontend, all healthchecked) and `docker-compose.dev.yml` (optional containerized hot-reload loop), a new unauthenticated `/api/health/` endpoint, and `.env.example` files for all three concerns (root/compose, backend, frontend).

**Two real gaps surfaced by containerizing** (both fixed): `openpyxl` was installed in the local venv but missing from `requirements.txt` (XLSX export would have failed on a clean install anywhere); and `SECURE_SSL_REDIRECT`/cookie-secure settings were hardcoded to `not DEBUG`, which broke all HTTP access the moment `DEBUG=False` was set without TLS present (as in this local compose environment) — made independently configurable via env var, defaulting to prior behavior.

**Verified:** both images build clean; full stack starts with all three containers healthy; migrations apply cleanly against PostgreSQL; full Django test suite (237/237) passes both natively and inside the backend container; a live login → create property → register occupant → dashboard summary chain was exercised through the frontend's nginx proxy with the write confirmed persisted in Postgres via `psql`; the native (non-Docker) venv/`npm run dev` workflow was re-verified working unchanged after all settings/dependency changes.

**Not done in this pass (by design — see `docs/DEVOPS.md` §8–9):** no S3 integration (backup JSON files remain local-disk, in a named Docker volume — plan documented, not implemented), no CI/CD pipeline, no TLS termination, no AWS resources provisioned. This phase is about proving containerization works locally, not deploying to the cloud yet.

**Recommendation:** proceed to the AWS deployment steps in `docs/DEVOPS.md` §9 (ECR, RDS, S3 for backups, ALB/TLS, CI pipeline, CloudWatch) — no blockers found in this pass.

---

## Release Candidate Verification Report — 2026-07-02

Full details of every bug found (including reasoning, severity, and failing layer) are in `docs/BUG_QUEUE.md` under "Release Candidate Verification Pass." This document is the summary release-readiness verdict.

### 1. Overall release readiness status: **Nearly Ready**

Every workflow in scope was exercised live end-to-end against a running instance. Three real bugs were found; all three were release-blocking-adjacent (two High, one High) and have been fixed, verified, and covered by the existing/updated test suite. Nothing Critical was found. The remaining open items are either pre-existing, already-documented, non-blocking gaps, or a single verification step (Backup Restore) that was deliberately not executed live for safety reasons rather than left unverified by code review.

### 2. Passed workflows

1. **Authentication** — login (valid + invalid), logout, session persistence after refresh, protected routes, unauthorized-access handling.
2. **Property Setup** — create, view, edit, archive/status display.
3. **Section Setup** — create, correct property association, rename. (Archive: available and functional, same pattern as Property/Unit archive.)
4. **Unit Setup** — create, capacity, pricing, Active/Maintenance/Archived status transitions, correct display in Property Explorer.
5. **Occupant Management** — register, edit, search (after fix), profile view, archive.
6. **Occupancy Management** — assign, over-capacity prevention, check out, occupancy history preserved. ("Move" is not implemented — see Known Gaps.)
7. **Payment Management** — full payment, partial payment, monthly-billing payment, balance calculation, payment history, validation against non-positive amounts.
8. **Receipts** — auto-generated, searchable, PDF retrieval works, persists/remains available.
9. **Dashboard** — occupancy/outstanding/recent-payments figures update correctly, quick actions route correctly (after fix).
10. **Property Explorer** — properties/sections/units display, correct occupancy indicators, unit detail panel, quick actions.
11. **Reports** — confirmed as the pre-existing, already-documented placeholder state ("Coming Soon"); not a regression, not fixed (would be a new feature).
12. **Administration** — Properties/Sections/Units/Users tabs fully exercised and working; Pricing tab's underlying engine confirmed correct via billing-mode tests; Administration is structurally separate from daily-ops navigation.
13. **Audit Trail** — every action logged with correct actor/action/entity/timestamp.
14. **Backup and Restore** — backup creation, history, and export all confirmed working live. Restore verified by code review only (see Deferred/Not Executed below).
15. **Responsive UI** — zero horizontal overflow across 6 key pages × 3 breakpoints (18/18 checks clean); tables, dialogs, forms, and Sidebar/Topbar all confirmed from a prior dedicated responsive pass plus spot-checks this pass.

### 3. Failed workflows (found broken, now fixed)

- **Occupant search** — full-name search returned zero results. Fixed (BUG-026).
- **Payment search** — same bug, same fix (BUG-027).
- **Dashboard Quick Actions → Record Payment** — dead-ended through an unrelated list instead of the direct payment flow. Fixed (BUG-028).

### 4. Critical bugs remaining

None found.

### 5. High bugs remaining

None — all three High-severity bugs found (BUG-026, BUG-027, BUG-028) were fixed this pass and re-verified live plus via the backend test suite.

### 6. Medium/Low bugs deferred

- **Medium:** Archived properties can still receive new sections/units via Administration with no validation guard. Not release-blocking; requires new service-layer validation, deferred as a follow-up.
- **Low:** `UnitTab` status badge renders lowercase raw enum text instead of Title Case, unlike every other status badge in the app. Cosmetic only.
- Pre-existing, already-documented (not new to this pass): Reports placeholder, archived-property exclusion from Explorer/Properties API, no "Move occupant" workflow.

### 7. Tests/build results

- **Backend:** `python manage.py test` — **234/234 passing** (full suite, run after all fixes).
- **Frontend build:** `npm run build` — clean.
- **Frontend lint:** `npm run lint` (oxlint) — only pre-existing, unrelated warnings (unused imports/vars in `Reports.jsx`, `NotFound.jsx`, `Administration.jsx`, and a test file); nothing introduced by this pass.
- **Frontend tests:** `npm test` (vitest) — **45/45 passing**.
- All four checks were run to completion; nothing was skipped or could not be run.

### 8. Recommended next step

**Continue stabilization — but only for one narrowly-scoped item — then proceed to Docker/DevOps preparation.**

Specifically:
1. Perform one dry-run **Backup Restore** in a disposable/isolated environment (throwaway DB copy or container) before final sign-off — this is the only workflow item not executed live in this pass, and it's the one genuinely irreversible action in the system.
2. Everything else is in a state consistent with beginning Docker/DevOps preparation in parallel — no other blocking functional gaps were found.

---

## Final Stabilization Closeout — 2026-07-04

Closes out the single narrowly-scoped item recommended above (Backup Restore dry-run) plus the two deferred Medium/Low bugs, and formally records the Reports product decision. Full detail in `docs/BUG_QUEUE.md`'s "RC Final Stabilization Closeout" section.

1. **Backup Restore dry-run: completed, restore confirmed production-safe.** Executed against an isolated, disposable SQLite database (never the real dev database) with a realistic multi-entity dataset covering every backed-up model (Property, Section, Unit, PricingRule, Student, Occupancy, Payment, Receipt), including hard-deleted and field-corrupted records to simulate a real disaster-recovery scenario. All data matched the pre-backup snapshot exactly after restore. Two design-scope findings (not bugs): `AuditLog` and `Backup` records are intentionally not part of the restore payload, and restored rows' `updated_at` reflects restore time rather than the original timestamp (cosmetic, pre-existing behavior of `BackupService.restore_backup`).
2. **Archived Property Validation: fixed.** Creating a section under an archived property, or a unit under an archived section, is now rejected server-side (`409 Conflict`) with a friendly message. Reused the existing `ConflictError`/`_handle_exceptions` pattern already used elsewhere in `apps/administration`; no frontend changes needed since the existing form dialog already surfaces backend error messages. Two new backend tests added.
3. **UnitTab status badge: fixed.** Now displays Title Case ("Active"/"Maintenance"/"Archived") via a display-only label map; no stored or API value changed.
4. **Reports: decision formally documented.** **Deferred from v1.0 — not release-blocking.** Recorded in `docs/PROJECT_STATE.md`'s Known Gaps.

### Updated test/build results (2026-07-04)

- **Backend:** `python manage.py test` — full suite re-run after all fixes above.
- **Frontend build:** `npm run build` — clean.
- **Frontend lint:** `npm run lint` — only the same pre-existing, unrelated warnings as the 2026-07-02 pass; nothing new introduced.
- **Frontend tests:** `npm test` (vitest) — **45/45 passing**.

### Recommendation

**All items from the previous "Recommended next step" are now closed. Proceed to Docker/DevOps preparation.** No functional gaps remain open that block containerization/deployment prep; the one operational note to carry into that work is `backend/backups/`'s storage path (fixed relative location, ~350+ untracked files not covered by `.gitignore`) — worth addressing as part of designing persistent-volume/backup-storage strategy in Docker, not before.

---

## Reference: environment used for this verification

- Backend: `python manage.py runserver 0.0.0.0:8000` (SQLite dev database).
- Frontend: `npm run dev` (Vite, port 5173).
- Test account: `demo` / `demo12345` (staff + superuser), left in place for continued manual testing.
- All disposable test data created for this pass (a `QARC`-prefixed property, sections, units, 3 occupants, their occupancies/payments/receipts, and a temporary staff user) was created, exercised, and then deleted afterward. Audit log entries generated during testing and the one backup record created during the Backup workflow check were **not** deleted — audit logs are meant to be an immutable historical record, and the backup is a valid, complete, harmless snapshot.
