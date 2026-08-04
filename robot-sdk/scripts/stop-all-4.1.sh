#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
"$ROOT/stop-navigation-4.1.sh" >/dev/null 2>&1 || true
"$ROOT/stop-arm-4.1.sh"
"$ROOT/stop-vision-4.1.sh"
"$ROOT/stop-lidar-4.1.sh"
"$ROOT/stop-host-chassis.sh"
echo "robot_stack=STOPPED"
