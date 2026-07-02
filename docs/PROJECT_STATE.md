# Project State

Snapshot as of 2026-07-02, after the Release Candidate Verification Pass (see `docs/RELEASE_PLAN.md` and `docs/BUG_QUEUE.md`).

## Where things stand

KarosL is a Django REST Framework + React (Vite) accommodation-management platform, currently in Release Candidate stabilization. Core domain (properties → sections → units, occupants, occupancy, payments/receipts, administration, audit log, backup/export) is implemented and has been verified end-to-end against a live running instance.

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

- **Reports** page is a placeholder ("Coming Soon" on Occupancy/Financial/Student report cards) — pre-existing, already documented in `BUG_QUEUE.md`'s Deferred section from an earlier pass.
- **Move occupant to another unit** is not implemented (no route, no service method). Present in `docs/WORKFLOWS.md`'s aspirational spec but never built.
- Archived properties can still receive new sections/units via Administration (no guard) — logged as a deferred Medium bug (see `BUG_QUEUE.md`).
- Archived properties are excluded entirely from the Property Explorer / Properties list API (`PropertyExplorerView` filters `is_active=True`) rather than shown with an Archived badge — a pre-existing, previously-documented design gap.
- `Backup Restore` was verified by code review only, not executed live, since it is a genuine irreversible full-data overwrite with no isolated/disposable environment available in this session.

## Fixed this pass

- Full-name search (occupants and payments) returning zero results — see BUG-026, BUG-027.
- Dashboard's own "Record Payment" quick action dead-ending through the unrelated Occupants list — see BUG-028.

## Test/build baseline (end of this pass)

- Backend: full Django test suite — **234/234 passing**.
- Frontend: `npm run build` clean, `npm run lint` shows only pre-existing, unrelated warnings, `npm test` **45/45 passing**.

## Environment notes for whoever picks this up next

- Two onboarding overlays exist and stack: `WelcomeScreen` (dismissed via "Skip tour") automatically triggers `GuidedTour` immediately after, which needs its own dismissal (Escape key works, or click through its steps). Both use `localStorage` keys (`karos_welcome_dismissed`, `karos_tour_dismissed`) that persist once dismissed in a given browser profile.
- A `demo` / `demo12345` staff+superuser account exists in the dev database for manual testing (created in a prior session at the user's request, not deleted).
