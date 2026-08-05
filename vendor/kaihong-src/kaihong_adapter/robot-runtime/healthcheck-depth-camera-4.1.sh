#!/bin/sh
# Dedicated Astra Pro Plus read-only acceptance test.
set -u

NAME=rk3588s-vision
ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
FAIL=0

if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo false)" != true ]; then
  echo 'VISION_CONTAINER=FAIL'
  exit 2
fi

check_topic() {
  topic="$1"
  label="$2"
  if docker exec "$NAME" bash -lc \
      "source /opt/ros/noetic/setup.bash; source /chassis_ws/devel/setup.bash; source /vision_ws/devel/setup.bash; timeout 10 rostopic echo -n 1 '$topic'" \
      >/dev/null 2>&1; then
    echo "${label}=PASS"
  else
    echo "${label}=FAIL"
    FAIL=1
  fi
}

check_rate() {
  topic="$1"
  label="$2"
  output="/tmp/${label}.hz"
  docker exec "$NAME" bash -lc \
    "source /opt/ros/noetic/setup.bash; source /chassis_ws/devel/setup.bash; source /vision_ws/devel/setup.bash; timeout 8 rostopic hz -w 20 '$topic'" \
    >"$output" 2>&1 || true
  if grep -q 'average rate:' "$output"; then
    rate_line=$(grep 'average rate:' "$output" | tail -n 1)
    echo "${label}_HZ=PASS ${rate_line}"
  else
    echo "${label}_HZ=FAIL"
    tail -n 20 "$output"
    FAIL=1
  fi
}

check_topic /astra_camera/rgb/camera_info RGB_INFO
check_topic /astra_camera/depth/camera_info DEPTH_INFO
check_topic /astra_camera/ir/camera_info IR_INFO
check_topic /astra_camera/depth/points POINT_CLOUD

docker exec "$NAME" bash -lc '
  source /opt/ros/noetic/setup.bash
  source /chassis_ws/devel/setup.bash
  source /vision_ws/devel/setup.bash
  echo ===RGB_CAMERA_INFO===
  timeout 8 rostopic echo -n 1 /astra_camera/rgb/camera_info | grep -E "width:|height:|distortion_model:"
  echo ===DEPTH_CAMERA_INFO===
  timeout 8 rostopic echo -n 1 /astra_camera/depth/camera_info | grep -E "width:|height:|distortion_model:"
  echo ===ENCODINGS===
  printf "RGB="
  timeout 8 rostopic echo -n 1 /astra_camera/rgb/image_raw/encoding
  printf "DEPTH="
  timeout 8 rostopic echo -n 1 /astra_camera/depth/image_raw/encoding
  printf "IR="
  timeout 8 rostopic echo -n 1 /astra_camera/ir/image_raw/encoding
  echo ===POINT_FRAME===
  timeout 8 rostopic echo -n 1 /astra_camera/depth/points/header/frame_id
' || FAIL=1

check_rate /astra_camera/rgb/image_raw RGB
check_rate /astra_camera/depth/image_raw DEPTH
check_rate /astra_camera/ir/image_raw IR
check_rate /astra_camera/depth/points POINTS

docker stats --no-stream "$NAME" 2>/dev/null || true

if [ "$FAIL" -eq 0 ]; then
  echo 'depth_camera_healthcheck=PASS'
else
  echo 'depth_camera_healthcheck=FAIL'
fi
exit "$FAIL"
