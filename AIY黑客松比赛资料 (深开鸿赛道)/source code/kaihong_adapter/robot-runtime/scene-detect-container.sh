#!/bin/bash
set -e
source /opt/ros/noetic/setup.bash
source /chassis_ws/devel/setup.bash
source /vision_ws/devel/setup.bash
python3 /tmp/scene-detect-once.py
