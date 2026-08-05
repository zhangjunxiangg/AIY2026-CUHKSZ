#!/bin/sh
# start_camera.sh — 解析 icSpring 相机设备节点并启动 gripper_camera_node（带逐个验证）
# 设备号会在重启/重枚举后漂移（已观测 video20/21/22 变化），所以：
#   1. 按 /sys 名字解析所有 icspring 节点；
#   2. 从小到大逐个尝试：启动 → 等 3s → 日志无 "cannot open"/"capture failed" 才算成功。
set -eu

TOPIC="${1:-/gripper_camera/image_raw}"
LOG=/data/local/grasping/logs/camera_node.log

# 已在跑且日志健康则直接返回
if pgrep -f gripper_camera_node.py >/dev/null 2>&1; then
    if ! tail -5 "$LOG" 2>/dev/null | grep -q "capture failed\|cannot open"; then
        echo "gripper_camera_node already RUNNING and healthy"
        exit 0
    fi
    echo "existing node unhealthy, restarting..."
    pkill -f gripper_camera_node.py || true
    sleep 1
fi

# 收集 icspring 节点（顺序不重要，失败的会自动试下一个）
DEVS=""
for d in /sys/class/video4linux/video*; do
    name=$(cat "$d/name" 2>/dev/null || true)
    case "$name" in
        *icspring*) DEVS="$DEVS /dev/$(basename "$d")" ;;
    esac
done

if [ -z "$DEVS" ]; then
    echo "ERROR: icspring camera not found in /sys/class/video4linux" >&2
    exit 1
fi

for DEV in $DEVS; do
    echo "trying $DEV ..."
    : > "$LOG"
    cd /data/local/perception
    nohup run python3 gripper_camera_node.py --device "$DEV" --topic "$TOPIC" >> "$LOG" 2>&1 &
    sleep 4
    if pgrep -f gripper_camera_node.py >/dev/null 2>&1 \
       && ! grep -q "cannot open\|capture failed" "$LOG"; then
        echo "gripper_camera_node=RUNNING dev=$DEV topic=$TOPIC"
        exit 0
    fi
    echo "$DEV failed, next"
    pkill -f gripper_camera_node.py || true
    sleep 1
done

echo "ERROR: all icspring nodes failed, see $LOG" >&2
exit 2
