#!/bin/sh
set -eu

echo "=== USB ==="
lsusb | grep '2bc5:0800' || true

echo "=== CONTAINER ==="
docker ps -a --filter name=rk3588s-gemini335 --format '{{.Names}} {{.Status}} {{.Image}}'

if docker ps --format '{{.Names}}' | grep -qx rk3588s-gemini335; then
    echo "=== ROS ==="
    docker exec rk3588s-gemini335 bash -lc '
        source /opt/ros/noetic/setup.bash
        source /vision_ws/devel/setup.bash
        source /gemini_ws/devel/setup.bash
        echo ROS_MASTER_URI=$ROS_MASTER_URI
        echo ROS_IP=$ROS_IP
        timeout 8 rostopic echo -n 1 /aux_camera/device_info 2>/dev/null || true
        timeout 8 rostopic echo -n 1 /aux_camera/color/camera_info 2>/dev/null | head -n 8 || true
        timeout 8 rostopic echo -n 1 /aux_camera/depth/camera_info 2>/dev/null | head -n 8 || true
        if timeout 15 rostopic echo -n 1 /aux_camera/depth/image_raw >/dev/null 2>&1; then
            echo DEPTH_FRAME=PASS
        else
            echo DEPTH_FRAME=FAIL
        fi
        if timeout 15 rostopic echo -n 1 /aux_camera/color/image_raw/compressed >/dev/null 2>&1; then
            echo COMPRESSED_COLOR_FRAME=PASS
        else
            echo COMPRESSED_COLOR_FRAME=FAIL
        fi
    '
fi
