#!/usr/bin/env bash
# ============================================
# M-Robots 机器人全链路健康检查
# 用法: bash scripts/healthcheck.sh [connect-key]
# 默认 connect-key: ec29004133314d38433031a523403c00
# ============================================

TARGET=${1:-ec29004133314d38433031a523403c00}
HDC="hdc -t $TARGET"

echo "=========================================="
echo "M-Robots 机器人健康检查"
echo "Target: $TARGET"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# ---------- 0. HDC 连接检查 ----------
echo "[0] HDC 连接检查"
if ! $HDC shell "echo HDC_OK" >/dev/null 2>&1; then
    echo "[FAIL] HDC 无法连接板子"
    exit 1
fi
echo "[PASS] HDC 连接正常"
echo ""

# ---------- 1. 系统基础 ----------
echo "[1] 系统基础"
$HDC shell "uname -a"
$HDC shell "uptime"
echo ""

# ---------- 2. ROS 核心 ----------
echo "[2] ROS 核心节点"
$HDC shell "run rosnode list 2>/dev/null" | while read -r node; do
    echo "  $node"
done
echo ""

# ---------- 3. 传感器数据检查 ----------
echo "[3] 传感器数据流检查"

check_topic() {
    local topic="$1"
    local label="$2"
    if $HDC shell ". /data/robot-host/robot-env.sh && timeout 5 rostopic echo -n 1 $topic >/dev/null 2>&1"; then
        echo "[PASS] $label ($topic)"
        return 0
    else
        echo "[FAIL] $label ($topic) - 无数据"
        return 1
    fi
}

check_topic "/ros_robot_controller/imu_raw" "IMU"
check_topic "/ros_robot_controller/battery" "电池"
check_topic "/odom" "里程计"
check_topic "/scan" "激光雷达"
check_topic "/servo_controllers/port_id_1/servo_states" "舵机状态"
check_topic "/arm_controller/state" "机械臂状态"
check_topic "/gripper_controller/state" "夹爪状态"

echo ""

# ---------- 4. 相机/视觉检查 ----------
echo "[4] 相机/视觉检查"
if $HDC shell "run rostopic list 2>/dev/null | grep -i astra" >/dev/null 2>&1; then
    echo "[PASS] Astra 相机话题已发布"
else
    echo "[FAIL] Astra 相机话题未发布"
    echo "       可能原因: rk3588s-vision Docker 容器未启动"
    echo "       修复: 板端执行 /data/robot-host/start-vision-4.1.sh"
fi

if $HDC shell "docker ps 2>/dev/null | grep rk3588s-vision" >/dev/null 2>&1; then
    echo "[PASS] rk3588s-vision 容器运行中"
else
    echo "[FAIL] rk3588s-vision 容器未运行"
fi
echo ""

# ---------- 5. 控制链路检查 ----------
echo "[5] 控制链路检查"
if $HDC shell "run rostopic info /cmd_vel 2>/dev/null | grep -i publisher" >/dev/null 2>&1; then
    echo "[PASS] /cmd_vel 控制链路正常"
else
    echo "[FAIL] /cmd_vel 无发布者"
fi

if $HDC shell "run rosnode list 2>/dev/null | grep chassis_controller" >/dev/null 2>&1; then
    echo "[PASS] chassis_controller 节点运行中"
else
    echo "[FAIL] chassis_controller 节点未运行"
fi
echo ""

# ---------- 6. 硬件设备文件 ----------
echo "[6] 硬件设备文件"
echo "ttyUSB:"
$HDC shell "ls /dev/ttyUSB* 2>/dev/null || echo '  无 ttyUSB 设备'"
echo "video (前5个):"
$HDC shell "ls /dev/video* 2>/dev/null | head -5 || echo '  无 video 设备'"
echo ""

# ---------- 7. M-Claw / AI 运行时 ----------
echo "[7] M-Claw / AI 运行时"
if $HDC shell "which mclaw" >/dev/null 2>&1; then
    echo "[PASS] mclaw 已安装"
else
    echo "[FAIL] mclaw 未安装"
fi

if $HDC shell "ls /data/local/tmp/.mclaw/skills 2>/dev/null" >/dev/null 2>&1; then
    echo "[PASS] M-Claw skills 目录存在"
else
    echo "[FAIL] M-Claw skills 目录不存在"
fi
echo ""

# ---------- 8. 网络与 SSH ----------
echo "[8] 网络与 SSH"
$HDC shell "ifconfig 2>/dev/null | grep -E 'inet addr|inet ' | head -3" || echo "  无网络信息"
if $HDC shell "ps | grep sshd | grep -v grep" >/dev/null 2>&1; then
    echo "[PASS] SSH 服务运行中"
else
    echo "[WARN] SSH 服务未运行"
fi
echo ""

# ---------- 9. 存储空间 ----------
echo "[9] 存储空间"
$HDC shell "df -h /data 2>/dev/null | tail -1" || echo "  无法获取存储信息"
echo ""

# ---------- 10. 总结 ----------
echo "=========================================="
echo "检查完成"
echo "=========================================="
