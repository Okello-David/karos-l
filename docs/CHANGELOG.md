# Changelog

## [Unreleased]

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
