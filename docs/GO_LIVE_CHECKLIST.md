# Go-Live Checklist — KarosL v1.0

**Date:** 2026-08-24. Every row has a status and cites its evidence — no unverified claims. "✅ Live"
= checked directly against the running system today. "✅ Code" = confirmed by reading the actual
implementation (route exists, permission wired correctly), not by clicking through it. "✅ 2026-08-20" =
last confirmed via a full live click-through smoke test on that date — still the best available evidence for
that specific row, dated so its freshness is visible. "⚠️" = a real, named gap.

## Application

| Item | Status | Evidence |
|---|---|---|
| Login | ✅ 2026-08-20 | Full smoke test, `docs/PRODUCTION_READINESS_REVIEW.md` §13; component confirmed unchanged this session (`Login.jsx`) |
| Logout | ✅ 2026-08-20 | Same smoke test — session/token cleared, redirect to `/login` confirmed |
| Dashboard | ✅ Code + 2026-08-20 | Stat cards, quick actions, recent activity/payments traced in full this session (`Dashboard.jsx`); permission-aware rendering added and tested this session (282/282 backend, 53/53 frontend) |
| Properties | ✅ Code + 2026-08-20 | `Properties.jsx` read-only summary view confirmed; endpoint `IsAuthenticated`-only, tested |
| Sections | ✅ Code + 2026-08-20 | Admin CRUD confirmed in `Administration.jsx`, `CanManageProperty`-gated, tested |
| Units | ✅ Code + 2026-08-20 | Same as Sections; over-capacity blocking confirmed in the 2026-08-20 smoke test |
| Occupants | ✅ Code + 2026-08-20 | Register/edit/search/archive traced this session (`OccupantForm.jsx`, `Occupants.jsx`); search-field accuracy verified against the actual backend query |
| Occupancy | ✅ Code + 2026-08-20 | Assignment wizard, checkout, history traced this session (`AssignOccupancyDialog.jsx`); "move to another unit" confirmed genuinely absent (§7, scope doc) |
| Payments | ✅ Code + 2026-08-20 | Record-payment flow traced; double-toast bug found and fixed this session, regression-tested |
| Receipts | ✅ Code + 2026-08-20 | `Receipts.jsx` search/PDF download traced this session |
| Explorer | ✅ Code + 2026-08-20 | Traffic-light logic read directly from `UnitNode.jsx` this session — thresholds confirmed (green &lt;75%, yellow ≥75%, red full) |
| Administration | ✅ Code | Full tab-by-tab trace this session, including the RBAC-driven Users/Audit tab hiding from Property Managers built this session |
| Reports | ✅ Code | `apps/reports/views.py` confirmed live and working — **note**: `docs/BUG_QUEUE.md` still has a stale "not implemented" note for this; corrected in `docs/V1_RELEASE_SCOPE.md` |
| Audit logs | ✅ Code + 2026-08-20 | Coverage confirmed (create/update/archive/assign/checkout/record_payment); Super-Admin-only access confirmed correct this session |
| **Full end-to-end workflow (register→assign→pay→receipt→balance→audit)** | ⏳ Pending | See Phase 8 — to be run live this sprint with you logged in |

## Security

| Item | Status | Evidence |
|---|---|---|
| HTTPS | ✅ Live | External check today: `curl` confirms HTTPS serving, dual cert lineages per `docs/HTTPS_IP_CERTIFICATE.md` |
| Authentication | ✅ Live | Unauthenticated request to `/api/occupants/` returns clean `401` JSON, checked today |
| Authorization | ✅ Live + tested | 3-role RBAC deployed and live (this session); 282 backend tests include explicit elevation-prevention and ID-substitution regression tests |
| RDS private | ✅ Live | `aws rds describe-db-instances`: `PubliclyAccessible: false`, checked today |
| S3 private | ✅ Live | `aws s3api get-public-access-block`: all 4 flags `true`, no bucket policy, checked today |
| IAM least privilege | ✅ Documented + Live | Backup role confirmed to lack `s3:DeleteObject` (DR sprint); instance profile confirmed attached today |
| `DEBUG=False` | ✅ 2026-08-20 + Live corroboration | Direct `.env` check 2026-08-20; external error-page probe today shows clean DRF JSON, no debug leakage — **⚠️ known gap**: code defaults to `True` if the env var is ever unset, no fail-fast guard |
| Secrets protected | ✅ Live + ⚠️ gap | `.gitignore` covers all `.env` files (confirmed clean via `git log`); **⚠️ `.env` itself has no second copy anywhere outside the EC2 instance** — see `docs/DISASTER_RECOVERY.md` |

## Infrastructure

| Item | Status | Evidence |
|---|---|---|
| EC2 healthy | ✅ Live | Instance `running`, external `/api/health/` returns `{"status":"ok","database":"ok"}`, checked today |
| Docker containers healthy | ✅ Live (via deploy) | Today's deploy pipeline's own health-check gate passed (backend/frontend both healthy before traffic serves) |
| RDS healthy | ✅ Live | `DBInstanceStatus: available`, `DeletionProtection: true`, `StorageEncrypted: true`, checked today |
| S3 backups healthy | ✅ Live | Daily backup objects present through today (`karosl_db_2026-08-24_135700.sql.gz` and 3 earlier same-day ones from deploy pre-backups) |
| CloudWatch healthy | ✅ Live | All 7 alarms in `OK` state, checked today; the 3 RDS alarms independently verified to actually notify via SNS this same sprint |
| CI/CD healthy | ✅ Live | Today's deploy: all jobs green (backend ×2, frontend, Docker build, deploy, external smoke test), post-secret-cleanup |

## Data

| Item | Status | Evidence |
|---|---|---|
| Live database backed up | ✅ Live | Latest backup object is from today, 13:57 UTC (a deploy pre-backup) |
| S3 backup verified | ✅ Live, this session | Restored the actual latest backup into a disposable database for the live-data audit — real, working restore, not assumed |
| Restore procedure documented | ✅ | `docs/runbooks/03-s3-backup-recovery.md`, proven (15s restore, &lt;1min full verification) |
| No test data accidentally mixed with real data | ✅ Audited | `docs/LIVE_DATA_AUDIT.md` — all test records are clearly labeled, already archived, and classified; no ambiguous/unknown records found |

## Operations

| Item | Status | Evidence |
|---|---|---|
| Alert notifications confirmed | ✅ Live | SNS subscription confirmed (real ARN, not pending); the 3 new RDS alarms independently verified to actually publish, this sprint |
| Incident response documented | ✅ | `docs/runbooks/06-security-incident.md` — 5 scenarios, **undrilled** (honest, not claimed tested) |
| Recovery procedures documented | ✅ | `docs/DISASTER_RECOVERY.md` + 7 runbooks, one path (S3 restore) empirically tested, others documented-but-untested and labeled as such |
| Deployment/rollback procedures documented | ✅ Live-proven | `docs/CI_CD.md`, `docs/ADMIN_RUNBOOK.md`; rollback logic read in full and confirmed never touches the database |

## Outstanding before this checklist can read "fully complete"

1. Phase 8's live end-to-end workflow test (application row above) — pending your login.
2. The two known, documented, non-blocking gaps (`DEBUG` fail-fast guard, backup-timer-silent-stop alarm) —
   tracked, not fixed this sprint (out of scope; see `docs/RELEASE_PLAN.md`'s next-sprint recommendations).
