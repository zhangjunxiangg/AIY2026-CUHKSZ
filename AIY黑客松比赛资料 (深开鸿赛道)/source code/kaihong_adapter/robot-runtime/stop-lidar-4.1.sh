#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
PID_FILE="$ROOT/run/lidar.pid"
pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  attempt=0
  while kill -0 "$pid" 2>/dev/null && [ "$attempt" -lt 30 ]; do
    sleep 0.1
    attempt=$((attempt + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
fi
rm -f "$PID_FILE"
echo 'lidar=STOPPED'
