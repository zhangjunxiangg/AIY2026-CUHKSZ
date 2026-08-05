#!/bin/sh

# M-Robots OS 4.1 host-side Python/ROS environment.
# The vendor runtime is complete but is not on the default PATH.
ROBOT_HOST_ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
PYROOT="${PYROOT:-/data/local/release/usr}"

export ROBOT_HOST_ROOT PYROOT
export PYTHONHOME="$PYROOT"
export LD_LIBRARY_PATH="$PYROOT/lib:/data/local/release/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$ROBOT_HOST_ROOT/bin:$PYROOT/bin:$PATH"
export PYTHONPATH="$ROBOT_HOST_ROOT/host_arm/kinematics/src:$ROBOT_HOST_ROOT/host_arm/servo_driver/src:$ROBOT_HOST_ROOT/host_arm/servo_controllers/src:$ROBOT_HOST_ROOT/host_arm/python:$ROBOT_HOST_ROOT/python:$ROBOT_HOST_ROOT/src/ros_robot_controller/src:$ROBOT_HOST_ROOT/src/chassis_controller/src:$PYROOT/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export CMAKE_PREFIX_PATH="$PYROOT${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export ROS_PACKAGE_PATH="$ROBOT_HOST_ROOT/navigation_runtime:$ROBOT_HOST_ROOT/host_arm:$ROBOT_HOST_ROOT/src:$PYROOT/share${ROS_PACKAGE_PATH:+:$ROS_PACKAGE_PATH}"
export HOME="${HOME:-/data/robot}"
export ROS_HOME="${ROS_HOME:-$ROBOT_HOST_ROOT/run/ros}"
# ROS CLI tools create a new log on every status call. Keep those transient
# logs in /tmp; production node stdout remains in fixed files under log/.
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/kaihong-ros-log}"

detect_wlan_ipv4() {
    output=$(ip -4 addr show wlan0 2>/dev/null || true)
    previous=""
    for word in $output; do
        if [ "$previous" = "inet" ]; then
            printf '%s\n' "${word%/*}"
            return 0
        fi
        previous=$word
    done
    return 1
}

# ROS1 embeds node addresses in the master registry.  Use the current wlan0
# address so nodes on an auxiliary camera board can reach this robot.  Keep a
# loopback fallback for offline bench use, and respect explicit overrides.
if [ -z "${ROS_IP:-}" ]; then
    ROS_IP=$(detect_wlan_ipv4 || true)
    ROS_IP=${ROS_IP:-127.0.0.1}
fi
export ROS_IP
export ROS_MASTER_URI="${ROS_MASTER_URI:-http://$ROS_IP:11311}"
unset ROS_HOSTNAME

mkdir -p "$ROS_HOME" "$ROS_LOG_DIR" "$ROBOT_HOST_ROOT/run" "$ROBOT_HOST_ROOT/log"
