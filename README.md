# AIY 2026 · 深开鸿 M-Robots 赛道

> 队伍：CUHKSZ 代表队（5 人）  
> 比赛时间：2026-08-04 至 2026-08-06  
> 仓库用途：作品代码 + 赛前准备文档 + 现场调试记录

## 仓库结构

```
├── docs/              # 团队材料与官方文档转录（唯一文档源）
│   ├── 官方材料/      # 赛方原始材料转录
│   ├── 板端开发参考/   # 板端数据结构、踩坑、HDC排查、传感器规格
│   ├── 选题方向与场景策略研究.md
│   ├── 0802会议材料-系统分层与场景定义.md
│   ├── 项目启动全员必备知识文档.md
│   └── ...
├── prep/              # 赛前准备交付物（环境、工具包、选题、演练记录）
│   ├── 环境验证.md
│   ├── 工具使用简介.md
│   ├── 安装包清单.md
│   └── ...
├── papers/            # 参考论文与阅读笔记（不入库大文件）
└── _audit-cache/      # 调研审计缓存
```

## 快速入口

- [比赛认知与评分策略](docs/AIY比赛认知.md)
- [系统分层与场景定义](docs/0802会议材料-系统分层与场景定义.md)
- [板端开发速查与踩坑手册](docs/板端开发参考/板端开发速查与踩坑手册.md)
- [传感器数据规格手册](docs/板端开发参考/传感器数据规格手册.md)
- [M-Robots 开发踩坑与参考库](docs/板端开发参考/M-Robots开发踩坑与参考库.md)
- [HDC 连接中断排查记录](docs/板端开发参考/HDC连接中断排查记录.md)
- [机器人健康检查脚本](scripts/healthcheck.sh)

## 技术栈

- 板端系统：KaihongBoard-3588S-SBC + M-Robots OS 4.1
- 机器人：驭系列移动机器人（麦轮底盘 + 5DOF 机械臂 + 夹爪）
- 感知：Astra Pro Plus / Orbbec Gemini 335 深度相机 + 思岚 A1 雷达
- 中间件：ROS1（noetic 兼容运行时）+ Dora 0.3.12 + M-Claw 智能体
- 开发机：Windows 11 + HDC + VSCode

## 当前状态

- 开发板：KaihongBoard-3588S-SBC 已拿到，镜像已预制 ROS/Python/Dora/M-Claw；当前正从网络 HDC 切回 USB HDC（板子需物理接入 USB 线并通电）。
- 传感器：激光雷达、Astra 深度相机、里程计、IMU、电池、舵机状态、相机内参已上板实测并写入 `docs/传感器数据规格手册.md`。
- 运行时：ROS1 兼容运行时、Python 3.12.7、Dora 0.3.12 已预装可用；运行 Python 节点需 `LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0`。
- Demo：Dora Hello World + 5Hz sensor/filter 节点（`prep/demo代码/`）与 ROS1 talker/listener 均已在板端跑通，记录分别见 `prep/demo记录/dora样例记录.md` 和 `prep/demo记录/ros1样例记录.md`。
- 执行器方案：底盘 `/cmd_vel`、机械臂与夹爪 `FollowJointTrajectoryAction`、M-Claw `robot_ops.py` 高层 JSON 命令链路已确认，见 `prep/机器人硬件方案.md`。
- 选题与答疑：`prep/选题/候选方案.md` 与 `prep/老师确认记录.md` 已就位；最终选题待现场根据物料收敛。
- 备份机制：`prep/deploy.sh` 一键推送脚本已验证可用；换板恢复 SOP 待补。

## 现场支持

- Agent / M-Claw 问题 → 鲍奇瀚导师
- 机器车硬件 → 千笑老师
- M-Robots OS → 嘉妤老师

---

*本仓库为 AIY Hackathon 2026 参赛作品代码与文档仓库。*
