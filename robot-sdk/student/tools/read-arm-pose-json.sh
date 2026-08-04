#!/system/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
. "$ROOT/host-arm-env.sh"
exec "$ROOT/bin/python3" "$ROOT/student/tools/read-arm-pose-json.py"
