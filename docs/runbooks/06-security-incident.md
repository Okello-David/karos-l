# Runbook: Security Incident Response

**Status: this runbook is entirely new as of this DR pass (2026-08-24).** Before today, this repository had
**zero** security-incident-response, credential-rotation-at-scale, or account-compromise documentation
(confirmed by a full search across every doc in `docs/`). The one pre-existing precedent — a real,
already-proven CI-deploy-SSH-key rotation sequence in `docs/CI_CD.md` — is reused below as the model for the
rotation steps, since it's the one piece of this domain known to actually work here. **This runbook has not
been drilled against a real incident.**

**General shape for every scenario below:** Contain → Investigate (audit log + CloudWatch Logs) → Determine
blast radius → Rotate credentials → Restore/repair → Verify → Document. No real credentials, keys, or
passwords appear anywhere in this document — only the commands and AWS/GitHub console paths used to rotate
them.

---

## Scenario A: Compromised application account (KarosL login)

### Symptoms
- Audit log shows actions from a known user at implausible times, or actions inconsistent with that user's
  normal role.
- A user reports they didn't perform an action attributed to them.
- Unexpected changes to occupants/payments/properties with no corresponding support request.

### Severity
**High** if the account has Property Manager privileges (can create occupants, record payments) — real
tenant/payment data is at risk. **Medium** for a read-only authenticated account, given the current
permission model (post the 2026-08-24 permission-gap fix — see `docs/BUG_QUEUE.md`).

### Immediate actions
1. **Contain first, investigate second** — deactivate the account immediately:
   ```
   docker compose exec backend python manage.py shell -c "
   from apps.accounts.models import User
   u = User.objects.get(username='<username>')
   u.is_active = False
   u.save()"
   ```
2. Revoke any active auth token for that user:
   ```
   docker compose exec backend python manage.py shell -c "
   from rest_framework.authtoken.models import Token
   Token.objects.filter(user__username='<username>').delete()"
   ```
   This immediately invalidates their session — no separate "logout" mechanism is needed, DRF token auth is
   stateless per-request.

### Investigation
- Pull every audit log entry for that actor, full history, not just recent: filter `AuditLog` by `actor` in
  the Audit Trail page or via shell (`AuditLog.objects.filter(actor__username='<username>').order_by('timestamp')`).
- Cross-reference against CloudWatch Logs (`/karosl/staging/django`) for the same time window — the audit
  log tells you *what* the app recorded; the request logs can show source IPs and request patterns the audit
  log doesn't capture.
- Determine blast radius: which specific records were touched, and — critically, given the audit log's known
  gap (see `docs/runbooks/05-database-corruption.md`) — whether any hard-delete or direct-database action
  might have occurred outside what the audit log can show.

### Recovery procedure
1. Reset the account's password (do not just reactivate with the old one):
   ```
   docker compose exec backend python manage.py changepassword <username>
   ```
2. Review and reverse any illegitimate actions found in step "Investigation" — un-archive, correct payment
   records, etc., following `docs/runbooks/05-database-corruption.md`'s Case A/B procedure as appropriate.
3. Reactivate the account only once the password is reset and the user is confirmed to still need access.

### Verification
- Confirm the old token no longer authenticates (a request with the revoked token returns 401).
- Confirm the audit log shows the corrective actions from step 2, giving a clean incident trail.

### Rollback
Not applicable — deactivation/token revocation are safe, reversible actions with no down-side to undo.

### Escalation
If the account is a superuser (`karosadmin` or any other), treat this as significantly more severe —
superuser accounts bypass the Property Manager group check entirely (`IsPropertyManager.has_permission`
short-circuits `True` for any superuser) and can also access the Backup & Export and Administration surfaces.
Escalate to Scenario D (AWS credential compromise) investigation as well, in case the same access was used
to reach the AWS console via any stored session.

---

## Scenario B: Compromised SSH credentials (EC2 access)

### Symptoms
- Unexpected SSH sessions in `/var/log/secure` (or `journalctl -u sshd`) on the instance.
- Files modified outside of a known deploy (compare `git status`/`git log` in `~/apps/karosl` against
  `~/.karosl-deploy-history` — anything not explained by a recorded deploy is suspicious).
- The security group's SSH ingress rule shows a CIDR you don't recognize (someone widened it).

### Severity
**Critical** — SSH access to the instance means access to `.env` (all application secrets), the ability to
modify the live application directly, and reach into RDS via the app's own credentials.

### Immediate actions
1. **Tighten the security group immediately** to only the legitimate admin's current `/32` — do not leave a
   wider rule in place while investigating:
   ```
   aws ec2 revoke-security-group-ingress --group-id sg-065fb018e22aa18a5 --protocol tcp --port 22 --cidr <suspicious-cidr>
   aws ec2 authorize-security-group-ingress --group-id sg-065fb018e22aa18a5 --protocol tcp --port 22 --cidr <legitimate-admin-ip>/32
   ```
2. If the key itself (not just the security group) is suspected compromised, this is more serious than a
   simple re-lock — proceed to credential rotation below before doing anything else on the box.

### Investigation
- `last` and `journalctl -u sshd --since "<window>"` on the instance for actual login history.
- Diff the live `~/apps/karosl` working tree against what `git log` says should be there — anything
  modified outside a recorded deploy is a red flag.
- Check `~/.karosl-deploy-history` against GitHub Actions' own run history — a discrepancy (a deploy
  recorded locally that GitHub has no matching run for) suggests direct, non-CI/CD server access was used.

### Recovery procedure — SSH key rotation
1. Generate a new keypair locally (never on the compromised instance): `ssh-keygen -t ed25519 -f
   karosl-staging-key-new`.
2. **Because the instance may itself be untrusted, prefer re-provisioning over trying to update
   `authorized_keys` on a possibly-compromised box** — treat this as EC2 failure recovery
   (`docs/runbooks/01-ec2-failure.md`) with a **new** keypair from the start, rather than trying to clean the
   existing instance. This also naturally forces the `.env` secrets rotation described there, which you want
   anyway if SSH access is suspected compromised (assume `.env` was read).
3. If full re-provisioning isn't warranted (e.g. the CIDR was merely widened by mistake, key itself not
   proven compromised): update `~/.ssh/authorized_keys` on the instance with the new public key, confirm the
   new key works, **then** remove the old key.
4. Terminate any other sessions: `pkill -KILL -u ec2-user -f sshd` (careful — this also kills your own
   session if you're logged in as the same user; do this from a fresh connection with the new key first).

### Verification
`./scripts/verify-staging.sh` to confirm the application itself is still healthy after any lockout/rotation
steps. Confirm the old key no longer authenticates.

### Rollback
Re-provisioning has no rollback (it's a forward-only replace). A simple security-group tightening can be
reversed by re-adding the legitimate CIDR if it was accidentally over-restricted.

### Escalation
Given SSH access implies `.env` access, always also run Scenario A's investigation for the RDS application
credential and consider it compromised too — rotate the RDS password as part of this response, not as a
separate later task.

---

## Scenario C: Compromised GitHub credentials

### Symptoms
- Commits/pushes to `cloud-deployment` or `dev` you don't recognize.
- GitHub Secrets modified, or new ones added.
- Unexpected changes to `.github/workflows/*.yml` (a classic supply-chain attack vector — a modified
  workflow can exfiltrate secrets or deploy arbitrary code).
- New collaborators added to the repo, or repo settings changed.

### Severity
**Critical** — the repo is public and this workflow has deploy access to the live instance (via the
self-hosted runner). A compromised GitHub account with push access is close to a compromised production
environment.

### Immediate actions
1. From a known-good device, revoke the compromised account's active sessions: GitHub Settings → Sessions →
   sign out of all other sessions. Rotate that account's password and any Personal Access Tokens
   immediately.
2. **Check `.github/workflows/*.yml` for unauthorized changes first** — this is the highest-leverage thing
   an attacker with push access could have done, since the self-hosted runner executes whatever the workflow
   file says on every push to `cloud-deployment`. Diff against the last known-good commit.
3. If a malicious workflow change reached `cloud-deployment` and may have already run: treat the EC2
   instance as compromised (Scenario B territory) — a malicious workflow run on the self-hosted runner has
   the same access as any legitimate deploy.

### Investigation
- GitHub's own audit log (repo Settings → or org-level if applicable) for the account's recent actions.
- `git log` on `cloud-deployment` and `dev` for any commit outside expected activity.
- Check GitHub Actions run history for any run that doesn't correspond to a real, intended push.

### Recovery procedure
1. Revert any unauthorized commits (`git revert`, not `git reset --hard`, to preserve history for
   investigation).
2. Rotate the compromised account's GitHub credentials (password, 2FA re-enrollment, regenerate any PATs).
3. **Reuse the already-proven CI-deploy-key rotation pattern** (`docs/CI_CD.md`) if any deploy-related
   secret might have been exposed: generate new credential material → add alongside the old (don't remove
   yet) → verify a deploy still succeeds → only then remove the old credential. This "add-verify-remove"
   sequence avoids a self-inflicted outage from rotating too aggressively.
4. If the self-hosted runner may have executed anything malicious, treat the EC2 instance as compromised —
   follow `docs/runbooks/01-ec2-failure.md` with a full re-provision rather than trying to "clean" it.

### Verification
Confirm `.github/workflows/*.yml` matches the last known-good version exactly. Confirm a normal deploy still
succeeds end-to-end (`./scripts/verify-staging.sh` after the next legitimate push).

### Rollback
`git revert` is itself the rollback mechanism for unauthorized commits — always additive, never rewrites
history that others (or CI) may have already acted on.

### Escalation
A compromised GitHub account with push access to a public repo that controls a live deployment pipeline is
a whole-system-trust incident — treat AWS credentials (Scenario D) as compromised too until proven
otherwise, since deploy pipelines often have implicit access to infrastructure secrets.

---

## Scenario D: Compromised AWS credentials

### Symptoms
- `aws cloudtrail` (if enabled — **status unknown from this documentation set, verify directly against the
  account**) shows API calls you don't recognize.
- Unexpected resources in the account (new instances, new IAM users/roles, modified security groups).
- AWS Budget alerts firing unexpectedly (a compromised account is sometimes used for cryptomining or other
  resource abuse).
- The SNS topic (`karosl-staging-alerts`) shows subscription changes you didn't make.

### Severity
**Critical** — AWS account access can reach everything: RDS (read/modify/delete, though deletion protection
mitigates the last one), S3 backups, EC2, IAM.

### Immediate actions
1. From the AWS root account or an unaffected IAM identity, **deactivate the compromised IAM
   user/role's access keys immediately**: `aws iam update-access-key --access-key-id <key-id> --status
   Inactive --user-name <user>`. Deactivate, don't delete yet — deletion removes the ability to audit what
   the key was used for.
2. Check IAM for any new users, roles, or policy attachments created since the suspected compromise window —
   `aws iam list-users`, `aws iam list-roles` sorted by `CreateDate`. Remove anything unauthorized once
   confirmed.

### Investigation
- CloudTrail (if enabled) for the full API call history under the compromised credential.
- `aws s3api list-objects-v2` on the backup bucket, checked against expected daily objects — confirm no
  backups were deleted (the backup IAM role deliberately has no `s3:DeleteObject`, so if backups *are*
  missing, that's a strong signal a different, more privileged credential was used, not the backup role
  itself).
- RDS: confirm deletion protection is still enabled (`aws rds describe-db-instances --query
  'DBInstances[].DeletionProtection'`) — this is the strongest safeguard against a compromised credential
  actually destroying the database.

### Recovery procedure
1. Rotate every credential the compromised identity had access to use or view — this likely includes the
   RDS password (visible in `.env` if the credential had EC2/SSM access) and any other secrets that
   identity's permissions could have reached.
2. Review and tighten IAM policies if the compromise was enabled by overly broad permissions (e.g. a key
   with more access than its actual use case needed).
3. If any AWS resource was modified or created illegitimately, remove/revert it, documenting exactly what
   was found and changed.

### Verification
`aws sts get-caller-identity` with the deactivated key should fail. Confirm the application itself is
unaffected (`./scripts/verify-staging.sh`) if no infrastructure was actually touched by the attacker beyond
credential access.

### Rollback
Reactivating a deactivated (not yet deleted) access key is possible if containment turns out to have been a
false alarm — prefer deactivation over immediate deletion for exactly this reason.

### Escalation
This is the most severe scenario in this runbook — if in doubt about scope, treat the entire AWS account as
compromised rather than trying to scope it narrowly. Consider engaging AWS Support (if on a support plan)
for guidance on account-level compromise response.

---

## Scenario E: Suspicious database activity

### Symptoms
- Unexplained data changes with no corresponding audit log entry (suggests access outside the application
  layer — see the audit log's known gap in `docs/runbooks/05-database-corruption.md`).
- Unexpected connections to RDS visible via CloudWatch (if RDS-level connection monitoring were in place —
  currently it is not, see `docs/DISASTER_RECOVERY.md` remaining risks; this is a real gap for detecting
  this specific scenario).
- Unusual query patterns or load reported by the application (slow queries, unexpected lock contention).

### Severity
**Critical** — direct database access outside the application layer bypasses every permission check KarosL
enforces at the API level.

### Immediate actions
1. RDS is `PubliclyAccessible: false` and reachable only from the EC2 security group by reference — so
   direct external database access should not be possible at all under normal configuration. **First confirm
   this hasn't changed**: `aws rds describe-db-instances --query 'DBInstances[].PubliclyAccessible'` should
   return `false`. If it returns `true`, that itself is the incident — someone changed it — revert
   immediately (`aws rds modify-db-instance --no-publicly-accessible --apply-immediately`).
2. If the database is still correctly private, the access must have come through the EC2 instance itself —
   treat this as Scenario B (compromised SSH/instance access) investigation in parallel.

### Investigation
- Same as Scenario A/B — the audit log for anything explainable, CloudWatch Logs for application-layer
  request patterns, and `last`/`journalctl` on the instance for direct access.
- Restore the most recent backup into a disposable database (`docs/runbooks/03-s3-backup-recovery.md`) and
  diff it against current live data to precisely characterize what changed and when, if the scope is
  unclear.

### Recovery procedure
Follow `docs/runbooks/05-database-corruption.md`'s Case B/C procedure to repair affected data, combined with
Scenario B/D's credential rotation for however access was actually obtained (this scenario is a symptom, not
its own root cause — the root cause is always one of A–D).

### Verification
Confirm `PubliclyAccessible` is `false`. Confirm no anomalous connections remain (would require RDS
connection-count monitoring, which — flagged honestly — doesn't currently exist; this is the clearest
argument for adding the RDS-specific CloudWatch alarms recommended in `docs/DISASTER_RECOVERY.md`'s next
sprint).

### Rollback
N/A — this scenario's "rollback" is the data-corruption repair procedure it's combined with.

### Escalation
Always combine this with whichever of Scenarios A–D actually explains *how* access was obtained — this
scenario alone only describes the symptom.

---

## Lessons learned (fill in after a real incident or a tabletop drill)
_This runbook has not been exercised. The first real use — incident or deliberate tabletop walkthrough —
should record here: which steps were unclear or missing, whether CloudTrail was actually enabled (verify
this independently of this document, since its status is unknown from the existing docs), and how long
containment actually took in practice._
