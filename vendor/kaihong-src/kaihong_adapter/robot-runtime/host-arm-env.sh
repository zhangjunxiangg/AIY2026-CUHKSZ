#!/bin/sh

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
ARM_HOST_ROOT="${ARM_HOST_ROOT:-$ROOT/host_arm}"

export ARM_HOST_ROOT
export PYTHONPATH="$ARM_HOST_ROOT/kinematics/src:$ARM_HOST_ROOT/servo_driver/src:$ARM_HOST_ROOT/servo_controllers/src:$ARM_HOST_ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export ROS_PACKAGE_PATH="$ARM_HOST_ROOT${ROS_PACKAGE_PATH:+:$ROS_PACKAGE_PATH}"
