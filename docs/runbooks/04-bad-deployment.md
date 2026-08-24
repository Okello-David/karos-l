# Runbook: Bad Deployment Recovery

**Covers:** a broken Docker image, failed deployment, failed migration, broken frontend build, or broken
backend release reaching (or nearly reaching) the live application.

**Status:** rollback behavior verified this pass by reading `scripts/rollback-staging.sh` in full — every
claim below matches what the script actually does. Not exercised against a live broken deploy (correctly —
the brief prohibits intentionally deploying broken code to the live application).

## Symptoms
- `deploy-staging.yml`'s deploy or smoke-test job fails in GitHub Actions.
- `/api/health/` stops returning `"status":"ok"` after a deploy.
- The frontend loads but shows a blank page / console errors (broken build reached production despite CI
  passing — e.g. a runtime-only bug CI's test suite didn't catch).
- Users report a specific feature broken immediately after a known deploy time.

## Severity
**High** if the application is fully down (failed health check, container won't start). **Medium** if it's
degraded (one feature broken, core app usable) — still urgent, less time-pressured.

## Immediate actions
1. Confirm this is actually deploy-related: check the deploy time against when the symptom started
   (`~/.karosl-deploy-history` on the instance has `<timestamp> <sha>` for every successful deploy).
2. Check whether CI/CD's own gates already caught it: if the GitHub Actions deploy job failed outright, the
   bad code **never reached the live containers** — the pipeline's `needs:` gating (backend tests → frontend
   tests/build → Docker build validation, all before the deploy step) means most broken releases are caught
   before touching production at all. Confirm via the Actions tab which job failed.
3. If the bad release *did* reach production (deploy job succeeded, but the app is now broken — e.g. a
   runtime bug tests didn't catch, or a broken migration that only surfaces under real data), proceed to
   rollback.

## Investigation
- `docker compose ps` on the instance — is the backend container even `healthy`, or crash-looping?
- `./scripts/docker-logs.sh backend` (or `frontend`) for the actual error.
- If a migration is suspected: `docker compose exec backend python manage.py showmigrations` to see what's
  actually applied vs. what the rolled-forward code expects.
- Check CloudWatch Logs (`/karosl/staging/django`) for the same information, if the container is too broken
  to `exec` into cleanly.

## Recovery procedure
```bash
# From the instance, in ~/apps/karosl:
./scripts/rollback-staging.sh                    # rolls back to the previous known-good deploy
# or, to a specific commit:
./scripts/rollback-staging.sh --to=<sha>
```

**What this actually does (confirmed by reading the script in full):**
1. Determines the target commit — previous entry in `~/.karosl-deploy-history`, or your explicit `--to=`.
2. Refuses if the working tree has uncommitted changes to tracked files (won't discard in-progress work
   silently).
3. **If a migration was applied since the target commit, prints a warning and pauses 5 seconds** (Ctrl-C to
   abort) — **this is the one case requiring human judgment**, because the script cannot safely
   auto-downgrade a migration against live data. Read the warning's suggested `git log` command before
   letting it proceed, so you know whether the rolled-back code will be compatible with the current schema.
4. Checks out the target commit as a detached HEAD.
5. Rebuilds and restarts the stack with the correct compose overlays (HTTPS/CloudWatch/RDS), re-evaluated
   fresh against the target commit.
6. Runs the same content-based health check the deploy pipeline uses.
7. **Confirmed: never touches the database, volumes, or runs `down -v`.** Code-only rollback.
8. Appends a `ROLLBACK-TO <sha>` entry to `~/.karosl-deploy-history` on success.

**If the migration warning in step 3 applies and you're unsure it's safe:** do not proceed blindly. The
safer sequence is: roll back the code first if the migration is purely additive (new table/column the old
code just ignores — usually safe), or write and apply a compensating migration on `dev`/`cloud-deployment`
and deploy *forward* past the bug instead of backward past the schema change, if the migration removed or
renamed something the old code still expects.

## Verification
- `./scripts/verify-staging.sh` — full stack check, not just the health endpoint.
- Confirm the specific symptom that triggered this runbook is actually gone (re-test the broken feature
  manually, don't just trust a green health check).
- Check `~/.karosl-deploy-history` shows the `ROLLBACK-TO` entry.

## Rollback (of the rollback)
You're now on a detached HEAD, not a branch. To move forward again once a real fix is ready:
```bash
git checkout cloud-deployment && ./scripts/deploy-staging.sh --pull
```
This deploys the latest `cloud-deployment` commit (which should include the fix) forward, past whatever was
rolled back.

## Escalation
If rollback itself fails to reach a healthy state (rolling back doesn't fix it — meaning the problem isn't
actually the recent deploy), stop and broaden the investigation: check RDS status
(`docs/runbooks/02-rds-recovery.md`), check EC2 instance health
(`docs/runbooks/01-ec2-failure.md`), and check for an infrastructure-level cause rather than continuing to
treat this as purely a code problem.

## Lessons learned (fill in after a real incident)
_Record here: which failure mode actually occurred (CI caught it vs. reached production), how long detection
took, whether the migration-compatibility warning applied and how it was resolved._
