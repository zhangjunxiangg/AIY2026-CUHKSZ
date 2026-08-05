#!/bin/sh
set -eu

ROOT=${ROBOT_HOST_ROOT:-/data/robot-host}
. "$ROOT/robot-env.sh"
exec python3 -X faulthandler "$ROOT/student/tools/receive-aux-rgbd-once.py"
