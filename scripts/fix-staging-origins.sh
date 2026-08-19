#!/usr/bin/env bash
#
# KarosL — repair the server .env after the public IP changed.
#
# The staging instance has no Elastic IP, so its public address changes on
# EVERY stop/start. The sslip.io hostname is derived from that address, so an
# IP change silently breaks three things at once:
#
#   1. ALLOWED_HOSTS no longer matches  -> every API call returns 400
#   2. CSRF/CORS origins no longer match
#   3. the TLS certificate is for the OLD hostname
#
# It fails quietly from outside: nginx keeps serving the SPA regardless of
# Django, so the home page looks fine while the whole API is down. That is
# exactly how the 2026-07-31 outage went unnoticed.
#
# This script automates steps 1 and 2 of the docs/DOMAIN_HTTPS_PLAN.md §9
# runbook. It deliberately does NOT run certbot (step 3) or restart the
# stack (step 4): Let's Encrypt rate-limits certificates against the SHARED
# sslip.io domain, so issuance stays a deliberate, human-triggered act. The
# exact commands are printed for you to run.
#
# What it does:
#   1. reads the instance's current public IP from IMDSv2 (no AWS creds needed)
#   2. derives the sslip.io hostname (IP with dots replaced by dashes)
#   3. backs up .env, then rewrites ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS,
#      CORS_ALLOWED_ORIGINS, STAGING_DOMAIN and PUBLIC_IP — CSRF/CORS carry
#      BOTH the sslip.io hostname's origin and the bare-IP origin, since
#      docs/HTTPS_IP_CERTIFICATE.md's bare-IP HTTPS path needs its own origin
#      trusted too, not just the hostname's
#   4. prints the certbot + compose commands to finish the job (both the
#      hostname cert and the IP cert)
#
# What it deliberately does NOT do:
#   - run certbot, or issue/renew any certificate
#   - restart or rebuild any container
#   - touch the security group (if YOUR workstation IP also changed, update
#     the SSH rule by hand — see docs/DOMAIN_HTTPS_PLAN.md §9)
#   - print any secret from .env
#
# Usage (from the repo root on the staging server):
#   ./scripts/fix-staging-origins.sh
#   ./scripts/fix-staging-origins.sh --dry-run   # show the changes, write nothing
#
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

[ -f .env ] || die ".env not found in $REPO_ROOT — run this on the staging server, from the repo root."

# --- Find the current public IP ---------------------------------------------
# IMDSv2 (token-required) is enforced on this instance, so the token call is
# mandatory, not optional. This needs no AWS credentials and no network egress.
log "Reading the instance's current public IP from instance metadata..."
TOKEN=$(curl -sS --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 120" 2>/dev/null) \
    || die "Could not reach the instance metadata service. Are you running this on the EC2 instance?"

NEW_IP=$(curl -sS --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" \
    "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null) || true

[[ "$NEW_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] \
    || die "Did not get a valid public IPv4 from metadata (got: '${NEW_IP:-<empty>}').
If the instance genuinely has no public IP, it cannot serve traffic at all."

NEW_DOMAIN="${NEW_IP//./-}.sslip.io"

# --- Compare against what .env currently says -------------------------------
CURRENT_DOMAIN=$(grep -E '^STAGING_DOMAIN=' .env | head -1 | cut -d= -f2- || true)
CURRENT_PUBLIC_IP=$(grep -E '^PUBLIC_IP=' .env | head -1 | cut -d= -f2- || true)

printf '\n    current IP:      %s\n' "$NEW_IP"
printf '    new hostname:    %s\n' "$NEW_DOMAIN"
printf '    .env currently:  %s / PUBLIC_IP=%s\n' "${CURRENT_DOMAIN:-<STAGING_DOMAIN not set>}" "${CURRENT_PUBLIC_IP:-<not set>}"

if [ "$CURRENT_DOMAIN" = "$NEW_DOMAIN" ] && [ "$CURRENT_PUBLIC_IP" = "$NEW_IP" ]; then
    log "Already correct — .env matches the current IP. Nothing to do."
    printf '\nIf the API is still failing, the problem is elsewhere. Check:\n'
    printf '  docker compose ps\n'
    printf '  curl -sS https://%s/api/health/\n' "$NEW_DOMAIN"
    exit 0
fi

# --- Rewrite the origins ----------------------------------------------------
# ALLOWED_HOSTS must keep localhost/127.0.0.1/backend: the backend container's
# HEALTHCHECK curls localhost:8000, and Django 400s an unlisted Host — which
# marks a perfectly healthy container as unhealthy forever.
NEW_ALLOWED="${NEW_DOMAIN},${NEW_IP},localhost,127.0.0.1,backend"
# Both origins trusted: the hostname path (docs/DOMAIN_HTTPS_PLAN.md) and the
# bare-IP path (docs/HTTPS_IP_CERTIFICATE.md) are served side by side.
NEW_CSRF_CORS="https://${NEW_DOMAIN},https://${NEW_IP}"

if [ "$DRY_RUN" = true ]; then
    log "--dry-run: these lines WOULD be written to .env"
    printf '    ALLOWED_HOSTS=%s\n'        "$NEW_ALLOWED"
    printf '    CSRF_TRUSTED_ORIGINS=%s\n' "$NEW_CSRF_CORS"
    printf '    CORS_ALLOWED_ORIGINS=%s\n' "$NEW_CSRF_CORS"
    printf '    STAGING_DOMAIN=%s\n'       "$NEW_DOMAIN"
    printf '    PUBLIC_IP=%s\n'            "$NEW_IP"
    exit 0
fi

BACKUP=".env.bak-$(date +%Y%m%d-%H%M%S)"
cp .env "$BACKUP"
chmod 600 "$BACKUP"
log "Backed up .env to $BACKUP"

# Replace in place if the key exists, append if it does not. Values are written
# with a literal-safe delimiter because hostnames contain dots and slashes.
set_env_var() {
    local key="$1" value="$2"
    if grep -qE "^${key}=" .env; then
        python3 - "$key" "$value" <<'PY'
import sys, pathlib
key, value = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env")
lines = p.read_text().splitlines(keepends=True)
out = []
for line in lines:
    if line.startswith(f"{key}="):
        nl = "\n" if line.endswith("\n") else ""
        out.append(f"{key}={value}{nl}")
    else:
        out.append(line)
p.write_text("".join(out))
PY
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

set_env_var ALLOWED_HOSTS        "$NEW_ALLOWED"
set_env_var CSRF_TRUSTED_ORIGINS "$NEW_CSRF_CORS"
set_env_var CORS_ALLOWED_ORIGINS "$NEW_CSRF_CORS"
set_env_var STAGING_DOMAIN       "$NEW_DOMAIN"
set_env_var PUBLIC_IP            "$NEW_IP"
chmod 600 .env

log "Updated .env:"
grep -E '^(ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|CORS_ALLOWED_ORIGINS|STAGING_DOMAIN|PUBLIC_IP)=' .env | sed 's/^/    /'

# --- Tell the operator what is left -----------------------------------------
CERT_EMAIL=$(grep -E '^CERTBOT_EMAIL=' .env | head -1 | cut -d= -f2- || true)

cat <<EOF

$(printf '\033[1;34m==>\033[0m') Not done automatically — run these yourself (docs/DOMAIN_HTTPS_PLAN.md §9,
  docs/HTTPS_IP_CERTIFICATE.md for the IP cert):

  Both the hostname and the IP changed, so BOTH certificates need reissuing —
  the old ones no longer match. Let's Encrypt counts hostname certs against
  the shared sslip.io domain (50/week for everyone using the service) and IP
  certs against the IP itself (50/week, not shared) — issuance stays a
  deliberate step either way. Dry-run first.

  # 1. Serve the ACME challenge (no certificate exists for the new name/IP yet)
  docker compose -f docker-compose.yml -f docker-compose.acme.yml up -d frontend

  # 2. Hostname cert — check it would work, THEN issue for real
  sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/certbot -d ${NEW_DOMAIN} --dry-run
  sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/certbot -d ${NEW_DOMAIN} \\
      --agree-tos -m ${CERT_EMAIL:-<YOUR_EMAIL>} --non-interactive

  # 3. IP cert — same pattern, mandatory shortlived profile (~160h lifetime)
  sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/certbot --ip-address ${NEW_IP} \\
      --preferred-profile shortlived --staging --agree-tos --register-unsafely-without-email --non-interactive
  sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/certbot --ip-address ${NEW_IP} \\
      --preferred-profile shortlived --agree-tos --register-unsafely-without-email --non-interactive

  # 4. Back to HTTPS (renders both server blocks — see deploy/nginx/staging-https.conf.template)
  docker compose -f docker-compose.yml -f docker-compose.https.yml up -d

  # 5. Verify — check the API, not just the home page, on BOTH origins
  curl -sS https://${NEW_DOMAIN}/api/health/
  curl -sS https://${NEW_IP}/api/health/

  Also update the security group's SSH rule if YOUR workstation IP changed.

  Old-IP certificate lineages (both the hostname's and the previous IP's) are
  orphaned by this — recover-staging.sh sweeps them after the container
  recreate; safe to leave alone in the meantime, they just stop renewing.

  To roll back: cp ${BACKUP} .env && docker compose up -d backend
EOF
