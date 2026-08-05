# 夹爪 CLI 控制手册

> 验证环境：KaihongBoard-3588S + M-Robots OS 4.1（2026-08-05 实测）  
> 夹爪硬件：总线舵机 **ID 10**，挂在舵机串口 `port_id_1`

---

## 0. 关键参数（先记住这些）

| 项 | 值 | 说明 |
|---|---|---|
| 舵机 ID | 10 | `servo_controller.yaml` 中 `r_joint_controller` |
| 原始值范围（软件） | 0 – 1000 | 反向映射（`min: 1000 / max: 0`） |
| **实测安全范围** | **200 – 700** | **不要超过 700**，会顶死/过流 |
| 参考姿态 | 300 ≈ 张开，600+ ≈ 闭合 | 中位 init = 700 |
| 状态反馈 | `/servo_controllers/port_id_1/servo_states` | id 10 条目，真实反馈（非开环） |

**前置条件**：机械臂栈已启动（`servo_manager` 运行中）。检查：

```bash
ssh -p 2223 root@<板子IP> "sh /data/robot-host/start-host-arm-4.1.sh"
```

以下所有命令都通过 SSH 在板端执行（HDC 下把 `ssh ...` 换成 `hdc shell` 亦可）：

```bash
SSH="ssh -p 2223 -i ~/.ssh/id_ed25519 root@172.20.10.5"
```

---

## 1. 方法一：CLI 一行命令（Raw 话题，最直接）

向 `/servo_controllers/port_id_1/id_pos_dur` 发一条 `servo_msgs/RawIdPosDur`：

```bash
$SSH ". /data/robot-host/robot-env.sh && \
  rostopic pub -1 /servo_controllers/port_id_1/id_pos_dur servo_msgs/RawIdPosDur \
  '{id: 10, position: 300, duration: 2.0}'"
```

- `position`：目标原始值（200–700）
- `duration`：运动时长（秒），建议 ≥ 1.0，夹取易碎物放慢到 2–3s

**注意**：Raw 话题**不经过软件限位**，目标值必须自己守住 200–700。

验证到位：

```bash
$SSH ". /data/robot-host/robot-env.sh && \
  timeout 5 rostopic echo -n 1 /servo_controllers/port_id_1/servo_states | grep -A6 'id: 10'"
```

`position` 接近 `goal`、`error` 绝对值 ≤ 5 即到位。

---

## 2. 方法二：Python 脚本（rospy Publisher）

适合写进自己的节点/状态机。在板端用 `run` 包装器或 source 环境后执行：

```python
#!/usr/bin/env python3
"""gripper_set.py — 设置夹爪开合
用法: run python3 gripper_set.py <position> [duration]
示例: run python3 gripper_set.py 300 2.0   # 张开
      run python3 gripper_set.py 650 2.0   # 闭合夹取
"""
import sys
import rospy
from servo_msgs.msg import RawIdPosDur

GRIPPER_ID = 10
MIN_POS, MAX_POS = 200, 700  # 实测安全范围，勿超 700

def main():
    position = int(sys.argv[1])
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    if not (MIN_POS <= position <= MAX_POS):
        sys.exit(f"position 必须在 {MIN_POS}-{MAX_POS} 之间")

    rospy.init_node("gripper_set", anonymous=True)
    pub = rospy.Publisher("/servo_controllers/port_id_1/id_pos_dur",
                          RawIdPosDur, queue_size=1)
    rospy.sleep(0.5)  # 等 publisher 建连
    pub.publish(RawIdPosDur(id=GRIPPER_ID, position=position, duration=duration))
    rospy.sleep(0.2)
    print(f"gripper -> {position} (duration {duration}s)")

if __name__ == "__main__":
    main()
```

板端运行（`servo_msgs` 是自定义消息，**必须**走 `run` 或先 source `robot-env.sh`，否则报 `Cannot load message class`）：

```bash
$SSH "cd /data/local/robot && run python3 gripper_set.py 300 2.0"
```

---

## 3. 方法三：FollowJointTrajectory Action（轨迹接口）

需要与 MoveIt/轨迹规划链路对接时用，关节名 `r_joint`：

```bash
$SSH ". /data/robot-host/robot-env.sh && \
  rostopic pub -1 /gripper_controller/follow_joint_trajectory/goal \
  control_msgs/FollowJointTrajectoryActionGoal \
  '{goal: {trajectory: {joint_names: [r_joint], points: [{positions: [0.5], time_from_start: {secs: 2}}]}}}'"
```

`positions` 是弧度（相对 init=700 的反向映射，1 tick = 0.24°）。日常手动控制建议直接用方法一/二，Action 接口主要给规划器用。

---

## 4. 方法四：M-Claw 高层命令（`robot_ops.py`）

走 M-Claw 智能体链路，JSON 命令：

```json
{"command": "gripper-set", "params": {"position": 0.5, "duration": 1.0}}
```

适合语音/Agent 场景；调试硬件时建议先用方法一确认底层正常。

---

## 5. 状态查询与故障处理

读夹爪状态：

```bash
$SSH ". /data/robot-host/robot-env.sh && \
  timeout 5 rostopic echo -n 1 /servo_controllers/port_id_1/servo_states | grep -A6 'id: 10'"
```

返回字段：`goal`（目标）、`position`（当前）、`error`（偏差）、`voltage`（正常约 9000mV）。

| 现象 | 处理 |
|---|---|
| `servo_states` 整个无数据 | 机械臂栈没起：`sh /data/robot-host/start-host-arm-4.1.sh` |
| 报 `Cannot load message class [servo_msgs/...]` | 没 source 环境，用 `run python3` 或 `. /data/robot-host/robot-env.sh` |
| 夹爪卡住/过流发热 | 立即停止发令，释放扭矩；长时间运行温度 >70°C 需停机冷却 |
| 需要紧急停止 | 停止发新命令；如需释放，将扭矩使能置 0（`enable_torque=0`） |

---

## 6. 安全清单

1. 目标值永远限制在 **200–700**，超 700 会机械顶死。
2. Raw 话题无软件限位，脚本里自己加范围检查（方法二的脚本已内置）。
3. 夹取动作 duration ≥ 2s，到位后读 `servo_states` 确认再进下一步。
4. 改动控制代码前先跑 `bash scripts/check-control-ready.sh` 确认链路就绪。

---

*维护：实测范围或接口变化时更新本文档。*
