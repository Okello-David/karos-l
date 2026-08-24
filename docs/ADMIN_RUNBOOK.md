# Administrator Runbook — KarosL

Quick-reference for a technical operator/maintainer. This is a task-oriented index into commands and
scripts that already exist and have been proven this session — not a rewrite of the deeper procedures in
`docs/runbooks/`, which this doc points to for anything beyond a quick check.

## How to check application health

```bash
./scripts/verify-staging.sh
```
Read-only, exit code is the signal. Checks: HTTP→HTTPS redirect, TLS handshake/chain/expiry (both
certificate lineages), `/api/health/` content (`"database":"ok"` — the check that matters most, since the
frontend can serve 200 while the API underneath is broken), SPA load, the 401 auth boundary, HSTS header,
and that ports 8000/5432/5173 are closed to the internet.

Quick manual check from anywhere:
```bash
curl https://<current-ip-with-dashes>.sslip.io/api/health/
# {"status":"ok","database":"ok"}
```

## How to inspect logs

CloudWatch Logs (from anywhere with AWS CLI access):
```bash
aws logs tail /karosl/staging/django --since 1h --follow
aws logs tail /karosl/staging/nginx --since 1h --follow
aws logs tail /karosl/staging/backup --since 1h --follow
```

On the instance directly (requires SSH — see `docs/AWS_EC2_DEPLOYMENT.md` for access):
```bash
docker compose logs backend --tail 100
docker compose logs frontend --tail 100
./scripts/docker-logs.sh backend   # convenience wrapper
```

## How to inspect Docker containers

On the instance:
```bash
docker compose ps                 # status/health of all containers
docker compose exec backend python manage.py shell   # Django shell
docker stats                      # live resource usage
```

## How to check RDS

```bash
aws rds describe-db-instances --db-instance-identifier karosl-staging-postgres \
  --query 'DBInstances[].{Status:DBInstanceStatus,Storage:AllocatedStorage,MultiAZ:MultiAZ,Deletion:DeletionProtection}'
aws rds describe-db-snapshots --db-instance-identifier karosl-staging-postgres
```
Full recovery procedure: `docs/runbooks/02-rds-recovery.md`.

## How to verify S3 backups

```bash
export KAROSL_BACKUP_BUCKET="karosl-staging-backups-908877263055"
./scripts/restore-from-s3.sh --list                          # see what's available
./scripts/restore-from-s3.sh --latest --target-db=verify_$(date +%Y%m%d) --keep
# inspect, then drop it:
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE verify_YYYYMMDD;"'
```
Never targets the live database — the script refuses if `--target-db` matches it. Full procedure:
`docs/runbooks/03-s3-backup-recovery.md`.

## How to check CloudWatch alarms

```bash
aws cloudwatch describe-alarms --alarm-name-prefix karosl \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue,Metric:MetricName}'
```
All 7 alarms and their thresholds/response actions: `docs/CLOUDWATCH_MONITORING.md` §7.

To manually verify an alarm's SNS notification path (safe, standard technique, used repeatedly this
session):
```bash
aws cloudwatch set-alarm-state --alarm-name <name> --state-value ALARM --state-reason "manual verification"
aws cloudwatch describe-alarm-history --alarm-name <name> --history-item-type Action --max-records 1
# confirm "actionState":"Succeeded", then reset:
aws cloudwatch set-alarm-state --alarm-name <name> --state-value OK --state-reason "reset after verification"
```

## How to inspect GitHub Actions

```bash
gh run list --branch cloud-deployment --limit 5
gh run watch <run-id> --interval 15     # live-follow a run
gh run view <run-id> --json status,conclusion
```
Pipeline structure and job breakdown: `docs/CI_CD.md`.

## How to deploy

Normal path: `git push origin cloud-deployment` — the self-hosted runner tests, builds, deploys, and
externally smoke-tests automatically. No manual step needed for a routine deploy.

Manual deploy from the instance (e.g. to skip CI for local iteration):
```bash
./scripts/deploy-staging.sh --pull
```

## How to roll back

```bash
./scripts/rollback-staging.sh              # rolls back to the previous known-good deploy
./scripts/rollback-staging.sh --to=<sha>    # rolls back to a specific commit
```
Code-only — confirmed by reading the full script that it never touches the database, volumes, or runs
`down -v`. **If a migration was applied since the target commit**, the script warns and pauses 5 seconds
before proceeding — read the warning, since rollback can't auto-downgrade a schema change. Full detail:
`docs/runbooks/04-bad-deployment.md`.

## How to restore data

- **From S3** (the tested, proven path): see "How to verify S3 backups" above —
  `docs/runbooks/03-s3-backup-recovery.md`.
- **From RDS's own automated backup/PITR**: `docs/runbooks/02-rds-recovery.md` — documented, not yet
  empirically tested (would require a temporary second RDS instance).
- **From the in-app Backup & Export feature** (Super Admin UI, `/backup`): covers 8 business models only,
  excludes users/tokens/audit log — use for a targeted business-data restore, not full disaster recovery.

## How to respond to common failures

| Symptom | Likely cause | First step |
|---|---|---|
| `/api/health/` returns `503` or `"database":"unavailable"` | RDS connectivity or credential issue | `docs/runbooks/02-rds-recovery.md` |
| Site unreachable, SSH still works | Nginx/container down, or a stale compose overlay | `./scripts/verify-staging.sh` to isolate which layer, then `docs/runbooks/07-https-nginx-failure.md` |
| Deploy job fails in GitHub Actions | Check which specific job failed — tests catching a real bug is not an incident | `docs/runbooks/04-bad-deployment.md` |
| A CloudWatch alarm fires | See its response action in `docs/CLOUDWATCH_MONITORING.md` §7 | Investigate before assuming it's a false positive |
| Suspected account/credential compromise | — | `docs/runbooks/06-security-incident.md` — 5 scenarios covered |
| Data looks wrong/missing | Could be an accidental in-app change, or something outside the app | `docs/runbooks/05-database-corruption.md` — check the audit log first |
| Instance was stopped and restarted | Public IP changed (no Elastic IP, by design) | `./scripts/recover-staging.sh` — handles cert reissuance and origin fixes automatically |

For anything not covered by a quick command above, the full incident-response shape (contain → investigate
→ determine blast radius → rotate/restore → verify → document) and every scenario's detail lives in
`docs/runbooks/`. Start there for anything serious; this document is for the fast, routine path.
