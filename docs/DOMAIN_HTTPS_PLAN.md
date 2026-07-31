# Domain & HTTPS Plan — KarosL AWS Staging

**Status: IMPLEMENTED 2026-07-31.** Staging now serves HTTPS with a trusted Let's Encrypt certificate,
HTTP→HTTPS redirect, and automated renewal.

Scope guardrails held throughout: **no RDS, no NAT Gateway, no load balancer, no ECS/Fargate, no CloudFront, no
Elastic IP, no secrets committed, PostgreSQL never exposed, and exactly one new inbound port (443).**

---

## 1. Target architecture

```
                     User
                       │
                       ▼
              Domain name  <STAGING_DOMAIN>
                       │  DNS A record
                       ▼
              EC2 public IP  <EC2_PUBLIC_IP>
                       │  security group :80 (redirect + ACME), :443
                       ▼
   ┌───────────────────────────────────────────────────────────┐
   │ frontend container — nginx 1.27                           │
   │   TLS TERMINATES HERE (Let's Encrypt cert, bind-mounted)  │
   │   serves the React build; proxies /api /admin /static     │
   └───────────────────────────────────────────────────────────┘
                       │  internal compose network, plaintext HTTP
                       ▼
        backend container — Gunicorn/Django  (127.0.0.1:8000 on the host only)
                       │
                       ▼
        db container — PostgreSQL 16  (never published, not even to the host)
```

---

## 2. Domain decision

### Option A — EC2 public IP only

- Cheapest and simplest; nothing to configure.
- **No trusted HTTPS is possible.** Let's Encrypt does not issue certificates for bare IP addresses. The only
  alternatives are a self-signed certificate — which every browser blocks with a full-page interstitial, making
  it useless for anyone but the developer — or staying on plaintext HTTP.
- Acceptable only for short-lived throwaway staging that no one but the developer touches.

### Option B — a real domain or subdomain — **RECOMMENDED**

- Enables Let's Encrypt, hence real browser-trusted HTTPS.
- Human-readable and stable; survives an IP change with a DNS edit instead of a re-issued certificate.
- Easier for testers, and a prerequisite for anything resembling real use.

**Recommendation: Option B before any real user touches the app.** Plaintext HTTP means the login POST — username
and password — is readable by anyone on the network path. That, not convenience, is the reason this matters.

### What was chosen: Option B, via sslip.io

Staging uses **`<EC2_PUBLIC_IP with dots as dashes>.sslip.io`** (currently `51-20-144-52.sslip.io`).

sslip.io is a free public wildcard-DNS service: any hostname of the form `1-2-3-4.sslip.io` resolves to `1.2.3.4`
with no registration, no account, and no DNS records to create. Let's Encrypt treats it as an ordinary domain and
issues an ordinary certificate.

| | |
|---|---|
| **Why it was chosen** | Real, browser-trusted HTTPS today, at zero cost, with no registrar and no DNS provider. Removes the plaintext-login limitation immediately. |
| **What it costs** | The hostname is derived from the public IP, so **it changes whenever the IP changes** (see §3 and §9). |
| **When to move off it** | Before real users or a demo. Migrating to a purchased domain is one A record plus a re-run of `certbot certonly` — the nginx and Django configuration is already domain-agnostic. |

---

## 3. Elastic IP decision

**Decision: no Elastic IP allocated.** Not created automatically, and not to be created without explicit approval.

### The tradeoff, accurately

A correction to earlier documentation: since AWS began charging for all public IPv4 addresses, an Elastic IP
attached to a **running** instance costs the **same** as the auto-assigned public IP — about $0.005/hr
(~$3.65/mo). It is not an extra charge while running. The difference appears only when the instance is stopped.

| | Without Elastic IP (current) | With Elastic IP |
|---|---|---|
| Instance running | ~$3.65/mo public IPv4 | ~$3.65/mo — **the same** |
| Instance stopped | **$0** for the IP (~$0.80/mo EBS only) | ~$3.65/mo, still billing for an idle address |
| Address stability | Changes on every stop/start | Stable |
| DNS / certificate | sslip.io hostname changes with the IP; certificate must be re-issued | Set once, stays valid |

**Why no EIP here:** KarosL staging is deliberately stopped between sessions, which is exactly when an Elastic IP
would start costing money for nothing. The same account already demonstrates the trap — `dc-intern-backend` is a
**stopped** instance with an Elastic IP still attached, billing hourly while idle.

**The accepted cost** is the restart runbook in §9. If staging ever needs to stay up continuously, or gets a real
domain with real users, allocate an Elastic IP then — at that point it is free relative to running anyway.

---

## 4. Security group

`karosl-staging-sg` (`sg-065fb018e22aa18a5`) — **inbound**:

| Type | Protocol | Port | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | `<MY_IP>/32` | Administration only. Never `0.0.0.0/0`. |
| HTTP | TCP | 80 | `0.0.0.0/0` | **Still required** — see below. |
| HTTPS | TCP | 443 | `0.0.0.0/0` | The application. Added 2026-07-31 (`sgr-0b29986c961ba61aa`). |

Outbound: default allow-all (package repos, Docker Hub, GitHub, ACME).

### Why port 80 stays open after HTTPS works

1. **The HTTP→HTTPS redirect lives there.** Users type bare hostnames; closing 80 gives them a connection timeout
   instead of an upgrade to HTTPS.
2. **Let's Encrypt `http-01` validation uses it — at every renewal, not just at issuance.** Certificates last 90
   days and renew unattended. Closing port 80 breaks renewal *silently*, and the failure surfaces ~60 days later
   as an expired certificate.

### Never opened

**5432 (PostgreSQL), 8000 (Gunicorn), 5173 (Vite), and every Docker-internal port.** PostgreSQL is not published
to the host at all; Gunicorn is bound to `127.0.0.1` only. Verified closed from the internet after the change.

---

## 5. Nginx HTTPS design

The frontend image bakes `frontend/nginx.conf` in at build time, and rebuilding the frontend on a 916 MB
`t3.micro` is the documented OOM risk. So **TLS config is bind-mounted, never baked** — enabling HTTPS requires
no image rebuild at all.

Three design points, each of which was a real failure mode avoided:

- **The domain is injected, not hardcoded.** The official nginx image renders `/etc/nginx/templates/*.template`
  through `envsubst` at container start. `NGINX_ENVSUBST_FILTER=STAGING_DOMAIN` restricts substitution to that one
  variable, so nginx's own `$host`, `$uri`, and `$scheme` are not blanked out. **The real hostname therefore never
  enters a committed file.**
- **`/etc/letsencrypt` is mounted whole, read-only, at the same path.** `live/<domain>/*.pem` are *relative*
  symlinks into `archive/<domain>/`; mounting only the `live` subdirectory produces dangling links and nginx
  refuses to start.
- **Two stages, because nginx will not start if `ssl_certificate` points at a missing file.** The certificate
  cannot exist before nginx serves the challenge, and nginx cannot load the TLS config before the certificate
  exists. Stage 1 serves the ACME path over HTTP; stage 2 adds TLS.

### Files

| File | Role |
|---|---|
| `deploy/nginx/staging-http.conf.template` | Stage 1. Port 80, plus `/.well-known/acme-challenge/` from `/var/www/certbot`. Otherwise identical to `frontend/nginx.conf`. |
| `deploy/nginx/staging-https.conf.template` | Stage 2. Port 80 keeps ACME + `/healthz` and 301s the rest; port 443 terminates TLS and carries the full application location set. |
| `docker-compose.acme.yml` | Stage-1 overlay: mounts the HTTP template and the webroot. Changes nothing about Django, publishes no new port. |
| `docker-compose.https.yml` | Stage-2 overlay: publishes 443, mounts certificates and the HTTPS template, and flips the Django secure flags. |

The application location blocks (`/api/`, `/admin/`, `/static/`, `/healthz`, SPA `try_files`) are **copied
verbatim** from `frontend/nginx.conf`. Only `listen`/TLS directives and the redirect server are new — no rewrite
of working routing.

### Two healthcheck traps, both handled

- **`/healthz` stays on HTTP, un-redirected.** The frontend image's `HEALTHCHECK` runs
  `wget http://127.0.0.1/healthz` inside the container. Redirecting it would send wget to `https://127.0.0.1/`,
  which fails certificate verification against the hostname and marks a perfectly healthy container unhealthy.
- **`/api/health/` is exempt from Django's SSL redirect** (`SECURE_REDIRECT_EXEMPT`, `backend/config/settings.py`).
  The backend `HEALTHCHECK` curls Gunicorn directly, bypassing nginx, so the request carries no
  `X-Forwarded-Proto` and Django would answer with a 301. `curl -f` treats a 301 as success, so the healthcheck
  would keep reporting "healthy" while no longer testing the database connectivity it exists to test. This is not
  an external bypass: nginx still redirects every non-ACME HTTP request before it reaches Django.

### Certbot on Amazon Linux 2023

```bash
sudo dnf install -y certbot          # 2.6.0, in the amazonlinux repo — no EPEL needed
sudo mkdir -p /var/www/certbot
```

`python3-certbot-nginx` is **not** installed and must not be: nginx runs in a container and is not certbot-managed.
The `--webroot` plugin is used instead — `--standalone` cannot work, because the frontend container owns port 80.

```bash
# Always dry-run first: Let's Encrypt rate-limits duplicate certificates (5/week).
sudo certbot certonly --webroot -w /var/www/certbot -d <STAGING_DOMAIN> \
     --agree-tos -m <EMAIL> --non-interactive --dry-run

sudo certbot certonly --webroot -w /var/www/certbot -d <STAGING_DOMAIN> \
     --agree-tos -m <EMAIL> --non-interactive
```

**Where certificates live**

| Path | Contents |
|---|---|
| `/etc/letsencrypt/live/<STAGING_DOMAIN>/fullchain.pem` | Certificate + chain — this is what `ssl_certificate` points at |
| `/etc/letsencrypt/live/<STAGING_DOMAIN>/privkey.pem` | Private key (`ssl_certificate_key`), mode 600, root-owned |
| `/etc/letsencrypt/archive/<STAGING_DOMAIN>/` | The real files; `live/` holds relative symlinks into here |
| `/etc/letsencrypt/renewal/<STAGING_DOMAIN>.conf` | Renewal parameters recorded by certbot |

**Renewal.** The certbot RPM ships `certbot-renew.timer`:

```bash
sudo systemctl enable --now certbot-renew.timer
sudo certbot renew --dry-run          # exercises webroot + deploy hook without issuing
```

A deploy hook at `/etc/letsencrypt/renewal-hooks/deploy/reload-karosl-nginx.sh` reloads the container's nginx
after each renewal:

```sh
docker kill -s HUP karosl-frontend-1 2>/dev/null || true
```

`docker kill -s HUP` is used rather than `docker compose exec` because `exec -T` swallows the rest of a piped
script (`docs/DEVOPS.md` §10) and this hook runs non-interactively from the systemd timer.

---

## 6. Django settings for domain access

### Server `.env` (never committed)

```
DEBUG=False
ALLOWED_HOSTS=<STAGING_DOMAIN>,<EC2_PUBLIC_IP>,localhost,127.0.0.1,backend
CSRF_TRUSTED_ORIGINS=https://<STAGING_DOMAIN>
CORS_ALLOWED_ORIGINS=https://<STAGING_DOMAIN>
CORS_ALLOW_ALL_ORIGINS=False
STAGING_DOMAIN=<STAGING_DOMAIN>
```

- `CSRF_TRUSTED_ORIGINS` needs the **scheme, and no trailing slash**, and the scheme must match what the browser
  actually uses. `https://` here, not `http://` — a mismatch is the documented cause of 403-on-login.
- **Keep `localhost` and `127.0.0.1`** in `ALLOWED_HOSTS`: the backend `HEALTHCHECK` uses them.
- `<EC2_PUBLIC_IP>` is retained so the raw address still works for diagnostics.

### Secure cookies and redirect — set by `docker-compose.https.yml`, not `.env`

```yaml
SECURE_SSL_REDIRECT: "True"
CSRF_COOKIE_SECURE: "True"
SESSION_COOKIE_SECURE: "True"
USE_X_FORWARDED_PROTO: "True"
SECURE_HSTS_SECONDS: "300"
```

**They must be set in the overlay, not `.env`.** The base `docker-compose.yml` hardcodes the first three to
`"False"` in its own `environment:` block, and an `environment:` value outranks `env_file` — setting them in
`.env` alone would silently do nothing.

### Code changes in `backend/config/settings.py`

Three additions, all env-gated and defaulting to today's behaviour, so **local development and the local Compose
stack are unaffected**:

- **`SECURE_PROXY_SSL_HEADER`, gated behind `USE_X_FORWARDED_PROTO` (default off).** This is the setting whose
  absence would have taken the site down. With TLS terminating at nginx, the request reaching Django arrives over
  plain HTTP, so `request.is_secure()` is `False` and `SECURE_SSL_REDIRECT` redirects to HTTPS *forever* — an
  infinite loop. It is opt-in rather than tied to `DEBUG` because trusting a client-settable header is only safe
  when clients cannot bypass the proxy: true here (Gunicorn is loopback-bound and nginx always overwrites the
  header), false for anyone running Gunicorn exposed.
- **`SECURE_HSTS_SECONDS` made env-overridable**, defaulting to the previous one year. Staging uses **300
  seconds**, because HSTS is a browser-side commitment that outlives the deployment: the sslip.io hostname is
  derived from an ephemeral IP that will later belong to someone else, and a one-year pin with `includeSubDomains`
  and `preload` would follow that address around.
- **`SECURE_REDIRECT_EXEMPT = [r'^api/health/$']`** — see the healthcheck trap in §5.

> **Note:** `backend/config/settings_production.py` contains a `SECURE_PROXY_SSL_HEADER` line but is **dead code** —
> nothing imports it. `DJANGO_SETTINGS_MODULE` is `config.settings` (`backend/Dockerfile`, `manage.py`, `wsgi.py`).
> Do not "fix" HTTPS by editing that file; it has no effect.

**No frontend rebuild is needed for a domain change.** `VITE_API_BASE_URL=/api` is relative, so the bundle is
origin-agnostic — which is also why there is no mixed-content risk: API calls are same-origin by construction.

---

## 7. DNS setup

Registrar-agnostic. **Do not assume Route 53** — any registrar's DNS panel works.

**Root domain** (`example.com`):

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `<EC2_PUBLIC_IP>` (or Elastic IP) | 300 |

**Subdomain** (`app.example.com`):

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `app` | `<EC2_PUBLIC_IP>` (or Elastic IP) | 300 |

- Use an **A record to an IP**, not a CNAME — there is no AWS hostname to alias here.
- **Propagation takes time**: usually minutes, up to hours, bounded by the *previous* record's TTL. Set a low TTL
  *before* a planned IP change.
- Verify with `dig +short <domain>` or `getent hosts <domain>` — **not** the browser, which caches aggressively.
- **Do not request a certificate until DNS resolves to the server.** The `http-01` challenge fails otherwise, and
  failures count against the rate limit.
- If Route 53 is used later, a public hosted zone bills ~$0.50/mo — a real cost, not free.

**sslip.io needs none of this.** `51-20-144-52.sslip.io` resolves by construction; no record is created.

---

## 8. Implementation guardrails

Checked before any live change was made:

| # | Guardrail | Status |
|---|---|---|
| 1 | Domain confirmed | ✅ `51-20-144-52.sslip.io` |
| 2 | Elastic IP decision confirmed | ✅ none, explicitly |
| 3 | DNS A record resolves to the server | ✅ verified |
| 4 | Ports 80 and 443 open | ✅ 80 already; 443 added |
| 5 | Current HTTP app works | ⚠️ **failed initially** — fixed first (§9) |

Guardrail 5 was not a formality. The API was returning `400 DisallowedHost` before this sprint started; attempting
HTTPS on top of a broken app would have made the cause impossible to isolate.

---

## 9. Runbook: the public IP changed

**This happens on every stop/start**, and is the standing cost of running without an Elastic IP. It is what broke
staging on 2026-07-31.

Symptom: the SPA still loads (nginx serves static files regardless), but every API call returns
`Bad Request (400)`. It fails quietly from the outside — always check `/api/health/`, not just the home page.

```bash
# 1. Get the new IP
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --region eu-north-1 \
    --query 'Reservations[].Instances[].PublicIpAddress' --output text

# 2. On the server, update .env — the new sslip.io hostname is the new IP with dashes
cd ~/apps/karosl && cp .env .env.bak-$(date +%Y%m%d-%H%M%S)
#   ALLOWED_HOSTS=<NEW_DOMAIN>,<NEW_IP>,localhost,127.0.0.1,backend
#   CSRF_TRUSTED_ORIGINS=https://<NEW_DOMAIN>
#   CORS_ALLOWED_ORIGINS=https://<NEW_DOMAIN>
#   STAGING_DOMAIN=<NEW_DOMAIN>

# 3. Issue a certificate for the new hostname (stage-1 overlay first — no cert exists for it yet)
docker compose -f docker-compose.yml -f docker-compose.acme.yml up -d frontend
sudo certbot certonly --webroot -w /var/www/certbot -d <NEW_DOMAIN> --agree-tos -m <EMAIL> --non-interactive

# 4. Back to HTTPS
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

Also update the SSH source in the security group if the **admin** workstation IP has changed.

> **Rate limits.** Each restart yields a *new* hostname and therefore a new certificate. Let's Encrypt allows 50
> certificates per registered domain per week, counted against `sslip.io` — shared with every other user of the
> service. Frequent cycling can hit it. This is the strongest practical argument for a purchased domain.

---

## 10. Rollback

Every step is reversible, and none touches application code or data. `down -v` is never used.

```bash
# 1. Drop the overlay -> HTTP only, image's baked-in nginx.conf, secure flags off
cd ~/apps/karosl && docker compose -f docker-compose.yml up -d

# 2. Restore the previous origins
cp .env.bak-<timestamp> .env && docker compose up -d backend

# 3. Optional: stop renewals (certificates can be left in place; they are inert)
sudo systemctl disable --now certbot-renew.timer

# 4. Optional: close 443 again
aws ec2 revoke-security-group-ingress --region eu-north-1 \
    --group-id sg-065fb018e22aa18a5 --protocol tcp --port 443 --cidr 0.0.0.0/0
```

**One caveat:** browsers that already saw the HSTS header will refuse plaintext HTTP to that hostname until it
expires. The 300-second `max-age` keeps that window to five minutes — which is precisely why it is set short.

---

## 11. Verification results — 2026-07-31

| # | Check | Result |
|---|---|---|
| 1 | `http://<domain>` redirects to `https://` | ✅ 301 → `https://<domain>/dashboard` |
| 2 | `https://<domain>` loads the frontend | ✅ 200 |
| 3 | Deep-link refresh (`/dashboard`) over HTTPS | ✅ 200 via `try_files` |
| 4 | API over HTTPS | ✅ `/api/health/` → `{"status":"ok","database":"ok"}` |
| 5 | Browser-valid certificate | ✅ `CN=51-20-144-52.sslip.io`, issuer Let's Encrypt, `Verify return code: 0 (ok)`, expires 2026-10-29 |
| 6 | Login endpoint over HTTPS | ✅ proper DRF validation error on bad credentials — no CSRF/CORS/gateway failure |
| 7 | Protected routes unauthenticated | ✅ 401 on `/properties/`, `/occupants/`, `/dashboard/`, `/payments/` |
| 8 | Mixed content | ✅ none possible — `VITE_API_BASE_URL=/api` is same-origin |
| 9 | CORS / CSRF errors | ✅ none |
| 10 | HSTS header | ✅ `max-age=300; includeSubDomains; preload` |
| 11 | Container health | ✅ all three `Up (healthy)` — both healthcheck traps avoided |
| 12 | `manage.py check --deploy` | ✅ **0 issues** (previously 4 TLS warnings) |
| 13 | Renewal | ✅ `certbot renew --dry-run` succeeded; `certbot-renew.timer` enabled and active |
| 14 | Ports 8000 / 5432 / 5173 from the internet | ✅ all closed |
| 15 | Ports 80 / 443 from the internet | ✅ both open, as intended |

### Authenticated business workflow over HTTPS — 12/12

Run as real authenticated HTTPS calls with a temporary superuser, which was deleted afterwards along with all
data it created (the same pattern as the 2026-07-29 verification).

| # | Check | Result |
|---|---|---|
| 1 | Login over HTTPS | ✅ 40-char DRF token returned |
| 2 | Dashboard | ✅ 200 |
| 3 | Create property | ✅ created |
| 4 | Create section | ✅ created |
| 5 | Create unit | ✅ created (capacity 2, prices set) |
| 6 | Register occupant | ✅ created |
| 7 | Assign occupancy | ✅ linked occupant → unit |
| 8 | Record payment | ✅ 1000.00, receipt `RCP-2026-00003` auto-generated |
| 9 | Receipt PDF | ✅ 200, `application/pdf`, **valid 1-page PDF v1.4** (2499 bytes) |
| 10 | Property Explorer hierarchy | ✅ `/properties/` and `/units/` both 200 |
| 11 | Logout | ✅ 200 |
| 12 | Token invalidated after logout | ✅ 401 on reuse |

Cleanup confirmed: verification property, section, unit, occupant, occupancy, payment, receipt, and the temporary
superuser all deleted. Only `karosadmin` remains.

> **Note:** the staging database still holds properties `KG1`/`SMK1`, 5 students, and 2 payments left over from the
> 2026-07-29 smoke test. Unrelated to this sprint and left untouched, but worth clearing before any demo.

---

## 12. Remaining risks

| Risk | Severity | Mitigation |
|---|---|---|
| Hostname changes on every stop/start; certificate stops matching | **High** (operational) | Runbook §9. Resolved permanently by an Elastic IP or a purchased domain. |
| Let's Encrypt rate limit against shared `sslip.io` | Medium | Dry-run before every issuance; avoid needless instance cycling. |
| No automated backups — `pg_dump` is still manual | **High** (data) | Next sprint. HTTPS makes the app usable with real data, which makes this the top remaining gap. |
| Single point of failure — one instance, one container DB | Medium | Accepted for staging. |
| HSTS pinned on a recyclable hostname | Low | `max-age=300`. |
| Certificate renewal depends on port 80 staying open | Low | Documented in §4; `certbot renew --dry-run` verifies it. |
| Server working tree may drift from git | Low | Keep the deployment assets committed and pull on the server. |
