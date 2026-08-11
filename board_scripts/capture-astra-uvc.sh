#!/bin/sh
set -e
TMP=/data/robot-host/capture-tmp
mkdir -p "$TMP"

IMAGE_TAG=rk3588s-ros1-vision:noetic

# Kill any stale UVC publisher inside the vision container so the camera
# is released and we capture a fresh frame.
echo "[CAPTURE] stopping stale uvc_astra_publisher..."
docker exec rk3588s-vision sh -c 'pkill -f uvc_astra_publisher.py || true' || true
sleep 1

DEV=$(docker run --rm --privileged --network host -v "$TMP:/cap:ro" "$IMAGE_TAG" python3 /cap/find_astra.py 2>/dev/null)
echo "astra uvc dev=/dev/video$DEV"

echo "$DEV" > "$TMP/astra_dev.txt"
docker run --rm --privileged --network host \
  -v /data/robot-host/student/output:/out \
  -v "$TMP:/cap:ro" \
  "$IMAGE_TAG" python3 /cap/cap_astra_uvc.py
echo "ok -> /data/robot-host/student/output/astra_uvc_latest.jpg"
