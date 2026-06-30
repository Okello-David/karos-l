# KarosL Bug Queue

This document is the official bug tracker for KarosL during the Release Candidate (RC) phase. All bugs discovered during testing — whether by developers, QA, or end users — must be recorded here before any fix is applied. No issue shall be resolved without first being documented in this queue.

Every issue follows a defined lifecycle from discovery through verification and closure. This ensures traceability, prioritisation, and a clear record of the system's stability over time.

---

## Severity Levels

| Level | Label | Description |
|---|---|---|
| 🔴 | **Critical** | Prevents the application from functioning. Data loss. Security vulnerabilities. Authentication failures. |
| 🟠 | **High** | Major functionality broken. Serious UI or layout defects that block workflows. Incorrect financial calculations. |
| 🟡 | **Medium** | Workflow inconvenience. Minor UI inconsistencies that do not block core tasks. Validation gaps. |
| 🟢 | **Low** | Cosmetic issues. Minor wording or alignment problems. Nice-to-have improvements. |

---

## Status Workflow

```
New → Confirmed → Assigned → In Progress → Fixed → Verified → Closed
```

| Stage | Description |
|---|---|
| **New** | Bug has been reported and entered into the queue. No investigation has taken place. |
| **Confirmed** | A developer or QA has reproduced the bug and verified it is a genuine issue. |
| **Assigned** | A developer has been assigned to investigate and fix the bug. |
| **In Progress** | Work on the fix is actively underway. |
| **Fixed** | A fix has been implemented and committed. Awaiting verification. |
| **Verified** | QA has confirmed the fix resolves the issue in a test environment. |
| **Closed** | The fix has been deployed to production and the issue is fully resolved. |

---

## Bug Report Template

```
### BUG-XXX

**Title:**

**Severity:**

**Status:**

**Module:**

**Reported By:**

**Assigned To:**

**Date Reported:**

---

**Description:**



**Steps to Reproduce:**

1.
2.
3.

**Expected Behaviour:**



**Actual Behaviour:**



**Possible Cause:**



**Resolution:**



**Verification Notes:**



---
```

---

## Open Bugs

### BUG-002

**Title:** Frontend authentication pipeline is incomplete — no login page, token never stored

**Severity:** 🔴 Critical

**Status:** Fixed

**Module:** Frontend — Authentication

**Reported By:** QA

**Assigned To:** Engineering

**Date Reported:** 2026-06-28

---

**Description:**

After logging in successfully (via DRF browsable API at port 8000), all protected pages return `"Authentication credentials were not provided."` The frontend SPA at port 5173 cannot authenticate because:

1. No login page exists — the user cannot authenticate through the UI.
2. No AuthContext or auth state management exists — the application has no knowledge of the current user.
3. No frontend code ever writes the `auth_token` to `localStorage` — the API client reads from a key that is never populated.
4. Session cookies set by the DRF browsable API on port 8000 are not shared with port 5173, so SessionAuthentication also fails.
5. All routes are publicly accessible — there is no route protection.

**Steps to Reproduce:**

1. Start the application (Django on port 8000, Vite on port 5173).
2. Navigate to `http://localhost:8000/api/auth/login/` in a browser.
3. Log in via the DRF browsable API form.
4. Navigate to `http://localhost:5173/`.
5. Observe that the page appears blank or shows a loading spinner, and all API calls fail with 401.

**Expected Behaviour:**

- A login page should be available at `/login` within the SPA.
- Submitting valid credentials should call `POST /api/auth/login/`, store the returned token in `localStorage`, and redirect to the dashboard.
- All protected routes should check for an authenticated user and redirect to `/login` if unauthenticated.
- The sidebar and topbar should display the real authenticated user's name and initials.
- A "Sign out" button should call `POST /api/auth/logout/`, clear the token, and redirect to `/login`.

**Actual Behaviour:**

- No login page exists.
- The `AuthContext` is absent — no user state is tracked.
- The `api.js` client reads `localStorage.auth_token`, but nothing in the frontend ever writes to it.
- The sidebar and topbar display hardcoded "Property Manager" / "manager@karosl.com" regardless of the actual user.

**Possible Cause:**

The frontend authentication system was never implemented. The project has a complete backend auth system (`TokenAuthentication`, login/logout/me endpoints, permission classes) but no frontend integration to consume it.

**Resolution:**

Created the full frontend authentication pipeline:

| File | Change |
|---|---|
| `src/context/AuthContext.jsx` | **New.** `AuthProvider` with `useAuth()` hook exposing `{ user, loading, login, logout }`. On mount, checks `localStorage` for an existing token and validates it via `GET /api/auth/me/`. |
| `src/pages/Login.jsx` | **New.** Login form page at `/login` with username/password fields, error handling, and submit that calls `POST /api/auth/login/` via the context. |
| `src/App.jsx` | **Rewritten.** Wrapped in `AuthProvider`. Added `ProtectedRoute` component that redirects to `/login` when unauthenticated. Added `/login` route outside the protected layout. All other routes are wrapped in `ProtectedRoute`. |
| `src/components/Sidebar.jsx` | **Updated.** Uses `useAuth()` for real user data (initials, display name, email). Added "Sign out" button with icon. |
| `src/components/Topbar.jsx` | **Updated.** Uses `useAuth()` for real display name and initials instead of hardcoded "Property Manager" / "PM". |

**Verification Notes:**

- Login flow tested via curl against both port 8000 and port 5173 (Vite proxy). Returns `{ token, user }` correctly.
- Protected endpoint (`GET /api/occupants/`) returns 200 with token, 401 without.
- Logout deletes the token; subsequent requests with the same token return 401.
- Build passes (411 KB JS, 31 KB CSS).
- All 36 frontend tests pass across 8 test files.
- The SPA server at port 5173 correctly serves the login page and protects all authenticated routes.

---

### BUG-006

**Title:** CardSkeleton is not defined — occupant detail page crashes

**Severity:** 🔴 Critical

**Status:** Fixed

**Module:** Frontend — Occupant Detail

**Reported By:** QA

**Assigned To:** Engineering

**Date Reported:** 2026-06-29

---

**Description:**

Navigating to an occupant detail page (e.g., from Payments → selecting an occupant) crashes the application with "Something went wrong". The underlying error is `CardSkeleton is not defined`.

**Steps to Reproduce:**

1. Log in and navigate to the Occupants page.
2. Click any occupant to view their detail page.
3. Observe the crash — "Something went wrong" is displayed.

**Expected Behaviour:**

The occupant detail page should load. The Payment Summary card should show skeleton placeholders while the balance is loading.

**Actual Behaviour:**

The page crashes with a runtime `ReferenceError: CardSkeleton is not defined`. The error occurs because `CardSkeleton` is rendered in the Payment Summary loading state but was never imported.

**Possible Cause:**

`OccupantDetail.jsx` imports `{ Skeleton, TableSkeleton }` from `../components/Skeleton` but omits `CardSkeleton`, which is used on line 185.

**Resolution:**

| File | Change |
|---|---|
| `frontend/src/pages/OccupantDetail.jsx:7` | Added `CardSkeleton` to the import: `import { Skeleton, TableSkeleton, CardSkeleton } from '../components/Skeleton'` |

**Verification Notes:**

- Verified import line 7 now includes `CardSkeleton`.
- All 36 frontend tests pass (including Skeleton test suite that tests `CardSkeleton` rendering).
- No other files affected — confirmed by full project scan.

---

---

## Closed Bugs

*No closed bugs to display.*

---

## Testing Checklist

### Authentication
- [ ] Login with valid credentials succeeds and returns a token.
- [ ] Login with invalid credentials returns appropriate error.
- [ ] Logout invalidates the current token.
- [ ] Protected endpoints reject unauthenticated requests (401).
- [ ] Token expiry and refresh behaviour (if applicable).
- [ ] Super Admin access grants full system visibility.
- [ ] Property Manager access is restricted to assigned modules.
- [ ] Staff access enforces read-only limitations.

### Dashboard
- [ ] Summary statistics load correctly (occupied beds, total capacity, available spaces).
- [ ] Occupancy summary matches data in Occupancy module.
- [ ] Recent payments table reflects latest recorded payments.
- [ ] Overdue count and total match overdue query results.
- [ ] Quick action buttons navigate to the correct pages.
- [ ] Recent activity feed displays real audit log entries.
- [ ] Loading states render while data is being fetched.
- [ ] Empty states render when no data exists.

### Occupants
- [ ] Occupant list loads with correct pagination.
- [ ] Search filters results by name, email, or student ID.
- [ ] Status tabs (All / Active / Archived) filter correctly.
- [ ] Create occupant form validates required fields.
- [ ] Duplicate email or student ID is rejected.
- [ ] Edit occupant form pre-populates with existing data.
- [ ] Archive occupant marks the record and removes from active views.
- [ ] Occupant detail page shows profile, payments, and occupancy history.
- [ ] Empty state shown when no occupants match filters.

### Accommodation (Occupancy)
- [ ] Assign occupancy wizard loads properties, sections, and units.
- [ ] Unit capacity is enforced — full units cannot receive new assignments.
- [ ] Archived or already-assigned occupants cannot be assigned.
- [ ] Checkout successfully ends an active occupancy.
- [ ] Billing mode selection (semester / monthly) is persisted.
- [ ] Agreed price snapshot is captured at assignment time.
- [ ] Occupancy history for a student shows all past assignments.
- [ ] Active occupancy is clearly indicated on the occupant detail page.

### Payments
- [ ] Record payment form validates all required fields.
- [ ] Negative amounts and zero amounts are rejected.
- [ ] Duplicate reference numbers are rejected.
- [ ] Payment method options (Cash / Bank Transfer / Card) are selectable.
- [ ] Payment date defaults to today and can be changed.
- [ ] Student balance calculation is accurate (charges − payments).
- [ ] Overdue students list matches calculated balances.
- [ ] Payment detail dialog shows full receipt information.
- [ ] Payment list supports search, date range, and method filters.

### Receipts
- [ ] Receipt is auto-generated when a payment is recorded.
- [ ] Receipt number follows the `RCP-YYYYMMDD-NNNN` format.
- [ ] Receipt list is paginated and searchable.
- [ ] Receipt snapshot includes correct occupant, unit, and amount data.
- [ ] PDF download produces a valid, readable document.
- [ ] Receipt page shows correct balance after payment.
- [ ] Link from payment detail to receipt works correctly.

### Property Explorer
- [ ] Property tree loads with all properties, sections, and units.
- [ ] Unit occupancy indicators (Green / Yellow / Red) reflect live data.
- [ ] Search filters units by name and occupant name.
- [ ] Unit detail panel shows correct pricing, occupants, and history.
- [ ] Quick actions (Assign, Record Payment) navigate correctly.
- [ ] Responsive layout switches between panel and modal views.

### Reports
- [ ] Report cards display with correct icons and descriptions.
- [ ] "Coming Soon" buttons are disabled and clearly labelled.
- [ ] Export link navigates to the Backup & Export page.

### Administration
- [ ] Properties tab: CRUD operations work with validation.
- [ ] Properties tab: archive blocks if active sections exist.
- [ ] Sections tab: CRUD operations work with property filter.
- [ ] Sections tab: reorder buttons update order correctly.
- [ ] Units tab: CRUD operations work with property and section filters.
- [ ] Units tab: status changes (active / maintenance / archived) are persisted.
- [ ] Pricing tab: rules can be added, edited, and deleted per unit.
- [ ] Pricing tab: effective-date changes do not alter existing occupancies.
- [ ] Users tab: create, edit, and toggle active status work.
- [ ] Users tab: role selection (Staff / Property Manager) is enforced.
- [ ] Audit Log tab: filters (entity, action, date range) work correctly.
- [ ] Audit Log tab: timeline and detail views display accurate data.

### Backup & Restore
- [ ] Backup creation completes successfully and produces a JSON file.
- [ ] Backup list shows all created backups with correct metadata.
- [ ] Backup validation reports file integrity.
- [ ] Restore overwrites existing data with backed-up data (transactional).
- [ ] Export produces CSV and XLSX files with correct content.
- [ ] Export supports all entity types (occupants, occupancies, payments, receipts).
- [ ] Restore wizard shows appropriate warnings before proceeding.

### Responsive Design
- [ ] Desktop (≥ 1024px): sidebar is visible, content fills remaining width.
- [ ] Tablet (768px – 1023px): sidebar collapses, hamburger menu works.
- [ ] Mobile (< 768px): sidebar overlays as a slide-in panel.
- [ ] Tables scroll horizontally on narrow viewports.
- [ ] Forms are usable on all screen sizes.
- [ ] Dialog modals are centred and scrollable on small screens.

### Accessibility
- [ ] Skip-to-content link is visible on keyboard focus.
- [ ] All form inputs have associated labels (`<label>` or `aria-label`).
- [ ] Interactive elements are keyboard-navigable.
- [ ] Colour is not the sole means of conveying information.
- [ ] ARIA attributes are used where native semantics are insufficient.
- [ ] Focus management works correctly after dialog open and close.

### Performance
- [ ] Page load completes within acceptable time on a representative dataset.
- [ ] Paginated lists return results within reasonable response time.
- [ ] Search queries complete without noticeable delay.
- [ ] Asset bundles are within expected size budgets.
- [ ] No excessive re-renders or console warnings in development.

### Security
- [ ] Authentication is required for all API endpoints except login.
- [ ] Token authentication prevents session hijacking.
- [ ] Authorization checks enforce role-based access.
- [ ] Security headers are set (Content-Type, XSS, Frame options).
- [ ] Rate limiting is applied to login and API endpoints.
- [ ] Error responses do not leak sensitive information.
- [ ] Production settings disable debug mode and browsable API.

---

## Release Readiness Criteria

KarosL is considered ready for production deployment when **all** of the following conditions are met:

- [ ] No **Critical** severity bugs remain open.
- [ ] No **High** severity bugs remain open.
- [ ] All fixed bugs have been **Verified** by QA.
- [ ] All core workflows (Login, Occupants, Payments, Receipts, Backup) have passed the testing checklist.
- [ ] Documentation is up to date and reflects the current state of the system.
- [ ] Backup creation and restore have been verified end-to-end.
- [ ] Authentication and authorisation have been fully tested across all roles.
- [ ] The application builds without errors in production mode.
- [ ] Database migrations run cleanly on a fresh database.

---

## Future Improvements

*This section captures enhancement ideas that are not bugs but may be prioritised for future releases.*

- **Bulk occupant import** — Upload a CSV or spreadsheet to create multiple occupants in one operation.
- **Email notifications** — Send payment reminders and receipt notifications to occupants.
- **Recurring payments** — Support scheduled monthly or semester-based payment auto-generation.
- **Advanced reporting** — Visual charts for occupancy trends, revenue over time, and unit utilisation.
- **Multi-property dashboard** — Aggregate statistics across all properties with drill-down.
- **Dark mode** — Theme toggle for reduced eye strain in low-light environments.
- **Audit log export** — Download audit trail as CSV for external compliance review.
- **User activity sessions** — Track login/logout times and active sessions per user.
- **Unit maintenance scheduling** — Calendar view for tracking maintenance and inspection dates.
- **Localisation** — Support for additional languages and regional date/number formats.
