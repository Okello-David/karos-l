#!/usr/bin/env bash
#
# KarosL — bring staging from "stopped" back to "verified working", in one command.
#
# Run this from your WORKSTATION (it needs the AWS CLI and the SSH key), not
# from the instance.
#
# WHY THIS EXISTS
# ---------------
# The staging instance has no Elastic IP, so its public address changes on every
# stop/start. The staging hostname is derived from that address, so an IP change
# breaks three things at once:
#
#   1. .env origins go stale        -> Django 400s every API call
#   2. the certificate stops matching the new hostname
#   3. the previous certificate is orphaned and can never renew again
#
# Worse, it fails *quietly*. The containers restart automatically with the old
# hostname still baked into their stored environment, their healthchecks hit
# localhost and keep passing, and nginx serves the SPA as normal. From the box
# everything looks healthy while the entire API is down.
#
# This has happened three times. The real fix is an Elastic IP or a purchased
# domain; until then, this script makes the recovery routine rather than a
# rediscovery.
#
# WHAT IT DOES
#   1. starts the instance, retrying AWS capacity errors
#   2. waits for it and reads the new public IP
#   3. checks the SSH rule still matches your workstation IP
#   4. repairs the .env origins on the instance
#   5. issues a certificate for the new hostname, if one does not exist
#   6. recreates the containers so the new hostname is baked in
#   7. deletes orphaned certificates -- only after step 6, never before
#   8. verifies the whole thing from outside
#
# WHAT IT DOES NOT DO
#   - allocate an Elastic IP or buy a domain (the actual cures; both deferred)
#   - widen the security group, unless you pass --fix-ssh
#   - touch the database, backups, or any application data
#
# Usage:
#   ./scripts/recover-staging.sh              # full recovery
#   ./scripts/recover-staging.sh --fix-ssh    # also update the SSH rule to your current IP
#   ./scripts/recover-staging.sh --no-start   # assume it is already running
#   ./scripts/recover-staging.sh --dry-run    # show what would happen, change nothing
#
set -euo pipefail

INSTANCE_ID="${KAROSL_INSTANCE_ID:-i-0afd1871b46296500}"
SECURITY_GROUP="${KAROSL_SECURITY_GROUP:-sg-065fb018e22aa18a5}"
REGION="${AWS_DEFAULT_REGION:-eu-north-1}"
SSH_KEY="${KAROSL_SSH_KEY:-$HOME/.ssh/karosl-staging-key.pem}"
REMOTE_DIR="${KAROSL_REMOTE_DIR:-~/apps/karosl}"
SSH_USER="${KAROSL_SSH_USER:-ec2-user}"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
FIX_SSH=false
DO_START=true
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=true ;;
        --fix-ssh)  FIX_SSH=true ;;
        --no-start) DO_START=false ;;
        -h|--help)  sed -n '2,45p' "$0"; exit 0 ;;
        *) die "Unknown argument '$arg'. Try --help." ;;
    esac
done

command -v aws >/dev/null 2>&1 || die "The AWS CLI is required and was not found."
[ -f "$SSH_KEY" ] || die "SSH key not found at $SSH_KEY (override with KAROSL_SSH_KEY)."

remote() { ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -i "$SSH_KEY" "${SSH_USER}@${IP}" "$@"; }

# --- 1. Start ---------------------------------------------------------------
STATE=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[].Instances[].State.Name' --output text)
log "Instance is currently: $STATE"

if [ "$STATE" != "running" ] && [ "$DO_START" = true ]; then
    if [ "$DRY_RUN" = true ]; then
        warn "--dry-run: would start the instance here."
    else
        # InsufficientInstanceCapacity is a real, transient AWS-side condition:
        # it took 11 attempts on 2026-08-01. Retry rather than failing.
        log "Starting the instance (retrying capacity errors)..."
        started=false
        for attempt in $(seq 1 30); do
            if out=$(aws ec2 start-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
                     --query 'StartingInstances[].CurrentState.Name' --output text 2>&1); then
                printf '    started on attempt %s\n' "$attempt"
                started=true
                break
            fi
            case "$out" in
                *InsufficientInstanceCapacity*)
                    printf '    attempt %s: no capacity in this AZ, retrying...\n' "$attempt"
                    sleep 25 ;;
                *) die "start-instances failed: $out" ;;
            esac
        done
        [ "$started" = true ] || die "Could not start the instance after 30 attempts.
AWS has no t3.micro capacity in this availability zone right now. Try again later."

        log "Waiting for the instance to reach 'running'..."
        aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
    fi
fi

# --- 2. New address ---------------------------------------------------------
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[].Instances[].PublicIpAddress' --output text)
[ -n "$IP" ] && [ "$IP" != "None" ] || die "Instance has no public IP yet. Wait a moment and re-run."
DOMAIN="${IP//./-}.sslip.io"

log "Public IP:  $IP"
printf '    hostname: %s\n' "$DOMAIN"

# --- 3. SSH reachability ----------------------------------------------------
MY_IP=$(curl -sS --max-time 10 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]')
SSH_CIDR=$(aws ec2 describe-security-group-rules --region "$REGION" \
    --filters Name=group-id,Values="$SECURITY_GROUP" \
    --query 'SecurityGroupRules[?!IsEgress && FromPort==`22`].CidrIpv4' --output text 2>/dev/null)

if [ -n "$MY_IP" ] && [ "$SSH_CIDR" != "${MY_IP}/32" ]; then
    warn "The SSH rule allows ${SSH_CIDR}, but your workstation is ${MY_IP}."
    if [ "$FIX_SSH" = true ] && [ "$DRY_RUN" = false ]; then
        log "Updating the SSH rule (--fix-ssh)..."
        RULE_ID=$(aws ec2 describe-security-group-rules --region "$REGION" \
            --filters Name=group-id,Values="$SECURITY_GROUP" \
            --query 'SecurityGroupRules[?!IsEgress && FromPort==`22`].SecurityGroupRuleId' --output text)
        aws ec2 modify-security-group-rules --region "$REGION" --group-id "$SECURITY_GROUP" \
            --security-group-rules "SecurityGroupRuleId=${RULE_ID},SecurityGroupRule={IpProtocol=tcp,FromPort=22,ToPort=22,CidrIpv4=${MY_IP}/32,Description=admin workstation}"
        printf '    SSH now allowed from %s/32\n' "$MY_IP"
    else
        # Not fixed automatically: widening a firewall should be a deliberate act,
        # not a side effect of a routine recovery run.
        die "SSH will fail. Re-run with --fix-ssh, or update the rule yourself:
  aws ec2 modify-security-group-rules --region $REGION --group-id $SECURITY_GROUP \\
    --security-group-rules 'SecurityGroupRuleId=<id>,SecurityGroupRule={IpProtocol=tcp,FromPort=22,ToPort=22,CidrIpv4=${MY_IP}/32}'"
    fi
fi

if [ "$DRY_RUN" = true ]; then
    log "--dry-run: would now repair origins, issue a certificate for ${DOMAIN} if needed,"
    printf '    recreate the containers, delete orphaned certificates, and verify.\n\n'
    exit 0
fi

log "Waiting for SSH..."
for attempt in $(seq 1 20); do
    remote 'echo ok' >/dev/null 2>&1 && break
    [ "$attempt" -eq 20 ] && die "SSH never came up. Check the instance and the security group."
    sleep 10
done
printf '    connected\n'

# --- 4. Origins -------------------------------------------------------------
# Idempotent: exits early when .env already matches the current IP.
log "Repairing .env origins..."
remote "cd $REMOTE_DIR && ./scripts/fix-staging-origins.sh" 2>&1 | sed 's/^/    /' || true

# --- 5. Certificate ---------------------------------------------------------
if remote "sudo test -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem" 2>/dev/null; then
    log "Certificate for ${DOMAIN} already exists — skipping issuance."
    printf '    (re-running this script costs no Let'\''s Encrypt quota)\n'
else
    log "Issuing a certificate for ${DOMAIN}..."
    # Stage 1: nginx must serve the ACME challenge over port 80 before a
    # certificate for this name exists -- it cannot start with the HTTPS config
    # pointing at a certificate file that is not there yet.
    remote "cd $REMOTE_DIR && docker compose -f docker-compose.yml -f docker-compose.acme.yml up -d frontend" >/dev/null 2>&1
    sleep 8

    # Dry run first, always: Let's Encrypt rate-limits the SHARED sslip.io
    # domain (50 certificates/week across every user of the service), and
    # failed real attempts count against it.
    printf '    dry run...\n'
    remote "sudo certbot certonly --webroot -w /var/www/certbot -d ${DOMAIN} --dry-run" 2>&1 \
        | grep -qi "dry run was successful" || die "Certbot dry run failed. Nothing was issued.
Check that port 80 is open and that ${DOMAIN} resolves to ${IP}."

    printf '    issuing...\n'
    remote "sudo certbot certonly --webroot -w /var/www/certbot -d ${DOMAIN} --agree-tos --register-unsafely-without-email --non-interactive" 2>&1 \
        | grep -E "Successfully received|expires on" | sed 's/^/    /'
fi

# --- 6. Recreate containers -------------------------------------------------
# This is the step that actually fixes things. Everything above is undone if
# the containers keep running with the old hostname in their stored env.
log "Recreating containers with the HTTPS overlay..."
remote "cd $REMOTE_DIR && docker compose -f docker-compose.yml -f docker-compose.https.yml up -d" 2>&1 \
    | tail -4 | sed 's/^/    /'

# --- 7. Retire orphaned certificates ---------------------------------------
# ORDER MATTERS. The old certificate must outlive the old containers: nginx
# refuses to start when ssl_certificate points at a file that does not exist,
# so deleting it before step 6 would leave the frontend unable to boot.
log "Removing certificates for hostnames that no longer point here..."
ORPHANS=$(remote "sudo certbot certificates 2>/dev/null | grep 'Certificate Name:' | awk '{print \$3}' | grep -v '^${DOMAIN}\$'" || true)
if [ -n "$ORPHANS" ]; then
    while read -r orphan; do
        [ -n "$orphan" ] || continue
        printf '    deleting %s\n' "$orphan"
        remote "sudo certbot delete --cert-name ${orphan} --non-interactive" >/dev/null 2>&1 || warn "could not delete $orphan"
    done <<< "$ORPHANS"
else
    printf '    none found\n'
fi

# --- 8. Verify --------------------------------------------------------------
log "Verifying from outside..."
sleep 5
if "${REPO_ROOT}/scripts/verify-staging.sh" "$DOMAIN"; then
    printf '\033[1;32mRecovery complete.\033[0m\n'
    printf '  https://%s   (login: karosadmin)\n' "$DOMAIN"
    printf '  Remember to stop the instance when you are done — it bills while running.\n\n'
else
    die "Recovery ran, but verification failed. See the failed checks above.
Logs:  ssh -i $SSH_KEY ${SSH_USER}@${IP} 'cd $REMOTE_DIR && docker compose logs --tail 50'"
fi
