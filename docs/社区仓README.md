# 拾安 · Gauge —— 托育机构地面风险巡检机器人

> M-Robots 社区落地仓库（mrobots_app_shian_gauge）
> AIY Hackathon 2026 · 深开鸿 M-Robots 赛道参赛作品 · CUHKSZ 代表队
> 开源协议：Apache License 2.0（见 `LICENSE`，第三方依赖声明见 `NOTICE`）

拾安 Gauge 是一台面向托育机构场景的地面风险巡检机器人：基于 M-Robots OS 双板协同（机器车板 + Gemini 335 辅助相机板），用 M-Claw 智能体做任务入口与语义决策，完成"场地巡视 → 风险识别 → 精准拾取 → 复位归位"的闭环。

## 核心能力

- **抓取**：夹爪相机 eye-in-hand 像素伺服 pipeline，gated pipeline 八关验证（红/黄/绿圆柱实测通过）——`src/grasping/`
- **定位**：Gemini 335 场边俯拍全局定位，两级 DBSCAN 聚类 + 兜底检测器，Web 可视化 `/locate` 页面——`src/gemini335-web/`
- **感知**：多后端目标检测（HSV / 模板 / YOLO-ONNX），双相机 USB 带宽冲突修复（MJPEG 压缩流）——`src/perception/`、`board_scripts/`
- **底盘**：运动原语 CLI + 硬限速 0.2 m/s + 0.5s 看门狗 + 持久化急停——`src/robot-control/`
- **遥操**：键盘实时遥操作（移动/旋转/机械臂/夹爪/双相机拍照）——`src/teleop/`
- **智能体**：M-Claw 语义决策，安全约束全部落在确定性代码层——`src/mclaw-update/`、`docs/拾安/SOUL.md`

## 技术栈

- 平台：KaihongBoard-3588S ×2 + KaihongOS / M-Robots OS 4.1（软总线双板协同）
- 机器人：驭系列移动机器人（麦克纳姆全向底盘 + 5DOF 机械臂 + 夹爪）
- 感知硬件：Astra Pro Plus / Orbbec Gemini 335 深度相机 + 思岚 A1 雷达 + 夹爪末端 icSpring 相机
- 中间件：ROS1（noetic 兼容运行时）+ 软总线 / M-DDS
- 智能体：[M-CLAW](https://gitcode.com/m-robots/mclaw)（M-Robots 社区官方空间智能体）

## 目录结构

```
├── src/                  # 自研代码（抓取/遥操/感知/定位/底盘/M-Claw 补丁）
├── board_scripts/        # 板端部署与守护脚本（相机守护、UVC 发布等）
├── scripts/              # 运维脚本（健康检查、控制前就绪检查）
├── docs/                 # 文档（板端开发参考、技术选型、行为准则等）
├── presentation/         # 路演交付物（10 页 deck、口径基线）
├── LICENSE               # Apache-2.0
└── NOTICE                # 第三方依赖声明与合规说明
```

## 文档入口

- 行为准则（SOUL）：`docs/拾安/SOUL.md`
- 板端开发踩坑手册：`docs/板端开发参考/板端开发速查与踩坑手册.md`
- 传感器数据规格手册：`docs/板端开发参考/传感器数据规格手册.md`
- 开源协议合规审计：`docs/开源协议合规审计报告.md`
- 路演口径：`presentation/V3-路演口径基线.md`

## 合规说明

本仓库按 M-Robots 社区（开放原子基金会法务审查）要求整理：不包含 GPL / AGPL / LGPL
协议代码或依赖；官方/机器人自带内容不随本仓库分发；训练类工具链与运行时产物不入库。
详见 `NOTICE` 与 `docs/开源协议合规审计报告.md`。

## 社区

- M-Robots 社区：https://gitcode.com/org/m-robots/repos
- 问题与建议欢迎提 Issue；贡献前请先阅读社区贡献指南并签署 CLA。
