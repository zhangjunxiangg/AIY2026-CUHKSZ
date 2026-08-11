#!/bin/sh
# Astra 相机节点保活脚本（在机器车板端运行）
# 原理：每 5 秒在容器里用 rospy.wait_for_message 等一帧 RGB，
#      4 秒内拿不到就认为 Astra 节点卡死/断流，自动重启 rk3588s-vision。

CONTAINER=rk3588s-vision
TOPIC=/astra_camera/rgb/image_raw
CHECK_INTERVAL=5
WAIT_AFTER_RESTART=18

# 一次性把检查脚本写进容器 /tmp
CHECK_PY=/tmp/check_astra_frame.py
cat > "$CHECK_PY" <<'PY'
import sys
import rospy
from sensor_msgs.msg import Image
rospy.init_node('astra_frame_check', anonymous=True, disable_signals=True)
try:
    rospy.wait_for_message('/astra_camera/rgb/image_raw', Image, timeout=4.0)
    sys.exit(0)
except rospy.ROSException:
    sys.exit(1)
PY
docker cp "$CHECK_PY" "$CONTAINER:$CHECK_PY" >/dev/null 2>&1 || true

restart_container() {
    echo "[watchdog] $(date '+%H:%M:%S') no frame for ${CHECK_INTERVAL}s, restarting $CONTAINER ..."
    /data/robot-host/stop-vision-4.1.sh >/dev/null 2>&1 || true
    /data/robot-host/start-vision-4.1.sh >/dev/null 2>&1 || true
    docker cp "$CHECK_PY" "$CONTAINER:$CHECK_PY" >/dev/null 2>&1 || true
    echo "[watchdog] $(date '+%H:%M:%S') restart done, waiting ${WAIT_AFTER_RESTART}s for warm-up ..."
    sleep "$WAIT_AFTER_RESTART"
    echo "[watchdog] $(date '+%H:%M:%S') warm-up finished, resume monitoring"
}

echo "[watchdog] started, monitoring $TOPIC every ${CHECK_INTERVAL}s ..."

while true; do
    sleep "$CHECK_INTERVAL"

    # 在容器里等一帧 RGB；4s 内拿到说明正常，拿不到就重启
    if docker exec "$CONTAINER" bash -lc "
        source /opt/ros/noetic/setup.bash
        source /vision_ws/devel/setup.bash
        python3 $CHECK_PY
    " >/dev/null 2>&1; then
        continue
    fi

    restart_container
done
