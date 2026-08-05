#!/bin/sh
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
FAIL=0

check_host_topic() {
  topic="$1"
  label="$2"
  if timeout 8 rostopic echo -n 1 "$topic" >/dev/null 2>&1; then
    echo "$label=PASS"
  else
    echo "$label=FAIL"
    FAIL=1
  fi
}

check_container_topic() {
  topic="$1"
  label="$2"
  if docker exec rk3588s-vision bash -lc \
      "source /opt/ros/noetic/setup.bash; source /chassis_ws/devel/setup.bash; source /vision_ws/devel/setup.bash; timeout 8 rostopic echo -n 1 '$topic'" \
      >/dev/null 2>&1; then
    echo "$label=PASS"
  else
    echo "$label=FAIL"
    FAIL=1
  fi
}

check_host_topic /ros_robot_controller/imu_raw IMU
check_host_topic /ros_robot_controller/battery BATTERY
check_host_topic /odom ODOM_OPEN_LOOP
if "$ROOT/healthcheck-lidar-4.1.sh"; then
  echo "LIDAR_LAYER=PASS"
else
  echo "LIDAR_LAYER=FAIL"
  FAIL=1
fi
check_host_topic /astra_camera/rgb/camera_info RGB
check_host_topic /astra_camera/depth/camera_info DEPTH
check_container_topic /astra_camera/depth/points POINT_CLOUD
CAMERA_OPS=/data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/robot_ops.py
if [ -f "$CAMERA_OPS" ]; then
  camera_result=$(/bin/run python3 "$CAMERA_OPS" camera-capture 2>&1 || true)
  echo "$camera_result"
  if echo "$camera_result" | grep -Eq '"valid_depth_pixels": [1-9][0-9]*'; then
    echo "DEPTH_VALID_PIXELS=PASS"
  else
    echo "DEPTH_VALID_PIXELS=FAIL"
    FAIL=1
  fi
else
  echo "DEPTH_VALID_PIXELS=FAIL missing_camera_capture_interface"
  FAIL=1
fi
if rostopic list 2>/dev/null | grep -qx /detections; then
  check_container_topic /detections OPENCV_DETECTIONS
else
  echo "OPENCV_DETECTIONS=OPTIONAL_DISABLED"
fi

if "$ROOT/healthcheck-arm-4.1.sh"; then
  echo "ARM_LAYER=PASS"
else
  echo "ARM_LAYER=FAIL"
  FAIL=1
fi

# AI/agent runtime is intentionally host-based after the 4.1 migration.
# Do not start the retired AI Docker image during a health check: that image is
# retained only as a rollback artifact and may be removed after acceptance.
if command -v mclaw >/dev/null 2>&1 && \
   [ -d /data/local/tmp/.mclaw/skills ] && \
   [ -x "$(command -v mclaw)" ]; then
  echo "AI_RUNTIME=PASS mode=host"
else
  echo "AI_RUNTIME=FAIL mode=host"
  FAIL=1
fi

[ "$FAIL" -eq 0 ] && echo "healthcheck=PASS" || echo "healthcheck=FAIL"
exit "$FAIL"
