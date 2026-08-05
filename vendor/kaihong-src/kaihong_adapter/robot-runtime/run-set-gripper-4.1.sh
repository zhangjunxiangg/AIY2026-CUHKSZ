#!/bin/sh
set -eu
ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
exec "$ROOT/run-arm-python-4.1.sh" set-gripper-position.py "${1:-300}"

