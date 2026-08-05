#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"

if "$ROOT/status-host-arm-4.1.sh" >/dev/null 2>&1; then
    echo "arm=RUNNING mode=host"
    exit 0
fi

# Final delivery policy: the arm is host-only. No Docker fallback exists.
if "$ROOT/start-host-arm-4.1.sh"; then
    echo "arm=RUNNING mode=host"
    exit 0
fi

"$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
echo "ERROR: host arm failed; Docker fallback is disabled" >&2
exit 1
