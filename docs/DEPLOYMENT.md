# Deployment Guide

This document covers deploying KarosL's containers. For architecture rationale and day-to-day Docker usage (dev inner loop, migrations, superuser creation), see `docs/DEVOPS.md` first — this file focuses on the build/run/verify mechanics and the current deployment target (local, production-like).

## Deployment targets

| Target | Status | Where |
|---|---|---|
| **Local production-like** (Docker Compose on a dev machine) | ✅ Verified | This document |
| **AWS staging** (single EC2 + Docker Compose) | ✅ **Live since 2026-07-29** — `eu-north-1`, instance `i-0afd1871b46296500` | `docs/AWS_STAGING_CHECKLIST.md` + `docs/AWS_EC2_DEPLOYMENT.md` |
| **AWS staging — domain + HTTPS** | ✅ Live since 2026-07-31 | `docs/DOMAIN_HTTPS_PLAN.md` |
| **AWS production** (RDS, S3, CloudWatch) | ⛔ Not started, deliberately deferred | `docs/AWS_DEPLOYMENT_PLAN.md` Phases 3–6 |

## Required pre-deployment step for any AWS target: cost safety

> ⛔ **No AWS deployment should proceed before budget alerts are configured.**

Before creating **any** AWS resource — EC2, EBS, Elastic IP, RDS, S3, NAT Gateway:

1. **Create an AWS Budget** with an explicit monthly ceiling ($10–20/month for single-EC2 staging).
2. **Configure budget email alerts** at 50% / 80% / 100% plus forecasted-to-exceed, and **confirm the first alert email actually arrives**.
3. **Confirm the region** — pick one, write it down, create everything there.
4. **Confirm no NAT Gateway will be created** — the host sits in a public subnet behind a security group (~$32/month saved, always on, for zero benefit here).
5. **Use the smallest reasonable EC2 instance** — `t3.micro`/`t2.micro` to start; resize only on observed pressure.
6. **Avoid a load balancer for staging** — reach the app on the instance's public IP.
7. **Avoid RDS for the first staging deployment** unless explicitly chosen — PostgreSQL stays in the `db` container.
8. **Know the cleanup steps before you create anything** — `docker compose down`, `docker system prune -f`, stop the instance after each session; on teardown, terminate the instance, delete the EBS volume, release any Elastic IP, delete snapshots, then confirm in Cost Explorer 24–48h later that the run-rate actually dropped.

Full rationale and the per-phase cost traps: `docs/AWS_DEPLOYMENT_PLAN.md` ("Required pre-deployment step" and Task 2). The staging tick-list is `docs/AWS_STAGING_CHECKLIST.md`.

## Current Deployment Target: Local Production-Like Environment

KarosL does not yet deploy to any cloud provider. This phase proves the application runs correctly in containers, outside the developer's native venv/npm setup, as the direct prerequisite to an AWS deployment (see `docs/DEVOPS.md` §9 for the planned path).

## Prerequisites

- Docker Engine + Docker Compose v2 (`docker compose version`)
- Ports 8080, 8000, and 5432 free on the host (or override via `.env` — see below)

## Build & Run

```bash
git clone <repo>
cd Karos_L
cp .env.example .env
# Edit .env: at minimum set a real POSTGRES_PASSWORD/DB_PASSWORD (must match
# each other) and a real SECRET_KEY for anything beyond local testing.

docker compose up --build
```

This builds both images and starts all three services. On first start, the `backend` container's entrypoint waits for Postgres to accept connections, then runs `migrate` and `collectstatic` automatically before Gunicorn starts.

Once healthy:
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000/api/
- Health check: http://localhost:8000/api/health/

## Creating the First User

The Docker environment starts with an empty database (migrations only, no seed data or demo account):

```bash
docker compose exec backend python manage.py createsuperuser
```

Log in at http://localhost:8080/login with that account.

## Rebuilding After Code Changes

```bash
docker compose up --build            # rebuilds changed images, restarts services
docker compose build backend         # rebuild just one image
docker compose restart backend       # restart without rebuilding
```

## Stopping

```bash
docker compose down       # stop containers, keep data (named volumes persist)
docker compose down -v    # stop containers AND delete all data (Postgres, backups, logs)
```

## Verification Checklist

Run through this after any change to the Docker setup, in addition to the automated test suites:

1. `docker compose build` — both images build without error.
2. `docker compose up` — all three services reach a running state; `db` reports healthy before `backend` starts migrating.
3. `docker compose logs backend` — confirms `Applying database migrations...` then `Collecting static files...` then Gunicorn's boot log, with no traceback.
4. `curl http://localhost:8000/api/health/` — returns `{"status": "ok", "database": "ok"}`.
5. `curl http://localhost:8080/` — returns the SPA's `index.html`.
6. Open http://localhost:8080 in a browser — SPA loads, no console errors about failed API calls.
7. Create a superuser (above), log in through the UI — confirms frontend → nginx → backend → Postgres → response, end-to-end.
8. Create a property and register an occupant through the UI (or via the Administration API) — confirms a real write path through to Postgres.
9. Independently, run `cd backend && source venv/bin/activate && python manage.py test` and `cd frontend && npm run build && npm test` — confirms the native (non-Docker) workflow is untouched by these changes.

See the end of this pass's summary message (or `docs/CHANGELOG.md`) for the actual results of this checklist as executed.

## Environment Variables Reference

See `docs/DEVOPS.md` §5 for the full table of which `.env.example` file feeds which service. Never commit real `.env` files — only `.env.example` files are tracked in git.

## Known Limitations

See `docs/DEVOPS.md` §8 for the full list (no CI/CD, no S3 yet, single-replica assumption, no TLS termination locally). These are expected at this stage of the Cloud Engineering Phase and are not regressions.

## AWS Staging — deployed and verified 2026-07-29

Staging is **live** in `eu-north-1` on instance `i-0afd1871b46296500` (`karosl-staging-ec2`), behind security group `karosl-staging-sg`, with PostgreSQL still in a container. Full record, commands, and troubleshooting: `docs/AWS_EC2_DEPLOYMENT.md`.

**Post-deployment verification (2026-07-29):** 14/14 smoke-test workflows pass through the public IP; all three containers healthy with 0 restarts and 0 errors in logs; security review all-pass (`DEBUG=False`, secrets only in the server `.env`, only port 80 public, 8000 on loopback, 5432 unpublished, SSH restricted, no demo account). Details in `docs/AWS_STAGING_CHECKLIST.md` §4 and `docs/PROJECT_STATE.md`.

- **Observability** — logs, error counting, resource and disk inspection: `docs/DEVOPS.md` §11.
- **Backup & recovery** — `pg_dump`, copying the dump off the instance, and the safe disposable-database restore pattern: `docs/DEVOPS.md` §12. Full S3 architecture (bucket, IAM, retention, `scripts/restore-from-s3.sh`'s safety guarantees): `docs/S3_BACKUP_ARCHITECTURE.md`.

### HTTPS — added 2026-07-31

Staging is reachable over **HTTPS at a domain**, with a trusted Let's Encrypt certificate, an HTTP→HTTPS redirect,
and automated renewal. TLS terminates at the existing frontend nginx — **no load balancer, no ACM, no CloudFront,
no Elastic IP**, and exactly one new inbound port (443).

The domain is an [sslip.io](https://sslip.io) hostname derived from the public IP, which gives real browser-trusted
HTTPS at zero cost with no registrar. Its one cost is that the hostname changes when the IP does — see the restart
runbook in `docs/DOMAIN_HTTPS_PLAN.md` §9. **Move to a purchased domain before real users.**

Full record — domain and Elastic IP decisions, nginx/certbot design, Django settings, DNS guide, verification, and
rollback: **`docs/DOMAIN_HTTPS_PLAN.md`**.

### HTTPS via bare IP — added 2026-08-19

`https://<EC2_PUBLIC_IP>` also now shows a trusted certificate — a real Let's Encrypt IP-address certificate,
running **alongside**, not instead of, the sslip.io hostname path above. Short-lived by CA policy (~160h),
with automated renewal proven via a forced-renewal test. Full record: **`docs/HTTPS_IP_CERTIFICATE.md`**.

**Accepted staging limitations:** ~~no HTTPS~~ (resolved), ~~no automated backups~~ (resolved 2026-08-01 —
`scripts/backup-to-s3.sh` + a nightly systemd timer), single point of failure, ephemeral public IP.

### Cost safety

**Since the 2026-08-19 Live Pilot audit, the instance stays running continuously** — live-pilot data entry
needs the app reachable on the client's schedule, not only when an engineer starts it, and stopping between
sessions is what causes the public-IP-churn problem in the first place (see below). The instance has an
**auto-assigned public IP and no Elastic IP**, so nothing bills while stopped except the 10 GB EBS root
volume — that still matters if the pilot ever pauses:

```bash
aws ec2 stop-instances  --instance-ids i-0afd1871b46296500 --region eu-north-1
aws ec2 start-instances --instance-ids i-0afd1871b46296500 --region eu-north-1
```

After a start the **public IP changes**, so `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS` in the server's `.env` must be updated and `docker compose up -d` re-run — or just run `./scripts/recover-staging.sh`, which does exactly that. See `docs/AWS_EC2_DEPLOYMENT.md` §13.

### Redeploying a code change

```bash
ssh -i ~/.ssh/karosl-staging-key.pem ec2-user@<EC2_PUBLIC_IP>
cd ~/apps/karosl && ./scripts/deploy-staging.sh --pull
```

Three staging-only `.env` differences from local, each of which will bite if missed:
`FRONTEND_PORT=80` (default is 8080), `ALLOWED_HOSTS` must include the EC2 public IP **and keep `localhost`** (the backend container's healthcheck curls it), and `CSRF_TRUSTED_ORIGINS`/`CORS_ALLOWED_ORIGINS` must be `http://<EC2_PUBLIC_IP>` with scheme and no trailing slash.

Beyond staging, see `docs/DEVOPS.md` §9 and `docs/AWS_DEPLOYMENT_PLAN.md` Phases 3–6 for the recommended order of work (RDS, S3 for backups, TLS, CI pipeline, CloudWatch logging).
