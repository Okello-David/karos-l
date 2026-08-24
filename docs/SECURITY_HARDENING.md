# Security Hardening

Security posture reference for KarosL's authorization layer. Complements `docs/ARCHITECTURE_DECISIONS.md`
(the "why" behind each decision) with the concrete "what" — every protected endpoint, its required role, and
what was tested. Started 2026-08-24 during the RBAC hardening sprint.

## Endpoint-to-permission map

| App | Viewset/View | Permission class | Role required | Notes |
|---|---|---|---|---|
| payments | `PaymentViewSet` | `CanRecordPayment` | Property Manager+ | All actions (list/create/retrieve/student_balance/overdue) |
| payments | `ReceiptViewSet` | `IsAuthenticated` | Any authenticated user | Read-only, no write actions exist |
| occupants | `StudentViewSet` | `CanManageOccupants` | Property Manager+ | All actions |
| occupancy | `OccupancyViewSet` | `CanManageOccupancy` | Property Manager+ | Except `summary` — see below |
| occupancy | `OccupancyViewSet.summary` | `IsAuthenticated` (per-action override via `get_permissions()`) | Any authenticated user | Aggregate counts/occupancy-rate/property breakdown only, no per-occupant detail — the Dashboard/Overview page depends on this for every user |
| properties | `PropertyListView`, `PropertyExplorerView` | `IsAuthenticated` | Any authenticated user | Read-only |
| sections | `SectionListView` | `IsAuthenticated` | Any authenticated user | Read-only |
| units | `UnitListView`, `UnitDetailView` | `IsAuthenticated` | Any authenticated user | Read-only |
| dashboard | `DashboardSummaryView` | `IsAuthenticated` | Any authenticated user | Read-only |
| reports | `BaseReportView` (occupancy/financial/occupants) | `IsAuthenticated` | Any authenticated user | Read-only |
| administration | `AdminPropertyViewSet`, `AdminSectionViewSet`, `AdminUnitViewSet`, `PricingRuleViewSet` | `CanManageProperty` | Property Manager+ | All actions |
| administration | `AdminUserViewSet` | `CanManageUsers` | **Super Admin only** | Fixed this sprint — see AD-002. Was `IsPropertyManager`. |
| audit | `AuditLogListView`, `AuditLogDetailView`, `AuditEntityTypesView`, `AuditActionsView` | `IsAuthenticated & CanViewAuditLog` | Super Admin only | Unchanged this sprint — was already `IsSuperAdmin`, renamed for clarity |
| backup | `BackupListCreateView`, `BackupDetailView`, `BackupRestoreView`, `BackupValidateView`, `ExportView` | `IsAuthenticated & CanManageBackups` | Super Admin only | Unchanged this sprint — was already `IsSuperAdmin`, renamed for clarity |

**Read this table alongside `docs/ARCHITECTURE_DECISIONS.md` AD-001**: occupants/occupancy/payments are
scoped to Property Manager for *every* action, including reads — not just writes. This is deliberate, not
an oversight (see AD-001's rationale).

## The finding this sprint fixed (headline)

**`AdminUserViewSet` required only `IsPropertyManager`, and its update path (`AdminUserCreateSerializer`)
has a writable `password` field.** `is_superuser` was already read-only on that serializer, so a Property
Manager could not directly grant themselves superuser status — but they could reset *any* user's password,
including a superuser's, via `PATCH /api/admin/users/<id>/`, then authenticate as that account. This was a
live privilege-escalation path, unrelated to the original `IsAuthenticated | IsPropertyManager` no-op gap
fixed earlier the same day. Full detail: `docs/ARCHITECTURE_DECISIONS.md` AD-002.

**Fixed** by changing `AdminUserViewSet.permission_classes` to `CanManageUsers` (`IsSuperAdmin`). No
serializer changes were needed — `is_superuser` staying read-only there is still correct defense-in-depth
now that only superusers can reach the viewset at all.

## Elevation-prevention and ID-substitution testing

`backend/apps/core/tests.py::AuthorizationMatrixTests` is the consolidated regression suite for this
sprint's two central concerns:

- **A plain authenticated ("Staff") user never gains Property-Manager or Super-Admin-level write access
  merely by being authenticated** — tested directly against occupants, payments, occupancy, and
  administration-property write actions.
- **A real, existing object ID does not bypass a permission check that would otherwise deny access** — a
  Staff user cannot update a real occupant record or archive a real property by supplying its actual ID; a
  Property Manager cannot reset a real superuser's password by supplying that account's real ID (the
  specific AD-002 escalation, tested with a before/after password-hash comparison to prove the password
  genuinely didn't change, not just that the response was a 403).
- Cross-role coverage: unauthenticated, Staff, Property Manager, and Super Administrator are each tested
  against representative endpoints from every tier of the matrix (business writes, admin-property writes,
  user management, audit log, backups).

`backend/apps/administration/tests.py` carries the endpoint-specific regression tests for the `AdminUserViewSet`
fix itself (`test_users_property_manager_forbidden_*`), including one that asserts a targeted deactivation
attempt against a real user ID fails and leaves that user's `is_active` unchanged.

## Object-level protection

No `has_object_permission` checks exist in this codebase, and none were added this sprint. See
`docs/ARCHITECTURE_DECISIONS.md` AD-004 for why: with no property-scoping data model (AD-003), the
class-level `permission_classes` check on each viewset already is the complete authorization policy for
every object of that type — there's no "this object belongs to someone else" boundary to additionally
enforce. If per-property manager scoping is ever built, object-level checks become necessary at that point.

## Known limitations (stated plainly, not hidden)

- **No per-property scoping.** Every Property Manager has equal access to every property. See AD-003 for
  the full rationale — this matches KarosL's actual single-organization, multi-property shape, not an
  oversight, but it does mean the system cannot currently support delegated managers who should only see
  specific properties.
- **"Staff" is not a hard-enforced group.** Read-only endpoints stay `IsAuthenticated` rather than requiring
  explicit "Staff" group membership, specifically to avoid locking out any existing account that isn't
  currently in any group. A `Group(name="Staff")` row exists (auto-created,
  `backend/apps/accounts/apps.py`) but nothing currently requires membership in it.
- **The audit log has near-zero DELETE coverage** (pre-existing, not addressed this sprint) — the
  application is soft-delete-first (archiving, not deleting), so most "removal" actions are logged as
  ARCHIVE. The one real hard-delete path (`PricingRule`) is logged as DELETE. A hard delete performed outside
  the application layer (e.g. direct database access) would not appear in the audit log at all. See
  `docs/runbooks/05-database-corruption.md` (written during the disaster-recovery sprint,
  2026-08-24) for the full implication.
- **The audit log itself is Super-Admin-only** (`CanViewAuditLog`), including for Property Managers. This
  predates this sprint (audit was always `IsAuthenticated & IsSuperAdmin`) — meaning the Dashboard's
  "Recent Activity" panel is empty for every non-superuser, not just Staff. The frontend already handles
  this gracefully (shows "Recent activity is unavailable" rather than erroring) — see
  `frontend/src/pages/Dashboard.jsx`. Not fixed this sprint since it's a pre-existing gap, not a regression,
  and expanding audit-log access is a separate product decision (who should be able to see what happened,
  and does that conflict with audit-log integrity concerns) rather than a permission-class rename.
- **CloudWatch/AWS-level access is out of scope for this document** — see `docs/DISASTER_RECOVERY.md` and
  `docs/PRODUCTION_READINESS_REVIEW.md` for infrastructure-level security posture (SSH/security-group
  scope, RDS network isolation, S3 backup IAM least-privilege, etc.).

## Frontend permission alignment

Backend authorization is authoritative; the frontend changes below are UX-only — they hide actions a user
cannot perform rather than showing them and erroring on click. `frontend/src/utils/permissions.js` reads the
already-returned `is_superuser`/`groups` fields from `authService.getUser()` (populated at login via
`UserSerializer`, no new API field needed).

- **Administration → Users and Audit Log tabs** hidden from non-superusers (`frontend/src/pages/Administration.jsx`).
- **Occupants, Payments, and Administration nav items** hidden from Staff (`frontend/src/components/Sidebar.jsx`)
  — these surfaces require Property Manager for *every* action including reads, so showing the nav item
  would lead to an empty/erroring page, not a degraded-but-usable one.
- **Backup nav item** hidden from non-superusers (same file) — backups require Super Admin.
- **Dashboard quick actions** ("Register Occupant", "Record Payment") and the "View Payments"/"View
  Occupants" shortcut buttons hidden from Staff (`frontend/src/pages/Dashboard.jsx`) — these are the
  specific write/PM-only-read affordances the Dashboard surfaced to every authenticated user before this
  sprint. The "Outstanding Payments" stat card (data itself is Property-Manager-gated) is hidden entirely
  for Staff rather than shown with misleading zeros; "Recent Payments" shows an "unavailable" message for
  Staff, matching the existing pattern already used for "Recent Activity."
