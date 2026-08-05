#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
LOCK_DIR="$ROOT/run/start-all.lock"
mkdir -p "$ROOT/run"

# Autostart and an operator may request startup at nearly the same time.  Use
# an atomic directory lock so two launchers cannot race on the ROS master or
# the fixed rk3588s-vision container name.
attempt=0
while ! mkdir "$LOCK_DIR" 2>/dev/null; do
  owner=""
  [ ! -f "$LOCK_DIR/pid" ] || owner="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -z "$owner" ] || ! kill -0 "$owner" 2>/dev/null; then
    rm -rf "$LOCK_DIR"
    continue
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 120 ]; then
    echo "ERROR: robot stack startup lock timed out (owner=$owner)" >&2
    exit 5
  fi
  sleep 1
done
echo $$ >"$LOCK_DIR/pid"
cleanup_lock() {
  rm -rf "$LOCK_DIR"
}
trap cleanup_lock EXIT INT TERM HUP

"$ROOT/start-host-chassis.sh"
if ! "$ROOT/start-lidar-4.1.sh"; then
  "$ROOT/stop-host-chassis.sh" >/dev/null 2>&1 || true
  exit 1
fi
if ! "$ROOT/start-arm-4.1.sh"; then
  "$ROOT/stop-lidar-4.1.sh" >/dev/null 2>&1 || true
  "$ROOT/stop-host-chassis.sh" >/dev/null 2>&1 || true
  exit 1
fi
if ! "$ROOT/start-vision-4.1.sh"; then
  "$ROOT/stop-arm-4.1.sh" >/dev/null 2>&1 || true
  "$ROOT/stop-lidar-4.1.sh" >/dev/null 2>&1 || true
  "$ROOT/stop-host-chassis.sh" >/dev/null 2>&1 || true
  exit 1
fi
echo "robot_stack=RUNNING"
