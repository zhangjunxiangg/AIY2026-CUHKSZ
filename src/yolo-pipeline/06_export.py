"""06_export —— 导出 ONNX 并用 onnxruntime 重载推理验证（模拟板端加载方式）。

门禁：
  - 前驱 05 PASS
  - best.onnx 导出成功
  - onnxruntime 可加载，输出张量形状合法（N, C, S）
  - 对一张 val 图推理不抛异常
产出：runs/train/weights/best.onnx（复制到 models/best.onnx 供 perception 接入）
"""

from __future__ import annotations

import shutil

import util_paths
from util_gate import run_step


def main(step):
    step.gate_predecessor("05_evaluate")
    best = util_paths.RUNS / "train" / "weights" / "best.pt"
    step.gate(best.exists(), f"best.pt 存在（{best}）")

    from ultralytics import YOLO
    model = YOLO(str(best))
    t0 = step.now()
    onnx_path = model.export(format="onnx", imgsz=util_paths.IMG_SIZE,
                             half=False, verbose=False)
    step.time_phase("export_onnx", step.now() - t0)
    step.gate(str(onnx_path).endswith(util_paths.ONNX_NAME),
              f"ONNX 导出（{onnx_path}）")

    import numpy as np
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path))
    inp = sess.get_inputs()[0]
    step.gate(list(inp.shape[2:]) == [util_paths.IMG_SIZE, util_paths.IMG_SIZE],
              f"ONNX 输入尺寸 {inp.shape} 符合 {util_paths.IMG_SIZE}")

    val_imgs = sorted((util_paths.DATASET / "images" / "val").glob("*"))
    step.gate(len(val_imgs) > 0, "val 集存在图片用于推理验证")
    import cv2
    img = cv2.imdecode(np.fromfile(str(val_imgs[0]), dtype=np.uint8), cv2.IMREAD_COLOR)
    img = cv2.resize(img, (util_paths.IMG_SIZE, util_paths.IMG_SIZE))
    blob = img.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    t0 = step.now()
    out = sess.run(None, {inp.name: blob})[0]
    step.time_phase("infer_1img", step.now() - t0)
    step.gate(out.ndim == 3 and out.shape[0] == 1,
              f"推理输出形状合法（实测 {out.shape}）")
    step.log(f"onnxruntime 推理验证通过，输出 {out.shape}")

    models_dir = util_paths.ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    shutil.copy2(onnx_path, models_dir / util_paths.ONNX_NAME)
    step.log(f"已复制到 {models_dir / util_paths.ONNX_NAME}（供 perception/config.json 接入）")


if __name__ == "__main__":
    run_step("06_export", main)
