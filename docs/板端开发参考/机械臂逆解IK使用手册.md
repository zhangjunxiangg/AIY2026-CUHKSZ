# 机械臂逆解（IK）使用手册

> 验证环境：KaihongBoard-3588S + M-Robots OS 4.1（2026-08-05 实测）  
> 板端位置：`/data/robot-host/host_arm/kinematics/`（本地副本 `vendor/kaihong-src/kaihong_adapter/robot-runtime/host_arm/kinematics/`）  
> 说明：板端**没有本机 URDF**，官方提供的是纯 Python 解析 IK（Hiwonder 5-DOF），无需 URDF 即可用

---

## 1. 内置模型参数

`src/kinematics/inverse_kinematics.py` 中硬编码：

```python
_links = [0.23, 0.13, 0.13, 0.055, 0.117]   # 连杆长度（米）
_joint_range_deg = [
    [-120.2, 120.2],    # J1 基座旋转
    [-180.2,   0.2],    # J2 肩
    [-120.2, 120.2],    # J3 肘
    [-200.2,  20.2],    # J4 腕
    [-120.2, 120.2],    # J5 腕旋转
]
```

最大臂展约 0.35 m（0.13+0.13+0.055+0.117，不含基座高度 0.23 m）。坐标系：基座原点，X 前、Y 左、Z 上（米）。

---

## 2. 快速验证（CLI，只查询不动臂）

```bash
ssh -p 2223 root@<板子IP> "sh /data/robot-host/run-check-target-ik-4.1.sh <X> <Y> <Z>"
```

给定目标点，扫描 -90°~90° 末端俯仰角，输出每个可行解的 5 路舵机脉冲值、当前脉冲和增量。

**2026-08-05 实测**（目标 `0.15 0.0 0.10`）：

```text
IK pitch=85 pulses=[500, 434, 24, 313, 500] current=[474, 193, 296, 457, 483] deltas=[26, 241, -272, -144, 17]
IK pitch=90 pulses=[500, 412, 57, 281, 500] current=[474, 193, 296, 457, 483] deltas=[26, 219, -239, -176, 17]
IK_SOLUTION_COUNT=2
```

解读：该目标点有 2 个可行解（pitch 85°/90°）；`deltas` 告诉你要动多少——上例中 J2/J3 需要大幅运动（241/-272 tick ≈ 58°/65°），说明该点对当前姿态是个"大动作"，执行前要确认路径无障碍。

---

## 3. ROS 服务接口（`/kinematics` 节点，常驻运行）

节点：`/kinematics`（由 `start-host-arm-4.1.sh` 拉起，`scripts/search_kinematics_solutions_node.py`）

### 3.1 位姿目标求解：`/kinematics/set_pose_target`

`srv/interfaces/SetRobotPose.srv`：

```text
# Request
float64[] position      # [x, y, z] 目标位置（米）
float64 pitch           # 末端俯仰角（度）
float64[] pitch_range   # 俯仰角搜索范围 [min, max]
float64 resolution      # 搜索步长（度）
---
# Response
bool success
float64[] pulse         # 5 路舵机脉冲解（J1-J5）
uint16[] current_pulse  # 当前 5 路脉冲（来自 servo_states）
float64[] rpy
float64 min_variation   # 与当前姿态的最小变化量（选解参考）
```

Python 调用示例（板端 `run python3` 执行）：

```python
import rospy
from interfaces.srv import SetRobotPose

rospy.init_node("ik_client", anonymous=True)
rospy.wait_for_service("/kinematics/set_pose_target", timeout=5.0)
solve = rospy.ServiceProxy("/kinematics/set_pose_target", SetRobotPose)

result = solve([0.15, 0.0, 0.10], 90.0, [-90.0, 90.0], 1.0)
if result.success:
    pulses = [int(round(v)) for v in result.pulse]
    print("解（脉冲）:", pulses)
```

CLI 查询：

```bash
ssh -p 2223 root@<板子IP> ". /data/robot-host/robot-env.sh && \
  rosservice call /kinematics/set_pose_target '{position: [0.15, 0.0, 0.10], pitch: 90.0, pitch_range: [-90, 90], resolution: 1.0}'"
```

### 3.2 其他服务

| 服务 | 作用 |
|---|---|
| `/kinematics/get_current_pose` | 由当前舵机脉冲 FK 出末端位姿 |
| `/kinematics/set_joint_value_target` | 直接以关节角求解/校验 |
| `/kinematics/get_link` / `set_link` | 查询/修改连杆长度参数 |
| `/kinematics/get_joint_range` / `set_joint_range` | 查询/修改关节范围 |

---

## 4. 纯 Python 库用法（不依赖 ROS 服务）

`inverse_kinematics.py` 可独立 import（纯 math，无 rospy 依赖）：

```python
from kinematics import inverse_kinematics as ik

# 指定位置 + 俯仰角求解，返回所有可行解（关节角，度）
solutions = ik.get_ik([0.15, 0.0, 0.10], pitch=90, pitch_range=(-180, 180), resolution=1.0)

# 指定位姿（rpy）求解
solution = ik.get_position_ik(x=0.15, y=0.0, z=0.10, roll=0, pitch=90, yaw=0)

# 查看/修改模型参数
print(ik.get_link())
print(ik.get_joint_range(unit="deg"))
```

正解在 `forward_kinematics.py`，坐标变换工具在 `transform.py`。

---

## 5. 从解到执行

IK 返回的是**舵机脉冲值**（与 `servo_states` 的 position 同一量纲，500 = 中位，1 tick = 0.24°，反向映射）。执行方式：

- **整臂联动（推荐）**：向 `/arm_controller/follow_joint_trajectory` 发轨迹（关节角需自行由脉冲换算）
- **逐关节 Raw 话题**：向 `/servo_controllers/port_id_1/id_pos_dur` 逐个发 `{id: N, position: pulse, duration: t}`，详见《夹爪CLI控制手册》同套接口
- **选解原则**：用 `min_variation` / `deltas` 选离当前姿态最近的解，避免大角度扫掠

---

## 6. 手眼标定（相机 → 机械臂）

视觉抓取链路的坐标变换已标定：

- 标定文件：`vendor/kaihong-src/kaihong_adapter/robot-runtime/robot-runtime/astra-arm-calibration/astra-to-base.json`（Astra 相机 → 机械臂基座）
- 典型链路：相机识别目标点 → `astra-to-base` 变换到基座坐标系 → `/kinematics/set_pose_target` 求解 → 脉冲下发执行

---

## 7. 注意事项

1. **J3 位置反馈是开环估计**（硬件返回 0xffff），IK 节点读到的"当前脉冲"里 J3 是最后命令值，大动作后先等 duration 结束再求解。
2. 脉冲值方向为**反向映射**（值增大 ≠ 关节角增大），不要凭直觉手改脉冲。
3. `set_pose_target` 只做求解，**不会驱动机械臂**；执行需另行下发，下发前用 `deltas` 评估动作幅度。
4. 解不存在时 `success=false` 或 `IK_SOLUTION_COUNT=0`——先检查目标是否在臂展内（约 0.35 m）、pitch_range 是否给得太窄。
5. 软件关节范围 ≠ 机械安全区，新目标点第一次执行务必低速、有人在场急停。

---

*维护：IK 参数（连杆/范围）修改或服务接口变化时更新本文档。*
