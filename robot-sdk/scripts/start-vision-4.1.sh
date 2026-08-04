#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
NAME="rk3588s-vision"
IMAGE="${VISION_IMAGE:-rk3588s-ros1-vision:noetic}"

if ! rostopic list >/dev/null 2>&1; then
  echo "ERROR: ROS master is unavailable; start the host chassis/core first" >&2
  exit 2
fi

if docker inspect "$NAME" >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" = true ]; then
    echo "vision=RUNNING"
    exit 0
  fi
  docker rm "$NAME" >/dev/null
fi

docker run -d --name "$NAME" \
  --privileged \
  --network host \
  --add-host localhost:127.0.0.1 \
  -e ROS_MASTER_URI=http://127.0.0.1:11311 \
  -e ROS_IP=127.0.0.1 \
  -e VISION_ENABLE_DETECTOR="${VISION_ENABLE_DETECTOR:-0}" \
  -e VISION_ENABLE_WEB="${VISION_ENABLE_WEB:-0}" \
  -v "$ROOT/vision-stack.sh:/vision-stack.sh:ro" \
  -v "$ROOT/camera-web-ui.py:/camera-web-ui.py:ro" \
  "$IMAGE" bash /vision-stack.sh >/dev/null

sleep 10
if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo false)" != true ]; then
  echo "ERROR: vision container exited" >&2
  docker logs "$NAME" >&2 || true
  exit 3
fi
echo "vision=RUNNING DETECTOR=${VISION_ENABLE_DETECTOR:-0} WEB=${VISION_ENABLE_WEB:-0}"
