#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
"$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
echo "arm=STOPPED"
