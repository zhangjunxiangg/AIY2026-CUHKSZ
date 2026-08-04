#!/bin/sh
set -eu

BASE=/data/robot-host/student/demo
SORTING_BASE=$BASE/color_sorting
DETECT_BASE=$BASE/color_detect
OUT=/data/robot-host/student/output/color-sorting
CONTAINER=rk3588s-vision
CONTAINER_SRC=/tmp/student-color-sorting
CONTAINER_OUT=/tmp/student-color-sorting-output

test -f "$SORTING_BASE/color_sorting_demo.py"
test -f "$SORTING_BASE/color_sorting_config.json"
test -f "$DETECT_BASE/color_detect_demo.py"
test -f "$DETECT_BASE/color_ranges.json"
docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"

mkdir -p "$OUT"
docker exec "$CONTAINER" rm -rf "$CONTAINER_SRC" "$CONTAINER_OUT"
docker exec "$CONTAINER" mkdir -p "$CONTAINER_SRC" "$CONTAINER_OUT"
docker cp "$SORTING_BASE/color_sorting_demo.py" "$CONTAINER:$CONTAINER_SRC/color_sorting_demo.py"
docker cp "$SORTING_BASE/color_sorting_config.json" "$CONTAINER:$CONTAINER_SRC/color_sorting_config.json"
docker cp "$DETECT_BASE/color_detect_demo.py" "$CONTAINER:$CONTAINER_SRC/color_detect_demo.py"
docker cp "$DETECT_BASE/color_ranges.json" "$CONTAINER:$CONTAINER_SRC/color_ranges.json"
docker exec "$CONTAINER" bash -lc "
    source /opt/ros/noetic/setup.bash
    source /vision_ws/devel/setup.bash
    python3 $CONTAINER_SRC/color_sorting_demo.py \\
        --config $CONTAINER_SRC/color_sorting_config.json \\
        --detector-config $CONTAINER_SRC/color_ranges.json \\
        --output-dir $CONTAINER_OUT \\
        --public-output-dir $OUT
"
docker cp "$CONTAINER:$CONTAINER_OUT/." "$OUT/"
docker exec "$CONTAINER" rm -rf "$CONTAINER_SRC" "$CONTAINER_OUT"

echo "annotated=$OUT/latest-color-sorting.jpg"
echo "depth_preview=$OUT/latest-color-sorting-depth-preview.jpg"
echo "result=$OUT/latest-color-sorting.json"
echo "decision_topic=/student/color_sorting/decision"
