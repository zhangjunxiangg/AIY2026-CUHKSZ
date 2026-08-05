"""02_validate_dataset —— 标签校验 + train/val 划分 + 生成 data.yaml。

输入：dataset_transformed/ 图片 + 同名 .txt（YOLO 格式：<class> <cx> <cy> <w> <h>，归一化）
门禁：
  - 前驱 01 PASS
  - 标签解析：类别 id 合法、5 列、数值在 [0,1]、边长在 [MIN_BOX_SIDE, MAX_BOX_SIDE]
    （逐条排除坏标签文件，超过预算 FAIL；无标签图片=背景图，允许但计入统计）
  - 有标签图片比例 >= MIN_LABELED_FRACTION
  - 每个类别在 train 和 val 中都至少出现 1 次
产出：dataset/{images,labels}/{train,val}/ + dataset/data.yaml
"""

from __future__ import annotations

import json
import random
import shutil

import util_paths
from util_gate import run_step

IMG_EXTS = {".jpg", ".jpeg", ".png"}


def parse_label(path, num_classes):
    """解析一个 YOLO 标签文件；返回 (boxes, errors)。"""
    boxes, errors = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"行{i + 1}: 列数 {len(parts)} != 5")
            continue
        try:
            cls = int(parts[0])
            vals = [float(v) for v in parts[1:]]
        except ValueError:
            errors.append(f"行{i + 1}: 非数值")
            continue
        if not (0 <= cls < num_classes):
            errors.append(f"行{i + 1}: 类别 id {cls} 越界 [0,{num_classes})")
            continue
        if not all(0.0 <= v <= 1.0 for v in vals):
            errors.append(f"行{i + 1}: 坐标越界 [0,1]: {vals}")
            continue
        w, h = vals[2], vals[3]
        if not (util_paths.MIN_BOX_SIDE <= w <= util_paths.MAX_BOX_SIDE
                and util_paths.MIN_BOX_SIDE <= h <= util_paths.MAX_BOX_SIDE):
            errors.append(f"行{i + 1}: bbox 边长异常 w={w:.4f} h={h:.4f}")
            continue
        boxes.append([cls] + vals)
    return boxes, errors


def main(step):
    step.gate_predecessor("01_inspect_dataset")

    raw = util_paths.TRANSFORMED
    imgs = sorted(p for p in raw.rglob("*") if p.suffix.lower() in IMG_EXTS)
    step.gate(len(imgs) > 0, "dataset_transformed/ 中存在图片")

    valid, excluded, unlabeled = [], [], []
    class_counts = {c: 0 for c in util_paths.CLASSES}
    t0 = step.now()
    for img in imgs:
        lab = img.with_suffix(".txt")
        if not lab.exists():
            unlabeled.append(img.name)  # 背景图：允许
            valid.append((img, []))
            continue
        boxes, errors = parse_label(lab, len(util_paths.CLASSES))
        if errors:
            excluded.append({"file": lab.name, "errors": errors})
            step.warn(f"[EXCLUDE] {lab.name}: {'; '.join(errors)}")
            continue
        for b in boxes:
            class_counts[util_paths.CLASSES[b[0]]] += 1
        valid.append((img, boxes))
    step.time_phase("parse_labels", step.now() - t0)

    loss = len(excluded) / max(len(imgs), 1)
    step.gate(loss <= util_paths.MAX_EXCLUDE_FRACTION,
              f"坏标签比例 {loss:.1%} <= 预算 {util_paths.MAX_EXCLUDE_FRACTION:.0%}")
    labeled = sum(1 for _, boxes in valid if boxes)
    frac = labeled / max(len(valid), 1)
    step.gate(frac >= util_paths.MIN_LABELED_FRACTION,
              f"有标签图片比例 {frac:.1%} >= {util_paths.MIN_LABELED_FRACTION:.0%}")
    step.log(f"类别框数统计: {class_counts}；背景图 {len(unlabeled)} 张")

    # ---- 划分 + 落盘 ----
    t0 = step.now()
    rng = random.Random(42)
    rng.shuffle(valid)
    n_val = max(1, int(len(valid) * util_paths.VAL_SPLIT))
    splits = {"val": valid[:n_val], "train": valid[n_val:]}
    step.gate(len(splits["train"]) > 0, "train 集非空")

    ds = util_paths.DATASET
    if ds.exists():
        shutil.rmtree(ds)
    for split, items in splits.items():
        (ds / "images" / split).mkdir(parents=True)
        (ds / "labels" / split).mkdir(parents=True)
        for img, boxes in items:
            dst = ds / "images" / split / img.name
            shutil.copy2(img, dst)
            (ds / "labels" / split / (img.stem + ".txt")).write_text(
                "\n".join(" ".join(str(v) for v in b) for b in boxes),
                encoding="utf-8")
    (ds / "data.yaml").write_text(
        f"path: {ds.as_posix()}\n"
        f"train: images/train\nval: images/val\n"
        f"names: {util_paths.CLASSES}\n", encoding="utf-8")
    step.time_phase("write_dataset", step.now() - t0)

    for cls in util_paths.CLASSES:
        for split, items in splits.items():
            n = sum(1 for _, boxes in items for b in boxes
                    if util_paths.CLASSES[b[0]] == cls)
            step.gate(n > 0, f"类别 {cls} 在 {split} 集中至少出现 1 次（实测 {n}）")

    (step.dir / "dataset_stats.json").write_text(json.dumps({
        "train": len(splits["train"]), "val": len(splits["val"]),
        "unlabeled_background": len(unlabeled), "excluded": excluded,
        "class_counts": class_counts}, ensure_ascii=False, indent=1), encoding="utf-8")
    step.log(f"dataset 就绪: train={len(splits['train'])} val={len(splits['val'])}")


if __name__ == "__main__":
    run_step("02_validate_dataset", main)
