#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
found=0
for name in slam-host navigation-host; do
    file="$ROOT/run/$name.pid"
    if [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null; then
        echo "$name=RUNNING mode=host pid=$(cat "$file")"
        found=1
    fi
done
[ "$found" -eq 1 ] || echo "navigation=STOPPED"
