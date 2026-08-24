# Runbook: Database / Data Corruption Recovery

**Covers:** a user accidentally changes or deletes important information through the application (the
"fat-fingered a payment amount" or "archived the wrong property" class of incident) — not infrastructure
failure. For infrastructure-level database loss, see `docs/runbooks/02-rds-recovery.md` or
`docs/runbooks/03-s3-backup-recovery.md`.

## Symptoms
- A user reports "this data is wrong" or "this record disappeared."
- A report or dashboard figure looks implausible compared to known reality.
- Someone realizes they performed an action (archived a property, recorded a duplicate payment) that
  shouldn't have happened.

## Severity
**Medium**, usually — the application keeps running, this is a data-accuracy problem, not an outage. Can
escalate to **High** if the affected data is financial (payment records) and the client is actively
reviewing the app.

## Immediate actions
1. **Do not guess-fix it directly in the UI yet** — first establish the actual scope via the audit log, so
   the fix addresses exactly what happened, not an assumption about what happened.
2. Note the approximate time the change occurred, if known — narrows the audit log search.

## Investigation
1. **Check the audit log first** — `apps/audit` captures CREATE, UPDATE, ARCHIVE, ASSIGN, CHECKOUT, and
   RECORD_PAYMENT across every business entity, with actor, timestamp, and (for updates) a `changes` JSON
   field showing exactly what changed. Query via the Audit Trail page in the app, or directly:
   ```
   docker compose exec backend python manage.py shell -c "
   from apps.audit.models import AuditLog
   for log in AuditLog.objects.filter(entity_type='payment').order_by('-timestamp')[:20]:
       print(log.timestamp, log.actor, log.action, log.description)"
   ```
2. **Know the audit log's real coverage before trusting it completely:** it captures the actions above, but
   **does NOT capture most deletions**, because the application is soft-delete-first — almost everything
   that looks like "removal" is an ARCHIVE (which *is* logged), not a hard DELETE. The one exception is
   `PricingRule` deletion, which *is* logged as `Action.DELETE`. If data is missing in a way no archive
   action explains, that's a signal it may have been removed outside the application layer entirely (direct
   database access) — which the audit log has no visibility into at all.
3. If the audit log shows exactly what happened and by whom, you may not need a database restore at
   all — proceed to the fix in step 1 of the recovery procedure below.

## Recovery procedure

**Case A — the audit log explains it and it's reversible through the app:**
- An accidental archive: un-archive through the normal app UI/API — this is a completely ordinary,
  logged, no-special-tooling action.
- An accidental edit where the audit log's `changes` field shows the previous value: manually re-enter the
  correct value through the app UI — deliberate, logged, auditable.

**Case B — data is genuinely gone or the correct prior value isn't recoverable from the audit log alone:**
1. Restore the most recent backup into a **disposable** database, following
   `docs/runbooks/03-s3-backup-recovery.md` exactly — never restore over the live database.
2. Locate the correct data in the restored copy (query it directly via `psql` or the Django ORM pointed at
   the disposable database, per that runbook's verification section).
3. **Manually re-apply** the correct values to the live database — there is no automated "restore just these
   rows" tool. This should be done carefully, ideally through the application layer (so the fix itself is
   audit-logged) rather than a direct SQL `UPDATE`, unless the application layer has no path to set the
   needed value directly.
4. Drop the disposable database once done (per the S3-recovery runbook's cleanup step).

**Case C — the corruption predates every available backup (older than the retention window), or the loss
is severe enough that manual row-by-row reconstruction isn't practical:**
- This is the actual boundary of what's recoverable — see `docs/DISASTER_RECOVERY.md` §6/§7 for the honest
  statement of what data-loss window exists (up to ~24h, worst case, bounded by the S3 backup cadence).
  Beyond that window, or for data that was never captured by any backup, recovery is not possible through
  any means documented here.

## Verification
- Re-check the specific record/report that triggered the investigation — confirm it now shows correct data.
- Check the audit log again — confirm the *fix* itself is now logged (if applied through the app), giving a
  complete before/during/after trail for the incident.
- If a disposable database was used (Case B), confirm it was dropped.

## Rollback
If the "fix" turns out to be wrong (e.g. re-applied the wrong value), the audit log's `changes` field for
your own fix action tells you exactly what you just changed and from what — correct it the same way you
would any other data-entry mistake.

## Escalation
If the scope turns out to be broader than one or two records (e.g. a bulk operation went wrong, or many
records are affected), stop doing manual row-by-row fixes and treat it as a full-database restore situation
instead — restore the pre-incident backup into a disposable database, then decide whether a broader manual
reconciliation or a supervised, deliberate full-database restore (see the "Production restore" note in
`docs/S3_BACKUP_ARCHITECTURE.md` — explicitly described there as "a rare, high-stakes, human-supervised
operation") is the right call. That decision should not be made unilaterally by an agent or a single
engineer under time pressure — get a second person's sign-off before restoring over live data.

## Lessons learned (fill in after a real incident)
_Record here: what the audit log did/didn't reveal, how long root-cause investigation took vs. the actual
fix, and whether this incident suggests a gap in what the audit log should capture (e.g. if a hard-delete
path outside `PricingRule` turns out to exist and isn't logged)._
