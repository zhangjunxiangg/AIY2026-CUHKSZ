#!/bin/sh
# run.sh — teleop 运行环境包装（同 grasping/run_step.sh 的机制）
set -eu
. /data/robot-host/robot-env.sh
export LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0
cd /data/local/teleop
exec python3 "$@"
