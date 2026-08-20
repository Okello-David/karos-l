#!/usr/bin/env bash
#
# KarosL — the ONLY thing the CI deploy SSH key is allowed to run.
#
# Installed as the `command=` forced-command restriction on the CI deploy
# key's line in ~/.ssh/authorized_keys (see docs/CI_CD.md), alongside
# no-pty,no-X11-forwarding,no-agent-forwarding,no-port-forwarding. Whatever
# command a client requests over that key, sshd runs THIS instead — so if
# the private key ever leaked, the blast radius is "can trigger a deploy of
# the pinned branch," not "arbitrary shell on the box."
#
# Deliberately does not accept arguments from the SSH client ($SSH_ORIGINAL_COMMAND
# is read but only ever logged, never executed) — accepting and running
# whatever the client asked for would defeat the entire point of a forced
# command.
#
set -euo pipefail

if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
    logger -t karosl-ci-deploy "CI key connected; original request ignored: ${SSH_ORIGINAL_COMMAND}"
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec ./scripts/deploy-staging.sh --pull
