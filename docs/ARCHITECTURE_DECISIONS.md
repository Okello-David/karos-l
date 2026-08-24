# Architecture Decisions

This document records significant, durable architecture decisions and their rationale — the "why," not the
"what" (the code is the source of truth for what exists; `docs/CHANGELOG.md`/`docs/PROJECT_STATE.md` are the
retrospective logs of what changed and when). Started 2026-08-24 with the RBAC hardening sprint; earlier
decisions are captured where they're directly relevant to what's recorded here.

## AD-001: Three-role RBAC model (Super Administrator, Property Manager, Staff)

**Date:** 2026-08-24. **Status:** Adopted.

**Context:** A production-readiness audit (2026-08-20) found `IsAuthenticated | IsPropertyManager` used as a
no-op OR on every business viewset — any authenticated user could create occupants and record payments,
regardless of role. A first pass (same day, 2026-08-24) closed that gap by requiring `IsPropertyManager` on
write-capable endpoints. This sprint formalizes the role model those permission classes actually implement,
and — critically — found and fixed a second, more serious gap in the same area (AD-002).

**Decision:** Three roles, matching what the codebase's existing primitives (Django's `is_superuser` flag and
the "Property Manager" group) already express, plus a third implicit tier for everyone else:

| Role | Basis |
|---|---|
| **Super Administrator** | `request.user.is_superuser` |
| **Property Manager** | Member of the Django "Property Manager" group (or superuser — superusers bypass every group check) |
| **Staff** | Any other authenticated user. Not a hard-enforced group membership — see AD-003. |

**Permission matrix** (what each role can view / create / update / archive):

| Capability | Super Admin | Property Manager | Staff |
|---|---|---|---|
| View properties/sections/units/dashboard/reports/receipts | ✅ | ✅ | ✅ |
| View occupants/occupancy/payments (list/detail) | ✅ | ✅ | ❌ |
| Create/update/archive properties, sections, units, pricing rules | ✅ | ✅ | ❌ |
| Create/update/archive occupants | ✅ | ✅ | ❌ |
| Assign/checkout occupancy | ✅ | ✅ | ❌ |
| Record payments | ✅ | ✅ | ❌ |
| View occupancy summary (aggregate dashboard stats) | ✅ | ✅ | ✅ |
| **Manage user accounts** (create/update/deactivate/reset password) | ✅ | ❌ | ❌ |
| **View the audit log** | ✅ | ❌ | ❌ |
| **Manage backups / export data** | ✅ | ❌ | ❌ |

**Rationale for the Staff-cannot-read-occupants/occupancy/payments row:** this predates this sprint (decided
2026-08-24, earlier the same day, when the original permission gap was fixed) — occupants, occupancy, and
payments are each a single DRF `ViewSet` bundling list/retrieve alongside create/update, with one
`permission_classes` covering every action. The decision at the time was that this entire surface (not just
its write actions) should require Property Manager — this document makes that decision explicit and
official rather than leaving it implicit in the code. One deliberate carve-out: `OccupancyViewSet.summary`
(aggregate counts/occupancy-rate/property breakdown, no per-occupant detail) is split out via
`get_permissions()` to stay `IsAuthenticated`, since the Dashboard/Overview page — every user's landing
page — depends on it.

**Implementation:** named, per-capability permission classes in `backend/apps/core/permissions.py`
(`CanManageProperty`, `CanManageOccupants`, `CanManageOccupancy`, `CanRecordPayment`, `CanManageUsers`,
`CanViewAuditLog`, `CanManageBackups`) — thin subclasses of `IsPropertyManager`/`IsSuperAdmin`, no new
authorization logic. Each viewset's `permission_classes` now states its actual intent instead of a generic
role name repeated at every call site. See `docs/SECURITY_HARDENING.md` for the full endpoint-by-endpoint
mapping.

## AD-002: User-account management requires Super Administrator, not Property Manager

**Date:** 2026-08-24. **Status:** Adopted (critical fix).

**Context:** While auditing the current permission state for AD-001, `AdminUserViewSet`
(`backend/apps/administration/views.py`) was found to require only `IsPropertyManager` for full user-account
management — create, update, deactivate, list. Its update path uses `AdminUserCreateSerializer`, which has a
writable `password` field. `is_superuser` is read-only on that serializer, so a Property Manager could not
flip that flag directly — **but they could reset any user's password, including a superuser's, via
`PATCH /api/admin/users/<id>/`, then log in as that account.** This is a genuine privilege-escalation path
that was live in production, independent of (and not fixed by) the original permission-gap fix.

**Decision:** `AdminUserViewSet` requires `CanManageUsers` (`IsSuperAdmin`). A Property Manager must never be
able to reach account management for exactly this reason — any endpoint that can modify another account's
password or group membership is equivalent in power to a superuser-gated action, and must be gated the same
way, regardless of what else that endpoint superficially looks like (in this case, "user administration"
looked adjacent to "property administration," which is why it was grouped under the same `IsPropertyManager`
check in the original `apps/administration` app design — a understandable but incorrect grouping).

**Regression tests:** `backend/apps/administration/tests.py` (`test_users_property_manager_forbidden_*`) and
`backend/apps/core/tests.py` (`AuthorizationMatrixTests.test_property_manager_cannot_reset_real_users_password_by_id`)
assert a Property Manager gets 403 on every user-management action, including the specific password-reset
path, and that the target account's password is provably unchanged afterward.

## AD-003: Property-level scoping — documented limitation, not built this sprint

**Date:** 2026-08-24. **Status:** Deferred, documented.

**Context:** KarosL supports multiple properties. The brief for this sprint asked whether Property Managers
can be scoped to specific assigned properties, so that a manager of Property A cannot reach Property B's
records by substituting an object ID.

**Finding:** No `User`↔`Property` relationship exists anywhere in the data model — no FK, no M2M, checked
models and migrations directly. "Property Manager" is a single global Django group; every member has equal
access to every property, by design (or, more precisely, by omission — the concept of per-property
assignment was never built).

**Decision: do not build a new assignment data model this sprint.** Reasoning:
- KarosL's actual shape is a **single organization operating multiple properties it owns** — not multi-tenant
  SaaS with mutually-untrusted separate customers. Every Property Manager today is trusted org-wide. There is
  currently no evidence (no client request, no incident) that per-property delegation is an actual product
  need rather than a hypothetical one.
- Building it properly (a join table/M2M, a migration, `get_queryset` filtering across every business
  viewset, UI for assigning managers to properties, and a decision about what happens to *unassigned*
  managers — do they see nothing, or everything?) is a substantial new architecture piece, not a permission
  tweak. Building it speculatively risks exactly the kind of unrequested scope this sprint's brief explicitly
  warned against ("do not invent a large new tenancy architecture").
- This mirrors how the original permission gap itself was handled: flag clearly, get a product decision,
  don't unilaterally build ahead of an actual requirement.

**Consequence, stated plainly:** the "never allow ID substitution to leak another property's records"
requirement in this sprint's brief does not currently apply in the way it would for a multi-tenant system,
because there is no "another property's records" boundary to cross — every Property Manager is equally
authorized to every property's data today. This is not a vulnerability being overlooked; it's the correct
description of an intentionally flat, single-organization trust model. If the client ever wants delegated,
scoped property managers, that's a product decision requiring new data modeling — flagged here for exactly
that future conversation, not silently absent from this document.

## AD-004: Object-level (`has_object_permission`) checks — none added, none currently needed

**Date:** 2026-08-24. **Status:** Documented, no action taken.

**Context:** Investigated whether any object-level permission checks exist in the codebase, and whether any
should be added as part of this sprint's ID-substitution hardening.

**Finding:** Zero `has_object_permission` overrides exist anywhere. Every `retrieve`/`update`/`archive`/
`destroy` across every viewset fetches purely by `pk` via service-layer helpers, with no per-user filtering.

**Decision:** given AD-003 (no ownership/scoping boundary exists between properties, by design), there is
currently no meaningful *additional* object-level check to add on top of the class-level
`permission_classes` checks. The class-level check — "is this user a Property Manager at all?" — already IS
the complete authorization policy for every object of a given type, because every Property Manager is
equally authorized to every object of that type. The one real object-level-adjacent gap this sprint found
and fixed was AD-002 (wrong *class-level* role on `AdminUserViewSet`, not a missing object-level check). If
AD-003 is ever revisited (per-property scoping gets built), object-level checks become necessary at that
point — noted here so that connection isn't lost.
