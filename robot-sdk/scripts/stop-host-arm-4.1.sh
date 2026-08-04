#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
PID_DIR="$ROOT/run"

for name in arm-kinematics-host arm-manager-host; do
    file="$PID_DIR/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
    fi
done
sleep 1
for name in arm-kinematics-host arm-manager-host; do
    file="$PID_DIR/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
done
echo "host_arm=STOPPED"

