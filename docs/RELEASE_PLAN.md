# Release Plan

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
