#!/bin/sh
# bringup.sh — 板端全栈拉起（重启后一键恢复）
#
# 原则：各步骤直接输出官方脚本的原始 stdout/stderr，不包装不隐藏错误。
# 幂等：已在运行的服务跳过；任何一步失败即以该脚本的原始退出码退出。
#
# 用法：ssh 上板后  sh /data/local/grasping/bringup.sh
set -u

R=/data/robot-host
G=/data/local/grasping
say() { echo "[bringup] $*"; }

# 0. ROS master：没起就先拉底盘核心（roscore 在里面）
if ! (. $R/robot-env.sh >/dev/null 2>&1 && rostopic list >/dev/null 2>&1); then
    say "=== 1/5 底盘核心（roscore/STM32/底盘控制）==="
    sh $R/start-host-chassis.sh
fi

# 等 master 就绪（竞态防护：官方 autostart 就是死在这）
i=0
until . $R/robot-env.sh >/dev/null 2>&1 && rostopic list >/dev/null 2>&1; do
    i=$((i+1)); [ $i -gt 30 ] && { say "ERROR: ROS master 30s 未就绪"; exit 1; }
    sleep 1
done
say "ROS master OK"

# 1. 雷达
if ps -ef | grep -v grep | grep -q rplidar_raw_node; then
    say "=== 2/5 雷达：已在运行，跳过 ==="
else
    say "=== 2/5 雷达 ==="
    sh $R/start-lidar-4.1.sh
fi

# 2. 视觉容器（Astra）
if docker ps 2>/dev/null | grep -q rk3588s-vision; then
    say "=== 3/5 视觉容器：已在运行，跳过 ==="
else
    say "=== 3/5 视觉容器（Astra）==="
    sh $R/start-vision-4.1.sh
fi

# 3. 臂栈（hold 检查首试常因 J2 下垂失败，重读位姿后可过；最多 3 次）
if ps -ef | grep -v grep | grep -q controller_manager; then
    say "=== 4/5 臂栈：已在运行，跳过 ==="
else
    say "=== 4/5 臂栈 ==="
    ok=0
    for i in 1 2 3; do
        sh $R/start-host-arm-4.1.sh && { ok=1; break; }
        say "臂栈第 $i 次启动失败（原始报错见上），1s 后重试"
        sleep 1
    done
    [ $ok -eq 1 ] || { say "ERROR: 臂栈 3 次启动均失败"; exit 1; }
fi

# 4. 夹爪相机
say "=== 5/5 夹爪相机 ==="
sh $G/start_camera.sh

# 5. 状态汇总（/cmd_vel 查订阅者，其余查数据流）
say "======== 状态汇总 ========"
. $R/robot-env.sh >/dev/null 2>&1
fail=0
if rostopic info /cmd_vel 2>/dev/null | grep -q "Subscribers: None"; then
    say "FAIL  /cmd_vel（无订阅者）"; fail=1
else
    say "PASS  /cmd_vel（底盘控制器订阅中）"
fi
for t in /scan /odom /ros_robot_controller/imu_raw \
         /servo_controllers/port_id_1/servo_states \
         /astra_camera/rgb/image_raw /gripper_camera/image_raw; do
    if timeout 4 rostopic echo -n 1 $t >/dev/null 2>&1; then
        say "PASS  $t"
    else
        say "FAIL  $t（无数据）"; fail=1
    fi
done
say "======== 完成（fail=$fail）========"
exit $fail
