# Changelog

## Backend API Stability Sweep

### Backend Fixes
- Fixed occupant creation crashing with HTTP 500 (`IntegrityError`) whenever a second occupant was created without an email, student ID, or national ID, by making those fields nullable and normalizing blank submissions to `null` (ported and applied the existing vetted fix for this).
- Applied a same-day-checkout database migration that existed in the codebase but had never been run, so same-day checkout still crashed before this fix.
- Fixed a crash recording payments for occupants without a student ID number, caused by the occupant nullability fix above.
- Made payment recording atomic so a receipt-generation failure no longer leaves an orphaned payment record with no receipt.
- Fixed occupancy checkout incorrectly allowing a stale "active" state after an occupancy's end date was updated directly, which could crash a later checkout attempt.
- Fixed CSV/Excel exports for occupants, occupancies, and receipts silently omitting the Student ID, Active, Outstanding Balance, Unit, and Property columns due to a header/data key mismatch.

### Tests
- Added backend regression tests for: creating a second occupant with blank optional identifiers, recording a payment for an occupant without a student ID, payment/receipt atomicity on failure, occupancy `end_date`/`is_active` consistency, and export column accuracy for occupants, occupancies, and receipts.

## Critical/High Debugging Pass

### Backend Fixes
- Restricted administration endpoints to authenticated Property Manager users or superusers instead of any authenticated user.
- Prevented admin user create/update from accepting writable `is_superuser` and fixed group assignment through `groups.set(...)`.
- Fixed pricing-rule create/delete HTTP 500 errors caused by reading serializer-only `unit_name` on `PricingRule` models.
- Fixed backup restore for serialized foreign keys by restoring FK values through `<field>_id` attributes.
- Fixed occupancy assignment price snapshots to use effective pricing rules.
- Fixed monthly balance calculation so snapshotted monthly prices are multiplied by elapsed billing months.
- Allowed same-day checkout by aligning occupancy validation and DB constraint with checkout behavior.
- Fixed payment serialization for payments that do not have receipt records.
- Fixed dashboard summary API response for the current Dashboard page by returning `total_students` and `active_students` from `/api/occupancy/summary/`.

### Frontend Fixes
- Fixed `OccupantDetail` payment-summary loading crash by importing `CardSkeleton`.
- Fixed Global Search endpoint paths and explorer response handling.
- Fixed Explorer unit selection so clicking a unit opens the existing detail panel.
- Fixed authenticated receipt PDF downloads by fetching PDFs through the token-aware API client.
- Fixed the Properties page so created properties display from the existing property hierarchy API instead of a static placeholder.
- Prevented Administration unit creation from submitting without a selected section.
- Fixed Payment workflow crash (`useState is not defined`) by importing `useState` in `PaymentDetailDialog`.

### Tests
- Added/updated backend tests for admin permissions, pricing-rule create/delete, user groups, backup FK restore, pricing-rule snapshots, same-day checkout, monthly billing snapshots, and payments without receipts.
- Added a backend release workflow test covering login, property/section/unit setup, occupant assignment, payment/receipt, dashboard/explorer, backup/export/restore, and logout.
- Added frontend tests for Global Search API paths, Explorer unit selection, and the Properties overview page.
- Added a frontend test for `PaymentDetailDialog` rendering to guard against the missing-import crash.

## Sprint 17 — UX & Onboarding (DONE)

### New Components

#### Toast Notification System (`src/components/Toast.jsx`)
- `ToastProvider` — React context provider wrapping the app; renders notification stack at bottom-right
- `useToast()` hook — `addToast(message, { type, duration })` and `dismissToast(id)`; types: success/error/warning/info
- Auto-dismiss after configurable duration (default 4s), manual dismiss via close button
- Accessible with `aria-live="polite"` and `aria-label="Notifications"`

#### Welcome Screen (`src/components/WelcomeScreen.jsx`)
- 4-step onboarding modal shown on first visit (stored in `localStorage`)
- Steps: Welcome, Manage Occupants & Payments, Explore & Monitor, Keyboard Shortcuts
- SVG icons per step, step indicator dots, Skip/Next/Get Started navigation
- Transitions seamlessly into Guided Tour on dismiss if not previously completed

#### Guided Tour (`src/components/GuidedTour.jsx`)
- Step-by-step overlay tour highlighting key UI elements: sidebar, global search, explorer link, quick actions
- Tooltip positioning (top/bottom/left/right/center) with arrow indicators
- Highlight ring around target elements, backdrop overlay, keyboard (Escape) support
- Completion tracked in `localStorage`; `resetTour()` utility for re-testing

#### Global Search (`src/components/GlobalSearch.jsx`)
- Modal search dialog triggered via Ctrl+K (or shortcut button)
- Debounced (300ms) parallel search across 3 APIs: `/api/occupants/`, `/api/receipts/`, `/api/explorer/properties/`
- Categorized results (Occupants, Receipts, Properties) with keyboard navigation (Arrow Up/Down/Enter)
- Results displayed with labels, subtitles, type badges; footer shows navigation hints
- Escape to close, backdrop click to close

#### Keyboard Shortcuts (`src/components/KeyboardShortcutsHelp.jsx` and `src/hooks/useKeyboardShortcuts.js`)
- `useKeyboardShortcuts(shortcuts, enabled)` — global keydown listener that avoids inputs
- Default shortcuts: Ctrl+K (search), ? (help), Escape (close/blur), H/E/O/P/R (navigation), / (focus search)
- `KeyboardShortcutsHelp` component — modal overlay with full shortcut listing; supports custom shortcuts prop
- All shortcuts rendered as `<kbd>` elements; accessible dialog with Escape to close

#### Skeleton Loading Components (`src/components/Skeleton.jsx`)
- `Skeleton` — base animated pulse placeholder with custom className
- `TableSkeleton` — row × column grid skeleton for table loading states
- `CardSkeleton` — card grid skeleton with configurable count and height

#### Enhanced Spinner (`src/components/Spinner.jsx`)
- Added `size` prop (sm/md/lg) and `label` prop for accessible loading text
- Added `InlineSpinner` — small inline variant for buttons and inline contexts
- Added `role="status"` for accessibility

#### Enhanced EmptyState (`src/components/EmptyState.jsx`)
- Added `icon` prop with 6 built-in options: default, people, currency, search, building, receipt
- Added `hint` prop for secondary contextual help text below description
- Backward compatible — existing uses continue to work with default icon

### Updated Components

#### MainLayout (`src/layouts/MainLayout.jsx`)
- Wrapped in `ToastProvider` for global notification access
- Integrated `WelcomeScreen` (shown once, checks `localStorage`)
- Integrated `GuidedTour` (auto-starts after welcome dismiss)
- Integrated `GlobalSearch` (Ctrl+K toggle)
- Integrated `KeyboardShortcutsHelp` (? toggle)
- Registered all keyboard shortcuts via `useKeyboardShortcuts`

#### Sidebar (`src/components/Sidebar.jsx`)
- Added `data-tour="sidebar"` and `data-tour="explorer-link"` attributes for tour targeting

#### Topbar (`src/components/Topbar.jsx`)
- Added `data-tour="topbar-search"` attribute for tour targeting

#### ActionCard (`src/components/dashboard/ActionCard.jsx`)
- Added `data-tour="actions"` attribute for tour targeting

### Page Improvements

#### Updated Empty States
- **Occupants** — `icon="people"` for no results, `icon="search"` for search misses; added hint for occupant import
- **Payments** — `icon="currency"` for no payments; contextual message for search misses; overdue section uses EmptyState for "all caught up"
- **Receipts** — `icon="receipt"` for no receipts; contextual message for search misses
- **Properties** — `icon="building"` with hint to Administration; action button navigates to /administration
- **Administration** — all tabs use EmptyState components with appropriate icons; audit tab uses EmptyState
- **Dashboard** — "No properties" and "No recent activity" now use EmptyState components
- **Backup** — empty backup history uses EmptyState component
- **Explorer** — no results/empty state uses EmptyState component (search or building icon)

#### Consistent Loading States
- **All pages** — inline `animate-pulse` divs replaced with reusable `Skeleton` component:
  - OccupantForm (form skeleton)
  - Occupants (table skeleton)
  - Payments (table + overdue skeletons)
  - Receipts (table skeleton)
  - Backup (table skeleton)
  - Administration (all 5 tabs + roles skeleton)
- `Spinner` usage reduced to only where spinning indicator is semantically correct (loading overlays, audit log)

#### New/Updated Pages
- **NotFound (404)** — redesigned with 6 quick-link navigation cards (Overview, Explorer, Occupants, Payments, Receipts, Administration) + CTA button; replaces bare "page not found" text
- **Reports** — redesigned with 3 feature cards (Occupancy, Financial, Student) each with icon + description + "Coming Soon" button; info banner with link to Backup/Export

#### Success Messages
- **OccupantForm** — toast on create/update success
- **Administration** — all CRUD operations (property/section/unit/pricing/user) and archive/toggle actions show toast instead of `alert()`

### Tests
- 20 new frontend tests across 4 new test files:
  - `Spinner.test.jsx` — 6 tests (sizes, label, role status, InlineSpinner)
  - `Skeleton.test.jsx` — 4 tests (base render, custom class, TableSkeleton, CardSkeleton)
  - `Toast.test.jsx` — 4 tests (success/error display, immediate dismiss, provider required)
  - `KeyboardShortcutsHelp.test.jsx` — 6 tests (hidden state, open rendering, close button, backdrop, Escape, custom shortcuts)
- All 36 tests pass across 8 test files

## Sprint 16 — Production Readiness Review (DONE)

### Backend — Security Hardening (`config/`)
- Added `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_BROWSER_XSS_FILTER`, `X_FRAME_OPTIONS='DENY'`
- Added secure cookie flags: `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- Added HSTS settings: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`
- Added `CORS_ALLOW_CREDENTIALS` and `CSRF_TRUSTED_ORIGINS`
- Created `config/settings_production.py` — production-optimized settings (PostgreSQL, strict CORS, email alerts, no browsable API)
- Created `.env.example` with comprehensive documentation for all environment variables
- Added DRF throttling: `AnonRateThrottle` (100/hr) and `UserRateThrottle` (1000/hr) with stricter production limits
- Added DRF global pagination defaults: `PAGE_SIZE=20`, `MAX_PAGE_SIZE=100`

### Backend — Error Handling (`apps/core/`)
- Added `drf_exception_handler()` — global exception handler returning consistent JSON `{detail, status_code}` for all API errors
- Prevents HTML error pages from being returned in DRF responses
- Preserves field-level validation errors while wrapping top-level exceptions
- Added 3 tests for exception handler (401, 404, 400 responses)

### Backend — Logging Improvements (`config/settings.py`)
- Added `RotatingFileHandler` — writes WARNING+ logs to `logs/karosl.log` (10MB max, 5 backups)
- Production settings add `mail_admins` handler for ERROR-level notifications
- Separate loggers for `django`, `django.request`, and `karosl` namespaces

### Backend — Performance (`apps/payments/services/`)
- Optimized `list_overdue_students()` — uses `prefetch_related` to reduce N+1 queries on occupancy data
- Reduced per-student balance queries by prefetching occupancies

### Backend — Dashboard App (`apps/dashboard/`)
- Implemented `DashboardSummaryView` with capacity, occupancy, student counts, and recent payments
- Added `urls.py` with endpoint at `/api/dashboard/`
- Registered dashboard URLs in root URL config
- Added 4 tests: unauthenticated, summary, with occupancy data, property manager access

### Frontend — Bug Fix (`src/hooks/useOccupants.js`)
- Fixed pagination: `useOccupants` now accepts a `params` object (like other hooks) instead of only `{search, status}`
- `page` parameter is now properly passed to the API and tracked via `JSON.stringify(params)` dependency
- Occupants page now resets to page 1 when search or status filter changes

### Frontend — Error Boundary (`src/components/ErrorBoundary.jsx`)
- Added `ErrorBoundary` component wrapping the entire app route tree
- Catches unhandled React errors and displays a friendly error page with "Try Again" and "Go to Overview" options
- Displays error message in a monospace styled block for debugging

### Frontend — Accessibility Improvements
- Added skip-to-content link at the top of `MainLayout.jsx` (visible on focus for keyboard users)
- Added `tabIndex={-1}` to `<main>` for programmatic focus management
- Added Escape key handling and auto-focus in `ConfirmDialog`
- Focus restoration on dialog close (returns focus to previously focused element)
- Expanded `breadcrumbMap` in `Topbar.jsx` to include all routes (Explorer, Receipts, Backup, New Occupant)

### Tests
- **Backend**: 11 new tests across dashboard (4), core exception handler (3), and additional coverage
- **Frontend**: All 16 existing tests continue to pass

## Sprint 15 — Backup, Restore & Data Export (DONE)

### Backend — Backup App (`apps/backup/`)
- `Backup` model — created_by (FK User), status (pending/in_progress/completed/failed), file_path, file_size, metadata (JSON), notes, created_at
- `BackupService.create_backup()` — serializes 8 models (Property, Section, Unit, PricingRule, Student, Occupancy, Payment, Receipt) to JSON; writes to `backups/` directory
- `BackupService.list_backups()` — paginated listing with select_related(created_by)
- `BackupService.get_backup()`, `validate_backup()` — validates file exists, JSON is valid, data key exists
- `BackupService.restore_backup()` — transactional (all-or-nothing), FK field conversion, upsert logic (update existing or create new)
- `ExportService.export_occupants/occupancies/payments/receipts()` — exports in CSV or XLSX (openpyxl) with proper headers, datetime sanitization
- 4 APIView-based endpoints at `/api/backups/`: list/create, detail, restore, validate
- Export endpoint at `/api/backups/export/` — `?entity=occupants&file_format=csv` or `xlsx`
- All endpoints restricted to `IsAuthenticated & IsSuperAdmin`
- Audit logging for backup create and export actions (`AuditLog.EntityType.BACKUP`)
- 31 tests: model, service (create/list/get/validate/restore/export), API (list/create/detail/restore/validate/export with auth/superuser/format/entity validation, CSV/XLSX)

### Fixes
- Export URL routing: restructured from ViewSet+DefaultRouter to explicit APIView subclasses to avoid `@action` decorator ordering issues
- `?file_format=` query param (not `?format=`) to avoid DRF content negotiation `Http404` on unknown renderer formats
- XLSX export: datetime objects sanitized via `_sanitize_cell_value()` to avoid openpyxl timezone error

### Frontend
- `services/backup.js` — `list()`, `get()`, `create()`, `restore()`, `validate()`, `exportData()` (blob download)
- `hooks/useBackup.js` — `useBackups(params)` (paginated), `useBackup(id)`, `useBackupAction()` (create/restore/validate with loading+error states)
- `pages/Backup.jsx` — Backup Dashboard with:
  - **Create Backup** card (one-click full system backup)
  - **Export Data** card → Export Dialog modal (entity + format selector, blob download)
  - **Restore** card with warning
  - **Backup History** table (status badges, date, size, records, notes, Restore button)
  - **RestoreWizard** modal: confirm step (warning + backup details) → done step (restored counts)
  - Pagination, loading/error/empty states
- `components/Sidebar.jsx` — added "Backup" nav item with database icon
- `App.jsx` — added `/backup` route

## Sprint 14 — Audit Trail (DONE)

### Backend — Audit App (`apps/audit/`)
- `AuditLog` model — actor (FK to User), entity_type (Occupant/Occupancy/Payment/Receipt/Property/Section/Unit/PricingRule/User), entity_id, action (Create/Update/Delete/Archive/Assign/Checkout/RecordPayment/Login/Other), description, changes (JSON), ip_address, timestamp (auto, indexed)
- `AuditService` — `log()` creates entries, `list_logs()` paginates with entity_type/action/actor/date filters, `get_log()` by primary key
- `AuditLogSerializer` — nested actor (id, username), entity_type_display/action_display computed fields
- `AuditLogListView` — `GET /api/audit/` paginated list with filter query params (entity_type, entity_id, action, actor_id, date_from, date_to); restricted to `IsSuperAdmin`
- `AuditLogDetailView` — `GET /api/audit/<id>/` single entry; restricted to `IsSuperAdmin`
- `AuditEntityTypesView` — `GET /api/audit/entity-types/` returns available entity type choices
- `AuditActionsView` — `GET /api/audit/actions/` returns available action choices
- URLs at `/api/audit/`

### Audit Integration (views layer)
- **Occupants** (`apps/occupants/views.py`): create, update, partial_update, archive all log audit entries
- **Occupancy** (`apps/occupancy/views.py`): assign (create), partial_update, checkout all log audit entries
- **Payments** (`apps/payments/views.py`): record_payment logs audit entry
- **Administration** (`apps/administration/views.py`): property/section/unit CRUD + archive, pricing rule CRUD + delete, user CRUD + toggle_active all log audit entries

### Tests
- 20 audit tests: model creation, string representation, service log/create/list/filter/get, API auth (superuser-only), list/detail/entity-types/actions endpoints, pagination, entity type/action filtering
- Integration tests: occupant create/archive, occupancy assign, payment record all automatically produce audit logs

### Frontend
- `services/audit.js` — `auditService.list()`, `auditService.get()`, `auditService.entityTypes()`, `auditService.actions()`
- `hooks/useAudit.js` — `useAuditLogs(params)` (paginated), `useAuditLog(id)`, `useAuditMeta()` (entity types + actions)
- `pages/Administration.jsx` — added "Audit Log" (6th) tab with:
  - Filter bar: entity type dropdown, action dropdown, date range pickers
  - Activity timeline: clickable cards with colored action badges, entity type styling, actor, timestamp
  - Detail view: full entry breakdown (ID, actor, IP, entity, action, description, changes JSON)
  - Pagination: Previous/Next with page indicator
  - Loading/error/empty states

## Sprint 13 — Administration Module (DONE)

### Model Changes
- `Section.order` — PositiveSmallIntegerField for reordering (migration 0002)
- `Unit.status` — CharField with choices: active / maintenance / archived; `is_active` auto-computed from status via `save()` (migration 0002)
- `Unit.order` — PositiveSmallIntegerField for ordering
- `Unit.semester_price` and `Unit.monthly_price` — preserved for backward compatibility
- `PricingRule` model — unit FK, billing_mode, price, effective_date; allows configurable pricing with effective dating (migration 0002)
- `Occupancy.agreed_price` — snapshots pricing at assignment time so historical occupancies don't change when prices update (migration 0003)
- `PaymentService._calculate_occupancy_charge()` — uses `agreed_price` if available, falls back to unit prices

### Backend — Administration App (`apps/administration/`)
- `AdminPropertyViewSet` — full CRUD + archive (blocks if active sections exist)
- `AdminSectionViewSet` — full CRUD + archive (blocks if active units exist) + reorder (bulk POST)
- `AdminUnitViewSet` — full CRUD + status changes + archive (blocks if active occupants exist)
- `PricingRuleViewSet` — CRUD for pricing rules; pricing is effective-dated so new rules don't touch existing occupancies
- `AdminUserViewSet` — list/create/update users, toggle active, list groups/roles
- `AdminService` — service layer with business rule enforcement (ConflictError for archive blocks, NotFoundError for missing resources)
- `_handle_exceptions` decorator on views that converts `ConflictError` → 409, `NotFoundError` → 404
- URLs at `/api/admin/properties/`, `/api/admin/sections/`, `/api/admin/units/`, `/api/admin/pricing-rules/`, `/api/admin/users/`
- 39 admin tests (CRUD, archive with validation, reorder, pricing validation, user toggle, auth)

### Frontend
- `services/admin.js` — complete API client for all 5 admin domains
- `hooks/useAdmin.js` — `useAdminProperties`, `useAdminSections`, `useAdminUnits`, `usePricingRules`, `useAdminUsers`, `useAdminGroups`
- `pages/Administration.jsx` — rebuilt with 5-tab navigation:
  - **Properties** — create/edit/archive table with status badge
  - **Sections** — create/edit/archive with reorder (up/down buttons), property selector
  - **Units** — create/edit with status/capacity/pricing, property+section dropdown filters
  - **Pricing** — effective-dated pricing rules per unit, property→section→unit drill-down, "How Pricing Works" explainer card
  - **Users** — create/edit users with staff/superadmin toggles, activate/deactivate, groups display
- `AdminFormDialog` — reusable modal form component with text/select/textarea/date/number field types
- All 5 tabs have loading skeletons, error states, empty states
- Sidebar "Administration" nav item preserved (already existed)

## Sprint 12 — Receipts & Transaction History (DONE)

### Backend
- `Receipt` model — snapshot of payment + occupant + unit info at time of payment; auto-generated `RCP-YYYYMMDD-NNNN` unique receipt numbers
- `ReceiptService` — auto-generates receipt on every `record_payment` via `_generate_receipt()` (copies student/unit/property info, calculates outstanding balance after payment)
- `ReceiptSerializer` — all receipt fields as read-only; includes payment_id linkage
- `ReceiptViewSet` — `GET /api/payments/receipts/` (paginated list with search by receipt #/occupant/reference, date range filter), `GET /api/payments/receipts/<id>/` (detail), `GET /api/payments/receipts/<id>/pdf/` (PDF download)
- PDF generation via reportlab — branded receipt with KarosL header, occupant/unit info table, amount/balance summary, footer with issue timestamp
- `PaymentSerializer` — added `receipt_id` and `receipt_number` computed fields for cross-linking
- 15 receipt tests (auto-creation, data accuracy, balance calc, list, pagination, search, retrieve, PDF download, auth)

### Frontend
- `services/payments.js` — `receiptsList()`, `receiptGet()`, `receiptPdfUrl()` API methods
- `hooks/usePayments.js` — `useReceipts(params)` and `useReceipt(id)` custom hooks
- `pages/Receipts.jsx` — searchable, filterable, paginated receipts table with direct PDF download links; loading/error/empty states
- `PaymentDetailDialog` — added receipt download link in detail modal
- `Sidebar` — added "Receipts" nav item with document icon between Payments and Reports
- `App.jsx` — added `/receipts` route
- `Payments` page — "View Receipts →" link in page header

## Sprint 11 — Interactive Property Explorer

### Backend
- `PropertyExplorerSerializer` — nested hierarchy: Property → Section → Unit with occupancy data
- `UnitExplorerSerializer` — unit card fields (name, capacity, occupancy count/percentage, active occupants, color status), uses prefetched `active_occupancies` via `to_attr`
- `SectionExplorerSerializer` — section with nested unit cards
- `PropertyDetailSerializer` — property with nested sections (via `Prefetch` for N+1 prevention)
- `PropertyExplorerView` — `GET /api/properties/explorer/` returns full hierarchy tree; supports `?search=` filtering by unit name or occupant name; uses 3-level `Prefetch` with Django ORM for performance
- `UnitDetailView` — `GET /api/units/<id>/detail/` returns unit info, current occupants (with balances via `PaymentService`), occupancy history, quick actions metadata
- `UnitDetailSerializer` — computed fields for current_occupant_count, available_spaces, is_full; `current_occupants` with balance data; `occupancy_history` (last 10)
- 13 explorer tests (auth, hierarchy, inactive filtering, occupancy counts, full-unit status, search by name/occupant, search scoping)

### Frontend
- `services/explorer.js` — `getHierarchy(search)` and `getUnitDetail(unitId)` API methods
- `hooks/useExplorer.js` — `useExplorer(search)` for hierarchy fetching, `useUnitDetail(unitId)` for detail panel
- `components/explorer/PropertyNode.jsx` — collapsible property card with unit count, chevron toggle
- `components/explorer/SectionNode.jsx` — collapsible section with full/total unit badge, 3-column unit grid on expand
- `components/explorer/UnitNode.jsx` — unit card with occupancy bar, color indicators (Green <75% / Yellow ≥75% / Red 100%), capacity/occupied/available stats
- `components/explorer/UnitDetailPanel.jsx` — side panel/modal with unit info (pricing, capacity), current occupants (with balance badges, View/Record Payment links), quick actions (Assign, Record Payment), occupancy history timeline
- `pages/Explorer.jsx` — search bar with debounce, tree view + detail panel layout, empty/no-results states, loading/error handling
- Responsive: Desktop (tree + side panel side-by-side), Tablet/Mobile (stacked + overlay modal)
- Dashboard "View Property Map" button navigates to `/explorer`
- Sidebar "Explorer" nav item added with map icon
- Route `/explorer` in App.jsx
- `Spinner` component for loading states
- 6 explorer frontend tests (loading, property rendering, unit count, empty state, search input, no results)

## Sprint 10 — Payment Management

### Backend
- `PaymentService` — `record_payment` (archived-student check, duplicate-reference check, model validation), `list_payments` (search, property, student, method, date-range filters), `calculate_student_balance` (derived from occupancy charges minus payments), `list_overdue_students`
- `PaymentSerializer` — student_name computed field, reference uniqueness validation
- `PaymentViewSet` — list, retrieve, create, `student_balance` action, `overdue` action
- Payment URLs at `/api/payments/` — list/create, detail, student_balance, overdue
- Balance formula: semester = `Unit.semester_price`, monthly = `Unit.monthly_price × ceil(days/30)`
- 31 payment tests (create, archive-student reject, duplicate reference, negative amount, balance, overdue, list filters, auth)

### Frontend
- `services/payments.js` — API client for payments CRUD, student balance, overdue list
- `hooks/usePayments.js` — `usePayments`, `useStudentBalance`, `useOverdueStudents`, `useStudentPaymentHistory`
- `RecordPaymentDialog` — modal form with occupant name, amount, date, method selector (Cash/Bank Transfer/Card), reference, notes; success/error feedback
- `PaymentDetailDialog` — modal showing full payment receipt (amount, occupant, date, method, reference, notes, timestamp)
- `Payments` page — stat cards (total collected, occupied beds, outstanding count), filterable table (search, method, date range), overdue balances list, payment methods breakdown; loading/error/empty states
- `OccupantDetail` — Payment Summary card (Amount Due / Total Paid / Outstanding) and Payment History table; Record Payment button in actions panel
- `Dashboard` — live recent payments table from API, live outstanding count/total from overdue endpoint, navigate-to-payments quick action

## Sprint 9 — Occupancy Management

### Backend
- `OccupancyService` — assign, checkout, update, list, get, summary methods with business rule enforcement (archived occupants, capacity, duplicate active occupancy)
- `OccupancySerializer` — nested student/unit/property display fields, create/update validation
- `OccupancyViewSet` — list (filterable by student, unit, active), retrieve, create (assign), partial_update, checkout action, summary action
- Occupancy URLs at `/api/occupancy/` — list/create, detail/update, checkout, summary
- Property/Section/Unit list endpoints at `/api/properties/`, `/api/sections/`, `/api/units/` (for assign wizard dropdowns)
- 24 occupancy tests (assign, capacity, double-booking, archived, checkout, history, update, summary, auth)

### Frontend
- `services/occupancy.js` — API client for occupancy CRUD, checkout, summary
- `services/properties.js` — API client for property/section/unit list endpoints
- `hooks/useOccupancy.js` — `useOccupancies`, `useOccupancySummary`, `useActiveOccupancy`, `useOccupancyHistory`
- `AssignOccupancyDialog` — 3-step wizard modal (Property → Section → Unit) with capacity indicators, date/billing-mode inputs
- `OccupantDetail` — real occupancy data: current assignment card (with Check Out), occupancy history table (with status badges), Assign button
- `Dashboard` — live occupancy summary from API replacing mock data; loading skeleton for property cards
- Vite proxy /api kept unchanged

## Sprint 8 — Occupant Management

### Backend
- `national_id` field on Student (unique, blank), migration 0002
- StudentSerializer with email uniqueness, phone format validation, computed `full_name`
- StudentService with list (search, status filter, pagination), get, create, update, archive
- StudentViewSet with 6 endpoints + custom `archive` action
- URLs at `/api/occupants/`

### Frontend
- API client (`services/api.js`) with Token auth, typed methods
- Occupant service, hooks (`useOccupants`, `useOccupant`)
- Occupants list page (search, Active/Archived tabs, paginated table, loading/error/empty states)
- OccupantDetail (profile card, edit/archive, ConfirmDialog)
- OccupantForm (unified create/edit, 6 fields, client validation)
- ConfirmDialog reusable component
- Routes `/occupants`, `/occupants/new`, `/occupants/:id`, `/occupants/:id/edit`

## Sprint 7 — Dashboard

- StatisticCard for occupancy/payments summary
- PropertySummaryCard with progress bar per property
- ActionCard for quick actions grid
- ActivityCard for recent activity feed
- PaymentTable for recent payments
- All cards consume mock data

## Sprint 6 — Application Shell

- MainLayout with sidebar navigation and top header
- Sidebar collapsible on mobile; highlights active route
- Consistent PageContainer, Card, Button components
- Inter font, soft blue primary palette, generous whitespace
