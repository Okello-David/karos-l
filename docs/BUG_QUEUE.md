# Bug Queue

## Backend API Stability Sweep (Release Candidate)

### Critical
- BUG-006: Occupant creation returned HTTP 500 (`IntegrityError: UNIQUE constraint failed: occupants_student.student_id_number`) whenever a second occupant was created with a blank `email`, `student_id_number`, or `national_id`, because those fields were `unique=True, blank=True` without `null=True`, and DRF's `CharField.run_validation` skips the auto-generated `UniqueValidator` for blank input, so duplicate empty strings reached the DB unchecked. Root cause verified live via `POST /api/occupants/` reproduction against a scratch copy of the dev DB. This exact fix already existed, reviewed and tested, on the `dev` branch (commit `0554017`, "Fix BUG-003") but was never merged into this branch — ported the vetted migration (`0003_add_null_to_unique_fields`), model, and serializer changes here instead of re-deriving a new one. Files: `apps/occupants/models.py`, `apps/occupants/serializers.py`, `apps/occupants/migrations/0003_add_null_to_unique_fields.py`, `apps/occupants/tests.py`.
- BUG-007: The `occupancy.0004_allow_same_day_checkout` migration existed on disk (relaxing the `ck_occupancy_end_date_after_start` CHECK constraint to allow `end_date == start_date`) but had never been applied to the dev database — `showmigrations` showed it unapplied. Same-day checkout therefore still crashed with `CHECK constraint failed`. Applied the pending migration.
- BUG-008: Recording a payment for an occupant with no `student_id_number` (now possible after BUG-006's fix) crashed with `IntegrityError: NOT NULL constraint failed: payments_receipt.student_id_number`, because `Receipt.student_id_number` is `NOT NULL` at the DB level but `PaymentService._generate_receipt` copied the student's (now possibly `None`) `student_id_number` straight across. Reproduced live via `POST /api/payments/`. Fixed by coercing `None` to `""` when snapshotting onto the receipt. File: `apps/payments/services/__init__.py`.
- BUG-009: `PaymentService.record_payment` saved the `Payment` row and generated its `Receipt` as two separate, non-atomic writes. Reproduced live: an earlier failed payment attempt (crashing during receipt generation, per BUG-008) left an orphaned `Payment` row with no `Receipt` permanently in the database, invisible to the user (who saw only a 500) and only discoverable via a balance discrepancy. Wrapped both writes in `transaction.atomic()` so a receipt-generation failure rolls back the payment too. File: `apps/payments/services/__init__.py`.

### High
- BUG-010: `OccupancyService.checkout_occupancy`'s "already closed" guard checked the `is_active` field instead of `end_date`, and `update_occupancy` (`PATCH /api/occupancy/<id>/`) never kept `is_active` in sync when `end_date` was set directly. Reproduced live: PATCHing `end_date` on an active occupancy left `is_active=True` (stale), and a subsequent `checkout` call then re-ran the checkout logic and crashed with `CHECK constraint failed: ck_occupancy_end_date_after_start`. Fixed `checkout_occupancy` to check `end_date is not None`, and `update_occupancy` to set `is_active = (end_date is None)` whenever `end_date` is part of the patch. Files: `apps/occupancy/services/__init__.py`, `apps/occupancy/tests.py`.
- BUG-011 (closes previously-deferred "export header/key mismatches"): CSV/XLSX export column headers are matched to row-dict keys via a lossy `header.lower().replace(" ", "_")` transform in `ExportService._write_csv`/`_write_xlsx`. Three of the four exports had headers that didn't actually match their row dict keys, so those columns were silently blank in every exported file: `export_occupants` ("Student ID" vs. key `student_id_number`, "Active" vs. `is_active`), `export_occupancies` ("Active" vs. `is_active`), `export_receipts` ("Outstanding Balance" vs. `outstanding_balance_after`, "Unit" vs. `unit_name`, "Property" vs. `property_name`). Reproduced live via `GET /api/backups/export/?entity=...`. Fixed by aligning row dict keys to the existing header-derived keys (via `.values(..., student_id=F("student_id_number"), active=F("is_active"))` for occupants, and renamed dict keys for occupancies/receipts) — no header text or API shape changed, only the previously-blank data now populates correctly. File: `apps/backup/services.py`.

### Verified clean (reproduced live, no bug found)
- Creating properties and confirming immediate visibility in `/api/properties/`, `/api/properties/explorer/`, and `/api/admin/properties/` — works correctly.
- Dashboard `/api/occupancy/summary/` `total_students`/`active_students`/`total_occupied` correctly reflect live data after creating occupants and assigning occupancy — the previously-documented "Dashboard 0/0" fix holds.

## Fixed In Current Debugging Pass

### Critical
- Admin APIs allowed any authenticated user because admin viewsets used `IsAuthenticated | IsPropertyManager`. Fixed by requiring `IsPropertyManager`, which already allows superusers and authenticated Property Manager group members.
- Pricing rule create/delete returned HTTP 500 because audit descriptions referenced serializer-only `unit_name` on the model. Fixed by reading `rule.unit.name`.
- Backup restore failed for foreign-key records because serialized FK values were assigned to model descriptors as integers. Fixed by restoring FK values through their `<field>_id` columns.
- Occupancy assignment ignored effective pricing rules. Fixed by using `AdminService.get_effective_price()` when snapshotting assignment price.
- Monthly balances used a one-month snapshot as the full charge forever. Fixed balance calculation so monthly snapshots are treated as monthly rates and multiplied by elapsed months.

### High
- Admin user create/update failed when `groups` were submitted because the service assigned many-to-many fields directly. Fixed by popping groups and applying `user.groups.set(...)` after save.
- Admin user create allowed submitted `is_superuser`. Fixed by making `is_superuser` read-only in admin user serializers.
- Same-day checkout failed validation because `end_date` had to be greater than `start_date`. Fixed validation and DB constraint to allow same-day checkout.
- Payment serialization could crash for payments without receipts. Fixed receipt fields to return `null` when the reverse receipt does not exist.
- Occupant detail could crash while loading payment summary because `CardSkeleton` was rendered without import. Fixed missing import.
- Global Search called double-prefixed and unregistered API paths and expected the wrong explorer response shape. Fixed endpoint paths and bare-list explorer handling.
- Explorer unit detail panel was unreachable because unit selection was not passed through `PropertyNode` and `SectionNode`. Fixed callback wiring.
- Receipt PDF links bypassed token authentication. Fixed by fetching PDFs as authenticated blobs through the API client.
- Payment workflow crashed with `useState is not defined` whenever a payment's detail view was opened because `PaymentDetailDialog` used `useState` without importing it from `react`. Fixed missing import and added a regression test.

### Release Workflow QA
- Dashboard occupant totals did not update after registering occupants because `/api/occupancy/summary/` did not return `total_students` or `active_students`, while the Dashboard page read those fields. Fixed the API response and added coverage.
- The Properties page never displayed created properties because it was a static placeholder. Fixed it to render the existing property hierarchy API in a read-only overview.
- Administration unit creation could submit from the `All Sections` state without a required `section`. Fixed by disabling `Add Unit` until a section is selected.

## Deferred
- Frontend login/logout UI is not implemented. The backend token login/logout workflow passes, but there is no React route, form, logout action, or auth guard to verify in the UI. This requires a product feature pass, so it was not added during bug fixing.
- Report generation is not implemented. The Reports route loads a placeholder with disabled report cards and a link to Backup & Export. This requires a reporting feature pass, so it was not added during bug fixing.
- Medium/low-priority audit findings remain queued for a separate pass: invalid pagination handling, backup history pagination UI, admin section reorder awaiting, guided tour positioning, and additional UX polish. (Export header/key mismatches, previously listed here, were fixed in the Backend API Stability Sweep — see BUG-011.)
- `IsAuthenticated | IsPropertyManager` is used as the permission class on regular business endpoints (occupants, occupancy, payments, properties read APIs). Since `IsAuthenticated` alone already grants access to any logged-in user, ORing it with `IsPropertyManager` has no additional effect — any authenticated user, regardless of group, can create occupants, record payments, and assign occupancy today. This appears to be an intentional two-tier design (day-to-day staff use these; only `apps/administration` truly requires the Property Manager role), but it was not specified anywhere, so flagging it rather than changing access control behavior without product sign-off.
