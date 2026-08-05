#!/bin/sh
set -eu

PREFIX="${1:-/data/robot/maps/real_test}"
ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
mkdir -p /data/robot/maps
. "$ROOT/robot-env.sh"
rosrun map_server map_saver -f "$PREFIX"
[ -s "$PREFIX.yaml" ] && [ -s "$PREFIX.pgm" ] || {
  echo 'ERROR: map files were not created' >&2
  exit 2
}
echo "map_saved=$PREFIX.yaml"
