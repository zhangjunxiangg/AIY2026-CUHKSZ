# YOLO 训练快速流程（现场版）

> 目标：让 YOLO 识别 `human_board`、`wood_cylinder`、A–D 字母等 HSV/模板兜不住的物体。
> 前提：现场有笔记本（带 GPU 更好）或 Colab 账号。

## 1. 采集图片

### 方式 A：在机器车上自动抓拍（推荐，视角正确）

在板端执行：

```bash
run python3 /data/local/perception/capture_dataset_frames.py \
  --topic /astra_camera/rgb/image_raw \
  --out /data/local/dataset/aimaterials_raw \
  --interval 1.0
```

把车开到不同位置、不同光照、不同角度，对每个物料拍 30–100 张。Ctrl-C 停止。

然后拉回电脑：

```powershell
scp -r mrobots:/data/local/dataset/aimaterials_raw ./dataset_raw/
```

### 方式 B：手机/相机拍照

把物料摆在比赛场地上，多角度、多距离拍 50–200 张，传到 `dataset_raw/`。

---

## 2. 自动生成 YOLO 标签

```bash
cd perception
python collect_yolo_dataset.py \
  --images ../dataset_raw \
  --out ../datasets/aimaterials \
  --split 0.8
```

这会调用现有的 HSV/模板/ArUco 管线生成 bbox 标签。标签**一定存在错误**，特别是 `human_board` 和 `wood_cylinder`，需要人工检查修正。

---

## 3. 人工检查修正标签

推荐安装 labelImg：

```bash
pip install labelImg
labelImg ../datasets/aimaterials/images/train ../datasets/aimaterials/classes.txt
```

修正错误的框，删掉误检，补上漏检。优先保证 `human_board`、`wood_cylinder`、A–D 字母的框准确。

---

## 4. 训练 YOLOv8n

> **协议提示（2026-08-11 起）**：ultralytics 为 AGPL-3.0，按 M-Robots 社区合规要求，
> 训练管线（`src/yolo-pipeline/`）已移出本仓库主线，仅作团队内部开发工具保存。
> 以下训练步骤请在仓库外的开发环境执行；**训练产物 `.onnx` 模型权重可安全分发**
> （工具产出物不构成 AGPL 衍生作品）。推理侧只使用 onnxruntime（MIT）/ rknnlite2。

### 方式 A：笔记本本地（有 NVIDIA GPU）

```bash
pip install ultralytics
yolo detect train data=datasets/aimaterials/data.yaml model=yolov8n.pt epochs=100 imgsz=640 batch=8
```

### 方式 B：Google Colab（推荐，免费 T4）

上传 `datasets/aimaterials` 到 Google Drive，新建 Colab Notebook：

```python
!pip install ultralytics
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.train(data='/content/drive/MyDrive/datasets/aimaterials/data.yaml', epochs=100, imgsz=640, batch=16)
```

训练时间：100  epoch 在 T4 上约 20–40 分钟。

---

## 5. 导出到板端可运行格式

### ONNX（通用，RK3588 CPU 可跑，较慢）

```python
from ultralytics import YOLO
model = YOLO('runs/detect/train/weights/best.pt')
model.export(format='onnx', imgsz=640, half=False)
```

得到 `best.onnx`，拷贝到 `src/perception/models/`。

### RKNN（RK3588 NPU，快，但转换链多一步）

1. 先用 Ultralytics 导出 ONNX：
   ```python
   model.export(format='onnx', imgsz=640, opset=12)
   ```
2. 在笔记本上安装 `rknn-toolkit2`：
   ```bash
   pip install rknn-toolkit2
   ```
3. 用官方脚本把 ONNX 转成 RKNN（INT8 需要校准数据集）：
   ```python
   from rknn.api import RKNN
   rknn = RKNN(verbose=False)
   rknn.load_onnx(model='best.onnx')
   rknn.build(do_quantization=True, dataset='./calibration.txt')
   rknn.export_rknn('best.rknn')
   ```

---

## 6. 在感知管线里启用 YOLO

把模型放到 `src/perception/models/`，修改 `config.json`：

```json
"yolo_detect": {
  "enable": true,
  "model_path": "models/best.onnx",
  "backend": "onnx",
  "conf_threshold": 0.5,
  "nms_threshold": 0.45,
  "input_size": 640,
  "class_map": {
    "red_block": 0,
    "green_block": 1,
    ...
  }
}
```

`backend` 可选 `auto`/`onnx`/`rknn`（`ultralytics` 后端已因 AGPL-3.0 合规要求移除）。

---

## 7. 现场时间估算

| 步骤 | 时间 |
|---|---|
| 采集 200 张图 | 30–60 min |
| 自动生成标签 | 5 min |
| 人工修正标签 | 1–2 h |
| 训练 100 epoch | 30–60 min |
| ONNX/RKNN 导出 | 15–30 min |
| 板上验证 | 15 min |

**总时间：3–5 小时**。如果比赛只剩半天，建议不要全押 YOLO，先把 HSV+模板+ArUco 调到能用，YOLO 作为备份。
