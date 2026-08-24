# KarosL v1.0 Release Scope

**Date:** 2026-08-24. This document defines exactly what is included in v1.0 — sourced from the actual
deployed code and this session's own verification work, not from planning docs alone. One stale doc
discrepancy corrected in place: `docs/BUG_QUEUE.md`'s "Deferred" section still lists reports as "not
implemented" — that's outdated; reports were built 2026-08-01 (`backend/apps/reports/`) and are live. The
deployed system is authoritative here, per this task's own instruction.

## 1. Included features

| Area | What's included |
|---|---|
| **Authentication** | Token-based login/logout, session-expiry handling |
| **Occupant management** | Register, edit, search (name/phone/Student ID/National ID — not email), archive |
| **Occupancy management** | Assign to unit (Property → Section → Unit wizard), checkout, occupancy history, over-capacity blocking |
| **Payments** | Record payment (cash/transfer/card), balance calculation, overdue tracking, payment history |
| **Receipts** | Auto-generated on payment, searchable, PDF download |
| **Property Explorer** | Drill-down property/section/unit tree, traffic-light availability (green &lt;75%, yellow ≥75%, red full), unit detail panel with quick actions |
| **Properties (list view)** | Summary table, occupancy rate, active/archived status |
| **Administration** | Property/section/unit/pricing-rule CRUD (Property Manager+); user account management (Super Admin only) |
| **Reports** | Occupancy, financial, and occupants reports, CSV/XLSX export — **live**, despite a stale doc note elsewhere claiming otherwise |
| **Audit log** | Every create/update/archive/assign/checkout/record_payment action, with actor/timestamp/changes — Super Admin only |
| **Backup & Export** | In-app JSON snapshot/restore (8 business models) and CSV/XLSX data export — Super Admin only |
| **Dashboard** | Occupancy/payment/occupant stat cards, quick actions, recent activity, permission-aware (Staff see a reduced view) |

## 2. Operational capabilities

- **CI/CD**: self-hosted GitHub Actions runner on the EC2 instance; `git push` to `cloud-deployment` tests
  (backend ×2 DB engines, frontend), builds, deploys, and externally smoke-tests automatically. Rollback via
  `scripts/rollback-staging.sh` (code-only, never touches the database).
- **Deployment**: Docker Compose, HTTPS via Let's Encrypt (dual certificate lineages — hostname + bare-IP),
  no Elastic IP (deliberate cost decision, `scripts/recover-staging.sh` handles the resulting IP churn).
- **Database**: Amazon RDS PostgreSQL (`db.t4g.micro`, Single-AZ), migrated from a local container
  2026-08-19; the old container is kept as a rollback safety net until its validation window closes
  (2026-08-26).
- **Backups**: automated nightly `pg_dump` to S3 (full database, 30-day daily / 400-day monthly retention),
  proven restorable (measured: 15 seconds to restore, under 1 minute fully verified — see
  `docs/DISASTER_RECOVERY.md`). RDS's own automated backups retained 1 day (Free Tier constraint).
- **Monitoring**: 7 CloudWatch alarms (EC2 status/CPU/disk, backup failures, RDS storage/CPU/connections),
  all wired to a confirmed SNS email subscription, each independently verified to actually fire.

## 3. Security controls

- **3-role RBAC**: Super Administrator (everything), Property Manager (full business-data CRUD, no user/
  audit/backup access), Staff (read-only on properties/units/dashboard/reports/receipts — no access at all,
  not even read, to occupants/occupancy/payments). Full matrix: `docs/ARCHITECTURE_DECISIONS.md`,
  `docs/SECURITY_HARDENING.md`.
- **HTTPS everywhere**, HSTS, secure cookies, no plaintext HTTP path to the app.
- **RDS and S3 both private** — confirmed live this sprint (`PubliclyAccessible: false`; all 4 S3
  public-access-block flags `true`, no bucket policy).
- **SSH restricted to a single `/32`** (the account owner's own IP) — confirmed live.
- **`DEBUG=False`** on the server — confirmed via the 2026-08-20 audit's direct `.env` check, corroborated
  by an external error-page probe this sprint (clean DRF JSON responses, no Django debug page/traceback
  leaked).
- **IAM least privilege** — the backup role can write and read backups but not delete them (`s3:DeleteObject`
  confirmed absent), so a compromised instance can't erase backup history.
- **Security-incident runbook** exists (`docs/runbooks/06-security-incident.md`) covering 5 compromise
  scenarios — written this session, undrilled against a real incident (honest, not claimed otherwise).

## 4. Backup/recovery capabilities

- **Tested, not just documented**: a real S3 backup was restored into a disposable database and verified
  end-to-end (all 9 record types, SQL and Django-ORM layers) during the disaster-recovery sprint — 15
  seconds to restore, under 1 minute fully verified. This is the empirically-measured RTO.
- **RPO ≈24h worst case**, evidenced by real daily backup objects present for every day checked.
- **RDS-native point-in-time-recovery**: a documented AWS platform capability (1-day window), procedure
  written (`docs/runbooks/02-rds-recovery.md`) but **not empirically tested** — would require provisioning a
  temporary second RDS instance, deliberately not done without explicit approval.
- **Rollback** (code-level, not data): proven via a real production incident and its fix during the CI/CD
  build-out (`docs/CI_CD.md` §2), and structurally unchanged since.

## 5. Monitoring capabilities

7 CloudWatch alarms (§2 above), each with a documented threshold and response action
(`docs/CLOUDWATCH_MONITORING.md`), all confirmed wired to a live, confirmed SNS subscription. **One
known, real gap, not hidden**: no alarm exists for the backup *timer* silently stopping (as opposed to a
backup *run* failing, which is alarmed and proven) — flagged in the disaster-recovery sprint as the
highest-likelihood "you wouldn't find out" risk in the system.

## 6. Known limitations

Ranked by real impact, not by convenience of framing — see also `docs/DISASTER_RECOVERY.md`'s and
`docs/SECURITY_HARDENING.md`'s own "remaining risks" sections for full detail:

1. **`.env` secrets (`SECRET_KEY`, RDS password) exist only on the EC2 instance, no second copy anywhere.**
   Instance loss means rotation, not recovery. The single highest-impact infrastructure gap.
2. **No alarm for the backup timer silently stopping.**
3. **No per-property RBAC scoping** — every Property Manager has equal access to every property (documented,
   deliberate for a single-organization tool, not a multi-tenant SaaS boundary — see AD-003).
4. **RDS's own PITR path is unproven** (the S3 `pg_dump` path is the one with real evidence).
5. **RDS automated backup retention is 1 day** (AWS Free Tier account cap, not a chosen value).
6. **`DEBUG` defaults to `True` if unset**, with no fail-fast guard in code — currently inert (the server's
   `.env` sets it correctly) but a latent risk if that env var is ever accidentally dropped during a future
   config change.
7. **Security-incident runbook is undrilled** — real content, no live-fire test yet.
8. **Audit log is Super-Admin-only**, including for Property Managers — a pre-existing design choice, not a
   bug, but worth knowing (the Dashboard's "Recent Activity" panel is empty for anyone but a superuser).

## 7. Explicitly deferred features — not silently promoted into v1.0

- **"Move occupant to another unit"** — no route, no service method. A real gap versus `docs/WORKFLOWS.md`'s
  aspirational spec, confirmed absent in the live smoke test (2026-08-20) and unchanged since.
- **Archived properties don't show an "Archived" badge in Property Explorer** — they're filtered out
  entirely (`is_active=True` filter) rather than shown-but-marked. Working as coded, not as originally
  envisioned; a product decision, not built this sprint.
- **`BackupService`'s local JSON exports don't cover users/tokens/audit log/backup records** — by design,
  documented; the S3 `pg_dump` pipeline is the only complete backup mechanism.
- **Invalid pagination handling, backup-history pagination UI, admin section reorder polish, guided-tour
  positioning** — named in `docs/BUG_QUEUE.md`'s Deferred section, still genuinely queued, not addressed
  this sprint (out of this sprint's scope — operational/launch readiness, not feature polish).
- **Property-level manager scoping** (per AD-003) — a future product decision, not built speculatively.
