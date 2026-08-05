# MANIFEST — depth-filter 子管线

## 目的（不可变）

改善 Gemini 335 深度流的观感与稳定性：**降低时间抖动和散斑噪点，不牺牲速度与深度质量**。
原始 ROS 话题保持原样，滤波只作用于 Web 展示层（`gemini_web_stream.py`）。

## 目标态（可检验的完成判据）

1. `01` 采集基线：≥80 帧真实原始深度（16UC1, mm）+ 原始深度视频 + 彩色视频，落盘。
2. `02` 离线评估（在板端容器 CPU 上实测）：相对原始基线——
   - 时间抖动：有效像素逐像素时间 std 中位数下降 ≥50%
   - 有效像素率：下降 ≤2 个百分点
   - 散斑：有效小连通域（<24px）数量下降 ≥70%
   - 速度：滤波耗时 p95 ≤15 ms/帧（10fps 预算内）
   - 产出 raw|filtered 并排对比视频
3. `03` 集成进 Web 服务：滤波深度为主流，原始深度可在 `/raw` 对比查看。
4. `04` 在线验证：`/health` 双流 ≥5 fps、滤波器激活；从浏览器实际消费的 MJPEG 端点
   录制 live 视频 dump，人工（ReadMediaFile）确认改善。
5. artifacts 板端 `/data/gemini335-web/` 与电脑 `gemini335-web\` 同步一致，README 更新。

## 不变量

- 单位一律毫米（uint16），0 = 无效深度；不得在前向链路里用填充值伪造有效深度。
- 大空洞保持无效（黑），只允许 ≤hold_frames 的时间保持与小连通域清理。
- 每一步先在板端容器实测再下结论；阈值由实测数据校准并记录理由。

## 地图

- `util_gate.py` / `util_filter.py` — 共享 gate 与滤波/度量实现
- `01_capture_baseline.py`、`02_evaluate_filter.py`、`04_verify_live.py` — 编号步骤，按序执行
- `03` = 集成（直接编辑 `../gemini_web_stream.py`，记录于 logs/03_integrate/）
- `run1/` — 采集数据与离线产物（npy/mp4/metrics）；`logs/<step>/STATUS.txt` — 每步 PASS/FAIL
