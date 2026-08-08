# AIY 2026 · 深开鸿 M-Robots 赛道

> 队伍：CUHKSZ 代表队（5 人）  
> 比赛时间：2026-08-04 至 2026-08-06  
> 作品：拾安 · Gauge —— 托育机构地面风险巡检机器人  
> 仓库用途：作品代码 + 路演交付物 + 赛前准备文档 + 现场调试记录

> ⚠️ **2026-08-09 历史重写通知**：仓库已做敏感数据清除并 force push，旧克隆作废。
> 队员请先阅读 [分支同步与敏感数据清理指南](docs/分支同步与敏感数据清理指南.md) 再操作。

## 仓库结构

```
├── docs/                     # 团队材料与官方文档转录（唯一文档源）
│   ├── 官方材料/             # 赛方原始材料转录
│   ├── 板端开发参考/          # 板端数据结构、踩坑、HDC排查、传感器规格
│   ├── 技术选型报告/          # 算法与技术选型文档
│   ├── 拾安/                 # 拾安 · Gauge 行为准则（SOUL.md）
│   ├── 新手快速入门手册/      # 入门指南
│   ├── 分支同步与敏感数据清理指南.md  # 全员必读的协作与清理规范
│   ├── 0802会议材料-系统分层与场景定义.md
│   └── ...
├── src/                      # 团队自研代码统一入口
│   ├── grasping/             # 夹爪相机像素伺服抓取 pipeline（gated pipeline，实测 PASS）
│   ├── teleop/               # 键盘遥操作（方向键/A、D/S、X/J、L/W）
│   ├── yolo-pipeline/        # YOLO 蓝色锥桶训练与推理管线（含 Astra 风格数据增强）
│   ├── gemini335-web/        # Gemini 335 相机 Web 双流监视 + /locate 场地定位
│   ├── perception/           # 相机与感知节点（含 MJPEG 带宽修复）
│   ├── robot-control/        # 底盘运动控制工作区（运动原语、安全护栏，含 specs）
│   └── mclaw-update/         # M-Claw 本地补丁与测试
├── vendor/                   # 官方/外部源码（只读）
│   ├── kaihong-src/          # KaihongBoard 官方 SDK 与 ROS 工作区
│   └── robot-folder/         # 官方 robot-folder 归档
├── presentation/             # 路演交付物
│   ├── deck/                 # 拾安 Gauge 10 页路演 deck v4（HTML/PDF）
│   ├── V3-路演口径基线.md     # 对外唯一口径（冻结）
│   ├── 路演逐页文案.md        # 逐页口播稿
│   └── 路演任务追踪.md
├── scripts/                  # 运维脚本
│   ├── healthcheck.sh        # 全链路健康检查
│   ├── check-control-ready.sh # 控制前就绪检查
│   ├── sshd-foreground.sh + sshd.cfg  # 板端 SSH 双端口自启
│   └── README.md             # 控制前必须运行的脚本文档
└── prep/                     # 赛前准备交付物（环境、工具包、选题、演练记录）
```

说明：
- `src/` 为团队自研代码统一入口；`vendor/` 为官方只读源码；`AIY文件/` 为官方原始档案（docx/pdf），保持不动。
- **敏感与个人内容不入库**：队长个人卡片、AI 会话存档、个人任务数据、含密钥的配置笔记、大体积素材等已移出版本控制并加入 `.gitignore`（原件保留在各自电脑上）。详见[清理指南](docs/分支同步与敏感数据清理指南.md)。

## 快速入口

- [拾安 · Gauge 行为准则](docs/拾安/SOUL.md)
- [路演口径基线 V3（冻结）](presentation/V3-路演口径基线.md)
- [分支同步与敏感数据清理指南](docs/分支同步与敏感数据清理指南.md)
- [比赛认知与评分策略](docs/AIY比赛认知.md)
- [系统分层与场景定义](docs/0802会议材料-系统分层与场景定义.md)
- [板端开发速查与踩坑手册](docs/板端开发参考/板端开发速查与踩坑手册.md)
- [传感器数据规格手册](docs/板端开发参考/传感器数据规格手册.md)
- [机器人健康检查脚本](scripts/healthcheck.sh)
- [控制前必须运行的脚本](scripts/README.md)

## 技术栈

- 板端系统：KaihongBoard-3588S-SBC ×2 + KaihongOS / M-Robots OS 4.1（软总线双板协同）
- 机器人：驭系列移动机器人（麦克纳姆全向底盘 + 5DOF 机械臂 + 夹爪）
- 感知：Astra Pro Plus / Orbbec Gemini 335 深度相机 + 思岚 A1 雷达
- 智能：M-Claw 智能体（语义分级）+ HSV/模板/QR 轻量视觉
- 中间件：ROS1（noetic 兼容运行时）+ 软总线 / M-DDS
- 开发机：Windows 11 + HDC + SSH（密钥认证，端口 22/2223）

## 最终状态（赛后）

- **抓取**：夹爪相机 eye-in-hand 像素伺服 pipeline 端到端跑通（红色圆柱实测 PASS，gated pipeline 八关全过）。
- **定位**：Gemini335 辅助板 /locate 场地定位可视化（两级 DBSCAN + 兜底检测器）。
- **感知**：YOLO 蓝色锥桶训练管线（Astra 成像风格 LUT 数据增强）；双相机 USB 带宽冲突已修复（夹爪相机改 MJPEG）。
- **底盘**：运动原语 CLI + 硬限速 0.2m/s + 0.5s 超时看门狗 + 持久化急停。
- **智能**：板端 M-Claw 切换至 Kimi 通路；安全逻辑全部写死在确定性代码。
- **路演**：拾安 Gauge 10 页 deck v4 + AIGC 概念宣传片已合入 `presentation/`。

## 协作规则（赛后版）

- `main` 为唯一主线，功能一律经 PR 合入；只动自己的分支。
- 个人文档、密钥、大文件一律不进仓库（见[清理指南](docs/分支同步与敏感数据清理指南.md)）。
- Git 协作详见 `prep/git协作约定.md`。

## 现场支持

- Agent / M-Claw 问题 → 鲍奇瀚导师
- 机器车硬件 → 千笑老师
- M-Robots OS → 嘉妤老师

---

*本仓库为 AIY Hackathon 2026 参赛作品代码与文档仓库。*
