#!/usr/bin/env bash
# ============================================
# 机器人控制就绪检查脚本
# 用法: bash scripts/check-control-ready.sh [connect-key]
# 默认: ec29004133314d38433031a523403c00
# ============================================

TARGET=${1:-ec29004133314d38433031a523403c00}
HDC="hdc -t $TARGET"
SSH_CMD="ssh -p 2223 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@172.20.10.5"

echo "=========================================="
echo "机器人控制就绪检查"
echo "Target: $TARGET"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# ---------- 0. 连接检查（优先 SSH，因为板子常走 WiFi） ----------
echo "[0] 连接检查"
if $SSH_CMD "echo SSH_OK" >/dev/null 2>&1; then
    echo "[PASS] SSH 连接正常"
    USE_SSH=true
elif $HDC shell "echo HDC_OK" >/dev/null 2>&1; then
    echo "[PASS] HDC 连接正常"
    USE_SSH=false
else
    echo "[FAIL] SSH 和 HDC 均无法连接"
    exit 1
fi
echo ""

# 封装执行命令
exec_cmd() {
    if [ "$USE_SSH" = true ]; then
        $SSH_CMD "$1"
    else
        $HDC shell "$1"
    fi
}

# ---------- 1. 串口设备检查 ----------
echo "[1] 串口设备检查"
if exec_cmd "ls -la /dev/ttyCH343USB0" 2>/dev/null | grep -q "crw"; then
    echo "[PASS] STM32 串口 /dev/ttyCH343USB0 存在"
else
    echo "[FAIL] STM32 串口不存在"
fi

if exec_cmd "ls -la /dev/ttyUSB*" 2>/dev/null | grep -q "crw"; then
    LIDAR_DEV=$(exec_cmd "ls /dev/ttyUSB* 2>/dev/null" | head -1)
    echo "[PASS] 雷达串口存在 ($LIDAR_DEV)"
else
    echo "[WARN] 雷达串口不存在（可能未接雷达）"
fi
echo ""

# ---------- 2. ROS 节点检查 ----------
echo "[2] ROS 节点检查"
check_node() {
    local node_name="$1"
    local label="$2"
    if exec_cmd ". /data/robot-host/robot-env.sh && rosnode list 2>/dev/null | grep -q \"$node_name\""; then
        echo "[PASS] $label ($node_name)"
        return 0
    else
        echo "[FAIL] $label ($node_name) 未运行"
        return 1
    fi
}

check_node "ros_robot_controller" "STM32 通信节点"
check_node "servo_manager" "舵机管理节点"
check_node "chassis_controller" "底盘控制节点"
check_node "rplidar_raw_node" "雷达节点"
echo ""

# ---------- 3. 话题/服务检查 ----------
echo "[3] 话题/服务检查"
check_topic_sub() {
    local topic="$1"
    local label="$2"
    if exec_cmd ". /data/robot-host/robot-env.sh && rostopic info $topic 2>/dev/null | grep -q 'Subscribers:'"; then
        echo "[PASS] $label ($topic) 有订阅者"
        return 0
    else
        echo "[FAIL] $label ($topic) 无订阅者"
        return 1
    fi
}

check_service() {
    local service="$1"
    local label="$2"
    if exec_cmd ". /data/robot-host/robot-env.sh && rosservice list 2>/dev/null | grep -q \"$service\""; then
        echo "[PASS] $label ($service)"
        return 0
    else
        echo "[FAIL] $label ($service) 不存在"
        return 1
    fi
}

check_topic_sub "/servo_controllers/port_id_1/id_pos_dur" "舵机命令话题"
check_topic_sub "/cmd_vel" "底盘控制话题"
check_service "/ros_robot_controller/bus_servo/get_state" "舵机查询服务"
echo ""

# ---------- 4. 舵机状态快速验证 ----------
echo "[4] 舵机状态验证"
if exec_cmd ". /data/robot-host/robot-env.sh && timeout 3 rostopic echo -n 1 /servo_controllers/port_id_1/servo_states >/dev/null 2>&1"; then
    echo "[PASS] 舵机状态话题有数据"
else
    echo "[FAIL] 舵机状态话题无数据"
fi
echo ""

# ---------- 5. 软总线/网络检查 ----------
echo "[5] 软总线/网络检查"
if exec_cmd "ifconfig wlan0 2>/dev/null | grep -q 'inet addr'"; then
    IP=$(exec_cmd "ifconfig wlan0 2>/dev/null | grep 'inet addr' | sed 's/.*inet addr:\([0-9.]*\).*/\1/'")
    echo "[PASS] WiFi 已连接，IP: $IP"
else
    echo "[WARN] WiFi 未连接"
fi

if exec_cmd "ps | grep -q sshd"; then
    echo "[PASS] SSH 服务运行中"
else
    echo "[WARN] SSH 服务未运行"
fi
echo ""

# ---------- 6. 控制链路总结 ----------
echo "=========================================="
echo "控制就绪状态总结"
echo "=========================================="

# 统计 FAIL 数量
FAIL_COUNT=0
check_node_count() {
    if ! exec_cmd ". /data/robot-host/robot-env.sh && rosnode list 2>/dev/null | grep -q \"$1\""; then
        FAIL_COUNT=$((FAIL_COUNT+1))
    fi
}

check_node_count "ros_robot_controller"
check_node_count "servo_manager"
check_node_count "chassis_controller"

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✅ 控制链路就绪，可以开始控制"
    exit 0
else
    echo "❌ $FAIL_COUNT 个关键节点未运行，请先修复"
    echo ""
    echo "修复建议："
    echo "  1. 启动机械臂: sh /data/robot-host/start-host-arm-4.1.sh"
    echo "  2. 启动底盘: sh /data/robot-host/start-host-chassis.sh"
    echo "  3. 全链路自检: sh /data/robot-host/healthcheck-all-4.1.sh"
    exit 1
fi
