#!/bin/sh
set -u

NAME="rk3588s-vision"
if docker inspect "$NAME" >/dev/null 2>&1 && [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" = true ]; then
  echo "vision=RUNNING"
  docker exec "$NAME" bash -lc \
    'source /opt/ros/noetic/setup.bash; source /chassis_ws/devel/setup.bash; source /vision_ws/devel/setup.bash; rostopic list' \
    2>/dev/null | grep -E '^/astra_camera/|^/detections$|^/target_'
else
  echo "vision=STOPPED"
fi
