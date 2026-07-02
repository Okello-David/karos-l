# Release Plan

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

## Reference: environment used for this verification

- Backend: `python manage.py runserver 0.0.0.0:8000` (SQLite dev database).
- Frontend: `npm run dev` (Vite, port 5173).
- Test account: `demo` / `demo12345` (staff + superuser), left in place for continued manual testing.
- All disposable test data created for this pass (a `QARC`-prefixed property, sections, units, 3 occupants, their occupancies/payments/receipts, and a temporary staff user) was created, exercised, and then deleted afterward. Audit log entries generated during testing and the one backup record created during the Backup workflow check were **not** deleted — audit logs are meant to be an immutable historical record, and the backup is a valid, complete, harmless snapshot.
