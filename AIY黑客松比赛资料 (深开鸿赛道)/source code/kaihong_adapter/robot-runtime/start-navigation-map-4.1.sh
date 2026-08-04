#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
MAP_FILE="${1:-/data/robot/maps/map.yaml}"
. "$ROOT/robot-env.sh"
export ROS_PACKAGE_PATH="$ROOT/navigation_runtime:$ROS_PACKAGE_PATH"

[ -f "$MAP_FILE" ] || {
    echo "ERROR: map file not found: $MAP_FILE" >&2
    exit 2
}
timeout 5 rostopic echo -n 1 /scan >/dev/null 2>&1 || {
    echo "ERROR: /scan has no data" >&2
    exit 3
}
timeout 5 rostopic echo -n 1 /odom >/dev/null 2>&1 || {
    echo "ERROR: /odom has no data" >&2
    exit 4
}

"$ROOT/stop-navigation-4.1.sh" >/dev/null 2>&1 || true
roslaunch "$ROOT/navigation_runtime/launch/navigation.launch" map_file:="$MAP_FILE" \
    >"$ROOT/log/navigation-host.log" 2>&1 &
echo $! >"$ROOT/run/navigation-host.pid"
sleep 5
kill -0 "$(cat "$ROOT/run/navigation-host.pid")" 2>/dev/null || {
    echo "ERROR: host navigation exited; see $ROOT/log/navigation-host.log" >&2
    exit 5
}
rosnode list | grep -q /move_base || {
    echo "ERROR: /move_base missing" >&2
    exit 6
}
echo "navigation=RUNNING mode=host map=$MAP_FILE"
