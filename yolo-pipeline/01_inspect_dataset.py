"""01_inspect_dataset —— 原始数据检查。

输入：dataset_transformed/（subpipeline-astra-style 产出的 Astra 风格图）
前置门禁：subpipeline 03_verify 必须 PASS
门禁：
  - 目录存在且非空
  - 图片总数 >= MIN_IMAGES
  - 每张图可解码（逐条排除，超过 MAX_EXCLUDE_FRACTION 则 FAIL）
  - 报告分辨率分布（不门禁，供后续参考）
产出：logs/01_inspect_dataset/inspect.json（合格图片清单）
"""

from __future__ import annotations

import json

import cv2
import numpy as np

import util_paths
from util_gate import run_step

EXTS = {".jpg", ".jpeg", ".png"}


def main(step):
    # 父级集成门禁：风格迁移子管线必须先 PASS（输入是转换后的图，不是手机原图）
    sub_status = util_paths.LOGS / "03_verify" / "STATUS.txt"
    step.gate(sub_status.exists() and sub_status.read_text().strip() == "PASS",
              f"subpipeline-astra-style 03_verify STATUS=PASS（实测: "
              f"{sub_status.read_text().strip() if sub_status.exists() else '缺失'}）")

    raw = util_paths.TRANSFORMED
    step.gate(raw.is_dir(), f"dataset_transformed/ 目录存在（实测: {raw} 不存在）")

    files = sorted(p for p in raw.rglob("*") if p.suffix.lower() in EXTS)
    step.log(f"发现图片 {len(files)} 张")
    step.gate(len(files) >= util_paths.MIN_IMAGES,
              f"图片数量 {len(files)} >= 最小要求 {util_paths.MIN_IMAGES}")

    ok, excluded, sizes = [], [], {}
    t0 = step.now()
    for f in files:
        try:
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None or img.size == 0:
                raise ValueError("decode returned None")
            ok.append(str(f.relative_to(raw)))
            key = f"{img.shape[1]}x{img.shape[0]}"
            sizes[key] = sizes.get(key, 0) + 1
        except Exception as e:  # 逐条排除：坏图是设计内行为
            excluded.append({"file": str(f.relative_to(raw)), "reason": str(e)})
            step.warn(f"[EXCLUDE] {f.name}: {e}")
    step.time_phase("decode_all", step.now() - t0)

    loss = len(excluded) / max(len(files), 1)
    step.gate(loss <= util_paths.MAX_EXCLUDE_FRACTION,
              f"坏图比例 {loss:.1%} <= 预算 {util_paths.MAX_EXCLUDE_FRACTION:.0%}"
              f"（排除 {len(excluded)}/{len(files)}）")
    step.gate(len(ok) >= util_paths.MIN_IMAGES,
              f"合格图片 {len(ok)} >= 最小要求 {util_paths.MIN_IMAGES}")

    step.log(f"分辨率分布: {sizes}")
    (step.dir / "inspect.json").write_text(json.dumps(
        {"total": len(files), "ok": ok, "excluded": excluded, "sizes": sizes},
        ensure_ascii=False, indent=1), encoding="utf-8")
    step.log(f"合格 {len(ok)} 张，排除 {len(excluded)} 张，清单写入 inspect.json")


if __name__ == "__main__":
    run_step("01_inspect_dataset", main)
