# AWS Deployment Plan

Status: **Planning only.** This document defines KarosL's AWS deployment architecture, cost controls, environment strategy, secrets handling, and exit path **before any cloud resource is provisioned.** Nothing in here has been deployed. No AWS account resources have been created as part of writing it.

It builds directly on the containerization work already delivered (`docs/DEVOPS.md`, `docs/DEPLOYMENT.md`) — KarosL already runs as a production-like Docker Compose stack (Nginx-served frontend → Gunicorn/Django backend → PostgreSQL), which is the foundation every phase below reuses.

> ⛔ **HARD RULE — read before touching the AWS console.**
> **No AWS resource may be created before an AWS Budget with email alerts is configured (Task 2).** This includes EC2, RDS, S3, Elastic IPs, and NAT Gateways. The budget is the first thing that gets created in the account, before anything that can cost money. This is not a suggestion — it is the gate for the entire phase.

---

## Required pre-deployment step (cost safety) — do this first, every time

**No AWS deployment should proceed before budget alerts are configured.** This section is the mandatory gate that sits in front of Phase 2 and every phase after it. Work through it top to bottom before the first resource is created; re-confirm items 1–3 before any later phase that adds a new billable service (RDS, S3, CloudWatch, ALB).

| # | Step | Why it is here |
|---|---|---|
| 1 | **Create an AWS Budget** — a monthly cost budget with an explicit ceiling (**$10–20/month** for the single-EC2 staging phase; $20–30 once RDS joins). | Without a ceiling there is no definition of "too much", so nothing can alert. |
| 2 | **Configure budget email alerts** at **50% / 80% / 100%** plus a **forecasted-to-exceed** alert, to an address that is actually read — and **confirm the first alert email arrives**. | Subscribing is not the same as working. An alert you never receive is not a guardrail. |
| 3 | **Confirm the region** — pick one, write it down, and create everything in it. | Resources in a forgotten region keep billing while being invisible on the console's default view. |
| 4 | **Confirm no NAT Gateway will be created** — the EC2 host goes in a **public subnet** with a security group, not behind private subnets + NAT. | ~$32/month, always on, plus per-GB data processing. Buys nothing for a single public web host. |
| 5 | **Use the smallest reasonable EC2 instance** — start at `t3.micro`/`t2.micro`; resize up only on observed pressure. | Instance size is the largest controllable line item in this architecture. |
| 6 | **Avoid a load balancer for staging** — reach the app directly on the instance's public IP. | An ALB is another ~$16–20+/month, always on, for a single-instance environment that gains no availability from it. |
| 7 | **Avoid RDS for the first staging deployment** unless explicitly chosen — PostgreSQL runs as the existing `db` container. | RDS is a real, deliberate step (Phase 3) taken when the data's value justifies it, not a default that quietly doubles the bill. |
| 8 | **Read the cleanup steps below before creating anything** — know how to turn it off before you turn it on. | Most surprise AWS bills come from resources nobody remembered creating. |

### Cleanup steps — how to stop and delete everything

Cost control is not a one-time act at creation; it is what you do when you stop using the thing.

**After each testing session (keeps the bill near zero):**

```bash
docker compose down          # stop containers, keep data volumes
docker system prune -f       # drop dangling images and build cache
```
Then **stop the EC2 instance** in the console. Compute charges stop immediately. You **still pay** for the EBS volume, and for an Elastic IP if one is attached to a stopped instance.

**When the environment is finished for good:**

1. **Back up anything worth keeping first** (`pg_dump`, copied off the instance) — termination is irreversible.
2. **Terminate the EC2 instance.**
3. **Delete the EBS volume** if it was not set to delete-on-termination. Orphaned volumes bill indefinitely and are invisible unless you go looking at the Volumes page.
4. **Release the Elastic IP** if one was allocated — an unassociated EIP is billed hourly, and is the single most common surprise line item.
5. **Delete EBS/RDS snapshots** taken during testing; they accumulate silently.
6. **Delete the RDS instance** (if Phase 3 was reached), deciding deliberately whether to keep a final snapshot — it also bills.
7. **Empty and delete S3 buckets** (if Phase 4 was reached); versioned buckets keep billing for old object versions until those are purged too.
8. **Set/verify CloudWatch log-group retention** (if Phase 5 was reached), or delete the log groups.
9. **Check Cost Explorer 24–48h later** and confirm the daily run-rate actually dropped to ~$0. Verify, don't assume.

The full operational tick-list for staging lives in `docs/AWS_STAGING_CHECKLIST.md` §5; the command-level runbook is `docs/AWS_EC2_DEPLOYMENT.md`.

---

## 1. Guiding principle: start simple, grow deliberately

KarosL is being deployed by a small team optimizing for **low cost, learnability, and reversibility**, not for scale it does not yet have. Every phase below is chosen so that the cheapest, simplest thing that could possibly work is tried first, and complexity is added only when a concrete need forces it.

Why start with a single EC2 box running the same Docker Compose stack we already run locally, instead of jumping straight to ECS/Fargate + RDS + ALB?

- **Lower cost.** One small EC2 instance (or the free-tier `t3.micro`/`t2.micro`) plus one Elastic IP is a few dollars a month or less. A production-grade ECS + ALB + multi-AZ RDS + NAT Gateway stack is $60–100+/month before any traffic — the ALB and NAT Gateway alone are ~$32/month **each**, always-on, whether or not anyone uses the app.
- **Easier debugging.** On a single EC2 host you can `ssh` in, run `docker compose logs`, `docker compose ps`, `docker compose exec backend ...` — the exact commands the team already uses locally. There is no orchestration layer, no task-definition indirection, no service-discovery to reason about when something breaks.
- **Better learning path.** The team already understands Docker Compose. EC2 + Compose introduces exactly one new concept at a time (a remote Linux host, a security group, an Elastic IP) rather than a dozen at once. RDS, S3, and CloudWatch are then each introduced as a single, isolated, well-understood swap.
- **Easier migration later.** Because the same `docker-compose.yml` runs locally and on EC2, moving off AWS — or up to ECS — later means moving containers, not rewriting the app. The application code is already cloud-agnostic (12-factor config via env vars; see `docs/DEVOPS.md` §5). See Task 7.

The phases are **additive and independently valuable** — each one is a shippable stopping point. You do not have to reach Phase 6 for the deployment to be "done"; most small deployments stop at Phase 3–5.

---

## Task 1 — Phased AWS deployment path

### Phase 1 — Local Docker production simulation *(already done)*

Run the production-like stack (`docker compose up --build`) on a developer machine with `DEBUG=False`, PostgreSQL, Gunicorn, and the Nginx-served frontend. This is exactly what `docs/DEPLOYMENT.md` describes and what has already been verified end-to-end (237/237 backend tests inside the container, live login → property → occupant → dashboard through the Nginx proxy against Postgres).

**Purpose:** prove the containers are correct with zero cloud spend and zero cloud risk. This is the reference environment every later phase is compared against.

**Exit criteria:** the "Before AWS" checklist (Task 8) is fully green.

### Phase 2 — Single EC2 deployment using Docker Compose

Provision **one** small EC2 instance (Amazon Linux 2023 or Ubuntu LTS), install Docker + the Compose plugin, clone the repo (or pull pre-built images later), copy a production `.env`, and run the **same `docker-compose.yml`** already used locally. Attach an Elastic IP so the address is stable. Open only ports 22 (SSH, ideally restricted to your IP) and 80/443 in the security group.

- Database: **PostgreSQL in a Docker container** on the EC2 box (the `db` service, unchanged), with its data on the named `postgres_data` volume backed by the instance's EBS volume.
- This is the **staging / demo** deployment. It is real, reachable, and cheap.

**Purpose:** get KarosL onto the internet on real infrastructure with the smallest possible surface area and cost. Everything the team already knows transfers directly.

**How to execute it:** `docs/AWS_STAGING_CHECKLIST.md` (the tick-list) and `docs/AWS_EC2_DEPLOYMENT.md` (the command runbook).

**Exit criteria:** app reachable at the EC2 Elastic IP (or a test domain), smoke tests pass (Task 8), backups confirmed to survive an instance reboot.

### Phase 3 — Move the database to Amazon RDS PostgreSQL

Stand up an **Amazon RDS for PostgreSQL** instance (single-AZ, smallest burstable class, e.g. `db.t4g.micro`, to start). Migrate data out of the container Postgres (`pg_dump` → `pg_restore`/`psql`). Point the backend at RDS by changing **only environment variables** — `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` — and remove the `db` service from the Compose file on EC2. **No application code changes are required**; this is exactly the seam the containerization work was designed around (`docs/DEVOPS.md` §9 step 3).

- Amazon RDS supports PostgreSQL DB instances and AWS publishes a PostgreSQL getting-started flow (create instance → connect → load data) that maps 1:1 to this phase.
- RDS gives managed automated backups, point-in-time recovery, and patching that a hand-run container Postgres does not.

**Purpose:** move the one piece of state that genuinely matters (the database) onto managed, durable, backed-up infrastructure. See Task 3 for the Docker-Postgres-vs-RDS tradeoff and when to make this jump.

**Exit criteria:** backend runs against RDS, RDS automated backups enabled and a restore test performed, container Postgres decommissioned.

### Phase 4 — Move receipts / backups / media to Amazon S3

Move the backup JSON exports (`BackupService.create_backup`, currently written to `backend/backups/*.json` on the `backend_backups` volume) to an **S3 bucket** with a versioned, private, lifecycle-managed configuration. The read/write call sites are already isolated to `apps/backup/services.py`, so this is a contained backend change (swap the local-disk path for an S3 storage backend), not an architectural one (`docs/DEVOPS.md` §6 and §9 step 2).

- **Reality check on scope (from `docs/DEVOPS.md` §6):** the *only* genuine local-disk state today is the backup JSON files. CSV/XLSX exports and receipt PDFs are generated **in memory and streamed** — they never touch disk, so there is nothing to migrate for them. There are **no user file uploads** (`MEDIA_ROOT`/`FileField` do not exist anywhere in the models). So "receipts/backups/media → S3" is, concretely, "**backups → S3**", plus a bucket ready for real media if a future feature ever needs it.
- S3 will be used for durable object storage that survives instance replacement and, later, scale-out beyond one host.

**Purpose:** stop trusting a single EBS volume with the disaster-recovery backups; make backups durable and independent of the compute host.

**Exit criteria:** new backups land in S3, a backup can be listed/downloaded/restored from S3, EBS-local backups migrated or retired.

### Phase 5 — Add CloudWatch logging / monitoring

Ship container logs to **Amazon CloudWatch Logs** instead of (or in addition to) the local `backend_logs` volume (`docs/DEVOPS.md` §9 step 7). Add a few CloudWatch **alarms** on the essentials — EC2 CPU/status-check, RDS free storage / CPU / connections, and a billing/estimated-charges alarm layered on top of the Task 2 budget.

- CloudWatch Logs can monitor, store, and access log files from EC2 instances and other sources, and lets you search/retain them centrally instead of `ssh`-ing in to `docker compose logs`.
- Set a **log retention policy** (e.g. 14–30 days) from day one — CloudWatch Logs bills for stored data, and "never expire" is a silent, growing cost (Task 2).

**Purpose:** be able to see what the app is doing and get paged when it (or the bill) misbehaves, without logging into the box.

**Exit criteria:** backend/frontend logs visible in CloudWatch, retention set, core alarms firing to email/SNS.

### Phase 6 — *(Optional, future)* ALB + ECS/Fargate

Only if and when a single EC2 box is genuinely insufficient — you need zero-downtime deploys, more than one backend replica, or automated horizontal scaling — move the containers to **ECS (Fargate)** behind an **Application Load Balancer**, with the images stored in **Amazon ECR** and TLS terminated at the ALB via **ACM**.

- Before scaling `backend` past one replica, move the migrate-on-start entrypoint step to a **one-shot ECS task / deploy job** so replicas don't race on migrations (`docs/DEVOPS.md` §8, §9 step 4).
- This is where the always-on ALB + (if you introduce private subnets) NAT Gateway costs appear — do **not** take this phase for cost or prestige reasons, only for a real availability/scale need.

**Purpose:** production-grade availability and scaling — deliberately deferred until the app's usage actually demands it.

**Exit criteria:** N/A for now — explicitly out of scope for the initial deployment. Documented so the path is known, not so it is taken soon.

---

## Task 2 — Cost guardrails (mandatory, before anything else)

> ⛔ **No AWS resource may be created before budget alerts are configured.** The budget is step zero of touching the account.

### Must-do before provisioning

1. **Create an AWS Budget.** A monthly cost budget (e.g. a hard ceiling like **$20–30/month** for the EC2+RDS phase) in AWS Budgets.
2. **Add email alerts.** Configure alerts at **50%, 80%, and 100%** of the budget (and a forecasted-to-exceed alert) to a monitored email address. Optionally wire to an SNS topic. Verify the first alert email actually arrives.
3. **Review Free Tier usage.** Check the **Free Tier** dashboard before and periodically after provisioning. Prefer free-tier-eligible instance classes (`t2.micro`/`t3.micro` for EC2, `db.t3.micro`/`db.t4g.micro` for RDS) while eligible, and know your 12-month free-tier clock.
4. **Enable Cost Explorer** and skim it weekly during the first month.

### Architectural cost rules

- **Avoid NAT Gateway initially.** A NAT Gateway is ~$32/month plus data-processing charges, always on. Keep the EC2 host in a **public subnet** with a security group instead of hiding it behind private subnets + NAT for the single-box phase. Introduce private networking only at Phase 6 if genuinely needed.
- **Avoid always-on oversized services.** No ALB, no ECS, no multi-AZ RDS, no provisioned-IOPS storage until a real need exists. Every one of those bills 24/7 regardless of traffic.
- **Use a small EC2 instance.** Start at the smallest burstable class that runs the stack (`t3.micro`/`t3.small`). Resize up only if you observe real resource pressure in CloudWatch (Phase 5).
- **Stop / delete unused resources.** Stop the EC2 instance when a demo environment isn't needed (you still pay for its EBS volume and Elastic IP, but not compute). Terminate throwaway experiments the same day you create them.

### Sneaky costs to watch specifically

| Resource | The trap | Guardrail |
|---|---|---|
| **RDS** | Runs 24/7; multi-AZ doubles it; storage grows and doesn't shrink | Single-AZ + smallest class to start; watch free-storage alarm |
| **EBS volumes** | Persist and bill **even when the EC2 instance is stopped or terminated** | Delete orphaned volumes; keep volumes small |
| **Snapshots** | RDS + EBS snapshots accumulate silently forever | Set/verify snapshot retention; prune old ones |
| **CloudWatch Logs** | Stored log data bills indefinitely if retention is "never expire" | Set 14–30 day retention on every log group (Phase 5) |
| **Elastic IP** | **Free only while attached to a running instance** — an unattached (or attached-to-stopped) EIP is billed hourly | Release EIPs you're not actively using; expect a small charge while the instance is stopped |
| **NAT Gateway** | ~$32/mo + per-GB, always on | Don't create one in the single-box phase (above) |
| **Data transfer out** | Egress to the internet is billed per GB | Minor at this scale, but watch it in Cost Explorer |

---

## Task 3 — First AWS architecture

The initial single-EC2 deployment (Phase 2, optionally Phase 3 for the DB):

```
                    User (browser)
                         │  HTTP/HTTPS
                         ▼
        EC2 public Elastic IP  (or test domain via Route 53 later)
                         │
                         ▼
   ┌──────────────────── EC2 instance (Docker Compose) ────────────────────┐
   │                                                                        │
   │     Nginx reverse proxy  ── frontend container (built SPA)             │
   │       :80 / :443            serves static bundle; proxies /api, /admin │
   │          │                                                             │
   │          ▼                                                             │
   │     Backend container  (Gunicorn + Django)  :8000                      │
   │          │                                                             │
   │          ▼                                                             │
   │     PostgreSQL  ── Phase 2: container on this box (postgres_data vol)  │
   │                 └─ Phase 3: Amazon RDS PostgreSQL (external, managed)  │
   └────────────────────────────────────────────────────────────────────────┘
```

This is the **same three-tier topology already running locally** (`docs/DEVOPS.md` §1). The only differences from local are: it's on an EC2 host, it has a public Elastic IP, and — from Phase 3 — Postgres moves out to RDS. The frontend container's Nginx already reverse-proxies `/api/`, `/admin/`, and `/static/` to the backend, so the SPA's relative `/api` base URL works unchanged.

### Database placement: the key early decision

**Start option — PostgreSQL inside Docker (Phase 2, staging/demo):**
- ✅ Cheaper and simpler — no separate managed service to pay for or configure; it's just the `db` service you already run.
- ✅ Good for **demo / staging** and early cost control.
- ⚠️ **Weaker durability** — data lives on the instance's EBS volume; you own backups, patching, and recovery by hand. An instance/volume loss without a good backup is data loss.

**Production option — Amazon RDS PostgreSQL (Phase 3):**
- ✅ **Safer for real production** — decoupled from the compute host; the box can be rebuilt without touching the data.
- ✅ **Managed automated backups** + point-in-time recovery.
- ✅ **Better reliability** — managed patching, monitoring, optional multi-AZ failover.
- ⚠️ **May cost more** — it's an always-on managed instance on top of EC2 (though the smallest single-AZ class is modest, and free-tier-eligible for the first 12 months).

**Rule of thumb:** container Postgres for staging/demo and while learning; **move to RDS before KarosL holds real tenant/payment data you cannot afford to lose.** The migration is env-vars-only (Phase 3), so this is a low-friction upgrade you can make exactly when the data's value justifies the cost.

---

## Task 4 — AWS services KarosL will likely use

| Service | Role in KarosL | When |
|---|---|---|
| **EC2** | The application host — runs the Docker Compose stack (Nginx + Gunicorn/Django + optionally Postgres) | Phase 2 |
| **RDS for PostgreSQL** | Managed production database. **Amazon RDS supports PostgreSQL DB instances**, and AWS documentation includes a PostgreSQL getting-started flow (create → connect → load) that this plan follows | Phase 3 |
| **S3** | Durable object storage for backup JSON exports (and future media). **S3 will be used later for durable object storage** that outlives any single instance | Phase 4 |
| **CloudWatch Logs** | Centralized logging + basic monitoring/alarms. **CloudWatch Logs can monitor, store, and access log files from EC2 instances and other sources** | Phase 5 |
| **IAM** | Least-privilege access — an EC2 **instance role** for S3/CloudWatch access (no long-lived keys on the box), scoped users/roles for humans and CI | From Phase 2, tightened each phase |
| **ECR** | Private registry for the `backend`/`frontend` images once builds move off the box | Phase 6 (or earlier if CI pushes images) |
| **Route 53** | DNS, **later**, if/when KarosL gets a custom domain | Later |
| **ACM** | TLS certificates, **later**, for HTTPS when a load balancer / CloudFront terminates TLS | Later (with Phase 6 / a domain) |
| **Elastic IP** | Stable public address for the EC2 host | Phase 2 (mind the cost rules in Task 2) |

Least-privilege note: prefer an **EC2 instance role** so the app reaches S3/CloudWatch without any AWS keys stored on disk (Task 6). Scope every IAM policy to the specific bucket/log group/RDS resource — never `*`.

---

## Task 5 — Environment plan

Four environments, each a deliberate step in fidelity:

### Development (native, day-to-day)
- Local **SQLite** (default) or a local PostgreSQL.
- Frontend via `npm run dev` (Vite dev server, port 5173).
- Backend via Django `runserver`.
- `DEBUG=True`; the primary, documented developer workflow (`docs/DEVOPS.md`). Unchanged by any of this.

### Docker local (production simulation) — *Phase 1*
- **Docker Compose** (`docker-compose.yml`).
- **PostgreSQL container** (`db` service) with the `postgres_data` volume.
- Production-like env vars: `DEBUG=False`, Gunicorn, Nginx-served frontend, real `SECRET_KEY`.
- Frontend on `:8080`, backend on `:8000`. This is the reference target for everything below.

### AWS staging — *Phase 2*
- **EC2** instance running the same Docker Compose stack.
- **PostgreSQL container** on the box (not yet RDS).
- Reachable via the EC2 **public Elastic IP** or a **test domain**.
- **Limited test data** only; a scrubbed/seeded dataset, never real tenant data. Demo/tour accounts fine here — but see the "demo account removed/changed" checklist item before production.

### AWS production — *Phases 3–5 (+6 later)*
- **EC2** (or later **ECS**) for compute.
- **RDS PostgreSQL** for the database.
- **S3** for backups/media storage.
- **Automated backups** (RDS) + verified restore.
- **CloudWatch** monitoring + alarms + log retention.
- **HTTPS** configured (via a domain + TLS; ALB/CloudFront + ACM at Phase 6, or a reverse-proxy cert like Let's Encrypt on the single box before then).
- `DEBUG=False`, real `ALLOWED_HOSTS`, tightened CORS/CSRF (see Task 8 "Before production").

---

## Task 6 — Secret management plan

### Secrets that must NEVER enter Git

- **Django `SECRET_KEY`**
- **Database password** (`DB_PASSWORD` / `POSTGRES_PASSWORD`)
- **JWT / refresh-token secrets**, if ever configured separately from `SECRET_KEY`
- **AWS access keys** (access key ID / secret access key)
- **Admin / superuser passwords** (and the demo account credentials)
- **Email credentials** (`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — already an env var in `backend/.env.example`)
- **S3 bucket credentials / policies** and any signed-URL secrets

Only `*.env.example` files (placeholders) are committed; real `.env` files are gitignored (`docs/DEVOPS.md` §5). That invariant continues on AWS.

### Recommended handling, by stage

- **Local development:** `.env` files on disk, never committed. (Already the case.)
- **CI/CD (later):** **GitHub Secrets** for anything the pipeline needs (registry creds, deploy keys, a deploy-time `SECRET_KEY`), injected at build/deploy time — never printed to logs.
- **On AWS compute:** prefer **AWS IAM roles** over stored keys wherever possible — an **EC2 instance role** lets the app reach S3/CloudWatch/RDS with **zero long-lived AWS keys on the box**. This is the single biggest secret-leak reduction available and should be the default.
- **Application secrets on AWS (later):** move `SECRET_KEY`, DB password, email creds into **AWS Secrets Manager** or **SSM Parameter Store** (SecureString) and have the app/entrypoint read them at start, instead of a plaintext `.env` on the instance. Parameter Store's standard tier is effectively free and is the pragmatic first choice; Secrets Manager adds rotation for a per-secret monthly cost.

### Housekeeping

- Rotate the `SECRET_KEY`, DB password, and any admin/demo password between local, staging, and production — never reuse the local dev values (`django-insecure-...`) anywhere reachable.
- Confirm `.gitignore` still excludes all `.env` variants before the first push to a public/shared remote (Task 8).

---

## Task 7 — Migration / exit plan (moving off AWS if needed)

KarosL is intentionally portable: the app reads all config from environment variables and runs as standard Docker containers, so it is not locked to AWS. To move to another provider (or back to on-prem / a different VPS):

1. **Export the PostgreSQL database.** `pg_dump` from RDS (or the container Postgres) → a portable dump file.
2. **Copy receipts / backups / media.** Sync the S3 bucket contents down (`aws s3 sync`) — currently just the backup JSON files (Task 1, Phase 4), plus any future media.
3. **Move the Docker Compose stack.** The same `docker-compose.yml` runs on any Docker host — another cloud VM, a different provider, or local. No image rebuild needed if images are in a registry; otherwise rebuild from the repo.
4. **Update environment variables.** Point `DB_HOST`/`DB_PORT`/credentials at the new database; point the storage backend at the new object store; update `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`.
5. **Update DNS.** Repoint the domain's A/CNAME records (Route 53 or elsewhere) at the new host's IP/endpoint; mind TTLs.
6. **Smoke-test the workflows.** Run the smoke tests (Task 8): login → create property → register occupant → record payment → generate receipt → dashboard summary → create + restore a backup — end to end on the new environment before cutting traffic over.

Because steps 1–4 are all data-copy and env-var changes — no code rewrite — the exit cost stays low. This is a direct payoff of keeping the architecture container-based and 12-factor from the start.

---

## Task 8 — Checklists

### ✅ Before AWS (before creating any cloud resource)

- [ ] **Docker works locally** — `docker compose up --build` brings all services healthy (`docs/DEPLOYMENT.md` verification checklist).
- [ ] **Tests pass** — backend `python manage.py test` and frontend `npm test` + `npm run build`, both native and (backend) in-container.
- [ ] **`.env.example` complete** — every variable the stack needs is present in the relevant `*.env.example` with a safe placeholder.
- [ ] **No secrets in the repo** — `.gitignore` excludes all `.env` variants; a history scan finds no committed keys/passwords.
- [ ] **Budget alerts configured** — AWS Budget + email alerts live and a test alert received. **(This is the gate — see Task 2.)**
- [ ] **Backup restore verified** — create a backup and restore it into a disposable database successfully (already done once, `docs/RELEASE_PLAN.md` Final Stabilization Closeout — re-verify against the deployment DB).
- [ ] **Demo account removed / changed** — the `demo` / `demo12345` staff+superuser account (and the onboarding overlays' assumptions) removed or its password rotated before anything is internet-reachable.

### ✅ Before production (before real users / real data)

- [ ] **`DEBUG=False`** in the production environment.
- [ ] **`ALLOWED_HOSTS`** set to the real domain / EC2 address (not `localhost`).
- [ ] **CSRF / CORS configured** — `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS` set to the real origin(s); `CORS_ALLOW_ALL_ORIGINS=False`.
- [ ] **HTTPS configured** — TLS terminating in front of the app; re-enable `SECURE_SSL_REDIRECT` / `CSRF_COOKIE_SECURE` / `SESSION_COOKIE_SECURE` (which were deliberately disabled for the TLS-less local compose env — `docs/DEVOPS.md`, `docs/CHANGELOG.md`).
- [ ] **Backups verified** — automated backups running (RDS or backup service → S3) and a restore tested against the real backend.
- [ ] **Admin account secured** — strong, unique superuser password; demo/default accounts gone; admin not using a shared or dev credential.
- [ ] **Logs reviewed** — CloudWatch (or container) logs checked for errors/tracebacks; log retention set (Task 2).
- [ ] **Smoke tests pass** — the full workflow chain (Task 7 step 6) passes against production before announcing it.

---

## Cross-references

- `docs/AWS_STAGING_CHECKLIST.md` — the Phase 2 tick-list: account safety, EC2 plan, security group, server setup, verification, cleanup.
- `docs/AWS_EC2_DEPLOYMENT.md` — the Phase 2 command-level runbook (connect → install Docker → clone → `.env` → build → migrate → superuser → logs → troubleshooting).
- `docs/DEVOPS.md` — Docker architecture, env-var strategy, static/media-to-S3 analysis (§6), the AWS next-steps list (§9), troubleshooting (§10).
- `docs/DEPLOYMENT.md` — build/run/verify mechanics for the container stack.
- `docs/PROJECT_STATE.md` — current phase and verified baseline.
- `docs/RELEASE_PLAN.md` — phase history and recommendations.
- `docs/CHANGELOG.md` — change record.

**Reminder, one more time:** this document is a plan. **No AWS resource is to be created before the Task 2 budget + alerts are in place.**
