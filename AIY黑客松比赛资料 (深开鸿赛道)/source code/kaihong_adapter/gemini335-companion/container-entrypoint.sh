#!/bin/bash
set -eu

/tmp/create-usb6-nodes.sh >/tmp/create-usb-nodes.log 2>&1

source /opt/ros/noetic/setup.bash
source /vision_ws/devel/setup.bash
source /gemini_ws/devel/setup.bash

if [ "${GEMINI_START_LOCAL_ROSCORE:-1}" = "1" ]; then
    roscore >/tmp/roscore.log 2>&1 &
    sleep 4
fi

python3 /tmp/publish_compressed_color.py >/tmp/compressed-color.log 2>&1 &

exec roslaunch orbbec_camera gemini_330_series.launch \
    camera_name:=aux_camera \
    enable_color:=true color_width:=640 color_height:=480 color_fps:=15 color_format:=MJPG \
    enable_depth:=true depth_width:=640 depth_height:=480 depth_fps:=15 depth_format:=Y16 \
    depth_registration:=true align_mode:=SW \
    enable_laser:=true laser_energy_level:=1 enable_ldp:=false \
    enable_hardware_noise_removal_filter:=false enable_noise_removal_filter:=false \
    enable_sync_host_time:=false enable_frame_sync:=false \
    enable_point_cloud:=false enable_colored_point_cloud:=false
