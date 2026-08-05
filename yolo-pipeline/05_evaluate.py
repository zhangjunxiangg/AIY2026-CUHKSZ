"""05_evaluate —— val 集评估，mAP 门禁（对照平凡基线）。

门禁：
  - 前驱 04 PASS
  - mAP50 >= MIN_MAP50（且 > BASELINE_MAP50，即优于无检测器基线）
产出：logs/05_evaluate/metrics.json（含原始指标，供复绘）
"""

from __future__ import annotations

import json

import util_paths
from util_gate import run_step


def main(step):
    step.gate_predecessor("04_train")
    best = util_paths.RUNS / "train" / "weights" / "best.pt"
    step.gate(best.exists(), f"best.pt 存在（{best}）")

    from ultralytics import YOLO
    model = YOLO(str(best))
    t0 = step.now()
    metrics = model.val(data=str(util_paths.DATASET / "data.yaml"),
                        imgsz=util_paths.IMG_SIZE, verbose=False)
    step.time_phase("val", step.now() - t0)

    map50 = float(metrics.box.map50)
    map5095 = float(metrics.box.map)
    precision = float(metrics.box.mp)
    recall = float(metrics.box.mr)
    step.log(f"mAP50={map50:.4f} mAP50-95={map5095:.4f} "
             f"P={precision:.4f} R={recall:.4f}")

    step.gate(map50 > util_paths.BASELINE_MAP50,
              f"mAP50 {map50:.4f} > 基线 {util_paths.BASELINE_MAP50}")
    step.gate(map50 >= util_paths.MIN_MAP50,
              f"mAP50 {map50:.4f} >= 阈值 {util_paths.MIN_MAP50}")

    (step.dir / "metrics.json").write_text(json.dumps({
        "mAP50": map50, "mAP50-95": map5095,
        "precision": precision, "recall": recall,
        "baseline_mAP50": util_paths.BASELINE_MAP50,
        "threshold_mAP50": util_paths.MIN_MAP50,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    run_step("05_evaluate", main)
