#!/usr/bin/env bash
#
# KarosL — check whether staging is genuinely working, from outside.
#
# "From outside" is the whole point. After a restart the containers come back
# up with the OLD hostname baked into their stored environment, so on the box
# everything looks perfect: all three containers report healthy (their
# healthchecks hit localhost, which never changes) and nginx serves the SPA
# happily. Meanwhile nginx is presenting a certificate for a hostname that no
# longer resolves here, and Django returns 400 to every API call.
#
# `docker compose ps` cannot see that failure. This script can, because it
# checks the real hostname over the real network, the way a user would.
#
# Encodes the verification list from docs/DOMAIN_HTTPS_PLAN.md §11 so it stops
# being something a human re-types from memory.
#
# Exit status is the point: 0 = staging is up, non-zero = it is not. Safe to
# run any time; it only reads.
#
# Usage:
#   ./scripts/verify-staging.sh                      # resolve the domain from AWS
#   ./scripts/verify-staging.sh <domain-or-ip>       # check a specific host
#
set -uo pipefail   # deliberately NOT -e: every check must run, so one failure
                   # does not hide the others behind it.

INSTANCE_ID="${KAROSL_INSTANCE_ID:-i-0afd1871b46296500}"
REGION="${AWS_DEFAULT_REGION:-eu-north-1}"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 2; }

PASS=0
FAIL=0
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[1;31m✗\033[0m %s\n' "$1"; FAIL=$((FAIL + 1)); }

for arg in "$@"; do
    case "$arg" in
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        -*) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

TARGET="${1:-}"

# --- Work out what to check ------------------------------------------------
if [ -z "$TARGET" ]; then
    command -v aws >/dev/null 2>&1 || die "No host given and the AWS CLI is not installed.
Pass the domain explicitly: ./scripts/verify-staging.sh <domain>"

    STATE=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[].Instances[].State.Name' --output text 2>/dev/null)
    IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[].Instances[].PublicIpAddress' --output text 2>/dev/null)

    if [ "$STATE" != "running" ]; then
        printf '\n\033[1;31mStaging is not running\033[0m (instance state: %s).\n' "${STATE:-unknown}"
        printf 'Bring it back with:  ./scripts/recover-staging.sh\n\n'
        exit 1
    fi
    [ -n "$IP" ] && [ "$IP" != "None" ] || die "Instance is running but has no public IP."
    TARGET="${IP//./-}.sslip.io"
fi

log "Checking https://${TARGET}"

# --- HTTP -> HTTPS ----------------------------------------------------------
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "http://${TARGET}/" 2>/dev/null)
[ "$code" = "301" ] && ok "HTTP redirects to HTTPS (301)" || bad "HTTP did not redirect (got ${code:-no response})"

# --- Certificate ------------------------------------------------------------
# Checked without -k on purpose: a certificate that only validates when
# verification is disabled is exactly the failure this script exists to catch.
cert=$(echo | timeout 15 openssl s_client -connect "${TARGET}:443" -servername "$TARGET" 2>/dev/null)
if [ -n "$cert" ]; then
    subject=$(echo "$cert" | openssl x509 -noout -subject 2>/dev/null)
    verify=$(echo "$cert" | grep -m1 "Verify return code")
    enddate=$(echo "$cert" | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

    echo "$subject" | grep -q "$TARGET" \
        && ok "Certificate is for ${TARGET}" \
        || bad "Certificate hostname mismatch (${subject:-none}) — the classic post-restart symptom"

    echo "$verify" | grep -q "code: 0" \
        && ok "Certificate chain verifies (${verify#*: })" \
        || bad "Certificate does not verify (${verify:-unknown})"

    if [ -n "$enddate" ]; then
        days=$(( ( $(date -d "$enddate" +%s) - $(date +%s) ) / 86400 ))
        if [ "$days" -lt 0 ];      then bad "Certificate EXPIRED ${days#-} days ago"
        elif [ "$days" -lt 14 ];   then bad "Certificate expires in ${days} days — renewal is failing"
        else                            ok "Certificate valid for ${days} more days"
        fi
    fi
else
    bad "No TLS handshake on port 443"
fi

# --- The API ----------------------------------------------------------------
# This is the check that matters most. The SPA is static files and will serve
# happily while the entire API is returning 400, so a green home page proves
# nothing at all.
health=$(curl -sS --max-time 15 "https://${TARGET}/api/health/" 2>/dev/null)
if echo "$health" | grep -q '"status":"ok"' && echo "$health" | grep -q '"database":"ok"'; then
    ok "API healthy end to end (nginx → gunicorn → postgres)"
else
    bad "API unhealthy: ${health:-no response}"
    echo "$health" | grep -qi "bad request\|DisallowedHost" \
        && warn "That looks like stale ALLOWED_HOSTS — run ./scripts/recover-staging.sh"
fi

# --- SPA --------------------------------------------------------------------
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${TARGET}/" 2>/dev/null)
[ "$code" = "200" ] && ok "SPA loads (200)" || bad "SPA returned ${code:-no response}"

code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${TARGET}/dashboard" 2>/dev/null)
[ "$code" = "200" ] && ok "Deep link refresh works (try_files)" || bad "Deep link returned ${code:-no response}"

# --- Auth boundary ----------------------------------------------------------
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${TARGET}/api/reports/occupancy/" 2>/dev/null)
[ "$code" = "401" ] && ok "Protected routes reject anonymous access (401)" || bad "Protected route returned ${code:-no response}, expected 401"

# --- HSTS -------------------------------------------------------------------
# Emitted by Django, so it appears on API responses rather than on nginx-served
# static files. Checking "/" here would produce a false failure.
curl -sSI --max-time 15 "https://${TARGET}/api/health/" 2>/dev/null | grep -qi "strict-transport-security" \
    && ok "HSTS header present" || bad "HSTS header missing"

# --- Ports that must stay shut ---------------------------------------------
host_only="${TARGET%%.sslip.io}"
host_only="${host_only//-/.}"
for port in 8000 5432 5173; do
    if timeout 5 bash -c "</dev/tcp/${host_only}/${port}" 2>/dev/null; then
        bad "Port ${port} is OPEN to the internet — it must not be"
    else
        ok "Port ${port} closed"
    fi
done

# --- Verdict ----------------------------------------------------------------
printf '\n'
if [ "$FAIL" -eq 0 ]; then
    printf '\033[1;32mStaging is up.\033[0m  %d/%d checks passed.\n' "$PASS" "$((PASS + FAIL))"
    printf '  https://%s\n\n' "$TARGET"
    exit 0
fi

printf '\033[1;31mStaging is NOT healthy.\033[0m  %d passed, %d failed.\n' "$PASS" "$FAIL"
printf '  Most failures after a restart are the stale-hostname problem.\n'
printf '  Fix with:  ./scripts/recover-staging.sh\n\n'
exit 1
