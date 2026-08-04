#!/bin/sh
set -eu

BASE=/data/robot-host/student/demo/color_detect
OUT=/data/robot-host/student/output/color-detect
CONTAINER=rk3588s-vision
CONTAINER_SRC=/tmp/student-color-detect
CONTAINER_OUT=/tmp/student-color-detect-output

test -f "$BASE/color_detect_demo.py"
test -f "$BASE/color_ranges.json"
docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"

mkdir -p "$OUT"
docker exec "$CONTAINER" rm -rf "$CONTAINER_SRC" "$CONTAINER_OUT"
docker exec "$CONTAINER" mkdir -p "$CONTAINER_SRC" "$CONTAINER_OUT"
docker cp "$BASE/color_detect_demo.py" "$CONTAINER:$CONTAINER_SRC/color_detect_demo.py"
docker cp "$BASE/color_ranges.json" "$CONTAINER:$CONTAINER_SRC/color_ranges.json"
docker exec "$CONTAINER" bash -lc "
    source /opt/ros/noetic/setup.bash
    source /vision_ws/devel/setup.bash
    python3 $CONTAINER_SRC/color_detect_demo.py \\
        --config $CONTAINER_SRC/color_ranges.json \\
        --output-dir $CONTAINER_OUT
"
docker cp "$CONTAINER:$CONTAINER_OUT/." "$OUT/"
docker exec "$CONTAINER" rm -rf "$CONTAINER_SRC" "$CONTAINER_OUT"

echo "annotated=$OUT/latest-color-detect.jpg"
echo "depth_preview=$OUT/latest-color-detect-depth-preview.jpg"
echo "result=$OUT/latest-color-detect.json"
