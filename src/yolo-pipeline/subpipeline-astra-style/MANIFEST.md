# MANIFEST — 子管线：Astra 风格迁移（subpipeline-astra-style）

> 父管线：`yolo-pipeline/MANIFEST.md`。本子管线是父管线的一个步骤级公民。

## 目的

手机拍摄的训练图（4096×3072、锐利、鲜艳）与板端 Astra 相机实际画面
（640×480、青蓝色偏、柔焦模糊、低对比、洗白）存在**域差异**。
本子管线从 Astra 实拍样图中提取风格统计量（色偏、模糊程度、对比度），
把手机图转换成"Astra 风格"，使 YOLO 训练分布贴近部署分布。

## 完成态（Goal State）

1. `astra_style.json` 存在且字段合法：BGR 三通道均值/标准差、拉普拉斯方差（模糊度）。
2. `../dataset_transformed/` 中每张输入图都有对应输出图（640×480）+ 同名标签
   （若源图有标签；几何不变换，归一化坐标直接复用），坏图排除比例 ≤ 10%。
3. 风格验证通过：转换后图片集的模糊度与 Astra 样图之比在 [0.5, 2.0]，
   通道均值距离相比转换前显著缩小（缩小 > 50%）。

## 不变量

- 只做**光度/模糊**变换，不做几何变换（缩放除外）——标签坐标保持有效。
- 输出尺寸恒为 640×480（部署分辨率）。
- 步骤与门禁框架复用父管线 `util_gate.py` / `util_paths.py`。

## 地图

```
subpipeline-astra-style/
├── 01_analyze_astra.py   # 从 Astra 样图提取风格统计 → astra_style.json
├── 02_transfer.py        # 对 dataset_raw/ 逐张转换 → dataset_transformed/
├── 03_verify.py          # 风格门禁（模糊度比、色距缩小）
└── logs/<step>/          # step.log / timing.json / STATUS.txt
```
