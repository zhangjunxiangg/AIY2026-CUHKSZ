#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
export ROS_PACKAGE_PATH="$ROOT/navigation_runtime:$ROS_PACKAGE_PATH"

if ! timeout 5 rostopic echo -n 1 /scan >/dev/null 2>&1; then
    echo "ERROR: /scan has no data" >&2
    exit 2
fi
if ! timeout 5 rostopic echo -n 1 /odom >/dev/null 2>&1; then
    echo "ERROR: /odom has no data" >&2
    exit 3
fi
if [ -f "$ROOT/run/slam-host.pid" ] &&
   kill -0 "$(cat "$ROOT/run/slam-host.pid")" 2>/dev/null; then
    echo "slam=RUNNING mode=host"
    exit 0
fi

"$ROOT/stop-navigation-4.1.sh" >/dev/null 2>&1 || true
roslaunch "$ROOT/navigation_runtime/launch/slam.launch" \
    >"$ROOT/log/slam-host.log" 2>&1 &
echo $! >"$ROOT/run/slam-host.pid"
sleep 4
kill -0 "$(cat "$ROOT/run/slam-host.pid")" 2>/dev/null || {
    echo "ERROR: host SLAM exited; see $ROOT/log/slam-host.log" >&2
    exit 4
}
rosnode list | grep -q /slam_gmapping || {
    echo "ERROR: /slam_gmapping missing" >&2
    exit 5
}
echo "slam=RUNNING mode=host"
