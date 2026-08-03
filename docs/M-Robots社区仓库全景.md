# M-Robots 社区仓库全景（org/m-robots）

> 扫描范围：AtomGit/GitCode `m-robots` 组织全部仓库（约 600 个，2026-08-02 通过 GitCode API 全量枚举）
> 用途：了解社区有什么、哪些可用、未来往哪里贡献
> 地址：https://atomgit.com/org/m-robots/repos （GitCode 镜像同）

## 0. 一句话总览

这个组织库 = **1 个 M-Robots 核心项目群（约 12 个仓库）+ KaihongOS 5.0.1 操作系统源码镜像（约 380 个）+ 第三方依赖镜像（约 200 个）**。真正属于"M-Robots 自己"的项目只有第一层，也是我们使用和贡献的主战场。

---

## 1. M-Robots 核心项目（全部精读过了 README）

### ⭐ M-CLAW —— 自进化空间智能体（比赛 25 分的核心）
- **语言/协议**：Python 3.11+，Apache-2.0，当前 v1.0.0 源码安装
- **平台**：Windows / Linux / KaihongOS / M-Robots OS（识别鸿蒙主机后启用 KaihongRuntime，禁用 checkpoint 和浏览器自动化，保留基础能力）
- **定位**：面向具身智能的 Agent Runtime——连接语言模型与物理执行系统，"一机一脑、多脑协同"
- **四层架构**：Agent Runtime Core（执行循环/状态）→ Tool Runtime（环境接口）→ Skill Layer（可复用能力单元）→ Safety Runtime（策略约束/审计/回滚）
- **工具集**：**21 个基础工具**（credentials 密钥请求、terminal/process、file 系列、memory 系列、skills 系列、session_search、delegate_task 子代理）+ **13 个可选工具**（web_search/extract、vision_analyze（Qwen 视觉模型）、browser 系列、微信/钉钉发送）
- **22 个内置命令**：模型切换、搜索/提取后端切换、语音输入、rollback/checkpoint、定时任务、Skill 管理、`mclaw doctor` 诊断
- **模型接入**：OpenAI-compatible + Anthropic Messages 双协议；经 models.dev 获取模型目录（145 个 provider、5246 条记录），适配 31 个国内外供应商，可自定义 endpoint；`mclaw setup` 首次配置
- **三层记忆**：会话记忆（SQLite+FTS5）/ 长期记忆（MEMORY.md、USER.md）/ Skill 记忆（SKILL.md + skill_evolution.json 演化记录）
- **Skill as Memory**：Skill = SKILL.md（语义）+ mclaw_skill.yaml（元数据）+ skill_evolution.json（经验）+ 执行资产；写入只能走 `skill_manage`，有后台演化审查
- **安全**：PathPolicy 路径保护、Scoped Secret 密钥不明文、Checkpoint 快照、/rollback 回滚；**1.0.0 无沙箱无权限分级**
- **交互通道**：CLI/TUI、语音输入（Qwen realtime ASR，唤醒词/按键两种）、微信网关、钉钉网关
- **Roadmap**：2026.09 v1.1 分布式运行时协同网络 + "脑-小脑"分层（大脑意图规划、小脑高频实时执行）→ 2026.10 v1.2 Mycelium 控制平台 + Skill Hub 生态 → 2026.12 v2.0 空间智能体运行时（空间记忆/空间建模/跨机器人调度）
- **关键文档**：`docs/manual/README.md` 操作手册（Slash Command、示例提示词、平台限制）——**赛前必读，回答了我们 Top 10 问题里的大部分 M-Claw 疑问**

### ⭐ robot_middleware —— 机器人核心中间件（Rust）
- 定位：机器人操作系统中间件框架，统一编程接口（通信与消息传递）
- 结构：framework / interfaces / idl / impl / sa（系统服务）/ examples / docs
- **中间件支持**：Dora ✅ 已支持；ROS 🛠️ 构建中；ROS2 🛠️ 构建中
- **多语言接口**：C++/JavaScript/Rust/ArkTS 均"构建中"（订阅发布）——**明确的可贡献点**
- 消息类型：基于 ROS 标准消息，兼容 ROS 生态
- 构建：cargo build --release（Ubuntu）；aarch64 交叉编译见 cross-compile.md

### robot_docs —— 系统文档（我们已读 14 篇）
- 安装/工具使用/ROS/Dora/调试五大章 + build.md（下载编译说明，配 manifest 用）
- **最适合新手贡献的仓库**（文档修复、补全"待推出"章节）

### robot_tools_maestro —— Web 可视化编程调试工具（JS+Rust）
- 功能：ROS1 节点/话题/服务实时监控可视化；**传感器数据渲染（Image、CompressedImage、LaserScan、PointCloud2）**；拖拽可视化编程（自定义 JS 节点）；自定义消息类型；DAE 模型导入 + URDF 生成 + Gazebo 集成
- 支持：ROS1 ✅；ROS2/Dora 构建中；Ubuntu/OpenHarmony
- 板上安装：`ferrium install maestro-0.1.0@aarch64`
- 对比赛价值：调试时可视化雷达/图像的现成工具；低代码演示可能加分

### robot_tools_rerun_tools —— SLAM 可视化工具（Rust/C++）
- 可视化：雷达点云（XYZ/XYZI）、图像（灰度/RGB/RGBA/JPEG/Nv12/YUY2）、小车轨迹、相机姿态、RGBD 帧对
- **板上用法（重要）**：`startxvfb` → `run x11vnc` → `DISPLAY=:0 run_gui ./rerun --renderer=gl` → `run slam_viewer actions --pcd-xyz/--image/--trajectory/...`
- 对比赛价值：**雷达点云和相机画面的可视化方案**（RViz 之外的备选，官方自带）

### robot_tools_ferrium（+ ferrium_pkgs）—— Rust 包管理工具
- 能力：包安装/卸载/部署/回滚、依赖解析、多工具链、镜像、chroot 交叉编译环境
- **关键认知**：这是往 M-Robots 板上装软件的官方渠道——`ferrium install dora-0.3.12@aarch64` / `maestro-0.1.0@aarch64` / `rerun-tools-0.1.0@aarch64` / `rustc-1.86.0#ohos` 等
- ferrium_pkgs：软件包配置仓库（贡献新包打包配置的地方）

### third_party_dora —— Dora 中间件镜像（Rust）
- dora-rs 官方镜像 + **OpenHarmony 交叉编译完整补丁说明**（nix/iana-time-zone 的 ohos 适配 patch、`aarch64-unknown-linux-ohos` target）
- 对贡献者价值：想给 OHOS 移植 Rust 软件，这份补丁流程是模板

### 其他
| 仓库 | 内容 |
|------|------|
| `manifest` / `mrobots_manifest` | M-Robots OS + OpenHarmony 组件下载配置（repo sync 用，分支 M-Robots_6.1_Release） |
| `M-Robots_release` | 可直接烧录的系统固件（3588A/3588S） |
| `docs-readme` | 社区介绍页 |
| `M-Robots组织架构` | 组织说明（Markdown） |

## 2. KaihongOS 5.0.1 系统源码镜像（约 380 个）

这些是 OpenHarmony/KaihongOS 操作系统的组件源码（2026-06-25 批量镜像），按域分类。对大多数人只需知道存在；**以下 5 个与我们直接相关**：

| 仓库 | 为什么相关 |
|------|-----------|
| **`communication_dsoftbus`** | **分布式软总线源码**（25 分协同能力的底层）——想深挖软总线组网/API 看这里 |
| `ai_neural_network_runtime` | NPU 神经网络推理运行时（NNRt）——RKNPU 推理的系统侧 |
| `vendor_kaihong_khd_rk3588_a` | 3588A 开发板厂商适配层（编译源码时的产品定义） |
| `kernel_linux_6.6` / `kernel_linux_patches` | 内核与补丁（PREEMPT_RT 实时性相关） |
| `xts_acts` / `xts_dcts` / `testfwk_*` | 兼容性测试套件（贡献代码时的测试参考） |

其余域（不用细看）：multimedia_*（相机/音视频）、graphic_*（2D/3D 渲染）、arkui_*（UI 框架）、ability_*（应用框架）、distributedhardware_*（分布式硬件，含 mechbody_controller）、distributeddatamgr_*、filemanagement_*、bundlemanager_*、communication_*（WiFi/蓝牙/NFC/IPC/netstack）、window_*、ai_engine、ai_intelligent_voice_framework、accessibility、kh_*（开鸿安全/云/超级设备）、third_party_*（181 个）+ kh_third_party_*（22 个）依赖镜像。

## 3. 贡献地图（未来想给社区贡献，从哪入手）

| 方向 | 仓库 | 切入点 | 门槛 |
|------|------|--------|------|
| **文档**（推荐新手） | `robot_docs` | 迁移/RKNPU 两章标注"待推出"；调试案例、FAQ 补充 | ⭐ |
| **M-Claw Skill 生态** | `M-CLAW` | 写 Skill（SKILL.md + 资产）——巡检/抓取/寻物技能包；Skill Hub 生态 2026.10 上线，现在写正当时 | ⭐⭐ |
| **中间件接口** | `robot_middleware` | ROS/ROS2 支持、C++/JS/ArkTS 接口都标着"构建中" | ⭐⭐⭐ |
| **可视化工具** | `robot_tools_maestro` | ROS2/Dora 支持、3D 可视化增强（README 有贡献指南：fork→分支→PR） | ⭐⭐ |
| **软件包** | `robot_tools_ferrium_pkgs` | 把常用工具（如 debugpy 环境、视觉库）打成 ferrium 包 | ⭐⭐⭐ |
| **OHOS 移植** | `third_party_dora` 模式 | 参照其交叉编译补丁流程移植其他 Rust 工具 | ⭐⭐⭐⭐ |
| **比赛作品回流** | 社区优秀案例集 | 官网明确"优秀项目将被纳入官方优秀案例集"——黑客松作品本身就是贡献 | ⭐ |

**协议**：Apache-2.0 + 木兰宽松许可证 V2（robot_docs）。贡献流程：fork → 功能分支 → Pull Request（maestro README 明示）。

## 4. 对我们比赛的三个直接 actionable

1. **M-CLAW 操作手册（docs/manual/README.md）赛前必读**——Slash Command、示例提示词、平台限制都在里面，山茶（E）负责，读完回填《传感器数据规格手册》和 Top10 问题
2. **板上装工具用 ferrium**：`ferrium install dora/maestro/rerun-tools @aarch64`——刘昱麟（B）到现场装可视化工具的标准姿势
3. **可视化双方案**：RViz（X11+VNC）之外多了 rerun-tools（官方支持雷达点云/图像/轨迹）——应露（C）调传感器时的备选

## 5. 扫描原始数据

- 全量仓库清单：`_audit-cache/mrobots_repos.txt`（300）+ `_audit-cache/mrobots_repos_p456.txt`（299）
- 核心 README 存档：`_audit-cache/core_readmes/`（M-CLAW 中文 README、middleware/maestro/ferrium/rerun/dora README）
