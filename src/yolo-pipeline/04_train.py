"""04_train —— 完整训练。

门禁：
  - 前驱 02 PASS（不得在未经校验的数据上训练）
  - 前驱 03 PASS（链路已冒烟）
  - data.yaml 存在且类别与 util_paths.CLASSES 一致
  - 训练产出 best.pt 与 last.pt（保留最优而非最后，由 ultralytics 保证）
产出：runs/train/weights/best.pt
"""

from __future__ import annotations

import util_paths
from util_gate import run_step


def main(step):
    step.gate_predecessor("02_validate_dataset")
    step.gate_predecessor("03_smoke_train")

    data_yaml = util_paths.DATASET / "data.yaml"
    step.gate(data_yaml.exists(), f"data.yaml 存在（{data_yaml}）")
    content = data_yaml.read_text(encoding="utf-8")
    step.gate(str(util_paths.CLASSES) in content,
              f"data.yaml 类别与 util_paths.CLASSES 一致（{util_paths.CLASSES}）")

    from ultralytics import YOLO
    model = YOLO(util_paths.MODEL)
    step.log(f"开始完整训练: epochs={util_paths.EPOCHS_FULL} "
             f"imgsz={util_paths.IMG_SIZE} batch={util_paths.BATCH}")
    t0 = step.now()
    model.train(data=str(data_yaml), epochs=util_paths.EPOCHS_FULL,
                imgsz=util_paths.IMG_SIZE, batch=util_paths.BATCH,
                project=str(util_paths.RUNS), name="train", verbose=False)
    step.time_phase("train_full", step.now() - t0)

    best = util_paths.RUNS / "train" / "weights" / "best.pt"
    last = util_paths.RUNS / "train" / "weights" / "last.pt"
    step.gate(best.exists(), f"best.pt 存在（{best}）")
    step.gate(last.exists(), f"last.pt 存在（{last}）")
    step.log("完整训练完成，best.pt 已保留")


if __name__ == "__main__":
    run_step("04_train", main)
