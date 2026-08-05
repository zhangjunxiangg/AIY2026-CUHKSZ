#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"

for name in roscore rrc chassis odom; do
    file="$ROOT/run/$name.pid"
    if [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null; then
        echo "$name=RUNNING pid=$(cat "$file")"
    else
        echo "$name=STOPPED"
    fi
done

if rostopic list >/dev/null 2>&1; then
    echo "rosmaster=READY"
    rostopic list
else
    echo "rosmaster=UNAVAILABLE"
fi
