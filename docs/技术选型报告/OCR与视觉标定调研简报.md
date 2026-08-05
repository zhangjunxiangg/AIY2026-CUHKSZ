# AIY 2026 黑客松 · OCR 字符识别 + 视觉基准标定（Fiducial Marker）调研简报

**场景**：RK3588S（6TOPS NPU，8GB RAM，ARM64）+ Astra Pro Plus / Gemini 335 RGBD，ROS1 noetic，36 小时现场实时可用。
**目标物**：① 印刷大字字母点位标识（A–D，共 4 类，字体/尺寸已知）；② 马赛克/符号标定（疑为二维码/AprilTag 类）。

---

## 0. 核心结论（先看这里）

| 子任务 | 推荐方案 | 理由 |
|---|---|---|
| A–D 字母点位识别 | ✅ **推荐：二值化+透视矫正+模板匹配 / 4类微型CNN（<1MB）** | 已知印刷体、闭集4类，不需要OCR管线 |
| 马赛克/符号标定 | ✅ **推荐：OpenCV ArUco（objdetect 模块，CPU实时）**；若主办方用 AprilTag 则 AprilTag3 + apriltag_ros | 纯CPU即可 >30fps，无需NPU，零模型部署成本 |
| 完整 OCR 管线（PP-OCRv4 mobile） | ⚠️ **备选/不推荐**：仅当现场发现字母字号小、字体多样或需读数字编号时启用 | 部署RKNN链路需半天工时，对4类大字是杀鸡用牛刀 |

---

## 1. arXiv 论文（2020–2026）

### 1.1 轻量场景文字识别（STR）

| 论文 | 年份/链接 | 贡献 | 大小/算力 | 适用性 |
|---|---|---|---|---|
| **PP-OCR: A Practical Ultra Lightweight OCR System** | 2020, [arXiv:2009.09941](https://arxiv.org/abs/2009.09941) | DB检测+CRNN识别全链路瘦身（剪枝/蒸馏/PACT量化），中英模型仅 **3.5MB（rec）/ 1.4MB（det slim）** | mobile rec ~2.2M参数；CPU实时 | PP-OCR系列基线，mobile版可跑ARM CPU |
| **PP-OCRv2: Bag of Tricks for Ultra Lightweight OCR System** | 2021, [arXiv:2109.03144](https://arxiv.org/abs/2109.03144) | CML互学习蒸馏、增广copy-paste、轻量CPPN，精度↑7%，体积不变 | 与v1同量级 | 备选 |
| **PP-OCRv3** | 2022, [arXiv:2206.03001](https://arxiv.org/abs/2206.03001) | RSE-FPN检测、SVTR_LCNet识别头、文本方向判别 | rec ~12.4MB | v4前最佳mobile版 |
| **PP-OCRv4**（官方技术报告，PaddleOCR仓库+ [PaddleOCR 3.0 Report, arXiv:2507.05595](https://arxiv.org/abs/2507.05595)） | 2023–2025 | mobile版 det≈4.7MB + rec≈10MB；DFKD无数据蒸馏 | **整套 mobile <20MB**；RK3588 NPU（RKNN）实测 det+rec 合计 ~100–200ms/图 | 备选方案的唯一OCR候选 |
| **PP-OCRv5 / PP-OCRv6** | 2025/2026, [arXiv:2603.24373](https://arxiv.org/abs/2603.24373)、[arXiv:2606.13108](https://arxiv.org/abs/2606.13108) | 5M–34.5M参数统一中英/手写，精度超部分VLM | tiny版~1.5M参数起 | 太新，RKNN转换链不成熟，黑客松不建议 |
| **CRNN**（基础方法） | 2015（超出年限，仅作基线）, [arXiv:1507.05717](https://arxiv.org/abs/1507.05717) | CNN+BiLSTM+CTC，端到端序列识别 | ~8M参数 | 教学参考；PP-OCR识别头即源于此 |
| **SVTR: Scene Text Recognition with a Single Visual Model** | 2022 (IJCAI), [arXiv:2205.00159](https://arxiv.org/abs/2205.00159) | 纯视觉Transformer STR，去语言模型，SOTA精度；**SVTR-Tiny ~4M参数** | Tiny版算力友好 | PP-OCRv4 rec主干（SVTR_LCNet）的出处 |
| **PARSeq: Scene Text Recognition with Permuted Autoregressive Sequence Models** | 2022 (ECCV), [arXiv:2207.06966](https://arxiv.org/abs/2207.06966) | 置换语言建模+迭代并行解码，当前STR高精度基线 | PARSeq-Ti ~24M参数，ViT-based，**不适合6TOPS NPU实时** | ❌ 不推荐本场景（过重） |

### 1.2 Fiducial Marker 系统

| 系统/论文 | 链接 | 特点 |
|---|---|---|
| **AprilTag 2/3**（Olson 组）：AprilTag2 论文 "Flexible Layouts for Fiducial Tags" (IROS 2019), [arXiv:1904.12437](https://arxiv.org/abs/1904.12437)；AprilTag3 (Wang & Olson, IROS 2016/2019 detector) | 官方仓库 [github.com/AprilRobotics/apriltag](https://github.com/AprilRobotics/apriltag) | 边缘梯度直线拟合，位姿精度高，误检率极低；CPU检测 640×480 约 10–20ms。机器人界事实标准 |
| **ArUco**（OpenCV 内置） | [OpenCV 4.x 官方教程](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)；论文 Garrido-Jurado et al., *Pattern Recognition* 2014 | `cv2.aruco`（4.7+并入 `objdetect`，Python `opencv-contrib-python`）；字典 4×4~7×7；支持 ChArUco 亚像素标定板。**零部署成本，首选** |
| **STag: A Stable Fiducial Marker System** | [arXiv:1707.06292](https://arxiv.org/abs/1707.06292)（IEEE TIP 2019）；[github.com/bdaiinstitute/stag](https://github.com/bdaiinstitute/stag) | 圆形内框精化单应性，遮挡鲁棒、位姿抖动最小；检测率略低于AprilTag、>40px才稳定 |
| **FMAC 公平对比基准** | [arXiv:2601.07723](https://arxiv.org/html/2601.07723) | ArUco/AprilTag/STag/TopoTag 位姿误差系统对比：AprilTag 与 STag 平移精度相当；ArUco 与 AprilTag 角误差更小；TopoTag 检测率仅57.65% → **不建议 TopoTag** |
| ChArUco（标定板） | OpenCV aruco 模块内置 | 用于相机内参标定/高精度亚像素定位，赛前标定 Astra Pro 用 |

---

## 2. GitHub 开源代码

### 2.1 PaddleOCR（备选路线）
- 仓库：[github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)，⭐ **55k+**，**Apache-2.0**
- PP-OCRv4 mobile：det+cls+rec 合计 **<20MB**；官方预训练模型直接下载
- ARM/RK3588 部署三条路径：
  1. **PaddleLite**（官方ARM路线，[Paddle-Lite](https://github.com/PaddlePaddle/Paddle-Lite)）：ARM CPU fp32/int8，RK3588 CPU 实测整套 ~200–400ms
  2. **ONNX → RKNN Toolkit2**：社区成熟项目 [github.com/airockchip/rknn_model_zoo](https://github.com/airockchip/rknn_model_zoo)（含 OCR 示例）与 PaddleOCR 官方 FastDeploy RKNN 文档；NPU 推理 det ~60ms + rec ~30ms（实测社区报告量级）
  3. **ONNX Runtime CPU**：最快落地、无需转换，640×480 输入 mobile 模型 ~300ms/图
- 实测速度参考（RK3588）：PaddleLite int8 mobile 套件 5–8 fps；RKNN NPU 10–15 fps。**对 A–D 四个大字是过度方案**

### 2.2 Fiducial Marker 代码
- **OpenCV ArUco/AprilTag 字典**：`pip install opencv-contrib-python` 后：
  ```python
  det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11))
  corners, ids, _ = det.detectMarkers(gray)   # RK3588 CPU 全幅 <15ms
  ```
  内置 DICT_4X4/…/DICT_APRILTAG_16h5/25h9/36h10/36h11，**同时支持 ArUco 与 AprilTag2 族**。教程：https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html
- **AprilTag 官方 C 库**：[github.com/AprilRobotics/apriltag](https://github.com/AprilRobotics/apriltag)（BSD-2，⭐~1.5k），比 OpenCV 实现更快更准；ROS1 封装 [github.com/AprilRobotics/apriltag_ros](https://github.com/AprilRobotics/apriltag_ros)（noetic 分支可用）→ **有现成 ROS topic，强烈推荐若主办方用 AprilTag**
- **STag**：[github.com/bdaiinstitute/stag](https://github.com/bdaiinstitute/stag)（BSD），备选
- **二维码**：OpenCV `cv2.QRCodeDetector`（CPU 内置，零依赖）——若"马赛克"实为二维码，这是最优解

### 2.3 轻量单字符分类（MNIST 式 26 字母）
- EMNIST Letters（26类，28×28）参考实现：
  - [github.com/Khalil071/EMNIST-Letter-Classification-using-CNN-and-ViT](https://github.com/Khalil071/EMNIST-Letter-Classification-using-CNN-and-ViT)（CNN 版 ~1MB）
  - [github.com/awmirma/EMNIST-Image-Classification](https://github.com/awmirma/EMNIST-Image-Classification)（TF/Keras，MIT）
- ⚠️ EMNIST 是**手写**体，场地为印刷体 → 建议**用场地同款字体合成数据自训 4 类小CNN**（用 `PIL.ImageFont` 渲 A/B/C/D + 随机旋转/亮度/模糊/透视增广，30 分钟出数据），模型 <500KB，RK3588 CPU <5ms，亦可转 RKNN 用 NPU

---

## 3. 工时/鲁棒性权衡（特别评估）

| 方案 | 现场工时 | 鲁棒性 | 结论 |
|---|---|---|---|
| **A. 模板匹配**（HSV/二值化找大色块→轮廓透视矫正→`matchTemplate` 或逐像素比对 4 模板） | **2–4 小时** | 印刷大字、固定字体、近距离时极高；尺度/光照变化需多尺度+自适应阈值兜底 | ✅ **推荐主方案** |
| **B. 合成数据 4 类小 CNN**（LeNet级/PP-LCNet-0.25x） | 4–6 小时（含训练导出） | 对光照/模糊/轻微遮挡更鲁棒，可输出置信度 | ✅ **推荐（与A并联投票）** |
| **C. PP-OCRv4 mobile 全管线**（det+rec，RKNN） | 8–14 小时（转换链+量化调参+ROS集成） | 泛化最强，但4类闭集下精度优势无意义，且det模型对超大字容易漏检 | ⚠️ **备选**：仅当点位还含数字编号/多字符时才上 |
| D. PARSeq/SVTR-B 等重模型 | >16h 且NPU算子支持有风险 | — | ❌ 不推荐 |
| **马赛克=AprilTag/二维码** | **0.5–1 小时**（OpenCV/apriltag_ros 开箱即用） | 工业级 | ✅ **最优解，直接上**；务必赛题一公布就确认 marker 类型并现场打印备份 |
| 马赛克=自定义色块图案 | 2–3 小时（颜色直方图+格点采样解码） | 高 | 备选 |

**建议组合**：白天先做「马赛克=OpenCV fiducial 检测」+「字母=模板匹配」两条零深度学习管线（合计半天），剩余时间做 CNN 备份与 RGBD 深度辅助（用深度把字母 ROI 从地面/墙面分割出来，模板匹配稳定性大幅提升）。

---

## 4. 评估表

| 模块 | 调用频率 | 算力需求 | 部署位置 | 推荐度 |
|---|---|---|---|---|
| ArUco/AprilTag 检测（OpenCV） | 每帧（10–30Hz） | 极低，单帧 <15ms | **板端 CPU** | ✅ 推荐 |
| apriltag_ros（AprilTag3 C库） | 每帧 | 低 | 板端 CPU，ROS topic 直出 | ✅ 推荐（若官方tag） |
| cv2.QRCodeDetector | 事件触发/每帧 | 极低 | 板端 CPU | ✅ 推荐（若是二维码） |
| 字母模板匹配（多尺度） | 事件触发（到达点位附近时 5–10Hz） | 极低 | 板端 CPU | ✅ 推荐 |
| 4类字母小CNN（合成数据） | 事件触发 | <0.05 GFLOPs | 板端 CPU（或 RKNN NPU 闲置时） | ✅ 推荐（备份/投票） |
| PP-OCRv4 mobile（det+rec） | 事件触发 | ~2–4 GFLOPs/图 | **RKNN NPU**（FastDeploy/PaddleLite） | ⚠️ 备选 |
| PP-OCRv5/v6 | — | 转换链不成熟 | — | ❌ 不推荐 |
| PARSeq / SVTR-Base | — | >10 GFLOPs，ViT算子NPU支持差 | 云端（现场无网络保障，不可行） | ❌ 不推荐 |
| 任何云端 OCR API | — | 依赖场馆网络 | 云端 | ❌ 不推荐（网络不可靠） |

---

## 5. 赛前准备清单
1. 装好 `opencv-contrib-python==4.10+`（注意 4.7 起 aruco 并入 objdetect，API 用 `ArucoDetector`），编译 ROS1 的 `apriltag_ros`（noetic）
2. 用 Astra Pro / Gemini 335 跑一遍 ChArUco 内参标定并保存 yaml
3. 预生成 A/B/C/D 各字体的合成训练集 + 导出 ONNX 小 CNN；备好 RKNN Toolkit2 环境
4. 打印一套 36h11 AprilTag、ArUco 6×6、二维码各若干带到现场做联调
