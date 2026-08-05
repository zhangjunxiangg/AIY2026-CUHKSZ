#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
PID_FILE="$ROOT/run/lidar.pid"
pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
  echo 'lidar=STOPPED'
  exit 1
fi
if timeout 5 rostopic echo -n 1 /scan >/dev/null 2>&1; then
  echo 'lidar=RUNNING SCAN=READY DRIVER=raw-standard'
else
  echo 'lidar=RUNNING SCAN=NO_DATA'
  exit 2
fi
