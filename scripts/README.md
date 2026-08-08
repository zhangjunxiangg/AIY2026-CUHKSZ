# 机器人控制前必须运行的脚本

> 用途：每次控制机器人前，按顺序执行以下检查，确保链路就绪。  
> 位置：`scripts/`  
> 更新：2026-08-09

---

## 本目录脚本一览

| 脚本 | 用途 |
|---|---|
| `check-control-ready.sh` | 控制前快速检查（30 秒，见下） |
| `healthcheck.sh` | 全链路健康检查（2 分钟，见下） |
| `sshd-foreground.sh` + `sshd.cfg` | 板端 SSH 服务前台启动与配置（开机自启双端口 22+2223 用） |

> 注：队长的个人工具脚本（会话存档提取、卡片 docx 转换等）属私人内容，已移出版本控制，不在本目录的仓库版本中。

---

## 1. 快速检查（30 秒）

```bash
bash scripts/check-control-ready.sh
```

**检查内容**：
- SSH/HDC 连接状态
- STM32 串口 `/dev/ttyCH343USB0`
- ROS 关键节点（`ros_robot_controller`、`servo_manager`、`chassis_controller`）
- 舵机命令/状态话题
- 底盘控制话题
- WiFi/SSH 服务

**通过标准**：全部 PASS，最后输出 `✅ 控制链路就绪，可以开始控制`

---

## 2. 全链路健康检查（2 分钟）

```bash
bash scripts/healthcheck.sh
```

**检查内容**（在快速检查基础上增加）：
- 传感器数据流（IMU、电池、里程计、雷达、舵机、机械臂、夹爪）
- 相机/视觉容器状态
- 硬件设备文件（ttyUSB、video）
- M-Claw / AI 运行时
- 存储空间

**通过标准**：全部 PASS

---

## 3. 板端自启检查（可选）

如果刚重启板子或怀疑服务未启动，在板端执行：

```bash
# 板端执行
sh /data/robot-host/healthcheck-all-4.1.sh
```

**检查内容**：
- IMU、电池、里程计
- 雷达、相机、点云
- 机械臂舵机状态
- 运动学服务
- M-Claw 运行时

---

## 4. 常见问题修复

| 问题 | 修复命令 |
|---|---|
| `servo_manager` 未运行 | `sh /data/robot-host/start-host-arm-4.1.sh` |
| 底盘不动 | `sh /data/robot-host/start-host-chassis.sh` |
| 相机无数据 | `sh /data/robot-host/start-vision-4.1.sh` |
| 雷达无数据 | `sh /data/robot-host/start-lidar-4.1.sh` |
| 全部重启 | `sh /data/robot-host/stop-all-4.1.sh && sh /data/robot-host/start-all-4.1.sh` |

---

## 5. 控制方式速查

### 夹爪控制（Raw Topic）

```python
import rospy
from servo_msgs.msg import RawIdPosDur

pub = rospy.Publisher('/servo_controllers/port_id_1/id_pos_dur', RawIdPosDur, queue_size=1)
pub.publish(RawIdPosDur(id=10, position=300, duration=2.0))  # 300=打开, 600+=关闭
```

### 底盘控制

```python
import rospy
from geometry_msgs.msg import Twist

pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
msg = Twist()
msg.linear.x = 0.1   # 前进 0.1 m/s
msg.angular.z = 0.0
pub.publish(msg)
```

### 机械臂单关节

```python
import rospy
from servo_msgs.msg import RawIdPosDur

pub = rospy.Publisher('/servo_controllers/port_id_1/id_pos_dur', RawIdPosDur, queue_size=1)
pub.publish(RawIdPosDur(id=3, position=500, duration=1.0))  # ID3 到 500
```

---

## 6. 安全提醒

1. **控制前必跑检查**：不要跳过 `check-control-ready.sh`。
2. **夹爪范围**：软件建议 250-700，实测 200-700 可用，**不要超过 700**。
3. **底盘超时**：`cmd_vel` 超过 0.5s 无更新会自动停车，演示时要持续发指令。
4. **舵机温度**：长时间运行注意夹爪温度（>70°C 需停机冷却）。
5. **紧急停止**：底盘发送零速 `Twist()`，机械臂释放扭矩 `enable_torque=0`。

---

*维护：每次新增控制脚本或发现新的前置条件时更新本文档。*
