#!/usr/bin/env python3
"""02_evaluate_filter: run the filter chain offline on the captured baseline.

Executes on the board CPU (same hardware as deployment) so timing is real.
Produces metrics raw vs filtered, a side-by-side comparison video, and gates:
  - median temporal std reduced >= 50%
  - valid ratio drop <= 2 percentage points
  - speckle clusters reduced >= 70%
  - filter time p95 <= 15 ms/frame
Usage: 02_evaluate_filter.py <out_root>
"""

import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util_gate import Step
from util_filter import (DepthFilter, colorize, speckle_clusters,
                         temporal_std, valid_ratio)


def main(out_root):
    step = Step(out_root, "02_evaluate_filter")
    step.require_predecessor(out_root, "01_capture_baseline")

    seq_path = os.path.join(out_root, "depth_seq.npy")
    seq = np.load(seq_path)
    step.log(f"loaded {seq.shape} from {seq_path}")

    with step.timeit("metrics_raw"):
        raw = {"temporal": temporal_std(seq), "valid_ratio": valid_ratio(seq),
               "speckles": speckle_clusters(seq)}
    step.log(f"raw: {json.dumps(raw)}")

    filt = DepthFilter()
    times = []
    out = np.empty_like(seq)
    with step.timeit("filter_all"):
        for i, frame in enumerate(seq):
            t0 = time.perf_counter()
            out[i] = filt.process(frame)
            times.append((time.perf_counter() - t0) * 1000.0)
    p95 = float(np.percentile(times, 95))
    mean_ms = float(np.mean(times))
    step.log(f"filter time mean={mean_ms:.2f}ms p95={p95:.2f}ms")

    with step.timeit("metrics_filtered"):
        flt = {"temporal": temporal_std(out), "valid_ratio": valid_ratio(out),
               "speckles": speckle_clusters(out)}
    step.log(f"filtered: {json.dumps(flt)}")

    with step.timeit("write_compare_video"):
        h, w = seq.shape[1:]
        vw = cv2.VideoWriter(os.path.join(out_root, "compare_depth.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), 10, (w * 2, h))
        font = cv2.FONT_HERSHEY_SIMPLEX
        for i in range(len(seq)):
            left = colorize(seq[i])
            right = colorize(out[i])
            cv2.putText(left, "raw", (8, 24), font, 0.7, (255, 255, 255), 2)
            cv2.putText(right, "filtered", (8, 24), font, 0.7, (255, 255, 255), 2)
            vw.write(np.hstack([left, right]))
        vw.release()

    metrics = {"raw": raw, "filtered": flt,
               "filter_ms": {"mean": mean_ms, "p95": p95},
               "params": filt.params()}
    with open(os.path.join(out_root, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)

    std_drop = 1.0 - flt["temporal"]["median_std_mm"] / max(
        raw["temporal"]["median_std_mm"], 1e-9)
    vratio_drop_pp = (raw["valid_ratio"] - flt["valid_ratio"]) * 100.0
    speck_drop = 1.0 - flt["speckles"] / max(raw["speckles"], 1e-9)

    step.gate(std_drop >= 0.50, "temporal std reduction >= 50%",
              f"{std_drop * 100:.1f}%", ">=50%")
    step.gate(vratio_drop_pp <= 2.0, "valid ratio drop <= 2pp",
              f"{vratio_drop_pp:.2f}pp", "<=2pp")
    step.gate(speck_drop >= 0.70, "speckle reduction >= 70%",
              f"{speck_drop * 100:.1f}%", ">=70%")
    step.gate(p95 <= 15.0, "filter time p95 <= 15ms", f"{p95:.2f}ms", "<=15ms")
    step.gate(flt["valid_ratio"] >= 0.05, "filtered still has depth",
              round(flt["valid_ratio"], 4), ">=0.05")

    step.finish("PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/df/out")
