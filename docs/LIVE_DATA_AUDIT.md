# Live Data Audit — KarosL Staging/Live Pilot

**Date:** 2026-08-24. **Method:** the actual latest S3 backup (`database/karosl_db_2026-08-24_135700.sql.gz`,
taken automatically as part of that day's operational-cleanup deploy) restored into a disposable local
database using `scripts/restore-from-s3.sh` — the same proven, safe pattern used during the disaster-recovery
sprint. Read-only inspection; the disposable database was dropped immediately after. **This environment has
no write path to the live database** (no SSH to the instance, no direct RDS access — private by design), so
every finding below is real evidence from a real backup, but no cleanup was executed against the live
system — only documented, per this task's own instruction not to delete automatically.

## Summary

| Category | Count | Action |
|---|---|---|
| Real/demo (intentional — the current, correct state) | 2 properties, 16 occupants, 13 payments/receipts | None — keep |
| Test (confirmed, already archived, clearly labeled) | 3 properties, 5 sections, 3 units, 3 occupants, 3 payments, 3 receipts | Recommended for removal (below) — not executed |
| Unknown / requires manual confirmation | 0 | — |
| Real production tenant data | 0 | Client has not yet onboarded real tenants (matches project context — she is still reviewing) |
| User accounts | 1 (`karosadmin`, superuser) | No test/demo accounts found |

## Real / Demo data — classify as "Real," keep as-is

This is **not** test data that accidentally leaked into the live system — it's the deliberate demo dataset
seeded via `manage.py seed_demo_data` (2026-08-01) specifically so the client can review the app with
realistic, uneven occupancy data (the whole point of the seed command, per its own design — flat/empty data
shows nothing useful in Property Explorer's traffic-light view). Removing or flagging this would be a
mistake; it's the intended current state of a review-stage deployment, not production tenant data yet.

| Property | Code | Status |
|---|---|---|
| Kikoni Heights | KIK | Active |
| Wandegeya Court | WDG | Active |

16 occupants (Aisha Nakato through Patricia Nalwoga, `STU-2026-001` through `-016`), 13 payments/receipts
against 13 of them (3 have no payment yet — deliberate, for demonstrating outstanding-balance UI), all
created `2026-08-01 18:05:28` in a single seed transaction (timestamps are seconds apart, confirming a
script run, not organic data entry).

## Test data — confirmed, already archived, recommended for removal

All records below are **already archived** (`is_active=false`) — invisible in the normal UI (Property
Explorer and the Properties list both filter to active-only) — and unambiguously labeled `AUDIT-TEST` or
`RDS-MIGRATION-TEST-DELETE-ME` in their own names, created during three separate prior audit/migration
sessions. Classified **Test**, not **Unknown**, because the labeling is explicit and self-describing — no
manual confirmation needed to know what these are.

| Property | Code | Created | Source pass |
|---|---|---|---|
| `AUDIT-TEST Property` | AUD | 2026-08-19 10:38 | Live smoke test during the CloudWatch/monitoring pass |
| `AUDIT-TEST Property IP` | ATI | 2026-08-19 13:32 | Bare-IP HTTPS certificate verification pass |
| `RDS-MIGRATION-TEST-DELETE-ME` | RDSTST | 2026-08-20 09:33 | RDS cutover verification pass |

Each has one section, one unit, one occupant (also named `AUDIT-TEST ...`), one occupancy (closed same-day,
`start_date = end_date`), one UGX 1,000 payment, and one receipt — a complete, self-contained,
already-closed test chain per pass, exactly matching this project's own established convention of labeling
throwaway verification data `AUDIT-TEST`/`DELETE-ME` and archiving it immediately after use (see
`docs/PRODUCTION_READINESS_REVIEW.md`'s own live-smoke-test section for the same pattern).

Full record inventory (all confirmed via direct query against the restored backup):
- **Properties**: id 6 (AUD), id 7 (ATI), id 8 (RDSTST)
- **Sections**: id 7 (`AUDIT-TEST Section`, under AUD), id 8 (`AUDIT-TEST Section IP`, under ATI), plus one
  under RDSTST
- **Units**: id 16 (`AUDIT-101`), id 17 (`AUDIT-IP-101`), plus one (`A-102`) under RDSTST's section
- **Occupants**: id 23 (`AUDIT-TEST Occupant`), id 24 (`AUDIT-TEST Occupant IP`), id 25 (`AUDIT-TEST
  DELETE-ME`)
- **Occupancies**: id 19, 20, 21 — all closed same-day they were created
- **Payments**: id 17, 18, 19 — UGX 1,000 each
- **Receipts**: 3, matching the payments above

## Recommended cleanup (documented only — not executed)

Since these are already archived and invisible in the app, there is no urgency, but for a clean v1.0
database, whoever has direct database access to the live instance (this environment does not) can remove
them with a single transaction, ordered to respect foreign-key `RESTRICT` constraints (payments/receipts →
occupancy → occupant/unit → section → property):

```sql
BEGIN;
DELETE FROM payments_receipt WHERE student_name LIKE 'AUDIT-TEST%';
DELETE FROM payments_payment WHERE id IN (17, 18, 19);
DELETE FROM occupancy_occupancy WHERE id IN (19, 20, 21);
DELETE FROM occupants_student WHERE id IN (23, 24, 25);
DELETE FROM units_unit WHERE name IN ('AUDIT-101', 'AUDIT-IP-101', 'A-102');
DELETE FROM sections_section WHERE name LIKE 'AUDIT-TEST%';
DELETE FROM properties_property WHERE code IN ('AUD', 'ATI', 'RDSTST');
COMMIT;
```

**Before running this against the live database**: take a fresh `backup-to-s3.sh` snapshot first (standard
practice, cheap, already automated on every deploy), and verify the exact IDs above still match — this
audit is a point-in-time snapshot from the 2026-08-24 13:57 UTC backup; if new test data has been created
since, re-run the same restore-and-inspect procedure rather than trusting these IDs blindly. This is real
data deletion (hard delete, not archive) — deliberate, supervised, not something to automate.

## Not found

No unlabeled, ambiguous, or placeholder-looking records were found — no `test@test.com`, `foo`/`bar`,
`asdf`, sequential fake names, or similar patterns outside the two categories above. No demo/test user
accounts beyond the single real `karosadmin` superuser. No orphaned or partially-written records (every
test chain above is complete and internally consistent — payment ↔ receipt ↔ occupancy ↔ occupant, no
dangling references).
