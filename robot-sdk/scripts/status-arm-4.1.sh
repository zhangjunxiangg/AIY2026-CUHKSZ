#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"

if "$ROOT/status-host-arm-4.1.sh" >/dev/null 2>&1; then
    echo "arm=RUNNING mode=host"
    "$ROOT/status-host-arm-4.1.sh"
    exit 0
fi

echo "arm=STOPPED"
exit 1
