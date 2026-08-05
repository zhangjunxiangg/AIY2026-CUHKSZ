#!/bin/sh
set -eu
ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
exec timeout 25 "$ROOT/run-arm-python-4.1.sh" diagnose-servo3-feedback.py

