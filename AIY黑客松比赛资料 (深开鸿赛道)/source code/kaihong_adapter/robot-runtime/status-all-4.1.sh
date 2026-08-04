#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
"$ROOT/status-host-chassis.sh"
"$ROOT/status-lidar-4.1.sh"
"$ROOT/status-arm-4.1.sh"
"$ROOT/status-vision-4.1.sh"
