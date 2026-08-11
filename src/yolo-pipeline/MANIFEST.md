# MANIFEST — 蓝色路障（锥桶）YOLO 检测模型训练管线

> 本文件是管线的唯一 immutable 根定义：目的、完成态、不变量、地图。
> 不为新功能修改本文件；功能文档放各步骤与报告中。

## 目的（Purpose）

为 AIY 2026 深开鸿赛道训练一个 YOLOv8n 检测模型，在板端 Astra 相机（640×480）画面里
**稳定检出蓝色路障锥桶**——HSV 路线已实测无法分离藏青锥与紫地毯/白布紫调褶皱
（见 perception 调试记录），YOLO 是替代方案。模型最终以 ONNX 导出，接入
`src/perception/` 感知包的 `yolo_detect` 后端。

## 完成态（Goal State，逐条可验证）

1. `dataset/` 通过校验：图片 ≥ 最小数量、每张图有可解析的 YOLO 标签、类别合法、
   bbox 归一化且在 [0,1]、train/val 划分存在、`data.yaml` 可由 ultralytics 加载。
2. 冒烟训练通过：coco8 上 1 epoch 真实跑通（证明 GPU/框架/导出链路可用），
   最终 loss < 初始 loss，checkpoint 文件存在。
3. 完整训练通过：产出 `weights/best.pt`（保留最优而非最后）。
4. 评估通过：val 集 mAP50 ≥ 阈值（见 `util_paths.py`），且优于平凡基线
   （无检测器基线 mAP50 = 0）。
5. 导出通过：`best.onnx` 存在，用 onnxruntime 重新加载并对一张 val 图推理，
   输出张量形状合法。
6. 报告存在：`report/REPORT.md` 从 logs/ 痕迹生成，含每步 PASS/FAIL 与关键指标。

## 不变量（Invariants，任何步骤不得违反）

- **任何步骤不得在输入未验证时运行**：先读前驱步骤的 STATUS.txt（必须为 PASS）。
- **不得在未经 02 校验的数据上训练**（04 的硬门禁）。
- 类别定义以 `util_paths.py` 的 `CLASSES` 为唯一来源，禁止各步骤自定义。
- 训练图像尺寸统一 640（与板端相机分辨率一致），禁止静默改用其他尺寸。
- 所有步骤把日志写入 `logs/<step>/`，STATUS.txt 只有 PASS / FAIL 两种值。
- 失败即停：某步 FAIL 后只修复并重跑该步，不跳过、不降级门禁。

## 地图（Map）

```
yolo-pipeline/
├── MANIFEST.md            # 本文件
├── util_paths.py          # 全部路径、常量、类别定义（唯一来源）
├── util_gate.py           # 门禁/日志/计时/STATUS 框架
├── 01_inspect_dataset.py  # 原始数据检查（图片可读、数量、分辨率分布）
├── 02_validate_dataset.py # 标签校验 + train/val 划分 + 生成 data.yaml
├── 03_smoke_train.py      # coco8 冒烟训练（不依赖业务数据）
├── 04_train.py            # 完整训练（保留 best.pt）
├── 05_evaluate.py         # val 评估，mAP 门禁
├── 06_export.py           # ONNX 导出 + 重载推理门禁
├── 07_report.py           # 从痕迹生成报告
├── dataset_raw/           # 待提供：原始图片（板端抓拍或手机拍）
├── dataset/               # 02 产出：YOLO 格式数据集
├── logs/<step>/           # 每步 step.log / timing.json / STATUS.txt
└── report/                # 07 产出
```
