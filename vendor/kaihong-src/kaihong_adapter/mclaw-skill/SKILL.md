---
name: kaihong-robot-operations
description: 统一检查和操作 Kaihong 4.1 小车。用于底盘前进、后退、横移、转向、停车和状态，机械臂与夹爪，雷达与 Astra RGB-D，连接、检查、拍摄和查看 Gemini 335 辅助相机最新照片，整机健康、ROS 比赛接口、辅助目标 relay，以及颜色分类、颜色分拣、color sorting、colorsorting Demo。
---

# Kaihong 4.1 Robot Operations

整机、机械臂和传感器使用统一 JSON 命令入口：

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" <command> [options]
```

4.1 默认架构是宿主 ROS：底盘、雷达、机械臂和运动学在板端宿主运行；仅 Astra
RGB-D 位于 `rk3588s-vision` Docker。不要直接访问串口、执行任意 `docker exec`，也
不要调用 `/ros_robot_controller/set_motor`。

## 安全规则

- 状态、舵机反馈、相机、雷达、接口和颜色分类是只读操作，可直接执行。
- 仅在用户当前会话明确要求真实运动时移动底盘、机械臂或夹爪。
- 底盘运动必须具备方向、速度和时长；缺少时询问，不推测默认值。先运行
  `chassis-status`，再执行一个有界命令；失败或用户要求停止时运行 `chassis-stop`。
- 底盘硬限制：平面线速度不超过 `0.20 m/s`，角速度不超过 `0.50 rad/s`，时长
  `0.1..10 s`。
- 调整机械臂前运行 `arm-read`，每次只修改一个 ID。ID1..5 使用 `arm-set-one`；
  ID10 仅使用 `gripper-set`。变化超过 120 脉冲需确认净空并加
  `--allow-large-delta`，超过 250 脉冲拒绝。
- ID5 是腕部旋转，ID10 是夹爪；只有用户明确要求且周围安全时才调整。
- 颜色分类仅做感知和分拣建议，不自动移动底盘、机械臂或夹爪，不把相机坐标当作
  `base_link` 抓取坐标。
- 相机和颜色分类覆盖固定 `latest` 输出，不创建时间戳归档。
- M-Claw 只运行在小车上，辅助板没有 M-Claw。连接、检查或拍摄 Gemini 335 时，
  必须让用户提供辅助板当前 IPv4；未提供时先询问，不猜测、不扫描网络、不沿用旧 IP。
- 若 `/cmd_vel` 和四路轮速均正常但轮子不转，先检查电机供电；经用户授权后运行
  `stop-all-4.1.sh`、`start-all-4.1.sh` 恢复控制链。不要重新发送或轮询
  `motor_type`，该操作会使本机4.1控制板保留遥测却停止电机输出。

## 整机与比赛接口

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" health
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" status
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" interfaces
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-start
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-status
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-stop
```

## 底盘

底盘必须直接运行同一 Skill 内捆绑的低层 ROS 发布器，不经过 `robot_ops.py`
中转。这与合并前已经实车验证的调用路径一致：

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/ros_cmd_vel.py" status
/bin/run python3 "{{SKILL_DIR}}/scripts/ros_cmd_vel.py" publish \
  --linear-x <m/s> --linear-y <m/s> --angular-z <rad/s> --duration <seconds>
/bin/run python3 "{{SKILL_DIR}}/scripts/ros_cmd_vel.py" stop
```

方向映射：前进 `linear-x > 0`，后退 `< 0`，左移 `linear-y > 0`，右移 `< 0`，
左转 `angular-z > 0`，右转 `< 0`。动作后报告实际发送值和时长。

## 机械臂与夹爪

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" arm-read
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" arm-set-one \
  --servo-id <1..5> --position <0..1000>
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" gripper-set \
  --position <250..800>
```

## Astra、雷达与颜色分类

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" camera-capture
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" lidar-status
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" lidar-scan
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" color-sorting
```

颜色分类默认简要返回检测数量及每项颜色、置信度和建议收纳区。仅在异常或用户要求
详情时展开深度质量、坐标和输出路径。不得替换为旧的
`/data/robot-host/run-scene-detect-4.1.sh`。

相机输出位于 `/data/local/tmp/.mclaw/output/robot/`；颜色分类输出位于
`/data/robot-host/student/output/color-sorting/`。只报告真实返回字段，不补全缺失
的雷达、深度或舵机数据。

## Gemini 335 辅助相机

这些命令只在小车上运行。`<辅助板IPv4>` 必须由用户本次明确提供：

```sh
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-camera-connect \
  --aux-ip <辅助板IPv4>
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-camera-status \
  --aux-ip <辅助板IPv4>
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-camera-capture \
  --aux-ip <辅助板IPv4>
/bin/run python3 "{{SKILL_DIR}}/scripts/robot_ops.py" aux-camera-view
```

`connect` 确认彩色、深度发布节点来自用户提供的辅助板 IP，然后接收真实 RGB-D；
`status` 只核对发布源；`capture` 核对发布源并覆盖最新快照。如果话题不存在，提示用户
先在辅助板终端用小车当前 IP 执行 `configure-car-ros.sh`、`start-gemini335.sh` 和
`status-gemini335.sh`。不要声称小车 M-Claw 可以执行辅助板本地命令。

用户要求“查看最新照片”时运行 `aux-camera-view`，简要返回 `color_url` 作为可在同一
局域网电脑浏览器打开的地址。只共享四个固定 `latest` 文件，不提供目录列表；服务默认
10 分钟后自动停止。按需报告深度和元数据地址。

快照固定覆盖：

```text
/data/robot-host/student/output/aux-camera-latest-color.jpg
/data/robot-host/student/output/aux-camera-latest-depth.png
/data/robot-host/student/output/aux-camera-latest-depth-preview.pgm
/data/robot-host/student/output/aux-camera-latest.json
```
