# Kaihong 4.1 机械臂/夹爪只读探测与底层控制链路报告

- 生成时间：2026-08-04 18:45 左右
- 执行方式：只读探测；本轮未发送任何 position/home/offset/limit 写命令
- 读取入口：`/ros_robot_controller/bus_servo/get_state`（ROS 边界，低于 Skill，不经过 `kaihong-robot-operations`）
- 探测脚本：`/tmp/mclaw_readonly_bus_servo_probe.py`
- 注意：没有直接打开 `/dev/ttyCH343USB0`，避免与正在运行的 `ros_robot_controller_node` 争抢串口。

## 1. 底层控制链路位置

真正的串口/STM32 SDK 在：

```text
/data/robot-host/src/ros_robot_controller/src/ros_robot_controller/ros_robot_controller_sdk.py
```

关键类：`Board`

默认串口参数：

```python
device = os.environ.get("RRC_DEVICE", "/dev/ttyCH343USB0")
baudrate = int(os.environ.get("RRC_BAUDRATE", "1000000"))
```

协议格式：

```text
0xAA 0x55 Length Function ID Data Checksum
```

总线舵机功能号：

```python
PACKET_FUNC_BUS_SERVO = 5
```

与夹爪/机械臂总线舵机直接相关的底层方法：

| 功能 | 方法 | 子命令/说明 |
|---|---|---|
| 设置位置 | `bus_servo_set_position(duration, positions)` | 子命令 `0x01`；`duration` 秒转 ms；每个舵机 `(id, position_u16le)` |
| 读位置 | `bus_servo_read_position(servo_id)` | 子命令 `0x05` |
| 读角度限制 | `bus_servo_read_angle_limit(servo_id)` | 子命令 `0x32` |
| 设角度限制 | `bus_servo_set_angle_limit(servo_id, [low, high])` | 子命令 `0x30` |
| 扭矩使能 | `bus_servo_enable_torque(servo_id, enable)` | 4.1 镜像已修正：enable=1 用 `0x0C`，enable=0 用 `0x0B` |
| 读扭矩 | `bus_servo_read_torque_state(servo_id)` | 子命令 `0x0D` |
| 读写 offset / 电压温度限制 / stop | 同文件内对应方法 | 见 SDK |

ROS 驱动节点：

```text
/data/robot-host/src/ros_robot_controller/scripts/ros_robot_controller_node.py
```

暴露接口：

```text
写：/ros_robot_controller/bus_servo/set_state
读：/ros_robot_controller/bus_servo/get_state
```

host 机械臂封装：

```text
/data/robot-host/host_arm/servo_driver/src/servo_driver/servo_io.py
/data/robot-host/host_arm/servo_controllers/src/servo_controllers/joint_position_controller.py
```

说明：`ServoIO` 不是最底层串口 SDK，它通过 ROS service/topic 调用 `ros_robot_controller_node`。按 `robot-env.sh` 的 `PYTHONPATH`，host 栈优先使用 `host_arm/servo_driver/src` 这份封装。

## 2. 初始位置 / 零点结论

配置零点参考在：

```text
/data/robot-host/host_arm/servo_controllers/config/servo_controller.yaml
```

内容要点：

```yaml
joint1..joint5: servo.init = 500
r_joint / gripper ID10: servo.init = 700
```

但这个 `init` 是弧度换算零点，不是自动回零动作。启动脚本 `start-host-arm-4.1.sh` 明确执行 `hold-arm-current-position.py`：把当前实测位置写成目标后再使能保持，避免启动后召回旧目标或自动回 home。

## 3. 本次只读结果

原始返回 JSON：

```json
{
  "service": "/ros_robot_controller/bus_servo/get_state",
  "servos": {
    "1": {"enable_torque": [1], "max_temperature_limit": [85], "offset": [6], "ok": true, "position": [560], "position_limit": [0, 1000], "present_id": [1], "temperature": [34], "voltage": [11358], "voltage_limit": [4500, 14000]},
    "10": {"enable_torque": [1], "max_temperature_limit": [85], "offset": [45], "ok": true, "position": [558], "position_limit": [0, 700], "present_id": [10], "temperature": [70], "voltage": [11422], "voltage_limit": [4500, 14000]},
    "2": {"enable_torque": [1], "max_temperature_limit": [85], "offset": [-2], "ok": true, "position": [506], "position_limit": [0, 1000], "present_id": [2], "temperature": [32], "voltage": [11362], "voltage_limit": [4500, 14000]},
    "3": {"enable_torque": [1], "max_temperature_limit": [85], "offset": [-3], "ok": true, "position": [437], "position_limit": [0, 1000], "present_id": [3], "temperature": [31], "voltage": [11260], "voltage_limit": [4500, 14000]},
    "4": {"enable_torque": [1], "max_temperature_limit": [85], "offset": [-3], "ok": true, "position": [709], "position_limit": [0, 1000], "present_id": [4], "temperature": [31], "voltage": [11375], "voltage_limit": [4500, 14000]},
    "5": {"enable_torque": [0], "max_temperature_limit": [70], "offset": [14], "ok": true, "position": [481], "position_limit": [0, 1000], "present_id": [5], "temperature": [28], "voltage": [11300], "voltage_limit": [4500, 14000]}
  },
  "stamp": 1785843389.78839
}
```

汇总表：

| ID | 位置 | 硬件/固件角度限制 | offset | 扭矩 | 温度 | 电压 mV | 备注 |
|---:|---:|---|---:|---:|---:|---:|---|
| 1 | 560 | 0..1000 | 6 | 1 | 34 | 11358 | 机械臂关节 |
| 2 | 506 | 0..1000 | -2 | 1 | 32 | 11362 | 机械臂关节 |
| 3 | 437 | 0..1000 | -3 | 1 | 31 | 11260 | 历史上反馈异常，配置有 fallback/open-loop 说明 |
| 4 | 709 | 0..1000 | -3 | 1 | 31 | 11375 | 当前偏离 500 零点最大 |
| 5 | 481 | 0..1000 | 14 | 0 | 28 | 11300 | 腕旋；此前 Skill 记录其扭矩反馈不可靠/特殊 |
| 10 夹爪 | 558 | **0..700** | 45 | 1 | 70 | 11422 | 温度偏高但低于 85 上限 |

## 4. 对夹爪开合范围的修正判断

之前 Skill 软件层允许夹爪命令范围写作 `250..800`。本次底层只读显示 ID10 固件/舵机侧 `position_limit = [0, 700]`，因此应以更保守的硬件限制为准：

```text
夹爪 ID10 当前值：558
夹爪 ID10 底层限制：0..700
夹爪配置零点 init：700
Skill 软件范围：250..800，其中 800 超过底层 700，不应再使用
```

`init=700` 与 `position_limit` 上限同为 700，提示 700 可能是夹爪一侧行程端点/零点参考；当前 558 距离 700 还有约 142 脉冲，距离 0 端点更远。单次只读无法判断 0 对应张开还是闭合、700 对应闭合还是张开，也无法换算成毫米开口。

## 5. 之前小动作失败的可能解释

用户曾要求“简单开一下”，Skill 层尝试 ID10 到 580，返回：

```text
GRIPPER ORIGINAL=558 TARGET=580
GRIPPER=FAIL ACTUAL=559
```

结合本次底层只读：

- 目标 580 没有超过底层 `0..700`，所以失败不像是被固件角度限制拒绝。
- 夹爪扭矩为使能状态 `enable_torque=1`，温度 70℃，略高但未超过 `max_temperature_limit=85`。
- 更可能原因：夹爪已接近机械阻力/限位、夹持机构顶住、零点/方向未标定，或控制链路目标未实际更新。当前没有视觉/触觉反馈，不能断言具体原因。

## 6. 安全建议

1. 暂时不要对 ID10 使用超过 `700` 的值；Skill 的 `800` 上限应视为过宽。
2. 不要自动回 `500/700` 这类“初始值”；当前系统没有已验证 home 动作。
3. 若要建立开合方向映射，只能在现场确认净空后做小步进：每次 `10~30` 脉冲，观察实物方向，并记录 raw 与开合方向。
4. ID3 位置历史上按 fallback/open-loop 处理，做整机姿态判断时不要完全信任 ID3 反馈。
5. ID5 本轮只读 `enable_torque=0`，与机械臂保持状态可能不一致；若要精细动腕部，先单独只读复核，不要直接大角度命令。

## 7. 可复用命令

只读探测命令示例：

```sh
/bin/sh -c '. /data/robot-host/robot-env.sh; . /data/robot-host/host-arm-env.sh; exec python3 /tmp/mclaw_readonly_bus_servo_probe.py'
```

不要用于自动回零；当前仅用于读取。