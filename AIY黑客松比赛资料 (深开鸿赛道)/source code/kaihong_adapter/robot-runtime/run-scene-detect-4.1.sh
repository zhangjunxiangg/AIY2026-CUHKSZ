#!/bin/sh
# Host entry point for one-shot RGB-D/tag/color detection.
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
NAME=rk3588s-vision

[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo false)" = true ] || {
  echo 'ERROR: vision container is not running' >&2
  exit 2
}

docker cp "$ROOT/scene-detect-once.py" "$NAME:/tmp/scene-detect-once.py"
docker cp "$ROOT/scene-detect-container.sh" "$NAME:/tmp/scene-detect-container.sh"
docker exec "$NAME" bash /tmp/scene-detect-container.sh
docker cp "$NAME:/tmp/scene-detect.jpg" "$ROOT/scene-detect.jpg"
echo "SCENE_IMAGE=$ROOT/scene-detect.jpg"
