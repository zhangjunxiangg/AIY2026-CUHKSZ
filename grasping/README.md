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
├── util_gate.py               # gate/日志/timing/STATUS 框架
├── util_board.py              # ROS 硬件接口（取帧/检测/臂状态/IK/微动/夹爪）
├── 01_camera_ready.py         # 相机就绪：曝光收敛 + 帧有效性
├── 02_detect_centroid.py      # 三色质心检测 + 证据图
├── 03_arm_state.py            # 舵机状态 + FK 当前位姿
├── 04_jog_probe.py            # 单步微动 → 像素响应方向/比例标定
├── 05_align.py                # 像素伺服对准（不降 Z）
├── 06_descend.py              # 对准保持 + 分段下降到位
├── 07_grasp.py                # 夹取 + 抬升验证
├── 08_full_run.py             # 端到端：输入颜色+形状 → 抓起
├── grasp.py                   # 交付主程序（08 的产品化封装）
├── sync.sh                    # 本地 → 板端同步（scp）
└── logs/<step>/{step.log,timing.json,STATUS.txt,*.jpg}
```

## 运行方式

板端执行（SSH）：

```bash
ssh -p 2223 root@<板子IP>
cd /data/local/grasping
run python3 01_camera_ready.py   # 依次执行，下一步前确认上一步 PASS
```

前置：`gripper_camera_node` 已启动（`/gripper_camera/image_raw` 在发布）；机械臂栈已启动（`start-host-arm-4.1.sh`）。
