#!/bin/bash
# Patched copy of /data/gemini335/runtime/container-entrypoint.sh.
# Changes vs the 2026-08-03 original:
#   1. Docker on KaihongOS creates an EMPTY /etc/hosts, so roslaunch dies
#      with "RLException: cannot resolve host address for machine
#      [localhost]" whenever it must resolve localhost (standalone /
#      loopback mode). Ensure a minimal hosts entry exists.
#   2. Use create-usb-nodes.sh (all buses) instead of create-usb6-nodes.sh
#      (bus 006 only), so the camera works from any physical USB port.
set -e

if ! grep -q 'localhost' /etc/hosts 2>/dev/null; then
    printf '127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n' >> /etc/hosts
fi

/tmp/create-usb-nodes.sh >/tmp/create-usb-nodes.log 2>&1

source /opt/ros/noetic/setup.bash
source /vision_ws/devel/setup.bash
source /gemini_ws/devel/setup.bash

if [ "${GEMINI_START_LOCAL_ROSCORE:-1}" = "1" ]; then
    roscore >/tmp/roscore.log 2>&1 &
    sleep 4
fi

python3 /tmp/publish_compressed_color.py >/tmp/compressed-color.log 2>&1 &

# Web streamer (deployed by start-gemini335.sh when
# /data/gemini335-web/gemini_web_stream.py exists). The until-loop restarts
# it if it ever crashes; because this block lives in the entrypoint, the
# streamer also comes back automatically on container restart.
if [ -f /tmp/gemini_web_stream.py ]; then
    (
        until python3 /tmp/gemini_web_stream.py >>/tmp/gemini-web.log 2>&1; do
            sleep 2
        done
    ) &
fi

exec roslaunch orbbec_camera gemini_330_series.launch \
    camera_name:=aux_camera \
    enable_color:=true color_width:=640 color_height:=480 color_fps:=15 color_format:=MJPG \
    enable_depth:=true depth_width:=640 depth_height:=480 depth_fps:=15 depth_format:=Y16 \
    depth_registration:=true align_mode:=SW \
    enable_laser:=true laser_energy_level:=1 enable_ldp:=false \
    enable_hardware_noise_removal_filter:=false enable_noise_removal_filter:=false \
    enable_sync_host_time:=false enable_frame_sync:=false \
    enable_point_cloud:=false enable_colored_point_cloud:=false
