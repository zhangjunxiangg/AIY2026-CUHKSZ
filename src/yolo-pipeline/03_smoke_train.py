"""03_smoke_train —— 冒烟训练：证明 GPU/框架/训练/保存链路可用（不依赖业务数据）。

用 ultralytics 自带 coco8（8 张图）跑 1 epoch。
门禁：
  - ultralytics/torch 可导入，CUDA 可用（不可用则 FAIL 并说明——CPU 训练 100 epoch 不现实）
  - 训练完成后 checkpoint 存在
  - 最终 train loss < 初始 train loss（真实学习信号，非"跑完了事"；
    因此 EPOCHS_SMOKE 必须 >= 2，单 epoch 时 results.csv 只有一行无法比较）
产出：runs/smoke/weights/best.pt
"""

from __future__ import annotations

import csv

import util_paths
from util_gate import run_step


def main(step):
    import torch
    step.gate(torch.cuda.is_available(),
              f"CUDA 可用（实测: False, torch {torch.__version__}）")
    step.log(f"GPU: {torch.cuda.get_device_name(0)}")

    from ultralytics import YOLO
    model = YOLO(util_paths.MODEL)

    t0 = step.now()
    model.train(data="coco8.yaml", epochs=util_paths.EPOCHS_SMOKE,
                imgsz=util_paths.IMG_SIZE, batch=util_paths.BATCH,
                project=str(util_paths.RUNS), name="smoke", verbose=False)
    step.time_phase("train_1epoch", step.now() - t0)

    ckpt = util_paths.RUNS / "smoke" / "weights" / "best.pt"
    step.gate(ckpt.exists(), f"checkpoint 存在（{ckpt}）")

    results_csv = util_paths.RUNS / "smoke" / "results.csv"
    step.gate(results_csv.exists(), "results.csv 存在")
    rows = list(csv.DictReader(open(results_csv, encoding="utf-8")))
    loss_col = [c for c in rows[0] if "box_loss" in c][0]
    first, last = float(rows[0][loss_col]), float(rows[-1][loss_col])
    step.gate(last < first, f"loss 下降: {first:.4f} -> {last:.4f}")
    step.log("冒烟训练通过：GPU 链路、训练循环、checkpoint 保存均可用")


if __name__ == "__main__":
    run_step("03_smoke_train", main)
