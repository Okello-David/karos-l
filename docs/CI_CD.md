# CI/CD

Status: **live and verified end-to-end since 2026-08-20.** `git push` to `cloud-deployment` now tests,
build-validates, and deploys to the live pilot automatically. This reverses a deliberate earlier choice —
`.github/workflows/ci.yml`'s own header comment used to say "deployment stays manual and deliberate" —
made when the repo went public and before there was a safe, scoped way to hand a workflow real credentials.
This doc is the reference for how that's now done safely.

## 0. Update — self-hosted runner pivot, production-readiness audit (2026-08-20)

**Sections 1–4 and 14 below describe the original SSH-deploy-key design as built 2026-08-19. That design
was superseded the next day, before it had ever actually run in GitHub Actions, and is kept below only as
a historical record — the current, live mechanism is the self-hosted runner described here.**

The pipeline's first-ever real run (this doc's original §14 tested everything manually, over SSH from the
operator's own machine — it never actually validated a connection from GitHub's own infrastructure) failed
immediately at the SSH host-key step. Root cause: the EC2 security group allows SSH only from the
operator's own `/32` (`docs/AWS_STAGING_CHECKLIST.md` §2a) — correct and deliberate — but GitHub-hosted
runners connect from thousands of dynamic IPs that were never going to be on that allowlist. GitHub's own
published IP ranges for Actions (`https://api.github.com/meta`, `actions` key) total **5,645 IPv4 CIDRs**
(7,280 with IPv6) — far beyond what an EC2 security group can hold (AWS caps out around 1,000 rules with a
quota increase, default 60), so widening the security group to cover them isn't viable.

**Fix: a self-hosted GitHub Actions runner, installed as a systemd service directly on the EC2 instance**
(label `karosl-staging`, package `actions-runner-linux-x64-2.336.0`, run as `ec2-user`). It polls GitHub
outbound — no inbound security-group change needed at all. The `deploy` job now runs its command directly
on the instance (no SSH hop, no deploy key); a new `smoke-test` job stays on a GitHub-hosted runner
specifically so external reachability is still verified from outside the box over the real HTTPS path, not
just a loopback check from the same machine that just deployed.

**Security invariant, load-bearing and documented directly in the workflow header**: the self-hosted
runner must never be reachable from any workflow triggerable by a `pull_request` from a fork — this repo is
public, and a self-hosted runner reachable from a fork's PR workflow is a remote-code-execution path onto
the live pilot instance. `ci.yml` (which does run on PRs from anyone) stays on `ubuntu-latest` and was
confirmed to have zero references to the `karosl-staging` label. `deploy-staging.yml` is safe because its
only trigger is `push: branches: [cloud-deployment]` — no `pull_request` trigger of any kind, so only
someone who can already push to that branch can reach the runner.

**Retired 2026-08-24**: `EC2_DEPLOY_KEY`/`EC2_USER` (the old SSH deploy key and its forced-command
entrypoint, `scripts/ci-deploy-entrypoint.sh`) were no longer used by CI as of this change, and were
confirmed to have zero remaining references anywhere in `.github/workflows/*.yml` or any script before
removal — the self-hosted runner deploy job runs `deploy-staging.sh --pull` directly on the instance, no SSH
hop of any kind. `scripts/ci-deploy-entrypoint.sh` was deleted; the `EC2_DEPLOY_KEY` and `EC2_USER` GitHub
Secrets were deleted (`gh secret delete`). **`EC2_HOST` was deliberately kept** — it's still actively read
by the `smoke-test` job (`curl ... secrets.EC2_HOST`), unrelated to the old SSH mechanism. **Known
limitation**: the old key's corresponding `authorized_keys` line on the EC2 instance itself (if it still
exists there) was not verified or removed as part of this — that requires direct SSH access to the
instance, which the environment doing this cleanup pass did not have (correctly — the security group only
allows the account owner's own `/32`). Recommended manual follow-up for the account owner: `ssh` in and
check `~/.ssh/authorized_keys` for a forced-command line referencing the deleted key, remove it if present.

**A second real bug was caught by this run**, after the network fix: `scripts/deploy-staging.sh`'s
password sanity check (§5/§14 below) required `POSTGRES_PASSWORD` to equal `DB_PASSWORD` unconditionally —
true only on the container-Postgres path, where `POSTGRES_PASSWORD` configures that same container. Since
the RDS migration (`docs/RDS_MIGRATION.md`), `DB_PASSWORD` is a separate, deliberately different RDS
credential, so this check `die`d on every deploy once RDS was live. Fixed by gating the check on the same
`$_db_host` condition already used for the RDS compose overlay immediately above it in the script.

**First fully green run, with both bugs fixed**: all six jobs passed — backend (SQLite + Postgres),
frontend, Docker build, deploy (on the self-hosted runner), and the external smoke test — confirmed via
`gh run watch` and independently via `./scripts/verify-staging.sh` (12/12) immediately after.

## 1. Current deployment, before this work (Task 1)

For context — this is what existed and what changed:

| | Before | After |
|---|---|---|
| Repository location (workstation) | `/home/david11/Karos_L` | unchanged |
| Deployment directory (EC2) | `/home/ec2-user/apps/karosl` | unchanged |
| How the server gets code | Manual `scp` or `git pull` over SSH, by a human | `git pull` inside `scripts/deploy-staging.sh`, triggered automatically by GitHub Actions **or** still runnable by hand exactly as before |
| `.env` location | `~/apps/karosl/.env` on the instance, never committed | unchanged |
| Deploy command | `./scripts/deploy-staging.sh --pull`, run by hand over SSH with the operator's own key | Same script, same command — now also invoked by CI over a separate restricted key |
| Restart behavior | `docker compose build && up -d` (recreates changed containers, no full teardown) | unchanged, but now **always** includes the HTTPS + CloudWatch overlays (see the incident below — this was a real gap, not always true before) |
| Rollback | None — would have meant manually checking out an old commit and rebuilding by hand | `scripts/rollback-staging.sh`, new |

## 2. A real incident during this work, fixed before shipping

Worth recording plainly rather than glossing over, since it's exactly the kind of mistake this whole
CI/CD effort exists to prevent happening silently in production later:

**While manually testing the newly-extended `deploy-staging.sh` on the live instance, running it exactly as
its own header comment always documented (`docker compose build && docker compose up -d`, no `-f` flags)
dropped port 443 entirely** — the script, in every version before and during this work, never applied the
`docker-compose.https.yml`/`docker-compose.cloudwatch.yml` overlays that staging actually depends on. HTTPS
was down for several minutes before being caught by an external check and fixed. Root cause and fix:

- `scripts/deploy-staging.sh` and `scripts/rollback-staging.sh` now build a `COMPOSE_FILES` array,
  detecting which overlay files are actually present, and use it for **every** `docker compose` invocation
  (`build`, `up -d`, `ps`, `exec`) — never a bare `docker compose` again. In `rollback-staging.sh` this check
  deliberately runs *after* the `git checkout` to the rollback target, not before, so it reflects what that
  specific commit actually ships, not whatever was checked out when the script started.
- A **second**, related bug was found while re-verifying the fix: with the HTTPS overlay active,
  `SECURE_SSL_REDIRECT` makes port 80 301 to 443 for everything except `/healthz` — so the script's internal
  health check, which hit plain `http://localhost/api/health/`, was fetching a redirect page instead of the
  real response. `curl -f` does **not** treat a 301 as failure, so the script was reporting deploy success
  without ever having actually reached Django. Fixed by checking response **content**
  (`grep '"status":"ok"'`), the same pattern `scripts/verify-staging.sh` already used correctly for the
  external check — and by checking `https://localhost/...` (with `-k`, safe for a loopback check on the box
  itself) when the HTTPS overlay is active.

Both fixes were verified for real afterward: a subsequent deploy correctly kept port 443 up and the health
check correctly returned `{"status":"ok","database":"ok"}` instead of an HTML redirect page.

A **third** bug turned up testing `rollback-staging.sh`: its dirty-working-tree guard checked
`git status --porcelain`, which flags *untracked* files the same as real uncommitted modifications — but
`git checkout` never touches untracked files, so a harmless `.env.bak-*` file sitting in the repo root
(there were several, left over from earlier stop/start recoveries) made the script refuse to run at all.
Fixed to check tracked-file modifications specifically. See §14 for the full test log, including a second
occurrence of the port-443 incident caused by rolling forward before the first fix was committed — the
concrete reason this work is committed and pushed promptly rather than left as local patches.

## 3. Pipeline (Task 2)

Two workflows, deliberately not chained via `workflow_run` (simpler to reason about independently, at the
cost of some duplicated steps):

- **`.github/workflows/ci.yml`** — `dev` branch and all PRs. Backend tests (SQLite+PostgreSQL matrix),
  frontend lint/test/build, Docker build validation. Read-only, no deploy credentials, unchanged in spirit
  from before this work — `cloud-deployment` was removed from its trigger so the same push doesn't run the
  suite twice.
- **`.github/workflows/deploy-staging.yml`** — `cloud-deployment` push only, never PRs, never other
  branches. Stages: checkout → backend tests → frontend tests+build → Docker build validation → (all three
  must pass, via `needs:`) → SSH deploy → smoke test → pass/fail. **Tests failing blocks deployment
  outright** — the `deploy` job cannot start until `backend`, `frontend`, and `docker` all succeed.

## 4. Deployment credentials (Task 3)

A **dedicated** SSH key, not the operator's own `karosl-staging-key`:

```bash
ssh-keygen -t ed25519 -f karosl-deploy-key -C karosl-ci-deploy -N ""
```

Public half installed as a **second, restricted** line in `~/.ssh/authorized_keys` on the instance:

```
command="/home/ec2-user/apps/karosl/scripts/ci-deploy-entrypoint.sh",no-pty,no-X11-forwarding,no-agent-forwarding,no-port-forwarding ssh-ed25519 AAAA... karosl-ci-deploy
```

The `command=` forced-command restriction means **whatever the client requests, sshd runs the entrypoint
script instead** — so a leaked deploy key's blast radius is "can trigger a deploy of `cloud-deployment`," not
"arbitrary shell on the box." `scripts/ci-deploy-entrypoint.sh` is the only thing that command can ever be;
it `exec`s `deploy-staging.sh --pull` and logs (never executes) whatever the client actually asked for.

Private half → GitHub Secret, piped directly from the keyfile so it never appears in a terminal, chat
message, or shell-history argument:

```bash
gh secret set EC2_DEPLOY_KEY < karosl-deploy-key
```

**GitHub Secrets** (exactly these three — nothing added beyond what's required):

| Secret | Value |
|---|---|
| `EC2_HOST` | The instance's current public IP |
| `EC2_USER` | `ec2-user` |
| `EC2_DEPLOY_KEY` | The restricted key's private half |

**Rotation**: generate a new pair → add its public half as a *second* CI-key line in `authorized_keys`
(don't remove the old one yet) → `gh secret set EC2_DEPLOY_KEY` with the new private half → push a harmless
commit and confirm `deploy-staging.yml` succeeds with the new key → only then remove the old key's line from
`authorized_keys`. Never a gap where neither key is trusted.

**`EC2_HOST` and IP churn**: the instance has no Elastic IP (`docs/HTTPS_IP_CERTIFICATE.md`,
`docs/PROJECT_STATE.md`) — this secret can go stale if the instance is ever stopped/started. It's
deliberately *not* solved with new IP-discovery automation here (would be new complexity for a problem the
instance is supposed to not have anymore, now that it stays running continuously during Live Pilot). If it
ever does happen: `gh secret set EC2_HOST` with the new IP before the next deploy.

## 5. Deployment script (Task 4)

`scripts/deploy-staging.sh` — extended, not rewritten, from the version that already existed:

1. `.env` sanity checks (unchanged, pre-existing)
2. **New**: branch verification — refuses to deploy unless checked out on `cloud-deployment`
   (`--branch=<name>` overrides for a deliberate manual deploy of something else)
3. Optional `git pull --ff-only` (`--pull`, pre-existing)
4. **New**: pre-deploy backup via `scripts/backup-to-s3.sh` (`--no-backup` to skip for fast manual
   iteration — always on for CI)
5. `docker compose build`, now always with the correct overlay files (§2)
6. `docker compose up -d`, same file set
7. Wait for container health (pre-existing)
8. **New**: explicit `docker compose exec backend python manage.py migrate --noinput` — redundant with the
   entrypoint's own automatic migration (harmless; Django migrations are idempotent) but gives migration
   output its own clearly-labeled section in CI logs (Task 7)
9. Content-based `/api/health/` check (fixed during this work — §2)
10. **New**: records `<timestamp> <sha>` to `~/.karosl-deploy-history` on success — `rollback-staging.sh`
    reads this

## 6. Rollback (Task 5)

`scripts/rollback-staging.sh` — new. Reads the entry before the current one in
`~/.karosl-deploy-history` (or an explicit `--to=<sha>`), checks it out (detached HEAD — a rollback target
is a specific point in history, not a branch), rebuilds, restarts, health-checks. **Never touches the
database, volumes, or runs `down -v`.**

**Real limitation, documented rather than papered over**: this is code-only rollback. There is no container
registry (§8), so it's "rebuild the old commit," not an instant image swap — and there is no automated
migration *downgrade*. If a migration was applied since the rollback target, older code may not match the
current database schema. The script warns and pauses (5s, `Ctrl-C` to abort) rather than guessing at an
automated downgrade, which would risk being genuinely destructive to real data — exactly the kind of
"rollback that's worse than the problem" this work is trying to avoid.

```bash
./scripts/rollback-staging.sh              # roll back to the previous recorded deploy
./scripts/rollback-staging.sh --to=<sha>   # roll back to a specific commit
```

## 7. Health check (Task 6)

The existing `/api/health/` endpoint (`{"status":"ok","database":"ok"}`), checked twice per deploy: once
internally by `deploy-staging.sh` on the instance itself, once externally by `deploy-staging.yml`'s smoke
test step from the GitHub Actions runner, over the real HTTPS path — the way an actual user reaches the app,
not just "the box can see itself." Both checks are content-based (§2), not exit-code-based.

If the smoke test fails: the workflow run is marked failed, its logs (including the deploy step's full
output) are preserved in the GitHub Actions UI. **Automatic rollback on smoke-test failure is deliberately
not wired up** — `rollback-staging.sh` exists and is documented, but triggering it automatically on any
smoke-test failure risks compounding a real problem with an unattended rollback attempt during an incident.
Run it by hand once the failure is understood.

## 8. Migrations (Task 7)

Already automatic before this work: `backend/docker-entrypoint.sh` runs `migrate --noinput` before Gunicorn
starts, so a failed migration already prevents the container from ever becoming healthy — the deploy fails
at the "wait for health" step regardless. What's new: an explicit, visible migration step in
`deploy-staging.sh` (§5, step 8) so migration output gets its own labeled section in CI logs instead of
being buried inside container startup output. No destructive migration operations are run automatically —
`migrate --noinput` only ever applies forward migrations already committed to the codebase; it does not
generate, squash, or reverse anything.

## 9. Docker architecture (Task 8)

Unchanged: build on EC2, no registry, `docker compose up -d` restarts changed containers.

| | |
|---|---|
| **Pros** | Simple — one less moving part (no registry auth, no image push/pull step); inexpensive — no ECR/registry cost; easy to understand — the CI deploy step is the same command an operator would type by hand |
| **Cons** | Build workload runs on the `t3.micro` itself (a few minutes, not free CPU); slower deployment than an image-swap (rebuild vs. pull-and-restart); not how a larger production deployment would want to scale — a registry + image-only deploy is the natural next step if/when that matters |

Explicitly not introduced: a container registry, ECS/Fargate, or any other AWS service beyond what already
exists — matches this task's own constraints.

## 10. Branch strategy (Task 9)

There is no `main` branch in this repository — `dev`, `cloud-deployment`, `UI_UX`, and `test` exist.
**`cloud-deployment` plays the role "main → staging" would play** in the brief's example: it's where every
infrastructure change has actually landed, and is now the sole trigger for `deploy-staging.yml`.

```
feature/dev work  →  pull request  →  ci.yml (tests)  →  merge to dev
                                                              ↓
                                          (deliberately, a human decides when
                                           to bring dev's changes into
                                           cloud-deployment — not automatic)
                                                              ↓
                                     push to cloud-deployment  →  deploy-staging.yml
                                                                   (tests + build + deploy)
```

**A feature branch is never auto-deployed** — `deploy-staging.yml`'s trigger is `push: branches:
[cloud-deployment]` only, no PR trigger, no wildcard branches.

## 11. Concurrency safety (Task 10)

```yaml
concurrency:
  group: staging-deploy
  cancel-in-progress: false
```

Only one `deploy-staging.yml` run proceeds at a time; a second push while one is running **queues** rather
than cancelling — interrupting a deploy mid-build or mid-restart is worse than a short wait.

## 12. Notifications (Task 11)

GitHub Actions' own check UI only — no email/SMS/Slack infrastructure added. Each stage (backend tests,
frontend tests, Docker build, deploy, smoke test) is its own job/step, so pass/fail for each is visible
individually in the run summary, not collapsed into one opaque "CI" status.

## 13. Secrets and security review (Task 12)

**This table describes the review as performed on 2026-08-19, against the original SSH-deploy-key design —
kept as a historical record (see §0). It is stale in two specific ways as of the 2026-08-24 operational
cleanup: `deploy-staging.yml` never actually used `webfactory/ssh-agent` (no such step exists anywhere in
the current or historical workflow — that line was inaccurate even at the time), and the GitHub Secrets set
changed on 2026-08-24 when `EC2_DEPLOY_KEY`/`EC2_USER` were retired (§0).**

| Check | Status (as of 2026-08-19) |
|---|---|
| `.gitignore` covers `.env`, `backend/.env`, `frontend/.env` | ✅ already true, unchanged |
| No `.env` committed | ✅ confirmed via `git log --all -p -- '*.env'`, clean |
| No private key committed | ✅ the deploy key was generated to a scratch path outside the repo, never written into it |
| No passwords in scripts | ✅ every script in this repo reads credentials from the container's own environment or GitHub Secrets, never hardcodes or echoes them |
| No tokens printed in CI logs | ✅ GitHub automatically masks registered secret values in logs; `deploy-staging.yml` never echoed `EC2_DEPLOY_KEY` |
| Deploy key scope | ✅ forced-command restricted (§4) — cannot be used for arbitrary shell access even if leaked |
| GitHub Secrets | `EC2_HOST`/`EC2_USER`/`EC2_DEPLOY_KEY`, confirmed via `gh secret list` at the time — **as of 2026-08-24, only `EC2_HOST` remains** (§0) |

## 14. Testing performed before enabling automation (Task 13)

1. Manually ran the extended `deploy-staging.sh` via the operator's own admin key first — this is what
   caught both bugs in §2, *before* any CI involvement, exactly the point of testing manually first.
2. Fixed both bugs, redeployed the scripts, reran manually — confirmed port 443 stayed up and the health
   check returned real content (`{"status":"ok","database":"ok"}`, not a redirect page) this time.
3. Generated and installed the restricted CI deploy key; confirmed `gh secret list` shows exactly the three
   expected secrets, nothing more.
4. **Reconciled the server's git state** to match `origin/cloud-deployment` (it had drifted — every file
   this whole session had been delivered by `scp`, not `git pull`, so the server's `HEAD` was five commits
   behind what was actually running). Necessary before `--pull`-based deploys could be tested meaningfully.
5. **Tested the restricted CI key directly**: connected and requested `id; whoami; echo
   THIS_SHOULD_NEVER_PRINT` — none of that output appeared; the forced command ran instead, and
   `THIS_SHOULD_NEVER_PRINT` is confirmed absent from the transcript. `journalctl -t karosl-ci-deploy`
   confirms the ignored request was logged: `CI key connected; original request ignored: id; whoami; echo
   THIS_SHOULD_NEVER_PRINT`. The deploy the forced command triggered succeeded end to end, port 443 intact.
6. **Tested `rollback-staging.sh` against a real prior commit** (`c80060f`, predating today's HTTPS/S3/
   CloudWatch work). Found and fixed a **third bug** in the process: its "refuse if the working tree is
   dirty" guard checked `git status --porcelain`, which flags *untracked* files (harmless `.env.bak-*`
   clutter, scratch scripts) the same as real uncommitted modifications — `git checkout` never touches
   untracked files at all, so this was a false positive that would have made the script unusable on any
   repo with routine scratch files present. Fixed to check tracked-file modifications specifically
   (`git diff --quiet && git diff --cached --quiet`). Re-tested: rollback succeeded, checked out the older
   commit, rebuilt, restarted, health-checked, confirmed the older nginx config was genuinely in effect (the
   bare-IP path no longer presented a matching certificate — expected, since that commit predates the
   dual-cert design), then rolled forward again.
7. **Rolling forward reproduced the exact §2 incident a second time** — `git checkout cloud-deployment`
   restored the *committed* (still-unfixed) version of `deploy-staging.sh`, since the fix existed only
   locally/stashed at that point, not yet pushed. Port 443 dropped again; caught immediately via the same
   external check pattern and restored. **This is the concrete reason the fix had to be committed and
   pushed promptly, not left as an uncommitted local patch**: until it's the canonical `git` state, every
   checkout/pull-based operation on the instance can silently reintroduce the exact bug it fixes.
8. All of the above run against the live pilot; live database row counts and both external HTTPS paths
   (`scripts/verify-staging.sh`) were reconfirmed clean after every step, including after both incidents.

## 15. Troubleshooting

**The two SSH-specific entries that used to be here ("deploy step fails at the SSH connection", "deploy
step connects but nothing happens") were removed 2026-08-24** — they described the retired SSH deploy
mechanism (§0) and no longer apply; the `deploy` job runs directly on the self-hosted runner, no SSH hop.

- **Self-hosted runner offline / deploy job stuck queued** — check the runner's systemd service is running
  on the instance (`sudo systemctl status actions.runner.*`), and that the instance itself is up
  (`./scripts/verify-staging.sh` or `aws ec2 describe-instances`).
- **External smoke test fails specifically** — it's the one job still on a GitHub-hosted runner and reads
  `EC2_HOST` via `curl`; confirm that secret matches the instance's current public IP
  (`aws ec2 describe-instances ...`) — the instance has no Elastic IP, so this can go stale after a
  stop/start (§0).
- **HTTPS or CloudWatch logging silently stops after any deploy** — check `docker compose ps` shows port
  443 published and check `docker inspect karosl-frontend-1 --format '{{.HostConfig.LogConfig.Type}}'` shows
  `awslogs`; if not, `COMPOSE_FILES` in `deploy-staging.sh`/`rollback-staging.sh` didn't pick up the overlay
  files — confirm `docker-compose.https.yml`/`docker-compose.cloudwatch.yml` exist in the repo root on the
  instance (§2's incident, guarded against but worth knowing how to recognize if it ever recurs).
- **Health check passes internally but the external smoke test fails** — likely a security-group or DNS/IP
  mismatch rather than an application problem; run `./scripts/verify-staging.sh` directly for the full
  12-check diagnostic.
- **Migration step fails** — `docker compose ... logs backend --tail 100` for the actual Django traceback;
  not destructive on its own (§8), but the deploy correctly fails rather than serving a broken schema.
- **Need to roll back** — `./scripts/rollback-staging.sh`, see §6 for the migration-compatibility caveat.

## 16. Cost

No new AWS resources — GitHub Actions runners are free-tier for a public repo; the self-hosted runner is a
systemd service on the already-running EC2 instance, not a separate resource. No new AWS API calls beyond
what `backup-to-s3.sh` already makes during the pre-deploy backup. Zero marginal AWS cost from this work.
