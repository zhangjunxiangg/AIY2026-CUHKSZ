#!/bin/sh
set -eu

BASE=/data/gemini335
OUT="$BASE/output"
CONTAINER=rk3588s-gemini335

mkdir -p "$OUT"
docker exec "$CONTAINER" bash -lc '
    source /opt/ros/noetic/setup.bash
    source /vision_ws/devel/setup.bash
    source /gemini_ws/devel/setup.bash
    rm -rf /tmp/gemini-output
    GEMINI_OUTPUT_DIR=/tmp/gemini-output python3 /tmp/capture_gemini335_rgbd.py
'
docker cp "$CONTAINER:/tmp/gemini-output/." "$OUT/"

echo "color=$OUT/latest-color.jpg"
echo "depth16=$OUT/latest-depth.png"
echo "depth_preview=$OUT/latest-depth-preview.jpg"
echo "metadata=$OUT/latest-metadata.json"
