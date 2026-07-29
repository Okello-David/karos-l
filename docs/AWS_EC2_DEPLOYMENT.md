# AWS EC2 Staging Deployment Guide

Status: **Executed — staging is live.** First deployed 2026-07-29. See the deployment record below.

---

## Deployment record — AWS staging (2026-07-29)

| Item | Value |
|---|---|
| Region | `eu-north-1` (Stockholm) |
| Availability zone | `eu-north-1a` |
| Instance ID | `i-0afd1871b46296500` |
| Instance name tag | `karosl-staging-ec2` (Project=KarosL, Environment=staging) |
| Instance type | `t3.micro` (2 vCPU, ~916 MB usable RAM) |
| AMI | `ami-0c783070b2e26d98c` — Amazon Linux 2023 |
| Public IPv4 | `<EC2_PUBLIC_IP>` — auto-assigned, **no Elastic IP**; changes on every stop/start (see §13) |
| Key pair | `karosl-staging-key` (private key at `~/.ssh/karosl-staging-key.pem`, mode 400) |
| Security group | `karosl-staging-sg` — `sg-065fb018e22aa18a5` |
| VPC / subnet | default `vpc-04664b7a9c5f76d68` / `subnet-0d36cc95a8da7b99c` (public) |
| Root volume | 10 GB gp3, encrypted, delete-on-termination |
| IMDS | IMDSv2 required (`HttpTokens=required`) |
| Swap | 2 GB `/swapfile`, persisted in `/etc/fstab` |
| App directory | `/home/ec2-user/apps/karosl` |
| Deployed branch | `cloud-deployment` |
| Admin username | `karosadmin` |

**Deliberately NOT created:** RDS, NAT Gateway, load balancer, ECS/Fargate, Elastic IP, extra EBS volumes.

**Verified on deployment:** all three containers healthy; 40 migrations applied; `/api/health/` returns `{"status":"ok","database":"ok"}` through the public IP (proving internet → security group → nginx → Gunicorn → PostgreSQL); SPA serves with deep-link refresh working; `/api/auth/login/` returns a proper Django validation error rather than a gateway error; protected endpoints return 401; **ports 8000 and 5432 confirmed unreachable from the internet.**

**Authenticated access verified:** `karosadmin` password set and login confirmed through the public IP — DRF token issued, and `/api/dashboard/`, `/api/properties/`, `/api/occupants/` all return 200 with it.

**Known issues at time of writing:** the business-workflow walkthrough (create property → register occupant → record payment → receipt) has not been exercised on staging yet; the database is empty. See `docs/AWS_STAGING_CHECKLIST.md` §4.

---

Step-by-step commands to deploy KarosL to a single EC2 instance running the existing Docker Compose stack. This is **staging only** — no RDS, no load balancer, no HTTPS, no real tenant data.

> ⛔ **Before running anything here:** `docs/AWS_STAGING_CHECKLIST.md` §1 must be green — **AWS Budget + email alerts configured and a test alert received.** No AWS deployment proceeds before that.

**Placeholders used throughout.** Substitute your own values; never commit real ones.

| Placeholder | Meaning | Example shape |
|---|---|---|
| `<EC2_PUBLIC_IP>` | Instance's public IPv4 | `203.0.113.42` |
| `<KEY_NAME>.pem` | Your EC2 key pair file | `karosl-staging.pem` |
| `<SSH_USER>` | `ec2-user` (Amazon Linux 2023) or `ubuntu` (Ubuntu LTS) | `ec2-user` |
| `<REPO_URL>` | Git remote for KarosL | `https://github.com/<org>/Karos_L.git` |
| `<APP_DIR>` | App directory on the server | `/opt/karosl` |
| `<STRONG_DB_PASSWORD>` | Generated DB password | *(generated, see §5)* |
| `<GENERATED_SECRET_KEY>` | Fresh Django secret key | *(generated, see §5)* |
| `<MY_IP>` | Your workstation's public IP | `198.51.100.7` |

---

## 1. Target architecture

```
                     Browser
                        │  HTTP :80   (HTTPS deferred to the domain/SSL sprint)
                        ▼
              EC2 public IP  <EC2_PUBLIC_IP>
                        │
                        ▼
  ┌──────────── EC2 instance — Docker Compose ─────────────┐
  │                                                          │
  │   frontend   nginx:1.27-alpine  :80                     │
  │              serves the built React SPA                 │
  │              reverse-proxies /api/ /admin/ /static/     │
  │                        │                                │
  │                        ▼  (compose network)             │
  │   backend    gunicorn + Django  :8000                   │
  │                        │                                │
  │                        ▼  db:5432 (internal only)       │
  │   db         postgres:16-alpine                         │
  │              volume: postgres_data                      │
  └──────────────────────────────────────────────────────────┘
```

Identical to the locally verified stack (`docs/DEVOPS.md` §1). The only differences: it runs on an EC2 host, the frontend publishes on port **80** instead of 8080, and `ALLOWED_HOSTS`/CSRF/CORS name the EC2 IP.

## 2. Provision the instance

Console → EC2 → Launch instance:

- **AMI:** Amazon Linux 2023, or Ubuntu Server LTS (22.04/24.04).
- **Instance type:** `t3.micro` (or `t2.micro` if that's your free-tier class).
- **Key pair:** create/select one; download the `.pem` and `chmod 400` it.
- **Network:** default VPC, a **public** subnet, **auto-assign public IP = Enable**. No NAT Gateway.
- **Storage:** 8–20 GB gp3. Leave "delete on termination" **enabled** so terminating doesn't orphan a billing volume.
- **Security group:** see §3.

## 3. Security group

**Inbound**

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | `<MY_IP>/32` — **your IP only** |
| HTTP | TCP | 80 | `0.0.0.0/0` — temporary staging |
| ~~HTTPS~~ | TCP | 443 | *deferred to the domain/SSL sprint* |

**Outbound:** leave the default allow-all — the instance must reach package repos, Docker Hub, and GitHub.

**Do not add 5432.** Do not add 8000. Postgres and Gunicorn are reached over the internal compose network, never from the internet — full rationale in `docs/AWS_STAGING_CHECKLIST.md` §2b.

Find your own IP for the SSH rule:
```bash
curl -s https://checkip.amazonaws.com
```

## 4. Connect and install prerequisites

### 4.1 Connect

```bash
chmod 400 <KEY_NAME>.pem
ssh -i <KEY_NAME>.pem <SSH_USER>@<EC2_PUBLIC_IP>
```

If it hangs: the SSH rule's source IP is wrong (your address changed) or the instance is still booting. If it says `Permission denied (publickey)`: wrong `<SSH_USER>` for the AMI.

### 4.2 Install Docker + Compose plugin — Amazon Linux 2023

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# The Compose v2 plugin is not bundled on AL2023 — install it explicitly.
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

### 4.3 Install Docker + Compose plugin — Ubuntu LTS

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg git

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### 4.3b Install a current buildx plugin *(required on Amazon Linux 2023)*

Compose v2.30+/v5 delegates image building to **buildx** and refuses to build with anything older than **0.17.0**. Amazon Linux 2023's `docker` package ships **buildx 0.12.1**, so `docker compose build` fails immediately with:

```
compose build requires buildx 0.17.0 or later
```

Confirmed on a real AL2023 `t3.micro` during the first staging deployment. Install a current buildx alongside the distro's Docker:

```bash
BX_TAG=$(curl -fsSL https://api.github.com/repos/docker/buildx/releases/latest \
  | grep -oE '"tag_name": *"[^"]+"' | cut -d'"' -f4)
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fsSL \
  "https://github.com/docker/buildx/releases/download/${BX_TAG}/buildx-${BX_TAG}.linux-amd64" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
docker buildx version      # expect >= v0.17.0
```

`scripts/server-setup.sh` now performs this check and install automatically. Ubuntu's `docker-ce` packages ship a current buildx, so this step is a no-op there.

### 4.4 Apply the group change and verify

```bash
exit          # the docker group only applies to a NEW login session
ssh -i <KEY_NAME>.pem <SSH_USER>@<EC2_PUBLIC_IP>

docker --version
docker compose version     # must print v2.x — note: no hyphen
docker run --rm hello-world
```

### 4.5 Add swap if the instance has under 2 GB RAM

The frontend image build runs `npm ci && npm run build`, which can exhaust a 1 GB instance and get the Node process OOM-killed mid-build (it usually presents as a build that dies with no clear error). One-time fix:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab   # survive reboot
free -h
```

## 5. Clone the repo and create the server `.env`

### 5.1 App directory and clone

```bash
sudo mkdir -p <APP_DIR>
sudo chown $USER:$USER <APP_DIR>
git clone <REPO_URL> <APP_DIR>
cd <APP_DIR>
```

### 5.2 Generate the secrets — on the server, into your scrollback only

```bash
# Django SECRET_KEY
docker run --rm python:3.12-slim python -c \
  "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#\$%^&*(-_=+)') for _ in range(50)))"

# Database password
openssl rand -base64 32
```

Generate them fresh for staging. Never reuse the local dev values, never reuse them again in production, never paste them into a commit, a chat, or a ticket.

### 5.3 Create `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env          # or vi
```

The root `.env` is the only env file the compose stack needs — `docker-compose.yml` passes it to the backend via `env_file`. Do **not** create `backend/.env` or `frontend/.env` on the server; they are for the native (non-Docker) workflow and would be ignored here.

**Complete staging `.env`:**

```bash
# --- PostgreSQL (docker-compose "db" service) ---
POSTGRES_DB=karosl
POSTGRES_USER=karosl_user
POSTGRES_PASSWORD=<STRONG_DB_PASSWORD>

# --- Backend (Django) ---
SECRET_KEY=<GENERATED_SECRET_KEY>
DEBUG=False

# Keep localhost/127.0.0.1 — the backend container's HEALTHCHECK curls
# http://localhost:8000/api/health/. Keep "backend" — that's the compose
# hostname nginx proxies to. Add the EC2 public IP for browser traffic.
ALLOWED_HOSTS=<EC2_PUBLIC_IP>,localhost,127.0.0.1,backend

DB_ENGINE=django.db.backends.postgresql
DB_NAME=karosl
DB_USER=karosl_user
DB_PASSWORD=<STRONG_DB_PASSWORD>     # must equal POSTGRES_PASSWORD above
DB_HOST=db
DB_PORT=5432

# Scheme included, no trailing slash, http (not https) until TLS exists.
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=http://<EC2_PUBLIC_IP>
CSRF_TRUSTED_ORIGINS=http://<EC2_PUBLIC_IP>

# --- Frontend (build-time only) ---
# Leave as /api. Nginx reverse-proxies it; an absolute URL would bake the
# EC2 IP into the JS bundle and force an image rebuild whenever it changes.
VITE_API_BASE_URL=/api

# --- Host ports ---
# 80 so the app is at http://<EC2_PUBLIC_IP> with no port suffix.
FRONTEND_PORT=80
# Bind Gunicorn to loopback only — defence in depth behind the security
# group, so port 8000 is never published on the public interface.
BACKEND_PORT=127.0.0.1:8000
```

**Auth note:** KarosL uses **DRF Token authentication** (`rest_framework.authentication.TokenAuthentication`, see `backend/config/settings.py`), not JWT. Tokens are database rows, not signed blobs — there is **no separate JWT signing secret to configure**. `SECRET_KEY` remains the only cryptographic secret the app needs.

**TLS note:** `docker-compose.yml` explicitly sets `SECURE_SSL_REDIRECT`, `CSRF_COOKIE_SECURE`, and `SESSION_COOKIE_SECURE` to `False`, which is exactly right for HTTP staging — leaving them on would force an HTTPS redirect to a port nothing is listening on and lock you out entirely. **Flip all three back to `True` in the domain/SSL sprint**, once TLS actually terminates in front of the app.

## 6. Build and start

```bash
cd <APP_DIR>

docker compose build          # first build is slow (npm ci dominates); ~5-15 min on t3.micro
docker compose up -d
docker compose ps             # all three should reach (healthy) within ~60s
```

Migrations and `collectstatic` run automatically on every backend container start via `backend/docker-entrypoint.sh`, which first waits for Postgres to accept connections. Django's migration runner is idempotent, so this is safe on every restart.

## 7. Run migrations manually (if ever needed)

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py migrate --check    # exit 0 = nothing pending
docker compose exec backend python manage.py showmigrations
```

## 8. Create the superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

Strong, unique password. **Not** the local dev credential, and **not** `demo`/`demo12345` — that account must not exist on anything internet-reachable.

## 9. Verify

From the server:
```bash
curl -s localhost/api/health/          # {"status": "ok", "database": "ok"}
curl -sI localhost/ | head -1          # HTTP/1.1 200 OK
```

From your own machine:
```bash
curl -s http://<EC2_PUBLIC_IP>/api/health/
```

Then in a browser at `http://<EC2_PUBLIC_IP>` — walk the full checklist in `docs/AWS_STAGING_CHECKLIST.md` §4 (login → dashboard → property → occupant → payment → receipt).

## 10. Viewing logs

```bash
docker compose ps                          # status of all services
docker compose logs backend                # full backend log
docker compose logs -f backend             # follow live
docker compose logs --tail=100 backend     # last 100 lines
docker compose logs --since 10m backend    # last 10 minutes
docker compose logs frontend               # nginx access/error log
docker compose logs db                     # postgres
docker compose logs                        # everything, interleaved
```

Helper: `./scripts/docker-logs.sh backend -f`

Django also writes to the `backend_logs` volume (`/app/logs/karosl.log` in the container):
```bash
docker compose exec backend tail -100 /app/logs/karosl.log
```

## 11. Restarting and stopping

```bash
docker compose restart                 # restart all (re-runs migrations on backend start)
docker compose restart backend         # restart one service

docker compose stop                    # stop, keep containers and data
docker compose start                   # start them again

docker compose down                    # remove containers, KEEP named volumes (data safe)
docker compose down -v                 # remove containers AND DELETE ALL DATA — destructive
```

`docker compose down -v` deletes `postgres_data`, `backend_backups`, and `backend_logs`. On staging that means every property, occupant, and payment you created. There is no undo.

## 12. Redeploying after a code change

```bash
cd <APP_DIR>
git pull
docker compose build
docker compose up -d           # recreates only what changed
docker compose ps
```

Helper: `./scripts/deploy-staging.sh`

**Frontend env vars are build-time.** `VITE_API_BASE_URL` is inlined into the JS bundle during `docker compose build`; changing it requires a rebuild, not just a restart. Backend env vars take effect on container restart.

## 13. If the public IP changes

With an auto-assigned public IP, stopping and starting the instance gives you a **new address**, and Django will reject every request with a `DisallowedHost` error until you update it:

```bash
cd <APP_DIR>
nano .env      # update ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS
docker compose up -d      # recreates the backend with the new env
```

No image rebuild is needed — `VITE_API_BASE_URL=/api` is relative, so the frontend bundle does not contain the IP at all.

## 13a. Cost safety — resource inventory and cleanup

### What exists (KarosL staging, `eu-north-1`)

| Resource | Identifier | Billing behaviour |
|---|---|---|
| EC2 instance | `i-0afd1871b46296500` (`karosl-staging-ec2`), `t3.micro` | Charged only while **running**. Stop it and compute billing stops immediately. |
| EBS root volume | 10 GB gp3, encrypted, delete-on-termination | Charged **even while the instance is stopped**. A few cents a month at this size. |
| Security group | `karosl-staging-sg` (`sg-065fb018e22aa18a5`) | Free |
| Key pair | `karosl-staging-key` | Free |
| Public IPv4 | auto-assigned, **no Elastic IP** | Charged while the instance runs; **nothing** accrues while stopped, because there is no EIP to sit idle. |

### Intentionally NOT created

**RDS** · **S3** · **Load Balancer / ALB** · **NAT Gateway** · **ECS / Fargate** · **Elastic IP** · **extra EBS volumes**

Each of these bills 24/7 regardless of traffic. An ALB and a NAT Gateway are ~$16–32/month **each**, always on, and neither adds anything to a single-instance staging box. This is the main reason staging costs cents rather than tens of dollars.

> ⚠️ **Other projects share this AWS account.** As of 2026-07-29 `eu-north-1` also contains `dc-intern-postgres` (RDS `db.t4g.micro`, 20 GB, running) and `dc-intern-backend` (EC2, stopped, **with Elastic IP `16.192.137.239` still attached** — an unassociated/idle EIP bills hourly). Neither belongs to KarosL and neither was created or modified by this work, but both affect the account's bill and the shared budget alarm. Worth a look if those projects are finished.

### Reminder: stop the instance when not testing

This is the single most effective cost control available here. See the commands below.

## 13b. Cleanup commands — live instance

Nothing here runs automatically. Each command is deliberate.

### Containers (on the instance)

```bash
cd ~/apps/karosl
docker compose ps                  # what is running
docker compose stop                # stop containers, keep them and the data
docker compose down                # remove containers, KEEP named volumes (data safe)
docker system prune -f             # reclaim dangling images and build cache
```
`docker compose down -v` additionally deletes `postgres_data`, `backend_backups`, and `backend_logs` — **every property, occupant, and payment on staging. No undo.**

### Stop the instance between testing sessions (from your workstation)

This is the main cost lever: compute charges stop immediately. The 10 GB EBS root volume keeps billing (a few cents a month), and there is **no Elastic IP**, so nothing else accrues.

```bash
aws ec2 stop-instances  --instance-ids i-0afd1871b46296500 --region eu-north-1
aws ec2 start-instances --instance-ids i-0afd1871b46296500 --region eu-north-1

# The public IP CHANGES after each start — fetch the new one:
aws ec2 describe-instances --instance-ids i-0afd1871b46296500 --region eu-north-1 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```
Then update `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` in the server's `.env` and run `docker compose up -d` (§13).

### Terminate when staging is no longer needed

**Back up anything worth keeping first — termination is irreversible.**

```bash
# 1. Dump the database and copy it off the instance
ssh -i ~/.ssh/karosl-staging-key.pem ec2-user@<EC2_PUBLIC_IP> \
  'cd ~/apps/karosl && docker compose exec -T db pg_dump -U karosl_user karosl' \
  > karosl-staging-$(date +%F).sql

# 2. Terminate the instance (the root volume is delete-on-termination, so it goes too)
aws ec2 terminate-instances --instance-ids i-0afd1871b46296500 --region eu-north-1

# 3. Confirm no volumes were orphaned (expect an empty list)
aws ec2 describe-volumes --region eu-north-1 \
  --filters "Name=status,Values=available" \
  --query 'Volumes[].{Id:VolumeId,Size:Size,Created:CreateTime}' --output table

# 4. Optional — remove the security group and key pair if not reusing them
aws ec2 delete-security-group --group-id sg-065fb018e22aa18a5 --region eu-north-1
aws ec2 delete-key-pair --key-name karosl-staging-key --region eu-north-1

# 5. Confirm nothing is still running in the region
aws ec2 describe-instances --region eu-north-1 \
  --filters "Name=instance-state-name,Values=running,stopped" \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name}' --output table
```

Check Cost Explorer 24–48 h later and confirm the daily run-rate actually dropped. Verify, don't assume.

## 14. Troubleshooting

Common symptoms and their causes, ordered by how often they actually happen. See also `docs/DEVOPS.md` §10.

### Diagnostic commands

```bash
docker compose ps
docker compose logs backend
docker compose logs frontend
docker compose logs db
docker compose exec backend python manage.py check
docker compose exec backend python manage.py check --deploy    # security-settings review
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py showmigrations
docker compose exec db psql -U karosl_user -d karosl -c '\dt'
docker stats --no-stream       # CPU/memory pressure
df -h                          # disk full? images and logs eat small volumes
```

### `DisallowedHost` / "Invalid HTTP_HOST header"

Backend log shows `Invalid HTTP_HOST header: '203.0.113.42'. You may need to add '203.0.113.42' to ALLOWED_HOSTS`.

The EC2 public IP is missing from `ALLOWED_HOSTS`, or the instance was restarted and the IP changed (§13). Nginx forwards the browser's `Host` header (`proxy_set_header Host $host`), so Django sees the IP the user typed. Fix `.env`, then `docker compose up -d`.

### Backend container stuck `unhealthy` but the app works fine

`ALLOWED_HOSTS` is missing `localhost`. The Docker `HEALTHCHECK` in `backend/Dockerfile` curls `http://localhost:8000/api/health/` from *inside* the container; Django rejects the `localhost` Host header and returns 400, so the healthcheck fails forever. Keep `localhost,127.0.0.1` in the list.

### CSRF errors — "CSRF verification failed" / 403 on login

`CSRF_TRUSTED_ORIGINS` must contain the **full origin with scheme and no trailing slash**: `http://<EC2_PUBLIC_IP>`, not `<EC2_PUBLIC_IP>` and not `http://<EC2_PUBLIC_IP>/`. If you have added TLS, it must say `https://`, matching what the browser actually uses.

### CORS errors in the browser console

Usually a red herring on this architecture: the SPA and API are served from the **same origin** through the Nginx proxy, so ordinary requests are not cross-origin at all. A genuine CORS error here almost always means `VITE_API_BASE_URL` was set to an absolute URL, making the browser call a different origin. Set it back to `/api` and **rebuild** the frontend image (build-time variable). If you truly need a split origin, set `CORS_ALLOWED_ORIGINS` to that exact origin and keep `CORS_ALLOW_ALL_ORIGINS=False`.

### Redirected to `https://` and nothing loads

`SECURE_SSL_REDIRECT` got turned on without TLS in front. `docker-compose.yml` sets it to `False` deliberately; if you overrode it, revert until the SSL sprint.

### Database connection errors

`could not connect to server` / `password authentication failed` / backend restarting in a loop.

- `POSTGRES_PASSWORD` and `DB_PASSWORD` **must be identical**. This is the single most common cause.
- `DB_HOST` must be `db` (the compose service name), never `localhost` — inside the backend container, `localhost` is the backend itself.
- **A changed `POSTGRES_PASSWORD` does not take effect on an existing volume.** Postgres only reads it when initializing an empty data directory, so editing it later leaves the old password in place. Either set the old one back, change it inside the database (`ALTER USER`), or wipe with `docker compose down -v` (**destroys all data**).
- Check the db container is actually healthy: `docker compose ps`, `docker compose logs db`.

### Migration errors

```bash
docker compose logs backend | grep -A20 -i "traceback\|migrat"
docker compose exec backend python manage.py showmigrations
```
The entrypoint runs `migrate --noinput` before Gunicorn starts, so a migration failure means the container never serves traffic. If `db` was not healthy in time the entrypoint gives up after ~60s — restart with `docker compose up -d` once Postgres is healthy.

### Frontend loads but cannot reach the backend (API calls fail)

- `docker compose ps` — is `backend` actually up and healthy?
- `docker compose exec frontend wget -qO- http://backend:8000/api/health/` — tests the internal hop, isolating Nginx→Gunicorn from browser→Nginx.
- Check `docker compose logs frontend` for `502 Bad Gateway` (backend down or still starting) versus `404` (path/routing issue).
- Confirm the browser is calling `/api/...` on the same origin, not an absolute URL (see the CORS entry above).

### Static files missing — Django admin unstyled, DRF browsable API bare

`collectstatic` runs automatically at backend start and WhiteNoise serves the result; Nginx proxies `/static/` through to the backend. Check for `Collecting static files...` in `docker compose logs backend`, then confirm `docker compose exec backend ls /app/staticfiles | head`. Note the SPA's own assets are served directly by Nginx from the image and are unrelated to this path.

**Media files:** there are none. KarosL has no `MEDIA_ROOT` and no `FileField`/`ImageField` anywhere — receipt PDFs and CSV/XLSX exports are generated in memory and streamed, never written to disk (`docs/DEVOPS.md` §6). If media is "missing", the cause is a feature that does not exist yet, not a deployment fault.

### Port 80 already in use

```bash
sudo ss -tlnp | grep :80
```
Usually a distro's Apache/Nginx installed by a "web server" setup step. `sudo systemctl disable --now apache2 nginx` (whichever exists), then `docker compose up -d`.

### Site unreachable from the browser but `curl localhost` works on the server

Security group inbound rule for HTTP 80 is missing or scoped to the wrong source. Also confirm `FRONTEND_PORT=80` in `.env` — otherwise it's listening on 8080, which the security group does not allow.

### `compose build requires buildx 0.17.0 or later`

Amazon Linux 2023's Docker package ships buildx 0.12.1, which is too old for Compose v2.30+/v5. Install a current buildx plugin — see §4.3b. `scripts/server-setup.sh` handles it automatically.

### Build fails or dies silently on a small instance

Out of memory during the frontend `npm run build`. Add swap (§4.5), or build with more RAM and push images to a registry later (`docs/DEVOPS.md` §9).

---

## Cross-references

- `docs/AWS_STAGING_CHECKLIST.md` — the tick-list this runbook executes, incl. cleanup.
- `docs/AWS_DEPLOYMENT_PLAN.md` — phased strategy, cost guardrails, secrets plan.
- `docs/DEVOPS.md` — Docker architecture, env vars, health checks, troubleshooting.
- `scripts/server-setup.sh`, `scripts/deploy-staging.sh`, `scripts/docker-logs.sh` — optional helpers for §4, §12, §10.
