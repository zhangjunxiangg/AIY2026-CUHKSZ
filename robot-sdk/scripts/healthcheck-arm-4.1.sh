#!/bin/sh
# Read-only health check: never publishes joint or servo command topics.
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"

if "$ROOT/status-host-arm-4.1.sh" >/dev/null 2>&1; then
    echo "ARM_RUNTIME=HOST"
    exec "$ROOT/healthcheck-host-arm-4.1.sh"
fi

echo "ARM_RUNTIME=FAIL mode=host"
exit 2
