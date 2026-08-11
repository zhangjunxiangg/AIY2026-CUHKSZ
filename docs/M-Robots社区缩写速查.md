# M-Robots 社区贡献相关缩写速查

> 整理日期：2026-08-06
> 配套文档：`docs/M-Robots社区贡献流程.md`、`docs/社区贡献issues/`

## 社区治理类

| 缩写 | 全称 | 含义 |
|---|---|---|
| **CLA** | Contributor License Agreement | 贡献者许可协议。签署即授权社区使用你的代码、并保证不侵犯第三方知识产权。M-Robots 所有仓库强制检查，未签署 PR 无法合并；首次提 PR 时签署助手自动触发 |
| **TSC** | Technical Steering Committee | 技术指导委员会。负责定义技术愿景、技术地图和发展方向 |
| **PMC** | Project Management Committee | 项目管理委员会。负责版本规划、架构看护、处理 Issue、选举/退出 Committer |
| **SIG** | Special Interest Group | 特别兴趣小组。按技术领域划分的 13 个开发小组（如 SIG9 = M-Claw 与多机协同、SIG11 = 开发者工具链），社区开发的基层组织，任何人可加入 |
| **Committer** | —（非缩写） | 对特定仓库有代码审查和合并权限的核心贡献者。条件：持续贡献 3 个月以上、约 10 个有效 PR、获现有 Committer 或 PMC 提名 |

## 贡献流程类

| 缩写 | 全称 | 含义 |
|---|---|---|
| **PR** | Pull Request | 合并请求。fork 仓库改完代码后，请求官方仓库合入主干 |
| **RFC** | Request for Comments | 方案征求意见。大改动先写方案文档讨论，定了再动手 |
| **L5** | Level 5 | 社区成长等级（社区领袖级），靠贡献积分累积晋升，是提名 Committer 的参考条件 |
| **Fixes #编号** | —（固定写法） | 写在 PR 描述里，合入时自动关闭对应 Issue，建立代码与问题的关联 |
| **Host Verified / Device Pending** | —（非缩写） | 官方推荐的两段式验证标注：前者=主机上已完成验证，后者=需开发板接力验证，不得假装做过硬件验证 |

## 技术术语类

| 缩写 | 全称 | 含义 |
|---|---|---|
| **HDC** | OpenHarmony Device Connector | 开发机连接开发板的命令行调试工具（类似安卓 adb），支持 USB/网络两种连接 |
| **ROS** | Robot Operating System | 机器人操作系统（消息通信框架），ROS1/ROS2 是两个大版本；机器车全套软件栈基于 ROS1 |
| **Dora** | —（非缩写） | 高性能实时数据流处理框架，robot_middleware 目前唯一已支持的中间件 |
| **M-DDS** | M-Robots Data Distribution Service | M-Robots 数据分发服务，软总线通信技术（SIG3 负责） |
| **UVC** | USB Video Class | USB 摄像头标准协议，夹爪相机（icSpring）即 UVC 设备 |
| **IK / FK** | Inverse / Forward Kinematics | 逆运动学 / 正运动学。FK = 关节角度算末端位姿，IK = 给定位姿反算关节角度 |
| **HIL** | Hardware-in-the-Loop | 硬件在环测试，指真机验证（相对纯软件仿真） |
