# AWS Staging Checklist

Status: **Executed 2026-07-29 — staging is live in `eu-north-1`.** Sections 1–3 are complete; Section 4 is partially verified (see the progress note below). This is the tick-list for KarosL's first AWS staging deployment (Phase 2 of `docs/AWS_DEPLOYMENT_PLAN.md`) — a single EC2 instance running the same Docker Compose stack already verified locally.

> **Deployment progress (2026-07-29).** §1 account safety: budget + alerts confirmed by the account owner before provisioning; region `eu-north-1`. §2 EC2 + security group: done — instance `i-0afd1871b46296500`, SG `karosl-staging-sg` (`sg-065fb018e22aa18a5`), auto-assigned public IP, no Elastic IP. §3 server setup: done, including a 2 GB swapfile and a buildx upgrade (see below). §4 verification: **infrastructure and unauthenticated checks pass; the authenticated workflow walkthrough is still outstanding** because the `karosadmin` password has not been set. §5 cleanup: not yet needed — remember to stop the instance between sessions.
>
> **Deviation from plan, worth knowing:** Amazon Linux 2023 ships Docker with buildx 0.12.1, but Compose v5 requires buildx ≥ 0.17.0, so `docker compose build` failed on first run. Fixed by installing a current buildx plugin; `scripts/server-setup.sh` now does this automatically. Full detail in `docs/AWS_EC2_DEPLOYMENT.md` §4.3b.

> ⛔ **GATE — Section 1 must be fully green before anything in Sections 2–3 is touched.**
> **No AWS deployment should proceed before budget alerts are configured.** Not the EC2 instance, not the security group, not an Elastic IP, not a test bucket. The budget is the first thing created in the account.

**Scope reminder:** this is **staging only**. No RDS, no load balancer, no NAT Gateway, no HTTPS, no real tenant data. Production is a later, separate decision (`docs/AWS_DEPLOYMENT_PLAN.md` Phases 3–6).

Step-by-step commands for Sections 3–4 live in `docs/AWS_EC2_DEPLOYMENT.md`. This file is the checklist; that file is the runbook.

---

## 1. AWS account safety *(the gate)*

- [ ] **AWS Budget created.** A monthly cost budget in AWS Budgets — suggested ceiling **$10–20/month** for staging (one small EC2 + one EBS volume + maybe one Elastic IP; no RDS, no ALB).
- [ ] **Budget email alerts configured** at **50% / 80% / 100%** of budget, plus a **forecasted-to-exceed** alert, to an email address that is actually read.
- [ ] **First alert email confirmed received.** Subscribing is not the same as working — confirm delivery (check spam) before trusting it.
- [ ] **Region selected and written down.** Pick one region and use it for everything; resources in another region are invisible on the console's default view and get forgotten while still billing. Choose the region closest to your users (e.g. `eu-west-1` Ireland, `eu-central-1` Frankfurt, or `af-south-1` Cape Town for East/Southern Africa — note `af-south-1` is an opt-in region and is **not** free-tier friendly for every instance type; verify pricing before choosing it).
- [ ] **Region recorded here:** `__________________`
- [ ] **MFA enabled on the root user.** Non-negotiable for any account with a payment method attached.
- [ ] **Root user not used for daily work.** Create an IAM user (or Identity Center user) with the access you need, enable MFA on it too, and use that.
- [ ] **Free Tier dashboard checked.** Know whether the account is inside its 12-month free-tier window and which instance classes qualify (`t2.micro`/`t3.micro`).
- [ ] **Cost Explorer enabled.** Plan to skim it weekly for the first month.
- [ ] **No NAT Gateway will be created.** The instance goes in a **public subnet** with a public IP. A NAT Gateway is ~$32/month, always on, and buys nothing for a single public web host.
- [ ] **No load balancer will be created.** An ALB is another ~$16–20+/month, always on. Staging is reached directly on the instance's public IP.
- [ ] **No RDS instance will be created** for this first staging deployment. PostgreSQL runs as the existing `db` container. RDS is a deliberate, later, explicitly-chosen step (Phase 3) — not a default.

## 2. EC2 plan

- [ ] **AMI chosen:** Amazon Linux 2023 **or** Ubuntu Server LTS (22.04/24.04). Both are fine; the setup commands differ slightly and both are given in `docs/AWS_EC2_DEPLOYMENT.md`.
- [ ] **Instance type: smallest that works.** Start at `t3.micro` (2 GB RAM) — or `t2.micro` if that is what your free tier covers. Note: the frontend image builds with `npm ci && npm run build`, which is memory-hungry; see the swap note in the deployment guide if a 1 GB instance OOMs during build. Resize up only on observed pressure.
- [ ] **Storage: keep the root EBS volume small** (8–20 GB gp3). EBS bills **even while the instance is stopped**.
- [ ] **Key pair created and the `.pem` saved somewhere safe** (`chmod 400`). Losing it means losing SSH access to the instance.
- [ ] **Security group created** with the rules in Section 2a below.
- [ ] **Public IPv4 assigned.** Either the auto-assigned public IP (free, but **changes on every stop/start**) or an Elastic IP (stable, free *only while attached to a running instance*). For staging that gets stopped nightly, the auto-assigned IP is cheaper — at the cost of updating `ALLOWED_HOSTS` and the URL each time.
- [ ] **Decision recorded:** auto-assigned IP ☐ / Elastic IP ☐

### 2a. Security group rules

**Inbound**

| Type | Protocol | Port | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | **My IP only** (`x.x.x.x/32`) | Administration. Never `0.0.0.0/0` — port 22 open to the world gets credential-stuffed within minutes of the instance booting. |
| HTTP | TCP | 80 | `0.0.0.0/0` | **Still required after HTTPS**: it carries the HTTP→HTTPS redirect and the Let's Encrypt `http-01` challenge, which runs at *every* renewal. Closing it breaks renewal silently, surfacing ~60 days later as an expired certificate. |
| HTTPS | TCP | 443 | `0.0.0.0/0` | ✅ **Open since 2026-07-31** (`sgr-0b29986c961ba61aa`) — TLS terminates at the frontend container's nginx. See `docs/DOMAIN_HTTPS_PLAN.md`. |

- [ ] SSH restricted to my IP (`__________/32`). If on a dynamic/ISP-rotated address, plan to update it — or use EC2 Instance Connect / SSM Session Manager instead of an open port.
- [ ] HTTP 80 open to `0.0.0.0/0`, and understood as temporary.
- [ ] **PostgreSQL port 5432 NOT in the inbound rules — at all.**
- [ ] Django's port 8000 not exposed either (see Section 3).

**Outbound**

- [ ] **Default outbound (all traffic allowed) left as-is.** The instance needs it to reach package repos, Docker Hub, and GitHub. Restricting egress is a hardening step worth taking later, once the exact set of destinations is known — locking it down before that just breaks `docker pull` in confusing ways.

### 2b. Why PostgreSQL must never be publicly exposed

A security group's inbound rules are the instance's firewall — they decide what the internet can reach. Opening 5432 to `0.0.0.0/0` would make the database directly reachable by anyone on the internet, and that is categorically different from exposing port 80:

- **The database is the whole asset.** HTTP exposes an app that enforces authentication, permissions (`IsPropertyManager`/`IsStaff`/`IsSuperAdmin`), throttling, and an audit trail on every write. Postgres exposed on 5432 bypasses all of it — every occupant record, payment, and receipt is one password away, with **no audit log entry** for the read.
- **A password is the only control.** There is no MFA, no lockout, no rate limit on a raw Postgres port. Automated scanners sweep 5432 across the entire IPv4 space continuously and will find the instance within hours of it being opened.
- **The app does not need it.** The `backend` container reaches Postgres over the **internal Docker Compose network** at hostname `db:5432`. That traffic never leaves the instance and is unaffected by any security group rule. Publishing the port to the host or the internet adds exactly zero application capability.
- **`docker-compose.yml` already gets this right** — the `db` service's `ports:` block is deliberately commented out, so Postgres is not even published to the EC2 host, let alone the internet.

**To inspect the database, use SSH as the transport**, never an open port: `docker compose exec db psql -U karosl_user -d karosl` over your SSH session, or an SSH tunnel (`ssh -L 5433:localhost:5432 ...`) if you want a GUI client. Both give full access with zero public attack surface.

The same reasoning applies to Gunicorn on 8000: it has no business being internet-reachable when Nginx is the front door.

## 3. Server setup

Commands: `docs/AWS_EC2_DEPLOYMENT.md`. Optional helper: `scripts/server-setup.sh`.

- [ ] **SSH in** as `ec2-user` (Amazon Linux) or `ubuntu` (Ubuntu), using the key pair.
- [ ] **System packages updated.**
- [ ] **Docker Engine installed** and the daemon enabled + started.
- [ ] **Docker Compose plugin installed** — verify with `docker compose version` (v2 syntax, no hyphen). The old `docker-compose` binary is not what this project uses.
- [ ] **Non-root Docker access configured** — user added to the `docker` group, then log out and back in (the group change does not apply to the current shell).
- [ ] **Git installed.**
- [ ] **App directory created** — `/opt/karosl` (root-owned, chowned to your user) or `~/karosl`. Pick one and be consistent.
- [ ] **Repository cloned** (or `git pull` on redeploy) at the intended branch/tag.
- [ ] **`.env` created manually on the server** — `cp .env.example .env` then edit. **Never** commit it, never `scp` it from a machine where it was committed, never paste it into a chat/ticket. Values per Section 3a.
- [ ] **`.env` permissions tightened** — `chmod 600 .env` (it holds the DB password and `SECRET_KEY`).
- [ ] **Containers built** — `docker compose build` (first build is slow; the frontend `npm ci` dominates).
- [ ] **Services started** — `docker compose up -d`.
- [ ] **Migrations confirmed applied.** They run automatically via `backend/docker-entrypoint.sh` on every backend start; confirm in the logs rather than assuming.
- [x] **Superuser created and password set** — `karosadmin` (2026-07-29), login verified through the public IP.

  To rotate it (recommended, since the initial value was set non-interactively):
  ```bash
  ssh -i ~/.ssh/karosl-staging-key.pem ec2-user@<EC2_PUBLIC_IP>
  cd ~/apps/karosl && docker compose exec backend python manage.py changepassword karosadmin
  ```
  Run it interactively so the value never lands in shell history, a script, or a transcript. Use a strong, unique password — **not** the local dev password, and **not** `demo`/`demo12345`.

  **Note on `docker compose exec -T`:** it reads stdin, so calling it inside a piped/heredoc script silently swallows the rest of that script. Always append `< /dev/null` when scripting a non-interactive `exec`.
- [ ] **All three services report `healthy`** — `docker compose ps`.

### 3a. Required `.env` values on the staging server

Full annotated values in `docs/AWS_EC2_DEPLOYMENT.md` §5. The four that differ from local and *will* bite you if missed:

- [ ] `FRONTEND_PORT=80` — the default is `8080`. Without this the app is at `http://<IP>:8080`, not `http://<IP>`.
- [ ] `ALLOWED_HOSTS=<EC2_PUBLIC_IP>,localhost,127.0.0.1,backend` — **keep `localhost`**. The backend container's Docker `HEALTHCHECK` curls `http://localhost:8000/api/health/`; drop `localhost` and the container is marked unhealthy forever even though the app works.
- [ ] `CSRF_TRUSTED_ORIGINS=http://<EC2_PUBLIC_IP>` and `CORS_ALLOWED_ORIGINS=http://<EC2_PUBLIC_IP>` — scheme included, **no trailing slash**, `http` not `https` for now.
- [ ] `SECRET_KEY` — freshly generated for staging, never the `django-insecure-...` placeholder.
- [ ] `POSTGRES_PASSWORD` and `DB_PASSWORD` set to the **same** strong value.
- [ ] `DEBUG=False`.
- [ ] `VITE_API_BASE_URL=/api` — left at the default. The Nginx reverse proxy handles it; an absolute URL would hardcode the IP into the JS bundle and force a rebuild on every IP change.

## 4. Verification

Run against `http://<EC2_PUBLIC_IP>` from your own browser, not from the server.

- [x] **`docker compose ps`** — `db`, `backend`, `frontend` all `Up` and `(healthy)`. ✅ 2026-07-29
- [x] **`curl http://<EC2_PUBLIC_IP>/api/health/`** → `{"status": "ok", "database": "ok"}`. This one call proves the whole chain: internet → security group → Nginx → Gunicorn → Postgres. ✅ 2026-07-29
- [x] **App loads** — the SPA renders at `http://<EC2_PUBLIC_IP>`. ✅ HTTP 200, `<title>KarosL</title>`, hashed asset bundle served.
- [x] **Deep-link refresh works** — `/dashboard` returns 200 via Nginx `try_files`. ✅ 2026-07-29
- [x] **API reachable and auth enforced** — `POST /api/auth/login/` with bad credentials returns a Django validation error (400), not a gateway error; `/api/properties/`, `/api/occupants/`, `/api/dashboard/` all return 401 unauthenticated. ✅ 2026-07-29
- [x] **Ports 8000 and 5432 unreachable from the internet.** ✅ verified externally
- [x] **Login works** with the superuser created above. ✅ 2026-07-29 — `POST /api/auth/login/` through the public IP returns a DRF token and the correct user object (`is_staff`/`is_superuser` true).
- [x] **Session persists** — the issued token remains valid across separate connections. ✅
- [x] **Dashboard loads** with live figures. ✅ returns real aggregates (`total_capacity`, `total_occupied`, `occupancy_rate`, `total_students`, `recent_payments`) and updated correctly after writes.
- [x] **Property creation works** ✅ — `POST /api/admin/properties/` → 201, persisted.
- [x] **Section + unit creation works** ✅ — section and a capacity-2 unit created under that property.
- [x] **Occupant creation works** ✅ — `POST /api/occupants/` → 201.
- [x] **Occupancy assignment works** ✅ — `POST /api/occupancy/` → 201, with correct `student_full_name` / `unit_name` / `property_name` denormalization.
- [x] **Over-capacity prevention works** ✅ — a third assignment to a capacity-2 unit was rejected: *"Unit 'A-101' is at full capacity (2)."*
- [x] **Payment workflow works** ✅ — payment recorded, receipt **auto-generated** (`RCP-2026-00002`), and the PDF downloads as a valid `application/pdf`.
- [x] **Property Explorer works** ✅ — full property → section → unit hierarchy with live occupancy counts (`2/2`, `1/2`, `0/3`).
- [x] **Logout works** ✅ — returns 200 and the token is immediately rejected (401) afterwards.
- [x] **Protected routes** ✅ — `/api/dashboard/`, `/api/properties/`, `/api/occupants/`, `/api/payments/`, `/api/admin/properties/`, `/api/audit/` all 401 without a token.
- [x] **Logs are visible and clean** ✅ — 0 backend tracebacks/ERRORs, 0 db FATALs, 0 nginx 5xx. (4xx count is non-zero and expected: the deliberate unauthenticated probes above.)
- [ ] **Data survives a container restart** — `docker compose restart`, confirm the property you created is still there.
- [ ] **Data survives an instance reboot** — `sudo reboot`, wait, SSH back in, confirm containers came back (`restart: unless-stopped`) and the data is intact. This is the one that actually tests the `postgres_data` volume.
- [x] **Staging data is test data only.** ✅ Only synthetic records (`Smoke Test Hostel`, `Karos Garden`, `Smoke Tester`, `Cap Two/Three`). No real tenant names or payment records.

> **Still to execute (2026-07-29):** the `pg_dump` backup drill (`docs/DEVOPS.md` §12) and the container-restart / EC2-reboot survival checks. The procedures are written and reviewed; they were not run in the verification pass. Both are quick and non-destructive apart from the reboot, which is safe given `restart: unless-stopped` and the `postgres_data` volume — but should be done with someone watching.

> **Smoke-test result (2026-07-29): 14/14 workflows pass**, plus the over-capacity guard. One initial failure — "assign occupancy" — was traced to a **bug in the test script, not the app**: `UID` is a readonly variable in bash, so `UID=$(...)` silently kept the shell's own uid (`1000`) and sent it as the unit primary key. Retried with a correctly-named variable and it passed.

## 5. Cleanup

Cost control is not a one-time act at creation; it is what you do when you stop using the thing.

**After each testing session (keeps the bill near zero):**
- [ ] `docker compose down` — stop containers, keep the data volumes.
- [ ] `docker system prune -f` — remove dangling images/build cache. Rebuilds accumulate layers fast on a small disk.
- [ ] **Stop the EC2 instance** in the console. You stop paying for compute immediately. You **still pay** for the EBS volume, and for an Elastic IP if one is attached to the now-stopped instance.
- [ ] Note: with an auto-assigned public IP, **the IP changes on the next start** — you must update `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`CORS_ALLOWED_ORIGINS` in `.env` and `docker compose up -d` again.

**When staging is finished for good:**
- [ ] **Back up anything you want to keep first** — `docker compose exec db pg_dump ...` and copy it off the instance. Termination is irreversible.
- [ ] **Terminate the EC2 instance.**
- [ ] **Delete the EBS volume** if it was not set to delete-on-termination. Orphaned volumes bill forever and are invisible unless you go looking on the Volumes page.
- [ ] **Release the Elastic IP** if one was allocated. An unassociated EIP is billed hourly — this is the single most common surprise line item.
- [ ] **Delete EBS snapshots** taken during testing.
- [ ] **Delete the security group and key pair** if they will not be reused (cosmetic; neither costs money).
- [ ] **Check Cost Explorer / the Billing page 24–48h later** and confirm the daily run-rate actually dropped to ~$0. Verify, don't assume.

---

## Cross-references

- `docs/AWS_DEPLOYMENT_PLAN.md` — the phased strategy, cost guardrails, and why this architecture.
- `docs/AWS_EC2_DEPLOYMENT.md` — the step-by-step command runbook for Sections 3–4.
- `docs/DEVOPS.md` — Docker architecture, env-var strategy, troubleshooting.
- `docs/DEPLOYMENT.md` — local build/run/verify mechanics.
