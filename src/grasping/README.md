# grasping — 夹爪相机像素伺服抓取 pipeline

> 本文件 = 本 pipeline 的 MANIFEST（不可变根清单）。先读这个，再动代码。

## 目的（Purpose）

仅用夹爪上方的 icSpring RGB 相机（禁 Astra 深度、禁移动底盘），输入**颜色（red/yellow/green）+ 形状（cylinder）**后，
通过质心检测 + 像素伺服控制机械臂对准、下降、夹爪闭合，自动抓起对应圆柱体。

## 目标态（Goal state / 完成判据）

1. pipeline 每个步骤 `logs/<step>/STATUS.txt` 均为 PASS；
2. 端到端程序（`08_full_run.py` / `grasp.py`）输入颜色和形状后，无人工干预完成：
   对准（质心到画面中心，误差 ≤ 阈值）→ 下降到位 → 夹爪闭合夹起 → 抬离原位；
3. 交付物：本 README + `grasp.py` 主程序 + 各 gate 日志证据。

## 不变量（Invariants，任何时候不得违反）

- 只能用 `/gripper_camera/image_raw` 作为视觉输入；禁止用 Astra 深度/点云做定位。
- 禁止 `/cmd_vel`：底盘全程不动。只允许机械臂（舵机 ID 1-5）与夹爪（ID 10）。
- 舵机原始值范围 0-1000；夹爪 200-700，**绝不超过 700**。
- 单关节单步 ≤ 60 tick；单次笛卡尔微动 ≤ 20mm；下降每步 ≤ 10mm。
- J3 位置反馈是开环估计，任何运动后必须等够 duration 再读状态。
- 每个步骤独立可重跑；下一步必须检查上一步 STATUS=PASS。

## 地图（Map）

```
grasping/                      # 本地仓库目录 == 板端 /data/local/grasping/（同名，双向同步）
├── README.md                  # 本文件（MANIFEST）
├── grasp.py                   # ★ 交付主程序：复位→扫描→J1对准→底盘逼近→闭合→抬升验证
├── 像素伺服抓取说明文档.md      # ★ 原理与使用文档
├── arm                        # ★ 关节调试 CLI：./arm 2 300 / ./arm 查状态
├── car                        # ★ 底盘移动 CLI：./car forward 0.1 / turn 30
├── joint_set.py / car_move.py # arm / car 的实现
├── start_camera.sh            # 相机启动（按名字解析设备号，掉线自愈）
├── run_step.sh                # 运行环境包装（robot-env + LD_PRELOAD）
├── util_gate.py               # gate/日志/timing/STATUS 框架
├── util_board.py              # ROS 硬件接口 + 安全护栏（取帧/检测/J1伺服/底盘/夹爪）
├── 01_camera_ready.py ~ 04_jog_probe.py   # 分步 gate 验证（相机/检测/臂状态/标定）
├── 05_align.py ~ 07_grasp.py              # 早期笛卡尔伺服方案步骤（已被 grasp.py 取代，留档）
├── servo_direction_probe.py   # 舵机方向实证探针
├── sync.sh                    # 本地 → 板端同步（scp）
└── logs/<step>/{step.log,timing.json,STATUS.txt,*.jpg}
```

## 运行方式

板端执行（SSH）：

```bash
ssh -p 2223 root@<板子IP>
cd /data/local/grasping
sh run_step.sh grasp.py --color red --shape cylinder   # 端到端抓取
./arm    # 查关节状态；./car forward 0.1   # 底盘前进 10cm
```

前置：`gripper_camera_node` 已启动（`/gripper_camera/image_raw` 在发布）；机械臂栈已启动（`start-host-arm-4.1.sh`）。
