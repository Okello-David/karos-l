#!/usr/bin/env bash
#
# KarosL — read-only convenience wrapper around `docker compose logs`.
#
# Saves typing when troubleshooting on the staging server. Purely read-only:
# it starts, stops, and changes nothing. Everything it does is a plain
# `docker compose logs` invocation (docs/AWS_EC2_DEPLOYMENT.md §10).
#
# Usage:
#   ./scripts/docker-logs.sh                    # last 100 lines, all services
#   ./scripts/docker-logs.sh backend            # last 100 lines, backend only
#   ./scripts/docker-logs.sh backend -f         # follow backend live
#   ./scripts/docker-logs.sh db --since 10m     # db, last 10 minutes
#   ./scripts/docker-logs.sh --errors           # grep all logs for problems
#   ./scripts/docker-logs.sh --status           # docker compose ps + disk usage
#
# Any extra arguments are passed straight through to `docker compose logs`.
#
set -euo pipefail

die() { printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

command -v docker >/dev/null 2>&1 || die "docker not found."
docker compose version >/dev/null 2>&1 || die "The Docker Compose v2 plugin is missing."

case "${1:-}" in
    -h|--help)
        sed -n '2,20p' "$0"
        exit 0
        ;;
    --status)
        # Each probe is time-bounded: `docker system df` in particular can take
        # a very long time on a host with a large image/build cache, and a
        # diagnostic command that hangs is worse than one that says "timed out".
        run_bounded() {
            local secs="$1"; shift
            if command -v timeout >/dev/null 2>&1; then
                timeout "$secs" "$@" || printf '(no output — command failed or timed out after %ss)\n' "$secs"
            else
                "$@" || true
            fi
        }

        printf '\n\033[1;34m==> Services\033[0m\n'
        run_bounded 20 docker compose ps
        printf '\n\033[1;34m==> Container resource usage\033[0m\n'
        run_bounded 20 docker stats --no-stream
        printf '\n\033[1;34m==> Disk usage (a full disk breaks builds and Postgres)\033[0m\n'
        run_bounded 10 df -h /
        printf '\n\033[1;34m==> Docker disk usage\033[0m\n'
        run_bounded 30 docker system df
        exit 0
        ;;
    --errors)
        printf '\n\033[1;34m==> Scanning recent logs for errors/tracebacks\033[0m\n'
        # `|| true` so a clean log (no matches, grep exit 1) is a success, not
        # a script failure — "nothing found" is the good outcome here.
        docker compose logs --tail 500 2>&1 \
            | grep -iE 'error|traceback|exception|fatal|critical|refused|unhealthy' \
            || printf 'No errors found in the last 500 log lines.\n'
        exit 0
        ;;
esac

# First argument is a service name only if it is one of ours; otherwise treat
# everything as flags for `docker compose logs`.
SERVICE=""
if [ $# -gt 0 ]; then
    case "$1" in
        backend|frontend|db) SERVICE="$1"; shift ;;
    esac
fi

# Default to a bounded tail so an unfiltered call cannot dump a huge log.
if [ $# -eq 0 ]; then
    set -- --tail 100
fi

if [ -n "$SERVICE" ]; then
    exec docker compose logs "$@" "$SERVICE"
else
    exec docker compose logs "$@"
fi
