# Changelog

## [Unreleased]

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
