@echo off
REM ============================================
REM M-Robots 机器人全链路健康检查（Windows 一键运行）
REM 用法: healthcheck.bat [connect-key]
REM 默认 connect-key: ec29004133314d38433031a523403c00
REM ============================================

setlocal EnableDelayedExpansion
set TARGET=%1
if "%TARGET%"=="" set TARGET=ec29004133314d38433031a523403c00
set HDC=hdc -t %TARGET%

echo ==========================================
echo M-Robots 机器人健康检查
echo Target: %TARGET%
echo Time: %date% %time%
echo ==========================================
echo.

REM ---------- 0. HDC 连接检查 ----------
echo [0] HDC 连接检查
%HDC% shell "echo HDC_OK" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] HDC 无法连接板子
    goto :end
)
echo [PASS] HDC 连接正常
echo.

REM ---------- 1. 系统基础 ----------
echo [1] 系统基础
%HDC% shell "uname -a"
%HDC% shell "uptime"
echo.

REM ---------- 2. ROS 核心 ----------
echo [2] ROS 核心节点
for /f "delims=" %%i in ('%HDC% shell "run rosnode list 2>/dev/null"') do (
    echo   %%i
)
echo.

REM ---------- 3. 传感器数据检查 ----------
echo [3] 传感器数据流检查

call :check_topic "/ros_robot_controller/imu_raw" "IMU"
call :check_topic "/ros_robot_controller/battery" "电池"
call :check_topic "/odom" "里程计"
call :check_topic "/scan" "激光雷达"
call :check_topic "/servo_controllers/port_id_1/servo_states" "舵机状态"
call :check_topic "/arm_controller/state" "机械臂状态"
call :check_topic "/gripper_controller/state" "夹爪状态"

echo.

REM ---------- 4. 相机/视觉检查 ----------
echo [4] 相机/视觉检查
%HDC% shell "run rostopic list 2>/dev/null | grep -i astra" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Astra 相机话题未发布
    echo        可能原因: rk3588s-vision Docker 容器未启动
    echo        修复: 板端执行 /data/robot-host/start-vision-4.1.sh
) else (
    echo [PASS] Astra 相机话题已发布
)
%HDC% shell "docker ps 2>/dev/null | grep rk3588s-vision" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] rk3588s-vision 容器未运行
) else (
    echo [PASS] rk3588s-vision 容器运行中
)
echo.

REM ---------- 5. 控制链路检查 ----------
echo [5] 控制链路检查
%HDC% shell "run rostopic info /cmd_vel 2>/dev/null | grep -i publisher" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] /cmd_vel 无发布者
) else (
    echo [PASS] /cmd_vel 控制链路正常
)
%HDC% shell "run rosnode list 2>/dev/null | grep chassis_controller" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] chassis_controller 节点未运行
) else (
    echo [PASS] chassis_controller 节点运行中
)
echo.

REM ---------- 6. 硬件设备文件 ----------
echo [6] 硬件设备文件
%HDC% shell "ls /dev/ttyUSB* 2>/dev/null || echo '无 ttyUSB 设备'"
%HDC% shell "ls /dev/video* 2>/dev/null | head -5 || echo '无 video 设备'"
echo.

REM ---------- 7. M-Claw / AI 运行时 ----------
echo [7] M-Claw / AI 运行时
%HDC% shell "which mclaw" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] mclaw 未安装
) else (
    echo [PASS] mclaw 已安装
)
%HDC% shell "ls /data/local/tmp/.mclaw/skills 2>/dev/null" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] M-Claw skills 目录不存在
) else (
    echo [PASS] M-Claw skills 目录存在
)
echo.

REM ---------- 8. 网络与 SSH ----------
echo [8] 网络与 SSH
%HDC% shell "ifconfig | grep -E 'inet addr|inet ' | head -3"
%HDC% shell "ps | grep sshd | grep -v grep" >nul 2>&1
if errorlevel 1 (
    echo [WARN] SSH 服务未运行
) else (
    echo [PASS] SSH 服务运行中
)
echo.

REM ---------- 9. 存储空间 ----------
echo [9] 存储空间
%HDC% shell "df -h /data | tail -1"
echo.

REM ---------- 10. 总结 ----------
echo ==========================================
echo 检查完成
echo ==========================================
goto :end

REM ---------- 函数: 检查话题 ----------
:check_topic
set topic=%~1
set label=%~2
%HDC% shell "timeout 3 run rostopic echo -n 1 %topic% >/dev/null 2>&1"
if errorlevel 1 (
    echo [FAIL] %label% (%topic%) - 无数据
) else (
    echo [PASS] %label% (%topic%)
)
exit /b 0

:end
endlocal
