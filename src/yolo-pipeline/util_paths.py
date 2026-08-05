"""全部路径、常量、类别定义 —— 唯一来源，禁止各步骤自行定义。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---- 目录 ----
DATASET_RAW = ROOT / "dataset_raw"          # 输入：原始图片（手机拍摄原图）
TRANSFORMED = ROOT / "dataset_transformed"  # subpipeline-astra-style 产出：Astra 风格图
DATASET = ROOT / "dataset"                  # 输出：YOLO 格式数据集
LOGS = ROOT / "logs"
REPORT = ROOT / "report"
RUNS = ROOT / "runs"                        # 训练输出（ultralytics project dir）

# ---- Astra 风格迁移（subpipeline-astra-style）----
ASTRA_SAMPLES = [
    ROOT.parent / "car_output" / "astra_uvc_latest.jpg",
]

# ---- 类别（唯一来源；index 即 YOLO class id）----
CLASSES = ["blue_cone"]

# ---- 数据门禁常量 ----
MIN_IMAGES = 30                # 少于这个数量不允许进入训练（建议 50-200）
MIN_LABELED_FRACTION = 0.95    # 有标签图片比例下限
VAL_SPLIT = 0.2                # val 比例
MAX_EXCLUDE_FRACTION = 0.10    # 逐条排除预算：坏图/坏标签超过 10% 则步骤 FAIL
MIN_BOX_SIDE = 0.01            # bbox 归一化边长下限（过小视为标注错误）
MAX_BOX_SIDE = 0.95            # bbox 归一化边长上限（过大视为标注错误）

# ---- 训练常量 ----
IMG_SIZE = 640                 # 与板端 Astra 相机 640x480 对齐
MODEL = "yolov8n.pt"
EPOCHS_SMOKE = 3                   # ≥2，冒烟门禁要比较首末 epoch 的 loss
EPOCHS_FULL = 100
BATCH = 8                      # RTX 3050 4GB 安全值；冒烟步骤可探测后下调

# ---- 评估门禁常量 ----
MIN_MAP50 = 0.60               # val mAP50 下限（第一版阈值，首批训练后按实测校准）
BASELINE_MAP50 = 0.0           # 平凡基线：无检测器

# ---- 导出 ----
ONNX_NAME = "best.onnx"
