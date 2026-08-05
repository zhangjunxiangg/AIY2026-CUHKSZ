#!/bin/sh
set -u

echo ===video-nodes===
ls -l /dev/video* 2>/dev/null || true
echo ===usb===
lsusb 2>/dev/null || true
echo ===v4l2-names===
for file in /sys/class/video4linux/video*/name; do
  [ -f "$file" ] || continue
  printf '%s: ' "$file"
  cat "$file"
done
echo ===camera-processes===
ps -ef | grep -E 'camera|video|uvc|astra|gemini' | grep -v grep || true
echo ===ros-camera-topics===
docker exec rk3588s-vision bash -lc '
  source /opt/ros/noetic/setup.bash
  rostopic list | grep -Ei "camera|image|video|usb_cam|astra|gemini" || true
'
