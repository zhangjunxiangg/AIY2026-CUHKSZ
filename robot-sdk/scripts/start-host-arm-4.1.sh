#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
PID_DIR="$ROOT/run"
LOG_DIR="$ROOT/log"

. "$ROOT/robot-env.sh"
. "$ROOT/host-arm-env.sh"

manager_running=false
kinematics_running=false
if [ -f "$PID_DIR/arm-manager-host.pid" ]; then
    kill -0 "$(cat "$PID_DIR/arm-manager-host.pid")" 2>/dev/null && manager_running=true
fi
if [ -f "$PID_DIR/arm-kinematics-host.pid" ]; then
    kill -0 "$(cat "$PID_DIR/arm-kinematics-host.pid")" 2>/dev/null && kinematics_running=true
fi
if [ "$manager_running" = true ] && [ "$kinematics_running" = true ]; then
    echo "host_arm=RUNNING"
    exit 0
fi

"$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
rostopic list >/dev/null 2>&1 || {
    echo "ERROR: ROS master unavailable" >&2
    exit 3
}
rosservice type /ros_robot_controller/bus_servo/get_state >/dev/null 2>&1 || {
    echo "ERROR: STM32 bus-servo service unavailable" >&2
    exit 4
}

for required in \
    "$ARM_HOST_ROOT/servo_controllers/config/servo_controller.yaml" \
    "$ARM_HOST_ROOT/servo_controllers/scripts/controller_manager.py" \
    "$ARM_HOST_ROOT/kinematics/scripts/search_kinematics_solutions_node.py" \
    "$ARM_HOST_ROOT/kinematics/src/kinematics/forward_kinematics.py" \
    "$ARM_HOST_ROOT/kinematics/src/kinematics/inverse_kinematics.py"; do
    [ -f "$required" ] || {
        echo "ERROR: host arm file missing: $required" >&2
        exit 5
    }
done

rosparam delete /servo_manager >/dev/null 2>&1 || true
rosparam delete /kinematics >/dev/null 2>&1 || true
rosparam load \
    "$ARM_HOST_ROOT/servo_controllers/config/servo_controller.yaml" \
    /servo_manager

"$ROOT/bin/python3" \
    "$ARM_HOST_ROOT/servo_controllers/scripts/controller_manager.py" \
    __name:=servo_manager >"$LOG_DIR/arm-manager-host.log" 2>&1 &
echo $! >"$PID_DIR/arm-manager-host.pid"

ready=0
attempt=0
while [ "$attempt" -lt 25 ]; do
    if ! kill -0 "$(cat "$PID_DIR/arm-manager-host.pid")" 2>/dev/null; then
        break
    fi
    if rosparam get /servo_manager/init_finish >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "ERROR: host servo manager failed; see $LOG_DIR/arm-manager-host.log" >&2
    "$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
    exit 6
fi

"$ROOT/bin/python3" \
    "$ARM_HOST_ROOT/kinematics/scripts/search_kinematics_solutions_node.py" \
    __name:=kinematics >"$LOG_DIR/arm-kinematics-host.log" 2>&1 &
echo $! >"$PID_DIR/arm-kinematics-host.pid"

ready=0
attempt=0
while [ "$attempt" -lt 12 ]; do
    if ! kill -0 "$(cat "$PID_DIR/arm-kinematics-host.pid")" 2>/dev/null; then
        break
    fi
    if rosparam get /kinematics/init_finish >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "ERROR: host kinematics failed; see $LOG_DIR/arm-kinematics-host.log" >&2
    "$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
    exit 7
fi

# Never let the arm recall stale controller goals after boot.  Synchronize the
# measured pose first, then enable holding torque in a separate command.
"$ROOT/bin/python3" "$ROOT/hold-arm-current-position.py" \
    >"$LOG_DIR/arm-hold-current.log" 2>&1 || {
    echo "ERROR: failed to hold arm at its current pose; see $LOG_DIR/arm-hold-current.log" >&2
    "$ROOT/stop-host-arm-4.1.sh" >/dev/null 2>&1 || true
    exit 8
}

echo "host_arm=RUNNING_HOLDING_CURRENT_POSITION"
