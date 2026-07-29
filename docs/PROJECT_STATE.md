# Project State

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

- **Reports** page is a placeholder ("Coming Soon" on Occupancy/Financial/Student report cards). **Product decision (2026-07-04): deferred from v1.0, not release-blocking.** Reports require a genuine reporting-feature pass (data aggregation, filters, export formats) that is out of scope for stabilization; the placeholder with a link to the working Backup & Export CSV/XLSX export is considered an acceptable v1.0 substitute. Revisit as a post-launch feature pass, not before.
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
