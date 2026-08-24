# DevOps: Containerization & Local Production-Like Environment

Status: KarosL is in the **Cloud Engineering Phase** — Docker is used to prove KarosL can run outside the developer's machine setup, as a stepping stone toward AWS deployment. The local production-like stack is verified; **AWS staging is documented and asset-ready but not yet deployed** (see §9, `docs/AWS_STAGING_CHECKLIST.md`, `docs/AWS_EC2_DEPLOYMENT.md`). No business features or architecture changed as part of this pass; see `docs/CHANGELOG.md` and `docs/RELEASE_PLAN.md` for the full list of changes.

## 1. Docker Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     docker-compose.yml (prod-like)               │
│                                                                   │
│  ┌────────────┐      ┌──────────────────┐      ┌──────────────┐ │
│  │  frontend  │─────▶│     backend       │────▶│      db      │ │
│  │  nginx     │ /api │  gunicorn+Django  │      │  postgres:16 │ │
│  │  :80→8080  │      │  :8000            │      │  :5432       │ │
│  └────────────┘      └──────────────────┘      └──────────────┘ │
│   built from           built from                 named volume  │
│   frontend/Dockerfile   backend/Dockerfile          postgres_data│
└─────────────────────────────────────────────────────────────────┘
```

- **`frontend`** — multi-stage build: `node:20-alpine` builds the Vite production bundle, then `nginx:1.27-alpine` serves the static files. Nginx also reverse-proxies `/api/`, `/admin/`, and `/static/` to the `backend` service, so the SPA's existing relative `/api` base URL (`frontend/src/services/api.js`) works with zero configuration — the same pattern the Vite dev proxy already uses natively.
- **`backend`** — `python:3.12-slim`, installs `requirements.txt` (now including `gunicorn` and `whitenoise`), runs migrations and `collectstatic` on container start via `docker-entrypoint.sh`, then serves via Gunicorn (never `runserver`). WhiteNoise serves Django's own static assets (admin CSS/JS, DRF browsable API) directly from the app container.
- **`db`** — official `postgres:16-alpine` image with a named volume (`postgres_data`) for persistence across restarts. Credentials come entirely from environment variables (`.env`, gitignored).

A second file, **`docker-compose.dev.yml`**, gives a containerized hot-reload inner loop (Django `runserver` + Vite dev server, bind-mounted source) as an *alternative* to the native venv/`npm run dev` workflow — it does not replace it. The native workflow is untouched and remains the default/documented path for day-to-day development.

## 2. Running Locally with Docker

### Production-like environment

```bash
cp .env.example .env
# edit .env — at minimum change POSTGRES_PASSWORD/DB_PASSWORD (must match) and SECRET_KEY

docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API directly: http://localhost:8000/api/
- Backend health check: http://localhost:8000/api/health/
- Postgres: localhost:5432 (only exposed for local inspection/psql; not required by the app)

Stop and remove containers (data persists in named volumes):
```bash
docker compose down
```

Stop and wipe all data (Postgres, backups, logs):
```bash
docker compose down -v
```

### Docker-based dev inner loop (optional)

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

- Frontend (Vite dev server, HMR): http://localhost:5173
- Backend (Django `runserver`, auto-reload): http://localhost:8000

Source directories are bind-mounted, so edits on the host are reflected immediately in both containers, matching the native dev experience.

### Native local development (unchanged)

The pre-existing workflow still works exactly as before and remains the primary documented path:
```bash
cd backend && source venv/bin/activate && python manage.py runserver 0.0.0.0:8000
cd frontend && npm run dev
```

## 3. Running Migrations

Migrations run automatically on every `backend` container start (see `backend/docker-entrypoint.sh`) — this is safe to repeat since Django's migration runner is idempotent (already-applied migrations are skipped). To run migrations manually against a running stack:

```bash
docker compose exec backend python manage.py migrate
```

To make a new migration after a model change (same as native dev):
```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

## 4. Creating a Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

## 5. Environment Variables

Three example files, one per concern:

| File | Consumed by | Purpose |
|---|---|---|
| `.env.example` (root) | `docker-compose.yml` / `docker-compose.dev.yml` | Postgres credentials, host port mappings, values forwarded into the backend container via `env_file` |
| `backend/.env.example` | Django (native venv or container) | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_*`, `CORS_*`, `CSRF_TRUSTED_ORIGINS` |
| `frontend/.env.example` | Vite build (`npm run build` / Docker build stage) | `VITE_API_BASE_URL` — build-time only, baked into the JS bundle, not readable at container runtime |

Copy each to its non-`.example` counterpart before use; none are committed (see `.gitignore`).

**Note on `DB_NAME` semantics:** `backend/config/settings.py` resolves `DB_NAME` differently depending on `DB_ENGINE` — for SQLite it's treated as a filesystem path (resolved relative to `BASE_DIR`); for PostgreSQL (or any non-SQLite engine) it's used as-is as a plain database name. This was fixed as part of this pass (previously `DB_NAME` was always path-resolved, which silently broke `DB_NAME=karosl` for Postgres — see `docs/CHANGELOG.md`).

**Note on Vite env vars:** `VITE_API_BASE_URL` is compiled into the JS bundle at `docker build` time (`ARG`/`ENV` in `frontend/Dockerfile`), not read at container runtime — changing it requires rebuilding the frontend image, unlike backend env vars which take effect on container restart.

## 6. Static and Media Files — Current State & Cloud Storage Plan

Reviewed what KarosL persists to disk today, ahead of introducing S3:

| Data | Where it lives today | Plan |
|---|---|---|
| Django static assets (admin CSS/JS, DRF browsable API) | `backend/staticfiles/` (`STATIC_ROOT`), served by WhiteNoise from inside the container | **Local-only, staying local.** Small, versioned with the code, no reason to move to S3. |
| Backup JSON exports (`BackupService.create_backup`) | `backend/backups/*.json` on local disk, path fixed at `settings.BASE_DIR / "backups"` | **Local-only for now.** Persisted via the `backend_backups` named Docker volume so it survives container restarts, matching current local-dev behavior. **Will move to S3** before real multi-instance/ECS deployment, since local disk in an ephemeral cloud container won't survive redeploys or scale past one instance. |
| CSV/XLSX exports (`ExportService`) | **Nowhere** — generated in memory and streamed directly as the HTTP response body, never written to disk | Nothing to migrate; this pattern is already cloud-friendly as-is. |
| Receipt PDFs (`reportlab`) | **Nowhere** — generated in memory per-request in `apps/payments/views.py`'s `_generate_pdf_receipt`, streamed directly, never written to disk | Nothing to migrate; already cloud-friendly. |
| User file uploads | **None exist.** No `MEDIA_ROOT`, no `FileField`/`ImageField` anywhere in the models. | N/A — nothing to plan for until a feature actually needs it. |

**Bottom line:** the only genuine "local disk that needs to become S3 later" item is the backup JSON files. Everything else is either static application code (stays local) or already generated in-memory with no disk footprint. No S3 integration was implemented in this pass, per scope — this section only documents the plan.

**Re-reviewed during the 2026-08-24 operational cleanup sprint**: confirmed `BackupService`'s local JSON
export is still a live, working, Super-Admin-gated feature (not dead code) — reachable at
`frontend/src/pages/Backup.jsx`, gated by `CanManageBackups`
(`docs/SECURITY_HARDENING.md`), genuinely persisted via the `backend_backups` volume as documented above. It
remains intentionally narrower in scope than the S3 `pg_dump` pipeline (§12) — that hasn't changed and isn't
being changed. **Proposed migration path, documented only, not implemented this pass**: `BackupService.create_backup`
could additionally upload its JSON output to S3 (same bucket, a new prefix such as `manual-backups/`) as a
durability improvement, without changing its restore behavior or 8-model scope — no evidence this is an
active need yet (the volume-backed local storage has worked fine), so it wasn't built speculatively.
**Separately fixed this pass**: 153 backup JSON files that predated a 2026-07-29 `.gitignore` fix
(`backend/backups/`) were still tracked in git — `git rm --cached` removed them from tracking (they remain
on disk; nothing was deleted).

## 7. Health Checks

- **Endpoint:** `GET /api/health/` (`apps/core/views.py`) — no authentication required (container orchestrators can't hold a token). Runs `SELECT 1` against the database; returns `{"status": "ok", "database": "ok"}` / HTTP 200 when healthy, `{"status": "degraded", "database": "unavailable"}` / HTTP 503 otherwise.
- **Backend container:** Docker `HEALTHCHECK` (`backend/Dockerfile`) curls this endpoint every 30s.
- **Frontend container:** Docker `HEALTHCHECK` hits nginx's `/healthz` (static 200 response, `frontend/nginx.conf`) — confirms nginx itself is serving, independent of backend health.
- **Postgres:** `pg_isready` healthcheck in `docker-compose.yml`; `backend` has `depends_on: db: condition: service_healthy` so it won't start migrating against a database that isn't accepting connections yet.

## 8. Known Limitations

- **CI exists** (`.github/workflows/ci.yml`) but stops at verification: it runs the backend suite against SQLite *and* PostgreSQL, the frontend lint/test/build, and a build of both images. It does **not** push images to a registry and does **not** deploy — the repo is public, so no deployment credentials live in it. Deployment stays the manual, deliberate path in `docs/AWS_EC2_DEPLOYMENT.md`.
- No S3 integration **inside the application** yet (see section 6) — `BackupService`'s JSON exports are still local-disk-only and will not survive a redeploy on most cloud container platforms. Database backups themselves are covered: `scripts/backup-to-s3.sh` ships nightly `pg_dump`s to S3 from the host (§12), which is the more complete of the two since it also captures users, tokens, and the audit log.
- Single backend replica assumed. Running multiple `backend` replicas would race on the migrate-on-start entrypoint step; harmless with Postgres (Django wraps migrations transactionally and a second replica's migrate is a no-op) but worth moving to a dedicated one-shot migration step (e.g. an init container or deploy-time job) before scaling out.
- No HTTPS/TLS termination in this **local** compose setup — deliberately. On AWS staging, TLS is terminated by the same frontend nginx via bind-mounted Let's Encrypt certificates and the `docker-compose.https.yml` overlay, so no image differs between local and staging (`docs/DOMAIN_HTTPS_PLAN.md`).
- The `backend`/`frontend` Docker images are not yet pushed to any registry — building is entirely local for this phase.

## 9. Next Steps Toward AWS Deployment

**AWS staging (Phase 2) is DEPLOYED as of 2026-07-29** — the same Compose stack on one `t3.micro` in `eu-north-1` (instance `i-0afd1871b46296500`), over HTTP, with PostgreSQL still in a container. Nothing about the Docker architecture above changed to make this work; only environment values differed.

- `docs/AWS_STAGING_CHECKLIST.md` — account safety gate, EC2 plan, security group rules (incl. why 5432 must never be public), server setup, verification, cleanup.
- `docs/AWS_EC2_DEPLOYMENT.md` — the command runbook (connect → install Docker → clone → `.env` → build → migrate → superuser → logs → troubleshooting).
- `scripts/server-setup.sh`, `scripts/deploy-staging.sh`, `scripts/docker-logs.sh` — optional helpers, though
  `deploy-staging.sh` is no longer *only* a manual helper — since 2026-08-19 it's also what CI runs
  automatically on push to `cloud-deployment`. Full pipeline reference: `docs/CI_CD.md`.

> ⛔ **No AWS deployment proceeds before an AWS Budget with email alerts is configured.** See `docs/AWS_DEPLOYMENT_PLAN.md`.

**Three env differences that make staging work** (each one silently breaks the deployment if missed): `FRONTEND_PORT=80` (the default 8080 is not open in the security group); `ALLOWED_HOSTS` must add the EC2 public IP **and keep `localhost`** (the backend container's `HEALTHCHECK` curls `localhost:8000`, so dropping it marks the container permanently unhealthy); and `CSRF_TRUSTED_ORIGINS`/`CORS_ALLOWED_ORIGINS` must be `http://<EC2_PUBLIC_IP>` — scheme included, no trailing slash.

Beyond staging:

1. Push `backend`/`frontend` images to a registry (Amazon ECR).
2. ~~Get backups off the instance~~ — **done for staging (2026-08-01)**: `scripts/backup-to-s3.sh` plus a systemd timer ships a verified nightly `pg_dump` to a private, versioned, lifecycle-managed S3 bucket using an EC2 instance role (no AWS keys on the box). See §12. **Still open:** moving `BackupService`'s own `backend/backups/*.json` exports to S3 (swap `BackupService.BACKUP_DIR` for an S3-backed storage backend — the read/write call sites are already isolated to `apps/backup/services.py`, so this is a contained change).
3. ~~Replace the local Postgres container with Amazon RDS (PostgreSQL)~~ — **done (2026-08-19)**: only `DB_HOST`/`DB_PORT`/credentials changed via env vars, exactly as designed here. The container itself is deliberately still running as a rollback safety net, not yet decommissioned. See `docs/RDS_MIGRATION.md`.
4. Run the migrate-on-start entrypoint step as a one-shot ECS task (or equivalent) instead of every replica's container start, ahead of scaling `backend` beyond one instance.
5. ~~Terminate TLS~~ — **done for staging (2026-07-31)** at the frontend nginx with Let's Encrypt, not at a load balancer, which keeps the no-ALB cost guardrail intact. An ALB with ACM only becomes relevant at Phase 6, if multi-instance scaling ever does. See `docs/DOMAIN_HTTPS_PLAN.md`.
6. ~~Add a CI pipeline~~ — **done 2026-08-01** (`.github/workflows/ci.yml`): three parallel jobs running the backend suite on a SQLite/PostgreSQL matrix, the frontend lint/test/build, and a `buildx bake` of both images from a clean checkout. Triggers on pushes to `dev`/`cloud-deployment` and on every pull request. **Still open:** pushing images to ECR on merge, which is the part that needs AWS credentials in the repo and is therefore a separate, deliberate decision.
7. Wire container logs to CloudWatch (or equivalent) instead of the local `backend_logs` volume.

## 10. Logging & Troubleshooting

The same commands work identically on a laptop and on an EC2 staging host — that portability is the main practical payoff of the Compose-everywhere approach.

### Staging is stopped, or broken after a restart — start here

```bash
./scripts/verify-staging.sh        # is it actually up? read-only, safe any time
./scripts/recover-staging.sh       # stopped -> running -> verified, one command
```

Run both from your **workstation**, not the instance. Full detail in `docs/DOMAIN_HTTPS_PLAN.md` §9.

**Do not trust `docker compose ps` here.** After a restart the containers come back with the *old* hostname baked into their stored environment, and their healthchecks hit `localhost`, so all three report `healthy` while Django returns 400 to every API call and nginx serves a certificate for a hostname that no longer resolves. The failure is only visible from outside, over the real hostname.

### Diagnostic commands

```bash
docker compose ps                                          # service status + health
docker compose logs backend                                # full backend log
docker compose logs -f backend                             # follow live
docker compose logs --tail=100 --since 10m backend         # bounded / time-windowed
docker compose logs frontend                               # nginx access + error log
docker compose logs db                                     # postgres

docker compose exec backend python manage.py check         # Django config check
docker compose exec backend python manage.py check --deploy  # security-settings review
docker compose exec backend python manage.py migrate       # apply migrations manually
docker compose exec backend python manage.py migrate --check  # exit 0 = nothing pending
docker compose exec backend python manage.py showmigrations
docker compose exec backend python manage.py createsuperuser

docker compose exec backend tail -100 /app/logs/karosl.log # Django's own log file
docker compose exec db psql -U karosl_user -d karosl -c '\dt'
docker stats --no-stream                                   # CPU/memory pressure
df -h                                                      # disk full breaks builds and Postgres
```

Helper: `./scripts/docker-logs.sh --status` (status + resources + disk), `./scripts/docker-logs.sh --errors` (grep recent logs for tracebacks), `./scripts/docker-logs.sh backend -f`.

### Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `DisallowedHost` / "Invalid HTTP_HOST header" | The host the browser used is not in `ALLOWED_HOSTS`. Nginx forwards the real `Host` header (`proxy_set_header Host $host`), so Django sees the IP/domain the user typed. | Add it to `ALLOWED_HOSTS`, then `docker compose up -d`. On AWS this recurs whenever an auto-assigned public IP changes. |
| Backend container `unhealthy`, but the app works | `ALLOWED_HOSTS` is missing `localhost`. The container's `HEALTHCHECK` curls `http://localhost:8000/api/health/` from inside itself; Django 400s an unlisted Host. | Keep `localhost,127.0.0.1` in `ALLOWED_HOSTS`, always. |
| CSRF verification failed / 403 on login | `CSRF_TRUSTED_ORIGINS` needs the **full origin with scheme, no trailing slash** — and the scheme must match what the browser actually uses. | `http://<host>` (or `https://<host>` once TLS exists). |
| CORS errors in the console | Usually means `VITE_API_BASE_URL` was set to an absolute URL, turning same-origin calls into cross-origin ones. Through the nginx proxy the SPA and API share an origin, so real CORS should not occur. | Set it back to `/api` and **rebuild** the frontend image — it is a build-time variable. |
| Everything redirects to `https://` and dies | `SECURE_SSL_REDIRECT` on with no TLS in front. | `docker-compose.yml` sets it (and the two cookie-secure flags) to `False` deliberately; leave them until TLS is real. |
| Infinite redirect loop **with** TLS working | TLS terminates at nginx, so the request reaches Django over plain HTTP and `request.is_secure()` is `False` — Django 301s to HTTPS on an already-HTTPS request, forever. | Set `USE_X_FORWARDED_PROTO=True` so `SECURE_PROXY_SSL_HEADER` trusts nginx's `X-Forwarded-Proto`. Handled by `docker-compose.https.yml`. Only safe because Gunicorn is loopback-bound and nginx overwrites the header. |
| nginx container will not start after enabling TLS | `ssl_certificate` points at a missing file — nginx refuses to start rather than serve without it. Usually the certificate has not been issued yet, or only `/etc/letsencrypt/live` was mounted, leaving the relative symlinks into `archive/` dangling. | Issue the certificate with the stage-1 (`docker-compose.acme.yml`) config first, and mount **`/etc/letsencrypt` whole** at the same path. |
| Frontend container `unhealthy` after enabling HTTPS | Its `HEALTHCHECK` runs `wget http://127.0.0.1/healthz`; if port 80 redirects everything, wget follows to `https://127.0.0.1/` and fails certificate verification against the hostname. | Keep `/healthz` served on port 80 ahead of the catch-all redirect (`deploy/nginx/staging-https.conf.template`). |
| Backend reports healthy but the database is down | With `SECURE_SSL_REDIRECT` on, the backend `HEALTHCHECK` curls Gunicorn directly with no `X-Forwarded-Proto`, so Django answers 301 — and `curl -f` treats 301 as success, so the check passes without testing anything. | `SECURE_REDIRECT_EXEMPT = [r'^api/health/$']` in `backend/config/settings.py`. |
| Certificate expired after ~60–90 days | Renewal needs port **80** for the `http-01` challenge at every renewal, not just at issuance. Closing 80 after HTTPS works breaks it silently. | Keep 80 open; verify with `sudo certbot renew --dry-run`. |
| The **bare-IP** certificate expires after ~6 days, not ~60–90 | This is expected and by design, not a bug — Let's Encrypt IP-address certificates are mandatorily short-lived (~160h). Don't apply the 60–90 day mental model from the row above to this cert. | `docs/HTTPS_IP_CERTIFICATE.md`. Verify with `sudo /opt/certbot-venv/bin/certbot renew --cert-name <IP> --dry-run`. |
| `password authentication failed` / backend restart loop | `POSTGRES_PASSWORD` ≠ `DB_PASSWORD`; or `DB_HOST` is `localhost` instead of `db`; or `POSTGRES_PASSWORD` was changed after the volume was initialized — Postgres only reads it when creating an empty data directory. | Make the two match; use `DB_HOST=db`; to change an existing password use `ALTER USER` inside the db container (or `docker compose down -v`, which **destroys all data**). |
| Migration errors | The entrypoint runs `migrate --noinput` before Gunicorn starts, so a failure means the container never serves traffic. It also gives up if `db` is not healthy within ~60s. | `docker compose logs backend`, `showmigrations`; restart once `db` is healthy. |
| Frontend loads, API calls fail | Backend down, still starting, or unreachable on the compose network. | `docker compose exec frontend wget -qO- http://backend:8000/api/health/` isolates the nginx→gunicorn hop from browser→nginx. `502` in the nginx log = backend down; `404` = routing. |
| Django admin unstyled / DRF browsable API bare | `collectstatic` did not run, or `/static/` is not reaching the backend. WhiteNoise serves these from inside the backend container; nginx proxies `/static/` through. | Look for `Collecting static files...` in the backend log; `docker compose exec backend ls /app/staticfiles`. The SPA's own assets are served by nginx from its image and are unrelated. |
| "Media files missing" | There are none. KarosL has no `MEDIA_ROOT` and no `FileField`/`ImageField`; receipt PDFs and CSV/XLSX exports are generated in memory and streamed (§6). | Nothing to fix — the feature does not exist yet. |
| Port 80/8080 already in use | A host web server (Apache/nginx) is bound to it. | `sudo ss -tlnp \| grep :80`, then disable the offending service or change `FRONTEND_PORT`. |
| Build dies with no clear error on a small host | Out of memory during the frontend `npm run build`. | Add swap (`docs/AWS_EC2_DEPLOYMENT.md` §4.5) or build on a bigger machine and push images to a registry. |
| `compose build requires buildx 0.17.0 or later` | Amazon Linux 2023's docker package ships buildx 0.12.1; Compose v2.30+/v5 delegates building to buildx and rejects anything older. Hit for real on an AL2023 `t3.micro`. | Install a current buildx CLI plugin — `docs/AWS_EC2_DEPLOYMENT.md` §4.3b. `scripts/server-setup.sh` now does this automatically. Ubuntu's `docker-ce` packages are unaffected. |
| `readonly variable` when scripting an id into a shell var | `UID` (and `EUID`, `PPID`) are readonly in bash. Assigning `UID=$(...)` silently fails and the shell's own uid (e.g. `1000`) is substituted instead — which then reaches the API as a bogus primary key. Cost a false "assign occupancy failed" during the staging smoke test. | Never use `UID` as a variable name in scripts. Use `UNIT_ID`, `unit_id`, etc. |
| `docker compose exec -T` eats the rest of a script | `exec -T` reads stdin. Inside a heredoc or piped script it consumes everything after its own line, so subsequent commands silently never run. | Always append `< /dev/null` to a non-interactive `docker compose exec -T`. |

## 11. Observability

Everything below is read-only and works identically locally and on the EC2 staging host.

**Beyond local `docker compose logs`**: staging ships Django's WARNING+ log, nginx's access/error logs, and
backup run output to CloudWatch Logs, with alarms on EC2 health, disk, and backup failures notifying via
SNS email. Full reference, including the IAM policy and troubleshooting: `docs/CLOUDWATCH_MONITORING.md`.

### Logs

```bash
docker compose logs backend                 # Django / Gunicorn
docker compose logs -f backend              # follow live
docker compose logs --tail=100 backend      # bounded
docker compose logs --since 15m backend     # time-windowed
docker compose logs frontend                # nginx access + error log
docker compose logs db                      # PostgreSQL
docker compose logs                         # all services, interleaved

# Django's own log file, on the backend_logs volume
docker compose exec backend tail -100 /app/logs/karosl.log
```

Helper: `./scripts/docker-logs.sh backend -f`, `./scripts/docker-logs.sh --errors`.

### Counting problems rather than eyeballing them

```bash
docker compose logs backend  2>&1 | grep -ciE 'traceback|ERROR '   # app errors
docker compose logs db       2>&1 | grep -ci FATAL                 # db failures
docker compose logs frontend 2>&1 | grep -cE '" 5[0-9][0-9] '      # nginx 5xx
docker compose logs frontend 2>&1 | grep -cE '" 4[0-9][0-9] '      # nginx 4xx
```

A 4xx count above zero is normal — it includes every deliberate 401 from an unauthenticated probe. A **5xx count above zero is a real signal.**

### Containers, resources, disk

```bash
docker compose ps                      # status + health of each service
docker compose ps -a                   # includes exited/failed containers
docker ps -a --filter status=exited    # failed containers specifically
docker inspect -f '{{.State.Health.Status}} restarts={{.RestartCount}}' karosl-backend-1
docker stats --no-stream               # per-container CPU / memory
free -h                                # host memory + swap
df -h /                                # host disk — a full disk breaks builds and Postgres
docker system df                       # image / volume / build-cache usage
```

Helper: `./scripts/docker-logs.sh --status` bundles status, resources, and disk in one call.

### Application state

```bash
docker compose exec backend python manage.py check            # config sanity
docker compose exec backend python manage.py check --deploy   # security posture
docker compose exec backend python manage.py migrate --check   # exit 0 = nothing pending
docker compose exec backend python manage.py showmigrations
curl -s localhost/api/health/                                  # liveness + DB connectivity
```

## 12. Backup & recovery (staging, PostgreSQL in a container)

**Full reference, including the IAM policy, retention design, restore-script safety guarantees, and the
`[EVENT]` log markers both scripts emit for future CloudWatch monitoring:
`docs/S3_BACKUP_ARCHITECTURE.md`.** This section stays the quick-reference/manual-procedure version.

**Since 2026-08-19, the live database is Amazon RDS** (`docs/RDS_MIGRATION.md`), with RDS's own automated
backups on top of the mechanisms below. The `db` container and its `postgres_data` volume are still
running as a rollback safety net (data frozen at the pre-migration point) but are no longer what the
application writes to — `pg_dump` against RDS, not the container, is now the live disaster-recovery story.
The container's own volume still survives `docker compose down` and an EC2 reboot, but **not**
`docker compose down -v` and **not** instance termination, if it's ever removed.

Two independent mechanisms exist; they are not interchangeable:

| Mechanism | Covers | Does not cover |
|---|---|---|
| **`pg_dump`** (below) | The entire database — every table, including `AuditLog` and `Backup` rows, users, and tokens | Nothing; it is a full logical dump |
| **KarosL's own `BackupService`** (`/api/backups/`, JSON exports on the `backend_backups` volume) | The 8 business models (Property, Section, Unit, PricingRule, Student, Occupancy, Payment, Receipt) | **Users, auth tokens, `AuditLog`, and `Backup` records** — by design (`docs/BUG_QUEUE.md`) |

For host loss, `pg_dump` is the one that matters.

### Automated: nightly dump to S3 (the normal path)

`scripts/backup-to-s3.sh` is the automated form of the manual procedure below — same `pg_dump` command, plus verification, compression, and an upload to S3. It is what a systemd timer runs unattended; run it by hand before doing anything risky.

```bash
cd ~/apps/karosl
./scripts/backup-to-s3.sh --dry-run    # dump and verify, upload nothing
./scripts/backup-to-s3.sh              # dump, verify, upload, prune local copies
```

**Setup, once per instance:**

```bash
# 1. Tell the script which bucket to use (never committed — the .env is gitignored)
echo "KAROSL_BACKUP_BUCKET=<bucket-name>" >> ~/apps/karosl/.env

# 2. Install the timer
sudo cp deploy/systemd/karosl-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now karosl-backup.timer

# 3. Confirm it is scheduled, then force one run to prove it works end to end
systemctl list-timers karosl-backup.timer
sudo systemctl start karosl-backup.service
journalctl -u karosl-backup.service -n 30 --no-pager
```

Four properties of this setup are deliberate and worth knowing:

- **No AWS keys on the box.** Access comes from the EC2 instance role `karosl-staging-backup-role`. Confirm with `aws sts get-caller-identity` (it should report the role, not a user) and by the absence of `~/.aws/credentials`.
- **The role has no `s3:DeleteObject`.** A compromised instance can write backups and read them back, but cannot erase backup history. Expiry is the bucket's lifecycle rules' job — 30 days for daily backups, 400 days for the one-per-month tier under `database/monthly/` — not the instance's. Full retention rationale in `docs/S3_BACKUP_ARCHITECTURE.md` §6.
- **The script verifies the dump before uploading** — non-zero size, `CREATE TABLE` statements present, `COPY` data blocks present. A 0-byte dump that looks successful in `ls` is the classic silent backup failure, and an exit code alone does not catch it.
- **`Persistent=true` on the timer.** Belt-and-braces: the instance stays running continuously during Live
  Pilot, but if it is ever stopped (maintenance, a pause between pilots), a missed run is not silently
  skipped to the following night — it fires shortly after next boot instead. Proven, not just configured:
  after 18 days stopped, the 2026-08-19 audit watched the catch-up run fire ~4 minutes into the new boot and
  land in S3, via `journalctl`.

The manual procedure below remains correct and is what the script runs. Use it when you want to see each step, or when the script cannot run.

### Take a dump

Credentials are read from the container's own environment, so they never appear in a command line or shell history:

```bash
cd ~/apps/karosl
mkdir -p ~/backups && chmod 700 ~/backups
OUT=~/backups/karosl-staging-$(date +%F-%H%M).sql

docker compose exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < /dev/null > "$OUT"

chmod 600 "$OUT"
ls -l "$OUT"                      # confirm it exists and is non-trivial in size
head -1 "$OUT"                    # confirm it is a real dump header
grep -c 'CREATE TABLE' "$OUT"     # confirm schema is present
grep -c '^COPY '        "$OUT"    # confirm data blocks are present
```

A dump that exists but is 0 bytes is the classic silent failure — **always check the size**, not just the exit code.

### Copy it off the server

The instance is the single point of failure, so a backup that only lives on it is not a backup:

```bash
# From your workstation
scp -i ~/.ssh/karosl-staging-key.pem \
  ec2-user@<EC2_PUBLIC_IP>:'~/backups/karosl-staging-*.sql' ./
```

Store it somewhere that is not the EC2 instance. `scripts/backup-to-s3.sh` now does this automatically (uploading to the `database/` prefix, since 2026-08-19 — see `docs/S3_BACKUP_ARCHITECTURE.md` §2 for the key layout and why older `pg_dump/<year>/...` objects are left where they are); `scp` remains the manual fallback, and off-box local storage is still infinitely better than on-box.

### Restore into a disposable database — never over the live one

**Automated (the normal path):**

```bash
./scripts/restore-from-s3.sh --list      # see what's available
./scripts/restore-from-s3.sh --latest    # download, decompress, restore into karosl_restore_test, verify, drop
```

This script **cannot** reach the live database under any flag combination — it hard-refuses if asked to
target the live `POSTGRES_DB` name. See `docs/S3_BACKUP_ARCHITECTURE.md` §5 for the full design and the
2026-08-19 end-to-end verification evidence.

**Manual**, for when you want to see each step or the script can't run:

```bash
aws s3 ls s3://<bucket>/database/ --recursive --region eu-north-1
aws s3 cp s3://<bucket>/database/<dump>.sql.gz . --region eu-north-1
gunzip <dump>.sql.gz

# Create a throwaway database alongside the live one
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE karosl_restore_test;"' < /dev/null

# Restore the dump into it
docker compose exec -T db sh -c \
  'psql -q -U "$POSTGRES_USER" -d karosl_restore_test' < ~/backups/<dump>.sql

# Compare row counts against the live database, then clean up
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE karosl_restore_test;"' < /dev/null
```

⚠️ **Risk note.** Restoring into the live `karosl` database with a `--clean` dump **drops and recreates every table**, destroying anything created since the dump. Never point a restore at the live database to "test" it. The disposable-database pattern above gives the same confidence with none of the risk. A real production restore (replacing live data on purpose) is a separate, manual, human-supervised procedure — `docs/S3_BACKUP_ARCHITECTURE.md` §5.

### Confirm the backup is not publicly reachable

Backups live in `~/backups` (mode 700) on the instance, outside any container and outside nginx's web root, so there is no URL that serves them. Verify rather than assume:

```bash
curl -s -o /dev/null -w '%{http_code}\n' localhost/backups/<dump>.sql   # expect 404
stat -c '%A %U:%G' ~/backups                                            # expect drwx------
```
