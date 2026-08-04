#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"

if [ -n "${RRC_DEVICE:-}" ]; then
    :
elif [ -c /dev/ttyCH343USB0 ]; then
    # M-Robots OS 4.1 names the CH9102F/CH343 chassis adapter this way.
    RRC_DEVICE=/dev/ttyCH343USB0
elif [ -c /dev/rrc ]; then
    RRC_DEVICE=/dev/rrc
else
    RRC_DEVICE=/dev/ttyUSB0
fi
RRC_BAUDRATE="${RRC_BAUDRATE:-1000000}"
PID_DIR="$ROOT/run"
LOG_DIR="$ROOT/log"

if [ ! -c "$RRC_DEVICE" ]; then
    echo "ERROR: chassis serial device not found: $RRC_DEVICE" >&2
    exit 2
fi

if [ -f "$PID_DIR/chassis.pid" ] && kill -0 "$(cat "$PID_DIR/chassis.pid")" 2>/dev/null; then
    echo "host chassis is already running"
    exit 0
fi

cleanup_failed_start() {
    "$ROOT/stop-host-chassis.sh" >/dev/null 2>&1 || true
}
trap cleanup_failed_start INT TERM HUP

roscore >"$LOG_DIR/roscore.log" 2>&1 &
echo $! >"$PID_DIR/roscore.pid"
ready=0
attempt=0
while [ "$attempt" -lt 10 ]; do
    if rostopic list >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "ERROR: host roscore failed; see $LOG_DIR/roscore.log" >&2
    cleanup_failed_start
    exit 3
fi

# Keep the controller's vendor motor configuration. Re-sending motor_type=2
# on this 4.1 controller leaves telemetry working but prevents motor output.
"$ROOT/bin/python3" "$ROOT/src/ros_robot_controller/scripts/ros_robot_controller_node.py" \
    _device:="$RRC_DEVICE" _baudrate:="$RRC_BAUDRATE" \
    _cmd_timeout:=0.5 _configure_controller:=false _init_pwm_servo:=false \
    >"$LOG_DIR/ros_robot_controller.log" 2>&1 &
echo $! >"$PID_DIR/rrc.pid"

"$ROOT/bin/python3" "$ROOT/src/chassis_controller/scripts/chassis_controller_node.py" \
    _cmd_timeout:=0.5 _max_linear:=0.20 _max_angular:=0.50 _max_motor_rps:=1.50 \
    >"$LOG_DIR/chassis_controller.log" 2>&1 &
echo $! >"$PID_DIR/chassis.pid"

"$ROOT/bin/python3" "$ROOT/cmd_vel_odom_node.py" \
    _cmd_timeout:=0.5 _cmd_vel_topic:=/cmd_vel _odom_topic:=/odom \
    >"$LOG_DIR/cmd_vel_odom.log" 2>&1 &
echo $! >"$PID_DIR/odom.pid"

sleep 3
for name in roscore rrc chassis odom; do
    pid=$(cat "$PID_DIR/$name.pid")
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "ERROR: $name process exited; check $LOG_DIR" >&2
        cleanup_failed_start
        exit 4
    fi
done

echo "host chassis started"
echo "ROS_MASTER_URI=$ROS_MASTER_URI"
echo "RRC_DEVICE=$RRC_DEVICE"
echo "No movement command has been sent."
