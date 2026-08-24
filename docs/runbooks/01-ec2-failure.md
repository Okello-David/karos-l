# Runbook: EC2 Instance Failure

**Covers:** the EC2 instance (`karosl-staging-ec2`, `i-0afd1871b46296500`) becoming unreachable, failing
status checks, or being terminated/destroyed. For a merely **stopped** instance (planned or accidental stop,
no data/config loss), use `scripts/recover-staging.sh` directly — that path is already automated and proven;
this runbook is for the harder case where the instance itself is gone or unrecoverable.

## Symptoms
- `scripts/verify-staging.sh` fails every check (TLS handshake, health endpoint, SPA load) — not just one.
- AWS Console / `aws ec2 describe-instances` shows the instance `terminated`, or `stopped` with repeated
  `StatusCheckFailed` on restart attempts.
- SSH connection refused or times out even after confirming the security group allows your current IP.
- GitHub Actions deploys start failing with "no runner available" (the self-hosted runner lives on this
  instance).

## Severity
**High.** The application is fully down. Not an emergency in the sense of active data loss (RDS is a
separate resource, unaffected by EC2 loss), but every minute of downtime is visible to end users, and the
client is actively reviewing the app (see project context — infra decisions should account for this).

## Immediate actions
1. Confirm this is really instance loss, not a transient network blip: `aws ec2 describe-instances
   --instance-ids i-0afd1871b46296500 --query 'Reservations[].Instances[].State.Name'`.
2. If `stopped`, **do not proceed with this runbook** — use `./scripts/recover-staging.sh` instead, it's
   built for exactly that case and is non-destructive.
3. If `terminated` or genuinely unrecoverable (e.g. repeated `StatusCheckFailed` that `stop`/`start` doesn't
   clear): confirm RDS is unaffected (`aws rds describe-db-instances --db-instance-identifier
   karosl-staging-postgres --query 'DBInstances[].DBInstanceStatus'` should show `available`) — this tells
   you the database survives and the recovery is "rebuild the app tier," not "rebuild everything."

## Investigation
- Check CloudWatch Logs (`/karosl/staging/django`, `/karosl/staging/nginx`) for the last entries before the
  instance went dark — may explain *why* (out-of-memory, disk full, a bad process) even if it doesn't change
  the recovery steps.
- Check the `karosl-staging-status-check-failed` and `karosl-staging-high-cpu` CloudWatch alarms' history —
  did either fire before the loss? This tells you whether it was gradual (resource exhaustion) or sudden
  (external termination, AWS zone issue).

## Recovery procedure
**What's lost with the instance vs. what survives it — know this before starting:**

| Survives (external) | Lost (instance-only, no other copy) |
|---|---|
| Application code (GitHub) | **`.env` file — `SECRET_KEY`, RDS app password, every secret** |
| Database contents (RDS, separate resource) | TLS certificates (cheap to re-issue, not a real loss) |
| Docker/CI definitions (GitHub) | GitHub Actions self-hosted runner registration |
| S3 backups (separate resource) | Any undocumented manual server-side changes |

Steps:
1. Launch a replacement EC2 instance — same AMI family (Amazon Linux 2023), same instance type
   (`t3.micro`), same VPC/subnet. Attach the existing security group (`sg-065fb018e22aa18a5`) if it still
   exists (security groups are VPC-level, independent of any one instance), or recreate it per
   `docs/AWS_EC2_DEPLOYMENT.md`'s documented rules (SSH from the operator's `/32` only, 80/443 open).
2. `git clone` the repo to `~/apps/karosl` on the new instance.
3. **Rebuild `.env` from scratch.** There is no source to copy this from — `SECRET_KEY` must be freshly
   generated, and because the old RDS application password only ever existed in the now-lost `.env`, **you
   must also reset it** via `aws rds modify-db-instance --db-instance-identifier karosl-staging-postgres
   --master-user-password <new-password> --apply-immediately` (or reset the application-level DB user's
   password directly if it differs from the master user — check `docs/RDS_MIGRATION.md` for which one
   KarosL actually uses). Set `DB_HOST` to the existing RDS endpoint — the data itself is untouched by any
   of this, only the credential needs to be new.
4. Install and register a fresh self-hosted GitHub Actions runner (`docs/CI_CD.md` has full setup steps) —
   requires a new registration token from the GitHub repo's Settings → Actions → Runners page.
5. First deploy: either let the newly-registered runner pick up the next `git push`, or run
   `./scripts/deploy-staging.sh` manually once to get the stack up without waiting on CI.
6. Re-issue TLS certificates: `./scripts/recover-staging.sh` already automates this for "instance has a new
   IP" (which a replacement instance always does) — dry-run-first, rate-limit-safe, handles both the
   hostname and bare-IP certificate lineages.
7. Confirm DNS/origin config: `scripts/fix-staging-origins.sh` (called internally by `recover-staging.sh`)
   updates `.env`'s recorded origins and CORS/CSRF trusted-origins to match the new IP/hostname.

## Verification
Run `./scripts/verify-staging.sh` against the new instance's IP. It independently checks: HTTP→HTTPS
redirect, TLS handshake + chain + expiry (both certificate lineages), `/api/health/` content
(`"database":"ok"` specifically — proves the RDS reconnection in step 3 actually worked), SPA load and
deep-link routing, the 401 auth boundary, HSTS header, and that ports 8000/5432/5173 are closed externally.
Do not consider the instance recovered until every check passes.

## Rollback
There is no "rollback" concept for this scenario — you're building a replacement, not reverting a change. If
step 3's new RDS password doesn't work, double-check you modified the correct DB user (master vs.
application user) and that `docker-compose.rds.yml`'s overlay is actually being applied (verify `.env`'s
`DB_HOST` is not still `db`).

## Escalation
If RDS itself also shows `unavailable`/degraded during this incident (not just EC2), stop and treat it as a
combined RDS+EC2 incident — see `docs/runbooks/02-rds-recovery.md` for the database side, and prioritize
getting the database healthy before spending further effort on the app tier.

## Lessons learned (fill in after a real incident)
_Record here: what actually failed, how long recovery actually took vs. the ~20-30 minute estimate in
`docs/DISASTER_RECOVERY.md` §3, and any step that turned out harder/easier than documented._
