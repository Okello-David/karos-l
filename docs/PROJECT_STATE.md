# Project State

## Staging stopped, with one-command recovery (2026-08-01)

**Staging is STOPPED** (compute billing off) after the demo-readiness work, and restarting it is now a
single command instead of four manual steps across two machines.

```bash
./scripts/recover-staging.sh     # stopped -> running -> verified working
./scripts/verify-staging.sh      # "is staging actually up?" — read-only, any time
```

Both run from the **workstation**. `recover-staging.sh` starts the instance (retrying AWS capacity errors),
repairs the `.env` origins, issues a certificate for the new hostname only if one is missing, recreates the
containers, deletes orphaned certificates, and verifies from outside. **Proven end to end**, not just
written: the instance was stopped, `verify-staging.sh` correctly reported it down, `recover-staging.sh`
brought it back unattended to **12/12 checks passing**, and a second run correctly skipped certificate
issuance and found no orphans.

**The failure this addresses is deceptive, which is why it kept costing time.** After a restart the
containers come back automatically with the **old hostname still in their stored environment**
(`STAGING_DOMAIN` on the frontend, `ALLOWED_HOSTS` on the backend). Their healthchecks hit `localhost`, so
all three report **healthy**, and nginx serves the SPA with a **200** — while presenting a certificate for a
hostname that no longer resolves there and Django returns **400 to every API call**. `docker compose ps`
cannot see this. Only an external check over the real hostname can.

**Ordering trap now encoded in the script:** the old certificate must outlive the old containers. nginx
refuses to start when `ssl_certificate` points at a missing file, so deleting the orphan *before*
recreating the containers would leave the frontend unable to boot.

### Known-good baseline — what a healthy staging looks like

Confirmed **unchanged across a full stop → start → recover cycle**, so this is what recovery should restore:

| | |
|---|---|
| Data | 2 properties, 3 sections, 11 units, 16 occupants, 14 active occupancies, 13 payments, 13 receipts |
| Migrations | 40 applied, none pending |
| Users | `karosadmin` only |
| Containers | 3/3 `Up (healthy)` |
| Certificates | exactly **1** (orphans are a bug, not a leftover) |
| Timers | `karosl-backup.timer` and `certbot-renew.timer` both active after boot |
| External checks | 12/12 in `verify-staging.sh` |

A final `pg_dump` was pushed to S3 before stopping, so this dataset survives the instance entirely.

**Standing cost, unchanged:** the address moved twice more during this work (`16.171.114.188` →
`16.171.227.174` → `13.61.179.252`). Recovery is now cheap, but it is a *treatment*. Only an Elastic IP or a
purchased domain removes the cause.

## Demo readiness: Reports built, demo data seeded (2026-08-01)

**Reports is no longer a placeholder.** The three cards that had said "Coming Soon" since the feature was
deferred from v1.0 on 2026-07-04 now produce real reports, each viewable in the page and downloadable as
CSV or XLSX. This closes the longest-standing known gap in `docs/PROJECT_STATE.md`.

**New `backend/apps/reports/`** — three read-only endpoints, **no new models and no new business rules**:

| Endpoint | Shows |
|---|---|
| `/api/reports/occupancy/` | Capacity, occupied, available and occupancy rate per property, plus totals |
| `/api/reports/financial/` | Collections, outstanding balances, per-property split, payment-method breakdown, optional date range |
| `/api/reports/occupants/` | Every active occupant with unit assignment, contact details and balance |

Occupancy reuses the capacity maths from `DashboardSummaryView`; balances go through
`PaymentService._calculate_occupancy_charge`. **A report therefore cannot disagree with what an occupant's
own profile shows** — which is the whole reason for reusing rather than reimplementing.

**Two design decisions worth knowing:**

- **The financial date range filters payments only.** What someone owes today is not a function of which
  dates you are looking at, so narrowing the window changes collections without pretending the debt moved.
- **Payments from occupants with no active unit are attributed to "Unassigned", not dropped.** That is a
  real case (BUG-022), and dropping them would make the per-property totals silently disagree with the
  headline figure. A test asserts they reconcile.

**Guarded against the BUG-011 failure mode.** `ExportService` maps a header to a row key with a lossy
`header.lower().replace(" ", "_")`; a mismatch yields a column that exists but is **always blank**, which is
exactly how three of the four original exports shipped. Headers are now declared beside their keys, and
three tests check the transform, the keys the reports actually produce, and that no exported column is
blank in every row.

**New `manage.py seed_demo_data`** — the repo's first management command. Creates a realistic hostel
(2 properties, 3 sections, 11 units, 16 occupants, 13 payments) with **deliberately uneven occupancy**, so
the Property Explorer's traffic-light visualisation exercises full, partial and vacant states rather than
showing one flat colour. It goes through the **service layer** rather than writing rows directly, so
everything obeys the real validation and receipt-generation rules — a demo dataset that could not have been
produced through the UI would be worse than none. It refuses to run when business data exists unless
`--reset` is passed, and `--reset` never touches users or the audit log.

**Test baseline: backend 257/257** (237 + 20 new), **frontend 52/52** (45 + 7 new), build clean, lint
still exit 0 with one fewer warning. Green in CI on **both SQLite and PostgreSQL**.

Also fixed on the Reports page while it was being rewritten: an unused `Card` import (one of the known lint
warnings) and a `window.location.href` navigation that forced a full page reload inside the SPA.

## Continuous integration (2026-08-01)

**KarosL's test suites now run automatically.** `.github/workflows/ci.yml` runs on pushes to `dev` and
`cloud-deployment` and on every pull request. Until now there was no `.github/` directory at all: the
237-backend / 45-frontend baselines quoted throughout this document were produced by someone running the
suites by hand and typing the numbers in. They are now machine-enforced.

**Three parallel jobs, ~2m20s total wall time** (first run, before layer caching):

| Job | Result | Time |
|---|---|---|
| Backend tests (sqlite) | **237/237** | 2m09s |
| Backend tests (postgres) | **237/237** | 2m06s |
| Frontend lint, test, build | **45/45**, build clean | 32s |
| Docker images build | both images built | 55s |

**The backend runs a SQLite/PostgreSQL matrix**, not SQLite alone. PostgreSQL is what Docker and AWS
staging actually run, and this codebase has already had bugs that exist only at the database level
(BUG-007 and BUG-010, on the occupancy end-date CHECK constraint). Verified that the two legs are genuinely
different rather than silently both SQLite: the logs show `test_karosl_ci` created on PostgreSQL versus
`file:memorydb_default?mode=memory&cache=shared` on SQLite.

**CI was verified by making it fail, not only by making it pass.** A throwaway branch broke one backend
assertion and one frontend assertion and opened a pull request. Both backend legs and the frontend job went
**red**, traced in the logs to exactly those two breaks — and the Docker job correctly stayed **green**,
because the images still build. That also confirmed the `pull_request` trigger works, which the push
trigger alone would not have exercised. The branch and PR were deleted afterwards.

**Deliberately not included:** no deploy step, no registry push, and **no AWS credentials in the repo** —
it is public, so anything a workflow can reach is effectively public. Deployment stays the manual path in
`docs/AWS_EC2_DEPLOYMENT.md`. Branch protection (requiring CI to pass before merge) is a GitHub repo
setting, not a file, and is left for a deliberate decision.

**Note for the next person:** the repo's default branch is **`dev`**, not `main` or `master` — worth
knowing before opening a PR.

## Automated backups to S3 (2026-08-01)

**Staging database backups are now automated, verified, and off the instance.** This closes the gap that
both `docs/RELEASE_PLAN.md` and `docs/DOMAIN_HTTPS_PLAN.md` §12 independently rated the top remaining
risk: HTTPS had made the app usable with real data while `pg_dump` was still a manual habit, and the only
copy of that data lived on the same EBS volume as the compute.

**What was built:** `scripts/backup-to-s3.sh` (dump → verify → gzip → upload → prune) plus
`deploy/systemd/karosl-backup.{service,timer}`, running nightly at 02:30 UTC with `Persistent=true` so a
run missed while the instance is stopped fires on the next boot rather than being skipped. One private,
versioned, SSE-S3-encrypted bucket in `eu-north-1` with a 30-day lifecycle expiry and noncurrent-version
purge. **No new inbound port, no RDS, no NAT, no load balancer, no Elastic IP.**

**`pg_dump` was chosen over refactoring `BackupService`** because it is the only *complete* backup:
KarosL's own `BackupService` covers 8 business models and deliberately excludes users, auth tokens,
`AuditLog`, and `Backup` rows. The restore drill confirmed the dump carries all of them.

**Security posture — verified by trying the operations, not by reading the policy:** access is an EC2
instance role (`karosl-staging-backup-role`); `aws sts get-caller-identity` on the box returns the role
ARN and `~/.aws/credentials` does not exist. The role can write and read the `pg_dump/` prefix but
**`s3:DeleteObject` returns `AccessDenied`**, so a compromised instance cannot erase backup history, and
`ListBucket` outside that prefix is denied too. Expiry is the bucket lifecycle's job, not the instance's.

**Restore drill: 21/21 tables match.** A dump was pulled back *from S3* (not the local copy), restored
into a disposable `karosl_restore_test` database, and every table's row count compared against live —
identical, zero errors, live database untouched.

**Staging was found broken again on arrival, exactly as predicted.** The instance had been stopped since
2026-07-31, so its IP had moved `51.20.144.52` → `16.171.114.188`; the API returned `400` while the SPA
returned `200`, hiding the outage. Repaired with the new `scripts/fix-staging-origins.sh`, which reads the
current IP from IMDSv2, rewrites the four origin variables, and **prints rather than runs** the certbot
commands (Let's Encrypt rate-limits against the shared `sslip.io` domain). New certificate issued for
`16-171-114-188.sslip.io`, expiring 2026-10-30. **HTTPS verification re-passed:** HTTP 301s to HTTPS,
`/api/health/` returns `{"status":"ok","database":"ok"}` over a trusted certificate (`Verify return code:
0`), deep links load, protected routes 401, HSTS present, 3/3 containers healthy, `check --deploy` reports
**0 issues**, no pending migrations, and 8000/5432/5173 confirmed still closed.

**New finding — stale certificates accumulate.** Every IP change leaves the previous hostname's
certificate behind, and it can never renew again because that address no longer routes to this instance.
`certbot-renew.timer` will therefore start logging failures, and they will pile up one per restart. The
stale `51-20-144-52.sslip.io` certificate was deleted this pass; one certificate now remains. Folding that
cleanup into `fix-staging-origins.sh` is the obvious follow-up so it travels with the repair.

**Not done this pass:** the leftover 2026-07-29 smoke-test data (`KG1`/`SMK1`, 5 students, 2 payments) is
**still on staging** — the deletion was blocked by a tooling guard, not by any product problem. A ready-to-run
script is staged on the instance at `~/purge-smoketest-data.py`; run it with
`docker compose exec -T backend python manage.py shell < ~/purge-smoketest-data.py`. It deletes business
data only and preserves the audit log. A verified backup was taken immediately beforehand.

## Domain + HTTPS on AWS staging (2026-07-31)

**KarosL staging now serves HTTPS at a domain**, with a browser-trusted Let's Encrypt certificate, an HTTP→HTTPS
redirect, and automated renewal. This closes the limitation that had blocked real use — the login POST is no
longer plaintext.

**Domain:** `51-20-144-52.sslip.io` — a free wildcard-DNS hostname derived from the public IP. No registrar, no
DNS account, no cost, and a real certificate. **No Elastic IP was allocated**, and no RDS, NAT Gateway, load
balancer, ECS/Fargate, or CloudFront was created. Exactly one new inbound port: **443**
(`sgr-0b29986c961ba61aa`).

**Two problems were found before any change was made.** First, **staging was broken**: the instance had restarted
that morning and its public IP moved `13.62.49.29` → `51.20.144.52`, but the server `.env` still pinned the old
address, so every API call returned `400 DisallowedHost`. The SPA still loaded — nginx serves static files
regardless — so the outage was invisible from the home page. Second, **`SECURE_PROXY_SSL_HEADER` was absent from
the active settings module**; it exists only in `backend/config/settings_production.py`, which nothing imports.
Enabling `SECURE_SSL_REDIRECT` behind TLS-terminating nginx without it would have produced an infinite redirect
loop and taken the whole app down.

**Design:** TLS terminates at the **existing frontend nginx** — not at a load balancer, which keeps the no-ALB
guardrail intact. Certificates are obtained by certbot on the host in `--webroot` mode (the container owns port
80, so `--standalone` cannot work) and bind-mounted read-only. The nginx config is **mounted, not baked**, with
the domain injected via the image's `envsubst` templating, so **enabling HTTPS required no frontend image rebuild**
— avoiding the known `t3.micro` OOM risk — and **the real hostname is in no committed file**.

**Verified (15/15):** HTTP 301s to HTTPS; SPA and deep-link refresh load over HTTPS; `/api/health/` returns
`{"status":"ok","database":"ok"}`; certificate valid (`Verify return code: 0`, issuer Let's Encrypt, expires
2026-10-29); login returns a proper DRF validation error rather than a CSRF/CORS/gateway failure; protected routes
401; HSTS present; all three containers `Up (healthy)`; **`manage.py check --deploy` reports 0 issues**, down from
the four TLS warnings; `certbot renew --dry-run` succeeds with the timer enabled; ports 8000/5432/5173 confirmed
still closed from the internet, 80 and 443 open.

**Two healthcheck traps were found and handled**, either of which would have marked a working container unhealthy
or — worse — falsely healthy: the frontend's `wget http://127.0.0.1/healthz` must not be redirected to HTTPS
(certificate verification against a loopback address fails), and the backend's `curl` to Gunicorn bypasses nginx,
so Django would answer 301 — which `curl -f` treats as success, leaving a healthcheck that no longer tests the
database. Fixed with a port-80 `/healthz` location and `SECURE_REDIRECT_EXEMPT`.

**Authenticated business workflow re-verified over HTTPS (12/12):** login → dashboard → create property → section
→ unit → register occupant → assign occupancy → record payment (receipt `RCP-2026-00003` auto-generated) →
**valid 1-page PDF receipt** → Property Explorer hierarchy → logout → token rejected on reuse. Run with a
temporary superuser that was deleted afterwards along with every record it created; only `karosadmin` remains.

**Note:** the staging database still holds properties `KG1`/`SMK1`, 5 students, and 2 payments left over from the
2026-07-29 smoke test — unrelated to this sprint, left untouched, worth clearing before any demo.

**Standing cost of no Elastic IP:** the public IP — and therefore the sslip.io hostname and its certificate —
changes on every stop/start. Runbook: `docs/DOMAIN_HTTPS_PLAN.md` §9. A purchased domain is recommended before
real users.

**Cost correction:** an Elastic IP attached to a *running* instance costs the **same** as the auto-assigned public
IPv4, not extra. It bills only when the instance is stopped — which is exactly this project's usage pattern, and
is why no EIP was allocated. `dc-intern-backend` remains a live example of that trap.

## Post-deployment verification & hardening pass (2026-07-29)

A verification and hardening pass was run against the live staging deployment. **No business features added, no UI changes, no application code changed, no new AWS resources created.**

### Smoke test — 14/14 workflows pass

Exercised against the live public IP as real authenticated HTTP calls: frontend load, login, session persistence, dashboard, create property → section → unit, register occupant, assign occupancy, record payment, receipt JSON + **valid PDF**, Property Explorer hierarchy with live occupancy counts, logout with immediate token invalidation, and 401 on six protected routes unauthenticated. The **over-capacity guard** was also confirmed still enforced (a third assignment to a capacity-2 unit was rejected).

One apparent failure was traced to the **test harness, not the product**: `UID` is readonly in bash, so a captured unit id was silently replaced by the shell's own uid. Documented in `docs/DEVOPS.md` §10 so it doesn't cost anyone an hour again.

### Container health — clean

All three services `Up (healthy)` with `restart: unless-stopped` and **0 restarts** since launch. 40 migrations applied, `migrate --check` clean. **0 backend tracebacks/ERRORs, 0 PostgreSQL FATALs, 0 nginx 5xx.** Django admin static assets (200), SPA bundle (200), and nginx `/healthz` (200) all serving.

### Security review — all checks pass

`DEBUG=False`; `SECRET_KEY` 50 chars, not the insecure placeholder, present only in the server's `.env` (mode `600`, gitignored, 0 uncommitted files in the repo); `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS` all correctly scoped to the EC2 IP with `CORS_ALLOW_ALL_ORIGINS=False`. Host listening sockets are **only** `:80` (public), `:22` (SG-restricted to the admin `/32`), and `:8000` **bound to `127.0.0.1` only** — PostgreSQL is not published to the host at all. Externally confirmed: ports **8000, 5432, 5173, and 443 are all closed**; only 80 is open. **No `demo` account exists** on staging; the only account is `karosadmin`.

`manage.py check --deploy` reports 4 warnings, all four being TLS-related (`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) — the expected and documented consequence of HTTP-only staging, resolved by the HTTPS sprint. Notably **absent** are `W018` (DEBUG on) and `W009` (weak SECRET_KEY), which is positive evidence rather than silence.

### Known limitations (staging, accepted)

- **No HTTPS.** Traffic is plaintext HTTP, including the login POST. Acceptable only because staging holds no real data — and the reason no real tenant data may be entered.
- **No automated backups.** `pg_dump` is manual; the `postgres_data` volume survives reboots and `docker compose down`, but not `down -v` or instance termination.
- **Single point of failure.** One instance, one container database, no replication.
- **Public IP is ephemeral** (no Elastic IP) — it changes on stop/start and requires a `.env` origin update each time.
- KarosL's own `BackupService` does **not** cover users, auth tokens, `AuditLog`, or `Backup` rows; only `pg_dump` is a complete backup.

## AWS staging DEPLOYED (2026-07-29)

**KarosL is live on AWS staging.** Region `eu-north-1`, instance `i-0afd1871b46296500` (`karosl-staging-ec2`, `t3.micro`, Amazon Linux 2023), security group `karosl-staging-sg` (`sg-065fb018e22aa18a5`), 10 GB encrypted gp3 root volume, auto-assigned public IP. The stack is the unmodified `docker-compose.yml` — nginx/React + Gunicorn/Django + PostgreSQL container — deployed from the new `cloud-deployment` branch into `/home/ec2-user/apps/karosl`.

**Deliberately not created:** RDS, NAT Gateway, load balancer, ECS/Fargate, Elastic IP, extra EBS volumes.

**Verified live:** all three containers healthy; 40 migrations applied against PostgreSQL; `/api/health/` returns `{"status":"ok","database":"ok"}` *through the public IP*, proving the whole internet → security group → nginx → Gunicorn → PostgreSQL chain; SPA loads with deep-link refresh working; `/api/auth/login/` returns a proper Django validation error rather than a gateway error; protected endpoints return 401; ports 8000 and 5432 confirmed unreachable from the internet.

**Authenticated access verified:** `karosadmin` password set; login through the public IP returns a DRF token and authenticated reads of dashboard/properties/occupants all return 200.

**Outstanding:** the business-workflow walkthrough (create property → register occupant → record payment → receipt) has not been run on staging; the database is empty apart from the admin user.

**Two environment realities found by deploying for real:**
- Amazon Linux 2023 ships Docker with **buildx 0.12.1**, but Compose v5 requires **≥ 0.17.0**, so `docker compose build` fails outright until a current buildx plugin is installed. `scripts/server-setup.sh` now handles this.
- A `t3.micro` has ~916 MB usable RAM. A 2 GB swapfile was added before building; the previously-documented OOM risk for the frontend `npm run build` is real, not theoretical.

**Cost posture:** no Elastic IP, so a stopped instance bills only its 10 GB EBS volume. Stop it between sessions; note the public IP changes on restart and the `.env` origins must be updated.

---

Snapshot as of 2026-07-29, after the AWS **staging preparation** pass (see `docs/AWS_STAGING_CHECKLIST.md` and `docs/AWS_EC2_DEPLOYMENT.md`). Prior snapshot (2026-07-23) was the AWS deployment planning pass (`docs/AWS_DEPLOYMENT_PLAN.md`); before that (2026-07-04), the Cloud Engineering Phase's containerization pass (`docs/DEVOPS.md`, `docs/DEPLOYMENT.md`), which itself followed the RC Final Stabilization Closeout (`docs/RELEASE_PLAN.md`, `docs/BUG_QUEUE.md`).

## AWS staging preparation (2026-07-29)

**Documentation and deployment assets only. No AWS resources created, nothing deployed, no application code or business features changed.** KarosL has passed local Docker production simulation, so this pass prepared everything needed to execute Phase 2 of `docs/AWS_DEPLOYMENT_PLAN.md` — a single EC2 instance running the same Compose stack over HTTP, with PostgreSQL still in a container.

Delivered: `docs/AWS_STAGING_CHECKLIST.md` (account-safety gate, EC2 plan, security-group rules with the rationale for never exposing 5432, server setup, verification, cleanup), `docs/AWS_EC2_DEPLOYMENT.md` (the full command runbook plus a troubleshooting section), a mandatory cost-safety pre-deployment step in `docs/AWS_DEPLOYMENT_PLAN.md` and `docs/DEPLOYMENT.md`, staging env-var documentation in all three `.env.example` files, a troubleshooting section in `docs/DEVOPS.md` §10, and three optional helper scripts (`scripts/server-setup.sh`, `scripts/deploy-staging.sh`, `scripts/docker-logs.sh`).

**The gate is restated everywhere it matters: no AWS deployment proceeds before an AWS Budget with email alerts is configured and a test alert is confirmed received.**

Three configuration facts were established by reading the actual container definitions, and each one silently breaks a staging deployment if missed:
- `FRONTEND_PORT` defaults to `8080` and must be `80` on EC2 — the security group only opens port 80, so the app would otherwise be unreachable.
- `ALLOWED_HOSTS` must gain the EC2 public IP **and keep `localhost`** — the backend container's Docker `HEALTHCHECK` curls `http://localhost:8000/api/health/`, and Django returns 400 for an unlisted `Host`, marking the container permanently unhealthy while the app itself works fine.
- `VITE_API_BASE_URL` must stay `/api` — it is inlined into the JS bundle at build time, so an absolute URL would freeze the EC2 IP into the image and turn same-origin API calls into cross-origin ones.

Also confirmed while reviewing settings for the env documentation: KarosL uses **DRF Token authentication, not JWT** (`backend/config/settings.py`), so there is no separate JWT signing secret to manage — `SECRET_KEY` remains the only cryptographic secret.

## Where things stand

KarosL is a Django REST Framework + React (Vite) accommodation-management platform. Application stabilization (Release Candidate) is complete; the project is in the **Cloud Engineering Phase**, with AWS staging **deployed and live** in `eu-north-1` (see the top of this document). Core domain (properties → sections → units, occupants, occupancy, payments/receipts, administration, audit log, backup/export) is implemented and has been verified end-to-end against a live running instance, and verified running fully containerized (Docker Compose: Nginx + Gunicorn/Django + PostgreSQL) — see `docs/DEVOPS.md` for architecture and `docs/DEPLOYMENT.md` for build/run/verify steps.

## Docker stack re-verification (2026-07-23)

Ahead of the AWS EC2 deployment, the local production-like Docker stack was re-verified end-to-end on Docker Engine 29.1.3 / Compose v5.1.4. **No Docker files needed changes** — the 2026-07-04 containerization was audited and confirmed working as-is (zero gaps). All 11 verification points passed: both images build; all three services come up healthy; Django connects to PostgreSQL with 40 migrations applied and none pending; superuser creation works; the SPA loads through Nginx (including deep-link refresh via `try_files`); the frontend reaches the API through the Nginx `/api` proxy; token login works through the proxy; and a real write workflow (create property) was confirmed persisted by querying PostgreSQL directly. Backend tests are **237/237 in-container against PostgreSQL** and **237/237 native (SQLite)**; frontend `npm run build` is clean and `npm test` is **45/45** — so the non-Docker local workflow remains intact. See `docs/DEVOPS.md`/`docs/DEPLOYMENT.md` for architecture/commands and `docs/CHANGELOG.md` for the full verification record.

## AWS deployment planning (2026-07-23)

The AWS deployment architecture, cost controls, environment strategy, secrets handling, and exit path are now **documented ahead of provisioning any cloud resource** — see `docs/AWS_DEPLOYMENT_PLAN.md`. **Nothing has been deployed and no AWS resources have been created.** This was a documentation-only pass (no application code, no infra, no business features changed).

The plan is a cost-conscious, phased path that reuses the existing Docker Compose stack unchanged: **(1)** local Docker production simulation *(already done)* → **(2)** single small EC2 running Docker Compose (Postgres in a container; staging/demo) → **(3)** move DB to Amazon RDS PostgreSQL (env-vars-only swap) → **(4)** move backup files to S3 → **(5)** CloudWatch logging/monitoring → **(6)** optional future ALB + ECS/Fargate. A hard gate is documented: **no AWS resource may be created before an AWS Budget with email alerts is configured.** Next concrete step is Phase 2, gated on the "Before AWS" checklist (incl. budget alerts and removing/rotating the `demo` account).

## Containerization (2026-07-04)

KarosL now runs outside the developer's native machine setup, proven via a local, production-like Docker Compose stack:

- `backend/Dockerfile` — `python:3.12-slim`, Gunicorn (never `runserver`), migrations + `collectstatic` run automatically on container start via `backend/docker-entrypoint.sh`, WhiteNoise serving Django's own static assets.
- `frontend/Dockerfile` — multi-stage: `node:20-alpine` builds the Vite production bundle, `nginx:1.27-alpine` serves it and reverse-proxies `/api/`, `/admin/`, `/static/` to the backend.
- `docker-compose.yml` — production-like stack (Postgres + backend + frontend), all three healthchecked.
- `docker-compose.dev.yml` — optional containerized hot-reload dev loop (Django `runserver` + Vite dev server); the native venv/`npm run dev` workflow remains the primary path and is untouched.
- New `GET /api/health/` endpoint (`apps/core/views.py`) — unauthenticated liveness/readiness probe, checks DB connectivity, used by the backend container's `HEALTHCHECK`.

Two real, pre-existing gaps surfaced only by containerizing (both fixed, not previously visible because the native venv had extra packages/assumptions baked in by hand):
- `openpyxl` (used by `ExportService._write_xlsx`) was installed in the local venv but never listed in `requirements.txt` — the container's XLSX export tests failed until added.
- `SECURE_SSL_REDIRECT`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SECURE` were hardcoded to `not DEBUG`, silently assuming DEBUG=False implies HTTPS is present. The Docker Compose environment runs DEBUG=False with no TLS termination anywhere in the chain, so this forced HTTPS redirects and broke all HTTP access. Fixed by making these independently env-configurable (default behavior unchanged for real production behind TLS); `docker-compose.yml` explicitly sets them to `False` for this TLS-less local environment.

Verified end-to-end inside the container stack: `docker compose build` (both images), `docker compose up` (all three healthy), migrations applied against Postgres, full Django test suite (237/237) run inside the backend container, and a live login → create property → register occupant → dashboard summary chain through the frontend's nginx proxy, with data confirmed persisted in Postgres. Full detail in `docs/DEVOPS.md` and `docs/DEPLOYMENT.md`.

Full detail on what's local-only today vs. planned for S3 (backup JSON files only — everything else is either static app code or generated in-memory with no disk footprint) is in `docs/DEVOPS.md` §6.

## Prior state: Release Candidate Stabilization (complete)

## What works (verified live this pass)

- Authentication: login/logout, session persistence across refresh, protected routes, unauthorized-access redirects.
- Property / Section / Unit management, including status transitions (Active/Maintenance/Archived) and capacity/pricing.
- Property Explorer: live occupancy visualization, unit detail panel, quick actions.
- Occupant register/search/edit/profile/archive.
- Occupancy assignment (3-step wizard), over-capacity prevention, checkout, occupancy history preservation.
- Payments: full/partial/monthly billing, balance calculation, payment history, validation against non-positive amounts.
- Receipts: auto-generated per payment, searchable, PDF retrieval.
- Dashboard: live occupancy/outstanding/recent-payments figures, working quick actions.
- Administration: Properties, Sections, Units, Users tabs fully exercised; Pricing tab's underlying pricing engine confirmed correct via the payment/billing-mode tests (full click-through on the Pricing tab's own CRUD UI was not completed live due to test-script fragility, not a known product issue).
- Audit Trail: every action taken during this pass logged with correct actor/action/entity/timestamp.
- Backup & Export: backup creation, backup history, CSV export all confirmed working.
- Responsive layout: zero horizontal overflow across 6 key pages at desktop/tablet/mobile widths.

## Known gaps (not implemented, out of scope to add per "no new business features")

- ~~**Reports** page is a placeholder~~ — **closed 2026-08-01.** Deferred from v1.0 on 2026-07-04 as a product decision, and built when a client review made the "Coming Soon" cards a liability rather than an honest expectation-setter. All three reports now work and export to CSV/XLSX; see the demo-readiness entry at the top of this document.
- **Move occupant to another unit** is not implemented (no route, no service method). Present in `docs/WORKFLOWS.md`'s aspirational spec but never built.
- Archived properties are excluded entirely from the Property Explorer / Properties list API (`PropertyExplorerView` filters `is_active=True`) rather than shown with an Archived badge — a pre-existing, previously-documented design gap.
- No CI/CD pipeline, no S3/object storage integration, no TLS termination, and no cloud hosting yet — expected at this stage of the Cloud Engineering Phase, not regressions. Full detail and planned order of work in `docs/DEVOPS.md` §8–9.

## Fixed this pass (2026-07-04, RC Final Stabilization Closeout)

- Archived properties/sections could still receive new sections/units via Administration with no guard — now rejected server-side with a friendly error message. See `BUG_QUEUE.md`.
- `UnitTab`'s status badge rendered the raw lowercase enum instead of Title Case — cosmetic fix, no stored/API values changed. See `BUG_QUEUE.md`.
- `Backup Restore` dry-run executed against an isolated, disposable SQLite database (never the real dev database) with a realistic multi-entity dataset, including hard-deleted and corrupted records. All checks passed — **restore is confirmed production-safe** for the data it covers (Property, Section, Unit, PricingRule, Student, Occupancy, Payment, Receipt). Note: `AuditLog` and `Backup` records are intentionally outside restore's scope (by design), and restored rows' `updated_at` reflects the restore's own execution time, not the original backup timestamp (a pre-existing, cosmetic limitation of `BackupService.restore_backup`). Full detail in `BUG_QUEUE.md`.

## Fixed prior pass (2026-07-02, Release Candidate Verification Pass)

- Full-name search (occupants and payments) returning zero results — see BUG-026, BUG-027.
- Dashboard's own "Record Payment" quick action dead-ending through the unrelated Occupants list — see BUG-028.

## Test/build baseline (end of Cloud Engineering containerization pass, 2026-07-04)

- Backend: full Django test suite — **237/237 passing** (236 prior + 1 new health-check test), run both natively (SQLite) and inside the Docker container against PostgreSQL.
- Frontend: `npm run build` clean, `npm run lint` shows only pre-existing, unrelated warnings, `npm test` **45/45 passing** — verified natively; the Docker-built bundle was verified by loading it through the running frontend container instead of re-running the Vitest suite inside that image (Vitest/jsdom isn't part of the nginx runtime image by design).
- Docker: both images build clean; full stack (`db`, `backend`, `frontend`) starts healthy; login → create property → register occupant → dashboard summary verified end-to-end through the frontend's nginx proxy, with the write confirmed persisted in Postgres via `psql`.

## Test/build baseline (RC Final Stabilization Closeout, 2026-07-04 earlier)

- Backend: full Django test suite — **236/236 passing** (234 prior + 2 new tests for the archived-property validation guard).
- Frontend: `npm run build` clean, `npm run lint` shows only pre-existing, unrelated warnings, `npm test` **45/45 passing** (no frontend tests added — the cosmetic badge fix and backend-only validation guard needed no new frontend test coverage).

## Environment notes for whoever picks this up next

- Two onboarding overlays exist and stack: `WelcomeScreen` (dismissed via "Skip tour") automatically triggers `GuidedTour` immediately after, which needs its own dismissal (Escape key works, or click through its steps). Both use `localStorage` keys (`karos_welcome_dismissed`, `karos_tour_dismissed`) that persist once dismissed in a given browser profile.
- A `demo` / `demo12345` staff+superuser account exists in the dev database for manual testing (created in a prior session at the user's request, not deleted).
