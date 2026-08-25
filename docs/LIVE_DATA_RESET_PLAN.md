# Live Data Reset Plan — KarosL Go-Live

**Status: PROPOSAL ONLY. RESET NOT EXECUTED — awaiting approval.**

**Date prepared:** 2026-08-25. **Method:** desk audit — no live database connection was made or attempted (this environment has no SSH/RDS access). Findings are drawn from `docs/LIVE_DATA_AUDIT.md` (2026-08-24, the most recent hard evidence of live DB contents — produced by restoring the actual latest S3 backup into a disposable database and inspecting it directly), cross-checked against the Django model/FK definitions in `backend/apps/*/models.py`, and against `docs/RELEASE_PLAN.md` / `docs/BUG_QUEUE.md` for historical test-data conventions. No commit exists in this repository after 2026-08-24 (`git log` — latest is `21e0af3`, same day as the audit), so nothing has changed the live database's contents since that audit was taken.

A tested tool already exists to execute this reset once approved: `backend/apps/core/management/commands/reset_live_data.py` (classify-then-delete, `--dry-run`/`--confirm`, 6 passing tests in `backend/apps/core/tests_reset_live_data.py`). This report is the human-reviewable proposal that must be approved — and re-verified live via that tool's `--dry-run` mode — before `--confirm` is ever run.

---

## 0. A claim checked specifically for this report: "QARC"-prefixed data

The task brief that prompted this report named `QARC`-prefixed records as an example test indicator. Checked directly: `QARC`-prefixed data is real, but it traces only to a single Release Candidate verification pass on **2026-07-02**, run against the **local SQLite dev database** — never the live/staging RDS instance (`docs/RELEASE_PLAN.md:647`: "a `QARC`-prefixed property, sections, units, 3 occupants, their occupancies/payments/receipts, and a temporary staff user"; `docs/BUG_QUEUE.md:80,83`). Two other historical prefixes were checked the same way: `KG1`/`SMK1` and a `Verify Tester` occupant, both flagged in `docs/RELEASE_PLAN.md` as staging leftovers from passes on 2026-07-31/08-01, both stated as removed via `manage.py seed_demo_data --reset` on 2026-08-01 — before, and consistent with, the 2026-08-24 audit finding no such records.

**Gap worth noting**: `reset_live_data.py`'s classification pattern (`AUDIT-TEST|RDS-MIGRATION-TEST|DELETE-ME`) does not match `QARC` or `KG1`/`SMK1`. This is safe by construction, not a bug — if either pattern were ever found live, the tool would classify those rows `UNKNOWN` and refuse to delete them without an explicit `--allow-unknown` override, rather than guessing. It's flagged here so a human reviewing the live `--dry-run` output knows what an unexpected `UNKNOWN` row named that way would mean.

---

## 1. Current record counts

As of the 2026-08-24 backup-restore audit (**one day old — must be re-confirmed live before backup/deletion**, via `reset_live_data --dry-run`):

| Model | Total | Notes |
|---|---|---|
| Property | 5 | 2 demo (`KIK`, `WDG`) + 3 archived test (`AUD`, `ATI`, `RDSTST`) |
| Section | 6 | 3 demo + 3 test — **see discrepancy note below** |
| Unit | 14 | 11 demo + 3 test |
| PricingRule | 0 (assumed) | `seed_demo_data` sets `Unit.semester_price`/`monthly_price` directly, never creates `PricingRule` rows; not independently counted in the 2026-08-24 audit — **confirm via live dry-run, do not treat as verified** |
| Student (Occupants) | 19 | 16 demo + 3 test |
| Occupancy | 17 | 14 demo (2 of the 16 demo occupants are deliberately unassigned, per `seed_demo_data`'s design) + 3 test |
| Payment | 16 | 13 demo + 3 test |
| Receipt | 16 | 13 demo + 3 test |
| User | 1 | `karosadmin` (superuser) — no demo/test accounts on live |
| AuditLog | not counted | Out of scope for the 2026-08-24 backup-restore audit; irrelevant to the reset decision since it is never touched (§8) |
| Backup (metadata) | n/a | Operational record of backup runs, not business data — explicitly out of scope of this reset |

**Discrepancy flagged, not silently resolved**: `docs/LIVE_DATA_AUDIT.md`'s own summary table states "3 properties, **5 sections**, 3 units..." for the test group, while its detailed per-record inventory in the same document lists only 3 test sections (one under each of `AUD`, `ATI`, `RDSTST`). The section counts above use the detailed list (3 test + 3 demo = 6 total); the live `--dry-run` re-audit should resolve which figure is correct before execution.

## 2. Records classified TEST

All already archived (`is_active=false`) and unambiguously named, created during three separate prior verification/migration passes directly against the live system:

| Property | Code | ID | Created | Pass |
|---|---|---|---|---|
| `AUDIT-TEST Property` | AUD | 6 | 2026-08-19 10:38 | CloudWatch/monitoring live smoke test |
| `AUDIT-TEST Property IP` | ATI | 7 | 2026-08-19 13:32 | Bare-IP HTTPS certificate verification |
| `RDS-MIGRATION-TEST-DELETE-ME` | RDSTST | 8 | 2026-08-20 09:33 | RDS cutover verification |

Each has one section, one unit, one occupant (also `AUDIT-TEST`-named), one occupancy (closed same-day it was opened), one UGX 1,000 payment, and one matching receipt. Classified TEST on two independent signals together (name pattern **and** archived status) — never on name alone.

## 3. Records classified REAL / DEMO

`Kikoni Heights` (KIK) and `Wandegeya Court` (WDG), and everything under them: 3 sections, 11 units, 16 occupants (`Aisha Nakato` … `Patricia Nalwoga`, IDs `STU-2026-001`–`016`, emails `*@example.com`), 13 payments/receipts. This is the deliberate demo dataset seeded via `manage.py seed_demo_data` on 2026-08-01 specifically so the client could review the app with realistic, uneven occupancy data — it is **not** organically-entered real business activity.

Per this task's framing ("we have confirmed that this data is dummy data and should NOT be archived as historical business records" / desired end state = "empty operational/business dataset"), **this demo dataset is proposed for removal alongside the TEST records**, not retained. It is listed as its own category here (rather than folded into TEST) only because its provenance and purpose differ — intentional demo content vs. throwaway verification residue — not because it is treated differently in the deletion proposal below.

## 4. Records classified UNKNOWN

**None**, per the 2026-08-24 audit: "no unlabeled, ambiguous, or placeholder-looking records were found — no `test@test.com`, `foo`/`bar`, `asdf`, sequential fake names, or similar patterns outside the two categories above." This must still be re-confirmed by the live `--dry-run` at execution time, since it is a point-in-time finding. Per this task's explicit instruction, **anything the live re-audit classifies UNKNOWN will not be deleted**, regardless of this prior finding.

## 5. Records proposed for deletion

The union of §2 (TEST) and §3 (DEMO) — in practice, everything currently present in the 8 business tables (Property, Section, Unit, PricingRule, Student, Occupancy, Payment, Receipt), since the audit found 100% of existing rows in those tables fall into one of those two categories and 0% are UNKNOWN or confirmed real client data. Nothing outside those 8 tables (User, AuditLog, Backup) is proposed for deletion.

## 6. Users proposed for retention

- **`karosadmin`** (superuser) — the production administrator account. Retained unconditionally; not affected by this operation in any way.

## 7. Users proposed for deletion

**None.** No demo or test user accounts exist on the live database — confirmed independently twice: the RDS migration cutover row-count diff on 2026-08-19 (1/1 users matched), and the 2026-08-24 audit ("No test/demo accounts found"). (A separate `demo`/`demo12345` account is documented, but only ever existed in the local dev database — never on staging/live.)

## 8. Audit-log treatment

**Preserve entirely — no AuditLog row will be read, modified, or deleted by this operation.** This matches established, repeatedly-stated project policy: `seed_demo_data --reset` already never touches `User` or `AuditLog`; multiple docs (`CHANGELOG.md`, `PROJECT_STATE.md`, `DISASTER_RECOVERY.md`, `RELEASE_PLAN.md`) state the audit trail is meant to be immutable, including being the record that a prior data reset happened. No audit-log reset mechanism exists anywhere in this codebase, and none is proposed here.

Because the audit log cannot be annotated with a "pre-live" marker at the schema level (no such field exists on `AuditLog`), the recommended approach — to be carried out **after** execution, not as part of this report — is a separate document (`docs/LIVE_DATA_RESET.md`) recording the reset's date/time as the dividing line, so future readers of the audit log know entries before that timestamp reflect pre-live testing and demo activity, without altering the log itself.

## 9. Deletion order (dependency graph)

Derived directly from the Django FK definitions (`on_delete=RESTRICT` throughout, except `PricingRule → Unit` which is `CASCADE`):

```
Receipt
  ↓ (OneToOne, RESTRICT)
Payment
  ↓ (RESTRICT)
Occupancy
  ↓ (RESTRICT)          ↓ (RESTRICT, unit side)
Student                 PricingRule (CASCADE from Unit)
                           ↓
                         Unit
                           ↓ (RESTRICT)
                         Section
                           ↓ (RESTRICT)
                         Property
```

Concretely: **Receipt → Payment → Occupancy → {Student, PricingRule} → Unit → Section → Property**. `AuditLog` and `Backup` reference `User` via `SET_NULL` only — they neither block nor are affected by any step in this order.

## 10. Expected final record counts (post-reset, if approved and executed)

| Model | Before | After |
|---|---|---|
| Property | 5 | 0 |
| Section | 6 | 0 |
| Unit | 14 | 0 |
| PricingRule | 0 | 0 |
| Student | 19 | 0 |
| Occupancy | 17 | 0 |
| Payment | 16 | 0 |
| Receipt | 16 | 0 |
| User | 1 | 1 (unchanged) |
| AuditLog | unknown | unchanged (no rows removed) |

## 11. Backup required before execution

A fresh full PostgreSQL backup is a hard prerequisite — deletion must not proceed if any of these checks fail:

1. Run `./scripts/backup-to-s3.sh` (the already-existing, already-automated nightly backup script) immediately before any deletion step.
2. The script must complete successfully — it already fails loudly (`die`) on: a dump under a minimum size threshold, a dump missing expected `CREATE TABLE`/`COPY` structure, or an S3 upload failure.
3. Verify via the script's own S3 `head-object` check: non-zero object size, a `VersionId` present (bucket versioning), and `ServerSideEncryption` confirmed.
4. Record the resulting S3 key and timestamp for the post-execution report.
5. Additionally recommended (not strictly required, since step 2 already proves the dump is structurally sound): a restorability proof via `./scripts/restore-from-s3.sh --latest --keep`, comparing its row counts against this report's §1 table, then dropping the disposable database once satisfied.

If backup or restorability verification fails at any point, **execution stops** — no deletion is authorized until a fresh, verified backup exists.

## 12. Post-reset verification plan

1. `curl -f https://<host>/api/health/` → expect `HTTP 200`, `{"status":"ok","database":"ok"}`.
2. Re-run `python manage.py reset_live_data --dry-run` → expect `demo=0 test=0 unknown=0` across all 8 business tables (this doubles as an idempotency check on the tool itself).
3. `User.objects.count()` → 1 (`karosadmin`, unchanged).
4. Dashboard/Property Explorer shows an empty operational state with no errors.
5. `python manage.py migrate --check` → clean, no pending migrations.
6. RDS health (console or the existing CloudWatch alarms, expect 7/7 OK), S3 backup bucket still reachable, CI/CD deploy pipeline unaffected (no code path in this reset touches deploy config).
7. AuditLog row count immediately after execution equals the count immediately before it (no rows added or removed by the reset itself).
8. Optional: create one real property/occupant through the UI to confirm the application is fully functional end-to-end post-reset.

---

## Execution is not covered by this report

Actually running this reset — a live re-audit via `reset_live_data --dry-run`, the backup and restorability proof, and finally `reset_live_data --confirm` — requires direct SSH/RDS access to the live EC2 instance, which was neither available nor used in preparing this report. This document is the proposal to review; execution is a separate, later, explicitly-authorized step.

**RESET NOT EXECUTED — awaiting approval.**
