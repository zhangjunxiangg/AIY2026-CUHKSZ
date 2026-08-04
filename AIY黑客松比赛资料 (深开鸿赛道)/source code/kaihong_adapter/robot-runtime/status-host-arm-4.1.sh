#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
. "$ROOT/host-arm-env.sh"

fail=0
for name in arm-manager-host arm-kinematics-host; do
    file="$ROOT/run/$name.pid"
    if [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null; then
        echo "$name=RUNNING pid=$(cat "$file")"
    else
        echo "$name=STOPPED"
        fail=1
    fi
done

rosparam get /servo_manager/init_finish >/dev/null 2>&1 || fail=1
rosparam get /kinematics/init_finish >/dev/null 2>&1 || fail=1
rosservice type /kinematics/get_link >/dev/null 2>&1 || fail=1

if [ "$fail" -eq 0 ]; then
    echo "host_arm=READY"
else
    echo "host_arm=NOT_READY"
fi
exit "$fail"

