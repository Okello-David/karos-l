# UI/UX Audit: KarosL Frontend

Date: 2026-07-02
Scope: Full React frontend review against `docs/BUG_QUEUE.md` and `docs/CHANGELOG.md` context. No code changes made as part of this audit.

## What is already good

- **Consistent design tokens** — single Tailwind primary palette (`tailwind.config.js:9-21`), Inter font, shared `Button`/`Card` primitives used almost everywhere.
- **Loading/empty/error pattern genuinely followed** across `Occupants.jsx`, `OccupantDetail.jsx`, `Payments.jsx`, `Receipts.jsx`, `Administration.jsx` — including retry buttons and helpful hint text.
- **Toasts + confirm dialogs** wrap destructive/important actions (archive, checkout, payments) — the right pattern for a non-technical user.
- **Property Explorer occupancy visualization is the strongest surface in the app** — `UnitNode.jsx`'s traffic-light badge + progress bar is genuinely clear at a glance and should be the template elsewhere.
- **Real accessibility work**: skip-link, `aria-modal`/`role="dialog"`, focus return on dialog close, `aria-live` toast region, keyboard shortcuts (Ctrl+K, `?`).
- **Occupants tables already collapse responsibly** via `hidden sm:/md:/lg:table-cell` — the right convention, just not applied everywhere (see High-priority).

## Critical UI issues

1. **"Record Payment" in the Explorer unit panel doesn't record a payment.** `UnitDetailPanel.jsx:146-159` — both "View Occupant" and "Record Payment" call the same handler, routing to the occupant profile. Mislabeled on the app's most action-oriented surface.
2. **Sidebar footer shows a hardcoded fake user** (`Sidebar.jsx:144-151`: `"Property Manager" / manager@karosl.com`) while `Topbar.jsx` correctly shows the real logged-in user (matches known BUG-012). Two chrome elements disagreeing about who's logged in reads as broken.
3. **Properties page hardcodes "Active" status** (`Properties.jsx:107`) regardless of `property.is_active` — an archived property still displays Active, directly misleading for placement decisions.

## High-priority improvements

4. **Payments and Receipts tables have zero responsive column-hiding** (`Payments.jsx:180-222`, `Receipts.jsx:103-147` — 7 columns each, bare `overflow-x-auto`), unlike Occupants two files over.
5. **Administration's 6-tab nav has no overflow handling** for narrow screens (`Administration.jsx:1044-1060`).
6. **Administration's data tables also lack responsive column hiding** (e.g. `UnitTab` 7 cols at `Administration.jsx:464-474`, `UsersTab` 6 cols at `:743-751`).
7. **"Properties" and "Property Explorer" are two overlapping, uncross-linked views** of the same hierarchy — genuine "which one do I use?" confusion for a non-technical user.
8. **No direct "Record Payment" entry point on the Payments page itself** (`Payments.jsx:100-111`) — only reachable via an occupant's profile or the (currently broken) Explorer panel, despite being the most frequent daily task.

## Medium-priority improvements

9. Duplicate/inconsistent `formatUGX` implementations (`utils/format.js` vs. local redefinitions in `PaymentTable.jsx`, `UnitDetailPanel.jsx` with different decimal handling).
10. `ActionCard.jsx`/`ActivityCard.jsx` are unused — `Dashboard.jsx` reimplements the same UI inline instead.
11. Dashboard's Recent Payments table always shows "—" for Property (`Dashboard.jsx:22-28`).
12. Icon stroke-width inconsistency: `EmptyState.jsx` uses `strokeWidth={1}` vs. `1.5` elsewhere.
13. `Settings.jsx` is dead code — unreachable (not routed, not in nav) and doesn't match the design system.
14. Explorer's "Assign Occupant"/"View Payments" quick actions lose context, dropping the user back to unfiltered lists.

## Low-priority polish

15. Guided tour positioning — already a known/documented gap (`BUG_QUEUE.md:52`).
16. Breadcrumb falls back to generic "Page" label for unmapped routes.
17. `AssignOccupancyDialog.jsx` uses fixed `grid-cols-2` (no `sm:` prefix) — tight on smallest phone widths.
18. Payments' "Payment Methods" card aggregates only the current page, can silently disagree with "Total Collected" once paginated.

## Recommended design direction

The visual language (soft blue primary, rounded-xl cards, calm neutral grays, traffic-light status colors) is already right for the calm/professional/non-technical goal — don't redesign it. The real gap is **consistency and completeness of patterns already established**, not new visual design: extend the Occupants responsive-table convention everywhere, make Payments a true one-click entry point, consolidate Properties/Explorer, and clean out dead/duplicated code so inconsistencies (like the Sidebar/Topbar user mismatch) stop accumulating.

## Suggested implementation order

1. Critical fixes (low-risk, high trust impact): Sidebar fake user, Properties status bug, Explorer "Record Payment" mislabel.
2. Responsive table pass: Payments, Receipts, all Administration tabs + tab-bar overflow.
3. Add a direct "Record Payment" entry point on the Payments page.
4. Resolve Properties vs. Explorer duplication.
5. Cleanup: dead code (`Settings.jsx`, `ActionCard`/`ActivityCard`), duplicate `formatUGX`, Dashboard property-name gap.
6. Polish: icon stroke-width, breadcrumb fallback, remaining low-priority items.
