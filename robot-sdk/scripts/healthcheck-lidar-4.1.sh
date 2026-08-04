#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
TMP="$ROOT/run/lidar-scan-sample.txt"
mkdir -p "$ROOT/run"

timeout 8 rostopic echo -n 1 /scan >"$TMP" 2>/dev/null || {
  echo 'LIDAR_SCAN=FAIL'
  exit 2
}
grep -q 'frame_id: "laser"' "$TMP" || { echo 'LIDAR_FRAME=FAIL'; exit 3; }
grep -q 'angle_min: -3.14' "$TMP" || { echo 'LIDAR_ANGLE_MIN=FAIL'; exit 4; }
grep -q 'angle_max: 3.14' "$TMP" || { echo 'LIDAR_ANGLE_MAX=FAIL'; exit 5; }
grep -q 'range_max: 12.0' "$TMP" || { echo 'LIDAR_RANGE=FAIL'; exit 6; }

echo 'LIDAR_SCAN=PASS'
grep -E 'frame_id:|angle_min:|angle_max:|angle_increment:|scan_time:|range_min:|range_max:' "$TMP" | head -n 12
echo 'lidar_healthcheck=PASS'
