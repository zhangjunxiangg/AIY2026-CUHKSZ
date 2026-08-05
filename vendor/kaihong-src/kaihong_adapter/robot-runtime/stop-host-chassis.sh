#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
PID_DIR="$ROOT/run"

# Stop publishers first. The controller shutdown handler publishes zeros and
# the STM32 node also has its own 0.5 second motor watchdog.
for name in chassis odom rrc roscore; do
    file="$PID_DIR/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
    fi
done
sleep 1
for name in chassis odom rrc roscore; do
    file="$PID_DIR/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
done
echo "host chassis stopped"
