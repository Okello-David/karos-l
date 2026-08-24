# Runbook: HTTPS / Nginx / Network Failure Recovery

**Covers:** HTTPS/TLS failures, nginx down, EC2 network/security-group problems, and RDS connectivity
failure. **KarosL currently has no purchased custom domain** — this is documented as a deliberate, standing
decision, gated on client sign-off before further infrastructure spend. This runbook documents the actual
live architecture (sslip.io-based, no DNS to manage), not an assumed domain setup.

## Symptoms
- Browser shows a TLS/certificate error, or `verify-staging.sh`'s TLS checks fail.
- `verify-staging.sh` reports the HTTP→HTTPS redirect check failing.
- The app loads over HTTP but not HTTPS, or vice versa.
- `/api/health/` returns fine but the `"database"` field is not `"ok"` (this is an RDS-connectivity
  symptom, not actually an HTTPS/network one — see the dedicated section below, don't misdiagnose it as a
  cert problem).
- SSH still works but the site itself is unreachable (points at nginx/container-level failure, not EC2/network).

## Severity
**High** — the application is either fully down or showing security warnings that would justifiably make
users (including the reviewing client) distrust the app.

## Immediate actions
Run `./scripts/verify-staging.sh` first, always — it independently checks every layer this runbook covers
(HTTP redirect, TLS handshake + chain + expiry for **both** certificate lineages, health endpoint content,
SPA routing, auth boundary, HSTS, closed ports) and tells you exactly which layer is actually broken, so you
don't spend time on the wrong fix.

## Investigation — by symptom

### TLS/certificate errors
KarosL runs **two independent certificate lineages simultaneously**, both Let's Encrypt, served via nginx
SNI on the same port 443:
1. **Hostname cert** (`<ip-with-dashes>.sslip.io`) — standard ~90-day validity.
2. **Bare-IP cert** — mandatorily short-lived, **~160 hours (~6.67 days)**. This one expires far more often
   by design, and is the more likely culprit if renewal has silently stopped.

Check which lineage is actually failing — `verify-staging.sh` checks both independently and will tell you.
Both renew via `certbot-renew.timer`, twice daily. If renewal has stopped:
```
sudo systemctl status certbot-renew.timer
sudo journalctl -u certbot-renew.service --since "3 days ago"
```

### Nginx down
```
docker compose ps                    # is the frontend/nginx container even running?
./scripts/docker-logs.sh frontend    # what's it saying?
```
A crash-looping nginx container is most often a certificate file nginx expects but can't find (e.g. a
partial/failed cert renewal left a broken symlink) — `nginx` refuses to start if `ssl_certificate` points at
a missing file. Check `/etc/letsencrypt/live/` for both expected lineages before assuming a code-level nginx
config problem.

### EC2 network / security-group problems
- Confirm the security group still allows 80/443 from the internet and 22 from the admin `/32`:
  `aws ec2 describe-security-groups --group-ids sg-065fb018e22aa18a5`.
- If the instance was recently stopped/started, **its public IP has changed** (no Elastic IP, by deliberate
  cost decision) — this is the single most common cause of "everything was fine yesterday" network
  confusion here. Check the current IP against what `.env` and both certificate lineages actually reference.

### RDS connectivity failure
This surfaces through the **application health check**, not a network-layer symptom directly — `/api/health/`
explicitly checks `"database":"ok"` separately from the endpoint responding at all (called out in
`verify-staging.sh`'s own comments as "the check that matters most," since the SPA can serve a 200 from
static files even when the API underneath is fully broken). Since RDS is `PubliclyAccessible: false` and
reachable only from the EC2 security group by reference, a connectivity failure here is almost always one of:
- The EC2 security group's egress or the RDS security group's ingress rule was changed.
- RDS itself is down/degraded (`aws rds describe-db-instances` — see `docs/runbooks/02-rds-recovery.md`).
- `.env`'s `DB_HOST`/`DB_PASSWORD` is stale or wrong (e.g. after an incomplete credential rotation).

## Recovery procedure

**For the common "instance restarted, everything's stale" case** (new IP, stale `.env` origins, possibly
orphaned/missing certs): use the already-built, already-proven tool rather than fixing pieces by hand:
```
./scripts/recover-staging.sh
```
This handles, in the correct order: fixing `.env`'s recorded origins → re-issuing both certificate lineages
(dry-run-first, rate-limit-safe) → recreating containers with the HTTPS overlay so they pick up the new
values → sweeping orphaned old-hostname/old-IP certificates (only *after* containers are recreated, since
deleting them first would leave nginx unable to start) → verifying via `verify-staging.sh` against both the
hostname and bare-IP addresses.

**For a security-group misconfiguration**: correct the rule directly via `aws ec2
authorize-security-group-ingress`/`revoke-security-group-ingress` — do not widen beyond what's documented
(80/443 open, 22 restricted to the admin `/32`) even temporarily, per standing project convention.

**For RDS connectivity specifically**: see `docs/runbooks/02-rds-recovery.md` if RDS itself is the problem;
if it's a security-group/credential issue instead, correct the specific misconfiguration and restart just
the backend container (`docker compose up -d backend`) to pick up the fix without a full stack restart.

## Verification
`./scripts/verify-staging.sh` — must pass every check, not just the one that originally failed. A partial
fix that resolves the reported symptom but leaves another layer broken (e.g. fixed the hostname cert but the
bare-IP cert is still expired) should not be considered done.

## Rollback
Certificate re-issuance and origin fixes are not really "rollback-able" in a meaningful sense — they're
idempotent repairs, safe to re-run (`recover-staging.sh` is explicitly designed to be a no-op if things are
already correct). For a security-group change made in error, simply revert to the previously-correct rule.

## Escalation
If `verify-staging.sh` continues failing after `recover-staging.sh` completes successfully, the problem is
likely not the "stale environment after restart" case this tooling targets — broaden investigation to
EC2 instance health (`docs/runbooks/01-ec2-failure.md`) or a genuine RDS problem
(`docs/runbooks/02-rds-recovery.md`).

## Lessons learned (fill in after a real incident)
_Record here: which of the two certificate lineages actually caused the problem (the short-lived bare-IP one
is statistically more likely, given it expires roughly 13x more often), and whether `recover-staging.sh`
resolved it without manual intervention._
