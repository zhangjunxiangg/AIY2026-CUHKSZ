#!/bin/sh
# run_step.sh — pipeline step 运行包装器
# robot-env.sh 提供 host_arm 包路径（servo_msgs/interfaces）；
# LD_PRELOAD 解决 OpenHarmony Python 缺符号段错误（见板端踩坑手册 §2.2）。
set -eu
. /data/robot-host/robot-env.sh
export LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0
cd /data/local/grasping
exec python3 "$@"
