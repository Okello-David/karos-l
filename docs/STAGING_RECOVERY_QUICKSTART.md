# Staging Recovery Quickstart

Fast, self-service reference for the one recurring issue: **the app is unreachable, or you just
stopped/started the staging EC2 instance.** Run these from your own terminal, on your own machine —
you already have everything needed (AWS CLI credentials, the SSH key, the scripts below), no Claude
session required.

For anything beyond this scenario, see `docs/ADMIN_RUNBOOK.md` (quick command index) or
`docs/DISASTER_RECOVERY.md` / `docs/runbooks/` (deeper procedures).

## Step 1 — check status

```bash
cd ~/Karos_L   # or wherever your checkout lives
./scripts/verify-staging.sh
```

Read-only, safe to run anytime. Ends with `N/12 checks passed`.

- **12/12, "Staging is up."** → nothing to do.
- **Anything less** → almost always the stale-hostname problem below. Go to Step 2.

## Step 2 — fix it

```bash
./scripts/recover-staging.sh
```

One command does the whole thing: starts the instance if needed, repairs `.env` origins, re-issues
both TLS certificates (hostname + IP), recreates the containers, sweeps orphaned old certs, and
re-verifies from outside. It never touches the database, backups, or application data.

**If it stops with an SSH warning** like:

```
[warn] The SSH rule allows X.X.X.X/32, but your workstation is Y.Y.Y.Y.
[error] SSH will fail. Re-run with --fix-ssh, ...
```

your own workstation's IP has also changed since the security group was last updated. Re-run with:

```bash
./scripts/recover-staging.sh --fix-ssh
```

This is the only flag that modifies the security group, which is why it's opt-in rather than
automatic — only pass it when you actually see that warning.

Other flags: `--no-start` (skip the instance-start step if it's already running), `--dry-run` (show
what would happen, change nothing).

## Step 3 — confirm

The script prints the working URL(s) at the end, e.g.:

```
https://13-62-223-91.sslip.io   (login: karosadmin)
https://13.62.223.91            (same app, bare-IP path)
```

- The **`sslip.io` hostname URL** is the one to bookmark/share — its certificate lasts ~90 days.
- The **bare-IP URL** is a fallback path with a short-lived certificate (~7 days) by design — expect
  it to need reissuing more often; that's normal, not a problem.
- Both URLs change on every stop/start (no Elastic IP, a deliberate cost decision) — re-run this
  same procedure whenever that happens.

## If something's still wrong

`./scripts/verify-staging.sh` reports which specific layer failed (TLS, API, SPA, auth boundary,
etc.) — match that against the failure table in `docs/ADMIN_RUNBOOK.md`, or go straight to the
relevant `docs/runbooks/` procedure for anything that isn't a simple IP-change recovery.
