#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
for name in navigation-host slam-host; do
    file="$ROOT/run/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    [ -z "$pid" ] || kill "$pid" 2>/dev/null || true
done
sleep 1
for name in navigation-host slam-host; do
    file="$ROOT/run/$name.pid"
    [ -f "$file" ] || continue
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
done
echo "navigation=STOPPED"
