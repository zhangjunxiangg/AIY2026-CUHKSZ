"""07_report —— 从 logs/ 痕迹生成最终报告（不从记忆写报告）。

门禁：
  - 汇总各步骤 STATUS；任何 FAIL 都在报告中点名
  - report/REPORT.md 生成
"""

from __future__ import annotations

import json

import util_paths
from util_gate import run_step

STEPS = ["01_inspect_dataset", "02_validate_dataset", "03_smoke_train",
         "04_train", "05_evaluate", "06_export"]


def main(step):
    lines = ["# YOLO 训练管线报告", ""]
    lines.append("| 步骤 | 状态 |")
    lines.append("|---|---|")
    n_pass = 0
    for s in STEPS:
        f = util_paths.LOGS / s / "STATUS.txt"
        status = f.read_text().strip() if f.exists() else "未运行"
        n_pass += status == "PASS"
        lines.append(f"| {s} | {status} |")
    lines.append("")

    metrics_file = util_paths.LOGS / "05_evaluate" / "metrics.json"
    if metrics_file.exists():
        m = json.loads(metrics_file.read_text(encoding="utf-8"))
        lines += ["## 评估指标", "",
                  f"- mAP50: **{m['mAP50']:.4f}**（阈值 {m['threshold_mAP50']}，"
                  f"基线 {m['baseline_mAP50']}）",
                  f"- mAP50-95: {m['mAP50-95']:.4f}",
                  f"- Precision: {m['precision']:.4f} / Recall: {m['recall']:.4f}", ""]

    stats_file = util_paths.LOGS / "02_validate_dataset" / "dataset_stats.json"
    if stats_file.exists():
        s = json.loads(stats_file.read_text(encoding="utf-8"))
        lines += ["## 数据集", "",
                  f"- train {s['train']} / val {s['val']}，"
                  f"背景图 {s['unlabeled_background']}，排除 {len(s['excluded'])}",
                  f"- 类别框数: {s['class_counts']}", ""]

    onnx = util_paths.ROOT / "models" / util_paths.ONNX_NAME
    lines += ["## 产物", "",
              f"- 模型: `{onnx}`（{'存在' if onnx.exists() else '缺失'}）",
              f"- 接入: perception/config.json 的 yolo_detect.model_path 指向上述文件", ""]

    util_paths.REPORT.mkdir(exist_ok=True)
    (util_paths.REPORT / "REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8")
    step.log(f"报告已生成: {util_paths.REPORT / 'REPORT.md'}（{n_pass}/{len(STEPS)} 步 PASS）")


if __name__ == "__main__":
    run_step("07_report", main)
