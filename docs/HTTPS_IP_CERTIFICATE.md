# HTTPS via bare EC2 IP (Let's Encrypt IP-address certificate)

Status: **live since 2026-08-19.** `https://<EC2_PUBLIC_IP>` now shows a real, browser-trusted certificate,
alongside — not instead of — the existing sslip.io hostname path from `docs/DOMAIN_HTTPS_PLAN.md`. This doc
is the reference for that second path specifically.

## Why this exists, and why it's additive

The task was to make the app reachable with a trusted padlock by typing the bare EC2 IP into a browser —
something the existing sslip.io setup does not do (a browser hitting `https://<IP>` directly against the
old config got a certificate-hostname mismatch, since the cert was only ever issued for the derived
`<ip-with-dashes>.sslip.io` name). Let's Encrypt historically never issued certificates for bare IP
addresses at all; that changed on **2026-01-15** when IP-address certificates went GA, with Certbot support
landing in **5.3/5.4** (Feb–Mar 2026). Confirmed directly against this exact box, not assumed from
documentation: the box's own `pip install certbot` resolved to Certbot 4.2.0, not 5.x, because the venv used
the system Python (3.9.25) and Certbot ≥5.0 requires Python ≥3.10. Installing `python3.12` (an official,
already-available AL2023 package) and rebuilding the venv against it correctly resolved 5.7.0 — always
verify a capability empirically against the exact box, distro package repos silently omit or gate
newer releases in ways generic documentation can't predict.

**The existing sslip.io-hostname path was kept, unmodified, running alongside the new one — not replaced.**
Two independent TLS server blocks share port 443 in the same nginx config, on two independent certificates.
If the new IP-cert automation ever breaks, only the new access path degrades; the pilot's actual working
access path is unaffected. This also means: no change to the existing Docker Compose architecture beyond
one more env var and one more `server{}` block — same 3 services, same volumes, same host-level (not
container-level) certbot, matching the existing convention that nginx has never been certbot-managed here.

## 1. Certificate

| | |
|---|---|
| Type | Let's Encrypt IP-address certificate — SAN `IP Address:<EC2_PUBLIC_IP>`, no CN (empty subject) |
| CA / trust | Same Let's Encrypt root chain (ISRG Root X1/X2) as any normal cert — no special browser trust needed, confirmed by a clean `Verify return code: 0` |
| Lifetime | **160 hours (~6.67 days)** — a mandatory property of the `shortlived` ACME profile, which IP certs require |
| Rate limit | 50 certificates per IPv4 address per 7 days — not a practical constraint at this cadence |
| Storage | `/etc/letsencrypt/live/<dotted-IP>/` on the host, e.g. `/etc/letsencrypt/live/51.20.141.56/` — **dotted**, unlike the hostname lineage's **dashed** `sslip.io` naming (`51-20-141-56.sslip.io`). Two different, unrelated naming schemes; don't conflate them when scripting against either. |
| Nginx integration | Second `server { listen 443 ssl default_server; ... }` block in `deploy/nginx/staging-https.conf.template`, `ssl_certificate`/`ssl_certificate_key` pointed at the IP lineage |

## 2. Why `default_server`, not just SNI

TLS Server Name Indication (SNI) is not reliable for bare-IP connections — RFC 6066 forbids IP literals as
the SNI `HostName` value, and while some clients send the IP anyway, it can't be depended on. So the IP
block is marked `default_server` (wins when SNI is absent or doesn't match any block) **and** still declares
`server_name ${PUBLIC_IP}` (wins if a client does send the IP as SNI). The hostname block keeps
`server_name ${STAGING_DOMAIN}` as before. Verified directly: a TLS handshake with `-servername
<hostname>` gets the hostname cert; one with no SNI at all gets the IP cert.

## 3. Certbot: an isolated venv, not the OS package

Amazon Linux 2023's `dnf`-packaged certbot is **2.6.0** — no `--ip-address` flag, no `--preferred-profile`.
Installed a modern one (5.7.0) into `/opt/certbot-venv` (built against `python3.12`, an official AL2023
package installed alongside — not replacing — the system `python3`), and cut the renewal timer over to it
via a **systemd drop-in override** rather than touching `/usr/bin/certbot` directly:

```bash
sudo dnf install -y python3.12
sudo python3.12 -m venv /opt/certbot-venv
sudo /opt/certbot-venv/bin/pip install --upgrade pip certbot   # -> 5.7.0

sudo systemctl edit certbot-renew.service   # writes the drop-in below
```
```ini
# /etc/systemd/system/certbot-renew.service.d/override.conf
[Service]
ExecStart=
ExecStart=/opt/certbot-venv/bin/certbot renew --noninteractive --no-random-sleep-on-renew $PRE_HOOK $POST_HOOK $RENEW_HOOK $DEPLOY_HOOK $CERTBOT_ARGS
```

Why not `dnf remove certbot` and install fresh: the dnf package **owns** `/usr/lib/systemd/system/certbot-renew.timer`/`.service` — removing it would delete the already-working unit files. Why not overwrite
`/usr/bin/certbot`: a future `dnf update` could silently revert it. The drop-in changes only the one line
that matters and survives both.

**Verified, not assumed:** `certificates` on the new venv binary correctly listed the pre-existing hostname
lineage (proves it reads the same `/etc/letsencrypt` state regardless of install method); a manual
`systemctl start certbot-renew.service` trigger correctly processed both lineages and reported "not yet due
for renewal" for the fresh 160h IP cert — not the legacy "always renew inside 30 days" heuristic, which
would be nonsensical for a 6.67-day cert.

## 4. Issuance

```bash
sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/certbot \
    --ip-address <EC2_PUBLIC_IP> --preferred-profile shortlived \
    --agree-tos --register-unsafely-without-email --non-interactive
```

Same `webroot` plugin, same `/var/www/certbot` path, same ACME-challenge nginx stage
(`docker-compose.acme.yml`) as the hostname cert — the `nginx`/`apache` certbot plugins don't support IP
validation yet, but that was never used here anyway (nginx has never been certbot-managed in this repo).
Tested against Let's Encrypt's `--staging` endpoint first (untrusted test cert, no rate-limit cost) before
the real issuance, same discipline as the hostname cert's runbook in `docs/DOMAIN_HTTPS_PLAN.md`.

## 5. Renewal — proven, not just configured

The deploy-hook that reloads nginx after a renewal **already existed** from 2026-07-31
(`/etc/letsencrypt/renewal-hooks/deploy/reload-karosl-nginx.sh`, `docker kill -s HUP karosl-frontend-1`) —
found during this work, not created by it; it fires for every lineage automatically, no extra wiring
needed for the new cert.

**Forced-renewal test, done deliberately rather than waiting for natural expiry (2026-08-19):**
```bash
sudo /opt/certbot-venv/bin/certbot renew --cert-name <EC2_PUBLIC_IP> --force-renewal
```
Result: renewal succeeded, the deploy-hook fired and reloaded nginx automatically, and
`./scripts/verify-staging.sh <EC2_PUBLIC_IP>` was green (12/12) immediately after — with zero manual
intervention and zero downtime. New cert's `notBefore` confirmed the reissue actually happened, not a no-op.

The existing twice-daily `certbot-renew.timer` (`OnCalendar=*-*-* 00/12:00:00`) covers this cert too — no
new timer needed. At 160h lifetime with 12h check intervals, there are ~13 renewal opportunities per cert
lifetime even before accounting for Let's Encrypt's ACME Renewal Info (ARI)-based early-renewal window.

## 6. Django configuration — env-only, no code changes

`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` already parsed comma-separated lists
(`backend/config/settings.py`, `.split(',')`) before this work — confirmed by reading the code, not assumed.
Adding the bare-IP origin was purely a server `.env` change:
```
ALLOWED_HOSTS=<STAGING_DOMAIN>,<PUBLIC_IP>,localhost,127.0.0.1,backend
CSRF_TRUSTED_ORIGINS=https://<STAGING_DOMAIN>,https://<PUBLIC_IP>
CORS_ALLOWED_ORIGINS=https://<STAGING_DOMAIN>,https://<PUBLIC_IP>
PUBLIC_IP=<EC2_PUBLIC_IP>
```
`scripts/fix-staging-origins.sh` writes all of this automatically now (it already wrote the bare IP into
`ALLOWED_HOSTS` before this work — someone had already anticipated part of this; only `CSRF_TRUSTED_ORIGINS`/
`CORS_ALLOWED_ORIGINS`/`PUBLIC_IP` needed adding).

`DEBUG=False` and `SECURE_SSL_REDIRECT`/`CSRF_COOKIE_SECURE`/`SESSION_COOKIE_SECURE=True` were already set
for staging (`docker-compose.https.yml`) — unaffected by this work, apply identically to both origins since
they're Django-level settings, not per-origin.

## 7. Frontend — no rebuild needed

`VITE_API_BASE_URL` defaults to the relative path `/api` (`frontend/src/services/api.js`), baked in at
build time but origin-agnostic — confirmed by reading the code. The SPA calls back into whatever origin
served it, so it already worked against the bare IP with zero changes, zero rebuild.

## 8. Docker Compose / nginx changes

`docker-compose.https.yml`: added `PUBLIC_IP: ${PUBLIC_IP:?set PUBLIC_IP in .env}`, changed
`NGINX_ENVSUBST_FILTER: STAGING_DOMAIN` to `STAGING_DOMAIN|PUBLIC_IP` (the nginx image's entrypoint feeds
this straight into an awk extended-regex match against env-var *names* — alternation is correct syntax,
confirmed by reading the actual entrypoint script inside `nginx:1.27-alpine`).

`deploy/nginx/staging-https.conf.template`: the existing 443 block gained an explicit
`server_name ${STAGING_DOMAIN};` (was the catch-all `_`); a new, directive-for-directive identical block
was added for the IP path (only `server_name`, `default_server`, and the two `ssl_certificate*` lines
differ) — kept intentionally identical so the two access paths can't silently drift apart. Port 80 needed
**zero changes**: its ACME-challenge and redirect logic was already host-agnostic and already correctly
redirects `http://<IP>/...` → `https://<IP>/...`.

## 9. Security-group requirements — unchanged

No security-group change was needed. Confirmed via AWS CLI, unchanged from `docs/AWS_STAGING_CHECKLIST.md`:
SSH 22 from the admin `/32` only, HTTP 80 and HTTPS 443 from `0.0.0.0/0`, and 5432/8000/5173 never in the
inbound rules — `scripts/verify-staging.sh` checks the port-closed state externally against both the
hostname and the bare IP on every run.

## 10. Verification (2026-08-19)

- `https://<PUBLIC_IP>` loads with a trusted padlock, CN/SAN = the IP, no interstitial warning.
- `scripts/verify-staging.sh` green (12/12) against **both** the hostname and the bare IP, including a
  short-lived-cert-aware expiry threshold (`<1 day → bad` for the IP cert vs. `<14 days → bad` for the
  90-day hostname cert — a healthy IP cert is *never* going to show 14+ days remaining, so reusing the
  hostname threshold unchanged would have been a permanent false failure).
- Full browser smoke test against the bare-IP origin specifically, with a **fresh login** (cookies are
  origin-scoped — the hostname session does not carry over): login, dashboard, property → section → unit,
  occupant registration, occupancy assignment, payment recording, receipt PDF generation, Property Explorer.
  Zero console errors — no mixed content, no CORS, no CSRF. `AUDIT-TEST`-prefixed records archived
  afterward; dashboard returned to the exact pre-test baseline.
- Forced-renewal test (§5) succeeded with zero downtime and zero manual steps.
- Postgres/5432, Gunicorn/8000, Vite/5173 confirmed still closed to the internet on both targets.

## 11. Rollback

Fully additive → rollback never touches volumes, the database, or containers beyond a recreate:
```bash
git checkout -- deploy/nginx/staging-https.conf.template docker-compose.https.yml
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```
The hostname path is unaffected throughout — it's a separate `server{}` block on a separate certificate.
To also roll back the certbot/renewal changes: `sudo systemctl revert certbot-renew.service` and remove
`/opt/certbot-venv`. The IP-cert lineage is safe to leave in place inert (it just stops renewing and expires
within ≤160h with nothing referencing it) rather than needing explicit deletion.

## 12. Troubleshooting

- **Browser shows the hostname's cert when hitting the bare IP, not the IP cert** — check that the IP block
  in `staging-https.conf.template` actually has `default_server`; only one block per `listen` may carry it.
- **`certonly --ip-address` fails with "will not issue certificates for a bare IP address"** — the client is
  too old. Check `certbot --version` is ≥5.3 and that it's actually the venv binary being invoked
  (`/opt/certbot-venv/bin/certbot`), not the dnf-packaged `/usr/bin/certbot` (2.6.0).
- **Renewal timer shows the wrong certbot version in its logs** — check the systemd drop-in is actually
  loaded: `systemctl cat certbot-renew.service` should show the override's `ExecStart=` last.
- **Orphaned IP-cert lineages after a future IP change** — `scripts/recover-staging.sh` sweeps these
  automatically after recreating containers, matching how it already handles hostname orphans (see that
  script's own comments for the ordering rationale).
- **`verify-staging.sh` reports the IP cert as failing on expiry when it looks fine** — confirm you're
  running the version with the IP-aware threshold (`<1 day`, not `<14 days`); an old copy of the script
  would misfire here.

## 13. Related docs

`docs/DOMAIN_HTTPS_PLAN.md` (the hostname path this sits alongside), `docs/DEVOPS.md` §12 (backup, separate
concern), `docs/AWS_STAGING_CHECKLIST.md` (security-group baseline), `docs/PROJECT_STATE.md` (dated status).
