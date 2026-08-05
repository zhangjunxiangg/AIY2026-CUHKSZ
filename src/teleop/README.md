# teleop — 键盘遥操作（MANIFEST）

## 目的

HDC/SSH 终端里直接运行，用键盘实时控制机器人：
- **方向键**：前/后/左/右 平移（麦轮）
- **A / D**：左转 / 右转（原地旋转）
- **S / X**：Joint 2 抬升 / 下降（只动 J2，每按一次 10 tick ≈ 2.4°，软限位 100-400）
- **J / L**：夹爪 闭合 / 张开（每按一次 25 tick，硬钳制 200-700）
- **W**：拍摄夹爪相机 + Astra 相机各一张，按时间戳存 `captures/`
- **Q 或 ESC**：退出（自动停车）

臂/夹爪控制复用 `../grasping/util_board.py` 的安全护栏（跳变 ≤120 tick、速度 ≤60 tick/s、
范围钳制），方向约定写在 `teleop.py` 顶部常量区，反了改那里。

## 目标态（完成判据）

1. `logs/01_env_check/STATUS.txt` = PASS（termios 可用、ROS 话题在线、两相机出图存盘、
   舵机 1-5+10 全部在线）；
2. 终端运行 `./teleop` 后：按键车动、松手即停（0.3s 无输入自动刹车）、S/X 只动 J2、
   J/L 只动夹爪、W 出双图、Q 退出。

## 不变量

- 线速度 ≤ 0.10 m/s，角速度 ≤ 0.4 rad/s。
- 无键盘输入超过 0.3s 必须停车（deadman）。
- 退出（含异常）必须发零速 Twist。
- J2 软限位 100-400 tick；夹爪硬钳制 200-700 tick；任何臂控指令走 util_board 护栏。
- 照片只增不删，文件名带时间戳。

## 运行

```bash
# 板端（hdc shell 或 ssh 进入后）
cd /data/local/teleop
./teleop
```

## 地图

```
teleop/                          # 本地仓库 == 板端 /data/local/teleop/
├── README.md                    # 本文件（MANIFEST）
├── teleop                       # ★ 启动入口（./teleop）
├── teleop.py                    # 主程序（键盘循环 + cmd_vel + 拍照）
├── 01_env_check.py              # 环境 gate（termios/话题/相机/存盘）
├── run.sh                       # 运行环境包装（robot-env + LD_PRELOAD）
├── captures/                    # 照片输出（YYYYMMDD_HHMMSS_{gripper,astra}.jpg）
└── logs/01_env_check/           # gate 证据
```
