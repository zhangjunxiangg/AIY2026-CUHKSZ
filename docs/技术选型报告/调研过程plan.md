# Plan — 机器人算法技术选型调研报告

## 背景
AIY 2026 黑客松深开鸿 M-Robots OS 赛道。硬件：KaihongBoard-3588S×2（RK3588S，6TOPS NPU，8GB RAM）、麦轮底盘+5DOF机械臂+夹爪、Astra Pro Plus 深度相机、思岚A1雷达、Gemini 335 RGBD。36小时现场实时可部署。规则允许云端 API（M-Claw/Kimi/Qwen），核心感知建议端侧。

## Stage 1 — 并行深度调研（deep-research-swarm，Route A 变体：分方向并行）
按算法域拆 6 个并行 explore 子代理，每个都要求：arXiv 论文（近3年优先，标注年份/引用/链接）+ GitHub/GitLab 开源代码（star数、维护状态、license、部署依赖、ARM/RK3588 适配性）：
1. 底盘运控与路径规划：麦轮里程计、A*/DWA/TEB 局部避障、基于深度/2D雷达的实时避障（轻量、CPU可跑）
2. 抓取：轻量抓取检测（GGCNN/GR-ConvNet/Contact-GraspNet lite）、5DOF 臂几何启发式抓取、手眼标定（eye-in-hand）
3. 目标检测与位姿/距离估计：YOLOv8n/YOLOv11 轻量检测 + 深度相机距离解算、RKNN NPU 部署（rknn-toolkit2、yolov8 rknn 参考实现）
4. 字符/OCR/马赛克识别：轻量 OCR（PaddleOCR PP-OCRv4 mobile、CRNN）、模板匹配、AprilTag/ArUco 标定定位
5. VLA/端到端抓取与 LLM 任务规划（π0 类轻量策略是否可行的可行性评估；36h 内可用性判断）
6. 工程部署交叉验证：RK3588 NPU 实际算力实测、ROS1 noetic 在 ARM64 上的导航栈（move_base/navfn/dwa）成熟案例

每个子代理输出：候选清单 + 调用频率评估 + 算力需求 + 端侧/云侧/笔记本外侧建议。

## Stage 2 — 综合与技术选型（report-writing）
主代理整合 6 份调研，产出技术选型报告 md：
- 每算法域：首选方案 + 备选 + 降级
- 调用频率表、算力配置表、部署位置决策表
- 36h 落地优先级（对齐 P0-P3）

## Stage 3 — 三轮独立审核（verifier × 3，并行）
- V1：事实核查（论文/仓库链接、star、license 真实性，链接可达）
- V2：技术可行性核查（RK3588S 6TOPS/8GB 能否跑、ROS1 noetic 兼容、36h 工时合理性）
- V3：场景对齐核查（与比赛手册算法清单/算力分配/物料对齐，遗漏检查）
按审核意见修订报告。

## Stage 4 — 交付（docx skill）
最终 md → docx，输出至 /mnt/agents/output/。
