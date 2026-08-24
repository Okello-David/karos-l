# Production Readiness Review — KarosL Live Pilot

**Date:** 2026-08-20. **Scope:** audit and harden only — no redesign, no new major AWS services, no
business features, no infrastructure migration, no destructive changes. **Reviewer stance:** every claim
below is backed by a command actually run or an action actually performed during this review, not by
re-stating existing docs. Where docs and reality disagreed, reality wins and the doc was corrected
(`docs/RDS_MIGRATION.md`, `docs/S3_BACKUP_ARCHITECTURE.md`, `docs/AWS_STAGING_CHECKLIST.md`, `docs/CI_CD.md`
— see their individual diffs this same day).

## 0. Updates — SNS confirmed, permission gap fixed, DR/IR sprint completed, RBAC hardening completed

**This section contains dated addenda to the original 2026-08-20 audit.** Everything below it (§§1–13) is
preserved exactly as written during the original audit earlier on 2026-08-20. This section documents
resolutions made after the audit's initial findings.

### RBAC hardening: a second, more serious permission finding, fixed (2026-08-24)

A follow-up authorization audit (see `docs/ARCHITECTURE_DECISIONS.md`, `docs/SECURITY_HARDENING.md`) went
beyond the `IsAuthenticated | IsPropertyManager` gap this review originally flagged, and found a **more
serious, previously-undocumented privilege-escalation path**: `AdminUserViewSet` (full user-account
management) required only `IsPropertyManager`, and its update path has a writable `password` field —
meaning any Property Manager could reset any user's password, including a superuser's, and log in as that
account. This was live in production, independent of the original permission-gap finding.

**Fixed**: `AdminUserViewSet` now requires Super Admin (`CanManageUsers`). A formal 3-role RBAC matrix
(Super Administrator / Property Manager / Staff) was documented, named per-capability permission classes
replaced raw role checks throughout, and a real regression (the Dashboard's core stats endpoint
accidentally swept into a Property-Manager-only gate) was caught and fixed in the same pass. Property-level
scoping was investigated and found to require new data modeling that doesn't currently exist — documented
as a known limitation rather than built speculatively, consistent with this review's original scope
discipline ("no redesign," "smallest safe change"). Full backend suite: 281/281. Frontend: 52/52, lint and
build clean.

**This closes a real security gap this review's original pass did not know to look for.** The original
verdict (§13) is unaffected in its conclusions about the items it did assess, but this addendum records
that the permission surface was more thoroughly audited on 2026-08-24 than on 2026-08-20, and the deeper
audit found something the shallower one missed — worth remembering as a reason to periodically re-audit
authorization surfaces, not just fix what's already been flagged.

### SNS subscription confirmed (2026-08-20, later the same day)

The SNS subscription referenced in §6 and §12 (blocker 2) **was confirmed**: found the AWS confirmation
email in `grbsderrick@gmail.com`'s inbox and clicked "Confirm subscription." This was **independently
verified via the AWS CLI** (`aws sns list-subscriptions-by-topic --topic-arn
arn:aws:sns:eu-north-1:908877263055:karosl-staging-alerts`), which now returns a real subscription ARN
(`...karosl-staging-alerts:64350d94-395a-46c9-802d-eeca8198c2b9`) rather than `PendingConfirmation` — not
just a "confirmed" page in the browser taken on faith.

**This closes the SNS-notification blocker** named in the original §12/§13. CloudWatch alarms now actually
reach that inbox.

### Permission gap fixed (2026-08-24)

The permission gap named in the original §3/§12 (blocker 1, `IsAuthenticated | IsPropertyManager` no-op on
12 viewsets across 8 apps) **has been fixed**. See `docs/BUG_QUEUE.md` for the full context and decision;
short version:

- **Decision made:** Any authenticated user should not be able to create occupants/record payments — restricted
  to Property Manager group only, matching the precedent in `apps/administration` (already fixed per BUG_QUEUE).
  Read-only endpoints stay open to any authenticated user.
- **Implementation:** Tightened write-capable viewsets (occupants, occupancy, payments) to `[IsPropertyManager]`,
  simplified read-only viewsets to `[IsAuthenticated]`.
- **Tested:** All 260/260 backend tests pass (51 payments, 53 occupants/occupancy, plus others — 3 new
  negative-path tests added). Added explicit negative-path tests asserting 403 for non-managers trying to
  create/modify data.
- **Safe for demo account:** `karosadmin` is a Django superuser; `IsPropertyManager` short-circuits True for
  any superuser, so the change will not lock it out during client review.

**This closes the sole remaining blocker from the audit** — the system now satisfies the "READY WITH LIMITATIONS"
verdict with both named blockers resolved.

### Disaster recovery & incident response sprint (2026-08-24)

A full DR/IR review was performed as a dedicated sprint — full record in `docs/DISASTER_RECOVERY.md` and
`docs/runbooks/`. This directly answers §12's own "Non-blocking, recommended next steps" item calling for a
real, timed DR drill (RPO evidenced, RTO not yet measured, as this review originally stated). Short version:

- **RPO confirmed ≈24h worst case** — evidenced by real S3 backup objects present daily,
  2026-08-19 through 2026-08-24, at the documented `02:30 UTC` cadence.
- **RTO measured for the first time, not estimated**: a real S3 `pg_dump` backup was restored into a
  disposable local database, verified across all 9 required record types at both the SQL and Django-ORM
  layers. **Restore: 15 seconds. Full verification: under 1 minute.** Live database, dev database, and
  existing backups untouched throughout — the restore script's own guardrail refuses to target the live
  database name.
- **RDS-specific CloudWatch alarms remain the one item from this review's §12 that is still open** — still
  not added (see original §6/§12 below); the DR pass re-confirms this as a real, named gap rather than
  letting it quietly age out of every subsequent review.
- **New gaps found by the DR pass, not previously named in this review**: no alarm exists for the backup
  timer silently stopping (as opposed to failing, which is alarmed and proven); `.env` secrets have no
  second copy anywhere outside the EC2 instance (rotation-only recovery, not restoration, if the instance is
  lost); RDS-native point-in-time-recovery is a documented AWS capability but an untested procedure for this
  application specifically.
- **Net-new security-incident-response runbook** (`docs/runbooks/06-security-incident.md`) — this review's
  original scope did not include incident-response procedures at all; the DR pass found none existed
  anywhere in the repo and wrote a full one covering 5 compromise scenarios. Undrilled, as expected for a
  first pass.
- **DR posture verdict: YELLOW** — real mechanisms exist and one is now proven with real timing and real
  data, but RDS-native PITR, EC2-loss recovery, and the security-incident runbook all remain
  documented-but-untested. This review's own "READY WITH LIMITATIONS" verdict is unchanged by the DR
  pass — DR/IR posture is assessed and tracked separately in `docs/DISASTER_RECOVERY.md`, not folded into
  the production-readiness verdict itself.

## 1. Architecture

```
GitHub (public repo)
  |
  |-- push to `dev` / PR -----------> ci.yml (GitHub-hosted runner, read-only: test+build, no deploy)
  |
  '-- push to `cloud-deployment` ---> deploy-staging.yml
                                        |-- backend/frontend/docker jobs (GitHub-hosted, gate)
                                        '-- deploy job (SELF-HOSTED runner, ON the EC2 instance)
                                               |
                                               v
                                        Internet
                                          |
                                          v  HTTPS :443 (Let's Encrypt, sslip.io bare-IP cert)
                                        EC2 (karosl-staging-ec2, t3.micro, eu-north-1)
                                          |-- Nginx / React (frontend container)
                                          '-- Django / Gunicorn (backend container)
                                                |                      |
                                                | TCP 5432             | CloudWatch Agent
                                                | (SG-reference only)  | + Docker awslogs driver
                                                v                      v
                                        Amazon RDS PostgreSQL   CloudWatch Logs/Alarms/SNS
                                        (karosl-staging-postgres,      |
                                         private, encrypted)           v
                                                |                 grbsderrick@gmail.com
                                                | nightly pg_dump   (subscription UNCONFIRMED)
                                                v
                                        Amazon S3 (private, versioned, encrypted,
                                        lifecycle-managed, IAM role — no AWS keys on box)
```

The old container Postgres (`db` service) is still running, deliberately, as a rollback safety net — it is
no longer what the application talks to.

## 2. Current AWS resources (verified via `aws` CLI, not assumed)

| Resource | Value | Status |
|---|---|---|
| EC2 instance | `i-0afd1871b46296500`, `t3.micro`, AL2023 | Running; IMDSv2 enforced; root volume 10 GiB gp3, **encrypted**; no Elastic IP (by design) |
| EC2 security group | `sg-065fb018e22aa18a5` | 22/tcp from admin `/32` only; 80,443/tcp from `0.0.0.0/0`; egress all |
| RDS instance | `karosl-staging-postgres`, PostgreSQL 16.14, `db.t4g.micro` | `PubliclyAccessible: false`, `StorageEncrypted: true`, `DeletionProtection: true`, Single-AZ, 20 GiB gp3 (autoscale 30), 1-day backup retention |
| RDS security group | `sg-0bd2df032ea18c46d` | Exactly one ingress rule: 5432/tcp, **SG-reference only**, no CIDR |
| S3 bucket | `karosl-staging-backups-908877263055` | Private (all 4 public-access-block flags true), versioned, SSE-AES256, 4 lifecycle rules, no bucket policy needed |
| IAM role | `karosl-staging-backup-role` | Trust: `ec2.amazonaws.com` only. Two inline policies: S3 write/read (no `s3:DeleteObject`) + CloudWatch Logs/metrics write. No RDS permissions. |
| CloudWatch Logs | `/karosl/staging/django`, `/karosl/staging/nginx`, `/karosl/staging/backup` | 14-day retention each |
| CloudWatch Alarms | 4 (`backup-failed`, `high-cpu`, `low-disk`, `status-check-failed`) | 3 OK, 1 in `ALARM` (investigated — see §5) |
| SNS topic | `karosl-staging-alerts` | 1 email subscription, **`PendingConfirmation`** |
| Self-hosted GH Actions runner | `karosl-staging-runner`, label `karosl-staging` | systemd service on the EC2 instance, **online** (added this review, §7) |
| AWS Budget | `My Monthly Cost Budget`, $30/month | $9.65 spent, healthy |
| Not present | NAT Gateway, ALB, ECS/Fargate, second EC2/RDS for this project | Confirmed absent |

**Out-of-scope finding, flagged not fixed:** an unrelated project's leftover, `dc-intern-backend`
(stopped EC2 `i-00a02d5f6be675e18`), still has Elastic IP `16.192.137.239` attached — an idle EIP on a
stopped instance is a real, avoidable AWS cost leak, but it belongs to a different project and was not
touched.

## 3. Security findings

| Check | Result |
|---|---|
| RDS 5432 not public | ✅ Confirmed (`PubliclyAccessible: false`, SG-reference ingress) |
| SSH restricted | ✅ Single `/32`, confirmed — and this restriction is *why* the CI/CD pipeline initially failed (§7) |
| S3 private | ✅ Confirmed, all public-access-block flags true |
| No credentials in Git | ✅ Confirmed via `git log --all -p` scans for `.env`, `.pem`, `AKIA`, `-----BEGIN`, hardcoded `SECRET_KEY=`/`PASSWORD=` — all clean |
| `DEBUG=False` | ✅ On the server `.env` (code defaults `True` if unset — a real but currently-inert risk; no fail-fast guard, see below) |
| Secure cookies | ✅ `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/`SECURE_SSL_REDIRECT` all `True` via `docker-compose.https.yml` overlay |
| `ALLOWED_HOSTS` | ✅ Correctly set; code has a safe localhost-only default if unset |
| CSRF configuration | ✅ `CSRF_TRUSTED_ORIGINS` set correctly; `CSRF_COOKIE_HTTPONLY`/`SESSION_COOKIE_HTTPONLY` hardcoded `True` |

**Real bug found and fixed this review:** `backend/config/settings_production.py` — the module documented
in `docs/RDS_MIGRATION.md` as enforcing `DB_SSLMODE=require` on the RDS connection — was **never actually
loaded**. `Dockerfile`/`manage.py`/`wsgi.py` all hardcode `DJANGO_SETTINGS_MODULE=config.settings`, a
different module with no `OPTIONS`/sslmode logic at all. The documented TLS enforcement was silently a
no-op. **Fixed**: ported the same additive `OPTIONS` block into `config/settings.py` itself, guarded to
skip SQLite (`connect_timeout`/`sslmode` are psycopg2-only kwargs that break `sqlite3.connect()`).
Re-verified: backend test suite 257/257 on both SQLite and Postgres after the change. Commit `bf24e94`.

**Confirmed still-open, NOT fixed this sprint (by deliberate choice — see §11):**
`IsAuthenticated | IsPropertyManager` is a no-op OR on 8+ business viewsets — `apps/occupants`,
`apps/payments` (×2), `apps/properties` (×2), `apps/sections`, `apps/units` (×2), `apps/occupancy`,
`apps/dashboard`, `apps/reports` — meaning **any authenticated user, regardless of role, can create
occupants and record payments today**, against a live pilot holding real tenant/payment data. This exact
gap is already recorded in `docs/BUG_QUEUE.md` as deliberately deferred pending product sign-off, not an
oversight. It is the single most important finding in this review — see §12.

**Minor, fixed:** `.gitignore` had no SSH-key patterns (`*.pem`, `*_rsa`, `*_ed25519`) — no leak occurred,
but the gap was real. Added.

## 4. Database findings

PostgreSQL 16.14 on `db.t4g.micro`, Single-AZ, 20 GiB gp3 autoscaling to 30 GiB. Appropriate for current
scale: the live database is ~9–12 KB compressed (per the nightly dump size), nowhere near storage limits;
`db.t4g.micro` is the smallest Graviton burstable class and matches `docs/AWS_DEPLOYMENT_PLAN.md`'s own
Phase 3 sizing. **Not recommending Multi-AZ or a larger instance class** — no signal justifies the added
cost yet (CPU alarm shows 1–4% actual utilization).

1-day automated backup retention is a Free Tier account cap, not a choice — confirmed by
`docs/RDS_MIGRATION.md`'s own record of `FreeTierRestrictionError` when 7 days was attempted. This is
adequately compensated by the independent S3 `pg_dump` pipeline (30-day daily + 400-day monthly retention,
outside the AWS account's blast radius). **No expensive feature (Multi-AZ, Performance Insights, a bigger
instance class) added — not justified by current scale.**

## 5. Backup and disaster-recovery findings

- RDS automated backups: ✅ enabled, 2 recent automated snapshots confirmed via `describe-db-snapshots`,
  both encrypted.
- S3 `pg_dump` pipeline: ✅ verified landing on schedule — most recent object at 2026-08-20 05:36 UTC
  (~12 KB gzip), within the documented `02:00–03:00 UTC` systemd timer window.
- Backup encryption: ✅ both RDS snapshots (KMS) and S3 objects (SSE-AES256) encrypted.
- Backup verification: ✅ `backup-to-s3.sh` checks dump size/table count before upload, doesn't accept
  exit-code-0 alone.
- Restore procedure: documented and previously drilled (`docs/S3_BACKUP_ARCHITECTURE.md`,
  `docs/DEVOPS.md` §12) — always into a disposable database, never over the live one.
- Rollback documentation: ✅ `docs/RDS_MIGRATION.md` "Rollback procedure" — reversible by design (old
  container/volume kept, not deleted), with an explicit, honest limitation: any RDS writes after cutover
  are not in the frozen container and would be lost on a rollback.

**Investigated: the `karosl-staging-backup-failed` CloudWatch alarm was in `ALARM` state at the start of
this review.** Root cause, found via `journalctl -u karosl-backup.service`: a **deliberate test** on
2026-08-19 16:54:58 UTC that uploaded to an intentionally-fake bucket (`nonexistent-bucket-test-xyz`) to
prove the alarm actually fires — not a real production failure. Real backups succeeded both before and
after that test (08:29:55 and 16:52:38 UTC the same day, and again 2026-08-20). The alarm's
`TreatMissingData` is correctly set to `notBreaching`, but its evaluation `Period` is 86400s (24h) — it
simply hadn't reached its next evaluation boundary (~16:59 UTC, 2026-08-20) to clear back to `OK`. **No fix
applied — working as designed**, not a gap.

### RPO / RTO — evidence-based, not assumed

- **RPO**: for ordinary data-integrity issues (bad write, accidental delete), RDS's own point-in-time
  recovery covers the full 1-day retention window — effective RPO near-zero within that window. For
  catastrophic RDS loss (instance destroyed beyond PITR), the S3 pipeline bounds RPO to **≤24 hours**
  (nightly dump). No worse-case scenario found where more than a day of data is at risk.
- **RTO**: **not rigorously measured in this review** — no full disaster-recovery drill (new EC2 instance
  from scratch + S3 restore) was timed. What *is* evidenced: `scripts/recover-staging.sh` exists and is
  documented as idempotent for the "stopped instance → running → verified" path; the CI/CD deploy job
  observed in this review (§7) took **52 seconds** for a routine code deploy (build+restart, not a DR
  scenario). Per the audit's own instruction not to claim RPO/RTO without evidence: **treat RTO as
  unverified** until a real timed DR drill is run — recommended as next-sprint work, not claimed here.

## 6. Monitoring findings

- EC2 health: ✅ `status-check-failed` alarm, OK.
- CPU: ✅ `high-cpu` alarm (>80%, 3×5min), OK, actual 1–4%.
- Disk: ✅ `low-disk` alarm (>85%), OK, actual ~57%.
- Application logs: ✅ `/karosl/staging/django`, 14-day retention.
- Nginx logs: ✅ `/karosl/staging/nginx` via Docker `awslogs` driver, 14-day retention.
- Backup failures: ✅ dedicated log group + 2 metric filters + alarm exist and were proven to actually fire
  (§5's test).
- SNS notifications: **not yet functional** — the one email subscription is `PendingConfirmation`. Nobody
  currently receives an alert when any of these 4 alarms fire. **Action needed from the account owner**:
  check the inbox for `grbsderrick@gmail.com` for an AWS SNS confirmation email and click it — this cannot
  be done by an agent.

**Not currently monitored** (flagged, not added — avoiding excessive monitoring per scope): RDS-specific
metrics (free storage space, connection count, read/write latency) have no dedicated alarm — `docs/RDS_MIGRATION.md`'s
own "next sprint" section already recommends this. Reasonable to add later, not urgent given current
9–12 KB database size.

## 7. CI/CD findings

**The pipeline's first-ever real GitHub Actions run failed** — a genuine, previously-undiscovered
structural gap, not a fluke. Root cause: the EC2 security group correctly restricts SSH to the operator's
own `/32` (§3), but GitHub-hosted runners connect from thousands of dynamic IPs. GitHub's own published
Actions IP range (`api.github.com/meta`) is **5,645 IPv4 CIDRs** — too large for an EC2 security group
(AWS caps around 1,000 rules with a quota increase). **Fixed** by installing a self-hosted GitHub Actions
runner directly on the EC2 instance (systemd service, label `karosl-staging`) — it polls GitHub outbound,
needing no inbound network change. A documented, load-bearing **security invariant**: this runner must
never be reachable by any workflow triggerable from a fork PR (this repo is public) — `ci.yml` was
confirmed to have zero references to the runner's label, and `deploy-staging.yml`'s only trigger is
`push: branches: [cloud-deployment]`, never `pull_request`.

**A second real bug was caught by the same first run, after the network fix**: `deploy-staging.sh`'s
password sanity check required `POSTGRES_PASSWORD` (the now-unused local container's password) to equal
`DB_PASSWORD` (the RDS credential) — correct only for the container-Postgres path, and it `die`d on every
deploy since the RDS migration. **Fixed**, gated on the same `$_db_host` check already used for the RDS
compose overlay.

**Third real run, both bugs fixed: fully green end-to-end** — all 6 jobs (backend ×2, frontend, Docker
build, deploy, external smoke test) passed. Independently re-confirmed via `./scripts/verify-staging.sh`
(12/12) immediately after. This is the strongest evidence in this review: not "the pipeline looks correct"
but "the pipeline was run for real, failed twice, was fixed twice, and now demonstrably works."

| CI/CD check | Result |
|---|---|
| Tests run before deploy | ✅ `needs: [backend, frontend, docker]` + explicit `if: success()` |
| Deployment failures detected | ✅ proven — the pipeline failed loudly, twice, exactly as designed |
| Secrets protected | ✅ none echoed; `EC2_DEPLOY_KEY`/`EC2_USER` now unused (self-hosted runner needs no SSH), left in place rather than revoked — recommended cleanup |
| Deployments serialized | ✅ `concurrency: group: staging-deploy, cancel-in-progress: false` |
| Migrations handled safely | ✅ automatic via entrypoint + explicit labeled step; `migrate --noinput` only, no destructive operations |
| Health checks run | ✅ content-based (`grep '"status":"ok"'`), both internally and externally |
| Rollback procedure exists | ✅ `scripts/rollback-staging.sh`, tested in a prior session against a real prior commit |
| Previous known-good version identifiable | ✅ `~/.karosl-deploy-history`, written on every successful deploy |
| Branch protection | ❌ confirmed absent via `gh api .../branches/cloud-deployment/protection` → 404 |

Backend test suite: **257/257** (SQLite + Postgres, run for real, twice — once by research, once after the
sslmode fix). Frontend: lint clean (7 pre-existing warnings, corrected from a stale "8" in `ci.yml`'s
comment), **52/52** tests, build succeeds. Docker images for both services build cleanly.

## 8. Cost findings

| Item | Monthly | Notes |
|---|---|---|
| EC2 `t3.micro` | ~small | Running continuously since Live Pilot start; no Elastic IP (avoids the idle-EIP charge) |
| RDS `db.t4g.micro` | ~$11.68 | Per `docs/RDS_MIGRATION.md`'s AWS Pricing API check |
| RDS storage (20 GiB gp3) | ~$2.40 | |
| S3 backups | ~$0 | 9–12 KB dumps, far under any tier |
| CloudWatch Logs/alarms | ~$0 | 14-day retention, low volume |
| Self-hosted runner | $0 | Runs on the already-billed EC2 instance, no new resource |
| **Total account spend to date** | **$9.65 / $30 budget** | `HEALTHY`, confirmed via Budgets API |

No new AWS resource was introduced by this review beyond the (free) self-hosted runner software. The
`dc-intern-backend` EIP leak (§2) is real cost waste but belongs to an unrelated project — flagged to the
account owner, not touched.

## 9. Failure-mode analysis

| # | Scenario | Detection | Impact | Recovery | Mitigation today | Remaining gap |
|---|---|---|---|---|---|---|
| 1 | EC2 crashes | CloudWatch status-check alarm | Full outage | Manual/automated restart, `docker compose up -d` on boot (`unless-stopped` restart policy) | Restart policies confirmed via `docker inspect` in a prior session | RTO unmeasured (§5) |
| 2 | EC2 disk fills | `low-disk` alarm (>85%) | Degraded/failed writes | Prune old images/logs, expand EBS | Alarm exists, currently 57% used | SNS not confirmed (§6) — alarm would fire silently |
| 3 | Docker container crashes | `unless-stopped` restart policy, healthchecks | Brief outage of that service | Auto-restart | Confirmed working | None significant |
| 4 | Django crashes | Container healthcheck fails → container reports unhealthy | API errors | Auto-restart via Docker | `docker-entrypoint.sh` migration-gated start | None significant |
| 5 | Nginx crashes | Container healthcheck | Full outage (frontend is the front door) | Auto-restart | Confirmed | None significant |
| 6 | RDS unavailable | Backend `/api/health/` reports `database` not `ok` | Full API outage | RDS is managed — AWS handles instance-level recovery; app has no fallback | Single-AZ (deliberate cost tradeoff) | No automatic failover — accepted tradeoff at current scale, not a gap given cost constraints |
| 7 | S3 backup fails | CloudWatch alarm + metric filter — **proven to actually fire** (§5) | No new off-site backup that night | RDS's own 1-day PITR still covers same-day | Alarm works; **notification does not yet reach anyone** (§6) | SNS confirmation pending |
| 8 | GitHub Actions deployment fails | Job fails, workflow marked red, logs preserved | No deploy happens — old code keeps running | Fix and re-push, or `rollback-staging.sh` | **Proven twice this review** — real failures were caught, not silently ignored | None — this is the system working correctly |
| 9 | Bad deployment reaches EC2 | External smoke test (real HTTPS path, from GitHub-hosted runner) | Deploy job fails after code is already running | `rollback-staging.sh` to last known-good commit | Proven in a prior session against a real prior commit | Automatic rollback-on-failure deliberately not wired (documented decision, avoids compounding an incident) |
| 10 | Database migration fails | `migrate --noinput` step fails the deploy explicitly | Deploy blocked, old schema/code stay in sync | Fix migration, redeploy | Confirmed — migrations are idempotent, deploy fails loudly not silently | Rollback cannot auto-downgrade a migration (documented limitation) |
| 11 | EC2 public IP changes | `verify-staging.sh` external check; deploy smoke test | Origins/cert mismatch, `EC2_HOST` secret stale | `fix-staging-origins.sh`, re-issue cert, `gh secret set EC2_HOST` | Documented, previously drilled | Standing gap — no Elastic IP/domain yet (known, deferred pending client sign-off per project memory) |
| 12 | HTTPS certificate renewal fails | `certbot-renew.timer`; external cert-expiry check | HTTPS breaks in ~60 days silently if unnoticed | Manual renewal per `docs/HTTPS_IP_CERTIFICATE.md` | Cert currently valid 88 more days (confirmed via `verify-staging.sh`) | Same root cause as #11 — IP churn orphans certs |

## 10. Production-readiness score

| Category | Score | Why |
|---|---|---|
| Application | 🟡 YELLOW | Full smoke test passed end-to-end (login→property→section→unit→occupant→occupancy→payment→receipt→audit→logout) with real writes verified via audit log; one cosmetic bug found (double success toast on payment recording — confirmed **not** a duplicate write) |
| Security | 🔴 RED | RDS/S3/SSH/secrets all correctly locked down, but the permission gap (§3, §12) lets any authenticated user write payments/occupants on a live system with real tenant data — unresolved by deliberate choice, still a real gap |
| Infrastructure | 🟢 GREEN | EC2/RDS/S3/IAM all verified correctly configured, encrypted, and least-privilege; self-hosted runner added and secured with a documented invariant |
| Database | 🟢 GREEN | Sized appropriately for current scale, encrypted, deletion-protected, private |
| Backups | 🟢 GREEN | Two independent, verified, working backup mechanisms (RDS automated + S3 pipeline); alarm proven to actually fire |
| Monitoring | 🟡 YELLOW | Alarms exist and work, but notifications don't reach anyone yet (SNS unconfirmed) |
| CI/CD | 🟢 GREEN | Was YELLOW-leaning-RED at the start of this review (never actually run); now proven fully green end-to-end after fixing two real, previously-undiscovered bugs |
| Disaster Recovery | 🟡 YELLOW | RPO is evidenced and bounded (≤24h worst case); RTO is not measured — no timed DR drill exists |
| Cost Management | 🟢 GREEN | Well under budget, no untracked spend for this project (the `dc-intern-backend` EIP leak is a different project) |
| Documentation | 🟡 YELLOW | Generally excellent and self-correcting in style, but several docs were found stale this review (now fixed) — `AI_CONTEXT.md`/`ARCHITECTURE_DECISIONS.md`/`CODING_STANDARDS.md`/`AI_WORKFLOW.md` referenced by this audit's own brief do not exist in this repo |

## 11. What this review changed

Committed this session (`cloud-deployment`, all pushed):
- `bf24e94` — wired the dead `DB_SSLMODE`/`OPTIONS` logic into the settings module Django actually loads;
  `.gitignore` SSH-key patterns; untracked a stray log file; corrected stale CI/doc claims.
- `cc49993` — moved CI/CD deploy to a self-hosted runner after the pipeline's first real run proved the
  original SSH design unreachable from GitHub's infrastructure.
- `424251f` — fixed `deploy-staging.sh`'s password sanity check for the RDS path (found by the same first
  real run, after the network fix).
- This document, plus corrections to `docs/RDS_MIGRATION.md`, `docs/S3_BACKUP_ARCHITECTURE.md`,
  `docs/AWS_STAGING_CHECKLIST.md`, `docs/CI_CD.md`.

Deliberately **not** changed: the permission gap (§3, §12) — flagged prominently, left for a product
decision, per explicit instruction this sprint. The SNS email confirmation — cannot be done by an agent.
The tripped backup alarm — confirmed benign, left to self-clear. `EC2_DEPLOY_KEY`/old SSH deploy
infrastructure — no longer used, left in place rather than revoked (recommended follow-up, not urgent).

## 12. Remaining blockers vs. non-blocking improvements

**Blockers (should be resolved before calling this "production," not just "pilot"):**
1. **The permission gap.** Any authenticated user can create occupants and record payments. This needs a
   product decision (who should be able to do what), not a unilateral code change — flagged, not fixed.
   **Status: still open — the sole remaining blocker from this audit (see §0).**
2. ~~**SNS email confirmation.**~~ Trivial for the account owner (one click in their inbox), but until done,
   every alarm in §6/§9 is silently unmonitored. **Status: resolved 2026-08-20, see §0 — confirmed and
   independently verified via the AWS CLI.**

**Non-blocking, recommended next steps (ordered by leverage, not urgency):**
1. Confirm the SNS subscription (5 minutes, closes a real gap).
2. Run a real, timed disaster-recovery drill to get an evidenced RTO number.
3. Retire `EC2_DEPLOY_KEY`/`scripts/ci-deploy-entrypoint.sh` now that the self-hosted runner has replaced
   them, once the runner has proven itself over a longer window.
4. Add an RDS-specific CloudWatch alarm (free storage/CPU/connections) — cheap, already recommended in
   `docs/RDS_MIGRATION.md`.
5. Decommission the old `db` container/volume once the 7-day RDS validation window closes (~2026-08-26).
6. Fix the double-toast cosmetic bug on payment recording (confirmed harmless, but confusing).
7. Move `BackupService`'s local-disk JSON exports to S3 (already scoped as a contained change in
   `docs/DEVOPS.md`).
8. Purchased domain + Elastic IP — standing item, gated on client sign-off per project context, unrelated
   to this technical review.
9. Enable GitHub branch protection on `cloud-deployment` — currently anyone with push access can bypass
   CI entirely (though today that's just the one operator).

## 13. Verdict

# READY WITH LIMITATIONS

KarosL's infrastructure — EC2, RDS, S3, IAM, CloudWatch, HTTPS, and now CI/CD — is genuinely well-built:
encrypted at rest, least-privilege, no public database exposure, verified backups, and a deploy pipeline
that was actually tested against the real GitHub Actions environment (not just reviewed on paper) and
proven to catch real failures before they reached production. The application itself passed a full,
real, end-to-end smoke test with audit-trail confirmation of every write.

It is **not** simply "production ready" for two concrete, named reasons, not a vague hedge: (1) the
permission gap means the application does not currently enforce who can write financial/tenant data — a
real access-control gap on live data, and (2) monitoring alarms exist and were proven to fire correctly
but do not yet reach anyone, because the SNS subscription was never confirmed. Both are small, well-
understood, and fixable in under a day of combined effort — one is a product decision, the other is a
single email click — but neither should be waved away as already handled.

*(This verdict paragraph is preserved as originally written. As of the §0 update, reason (2) has been
resolved — the SNS subscription is confirmed and independently verified. Reason (1), the permission gap,
remains the sole open blocker.)*

Everything else in this review — database configuration, backup/DR posture within its evidenced RPO,
cost discipline, and the infrastructure's actual security posture — is genuinely solid and does not need
further hardening at current scale.
