#!/bin/bash
set -u

CAMERA_PID=""
DETECTOR_PID=""
WEB_PID=""
cleanup() {
  [ -z "$WEB_PID" ] || kill -INT "$WEB_PID" 2>/dev/null || true
  [ -z "$DETECTOR_PID" ] || kill -INT "$DETECTOR_PID" 2>/dev/null || true
  [ -z "$CAMERA_PID" ] || kill -INT "$CAMERA_PID" 2>/dev/null || true
  wait "$WEB_PID" "$DETECTOR_PID" "$CAMERA_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

roslaunch orbbec_camera astra_pro_plus.launch > /tmp/astra.log 2>&1 &
CAMERA_PID=$!
sleep 7
if ! kill -0 "$CAMERA_PID" 2>/dev/null; then
  echo "ERROR: Astra camera process exited" >&2
  tail -n 100 /tmp/astra.log >&2
  exit 3
fi

if [ "${VISION_ENABLE_DETECTOR:-0}" = 1 ]; then
  roslaunch opencv_detector opencv_detector.launch > /tmp/opencv-detector.log 2>&1 &
  DETECTOR_PID=$!
fi

if [ "${VISION_ENABLE_WEB:-0}" = 1 ]; then
  python3 /camera-web-ui.py > /tmp/camera-web-ui.log 2>&1 &
  WEB_PID=$!
  sleep 2
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo "ERROR: camera web UI exited" >&2
    cat /tmp/camera-web-ui.log >&2
    exit 4
  fi
fi

echo "VISION_CAMERA=RUNNING DETECTOR=${VISION_ENABLE_DETECTOR:-0} WEB=${VISION_ENABLE_WEB:-0}"
wait "$CAMERA_PID"
